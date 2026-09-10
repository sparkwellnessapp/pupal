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
    """One active status and the liveness clock(s) that back its claim.

    A HEARTBEAT CLOCK PROVES THE WORKER PROCESS EXISTS. It does not prove the
    work is progressing, that it can still land, or that the request which owns
    it is still alive - and the worker is the thing REFRESHING it. So an
    orphaned-but-still-scheduled coroutine renders its own row unfalsifiable:
    it keeps beating, the reaper keeps declining, and LIV-1's whole purpose
    ("a row that cannot be falsified is a row that traps the teacher forever")
    is satisfied in letter and defeated in fact.

    Hence the optional ABSOLUTE arm: a second clock on a column the worker does
    not touch (`started_at`), with a TTL derived from a number the work is
    supposed to be honoring. Past it the row is dead BY ARITHMETIC, whatever the
    heartbeat says. Its reason is separate on purpose - "the worker died" and
    "the worker overran its budget" are different events, and the teacher may
    act on them differently.
    """
    status: str
    clock_attr: str                      # "created_at" | "updated_at"
    ttl: Callable[[], timedelta]         # callable -> live settings reads
    reason: str                          # recorded on expiry (teacher-facing)
    # The cap the worker cannot refresh. Both None, or both set.
    absolute_clock_attr: Optional[str] = None      # e.g. "started_at"
    absolute_ttl: Optional[Callable[[], timedelta]] = None
    absolute_reason: str = ""

    def __post_init__(self):
        if bool(self.absolute_clock_attr) != bool(self.absolute_ttl):
            raise ValueError(
                "ActiveArm: absolute_clock_attr and absolute_ttl must be set "
                "together - a cap with no clock (or a clock with no cap) is a "
                "guard that silently never fires")


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
        clauses = []
        for arm in self.arms:
            clauses.append(and_(
                self.model.status == arm.status,
                getattr(self.model, arm.clock_attr) < now - arm.ttl(),
            ))
            if arm.absolute_clock_attr and arm.absolute_ttl:
                col = getattr(self.model, arm.absolute_clock_attr)
                clauses.append(and_(
                    self.model.status == arm.status,
                    # Stated, not assumed: an absolute clock that was never
                    # stamped must not condemn a row. `started_at` is written by
                    # the CAS claim so a running row always has one, but SQL
                    # NULL semantics would make the comparison quietly UNKNOWN
                    # rather than loud.
                    col.isnot(None),
                    col < now - arm.absolute_ttl(),
                ))
        return or_(*clauses)

    # -- the Python half (must agree with the SQL half) ----------------------

    @staticmethod
    def _aware(value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _absolute_expired(self, arm: ActiveArm, row, now: datetime) -> bool:
        if not (arm.absolute_clock_attr and arm.absolute_ttl):
            return False
        clock = self._aware(getattr(row, arm.absolute_clock_attr, None))
        return clock is not None and (now - clock) > arm.absolute_ttl()

    def is_expired(self, row, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        arm = self._arm_for(row.status)
        if arm is None:
            return False
        if self._absolute_expired(arm, row, now):
            return True
        clock = self._aware(getattr(row, arm.clock_attr, None))
        if clock is None:
            return False
        return (now - clock) > arm.ttl()

    def expiry_reason(self, row, now: Optional[datetime] = None) -> str:
        """The reason THIS row expired. The absolute cap is checked first and
        wins: when both fire it is the more specific fact, and it is the one
        that tells the teacher the work overran rather than vanished.

        `now` became a parameter when the absolute arm landed: the answer is no
        longer a pure function of `status`, so a caller that judges a row at a
        given instant (and every test that does) must be able to say WHICH
        instant. Defaulting to real now keeps every existing call site
        unchanged."""
        arm = self._arm_for(row.status)
        if arm is None:
            return ""
        if self._absolute_expired(arm, row, now or datetime.now(timezone.utc)):
            return arm.absolute_reason or arm.reason
        return arm.reason

    # -- reaping -------------------------------------------------------------

    def _reason_case(self, now: Optional[datetime] = None):
        """Per-status reason as ONE SQL expression, so a set-based reap stays
        one statement.

        Ordering mirrors `expiry_reason`: an arm's ABSOLUTE clause is tested
        before its heartbeat clause, so a row that blew its cap is recorded as
        having overrun rather than as having gone quiet. The two forms must
        agree - that is this module's standing invariant, and its test."""
        now = now or datetime.now(timezone.utc)
        whens = []
        for arm in self.arms:
            if arm.absolute_clock_attr and arm.absolute_ttl and arm.absolute_reason:
                col = getattr(self.model, arm.absolute_clock_attr)
                whens.append((
                    and_(self.model.status == arm.status,
                         col.isnot(None),
                         col < now - arm.absolute_ttl()),
                    arm.absolute_reason,
                ))
            whens.append((self.model.status == arm.status, arm.reason))
        if len(whens) == 1:
            return whens[0][1]
        return case(*whens[:-1], else_=whens[-1][1])

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
        stmt = stmt.values(**self.failed_values(self._reason_case(now), now)).returning(self.model.id)
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
