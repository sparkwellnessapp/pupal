"""
LIV-1's ABSOLUTE arm — the clock the worker cannot refresh.

WHY IT EXISTS. A heartbeat clock proves the worker PROCESS still exists. It
does not prove the work is progressing, that it can still land, or that the
request which owns it is still alive — and the worker is the thing refreshing
it. So a coroutine orphaned past its Cloud Run request deadline keeps beating,
the reaper keeps declining, and LIV-1's stated purpose («a row that cannot be
falsified is a row that traps the teacher forever») is satisfied in letter and
defeated in fact. `started_at` is written once by the CAS claim and never
touched again, so a cap on it can condemn that row when nothing else can.

THE STANDING INVARIANT of `job_liveness` is that its two forms — the SQL
expression for set-based reaping and the Python predicate for a loaded row —
agree. The absolute arm has to hold that line too, so it is tested on both
sides and on the reason each side records.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.transcription_job import TranscriptionJob
from app.services import transcription_job_liveness as tj
from app.services.job_liveness import ActiveArm, LivenessRule

NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def _rule(*, heartbeat_min: float, absolute_min: float | None) -> LivenessRule:
    return LivenessRule(
        model=TranscriptionJob,
        arms=(
            ActiveArm("running", "updated_at",
                      lambda: timedelta(minutes=heartbeat_min), "heartbeat-lapsed",
                      absolute_clock_attr="started_at" if absolute_min else None,
                      absolute_ttl=((lambda: timedelta(minutes=absolute_min))
                                    if absolute_min else None),
                      absolute_reason="overran" if absolute_min else ""),
        ),
        failed_values=lambda reason, now: dict(
            status="failed", error_message=reason, finished_at=now, updated_at=now),
    )


def _row(*, started_min_ago: float, updated_min_ago: float, status: str = "running"):
    return TranscriptionJob(
        status=status,
        created_at=NOW - timedelta(minutes=started_min_ago + 1),
        started_at=NOW - timedelta(minutes=started_min_ago),
        updated_at=NOW - timedelta(minutes=updated_min_ago),
    )


# ---------------------------------------------------------------------------
# The core behaviour
# ---------------------------------------------------------------------------

def test_a_perfectly_healthy_heartbeat_no_longer_saves_a_row_past_its_cap():
    """THE point of the arm. This row is heartbeating every few seconds — it
    would have passed the old check forever."""
    rule = _rule(heartbeat_min=5, absolute_min=20)
    row = _row(started_min_ago=45, updated_min_ago=0.1)
    assert rule.is_expired(row, NOW) is True
    assert rule.expiry_reason(row, NOW) == "overran"


def test_without_the_cap_the_same_row_is_immortal():
    # The falsification of the old design, stated as a test rather than as a
    # comment: same row, same instant, cap removed.
    rule = _rule(heartbeat_min=5, absolute_min=None)
    assert rule.is_expired(_row(started_min_ago=45, updated_min_ago=0.1), NOW) is False


def test_a_young_row_with_a_fresh_heartbeat_is_left_alone():
    rule = _rule(heartbeat_min=5, absolute_min=20)
    assert rule.is_expired(_row(started_min_ago=3, updated_min_ago=0.1), NOW) is False


def test_the_heartbeat_arm_still_fires_on_its_own_inside_the_cap():
    # The cap ADDS a way to die; it must not take one away. A worker that
    # simply stopped is still caught at 5 minutes, not held for 20.
    rule = _rule(heartbeat_min=5, absolute_min=20)
    row = _row(started_min_ago=8, updated_min_ago=6)
    assert rule.is_expired(row, NOW) is True
    assert rule.expiry_reason(row, NOW) == "heartbeat-lapsed"


def test_the_two_reasons_are_different_facts_and_do_not_collapse():
    # "the worker died" and "the worker overran its budget" are different
    # events; she may act on them differently, and the reason string is the
    # only thing that tells her which happened.
    rule = _rule(heartbeat_min=5, absolute_min=20)
    overran = _row(started_min_ago=45, updated_min_ago=0.1)
    died = _row(started_min_ago=8, updated_min_ago=6)
    assert rule.expiry_reason(overran, NOW) != rule.expiry_reason(died, NOW)


def test_when_both_arms_fire_the_more_specific_one_is_recorded():
    rule = _rule(heartbeat_min=5, absolute_min=20)
    both = _row(started_min_ago=45, updated_min_ago=30)
    assert rule.is_expired(both, NOW) is True
    assert rule.expiry_reason(both, NOW) == "overran"


def test_a_null_absolute_clock_cannot_condemn_a_row():
    # `started_at` is written by the CAS claim so a running row always has one.
    # Stating it anyway: an unstamped clock must not be read as "infinitely
    # old", which is the direction that would kill live work.
    rule = _rule(heartbeat_min=5, absolute_min=20)
    row = TranscriptionJob(status="running", created_at=NOW, started_at=None,
                           updated_at=NOW)
    assert rule.is_expired(row, NOW) is False


def test_terminal_rows_are_untouched_by_the_cap():
    rule = _rule(heartbeat_min=5, absolute_min=20)
    for status in ("completed", "failed"):
        assert rule.is_expired(
            _row(started_min_ago=999, updated_min_ago=999, status=status), NOW) is False


def test_a_cap_without_a_clock_is_refused_at_construction():
    # A half-configured arm is a guard that silently never fires — the failure
    # mode this whole module exists to prevent, reintroduced as a typo.
    with pytest.raises(ValueError):
        ActiveArm("running", "updated_at", lambda: timedelta(minutes=5), "r",
                  absolute_ttl=lambda: timedelta(minutes=20))
    with pytest.raises(ValueError):
        ActiveArm("running", "updated_at", lambda: timedelta(minutes=5), "r",
                  absolute_clock_attr="started_at")


# ---------------------------------------------------------------------------
# The two forms must agree (the module's standing invariant)
# ---------------------------------------------------------------------------

def test_the_sql_form_names_the_absolute_clock_and_guards_its_null():
    rule = _rule(heartbeat_min=5, absolute_min=20)
    sql = str(rule.expired_condition(NOW).compile(
        compile_kwargs={"literal_binds": True}))
    assert "started_at" in sql and "updated_at" in sql
    assert "IS NOT NULL" in sql.upper()


def test_the_sql_reason_case_can_say_overran():
    rule = _rule(heartbeat_min=5, absolute_min=20)
    case_sql = str(rule._reason_case(NOW).compile(          # noqa: SLF001
        compile_kwargs={"literal_binds": True}))
    assert "overran" in case_sql
    assert "heartbeat-lapsed" in case_sql
    # Ordering is load-bearing: the absolute clause must be tested FIRST, or a
    # row that blew its cap is recorded as having merely gone quiet.
    assert case_sql.index("overran") < case_sql.index("heartbeat-lapsed")


# ---------------------------------------------------------------------------
# The production instantiation
# ---------------------------------------------------------------------------

def test_transcription_jobs_carry_the_cap_and_it_can_only_catch_corpses():
    from app.config import settings

    running = [a for a in tj._RULE.arms if a.status == "running"]  # noqa: SLF001
    assert len(running) == 1
    arm = running[0]
    assert arm.absolute_clock_attr == "started_at"
    assert arm.absolute_reason == tj.REASON_OVERRAN

    # The cap must sit safely ABOVE every legitimate run: the document's own
    # wall budget is 480s and Cloud Run kills the owning request at 900s, so
    # nothing honest is still running when this fires.
    cap_s = arm.absolute_ttl().total_seconds()
    assert cap_s > settings.transcription_task_budget_s
    assert cap_s > 900, "the cap must outlive the Cloud Run request timeout"


def test_the_reaped_row_is_retryable_without_re_upload():
    # The reason is teacher-facing and rides `error_message`, which the failed
    # card renders verbatim. It must say the work can be retried — the source
    # PDF is in GCS, so it costs her nothing.
    assert "retried" in tj.REASON_OVERRAN
    assert "re-upload" in tj.REASON_OVERRAN


def test_an_overrun_row_is_accepted_by_the_public_transcription_api():
    # `expired_condition` is what the per-document retry endpoint ORs against
    # `status == 'failed'`, and `is_expired` is what the batch payload reports
    # as `retryable`. Both must see the capped row, or the affordance the
    # dashboard renders would 409.
    row = _row(started_min_ago=45, updated_min_ago=0.1)
    assert tj.is_expired(row, NOW) is True
    assert tj.expiry_reason(row, NOW) == tj.REASON_OVERRAN
