"""
Background-safe single-test transcription pipeline (S11).

transcribe_one() is the extracted core of POST /transcribe (S4).
- Called from POST /transcribe with batch_id=None (no behavior change for single-test)
- Called from POST /batches fan-out with batch_id set (batch mode)
- Creates its own AsyncSession via get_db_context() — fully request-context-free.
- Can be safely enqueued via BackgroundTasks or called from async code.

Error handling: raises on VLM or GCS failure. The background-task wrapper in
batch_grading.py catches exceptions and logs them; a failed transcription leaves
no row (the batch's transcribing count stays at expected - actual).
"""
import asyncio
import logging
import time
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..database import get_db_context
from ..models.grading import Rubric
from ..models.transcription import Transcription
from ..services.pdf_render import page_count as pdf_page_count
from ..services.gcs_service import get_gcs_service
from ..services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
)
from ..services.transcription_adapter import build_transcription_draft

logger = logging.getLogger(__name__)

# Upload-only re-attempts after the overlapped GCS upload fails (2026-08-12):
# by the time the upload is joined, the pipeline result — minutes of LLM work —
# is already in memory. Discarding it over a stalled upload is the one failure
# mode we actually lost data to; re-attempting costs only bandwidth.
_UPLOAD_EXTRA_ATTEMPTS = 2
_UPLOAD_RETRY_BACKOFF_S = 3.0


async def transcribe_one(
    pdf_bytes: bytes,
    filename: str | None,
    rubric_id: UUID,
    user_id: UUID,
    batch_id: UUID | None = None,
    doc_priority: int = 0,
) -> str:
    """
    Run the full transcription pipeline for one PDF and persist the result.
    Returns the new transcription_id as a string.

    Each call creates a new Transcription row. There is no idempotency guard —
    duplicate calls with the same PDF create duplicate rows (acceptable for
    the batch upload pattern where each PDF is distinct).

    Args:
        pdf_bytes: Raw PDF content.
        filename:  Original filename (for display and GCS path).
        rubric_id: The compiled rubric to transcribe against.
        user_id:   The owning teacher.
        batch_id:  Set for batch-mode transcriptions; None for single-test.

    Returns:
        str — the new transcription_id.

    Raises:
        ValueError if the rubric doesn't exist.
        Exception propagated from VLM or GCS on failure.

    TWO-SESSION DESIGN (2026-08-07 incident): a transcription is 60-90s of
    render + LLM + GCS work. The previous single session held an
    idle-in-transaction connection across all of it, and the Supabase
    transaction pooler resets such connections — the pipeline would finish and
    the INSERT then die on the dead connection, silently losing the row (a
    batch was observed landing 0/4 this way). Session 1 reads the rubric and
    releases immediately; NO connection is held during the pipeline; session 2
    is a fresh checkout (pool_pre_ping revalidates) just for the INSERT.
    """
    # Session 1: read the rubric, release the connection immediately.
    async with get_db_context() as db:
        rubric: Rubric | None = await db.get(Rubric, rubric_id)
        if rubric is None:
            raise ValueError(f"Rubric {rubric_id} not found")
        # Plain dicts — safe to use after the session closes.
        spec_source = rubric.draft_json or rubric.contract_json
        subject = rubric.subject  # the durable key (migration 027); selects the P1 profile

    # GCS upload OVERLAPS the pipeline (2026-08-12 latency finding): it needs
    # only pdf_bytes, yet it used to run AFTER the 60-90s pipeline, adding its
    # full duration to every document — minutes, when the Google route
    # degrades. Started here, awaited before the INSERT; on pipeline failure
    # it is awaited-and-abandoned (a possible orphan object is accepted — the
    # row is what matters, and no row references it).
    gcs = get_gcs_service()
    obj_id = str(uuid4())
    object_path = f"transcriptions/{user_id}/{obj_id}.pdf"
    upload_task = asyncio.create_task(run_in_threadpool(
        gcs.upload_bytes, pdf_bytes, object_path, "application/pdf"
    ))

    t_start = time.monotonic()
    try:
        return await _pipeline_and_persist(
            pdf_bytes=pdf_bytes, filename=filename, rubric_id=rubric_id,
            user_id=user_id, batch_id=batch_id, doc_priority=doc_priority,
            spec_source=spec_source, t_start=t_start,
            upload_task=upload_task, object_path=object_path,
            subject=subject,
        )
    except BaseException:
        # Don't leave the upload dangling past this call's lifetime.
        upload_task.cancel()
        raise


async def _join_upload_with_retry(
    upload_task: "asyncio.Task[None]",
    pdf_bytes: bytes,
    object_path: str,
    filename: str | None,
) -> None:
    """Await the overlapped source-PDF upload; on failure, re-attempt the
    upload itself up to _UPLOAD_EXTRA_ATTEMPTS times.

    Observed 2026-08-12: a transcription that had COMPLETED P1+P2 was thrown
    away because the storage SDK's retry budget died on a congested uplink.
    The pipeline result must never be hostage to this upload — the upload is
    re-tried fresh (same per-call object path — a uuid4 minted at intake,
    fixed for this call, NOT content-addressed — so re-attempts are
    idempotent); only when every attempt fails does the failure propagate.
    """
    try:
        await upload_task
        return
    except Exception as exc:
        last_exc: Exception = exc

    gcs = get_gcs_service()
    for attempt in range(1, _UPLOAD_EXTRA_ATTEMPTS + 1):
        logger.warning(
            "GCS upload of %s failed (%s) — re-attempting upload only (%d/%d)",
            filename, last_exc, attempt, _UPLOAD_EXTRA_ATTEMPTS,
        )
        await asyncio.sleep(_UPLOAD_RETRY_BACKOFF_S * attempt)
        try:
            await run_in_threadpool(
                gcs.upload_bytes, pdf_bytes, object_path, "application/pdf"
            )
            logger.info("GCS upload of %s recovered on re-attempt %d",
                        filename, attempt)
            return
        except Exception as exc:
            last_exc = exc

    from .net_diag import diagnose_transport_failure
    await diagnose_transport_failure(f"GCS upload of {filename}", last_exc)
    raise last_exc


async def run_pipeline_and_build_draft(
    *,
    pdf_bytes: bytes,
    filename: str | None,
    spec_source: dict | None,
    doc_priority: int = 0,
    t_start: float | None = None,
    subject: str = "computer_science",
    deadline_seconds: float | None = None,
    budget_started_at: float | None = None,
):
    """The engine-dispatch core, shared by BOTH entry shapes:
      * transcribe_one (single flow) — bytes from the request, upload overlapped;
      * transcription_job_runner (batch, Cloud Tasks) — bytes from GCS,
        upload already done at intake.
    Pure with respect to persistence: returns the built TranscriptionDraft,
    touches no DB and no GCS.

    TWO CLOCKS, and they measure different things — do not merge them:
      * `t_start` is the DURATION clock. It is reset on every entry, so
        `transcription_duration_ms` records the winning pipeline run. Its
        meaning is frozen: it is persisted in every draft ever written and on
        the wire, and redefining it would put old and new rows in quiet
        disagreement (owner ruling, 2026-09-10).
      * `budget_started_at` is the WALL clock, anchored by the job runner at
        its CAS claim. It covers everything the teacher waits through,
        including a discarded attempt and the GCS download. `deadline_seconds`
        is the ceiling on it; None = unbounded = the eval path.
    """
    t_start = t_start if t_start is not None else time.monotonic()

    if settings.transcription_engine == "two_phase":
        # P1 perception + P2 segmentation (+ trust layer when readers are
        # configured — retired in prod, see two_phase_engine). Draft text is
        # the baseline's verbatim output.
        from .transcription.two_phase_engine import (
            build_draft_from_trust_run,
            transcribe_two_phase,
        )
        if not spec_source:
            raise ValueError("Rubric has no draft/contract json to build the exam spec from")
        trust_run, name_suggestion = await transcribe_two_phase(
            pdf_bytes, filename or "upload.pdf", spec_source,
            doc_priority=doc_priority, subject=subject,
            deadline_seconds=deadline_seconds,
            budget_started_at=budget_started_at,
        )
        duration_ms = int((time.monotonic() - t_start) * 1000)
        page_count = len(trust_run.run.pages) or 1
        return build_draft_from_trust_run(
            trust_run, page_count=page_count, duration_ms=duration_ms,
            student_name_suggestion=name_suggestion,
        )

    provider = get_vlm_provider(
        settings.transcription_vlm_provider,
        **({"model": settings.transcription_vlm_model}
           if settings.transcription_vlm_model else {}),
    )
    service = HandwritingTranscriptionService(vlm_provider=provider)

    # VLM transcription — blocking, run in thread pool
    result = await run_in_threadpool(
        service.transcribe_pdf,
        pdf_bytes,
        filename or "upload.pdf",
    )
    duration_ms = int((time.monotonic() - t_start) * 1000)

    # Page count straight from the PDF (non-critical). This used to RENDER the
    # whole document at 72 DPI and take len() of the result — seconds of
    # rasterization for a number the PDF structure already carries.
    try:
        page_count = await run_in_threadpool(pdf_page_count, pdf_bytes)
    except Exception:
        page_count = 1

    # Build draft (with logprob annotation if available)
    return build_transcription_draft(
        result=result,
        page_count=page_count,
        model_version=(
            f"{settings.transcription_vlm_provider}/"
            f"{settings.transcription_vlm_model}"
        ),
        duration_ms=duration_ms,
    )


async def _pipeline_and_persist(
    *,
    pdf_bytes: bytes,
    filename: str | None,
    rubric_id: UUID,
    user_id: UUID,
    batch_id: UUID | None,
    doc_priority: int,
    spec_source: dict | None,
    t_start: float,
    upload_task: "asyncio.Task[None]",
    object_path: str,
    subject: str = "computer_science",
) -> str:
    draft = await run_pipeline_and_build_draft(
        pdf_bytes=pdf_bytes, filename=filename, spec_source=spec_source,
        doc_priority=doc_priority, t_start=t_start, subject=subject,
    )
    duration_ms = draft.transcription_duration_ms

    # Join the GCS upload that has been running since before the pipeline
    # started — on the happy path it finished long ago. Still no DB held.
    # A failed upload is re-attempted ON ITS OWN — never the pipeline.
    await _join_upload_with_retry(upload_task, pdf_bytes, object_path, filename)
    gcs_uri = f"gs://{settings.gcs_bucket_name}/{object_path}"

    # Session 2: fresh checkout just for the INSERT + commit.
    async with get_db_context() as db:
        transcription = Transcription(
            user_id=user_id,
            rubric_id=rubric_id,
            batch_id=batch_id,
            student_id=None,
            student_name=None,
            gcs_uri=gcs_uri,
            gcs_bucket=settings.gcs_bucket_name,
            gcs_object_path=object_path,
            filename=filename,
            draft_json=draft.model_dump(mode="json"),
            contract_json=None,
            status="transcribed",
        )
        db.add(transcription)
        await db.commit()

        logger.info(
            "transcription_created",
            extra={
                "transcription_id": str(transcription.id),
                "batch_id": str(batch_id) if batch_id else None,
                "rubric_id": str(rubric_id),
                "duration_ms": duration_ms,
            },
        )
        return str(transcription.id)
