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

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.schemas.graded_test_contract import GradedTestContract
from app.schemas.graded_test_draft import GradedTestDraft


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
    draft: GradedTestDraft  # deserialized from graded_tests.draft_json
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
