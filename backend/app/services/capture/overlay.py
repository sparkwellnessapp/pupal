"""
The capture student OVERLAY — read time only (ruling OD-3).

A transcription compiled from a capture version knows its student better than
the identity pass does: a human (the student on the link, or the teacher on
her page) chose it. So while the transcription is still `transcribed`, its
student signal comes from the capture submission, not from the name read off
page 1:

  confirmed  → an exact match on that student. Clean when nothing else is
               flagged, so it is eligible for bulk accept.
  pending    → never clean (`capture_student_pending`): the teacher approves
               the typed name as a new student or links it, one item at a time.
  conflict   → never clean (`capture_conflict`): two submissions claim one
               student, or a late resubmission arrived (D1/D5/D6).

Nothing is WRITTEN to the transcription — the approval CHECK forbids a student
on a `transcribed` row, and the auto-match has always been recomputed per read.
Once the transcription is approved its own `student_id` is the truth and the
overlay no longer applies (`overlay_for` returns None for any other status);
the approval paths write that student back onto the submission
(`sync_on_approval`), so the two never disagree afterwards.

ONE resolution (transcription → job → version → submission), used by every
verdict consumer: get_batch, list_batches and accept_clean judge with
byte-identical inputs, as `_verdict_inputs` already requires of the roster.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.capture import CaptureSubmission, CaptureVersion
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.transcription_job import TranscriptionJob
from ..batch_triage import StudentMatchResult


@dataclass(frozen=True)
class CaptureStudent:
    submission_id: UUID
    state: str                       # confirmed | pending | conflict | unassigned
    student_id: Optional[UUID]
    student_name: Optional[str]
    pending_name: Optional[str]
    conflict_note: Optional[str]

    def match(self) -> StudentMatchResult:
        if self.state == "confirmed" and self.student_id is not None:
            return StudentMatchResult(student_id=str(self.student_id),
                                      student_name=self.student_name,
                                      match_confidence="exact")
        return StudentMatchResult(student_id=None, student_name=None, match_confidence="none")

    def suggestion(self) -> Optional[str]:
        """The name the review surface pre-fills the picker with."""
        if self.state == "confirmed":
            return self.student_name
        return self.pending_name or self.student_name

    @property
    def verdict_state(self) -> Optional[str]:
        """What `compute_flag_verdict` needs to know: pending/conflict force
        a needs-eyes reason; confirmed is already an exact match."""
        return self.state if self.state in ("pending", "conflict") else None


async def capture_students(
    db: AsyncSession, transcription_ids: Iterable[UUID],
) -> dict[UUID, CaptureStudent]:
    """transcription_id → its capture submission's student facts, for every
    id that came from a capture version (others are simply absent)."""
    ids = list(transcription_ids)
    if not ids:
        return {}
    rows = (await db.execute(
        select(TranscriptionJob.transcription_id, CaptureSubmission, Student.full_name)
        .join(CaptureVersion, CaptureVersion.id == TranscriptionJob.capture_version_id)
        .join(CaptureSubmission, CaptureSubmission.id == CaptureVersion.submission_id)
        .outerjoin(Student, Student.id == CaptureSubmission.student_id)
        .where(TranscriptionJob.transcription_id.in_(ids))
    )).all()
    return {
        tid: CaptureStudent(
            submission_id=sub.id, state=sub.student_state, student_id=sub.student_id,
            student_name=name, pending_name=sub.pending_student_name,
            conflict_note=sub.conflict_note,
        )
        for tid, sub, name in rows
    }


def overlay_for(transcription: Transcription,
                overlays: dict[UUID, CaptureStudent]) -> Optional[CaptureStudent]:
    """The overlay applies only before the transcription gate (OD-3 case 3)."""
    if transcription.status != "transcribed":
        return None
    return overlays.get(transcription.id)


async def sync_on_approval(db: AsyncSession, transcription_id: UUID,
                           student_id: UUID) -> None:
    """Inside the approval transaction: the approved student becomes the
    capture submission's student. Without this, the submission would keep
    naming whoever was typed on the link, and THAT student's purge would
    delete photos that are another student's exam (the purge refuses on the
    disagreement — `capture_mismatch` — as a backstop). A no-op for a
    transcription that did not come from a capture."""
    submission_id = (await db.execute(
        select(CaptureVersion.submission_id)
        .join(TranscriptionJob, TranscriptionJob.capture_version_id == CaptureVersion.id)
        .where(TranscriptionJob.transcription_id == transcription_id)
    )).scalar_one_or_none()
    if submission_id is None:
        return
    await db.execute(
        update(CaptureSubmission)
        .where(CaptureSubmission.id == submission_id)
        .values(student_id=student_id, student_state="confirmed", conflict_note=None,
                updated_at=datetime.now(timezone.utc))
    )
