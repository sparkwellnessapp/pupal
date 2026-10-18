"""
Plan cache and pinning — grader-v6 §5.7, amendment AM-G6, migration 035.

  * the key is (contract_sha256, config_hash): one LIVE plan per key, so a v5 and
    a v6 plan of one contract coexist and never supersede each other;
  * a plan is built once under concurrency — the index decides, the loser gets
    the winner's row;
  * the grade-time wait is bounded by PLAN_WAIT_S alone, and running out takes
    the existing `failed` path;
  * a graded test pins the plan it was graded against (graded_tests.plan_hash).

Real database (Vivi-Test) wherever the guarantee lives in the database (the
partial unique index, the column); no provider is ever called — builds use a
fake model that fails, which lands a valid placeholder plan (W-2).
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, func, select

from app.agents.grader.plan_values import config_hash as v6_config_hash
from app.agents.grader.plan_values import plan_hash as v6_plan_hash
from app.database import get_db_context
from app.models.grading import GradedTest
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_build_runner as pbr
from app.services import plan_store
from app.services.grading_inputs import PlanPinConflict, pin_plan_hash
from app.services.plan_store import LIVE_STATUSES, V5_CONFIG_HASH as V5, contract_sha256

MIGRATION_035 = Path(__file__).resolve().parents[2] / "migrations" / "035_plan_cache_config_hash.sql"
V6 = v6_config_hash(compiler_version="plan-compiler/v6.0", planner_model="claude-sonnet-5",
                    planner_prompt_version="planner-test", pack_id="cs", pack_version="1")
PLAN_HASH = v6_plan_hash([], [])


def _run(coro):
    return asyncio.run(coro)


def _sha():
    return "test-" + uuid.uuid4().hex


def _v6_plan_json(config_hash=V6, plan_hash=PLAN_HASH):
    return {"plan_schema": "plan/v6", "plan_hash": plan_hash, "config_hash": config_hash,
            "rubric_contract_version": "cv", "subject_pack": {"pack_id": "cs", "pack_version": "1"},
            "terminals": [], "checks": []}


async def _cleanup(sha):
    async with get_db_context() as db:
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.contract_sha256 == sha))
        await db.commit()


async def _live_count(sha, config_hash):
    async with get_db_context() as db:
        return (await db.execute(
            select(func.count()).select_from(GradingPlanRecord)
            .where(GradingPlanRecord.contract_sha256 == sha,
                   GradingPlanRecord.config_hash == config_hash,
                   GradingPlanRecord.status.in_(LIVE_STATUSES)))).scalar_one()


async def _ready(db, row_id, sha, config_hash, plan_json, plan_hash=None):
    assert await plan_store.claim_building(db, row_id)
    await plan_store.mark_ready(db, row_id, plan_json=plan_json, plan_version="p",
                                skeleton_json=None, compiler_version="c", segmenter_model=None,
                                router_model=None, wording_source="placeholder",
                                cost_usd=Decimal("0"), sha=sha, config_hash=config_hash,
                                plan_hash=plan_hash)


def _outage_factory(model_key):
    """Every model call fails → the build lands a valid PLACEHOLDER plan (W-2)."""
    class _Runner:
        async def ainvoke(self, messages):
            raise ConnectionError("provider down")

    return SimpleNamespace(with_structured_output=lambda schema, include_raw=True: _Runner())


@pytest.fixture(scope="module")
def hobby_json():
    from tests.grading_eval_suite.fixtures import load_bundle
    return load_bundle("dan_basiuk").rubric_contract.model_dump(mode="json")


# ── the key ─────────────────────────────────────────────────────────────────

def test_v5_key_is_the_constant_migration_035_backfills_and_defaults():
    """ONE spelling in Python, pinned to the SQL: the backfill and the column
    DEFAULT a still-running pre-035 revision inserts under."""
    sql = MIGRATION_035.read_text(encoding="utf-8")
    assert f"SET DEFAULT '{V5}'" in sql
    assert f"SET config_hash = '{V5}'" in sql
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS idx_grading_plans_one_live_per_contract_config\s+"
                     r"ON public\.grading_plans \(contract_sha256, config_hash\)\s+"
                     r"WHERE status IN \('queued', 'building', 'ready'\)", sql)
    assert "DROP INDEX IF EXISTS public.idx_grading_plans_one_live_per_contract;" in sql
    assert re.fullmatch(r"[0-9a-f]{64}", V6) and V6 != V5


def test_config_hash_must_be_the_v5_constant_or_a_digest():
    async def scenario():
        async with get_db_context() as db:
            for bad in ("", "v6", PLAN_HASH.upper(), "x" * 64):
                with pytest.raises(ValueError, match="config_hash"):
                    await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                   sha=_sha(), config_hash=bad)
    _run(scenario())


# ── build once ──────────────────────────────────────────────────────────────

@pytest.mark.db
def test_plan_built_once_under_concurrency(hobby_json, monkeypatch):
    """Two concurrent builders of ONE key → one live row; the loser gets the
    winner's row. Pinned for the v5 key and a v6 key at the store, and end to
    end for the v5 grade path: two grades of a never-planned contract build
    the plan exactly once and both grade against it."""
    sha = _sha()

    async def race_the_store(config_hash):
        async with get_db_context() as a, get_db_context() as b:
            (ra, ca), (rb, cb) = await asyncio.gather(
                plan_store.insert_queued(a, rubric_id=None, contract_version="v", sha=sha,
                                         config_hash=config_hash),
                plan_store.insert_queued(b, rubric_id=None, contract_version="v", sha=sha,
                                         config_hash=config_hash))
        assert sorted([ca, cb]) == [False, True], "exactly one writer creates the row"
        assert ra.id == rb.id, "the loser gets the winner's row"
        assert await _live_count(sha, config_hash) == 1

    cj = dict(hobby_json, contract_version=str(uuid.uuid4()), rubric_name=f"once-{uuid.uuid4().hex[:8]}")
    sha_grade = contract_sha256(cj)
    builds = []
    real_build = pbr.build_plan_for_contract

    async def counting_build(*a, **k):
        builds.append(1)
        return await real_build(*a, **k)

    monkeypatch.setattr(pbr, "build_plan_for_contract", counting_build)
    monkeypatch.setattr(pbr, "POLL_S", 0.2)

    async def race_the_grades():
        r1, r2 = await asyncio.gather(
            pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=60),
            pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=60))
        assert len(builds) == 1, "the plan is built once"
        assert r1.row_id == r2.row_id
        assert sorted([r1.built_in_place, r2.built_in_place]) == [False, True]
        assert await _live_count(sha_grade, V5) == 1

    try:
        _run(race_the_store(V5))
        _run(race_the_store(V6))
        _run(race_the_grades())
    finally:
        _run(_cleanup(sha))
        _run(_cleanup(sha_grade))


# ── v5 and v6 coexist ───────────────────────────────────────────────────────

@pytest.mark.db
def test_a_v5_and_a_v6_plan_of_one_contract_coexist_as_two_live_rows():
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            r5, c5 = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                    sha=sha, config_hash=V5)
            r6, c6 = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                    sha=sha, config_hash=V6)
            assert c5 and c6 and r5.id != r6.id, "two keys, two live rows — no collision"
            await _ready(db, r5.id, sha, V5, {"plan": "v5"})
            await _ready(db, r6.id, sha, V6, _v6_plan_json(), plan_hash=PLAN_HASH)

            v5 = await plan_store.get_ready(db, sha, config_hash=V5)
            v6 = await plan_store.get_ready(db, sha, config_hash=V6)
            await db.refresh(v5)
            assert v5.id == r5.id and v5.status == "ready", "a v6 build never supersedes the v5 plan"
            assert v5.plan_json == {"plan": "v5"} and v5.plan_hash is None and v5.config_hash == V5
            assert v6.id == r6.id and v6.plan_hash == PLAN_HASH and v6.config_hash == V6
            assert (await plan_store.find_live(db, sha, config_hash=V5)).id == r5.id
            assert (await plan_store.find_live(db, sha, config_hash=V6)).id == r6.id
        assert await _live_count(sha, V5) == 1 and await _live_count(sha, V6) == 1
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


@pytest.mark.db
def test_a_plan_is_refused_under_a_key_that_is_not_its_own_and_nothing_lands():
    """The store is the only writer; it refuses a wiring bug instead of filing
    one planner's plan under another's key. The refused call supersedes
    nothing — the v5 ready plan it names by key stays ready."""
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            r5, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                   sha=sha, config_hash=V5)
            await _ready(db, r5.id, sha, V5, {"plan": "v5"})
            r6, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                   sha=sha, config_hash=V6)
            assert await plan_store.claim_building(db, r6.id)
            id5, id6 = r5.id, r6.id           # a refused write rolls back and expires the rows
            refusals = [
                dict(plan_json={"plan": "v5"}, config_hash=V6, plan_hash=None),     # v5 plan, v6 key
                dict(plan_json=_v6_plan_json(), config_hash=V5, plan_hash=None),    # v6 plan, v5 key
                dict(plan_json={"plan": "v5"}, config_hash=V5, plan_hash=PLAN_HASH),  # v5 with a hash
                dict(plan_json=_v6_plan_json(), config_hash=V6, plan_hash=None),    # v6 without
                dict(plan_json=_v6_plan_json(), config_hash=V6, plan_hash="0" * 64),  # disagrees
                dict(plan_json=_v6_plan_json(config_hash="1" * 64), config_hash=V6, plan_hash=PLAN_HASH),
            ]
            for r in refusals:
                with pytest.raises(ValueError):
                    await plan_store.mark_ready(db, id6, plan_version="p", skeleton_json=None,
                                                compiler_version="c", segmenter_model=None,
                                                router_model=None, wording_source="placeholder",
                                                cost_usd=Decimal("0"), sha=sha, **r)
            # right plan, wrong row: the v5 key names r5's family, r6 is not in it
            with pytest.raises(RuntimeError, match="no building row"):
                await plan_store.mark_ready(db, id6, plan_json={"plan": "v5-again"}, plan_version="p",
                                            skeleton_json=None, compiler_version="c",
                                            segmenter_model=None, router_model=None,
                                            wording_source="placeholder", cost_usd=Decimal("0"),
                                            sha=sha, config_hash=V5)
        async with get_db_context() as db:
            v5 = await db.get(GradingPlanRecord, id5)
            v6 = await db.get(GradingPlanRecord, id6)
            assert v5.status == "ready" and v5.plan_json == {"plan": "v5"}, "nothing was superseded"
            assert v6.status == "building" and v6.plan_json is None
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


@pytest.mark.db
def test_a_row_keyed_for_another_config_never_gets_a_v5_plan(hobby_json):
    """[plan at save] a non-v5 row reaching run_plan_build goes to the v6 builder, never the v5
    one; a key that is not the ACTIVE v6 configuration's fails loudly and nothing lands."""
    cj = dict(hobby_json, contract_version=str(uuid.uuid4()), rubric_name=f"cfg-{uuid.uuid4().hex[:8]}")
    sha = contract_sha256(cj)

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                    sha=sha, config_hash=V6)
        with patch.object(pbr, "build_plan_for_contract",
                          side_effect=AssertionError("must not build")):
            await pbr._build_claimed_row(row.id, llm_factory=_outage_factory, contract_json=cj)
        async with get_db_context() as db:
            r = await db.get(GradingPlanRecord, row.id)
            assert r.status == "failed" and "v6 configuration changed" in r.error_message
            assert r.plan_json is None
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


# ── the wait bound ──────────────────────────────────────────────────────────

@pytest.mark.db
def test_plan_build_timeout_takes_failed_path(hobby_json, monkeypatch):
    """[AM-G6] The wait on a live builder is bounded by PLAN_WAIT_S and nothing
    else. Running out raises PlanUnavailable — never a hang, never a guess —
    and the grade takes the existing failed path: the graded test lands
    `failed` naming it (retry is the revision chain's), while the plan row is
    left to its builder (still `building`)."""
    from app.config import settings
    from tests.services.test_grading_runner import (MINIMAL_RUBRIC_CONTRACT_JSON,
                                                    MINIMAL_TRANSCRIPTION_CONTRACT_JSON,
                                                    _make_db_mock, _make_graded_test_obj)
    from app.services.grading_runner import _do_grade

    monkeypatch.setattr(pbr, "POLL_S", 0.1)
    assert not hasattr(settings, "plan_build_timeout_s"), "AM-G6: PLAN_BUILD_TIMEOUT_S is deleted"
    late_json = dict(hobby_json, rubric_name=f"late-{uuid.uuid4().hex[:8]}")
    runner_json = dict(MINIMAL_RUBRIC_CONTRACT_JSON, rubric_name=f"late-{uuid.uuid4().hex[:8]}")

    async def a_live_builder_that_never_finishes(contract_json):
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v",
                                                    sha=contract_sha256(contract_json),
                                                    config_hash=V5)
            assert await plan_store.claim_building(db, row.id)     # fresh heartbeat, never lands
            return row.id

    async def resolve_gives_up():
        row_id = await a_live_builder_that_never_finishes(late_json)
        t0 = asyncio.get_event_loop().time()
        with pytest.raises(pbr.PlanUnavailable, match="still building"):
            await pbr.resolve_plan_for_grade(None, late_json, llm_factory=_outage_factory,
                                             wait_s=0.5)
        waited = asyncio.get_event_loop().time() - t0
        assert 0.5 < waited < 2 * 0.5 + 5, waited
        async with get_db_context() as db:
            assert (await db.get(GradingPlanRecord, row_id)).status == "building"

    async def the_grade_fails():
        row_id = await a_live_builder_that_never_finishes(runner_json)
        gt = _make_graded_test_obj(uuid.uuid4(), "grading")
        db = _make_db_mock(gt, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, runner_json)
        with patch("app.services.grading_runner.build_grader") as build_grader:
            await _do_grade(db, gt.id)
        build_grader.assert_not_called()
        assert gt.status == "failed" and gt.draft_json is None
        assert gt.error_message.startswith("PlanUnavailable:") and str(row_id) in gt.error_message
        async with get_db_context() as s:
            assert (await s.get(GradingPlanRecord, row_id)).status == "building"

    try:
        _run(resolve_gives_up())
        monkeypatch.setattr(settings, "grader_architecture", "v5")
        monkeypatch.setattr(settings, "plan_wait_s", 0.3)          # the ONLY knob the runner reads
        _run(the_grade_fails())
    finally:
        _run(_cleanup(contract_sha256(late_json)))
        _run(_cleanup(contract_sha256(runner_json)))


# ── the pin ─────────────────────────────────────────────────────────────────

async def _seed_graded_test():
    from app.models.grading import Rubric
    from app.models.student import Student
    from app.models.transcription import Transcription
    from app.models.user import User

    ids = SimpleNamespace(user=uuid.uuid4(), rubric=uuid.uuid4(), student=uuid.uuid4(),
                          transcription=uuid.uuid4(), graded=uuid.uuid4())
    tag = uuid.uuid4().hex[:8]
    async with get_db_context() as db:
        db.add(User(id=ids.user, email=f"plan_pin_{tag}@s2test.com", full_name="Pin Test",
                    password_hash="x"))
        await db.flush()
        db.add(Rubric(id=ids.rubric, user_id=ids.user, name=f"pin-{tag}", contract_version="cv",
                      contract_json={"contract_version": "cv"}))
        db.add(Student(id=ids.student, user_id=ids.user, full_name=f"תלמידה {tag}"))
        await db.flush()
        path = f"transcriptions/{ids.user}/{uuid.uuid4()}.pdf"
        db.add(Transcription(id=ids.transcription, user_id=ids.user, rubric_id=ids.rubric,
                             student_id=ids.student, gcs_uri=f"gs://b/{path}", gcs_bucket="b",
                             gcs_object_path=path, filename="pin.pdf",
                             draft_json={"page_count": 1, "answers": [], "annotations": []},
                             contract_json={"answers": [], "contract_version": "tcv"},
                             approved_at=datetime.now(timezone.utc), status="approved"))
        await db.flush()
        db.add(GradedTest(id=ids.graded, user_id=ids.user, rubric_id=ids.rubric,
                          transcription_id=ids.transcription, student_id=ids.student,
                          rubric_contract_version="cv", transcription_contract_version="tcv",
                          student_name="x", status="grading"))
        await db.commit()
    return ids


async def _teardown(ids):
    from sqlalchemy import text
    async with get_db_context() as db:
        for table, key in (("graded_tests", ids.graded), ("transcriptions", ids.transcription),
                           ("students", ids.student), ("rubrics", ids.rubric), ("users", ids.user)):
            await db.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": key})
        await db.commit()


@pytest.mark.db
def test_graded_test_pins_plan_hash():
    """The runner's draft write stamps the plan into graded_tests.plan_hash (035)
    in the SAME commit as grading → draft; the pin survives a re-read, is
    idempotent, and is never moved or filled with something that is not a
    plan hash. A row created by /grade starts unpinned (NULL)."""
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed_graded_test()
        async with get_db_context() as db:
            gt = await db.get(GradedTest, ids.graded)
            assert gt.plan_hash is None, "a pending/grading row carries no pin"
            pin_plan_hash(gt, PLAN_HASH)                     # the runner's draft write:
            gt.draft_json = {"scope_outcomes": [], "plan_hash": PLAN_HASH}
            gt.status = "draft"
            gt.draft_created_at = datetime.now(timezone.utc)
            await db.commit()
        async with get_db_context() as db:
            gt = await db.get(GradedTest, ids.graded)
            assert gt.status == "draft" and gt.plan_hash == PLAN_HASH
            pin_plan_hash(gt, PLAN_HASH)                     # same pin: a no-op
            with pytest.raises(PlanPinConflict):
                pin_plan_hash(gt, "0" * 64)                  # a pin is never moved
            for bad in (None, "", "v5", V6[:63], PLAN_HASH.upper()):
                with pytest.raises(ValueError):
                    pin_plan_hash(gt, bad)
            assert gt.plan_hash == PLAN_HASH
    try:
        _run(scenario())
    finally:
        if ids is not None:
            _run(_teardown(ids))


@pytest.mark.db
def test_a_manual_edit_successor_carries_the_pin_and_a_regrade_resolves_its_own():
    """The pin travels with the draft it describes: manual_edit copies the
    draft verbatim (and so its plan); regrade / retry start without a draft and
    resolve the plan current for the new row (§5.7)."""
    from app.services.graded_test_revision import extend_chain

    def source():
        return GradedTest(id=uuid.uuid4(), user_id=uuid.uuid4(), rubric_id=uuid.uuid4(),
                          transcription_id=uuid.uuid4(), student_id=uuid.uuid4(),
                          student_name="x", rubric_contract_version="cv",
                          transcription_contract_version="tcv", status="approved",
                          draft_json={"d": 1}, plan_hash=PLAN_HASH)

    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    src = source()
    edited = _run(extend_chain(db, src, new_status="draft", new_rubric_contract_version="cv",
                               new_draft_json=src.draft_json))
    assert edited.plan_hash == PLAN_HASH
    for status in ("pending",):                              # regrade and retry
        src = source()
        regraded = _run(extend_chain(db, src, new_status=status, new_rubric_contract_version="cv2",
                                     new_draft_json=None))
        assert regraded.plan_hash is None
