"""
Async rubric-extraction job endpoints (PR-1).

Public router: submit / status / result / retry / list — the durable
replacement for the synchronous POST /grading/extract_rubric_docx flow
(which remains, deprecated, until the frontend is fully cut over).

Internal router: the Cloud Tasks target. Extraction runs INSIDE that request
(ADR-1) so CPU is guaranteed for its full duration.

ROUTING NOTE (load-bearing): this public router's prefix nests under
/api/v0/rubrics, which rubric_management.py also serves with a catch-all
GET /{rubric_id}. Starlette matches first-registered-wins and does NOT fall
through after a UUID-parse 422 — main.py MUST register this router BEFORE
rubric_management's. See the comment at the registration site.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import cast, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_owned_or_404
from ...config import settings
from ...database import get_db
from ...models.rubric_extraction_job import ACTIVE_JOB_STATUSES, RubricExtractionJob
from ...models.user import User
from ...schemas.rubric_extraction_jobs import (
    JobProvenance,
    JobResultResponse,
    JobStatusResponse,
    PatchJobMetadataRequest,
    PatchJobMetadataResponse,
    RetryJobResponse,
    SubmitJobResponse,
)
from ...services.cloud_tasks_service import enqueue_extraction_task, verify_task_request
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/rubrics/extraction-jobs", tags=["rubric-extraction-jobs"])
internal_router = APIRouter(prefix="/internal/extraction-jobs", tags=["internal"])

_DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a ZIP container
_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _heartbeat_ttl() -> timedelta:
    return timedelta(minutes=settings.extraction_heartbeat_ttl_minutes)


def _is_stale(job: RubricExtractionJob, now: datetime) -> bool:
    """Computed, never stored: an 'extracting' row whose heartbeat lapsed —
    the instance died mid-job. Retry accepts these rows."""
    if job.status != "extracting" or job.updated_at is None:
        return False
    updated = job.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (now - updated) > _heartbeat_ttl()


def _status_response(job: RubricExtractionJob) -> JobStatusResponse:
    now = datetime.now(timezone.utc)
    elapsed: Optional[float] = None
    if job.status == "extracting" and job.started_at is not None:
        started = job.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = round((now - started).total_seconds(), 1)
    elif job.duration_ms is not None:
        elapsed = round(job.duration_ms / 1000, 1)
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_stage=job.progress_stage,
        progress_detail=job.progress_detail,
        stale=_is_stale(job, now),
        error_message=job.error_message,
        has_result=job.result_json is not None,
        source_filename=job.source_filename,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        elapsed_seconds=elapsed,
    )


async def _enqueue_or_fail(db: AsyncSession, job_id: UUID) -> None:
    """Hand the committed job to the substrate. If enqueue itself fails, the
    row must not rot as unreachable-'queued' — mark it failed so the client
    sees a durable, retryable state (retry re-enqueues)."""
    try:
        await enqueue_extraction_task(job_id)
    except Exception as e:
        logger.exception("extraction_enqueue_failed", extra={"job_id": str(job_id)})
        now = datetime.now(timezone.utc)
        await db.execute(
            update(RubricExtractionJob)
            .where(RubricExtractionJob.id == job_id,
                   RubricExtractionJob.status == "queued")
            .values(status="failed",
                    error_message=f"enqueue failed: {type(e).__name__}: {str(e)[:300]}",
                    finished_at=now, updated_at=now)
        )
        await db.commit()


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@router.post("/", response_model=SubmitJobResponse, status_code=202)
async def submit_extraction_job(
    file: UploadFile = File(..., description="Rubric DOCX file"),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    subject: str = Form("computer_science"),
    locale: str = Form("he-IL"),
    test_topic: Optional[str] = Form(None),
    # Stored in request_params for forward-compat; NOT passed to the pipeline
    # (preserves today's behavior — the sync endpoint ignores it too).
    question_purposes: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmitJobResponse:
    filename = file.filename or "rubric.docx"
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a DOCX document.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if not file_bytes.startswith(_DOCX_MAGIC):
        raise HTTPException(status_code=400, detail="File is not a valid DOCX document.")
    max_bytes = settings.extraction_max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {settings.extraction_max_upload_mb}MB).",
        )

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    # Capture BEFORE any rollback: current_user is attached to this request's
    # session; rollback() expires it and expunge_all() detaches it, after
    # which current_user.id raises DetachedInstanceError.
    user_id = current_user.id

    # Content-addressed source persistence: same file ⇒ same object; re-uploads
    # are overwrite-idempotent. This is the durability §C9 lacked — retry and
    # future re-extraction never need the teacher to re-upload.
    import asyncio

    from ...services.gcs_service import get_gcs_service

    gcs = get_gcs_service()
    object_path = f"rubric-sources/{user_id}/{sha256}.docx"
    await asyncio.to_thread(gcs.upload_bytes, file_bytes, object_path, _DOCX_CONTENT_TYPE)

    job = RubricExtractionJob(
        user_id=user_id,
        status="queued",
        source_gcs_uri=f"gs://{gcs.bucket_name}/{object_path}",
        source_filename=filename,
        source_sha256=sha256,
        request_params={
            "name": name,
            "description": description,
            "subject": subject,
            "locale": locale,
            "test_topic": test_topic,
            "question_purposes": question_purposes,
        },
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        # ADR-3: the partial unique (user_id, source_sha256) WHERE active fired.
        # Submit is idempotent — return the existing active job, don't 409.
        await db.rollback()
        # Drop the failed pending INSERT from the session — otherwise the
        # SELECT below autoflushes it, replaying the very IntegrityError we
        # just handled.
        db.expunge_all()
        result = await db.execute(
            select(RubricExtractionJob).where(
                RubricExtractionJob.user_id == user_id,
                RubricExtractionJob.source_sha256 == sha256,
                RubricExtractionJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:  # raced: the active job finished between conflict and select
            raise HTTPException(
                status_code=409,
                detail="המסמך כבר בעיבוד — נסי שוב בעוד רגע",
            )
        return SubmitJobResponse(job_id=existing.id, status=existing.status, reused=True)

    await db.refresh(job)
    await _enqueue_or_fail(db, job.id)
    # NB: 'filename' is a reserved LogRecord attribute — never use it as an
    # extra key (it raises KeyError inside logging and 500s the request).
    logger.info("extraction_job_submitted",
                extra={"job_id": str(job.id), "source_filename": filename})
    return SubmitJobResponse(job_id=job.id, status="queued", reused=False)


@router.get("/", response_model=List[JobStatusResponse])
async def list_extraction_jobs(
    active: bool = Query(False, description="Only queued/extracting jobs (resume surface)"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[JobStatusResponse]:
    stmt = select(RubricExtractionJob).where(RubricExtractionJob.user_id == current_user.id)
    if active:
        stmt = stmt.where(RubricExtractionJob.status.in_(ACTIVE_JOB_STATUSES))
    stmt = stmt.order_by(RubricExtractionJob.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_status_response(j) for j in result.scalars().all()]


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_extraction_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobStatusResponse:
    job = await get_owned_or_404(db, RubricExtractionJob, job_id, current_user.id)
    return _status_response(job)


# Metadata patch is legal for every non-terminal-failure status. A 'failed'
# job has nothing to name (PR-5 S1-2.2); 'completed' is patchable because the
# teacher names/labels the result on the review screen after extraction.
_PATCHABLE_STATUSES = ("queued", "extracting", "completed")


@router.patch("/{job_id}", response_model=PatchJobMetadataResponse)
async def patch_extraction_job_metadata(
    job_id: UUID,
    payload: PatchJobMetadataRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatchJobMetadataResponse:
    """Merge caller-supplied metadata (name / programming_language) into the
    job's request_params. METADATA-ONLY — the runner never reads these keys;
    this only persists them for later save/resume.

    The merge is a DB-level shallow concat (`request_params || :patch`), NOT a
    read-modify-write in Python: the runner writes progress_stage/heartbeat/
    result to the SAME row concurrently, so a full-row ORM save here would
    clobber its progress. Only the keys the caller actually sent are merged
    (exclude_unset), so an omitted field is untouched while an explicit null
    overwrites with JSON null."""
    job = await get_owned_or_404(db, RubricExtractionJob, job_id, current_user.id)
    if job.status == "failed":
        raise HTTPException(status_code=409, detail="לא ניתן לעדכן פרטים של הרצה שנכשלה")

    # Distinguish 'omitted' from 'explicit null': merge ONLY sent keys.
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        # Nothing to merge — idempotent no-op; echo the current state.
        return PatchJobMetadataResponse(
            job_id=job.id, status=job.status, request_params=job.request_params or {}
        )

    now = datetime.now(timezone.utc)
    # Atomic, column-targeted JSONB merge with the status guard folded into the
    # WHERE (closes the read→write race where the runner fails the job between
    # the ownership load above and this UPDATE). RETURNING gives the post-merge
    # values in one round-trip; the ORM-loaded `job` is now stale and unused.
    result = await db.execute(
        update(RubricExtractionJob)
        .where(
            RubricExtractionJob.id == job_id,
            RubricExtractionJob.user_id == current_user.id,
            RubricExtractionJob.status.in_(_PATCHABLE_STATUSES),
        )
        .values(
            request_params=RubricExtractionJob.request_params.op("||")(
                cast(patch, JSONB)
            ),
            updated_at=now,
        )
        .returning(RubricExtractionJob.status, RubricExtractionJob.request_params)
    )
    row = result.first()
    if row is None:
        # Raced: status flipped out of the patchable set (→ failed) after the
        # ownership load. Ownership was already proven, so this is not a 404.
        await db.rollback()
        raise HTTPException(status_code=409, detail="לא ניתן לעדכן פרטים של הרצה שנכשלה")
    await db.commit()
    logger.info("extraction_job_metadata_patched",
                extra={"job_id": str(job_id), "patched_keys": sorted(patch.keys())})
    return PatchJobMetadataResponse(
        job_id=job_id, status=row.status, request_params=row.request_params
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_extraction_job_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResultResponse:
    job = await get_owned_or_404(db, RubricExtractionJob, job_id, current_user.id)
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="החילוץ עדיין לא הושלם")
    return JobResultResponse(
        job_id=job.id,
        result=job.result_json,
        warnings=list(job.warnings or []),
        errors=list(job.errors or []),
        requires_review=job.requires_review,
        provenance=JobProvenance(
            prompt_version=job.prompt_version,
            pipeline_version=job.pipeline_version,
            llm_model=job.llm_model,
            input_tokens=job.input_tokens,
            output_tokens=job.output_tokens,
            retry_count=job.retry_count,
            finish_reason=job.finish_reason,
            duration_ms=job.duration_ms,
            llm_config=job.llm_config,
        ),
    )


@router.post("/{job_id}/retry", response_model=RetryJobResponse)
async def retry_extraction_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetryJobResponse:
    """Re-queue a failed job, or a stale 'extracting' one (heartbeat lapsed —
    the instance died mid-job). Source doc is in GCS: no re-upload."""
    await get_owned_or_404(db, RubricExtractionJob, job_id, current_user.id)

    now = datetime.now(timezone.utc)
    stale_cutoff = now - _heartbeat_ttl()
    # Atomic CAS — the WHERE encodes exactly the two legal retry sources; the
    # full reset satisfies the 'queued' arm of the status-consistency CHECK.
    result = await db.execute(
        update(RubricExtractionJob)
        .where(
            RubricExtractionJob.id == job_id,
            RubricExtractionJob.user_id == current_user.id,
            (
                (RubricExtractionJob.status == "failed")
                | (
                    (RubricExtractionJob.status == "extracting")
                    & (RubricExtractionJob.updated_at < stale_cutoff)
                )
            ),
        )
        .values(status="queued", error_message=None, started_at=None,
                finished_at=None, progress_stage=None, progress_detail=None,
                updated_at=now)
    )
    if result.rowcount == 0:
        await db.rollback()
        raise HTTPException(status_code=409, detail="ההרצה עדיין פעילה או שהמשימה כבר הושלמה")
    await db.commit()

    await _enqueue_or_fail(db, job_id)
    logger.info("extraction_job_retried", extra={"job_id": str(job_id)})
    return RetryJobResponse(job_id=job_id, status="queued")


# =============================================================================
# INTERNAL: Cloud Tasks target (ADR-1) — NOT behind get_current_user
# =============================================================================

@internal_router.post("/{job_id}/run", include_in_schema=False)
async def run_extraction_job_task(job_id: UUID, request: Request) -> dict:
    """Executes the extraction INSIDE this request (CPU guaranteed for its
    duration). Idempotent: the runner's first statement is the queued→extracting
    CAS; a duplicate delivery or already-terminal row is a 200 no-op.
    Always 200 on auth success — Cloud Tasks maxAttempts=1; our retry story is
    heartbeat-staleness + the explicit retry endpoint, never blind redelivery."""
    reason = verify_task_request(request)
    if reason is not None:
        logger.warning("internal_run_rejected",
                       extra={"job_id": str(job_id), "reason": reason})
        raise HTTPException(status_code=403, detail="Forbidden")

    from ...services.rubric_extraction_runner import run_extraction_job

    ran = await run_extraction_job(job_id)
    return {"job_id": str(job_id), "ran": ran}
