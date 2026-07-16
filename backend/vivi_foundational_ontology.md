Vivi Foundational Ontology North Star
Complete Technical Specification v2.0
Unified Ontology for Rubric Extraction, Test Grading, and Transcription
Last Updated: February 2026

1. Purpose & Scope
This document defines the complete ontological foundation for Vivi, the AI-powered Teacher's Assistant platform. It serves as the single source of truth for all AI agents, engineers, and systems operating within Vivi.
1.1 What This Document Covers
Domain
Description
Test
The exam document (questions only)
Rubric
Test + Criteria + Points (extends Test)
StudentAnswerDocument
Scanned/uploaded student submission
Transcription
VLM-extracted text from handwritten answers
StudentAnswer
Approved transcription (per question)
GradedTest
Complete grading result for one student
GradingSession
Workflow state for grading one student's test
GradingBatch
Collection of sessions (batch upload)
Teacher, Student, Class, School
User and organizational entities


1.2 The Core Insight: Draft → Contract Pattern
All entities in Vivi follow a Draft → Contract pattern:
Raw Input → AI Processing → DRAFT (editable) → Human Review → CONTRACT (frozen)
This pattern applies to:
Rubric: ExtractRubricResponse → GradingRubricContract
Transcription: Transcription → StudentAnswer[]
GradedTest: GradedTestDraft → GradedTestContract
1.3 Version History
Version
Date
Changes
1.0
Jan 2026
Initial ontology covering rubrics, tests, grading constructs
2.0
Feb 2026
Added: FlaggedOutcome, needs_review flags, validation_status, reasoning_summary, confidence levels, quote validation support. Full compatibility with TestGrader Agent North Star.


2. Architecture Layers
Layer
Contains
Changes
Ontology
Classes, relations, invariants
Rarely (versioned)
Policy
Defaults, thresholds, fallbacks
Occasionally
Implementation
Tools, prompts, pipelines
Frequently


2.1 Validation Boundaries
Concern
Mechanism
Enforcement Point
Class/relation structure
OWL-style schema
Schema definition
Sum constraints, coverage
SHACL-style shapes
Pre-save validation
Closed-world, referential integrity
Code
Compilation + runtime
Quote validation
Fuzzy matching (Levenshtein)
Agent ReAct loop
Audit trail
Database triggers
Persistence layer


3. Complete Class Taxonomy
Organization
├── School {name, region}
└── Class {name, subject, academic_year}
    └── hasStudents → Student[]

Person
├── Teacher {name, email, subjects[], preferences}
│   └── belongsTo → School (optional)
│   └── teaches → Class[]
└── Student {encrypted_name, encrypted_id}
    └── memberOf → Class

Assessment
├── Test {questions[], metadata}
└── Rubric extends Test {criteria[], points}
    ├── ExtractRubricResponse (draft, editable)
    └── GradingRubricContract (frozen, closed-world)

Question {questionType, totalPoints, text, subQuestions[]}
└── SubQuestion {index, text, points}

PedagogicalConcept
├── SkillTarget {id, name, priority: primary|trivial}
├── Requirement {id, description, promoted: boolean}
├── CorrectnessModel → ApproachClass (pipeline-only)
└── MisconceptionPattern

GradingConstruct
├── Criterion {criterion_id, description, points, measurabilityStatus}
│   └── hasRules → ReductionRule[]
├── ReductionRule {rule_id, maxPoints, scoringType, ruleKind, levels[]}
│   └── hasLevels → ScoringLevel[]
└── ScoringLevel {level_id, levelOrder, points, conditionHint}

StudentWork
├── StudentAnswerDocument {pages[], file_reference, upload_timestamp}
│   └── hasTranscription → Transcription
│   └── hasApprovedAnswers → StudentAnswer[]
├── Transcription {raw_text, confidence, flagged_segments[], status}
└── StudentAnswer {question_id, content, content_type, approved_at}

GradingResult
├── RuleOutcome {rule_id, selected_level_id, points_awarded, evidence_claim,
│               needs_review, review_reason}  // v2.0: added review flags
├── CriterionOutcome {criterion_id, points_earned, rule_outcomes[],
│                    reasoning_summary, needs_review}  // v2.0: added reasoning
├── QuestionOutcome {question_id, points_earned, criterion_outcomes[]}
└── GradedTest
    ├── GradedTestDraft (AI-generated, editable)
    │   └── warnings[], flagged_outcomes[]  // v2.0: added quality signals
    └── GradedTestContract (teacher-approved, frozen)

Evidence
├── EvidenceClaim {claim_type, claim_statement, matched_level_id,
│                 answer_quotations[], confidence_level}  // v2.0: added confidence
├── AnswerQuotation {quote_text, position_hint, span_pointer,
│                   validation_status}  // v2.0: added validation_status
└── PedagogicalSource {source_type, location, quote}

Workflow
├── GradingBatch {batch_id, teacher_id, rubric_contract_id, sessions[], status}
└── GradingSession {session_id, student_answer_document_id, status, timestamps}

Quality (v2.0: NEW)
└── FlaggedOutcome {rule_id?, criterion_id?, question_id?, reason}

Audit
├── RubricAuditRecord {draft_snapshot, contract_snapshot, diff_summary}
└── GradedTestAuditRecord {draft_snapshot, contract_snapshot, diff_summary}

4. Entity Definitions
4.1 Test
The base exam document containing only questions.
class Test(BaseModel):
    test_id: str
    name: str
    subject: Subject
    created_at: datetime
    created_by: str  # teacher_id
    duration_minutes: Optional[int] = None
    class_id: Optional[str] = None
    date_administered: Optional[date] = None
    source_file_reference: Optional[str] = None
    questions: List[Question]

    @property
    def total_points(self) -> Decimal:
        return sum(q.total_points for q in self.questions)
4.2 Rubric (extends Test)
A Test with criteria and point assignments added.
class Rubric(Test):
    rubric_id: str
    programming_language: Optional[str] = None  # For CS
    # Inherited: test_id, name, subject, questions, etc.
    # Each question now has criteria attached
4.3 Question & SubQuestion
class Question(BaseModel):
    question_id: str
    index: int
    question_type: QuestionType
    question_text: Optional[str] = None
    total_points: Decimal
    allow_multiple_valid_forms: bool = False
    skill_targets: List[SkillTarget] = []
    requirements: List[Requirement] = []
    sub_questions: List[SubQuestion] = []
    criteria: List[Criterion] = []  # Empty for Test, populated for Rubric

class SubQuestion(BaseModel):
    sub_question_id: str
    index: int  # 0 = 'a', 1 = 'b', etc.
    text: Optional[str] = None
    points: Decimal
    criteria: List[Criterion] = []
4.4 StudentAnswerDocument
The raw uploaded submission (scanned pages or typed document).
class StudentAnswerDocument(BaseModel):
    document_id: str
    test_id: str
    student_id: Optional[str] = None
    file_reference: str
    file_type: Literal['scanned_images', 'pdf', 'docx']
    pages: List[PageImage]
    uploaded_at: datetime
    uploaded_by: str  # teacher_id
    transcription_id: Optional[str] = None
    transcription_status: TranscriptionStatus
    approved_answers: List[StudentAnswer] = []
4.5 Transcription
The raw VLM-extracted text before teacher approval.
class Transcription(BaseModel):
    transcription_id: str
    document_id: str
    raw_text: str
    overall_confidence: float  # 0.0 - 1.0
    flagged_segments: List[FlaggedSegment]
    question_segments: List[QuestionSegment]
    page_references: List[PageReference]
    created_at: datetime
    model_version: str
    status: TranscriptionStatus
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
4.6 StudentAnswer
The approved answer content (per question). This is the CONTRACT form of transcription.
class StudentAnswer(BaseModel):
    answer_id: str
    document_id: str
    question_id: str
    sub_question_id: Optional[str] = None
    content: str  # The approved text
    content_type: Literal['text', 'code', 'mixed']
    transcription_id: str
    was_corrected: bool = False
    approved_at: datetime
    approved_by: str

4.7 GradedTest (Draft and Contract)
The complete grading result for one student. Follows Draft → Contract pattern.
4.7.1 GradedTestDraft
class GradedTestDraft(BaseModel):
    '''AI-generated grading result before teacher review.'''
    draft_id: str
    grading_session_id: str
    rubric_contract_id: str
    rubric_contract_version: str
    student_answer_document_id: str
    student_id: Optional[str] = None
    
    # Results
    question_outcomes: List[QuestionOutcome]
    total_points_earned: Decimal
    total_points_possible: Decimal
    
    # AI metadata
    graded_at: datetime
    model_version: str
    grading_duration_ms: int
    
    # Review status
    status: GradedTestStatus
    
    # === v2.0 ADDITIONS: Quality Signals ===
    warnings: List[str] = []  # Non-fatal issues during grading
    flagged_outcomes: List[FlaggedOutcome] = []  # Items needing review
    
    def compile(self) -> 'GradedTestContract':
        '''Compile to frozen contract after teacher approval.'''
        pass
4.7.2 GradedTestContract
class GradedTestContract(BaseModel):
    '''Teacher-approved, frozen grading result.'''
    contract_id: str
    contract_version: str  # UUID, new on each approval
    
    # References (immutable)
    rubric_contract_id: str
    rubric_contract_version: str
    student_answer_document_id: str
    student_id: Optional[str] = None
    
    # Frozen results
    question_outcomes: List[QuestionOutcome]
    total_points_earned: Decimal
    total_points_possible: Decimal
    
    # Approval metadata
    approved_at: datetime
    approved_by: str
    
    model_config = {'frozen': True}
4.7.3 FlaggedOutcome (v2.0 NEW)
class FlaggedOutcome(BaseModel):
    '''An outcome flagged for teacher attention.'''
    rule_id: Optional[str] = None
    criterion_id: Optional[str] = None
    question_id: Optional[str] = None
    reason: str  # 'no_answer', 'quote_not_found', 'low_confidence',
               # 'unmeasurable', 'llm_uncertainty'

class FlagReason(str, Enum):
    NO_ANSWER = 'no_answer'
    QUOTE_NOT_FOUND = 'quote_not_found'
    LOW_CONFIDENCE = 'low_confidence'
    UNMEASURABLE = 'unmeasurable'
    LLM_UNCERTAINTY = 'llm_uncertainty'
    FUZZY_MATCH = 'fuzzy_match'

4.8 Outcome Hierarchy
4.8.1 QuestionOutcome
class QuestionOutcome(BaseModel):
    '''Grading result for one question.'''
    question_id: str
    sub_question_id: Optional[str] = None
    points_earned: Decimal
    points_possible: Decimal
    criterion_outcomes: List[CriterionOutcome]
    
    @property
    def percentage(self) -> float:
        if self.points_possible == 0:
            return 0.0
        return float(self.points_earned / self.points_possible * 100)
4.8.2 CriterionOutcome
class CriterionOutcome(BaseModel):
    '''Grading result for one criterion.'''
    criterion_id: str
    points_earned: Decimal
    points_possible: Decimal
    rule_outcomes: List[RuleOutcome]
    
    # === v2.0 ADDITIONS ===
    reasoning_summary: Optional[str] = None  # Overall Hebrew assessment
    needs_review: bool = False  # Flag for teacher attention
4.8.3 RuleOutcome
class RuleOutcome(BaseModel):
    '''Result of evaluating one ReductionRule.'''
    rule_id: str
    selected_level_id: str
    points_awarded: Decimal
    evidence_claim: EvidenceClaim  # Exactly one
    
    # Teacher override tracking
    was_overridden: bool = False
    original_level_id: Optional[str] = None
    override_reason: Optional[str] = None
    
    # === v2.0 ADDITIONS ===
    needs_review: bool = False  # Flag for teacher attention
    review_reason: Optional[str] = None  # Why flagged
4.9 Evidence Types
4.9.1 EvidenceClaim
class EvidenceClaim(BaseModel):
    '''Atomic, auditable evidence unit.'''
    claim_id: str
    claim_type: ClaimType
    claim_statement: str  # The 'reasoning' - max 200 chars
    matched_level_id: str
    
    # Mandatory: at least one
    answer_quotations: List[AnswerQuotation]  # len >= 1
    
    # Optional: pedagogical backing
    pedagogical_sources: List[PedagogicalSource] = []
    
    # === v2.0 ADDITIONS ===
    confidence_level: Optional[ConfidenceLevel] = None
4.9.2 AnswerQuotation
class AnswerQuotation(BaseModel):
    '''Citation from student's actual work.'''
    quote_text: str  # Required, ground truth
    position_hint: Optional[str] = None  # 'line 5', 'paragraph 2'
    span_pointer: Optional[SpanPointer] = None
    
    # === v2.0 ADDITIONS ===
    validation_status: Optional[QuoteValidationStatus] = None

class QuoteValidationStatus(str, Enum):
    '''Result of validating quote against StudentAnswer.content'''
    EXACT = 'exact'       # Exact substring match
    FUZZY = 'fuzzy'       # Levenshtein distance <= threshold (0.15)
    NOT_FOUND = 'not_found'  # Quote not found in answer
4.9.3 ConfidenceLevel (v2.0 NEW)
class ConfidenceLevel(str, Enum):
    '''Calibrated confidence levels for grading.'''
    HIGH = 'high'      # >95% accurate: exact evidence found
    MEDIUM = 'medium'  # 70-95%: partial evidence or edge case
    LOW = 'low'        # <70%: needs human review

4.10 Workflow Entities
4.10.1 GradingBatch
class GradingBatch(BaseModel):
    '''A batch of student tests to grade.'''
    batch_id: str
    teacher_id: str
    rubric_contract_id: str
    rubric_contract_version: str
    sessions: List[GradingSession]
    created_at: datetime
    class_id: Optional[str] = None
    total_sessions: int
    completed_sessions: int
    status: BatchStatus
4.10.2 GradingSession
class GradingSession(BaseModel):
    '''Workflow state for grading one student's test.'''
    session_id: str
    batch_id: Optional[str] = None
    student_answer_document_id: str
    
    # Current state
    status: SessionStatus
    current_step: SessionStep
    
    # Timestamps
    timestamps: SessionTimestamps
    
    # Results
    transcription_id: Optional[str] = None
    graded_test_draft_id: Optional[str] = None
    graded_test_contract_id: Optional[str] = None
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # === v2.0 ADDITIONS: Progress Tracking ===
    total_criteria: Optional[int] = None
    completed_criteria: int = 0
    skipped_criteria: List[str] = []  # criterion_ids that failed
4.11 Organizational Entities
School, Class, Teacher, Student definitions remain unchanged from v1.0.
4.12 Audit Entities
RubricAuditRecord and GradedTestAuditRecord definitions remain unchanged from v1.0.

5. Key Relations
Relation
Domain → Range
Cardinality
extends
Rubric → Test
1:1
hasQuestion
Test → Question
1..*
hasSubQuestion
Question → SubQuestion
0..*
hasCriterion
Question ∪ SubQuestion → Criterion
0..* (Test), 1..* (Rubric)
hasRule
Criterion → ReductionRule
1..*
hasLevel
ReductionRule → ScoringLevel
2..*
hasTranscription
StudentAnswerDocument → Transcription
0..1
hasApprovedAnswers
StudentAnswerDocument → StudentAnswer
0..*
forQuestion
StudentAnswer → Question
1
gradedWith
GradedTest → GradingRubricContract
1
hasEvidenceClaim
RuleOutcome → EvidenceClaim
1
citesAnswer
EvidenceClaim → AnswerQuotation
1..*
hasFlaggedOutcome (v2.0)
GradedTestDraft → FlaggedOutcome
0..*


6. Invariants
6.1 Rubric Invariants (INV-R)
INVARIANT INV-R1 PointSumQuestion:
  |Σ(criterion.points) - question.totalPoints| ≤ tolerance

INVARIANT INV-R2 PointSumCriterion:
  |Σ(rule.maxPoints) - criterion.points| ≤ tolerance

INVARIANT INV-R3 ClosedWorldGrading:
  Grader cannot invent criteria, rules, or levels not in contract

INVARIANT INV-R4 EvidenceCitation:
  Every RuleOutcome contains exactly one EvidenceClaim
  Every EvidenceClaim cites at least one AnswerQuotation

INVARIANT INV-R5 LevelCoverage:
  Every ReductionRule has ≥2 levels including 0 and maxPoints

INVARIANT INV-R6 CriterionAlignment:
  Every Criterion links to ≥1 SkillTarget OR Requirement

INVARIANT INV-R7 DoubleCountingPrevention:
  No overlapping deductions unless dependsOn declared
6.2 GradedTest Invariants (INV-G)
INVARIANT INV-G1 RubricContractReference:
  GradedTest.rubric_contract_id must reference valid GradingRubricContract
  GradedTest.rubric_contract_version must match the contract's version

INVARIANT INV-G2 StructuralAlignment:
  Every question_outcome.question_id must exist in RubricContract
  Every criterion_outcome.criterion_id must exist in RubricContract
  Every rule_outcome.rule_id must exist in RubricContract
  Every rule_outcome.selected_level_id must exist in rule's levels

INVARIANT INV-G3 PointsBounded:
  For every QuestionOutcome: points_earned ≤ points_possible
  For every CriterionOutcome: points_earned ≤ points_possible
  For every RuleOutcome: points_awarded ≤ rule.max_points
  points_awarded ≥ 0 (no negative scores)

INVARIANT INV-G4 TotalConsistency:
  GradedTest.total_points_earned = Σ(question_outcome.points_earned)
  QuestionOutcome.points_earned = Σ(criterion_outcome.points_earned)
  CriterionOutcome.points_earned = Σ(rule_outcome.points_awarded)

INVARIANT INV-G5 EvidenceRequired:
  Every RuleOutcome must satisfy INV-R4 (evidence citation)
  Even teacher overrides must provide reasoning

INVARIANT INV-G6 ImmutabilityAfterApproval:
  GradedTestContract is frozen
  Any edit creates a new contract_version
6.3 Transcription Invariants (INV-T)
INVARIANT INV-T1 DocumentReference:
  Transcription.document_id must reference valid StudentAnswerDocument

INVARIANT INV-T2 ApprovalRequired:
  StudentAnswer can only be created from approved Transcription

INVARIANT INV-T3 QuestionCoverage:
  After approval, StudentAnswerDocument must have StudentAnswer
  for every question the student attempted
6.4 Workflow Invariants (INV-W)
INVARIANT INV-W1 SessionProgression:
  GradingSession.status transitions follow valid state machine:
  PENDING → IN_PROGRESS → AWAITING_REVIEW → COMPLETED
  (or → FAILED from any state)

INVARIANT INV-W2 BatchConsistency:
  All sessions in a batch must reference same rubric_contract_id

INVARIANT INV-W3 TranscriptionBeforeGrading:
  GradingSession cannot enter GRADING until transcription is APPROVED
6.5 Agent Invariants (INV-A) — v2.0 NEW
These invariants are enforced by the TestGrader Agent at runtime:
INVARIANT INV-A1 ClosedWorldEnforcement:
  For every RuleOutcome:
    rule_outcome.rule_id IN contract.all_rule_ids
    rule_outcome.selected_level_id IN contract.get_rule(rule_id).level_ids

INVARIANT INV-A2 PointsConsistency:
  points_awarded == level.points (exactly, from contract)
  criterion.points_earned == Σ(rule_outcomes.points_awarded)
  question.points_earned == Σ(criterion_outcomes.points_earned)
  total == Σ(question_outcomes.points_earned)

INVARIANT INV-A3 EvidenceCompleteness:
  For every RuleOutcome: LEN(evidence_claim.answer_quotations) >= 1

INVARIANT INV-A4 ProgressMonotonicity:
  completed_criteria only increases (never decreases)
  question_outcomes only appends (never removes)

INVARIANT INV-A5 SessionIntegrity:
  If status == COMPLETED: graded_test_draft IS NOT NULL
  If status == FAILED: error_message IS NOT NULL

INVARIANT INV-A6 ContractVersionLock:
  All grading in a batch uses identical contract_version

7. The Draft → Contract Pattern
7.1 Universal Pattern
┌────────────────────────────────────────────────────────────────────┐
│                    DRAFT → CONTRACT PATTERN                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Raw Input → AI Processing → DRAFT → Human Review → CONTRACT      │
│                               │           │            │          │
│                          (editable)  (validation)  (frozen)       │
│                               │           │            │          │
│                          - May have   - Teacher    - Immutable    │
│                            errors      corrects    - Versioned    │
│                          - Annotations - Approves  - Auditable    │
│                          - AI metadata                            │
│                          - Quality flags (v2.0)                   │
└────────────────────────────────────────────────────────────────────┘
7.2 Applied to Each Domain
Domain
Draft Entity
Contract Entity
Compile Trigger
Rubric
ExtractRubricResponse
GradingRubricContract
Teacher approves extraction
Transcription
Transcription
StudentAnswer[]
Teacher approves transcription
GradedTest
GradedTestDraft
GradedTestContract
Teacher approves grading

7.3 Audit Trail
Every Draft → Contract transition creates an audit record capturing the diff for quality measurement.

8. Enums Reference
class Subject(str, Enum):
    COMPUTER_SCIENCE = 'computer_science'
    MATHEMATICS = 'mathematics'
    HISTORY = 'history'
    ENGLISH = 'english'
    PHYSICS = 'physics'
    CHEMISTRY = 'chemistry'
    BIOLOGY = 'biology'
    LITERATURE = 'literature'

class QuestionType(str, Enum):
    SHORT_ANSWER = 'short_answer'
    CODING_TASK = 'coding_task'
    TRACE_TABLE = 'trace_table'
    COMPUTATION = 'computation'
    PROOF = 'proof'
    ESSAY = 'essay'
    SOURCE_ANALYSIS = 'source_analysis'
    MULTIPLE_CHOICE = 'multiple_choice'
    FILL_IN_BLANK = 'fill_in_blank'

class RuleKind(str, Enum):
    STRUCTURE_AST = 'structure_ast'
    EXECUTION_TESTS = 'execution_tests'
    TEXT_ALIGNMENT = 'text_alignment'
    REFERENCE_CITATION = 'reference_citation'
    FORMAT_REQUIREMENT = 'format_requirement'
    REASONING_QUALITY = 'reasoning_quality'
    PRESENCE_CHECK = 'presence_check'
    NUMERIC_ACCURACY = 'numeric_accuracy'

class ClaimType(str, Enum):
    PRESENCE = 'presence'
    CORRECTNESS = 'correctness'
    COVERAGE = 'coverage'
    CONSTRAINT = 'constraint'
    QUALITY = 'quality'

class MeasurabilityStatus(str, Enum):
    MEASURABLE = 'measurable'
    PARTIALLY_MEASURABLE = 'partially_measurable'
    NOT_MEASURABLE = 'not_measurable'

class TranscriptionStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    AWAITING_REVIEW = 'awaiting_review'
    APPROVED = 'approved'

class GradedTestStatus(str, Enum):
    DRAFT = 'draft'
    PENDING_REVIEW = 'pending_review'
    APPROVED = 'approved'
    SAVED = 'saved'
    RELEASED = 'released'

class SessionStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    AWAITING_REVIEW = 'awaiting_review'
    COMPLETED = 'completed'
    FAILED = 'failed'

class SessionStep(str, Enum):
    UPLOADED = 'uploaded'
    TRANSCRIBING = 'transcribing'
    AWAITING_TRANSCRIPTION_REVIEW = 'awaiting_transcription_review'
    GRADING = 'grading'
    AWAITING_GRADED_TEST_REVIEW = 'awaiting_graded_test_review'
    APPROVED_AND_SAVED = 'approved_and_saved'

class BatchStatus(str, Enum):
    CREATED = 'created'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    PARTIALLY_COMPLETED = 'partially_completed'

# === v2.0 ADDITIONS ===

class ConfidenceLevel(str, Enum):
    HIGH = 'high'      # >95% accurate
    MEDIUM = 'medium'  # 70-95%
    LOW = 'low'        # <70%, needs review

class QuoteValidationStatus(str, Enum):
    EXACT = 'exact'
    FUZZY = 'fuzzy'
    NOT_FOUND = 'not_found'

class FlagReason(str, Enum):
    NO_ANSWER = 'no_answer'
    QUOTE_NOT_FOUND = 'quote_not_found'
    LOW_CONFIDENCE = 'low_confidence'
    UNMEASURABLE = 'unmeasurable'
    LLM_UNCERTAINTY = 'llm_uncertainty'
    FUZZY_MATCH = 'fuzzy_match'

9. Foreign Key Enforcement Matrix
Source Entity
Field
Target Entity
Enforcement
Rubric
test_id
Test
Inheritance
Question
rubric_id
Rubric
Schema
Criterion
question_id
Question
Schema
ReductionRule
criterion_id
Criterion
Schema
GradedTestDraft
rubric_contract_id
GradingRubricContract
Compilation
RuleOutcome
rule_id
ReductionRule (contract)
Closed-world
RuleOutcome
selected_level_id
ScoringLevel (contract)
Closed-world
FlaggedOutcome (v2.0)
rule_id
RuleOutcome
Runtime


10. Versioning Strategy
Entity
Version Field
Increments When
GradingRubricContract
contract_version
Teacher edits + recompiles
GradingRubricContract
schema_version
Breaking schema change
GradedTestContract
contract_version
Teacher re-approves after edit
Transcription
(implicit)
Re-transcription requested
StudentAnswer
was_corrected flag
Teacher corrects transcription


Reproducibility Guarantee: Given contract_version for both RubricContract and GradedTestContract, the grading result is deterministic and auditable.

11. Pipeline Integration Points
11.1 DOCX Rubric Extraction Pipeline
DOCX Upload
    │
    ▼
┌─────────────────┐
│ Parser          │ → DocxDocument (raw structure)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Annotator       │ → AnnotatedDocument (structure labels)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Pattern Analyzer│ → Patterns (Hebrew, tables, code blocks)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Renderer        │ → LLM-ready text (~1800 tokens)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Classifier      │ → Question/Criterion structure
└────────┬────────┘
         ▼
┌─────────────────┐
│ Transformer     │ → ExtractRubricResponse (DRAFT)
└────────┬────────┘
         ▼
    Teacher Review
         │
         ▼
┌─────────────────┐
│ ContractCompiler│ → GradingRubricContract (CONTRACT)
└─────────────────┘
11.2 Grading Pipeline (v2.0 Updated)
Scanned Pages Upload
    │
    ▼
┌─────────────────────────┐
│ StudentAnswerDocument   │ (created)
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ VLM Transcription       │ → Transcription (DRAFT)
└────────┬────────────────┘
         ▼
    Teacher Review (flagged segments)
         │
         ▼
┌─────────────────────────┐
│ Approval                │ → StudentAnswer[] (CONTRACT)
└────────┬────────────────┘
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TestGrader Agent (LangGraph)                                │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ FOR each question (sequential):                         │ │
│ │   FOR each criterion:                                   │ │
│ │     → LLM Call (all rules in criterion)                 │ │
│ │     → Validate quotes (Levenshtein ≤ 0.15)              │ │
│ │     → ReAct loop if validation fails (max 2 retries)    │ │
│ │     → Flag if still invalid after retries              │ │
│ │   → Assemble CriterionOutcome                          │ │
│ │ → Assemble QuestionOutcome                              │ │
│ │ → Validate INV-A1 through INV-A6                        │ │
│ └─────────────────────────────────────────────────────────┘ │
│ → GradedTestDraft (DRAFT) with warnings[] and flagged[]    │
└────────┬────────────────────────────────────────────────────┘
         ▼
    Teacher Review (scores, reasoning, flagged items)
         │
         ▼
┌─────────────────────────┐
│ Approval                │ → GradedTestContract (CONTRACT)
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ AuditRecord             │ (created for quality tracking)
└─────────────────────────┘

12. Success Metrics
Metric
Target
Measurement
Teacher edits per rubric
< 5
RubricAuditRecord.teacher_edits_count
Teacher overrides per graded test
< 3
GradedTestAuditRecord.total_overrides
Transcription correction rate
< 10%
StudentAnswer.was_corrected percentage
Grading session completion rate
> 95%
Sessions reaching COMPLETED status
Closed-world violations
0
Invalid level_id selections
Evidence citation rate
100%
RuleOutcomes with valid EvidenceClaim
Quote validation rate (v2.0)
100%
AnswerQuotations with validation_status != NOT_FOUND
Grading latency per test (v2.0)
< 40s
grading_duration_ms
Teacher accuracy agreement (v2.0)
> 90%
1 - (overrides / total_rules)


13. Assumptions
Teachers upload complete rubrics or tests (partial documents not supported)
Single DOCX/PDF per rubric or test
Student submissions are 2-5 pages typically
Teachers review all AI outputs before finalization
Discrete scoring levels are sufficient (no continuous scoring)
Hebrew is primary language; system is RTL-aware
Student data requires encryption at rest
Audit trail retention follows institutional policy
(v2.0) Grading continues server-side even if browser closes
(v2.0) Quote validation uses Levenshtein distance ≤ 0.15 for fuzzy matching

14. Open Questions for Future Versions
Feedback Generation: How to transform EvidenceClaims into student-friendly feedback?
Cross-Class Analytics: Aggregation patterns for class/school-level reporting?
Collaborative Grading: Conflict resolution when multiple teachers grade same test?
Version Migration: Strategy for migrating data when schema_version changes?
Partial Automation: Which criteria can be fully automated vs. require human review?
(v2.0) Multi-level Scoring: Extract 'מלא/חלקי' columns for discrete_levels beyond binary?
(v2.0) PedagogicalSource Integration: Link authoritative sources to grading context?
(v2.0) Parallel Criterion Evaluation: Optimize latency for large tests?

Appendix A: TestGrader Agent Compatibility Matrix
This appendix documents the v2.0 additions made to ensure 100% compatibility with the TestGrader Agent North Star specification.
A.1 New Entities
Entity
Purpose
FlaggedOutcome
Identifies outcomes requiring teacher review (no_answer, quote_not_found, low_confidence, unmeasurable)
ConfidenceLevel
Calibrated confidence for AI decisions (high/medium/low)
QuoteValidationStatus
Result of validating quote against StudentAnswer (exact/fuzzy/not_found)
FlagReason
Enumeration of reasons for flagging outcomes

A.2 New Fields on Existing Entities
Entity
Field
Purpose
GradedTestDraft
warnings[]
Non-fatal issues encountered during grading
GradedTestDraft
flagged_outcomes[]
Items needing teacher review
CriterionOutcome
reasoning_summary
Overall Hebrew assessment of criterion
CriterionOutcome
needs_review
Flag for teacher attention
RuleOutcome
needs_review
Flag for teacher attention
RuleOutcome
review_reason
Why flagged (FlagReason enum)
EvidenceClaim
confidence_level
AI confidence in this claim
AnswerQuotation
validation_status
Quote validation result (exact/fuzzy/not_found)
GradingSession
total_criteria
For progress tracking
GradingSession
completed_criteria
Real-time progress counter
GradingSession
skipped_criteria[]
Criteria that failed all retries

A.3 New Invariants
INV-A1 through INV-A6 define runtime invariants enforced by the TestGrader Agent. These complement (not replace) the existing INV-R, INV-G, INV-T, and INV-W invariants.

— End of Document —
