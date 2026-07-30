"""The staleness decision behind the orphaned-job reaper.

An 'extracting' row whose heartbeat lapsed (worker died — server restart, Cloud
Run scale-in, or --reload in dev) is PROVABLY dead: the extraction wall deadline
(~14 min) is below the heartbeat TTL (15 min). `_reap_if_stale` / the read-repair
in the status + list + submit surfaces uses `_is_stale` to make that state terminal
so the resume surface can never re-attach to a dead job (the "connection lost" trap).
"""
from datetime import datetime, timezone, timedelta

from app.api.v0.rubric_extraction_jobs import _is_stale, _heartbeat_ttl
from app.models.rubric_extraction_job import RubricExtractionJob


def _now():
    return datetime.now(timezone.utc)


def test_fresh_extracting_is_not_stale():
    now = _now()
    job = RubricExtractionJob(status="extracting", updated_at=now)
    assert _is_stale(job, now) is False


def test_extracting_past_ttl_is_stale():
    now = _now()
    ttl_min = _heartbeat_ttl().total_seconds() / 60
    job = RubricExtractionJob(status="extracting", updated_at=now - timedelta(minutes=ttl_min + 5))
    assert _is_stale(job, now) is True


def test_just_within_ttl_is_not_stale():
    now = _now()
    ttl_min = _heartbeat_ttl().total_seconds() / 60
    job = RubricExtractionJob(status="extracting", updated_at=now - timedelta(minutes=ttl_min - 1))
    assert _is_stale(job, now) is False


def test_completed_and_failed_are_never_stale():
    now = _now()
    old = now - timedelta(hours=5)
    assert _is_stale(RubricExtractionJob(status="completed", updated_at=old), now) is False
    assert _is_stale(RubricExtractionJob(status="failed", updated_at=old), now) is False
    assert _is_stale(RubricExtractionJob(status="queued", updated_at=old), now) is False


def test_missing_updated_at_is_not_stale():
    now = _now()
    assert _is_stale(RubricExtractionJob(status="extracting", updated_at=None), now) is False


def test_naive_updated_at_is_treated_as_utc():
    now = _now()
    naive = (now - timedelta(minutes=60)).replace(tzinfo=None)
    job = RubricExtractionJob(status="extracting", updated_at=naive)
    assert _is_stale(job, now) is True


def test_ttl_exceeds_wall_deadline_so_stale_means_dead():
    # The safety invariant: a stale job cannot still be running.
    assert _heartbeat_ttl().total_seconds() > 840  # 14-min extraction wall deadline
