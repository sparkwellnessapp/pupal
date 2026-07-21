"""
API schemas for the async rubric-extraction job lifecycle (PR-1).

These are transport shapes only. The extraction result itself is an
ExtractRubricResponse (ontology_types.py — the single source of truth);
JobResultResponse carries its model_dump as an opaque dict so this module
never forks rubric types.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class SubmitJobResponse(BaseModel):
    job_id: UUID
    status: str                      # 'queued'
    reused: bool                     # True = ADR-3 conflict returned the existing active job


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str                      # queued | extracting | completed | failed
    progress_stage: Optional[str] = None
    progress_detail: Optional[str] = None
    # Computed, never stored: extracting AND heartbeat older than TTL —
    # signals an instance died mid-job; the retry endpoint accepts these rows.
    stale: bool = False
    error_message: Optional[str] = None
    has_result: bool = False
    source_filename: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None


class JobProvenance(BaseModel):
    prompt_version: Optional[str] = None
    pipeline_version: Optional[str] = None
    llm_model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    retry_count: Optional[int] = None
    finish_reason: Optional[str] = None
    duration_ms: Optional[int] = None
    llm_config: Optional[Dict[str, Any]] = None


class JobResultResponse(BaseModel):
    job_id: UUID
    result: Dict[str, Any]           # ExtractRubricResponse.model_dump(mode="json")
    warnings: List[str]
    errors: List[str]
    requires_review: Optional[bool] = None
    provenance: JobProvenance


class RetryJobResponse(BaseModel):
    job_id: UUID
    status: str                      # 'queued'


class PatchJobMetadataRequest(BaseModel):
    """Metadata patch for a rubric-extraction job (PR-5 S1-2.2).

    METADATA-ONLY: the runner never reads these keys — this endpoint only
    persists them into request_params for later save/resume. Both fields are
    OPTIONAL and 'omitted' is distinct from 'explicit null': only the keys the
    caller actually sent are merged (build the patch via model_dump(
    exclude_unset=True)), so an omitted field leaves the stored value untouched
    while an explicit null overwrites it with JSON null.
    """
    name: Optional[str] = None
    programming_language: Optional[str] = None


class PatchJobMetadataResponse(BaseModel):
    job_id: UUID
    status: str                      # queued | extracting | completed
    request_params: Dict[str, Any]   # post-merge, echoed so the caller can confirm
