"""
A provider outage is not a plan (owner OK 2026-10-18).

Seen live: a v6 plan built at save during an Anthropic credit outage finished in 7 s at $0, every
scope on the deterministic fallback, and was cached `ready` — so every later grade of that rubric
would have used it, a re-save could not replace it, and no billing alert fired.

  * when EVERY planned scope fell back because its planner CALL failed, the build raises
    `PlannerUnavailable` chained to the provider's error: the row lands `failed` and the A-8
    billing alert fires;
  * a refused output (content) and a partial outage still land a placeholder plan, as before;
  * a grade that builds in place during an outage fails ONCE (retryable) — it never re-inserts
    and rebuilds round after round until the task deadline;
  * once the provider is back, the next grade builds a real row in place.

No provider is called: the planner call and the grader's model are injected.
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.agents.planner.planner import ScopePlanResult
from app.agents.planner.schemas import ScopePlanOutput
from app.config import settings
from app.database import get_db_context
from app.models.grading import GradedTest
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_build_runner as pbr
from app.services.plan_build_v6 import PlannerUnavailable, build_plan_v6, provider_outage
from app.services.plan_store import contract_sha256, kick_plan_build
from app.services.provider_billing import PROVIDER_BILLING_EXHAUSTED, is_billing_exhausted
from tests.agents.test_grader_v6 import _Fake, _full
from tests.grading_eval_suite.fixtures import load_bundle
from tests.services.test_grading_runner_v6 import _seed, _teardown
from tests.services.test_provider_billing import anthropic_credit_too_low


def _r(origin, call_error=None):
    return ScopePlanResult("q", origin, [], [], [], call_error=call_error)


async def _refused(system, user):
    return ScopePlanOutput(terminals=[]), {}


async def _no_credit(system, user):
    raise anthropic_credit_too_low()


# ── the rule, pure ──────────────────────────────────────────────────────────

def test_an_outage_is_every_planned_scope_failing_its_call():
    e = RuntimeError("down")
    assert provider_outage([_r("fallback", e), _r("fallback", e), _r("compiled")]) is e


def test_a_billing_cause_is_preferred_so_the_alert_names_it():
    other, bill = RuntimeError("timeout"), anthropic_credit_too_low()
    assert provider_outage([_r("fallback", other), _r("fallback", bill)]) is bill


@pytest.mark.parametrize("results", [
    pytest.param([_r("fallback", RuntimeError()), _r("planner")], id="partial-outage"),
    pytest.param([_r("fallback", RuntimeError()), _r("repaired")], id="partial-outage-repaired"),
    pytest.param([_r("fallback"), _r("fallback")], id="refused-output-is-content"),
    pytest.param([_r("compiled"), _r("compiled")], id="nothing-needed-the-planner"),
    pytest.param([], id="no-scopes"),
])
def test_not_an_outage(results):
    assert provider_outage(results) is None


# ── the builder ─────────────────────────────────────────────────────────────

def test_the_builder_refuses_an_outage_chained_to_the_provider_error():
    contract = load_bundle("din_ezra", require_gt=False).rubric_contract
    with pytest.raises(PlannerUnavailable) as ei:
        asyncio.run(build_plan_v6(contract, sha="x", call=_no_credit))
    assert is_billing_exhausted(ei.value), "the chain reaches the provider's billing error"


def test_a_refused_output_still_lands_a_placeholder_plan():
    contract = load_bundle("din_ezra", require_gt=False).rubric_contract
    plan, _tel, _cost, wording = asyncio.run(build_plan_v6(contract, sha="x", call=_refused))
    assert wording == "placeholder" and plan.terminals


# ── end to end on the test DB ───────────────────────────────────────────────

def _v6(monkeypatch, planner):
    monkeypatch.setattr(settings, "grader_architecture", "v6")
    monkeypatch.setattr(settings, "v6_explainer_model", "")
    monkeypatch.setattr(settings, "feedback_model_key", "")
    monkeypatch.setattr("app.agents.planner.planner_llm.build_planner_call", lambda **kw: planner)
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model",
                        lambda *a, **kw: _Fake(_full))


async def _rows(sha):
    async with get_db_context() as db:
        return (await db.execute(select(GradingPlanRecord).where(
            GradingPlanRecord.contract_sha256 == sha))).scalars().all()


@pytest.mark.db
def test_a_build_at_save_in_an_outage_fails_and_alerts_then_the_grade_rebuilds(monkeypatch, caplog):
    from app.services.grading_runner import run_grading
    bundle = load_bundle("din_ezra", require_gt=False)
    sha = contract_sha256(bundle.rubric_contract.model_dump(mode="json"))
    down = {"now": True}

    async def planner(system, user):
        if down["now"]:
            raise anthropic_credit_too_low()
        return await _refused(system, user)

    _v6(monkeypatch, planner)
    caplog.set_level(logging.CRITICAL, logger="app.services.provider_billing")
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle, n_tests=1)
        with patch("app.services.cloud_tasks_service.enqueue_plan_build_task_or_log",
                   new_callable=AsyncMock):
            row_id = await kick_plan_build(ids.rubric)
        assert await pbr.run_plan_build(row_id)
        async with get_db_context() as db:
            row = await db.get(GradingPlanRecord, row_id)
            assert row.status == "failed" and "PlannerUnavailable" in row.error_message
            assert row.plan_json is None, "an outage is never cached as a plan"
        alerts = [r.getMessage() for r in caplog.records
                  if r.getMessage().startswith(PROVIDER_BILLING_EXHAUSTED)]
        assert any("site=plan_build_v6" in m for m in alerts), alerts

        down["now"] = False                                       # credit is back
        assert await run_grading(ids.graded[0])
        async with get_db_context() as db:
            gt = await db.get(GradedTest, ids.graded[0])
            assert gt.status == "draft", gt.error_message
        ready = [r for r in await _rows(sha) if r.status == "ready"]
        assert len(ready) == 1 and ready[0].id != row_id and gt.plan_hash == ready[0].plan_hash
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))


@pytest.mark.db
def test_a_grade_in_an_outage_fails_after_ONE_build_never_a_rebuild_loop(monkeypatch):
    from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
    from app.services.grading_runner import run_grading
    bundle = load_bundle("din_ezra", require_gt=False)
    sha = contract_sha256(bundle.rubric_contract.model_dump(mode="json"))
    planned = sum(1 for s in compile_stage1_v6(bundle.rubric_contract, exam_id="x",
                                               rubric_contract_sha256=sha).scopes if s.needs_planner)
    calls = []

    async def planner(system, user):
        calls.append(1)
        raise anthropic_credit_too_low()

    _v6(monkeypatch, planner)
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle, n_tests=1)
        await asyncio.wait_for(run_grading(ids.graded[0]), timeout=60)
        async with get_db_context() as db:
            gt = await db.get(GradedTest, ids.graded[0])
            assert gt.status == "failed" and "plan" in (gt.error_message or "").lower(), gt.error_message
        assert len(calls) == planned, f"one build round ({planned} scopes), got {len(calls)} calls"
        assert [r.status for r in await _rows(sha)] == ["failed"]
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))
