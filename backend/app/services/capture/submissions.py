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

from sqlalchemy import func, select, update
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
    StudentRef, SubmissionView,
)
from .. import classroom as classroom_service
from ..batch_ingest import ingest_batch_pdf
from . import paths, tokens
from .actors import NOT_FOUND, CaptureActor, CaptureError, StudentActor, TeacherActor
from .geometry import FULL_FRAME, InvalidCorners, validate_corners
from ..batch_triage import normalize_name
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
        pages=[await page_view(p) for p in await live_pages(db, sub.id)],
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


async def _competitors(db: AsyncSession, batch_id: UUID, *, exclude: Optional[UUID],
                       student_id: Optional[UUID] = None,
                       pending_name: Optional[str] = None) -> list[CaptureSubmission]:
    """Other ACTIVE submissions in the batch claiming the same student — by
    id, or (for an unresolved typed name) by the normalized name."""
    rows = (await db.execute(
        select(CaptureSubmission).where(CaptureSubmission.batch_id == batch_id,
                                        CaptureSubmission.status != "discarded")
    )).scalars().all()
    out = []
    for s in rows:
        if exclude is not None and s.id == exclude:
            continue
        if student_id is not None and s.student_id == student_id:
            out.append(s)
        elif (pending_name and s.student_id is None
              and same_name(s.pending_student_name, pending_name)):
            out.append(s)
    return out


async def create_student_submission(db: AsyncSession, *, link: CaptureLink, name: str,
                                    confirm_match: bool) -> tuple[CaptureSubmission, str]:
    """§6.3 POST /submissions. The match is RECOMPUTED here; a client never
    names a student id. The response is the same whatever the outcome — the
    student is never told her submission is a conflict (D1)."""
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
        competitors = await _competitors(db, batch.id, exclude=None, student_id=match.id)
        note = "duplicate_student"
    else:
        state, student_id, pending = "pending", None, typed
        competitors = await _competitors(db, batch.id, exclude=None, pending_name=typed)
        note = "duplicate_pending_name"
    secret = tokens.random_token()
    sub = CaptureSubmission(
        batch_id=batch.id, user_id=locked.user_id, source="student_link", link_id=locked.id,
        device_secret_hash=tokens.sha256(secret), student_id=student_id,
        student_state="conflict" if competitors else state, pending_student_name=pending,
        conflict_note=note if competitors else None, status="draft")
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
    length_range = f"1,{settings.capture_max_file_bytes}"                    # R2: silent cap
    url = await asyncio.to_thread(
        _gcs().generate_signed_url, raw, settings.capture_upload_url_minutes,
        method="PUT", content_type=content_type,
        headers={"x-goog-content-length-range": length_range})
    return NewPage(page, url, {"Content-Type": content_type,
                               "x-goog-content-length-range": length_range})


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
               CapturePage.status.in_(("awaiting_upload", "analyze_failed")))
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

async def _version_job(db: AsyncSession, version_id: Optional[UUID]) -> Optional[TranscriptionJob]:
    if version_id is None:
        return None
    return (await db.execute(select(TranscriptionJob).where(
        TranscriptionJob.capture_version_id == version_id))).scalar_one_or_none()


async def _is_approved(db: AsyncSession, sub: CaptureSubmission) -> bool:
    """Has the CURRENT version passed the transcription gate (D6)?"""
    job = await _version_job(db, sub.current_version_id)
    if job is None or job.transcription_id is None:
        return False
    return (await db.scalar(select(Transcription.status).where(
        Transcription.id == job.transcription_id))) == "approved"


async def _withdraw(db: AsyncSession, version_id: Optional[UUID]) -> None:
    """D7: hide, never abort — the job may finish; its scan stays out of the
    batch because every batch read filters withdrawn jobs (OD-2)."""
    if version_id is None:
        return
    await db.execute(update(TranscriptionJob)
                     .where(TranscriptionJob.capture_version_id == version_id,
                            TranscriptionJob.withdrawn_at.is_(None))
                     .values(withdrawn_at=_now(), updated_at=_now()))


async def _discard(db: AsyncSession, sub: CaptureSubmission) -> None:
    if await _is_approved(db, sub):
        raise CaptureError(409, "already_approved",
                           "התמלול של המבחן הזה כבר אושר — הוא לא יימחק")
    sub.status = "discarded"
    sub.updated_at = _now()
    await _withdraw(db, sub.current_version_id)
    await db.flush()


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


async def _copy_for_late_resubmission(db: AsyncSession, sub: CaptureSubmission,
                                      pages: Sequence[CapturePage]) -> CaptureSubmission:
    """D6: the approved version stays exactly as it is; what she sent now goes
    on a NEW submission flagged for the teacher, carrying her pages."""
    late = CaptureSubmission(
        batch_id=sub.batch_id, user_id=sub.user_id, source=sub.source, link_id=sub.link_id,
        device_secret_hash=sub.device_secret_hash, student_id=sub.student_id,
        student_state="conflict", pending_student_name=sub.pending_student_name,
        conflict_note="late_resubmission", status="draft")
    db.add(late)
    await db.flush()
    for p in pages:
        db.add(CapturePage(
            submission_id=late.id, raw_gcs_uri=p.raw_gcs_uri, preview_gcs_uri=p.preview_gcs_uri,
            content_type=p.content_type, status=p.status, image_w=p.image_w, image_h=p.image_h,
            corners=p.corners, corners_source=p.corners_source, auto_corners=p.auto_corners,
            auto_corners_source=p.auto_corners_source, detect_confidence=p.detect_confidence,
            quality=p.quality, rotation=p.rotation, position=p.position))
    await db.flush()
    return late


async def save(db: AsyncSession, actor: CaptureActor, submission_id: UUID) -> Saved:
    probe = await load_submission(db, actor, submission_id)
    await db.execute(select(GradingBatch.id).where(GradingBatch.id == probe.batch_id)
                     .with_for_update())                                  # LOCK ORDER: batch…
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

    target = sub
    if await _is_approved(db, sub):                                       # D6
        if sub.source == "teacher":
            # A teacher-source save after approval cannot become a conflict
            # submission (SCN-8: a saved teacher capture is always confirmed),
            # and she is the one who approved it. Refuse, plainly.
            raise CaptureError(409, "already_approved",
                               "התמלול של המבחן הזה כבר אושר — שינויים לא יישלחו")
        target = await _copy_for_late_resubmission(db, sub, pages)
        pages = await live_pages(db, target.id)

    previous = target.current_version_id
    version_no = (await db.scalar(select(func.max(CaptureVersion.version_no)).where(
        CaptureVersion.submission_id == target.id)) or 0) + 1
    version = CaptureVersion(
        id=uuid4(), submission_id=target.id, version_no=version_no,
        scan_pipeline_version=settings.scan_pipeline_version,
        pages_snapshot=[{"page_id": str(p.id), "raw_gcs_uri": p.raw_gcs_uri,
                         "content_type": p.content_type, "corners": p.corners,
                         "rotation": p.rotation} for p in pages])             # SCN-2
    db.add(version)
    await db.flush()
    await _withdraw(db, previous)                                         # SCN-3 / D7
    target.current_version_id = version.id
    target.status = "saved"
    target.updated_at = _now()
    await db.flush()

    filename = await _unique_filename(db, target.batch_id, await _display_name(db, target))
    job = await ingest_batch_pdf(                                         # OD-1: ONE ingestion
        db, batch_id=target.batch_id, user_id=target.user_id,
        object_path=paths.pdf_path(target.id, version.id), filename=filename,
        capture_version_id=version.id)
    logger.info("capture_saved submission=%s version=%s version_no=%d pages=%d job=%s",
                target.id, version.id, version_no, len(pages), job.id)
    return Saved(target.id, version, job.id, len(pages))


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
    sub = await load_submission(db, actor, submission_id, lock=True)
    _editable(sub)
    if create_name is not None:                                  # immediate (R1, teacher side)
        student = await _create_student(db, sub.batch_id, actor.user_id, create_name)
    else:
        student = await _owned_student(db, actor.user_id, student_id)
    others = await _competitors(db, sub.batch_id, exclude=sub.id, student_id=student.id)
    if others and not replace_existing:
        raise await _already_submitted(db, others[0])           # the D5 dialog
    for other in others:
        await _discard(db, other)                               # refuses an approved one
    sub.student_id, sub.student_state, sub.conflict_note = student.id, "confirmed", None
    sub.updated_at = _now()
    await db.flush()
    return sub


async def resolve_pending(db: AsyncSession, actor: TeacherActor, submission_id: UUID, *,
                          student_id: Optional[UUID], approve_new: bool) -> CaptureSubmission:
    sub = await load_submission(db, actor, submission_id, lock=True)
    if sub.student_state != "pending":
        raise CaptureError(409, "not_pending", "ההגשה הזאת כבר לא ממתינה לאישור")
    if approve_new:
        student = await _create_student(db, sub.batch_id, actor.user_id, sub.pending_student_name)
    else:
        student = await _owned_student(db, actor.user_id, student_id)
    others = await _competitors(db, sub.batch_id, exclude=sub.id, student_id=student.id)
    sub.student_id = student.id
    # Never a silent double assignment (D5): if that student already has an
    # exam here, this one becomes a CONFLICT she resolves with one decision.
    sub.student_state = "conflict" if others else "confirmed"
    sub.conflict_note = "duplicate_student" if others else None
    sub.updated_at = _now()
    await db.flush()
    return sub


async def resolve_conflict(db: AsyncSession, actor: TeacherActor, submission_id: UUID, *,
                           action: str, student_id: Optional[UUID]) -> CaptureSubmission:
    sub = await load_submission(db, actor, submission_id, lock=True)
    if sub.student_state != "conflict":
        raise CaptureError(409, "not_conflict", "אין כאן התנגשות לפתור")
    if action == "discard_this":
        await _discard(db, sub)
        return sub
    sid = student_id or sub.student_id
    if sid is None:
        raise CaptureError(422, "student_required", "יש לבחור תלמיד")
    student = await _owned_student(db, actor.user_id, sid)
    others = await _competitors(db, sub.batch_id, exclude=sub.id, student_id=student.id,
                                pending_name=sub.pending_student_name)
    for other in others:
        # D6: work she already approved is never discarded — it stays, and
        # this one is kept beside it.
        if not await _is_approved(db, other):
            await _discard(db, other)
    sub.student_id, sub.student_state, sub.conflict_note = student.id, "confirmed", None
    sub.updated_at = _now()
    await db.flush()
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


async def batch_rows(db: AsyncSession, batch: GradingBatch) -> CaptureSubmissionsResponse:
    """The submissions panel (§6.11) — polled every 10 s while a link is open,
    so it is a FIXED number of grouped queries, not a few per row. Previews
    are signed only for CONFLICT rows (the side-by-side resolve dialog needs
    them); signing is an IAM call each, and the other rows never show one."""
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
    sub_ids = [r[0].id for r in rows_q]
    page_counts = dict((await db.execute(
        select(CapturePage.submission_id, func.count())
        .where(CapturePage.submission_id.in_(sub_ids), CapturePage.deleted_at.is_(None))
        .group_by(CapturePage.submission_id))).all()) if sub_ids else {}

    # The resolve dialog shows a conflict BESIDE what it conflicts with, so every
    # row sharing a claim (a student id, or a typed name) with a conflict row
    # gets a preview — and only those.
    def claim(sub):
        return ("id", sub.student_id) if sub.student_id is not None             else ("name", normalize_name(sub.pending_student_name or ""))
    contested = {claim(r[0]) for r in rows_q if r[0].student_state == "conflict"}

    rows: list[CaptureSubmissionRow] = []
    confirmed: set[UUID] = set()
    others = 0
    for sub, version, job, t_status, name in rows_q:
        if sub.student_state == "confirmed" and sub.student_id is not None:
            confirmed.add(sub.student_id)
        else:
            others += 1
        preview = None
        if claim(sub) in contested:
            first = next(iter(await live_pages(db, sub.id)), None)
            preview = (await page_view(first)).preview_url if first else None
        rows.append(CaptureSubmissionRow(
            submission_id=sub.id, source=sub.source,
            student=StudentRef(student_id=sub.student_id, display_name=name)
            if sub.student_id is not None and name else None,
            pending_student_name=sub.pending_student_name, student_state=sub.student_state,
            conflict_note=sub.conflict_note, page_count=int(page_counts.get(sub.id, 0)),
            saved_at=version.created_at.isoformat() if version else None,
            version_no=version.version_no if version else None,
            job_id=job.id if job else None, version_status=job.status if job else None,
            error_code=_error_code(job),
            transcription_id=job.transcription_id if job else None,
            transcription_status=t_status, page1_preview_url=preview))
    roster_size = None
    if batch.class_id is not None:
        roster_size = int(await db.scalar(select(func.count()).select_from(ClassMembership).where(
            ClassMembership.class_id == batch.class_id)) or 0)
    return CaptureSubmissionsResponse(
        rows=rows, counter=CaptureCounter(submitted_students=len(confirmed) + others,
                                          roster_size=roster_size))
