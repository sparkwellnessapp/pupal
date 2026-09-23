"""
plan → execute → verify, against Vivi-Test with real rows and a recording fake
bucket (PR §12, §14, §16.1; census v2 §19).

The interface these tests pin — `app.services.erasure`:

  plan_purge(db, *, user_id, student_id, storage) -> PurgePlan      read-only
  execute_purge(plan, *, storage) -> PurgeResult                    deletes exactly `plan`
  purge_student(*, user_id, student_id, storage) -> PurgeResult     AM-B6: lock, plan, execute, verify
  verify_purged(plan, *, storage) -> VerifyReport
  retry_purge_failures(*, storage) -> int                           the M-B2 ledger's retry

Named invariants under test:
  PRV-2  AtomicRows          a row failure rolls everything back; no storage call
  PRV-3  ObjectsNeverSilentlyKept  a failed object delete lands in the ledger
  PRV-5  NoDeleteMidGrade    a blocker refuses; nothing touched
  PRV-6  PlanEqualsExecution the deleted set IS the plan; a stale plan fails closed
  PRV-7  VerifiedAfter       every purge ends with a report
  PRV-10 Consistency         the two selections of her graded tests must agree (AM-B5)
  PRV-11 PrefixSafety        (plan level) an object outside the allow-list refuses
  PRV-12 SharedObjects       an object another row still needs refuses
  OD-B1  the dead tables — the legacy pair and graded_test_pdfs — are asserted
         empty by verify; a graded_test_pdfs row under her grade refuses the plan
  OD-B3  the soft-delete window is reported, not hidden
  OD-B6  unassigned scans are counted in verify + audit, never deleted
  census E  a pre-jobs-era batch is excluded from the recount, and reported
  ruling  the student row is deleted LAST — never first with the constraints doing the rest

RED until the erasure core, migration 032 and migration 033 exist.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from tests.services.erasure.conftest import guarded
from tests.services.erasure.seed import (
    BUCKET,
    add_graded_blocker,
    add_legacy_batch_scan,
    add_pdf,
    add_running_job_on,
    batch_state,
    point_scan_at,
    row_counts,
    session,
    set_graded_student,
)


async def _plan(g, store, *, user_id=None):
    from app.services.erasure import plan_purge

    async with session() as db:
        return await plan_purge(db, user_id=user_id or g.user_id, student_id=g.student_id,
                                storage=guarded(store))


async def _purge(g, store):
    from app.database import engine
    from app.services.erasure import purge_student

    await engine.dispose(close=False)
    return await purge_student(user_id=g.user_id, student_id=g.student_id, storage=guarded(store))


def _as_sets(rows) -> dict[str, set]:
    return {table: set(ids) for table, ids in rows.items()}


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------

async def test_the_plan_lists_exactly_her_rows_and_objects(graph, store):
    plan = await _plan(graph, store)

    assert _as_sets(plan.rows) == graph.expected_rows()
    assert set(plan.objects) == graph.expected_objects()
    # M-B7: the two objects no row names are found by LISTING.
    assert (BUCKET, f"thumbs/{graph.t['alpha']}/p1_800x70-110.webp") in plan.objects
    assert (BUCKET, f"returned_exams/{graph.g['beta']}/k-superseded.pdf") in plan.objects
    assert not set(plan.objects) & graph.control_objects()


async def test_the_plan_recounts_her_batches_and_scrubs_her_failure_entry(graph, store):
    plan = await _plan(graph, store)

    assert set(plan.batch_recounts) == {graph.batch_id}
    assert dict(plan.failure_scrubs) == {graph.batch_id: 1}
    assert set(plan.legacy_count_batches) == set()


async def test_the_plan_counts_unassigned_scans_in_her_batches_and_never_deletes_them(graph, store):
    """OD-B6 (ruled): counted, with job ids; never on a name match; not deleted."""
    plan = await _plan(graph, store)

    assert plan.unassigned.count == 1
    assert set(plan.unassigned.job_ids) == {graph.j["gamma"]}
    assert graph.t["gamma"] not in plan.rows["transcriptions"]


async def test_a_pre_jobs_era_batch_is_excluded_from_the_recount_and_reported(graph, store):
    """Census E: COUNT(jobs) would zero it, and its true count is unrecoverable."""
    legacy = await add_legacy_batch_scan(graph)
    store.live |= graph.objects
    plan = await _plan(graph, store)

    assert legacy in plan.legacy_count_batches
    assert legacy not in plan.batch_recounts
    assert graph.t["legacy"] in plan.rows["transcriptions"]


async def test_the_plan_is_read_only(graph, store):
    before, batch_before = await row_counts(graph), await batch_state(graph.batch_id)
    await _plan(graph, store)

    assert await row_counts(graph) == before
    assert await batch_state(graph.batch_id) == batch_before
    assert store.delete_calls() == []


async def test_another_teachers_student_is_not_found_and_nothing_is_listed(graph, store):
    """PRV-4 at the service: the owner check comes before any storage call."""
    from app.services.erasure import StudentNotFound

    with pytest.raises(StudentNotFound):
        await _plan(graph, store, user_id=uuid.uuid4())
    assert store.calls == []


REFUSALS = [
    # (id, mutation, reason)
    ("her grade on another student's scan (PRV-10, AM-B5)",
     lambda g: set_graded_student(g, "delta", g.student_id), "selection_mismatch"),
    ("another student's grade on her scan (PRV-10, AM-B5)",
     lambda g: set_graded_student(g, "beta", g.other_student_id), "selection_mismatch"),
    ("a scan another student's row still points at (PRV-12)",
     lambda g: point_scan_at(g, "delta", path=g.scans["alpha"]), "shared_object"),
    ("a scan in a bucket outside the known set",
     lambda g: point_scan_at(g, "beta", bucket="some-other-bucket"), "unknown_bucket"),
    ("a scan path outside the allow-list (PRV-11)",
     lambda g: point_scan_at(g, "beta", path="tests/x.pdf"), "unsafe_target"),
    # graded_test_pdfs is DEAD (ruled 2026-09-23): the path below is inside an
    # allowed family on purpose — the refusal is about the table, not PRV-11.
    ("a graded_test_pdfs row under her grade (a dead table)",
     lambda g: add_pdf(g, "beta", f"returned_exams/{g.g['beta']}/k-legacy.pdf"), "dead_table_rows"),
]


@pytest.mark.parametrize("label,mutate,reason", REFUSALS, ids=[r[0] for r in REFUSALS])
async def test_the_plan_refuses_and_reports(graph, store, label, mutate, reason):
    from app.services.erasure import PurgeRefused

    await mutate(graph)
    before = await row_counts(graph)
    with pytest.raises(PurgeRefused) as refused:
        await _plan(graph, store)
    assert refused.value.reason == reason
    assert await row_counts(graph) == before
    assert store.delete_calls() == []


# ---------------------------------------------------------------------------
# blockers (PRV-5)
# ---------------------------------------------------------------------------

BLOCKERS = [
    ("a pending grade", lambda g: add_graded_blocker(g, "pending")),
    ("a grade in progress", lambda g: add_graded_blocker(g, "grading")),
    ("a running job on her scan", lambda g: add_running_job_on(g, "alpha")),
]


@pytest.mark.parametrize("label,block", BLOCKERS, ids=[b[0] for b in BLOCKERS])
async def test_a_blocker_refuses_the_purge_and_touches_nothing(graph, store, label, block):
    from app.services.erasure import PurgeBlocked

    await block(graph)
    store.live |= graph.objects
    before = await row_counts(graph)

    plan = await _plan(graph, store)
    assert len(plan.blockers) == 1
    with pytest.raises(PurgeBlocked) as blocked:
        await _purge(graph, store)
    assert blocked.value.count == 1
    assert await row_counts(graph) == before
    assert store.delete_calls() == []


# ---------------------------------------------------------------------------
# execution (PRV-6, PRV-2, the "student last" ruling)
# ---------------------------------------------------------------------------

async def test_the_purge_deletes_exactly_the_plan(graph, store):
    plan = await _plan(graph, store)
    await _purge(graph, store)

    async with session() as db:
        for table, ids in graph.expected_rows().items():
            key = "class_id" if table == "class_memberships" else "id"
            extra = " AND student_id = :s" if table == "class_memberships" else ""
            n = (await db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {key} = ANY(:ids){extra}"),
                                  {"ids": list(ids), "s": graph.student_id})).scalar_one()
            assert n == 0, f"{table}: {n} of her rows survived"
    after = await row_counts(graph)
    assert after["students"] == 1                                  # S2
    assert after["graded_tests"] == 1                              # g_delta
    assert after["transcriptions"] == 2                            # t_delta, t_gamma
    assert after["transcription_jobs"] == 3                        # j_delta, j_gamma, j_failed
    assert (after["grading_batches"], after["rubrics"], after["users"]) == (1, 1, 1)

    deleted = store.delete_calls()
    assert len(deleted) == len(set(deleted)), "an object was deleted twice"
    assert set(deleted) == set(plan.objects)                       # PRV-6
    assert graph.control_objects() <= store.live


async def test_the_batch_count_is_recomputed_from_jobs_and_her_failure_entry_is_scrubbed(graph, store):
    await _purge(graph, store)

    count, failures = await batch_state(graph.batch_id)
    assert count == 3                                              # COUNT(jobs) left: delta, gamma, failed
    assert [f["filename"] for f in failures] == ["scan-unrelated.pdf"]


async def test_a_pre_jobs_era_batch_keeps_its_count(graph, store):
    legacy = await add_legacy_batch_scan(graph)
    store.live |= graph.objects
    await _purge(graph, store)

    assert (await batch_state(legacy))[0] == 2


async def test_the_student_row_is_deleted_last(graph, store):
    """Ruling 2026-09-22: never delete the student first and let the
    constraints do the rest — that makes PRV-6 a lie."""
    from app.database import engine

    deletes: list[str] = []

    def _capture(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("DELETE"):
            deletes.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _capture)
    try:
        await _purge(graph, store)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture)

    targets = [s.split("FROM", 1)[1].split()[0].strip('"').split(".")[-1] for s in deletes]
    assert targets, "no DELETE statement was captured"
    assert targets[-1] == "students"
    assert targets.count("students") == 1


async def test_a_stale_plan_fails_closed_rolls_back_and_calls_no_storage(graph, store):
    """PRV-6 + PRV-2 + AM-B1: a dependent that appeared after planning is not in
    the plan, so its parent's delete raises under NO ACTION and nothing lands.
    (Under today's SET NULL the purge would succeed and orphan the new row.)"""
    from app.database import engine
    from app.services.erasure import PurgeRefused, execute_purge

    plan = await _plan(graph, store)
    late = await add_running_job_on(graph, "alpha")
    before, calls_before = await row_counts(graph), len(store.calls)

    await engine.dispose(close=False)
    with pytest.raises(PurgeRefused) as refused:
        await execute_purge(plan, storage=guarded(store))
    assert refused.value.reason == "plan_stale"
    assert await row_counts(graph) == before
    assert len(store.calls) == calls_before, "a storage call was made before the rows committed"
    async with session() as db:
        assert (await db.execute(text("SELECT transcription_id FROM transcription_jobs WHERE id = :j"),
                                 {"j": late})).scalar_one() == graph.t["alpha"]


# ---------------------------------------------------------------------------
# the ledger (PRV-3, M-B2)
# ---------------------------------------------------------------------------

async def test_a_failed_object_lands_in_the_ledger_and_the_retry_clears_it(graph, store, caplog):
    from app.services.erasure import retry_purge_failures, verify_purged

    stuck = (BUCKET, f"thumbs/{graph.t['alpha']}/p2_1200x80-150.webp")
    store.fail_on.add(stuck)
    plan = await _plan(graph, store)

    with caplog.at_level(logging.ERROR):
        result = await _purge(graph, store)
    assert [(f.bucket, f.object_name) for f in result.failures] == [stuck]
    assert (await row_counts(graph))["students"] == 1              # her rows are gone regardless
    assert any(str(graph.student_id) in r.getMessage() for r in caplog.records
               if r.levelno >= logging.ERROR)
    async with session() as db:
        ledger = (await db.execute(text(
            "SELECT bucket, object_name FROM purge_failures WHERE student_id = :s"),
            {"s": graph.student_id})).all()
    assert [tuple(r) for r in ledger] == [stuck]
    assert result.verify.objects_remaining == frozenset({stuck})
    assert result.verify.clean is False

    store.fail_on.clear()
    assert await retry_purge_failures(storage=guarded(store)) == 1
    async with session() as db:
        assert (await db.execute(text("SELECT COUNT(*) FROM purge_failures WHERE student_id = :s"),
                                 {"s": graph.student_id})).scalar_one() == 0
    assert stuck not in store.live
    assert (await verify_purged(plan, storage=guarded(store))).clean is True


# ---------------------------------------------------------------------------
# verify (PRV-7, OD-B1, OD-B3, OD-B6)
# ---------------------------------------------------------------------------

async def test_verify_is_not_vacuous(graph, store):
    from app.services.erasure import verify_purged

    plan = await _plan(graph, store)
    report = await verify_purged(plan, storage=guarded(store))

    assert report.clean is False
    assert all(report.rows_remaining[t] == len(ids) for t, ids in graph.expected_rows().items())
    assert report.objects_remaining == frozenset(plan.objects)


async def test_every_purge_ends_with_a_clean_verify_that_reports_the_soft_delete_window(graph, store):
    plan = await _plan(graph, store)
    result = await _purge(graph, store)
    report = result.verify

    assert report.clean is True
    assert all(n == 0 for n in report.rows_remaining.values())
    assert report.objects_remaining == frozenset()
    assert report.legacy_tables_empty is True                      # OD-B1, graded_test_pdfs
    assert report.soft_deleted_count == len(plan.objects)          # OD-B3
    week = datetime.now(timezone.utc) + timedelta(days=7)
    assert abs((report.restorable_until - week).total_seconds()) < 120


async def test_verify_asserts_the_dead_tables_stay_empty(graph, store):
    """A graded_test_pdfs row that is NOT hers blocks nothing — the plan never
    touches the table — but verify asserts the WHOLE table stays empty, like
    the legacy tables (OD-B1, ruled 2026-09-23), so the report is not clean."""
    await add_pdf(graph, "delta", f"returned_exams/{graph.g['delta']}/k-legacy.pdf")
    store.live |= graph.objects
    result = await _purge(graph, store)

    assert result.verify.legacy_tables_empty is False
    assert result.verify.clean is False
    assert (await row_counts(graph))["graded_test_pdfs"] == 1       # never purged


async def test_verify_and_the_audit_line_carry_the_unassigned_count_and_never_a_name(
        graph, store, caplog):
    """OD-B6: the count and job ids go to the verify report and the audit line —
    and no log line anywhere carries her name or a filename (OD-B4)."""
    with caplog.at_level(logging.INFO):
        result = await _purge(graph, store)

    assert result.verify.unassigned_count == 1
    assert set(result.verify.unassigned_job_ids) == {graph.j["gamma"]}
    audit = [r.getMessage() for r in caplog.records if "purge_audit" in r.getMessage()]
    assert len(audit) == 1
    assert str(graph.student_id) in audit[0] and str(graph.j["gamma"]) in audit[0]
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert graph.student_name not in everything
    assert not any(f in everything for f in graph.filenames.values())
