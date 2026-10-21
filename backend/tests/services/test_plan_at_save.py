"""
Plan at save (owner 2026-10-18): under GRADER_ARCHITECTURE=v6 the rubric's v6 plan builds in the
background when the rubric is saved, so the teacher's first grade finds it ready.

  * the save queues the v6 plan (its config key) and NO v5 plan — a plan no grader reads is
    spend for nothing;
  * a rubric re-saved with other content before its build starts makes the older job skip
    (superseded) instead of filing the new contract's plan under the old key;
  * the background build is the v6 builder, and a later grade reuses its plan;
  * a v6 grade waiting on a live builder gets 2 × plan_wait_s + the 2-minute grace (600 s)
    before it fails as retryable.

Real database where the guarantee lives in it; no provider is ever called (the planner call
and the grader's model are injected, as in `test_grading_runner_v6`).
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import get_db_context
from app.models.grading import GradedTest, Rubric
from app.models.grading_plan import GradingPlanRecord
from app.services import cloud_tasks_service as cts
from app.services import plan_build_runner as pbr
from app.services import plan_store
from app.services.plan_build_v6 import v6_config_hash, wait_bound_s
from app.services.plan_store import V5_CONFIG_HASH as V5, contract_sha256, kick_plan_build
from tests.agents.test_grader_v6 import _Fake, _full
from tests.grading_eval_suite.fixtures import load_bundle
from tests.services.test_grading_runner_v6 import _seed, _teardown


# ── the wait ────────────────────────────────────────────────────────────────

def test_a_v6_grade_waits_600s_by_default_inside_the_dispatch_deadline():
    assert settings.plan_wait_grace_s == 120                     # the owner's two minutes
    assert wait_bound_s(settings.plan_wait_s) == 600.0
    assert wait_bound_s(settings.plan_wait_s) < cts._DISPATCH_DEADLINE_SECONDS


# ── the save: the v6 plan, and no v5 plan ───────────────────────────────────

def _planner(calls):
    async def planner_refused(system, user):                # every scope's output is refused → the
        from app.agents.planner.schemas import ScopePlanOutput   # fallback (content, not an outage)
        calls.append(1)
        return ScopePlanOutput(terminals=[]), {}
    return planner_refused


@pytest.mark.db
def test_under_v6_the_save_queues_the_v6_plan_builds_it_in_the_background_and_a_grade_reuses_it(
        monkeypatch):
    from app.services.grading_runner import run_grading
    bundle = load_bundle("din_ezra", require_gt=False)
    cj = bundle.rubric_contract.model_dump(mode="json")
    sha = contract_sha256(cj)
    calls = []
    monkeypatch.setattr(settings, "grader_architecture", "v6")
    monkeypatch.setattr(settings, "v6_explainer_model", "")
    monkeypatch.setattr(settings, "feedback_model_key", "")
    monkeypatch.setattr("app.agents.planner.planner_llm.build_planner_call",
                        lambda **kw: _planner(calls))
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model",
                        lambda *a, **kw: _Fake(_full))
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle, n_tests=1)
        with patch("app.services.cloud_tasks_service.enqueue_plan_build_task_or_log",
                   new_callable=AsyncMock) as enq:
            row_id = await kick_plan_build(ids.rubric)
        assert row_id is not None
        enq.assert_awaited_once_with(row_id)                     # at once, no delay
        async with get_db_context() as db:
            rows = (await db.execute(select(GradingPlanRecord).where(
                GradingPlanRecord.contract_sha256 == sha))).scalars().all()
            assert [(r.id, r.config_hash, r.status) for r in rows] == \
                [(row_id, v6_config_hash(bundle.rubric_contract), "queued")], "no v5 row"
            assert all(r.config_hash != V5 for r in rows)

        assert await pbr.run_plan_build(row_id)                   # the Cloud Task
        built_calls = len(calls)
        assert built_calls > 0
        async with get_db_context() as db:
            row = await db.get(GradingPlanRecord, row_id)
            assert row.status == "ready" and row.plan_hash

        assert await run_grading(ids.graded[0])                   # her first grade
        assert len(calls) == built_calls, "the grade reused the background plan"
        async with get_db_context() as db:
            gt = await db.get(GradedTest, ids.graded[0])
            assert gt.status == "draft", gt.error_message
            assert gt.plan_hash == row.plan_hash
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))


@pytest.mark.db
def test_under_v5_the_save_still_queues_the_v5_plan(monkeypatch):
    bundle = load_bundle("din_ezra", require_gt=False)
    cj = bundle.rubric_contract.model_dump(mode="json")
    sha = contract_sha256(cj)
    monkeypatch.setattr(settings, "grader_architecture", "v5")
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle, n_tests=1)
        with patch("app.services.cloud_tasks_service.enqueue_plan_build_task_or_log",
                   new_callable=AsyncMock):
            row_id = await kick_plan_build(ids.rubric)
        async with get_db_context() as db:
            row = await db.get(GradingPlanRecord, row_id)
            assert row.config_hash == V5 and row.status == "queued"
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))


# ── a re-save before the build starts ───────────────────────────────────────

@pytest.mark.db
def test_a_build_whose_rubric_was_re_saved_skips_without_spending(monkeypatch):
    bundle = load_bundle("din_ezra", require_gt=False)
    cj = bundle.rubric_contract.model_dump(mode="json")
    sha = contract_sha256(cj)
    calls = []
    monkeypatch.setattr(settings, "grader_architecture", "v6")
    monkeypatch.setattr("app.agents.planner.planner_llm.build_planner_call",
                        lambda **kw: _planner(calls))
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle, n_tests=1)
        with patch("app.services.cloud_tasks_service.enqueue_plan_build_task_or_log",
                   new_callable=AsyncMock):
            row_id = await kick_plan_build(ids.rubric)
        async with get_db_context() as db:                        # she edits and saves again
            rubric = await db.get(Rubric, ids.rubric)
            rubric.contract_json = dict(cj, rubric_name=f"edited-{uuid.uuid4().hex[:8]}")
            await db.commit()
        with patch.object(pbr, "build_plan_for_contract", side_effect=AssertionError("v5 build")):
            assert await pbr.run_plan_build(row_id)
        assert calls == [], "a superseded build never reaches the planner"
        async with get_db_context() as db:
            row = await db.get(GradingPlanRecord, row_id)
            assert row.status == "failed" and row.error_message.startswith("superseded")
            assert row.plan_json is None
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))
