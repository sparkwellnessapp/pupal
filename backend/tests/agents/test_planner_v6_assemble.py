"""grader-v6 Phase 2 — the planner contract, mapping and fallback (§5.3, §5.6). Pure."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.agents.grader.plan_schemas import DeductionMarker, MarkerDisposition, PartialFraction
from app.agents.plan_compiler.stage1_v6 import V6Component, V6Scope, V6Terminal, compile_stage1_v6
from app.agents.planner.assemble import (MappingError, fallback_scope, map_scope, point_free,
                                         validate_scope)
from app.agents.planner.schemas import (PlannedCredit, PlannedFault, PlannedFaultOption,
                                        PlannedPartial, PlannedTerminal, ScopePlanOutput)
from tests.grading_eval_suite.fixtures import load_bundle

G = D("0.25")
EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}


@pytest.fixture(scope="module")
def stage1():
    return {e: compile_stage1_v6(load_bundle(f, require_gt=False).rubric_contract, exam_id=e,
                                 rubric_contract_sha256="x") for e, f in EXAMS.items()}


def test_planner_schema_has_no_numeric_fields():
    """D-LAW-2 / P-10: the planner never emits a number — no integer or number
    type anywhere in the schema it is held to."""
    found = []

    def walk(o, path):
        if isinstance(o, dict):
            if o.get("type") in ("number", "integer"):
                found.append(path)
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(ScopePlanOutput.model_json_schema(), "")
    assert found == []


def _credit(ref, span, desc="רכיב", partials=()):
    return PlannedCredit(component_ref=ref, description_he=desc, source_span=span,
                         full_label_he="קיים ומלא", absent_label_he="חסר",
                         partials=[PlannedPartial(label_he=l, fraction=f) for l, f in partials])


def _as_compiled(t):
    return PlannedTerminal(terminal_id=t.terminal_id, decomposition="as_compiled",
                           credits=[_credit(c.component_id, c.source_span) for c in t.components])


def test_planner_output_maps_to_checks(stage1):
    """A planner output for hobby q1.ג (fixed components, a monolith laddered, faults
    with `requires`) maps onto checks that pass V12–V20; code assigns every id and
    value — the ladder's half is 1.5 of the monolith's 3."""
    scope = stage1["hobby_tvshow"].scope("q1.ג")
    mono = next(t for t in scope.terminals if not t.fixed)
    terms = [_as_compiled(t) if t.fixed else PlannedTerminal(
        terminal_id=t.terminal_id, decomposition="ladder",
        credits=[_credit(t.components[0].component_id, "לולאה על מערך התחביבים",
                         desc="לולאה על מערך התחביבים",
                         partials=[("הלולאה נכונה אך בלי בדיקת null", PartialFraction.HALF)])])
        for t in scope.terminals]
    faults = [PlannedFault(anchor_terminal_id=m.home_terminal_id,
                           requires_component_ref=next(t for t in scope.terminals
                                                       if t.terminal_id == m.home_terminal_id
                                                       ).components[0].component_id,
                           description_he="טעות בחישוב",
                           options=[PlannedFaultOption(marker_id=m.marker_id, label_he="נמצאה הטעות")])
              for m in scope.markers]
    out = ScopePlanOutput(terminals=terms, faults=faults,
                          dispositions=[MarkerDisposition(marker_id=m.marker_id, disposition="fault")
                                        for m in scope.markers])
    terminals, checks, disps, _tel = map_scope(scope, out, G)
    assert validate_scope(scope, terminals, checks, disps, G) == []
    ladder = next(c for c in checks if c.priced_terminal_id == mono.terminal_id and c.role == "credit")
    assert (ladder.shape, [o.value for o in ladder.options]) == ("ladder", [D(3), D("1.5"), D(0)])
    f = next(c for c in checks if c.priced_terminal_id == mono.terminal_id and c.role == "fault")
    assert f.requires == ladder.check_id and [o.value for o in f.options] == [D(0), D(-1)]
    assert all(c.origin in ("planner", "compiler") for c in checks)


def _synthetic(markers_spec, text="בדיקת גבולות הלולאה עם i וגם count", points=4):
    t = V6Terminal("q9.c0", "q9", D(points), text, "components",
                   components=(V6Component("q9.c0.k1", text, D(points)),))
    markers = tuple(DeductionMarker(marker_id=f"q9.c0.m{i}", home_terminal_id="q9.c0", amount=D(a),
                                    polarity="deduct", text_span=span, charge_group=g,
                                    candidate_anchors=["q9.c0"])
                    for i, (a, span, g) in enumerate(markers_spec, start=1))
    return V6Scope("q9", (t,), markers, question_text="שאלה על לולאה", example_solution="")


def test_merge_reason_appended_to_interpretation_notes():
    """P-6: the same condition at two amounts merges; code applies the LENIENT
    amount and appends the planner's reason to the anchor's notes (§5.3)."""
    scope = _synthetic([("2", "אם הלולאה חורגת מהגבול להוריד 2", None),
                        ("1", "אם הלולאה חורגת מהגבול להוריד 1", None)])
    out = ScopePlanOutput(
        terminals=[PlannedTerminal(terminal_id="q9.c0", decomposition="binary",
                                   credits=[_credit("q9.c0.k1", "בדיקת גבולות הלולאה")])],
        faults=[PlannedFault(anchor_terminal_id="q9.c0", requires_component_ref="q9.c0.k1",
                             description_he="חריגה מגבולות הלולאה",
                             options=[PlannedFaultOption(marker_id="q9.c0.m1", label_he="הלולאה חורגת")])],
        dispositions=[MarkerDisposition(marker_id="q9.c0.m1", disposition="fault"),
                      MarkerDisposition(marker_id="q9.c0.m2", disposition="merged",
                                        merged_into_marker_id="q9.c0.m1",
                                        reason_he="אותו תנאי מופיע פעמיים; נבחר הסכום המקל")])
    terminals, checks, disps, _ = map_scope(scope, out, G)
    assert validate_scope(scope, terminals, checks, disps, G) == []
    (fault,) = [c for c in checks if c.role == "fault"]
    assert [o.value for o in fault.options] == [D(0), D(-1)]
    assert terminals[0].interpretation_notes_he == ["אותו תנאי מופיע פעמיים; נבחר הסכום המקל"]


def test_a_fixed_terminal_refuses_a_new_decomposition_with_a_repairable_message(stage1):
    scope = stage1["hobby_tvshow"].scope("q1.ג")
    fixed = next(t for t in scope.terminals if t.fixed)
    bad = PlannedTerminal(terminal_id=fixed.terminal_id, decomposition="split",
                          credits=[_credit("new:1", "x"), _credit("new:2", "y")])
    out = ScopePlanOutput(terminals=[bad] + [_as_compiled(t) if t.fixed else PlannedTerminal(
        terminal_id=t.terminal_id, decomposition="binary",
        credits=[_credit(t.components[0].component_id, "לולאה")]) for t in scope.terminals
        if t.terminal_id != fixed.terminal_id])
    with pytest.raises(MappingError) as e:
        map_scope(scope, out, G)
    assert any("as_compiled" in m and fixed.terminal_id in m for m in e.value.errors)


@pytest.mark.parametrize("exam", sorted(EXAMS))
def test_fallback_is_valid_by_construction(stage1, exam):
    """§5.6: the deterministic fallback passes V12–V20 on every scope of both exams."""
    s1 = stage1[exam]
    for scope in s1.scopes:
        terminals, checks, disps = fallback_scope(scope, s1.precision)
        assert validate_scope(scope, terminals, checks, disps, s1.precision) == [], scope.scope
        assert all(c.origin in ("fallback", "compiler") for c in checks)


def test_fallback_never_multiplies_tiers():
    """Markers anchored on one terminal are ONE fault check with the markers as
    options — exactly one can apply, so tiers never add up."""
    scope = _synthetic([("0.5", "אם התחילו מ-1 להוריד 0.5", None),
                        ("1", "אם רצו עד length להוריד 1", None),
                        ("2", "אם לא בדקו null להוריד 2", None)])
    terminals, checks, disps = fallback_scope(scope, G)
    faults = [c for c in checks if c.role == "fault"]
    assert len(faults) == 1 and [o.marker_id for o in faults[0].options[1:]] == [
        "q9.c0.m1", "q9.c0.m2", "q9.c0.m3"]
    assert validate_scope(scope, terminals, checks, disps, G) == []


def test_point_free_keeps_words_and_drops_amounts():
    assert point_free("אם לא בדקו null להוריד 2") == "אם לא בדקו null"
    assert point_free("צבירה של הדקות שלו (1)") == "צבירה של הדקות שלו"
    assert point_free("להוריד 1", fallback="טעות") == "טעות"
