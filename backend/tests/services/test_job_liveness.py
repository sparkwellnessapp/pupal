"""
Generic LivenessRule core (Cloud Tasks migration, Phase 0).

The extraction LIV-1 suite (test_extraction_job_liveness) pins the extraction
INSTANTIATION's behavior; this file pins the CORE's contract — arm selection,
clock choice, TTL boundary, reason mapping — and the drift-guard: the
extraction module's delegated API must equal the core rule's answers on the
same rows (three divergent copies of "is it dead" is the documented origin of
this bug class).
"""
from datetime import datetime, timedelta, timezone

from app.models.rubric_extraction_job import RubricExtractionJob
from app.services import extraction_job_liveness as ext
from app.services.job_liveness import ActiveArm, LivenessRule

NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)


def _rule(queued_ttl_min: float, running_ttl_min: float) -> LivenessRule:
    return LivenessRule(
        model=RubricExtractionJob,
        arms=(
            ActiveArm("queued", "created_at",
                      lambda: timedelta(minutes=queued_ttl_min), "reason-q"),
            ActiveArm("extracting", "updated_at",
                      lambda: timedelta(minutes=running_ttl_min), "reason-r"),
        ),
        failed_values=lambda reason, now: dict(
            status="failed", error_message=reason, finished_at=now, updated_at=now
        ),
    )


def _row(status: str, *, created_min_ago: float, updated_min_ago: float | None = None):
    created = NOW - timedelta(minutes=created_min_ago)
    updated = created if updated_min_ago is None else NOW - timedelta(minutes=updated_min_ago)
    return RubricExtractionJob(status=status, created_at=created, updated_at=updated)


def test_each_arm_uses_its_own_clock_and_ttl():
    rule = _rule(queued_ttl_min=10, running_ttl_min=5)
    # queued judged on created_at, even when updated_at is fresh:
    assert rule.is_expired(_row("queued", created_min_ago=11, updated_min_ago=0), NOW)
    assert not rule.is_expired(_row("queued", created_min_ago=9), NOW)
    # running judged on updated_at, even when created_at is ancient:
    assert not rule.is_expired(_row("extracting", created_min_ago=500, updated_min_ago=4), NOW)
    assert rule.is_expired(_row("extracting", created_min_ago=500, updated_min_ago=6), NOW)


def test_terminal_and_unknown_statuses_never_expire():
    rule = _rule(queued_ttl_min=0.001, running_ttl_min=0.001)
    assert not rule.is_expired(_row("completed", created_min_ago=999), NOW)
    assert not rule.is_expired(_row("failed", created_min_ago=999), NOW)


def test_reason_maps_per_arm_and_active_statuses_derive_from_arms():
    rule = _rule(10, 5)
    assert rule.expiry_reason(_row("queued", created_min_ago=0)) == "reason-q"
    assert rule.expiry_reason(_row("extracting", created_min_ago=0)) == "reason-r"
    assert rule.active_statuses == ("queued", "extracting")


def test_naive_datetimes_are_treated_as_utc():
    rule = _rule(10, 5)
    naive = RubricExtractionJob(
        status="queued",
        created_at=(NOW - timedelta(minutes=11)).replace(tzinfo=None),
        updated_at=(NOW - timedelta(minutes=11)).replace(tzinfo=None),
    )
    assert rule.is_expired(naive, NOW)


def test_extraction_module_delegates_to_the_same_rule():
    """Drift guard: the extraction wrappers and the core must give identical
    answers on identical rows — the module is an instantiation, not a copy."""
    fixtures = [
        _row("queued", created_min_ago=0.1),
        _row("queued", created_min_ago=10_000),
        _row("extracting", created_min_ago=120, updated_min_ago=0.5),
        _row("extracting", created_min_ago=120, updated_min_ago=10_000),
        _row("completed", created_min_ago=10_000),
    ]
    for row in fixtures:
        assert ext.is_expired(row, NOW) == ext._RULE.is_expired(row, NOW)
        if ext.is_expired(row, NOW):
            assert ext.expiry_reason(row) in (
                ext.REASON_NEVER_DISPATCHED, ext.REASON_HEARTBEAT_LAPSED
            )


def test_sql_condition_covers_exactly_the_arms():
    """The SQL half names each arm's status and clock; compile and check the
    rendered predicate mentions both statuses and both clock columns."""
    rendered = str(_rule(10, 5).expired_condition(NOW).compile(
        compile_kwargs={"literal_binds": True}))
    assert "queued" in rendered and "extracting" in rendered
    assert "created_at" in rendered and "updated_at" in rendered
