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
import logging
import time
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..database import get_db_context
from ..models.grading import Rubric
from ..models.transcription import Transcription
from ..services.document_parser import pdf_to_images
from ..services.gcs_service import get_gcs_service
from ..services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
)
from ..services.transcription_adapter import build_transcription_draft

logger = logging.getLogger(__name__)


async def transcribe_one(
    pdf_bytes: bytes,
    filename: str | None,
    rubric_id: UUID,
    user_id: UUID,
    batch_id: UUID | None = None,
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
    """
    async with get_db_context() as db:
        rubric: Rubric | None = await db.get(Rubric, rubric_id)
        if rubric is None:
            raise ValueError(f"Rubric {rubric_id} not found")

        t_start = time.monotonic()
        if settings.transcription_engine == "two_phase":
            # P1 perception + P2 segmentation + cross-reader trust layer.
            # Draft text is the baseline's verbatim output; readers contribute
            # only annotations (reader_disagreement / code_lint) + provenance.
            from .transcription.two_phase_engine import (
                build_draft_from_trust_run,
                transcribe_two_phase,
            )
            spec_source = rubric.draft_json or rubric.contract_json
            if not spec_source:
                raise ValueError(f"Rubric {rubric_id} has no draft/contract json")
            trust_run = await transcribe_two_phase(
                pdf_bytes, filename or "upload.pdf", spec_source
            )
            duration_ms = int((time.monotonic() - t_start) * 1000)
            page_count = len(trust_run.run.pages) or 1
            draft = build_draft_from_trust_run(
                trust_run, page_count=page_count, duration_ms=duration_ms
            )
        else:
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

            # Page count at low DPI (non-critical)
            try:
                page_count = len(await run_in_threadpool(pdf_to_images, pdf_bytes, 72))
            except Exception:
                page_count = 1

            # Build draft (with logprob annotation if available)
            draft = build_transcription_draft(
                result=result,
                page_count=page_count,
                model_version=(
                    f"{settings.transcription_vlm_provider}/"
                    f"{settings.transcription_vlm_model}"
                ),
                duration_ms=duration_ms,
            )

        # GCS upload
        gcs = get_gcs_service()
        obj_id = str(uuid4())
        object_path = f"transcriptions/{user_id}/{obj_id}.pdf"
        await run_in_threadpool(
            gcs.upload_bytes, pdf_bytes, object_path, "application/pdf"
        )
        gcs_uri = f"gs://{settings.gcs_bucket_name}/{object_path}"

        # Persist
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
