"""
Canonical Ontological Types for Vivi Rubric System.

This module is the SINGLE SOURCE OF TRUTH for all types defined in the
Ontological North Star specification. All other modules import from here.

Architecture:
- Ontology layer: Classes, relations, invariants (this file)
- Policy layer: Defaults, thresholds (NumericPolicy)
- Implementation layer: Tools, prompts (other services)

Invariants Enforced:
- INV-1–INV-4: Arithmetic sum invariants, enforced by ContractCompiler
- INV-5 ContractVersionLock: contract_version UUID on GradingRubricContract
- INV-6 ClosedWorld: all_criteria_ids / all_sub_criteria_ids on GradingRubricContract
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Self, Set
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, model_validator


# =============================================================================
# ENUMS
# =============================================================================

class QuestionType(str, Enum):
    """
    Categorizes questions for appropriate extraction and grading strategies.
    
    Used by:
    - Extraction pipeline: Routes to appropriate table parser
    - Grading agent: Selects evidence extraction strategy
    """
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    SOURCE_ANALYSIS = "source_analysis"
    CODING_TASK = "coding_task"
    TRACE_TABLE = "trace_table"
    COMPUTATION = "computation"
    PROOF = "proof"
    WORD_PROBLEM = "word_problem"
    READING_COMPREHENSION = "reading_comprehension"
    GRAMMAR_EXERCISE = "grammar_exercise"
    WRITING_TASK = "writing_task"



class ClaimType(str, Enum):
    """
    Categorizes evidence claims for double-counting prevention.
    
    Two RuleOutcomes with the same (quote_span, claim_type) pair
    cannot both deduct points unless dependsOn is declared.
    """
    PRESENCE = "presence"       # Something exists/doesn't exist
    CORRECTNESS = "correctness" # Something is right/wrong
    COVERAGE = "coverage"       # Completeness of solution
    CONSTRAINT = "constraint"   # Requirement satisfaction
    QUALITY = "quality"         # Style/clarity/optimization



class AnnotationSeverity(str, Enum):
    """
    Controls compilation behavior based on annotation severity.
    
    - ERROR: Blocks compilation to GradingRubricContract
    - WARNING: Requires teacher acknowledgment before compilation
    - INFO: Purely informational, no action required
    """
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# =============================================================================
# v2.0 ENUMS - GRADING OUTPUT TYPES
# =============================================================================

class QuoteValidationStatus(str, Enum):
    """
    Result of validating quote against StudentAnswer.content.
    
    Used by the TestGrader Agent during the ReAct validation loop.
    - EXACT: Substring exact match found
    - FUZZY: Levenshtein distance <= 0.15 (allows minor OCR errors)
    - NOT_FOUND: Quote cannot be verified in student answer
    """
    EXACT = "exact"
    FUZZY = "fuzzy"
    NOT_FOUND = "not_found"


class ConfidenceLevel(str, Enum):
    """
    Calibrated confidence levels for grading decisions.
    
    Guides teacher review attention:
    - HIGH: >95% accurate, exact evidence found
    - MEDIUM: 70-95%, partial evidence or edge case
    - LOW: <70%, definitely needs human review
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FlagReason(str, Enum):
    """
    Reasons for flagging an outcome for teacher review.
    
    Used by FlaggedOutcome to indicate why an item needs attention.
    """
    NO_ANSWER = "no_answer"
    QUOTE_NOT_FOUND = "quote_not_found"
    LOW_CONFIDENCE = "low_confidence"
    UNMEASURABLE = "unmeasurable"
    LLM_UNCERTAINTY = "llm_uncertainty"
    FUZZY_MATCH = "fuzzy_match"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    CLOSED_WORLD_VIOLATION = "closed_world_violation"
    UNGRADED_CRITERION = "ungraded_criterion"
    BOUNDS_CLAMPED = "bounds_clamped"


# =============================================================================
# NUMERIC POLICY
# =============================================================================

class NumericPolicy(BaseModel):
    """
    Contract-level numeric handling configuration.
    
    Inherited by all point calculations within a rubric.
    Used for invariant validation (sum tolerance) and display (rounding).
    """
    precision: Decimal = Field(
        default=Decimal("0.25"),
        description="Smallest point increment (quarter-point granularity)"
    )
    rounding_mode: str = Field(
        default="half_up",
        description="Python decimal rounding mode"
    )
    sum_tolerance: Decimal = Field(
        default=Decimal("0.01"),
        description="Maximum allowed deviation in point sum validation"
    )
    
    @field_serializer('precision', 'sum_tolerance')
    def serialize_decimal(self, v: Decimal) -> str:
        """Ensure Decimals serialize to JSON as strings."""
        return str(v)


# =============================================================================
# EVIDENCE TYPES
# =============================================================================

class SpanPointer(BaseModel):
    """
    Best-effort position information for answer quotations.
    
    Optional because LLMs are unreliable at character offsets,
    especially with Hebrew RTL text. The quote_text is ground truth.
    """
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    line_number: Optional[int] = None
    context: Optional[str] = Field(
        default=None,
        description="Semantic context like 'function main' or 'class Plane'"
    )


class AnswerQuotation(BaseModel):
    """
    Citation from student's actual work.
    
    The quote_text is REQUIRED and is the ground truth.
    Position hints help humans navigate but aren't critical for validation.
    
    v2.0: Added validation_status for quote validation tracking.
    """
    quote_text: str = Field(
        ...,
        min_length=1,
        description="The actual quoted text from student work"
    )
    position_hint: Optional[str] = Field(
        default=None,
        description="Human-readable hint like 'line 5' or 'in function main'"
    )
    span_pointer: Optional[SpanPointer] = None
    
    # v2.0 addition: Quote validation tracking
    validation_status: Optional[QuoteValidationStatus] = Field(
        default=None,
        description="Result of validating quote against student answer (v2.0)"
    )
    
    @field_serializer('validation_status')
    def serialize_validation_status(self, v: Optional[QuoteValidationStatus]) -> Optional[str]:
        return v.value if v else None


class EvidenceClaim(BaseModel):
    """
    Atomic, auditable evidence unit. One claim = one idea.
    
    Structural contract: One EvidenceClaim per RuleOutcome.
    This prevents "dump claims until something sticks" behavior.
    
    v2.0: Added confidence_level for calibrated AI confidence.
    """
    claim_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    claim_type: ClaimType
    claim_statement: str = Field(
        ...,
        max_length=200,
        description="Short, atomic, testable statement"
    )
    matched_level_id: str = Field(
        ...,
        description="References the ScoringLevel that was selected"
    )
    answer_quotations: List[AnswerQuotation] = Field(
        ...,
        min_length=1,
        description="At least one quotation required (INV-4)"
    )
    pedagogical_sources: List["PedagogicalSource"] = Field(
        default_factory=list,
        description="Conditional based on evidence_policy.pedagogical_source"
    )
    
    # v2.0 addition: AI confidence tracking
    confidence_level: Optional[ConfidenceLevel] = Field(
        default=None,
        description="Calibrated AI confidence in this claim (v2.0)"
    )
    
    @field_serializer('claim_type')
    def serialize_claim_type(self, v: ClaimType) -> str:
        return v.value
    
    @field_serializer('confidence_level')
    def serialize_confidence_level(self, v: Optional[ConfidenceLevel]) -> Optional[str]:
        return v.value if v else None



class PedagogicalSource(BaseModel):
    """
    Reference to teaching material that supports the grading decision.
    
    Used when evidence_policy.pedagogical_source is "required" or "optional".
    Helps teachers understand why a particular grading decision was made.
    """
    source_type: Literal["rubric", "syllabus", "textbook", "example"] = Field(
        ...,
        description="Type of pedagogical reference"
    )
    location: str = Field(
        ...,
        description="Where to find this source (e.g., 'page 42', 'criterion 3')"
    )
    quote: Optional[str] = Field(
        default=None,
        description="Optional quote from the source"
    )


# =============================================================================
# SUB-CRITERION
# =============================================================================

class SubCriterion(BaseModel):
    """
    A single graded sub-part of a criterion.

    Sub-criteria are optional. When present, INV-3 (SubCriteriaPointsSum)
    requires Σ sub_criterion.points == criterion.points (enforced by compiler).
    When absent, the criterion is graded as an atomic unit.
    """
    model_config = {"frozen": False}

    sub_criterion_id: str = Field(..., description="Stable ID, e.g. 'q1.c1.sc0'")
    index: int = Field(..., ge=0)
    description: str
    points: Decimal = Field(..., ge=Decimal("0"))

    @field_serializer('points')
    def serialize_points(self, v: Decimal) -> str:
        return str(v)


class SkillTarget(BaseModel):
    """
    Links a criterion to a teachable skill from the taxonomy.
    
    Used for CriterionAlignment validation (INV-6).
    """
    id: str = Field(..., description="Skill taxonomy ID like 'cs.loops.for'")
    name: str = Field(..., description="Human-readable name")
    priority: Literal["primary", "trivial"] = Field(
        default="primary",
        description="Primary skills are weighted; trivial are noted only"
    )


class Requirement(BaseModel):
    """
    A constraint or rule (vs a teachable skill).
    
    Examples: "Must use Java", "No libraries", "Max 20 lines"
    Can be promoted to SkillTarget if teacher consistently weights it.
    """
    id: str
    description: str
    promoted: bool = Field(
        default=False,
        description="True if promoted to primary skill status"
    )


class Annotation(BaseModel):
    """
    Pipeline annotation flagging issues with extraction or structure.
    
    Severity controls compilation:
    - ERROR blocks compilation
    - WARNING requires acknowledgment
    - INFO is informational only
    
    The id field is auto-computed if not provided, ensuring proper
    JSON serialization for acknowledgment tracking.
    """
    annotation_type: Literal[
        "grounding_issue",
        "narrowness_issue",
        "clarity_issue",
        "review_flag",
        "merge_proposal",
        "rubric_mismatch",
        "invariant_violation",
    ]
    severity: AnnotationSeverity
    message: str
    target_id: Optional[str] = Field(
        default=None,
        description=(
            "criterion_id, rule_id, question_id (e.g. 'q2'), or "
            "sub-question anchor (e.g. 'q2.א') this annotation targets. "
            "None = global annotation."
        ),
    )
    id: str = Field(
        default="",
        description="Unique ID for acknowledgment tracking (auto-computed if empty)"
    )
    # ---- PR-3: structured invariant context (ALL ADDITIVE, default None) ----
    # The compile-error payload used to be a flat English wall with `message_he`
    # holding a duplicate of the English string. These four fields let the editor
    # anchor a rejection to the exact node and state the arithmetic a teacher can
    # act on ("סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)").
    # Defaults are None, so every stored draft_json annotation still parses.
    invariant: Optional[str] = Field(
        default=None,
        description="Named invariant that produced this annotation, e.g. 'INV-2'.",
    )
    expected: Optional[str] = Field(
        default=None, description="Declared/expected value (stringified Decimal)."
    )
    actual: Optional[str] = Field(
        default=None, description="Computed/actual value (stringified Decimal)."
    )
    message_he: Optional[str] = Field(
        default=None,
        description="Real Hebrew message. When None the API falls back to `message`.",
    )
    
    @model_validator(mode='after')
    def compute_id(self) -> Self:
        """Compute id from annotation_type and target_id if not provided."""
        if not self.id:
            object.__setattr__(self, 'id', f"{self.annotation_type}:{self.target_id or 'global'}")
        return self



# =============================================================================
# CRITERION
# =============================================================================

class Criterion(BaseModel):
    """
    A grading criterion with optional sub-criteria breakdown.

    INV-3 (SubCriteriaPointsSum): if sub_criteria is non-empty,
    Σ sub_criterion.points must equal criterion.points (enforced by compiler).
    If sub_criteria is None/empty, the criterion is graded as an atomic unit.
    """
    criterion_id: str
    index: int = Field(..., ge=0)
    description: str = Field(..., min_length=1)
    points: Decimal = Field(..., gt=Decimal("0"))
    evaluation_guidance: Optional[str] = Field(
        default=None,
        description=(
            "Guidance for the GraderAgent: where to look in the student's answer, "
            "what the example solution demonstrates, and how to distinguish "
            "full vs partial credit for this criterion."
        ),
    )
    skill_targets: List[str] = Field(
        default_factory=list,
        description="References to SkillTarget.id"
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="References to Requirement.id"
    )
    sub_criteria: Optional[List[SubCriterion]] = Field(
        default=None,
        description=(
            "Optional breakdown of this criterion into graded sub-parts. "
            "When non-empty, INV-3 requires Σ sub_criteria.points == criterion.points. "
            "Null when the criterion is graded as an atomic unit."
        ),
    )
    extraction_confidence: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)

    @field_serializer('points')
    def serialize_points(self, v: Decimal) -> str:
        return str(v)

    @property
    def is_aligned(self) -> bool:
        """Check if criterion satisfies CriterionAlignment."""
        return len(self.skill_targets) > 0 or len(self.requirements) > 0


# =============================================================================
# SUB-QUESTION
# =============================================================================

class SubQuestion(BaseModel):
    """
    A sub-question within a parent question.

    Mirrors the foundational ontology (§4.3):
    SubQuestion {sub_question_id, index, text, points, criteria[]}

    Hebrew sub-question IDs use Hebrew letters: "א", "ב", "ג"
    English sub-question IDs use Latin letters: "a", "b", "c"

    Points are auto-aligned to Σ criteria.points by recalculateParentsFromCriteria
    in the frontend when criterion edits cascade; otherwise sq.points moves only by
    explicit teacher edit. INV-R1 enforces Σ sq.points == q.total_points at save time.
    """
    sub_question_id: str
    index: int = Field(..., ge=0, description="0-based order: 0='a'/'א', 1='b'/'ב', etc.")
    title: Optional[str] = Field(
        default=None,
        description=(
            "Editable UX-only display title for the sub-question, e.g. 'אלגוריתמים' "
            "or 'חלק תיאורטי'. None means the frontend should render the default "
            "positional label 'סעיף {index + 1}'. Pure UX metadata — does NOT "
            "participate in any rubric invariant and is NEVER included in "
            "GradingRubricContract (stripped by ContractCompiler)."
        ),
    )
    text: Optional[str] = None
    points: Decimal = Field(..., ge=Decimal("0"))
    example_solution: Optional[str] = Field(
        default=None,
        description="Per-sub-question example solution excerpt, when explicitly present in the source document.",
    )
    criteria: List[Criterion] = Field(default_factory=list)
    sub_questions: List["SubQuestion"] = Field(
        default_factory=list,
        description=(
            "Nested sub-sub-questions, e.g. '(1)','(2)' under a sub-question (FP2). "
            "RECURSIVE but DEPTH-CAPPED AT 2: a Question may have SubQuestions, and "
            "each SubQuestion may have child SubQuestions, but those children may NOT "
            "nest further (enforced by GradingRubricContract.validate_structure_exclusivity). "
            "StructureExclusivity (recursive): a node has `criteria` XOR `sub_questions`, never both."
        ),
    )
    # DOCX pipeline field — AI-proposed coverage-gap criteria for teacher review.
    # Ephemeral: populated by transformer.py, consumed by RubricEditor frontend.
    # NEVER included in GradingRubricContract (stripped by ContractCompiler).
    proposals: Optional[Dict[str, Any]] = Field(
        default=None,
        description="AI-proposed criteria awaiting teacher accept/reject"
    )

    @field_serializer('points')
    def serialize_points(self, v: Decimal) -> str:
        return str(v)

    @property
    def all_criteria(self) -> List["Criterion"]:
        """This node's direct criteria plus all criteria in descendant sub-questions."""
        result = list(self.criteria)
        for sq in self.sub_questions:
            result.extend(sq.all_criteria)
        return result

    @property
    def all_sub_questions(self) -> List["SubQuestion"]:
        """All descendant sub-questions (self excluded), depth-first."""
        result: List["SubQuestion"] = []
        for sq in self.sub_questions:
            result.append(sq)
            result.extend(sq.all_sub_questions)
        return result


# =============================================================================
# QUESTION
# =============================================================================

class Question(BaseModel):
    """
    A question containing criteria for grading.
    
    A question has:
    - Direct criteria (criteria not nested inside any sub-question)
    - Sub-questions, each with their own criteria
    
    INV-1 (PointSumQuestion): total_points ≈ Σ direct criteria.points + Σ sub_question.points
    
    Can link to SkillTargets and Requirements at the question level,
    which cascade to criteria if not overridden.
    """
    question_id: str
    question_type: QuestionType = QuestionType.SHORT_ANSWER
    question_text: Optional[str] = None
    total_points: Decimal = Field(..., gt=Decimal("0"))
    allow_multiple_valid_forms: bool = Field(
        default=False,
        description="True if multiple solution approaches are valid"
    )
    skill_targets: List[SkillTarget] = Field(default_factory=list)
    requirements: List[Requirement] = Field(default_factory=list)
    criteria: List[Criterion] = Field(
        default_factory=list,
        description="Direct criteria (not inside any sub-question)"
    )
    sub_questions: List[SubQuestion] = Field(
        default_factory=list,
        description="Sub-questions (e.g. א, ב, ג), each with their own criteria"
    )
    # DOCX pipeline fields — populated by transformer.py, passed through to the API
    # response and consumed by the frontend (RubricEditor).
    # Optional so PDF-sourced rubrics and existing saved rubrics remain valid.
    example_solution: Optional[str] = Field(
        default=None,
        description="Teacher's model solution, extracted verbatim from the DOCX"
    )
    trace_tables: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Code execution trace tables (TRACE_TABLE type). "
                    "Each entry: {headers: [...], rows: [{col: val}], row_count: N}"
    )
    context_tables: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Question context tables (QUESTION_LAYOUT_TABLE / EXAMPLE_DATA_TABLE / OTHER_TABLE "
                    "with belongs_to_question set). E.g. class interface definitions, I/O data tables. "
                    "Each entry: {headers: [...], rows: [{col: val}], row_count: N}"
    )
    # DOCX pipeline field — AI-proposed coverage-gap criteria for teacher review.
    # Ephemeral: populated by transformer.py, consumed by RubricEditor frontend.
    # NEVER included in GradingRubricContract (stripped by ContractCompiler).
    proposals: Optional[Dict[str, Any]] = Field(
        default=None,
        description="AI-proposed criteria awaiting teacher accept/reject"
    )

    @field_serializer('total_points')
    def serialize_total_points(self, v: Decimal) -> str:
        return str(v)
    
    @field_serializer('question_type')
    def serialize_question_type(self, v: QuestionType) -> str:
        return v.value
    
    @property
    def all_criteria(self) -> List[Criterion]:
        """All criteria: direct + from all sub-questions AT ANY DEPTH. Read-only accessor."""
        result = list(self.criteria)
        for sq in self.sub_questions:
            result.extend(sq.all_criteria)
        return result

    @property
    def all_sub_questions(self) -> List["SubQuestion"]:
        """All sub-questions at any depth, depth-first."""
        result: List["SubQuestion"] = []
        for sq in self.sub_questions:
            result.append(sq)
            result.extend(sq.all_sub_questions)
        return result


# =============================================================================
# STUDENT ANSWER
# =============================================================================

class StudentAnswer(BaseModel):
    """
    Student's submitted work for grading.
    
    Used as input to evidence extractors.
    """
    answer_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    question_id: str
    content: str = Field(..., description="Raw text/code submitted by student")
    content_type: Literal["text", "code", "image_transcription"] = "text"


# =============================================================================
# RULE OUTCOME (Grading Output)
# =============================================================================

class RuleOutcome(BaseModel):
    """
    Result of evaluating one ReductionRule against one StudentAnswer.

    Structural contract: Contains exactly ONE EvidenceClaim.
    This prevents non-deterministic "claim dumping" behavior.
    """
    rule_id: str
    selected_level_id: str
    points_awarded: Decimal
    evidence_claim: EvidenceClaim

    needs_review: bool = Field(
        default=False,
        description="Flag for teacher attention"
    )
    review_reason: Optional[str] = Field(
        default=None,
        description="Why this outcome is flagged for review"
    )
    
    @field_serializer('points_awarded')
    def serialize_points_awarded(self, v: Decimal) -> str:
        return str(v)
    
    @model_validator(mode='after')
    def validate_evidence_exists(self) -> Self:
        """
        Invariant 4: EvidenceCitation (structural enforcement)
        
        Every RuleOutcome must have exactly one EvidenceClaim
        with at least one AnswerQuotation.
        """
        if self.evidence_claim is None:
            raise ValueError("evidence_claim is required (INV-4)")
        if len(self.evidence_claim.answer_quotations) < 1:
            raise ValueError("At least one AnswerQuotation required (INV-4)")
        return self


# =============================================================================
# v2.0 GRADING OUTPUT MODELS
# =============================================================================

class FlaggedOutcome(BaseModel):
    """
    An outcome flagged for teacher attention.
    
    Used by GradedTestDraft to indicate items that need human review.
    Can reference a specific rule, criterion, or question.
    """
    rule_id: Optional[str] = None
    criterion_id: Optional[str] = None
    question_id: Optional[str] = None
    reason: FlagReason
    message: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of the flag"
    )
    
    @field_serializer('reason')
    def serialize_reason(self, v: FlagReason) -> str:
        return v.value


# =============================================================================
# SELECTION GROUPS (FP1)
# =============================================================================

class SelectionGroup(BaseModel):
    """
    A 'choose k of N' selection constraint over a set of questions.

    Israeli Bagrut exams frequently offer more questions than the student
    answers (e.g. 'answer 4 of 6'). The sum of all OFFERED question points
    therefore exceeds the achievable total; modelling that as a rubric-total
    error is wrong (it is the failure mode FP1 fixes).

    A question listed in no group is MANDATORY (always answered). Achievable
    points = Σ(mandatory question points) + Σ over groups of the top `choose_k`
    question totals within the group. With no groups, achievable = Σ all
    question totals — i.e. the selection-aware rule reduces to the old INV-4.

    `of_question_ids` reference Question.question_id ('q1', 'q2', ...).
    `label` is display-only and participates in no invariant.
    """
    group_id: str = Field(..., description="Stable id, e.g. 'sg0'.")
    choose_k: int = Field(..., ge=1, description="How many questions the student must answer from this group.")
    of_question_ids: List[str] = Field(..., min_length=1, description="Question ids in this group, e.g. ['q1','q2','q3'].")
    label: Optional[str] = Field(default=None, description="Display-only, e.g. 'פרק ראשון'. Not an invariant.")

    @model_validator(mode='after')
    def validate_choose_k(self) -> Self:
        if self.choose_k > len(self.of_question_ids):
            raise ValueError(
                f"SelectionGroup {self.group_id}: choose_k={self.choose_k} exceeds "
                f"group size {len(self.of_question_ids)}."
            )
        return self


# =============================================================================
# PEDAGOGICAL MISTAKES (teacher-induced rubric errors: detect → suggest → surface)
# =============================================================================

class PedagogicalMistakeKind(str, Enum):
    """Kinds of teacher-induced rubric error the detector can surface."""
    POINT_SUM_MISMATCH = "point_sum_mismatch"            # criteria don't sum to the declared total
    SELECTION_NORMALIZATION = "selection_normalization"  # non-uniform selection weights -> ambiguous/unfair total
    STRUCTURAL_MISLABEL = "structural_mislabel"          # a criterion/sub-q tagged under the wrong scope (content mismatch)
    ORPHAN_CRITERION = "orphan_criterion"                # a criterion that matches no sub-question's content


class SuggestedFix(BaseModel):
    """A concrete, machine-applicable correction the teacher can accept/reject in RubricEditor."""
    operation: str = Field(..., description="'reassign_subquestion' | 'adjust_points' | 'clarify_normalization' | ...")
    description: str = Field(..., description="Human-readable (Hebrew) summary of the proposed fix.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific args, e.g. {'from':'ב','to':'ג'}.")


class PedagogicalMistake(BaseModel):
    """
    A detected error IN THE TEACHER'S RUBRIC (not in extraction). Distinct from
    Annotation: it carries a suggested fix and an explicit 'needs teacher input'
    flag. Produced by a deterministic post-extraction analyzer; NEVER auto-applied —
    surfaced in RubricEditor for the teacher to accept/edit/reject (validation is the
    product). The Draft stays FAITHFUL to the rubric as written; the fix is applied
    only on teacher approval, at compile time.
    """
    mistake_id: str
    kind: PedagogicalMistakeKind
    severity: AnnotationSeverity = AnnotationSeverity.WARNING
    target_id: Optional[str] = Field(default=None, description="Scope anchor (question/sub-question/criterion id).")
    explanation: str = Field(..., description="What is wrong, in the teacher's language (Hebrew).")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="The numbers/labels that prove it.")
    suggested_fix: Optional[SuggestedFix] = Field(
        default=None, description="A concrete fix when inferable; None when the teacher must decide.")
    requires_teacher_input: bool = Field(
        default=False, description="True when no auto-fix exists (e.g. normalization intent is unknowable).")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# =============================================================================
# ARTIFACT MODELS
# =============================================================================

class ExtractRubricResponse(BaseModel):
    """
    Editable pipeline artifact for teacher review.
    
    Contains rich metadata that is stripped during compilation:
    - approach_classes
    - annotations
    - extraction_metadata
    
    Teachers review and edit this before saving.
    """
    schema_version: str = "2.0"
    rubric_id: str = Field(default_factory=lambda: str(uuid4()))
    rubric_name: str = ""
    subject: str = "computer_science"
    programming_language: Optional[str] = None
    total_points: Decimal = Decimal("0")
    questions: List[Question] = Field(default_factory=list)
    selection_groups: List[SelectionGroup] = Field(
        default_factory=list,
        description=(
            "Optional 'choose k of N' constraints (FP1). Empty ⇒ all questions answered. "
            "Drives achievable_points and the selection-aware INV-4."
        ),
    )
    pedagogical_mistakes: List[PedagogicalMistake] = Field(
        default_factory=list,
        description=(
            "Detected teacher-induced rubric errors (mislabels, sum mismatches, normalization "
            "ambiguities) with suggested fixes, surfaced to the teacher in RubricEditor. The "
            "Draft itself stays faithful to the rubric as written; fixes apply only on approval."
        ),
    )

    # Pipeline-only fields (stripped during compilation)
    approach_classes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Internal use for validation, not in contract"
    )
    annotations: List[Annotation] = Field(default_factory=list)
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Convenience fields for backward compatibility with extraction pipeline
    # These are aliases/computed from core fields
    name: Optional[str] = Field(default=None, description="Alias for rubric_name (backward compat)")
    description: Optional[str] = Field(default=None, description="Optional rubric description")
    document_context: Optional[str] = Field(default=None, description="Full document text for grading AI")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Alias for extraction_metadata")
    
    @field_serializer('total_points')
    def serialize_total_points(self, v: Decimal) -> str:
        return str(v)
    
    @model_validator(mode='after')
    def sync_aliases(self) -> Self:
        """Synchronize aliased fields for backward compatibility."""
        # Sync name <-> rubric_name
        if self.name and not self.rubric_name:
            object.__setattr__(self, 'rubric_name', self.name)
        elif self.rubric_name and not self.name:
            object.__setattr__(self, 'name', self.rubric_name)
        # Sync metadata <-> extraction_metadata
        if self.metadata and not self.extraction_metadata:
            object.__setattr__(self, 'extraction_metadata', self.metadata)
        elif self.extraction_metadata and not self.metadata:
            object.__setattr__(self, 'metadata', self.extraction_metadata)
        return self
    
    @property
    def num_questions(self) -> int:
        """Count of questions in this rubric."""
        return len(self.questions)
    
    @property
    def num_sub_questions(self) -> int:
        """Total count of sub-questions across all questions, AT ANY DEPTH."""
        return sum(len(q.all_sub_questions) for q in self.questions)

    @property
    def achievable_points(self) -> Decimal:
        """Max points a student can earn given selection_groups (FP1). See compute_achievable_points."""
        return compute_achievable_points(self.questions, self.selection_groups)
    
    @property
    def num_criteria(self) -> int:
        """Total count of criteria across all questions (direct + sub-question)."""
        return sum(len(q.all_criteria) for q in self.questions)
    
    @property
    def total_sub_criteria(self) -> int:
        """Total count of sub-criteria across all criteria."""
        return sum(
            len(c.sub_criteria)
            for q in self.questions
            for c in q.all_criteria
            if c.sub_criteria
        )
    
    def compile(
        self, 
        policy: NumericPolicy = None,
        acknowledged_warnings: List[str] = None
    ) -> "GradingRubricContract":
        """
        Compile to frozen GradingRubricContract.
        
        Delegates to ContractCompiler service.
        """
        from ..services.contract_compiler import ContractCompiler
        return ContractCompiler().compile(
            self, 
            policy or NumericPolicy(),
            acknowledged_warnings or []
        )


class GradingRubricContract(BaseModel):
    """
    Frozen, minimal artifact for grading agent.

    CLOSED-WORLD contract (INV-6): grader may only reference criterion_ids
    and sub_criterion_ids declared in all_criteria_ids / all_sub_criteria_ids.

    INV-5 (ContractVersionLock): contract_version is a fresh UUID on each
    compilation. Grading runs pin exactly one version; recompilation invalidates
    any in-flight grading job.

    Reproducibility: Given contract_version, grading output is deterministic.
    """
    schema_version: str = "2.0"
    contract_version: str = Field(
        ...,
        description="UUID, fresh on each compile() for reproducibility (INV-5)"
    )
    rubric_id: str
    subject: str
    programming_language: Optional[str] = None
    numeric_policy: NumericPolicy
    total_points: Decimal = Field(
        ...,
        description="Σ q.total_points. INV-4 anchor for grading validation."
    )
    questions: List[Question]
    selection_groups: List[SelectionGroup] = Field(
        default_factory=list,
        description=(
            "Propagated from the Draft by ContractCompiler (FP1). Empty ⇒ all questions "
            "answered. Grading/score-computation reads this for the achievable-points "
            "denominator. NOTE: population is part of the (deferred) ContractCompiler "
            "rewrite; the field defaults empty until then."
        ),
    )

    model_config = {"frozen": True}

    @model_validator(mode='after')
    def validate_structure_exclusivity(self) -> Self:
        """
        Recursive StructureExclusivity + depth cap (FP2).

        Every node (Question or SubQuestion) must have `criteria` XOR `sub_questions`,
        never both. Nesting is capped at depth 2: a Question's sub-questions may have
        child sub-questions, but those children may NOT nest further.
        """
        MAX_SUBQ_DEPTH = 2

        def check_node(node, label: str, depth: int) -> None:
            has_children = bool(getattr(node, "sub_questions", None))
            has_criteria = bool(getattr(node, "criteria", None))
            if has_children and has_criteria:
                raise ValueError(
                    f"{label} has both sub_questions and direct criteria — "
                    "use one or the other, never both (recursive StructureExclusivity)."
                )
            if has_children:
                if depth >= MAX_SUBQ_DEPTH:
                    raise ValueError(
                        f"{label} nests sub-questions beyond the depth-{MAX_SUBQ_DEPTH} cap "
                        "(Question → SubQuestion → SubSubQuestion is the limit)."
                    )
                for sq in node.sub_questions:
                    check_node(sq, f"{label}.{sq.sub_question_id}", depth + 1)

        for q in self.questions:
            check_node(q, q.question_id, depth=0)
        return self

    @property
    def achievable_points(self) -> Decimal:
        """Max points a student can earn given selection_groups (FP1)."""
        return compute_achievable_points(self.questions, self.selection_groups)

    @field_serializer('total_points')
    def serialize_total_points(self, v: Decimal) -> str:
        return str(v)

    @property
    def all_criteria_ids(self) -> List[str]:
        """All criterion_ids. ClosedWorld (INV-6): grader must only reference these."""
        return [c.criterion_id for q in self.questions for c in q.all_criteria]

    @property
    def all_sub_criteria_ids(self) -> List[str]:
        """All sub_criterion_ids. ClosedWorld (INV-6): grader must only reference these."""
        return [
            sc.sub_criterion_id
            for q in self.questions
            for c in q.all_criteria
            for sc in (c.sub_criteria or [])
        ]


# =============================================================================
# EXCEPTIONS
# =============================================================================

class OntologyValidationError(Exception):
    """Base exception for ontology validation failures."""
    pass


class CompilationError(OntologyValidationError):
    """Raised when compilation is blocked by error-severity annotations."""
    def __init__(self, message: str, errors: List[Annotation] = None):
        super().__init__(message)
        self.errors = errors or []


class WarningsRequireAcknowledgment(OntologyValidationError):
    """Raised when unacknowledged warnings block compilation."""
    def __init__(self, warnings: List[Annotation]):
        super().__init__(f"{len(warnings)} warning(s) require acknowledgment")
        self.warnings = warnings


class ClosedWorldViolation(OntologyValidationError):
    """Raised when grading agent references non-existent IDs."""
    pass


class EvidenceCitationViolation(OntologyValidationError):
    """Raised when RuleOutcome lacks required evidence."""
    pass


class DoubleCountingViolation(OntologyValidationError):
    """Raised when same span+claimType deducts twice without dependsOn."""
    pass


class VersionMismatchError(OntologyValidationError):
    """Raised when contract has been recompiled since grading request."""
    pass


# =============================================================================
# TYPE ALIASES
# =============================================================================

# Semantic alias for code that emphasizes editability over extraction
# ExtractRubricResponse = output of extraction pipeline
# DraftRubric = what teachers edit before compilation
DraftRubric = ExtractRubricResponse


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compute_achievable_points(
    questions: List["Question"],
    selection_groups: List["SelectionGroup"],
) -> Decimal:
    """
    Max points a student can earn given selection constraints (FP1).

    achievable = Σ(mandatory question points) + Σ over groups of [top choose_k totals].
    A question in no group is mandatory. With no groups, achievable = Σ all question
    totals — i.e. the selection-aware rule reduces to the legacy INV-4. A group member
    id not found among `questions` contributes 0 (the dangling reference is surfaced by
    structural validation, not silently corrected here).
    """
    by_id: Dict[str, Decimal] = {q.question_id: q.total_points for q in questions}
    grouped_ids: Set[str] = set()
    achievable = Decimal("0")
    for g in selection_groups:
        member_points = sorted(
            (by_id.get(qid, Decimal("0")) for qid in g.of_question_ids),
            reverse=True,
        )
        achievable += sum(member_points[: g.choose_k], Decimal("0"))
        grouped_ids.update(g.of_question_ids)
    for q in questions:
        if q.question_id not in grouped_ids:
            achievable += q.total_points
    return achievable

# DEAD UNTIL grader redesign — see grader-migration-TODO
# get_claim_type_for_rule_kind() was removed with RuleKind in the SubCriteria migration.
# The grading agent will need a new claim-type derivation strategy without rule kinds.
def get_claim_type_for_rule_kind(rule_kind: object) -> "ClaimType":
    raise NotImplementedError(
        "get_claim_type_for_rule_kind is removed — RuleKind no longer exists. "
        "See grader-migration-TODO."
    )


@dataclass(frozen=True)
class SubjectProfile:
    """
    Declares valid question types and evaluation strategy per subject.
    """
    subject_key: str
    display_name_he: str
    valid_question_types: Set[QuestionType]
    skill_taxonomy_key: Optional[str] = None


_UNIVERSAL_QUESTION_TYPES: Set[QuestionType] = {
    QuestionType.SHORT_ANSWER,
    QuestionType.ESSAY,
}


SUBJECT_PROFILES: Dict[str, SubjectProfile] = {
    "computer_science": SubjectProfile(
        subject_key="computer_science",
        display_name_he="מדעי המחשב",
        valid_question_types=_UNIVERSAL_QUESTION_TYPES
        | {
            QuestionType.CODING_TASK,
            QuestionType.TRACE_TABLE,
        },
        skill_taxonomy_key="bagrut_cs",
    ),
    "math": SubjectProfile(
        subject_key="math",
        display_name_he="מתמטיקה",
        valid_question_types=_UNIVERSAL_QUESTION_TYPES
        | {
            QuestionType.COMPUTATION,
            QuestionType.PROOF,
            QuestionType.WORD_PROBLEM,
        },
        skill_taxonomy_key=None,
    ),
    "english": SubjectProfile(
        subject_key="english",
        display_name_he="אנגלית",
        valid_question_types=_UNIVERSAL_QUESTION_TYPES
        | {
            QuestionType.READING_COMPREHENSION,
            QuestionType.GRAMMAR_EXERCISE,
            QuestionType.WRITING_TASK,
        },
        skill_taxonomy_key=None,
    ),
}


def get_subject_profile(subject: str) -> SubjectProfile:
    """Get the profile for a subject, raising ValueError if unknown."""
    profile = SUBJECT_PROFILES.get(subject)
    if not profile:
        raise ValueError(
            f"Unknown subject '{subject}'. Available: {list(SUBJECT_PROFILES.keys())}"
        )
    return profile


def validate_rubric_against_profile(
    rubric: ExtractRubricResponse,
    profile: SubjectProfile,
) -> List[str]:
    """
    Validate that all question types in a rubric are valid for the declared subject.

    Returns list of warning messages (empty list = valid).
    """
    warnings: List[str] = []

    for q in rubric.questions:
        if q.question_type not in profile.valid_question_types:
            warnings.append(
                f"Question {q.question_id}: question_type '{q.question_type}' "
                f"is not valid for subject '{profile.subject_key}'"
            )

    return warnings

# =============================================================================
# PYDANTIC FORWARD-REF REBUILD (recursive SubQuestion, FP2)
# =============================================================================
# SubQuestion.sub_questions: List["SubQuestion"] is self-referential; with
# `from __future__ import annotations` the annotation is a string, so rebuild
# the models once all names are bound.
SubQuestion.model_rebuild()
Question.model_rebuild()
ExtractRubricResponse.model_rebuild()
GradingRubricContract.model_rebuild()