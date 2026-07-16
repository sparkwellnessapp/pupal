# RubricAgent Engineering Guide

**What this document is**: The north star for AI engineers implementing Vivi's rubric extraction, classification, and enhancement pipeline. It defines the ontological structure, the agent architecture, the LLM orchestration, and the quality principles that govern every design decision.

**What the rubric agent produces**: A complete, normalized `rubric_draft` — a structured representation of a teacher's exam rubric that is ideal for automated test grading by the TestGrader agent. Everything in this pipeline exists to serve that downstream consumer.

---

## 1. The Rubric Ontology

### 1.1 Why This Structure Exists

The TestGrader agent receives a student's handwritten exam and a rubric_draft. It must, for every question the student answered, decide how many points the student earned and why. The rubric structure must make this decision process **mechanical and auditable**: the grader walks the tree, evaluates each node, and the points fall out deterministically.

This means the rubric must decompose "grade this question" into a tree of increasingly specific, independently evaluable decisions.

### 1.2 The Complete Hierarchy

```
Rubric
├── test_title: str                          # Broad subject domain ("בוחן לולאות For")
├── programming_language: str
├── numeric_policy: { precision, rounding_mode, sum_tolerance }
│
└── Question[]
    ├── question_id, question_number
    ├── total_points: float
    ├── question_purpose: str                # What knowledge/skills this tests
    ├── context_text: str                    # Problem setup, definitions, background (includes all code)
    ├── example_solution: str?               # Only when explicitly labeled (e.g. "פתרון לדוגמה")
    │
    ├── SubQuestion[]?                       # Present when question has parts (א, ב, ג...)
    │   ├── sub_question_id: str
    │   ├── full_text: str                   # The task text ("כתבו פעולה...")
    │   └── points: float
    │
    └── Criterion[]
        ├── criterion_id: str                # e.g., "q2.c0"
        ├── description: str                 # What this criterion measures
        ├── points: float                    # Total points for this criterion
        ├── belongs_to_sub_question: str?    # null if direct question-level
        ├── is_new: bool                     # Added by enhancement (not in original table)
        │
        └── Rule[]
            ├── rule_id: str                 # e.g., "q2.c0.r0"
            ├── description: str             # The specific aspect being measured
            ├── max_points: float
            ├── scoring_type: "binary" | "discrete_levels"
            │
            └── Level[]
                ├── level_id: str            # "none", "partial", "full" (or custom)
                ├── level_order: int          # 0 = worst, N = best
                ├── points: float            # Points awarded at this level
                └── condition_hint: str      # GRADING INSTRUCTION for TestGrader
```

### 1.3 What Each Layer Answers

| Layer | Question it answers | Who evaluates it |
|-------|-------------------|-----------------|
| **Question** | "What is the student being asked to do?" | Provides context for all below |
| **Sub-question** | "What specific task within the question?" | Scopes criteria to a part |
| **Criterion** | "What aspect of the answer matters?" | Groups related rules |
| **Rule** | "What specific thing must the student get right?" | The unit of measurement |
| **Level** | "How right did the student get it?" | The grading decision point |

### 1.4 The Critical Role of condition_hint

The `condition_hint` on each level is the single most important field for grading quality. It is the **grading instruction** — what the TestGrader agent reads to decide which level to assign for a given rule.

A bad condition_hint:
```
"partially correct"
```

A good condition_hint:
```
"Loop iterates over the array but has an off-by-one error on the upper bound (e.g., uses arr.length instead of arr.length-1, or starts from 1 instead of 0)"
```

The enhancement agent must write condition_hints as if it were writing instructions for a teaching assistant who has never seen this exam before. Specific, concrete, pattern-matchable against student work.

### 1.5 Point Sum Invariants

These must hold at every level of the tree:

```
Σ criterion.points (for a question) == question.total_points
Σ rule.max_points (for a criterion) == criterion.points
For each rule: levels must include a 0-point level and a max_points level
For discrete_levels: level points must be monotonically increasing with level_order
```

These are validated deterministically after every LLM call. Point sum violations are hard failures.

---

## 2. Pipeline Architecture

### 2.1 The Abstract Sequence

```
Upload rubric DOCX
    → [Stage 1] Parse and annotate (deterministic)
    → [Stage 2] Render for LLM (deterministic)  
    → [Stage 3] LLM Classification — builds normalized rubric_draft structure (semantic)
    → [Stage 4] LLM Enhancement — executes ontological chain, completes rubric_draft (semantic)
    → [Stage 5] Validation and type construction (deterministic)
    → [Stage 6] Display in RubricEditor.tsx → Teacher reviews and saves
```

### 2.2 Stage Responsibilities

**Stage 1 — Parse and Annotate**
- Parser: DOCX bytes → DocxDocument tree (paragraphs, tables, shapes with element IDs)
- Annotator: Labels elements with reliable pattern detections only: QUESTION_HEADER, CODE_BLOCK, EXAMPLE_SOLUTION. Sub-question detection is NOT used for classification — the LLM handles that.
- Output: Annotated document tree

**Stage 2 — Render for LLM**
- Converts annotated document tree into clean, LLM-readable text
- Includes lightweight semantic markers: `QUESTION N (pts)` section headers, `[TABLE #N]`, `[SQ: X]` (sub-question hint; next line has original א./סעיף א text), `[EXAMPLE_SOLUTION]...[/EXAMPLE_SOLUTION]`. Code is plain text (no [CODE_BLOCK]).
- Markers are simple and non-noisy — just enough for the LLM to orient itself
- Sub-question annotations are NOT included — the LLM infers these semantically
- Output: Rendered text string

**Stage 3 — LLM Classification**
- Receives rendered text + system prompt with clear principles
- Outputs complete `RubricDraftResponse`: questions with full text content, sub-questions with full text, table type classifications, and row-to-sub-question mappings
- The LLM is the semantic authority — it decides what's a sub-question vs context, maps criteria to sub-questions; all question content (including code) goes in full_text
- Output: `RubricDraftResponse` (the raw rubric_draft — correct structure, raw criteria)

**Stage 4 — LLM Enhancement**
- Executes the 4-step ontological chain (see Section 3)
- Takes the raw rubric_draft and produces the complete rubric_draft with purpose analysis, rebalanced criteria, rules, and scoring levels
- Output: Enhanced rubric_draft with complete rule+level tree

**Stage 5 — Validation and Type Construction**
- Validates all point sum invariants
- Fuzzy-verifies LLM-output text against rendered document (belt-and-suspenders for hallucination detection)
- Constructs final ontology types (Draft → Contract pattern)
- Output: Validated rubric ready for display

**Stage 6 — Teacher Review**
- RubricEditor.tsx displays the rubric_draft
- Teacher can edit criteria, adjust points, modify rules/levels
- Teacher approves and saves
- Output: Final rubric (Contract) ready for grading

### 2.3 The Governing Principle

**LLM leads, deterministic code verifies.**

The LLM handles all semantic work: understanding Hebrew text, distinguishing tasks from definitions, inferring pedagogical intent, writing grading instructions. Deterministic code handles all mechanical work: parsing table cells, summing points, validating invariants, constructing typed objects.

Never let pattern-matching code override or reconstruct what the LLM understood correctly. If you're writing code that reconstructs information the LLM already had, you're going the wrong direction.

---

## 3. The Enhancement Ontological Chain

This is the heart of the rubric agent's intelligence. It must execute in this exact order.

### Step 1 — Understand and Complete

**Input**: Test title, question context_text, sub-question texts, extracted criteria with original points, example solution (if available), programming language.

**The agent's task**: 
- Identify the primary knowledge/skills this question was designed to test, informed by: (a) the test title (broad domain), (b) the question and sub-question texts (specific skills)
- Evaluate: does the current set of criteria fully cover the question's purpose?
- If there are missing criteria — especially ones that measure the core skills the question targets — create them (description only, no rules yet)

**Key reasoning principle**: A criterion is "missing" if there is a significant aspect of what the question tests that no existing criterion measures. For example, if a For-loop question has criteria for "correct output" and "variable naming" but nothing for "loop structure and bounds" — that's a missing criterion on the question's primary skill.

### Step 2 — Evaluate and Rebalance

**Input**: All criteria (original + newly created), question purpose from Step 1.

**The agent's task**:
- Evaluate each criterion's importance relative to the question's purpose
- Reassign point distribution based on this evaluation
- The principle: **criteria that measure the aspects of the student's answer most directly addressing the question's purpose should carry the most weight**

**Key reasoning principle**: Consider a 20-point question on For loops that has 5 criteria. A criterion testing "correct For loop bounds and iteration" is more important to the question's purpose than "code formatting." The point distribution should reflect this — the core-skill criterion gets more points.

**Validation**: Σ rebalanced criteria points == question.total_points (hard constraint).

### Step 3 — Generate Rules

**Input**: Each criterion (with finalized description and points), question purpose, sub-question text.

**The agent's task**:
- For each criterion, identify the distinct measurable aspects — each becomes a rule
- Each rule should measure one specific thing that can be independently evaluated in a student's answer
- A criterion might have 1 rule (if it's already atomic) or 2-5 rules (if it covers multiple aspects)

**Key reasoning principle**: A rule is the unit of measurement. The grading agent evaluates each rule independently. If you find yourself describing a rule that requires the grader to evaluate two separate things at once (e.g., "correct loop bounds AND correct accumulator initialization"), split it into two rules.

**Validation**: Σ rule.max_points == criterion.points (hard constraint).

### Step 4 — Define Scoring Levels

**Input**: Each rule (with description and max_points), question purpose, example solution.

**The agent's task**:
- For each rule, determine scoring granularity:
  - **Binary** if: the aspect is truly pass/fail, OR max_points ≤ 1, OR there's no meaningful intermediate state
  - **Discrete levels** if: the student can demonstrate partial understanding, AND max_points > 1, AND there are nameable intermediate states
- For multi-level rules, define 2-4 levels with graduated point values
- For EVERY level, write a specific `condition_hint`

**Key reasoning principle for condition_hints**: Write them as grading instructions for someone who has never seen this exam. They must be:
- **Specific**: Reference concrete patterns in student code ("uses `<=` instead of `<` in loop bound")
- **Observable**: Based on what the grader can see in the answer, not internal student understanding
- **Exhaustive at the top level**: The "full" level hint should describe what a correct answer looks like for this rule
- **Distinguishing**: Each level's hint must describe something observably different from adjacent levels

**Example of well-defined levels for a "loop bounds" rule (5 points)**:
```
Level "none"    (0 pts):   "Loop does not iterate, or iterates over a hardcoded range 
                            unrelated to the input"
Level "partial" (2.5 pts): "Loop iterates over the input but bounds are incorrect — 
                            off-by-one error, wrong start index, or wrong end condition"  
Level "full"    (5 pts):   "Loop bounds correctly cover the entire required range with 
                            correct start, end, and step values"
```

### LLM Call Architecture Summary

```
┌─────────────────────────────────────────────────────┐
│ Call 1: Question-Level Analysis (Steps 1 + 2)       │
│                                                     │
│ Input:  test_title, context_text, sub_questions,    │
│         raw criteria, example_solution, language     │
│                                                     │
│ Output: question_purpose, complete criteria list     │
│         with rebalanced points                      │
│                                                     │
│ Runs: Once per question                             │
└──────────────────────┬──────────────────────────────┘
                       │ question_purpose + finalized criteria
                       ▼
┌─────────────────────────────────────────────────────┐
│ Call 2: Criterion-Level Rules + Levels (Steps 3 + 4)│
│                                                     │
│ Input:  criterion description + points,             │
│         question_purpose, sub_question text,         │
│         example_solution                            │
│                                                     │
│ Output: rules with scoring_type + levels            │
│         with specific condition_hints               │
│                                                     │
│ Runs: Once per criterion (parallelizable)           │
└─────────────────────────────────────────────────────┘
```

---

## 4. Classification Principles

These principles govern Stage 3 (LLM Classification). They must be embedded in the classification system prompt.

### 4.1 Sub-Questions Are Tasks

A sub-question is always an explicit task for the student. It contains action verbs: "כתבו" (write), "הגדירו" (define), "חשבו" (calculate), "הדפיסו" (print).

Everything else in the question body is `context_text`: class definitions, property lists ("arrEmployees – מערך חד-ממדי"), parameter descriptions, background story. These provide context for the sub-question tasks but are not themselves tasks.

This is the single most important semantic distinction in the classification step.

### 4.2 Complete Text, Not Pointers

The classification LLM outputs complete text content — `full_text` for each sub-question, `context_text` for each question, actual code for code blocks. No element IDs, no text snippets, no abstract pointers that need to be resolved later. The LLM reads the text; the LLM outputs the text.

### 4.3 Semantic Table Mapping

When a rubric table belongs to a question with sub-questions, the LLM maps each table row to the sub-question it grades. This uses semantic understanding (the criterion description references the sub-question's task), not positional heuristics.

### 4.4 Clean Annotations Enable Great Output

The renderer provides simple structural markers (`[TABLE #N]`, `[SQ: X]`, `[EXAMPLE_SOLUTION]`) that help the LLM orient itself; code and body text are plain (no [CODE_BLOCK]). The prompt provides clear principles about what to extract and how. Together, these produce excellent classification output.

---

## 5. Quality Principles for the Complete Rubric

A rubric_draft is "good" when the TestGrader agent can use it to grade a student's exam accurately, consistently, and with actionable feedback. This means:

### 5.1 Criteria Must Cover the Question's Purpose

If the question tests For loops, there must be criteria that directly measure correct For loop usage. Missing core-skill criteria lead to grades that don't reflect the question's intent.

### 5.2 Point Distribution Must Reflect Importance

Core-skill criteria carry more weight. Peripheral criteria (formatting, naming conventions) carry less. A student who gets the algorithm right but formats poorly should score significantly higher than one who formats well but gets the algorithm wrong.

### 5.3 Rules Must Be Independently Evaluable

Each rule measures one thing. The grader can evaluate it by looking at the student's answer without needing to have already evaluated other rules (unless `depends_on` is specified).

### 5.4 Levels Must Be Distinguishable

For multi-level rules, each level describes an observably different state of student work. The grader should never be uncertain about which of two adjacent levels applies — the condition_hints should make the distinction clear.

### 5.5 condition_hints Must Be Grading Instructions

Think of each condition_hint as a line in a rubric that a human teaching assistant would follow. It describes what to look for in the student's answer to determine this scoring level. It must be specific enough that two graders would assign the same level to the same answer.

### 5.6 The Point Sum Invariant Is Sacred

At every level of the hierarchy, points must sum correctly. This is never approximate. If an LLM call produces output that violates the invariant, it is rejected and retried. There is no "close enough."

---

## 6. Context Orchestration Reference

This section maps what information is available at each stage and what gets passed forward.

```
Stage 2 (Renderer) produces:
    → rendered_text: clean text with markers

Stage 3 (Classification) receives:
    → rendered_text
    Produces:
    → test_title (extracted or provided)
    → questions[]: full_text (includes all code), sub_questions[], example_solution (when labeled)
    → table_mappings[]: row_to_sub_question
    → raw criteria (from deterministic table parsing using table_mappings)

Stage 4 (Enhancement) receives per question:
    → test_title
    → question.context_text
    → question.sub_questions[] with full_text
    → raw criteria with original points
    → question.example_solution
    → programming_language
    
    Call 1 produces:
    → question_purpose
    → finalized criteria (completed + rebalanced)
    
    Call 2 receives per criterion:
    → criterion.description + criterion.points
    → question_purpose (from Call 1)
    → sub_question.full_text (if criterion belongs to a sub-question)
    → example_solution
    
    Call 2 produces:
    → rules[] with levels[] and condition_hints

Stage 5 (Validation) receives:
    → complete rubric_draft
    → rendered_text (for fuzzy verification)
    Validates:
    → all point sum invariants
    → text presence in source document
    → level ordering and completeness
```

---

## 7. Design for Future Extension

### 7.1 Teacher Purpose Input (Planned)

A future frontend flow will ask the teacher, for each question: "What are the most important skills/knowledge you want to test with this question?" The teacher's response becomes a third signal for `question_purpose`, joining test_title and question text.

Design the enhancement prompts so that `question_purpose` is a composable field. Currently it's inferred from signals 1-2. When signal 3 arrives, it will be injected as an authoritative override/refinement. The prompt structure should accept an optional `teacher_stated_purpose` field without restructuring.

### 7.2 Multi-Approach Questions (Existing in Ontology)

The ontology supports `allow_multiple_valid_forms` on questions. This is relevant when a coding question can be solved with different valid approaches (e.g., while-loop vs for-loop). The enhancement agent should recognize when multiple approaches are valid and ensure condition_hints accommodate this — a student shouldn't lose points for a correct but stylistically different solution.

### 7.3 Skill Targets (Existing in Ontology)

The ontology supports `skill_targets` on questions and criteria (e.g., `"cs.loops.for"`). These are currently not populated by the pipeline but are part of the schema. The question_purpose analysis in Step 1 is a natural precursor — once we have structured skill taxonomies, the enhancement agent can map its purpose analysis to formal skill IDs.
