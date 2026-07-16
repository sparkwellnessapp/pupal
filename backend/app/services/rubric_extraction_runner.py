"""
Extraction job runner (PR-1).

run_extraction_job(job_id) drives a queued RubricExtractionJob through:
    queued → extracting → completed   (or → failed)

Design constraints (mirrors grading_runner discipline, adapted to ADR-1):
  - Request-context-free: takes only a UUID, owns its own AsyncSessions.
  - Runs INSIDE the Cloud Tasks request (cloud_tasks mode) or an asyncio task
    (inline dev mode) — never FastAPI BackgroundTasks (CPU-throttle hazard).
  - CAS idempotency lives HERE so both modes share it: the first statement is
    UPDATE ... SET status='extracting' WHERE id=:id AND status='queued';
    zero rows ⇒ silent no-op (duplicate delivery / already-terminal row).
  - Session discipline: progress writes are short independent sessions/commits
    (stage + updated_at heartbeat) — never hold a transaction across the
    1–8 minute extraction.
  - DB CHECK rubric_extraction_jobs_status_consistency shapes every write:
    'completed' needs result_json + finished_at together; 'failed' needs
    error_message + finished_at together — one commit each.
"""
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import update

from app.config import settings
from app.database import get_db_context
from app.models.rubric_extraction_job import RubricExtractionJob
from app.services.docx_v3.pipeline import (
    EXTRACTION_PROMPT_VERSION,
    ExtractionConfig,
    ProgressEvent,
    _get_llm_config,
    _llm_timeout_s,
    _transport_attempts,
    extract_rubric_from_docx,
)

logger = logging.getLogger(__name__)


def _effective_llm_config() -> Dict[str, Any]:
    """Snapshot of the LLM env at run start — provenance for the job row.
    Reads the same channels the pipeline itself reads (_get_llm_config + the
    generation knobs), so the record matches what actually ran.

    PR-2: timeout_s / transport_retries are now experiment-relevant constants
    (they change transport behavior and latency), so they must be self-describing
    per job — same rationale as the D-2 model pin.
    """
    provider, model = _get_llm_config()
    return {
        "provider": provider,
        "model": model,
        "reasoning_effort": os.environ.get("EXTRACTION_LLM_REASONING_EFFORT") or None,
        "max_tokens": os.environ.get("EXTRACTION_LLM_MAX_TOKENS") or None,
        "timeout_s": _llm_timeout_s(),
        "transport_retries": _transport_attempts() - 1,
        "task_budget_s": settings.extraction_task_budget_s,
    }


async def _claim_job(job_id: UUID) -> bool:
    """CAS queued→extracting. False = someone else ran it / row is terminal."""
    now = datetime.now(timezone.utc)
    async with get_db_context() as db:
        result = await db.execute(
            update(RubricExtractionJob)
            .where(
                RubricExtractionJob.id == job_id,
                RubricExtractionJob.status == "queued",
            )
            .values(status="extracting", started_at=now, updated_at=now,
                    progress_stage=None, progress_detail=None)
        )
        await db.commit()
        return result.rowcount == 1


async def _write_progress(job_id: UUID, event: ProgressEvent) -> None:
    """Short-lived heartbeat write. Exceptions propagate to the pipeline's
    _emit_progress, which swallows them — a progress-write failure never
    affects the extraction."""
    async with get_db_context() as db:
        await db.execute(
            update(RubricExtractionJob)
            .where(RubricExtractionJob.id == job_id,
                   RubricExtractionJob.status == "extracting")
            .values(
                progress_stage=event.stage,
                progress_detail=event.detail,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()


async def run_extraction_job(job_id: UUID) -> bool:
    """Entry point for the task handler (cloud_tasks) and inline dev mode.

    Returns True if this invocation ran the extraction, False on no-op.
    Never raises: failures land on the row as status='failed'.
    """
    # PR-2: monotonic budget clock starts at TASK ENTRY — everything before the
    # pipeline (CAS, row load, GCS download) is real wall time inside the same
    # Cloud Run request, so it is MEASURED and subtracted, never assumed away.
    t0 = time.monotonic()

    if not await _claim_job(job_id):
        logger.info("run_extraction_skipped", extra={"job_id": str(job_id)})
        return False

    try:
        # Load the claimed row (fresh session; short-lived).
        async with get_db_context() as db:
            job: Optional[RubricExtractionJob] = await db.get(RubricExtractionJob, job_id)
            if job is None:  # row deleted between CAS and load — nothing to do
                logger.warning("run_extraction_row_vanished", extra={"job_id": str(job_id)})
                return False
            source_gcs_uri = job.source_gcs_uri
            params: Dict[str, Any] = dict(job.request_params or {})

        # Download source bytes (GCS client is sync — keep the loop free).
        import asyncio

        from app.services.gcs_service import get_gcs_service

        gcs = get_gcs_service()
        object_path = source_gcs_uri.removeprefix(f"gs://{gcs.bucket_name}/")
        file_bytes: bytes = await asyncio.to_thread(gcs.download_bytes, object_path)

        # Config exactly as the sync endpoint builds it today.
        config = ExtractionConfig(
            subject=params.get("subject") or "computer_science",
            locale=params.get("locale") or "he-IL",
        )
        llm_config = _effective_llm_config()

        async def on_progress(event: ProgressEvent) -> None:
            await _write_progress(job_id, event)

        # Budget remaining for the pipeline = task budget − pre-work already spent.
        deadline_seconds = settings.extraction_task_budget_s - (time.monotonic() - t0)
        logger.info(
            "extraction_budget",
            extra={"job_id": str(job_id),
                   "prework_s": round(time.monotonic() - t0, 1),
                   "deadline_s": round(deadline_seconds, 1)},
        )

        result = await extract_rubric_from_docx(
            file_bytes=file_bytes,
            extraction_config=config,
            name=params.get("name"),
            description=params.get("description"),
            test_topic=params.get("test_topic") or None,
            on_progress=on_progress,
            deadline_seconds=deadline_seconds,
        )

        if result.response is None:
            # Same condition the sync endpoint treats as failure today.
            raise RuntimeError("Extraction produced no result")

        now = datetime.now(timezone.utc)
        m = result.metrics
        async with get_db_context() as db:
            await db.execute(
                update(RubricExtractionJob)
                .where(RubricExtractionJob.id == job_id,
                       RubricExtractionJob.status == "extracting")
                .values(
                    status="completed",
                    result_json=result.response.model_dump(mode="json"),
                    warnings=list(result.warnings),
                    errors=list(result.errors),
                    requires_review=result.requires_review,
                    prompt_version=EXTRACTION_PROMPT_VERSION,
                    pipeline_version=result.metadata.get("pipeline_version"),
                    llm_model=m.llm_model,
                    input_tokens=m.input_tokens,
                    output_tokens=m.output_tokens,
                    retry_count=m.retry_count,
                    finish_reason=m.finish_reason,
                    duration_ms=int(m.total_time_seconds * 1000),
                    llm_config=llm_config,
                    progress_stage="complete",
                    progress_detail=None,
                    finished_at=now,
                    updated_at=now,
                )
            )
            await db.commit()
        logger.info(
            "extraction_completed",
            extra={"job_id": str(job_id), "input_tokens": m.input_tokens,
                   "output_tokens": m.output_tokens, "retries": m.retry_count,
                   "duration_ms": int(m.total_time_seconds * 1000)},
        )
        return True

    except Exception as e:
        logger.exception("extraction_failed", extra={"job_id": str(job_id)})
        now = datetime.now(timezone.utc)
        try:
            async with get_db_context() as db:
                await db.execute(
                    update(RubricExtractionJob)
                    .where(RubricExtractionJob.id == job_id,
                           RubricExtractionJob.status == "extracting")
                    .values(
                        status="failed",
                        error_message=f"{type(e).__name__}: {str(e)[:500]}",
                        finished_at=now,
                        updated_at=now,
                    )
                )
                await db.commit()
        except Exception:  # pragma: no cover — the row stays 'extracting' and
            # surfaces via heartbeat-staleness + the retry endpoint.
            logger.exception("extraction_failure_write_failed",
                             extra={"job_id": str(job_id)})
        return True
