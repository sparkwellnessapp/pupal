"""grader-v6 Phase 2 — the planner's call, its ONE repair, and the fallback (§5.6).
The LLM is never called: the call is injected and returns canned outputs."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.agents.grader.plan_schemas import MarkerDisposition, PackRef
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.planner import REPAIR_HEADER, assemble_plan, plan_all, plan_scope
from app.agents.planner.schemas import (PlannedCredit, PlannedFault, PlannedFaultOption,
                                        PlannedTerminal, ScopePlanOutput)
from tests.grading_eval_suite.fixtures import load_bundle

G = D("0.25")


@pytest.fixture(scope="module")
def hobby():
    return compile_stage1_v6(load_bundle("din_ezra", require_gt=False).rubric_contract,
                             exam_id="hobby_tvshow", rubric_contract_sha256="x")


def _credit(ref, span):
    return PlannedCredit(component_ref=ref, description_he="רכיב", source_span=span,
                         full_label_he="קיים", absent_label_he="חסר")


def _valid(scope):
    terms = [PlannedTerminal(terminal_id=t.terminal_id,
                             decomposition="as_compiled" if t.fixed else "binary",
                             credits=[_credit(c.component_id, c.source_span) for c in t.components])
             for t in scope.terminals]
    faults = [PlannedFault(anchor_terminal_id=m.home_terminal_id, description_he="טעות",
                           options=[PlannedFaultOption(marker_id=m.marker_id, label_he="נמצאה")])
              for m in scope.markers]
    return ScopePlanOutput(terminals=terms, faults=faults,
                           dispositions=[MarkerDisposition(marker_id=m.marker_id, disposition="fault")
                                         for m in scope.markers])


def _invalid(scope):
    """A fixed terminal re-decomposed — a structural mistake the mapping refuses."""
    out = _valid(scope)
    fixed = next(i for i, t in enumerate(scope.terminals) if t.fixed)
    bad = out.terminals[fixed].model_copy(update={"decomposition": "split"})
    return out.model_copy(update={"terminals": out.terminals[:fixed] + [bad] + out.terminals[fixed + 1:]})


class _Script:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    async def __call__(self, system, user):
        self.calls.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, {"input_tokens": 1, "output_tokens": 1}


async def test_repair_called_once_with_validator_messages(hobby):
    scope = hobby.scope("q1.ג")
    call = _Script(_invalid(scope), _valid(scope))
    r = await plan_scope(scope, precision=G, system_prompt="S", user_message="U", call=call)
    assert r.origin == "repaired" and len(call.calls) == 2
    repair_user = call.calls[1][1]
    assert repair_user.startswith("U") and REPAIR_HEADER in repair_user
    for msg in r.errors:                                   # the validator's words, verbatim
        assert f"- {msg}" in repair_user
    assert any("as_compiled" in m for m in r.errors)


async def test_a_failed_repair_falls_back_and_never_calls_a_third_time(hobby):
    scope = hobby.scope("q1.ג")
    call = _Script(_invalid(scope), _invalid(scope), _valid(scope))
    r = await plan_scope(scope, precision=G, system_prompt="S", user_message="U", call=call)
    assert r.origin == "fallback" and len(call.calls) == 2
    assert r.telemetry == ["planner_fallback q1.ג: repair_failed"]
    assert all(c.origin in ("fallback", "compiler") for c in r.checks)


async def test_a_failed_call_falls_back_without_repair(hobby):
    scope = hobby.scope("q1.ג")
    call = _Script(RuntimeError("provider down"))
    r = await plan_scope(scope, precision=G, system_prompt="S", user_message="U", call=call)
    assert (r.origin, len(call.calls)) == ("fallback", 1)
    assert r.telemetry == ["planner_fallback q1.ג: call_failed: RuntimeError"]


async def test_the_whole_exam_plans_and_assembles_into_one_hashed_plan(hobby):
    outputs = {s.scope: _valid(s) for s in hobby.scopes}

    async def call(system, user):
        return outputs[user], {}

    results = await plan_all(hobby, system_prompt="S", render=lambda s: s.scope, call=call)
    assert [r.origin for r in results] == ["planner"] * len(hobby.scopes)
    plan = assemble_plan(results, config_hash="c", rubric_contract_version="v",
                         pack=PackRef(pack_id="computer_science", pack_version="1"))
    again = assemble_plan(results, config_hash="c", rubric_contract_version="v",
                          pack=PackRef(pack_id="computer_science", pack_version="1"))
    assert plan.plan_hash == again.plan_hash and len(plan.terminals) == 38
