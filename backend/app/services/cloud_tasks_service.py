"""
Cloud Tasks integration for the async rubric-extraction lifecycle (PR-1, ADR-1).

Substrate decision: the task is an authenticated HTTP POST back to our own
service (/internal/extraction-jobs/{id}/run); extraction runs INSIDE that
request, so CPU is guaranteed for its full duration. FastAPI BackgroundTasks
are disqualified under the prod Cloud Run config (CPU throttled post-response,
min-instances 0).

Two responsibilities, both here so the substrate is one concept in one place:
  * enqueue_extraction_task(job_id) — dispatch per settings.extraction_execution_mode:
      "cloud_tasks" — create an HTTP task with an OIDC token (prod).
        maxAttempts=1 on the queue: our retry story is heartbeat-staleness +
        the explicit retry endpoint, never blind redelivery of a possibly
        half-run job.
      "inline"      — asyncio.create_task of the runner (LOCAL DEV ONLY; see
        config.py docstring for why this is unsafe under prod Cloud Run).
  * verify_task_request(request) — authenticate an incoming /internal call:
      OIDC token (audience = service URL, issuer accounts.google.com, email =
      the task-invoker SA), with an X-Internal-Token shared-secret fallback
      for inline/dev mode. Returns None if authorized, else a rejection reason.
"""
import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import Request

from ..config import settings

logger = logging.getLogger(__name__)

_INTERNAL_RUN_PATH = "/internal/extraction-jobs/{job_id}/run"
# Cloud Tasks dispatchDeadline for the extraction request. Must cover the
# worst-case extraction; matches the raised Cloud Run timeoutSeconds (900).
_DISPATCH_DEADLINE_SECONDS = 900


class TaskEnqueueError(Exception):
    """Raised when a job could not be handed to its execution substrate."""


def _run_url(job_id: UUID) -> str:
    base = (settings.service_base_url or "").rstrip("/")
    if not base:
        raise TaskEnqueueError(
            "service_base_url is not configured — required for cloud_tasks mode"
        )
    return base + _INTERNAL_RUN_PATH.format(job_id=job_id)


def _enqueue_cloud_task(job_id: UUID) -> None:
    """Create the Cloud Tasks HTTP task (prod path). Import is local so the
    package is only required where the mode is actually used."""
    from google.cloud import tasks_v2
    from google.protobuf import duration_pb2

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        settings.google_cloud_project,
        settings.cloud_tasks_location,
        settings.cloud_tasks_queue,
    )
    task: dict = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": _run_url(job_id),
        },
        "dispatch_deadline": duration_pb2.Duration(seconds=_DISPATCH_DEADLINE_SECONDS),
    }
    if settings.cloud_tasks_invoker_sa:
        task["http_request"]["oidc_token"] = {
            "service_account_email": settings.cloud_tasks_invoker_sa,
            "audience": (settings.service_base_url or "").rstrip("/"),
        }
    client.create_task(request={"parent": parent, "task": task})
    logger.info("extraction_task_enqueued", extra={"job_id": str(job_id)})


async def enqueue_extraction_task(job_id: UUID) -> None:
    """Hand a queued job to the execution substrate. Call AFTER the job row is
    committed — the task handler loads it by id in its own session."""
    mode = settings.extraction_execution_mode
    if mode == "inline":
        # LOCAL DEV ONLY (see config.py). Import here to avoid a cycle:
        # runner → (nothing from here), endpoints → both.
        from .rubric_extraction_runner import run_extraction_job

        asyncio.create_task(run_extraction_job(job_id))
        logger.info("extraction_task_inline", extra={"job_id": str(job_id)})
        return
    if mode == "cloud_tasks":
        # The tasks client is sync; keep the event loop free.
        await asyncio.to_thread(_enqueue_cloud_task, job_id)
        return
    raise TaskEnqueueError(f"Unknown extraction_execution_mode: {mode!r}")


def verify_task_request(request: Request) -> Optional[str]:
    """Authenticate an incoming /internal/extraction-jobs/{id}/run call.

    Returns None when authorized; otherwise a short rejection reason (the
    endpoint responds 403 without detail leakage — reasons go to logs only).

    Order: shared-secret header first (constant-time compare; the inline/dev
    channel), then OIDC bearer verification (the Cloud Tasks channel).
    """
    import hmac

    # 1. Shared-secret fallback (inline/dev)
    provided = request.headers.get("X-Internal-Token")
    if provided is not None and settings.internal_task_token:
        if hmac.compare_digest(provided, settings.internal_task_token):
            return None
        return "bad shared secret"

    # 2. OIDC bearer (Cloud Tasks → this service)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "missing bearer token"
    token = auth[len("Bearer "):]
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        audience = (settings.service_base_url or "").rstrip("/")
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=audience or None
        )
    except Exception as e:
        return f"oidc verification failed: {type(e).__name__}"

    if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        return "unexpected issuer"
    if settings.cloud_tasks_invoker_sa and claims.get("email") != settings.cloud_tasks_invoker_sa:
        return "unexpected caller identity"
    return None
