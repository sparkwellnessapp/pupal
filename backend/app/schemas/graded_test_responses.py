"""
Response schemas for graded-test read endpoints.

Shapes returned by GET /graded_test/{id} depending on status:
  pending / grading → GradedTestStatusResponse   (no draft yet)
  draft             → GradedTestDraftResponse     (full draft + aggregates)
  approved          → GradedTestApprovedResponse  (draft + frozen contract)  [S9]
  failed            → GradedTestFailedResponse    (status + error_message)

GET /graded_tests and GET /rubric/{id}/graded_tests return GradedTestListItem.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.schemas.graded_test_contract import GradedTestContract
from app.schemas.graded_test_draft import FeedbackBlock, GradedTestDraft, GradedTestOverrides
# [OD-F8] Used in the annotations below. `from __future__ import annotations`
# makes those lazy strings, so a missing import here does NOT fail at import
# time — `python -c "import app.main"` stays green while
# GradedTestDraftResponse/ApprovedResponse cannot be CONSTRUCTED at all
# ("not fully defined"), 500-ing every draft and approved GET. The boot sanity
# gate cannot see this class of break; `model_json_schema()` can, which is why
# the OpenAPI dump caught it first.
from app.schemas.ontology_types import NumericPolicy


class GradedTestListItem(BaseModel):
    """Lean list-view shape — no draft_json. Safe to return in bulk."""
    id: UUID
    student_name: str
    filename: Optional[str] = None
    status: str
    total_score: Optional[Decimal] = None
    total_possible: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    rubric_contract_version: str
    created_at: str  # ISO-8601 string — avoids timezone serialisation edge cases
    rubric_contract_stale: bool = False  # S10: computed at query time (never stored)

    @field_serializer("total_score", "total_possible", "percentage")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return str(v) if v is not None else None


class GradedTestStatusResponse(BaseModel):
    """Returned while grading is in flight (status='pending' or 'grading')."""
    id: UUID
    status: str
    student_name: str


class GradedTestDraftResponse(BaseModel):
    """Returned once grading completes (status='draft')."""
    id: UUID
    status: str
    student_name: str
    filename: Optional[str] = None
    total_score: Optional[Decimal] = None
    total_possible: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    total_cost_usd: Optional[Decimal] = None
    transcription_id: UUID
    draft: GradedTestDraft
    # [PR-G5] The SERVER's pricing of the overlay just saved. The client
    # re-derives the same numbers locally for instant feedback; these are
    # what will actually freeze, so a divergence must be visible BEFORE
    # approval rather than discovered inside the contract.
    effective_totals: Optional[Dict[str, Decimal]] = None   # terminal_id -> points
    effective_total: Optional[Decimal] = None               # the test total
    pricing_mismatch: bool = False
    # [PR-G8] first teacher open (column, not draft JSON)
    opened_at: Optional[datetime] = None  # deserialized from graded_tests.draft_json
    # [OD-F8] The rounding rule the client must re-price with. Without it the
    # browser guesses, and a client rounding differently from the server shows
    # the teacher one score while a DIFFERENT one freezes into the contract —
    # the exact failure `selection_scoring.py` exists to end.
    #
    # All three fields, not just `precision`: half_up vs half_even disagree on
    # every exact .5, which is where a 0.25 grid puts its boundaries.
    #
    # Sourced from the rubric's CURRENT contract. When `rubric_contract_stale`
    # is true that may differ from the policy this draft was priced under — but
    # a stale contract means the test needs re-grading, not re-pricing, and the
    # client already surfaces that.
    numeric_policy: Optional[NumericPolicy] = None
    rubric_contract_stale: bool = False  # S10: computed at query time
    regraded_from_id: Optional[UUID] = None  # S10: revision chain back-pointer

    @field_serializer("total_score", "total_possible", "percentage", "total_cost_usd")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return str(v) if v is not None else None


class GradedTestApprovedResponse(BaseModel):
    """Returned once a draft is teacher-approved (status='approved')."""
    id: UUID
    status: str
    student_name: str
    #: [student-profile PR, OD-2] The returned page links the student's name to
    #: the profile; the name alone cannot address it. `graded_tests.student_id`
    #: is NOT NULL, so this is never absent for a real row.
    student_id: Optional[UUID] = None
    filename: Optional[str] = None
    total_score: Optional[Decimal] = None
    total_possible: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    total_cost_usd: Optional[Decimal] = None
    transcription_id: UUID
    # [OD-F8] the rounding rule the client re-prices with; see the draft
    # response above for why all three fields travel, not just precision.
    numeric_policy: Optional[NumericPolicy] = None
    draft: GradedTestDraft
    contract: GradedTestContract
    approved_at: str  # ISO-8601 string
    rubric_contract_stale: bool = False  # S10: computed at query time
    regraded_from_id: Optional[UUID] = None  # S10: revision chain back-pointer

    @field_serializer("total_score", "total_possible", "percentage", "total_cost_usd")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return str(v) if v is not None else None


class GradedTestFailedResponse(BaseModel):
    """Returned when grading failed (status='failed')."""
    id: UUID
    status: str
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# grader-v6 review (owner rulings 2026-10-17 §7, the MVC)
# ═══════════════════════════════════════════════════════════════════════════

class V6ReasoningLine(BaseModel):
    """The line she reads under one criterion: the explainer's (grade time), the
    fallback composer's (after her edit), or the manual line (she set the grade)."""
    terminal_id: str
    text_he: str
    source: str


class GradedTestV6Response(BaseModel):
    """GET /graded_test/{id}/v6 and PATCH /graded_test/{id}/v6/draft.

    `content` is the draft's v6 block (the plan checks with their options and values,
    Vivi's selections and evidence) — the TS pricer re-prices it live from this alone
    (PRC-7). `overrides` is her FULL working copy, the body POST /approve takes;
    `overlay` is its v6 part, typed. `priced` is the SERVER's price of content +
    overlay, which the client compares with its own."""
    id: UUID
    status: str
    content: "DraftV6Content"
    overrides: GradedTestOverrides
    overlay: "PricingOverlay"
    priced: "PricedTest"
    ai_total_score: Decimal
    lines: List[V6ReasoningLine]
    undecided_check_ids: List[str]
    # Vivi's feedback as it stands (rewrites included), and the scopes whose text
    # her decisions have since made out of date (`feedback.inputs.stale_feedback_scopes`).
    feedback: Optional[FeedbackBlock] = None
    stale_feedback_scope_ids: List[str] = Field(default_factory=list)

    @field_serializer("ai_total_score")
    def _sd(self, v: Decimal) -> str:
        return str(v)


from app.schemas.graded_test_draft_v6 import DraftV6Content  # noqa: E402
from app.services.pricing_v6 import PricedTest, PricingOverlay  # noqa: E402

GradedTestV6Response.model_rebuild()
