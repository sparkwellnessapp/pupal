# TestGrader Agent Engineering Guide

## Executive Summary

This document guides LangChain/LangGraph engineers through implementing the TestGrader Agent using the `testgrader_agent_north_star.json` specification. The spec is **implementation-ready** — every design decision has been made, every edge case documented, and every invariant defined.

### What You're Building

A **LangGraph agent** that grades student test answers against a compiled rubric contract. The agent:

1. Receives `StudentAnswer[]` + `GradingRubricContract` as input
2. Processes questions sequentially, criteria sequentially within each question
3. Makes **1 LLM call per criterion** (evaluating all rules in that criterion)
4. Implements a **ReAct self-correction loop** for quote validation
5. Produces a complete `GradedTestDraft` with evidence citations
6. Handles failures gracefully (skip + flag, never crash the batch)

### Key Architecture Decisions (Already Made)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Processing order | Sequential (Q→C→R) | Simplicity, debuggability |
| LLM call granularity | 1 per criterion | Balance cost vs. context |
| Error handling | Graceful degradation | Always produce a draft |
| Quote validation | Fuzzy Levenshtein ≤ 0.15 | Handle OCR errors |
| Retry strategy | Max 2 retries per criterion | Cost/latency balance |
| State persistence | PostgreSQL (grading_sessions) | Survives browser close |

### Your Implementation Checklist

```
□ Phase 1: State & Types (Day 1)
  □ Define GradingAgentState TypedDict
  □ Create Pydantic models for LLM I/O
  □ Set up grading_sessions table

□ Phase 2: Graph Skeleton (Day 2)
  □ Implement all 8 nodes as stubs
  □ Wire up edges and conditional routing
  □ Verify graph compiles and runs empty

□ Phase 3: Core Logic (Days 3-5)
  □ Implement initialize node (DB loading)
  □ Implement evaluate_criterion_llm (LLM call)
  □ Implement validate_response (quote validation)
  □ Implement ReAct retry loop

□ Phase 4: Integration (Day 6)
  □ Wire to existing API endpoint
  □ Add progress tracking (real-time updates)
  □ Implement graceful degradation

□ Phase 5: Testing (Days 7-8)
  □ Run all 8 competency question tests
  □ Run adversarial tests
  □ Verify latency < 40s on real data
```

---

## Table of Contents: How to Use the JSON Spec

The JSON spec has 14 top-level sections. Here's **when and why** you'll reference each:

### 🎯 Before Writing Any Code

| Section | What It Tells You | When to Read |
|---------|-------------------|--------------|
| `problem_statement` | The one-paragraph mission | First thing, internalize the goal |
| `success_criteria_failure_modes_and_constraints` | What "done" looks like, what to avoid | Before architecture decisions |
| `assumptions_open_questions_and_risks` | Known unknowns, edge cases | Before estimating effort |

### 📐 When Defining Types & State

| Section | What It Tells You | Implementation Artifact |
|---------|-------------------|------------------------|
| `agent_state_schema` | Every field in `GradingAgentState` | `state.py` TypedDict |
| `input_output_and_acceptance_contracts` | Input validation, output structure | Pydantic models, validators |
| `decision_graph_and_state_invariants` | What must always be true | Assertion checks, unit tests |

### 🔧 When Building the Graph

| Section | What It Tells You | Implementation Artifact |
|---------|-------------------|------------------------|
| `agent_blueprint.nodes` | Each node's goal, inputs, outputs, routing | Node functions |
| `agent_blueprint.graph_edges` | How nodes connect | `StateGraph.add_edge()` calls |
| `workflow_and_cognitive_task_map` | Step-by-step flow with handoffs | Graph topology verification |

### 🤖 When Writing LLM Integration

| Section | What It Tells You | Implementation Artifact |
|---------|-------------------|------------------------|
| `appendix_llm_prompt_template` | Exact prompt structure | Prompt template string |
| `tooling_plan.tools` | Tool signatures and purposes | LangChain tools |
| `context_and_knowledge_plan` | What context to include, citation rules | Prompt construction logic |

### 🧪 When Writing Tests

| Section | What It Tells You | Implementation Artifact |
|---------|-------------------|------------------------|
| `competency_questions` | 8 critical scenarios with expected behavior | Test cases |
| `evaluation_plan.adversarial_test_cases` | Edge cases and attack vectors | Stress tests |
| `evaluation_plan.monitoring_signals` | What to measure in production | Metrics, alerts |

### 🗄️ When Setting Up Infrastructure

| Section | What It Tells You | Implementation Artifact |
|---------|-------------------|------------------------|
| `tooling_plan.audit_logging` | What events to log | Logging statements |
| `tooling_plan.failure_modes_and_fallback` | How to handle each failure | Try/catch blocks, fallbacks |
| `mvp_build_plan_and_phased_roadmap` | What's in scope vs. deferred | Sprint planning |

---

## Quick Reference: JSON Paths for Common Tasks

### "I need to define the state schema"
```python
# Look at: spec["agent_state_schema"]
# Sections: immutable_context, progress_tracking, accumulated_results, 
#           react_loop_state, quality_signals, error_state, timing_and_observability
```

### "I need to implement a specific node"
```python
# Look at: spec["agent_blueprint"]["nodes"][i]
# Fields: name, goal, inputs, output_format, acceptance_checks, 
#         failure_modes, routing
```

### "I need to wire the graph edges"
```python
# Look at: spec["agent_blueprint"]["graph_edges"]
# Each edge: {from, to, condition}
```

### "I need to write the LLM prompt"
```python
# Look at: spec["appendix_llm_prompt_template"]
# Contains: template string with placeholders
```

### "I need to validate the output"
```python
# Look at: spec["input_output_and_acceptance_contracts"]["acceptance_contract"]
# Sections: hard_validators (must pass), soft_validators (quality checks)
```

### "I need to write a test for X scenario"
```python
# Look at: spec["competency_questions"]
# Each CQ: id, name, question, expected_answer/behavior, passing_criteria
```

### "I need to handle failure case Y"
```python
# Look at: spec["tooling_plan"]["failure_modes_and_fallback"]
# Also: spec["decision_graph_and_state_invariants"]["decision_nodes"]
```

---

## Implementation Patterns

### Pattern 1: State TypedDict from Spec

```python
# Extract from spec["agent_state_schema"]
from typing import TypedDict, List, Dict, Any, Optional

class GradingAgentState(TypedDict):
    # Immutable context (from spec.agent_state_schema.immutable_context)
    session_id: str
    contract: Dict[str, Any]
    contract_version: str
    student_answers: List[Dict[str, Any]]
    answer_lookup: Dict[str, Dict[str, Any]]
    teacher_id: str
    student_name: str
    filename: Optional[str]
    
    # Progress tracking (from spec.agent_state_schema.progress_tracking)
    status: str  # "initialized" | "grading" | "completed" | "failed"
    current_question_idx: int
    current_criterion_idx: int
    total_questions: int
    total_criteria: int
    completed_criteria: int
    
    # ... continue for all sections
```

### Pattern 2: Node Function from Blueprint

```python
# Extract from spec["agent_blueprint"]["nodes"][4] (evaluate_criterion_llm)
def evaluate_criterion_llm(state: GradingAgentState) -> Dict[str, Any]:
    """
    Goal: Call LLM to evaluate all rules in criterion
    
    Inputs (from spec):
    - current_criterion (description, rules with levels)
    - current_student_answer (content)
    - validation_failures (if retry)
    """
    criterion = state["current_criterion"]
    answer = state["current_student_answer"]
    failures = state.get("validation_failures", [])
    
    # Build prompt from spec["appendix_llm_prompt_template"]
    prompt = build_criterion_prompt(criterion, answer, failures)
    
    # Call LLM
    start = time.time()
    response = llm.invoke(prompt)
    latency_ms = int((time.time() - start) * 1000)
    
    # Return output format (from spec)
    return {
        "pending_evaluation": parse_llm_response(response),
        "llm_calls_count": state["llm_calls_count"] + 1,
        "total_llm_latency_ms": state["total_llm_latency_ms"] + latency_ms,
    }
```

### Pattern 3: Conditional Routing from Edges

```python
# Extract from spec["agent_blueprint"]["graph_edges"]
def route_after_validation(state: GradingAgentState) -> str:
    """
    Routing logic from spec.agent_blueprint.graph_edges
    where from="validate_response"
    """
    validation_failures = state.get("validation_failures", [])
    retry_count = state.get("criterion_retry_count", 0)
    max_retries = state.get("max_criterion_retries", 2)
    
    if not validation_failures:
        return "accept"  # → select_next_criterion
    elif retry_count < max_retries:
        return "retry"   # → evaluate_criterion_llm
    else:
        return "skip"    # → select_next_criterion (with flags)

# Wire it up
workflow.add_conditional_edges(
    "validate_response",
    route_after_validation,
    {"accept": "select_next_criterion", 
     "retry": "evaluate_criterion_llm", 
     "skip": "select_next_criterion"}
)
```

### Pattern 4: Test Case from Competency Question

```python
# Extract from spec["competency_questions"][3] (CQ-4: closed_world_enforcement)
@pytest.mark.asyncio
async def test_closed_world_enforcement():
    """
    CQ-4: If the LLM returns selected_level_id: 'excellent' but the 
    rule only has ['pass', 'fail'], does the agent reject and retry?
    """
    # Arrange: Mock LLM to return invalid level first, valid second
    mock_responses = [
        {"rule_evaluations": [{"rule_id": "r0", "selected_level_id": "excellent", ...}]},  # Invalid
        {"rule_evaluations": [{"rule_id": "r0", "selected_level_id": "pass", ...}]},       # Valid
    ]
    
    # Act
    result = await run_agent_with_mock_llm(contract, answers, mock_responses)
    
    # Assert (from spec.competency_questions[3].passing_criteria)
    assert result["status"] == "completed"
    assert result["llm_calls_count"] >= 2  # Retry occurred
    assert "excellent" not in str(result["graded_test_draft"])  # Invalid level never persisted
```

### Pattern 5: Invariant Validation

```python
# Extract from spec["decision_graph_and_state_invariants"]["state_invariants"]
def validate_invariants(draft: Dict[str, Any], contract: Dict[str, Any]) -> List[str]:
    """Validate INV-A1 through INV-A6"""
    violations = []
    
    # INV-A1: ClosedWorldEnforcement
    all_rule_ids = extract_all_rule_ids(contract)
    all_level_ids = extract_all_level_ids(contract)
    for qo in draft["question_outcomes"]:
        for co in qo["criterion_outcomes"]:
            for ro in co["rule_outcomes"]:
                if ro["rule_id"] not in all_rule_ids:
                    violations.append(f"INV-A1: Unknown rule_id {ro['rule_id']}")
                if ro["selected_level_id"] not in all_level_ids.get(ro["rule_id"], []):
                    violations.append(f"INV-A1: Invalid level_id {ro['selected_level_id']}")
    
    # INV-A2: PointsConsistency
    total_earned = sum(qo["points_earned"] for qo in draft["question_outcomes"])
    if total_earned != draft["total_points_earned"]:
        violations.append(f"INV-A2: Total mismatch {total_earned} != {draft['total_points_earned']}")
    
    # ... continue for INV-A3 through INV-A6
    
    return violations
```

---

## Common Pitfalls & How the Spec Prevents Them

| Pitfall | Where Spec Addresses It |
|---------|------------------------|
| Hallucinated quotes | `decision_graph.quotations_valid` + ReAct retry loop |
| Invalid level selection | `decision_graph.llm_response_valid` + closed-world check |
| Partial draft saved on failure | `output_contract.guarantees.all_or_nothing` |
| Cross-student data leakage | `context_and_knowledge_plan.safety_and_leakage_prevention` |
| Batch inconsistency | `state_invariants.INV-A6` (ContractVersionLock) |
| Missing evidence | `acceptance_contract.hard_validators` (every RuleOutcome has EvidenceClaim) |
| Timeout on large tests | `constraints.max_latency_per_test` + progress tracking |

---

## File Structure Recommendation

```
app/
├── agents/
│   └── test_grader/
│       ├── __init__.py
│       ├── state.py              # GradingAgentState TypedDict
│       ├── models.py             # Pydantic models for LLM I/O
│       ├── nodes/
│       │   ├── __init__.py
│       │   ├── initialize.py
│       │   ├── select_next_question.py
│       │   ├── check_student_answer.py
│       │   ├── select_next_criterion.py
│       │   ├── evaluate_criterion_llm.py
│       │   ├── validate_response.py
│       │   ├── finalize_question.py
│       │   └── assemble_draft.py
│       ├── graph.py              # StateGraph definition
│       ├── prompts.py            # LLM prompt templates
│       ├── validators.py         # Quote validation, invariant checks
│       └── utils.py              # Levenshtein, helpers
├── tests/
│   └── agents/
│       └── test_grader/
│           ├── test_competency_questions.py  # CQ-1 through CQ-8
│           ├── test_adversarial.py           # Edge cases
│           └── fixtures/
│               ├── sample_contract.json
│               └── sample_answers.json
```

---

## Summary: Your North Star Usage Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     HOW TO USE THE JSON SPEC                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. START WITH THE GOAL                                                     │
│     Read: problem_statement, success_criteria                               │
│     Understand what "done" means before coding                              │
│                                                                             │
│  2. DEFINE YOUR TYPES                                                       │
│     Read: agent_state_schema, input_output_and_acceptance_contracts         │
│     Create: TypedDict, Pydantic models, DB schema                           │
│                                                                             │
│  3. BUILD THE SKELETON                                                      │
│     Read: agent_blueprint.nodes, agent_blueprint.graph_edges                │
│     Create: Empty node functions, StateGraph with all edges                 │
│                                                                             │
│  4. IMPLEMENT NODE BY NODE                                                  │
│     Read: agent_blueprint.nodes[i] for each node                            │
│     Create: Full implementation matching spec exactly                       │
│                                                                             │
│  5. ADD THE LLM INTEGRATION                                                 │
│     Read: appendix_llm_prompt_template, context_and_knowledge_plan          │
│     Create: Prompt builder, response parser                                 │
│                                                                             │
│  6. IMPLEMENT VALIDATION                                                    │
│     Read: decision_graph_and_state_invariants, acceptance_contract          │
│     Create: Quote validator, invariant checker, ReAct loop                  │
│                                                                             │
│  7. TEST AGAINST COMPETENCY QUESTIONS                                       │
│     Read: competency_questions, evaluation_plan                             │
│     Create: Test for each CQ, adversarial tests                             │
│                                                                             │
│  8. VERIFY SUCCESS CRITERIA                                                 │
│     Read: success_criteria_failure_modes_and_constraints                    │
│     Verify: Latency < 40s, accuracy > 90%, 100% valid quotes                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

**The spec is your single source of truth. When in doubt, check the JSON.**
