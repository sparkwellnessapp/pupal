"""G2 — the planner's RECORDED live outputs (plans/v6/<exam>.<model>.recorded.json, the
2026-09-30 re-record under AM-G17 aliases) replayed offline: they map and validate, and
each recording re-assembles to the plan hash it recorded. The LLM is never called (G2:
"the planner is mocked with recorded outputs")."""
from __future__ import annotations

import json

import pytest

from app.agents.grader.payload_aliases import ALIAS_PATTERN
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.assemble import map_scope, validate_scope
from app.agents.planner.inputs import SPLIT_REFS
from app.agents.planner.planner import assemble_plan, plan_scope
from app.agents.planner.prompt import PLANNER_PROMPT_VERSION
from app.agents.planner.schemas import (PlannedCredit, PlannedTerminal, ScopePlanOutput)
from app.agents.planner.stage1_input import planner_aliases
from app.agents.grader.plan_schemas import PackRef
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}
RECORDINGS = sorted((SUITE_DIR / "plans" / "v6").glob("*.*.recorded.json"))


def _stage1(exam):
    return compile_stage1_v6(load_bundle(EXAMS[exam], require_gt=False).rubric_contract,
                             exam_id=exam, rubric_contract_sha256="x")


@pytest.fixture(scope="module", params=RECORDINGS, ids=[p.name for p in RECORDINGS])
def recorded(request):
    exam = request.param.name.split(".", 1)[0]
    rec = json.loads(request.param.read_text(encoding="utf-8"))
    return exam, rec, _stage1(exam)


def test_there_is_a_recording_per_exam_and_planner_arm():
    names = {p.name for p in RECORDINGS}
    for exam in EXAMS:
        for model in ("claude-sonnet-5", "claude-sonnet-5.5"):
            assert f"{exam}.{model}.recorded.json" in names


def test_recordings_are_of_the_current_prompt_and_in_alias_space(recorded):
    exam, rec, _s1 = recorded
    assert rec["planner_prompt_version"] == PLANNER_PROMPT_VERSION
    for scope_id, r in rec["scopes"].items():
        for o in r["outputs"]:
            out = ScopePlanOutput.model_validate(o)
            ids = ([t.terminal_id for t in out.terminals]
                   + [c.component_ref for t in out.terminals for c in t.credits]
                   + [f.anchor_terminal_id for f in out.faults]
                   + [x.marker_id for f in out.faults for x in f.options]
                   + [d.marker_id for d in out.dispositions])
            # what the model RETURNED — an unknown alias would be dropped, but a real id
            # here would mean the payload leaked one
            assert all(ALIAS_PATTERN.fullmatch(i) for i in ids), (exam, scope_id, ids)


def test_planner_output_maps_to_checks(recorded):
    """Every scope the live planner planned (or repaired) maps and passes V12–V20."""
    exam, rec, s1 = recorded
    for scope_id, r in rec["scopes"].items():
        if r["origin"] not in ("planner", "repaired"):
            continue
        out = ScopePlanOutput.model_validate(r["outputs"][-1])
        scope = s1.scope(scope_id)
        terminals, checks, disps, _ = map_scope(scope, out, s1.precision)
        assert validate_scope(scope, terminals, checks, disps, s1.precision) == [], (exam, scope_id)


async def test_the_recording_replays_to_its_plan_hash(recorded):
    exam, rec, s1 = recorded
    results = []
    for scope in s1.scopes:
        queue = [ScopePlanOutput.model_validate(o) for o in rec["scopes"].get(scope.scope, {}).get("outputs", [])]

        async def call(system_, user_, q=queue):
            return q.pop(0), {}

        results.append(await plan_scope(scope, precision=s1.precision, system_prompt="S",
                                        user_message="U", call=call))
    assert [r.origin for r in results] == [rec["scopes"][s.scope]["origin"] for s in s1.scopes]
    plan = assemble_plan(results, config_hash=rec["config_hash"], rubric_contract_version="x",
                         pack=PackRef(pack_id="computer_science", pack_version="v1"))
    assert plan.plan_hash == rec["plan_hash"], exam


def test_a_fixed_components_span_is_copied_from_the_compiler():
    """C4: the planner phrases a fixed component; its span is compiler input,
    copied by code — a re-typed span can no longer trip V20."""
    s1 = _stage1("hobby_tvshow")
    scope = next(s for s in s1.scopes if any(t.fixed for t in s.terminals))
    t = next(t for t in scope.terminals if t.fixed)
    only = scope.__class__(scope.scope, (t,), (), scope.question_text, scope.example_solution)
    a = planner_aliases(only).alias
    out = ScopePlanOutput(terminals=[PlannedTerminal(
        terminal_id=a(t.terminal_id), decomposition="as_compiled",
        credits=[PlannedCredit(component_ref=a(c.component_id), description_he="רכיב",
                               source_span="משהו אחר לגמרי", full_label_he="קיים",
                               absent_label_he="חסר") for c in t.components])])
    _terms, checks, _d, _tel = map_scope(only, out, s1.precision)
    assert [c.source_span for c in checks if c.role == "credit"] == [c.source_span for c in t.components]
    assert SPLIT_REFS == tuple(f"n{i}" for i in range(1, 7))
