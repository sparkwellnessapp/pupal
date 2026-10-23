"""
Capture models — in-house scanning (migration 036, PR_in_house_scanning.md §4–§5).

Draft → Contract, the codebase's universal shape (CLAUDE.md §3.4):

  CaptureSubmission + CapturePage   the DRAFT — corners, rotation, order,
                                    deletions and the student assignment, all
                                    mutable while the student/teacher edits.
  CaptureVersion                    the CONTRACT — a frozen snapshot of the
                                    ordered pages taken at save (SCN-2). The
                                    only thing compilation reads.
  the PDF                           the boundary (OD-S9): one per version, at
                                    a path derived from the version id, compiled
                                    by step 0 of the version's transcription job.

There is deliberately NO compile status on CaptureVersion (ruling OD-1): the
save inserts the version AND its `transcription_jobs` row in one transaction,
so the job's own lifecycle (queued → running → completed | failed, LIV-1
liveness, the per-document retry) is the version's lifecycle. A second state
machine here would be a second opinion about the same fact.

Statuses are text + CHECK, mirrored here as tuples; the DB CHECKs are the
authority — mirror them, don't fight them.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, LargeBinary,
    REAL, SmallInteger, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..database import Base


def _utcnow() -> datetime:
    """Timezone-AWARE UTC now (see transcription_job._utcnow)."""
    return datetime.now(timezone.utc)


CAPTURE_SOURCES = ("student_link", "teacher")
STUDENT_STATES = ("unassigned", "confirmed", "pending", "conflict")
SUBMISSION_STATUSES = ("draft", "saved", "discarded")
ACTIVE_SUBMISSION_STATUSES = ("draft", "saved")
CONFLICT_NOTES = ("duplicate_student", "duplicate_pending_name", "late_resubmission")
PAGE_STATUSES = ("awaiting_upload", "analyzed", "analyze_failed")
PAGE_CONTENT_TYPES = ("image/jpeg", "image/png", "image/heic", "image/heif")
CORNERS_SOURCES = ("auto_model", "auto_contour", "full_frame", "manual")
PAGE_ROTATIONS = (0, 90, 180, 270)


class CaptureLink(Base):
    """One per batch (R6). The token is HMAC(secret, id, generation) — never
    stored; `token_hash` = sha256(token) is the lookup key (OD-4)."""
    __tablename__ = "capture_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("grading_batches.id"),
                      nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash = Column(LargeBinary, nullable=False, unique=True)
    token_generation = Column(Integer, nullable=False, default=1)
    exam_date = Column(Date, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)


class CaptureHandoff(Base):
    """D2 / OD-5: a one-time 10-minute handoff token, exchanged once for a
    12-hour session scoped to ONE batch. Both are opaque random tokens, kept
    only as sha256 (the auth_nonces pattern)."""
    __tablename__ = "capture_handoffs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("grading_batches.id"),
                      nullable=False, index=True)
    handoff_hash = Column(LargeBinary, nullable=False, unique=True)
    handoff_expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    session_hash = Column(LargeBinary, nullable=True, unique=True)
    session_expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CaptureSubmission(Base):
    """The Draft: one student's pages and their student assignment."""
    __tablename__ = "capture_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("grading_batches.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source = Column(Text, nullable=False)
    link_id = Column(UUID(as_uuid=True), ForeignKey("capture_links.id"), nullable=True)
    device_secret_hash = Column(LargeBinary, nullable=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=True)
    student_state = Column(Text, nullable=False, default="unassigned")
    pending_student_name = Column(Text, nullable=True)
    conflict_note = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="draft")
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)

    __table_args__ = (
        # AM-B4: a submission's student is its teacher's student.
        ForeignKeyConstraint(["student_id", "user_id"], ["students.id", "students.user_id"],
                             name="capture_submissions_student_tenant_fkey"),
        # A submission's current version is one of ITS versions. use_alter: the
        # two tables reference each other (the version names its submission).
        ForeignKeyConstraint(["current_version_id", "id"],
                             ["capture_versions.id", "capture_versions.submission_id"],
                             name="capture_current_version_fk", use_alter=True),
    )

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_SUBMISSION_STATUSES


class CapturePage(Base):
    __tablename__ = "capture_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("capture_submissions.id"),
                           nullable=False)
    raw_gcs_uri = Column(Text, nullable=False)
    preview_gcs_uri = Column(Text, nullable=True)
    content_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="awaiting_upload")
    image_w = Column(Integer, nullable=True)
    image_h = Column(Integer, nullable=True)
    corners = Column(JSONB, nullable=True)
    corners_source = Column(Text, nullable=True)
    auto_corners = Column(JSONB, nullable=True)
    auto_corners_source = Column(Text, nullable=True)
    detect_confidence = Column(REAL, nullable=True)
    quality = Column(JSONB, nullable=True)
    rotation = Column(SmallInteger, nullable=False, default=0)
    position = Column(Integer, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)


class CaptureVersion(Base):
    """The Contract. SCN-2: `pages_snapshot` is never mutated after insert —
    there is no UPDATE path anywhere, and compilation reads only this."""
    __tablename__ = "capture_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("capture_submissions.id"),
                           nullable=False)
    version_no = Column(Integer, nullable=False)
    pages_snapshot = Column(JSONB, nullable=False)
    scan_pipeline_version = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
