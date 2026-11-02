"""
Copy a capture batch's saved photo sets into a NEW batch on another rubric.

    python -m app.scripts.rebatch_capture --batch <id> --rubric <id>            # dry run
    python -m app.scripts.rebatch_capture --batch <id> --rubric <id> --apply

WHY THIS EXISTS (2026-11-02). A teacher saved a rubric, opened a batch on it,
photographed thirteen exams into it — and then noticed it was the wrong rubric
and uploaded the right one. A batch's rubric is pinned at creation and its
transcriptions are segmented into THAT rubric's question keys, so the photos
must be read again under the new rubric. Nobody should have to photograph
thirty pages twice to get there.

WHAT IT DOES
  * a new batch: the same fields `create_batch` writes (the new rubric and its
    contract version, the old batch's class and name);
  * per SAVED submission of the old batch (discarded and empty ones are not part
    of it): the version's objects are COPIED under a new submission's own prefix
    — raw photo + preview per page, and the compiled PDF when it exists, so step
    0 of the runner skips the compile (SCN-4) — then a new submission (same
    student, confirmed), new pages and a version 1 whose snapshot is the old
    one's with the new page ids and raw uris (same corners, rotation, order,
    scan pipeline version), and its job through `ingest_batch_pdf`, the ONE
    ingestion path (OD-1);
  * the old batch is renamed (`--old-suffix`) and its capture link closed. Its
    rows are otherwise untouched: nothing in it was approved (refused below).
  * ONE commit, then the jobs are enqueued. A failure before the commit deletes
    the objects it copied.

WHY COPY, NOT SHARE: the purge lists `captures/{submission_id}/` (PRV-11), and
the photos viewer shows a page only when its row belongs to the submission
(`version_view`). Objects referenced across submissions would be deleted by the
OTHER student's purge, or not shown at all.

WHAT IT REFUSES (nothing is written): a batch and rubric of different teachers;
the batch's own rubric; a rubric that cannot grade (`require_gradable_rubric`);
any transcription in the old batch past `transcribed` or any graded test; a
saved set with no confirmed student, or two claiming one student; a snapshot
page whose row is missing or whose photo is not under the set's own prefix; an
old batch already carrying the suffix (a second run would make a second
batch); and, with --apply, any job execution mode but `cloud_tasks` — inline
mode would transcribe on this machine.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.config import settings
from app.models.capture import CaptureLink, CapturePage, CaptureSubmission, CaptureVersion
from app.models.grading import GradedTest, GradingBatch, Rubric
from app.models.transcription import Transcription
from app.models.transcription_job import TranscriptionJob
from app.services.batch_ingest import enqueue_transcription_or_mark_failed, ingest_batch_pdf
from app.services.capture import paths

logger = logging.getLogger("rebatch_capture")

OLD_SUFFIX = " (מחוון שגוי)"

#: CapturePage columns that are NOT copied verbatim: identity, ownership, the
#: object uris (re-pointed at the copies), order (re-derived from the snapshot)
#: and lifecycle stamps.
_PAGE_REWRITTEN = {"id", "submission_id", "raw_gcs_uri", "preview_gcs_uri", "position",
                   "deleted_at", "created_at", "updated_at"}


class Refused(Exception):
    """A precondition failed. Nothing was written."""


@dataclass
class PageCopy:
    old: CapturePage
    new_id: UUID
    snap: dict


@dataclass
class SetCopy:
    old_sub: CaptureSubmission
    old_version: CaptureVersion
    filename: Optional[str]
    old_pdf: str
    new_sub_id: UUID = field(default_factory=uuid4)
    new_version_id: UUID = field(default_factory=uuid4)
    pages: List[PageCopy] = field(default_factory=list)

    @property
    def new_pdf(self) -> str:
        return paths.pdf_path(self.new_sub_id, self.new_version_id)


@dataclass
class Plan:
    batch: GradingBatch
    rubric: Rubric
    sets: List[SetCopy]
    skipped: List[Tuple[UUID, str]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _object_path(uri: str) -> str:
    bucket, path = paths.split_gs_uri(uri)
    if bucket != settings.gcs_bucket_name:
        raise Refused(f"object {uri} is not in the service bucket {settings.gcs_bucket_name}")
    return path


async def plan_rebatch(db, batch_id: UUID, rubric_id: UUID) -> Plan:
    batch = await db.get(GradingBatch, batch_id)
    rubric = await db.get(Rubric, rubric_id)
    if batch is None or rubric is None:
        raise Refused("batch or rubric not found")
    if batch.user_id != rubric.user_id:
        raise Refused("the batch and the rubric belong to different teachers")
    if batch.rubric_id == rubric.id:
        raise Refused("the batch already uses this rubric")
    if (batch.name or "").endswith(OLD_SUFFIX):
        raise Refused(f"batch {batch.id} is already renamed — it was rebatched before")
    if not rubric.is_compiled or not rubric.has_questions:
        raise Refused(f"rubric {rubric.id} cannot grade (not compiled, or no questions)")

    advanced = await db.scalar(select(func.count()).select_from(Transcription).where(
        Transcription.batch_id == batch.id, Transcription.status != "transcribed"))
    graded = await db.scalar(select(func.count()).select_from(GradedTest).where(
        GradedTest.batch_id == batch.id))
    if advanced or graded:
        raise Refused(f"the old batch has {advanced} transcription(s) past review and "
                      f"{graded} graded test(s) — copying would drop her decisions")

    subs = (await db.execute(select(CaptureSubmission).where(
        CaptureSubmission.batch_id == batch.id).order_by(CaptureSubmission.created_at)
    )).scalars().all()
    sets: List[SetCopy] = []
    skipped: List[Tuple[UUID, str]] = []
    seen_students = set()
    for sub in subs:
        if sub.status != "saved":
            skipped.append((sub.id, sub.status))
            continue
        if sub.student_state != "confirmed" or sub.student_id is None:
            raise Refused(f"saved set {sub.id} has no confirmed student ({sub.student_state})")
        if sub.student_id in seen_students:
            raise Refused(f"two saved sets claim student {sub.student_id} — resolve the duplicate first")
        seen_students.add(sub.student_id)
        version = await db.get(CaptureVersion, sub.current_version_id)
        job = (await db.execute(select(TranscriptionJob).where(
            TranscriptionJob.capture_version_id == version.id))).scalar_one_or_none()
        if job is None or job.withdrawn_at is not None:
            raise Refused(f"saved set {sub.id}: its current version has no live job")
        copy = SetCopy(old_sub=sub, old_version=version, filename=job.source_filename,
                       old_pdf=job.source_gcs_object_path)
        prefix = paths.submission_prefix(sub.id)
        for snap in version.pages_snapshot:
            page = await db.get(CapturePage, UUID(str(snap["page_id"])))
            if page is None or page.submission_id != sub.id:
                raise Refused(f"saved set {sub.id}: snapshot page {snap.get('page_id')} is missing")
            for uri in (page.raw_gcs_uri, page.preview_gcs_uri):
                if uri is not None and not _object_path(uri).startswith(prefix):
                    raise Refused(f"page {page.id}: {uri} is not under {prefix}")
            copy.pages.append(PageCopy(old=page, new_id=uuid4(), snap=dict(snap)))
        if not copy.pages:
            raise Refused(f"saved set {sub.id} has an empty snapshot")
        sets.append(copy)
    if not sets:
        raise Refused("the batch has no saved photo sets")
    return Plan(batch, rubric, sets, skipped)


def object_copies(plan: Plan, gcs) -> List[Tuple[str, str]]:
    """(source, destination) for every object the new sets need. The PDF is
    copied only when it exists; otherwise step 0 compiles it from the copies."""
    pairs: List[Tuple[str, str]] = []
    for s in plan.sets:
        for p in s.pages:
            pairs.append((_object_path(p.old.raw_gcs_uri), paths.raw_path(s.new_sub_id, p.new_id)))
            if p.old.preview_gcs_uri:
                pairs.append((_object_path(p.old.preview_gcs_uri),
                              paths.preview_path(s.new_sub_id, p.new_id)))
        if gcs.object_size(s.old_pdf) is not None:
            pairs.append((s.old_pdf, s.new_pdf))
    return pairs


async def write_rows(db, plan: Plan) -> Tuple[GradingBatch, List[UUID]]:
    """Every row, in the caller's transaction (it commits)."""
    old, rubric = plan.batch, plan.rubric
    bucket = settings.gcs_bucket_name
    new = GradingBatch(
        user_id=old.user_id, rubric_id=rubric.id,
        rubric_contract_version=rubric.contract_version,
        name=old.name, class_id=old.class_id, status="in_progress", test_count=0,
        expected_test_count=None, started_at=_now(),
    )
    db.add(new)
    await db.flush()

    job_ids: List[UUID] = []
    for s in plan.sets:
        sub = CaptureSubmission(
            id=s.new_sub_id, batch_id=new.id, user_id=old.user_id, source="teacher",
            student_id=s.old_sub.student_id, student_state="confirmed", status="draft")
        db.add(sub)
        await db.flush()
        snapshot = []
        for position, p in enumerate(s.pages, 1):
            raw = paths.gs_uri(bucket, paths.raw_path(s.new_sub_id, p.new_id))
            kept = {c.name: getattr(p.old, c.name) for c in CapturePage.__table__.columns
                    if c.name not in _PAGE_REWRITTEN}
            db.add(CapturePage(
                id=p.new_id, submission_id=s.new_sub_id, raw_gcs_uri=raw,
                preview_gcs_uri=(paths.gs_uri(bucket, paths.preview_path(s.new_sub_id, p.new_id))
                                 if p.old.preview_gcs_uri else None),
                position=position, **kept))
            snapshot.append({**p.snap, "page_id": str(p.new_id), "raw_gcs_uri": raw})
        db.add(CaptureVersion(id=s.new_version_id, submission_id=s.new_sub_id, version_no=1,
                              pages_snapshot=snapshot,
                              scan_pipeline_version=s.old_version.scan_pipeline_version))
        await db.flush()
        sub.current_version_id, sub.status, sub.updated_at = s.new_version_id, "saved", _now()
        await db.flush()
        job = await ingest_batch_pdf(db, batch_id=new.id, user_id=old.user_id,
                                     object_path=s.new_pdf, filename=s.filename,
                                     capture_version_id=s.new_version_id)
        job_ids.append(job.id)

    old.name = f"{old.name or ''}{OLD_SUFFIX}"
    old.updated_at = _now()
    link = (await db.execute(select(CaptureLink).where(
        CaptureLink.batch_id == old.id))).scalar_one_or_none()
    if link is not None and link.closed_at is None:
        link.closed_at = _now()
    await db.flush()
    return new, job_ids


async def run(batch_id: UUID, rubric_id: UUID, *, apply: bool, gcs, session_factory,
              enqueue: Optional[Callable[[UUID], Awaitable]] = None) -> Optional[UUID]:
    async with session_factory() as db:
        plan = await plan_rebatch(db, batch_id, rubric_id)
        pairs = object_copies(plan, gcs)
        print(f"batch {plan.batch.id} «{plan.batch.name}» → rubric {plan.rubric.id} "
              f"(contract {plan.rubric.contract_version})")
        for s in plan.sets:
            print(f"  set {s.old_sub.id} → {s.new_sub_id}  student={s.old_sub.student_id}  "
                  f"pages={len(s.pages)}  file={s.filename}")
        for sid, status in plan.skipped:
            print(f"  skipped {sid} ({status})")
        print(f"{len(plan.sets)} set(s), {len(pairs)} object copies")
        if not apply:
            print("dry run — nothing written")
            return None

        copied: List[str] = []
        try:
            for src, dst in pairs:
                await asyncio.to_thread(gcs.copy_object, src, dst)
                copied.append(dst)
            new, job_ids = await write_rows(db, plan)
            await db.commit()
        except BaseException:
            await db.rollback()
            for s in plan.sets:
                await asyncio.to_thread(gcs.delete_folder, paths.submission_prefix(s.new_sub_id))
            logger.error("rebatch_failed batch=%s copied=%d (deleted)", batch_id, len(copied))
            raise
        new_id = new.id
    for job_id in job_ids:
        await enqueue_transcription_or_mark_failed(job_id, enqueue=enqueue)
    print(f"new batch {new_id}: {len(job_ids)} job(s) enqueued")
    return new_id


async def main(batch_id: UUID, rubric_id: UUID, apply: bool) -> None:
    from app.database import AsyncSessionLocal, engine
    from app.services.cloud_tasks_service import jobs_execution_mode
    from app.services.gcs_service import get_gcs_service

    if apply and (jobs_execution_mode() != "cloud_tasks" or not settings.service_base_url):
        raise Refused(f"job execution mode is {jobs_execution_mode()!r} — --apply needs "
                      "JOBS_EXECUTION_MODE=cloud_tasks and SERVICE_BASE_URL, or the "
                      "transcriptions would run on this machine")
    try:
        await run(batch_id, rubric_id, apply=apply, gcs=get_gcs_service(),
                  session_factory=AsyncSessionLocal)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=UUID, required=True)
    ap.add_argument("--rubric", type=UUID, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.batch, args.rubric, args.apply))
