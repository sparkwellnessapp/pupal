"""
Pydantic schemas for classroom (students + classes) API endpoints.

These are thin API response shapes, distinct from the ORM models.
user_id is never included in responses — ownership is implicit.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from .graded_test_draft import StampPosition


# ---------------------------------------------------------------------------
# Nested mini-schemas (used inside detail responses)
# ---------------------------------------------------------------------------

class ClassMini(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True


class StudentMini(BaseModel):
    id: UUID
    full_name: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Student schemas
# ---------------------------------------------------------------------------

class StudentResponse(BaseModel):
    """No `notes` (OD-3 / UI-4): the field was removed from the product, and a
    body that still sends it is IGNORED, not rejected (Pydantic's default
    `extra='ignore'` — an older client must not start failing on save)."""
    id: UUID
    full_name: str
    created_at: datetime
    #: LST-4: derived from the ONE definition in `student_signed_tests`, on
    #: the roster (one grouped statement) and on the detail alike.
    signed_tests_count: int = 0

    class Config:
        from_attributes = True


class StudentDetailResponse(StudentResponse):
    classes: List[ClassMini] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CreateStudentRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)


class UpdateStudentRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)


# ---------------------------------------------------------------------------
# The student's signed tests (student-profile PR §5.2 — M-A1: the endpoint is
# NAMED for the invariant it carries; a future "add drafts" is a visible rename)
# ---------------------------------------------------------------------------

class SignedTestExam(BaseModel):
    """The exam event, in the form המבחנים שלי already renders it (M-A4):
    the STORED batch name when there is one, and the parts the client's own
    composer falls back to. `batch_id` is null for a single-flow test."""
    batch_id: Optional[UUID] = None
    name: Optional[str] = None
    rubric_name: Optional[str] = None
    class_name: Optional[str] = None
    #: M-A3: the batch's creation, or the scan's own when there is no batch.
    uploaded_at: datetime


class SignedTestThumbnail(BaseModel):
    """What the shared page-1 component needs (OD-8): the SAME page-1 resource
    the pile cards fetch through the authorized seam (FA-4 — a relative path,
    never a bare URL an `<img>` could load), and the stamp position already
    RESOLVED (overlay → batch default → null), so a row needs one image and
    no per-row detail call."""
    page1_image_url: Optional[str] = None
    stamp_position: Optional[StampPosition] = None


class SignedTestItem(BaseModel):
    graded_test_id: UUID
    exam: SignedTestExam
    approved_at: datetime
    #: OD-7 / LST-3: the approved row's dedicated columns, serialised exactly
    #: as `GradedTestApprovedResponse` serialises them (a Decimal STRING), so
    #: the profile and the returned page format one and the same value.
    total_score: Optional[Decimal] = None
    total_possible: Optional[Decimal] = None
    thumbnail: SignedTestThumbnail

    @field_serializer("total_score", "total_possible")
    def _decimal_as_string(self, v: Optional[Decimal]) -> Optional[str]:
        return str(v) if v is not None else None


class SignedTestsResponse(BaseModel):
    #: Always the TRUE count (§5.3), even when `truncated`.
    signed_tests_count: int
    truncated: bool
    # No defaults: on the wire both are ALWAYS present (the generated TS type
    # would otherwise mark them optional and every consumer would `?? []`).
    signed_tests: List[SignedTestItem]


# ---------------------------------------------------------------------------
# Class schemas
# ---------------------------------------------------------------------------

class PurgePreviewResponse(BaseModel):
    """[Part B §12] What deleting this student would delete — the purge plan,
    COUNTED. No object name and no filename crosses the wire, and unassigned
    scans are absent: they are not hers, and the teacher has nothing to do
    about them (OD-B6). `case` picks the Delete dialog's copy (PR §15)."""
    student_id: UUID
    case: Literal["signed_tests", "data_only", "nothing"]
    signed_tests_count: int
    blockers: int = Field(..., description="grades or jobs in flight — the purge answers 409 while > 0")
    counts: Dict[str, int]
    objects: Dict[str, int]


class ClassResponse(BaseModel):
    id: UUID
    name: str
    subject_matter_id: Optional[int] = None
    subject_matter_name: Optional[str] = None
    school_year: Optional[str] = None
    student_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ClassDetailResponse(ClassResponse):
    students: List[StudentMini] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CreateClassRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject_matter_id: Optional[int] = None
    school_year: Optional[str] = Field(None, max_length=20)


class UpdateClassRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject_matter_id: Optional[int] = None
    school_year: Optional[str] = Field(None, max_length=20)


# ---------------------------------------------------------------------------
# Membership schemas
# ---------------------------------------------------------------------------

class AddStudentToClassRequest(BaseModel):
    student_id: UUID
