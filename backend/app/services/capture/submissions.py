"""
Capture submissions — the Draft, its pages, and the save that freezes a
version (PR_in_house_scanning.md §6.3–§6.11; rulings OD-1/2/3/9, D1–D7).

ONE service for both modes. Every function takes the actor and enforces its
scope (SCN-7): a teacher acts within her batch; a student acts on the ONE
submission her device secret names, on her link. Functions flush and never
commit — the router owns the transaction, then enqueues after its commit.

LOCK ORDER (load-bearing): a save locks the BATCH row first, then the
submission — the order the upload append and the purge already take the
batch lock in, so a save can never deadlock against either. Page operations
lock the submission alone (SCN-1).

Nothing logged here names a student or a file (OD-B4): ids only.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models.capture import (
    CaptureLink, CapturePage, CaptureSubmission, CaptureVersion,
)
from ...models.classroom import ClassMembership
from ...models.grading import GradingBatch
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.transcription_job import TranscriptionJob
from ...schemas.capture import (
    CaptureCounter, CaptureSubmissionRow, CaptureSubmissionsResponse, PageView, QualityView,
    StudentRef, StudentSubmissionView, SubmissionView, VersionPagesView,
)
from .. import classroom as classroom_service
from ..batch_ingest import ingest_batch_pdf, refresh_test_count
from . import duplicates, paths, tokens
from .actors import NOT_FOUND, CaptureActor, CaptureError, StudentActor, TeacherActor
from .geometry import FULL_FRAME, InvalidCorners, validate_corners
from .naming import identify, same_name
from .scan_client import get_scan_client

logger = logging.getLogger(__name__)

_POSITION_OFFSET = 1_000_000   # two-phase reorder: park, then place


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gcs():
    from ..gcs_service import get_gcs_service
    return get_gcs_service()


def _bucket() -> str:
    return settings.gcs_bucket_name


def _uploads_pending(page_ids: Sequence[UUID]) -> CaptureError:
    return CaptureError(409, "uploads_pending", "עוד מעלה עמודים — רגע אחד",
                        {"page_ids": [str(p) for p in page_ids]})


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def _sign(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        return _gcs().generate_signed_url(path, settings.capture_upload_url_minutes)
    except Exception:                       # display tolerates (§3.5a): no preview, no crash
        logger.warning("capture_preview_sign_failed object=%s", path)
        return None


async def page_view(page: CapturePage) -> PageView:
    preview = None
    if page.preview_gcs_uri:
        preview = await asyncio.to_thread(_sign, paths.split_gs_uri(page.preview_gcs_uri)[1])
    return PageView(
        page_id=page.id, position=page.position, status=page.status,
        content_type=page.content_type, image_w=page.image_w, image_h=page.image_h,
        corners=page.corners, corners_source=page.corners_source, rotation=page.rotation,
        quality=QualityView(**page.quality) if page.quality else None, preview_url=preview)


async def live_pages(db: AsyncSession, submission_id: UUID) -> list[CapturePage]:
    return list((await db.execute(
        select(CapturePage)
        .where(CapturePage.submission_id == submission_id, CapturePage.deleted_at.is_(None))
        .order_by(CapturePage.position)
    )).scalars().all())


async def _student_ref(db: AsyncSession, student_id: Optional[UUID]) -> Optional[StudentRef]:
    if student_id is None:
        return None
    name = await db.scalar(select(Student.full_name).where(Student.id == student_id))
    return StudentRef(student_id=student_id, display_name=name) if name else None


async def _current_version(db: AsyncSession, sub: CaptureSubmission) -> Optional[CaptureVersion]:
    if sub.current_version_id is None:
        return None
    return await db.get(CaptureVersion, sub.current_version_id)


async def submission_view(db: AsyncSession, sub: CaptureSubmission) -> SubmissionView:
    version = await _current_version(db, sub)
    return SubmissionView(
        submission_id=sub.id, source=sub.source, status=sub.status,
        student_state=sub.student_state, student=await _student_ref(db, sub.student_id),
        pending_student_name=sub.pending_student_name,
        # Signed concurrently: each signature is an IAM call, and a 20-page
        # submission signed one by one was seconds of a student's wait.
        pages=list(await asyncio.gather(*(page_view(p) for p in await live_pages(db, sub.id)))),
        version_no=version.version_no if version else None,
        saved_at=version.created_at.isoformat() if version else None,
        updated_at=sub.updated_at.isoformat())


async def student_submission_view(db: AsyncSession, sub: CaptureSubmission) -> StudentSubmissionView:
    """The student's own view (D1): her pages and her name, never her state."""
    version = await _current_version(db, sub)
    ref = await _student_ref(db, sub.student_id)
    return StudentSubmissionView(
        submission_id=sub.id, status=sub.status,
        display_name=ref.display_name if ref else sub.pending_student_name,
        pages=list(await asyncio.gather(*(page_view(p) for p in await live_pages(db, sub.id)))),
        version_no=version.version_no if version else None,
        saved_at=version.created_at.isoformat() if version else None,
        updated_at=sub.updated_at.isoformat())


# ---------------------------------------------------------------------------
# scope (SCN-7)
# ---------------------------------------------------------------------------

async def load_submission(db: AsyncSession, actor: CaptureActor, submission_id: UUID, *,
                          lock: bool = False) -> CaptureSubmission:
    q = select(CaptureSubmission).where(CaptureSubmission.id == submission_id)
    if lock:
        # populate_existing: a row already in the identity map (an earlier,
        # unlocked read) is REFRESHED from the locked read, never served stale.
        q = q.with_for_update().execution_options(populate_existing=True)
    sub = (await db.execute(q)).scalar_one_or_none()
    if sub is None or sub.batch_id != actor.batch_id or sub.user_id != actor.user_id:
        raise NOT_FOUND()
    if isinstance(actor, StudentActor):
        # Her OWN submission only: the link AND the device secret (D1). A
        # classmate's submission id is a 404, exactly like a made-up one.
        if (sub.source != "student_link" or sub.link_id != actor.link_id
                or actor.device_hash is None or sub.device_secret_hash is None
                or not tokens.same_hash(sub.device_secret_hash, actor.device_hash)):
            raise NOT_FOUND()
    return sub


def _editable(sub: CaptureSubmission) -> None:
    # Draft, or SAVED for a resubmission (R4): editing a saved submission edits
    # its draft pages; its frozen versions are untouched (SCN-2).
    if sub.status == "discarded":
        raise CaptureError(409, "submission_discarded", "ההגשה הזאת בוטלה")


async def _load_page(db: AsyncSession, sub: CaptureSubmission, page_id: UUID) -> CapturePage:
    page = await db.get(CapturePage, page_id)
    if page is None or page.submission_id != sub.id or page.deleted_at is not None:
        raise NOT_FOUND()
    return page


# ---------------------------------------------------------------------------
# creating a submission
# ---------------------------------------------------------------------------

async def create_teacher_submission(db: AsyncSession, actor: TeacherActor) -> CaptureSubmission:
    sub = CaptureSubmission(batch_id=actor.batch_id, user_id=actor.user_id, source="teacher",
                            student_state="unassigned", status="draft")
    db.add(sub)
    await db.flush()
    return sub


async def own_submission(db: AsyncSession, link: CaptureLink,
                         device_hash: Optional[bytes]) -> Optional[CaptureSubmission]:
    """The newest ACTIVE submission this device made on this link (D1)."""
    if device_hash is None:
        return None
    return (await db.execute(
        select(CaptureSubmission)
        .where(CaptureSubmission.link_id == link.id,
               CaptureSubmission.device_secret_hash == device_hash,
               CaptureSubmission.status != "discarded")
        .order_by(CaptureSubmission.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def _competitors(db: AsyncSession, batch_id: UUID, *, exclude: UUID,
                       student_id: UUID) -> list[CaptureSubmission]:
    """Other ACTIVE submissions in the batch already assigned this student —
    what the teacher's D5 dialog asks about. In id order, so a caller that
    locks them locks in ONE order. (Saved duplicates between submissions are
    a derived fact — `duplicates.py`, SCN-13 — and never judged here.)"""
    return list((await db.execute(
        select(CaptureSubmission)
        .where(CaptureSubmission.batch_id == batch_id, CaptureSubmission.status != "discarded",
               CaptureSubmission.student_id == student_id, CaptureSubmission.id != exclude)
        .order_by(CaptureSubmission.id)
    )).scalars().all())


async def _lock_batch(db: AsyncSession, batch_id: UUID) -> None:
    """LOCK ORDER: batch → submission(s) by id → job. Every path that decides
    between submissions (save's duplicate check, the teacher's resolutions)
    takes the batch first, so those decisions serialize per batch and no two
    of them can lock the same submissions in opposite orders."""
    await db.execute(select(GradingBatch.id).where(GradingBatch.id == batch_id)
                     .with_for_update())


async def _lock_submissions(db: AsyncSession, ids) -> dict[UUID, CaptureSubmission]:
    """FOR UPDATE, in ID order, refreshed (populate_existing): every path that
    touches more than one submission locks this way, so two of them can never
    lock the same pair in opposite orders."""
    rows = (await db.execute(
        select(CaptureSubmission).where(CaptureSubmission.id.in_(sorted(set(ids))))
        .order_by(CaptureSubmission.id).with_for_update()
        .execution_options(populate_existing=True)
    )).scalars().all()
    return {r.id: r for r in rows}


async def create_student_submission(db: AsyncSession, *, link: CaptureLink, name: str,
                                    confirm_match: bool) -> tuple[CaptureSubmission, str]:
    """§6.3 POST /submissions. The match is RECOMPUTED here; a client never
    names a student id. Duplicates (D1/D5) are judged at SAVE, against saved
    submissions only — so an abandoned draft never makes a real submission a
    conflict, and the student is never told either way."""
    locked = (await db.execute(
        select(CaptureLink).where(CaptureLink.id == link.id).with_for_update())).scalar_one()
    count = await db.scalar(select(func.count()).select_from(CaptureSubmission).where(
        CaptureSubmission.link_id == locked.id))
    if count >= settings.capture_max_submissions_per_link:            # D12
        raise CaptureError(429, "link_full", "הגיעו יותר מדי הגשות לקישור הזה — פנו למורה")
    batch = await db.get(GradingBatch, locked.batch_id)
    typed = name.strip()
    match = await identify(db, class_id=batch.class_id, user_id=locked.user_id, name=typed)
    if confirm_match and match is not None:
        state, student_id, pending = "confirmed", match.id, None
    else:
        state, student_id, pending = "pending", None, typed
    # SCN-15, before a single photo is taken: the save would refuse it anyway.
    if await _approved_exam_for(db, batch.id, student_id=student_id, typed_name=pending):
        raise _closed_for_student()
    secret = tokens.random_token()
    sub = CaptureSubmission(
        batch_id=batch.id, user_id=locked.user_id, source="student_link", link_id=locked.id,
        device_secret_hash=tokens.sha256(secret), student_id=student_id,
        student_state=state, pending_student_name=pending, status="draft")
    db.add(sub)
    await db.flush()
    logger.info("capture_submission_created submission=%s link=%s state=%s",
                sub.id, locked.id, sub.student_state)
    return sub, secret


# ---------------------------------------------------------------------------
# pages (§6.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewPage:
    page: CapturePage
    upload_url: str
    required_headers: dict


async def create_page(db: AsyncSession, actor: CaptureActor, submission_id: UUID,
                      content_type: str) -> NewPage:
    sub = await load_submission(db, actor, submission_id, lock=True)          # SCN-1
    _editable(sub)
    pages = await live_pages(db, sub.id)
    if len(pages) >= settings.capture_max_pages:
        raise CaptureError(409, "page_cap", "הגעתם למקסימום של 20 עמודים")
    page_id = uuid4()
    raw = paths.raw_path(sub.id, page_id)
    page = CapturePage(id=page_id, submission_id=sub.id,
                       raw_gcs_uri=paths.gs_uri(_bucket(), raw), content_type=content_type,
                       status="awaiting_upload", position=(pages[-1].position if pages else 0) + 1)
    db.add(page)
    sub.updated_at = _now()
    await db.flush()
    # Both headers are inside the signature: R2's silent size cap, and
    # WRITE-ONCE (generation 0 = only if no object exists yet) — the URL can
    # land the photo, never replace it after it was analyzed. A retried PUT
    # whose first attempt did land is answered 412; the client reads that as
    # success (the bytes are the same file).
    signed = {"x-goog-content-length-range": f"1,{settings.capture_max_file_bytes}",
              "x-goog-if-generation-match": "0"}
    url = await asyncio.to_thread(
        _gcs().generate_signed_url, raw, settings.capture_upload_url_minutes,
        method="PUT", content_type=content_type, headers=signed)
    return NewPage(page, url, {"Content-Type": content_type, **signed})


async def confirm_upload(db: AsyncSession, actor: CaptureActor, submission_id: UUID,
                         page_id: UUID) -> CapturePage:
    """§6.5 `uploaded`. The object must EXIST (GCS metadata, size > 0) before
    the page counts as uploaded — SCN-6's half here. Analysis is synchronous
    and never blocks: any failure is the full frame, and she can still adjust
    and save (D9). Idempotent: an analyzed page is returned as it is."""
    sub = await load_submission(db, actor, submission_id)
    _editable(sub)
    page = await _load_page(db, sub, page_id)
    if page.status == "analyzed":
        return page
    if page.status == "analyze_failed" and page.corners_source == "manual":
        return page              # a repeat call must not replace corners she placed by hand
    raw = paths.split_gs_uri(page.raw_gcs_uri)[1]
    size = await asyncio.to_thread(_gcs().object_size, raw)
    if not size:
        raise CaptureError(409, "upload_not_found", "התמונה לא הגיעה — נסו שוב")
    preview = paths.preview_path(sub.id, page.id)
    raw_uri = page.raw_gcs_uri
    await db.commit()               # never hold a transaction across the scan call

    started = time.monotonic()
    try:
        r = await get_scan_client().analyze(raw_uri, paths.gs_uri(_bucket(), preview),
                                            timeout_s=settings.scan_analyze_timeout_s)
        values = dict(status="analyzed", image_w=r.image_w, image_h=r.image_h, corners=r.corners,
                      corners_source=r.corners_source, auto_corners=r.corners,
                      auto_corners_source=r.corners_source, detect_confidence=r.confidence,
                      quality=r.quality, preview_gcs_uri=r.preview_uri)
    except Exception as exc:                                             # D9
        logger.warning("capture_analyze_failed page=%s error=%s", page_id, type(exc).__name__)
        values = dict(status="analyze_failed", corners=FULL_FRAME, corners_source="full_frame",
                      auto_corners=FULL_FRAME, auto_corners_source="full_frame")
    await db.execute(
        update(CapturePage)
        .where(CapturePage.id == page_id,
               CapturePage.status.in_(("awaiting_upload", "analyze_failed")),
               or_(CapturePage.corners_source.is_(None), CapturePage.corners_source != "manual"))
        .values(**values, updated_at=_now()))
    await db.flush()
    page = await db.get(CapturePage, page_id, populate_existing=True)
    logger.info("capture_page_analyzed page=%s status=%s corners_source=%s confidence=%s "
                "reasons=%s ms=%d", page_id, page.status, page.corners_source,
                page.detect_confidence, ",".join((page.quality or {}).get("reasons", [])) or "-",
                int((time.monotonic() - started) * 1000))
    return page


async def patch_page(db: AsyncSession, actor: CaptureActor, submission_id: UUID, page_id: UUID,
                     *, corners=None, rotation: Optional[int] = None) -> CapturePage:
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    page = await _load_page(db, sub, page_id)
    if corners is not None:
        if page.status == "awaiting_upload":
            raise _uploads_pending([page.id])
        try:
            page.corners = validate_corners(corners)
        except InvalidCorners as exc:
            raise CaptureError(422, "invalid_corners", "הפינות לא יוצרות דף תקין",
                               {"reason": str(exc)}) from None
        if page.corners_source != "manual":
            # The live eval of corner detection (§11): every manual-after-auto.
            logger.info("capture_corners_adjusted page=%s from=%s", page.id, page.corners_source)
        page.corners_source = "manual"
    if rotation is not None:
        page.rotation = rotation
    page.updated_at = sub.updated_at = _now()
    await db.flush()
    return page


async def reset_corners(db: AsyncSession, actor: CaptureActor, submission_id: UUID,
                        page_id: UUID, to: str) -> CapturePage:
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    page = await _load_page(db, sub, page_id)
    if page.status == "awaiting_upload":
        raise _uploads_pending([page.id])
    if to == "auto" and page.auto_corners is not None:
        page.corners, page.corners_source = page.auto_corners, page.auto_corners_source
    else:
        page.corners, page.corners_source = FULL_FRAME, "full_frame"
    page.updated_at = sub.updated_at = _now()
    await db.flush()
    return page


async def _place(db: AsyncSession, ordered: Sequence[CapturePage]) -> None:
    """Positions 1..n in ONE transaction, two-phase so the live-pages unique
    index never sees two pages on one position mid-way."""
    for p in ordered:
        p.position = p.position + _POSITION_OFFSET
    await db.flush()
    for i, p in enumerate(ordered, 1):
        p.position = i
    await db.flush()


async def delete_page(db: AsyncSession, actor: CaptureActor, submission_id: UUID,
                      page_id: UUID) -> None:
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    page = await _load_page(db, sub, page_id)
    page.deleted_at = sub.updated_at = _now()
    await db.flush()
    await _place(db, await live_pages(db, sub.id))


async def reorder(db: AsyncSession, actor: CaptureActor, submission_id: UUID,
                  page_ids: Sequence[UUID]) -> None:
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    pages = {p.id: p for p in await live_pages(db, sub.id)}
    if len(page_ids) != len(pages) or set(page_ids) != set(pages):
        raise CaptureError(422, "order_mismatch", "סדר העמודים לא תואם — רעננו את הדף")
    sub.updated_at = _now()
    await _place(db, [pages[pid] for pid in page_ids])


# ---------------------------------------------------------------------------
# the transcription gate, seen from a submission
# ---------------------------------------------------------------------------

async def _version_job(db: AsyncSession, version_id: Optional[UUID], *,
                       lock: bool = False) -> Optional[TranscriptionJob]:
    if version_id is None:
        return None
    q = select(TranscriptionJob).where(TranscriptionJob.capture_version_id == version_id)
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(q)).scalar_one_or_none()


async def _is_approved(db: AsyncSession, sub: CaptureSubmission) -> bool:
    """Has the CURRENT version passed the transcription gate (D6)?

    LOCKS the version's job row first — the row every approval path locks
    (batch_ingest.lock_for_approval) — so an approval racing this decision
    either committed before it (and is seen: the transcription status is read
    by a fresh statement after the lock) or waits until the withdrawal commits
    (and is refused). Never both approved and withdrawn."""
    job = await _version_job(db, sub.current_version_id, lock=True)
    if job is None or job.transcription_id is None:
        return False
    return (await db.scalar(select(Transcription.status).where(
        Transcription.id == job.transcription_id))) == "approved"


async def _withdraw(db: AsyncSession, version_id: Optional[UUID]) -> None:
    """D7: hide, never abort — the job may finish; its scan stays out of the
    batch because every batch read filters withdrawn jobs (OD-2)."""
    if version_id is None:
        return
    batch_id = (await db.execute(
        update(TranscriptionJob)
        .where(TranscriptionJob.capture_version_id == version_id,
               TranscriptionJob.withdrawn_at.is_(None))
        .values(withdrawn_at=_now(), updated_at=_now())
        .returning(TranscriptionJob.batch_id))).scalar_one_or_none()
    if batch_id is not None:
        await refresh_test_count(db, batch_id)        # callers hold the batch lock


async def _discard(db: AsyncSession, sub: CaptureSubmission) -> None:
    """The caller holds `sub`'s row lock (and read it fresh)."""
    if sub.status == "discarded":
        return
    if await _is_approved(db, sub):
        raise CaptureError(409, "already_approved",
                           "התמלול של המבחן הזה כבר אושר — הוא לא יימחק")
    sub.status = "discarded"
    sub.updated_at = _now()
    await _withdraw(db, sub.current_version_id)
    await db.flush()


# ---------------------------------------------------------------------------
# SCN-15 — one approved exam per student per batch (owner ruling 2026-11-01)
# ---------------------------------------------------------------------------

async def _approved_exam_for(db: AsyncSession, batch_id: UUID, *,
                             student_id: Optional[UUID] = None,
                             typed_name: Optional[str] = None) -> bool:
    """Does this batch already hold an APPROVED exam for that student — by id,
    or, for a name nobody has confirmed yet, by that name? Any source counts:
    an approved uploaded PDF closes the student exactly as a capture does."""
    rows = (await db.execute(select(Transcription.student_id, Transcription.student_name).where(
        Transcription.batch_id == batch_id, Transcription.status == "approved"))).all()
    return any((student_id is not None and sid == student_id)
               or (typed_name and same_name(name, typed_name)) for sid, name in rows)


def _closed_for_student() -> CaptureError:
    # Student-facing, and deliberately unspecific: it must not confirm to a
    # classmate that someone's exam under this name exists (D1).
    return CaptureError(409, "exam_closed", "לא ניתן לשלוח את המבחן הזה — פנו למורה")


async def _refuse_approved_student(db: AsyncSession, batch_id: UUID, student: Student) -> None:
    """The teacher's side of SCN-15: a set cannot be attached to a student
    whose exam she already approved here."""
    if await _approved_exam_for(db, batch_id, student_id=student.id):
        raise CaptureError(409, "student_already_approved",
                           f"ל{student.full_name} כבר יש מבחן מאושר בקבוצה הזאת — "
                           "למבחן נוסף פתחי קבוצה חדשה")


async def _refuse_set_after_approval(db: AsyncSession, sub: CaptureSubmission) -> None:
    """SCN-15 at a save: the claim this submission makes, against the batch's
    approved exams. (Its OWN approved version is the caller's first check.)"""
    if sub.student_id is not None:
        closed = await _approved_exam_for(db, sub.batch_id, student_id=sub.student_id)
    else:
        closed = await _approved_exam_for(db, sub.batch_id, typed_name=sub.pending_student_name)
    if not closed:
        return
    if sub.source == "student_link":
        raise _closed_for_student()
    await _refuse_approved_student(db, sub.batch_id, await db.get(Student, sub.student_id))


# ---------------------------------------------------------------------------
# save — freezing a version (§6.6; SCN-2, SCN-3, SCN-6, SCN-8; D6, D7; OD-1, OD-9)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Saved:
    submission_id: UUID
    version: CaptureVersion
    job_id: UUID
    page_count: int


async def _display_name(db: AsyncSession, sub: CaptureSubmission) -> str:
    if sub.student_id is not None:
        name = await db.scalar(select(Student.full_name).where(Student.id == sub.student_id))
        if name:
            return name
    return (sub.pending_student_name or "").strip() or "מבחן"


async def _unique_filename(db: AsyncSession, batch_id: UUID, name: str) -> str:
    """OD-9: «{name}.pdf», then « (2)», « (3)»… among the batch's LIVE jobs.
    Called under the batch lock, so two saves cannot both take one name."""
    taken = set((await db.execute(select(TranscriptionJob.source_filename).where(
        TranscriptionJob.batch_id == batch_id, TranscriptionJob.withdrawn_at.is_(None)
    ))).scalars().all())
    base = name.replace("/", " ").strip() or "מבחן"
    candidate, n = f"{base}.pdf", 2
    while candidate in taken:
        candidate, n = f"{base} ({n}).pdf", n + 1
    return candidate


async def save(db: AsyncSession, actor: CaptureActor, submission_id: UUID) -> Saved:
    probe = await load_submission(db, actor, submission_id)
    await _lock_batch(db, probe.batch_id)                                 # LOCK ORDER: batch…
    sub = await load_submission(db, actor, submission_id, lock=True)      # …then submission
    _editable(sub)
    pages = await live_pages(db, sub.id)
    if not pages:
        raise CaptureError(422, "no_pages", "אין עמודים לשמירה")
    awaiting = [p.id for p in pages if p.status == "awaiting_upload"]
    if awaiting:
        raise _uploads_pending(awaiting)                                  # SCN-6
    if sub.source == "teacher" and sub.student_state != "confirmed":
        raise CaptureError(409, "student_not_confirmed", "יש לבחור תלמיד לפני השמירה")   # SCN-8

    # SCN-15 (owner ruling 2026-11-01): once she has approved a student's
    # exam, no new set of photos reaches the batch for that student — not a
    # resubmission of this one, not a second device's. Another set means a
    # new batch. Duplicates of UNAPPROVED sets are not judged here: they are
    # derived at read time (SCN-13), and she picks one (SCN-14).
    if await _is_approved(db, sub):
        raise CaptureError(409, "already_approved",
                           "התמלול של המבחן הזה כבר אושר — שינויים לא יישלחו"
                           if sub.source == "teacher" else
                           "המורה כבר אישרה את המבחן הזה — אי אפשר לשלוח גרסה חדשה")
    await _refuse_set_after_approval(db, sub)

    previous = sub.current_version_id
    version_no = (await db.scalar(select(func.max(CaptureVersion.version_no)).where(
        CaptureVersion.submission_id == sub.id)) or 0) + 1
    version = CaptureVersion(
        id=uuid4(), submission_id=sub.id, version_no=version_no,
        scan_pipeline_version=settings.scan_pipeline_version,
        pages_snapshot=[{"page_id": str(p.id), "raw_gcs_uri": p.raw_gcs_uri,
                         "content_type": p.content_type, "corners": p.corners,
                         "rotation": p.rotation} for p in pages])             # SCN-2
    db.add(version)
    await db.flush()
    await _withdraw(db, previous)                                         # SCN-3 / D7
    sub.current_version_id = version.id
    sub.status = "saved"
    sub.updated_at = _now()
    await db.flush()

    filename = await _unique_filename(db, sub.batch_id, await _display_name(db, sub))
    job = await ingest_batch_pdf(                                         # OD-1: ONE ingestion
        db, batch_id=sub.batch_id, user_id=sub.user_id,
        object_path=paths.pdf_path(sub.id, version.id), filename=filename,
        capture_version_id=version.id)
    logger.info("capture_saved submission=%s version=%s version_no=%d pages=%d job=%s",
                sub.id, version.id, version_no, len(pages), job.id)
    return Saved(sub.id, version, job.id, len(pages))


# ---------------------------------------------------------------------------
# students — the teacher assigns (§6.10, D5), the pending and conflict
# queues resolve (§6.11, R1)
# ---------------------------------------------------------------------------

async def _owned_student(db: AsyncSession, user_id: UUID, student_id: UUID) -> Student:
    s = await db.get(Student, student_id)
    if s is None or s.user_id != user_id:
        raise CaptureError(404, "student_not_found", "התלמיד לא נמצא")
    return s


async def _join_class(db: AsyncSession, batch_id: UUID, student_id: UUID) -> None:
    class_id = await db.scalar(select(GradingBatch.class_id).where(GradingBatch.id == batch_id))
    if class_id is not None:
        await classroom_service.add_membership(db, class_id=class_id, student_id=student_id)


async def _create_student(db: AsyncSession, batch_id: UUID, user_id: UUID, name: str) -> Student:
    try:
        student = await classroom_service.create_student(db, user_id=user_id, full_name=name.strip())
    except classroom_service.NameTaken:
        raise CaptureError(409, "student_exists", "כבר קיים תלמיד בשם הזה — בחרי אותו מהרשימה",
                           {"name": name.strip()}) from None
    await _join_class(db, batch_id, student.id)
    return student


async def _already_submitted(db: AsyncSession, other: CaptureSubmission) -> CaptureError:
    version = await _current_version(db, other)
    return CaptureError(409, "student_already_submitted", "כבר יש מבחן של התלמיד בקבוצה הזאת", {
        "existing_submission_id": str(other.id),
        "saved_at": version.created_at.isoformat() if version else None,
        "page_count": len(await live_pages(db, other.id)),
    })


async def assign_student(db: AsyncSession, actor: TeacherActor, submission_id: UUID, *,
                         student_id: Optional[UUID], create_name: Optional[str],
                         replace_existing: bool) -> CaptureSubmission:
    sub = await load_submission(db, actor, submission_id)
    _editable(sub)
    await _lock_batch(db, sub.batch_id)
    if create_name is not None:                                  # immediate (R1, teacher side)
        student = await _create_student(db, sub.batch_id, actor.user_id, create_name)
    else:
        student = await _owned_student(db, actor.user_id, student_id)
    others = await _competitors(db, sub.batch_id, exclude=sub.id, student_id=student.id)
    locked = await _lock_submissions(db, [sub.id, *(o.id for o in others)])
    if sub.id not in locked:                      # gone since it was read (a purge)
        raise NOT_FOUND()
    sub = locked[sub.id]
    _editable(sub)
    if sub.student_id != student.id and await _is_approved(db, sub):
        # Its scan already passed the transcription gate FOR the student named
        # on it: re-attributing the submission now would make the two disagree
        # (OD-3) — and the purge of either student would then be wrong.
        raise CaptureError(409, "already_approved",
                           "התמלול של המבחן הזה כבר אושר — לא ניתן לשנות את התלמיד")
    if sub.student_id != student.id:
        await _refuse_approved_student(db, sub.batch_id, student)          # SCN-15
    others = [locked[o.id] for o in others if o.id in locked
              and locked[o.id].status != "discarded" and locked[o.id].student_id == student.id]
    if others and not replace_existing:
        raise await _already_submitted(db, others[0])           # the D5 dialog
    for other in others:
        # Replacing = ONE kept, the other discarded (owner ruling 2026-11-01).
        # An approved other cannot reach here (SCN-15 refused it above);
        # `_discard` refuses one anyway.
        await _discard(db, other)
    sub.student_id, sub.student_state, sub.conflict_note = student.id, "confirmed", None
    sub.updated_at = _now()
    await db.flush()
    return sub


async def resolve_pending(db: AsyncSession, actor: TeacherActor, submission_id: UUID, *,
                          student_id: Optional[UUID], approve_new: bool) -> CaptureSubmission:
    probe = await load_submission(db, actor, submission_id)
    await _lock_batch(db, probe.batch_id)
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    # A typed name nobody has confirmed. `conflict` with no student is the
    # pre-SCN-13 spelling of the same thing (rows saved before 2026-11-01).
    if sub.student_id is not None or sub.student_state not in ("pending", "conflict"):
        raise CaptureError(409, "not_pending", "ההגשה הזאת כבר לא ממתינה לאישור")
    # SCN-14 order: which set to keep comes FIRST. Naming one half of a
    # duplicate would move it from a name claim to an id claim and could
    # split the pair (the 2026-10-30 incident).
    if sub.id in await duplicates.groups_in(db, [sub.batch_id]):
        raise CaptureError(409, "duplicate_unresolved",
                           "יש יותר מהגשה אחת בשם הזה — בחרי קודם איזו לשמור")
    if approve_new:
        student = await _create_student(db, sub.batch_id, actor.user_id, sub.pending_student_name)
    else:
        student = await _owned_student(db, actor.user_id, student_id)
        await _refuse_approved_student(db, sub.batch_id, student)          # SCN-15
    # Never a silent double assignment (D5): if that student already has a
    # set here, the two now form a duplicate (SCN-13) she resolves with one
    # decision — derived from the claims, not written here.
    sub.student_id, sub.student_state, sub.conflict_note = student.id, "confirmed", None
    sub.updated_at = _now()
    await db.flush()
    return sub


async def resolve_conflict(db: AsyncSession, actor: TeacherActor,
                           submission_id: UUID) -> CaptureSubmission:
    """«להשאיר את זו» (SCN-14, owner ruling 2026-11-01): ONE set of a
    duplicate is kept and every other set in its group is discarded. There is
    no "keep both" and no "it is someone else's" — one is kept, the rest go."""
    probe = await load_submission(db, actor, submission_id)
    await _lock_batch(db, probe.batch_id)         # every decision between sets serializes here
    group = (await duplicates.groups_in(db, [probe.batch_id])).get(probe.id)
    if not group:
        _editable(probe)                          # a discarded one says so
        raise CaptureError(409, "not_conflict", "אין כאן כפילות — ייתכן שכבר נבחרה הגשה")
    # Every row this decision touches, locked in ONE order and read fresh: a
    # stale panel (a second tab, the 10 s poll) re-checks against the truth.
    locked = await _lock_submissions(db, group)
    if probe.id not in locked:                    # gone since it was read (a purge)
        raise NOT_FOUND()
    sub = locked[probe.id]
    _editable(sub)
    others = [locked[i] for i in group if i != sub.id and i in locked
              and locked[i].status != "discarded"]
    for other in others:
        # Work she already approved is never discarded: with an approved set
        # in the group, that set is the only one she can keep.
        if await _is_approved(db, other):
            raise CaptureError(409, "other_approved",
                               "הגשה אחרת של התלמיד כבר אושרה — רק אותה אפשר לשמור")
    for other in others:
        await _discard(db, other)
    sub.student_state = "confirmed" if sub.student_id is not None else "pending"
    sub.conflict_note = None
    sub.updated_at = _now()
    await db.flush()
    logger.info("capture_duplicate_resolved kept=%s discarded=%s",
                sub.id, ",".join(str(o.id) for o in others))
    return sub


# ---------------------------------------------------------------------------
# the teacher's views
# ---------------------------------------------------------------------------

async def teacher_drafts(db: AsyncSession, actor: TeacherActor) -> list[CaptureSubmission]:
    return list((await db.execute(
        select(CaptureSubmission)
        .where(CaptureSubmission.batch_id == actor.batch_id,
               CaptureSubmission.user_id == actor.user_id,
               CaptureSubmission.source == "teacher", CaptureSubmission.status == "draft")
        .order_by(CaptureSubmission.created_at)
    )).scalars().all())


async def saved_count(db: AsyncSession, batch_id: UUID) -> int:
    return int(await db.scalar(select(func.count()).select_from(CaptureSubmission).where(
        CaptureSubmission.batch_id == batch_id, CaptureSubmission.status == "saved")) or 0)


def _error_code(job: Optional[TranscriptionJob]) -> Optional[str]:
    if job is None or job.status != "failed":
        return None
    return "compile_failed" if "CaptureCompileFailed" in (job.error_message or "") \
        else "transcription_failed"


def _effective_state(sub: CaptureSubmission, duplicate: bool) -> str:
    """What the teacher is asked about a SAVED submission: is it one of a
    duplicate (SCN-13, derived), else has a student been confirmed? The
    persisted `conflict` (rows saved before 2026-11-01) is not read here — a
    legacy conflict whose pair is gone is simply confirmed or pending."""
    if duplicate:
        return "conflict"
    return "confirmed" if sub.student_id is not None else "pending"


def _snapshot_len(version: Optional[CaptureVersion]) -> int:
    return len(version.pages_snapshot or []) if version is not None else 0


async def batch_rows(db: AsyncSession, batch: GradingBatch) -> CaptureSubmissionsResponse:
    """The submissions panel (§6.11) — polled every 10 s while a link is open,
    so it is a FIXED number of statements, not a few per row. It signs no
    photo: the pictures are fetched when she opens them (`version_view`)."""
    rows_q = (await db.execute(
        select(CaptureSubmission, CaptureVersion, TranscriptionJob, Transcription.status,
               Student.full_name)
        .outerjoin(CaptureVersion, CaptureVersion.id == CaptureSubmission.current_version_id)
        .outerjoin(TranscriptionJob, TranscriptionJob.capture_version_id == CaptureVersion.id)
        .outerjoin(Transcription, Transcription.id == TranscriptionJob.transcription_id)
        .outerjoin(Student, Student.id == CaptureSubmission.student_id)
        .where(CaptureSubmission.batch_id == batch.id, CaptureSubmission.status == "saved")
        .order_by(CaptureSubmission.created_at)
    )).all()
    claims = [duplicates.Claim(submission_id=sub.id, student_id=sub.student_id,
                               pending_name=sub.pending_student_name)
              for sub, *_rest in rows_q]
    groups = duplicates.duplicate_groups(claims)

    rows: list[CaptureSubmissionRow] = []
    for sub, version, job, t_status, name in rows_q:
        group = groups.get(sub.id)
        rows.append(CaptureSubmissionRow(
            submission_id=sub.id, source=sub.source,
            student=StudentRef(student_id=sub.student_id, display_name=name)
            if sub.student_id is not None and name else None,
            pending_student_name=sub.pending_student_name,
            student_state=_effective_state(sub, group is not None),
            duplicate_group=str(group[0]) if group else None,
            # What was SAVED — the frozen version she would be grading — not
            # pages a student may be editing on her phone right now (SCN-2).
            page_count=_snapshot_len(version),
            saved_at=version.created_at.isoformat() if version else None,
            version_no=version.version_no if version else None,
            job_id=job.id if job else None, version_status=job.status if job else None,
            error_code=_error_code(job),
            transcription_id=job.transcription_id if job else None,
            transcription_status=t_status))
    roster_size = None
    if batch.class_id is not None:
        roster_size = int(await db.scalar(select(func.count()).select_from(ClassMembership).where(
            ClassMembership.class_id == batch.class_id)) or 0)
    return CaptureSubmissionsResponse(
        rows=rows, counter=CaptureCounter(submitted_students=duplicates.claimant_count(claims),
                                          roster_size=roster_size))


async def version_view(db: AsyncSession, sub: CaptureSubmission) -> VersionPagesView:
    """The photos of the submission's CURRENT VERSION — exactly the set that
    was sent to scanning (SCN-2), in its frozen order, with its frozen corners
    and rotation. Never the live draft pages: a student editing after her save
    must not change what the teacher is shown as "this exam".

    Display only (SCN-11): a page whose row or preview is missing comes back
    without a picture; nothing here refuses."""
    version = await _current_version(db, sub)
    snapshot = list(version.pages_snapshot or []) if version is not None else []
    wanted: list[tuple[int, dict, UUID]] = []
    for position, snap in enumerate(snapshot, start=1):
        try:
            wanted.append((position, snap, UUID(str(snap.get("page_id")))))
        except (TypeError, ValueError):
            logger.warning("capture_version_page_unreadable submission=%s version=%s position=%d",
                           sub.id, version.id, position)
    found = {p.id: p for p in (await db.execute(
        select(CapturePage).where(CapturePage.id.in_([w[2] for w in wanted]))
    )).scalars().all()} if wanted else {}

    async def one(position: int, snap: dict, page_id: UUID) -> Optional[PageView]:
        page = found.get(page_id)
        if page is None or page.submission_id != sub.id:
            logger.warning("capture_version_page_missing submission=%s page=%s", sub.id, page_id)
            return None
        view = await page_view(page)
        return view.model_copy(update={
            "position": position, "corners": snap.get("corners"),
            "rotation": snap.get("rotation") or 0})

    pages = [v for v in await asyncio.gather(*(one(*w) for w in wanted)) if v is not None]
    job = await _version_job(db, sub.current_version_id)
    t_status = None
    if job is not None and job.transcription_id is not None:
        t_status = await db.scalar(select(Transcription.status).where(
            Transcription.id == job.transcription_id))
    return VersionPagesView(
        submission_id=sub.id, source=sub.source,
        student=await _student_ref(db, sub.student_id),
        pending_student_name=sub.pending_student_name,
        version_no=version.version_no if version else None,
        saved_at=version.created_at.isoformat() if version else None,
        transcription_status=t_status, pages=pages)
