"""
Cloud Tasks integration — the execution substrate, one concept in one place.

Born for the async rubric-extraction lifecycle (PR-1, ADR-1); generalized for
the Cloud Tasks migration (batch transcription jobs + grading). The substrate
decision is unchanged: a task is an authenticated HTTP POST back to our own
service (/internal/...jobs/{id}/run); the work runs INSIDE that request, so
CPU is guaranteed for its full duration. FastAPI BackgroundTasks are
disqualified under the prod Cloud Run config (CPU throttled post-response,
min-instances 0).

Per JOB KIND (extraction / transcription / grading), declared as a JobKind:
  * enqueue — dispatch per the kind's execution mode:
      "cloud_tasks" — create an HTTP task with an OIDC token (prod).
      "inline"      — asyncio.create_task of the kind's runner (LOCAL DEV
        ONLY; see config.py for why this is unsafe under prod Cloud Run).
  * queue — kinds get SEPARATE queues so rate/concurrency tune independently.

Redelivery policy differs BY DESIGN (owner-ratified 2026-08-13):
  * extraction queue: maxAttempts=1 — retry story is heartbeat-staleness +
    the explicit retry endpoint (ADR-1).
  * transcription/grading queues: maxAttempts=3 — the DB CAS claim makes a
    duplicate delivery a provable no-op, and redelivery is the only mechanism
    that heals DISPATCH-level failures (cold-start 503, instance death before
    the claim) under batch backlog, where a short queued-TTL cannot work.
    Mid-run deaths remain owned by heartbeat-TTL + explicit retry.

verify_task_request authenticates an incoming /internal call for ALL kinds:
OIDC token (audience = service URL, issuer accounts.google.com, email = the
task-invoker SA), with an X-Internal-Token shared-secret fallback for
inline/dev mode.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from uuid import UUID

from fastapi import Request

from ..config import settings

logger = logging.getLogger(__name__)

# Dispatch deadline for every kind: matches the raised Cloud Run
# timeoutSeconds (900). A task outliving it loses its CPU and is recovered by
# heartbeat-staleness, never by silently running headless.
_DISPATCH_DEADLINE_SECONDS = 900


class TaskEnqueueError(Exception):
    """Raised when a job could not be handed to its execution substrate."""


@dataclass(frozen=True)
class JobKind:
    """One background-work type: where its task POSTs, which queue carries it,
    which mode knob governs it, and what runs inline in dev mode."""
    label: str                                   # log prefix, e.g. "extraction_task"
    internal_path: str                           # "/internal/...-jobs/{job_id}/run"
    queue: Callable[[], str]                     # callable → live settings reads
    execution_mode: Callable[[], str]
    # Lazy import (avoids cycles: runner ← this module ← endpoints).
    inline_runner: Callable[[], Callable[[UUID], Awaitable]]


def jobs_execution_mode() -> str:
    """Mode for the NEW job kinds (transcription/grading). Defaults to the
    extraction knob so existing environments need ZERO new configuration:
    dev .env files already carry EXTRACTION_EXECUTION_MODE=inline, prod
    carries cloud_tasks. JOBS_EXECUTION_MODE overrides when set."""
    return settings.jobs_execution_mode or settings.extraction_execution_mode


def _run_url(kind: JobKind, job_id: UUID) -> str:
    base = (settings.service_base_url or "").rstrip("/")
    if not base:
        raise TaskEnqueueError(
            "service_base_url is not configured — required for cloud_tasks mode"
        )
    return base + kind.internal_path.format(job_id=job_id)


def _enqueue_cloud_task(kind: JobKind, job_id: UUID) -> None:
    """Create the Cloud Tasks HTTP task (prod path). Import is local so the
    package is only required where the mode is actually used."""
    from google.cloud import tasks_v2
    from google.protobuf import duration_pb2

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        settings.google_cloud_project,
        settings.cloud_tasks_location,
        kind.queue(),
    )
    task: dict = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": _run_url(kind, job_id),
        },
        "dispatch_deadline": duration_pb2.Duration(seconds=_DISPATCH_DEADLINE_SECONDS),
    }
    if settings.cloud_tasks_invoker_sa:
        task["http_request"]["oidc_token"] = {
            "service_account_email": settings.cloud_tasks_invoker_sa,
            "audience": (settings.service_base_url or "").rstrip("/"),
        }
    client.create_task(request={"parent": parent, "task": task})
    logger.info("%s_enqueued", kind.label, extra={"job_id": str(job_id)})


async def enqueue_job(kind: JobKind, job_id: UUID) -> None:
    """Hand a queued job to the execution substrate. Call AFTER the job row is
    committed — the task handler loads it by id in its own session."""
    mode = kind.execution_mode()
    if mode == "inline":
        # LOCAL DEV ONLY (see config.py).
        runner = kind.inline_runner()
        asyncio.create_task(runner(job_id))
        logger.info("%s_inline", kind.label, extra={"job_id": str(job_id)})
        return
    if mode == "cloud_tasks":
        # The tasks client is sync; keep the event loop free.
        await asyncio.to_thread(_enqueue_cloud_task, kind, job_id)
        return
    raise TaskEnqueueError(f"Unknown execution mode: {mode!r}")


# =============================================================================
# Kinds
# =============================================================================

def _extraction_runner():
    from .rubric_extraction_runner import run_extraction_job
    return run_extraction_job


EXTRACTION_KIND = JobKind(
    label="extraction_task",
    internal_path="/internal/extraction-jobs/{job_id}/run",
    queue=lambda: settings.cloud_tasks_queue,
    execution_mode=lambda: settings.extraction_execution_mode,
    inline_runner=_extraction_runner,
)


def _transcription_runner():
    from .transcription_job_runner import run_transcription_job
    return run_transcription_job


TRANSCRIPTION_KIND = JobKind(
    label="transcription_task",
    internal_path="/internal/transcription-jobs/{job_id}/run",
    queue=lambda: settings.cloud_tasks_transcription_queue,
    execution_mode=jobs_execution_mode,
    inline_runner=_transcription_runner,
)


def _grading_runner():
    from .grading_runner import run_grading
    return run_grading


GRADING_KIND = JobKind(
    label="grading_task",
    internal_path="/internal/grading-jobs/{job_id}/run",
    queue=lambda: settings.cloud_tasks_grading_queue,
    execution_mode=jobs_execution_mode,
    inline_runner=_grading_runner,
)


async def enqueue_extraction_task(job_id: UUID) -> None:
    await enqueue_job(EXTRACTION_KIND, job_id)


async def enqueue_transcription_task(job_id: UUID) -> None:
    await enqueue_job(TRANSCRIPTION_KIND, job_id)


async def enqueue_grading_task(graded_test_id: UUID) -> None:
    await enqueue_job(GRADING_KIND, graded_test_id)


async def enqueue_grading_task_or_log(graded_test_id: UUID) -> None:
    """Best-effort enqueue for an already-committed pending graded_test row
    (shared by all five grading kickoff sites). An enqueue failure needs no
    row write: the pending row is durable, and grading_job_liveness's
    dispatch backstop reaps it to 'failed' → the revision-retry chain."""
    try:
        await enqueue_grading_task(graded_test_id)
    except Exception:
        logger.exception("grading_enqueue_failed",
                         extra={"graded_test_id": str(graded_test_id)})


# =============================================================================
# Incoming /internal auth (all kinds)
# =============================================================================

def verify_task_request(request: Request) -> Optional[str]:
    """Authenticate an incoming /internal/...-jobs/{id}/run call.

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
