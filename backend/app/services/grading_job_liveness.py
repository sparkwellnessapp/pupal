"""
LIV-1 for grading runs — instantiation of the shared LivenessRule over
graded_tests rows (Cloud Tasks migration, Phase 4).

graded_tests was ALREADY row-first (pending → grading → draft | failed), so
the migration only changed the execution substrate — what was missing was
falsifiability: a 'grading' row whose worker died stayed 'grading' forever,
and a 'pending' row whose dispatch was lost stayed 'pending' forever. Arms:

  pending — "a dispatch will claim me." Clock = created_at. The queue's
            maxAttempts=3 redelivery heals dispatch flakes; this TTL is the
            absolute backstop (90 min), mirroring transcription jobs.
  grading — "a worker is grading me." Clock = updated_at, written once at the
            pending→grading claim (run_grading has no in-run heartbeat). The
            TTL (30 min) must exceed the task's 900s dispatch deadline, after
            which a killed worker can write nothing more.

Expiry reaps to 'failed' + error_message (exactly what the CHECK admits and
what the EXISTING revision-retry flow accepts: failed + leaf → retry extends
the chain with a fresh pending row). LCY-2 is respected by construction —
only pending/grading rows can match the reap predicate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.grading import GradedTest
from .job_liveness import ActiveArm, LivenessRule

logger = logging.getLogger(__name__)

REASON_NEVER_STARTED = (
    "orphaned: grading was never picked up (dispatch lost after queue retries)"
)
REASON_WORKER_DIED = "orphaned: grading worker died mid-run"


def dispatch_ttl() -> timedelta:
    return timedelta(minutes=settings.grading_job_dispatch_ttl_minutes)


def running_ttl() -> timedelta:
    return timedelta(minutes=settings.grading_job_running_ttl_minutes)


# ---------------------------------------------------------------------------
# DEFERRED (owner-ruled 2026-09-10, scope: transcription only this PR).
#
# This rule's heartbeat arm has the SAME hole `transcription_job_liveness`
# just closed: `grading.updated_at` is refreshed by the worker's own heartbeat, so a
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
    model=GradedTest,
    arms=(
        ActiveArm("pending", "created_at", dispatch_ttl, REASON_NEVER_STARTED),
        ActiveArm("grading", "updated_at", running_ttl, REASON_WORKER_DIED),
    ),
    # graded_tests has no finished_at; CHECK admits failed + error_message.
    failed_values=lambda reason, now: dict(
        status="failed", error_message=reason, updated_at=now
    ),
    log_label="grading_runs",
)


def expired_condition(now: Optional[datetime] = None):
    return _RULE.expired_condition(now)


def is_expired(row: GradedTest, now: Optional[datetime] = None) -> bool:
    return _RULE.is_expired(row, now)


def expiry_reason(row: GradedTest) -> str:
    return _RULE.expiry_reason(row)


async def reap_expired(
    db: AsyncSession,
    *,
    batch_id: Optional[UUID] = None,
    graded_test_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    commit: bool = False,
) -> int:
    extra = []
    if batch_id is not None:
        extra.append(GradedTest.batch_id == batch_id)
    if graded_test_id is not None:
        extra.append(GradedTest.id == graded_test_id)
    if user_id is not None:
        # B10: user-scoped bulk pass for the list page — one reap for all of
        # a teacher's batches, never a per-batch loop.
        extra.append(GradedTest.user_id == user_id)
    return await _RULE.reap(db, *extra, commit=commit)


async def sweep_on_startup() -> int:
    return await _RULE.sweep_on_startup()
