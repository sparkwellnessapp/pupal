TestGrader Agent North Star
Complete Technical Specification v1.0

1. Problem Statement
Vivi needs an AI agent that grades student test answers against a compiled rubric contract. The agent receives approved transcriptions (StudentAnswer[]) and a frozen GradingRubricContract, then produces a GradedTestDraft containing scored outcomes with evidence citations for every rule. The draft must be complete (all-or-nothing), auditable (every score has a quotation from student work), and high-quality (>90% agreement with teacher's final scores). Teachers review and approve the draft, optionally overriding AI decisions, before it becomes a frozen GradedTestContract.

2. Input, Output, and Acceptance Contracts
Input Contract
Trigger: Teacher clicks "Continue" from TranscriptionReview page
Required Fields:
FieldTypeConstraintsrubric_idUUIDMust exist in databasecontract_jsonGradingRubricContractMust be compiled (needs_recompilation == False)contract_versionstringImmutable reference for reproducibilitystudent_answersStudentAnswer[]At least one answer; each must have question_id, contentstudent_namestringFor display and recordfilenamestring (optional)Source file referenceteacher_idUUIDOwner of the grading session
Preconditions:

contract_json IS NOT NULL
needs_recompilation == False
All student_answers[].question_id exist in contract
Transcription review completed (answers are approved)

Output Contract
Primary Output: GradedTestDraft
FieldTypeConstraintsdraft_idUUIDUnique identifiersession_idUUIDFK → grading_sessionsrubric_contract_idUUIDFK → rubricscontract_versionstringExact version usedquestion_outcomes[]QuestionOutcome[]One per question in contracttotal_points_earnedDecimalΣ(question_outcomes.points_earned)total_points_possibleDecimalΣ(question_outcomes.points_possible)statusenum"draft"graded_attimestampCompletion timewarnings[]string[]Non-fatal issues encounteredflagged_outcomes[]FlaggedOutcome[]Items needing teacher review
Nested Structure:
GradedTestDraft
└── question_outcomes[]: QuestionOutcome
    ├── question_id: str
    ├── points_earned: Decimal
    ├── points_possible: Decimal
    └── criterion_outcomes[]: CriterionOutcome
        ├── criterion_id: str
        ├── criterion_reasoning: str (Hebrew, overall assessment)
        ├── points_earned: Decimal
        ├── points_possible: Decimal
        ├── needs_review: bool
        └── rule_outcomes[]: RuleOutcome
            ├── rule_id: str
            ├── selected_level_id: str (must exist in contract)
            ├── points_awarded: Decimal
            ├── needs_review: bool
            └── evidence_claim: EvidenceClaim
                ├── claim_type: ClaimType
                ├── claim_statement: str (Hebrew, ≤200 chars)
                └── answer_quotations[]: AnswerQuotation
                    ├── quote_text: str
                    ├── position_hint: str (optional)
                    └── validation_status: "exact" | "fuzzy" | "not_found"
All-or-Nothing Guarantee: Either a complete GradedTestDraft is produced, or the session is marked failed. No partial drafts are persisted.
Acceptance Contract
Hard Validators (Schema-Level):

 All question_outcomes[].question_id exist in contract
 All criterion_outcomes[].criterion_id exist in contract
 All rule_outcomes[].rule_id exist in contract
 All selected_level_id values exist in respective rule's levels[]
 points_awarded matches the selected level's points exactly
 total_points_earned == Σ(question_outcomes.points_earned)
 points_earned ≤ points_possible at every level
 Every RuleOutcome has exactly one EvidenceClaim
 Every EvidenceClaim has at least one AnswerQuotation

Soft Validators (Quality Heuristics):

 quote_text found in StudentAnswer.content (fuzzy match OK)
 claim_statement length ≤ 200 characters
 No duplicate rule_id in outcomes (double-counting prevention)
 Warning if >20% of outcomes flagged for review

Human Approval Checkpoint:

Teacher reviews GradedTestDraft in GradingResults page
Teacher can edit scores, override level selections, modify reasoning
Teacher clicks "Approve" → Draft compiles to GradedTestContract


3. Success Criteria, Failure Modes, and Constraints
Success Criteria
MetricTargetMeasurementLatency per student test< 40 secondscompleted_at - started_atEvidence quality100% valid quotationsrules_with_valid_quotes / total_rulesAccuracy> 90% agreement1 - (teacher_overrides / total_rules)Completion rate> 95%Sessions reaching COMPLETED statusClosed-world violations0Invalid level_id selections
Failure Modes (Ranked by Severity)
RankFailure ModeSeverityMitigation1.0Gross scoring error (0→full or full→0)CatastrophicMulti-level validation, teacher review1.0Batch crash, progress lostCatastrophicPersistent session state, graceful recovery0.9Hallucinated quotationHighQuote validation with fuzzy matching0.85Closed-world violationHighReject + retry with explicit instruction0.8Criterion mixing (wrong context)Medium-HighIsolated LLM calls per criterion0.7Latency > 40sMediumProgress tracking, async processing
Constraints
ConstraintValueRationaleMax latency per test40 secondsTeacher UXMax retries per criterion2Cost/latency balanceMax LLM calls per test~50Assuming ~15 criteria averageQuote validation thresholdLevenshtein ≤ 0.15Allow minor OCR errorsResponse languageHebrewIsraeli teachersPrompt languageEnglishBetter LLM performance

4. Decision Graph and State Invariants
Key Decision Nodes
┌─────────────────────────────────────────────────────────────────────────────┐
│  DECISION: Has valid contract?                                              │
│  Evidence: contract_json NOT NULL AND needs_recompilation == False          │
│  Yes → Continue                                                             │
│  No → REJECT with error "Rubric not compiled or needs recompilation"        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DECISION: Student answer exists for this question?                         │
│  Evidence: answer_lookup.get(question_id)                                   │
│  Yes → Grade normally                                                       │
│  No → Award 0 points, quote="[No answer provided]", flag for review         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DECISION: LLM response valid?                                              │
│  Evidence: JSON parses AND all level_ids exist in contract                  │
│  Valid → Continue to quote validation                                       │
│  Invalid level_id → Retry with explicit instruction (max 2)                 │
│  Malformed JSON (all retries) → Skip criterion, flag, continue              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DECISION: Quotations valid?                                                │
│  Evidence: Levenshtein distance ≤ 0.15 from StudentAnswer.content           │
│  All valid → Accept evaluation                                              │
│  Some invalid → Re-prompt with feedback (ReAct loop, max 2)                 │
│  Still invalid after retries → Accept but flag needs_review                 │
└─────────────────────────────────────────────────────────────────────────────┘
State Invariants
INVARIANT INV-A1 ClosedWorldEnforcement:
  For every RuleOutcome:
    rule_outcome.rule_id IN contract.all_rule_ids
    rule_outcome.selected_level_id IN contract.get_rule(rule_id).level_ids

INVARIANT INV-A2 PointsConsistency:
  For every RuleOutcome:
    rule_outcome.points_awarded == contract.get_level(selected_level_id).points
  For every CriterionOutcome:
    criterion_outcome.points_earned == Σ(rule_outcomes.points_awarded)
  For every QuestionOutcome:
    question_outcome.points_earned == Σ(criterion_outcomes.points_earned)
  For GradedTestDraft:
    total_points_earned == Σ(question_outcomes.points_earned)

INVARIANT INV-A3 EvidenceCompleteness:
  For every RuleOutcome:
    LEN(evidence_claim.answer_quotations) >= 1

INVARIANT INV-A4 ProgressMonotonicity:
  completed_criteria only increases (never decreases)
  question_outcomes only appends (never removes)

INVARIANT INV-A5 SessionIntegrity:
  If status == COMPLETED:
    graded_test_draft IS NOT NULL
  If status == FAILED:
    error_message IS NOT NULL

INVARIANT INV-A6 ContractVersionLock:
  All grading in a batch uses identical contract_version

5. Agent State Schema
pythonclass GradingAgentState(TypedDict):
    """
    LangGraph state for the TestGrader Agent.
    """
    
    # ═══════════════════════════════════════════════════════════════
    # IMMUTABLE CONTEXT
    # ═══════════════════════════════════════════════════════════════
    session_id: str                           # PK for grading_sessions table
    contract: Dict[str, Any]                  # GradingRubricContract
    contract_version: str                     # Immutable reference
    student_answers: List[Dict[str, Any]]     # StudentAnswer[]
    answer_lookup: Dict[str, Dict[str, Any]]  # question_id → StudentAnswer
    teacher_id: str
    student_name: str
    filename: Optional[str]
    
    # ═══════════════════════════════════════════════════════════════
    # PROGRESS TRACKING
    # ═══════════════════════════════════════════════════════════════
    status: str                    # initialized|grading|completed|failed
    current_question_idx: int      # 0-indexed
    current_criterion_idx: int     # 0-indexed within current question
    total_questions: int
    total_criteria: int            # Across all questions
    completed_criteria: int
    
    # ═══════════════════════════════════════════════════════════════
    # ACCUMULATED RESULTS
    # ═══════════════════════════════════════════════════════════════
    question_outcomes: List[Dict[str, Any]]           # Completed QuestionOutcome[]
    current_question_id: Optional[str]
    current_criterion_outcomes: List[Dict[str, Any]]  # WIP CriterionOutcome[]
    
    # ═══════════════════════════════════════════════════════════════
    # REACT LOOP STATE
    # ═══════════════════════════════════════════════════════════════
    current_criterion: Optional[Dict[str, Any]]       # Criterion being evaluated
    current_student_answer: Optional[Dict[str, Any]]  # StudentAnswer for question
    pending_evaluation: Optional[Dict[str, Any]]      # LLM response before validation
    validation_failures: List[Dict[str, Any]]         # Failed quote validations
    criterion_retry_count: int
    max_criterion_retries: int                        # Default: 2
    
    # ═══════════════════════════════════════════════════════════════
    # QUALITY SIGNALS
    # ═══════════════════════════════════════════════════════════════
    flagged_outcomes: List[Dict[str, Any]]  # [{rule_id, reason}]
    total_rules_evaluated: int
    rules_with_valid_quotes: int
    rules_flagged_for_review: int
    
    # ═══════════════════════════════════════════════════════════════
    # ERROR STATE
    # ═══════════════════════════════════════════════════════════════
    warnings: List[str]                # Non-fatal issues
    error_message: Optional[str]       # Fatal error (if failed)
    skipped_criteria: List[str]        # criterion_ids that failed all retries
    
    # ═══════════════════════════════════════════════════════════════
    # TIMING & OBSERVABILITY
    # ═══════════════════════════════════════════════════════════════
    started_at: Optional[str]          # ISO timestamp
    completed_at: Optional[str]
    llm_calls_count: int
    total_llm_latency_ms: int
    
    # ═══════════════════════════════════════════════════════════════
    # FINAL OUTPUT
    # ═══════════════════════════════════════════════════════════════
    graded_test_draft: Optional[Dict[str, Any]]  # GradedTestDraft when complete
```

### Field Ownership

| Field | Written By | Source of Truth |
|-------|------------|-----------------|
| `contract`, `contract_version` | Initialization | Database (rubrics table) |
| `student_answers`, `answer_lookup` | Initialization | API request |
| `status`, `current_*_idx` | Graph nodes | State transitions |
| `question_outcomes`, `current_*_outcomes` | `evaluate_criterion`, `finalize_question` | Accumulated |
| `pending_evaluation` | `evaluate_criterion_llm` | LLM response |
| `validation_failures` | `validate_quotations` | Validation logic |
| `flagged_outcomes`, `warnings` | Various nodes | Quality signals |
| `graded_test_draft` | `assemble_draft` | Final assembly |

---

## 6. Workflow and Cognitive Task Map

### Step-by-Step Flow
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: INITIALIZATION                                                     │
│  ───────────────────────                                                    │
│  Input: API request (rubric_id, student_answers, teacher_id)                │
│  Tasks:                                                                     │
│    1. Load GradingRubricContract from database                              │
│    2. Validate preconditions (compiled, not stale)                          │
│    3. Build answer_lookup: Dict[question_id → StudentAnswer]                │
│    4. Create grading_session record (status=initialized)                    │
│    5. Calculate totals (questions, criteria)                                │
│  Output: Initialized GradingAgentState                                      │
│  Handoff: → STEP 2                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: SELECT NEXT QUESTION                                               │
│  ───────────────────────────────                                            │
│  Input: current_question_idx, contract.questions                            │
│  Decision:                                                                  │
│    - If all questions processed → STEP 7 (assemble)                         │
│    - Else → Set current_question_id, reset criterion index                  │
│  Output: Updated state with current question context                        │
│  Handoff: → STEP 3                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: CHECK STUDENT ANSWER                                               │
│  ────────────────────────────                                               │
│  Input: current_question_id, answer_lookup                                  │
│  Decision:                                                                  │
│    - If answer exists and non-empty → STEP 4                                │
│    - If answer missing/empty → Create zero-score outcomes for all           │
│      criteria with quote="[No answer provided]", flag → STEP 6              │
│  Expert Judgment: Detecting gibberish vs. partial answer                    │
│  Output: current_student_answer or zero-score outcomes                      │
│  Handoff: → STEP 4 or STEP 6                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SELECT NEXT CRITERION                                              │
│  ─────────────────────────────                                              │
│  Input: current_criterion_idx, current_question.criteria                    │
│  Decision:                                                                  │
│    - If all criteria processed → STEP 6 (finalize question)                 │
│    - Else → Set current_criterion, reset retry count                        │
│  Output: Updated state with current criterion context                       │
│  Handoff: → STEP 5                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: EVALUATE CRITERION (ReAct Loop)                                    │
│  ───────────────────────────────────────                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  5A: LLM CALL                                                        │   │
│  │  Input: criterion.description, rules[], levels[], student_answer     │   │
│  │  Output: {criterion_reasoning, rule_evaluations[]}                   │   │
│  │  Expert Judgment: Level selection, evidence extraction               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          │                                                  │
│                          ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  5B: VALIDATE RESPONSE                                               │   │
│  │  Checks:                                                             │   │
│  │    - JSON parses correctly                                           │   │
│  │    - All selected_level_id exist in contract (closed-world)          │   │
│  │    - All quote_text found in student_answer (fuzzy Levenshtein)      │   │
│  │  Decision:                                                           │   │
│  │    - All valid → Accept, increment completed_criteria → STEP 4       │   │
│  │    - Invalid level_id → Retry with instruction (max 2)               │   │
│  │    - Invalid quotes only → Retry with feedback (max 2)               │   │
│  │    - Malformed JSON (all retries) → Skip criterion, flag → STEP 4    │   │
│  │    - Still invalid after retries → Accept with needs_review → STEP 4 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Output: CriterionOutcome added to current_criterion_outcomes               │
│  Handoff: → STEP 4 (next criterion) or retry loop                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: FINALIZE QUESTION                                                  │
│  ─────────────────────────                                                  │
│  Input: current_question_id, current_criterion_outcomes                     │
│  Tasks:                                                                     │
│    1. Calculate question total: Σ(criterion_outcomes.points_earned)         │
│    2. Create QuestionOutcome                                                │
│    3. Append to question_outcomes                                           │
│    4. Increment current_question_idx                                        │
│    5. Update database progress (for real-time tracking)                     │
│  Output: QuestionOutcome added to question_outcomes                         │
│  Handoff: → STEP 2 (next question)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: ASSEMBLE DRAFT                                                     │
│  ──────────────────────                                                     │
│  Input: question_outcomes, session metadata                                 │
│  Tasks:                                                                     │
│    1. Calculate total: Σ(question_outcomes.points_earned)                   │
│    2. Validate all invariants (INV-A1 through INV-A6)                       │
│    3. Create GradedTestDraft                                                │
│    4. Save to database (graded_tests table)                                 │
│    5. Update session status to COMPLETED                                    │
│    6. Record timing metrics                                                 │
│  Output: graded_test_draft                                                  │
│  Handoff: → END (returns to frontend for teacher review)                    │
└─────────────────────────────────────────────────────────────────────────────┘

7. Competency Questions (Evaluation-Driven)
CQ-1: Basic Rule Evaluation
Question: Given a binary rule "Function returns correct value" (5 points) and a student answer containing return x + y, can the agent select the correct level and cite the return statement?
Expected Answer:
json{
  "rule_id": "q1.c0.r0",
  "selected_level_id": "pass",
  "points_awarded": 5.0,
  "evidence_claim": {
    "claim_statement": "הפונקציה מחזירה את הסכום של שני הפרמטרים כנדרש",
    "answer_quotations": [{"quote_text": "return x + y"}]
  }
}
Required Entities: ReductionRule, ScoringLevel, StudentAnswer, RuleOutcome, EvidenceClaim
Passing Criteria: selected_level_id correct, quote_text exists in answer

CQ-2: Missing Answer Handling
Question: Given a question with no student answer, does the agent produce zero-score outcomes with appropriate flags?
Expected Answer:

All rules: selected_level_id: "fail", points_awarded: 0
All quotes: "[No answer provided]"
All outcomes: needs_review: true
Warning added to session

Passing Criteria: No crash, proper zero-scoring, flags set

CQ-3: Quote Validation Failure
Question: If the LLM returns a quote that doesn't exist in the student answer, does the agent retry and eventually flag?
Expected Behavior:

First attempt: LLM returns invalid quote
Validation fails
Retry with feedback: "Quote not found, please cite actual text"
Second attempt: Still invalid
Accept with needs_review: true, validation_status: "not_found"

Passing Criteria: Retry occurred, flag set, grading continued

CQ-4: Closed-World Enforcement
Question: If the LLM returns selected_level_id: "excellent" but the rule only has ["pass", "fail"], does the agent reject and retry?
Expected Behavior:

Validation detects invalid level_id
Retry with explicit instruction listing valid levels
Second attempt returns valid level_id
Evaluation accepted

Passing Criteria: Invalid level never persisted, retry with instruction, valid level accepted

CQ-5: Multi-Rule Criterion
Question: Given a criterion with 3 rules, does a single LLM call evaluate all 3 and produce consistent outcomes?
Expected Answer:
json{
  "criterion_reasoning": "התלמיד הציג הבנה חלקית...",
  "rule_evaluations": [
    {"rule_id": "r0", "selected_level_id": "pass", ...},
    {"rule_id": "r1", "selected_level_id": "fail", ...},
    {"rule_id": "r2", "selected_level_id": "pass", ...}
  ]
}
```

**Passing Criteria**: All 3 rules evaluated in one call, `criterion_reasoning` present, points sum correctly

---

### CQ-6: Batch Consistency

**Question**: When grading 3 students in a batch, are all graded with the same contract_version?

**Expected Behavior**:
- `GradingBatch.contract_version` set once
- All 3 `GradedTestDraft.contract_version` match
- If rubric edited mid-batch, warning shown (not re-graded automatically)

**Passing Criteria**: All `contract_version` values identical

---

### CQ-7: Partial Failure Recovery

**Question**: If student 2/3 fails all retries on one criterion, do students 1 and 3 complete successfully?

**Expected Behavior**:
- Student 1: COMPLETED
- Student 2: COMPLETED (with skipped_criteria, warnings, flags)
- Student 3: COMPLETED
- Batch: PARTIALLY_COMPLETED (2 clean, 1 with issues)

**Passing Criteria**: No cascade failure, each student independent

---

### CQ-8: Latency Budget

**Question**: Can a 15-criterion test be graded in under 40 seconds?

**Expected Behavior**:
- ~15 LLM calls (one per criterion)
- ~2 seconds per call average
- Total: ~30 seconds + overhead
- If exceeding budget: log warning, continue anyway

**Passing Criteria**: p95 latency < 40s for typical tests

---

## 8. Ontology Specification (Minimal, OWL/RDF Ready)

### Scope

This ontology covers only entities required for the TestGrader Agent decision-making. It references but does not redefine entities from the Vivi Foundational Ontology.

### Naming Conventions

- Classes: PascalCase (e.g., `RuleOutcome`)
- Properties: camelCase (e.g., `hasEvidenceClaim`)
- Instances: kebab-case with prefix (e.g., `session-abc123`)

### Class Taxonomy (Agent-Specific)
```
GradingAgentState (Transient)
├── hasContract → GradingRubricContract
├── hasStudentAnswers → StudentAnswer[]
├── hasQuestionOutcomes → QuestionOutcome[]
└── hasStatus → AgentStatus

AgentStatus (Enum)
├── INITIALIZED
├── GRADING
├── COMPLETED
└── FAILED

ValidationResult (Transient)
├── quotationValid: boolean
├── levelIdValid: boolean
└── failureReasons: string[]
Object Properties
PropertyDomainRangeCardinalitygradesUsingGradingSessionGradingRubricContract1gradesDocumentGradingSessionStudentAnswerDocument1producedByGradedTestDraftGradingSession1evaluatesRuleOutcomeReductionRule1selectsLevelRuleOutcomeScoringLevel1citesAnswerEvidenceClaimAnswerQuotation1..*
Constraints (SHACL-Style)
turtle# Every RuleOutcome must have exactly one EvidenceClaim
agent:RuleOutcomeShape a sh:NodeShape ;
    sh:targetClass vivi:RuleOutcome ;
    sh:property [
        sh:path vivi:hasEvidenceClaim ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] .

# EvidenceClaim must have at least one quotation
agent:EvidenceClaimShape a sh:NodeShape ;
    sh:targetClass vivi:EvidenceClaim ;
    sh:property [
        sh:path vivi:citesAnswer ;
        sh:minCount 1 ;
    ] .

# selected_level_id must exist in rule's levels (closed-world)
agent:ClosedWorldLevelShape a sh:NodeShape ;
    sh:targetClass vivi:RuleOutcome ;
    sh:sparql [
        sh:select """
            SELECT $this
            WHERE {
                $this vivi:selectsLevel ?level .
                $this vivi:evaluates ?rule .
                FILTER NOT EXISTS { ?rule vivi:hasLevel ?level }
            }
        """ ;
        sh:message "selected_level_id does not exist in rule's levels" ;
    ] .

9. Context and Knowledge Plan
Source Inventory
SourceTrust RankUsageGradingRubricContract1 (Authoritative)Closed-world for levels, rules, criteriaStudentAnswer1 (Authoritative)Ground truth for quotation validationLLM Response3 (Requires Validation)Level selection, reasoning, quotes
Freshness Requirements
DataFreshnessRefresh TriggerContractFrozen at session startNever (immutable for session)Student answersFrozen at session startNeverLLM capabilitiesN/AModel upgrade (out of scope)
Retrieval Strategy

Contract loading: Single DB query at initialization
Answer lookup: In-memory dict, O(1) per question
No RAG required: All context fits in LLM call

Citation Rules

Every claim_statement must be supported by answer_quotations
Quote must exist in StudentAnswer.content (fuzzy match allowed)
Position hints optional but encouraged

Conflict Resolution
ConflictResolutionLLM says "pass" but no quote foundFlag for review, teacher decidesLLM returns invalid level_idReject, retry with valid optionsLLM returns multiple levelsReject, retry with "select exactly one"
Safety and Leakage Prevention

Student answers never logged in full (truncate in logs)
No cross-student data leakage (isolated LLM calls)
Contract version locked to prevent mid-grading drift


10. Tooling Plan
Tools and Schemas
ToolPurposeInputOutputevaluate_criterionLLM call for criterion evaluationCriterion, rules, answerCriterionEvaluationvalidate_quotationCheck quote exists in answerquote_text, answer_contentValidationResultcalculate_levenshteinFuzzy string matchingstr1, str2float (0.0-1.0)persist_session_progressUpdate DB with progresssession_id, progressvoid
Failure Modes and Fallback
ToolFailure ModeFallbackevaluate_criterionLLM timeoutRetry with backoff (max 3)evaluate_criterionRate limitWait and retryevaluate_criterionMalformed responseRetry, then skip criterionvalidate_quotationNo matchFuzzy match, then flagpersist_session_progressDB errorLog warning, continue in-memory
Idempotency

Re-running same session_id returns cached result (if completed)
Retries within session are idempotent (same criterion, same attempt)

Audit Logging
EventLogged FieldsSession startedsession_id, contract_version, teacher_id, timestampCriterion evaluatedcriterion_id, llm_latency_ms, retry_countValidation failedrule_id, quote_text (truncated), reasonSession completedsession_id, total_latency, rules_evaluated, flags_count
Human-in-the-Loop Rules

Agent never directly produces GradedTestContract
Always produces GradedTestDraft for teacher review
Teacher can override any AI decision
Override reason optional but encouraged


11. Agent Blueprint (LangGraph-Ready)
Node: initialize
Goal: Set up grading context, validate preconditions
Inputs: API request (rubric_id, student_answers, teacher_id)
Required Context: Database access
Ontology Concepts: GradingRubricContract, StudentAnswer, GradingSession
Tools: DB query
Output Format:
python{
    "session_id": "uuid",
    "contract": {...},
    "contract_version": "v1.2.3",
    "answer_lookup": {"q1": {...}, "q2": {...}},
    "status": "initialized",
    "total_questions": 3,
    "total_criteria": 12
}
Acceptance Checks:

 Contract loaded successfully
 needs_recompilation == False
 At least one student answer provided

Failure Modes:

Contract not found → FAIL with "Rubric not found"
Needs recompilation → FAIL with "Rubric needs recompilation"

Escalation: Return error to API, no draft created

Node: select_next_question
Goal: Advance to next question or signal completion
Inputs: current_question_idx, contract.questions
Output Format:
python{
    "current_question_idx": 1,  # incremented
    "current_question_id": "q2",
    "current_criterion_idx": 0,  # reset
    "current_criterion_outcomes": []  # reset
}
Routing:

current_question_idx >= len(questions) → assemble_draft
else → check_student_answer


Node: check_student_answer
Goal: Verify answer exists, handle missing/empty
Inputs: current_question_id, answer_lookup
Output Format (if missing):
python{
    "current_criterion_outcomes": [
        # Zero-score outcomes for all criteria
    ],
    "warnings": ["No answer for question q2"],
    "flagged_outcomes": [{"question_id": "q2", "reason": "no_answer"}]
}
Routing:

Answer exists and non-empty → select_next_criterion
Answer missing/empty → Create zero outcomes, → finalize_question


Node: select_next_criterion
Goal: Advance to next criterion or finalize question
Inputs: current_criterion_idx, current_question.criteria
Output Format:
python{
    "current_criterion_idx": 1,  # incremented
    "current_criterion": {...},  # Criterion object
    "criterion_retry_count": 0,  # reset
    "pending_evaluation": None,  # reset
    "validation_failures": []  # reset
}
```

**Routing**:
- `current_criterion_idx >= len(criteria)` → `finalize_question`
- else → `evaluate_criterion_llm`

---

### Node: `evaluate_criterion_llm`

**Goal**: Call LLM to evaluate all rules in criterion

**Inputs**:
- `current_criterion` (description, rules with levels)
- `current_student_answer` (content)
- `validation_failures` (if retry, include feedback)

**Required Context**: LLM client

**Ontology Concepts**: Criterion, ReductionRule, ScoringLevel

**Tools**: `evaluate_criterion` (LLM call)

**Prompt Structure**:
```
You are grading a student's answer for a computer science exam.
Your role is that of a world-class teacher who grades fairly and precisely.

CRITERION: {criterion.description}

RULES TO EVALUATE:
{for each rule:}
  Rule {rule.rule_id}: {rule.description}
  Max Points: {rule.max_points}
  Levels (choose exactly ONE per rule):
  {for each level:}
    - {level.level_id}: {level.points} points — {level.condition_hint}

STUDENT ANSWER:
{student_answer.content}

{if validation_failures:}
IMPORTANT: Your previous response had issues:
{for each failure:}
  - Rule {failure.rule_id}: Quote "{failure.quote_text}" not found in student answer.
    Please cite actual text from the answer.

RESPOND IN JSON:
{
  "criterion_reasoning": "Overall assessment in Hebrew (2-4 sentences)",
  "rule_evaluations": [
    {
      "rule_id": "...",
      "selected_level_id": "...",  // Must be one of the level IDs listed above
      "claim_statement": "Hebrew explanation (2-4 sentences)",
      "quote_text": "Exact quote from student answer"
    },
    ...
  ]
}
Output Format:
python{
    "pending_evaluation": {
        "criterion_reasoning": "...",
        "rule_evaluations": [...]
    },
    "llm_calls_count": 5,  # incremented
    "total_llm_latency_ms": 12500  # accumulated
}
Acceptance Checks:

 JSON parses correctly
 All rule_id match expected rules
 All selected_level_id exist in respective rule's levels

Failure Modes:

LLM timeout → Retry (handled by tool)
Malformed JSON → validate_response will catch

Routing: Always → validate_response

Node: validate_response
Goal: Validate LLM response, decide retry or accept
Inputs: pending_evaluation, current_criterion, current_student_answer
Tools: validate_quotation, calculate_levenshtein
Validation Steps:

Check all selected_level_id exist (closed-world)
For each quote_text, validate against student_answer.content

Exact match: validation_status = "exact"
Fuzzy match (Levenshtein ≤ 0.15): validation_status = "fuzzy"
No match: validation_status = "not_found", add to failures



Output Format (validation passed):
python{
    "current_criterion_outcomes": [
        # Append new CriterionOutcome
    ],
    "completed_criteria": 5,  # incremented
    "rules_with_valid_quotes": 12,  # incremented
    "validation_failures": []  # cleared
}
Output Format (validation failed, retry):
python{
    "validation_failures": [
        {"rule_id": "r0", "quote_text": "...", "reason": "not_found"}
    ],
    "criterion_retry_count": 1  # incremented
}
Routing:

All valid → select_next_criterion
Invalid level_id, retries left → evaluate_criterion_llm (with instruction)
Invalid quotes, retries left → evaluate_criterion_llm (with feedback)
Max retries, some valid → Accept with flags → select_next_criterion
Max retries, all invalid → Skip criterion → select_next_criterion


Node: finalize_question
Goal: Aggregate criterion outcomes into question outcome
Inputs: current_question_id, current_criterion_outcomes
Output Format:
python{
    "question_outcomes": [
        # Append new QuestionOutcome
    ],
    "current_question_idx": 2,  # incremented
    "current_criterion_outcomes": []  # cleared for next question
}
Side Effect: Update grading_sessions table with progress (for real-time tracking)
Routing: → select_next_question

Node: assemble_draft
Goal: Create final GradedTestDraft, validate invariants
Inputs: question_outcomes, session metadata
Validation:

INV-A1: Closed-world (all IDs valid)
INV-A2: Points consistency (sums match)
INV-A3: Evidence completeness (all claims have quotes)

Output Format:
python{
    "graded_test_draft": {
        "draft_id": "uuid",
        "session_id": "...",
        "rubric_contract_id": "...",
        "contract_version": "...",
        "question_outcomes": [...],
        "total_points_earned": 75.5,
        "total_points_possible": 100.0,
        "status": "draft",
        "warnings": [...],
        "flagged_outcomes": [...]
    },
    "status": "completed",
    "completed_at": "2026-02-03T12:34:56Z"
}
Side Effect:

Insert GradedTestDraft into graded_tests table
Update grading_sessions.status = COMPLETED

Routing: → END

Graph Definition (LangGraph Pseudocode)
pythonfrom langgraph.graph import StateGraph, END

workflow = StateGraph(GradingAgentState)

# Add nodes
workflow.add_node("initialize", initialize)
workflow.add_node("select_next_question", select_next_question)
workflow.add_node("check_student_answer", check_student_answer)
workflow.add_node("select_next_criterion", select_next_criterion)
workflow.add_node("evaluate_criterion_llm", evaluate_criterion_llm)
workflow.add_node("validate_response", validate_response)
workflow.add_node("finalize_question", finalize_question)
workflow.add_node("assemble_draft", assemble_draft)

# Set entry point
workflow.set_entry_point("initialize")

# Add edges
workflow.add_edge("initialize", "select_next_question")

workflow.add_conditional_edges(
    "select_next_question",
    lambda s: "assemble" if s["current_question_idx"] >= s["total_questions"] else "continue",
    {"assemble": "assemble_draft", "continue": "check_student_answer"}
)

workflow.add_conditional_edges(
    "check_student_answer",
    lambda s: "no_answer" if s.get("_no_answer") else "has_answer",
    {"no_answer": "finalize_question", "has_answer": "select_next_criterion"}
)

workflow.add_conditional_edges(
    "select_next_criterion",
    lambda s: "done" if s["current_criterion_idx"] >= len(s["current_question"]["criteria"]) else "evaluate",
    {"done": "finalize_question", "evaluate": "evaluate_criterion_llm"}
)

workflow.add_edge("evaluate_criterion_llm", "validate_response")

workflow.add_conditional_edges(
    "validate_response",
    route_after_validation,  # Custom function based on validation result
    {
        "accept": "select_next_criterion",
        "retry": "evaluate_criterion_llm",
        "skip": "select_next_criterion"
    }
)

workflow.add_edge("finalize_question", "select_next_question")
workflow.add_edge("assemble_draft", END)

# Compile
app = workflow.compile()
```

---

## 12. Evaluation Plan

### Tests Mapped to Competency Questions

| CQ | Test Name | Input Fixture | Expected Output | Pass Criteria |
|----|-----------|---------------|-----------------|---------------|
| CQ-1 | `test_basic_rule_evaluation` | Simple rubric + correct answer | Pass with quote | Level correct, quote valid |
| CQ-2 | `test_missing_answer_handling` | Rubric + empty answer | Zero scores, flags | All zeros, all flagged |
| CQ-3 | `test_quote_validation_retry` | Mock LLM returns bad quote | Retry, then flag | Retry count = 1, flagged |
| CQ-4 | `test_closed_world_enforcement` | Mock LLM returns invalid level | Retry with instruction | Valid level in final |
| CQ-5 | `test_multi_rule_criterion` | 3-rule criterion | 3 evaluations | All rules present, sum correct |
| CQ-6 | `test_batch_contract_consistency` | 3 students | Same version | All versions match |
| CQ-7 | `test_partial_failure_recovery` | 1 student with failing criterion | 2 complete, 1 with skip | No cascade, warnings present |
| CQ-8 | `test_latency_budget` | Real 15-criterion test | Complete < 40s | Timer check |

### Adversarial Test Cases

| Test | Adversarial Input | Expected Behavior |
|------|-------------------|-------------------|
| `test_empty_string_answer` | `content: ""` | Zero scores, flagged |
| `test_gibberish_answer` | `content: "asdfghjkl"` | Zero scores, flagged |
| `test_llm_returns_negative_points` | Mock response | Rejected, retry |
| `test_llm_returns_extra_rules` | Mock response with unknown rule_id | Ignored, only known rules scored |
| `test_quote_with_special_chars` | Hebrew + code + special chars | Fuzzy match handles |
| `test_very_long_answer` | 10,000 char answer | Completes without truncation issues |
| `test_concurrent_rubric_edit` | Edit rubric mid-grading | Warning shown, results still valid |

### Monitoring Signals

| Signal | Threshold | Alert |
|--------|-----------|-------|
| Latency p95 | > 40s | Warning |
| Latency p99 | > 60s | Critical |
| Quote validation failure rate | > 20% | Warning |
| Closed-world violations | > 0 | Critical |
| Session failure rate | > 5% | Warning |
| Retry rate | > 30% | Warning |

---

## 13. MVP Build Plan and Phased Roadmap

### MVP Scope (Phase 3)

**In Scope**:
- [x] LangGraph-based agent with state schema
- [x] Sequential question→criterion processing
- [x] 1 LLM call per criterion (all rules together)
- [x] ReAct loop with quote validation + retry
- [x] Graceful degradation (skip + flag)
- [x] grading_sessions table for persistence
- [x] Real-time progress tracking
- [x] GradedTestDraft output with all invariants
- [x] Integration with existing API endpoints

**Deferred**:
- [ ] Multi-level scoring (discrete_levels beyond binary)
- [ ] PedagogicalSource integration
- [ ] Parallel criterion evaluation (optimization)
- [ ] Advanced hallucination detection beyond quote validation
- [ ] Model/prompt versioning for full reproducibility
- [ ] Student feedback generation

### Validation Milestones

| Milestone | Criteria | Validation Method |
|-----------|----------|-------------------|
| M1: Agent runs | Completes single test without crash | Manual test |
| M2: Correct output | Matches expected structure | Schema validation |
| M3: Evidence quality | 100% valid quotes | Automated test |
| M4: Accuracy baseline | Grades match teacher on 3 tests | Manual comparison |
| M5: Latency target | < 40s on real test | Timer |
| M6: Production ready | All CQ tests pass | CI/CD |

---

## 14. Assumptions, Open Questions, and Risks

### Assumptions

| # | Assumption | Risk Level | Validation |
|---|------------|------------|------------|
| A1 | All rules are binary (pass/fail) for MVP | Low | Known limitation, documented |
| A2 | 1 LLM call per criterion is sufficient | Medium | May need optimization if criteria are large |
| A3 | Levenshtein ≤ 0.15 catches OCR errors | Medium | Test with real transcriptions |
| A4 | 40s latency is acceptable to teachers | Low | Confirmed in interview |
| A5 | Hebrew prompts degrade LLM performance | Medium | Using English prompts |
| A6 | Teachers always review before approval | Low | Enforced by UI flow |

### Open Questions

| # | Question | Impact | Resolution Path |
|---|----------|--------|-----------------|
| Q1 | Optimal Levenshtein threshold? | Quote validation accuracy | A/B test with real data |
| Q2 | Should skipped criteria count toward accuracy? | Metric integrity | Define metric precisely |
| Q3 | How to handle rubric version warning UX? | Teacher experience | Design review |
| Q4 | Checkpoint strategy for very long tests? | Resumability | Future enhancement |

### Risks

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| R1 | LLM rate limits during batch | Medium | Batch delays | Exponential backoff, queue |
| R2 | Quote validation too strict | Medium | Excessive flags | Tune threshold, add fuzzy |
| R3 | Quote validation too loose | Medium | Hallucinations slip through | Manual review flags |
| R4 | Latency exceeds 40s on complex tests | Low | UX degradation | Progress indicator, async |
| R5 | Teacher edits rubric mid-batch | Low | Inconsistent grading | Version lock warning |

---

## Appendix: LLM Prompt Template
```
You are a world-class {subject} teacher grading a student's exam answer.
Grade fairly, precisely, and cite evidence from the student's work.

═══════════════════════════════════════════════════════════════════════════════
CRITERION: {criterion.description}
Points possible: {criterion.points}
═══════════════════════════════════════════════════════════════════════════════

RULES TO EVALUATE:
{for each rule in criterion.rules:}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rule ID: {rule.rule_id}
Description: {rule.description}
Max Points: {rule.max_points}

Select ONE level:
{for each level in rule.levels:}
  • {level.level_id} ({level.points} pts): {level.condition_hint}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════════════════════════════════════════════════════════════════════════════
STUDENT ANSWER:
═══════════════════════════════════════════════════════════════════════════════
{student_answer.content}

{if validation_failures:}
═══════════════════════════════════════════════════════════════════════════════
⚠️  CORRECTION REQUIRED
Your previous response had invalid quotations:
{for each failure:}
  • Rule {failure.rule_id}: "{failure.quote_text}" — NOT FOUND in student answer
    Please cite EXACT text from the answer above.
═══════════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════════
RESPOND IN THIS EXACT JSON FORMAT:
═══════════════════════════════════════════════════════════════════════════════
{
  "criterion_reasoning": "Overall assessment in Hebrew (2-4 sentences)",
  "rule_evaluations": [
    {
      "rule_id": "{rule.rule_id}",
      "selected_level_id": "<one of: {level_ids}>",
      "claim_statement": "Hebrew explanation why this level (2-4 sentences, ≤200 chars)",
      "quote_text": "Exact quote from student answer that supports your decision"
    }
  ]
}

IMPORTANT:
- selected_level_id MUST be one of the listed level IDs
- quote_text MUST be copied exactly from the student answer
- If student didn't attempt this aspect, use quote_text: "[No answer provided]"
- Respond ONLY with valid JSON, no markdown