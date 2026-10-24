"""
In-house scanning — every request and response type (PR_in_house_scanning.md
§6). Real types, no stringly-typed transport. The page and submission VIEWS
are shared by the teacher and the student routers (one concept, one place);
what differs between them is who may obtain one, not its shape.

SCN-9 lives in these shapes: no student-facing response type has a field
that can carry a roster — `IdentifyResponse.match` holds one display name,
and only the single exact match of the name the student typed.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

LinkState = Literal["not_yet_open", "open", "closed"]
ContentType = Literal["image/jpeg", "image/png", "image/heic", "image/heif"]
Rotation = Literal[0, 90, 180, 270]
Point = List[float]
# A person's or a class's name, as typed: STRIPPED before it is validated, so
# "   " is refused at the door instead of becoming a student called nothing.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


# ---------------------------------------------------------------------------
# the capture link (teacher)
# ---------------------------------------------------------------------------

class CaptureLinkCreateRequest(BaseModel):
    exam_date: date
    # Only when the batch has no class yet (R6) — then exactly one is required.
    class_id: Optional[UUID] = None
    new_class_name: Optional[Name] = None


class CaptureLinkPatchRequest(BaseModel):
    exam_date: date


class CaptureLinkResponse(BaseModel):
    link_id: UUID
    batch_id: UUID
    # Set when the link is created (R6); None only if the class was deleted since.
    class_id: Optional[UUID] = None
    class_name: Optional[str] = None
    exam_date: date
    state: LinkState
    closed_at: Optional[str] = None
    # Recomputed on every read (OD-4: the token is derived, never stored), so
    # the teacher can re-show the QR at any time on exam day.
    url: str


# ---------------------------------------------------------------------------
# the teacher's phone handoff (D2 / OD-5)
# ---------------------------------------------------------------------------

class CaptureHandoffResponse(BaseModel):
    handoff_url: str
    expires_at: str


class HandoffExchangeRequest(BaseModel):
    handoff_token: str = Field(..., min_length=10, max_length=200)


class HandoffExchangeResponse(BaseModel):
    capture_session: str
    batch_id: UUID
    expires_at: str


# ---------------------------------------------------------------------------
# pages (both modes)
# ---------------------------------------------------------------------------

class PageCreateRequest(BaseModel):
    content_type: ContentType


class PageCreateResponse(BaseModel):
    page_id: UUID
    position: int
    upload_url: str
    # Sent verbatim with the PUT: both are baked into the URL's signature.
    required_headers: Dict[str, str]


class PagePatchRequest(BaseModel):
    corners: Optional[List[Point]] = None
    rotation: Optional[Rotation] = None


class ResetCornersRequest(BaseModel):
    to: Literal["auto", "full_frame"]


class PageOrderRequest(BaseModel):
    page_ids: List[UUID]


class QualityView(BaseModel):
    blur: float
    short_side_px: int
    glare_ratio: float
    verdict: Literal["ok", "warn"]
    reasons: List[Literal["blurry", "too_far", "glare", "edges_not_found"]]


class PageView(BaseModel):
    page_id: UUID
    position: int
    status: Literal["awaiting_upload", "analyzed", "analyze_failed"]
    content_type: ContentType
    image_w: Optional[int] = None
    image_h: Optional[int] = None
    corners: Optional[List[Point]] = None
    corners_source: Optional[Literal["auto_model", "auto_contour", "full_frame", "manual"]] = None
    rotation: Rotation = 0
    quality: Optional[QualityView] = None
    # Display only (SCN-11): a fresh signed GET, 15 minutes. None when the
    # analysis never produced one — the client then shows what it captured.
    preview_url: Optional[str] = None


# ---------------------------------------------------------------------------
# submissions
# ---------------------------------------------------------------------------

class StudentRef(BaseModel):
    student_id: UUID
    display_name: str


class SubmissionView(BaseModel):
    submission_id: UUID
    source: Literal["student_link", "teacher"]
    status: Literal["draft", "saved", "discarded"]
    student_state: Literal["unassigned", "confirmed", "pending", "conflict"]
    student: Optional[StudentRef] = None
    pending_student_name: Optional[str] = None
    pages: List[PageView]
    version_no: Optional[int] = None
    saved_at: Optional[str] = None
    updated_at: str


class StudentSubmissionView(BaseModel):
    """What the STUDENT sees of her own submission. Deliberately narrower
    than SubmissionView: no student state, no student id — whether her
    submission became a conflict or awaits the teacher's confirmation is the
    teacher's business, and she is never told (D1, SCN-9)."""
    submission_id: UUID
    status: Literal["draft", "saved", "discarded"]
    display_name: Optional[str] = None
    pages: List[PageView]
    version_no: Optional[int] = None
    saved_at: Optional[str] = None
    updated_at: str


class SaveResponse(BaseModel):
    # The submission the version was saved ON — after an approval that is a
    # NEW (late) submission (D6), and the client continues on it.
    submission_id: UUID
    version_no: int
    saved_at: str
    page_count: int


class StudentCreate(BaseModel):
    name: Name


class StudentAssignRequest(BaseModel):
    """Exactly one of `student_id` / `create` (§6.10)."""
    student_id: Optional[UUID] = None
    create: Optional[StudentCreate] = None
    replace_existing: bool = False

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.student_id is None) == (self.create is None):
            raise ValueError("exactly one of student_id / create is required")
        return self


class TeacherCaptureState(BaseModel):
    batch_id: UUID
    batch_name: Optional[str] = None
    class_name: Optional[str] = None
    saved_count: int
    # Unsaved groups first, so reopening the page resumes them (§8.3).
    drafts: List[SubmissionView]


class RosterStudent(BaseModel):
    student_id: UUID
    display_name: str


class RosterResponse(BaseModel):
    students: List[RosterStudent]


# ---------------------------------------------------------------------------
# the student link (public)
# ---------------------------------------------------------------------------

class ExamLabel(BaseModel):
    batch_name: Optional[str] = None
    class_name: Optional[str] = None
    exam_date: date


class StudentLinkInfo(BaseModel):
    state: LinkState
    exam_label: ExamLabel
    own_submission: Optional[StudentSubmissionView] = None


class IdentifyRequest(BaseModel):
    name: Name


class IdentifyMatch(BaseModel):
    display_name: str


class IdentifyResponse(BaseModel):
    match: Optional[IdentifyMatch] = None


class StudentSubmissionCreateRequest(BaseModel):
    name: Name
    confirm_match: bool = False


class StudentSubmissionCreateResponse(BaseModel):
    submission_id: UUID
    # Returned ONCE (D1). The browser keeps it in localStorage and sends it as
    # X-Capture-Device; only its sha256 is stored.
    device_secret: str


# ---------------------------------------------------------------------------
# the batch's submissions panel (teacher)
# ---------------------------------------------------------------------------

class CaptureSubmissionRow(BaseModel):
    submission_id: UUID
    source: Literal["student_link", "teacher"]
    student: Optional[StudentRef] = None
    pending_student_name: Optional[str] = None
    student_state: Literal["unassigned", "confirmed", "pending", "conflict"]
    conflict_note: Optional[Literal["duplicate_student", "duplicate_pending_name",
                                    "late_resubmission"]] = None
    page_count: int
    saved_at: Optional[str] = None
    version_no: Optional[int] = None
    # The version's lifecycle IS its transcription job's (OD-1).
    job_id: Optional[UUID] = None
    version_status: Optional[Literal["queued", "running", "completed", "failed"]] = None
    error_code: Optional[Literal["compile_failed", "transcription_failed"]] = None
    transcription_id: Optional[UUID] = None
    transcription_status: Optional[Literal["transcribed", "approved"]] = None
    page1_preview_url: Optional[str] = None


class CaptureCounter(BaseModel):
    submitted_students: int
    roster_size: Optional[int] = None


class CaptureSubmissionsResponse(BaseModel):
    rows: List[CaptureSubmissionRow]
    counter: CaptureCounter


class ResolvePendingRequest(BaseModel):
    student_id: Optional[UUID] = None
    approve_new: bool = False

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.student_id is None) == (not self.approve_new):
            raise ValueError("exactly one of student_id / approve_new is required")
        return self


class ResolveConflictRequest(BaseModel):
    action: Literal["keep_this", "discard_this"]
    student_id: Optional[UUID] = None


# ---------------------------------------------------------------------------
# name suggestion (teacher only — SCN-10, SCN-12)
# ---------------------------------------------------------------------------

class NameSuggestResponse(BaseModel):
    read_name: Optional[str] = None
    match: Optional[StudentRef] = None
    confidence: Literal["high", "low"] = "low"
