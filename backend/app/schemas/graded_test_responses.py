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
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.schemas.graded_test_contract import GradedTestContract
from app.schemas.graded_test_draft import GradedTestDraft
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
