"""
LIV-1 — LIVENESS FOR EXTRACTION JOBS. One concept, one place.

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

WHY THIS MODULE EXISTS AT ALL — the bug it closes. Staleness used to be written
as `status == 'extracting' AND updated_at < cutoff`, spelled out THREE times (the
single-read reaper, the pre-submit reaper, the Python predicate). That covered a
worker dying MID-JOB and nothing else, so a job that died BEFORE starting — the
in-process `asyncio.create_task` lost to a server restart in inline mode, or a
Cloud Tasks enqueue that never got delivered — stayed `queued` with
`updated_at == created_at` FOREVER. It stayed in the active set, so the
resume-on-entry surface re-attached to it on every page load, and the
one-active-per-source unique index handed the same corpse back on re-upload. The
teacher could neither proceed nor start over.

Three copies of a special case is why a second shape of the same bug walked
through. So the rule lives here ONCE, in two forms that must agree — a SQL
expression for set-based reaping and a Python predicate for a loaded row — and
every door (get / list / pre-submit / startup) consumes it.

Expiry is recorded as `failed` with a distinct `error_message`: the CHECK
constraint already admits failed + error_message + finished_at, `/retry` accepts
failed leaves so the work stays recoverable, and the reason stays diagnosable
without a migration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.rubric_extraction_job import RubricExtractionJob

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


def expired_condition(now: Optional[datetime] = None):
    """The SQL half of the rule: active rows past their own deadline.

    Set-based so a reap is one UPDATE, and safe under multiple instances — it can
    only match a row whose deadline has already passed, never one another worker
    is still heartbeating.
    """
    now = now or datetime.now(timezone.utc)
    return or_(
        and_(
            RubricExtractionJob.status == "queued",
            RubricExtractionJob.created_at < now - dispatch_ttl(),
        ),
        and_(
            RubricExtractionJob.status == "extracting",
            RubricExtractionJob.updated_at < now - heartbeat_ttl(),
        ),
    )


def is_expired(job: RubricExtractionJob, now: Optional[datetime] = None) -> bool:
    """The Python half of the rule, for an already-loaded row. Must agree with
    `expired_condition` — the tests assert both against the same fixtures."""
    now = now or datetime.now(timezone.utc)

    def _aware(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    if job.status == "queued":
        created = _aware(job.created_at)
        return created is not None and (now - created) > dispatch_ttl()
    if job.status == "extracting":
        updated = _aware(job.updated_at)
        return updated is not None and (now - updated) > heartbeat_ttl()
    return False


def expiry_reason(job: RubricExtractionJob) -> str:
    return REASON_NEVER_DISPATCHED if job.status == "queued" else REASON_HEARTBEAT_LAPSED


async def reap_expired(
    db: AsyncSession,
    *,
    user_id=None,
    source_sha256: Optional[str] = None,
    job_id: Optional[UUID] = None,
    commit: bool = False,
) -> int:
    """Expire every active-but-past-deadline row in scope. Returns the row count.

    Scope narrows by user / source / id; unscoped it sweeps the table (startup).
    Idempotent: the WHERE clause re-checks status and deadline, so concurrent
    callers converge instead of fighting. `finished_at` and `error_message` are
    set together because the status CHECK constraint requires both for 'failed'.
    """
    now = datetime.now(timezone.utc)
    stmt = update(RubricExtractionJob).where(expired_condition(now))
    if user_id is not None:
        stmt = stmt.where(RubricExtractionJob.user_id == user_id)
    if source_sha256 is not None:
        stmt = stmt.where(RubricExtractionJob.source_sha256 == source_sha256)
    if job_id is not None:
        stmt = stmt.where(RubricExtractionJob.id == job_id)

    # The reason differs per status, so express it in SQL rather than reading rows
    # first — keeps this one statement.
    from sqlalchemy import case

    reason = case(
        (RubricExtractionJob.status == "queued", REASON_NEVER_DISPATCHED),
        else_=REASON_HEARTBEAT_LAPSED,
    )
    result = await db.execute(
        stmt.values(status="failed", error_message=reason, finished_at=now, updated_at=now)
    )
    reaped = result.rowcount or 0
    if reaped and commit:
        await db.commit()
    if reaped:
        logger.info("extraction_jobs_reaped", extra={"count": reaped})
    return reaped


async def sweep_on_startup() -> int:
    """Expire orphans left by the PREVIOUS process, in its own session.

    This is what makes the bad state unable to SURVIVE a restart. Inline mode
    dispatches with `asyncio.create_task`, which dies with the process, and Cloud
    Run scale-in kills workers mid-job — both leave rows whose owner no longer
    exists. Because it reuses the same deadlines, it can never kill a job a
    sibling instance is still heartbeating.
    """
    from ..database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            reaped = await reap_expired(db, commit=True)
            if reaped:
                logger.warning("extraction_startup_sweep_reaped", extra={"count": reaped})
            return reaped
    except Exception:
        # A boot-time convenience must never prevent the service from booting.
        logger.exception("extraction_startup_sweep_failed")
        return 0
