"""
The plan builder and the grade-time resolver (PLAN_production_wiring.md §5/§6.2).

Real database (Vivi-Test); the model is a FAKE injected through `llm_factory`
— no provider is ever called (and the root conftest makes the default factory
refuse, structurally). What is pinned:

  * a faithful model → `segmented`, cost accounted, the plan validates;
  * a provider outage → `placeholder`, STILL ready (W-2), the outage recorded;
  * an envelope overrun mid-segment → what was worded is kept, the rest is
    substituted (OD-W10), still `segmented`;
  * a CompilerBug → `failed` — the only way there;
  * resolve: ready → use; absent → build in place; failed → a new build;
    dead builder → claimed and built; live builder → waited for.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, update

from app.agents.plan_compiler.route import RoutedComponent, RouterResponse
from app.agents.plan_compiler.segment import SegmentedSlot, SegmenterResponse, substitute
from app.agents.plan_compiler.skeleton import CompilerBug
from app.database import get_db_context
from app.models.grading import Rubric
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_build_runner as pbr
from app.services import plan_store
from app.services.plan_store import contract_sha256


def _run(coro):
    return asyncio.run(coro)


# ── the fake model (the grader agents' surface) ─────────────────────────────

class _Runner:
    def __init__(self, llm, schema):
        self.llm, self.schema = llm, schema

    async def ainvoke(self, messages):
        self.llm.calls += 1
        parsed = self.llm.respond(messages[-1].content, self.schema)
        return {"raw": SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 300,
                                                       "input_token_details": {}},
                                       response_metadata={"model_name": "fake"}),
                "parsed": parsed, "parsing_error": None}


class FakeLLM:
    def __init__(self, respond):
        self.respond, self.calls = respond, 0

    def with_structured_output(self, schema, include_raw=True):
        return _Runner(self, schema)


def _slot_ids_in(message):
    return [line.split("slot ")[1].split(" ")[0] for line in message.splitlines()
            if line.strip().startswith("· slot ") and "." in line.split("slot ")[1].split(" ")[0]]


def _faithful_factory(skeleton_holder, solutions):
    """A factory whose segmenter echoes the skeleton's own spans and whose
    router names three components from the solution."""
    def respond(message, schema):
        if schema is RouterResponse:
            tid = message.splitlines()[0].split("TERMINAL: ")[1]
            scope = skeleton_holder["sk"].terminal(tid).scope
            lines = [l.strip() for l in solutions[scope].splitlines() if len(l.strip()) >= 12][:3]
            return RouterResponse(components=[RoutedComponent(evidence_span=l, name_he=f"רכיב {i}")
                                              for i, l in enumerate(lines, 1)])
        sk = skeleton_holder["sk"]
        by_slot = {s.slot_id: (t, s) for t in sk.terminals for s in t.slots}
        entries = []
        for sid in _slot_ids_in(message):
            t, s = by_slot[sid]
            d, q, n = substitute(s, t)
            entries.append(SegmentedSlot(slot_id=sid, rubric_quote=q or "", description_he=d,
                                         equivalence_note=n or ""))
        return SegmenterResponse(entries=entries)

    def factory(model_key):
        return FakeLLM(respond)
    return factory


def _outage_factory(model_key):
    def respond(message, schema):
        raise ConnectionError("provider down")
    return FakeLLM(respond)


@pytest.fixture(scope="module")
def hobby():
    from tests.grading_eval_suite.fixtures import load_bundle
    from app.agents.plan_compiler import compile_contract
    from app.agents.plan_compiler.context import scope_maps
    b = load_bundle("dan_basiuk")
    c = b.rubric_contract
    corpora, solutions, questions = scope_maps(c)
    return dict(contract=c, contract_json=c.model_dump(mode="json"), solutions=solutions)


def _holder(hobby):
    """The router reshapes the skeleton, so the segmenter fake must read the
    CURRENT skeleton; the builder does not expose it, so the fake recompiles
    with the same threshold and applies the same routing — good enough for a
    faithful echo because `substitute` needs only the slot ids and spans."""
    from app.agents.plan_compiler import compile_contract
    from app.agents.plan_compiler.route import apply_routing
    from app.config import settings
    sk = compile_contract(hobby["contract"], exam_id="x", rubric_contract_sha256="0" * 64,
                          route_min_points=Decimal(settings.plan_route_min_points))
    holder = {"sk": sk}

    def factory(model_key):
        base = _faithful_factory(holder, hobby["solutions"])(model_key)
        inner = base.respond

        def respond(message, schema):
            out = inner(message, schema)
            if schema is RouterResponse:      # mirror the routing the builder will apply
                tid = message.splitlines()[0].split("TERMINAL: ")[1]
                t = holder["sk"].terminal(tid)
                new = apply_routing(t, out.components, Decimal("0.25"))
                holder["sk"] = holder["sk"].__class__(
                    **{**holder["sk"].__dict__,
                       "terminals": tuple(new if x.terminal_id == tid else x for x in holder["sk"].terminals)})
            return out
        base.respond = respond
        return base
    return factory


# ── build_plan_for_contract ─────────────────────────────────────────────────

def test_a_faithful_model_yields_a_segmented_plan_that_validates(hobby):
    res = _run(pbr.build_plan_for_contract(hobby["contract"], plan_exam_id="rubric-x",
                                           llm_factory=_holder(hobby)))
    assert res.wording_source == "segmented" and res.error_message is None
    assert res.segmenter_model == "claude-haiku-4-5" and res.router_model == "claude-sonnet-5"
    assert res.cost_usd > 0 and res.substituted == 0 and res.router_failed == []
    assert res.plan.plan_version.startswith("rubric-x/compiled-")
    assert res.plan.segmenter_prompt_version == "segmenter/v1"
    # the routed monoliths were split (P ≥ 3 with a solution, OD-W5)
    assert len(res.plan.terminal("q2.א.c1").checks) == 3
    assert res.skeleton_json["build"]["substituted"] == 0


def test_a_provider_outage_still_yields_a_ready_placeholder_plan(hobby):
    res = _run(pbr.build_plan_for_contract(hobby["contract"], plan_exam_id="rubric-x",
                                           llm_factory=_outage_factory))
    assert res.wording_source == "placeholder"
    assert "router" in res.error_message and "segmenter" in res.error_message
    assert res.segmenter_model is None and res.router_model is None and res.cost_usd == 0
    assert len(res.plan.terminals) == 38


def test_an_envelope_overrun_keeps_what_was_worded_and_substitutes_the_rest(hobby):
    factory = _holder(hobby)
    res = _run(pbr.build_plan_for_contract(hobby["contract"], plan_exam_id="rubric-x",
                                           llm_factory=factory, envelope_usd=0.004))
    assert res.wording_source == "segmented"
    assert res.substituted > 0 and "envelope" in res.error_message
    total = sum(len(t.checks) for t in res.plan.terminals)
    assert 0 < res.substituted < total


def test_a_compiler_bug_is_the_only_way_to_fail(hobby, monkeypatch):
    def boom(*a, **k):
        raise CompilerBug("synthetic")
    monkeypatch.setattr(pbr, "compile_contract", boom)
    with pytest.raises(CompilerBug):
        _run(pbr.build_plan_for_contract(hobby["contract"], plan_exam_id="x", llm_factory=_outage_factory))


# ── the row lifecycle through run_plan_build ────────────────────────────────

async def _make_rubric(contract_json):
    async with get_db_context() as db:
        r = Rubric(name="plan-build-test", contract_json=contract_json,
                   contract_version=contract_json["contract_version"])
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return r.id


async def _cleanup(sha, rubric_id=None):
    async with get_db_context() as db:
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.contract_sha256 == sha))
        if rubric_id is not None:
            await db.execute(delete(Rubric).where(Rubric.id == rubric_id))
        await db.commit()


def test_run_plan_build_lands_a_ready_row_and_is_idempotent(hobby):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)
    rubric_id = None

    async def scenario():
        nonlocal rubric_id
        rubric_id = await _make_rubric(cj)
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=rubric_id, contract_version=cj["contract_version"], sha=sha)
        assert await pbr.run_plan_build(row.id, llm_factory=_outage_factory) is True
        assert await pbr.run_plan_build(row.id, llm_factory=_outage_factory) is False, "duplicate delivery"
        async with get_db_context() as db:
            ready = await plan_store.get_ready(db, sha)
            assert ready is not None and ready.wording_source == "placeholder"
            assert ready.plan_version.startswith(f"{rubric_id}/compiled-")
            assert ready.compiler_version == "plan-compiler/v2.0"
            assert ready.error_message and "provider down" in ready.error_message
            assert ready.skeleton_json and "terminals" in ready.skeleton_json
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha, rubric_id))


def test_run_plan_build_marks_failed_on_a_compiler_bug(hobby, monkeypatch):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)
    rubric_id = None

    def boom(*a, **k):
        raise CompilerBug("synthetic")
    monkeypatch.setattr(pbr, "compile_contract", boom)

    async def scenario():
        nonlocal rubric_id
        rubric_id = await _make_rubric(cj)
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=rubric_id, contract_version=cj["contract_version"], sha=sha)
        await pbr.run_plan_build(row.id, llm_factory=_outage_factory)
        async with get_db_context() as db:
            r = await db.get(GradingPlanRecord, row.id)
            assert r.status == "failed" and "CompilerBug" in r.error_message
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha, rubric_id))


# ── resolve_plan_for_grade ──────────────────────────────────────────────────

def test_resolve_builds_in_place_when_no_plan_exists(hobby):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)

    async def scenario():
        res = await pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=5)
        assert res.built_in_place and res.wording_source == "placeholder"
        assert len(res.plan.terminals) == 38
        again = await pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=5)
        assert not again.built_in_place and again.row_id == res.row_id
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_resolve_takes_over_a_dead_builder(hobby):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            await plan_store.claim_building(db, row.id)
            await db.execute(update(GradingPlanRecord).where(GradingPlanRecord.id == row.id)
                             .values(updated_at=datetime.now(timezone.utc) - timedelta(minutes=30)))
            await db.commit()
        res = await pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=5)
        assert res.built_in_place and res.row_id == row.id
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def test_resolve_waits_for_a_live_builder(hobby, monkeypatch):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)
    monkeypatch.setattr(pbr, "POLL_S", 0.2)

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            await plan_store.claim_building(db, row.id)

        async def finish_later():
            await asyncio.sleep(0.6)
            async with get_db_context() as db:
                await plan_store.mark_ready(db, row.id, plan_json=_placeholder_json(hobby), plan_version="p",
                                            skeleton_json=None, compiler_version="c", segmenter_model=None,
                                            router_model=None, wording_source="placeholder",
                                            cost_usd=Decimal("0"), sha=sha)
        task = asyncio.create_task(finish_later())
        res = await pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=5)
        await task
        assert not res.built_in_place and res.row_id == row.id and res.waited_s >= 0.5
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))


def _placeholder_json(hobby):
    from app.agents.plan_compiler import compile_contract
    from app.agents.plan_compiler.assemble import assemble_placeholder_plan
    sk = compile_contract(hobby["contract"], exam_id="x", rubric_contract_sha256="0" * 64)
    return assemble_placeholder_plan(sk).model_dump(mode="json")


def test_resolve_after_a_failed_build_starts_a_new_one(hobby):
    cj = dict(hobby["contract_json"], contract_version=str(uuid.uuid4()))
    sha = contract_sha256(cj)

    async def scenario():
        async with get_db_context() as db:
            row, _ = await plan_store.insert_queued(db, rubric_id=None, contract_version="v", sha=sha)
            await plan_store.claim_building(db, row.id)
            await plan_store.mark_failed(db, row.id, "CompilerBug: old")
        res = await pbr.resolve_plan_for_grade(None, cj, llm_factory=_outage_factory, wait_s=5)
        assert res.built_in_place and res.row_id != row.id
    try:
        _run(scenario())
    finally:
        _run(_cleanup(sha))
