"""
Step 0 of a capture-sourced transcription job — compile the PDF (ruling OD-1).

Capture save inserts the frozen version AND a `transcription_jobs` row in one
commit; the job's object path is the version's deterministic PDF path
(`capture/paths.pdf_path`). When the runner claims such a job and the PDF is
not there yet, this compiles it — from the RAW photos and the frozen snapshot
only (SCN-2, SCN-11) — and the unchanged pipeline then reads it like any
uploaded scan. The PDF is the boundary (OD-S9).

Idempotent by construction (SCN-4): the path is a function of the version id,
so a redelivered or retried job finds the object and skips, and a compile that
dies half-way leaves nothing (scan-service writes the PDF in one upload after
every page rendered). A refusal (a raw photo missing, a pipeline version the
service did not produce) raises `CaptureCompileFailed`, which the runner lands
as a FAILED, retryable job — never a partial PDF.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional
from uuid import UUID

from ...config import settings
from ...database import get_db_context
from ...models.capture import CaptureVersion
from .paths import gs_uri
from .scan_client import ScanServiceError, compile_with_retry, get_scan_client

logger = logging.getLogger(__name__)


class CaptureCompileFailed(Exception):
    """The PDF could not be built. Terminal for this run, retryable by her."""


async def ensure_capture_pdf(*, job_id: UUID, capture_version_id: UUID, object_path: str,
                             deadline_s: Optional[float]) -> None:
    from ..gcs_service import get_gcs_service

    gcs = get_gcs_service()
    if (await asyncio.to_thread(gcs.object_size, object_path)) is not None:
        return                                    # compiled already (SCN-4)

    async with get_db_context() as db:
        version: Optional[CaptureVersion] = await db.get(CaptureVersion, capture_version_id)
        if version is None:
            raise CaptureCompileFailed(f"capture version {capture_version_id} not found")
        snapshot = list(version.pages_snapshot)
        pipeline_version = version.scan_pipeline_version

    started = time.monotonic()
    try:
        result = await compile_with_retry(
            get_scan_client(), snapshot, pipeline_version,
            gs_uri(settings.gcs_bucket_name, object_path), deadline_s=deadline_s)
    except ScanServiceError as exc:
        logger.warning("capture_compile_failed job_id=%s version_id=%s code=%s ms=%d",
                       job_id, capture_version_id, exc.code,
                       int((time.monotonic() - started) * 1000))
        raise CaptureCompileFailed(f"scan-service: {exc.code}") from None
    # The numbers are in the MESSAGE: `extra` renders nowhere in this service.
    logger.info("capture_compiled job_id=%s version_id=%s pages=%d bytes=%d compile_ms=%d",
                job_id, capture_version_id, result.page_count, result.bytes,
                int((time.monotonic() - started) * 1000))
