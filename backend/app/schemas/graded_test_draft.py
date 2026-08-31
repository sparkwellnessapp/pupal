"""
GradedTestDraft domain schemas — in-memory S7 grading output.

These are the NEW outcome types produced by GraderAgent (S7).
They are DISTINCT from the legacy GradedTestDraft/CriterionOutcome in
ontology_types.py, which remain untouched until graded_json is dropped.

GradedTestDraft   → graded_tests.draft_json  (persisted by S8)
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import model_validator, BaseModel, Field, field_serializer

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

class StampPosition(BaseModel):
    """Where the approved stamp sits on page 1 — a corner, or a normalized
    point. Set by the teacher or auto-chosen; PR-G9 renders it."""
    corner: Optional[Literal["tl", "tr", "bl", "br"]] = None
    x: Optional[float] = None
    y: Optional[float] = None
    # [PR-G9] WHO chose this. "auto" = the corner picker's guess, which «apply
    # to all» may replace; "manual" = the teacher dragged it, which it may not.
    # Absent on positions written before this field existed — those predate the
    # manual affordance entirely, so they are all picker output and read as auto.
    source: Literal["auto", "manual"] = "auto"


class TeacherOverride(BaseModel):
    """The teacher's decision on ONE check.

    An override is a VERDICT, not a number. Points are derived from verdicts by
    `app/services/pricing.py`, in one direction, everywhere — so there is no
    `points_awarded` here and no second pricing path to keep in agreement.

    (R-2, owner ruling: decide by count. The production count of unapproved
    v3-era drafts carrying an overlay was 0 — in fact `graded_tests` was empty —
    so the simple branch applies with no legacy path and no data migration.)
    """
    check_id: str
    verdict: Literal["met", "partially_met", "not_met"]
    teacher_comment: Optional[str] = None      # the "H" note; no new field
    evidence_disputed: bool = False
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GradedTestOverrides(BaseModel):
    """The teacher's working copy, laid over the draft — never mutating it.

    SPARSE: only what she touched appears, so everything she did not look at
    keeps the AI's record. A terminal maps to a LIST because a terminal has
    several checks and she may decide any subset of them.
    """
    # An old-shape payload ({terminal_id: {points_awarded: ...}}) would otherwise
    # parse as an EMPTY overlay: 200 OK, every override silently discarded. A
    # wrong shape must be loud (422), never a quiet no-op.
    model_config = {"extra": "forbid"}

    # terminal_id -> her decisions on that terminal's checks
    terminals: Dict[str, List[TeacherOverride]] = Field(default_factory=dict)
    # scope_id | "summary" -> her edited feedback text
    feedback: Dict[str, str] = Field(default_factory=dict)
    stamp_position: Optional[StampPosition] = None

    def overrides_for(self, terminal_id: str) -> List[TeacherOverride]:
        return self.terminals.get(terminal_id, [])

    def all_check_ids(self) -> List[str]:
        return [o.check_id for lst in self.terminals.values() for o in lst]


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
        # grader-v5 Plan/Verify/Price (additive)
        "unverified_check",      # a plan check received no verdict from the model
        "evidence_unverified",   # met on an unverifiable span — credit refused by the pricer
        "tariff_coerced",        # partially_met on a binary tariff — treated as fired
        "charge_group_dedup",    # tariff suppressed: its charge_group already fired
        "note_only",             # rubric says note-don't-deduct — the observation, recorded
        "cascade_routed",        # Stage-3 router: scope escalated to the champion (trigger in metadata)
        # [PR-G4] the feedback call failed; the GRADE is unaffected and the
        # draft lands regardless — INFO, never a blocker.
        "feedback_unavailable",
    ]
    message: str  # Hebrew, user-facing
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Outcome hierarchy (flat-recursive — one level of sub_criterion_outcomes)
# ---------------------------------------------------------------------------

class Check(BaseModel):
    """One plan check as the grader priced it — the atomic unit the teacher
    reviews (PR-G1, spec §1.1).

    Field names follow the EXISTING AssessedVerdict vocabulary (`basis_he`,
    `confidence`) rather than inventing parallel ones (rev-3 correction).
    `confidence` is carried for the eval suite and is never rendered.

    The pricing inputs (`kind`, `points`, `tariff`, `partial_fraction`) ride
    along because §1.1 makes the terminal's awarded_points DERIVED and has the
    client re-derive it from the verdicts: a verdict plus a bare tariff cannot
    price a `required` check. Spec §1.1 listed only `tariff`; that is a spec
    bug, fixed here and reported.

    NOT PRESENT: `audit` (reserved out of v1 by ruling R-8 — dropped from the
    wire, not shipped dark) and `equivalence_note` (never invented).
    """

    check_id: str                       # stable under plan_version
    text: str                           # the plan's own Hebrew phrasing
    kind: Literal["required", "tariff", "note_only"]
    points: Decimal                     # required: the credit at stake; else 0
    tariff: Optional[Decimal] = None    # tariff only
    partial_fraction: Decimal = Decimal("0.5")
    # Same-defect-once, scope-wide. Without it neither the composer nor
    # the client can reproduce the pricer's dedup, and a defect charged
    # once by the grader would be charged twice on review.
    charge_group: Optional[str] = None
    verdict: Literal["met", "partially_met", "not_met"]
    quote: Optional[str] = None         # None when not_met, or when unverifiable
    quote_status: Optional[Literal["exact", "fuzzy", "not_found"]] = None
    basis_he: str = ""                  # lean: "" on met (the quote speaks)
    confidence: float = 0.0

    @field_serializer("points", "tariff", "partial_fraction")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return None if v is None else str(v)


class SubCriterionOutcome(BaseModel):
    """Leaf grading result when a criterion has sub_criteria (one-level depth)."""

    sub_criterion_id: str
    description: str                        # denormalized for display
    points_possible: Decimal
    points_awarded: Decimal                 # bounded [0, points_possible] by validator
    reasoning: str                          # Hebrew
    confidence: float                       # 0.0–1.0 LLM self-assessed per leaf
    evidence_quote: Optional[AnswerQuotation] = None
    # grader-v5: DECLARED multi-span evidence (one verified span per plan check).
    # None on the v3 single-quote path. When present, evidence_quote holds the
    # first span for legacy display and each span validates independently —
    # the structural fix for the E8 T1-STITCHED finding (a model whose reasoning
    # spans several places must not be forced to fabricate contiguity).
    evidence_quotes: Optional[List[AnswerQuotation]] = None
    # [PR-G1] the per-check record; REQUIRED under a v5 pin (validator on the
    # draft), None on v3 drafts so every existing row stays parseable.
    checks: Optional[List[Check]] = None
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
    evidence_quotes: Optional[List[AnswerQuotation]] = None   # grader-v5 multi-span (see SubCriterionOutcome)
    sub_criterion_outcomes: Optional[List[SubCriterionOutcome]] = None
    checks: Optional[List[Check]] = None          # [PR-G1] leaf criteria only
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
    cached_input_tokens: Optional[int] = None   # provider-reported cache reads (None: not broken out)

    @field_serializer("points_possible", "points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


# ---------------------------------------------------------------------------
# GradedTestDraft — the agent's complete in-memory output
# ---------------------------------------------------------------------------

class FeedbackText(BaseModel):
    """One piece of student-facing feedback, with the basis it was written for.

    `basis_hash` is sha256 of the ORDERED EFFECTIVE VERDICT VECTOR at generation
    (OD-G4.1). Staleness is derived from it rather than stored as a flag: when
    the verdicts move, the text says so by construction instead of relying on
    someone remembering to invalidate it.
    """
    text: str
    basis_hash: str = ""


class FeedbackBlock(BaseModel):
    """Per-scope feedback plus a whole-test summary (spec §1.3).

    Generated ONCE per test, strictly AFTER pricing, from the priced verdicts.
    `None` on the draft is a first-class state — the call may fail and the grade
    must still land (review-first, not guess) — not an error the UI hides.
    """
    scopes: Dict[str, FeedbackText] = Field(default_factory=dict)
    summary: FeedbackText
    model_version: str
    prompt_version: str


class GradedTestDraft(BaseModel):
    """
    Complete in-memory output of GraderAgent.grade().

    Never persisted by S7. S8 writes this to graded_tests.draft_json.
    teacher_overrides is EMPTY at draft time; S9 populates it.
    """

    schema_version: str = "1.0"
    rubric_contract_version: str            # echoed from GradableTest — audit/reproducibility
    transcription_contract_version: str
    model_version: str                      # the ACTUAL model id the agent ran
    prompt_version: str                     # GRADING_PROMPT_VERSION / VERIFIER_PROMPT_VERSION
    plan_version: Optional[str] = None      # grader-v5 only: the ratified GradingPlan version
    # [PR-G4] student-facing feedback. None when the call failed — the grade
    # lands regardless; an INFO annotation says why.
    feedback: Optional[FeedbackBlock] = None
    # [COST_TRUTH, owner-ordered] the PROVIDER-REPORTED model id(s) that served
    # this grade (response metadata), distinct from model_version (what we
    # requested). None = the provider did not report one — surfaced as
    # "unreported", never silently equated with the request.
    served_models: Optional[List[str]] = None

    scope_outcomes: List[ScopeOutcome]
    teacher_overrides: GradedTestOverrides = Field(default_factory=GradedTestOverrides)  # EMPTY at S7; S9 populates

    annotations: List[GradingAnnotation] = Field(default_factory=list)
    unmatched_transcription_answers: List[UnmatchedAnswer] = Field(default_factory=list)

    llm_calls_count: int                    # count of scopes that took the LLM grade path
    grading_duration_ms: int                # wall-clock for the whole parallel grade
    total_input_tokens: int = 0             # S8 — Σ scope_outcomes.input_tokens
    total_output_tokens: int = 0            # S8 — Σ scope_outcomes.output_tokens
    total_cached_input_tokens: Optional[int] = None  # Σ cached reads when the provider reports them
    # [COST_TRUTH, cascade] per-tier token split ({model_id: {input, output,
    # cached}}) — a cascade bills two tiers and each must be priced by its own
    # card; None on single-model paths.
    cascade_usage: Optional[Dict[str, Dict[str, int]]] = None

    # [PR-G1, OD-G1.3] `checks` is optional on the TYPE so v3 drafts stay
    # parseable, and REQUIRED whenever a plan_version is stamped: under the v5
    # pin the review module renders checks and nothing else, so a terminal
    # without them would render as an empty card rather than fail loudly.
    @model_validator(mode="after")
    def _checks_required_under_v5_pin(self):
        if not self.plan_version:
            return self
        missing = []
        for scope in self.scope_outcomes:
            # The rule is "the LLM produced verdicts", not a list of exclusions.
            # graded_by has FOUR states, and `excluded_by_selection` is applied
            # AFTER grading by grading_runner's model_copy — it OVERWRITES the
            # previous value, so a scope the student left blank that also misses
            # the best-k cut arrives here as excluded_by_selection with no
            # checks. On a choose-k exam that is the common case (the questions
            # a student skips are exactly the ones excluded), and enumerating
            # exclusions would make the draft unreadable on every GET.
            if scope.graded_by != "llm":
                continue
            for crit in scope.criterion_outcomes:
                leaves = crit.sub_criterion_outcomes or [crit]
                for leaf in leaves:
                    if leaf.checks is None:
                        missing.append(getattr(leaf, "sub_criterion_id", None)
                                       or crit.criterion_id)
        if missing:
            raise ValueError(
                f"plan_version={self.plan_version!r} is stamped but "
                f"{len(missing)} terminal(s) carry no checks: {missing[:5]} — "
                f"a v5 draft must carry its per-check record (PR-G1)")
        return self
