"""
GradedTestDraft domain schemas — in-memory S7 grading output.

These are the NEW outcome types produced by GraderAgent (S7).
They are DISTINCT from the legacy GradedTestDraft/CriterionOutcome in
ontology_types.py, which remain untouched until graded_json is dropped.

GradedTestDraft   → graded_tests.draft_json  (persisted by S8)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer

from app.schemas.gradable import UnmatchedAnswer
from app.schemas.ontology_types import (
    AnnotationSeverity,
    AnswerQuotation,
    FlaggedOutcome,
)


# ---------------------------------------------------------------------------
# Teacher override types — S9
# Sparse terminal-level overlay: only terminals the teacher actually changed.
# ---------------------------------------------------------------------------

class TeacherOverride(BaseModel):
    """
    Teacher's edit for one terminal criterion.
    Always carries the effective points_awarded (AI's value if unchanged, teacher's if changed).
    Presence in the map means "the teacher touched this terminal."
    """
    points_awarded: Decimal
    teacher_comment: Optional[str] = None

    @field_serializer("points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


# key = terminal_id (criterion_id for leaf criteria, sub_criterion_id for sub-criteria)
GradedTestOverrides = Dict[str, TeacherOverride]


# ---------------------------------------------------------------------------
# GradingAnnotation — grading-domain diagnostic surface
# Mirrors TranscriptionAnnotation (app/schemas/transcription.py) exactly.
# ---------------------------------------------------------------------------

class GradingAnnotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    severity: AnnotationSeverity
    target_id: str  # criterion_id | sub_criterion_id | question_id | scope composite
    annotation_type: Literal[
        "closed_world_violation",
        "ungraded_criterion",
        "bounds_clamped",
        "quote_not_found",
        "fuzzy_match",
        "no_answer",
        "llm_failure",
    ]
    message: str  # Hebrew, user-facing
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Outcome hierarchy (flat-recursive — one level of sub_criterion_outcomes)
# ---------------------------------------------------------------------------

class SubCriterionOutcome(BaseModel):
    """Leaf grading result when a criterion has sub_criteria (one-level depth)."""

    sub_criterion_id: str
    description: str                        # denormalized for display
    points_possible: Decimal
    points_awarded: Decimal                 # bounded [0, points_possible] by validator
    reasoning: str                          # Hebrew
    confidence: float                       # 0.0–1.0 LLM self-assessed per leaf
    evidence_quote: Optional[AnswerQuotation] = None
    flags: List[FlaggedOutcome] = Field(default_factory=list)

    @field_serializer("points_possible", "points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class CriterionOutcome(BaseModel):
    """
    Grading result for one criterion.

    Leaf criterion (no sub_criterion_outcomes): graded directly.
    Branch criterion (has sub_criterion_outcomes): points_awarded = Σ children.
    The branch criterion is NOT graded directly — its children are (terminal grading).
    confidence = min(sub_criterion confidences) for branches.
    """

    criterion_id: str
    description: str
    points_possible: Decimal
    points_awarded: Decimal
    reasoning: str                          # Hebrew; empty string for branch criteria
    confidence: float                       # 0.0–1.0; min of children for branches
    evidence_quote: Optional[AnswerQuotation] = None
    sub_criterion_outcomes: Optional[List[SubCriterionOutcome]] = None
    flags: List[FlaggedOutcome] = Field(default_factory=list)

    @field_serializer("points_possible", "points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class ScopeOutcome(BaseModel):
    """
    Grading result for one GradableScope (1:1 with GradableTest.scopes input).

    graded_by signals how this scope got its outcome:
      "llm"                   — normal grade path; LLM was called
      "skipped_no_answer"     — alignment=="answer_missing" or empty answer; deterministic 0
      "failed"                — LLM call failed after retry; degraded to flagged 0-outcome
      "excluded_by_selection" — PR-3. A member of a "choose k of N" group that did NOT
                                make the student's best-k. It is EXCLUDED from the score,
                                NOT given 0: on a choose-4-of-6 exam the two unchosen
                                questions are not failures, they were never owed.

    IMPORTANT — "excluded_by_selection" is DERIVED STATE, recorded for display/audit
    ONLY. The scoring math NEVER reads it (see services/selection_scoring.py): the
    counted/excluded split is recomputed from the CURRENT scores at every site. It has
    to be, because a teacher override can change which member is best-k (bump the
    15-pointer above the 50-pointer and membership flips). So the mark written at
    grading time is PROVISIONAL; the approval gate recomputes it from post-override
    scores and that recomputation is what gets frozen into the contract.

    min_confidence = min terminal confidence in this scope.
    0.0 for skipped and failed scopes (no grade was produced).
    """

    scope_kind: Literal["direct", "sub_question"]
    question_id: str
    sub_question_id: Optional[str] = None
    points_possible: Decimal
    points_awarded: Decimal                 # Σ criterion_outcomes.points_awarded
    min_confidence: float                   # review-queue triage signal
    criterion_outcomes: List[CriterionOutcome]
    flags: List[FlaggedOutcome] = Field(default_factory=list)
    graded_by: Literal["llm", "skipped_no_answer", "failed", "excluded_by_selection"]
    retry_count: int = 0                    # 0 = first-try success/failure; 1 = needed retry
    input_tokens: int = 0                   # S8 — LLM input tokens for this scope; 0 for skipped/failed
    output_tokens: int = 0                  # S8 — LLM output tokens for this scope; 0 for skipped/failed

    @field_serializer("points_possible", "points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


# ---------------------------------------------------------------------------
# GradedTestDraft — the agent's complete in-memory output
# ---------------------------------------------------------------------------

class GradedTestDraft(BaseModel):
    """
    Complete in-memory output of GraderAgent.grade().

    Never persisted by S7. S8 writes this to graded_tests.draft_json.
    teacher_overrides is EMPTY at draft time; S9 populates it.
    """

    schema_version: str = "1.0"
    rubric_contract_version: str            # echoed from GradableTest — audit/reproducibility
    transcription_contract_version: str
    model_version: str                      # settings.openai_model used
    prompt_version: str                     # GRADING_PROMPT_VERSION from prompt.py

    scope_outcomes: List[ScopeOutcome]
    teacher_overrides: GradedTestOverrides = Field(default_factory=dict)  # EMPTY at S7; S9 populates

    annotations: List[GradingAnnotation] = Field(default_factory=list)
    unmatched_transcription_answers: List[UnmatchedAnswer] = Field(default_factory=list)

    llm_calls_count: int                    # count of scopes that took the LLM grade path
    grading_duration_ms: int                # wall-clock for the whole parallel grade
    total_input_tokens: int = 0             # S8 — Σ scope_outcomes.input_tokens
    total_output_tokens: int = 0            # S8 — Σ scope_outcomes.output_tokens
