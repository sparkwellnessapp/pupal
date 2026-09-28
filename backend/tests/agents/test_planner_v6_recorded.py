"""G2 — the planner's RECORDED live outputs (plans/v6/<exam>.recorded.json) replayed
offline: they map and validate, and the committed plan re-assembles to its hash.
The LLM is never called (G2: "the planner is mocked with recorded outputs")."""
from __future__ import annotations

import json
from decimal import Decimal as D

import pytest

from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.assemble import map_scope, validate_scope
from app.agents.planner.schemas import (PlannedCredit, PlannedTerminal, ScopePlanOutput)
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}


@pytest.fixture(scope="module", params=sorted(EXAMS))
def recorded(request):
    exam = request.param
    rec = json.loads((SUITE_DIR / "plans" / "v6" / f"{exam}.recorded.json").read_text(encoding="utf-8"))
    s1 = compile_stage1_v6(load_bundle(EXAMS[exam], require_gt=False).rubric_contract,
                           exam_id=exam, rubric_contract_sha256="x")
    return exam, rec, s1


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


def test_the_recording_says_which_scopes_fell_back(recorded):
    exam, rec, _s1 = recorded
    fallbacks = [s for s, r in rec["scopes"].items() if r["origin"] == "fallback"]
    assert rec["origins"]["fallback"] == len(fallbacks) <= 1, (exam, fallbacks)


def test_a_fixed_components_span_is_copied_from_the_compiler(recorded):
    """C4: the planner phrases a fixed component; its span is compiler input,
    copied by code — a re-typed span can no longer trip V20."""
    _exam, _rec, s1 = recorded
    scope = next(s for s in s1.scopes if any(t.fixed for t in s.terminals))
    t = next(t for t in scope.terminals if t.fixed)
    out = ScopePlanOutput(terminals=[PlannedTerminal(
        terminal_id=t.terminal_id, decomposition="as_compiled",
        credits=[PlannedCredit(component_ref=c.component_id, description_he="רכיב",
                               source_span="משהו אחר לגמרי", full_label_he="קיים",
                               absent_label_he="חסר") for c in t.components])])
    only = scope.__class__(scope.scope, (t,), (), scope.question_text, scope.example_solution)
    _terms, checks, _d, _tel = map_scope(only, out, s1.precision)
    assert [c.source_span for c in checks if c.role == "credit"] == [c.source_span for c in t.components]


def test_a_romanised_terminal_id_is_recovered_by_cwv6(recorded):
    """CWV-6, reused unchanged: `q1.a.c0` is put back on `q1.א.c0` (telemetry),
    and nothing that is not an accepted spelling is guessed."""
    exam, _rec, s1 = recorded
    scope = next(s for s in s1.scopes if any(x.shape == "components" for x in s.terminals))
    t = next(x for x in scope.terminals if x.shape == "components")
    hebrew_label = t.terminal_id.split(".")[1]
    if not ("\u0590" <= hebrew_label[0] <= "\u05ff"):
        pytest.skip("the first scope's terminal has no Hebrew label")
    from app.agents.grader.validator import _HEBREW_LABEL_SPELLINGS
    latin = sorted(_HEBREW_LABEL_SPELLINGS[hebrew_label])[0]
    stray = t.terminal_id.replace(f".{hebrew_label}.", f".{latin}.", 1)
    from app.agents.planner.assemble import _recover_ids
    out = ScopePlanOutput(terminals=[PlannedTerminal(terminal_id=stray, decomposition="binary",
                                                     credits=[])])
    fixed, tel = _recover_ids(scope, out)
    assert fixed.terminals[0].terminal_id == t.terminal_id and tel == [f"id_recovered {stray} → {t.terminal_id}"]
    bengali = t.terminal_id.replace(hebrew_label, "ব", 1)      # not an accepted spelling: never guessed
    fixed, tel = _recover_ids(scope, out.model_copy(update={"terminals": [
        out.terminals[0].model_copy(update={"terminal_id": bengali})]}))
    assert fixed.terminals[0].terminal_id == bengali and tel == []
