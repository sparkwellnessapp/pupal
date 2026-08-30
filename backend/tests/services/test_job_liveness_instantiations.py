"""
LIV-1 instantiations for the Cloud Tasks migration — transcription jobs and
grading runs. The generic core is pinned in test_job_liveness; these pin each
domain's ARMS (which statuses are active, which clock each runs on, and that
the two never share a deadline by accident).
"""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.grading import GradedTest
from app.models.transcription_job import TranscriptionJob
from app.services import grading_job_liveness as gliv
from app.services import transcription_job_liveness as tliv

NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)


def _tjob(status: str, *, created_min_ago: float, updated_min_ago: float | None = None):
    created = NOW - timedelta(minutes=created_min_ago)
    updated = created if updated_min_ago is None else NOW - timedelta(minutes=updated_min_ago)
    return TranscriptionJob(status=status, created_at=created, updated_at=updated)


def _grun(status: str, *, created_min_ago: float, updated_min_ago: float | None = None):
    created = NOW - timedelta(minutes=created_min_ago)
    updated = created if updated_min_ago is None else NOW - timedelta(minutes=updated_min_ago)
    return GradedTest(status=status, created_at=created, updated_at=updated)


# ── transcription jobs ───────────────────────────────────────────────────────

def test_transcription_queued_backstop_is_generous_not_extractions_5min():
    """Batch backlog makes long queued waits HONEST — the dispatch arm must
    not fire inside the backstop (default 90 min), unlike extraction's 5."""
    ttl = settings.transcription_job_dispatch_ttl_minutes
    assert ttl >= 60
    assert not tliv.is_expired(_tjob("queued", created_min_ago=ttl - 5), NOW)
    stuck = _tjob("queued", created_min_ago=ttl + 1)
    assert tliv.is_expired(stuck, NOW)
    assert tliv.expiry_reason(stuck) == tliv.REASON_NEVER_STARTED


def test_transcription_running_heartbeat_arm():
    ttl = settings.transcription_job_heartbeat_ttl_minutes
    alive = _tjob("running", created_min_ago=500, updated_min_ago=ttl - 1)
    dead = _tjob("running", created_min_ago=500, updated_min_ago=ttl + 1)
    assert not tliv.is_expired(alive, NOW)      # old but heartbeating
    assert tliv.is_expired(dead, NOW)
    assert tliv.expiry_reason(dead) == tliv.REASON_WORKER_DIED


def test_transcription_terminal_rows_never_expire():
    assert not tliv.is_expired(_tjob("completed", created_min_ago=9999), NOW)
    assert not tliv.is_expired(_tjob("failed", created_min_ago=9999), NOW)


# ── grading runs (graded_tests rows) ─────────────────────────────────────────

def test_grading_pending_backstop_arm():
    ttl = settings.grading_job_dispatch_ttl_minutes
    assert not gliv.is_expired(_grun("pending", created_min_ago=ttl - 5), NOW)
    stuck = _grun("pending", created_min_ago=ttl + 1)
    assert gliv.is_expired(stuck, NOW)
    assert gliv.expiry_reason(stuck) == gliv.REASON_NEVER_STARTED


def test_grading_running_ttl_exceeds_dispatch_deadline():
    """The 'grading' arm has NO in-run heartbeat (updated_at is written once
    at the claim), so its TTL must exceed the 900s task dispatch deadline —
    otherwise a legitimately-running grade could be reaped mid-run."""
    assert settings.grading_job_running_ttl_minutes * 60 > 900

    ttl = settings.grading_job_running_ttl_minutes
    alive = _grun("grading", created_min_ago=100, updated_min_ago=ttl - 1)
    dead = _grun("grading", created_min_ago=100, updated_min_ago=ttl + 1)
    assert not gliv.is_expired(alive, NOW)
    assert gliv.is_expired(dead, NOW)
    assert gliv.expiry_reason(dead) == gliv.REASON_WORKER_DIED


def test_grading_reviewable_and_terminal_statuses_never_expire():
    """LCY-2 by construction: draft/approved/failed rows can never match the
    reap predicate — only the two ACTIVE statuses carry deadlines."""
    for status in ("draft", "approved", "failed"):
        assert not gliv.is_expired(_grun(status, created_min_ago=9999), NOW)
