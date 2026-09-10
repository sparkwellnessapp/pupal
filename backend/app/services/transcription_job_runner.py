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
import time
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
from .transcription.budget import BudgetExceeded
from .transcription.vlm_provider import VLMCallError

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 60.0
_DOC_RERUN_BACKOFF_S = 10.0
#: A second full pipeline is only worth STARTING if the budget can plausibly
#: cover one. Measured production runs land at 47-78s end to end; 120s is that
#: with headroom, and it is deliberately a floor on STARTING rather than a
#: promise about finishing — the pipeline's own budget checks handle the rest.
_DOC_RERUN_MIN_BUDGET_S = 120.0


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
            logger.warning("transcription_job_heartbeat_failed job_id=%s", job_id)


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
    # THE WALL CLOCK starts at the CAS claim, not at pipeline entry: the GCS
    # download and the rubric read are time the teacher waits through, so they
    # are INSIDE the budget rather than assumed away (PR-2: pre-work is
    # MEASURED, never assumed).
    t0 = time.monotonic()
    if not await _claim_job(job_id):
        logger.info("run_transcription_skipped job_id=%s", job_id)
        return False

    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_heartbeat_loop(job_id, stop))
    # Bound before the try so no error handler below can raise NameError while
    # reporting a different failure — an exception inside an exception path is
    # how a loud fault becomes a quiet one.
    filename: Optional[str] = None
    try:
        # Load the claimed row + the rubric's exam-spec source (short sessions).
        async with get_db_context() as db:
            job: Optional[TranscriptionJob] = await db.get(TranscriptionJob, job_id)
            if job is None:
                logger.warning("run_transcription_row_vanished job_id=%s", job_id)
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
        budget_s = settings.transcription_task_budget_s
        for attempt in (1, 2):
            try:
                draft = await run_pipeline_and_build_draft(
                    pdf_bytes=pdf_bytes, filename=filename,
                    spec_source=spec_source, doc_priority=doc_priority,
                    subject=subject,
                    deadline_seconds=budget_s,
                    budget_started_at=t0,
                )
                break
            except VLMCallError as exc:
                if not exc.retryable or attempt == 2:
                    raise
                # GATED ON THE REMAINING BUDGET (owner-ruled 2026-09-10). This
                # re-run was added for a real transient window, and it stays —
                # but it is the outermost of the three retry layers that used to
                # MULTIPLY (2 x 2 x 2 x 240s = 1,920s against a 900s Cloud Run
                # request timeout). Starting a second full pipeline the budget
                # cannot pay for buys nothing and costs the teacher the wait.
                elapsed = time.monotonic() - t0
                needed = _DOC_RERUN_BACKOFF_S + _DOC_RERUN_MIN_BUDGET_S
                if elapsed + needed > budget_s:
                    logger.warning(
                        "transcription transport failure (%s) on %s — NOT "
                        "re-running: %.0fs of the %.0fs budget already spent",
                        exc.kind.value, filename, elapsed, budget_s)
                    raise
                logger.warning(
                    "transcription transport failure (%s) — re-running "
                    "document once (%.0fs of %.0fs budget spent): %s",
                    exc.kind.value, elapsed, budget_s, filename)
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
                logger.warning("transcription_zombie_completion_discarded job_id=%s", job_id)
                return True
            await db.commit()
            logger.info(
                "transcription_created transcription_id=%s job_id=%s "
                "batch_id=%s file=%s duration_ms=%s wall_s=%.0f",
                transcription.id, job_id, batch_id, filename,
                draft.transcription_duration_ms, time.monotonic() - t0,
            )
        return True

    except BudgetExceeded as exc:
        # TERMINAL AND RETRYABLE, and deliberately NOT routed through net_diag:
        # the budget ran out, which is a statement about OUR wall clock, not
        # about the teacher's network — a "local-no-internet" verdict here would
        # send her to check her WiFi over a fault that is entirely ours. The
        # source PDF is in GCS, so the retry costs her nothing.
        logger.warning("transcription_job_budget_exceeded job_id=%s file=%s: %s",
                       job_id, filename, exc)
        try:
            await _fail_job(job_id, exc, None)
        except Exception:
            logger.exception("transcription_failure_write_failed job_id=%s", job_id)
        return True

    except Exception as exc:
        logger.exception("transcription_job_failed job_id=%s", job_id)
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
            # heartbeat-staleness, the absolute cap, + the retry endpoint.
            logger.exception("transcription_failure_write_failed job_id=%s",
                             job_id)
        return True

    finally:
        stop.set()
        heartbeat.cancel()
        try:
            await heartbeat
        except (asyncio.CancelledError, Exception):
            pass
