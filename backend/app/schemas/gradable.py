"""
GradableTest domain schemas — in-memory only, never persisted.

GradableTest is the marriage object: RubricContract + TranscriptionContract,
closed-world per-question pre-sliced. Built by gradable_compiler.compile(),
consumed by GraderAgent (S7). Recomputed on demand from two pinned contract
versions — never cached (Phase 0a §8).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, field_serializer, Field


class GradableSubCriterion(BaseModel):
    """Leaf grading unit when a criterion has a sub-criteria breakdown."""

    model_config = {"frozen": True}

    sub_criterion_id: str
    description: str
    points: Decimal

    @field_serializer("points")
    def _sp(self, v: Decimal) -> str:
        return str(v)


class GradableCriterion(BaseModel):
    """
    One criterion as seen by the GraderAgent.

    sub_criteria is a flat leaf list (Optional[List[GradableSubCriterion]]),
    not recursive. When present, the agent grades each sub-criterion individually;
    the parent criterion provides context only.
    """

    model_config = {"frozen": True}

    criterion_id: str
    description: str
    points: Decimal
    evaluation_guidance: Optional[str] = None
    notes: Optional[str] = None
    sub_criteria: Optional[List[GradableSubCriterion]] = None

    @field_serializer("points")
    def _sp(self, v: Decimal) -> str:
        return str(v)


class PriorPartContext(BaseModel):
    """PR-G1 v2 (RATIFIED 2026-08-25): read-only context about one PRECEDING
    sub-question of the same question — the prefix the student had already
    answered when they wrote the current part.

    OWNER-RATIFIED SHAPE — prior criteria and prior awarded points are
    DELIBERATELY EXCLUDED; do not add them. The context exists so the grader
    can resolve references ("כמו בסעיף א"), never to grade or re-grade the
    prior part.
    """

    model_config = {"frozen": True}

    sub_question_id: str                       # full path within the question
    sub_question_text: str
    example_solution: Optional[str] = None
    student_answer_text: Optional[str] = None
    answer_missing: bool = False


class GradableScope(BaseModel):
    """
    One gradable unit — either a direct-criteria question or a single sub-question.

    scope_kind="direct"       — question has direct criteria; sub_question_id is None.
    scope_kind="sub_question" — one sub-question; sub_question_id identifies it.

    Closed-world by construction (CW-1): `criteria` IS the full criterion set for
    this scope. The agent cannot reference criterion IDs outside this list.

    alignment values:
      "matched"              — a transcription answer was found for this scope.
      "answer_missing"       — no transcription answer matched; student_answer_text=None.
      "scope_not_in_contract"— reserved for future agent/UI use; compiler does not emit it.
    """

    model_config = {"frozen": True}

    scope_kind: Literal["direct", "sub_question"]

    # Identity
    question_id: str
    sub_question_id: Optional[str] = None  # set when scope_kind == "sub_question"

    # Closed-world criterion set for this scope only
    criteria: List[GradableCriterion]
    points: Decimal  # question.total_points (direct) or sub_question.points

    # Grading context — survives compilation after S6 ContractCompiler fix
    example_solution: Optional[str] = None  # question or sub-question level
    trace_tables: Optional[List[Dict[str, Any]]] = None   # question-level; carried to sub-q scopes
    context_tables: Optional[List[Dict[str, Any]]] = None  # question-level; carried to sub-q scopes
    question_text: Optional[str] = None
    sub_question_text: Optional[str] = None  # None for direct scopes

    # Student's answer for this scope
    student_answer_text: Optional[str] = None  # None when alignment == "answer_missing"
    alignment: Literal["matched", "answer_missing", "scope_not_in_contract"]

    # WHERE that answer CAME FROM. The text alone cannot say whether the
    # transcription addressed this leaf directly or whether the leaf inherited
    # its nearest ancestor's answer (the R3 fallback below) — and those are
    # different facts to anyone judging the grade.
    #
    #   "own"       — the transcription answered this exact scope id.
    #   "inherited" — it answered an ANCESTOR, and this leaf is graded against
    #                 that text; `answer_inherited_from` names the ancestor path.
    #   None        — alignment == "answer_missing"; there is no answer to source.
    #
    # `fallback_scopes` already counted these firings for the metric; this
    # records, per scope, the one thing a reader needs to interpret the grade.
    answer_source: Optional[Literal["own", "inherited"]] = None
    answer_inherited_from: Optional[str] = None  # e.g. "א" for the leaf "א.1"

    # PR-G1 v2 (2026-08-25): prefix-only prior-part context — all preceding
    # parts of the same question in document order; NEVER the current part,
    # never subsequent ones. [] for direct-criteria questions and first parts.
    # Additive with a safe default: existing constructors are untouched.
    prior_parts: List[PriorPartContext] = Field(default_factory=list)

    @field_serializer("points")
    def _sp(self, v: Decimal) -> str:
        return str(v)


class UnmatchedAnswer(BaseModel):
    """
    A transcription answer that matched no contract scope.

    Data for the teacher, not an error. The compiler never raises on orphans.
    Primary orphan channel in GradableTest.
    """

    model_config = {"frozen": True}

    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    reason: str  # e.g. "no contract question at position 4"


class GradableTest(BaseModel):
    """
    The GraderAgent's typed input. In-memory only — never persisted (Phase 0a §8).

    Deterministic: same (rubric_contract_version, transcription_contract_version)
    pair always produces the same GradableTest. Recompute; don't cache.
    """

    model_config = {"frozen": True}

    schema_version: str = "1.0"
    rubric_contract_version: str           # pinned rubric version, for audit/reproducibility
    transcription_contract_version: str    # pinned transcription version
    # Subject seam (2026-09-08): the rubric contract's subject KEY, so the grader
    # can select its profile. A key only — modalities/fragments never travel on
    # this type (docs/MULTISUBJECT_PLAN.md C2 "where it leaks"). Defaulted so every
    # existing constructor call stays valid and byte-identical.
    subject: str = "computer_science"

    scopes: List[GradableScope]                            # per-unit slices the agent iterates
    unmatched_transcription_answers: List[UnmatchedAnswer]  # orphans — data, not errors
    total_points: Decimal                                  # Σ scope.points — sanity anchor
    # PR-3 (R3): leaf scopes that had to inherit an ancestor's answer text because the
    # transcription was segmented shallower than the rubric. This is LOAD-BEARING for
    # every nested rubric, not a graceful degradation — its rate is the metric for when
    # the transcription depth-2 segmentation follow-up becomes urgent.
    parent_answer_fallback_scopes: List[str] = Field(default_factory=list)
    # ALPHA-GAP A-4 (D-2): no page reference per scope; alpha adds `page_numbers` so a figure scope can carry its page.

    @field_serializer("total_points")
    def _sp(self, v: Decimal) -> str:
        return str(v)
