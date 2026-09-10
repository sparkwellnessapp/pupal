"""
LIV-1 — LIVENESS FOR EXTRACTION JOBS.

THE RULE: an ACTIVE status is a CLAIM that work is in progress. Every claim must
be backed by a liveness signal with a DEADLINE, or it expires. A row that cannot
be falsified is a row that traps the teacher forever.

Each active status carries its own deadline, because they claim different things:

  queued     — "a dispatch is about to happen." Its clock starts at `created_at`
               and it has NO heartbeat: nothing about the row changes while it
               waits, so `updated_at` is useless here. Deadline =
               EXTRACTION_DISPATCH_TTL_MINUTES.
  extracting — "a worker is running me." Its clock is the heartbeat (`updated_at`),
               refreshed by the runner. Deadline =
               EXTRACTION_HEARTBEAT_TTL_MINUTES. A gap beyond the TTL is PROVABLY
               dead, not slow: the extraction wall deadline (840s ≈ 14 min) is
               below the TTL, so a live job always heartbeats inside it.

HISTORY — why one rule, one place. Staleness was once spelled out three times as
`status == 'extracting' AND updated_at < cutoff`, so a job that died BEFORE
starting (stuck 'queued', never heartbeat) was unreapable and unretryable and
re-attached the resume surface forever. Three copies of a special case is how a
second shape of the same bug walked through. The rule then lived here once; with
the Cloud Tasks migration (transcription jobs + grading need the same rule over
their own tables) the CORE moved to `job_liveness.LivenessRule` — this module is
the extraction INSTANTIATION and keeps its public API stable (the LIV-1
regression suite imports these exact names).

Expiry is recorded as `failed` with a distinct `error_message`: the CHECK
constraint already admits failed + error_message + finished_at, `/retry` accepts
failed leaves so the work stays recoverable, and the reason stays diagnosable
without a migration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.rubric_extraction_job import RubricExtractionJob
from .job_liveness import ActiveArm, LivenessRule

logger = logging.getLogger(__name__)

# The reason recorded on each expiry class — the teacher-facing string doubles as
# the diagnostic, so "why did this die" never needs a log dive.
REASON_NEVER_DISPATCHED = (
    "orphaned: the job was never picked up for processing "
    "(dispatch lost — server restart or queue failure)"
)
REASON_HEARTBEAT_LAPSED = "orphaned: extraction worker died mid-job (heartbeat lapsed)"
REASON_ABANDONED = "abandoned by the teacher"


def dispatch_ttl() -> timedelta:
    return timedelta(minutes=settings.extraction_dispatch_ttl_minutes)


def heartbeat_ttl() -> timedelta:
    return timedelta(minutes=settings.extraction_heartbeat_ttl_minutes)


# ---------------------------------------------------------------------------
# DEFERRED (owner-ruled 2026-09-10, scope: transcription only this PR).
#
# This rule's heartbeat arm has the SAME hole `transcription_job_liveness`
# just closed: `extracting.updated_at` is refreshed by the worker's own heartbeat, so a
# coroutine orphaned past its Cloud Run request deadline — still scheduled,
# still beating, no longer able to land anything — holds its row ACTIVE
# forever and no reader can falsify it. `ActiveArm` now supports the fix
# (`absolute_clock_attr` / `absolute_ttl` / `absolute_reason`: a cap on a
# column the worker never touches), and instantiating it here is a two-line
# change plus its TTL setting.
#
# It was NOT done here because the incident that produced the mechanism was a
# transcription one, and shipping the other domains unmeasured would be
# choosing a cap by analogy. AWAITS IMPLEMENTATION — do not read the presence
# of the mechanism in job_liveness.py as evidence that this domain uses it.
# ---------------------------------------------------------------------------

_RULE = LivenessRule(
    model=RubricExtractionJob,
    arms=(
        ActiveArm("queued", "created_at", dispatch_ttl, REASON_NEVER_DISPATCHED),
        ActiveArm("extracting", "updated_at", heartbeat_ttl, REASON_HEARTBEAT_LAPSED),
    ),
    failed_values=lambda reason, now: dict(
        status="failed", error_message=reason, finished_at=now, updated_at=now
    ),
    log_label="extraction_jobs",
)


def expired_condition(now: Optional[datetime] = None):
    """The SQL half of the rule: active rows past their own deadline."""
    return _RULE.expired_condition(now)


def is_expired(job: RubricExtractionJob, now: Optional[datetime] = None) -> bool:
    """The Python half of the rule, for an already-loaded row. Agrees with
    `expired_condition` by construction — both read the same LivenessRule."""
    return _RULE.is_expired(job, now)


def expiry_reason(job: RubricExtractionJob) -> str:
    return _RULE.expiry_reason(job)


async def reap_expired(
    db: AsyncSession,
    *,
    user_id=None,
    source_sha256: Optional[str] = None,
    job_id: Optional[UUID] = None,
    commit: bool = False,
) -> int:
    """Expire every active-but-past-deadline row in scope. Returns the row count.
    Scope narrows by user / source / id; unscoped it sweeps the table (startup)."""
    extra = []
    if user_id is not None:
        extra.append(RubricExtractionJob.user_id == user_id)
    if source_sha256 is not None:
        extra.append(RubricExtractionJob.source_sha256 == source_sha256)
    if job_id is not None:
        extra.append(RubricExtractionJob.id == job_id)
    return await _RULE.reap(db, *extra, commit=commit)


async def sweep_on_startup() -> int:
    """Expire orphans left by the PREVIOUS process (inline-mode asyncio tasks
    die with the process; Cloud Run scale-in kills workers mid-job)."""
    return await _RULE.sweep_on_startup()
