"""
LIV-1 for transcription jobs — instantiation of the shared LivenessRule.

Arms (each active status claims something different, so each runs its own clock):

  queued  — "Cloud Tasks will deliver me." Clock = created_at. Under batch
            backlog a document legitimately waits behind
            maxConcurrentDispatches, and the queue's maxAttempts=3 redelivery
            (owner-ratified; the CAS claim makes duplicates no-ops) already
            heals dispatch flakes — so this TTL is a generous ABSOLUTE
            BACKSTOP (default 90 min), not extraction's 5-minute window.
  running — "a worker is transcribing me." Clock = updated_at, refreshed by
            the runner's heartbeat sidecar (~60s). Default TTL 5 min: a live
            worker heartbeats 5× inside it, so a lapse is PROVABLY dead.
            PLUS an ABSOLUTE cap on started_at (default 20 min), which the
            worker cannot refresh. The heartbeat proves the PROCESS is alive,
            never that the WORK is progressing or that the request owning it
            still exists — so a coroutine orphaned past its Cloud Run request
            deadline keeps beating and holds the row forever. The cap is the
            only arm that can condemn that row, and it is safe because no
            legitimate run survives it: the document budget is 480s and Cloud
            Run kills the request at 900s.

Expiry reaps to 'failed' with a distinct reason (CHECK-compatible: failed
requires error_message + finished_at), which the per-document retry endpoint
accepts — the work stays recoverable without re-upload.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.transcription_job import TranscriptionJob
from .job_liveness import ActiveArm, LivenessRule

logger = logging.getLogger(__name__)

REASON_NEVER_STARTED = (
    "orphaned: the document was never picked up for transcription "
    "(dispatch lost after queue retries)"
)
REASON_WORKER_DIED = "orphaned: transcription worker died mid-document (heartbeat lapsed)"
REASON_OVERRAN = (
    "the document exceeded the maximum time a transcription may run; "
    "it was stopped and can be retried without re-uploading"
)


def dispatch_ttl() -> timedelta:
    return timedelta(minutes=settings.transcription_job_dispatch_ttl_minutes)


def heartbeat_ttl() -> timedelta:
    return timedelta(minutes=settings.transcription_job_heartbeat_ttl_minutes)


def absolute_ttl() -> timedelta:
    return timedelta(minutes=settings.transcription_job_absolute_ttl_minutes)


_RULE = LivenessRule(
    model=TranscriptionJob,
    arms=(
        ActiveArm("queued", "created_at", dispatch_ttl, REASON_NEVER_STARTED),
        ActiveArm("running", "updated_at", heartbeat_ttl, REASON_WORKER_DIED,
                  absolute_clock_attr="started_at",
                  absolute_ttl=absolute_ttl,
                  absolute_reason=REASON_OVERRAN),
    ),
    failed_values=lambda reason, now: dict(
        status="failed", error_message=reason, finished_at=now, updated_at=now
    ),
    log_label="transcription_jobs",
)


def expired_condition(now: Optional[datetime] = None):
    return _RULE.expired_condition(now)


def is_expired(job: TranscriptionJob, now: Optional[datetime] = None) -> bool:
    return _RULE.is_expired(job, now)


def expiry_reason(job: TranscriptionJob, now: Optional[datetime] = None) -> str:
    return _RULE.expiry_reason(job, now)


async def reap_expired(
    db: AsyncSession,
    *,
    batch_id: Optional[UUID] = None,
    job_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    commit: bool = False,
) -> int:
    """Expire active-but-past-deadline jobs in scope (batch reads are the
    main door: get_batch reaps before building the rollup, so expiry is
    terminal on read exactly like extraction). user_id scopes the list-page
    bulk pass (B10 — one reap for all of a teacher's batches, no per-batch
    loop; mirrors the extraction wrapper's precedent)."""
    extra = []
    if batch_id is not None:
        extra.append(TranscriptionJob.batch_id == batch_id)
    if job_id is not None:
        extra.append(TranscriptionJob.id == job_id)
    if user_id is not None:
        extra.append(TranscriptionJob.user_id == user_id)
    return await _RULE.reap(db, *extra, commit=commit)


async def sweep_on_startup() -> int:
    return await _RULE.sweep_on_startup()
