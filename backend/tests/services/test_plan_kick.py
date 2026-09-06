"""
`kick_plan_build` — the compile-time trigger (W-2), service half.

Real database; the enqueue is patched (the substrate is the job's concern).
Pinned: one queued row per contract content, the enqueue receives that row,
an unchanged re-save kicks nothing, and the kick never raises.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import delete

from app.database import get_db_context
from app.models.grading import Rubric
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_store
from app.services.plan_store import contract_sha256, kick_plan_build


def _run(coro):
    return asyncio.run(coro)


def _contract():
    from tests.grading_eval_suite.fixtures import load_bundle
    cj = load_bundle("dan_basiuk").rubric_contract.model_dump(mode="json")
    cj["contract_version"] = str(uuid.uuid4())
    # perturb one field so this test's hash is its own
    cj["rubric_name"] = f"kick-{uuid.uuid4().hex[:8]}"
    return cj


async def _rubric(cj):
    async with get_db_context() as db:
        r = Rubric(name="kick-test", contract_json=cj, contract_version=cj["contract_version"])
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return r.id


async def _cleanup(sha, rubric_id):
    async with get_db_context() as db:
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.contract_sha256 == sha))
        await db.execute(delete(Rubric).where(Rubric.id == rubric_id))
        await db.commit()


def test_kick_inserts_one_queued_row_and_enqueues_it():
    cj = _contract()
    sha = contract_sha256(cj)
    rubric_id = None

    async def scenario():
        nonlocal rubric_id
        rubric_id = await _rubric(cj)
        with patch("app.services.cloud_tasks_service.enqueue_plan_build_task_or_log",
                   new_callable=AsyncMock) as enq:
            row_id = await kick_plan_build(rubric_id)
            assert row_id is not None
            enq.assert_awaited_once_with(row_id)
            # the same content again: nothing new, nothing enqueued
            assert await kick_plan_build(rubric_id) is None
            enq.assert_awaited_once()
        async with get_db_context() as db:
            live = await plan_store.find_live(db, sha)
            assert live is not None and live.status == "queued" and live.rubric_id == rubric_id
            assert live.contract_version == cj["contract_version"]
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha, rubric_id))


def test_kick_never_raises():
    async def scenario():
        assert await kick_plan_build(uuid.uuid4()) is None          # no such rubric
        with patch("app.services.plan_store.ensure_plan_for_contract",
                   side_effect=RuntimeError("db down")):
            assert await kick_plan_build(uuid.uuid4()) is None
    _run(scenario())
