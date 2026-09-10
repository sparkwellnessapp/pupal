"""
LIV-1 for plan builds — the shared LivenessRule over grading_plans rows
(PLAN_production_wiring.md §8).

  queued   — "a dispatch will claim me." Clock = created_at, 90-min backstop
             (the plan-build-jobs queue redelivers dispatch flakes; this is the
             absolute limit, mirroring grading runs).
  building — "a worker is building me." Clock = updated_at, written by the
             runner's heartbeat every ~30 s. TTL 5 min: a dead builder's row
             must not stay `building` long, because a grade waiting on it
             (OD-W3) reads exactly this clock to decide the builder is dead.

Expiry reaps to `failed` + error_message — what the CHECK admits. The next
grade of that rubric builds on demand (OD-W1); a new row, append-only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.grading_plan import GradingPlanRecord
from .job_liveness import ActiveArm, LivenessRule

logger = logging.getLogger(__name__)

REASON_NEVER_STARTED = "orphaned: plan build was never picked up (dispatch lost after queue retries)"
REASON_WORKER_DIED = "orphaned: plan builder died mid-build (heartbeat lapsed)"


def dispatch_ttl() -> timedelta:
    return timedelta(minutes=settings.plan_build_dispatch_ttl_minutes)


def building_ttl() -> timedelta:
    return timedelta(minutes=settings.plan_build_heartbeat_ttl_minutes)


# ---------------------------------------------------------------------------
# DEFERRED (owner-ruled 2026-09-10, scope: transcription only this PR).
#
# This rule's heartbeat arm has the SAME hole `transcription_job_liveness`
# just closed: `building.updated_at` is refreshed by the worker's own heartbeat, so a
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
    model=GradingPlanRecord,
    arms=(
        ActiveArm("queued", "created_at", dispatch_ttl, REASON_NEVER_STARTED),
        ActiveArm("building", "updated_at", building_ttl, REASON_WORKER_DIED),
    ),
    failed_values=lambda reason, now: dict(status="failed", error_message=reason, updated_at=now),
    log_label="plan_builds",
)


def expired_condition(now: Optional[datetime] = None):
    return _RULE.expired_condition(now)


def is_expired(row: GradingPlanRecord, now: Optional[datetime] = None) -> bool:
    return _RULE.is_expired(row, now)


def expiry_reason(row: GradingPlanRecord) -> str:
    return _RULE.expiry_reason(row)


async def reap_expired(db: AsyncSession, *, row_id: Optional[UUID] = None,
                       commit: bool = False) -> int:
    extra = []
    if row_id is not None:
        extra.append(GradingPlanRecord.id == row_id)
    return await _RULE.reap(db, *extra, commit=commit)


async def sweep_on_startup() -> int:
    return await _RULE.sweep_on_startup()
