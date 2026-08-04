"""
LIV-1 regression suite — pinned to the two shapes of the SAME bug.

Shape 1 (fixed earlier): a worker dies MID-JOB → 'extracting' with a lapsed
heartbeat.
Shape 2 (this bug, which escaped): a job dies BEFORE starting → 'queued' with
`updated_at == created_at`, never heartbeat, unreapable and unretryable, so the
resume surface re-attached to it forever and a re-upload was handed the corpse.

The lesson these tests encode: the rule must be ONE rule. The Python predicate
and the SQL condition are asserted against the SAME fixtures so they cannot
drift, because three divergent copies of "is it dead" is what let shape 2 through.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models.rubric_extraction_job import ACTIVE_JOB_STATUSES, RubricExtractionJob
from app.services.extraction_job_liveness import (
    REASON_HEARTBEAT_LAPSED,
    REASON_NEVER_DISPATCHED,
    dispatch_ttl,
    expiry_reason,
    heartbeat_ttl,
    is_expired,
)

NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)


def job(status: str, *, created_min_ago: float, updated_min_ago: float | None = None):
    """A row shaped like the real thing. For 'queued' the default mirrors the bug:
    updated_at IS created_at, because nothing touches the row while it waits."""
    created = NOW - timedelta(minutes=created_min_ago)
    updated = created if updated_min_ago is None else NOW - timedelta(minutes=updated_min_ago)
    return RubricExtractionJob(status=status, created_at=created, updated_at=updated)


# ── shape 2: the job that never started ──────────────────────────────────────

def test_queued_past_dispatch_deadline_is_expired():
    """THE BUG. A 'queued' row that was never picked up must be reapable."""
    stuck = job("queued", created_min_ago=settings.extraction_dispatch_ttl_minutes + 1)
    assert is_expired(stuck, NOW) is True
    assert expiry_reason(stuck) == REASON_NEVER_DISPATCHED


def test_the_exact_production_row_is_expired():
    """The real stranded job: queued, never heartbeat, ~20 hours old."""
    stranded = job("queued", created_min_ago=1193.6)
    assert stranded.updated_at == stranded.created_at   # never heartbeat — the tell
    assert is_expired(stranded, NOW) is True


def test_a_freshly_queued_job_is_NOT_expired():
    """Dispatch is normally sub-second; a job still inside its window is alive."""
    assert is_expired(job("queued", created_min_ago=0.1), NOW) is False


def test_queued_uses_created_at_not_updated_at():
    """'queued' has no heartbeat, so updated_at carries no liveness information.
    Keying off it (as the old rule did) makes a lost dispatch unfalsifiable."""
    old_but_touched = job("queued",
                          created_min_ago=settings.extraction_dispatch_ttl_minutes + 30,
                          updated_min_ago=0)
    assert is_expired(old_but_touched, NOW) is True


# ── shape 1: the job that died mid-flight (must keep working) ────────────────

def test_extracting_past_heartbeat_is_expired():
    dead = job("extracting", created_min_ago=120,
               updated_min_ago=settings.extraction_heartbeat_ttl_minutes + 1)
    assert is_expired(dead, NOW) is True
    assert expiry_reason(dead) == REASON_HEARTBEAT_LAPSED


def test_a_long_running_but_heartbeating_job_is_NOT_expired():
    """The wall deadline (~14 min) sits below the TTL, so a live job always
    heartbeats inside the window. Reaping it would kill real work."""
    alive = job("extracting", created_min_ago=600, updated_min_ago=1)
    assert is_expired(alive, NOW) is False


def test_extracting_ignores_created_at():
    """A job may legitimately be hours old; only the heartbeat speaks."""
    assert is_expired(job("extracting", created_min_ago=10_000, updated_min_ago=0), NOW) is False


# ── terminal states are never touched ────────────────────────────────────────

@pytest.mark.parametrize("status", ["completed", "failed"])
def test_terminal_states_are_never_expired(status):
    assert is_expired(job(status, created_min_ago=99_999, updated_min_ago=99_999), NOW) is False


def test_every_active_status_has_a_deadline():
    """The STRUCTURAL guard. If a new active status is added without giving it a
    deadline, it would be unfalsifiable — the precise defect this suite exists
    for — and this test fails until the rule covers it."""
    ancient = 10_000
    for status in ACTIVE_JOB_STATUSES:
        j = job(status, created_min_ago=ancient, updated_min_ago=ancient)
        assert is_expired(j, NOW) is True, (
            f"active status {status!r} has no deadline: a row in this state can "
            f"never expire, and will strand the teacher forever"
        )


def test_deadlines_are_ordered_sensibly():
    """Dispatch should be the SHORTER wait: waiting to be picked up is cheap to
    retry, whereas killing a running extraction throws away real work."""
    assert dispatch_ttl() < heartbeat_ttl()


# ── ported from the retired tests/api/test_extraction_staleness.py ───────────
# That file was written for the previous rule and asserted, in so many words,
# `_is_stale(queued) is False` — it PINNED THE BUG as correct behaviour, which is
# why the gap looked covered. Its still-valid cases live on here, against the
# rule that replaced it.

def test_missing_timestamp_is_not_expired():
    """Absent evidence is not evidence of death — never reap on a NULL clock."""
    assert is_expired(RubricExtractionJob(status="extracting", updated_at=None), NOW) is False
    assert is_expired(RubricExtractionJob(status="queued", created_at=None), NOW) is False


def test_naive_timestamps_are_treated_as_utc():
    """Postgres can hand back naive datetimes; a missing tzinfo must not make a
    dead job look alive (or vice versa)."""
    naive_old = (NOW - timedelta(minutes=60)).replace(tzinfo=None)
    assert is_expired(RubricExtractionJob(status="extracting", updated_at=naive_old), NOW) is True
    assert is_expired(RubricExtractionJob(status="queued", created_at=naive_old), NOW) is True


def test_heartbeat_ttl_exceeds_the_extraction_wall_deadline():
    """The safety invariant behind reaping 'extracting': a job that has not
    heartbeat within the TTL cannot still be running, because the pipeline's own
    wall deadline (840s ≈ 14 min) is shorter. Without this ordering, reaping
    would kill live work."""
    assert heartbeat_ttl().total_seconds() > 840
