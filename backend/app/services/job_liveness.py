"""
Generic job-liveness core — LIV-1, generalized for the Cloud Tasks migration.

THE RULE (unchanged from extraction_job_liveness, where it was born): an ACTIVE
status is a CLAIM that work is in progress. Every claim must be backed by a
liveness clock with a DEADLINE, or it expires. A row that cannot be falsified
is a row that traps the teacher forever.

Why this module exists: the batch-transcription and grading migrations each
need the same rule over their own tables (transcription_jobs, graded_tests).
Copy-pasting the extraction module three times recreates the exact failure
LIV-1 documents — divergent copies of "is it dead" letting a new shape of the
bug through. So the rule lives HERE once, parameterized by:

  * which model,
  * which statuses are active and which CLOCK each one runs on
    ("created_at" for no-heartbeat statuses like queued/pending — nothing
    touches the row while it waits; "updated_at" for heartbeat statuses),
  * each arm's TTL (a callable, so settings changes apply live) and the
    reason string recorded on expiry,
  * what the model's terminal-failure write looks like (per-table CHECK
    constraints differ — extraction/transcription jobs require finished_at,
    graded_tests has no such column).

Two forms that must agree — a SQL expression for set-based reaping and a
Python predicate for a loaded row — exactly as before; per-domain modules
instantiate a rule and re-export thin wrappers so their public APIs (and
their regression suites) stay stable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import and_, case, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActiveArm:
    """One active status and the liveness clock that backs its claim."""
    status: str
    clock_attr: str                      # "created_at" | "updated_at"
    ttl: Callable[[], timedelta]         # callable → live settings reads
    reason: str                          # recorded on expiry (teacher-facing)


@dataclass(frozen=True)
class LivenessRule:
    model: type
    arms: tuple[ActiveArm, ...]
    # (reason_value, now) -> column values for the terminal-failure write.
    # reason_value is either a str (single row) or a SQL CASE expression
    # (set-based reap) — build_values must place it, not inspect it.
    failed_values: Callable[[Any, datetime], dict]
    log_label: str = "jobs"

    # -- shared internals ----------------------------------------------------

    def _arm_for(self, status: str) -> Optional[ActiveArm]:
        for arm in self.arms:
            if arm.status == status:
                return arm
        return None

    @property
    def active_statuses(self) -> tuple[str, ...]:
        return tuple(arm.status for arm in self.arms)

    # -- the SQL half --------------------------------------------------------

    def expired_condition(self, now: Optional[datetime] = None):
        """Active rows past their own deadline. Set-based and multi-instance
        safe: it can only match a row whose deadline has already passed, never
        one another worker is still heartbeating."""
        now = now or datetime.now(timezone.utc)
        return or_(*[
            and_(
                self.model.status == arm.status,
                getattr(self.model, arm.clock_attr) < now - arm.ttl(),
            )
            for arm in self.arms
        ])

    # -- the Python half (must agree with the SQL half) ----------------------

    def is_expired(self, row, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        arm = self._arm_for(row.status)
        if arm is None:
            return False
        clock = getattr(row, arm.clock_attr, None)
        if clock is None:
            return False
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=timezone.utc)
        return (now - clock) > arm.ttl()

    def expiry_reason(self, row) -> str:
        arm = self._arm_for(row.status)
        return arm.reason if arm is not None else ""

    # -- reaping -------------------------------------------------------------

    def _reason_case(self):
        """Per-status reason as ONE SQL expression, so a set-based reap stays
        one statement."""
        if len(self.arms) == 1:
            return self.arms[0].reason
        return case(
            *[(self.model.status == arm.status, arm.reason) for arm in self.arms[:-1]],
            else_=self.arms[-1].reason,
        )

    async def reap(
        self,
        db: AsyncSession,
        *extra_where,
        commit: bool = False,
    ) -> int:
        """Expire every active-but-past-deadline row in scope. Idempotent:
        the WHERE re-checks status and deadline, so concurrent callers
        converge instead of fighting."""
        now = datetime.now(timezone.utc)
        stmt = update(self.model).where(self.expired_condition(now), *extra_where)
        # E1 (closeout, owner-ruled): RETURN the ids. A reap silently converts
        # a teacher's in-flight work into a failure she is never shown — the
        # count alone made that unfindable without a DB query, which is the
        # wrong altitude for the one event that means "her batch died".
        stmt = stmt.values(**self.failed_values(self._reason_case(), now)).returning(self.model.id)
        result = await db.execute(stmt)
        reaped_ids = [row[0] for row in result.fetchall()]
        reaped = len(reaped_ids)
        if reaped and commit:
            await db.commit()
        if reaped:
            logger.warning(
                "%s_reaped", self.log_label,
                extra={
                    "count": reaped,
                    # Bounded: a pathological sweep must not write a novel.
                    "reaped_ids": [str(i) for i in reaped_ids[:50]],
                    "truncated": reaped > 50,
                },
            )
        return reaped

    async def sweep_on_startup(self) -> int:
        """Expire orphans left by the PREVIOUS process, in its own session.
        A boot-time convenience must never prevent the service from booting."""
        from ..database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                reaped = await self.reap(db, commit=True)
                if reaped:
                    logger.warning("%s_startup_sweep_reaped", self.log_label,
                                   extra={"count": reaped})
                return reaped
        except Exception:
            logger.exception("%s_startup_sweep_failed", self.log_label)
            return 0
