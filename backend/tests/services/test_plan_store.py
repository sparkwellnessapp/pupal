"""
grading_plans — the store (PLAN_production_wiring.md §3/§7; W-1, OD-W4).

Real database (Vivi-Test), zero mocks: the guarantees under test are the
partial unique index, the CHECK, and the transitions — none of which a mock
can exercise.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from app.database import get_db_context
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_store
from app.services.plan_store import contract_sha256


def _run(coro):
    return asyncio.run(coro)


def _sha():
    return "test-" + uuid.uuid4().hex


async def _cleanup(sha):
    async with get_db_context() as db:
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.contract_sha256 == sha))
        await db.commit()


# ── the hash ────────────────────────────────────────────────────────────────

def test_the_hash_is_canonical_and_blind_to_contract_version():
    """Two serialisations, one digest; the compile-time UUID never moves it
    (OD-W4): identical content reuses its plan."""
    a = {"b": 1, "a": {"y": "שלום", "x": [1, 2]}, "contract_version": str(uuid.uuid4())}
    b = json.loads(json.dumps({"a": {"x": [1, 2], "y": "שלום"}, "b": 1,
                               "contract_version": str(uuid.uuid4())}, ensure_ascii=True))
    assert contract_sha256(a) == contract_sha256(b)
    assert contract_sha256({"a": 1}) != contract_sha256({"a": 2})
    assert len(contract_sha256(a)) == 64


def test_the_hash_of_a_real_contract_is_stable_across_model_round_trips():
    from tests.grading_eval_suite.fixtures import load_bundle
    from app.schemas.ontology_types import GradingRubricContract

    c = load_bundle("dan_basiuk").rubric_contract
    d1 = c.model_dump(mode="json")
    d2 = GradingRubricContract.model_validate(d1).model_dump(mode="json")
    d2["contract_version"] = str(uuid.uuid4())
    assert contract_sha256(d1) == contract_sha256(d2)


# ── lifecycle ───────────────────────────────────────────────────────────────

def test_queued_to_building_to_ready_and_a_rebuild_supersedes():
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            row, created = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            assert created and row.status == "queued"
            assert await plan_store.claim_building(db, row.id)
            assert not await plan_store.claim_building(db, row.id), "a second claim must lose"
            await plan_store.mark_ready(db, row.id, plan_json={"plan": 1}, plan_version="p1",
                                        skeleton_json=None, compiler_version="c", segmenter_model=None,
                                        router_model=None, wording_source="placeholder",
                                        cost_usd=Decimal("0.1234"), sha=sha)
            ready = await plan_store.get_ready(db, sha)
            assert ready.id == row.id and ready.plan_json == {"plan": 1} and ready.built_at is not None
            assert ready.cost_usd == Decimal("0.1234")
            # a rebuild: a NEW row; the old ready row is superseded, its plan_json untouched
            row2, created2 = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            assert not created2 and row2.id == row.id, "one LIVE row per hash: ready blocks a new queued"
        # supersede path: mark the ready row superseded by building a fresh one through the API
        async with get_db_context() as db:
            await db.execute(update(GradingPlanRecord).where(GradingPlanRecord.id == row.id)
                             .values(status="superseded"))
            await db.commit()
            row3, created3 = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            assert created3
            assert await plan_store.claim_building(db, row3.id)
            await plan_store.mark_ready(db, row3.id, plan_json={"plan": 2}, plan_version="p2",
                                        skeleton_json=None, compiler_version="c", segmenter_model="m",
                                        router_model=None, wording_source="segmented",
                                        cost_usd=Decimal("0.2"), sha=sha)
            ready = await plan_store.get_ready(db, sha)
            assert ready.id == row3.id and ready.plan_json == {"plan": 2}
            old = await db.get(GradingPlanRecord, row.id)
            assert old.status == "superseded" and old.plan_json == {"plan": 1}, "append-only"
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_two_writers_race_and_the_index_decides():
    sha = _sha()

    async def scenario():
        async with get_db_context() as a, get_db_context() as b:
            ra, ca = await plan_store.insert_queued(a, rubric_id=None, contract_version="v", sha=sha)
            rb, cb = await plan_store.insert_queued(b, rubric_id=None, contract_version="v", sha=sha)
            assert ca and not cb and rb.id == ra.id
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_a_failed_row_is_history_and_a_new_build_can_start():
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            await plan_store.claim_building(db, row.id)
            await plan_store.mark_failed(db, row.id, "CompilerBug: x")
            assert await plan_store.find_live(db, sha) is None
            row2, created = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            assert created and row2.id != row.id
            failed = await db.get(GradingPlanRecord, row.id)
            assert failed.status == "failed" and failed.error_message.startswith("CompilerBug")
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_a_dead_builder_can_be_claimed_only_when_its_heartbeat_is_stale():
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            await plan_store.claim_building(db, row.id)
            now = datetime.now(timezone.utc)
            assert not await plan_store.claim_building(db, row.id, stale_before=now - timedelta(minutes=5)), \
                "a fresh heartbeat is a live builder"
            await db.execute(update(GradingPlanRecord).where(GradingPlanRecord.id == row.id)
                             .values(updated_at=now - timedelta(minutes=10)))
            await db.commit()
            assert await plan_store.claim_building(db, row.id, stale_before=now - timedelta(minutes=5))
            fresh = await db.get(GradingPlanRecord, row.id)
            await db.refresh(fresh)
            assert fresh.updated_at > now - timedelta(minutes=1)
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_the_check_refuses_a_ready_row_without_a_plan():
    """§0.5: the CHECK is correct; a writer that reaches it is wrong."""
    sha = _sha()

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            with pytest.raises(IntegrityError):
                await db.execute(update(GradingPlanRecord).where(GradingPlanRecord.id == row.id)
                                 .values(status="ready"))
                await db.commit()
            await db.rollback()
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_ensure_plan_for_contract_is_idempotent_on_content():
    contract = {"questions": [{"q": 1}], "contract_version": str(uuid.uuid4())}
    sha = contract_sha256(contract)

    async def scenario():
        first = await plan_store.ensure_plan_for_contract(rubric_id=None, contract_json=contract)
        assert first is not None
        again = dict(contract, contract_version=str(uuid.uuid4()))
        assert await plan_store.ensure_plan_for_contract(rubric_id=None, contract_json=again) is None
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))
