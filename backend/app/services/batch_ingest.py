"""
Ingestion into a batch — ONE place (PR_in_house_scanning.md §6.7, ruling OD-1).

A PDF becomes part of a batch exactly one way: a `transcription_jobs` row
inserted under the batch's FOR UPDATE lock, committed, then enqueued. Two
callers:

  * `POST /batches/{id}/files` — an uploaded PDF, already stored in GCS;
  * capture save — a frozen capture version whose PDF does not exist yet: the
    job's object path is the version's deterministic PDF path, and step 0 of
    the runner compiles it (SCN-4).

The caller owns the transaction. That is the point of the split: capture save
must insert the frozen version, supersede the previous one and insert this job
in ONE commit (SCN-3/SCN-6), while the upload endpoint commits the job alone
and maps its own IntegrityError to the idempotent path.

Withdrawn jobs (OD-2) are not part of their batch, so they are not counted:
`doc_priority`, the human-facing `test_count`, and the re-declare floor all
agree with the rollup's denominator.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_context
from ..models.grading import GradingBatch
from ..models.transcription import Transcription
from ..models.transcription_job import TranscriptionJob
from .cloud_tasks_service import enqueue_transcription_task

logger = logging.getLogger(__name__)


def live_jobs(batch_id: UUID):
    """`transcription_jobs` of a batch that are part of it — the ONE predicate
    every batch read and count uses (OD-2)."""
    return select(TranscriptionJob).where(
        TranscriptionJob.batch_id == batch_id,
        TranscriptionJob.withdrawn_at.is_(None),
    )


def live_transcriptions(batch_id: UUID):
    """`transcriptions` of a batch that are part of it: every row except the
    scans of WITHDRAWN jobs (a superseded capture version that finished
    anyway — D7 lets it finish — or a discarded submission's)."""
    withdrawn = select(TranscriptionJob.transcription_id).where(
        TranscriptionJob.batch_id == batch_id,
        TranscriptionJob.withdrawn_at.is_not(None),
        TranscriptionJob.transcription_id.is_not(None),
    )
    return select(Transcription).where(
        Transcription.batch_id == batch_id,
        Transcription.id.not_in(withdrawn),
    )


async def is_withdrawn_transcription(db: AsyncSession, transcription_id: UUID) -> bool:
    return (await db.execute(
        select(TranscriptionJob.id).where(
            TranscriptionJob.transcription_id == transcription_id,
            TranscriptionJob.withdrawn_at.is_not(None),
        ).limit(1)
    )).scalar_one_or_none() is not None


async def count_live_jobs(db: AsyncSession, batch_id: UUID) -> int:
    return int((await db.execute(
        select(func.count()).select_from(TranscriptionJob).where(
            TranscriptionJob.batch_id == batch_id,
            TranscriptionJob.withdrawn_at.is_(None),
        )
    )).scalar_one())


async def ingest_batch_pdf(
    db: AsyncSession,
    *,
    batch_id: UUID,
    user_id: UUID,
    object_path: str,
    filename: Optional[str],
    client_file_id: Optional[UUID] = None,
    capture_version_id: Optional[UUID] = None,
) -> TranscriptionJob:
    """Insert ONE queued job into the batch, under the batch row's FOR UPDATE
    lock (B9.4: `doc_priority` = live job count, race-free under parallel
    appends). Flushes; never commits — the caller does, then calls
    `enqueue_transcription_or_mark_failed(job.id)` AFTER its commit."""
    locked_batch = (await db.execute(
        select(GradingBatch).where(GradingBatch.id == batch_id).with_for_update()
    )).scalar_one()
    count = await count_live_jobs(db, batch_id)
    job = TranscriptionJob(
        user_id=user_id,
        batch_id=batch_id,
        rubric_id=locked_batch.rubric_id,
        status="queued",
        source_gcs_object_path=object_path,
        source_filename=filename,
        doc_priority=count,              # arrival order — within-doc depth-first
        client_file_id=client_file_id,
        capture_version_id=capture_version_id,
    )
    db.add(job)
    # test_count maintained under the same lock — the column stays honest for
    # humans reading the table; the rollup's truth is COUNT(live jobs) (B9.5).
    locked_batch.test_count = count + 1
    await db.flush()
    return job


async def enqueue_transcription_or_mark_failed(
    job_id: UUID, *, enqueue: Optional[Callable[[UUID], Awaitable]] = None,
) -> None:
    """Hand a committed job to the substrate (Cloud Tasks migration). If the
    enqueue itself fails, the row must not rot as unreachable-'queued' — mark
    it failed so the teacher sees a durable, retryable state (the retry
    endpoint re-enqueues from GCS). Own short session: the request session is
    closed by the time this runs. (A process that dies between the commit and
    this call leaves a 'queued' row; the 90-minute dispatch backstop of LIV-1
    reaps it to failed — slow, but never a trap.)

    `enqueue` lets a caller hand in ITS module-level name for the enqueue, so
    a test that patches that name keeps patching the one implementation."""
    try:
        await (enqueue or enqueue_transcription_task)(job_id)
    except Exception as e:
        logger.exception("transcription_enqueue_failed job_id=%s", job_id)
        now = datetime.now(timezone.utc)
        async with get_db_context() as db:
            await db.execute(
                update(TranscriptionJob)
                .where(TranscriptionJob.id == job_id,
                       TranscriptionJob.status == "queued")
                .values(status="failed",
                        error_message=f"enqueue failed: {type(e).__name__}: {str(e)[:300]}",
                        finished_at=now, updated_at=now)
            )
            await db.commit()
