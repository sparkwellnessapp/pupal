"""
Transcription job runner — Cloud Tasks migration.

run_transcription_job(job_id) drives a queued TranscriptionJob through:
    queued → running → completed   (or → failed)

Design (mirrors rubric_extraction_runner discipline):
  - Request-context-free: takes only a UUID, owns its own AsyncSessions.
  - Runs INSIDE the Cloud Tasks request (CPU guaranteed) or an asyncio task
    (inline dev mode) — never FastAPI BackgroundTasks.
  - CAS idempotency FIRST: UPDATE ... SET status='running' WHERE id=:id AND
    status='queued'; zero rows ⇒ silent no-op. This is what makes the queue's
    maxAttempts=3 redelivery safe (owner-ratified deviation from the
    extraction ADR): a duplicate delivery finds the row claimed/terminal.
  - Heartbeat: a SIDECAR task touches updated_at every ~60s while the
    pipeline runs — the pipeline itself is untouched (no plumbing through the
    two-phase engine). transcription_job_liveness reaps a lapsed heartbeat.
  - Terminal success is ONE transaction: INSERT transcriptions row + UPDATE
    job→completed, atomically — the lost-INSERT/state-divergence class dies.
    The job UPDATE is guarded on status='running'; rowcount 0 means the claim
    was lost (reaped + possibly retried elsewhere) and the ZOMBIE result is
    rolled back rather than double-inserted.
  - Bounded doc-level resilience: one re-run on RETRYABLE transport failure
    only (the eval runner's proven pattern, carried over from the old
    fan-out's _transcribe_with_cap).
  - Never raises: failures land on the row as status='failed' (+ net_diag
    verdict), which the per-document retry endpoint accepts.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import update

from ..config import settings
from ..database import get_db_context
from ..models.grading import Rubric
from ..models.transcription import Transcription
from ..models.transcription_job import TranscriptionJob
from .transcribe_one import run_pipeline_and_build_draft
from .transcription.vlm_provider import VLMCallError

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 60.0
_DOC_RERUN_BACKOFF_S = 10.0


async def _claim_job(job_id: UUID) -> bool:
    """CAS queued→running. False = duplicate delivery / already-terminal row."""
    now = datetime.now(timezone.utc)
    async with get_db_context() as db:
        result = await db.execute(
            update(TranscriptionJob)
            .where(TranscriptionJob.id == job_id,
                   TranscriptionJob.status == "queued")
            .values(status="running", started_at=now, updated_at=now,
                    attempt_count=TranscriptionJob.attempt_count + 1)
        )
        await db.commit()
        return result.rowcount == 1


async def _heartbeat_loop(job_id: UUID, stop: asyncio.Event) -> None:
    """Touch updated_at while the pipeline runs. Guarded on status='running'
    so a reaped/retried row is never resurrected. A single failed heartbeat
    is swallowed (transient DB hiccup) — the TTL tolerates several misses."""
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL_S)
            return                                    # stopped — worker is done
        except asyncio.TimeoutError:
            pass                                      # interval elapsed — beat
        try:
            async with get_db_context() as db:
                await db.execute(
                    update(TranscriptionJob)
                    .where(TranscriptionJob.id == job_id,
                           TranscriptionJob.status == "running")
                    .values(updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
        except Exception:
            logger.warning("transcription_job_heartbeat_failed",
                           extra={"job_id": str(job_id)})


async def _fail_job(job_id: UUID, exc: Exception, net_verdict: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    async with get_db_context() as db:
        await db.execute(
            update(TranscriptionJob)
            .where(TranscriptionJob.id == job_id,
                   TranscriptionJob.status == "running")
            .values(status="failed",
                    error_message=f"{type(exc).__name__}: {str(exc)[:400]}",
                    net_verdict=net_verdict,
                    finished_at=now, updated_at=now)
        )
        await db.commit()


async def run_transcription_job(job_id: UUID) -> bool:
    """Entry point for the task handler (cloud_tasks) and inline dev mode.
    Returns True if this invocation ran the document, False on no-op.
    Never raises: failures land on the row as status='failed'."""
    if not await _claim_job(job_id):
        logger.info("run_transcription_skipped", extra={"job_id": str(job_id)})
        return False

    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_heartbeat_loop(job_id, stop))
    try:
        # Load the claimed row + the rubric's exam-spec source (short sessions).
        async with get_db_context() as db:
            job: Optional[TranscriptionJob] = await db.get(TranscriptionJob, job_id)
            if job is None:
                logger.warning("run_transcription_row_vanished",
                               extra={"job_id": str(job_id)})
                return False
            batch_id = job.batch_id
            rubric_id = job.rubric_id
            user_id = job.user_id
            object_path = job.source_gcs_object_path
            filename = job.source_filename
            doc_priority = job.doc_priority

            rubric: Optional[Rubric] = await db.get(Rubric, rubric_id)
            if rubric is None:
                raise ValueError(f"Rubric {rubric_id} not found")
            spec_source = rubric.draft_json or rubric.contract_json
            subject = rubric.subject  # the durable key (migration 027); selects the P1 profile

        # Source bytes were persisted at intake — download, don't re-upload.
        from .gcs_service import get_gcs_service
        gcs = get_gcs_service()
        pdf_bytes: bytes = await asyncio.to_thread(gcs.download_bytes, object_path)

        # Bounded doc-level resilience: a transient window can outlast the
        # scheduler's single transport retry and kill the whole document.
        # Only RETRYABLE transport failures re-run; content/parse and
        # permanent errors never do.
        for attempt in (1, 2):
            try:
                draft = await run_pipeline_and_build_draft(
                    pdf_bytes=pdf_bytes, filename=filename,
                    spec_source=spec_source, doc_priority=doc_priority,
                    subject=subject,
                )
                break
            except VLMCallError as exc:
                if not exc.retryable or attempt == 2:
                    raise
                logger.warning(
                    "transcription transport failure (%s) — re-running "
                    "document once: %s", exc.kind.value, filename)
                await asyncio.sleep(_DOC_RERUN_BACKOFF_S)

        # Terminal success — ONE transaction: the transcriptions INSERT and
        # the job's completed flip commit or roll back together.
        now = datetime.now(timezone.utc)
        async with get_db_context() as db:
            transcription = Transcription(
                user_id=user_id,
                rubric_id=rubric_id,
                batch_id=batch_id,
                student_id=None,
                student_name=None,
                gcs_uri=f"gs://{settings.gcs_bucket_name}/{object_path}",
                gcs_bucket=settings.gcs_bucket_name,
                gcs_object_path=object_path,
                filename=filename,
                draft_json=draft.model_dump(mode="json"),
                contract_json=None,
                status="transcribed",
            )
            db.add(transcription)
            await db.flush()
            result = await db.execute(
                update(TranscriptionJob)
                .where(TranscriptionJob.id == job_id,
                       TranscriptionJob.status == "running")
                .values(status="completed",
                        transcription_id=transcription.id,
                        finished_at=now, updated_at=now)
            )
            if result.rowcount != 1:
                # The claim was lost (reaped as stale; possibly already
                # re-queued and re-run elsewhere). Committing would DOUBLE the
                # document — discard the zombie result instead.
                await db.rollback()
                logger.warning("transcription_zombie_completion_discarded",
                               extra={"job_id": str(job_id)})
                return True
            await db.commit()
            logger.info(
                "transcription_created",
                extra={
                    "transcription_id": str(transcription.id),
                    "job_id": str(job_id),
                    "batch_id": str(batch_id),
                    "duration_ms": draft.transcription_duration_ms,
                },
            )
        return True

    except Exception as exc:
        logger.exception("transcription_job_failed",
                         extra={"job_id": str(job_id)})
        net_verdict: Optional[str] = None
        try:
            from .net_diag import diagnose_transport_failure
            net_verdict = await diagnose_transport_failure(
                f"batch transcription job {job_id}", exc)
        except Exception:
            pass
        try:
            await _fail_job(job_id, exc, net_verdict)
        except Exception:  # the row stays 'running' and surfaces via
            # heartbeat-staleness + the retry endpoint.
            logger.exception("transcription_failure_write_failed",
                             extra={"job_id": str(job_id)})
        return True

    finally:
        stop.set()
        heartbeat.cancel()
        try:
            await heartbeat
        except (asyncio.CancelledError, Exception):
            pass
