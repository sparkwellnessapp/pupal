"""grader-v6 Stage 1 (§5.1) on the two committed contracts. Pure; zero spend."""
from __future__ import annotations

from collections import Counter
from dataclasses import fields
from decimal import Decimal as D

import pytest

from app.agents.plan_compiler import compile_contract
from app.agents.plan_compiler.patterns_v6 import V6_PATTERNS
from app.agents.plan_compiler.stage1_v6 import (V6Scope, V6Terminal, compile_stage1_v6)
from tests.grading_eval_suite.fixtures import load_bundle

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}


@pytest.fixture(scope="module", params=sorted(EXAMS))
def exam(request):
    contract = load_bundle(EXAMS[request.param], require_gt=False).rubric_contract
    s1 = compile_stage1_v6(contract, exam_id=request.param, rubric_contract_sha256="x")
    v2 = compile_contract(contract, exam_id=request.param, rubric_contract_sha256="x",
                          route_min_points=D("Infinity"), patterns=V6_PATTERNS)
    return request.param, contract, s1, v2


def test_stage1_markers_replace_tariff_slots(exam):
    """Every deduction v2 would have made a tariff slot is ONE marker — same home,
    amount, verbatim text and group — and the v6 terminal has no tariff at all."""
    _name, _c, s1, v2 = exam
    tariffs = Counter((t.terminal_id, s.tariff_amount, s.source_span, s.charge_group)
                      for t in v2.terminals for s in t.tariff_slots)
    markers = Counter((m.home_terminal_id, m.amount, m.text_span, m.charge_group)
                      for s in s1.scopes for m in s.markers)
    assert markers == tariffs and sum(markers.values()) > 0
    assert all(m.polarity == "deduct" and m.candidate_anchors for s in s1.scopes for m in s.markers)
    assert not any("tariff" in f.name for f in fields(V6Terminal))


def test_stage1_parent_phrase_candidates_are_siblings(exam):
    """S-4: a phrase written on a parent criterion over sub-criteria is a marker
    whose candidates are ALL the siblings; its OD-10 sibling group is kept."""
    name, contract, s1, _v2 = exam
    parents = [m for s in s1.scopes for m in s.markers if len(m.candidate_anchors) > 1]
    if name == "bagrut_899371":
        assert parents == []
        return
    (m,) = parents
    criterion = next(c for q in contract.questions for sq in (q.sub_questions or [q])
                     for c in (getattr(sq, "criteria", None) or [])
                     if c.criterion_id == "q2.ב.c4")
    assert m.candidate_anchors == [s.sub_criterion_id for s in criterion.sub_criteria]
    assert m.home_terminal_id in m.candidate_anchors and m.amount == D("3")
    assert m.charge_group and m.charge_group.startswith("q2.ב:q2.ב.c4:")


def test_stage1_enumerated_components_are_fixed_input(exam):
    """C4 binds the planner: two or more enumerated components are fixed input —
    exactly v2's earn slots, ids, spans and points, in order; one is a monolith."""
    _name, _c, s1, v2 = exam
    for s in s1.scopes:
        for t in s.terminals:
            if t.shape != "components":
                continue
            v2t = v2.terminal(t.terminal_id)
            assert [(c.component_id, c.source_span, c.points) for c in t.components] == [
                (x.slot_id, x.source_span, x.points) for x in v2t.slots if x.kind == "required"]
            assert t.fixed is (len(t.components) >= 2)
            assert sum(c.points for c in t.components) == t.points_possible


def test_stage1_all_compiled_scope_skips_planner(exam):
    """C7: no threshold — every scope goes to the planner unless all its
    terminals are fully compiled (levels / count)."""
    _name, _c, s1, _v2 = exam
    for s in s1.scopes:
        assert s.needs_planner is (not all(t.shape in ("levels", "count") for t in s.terminals))
    levels_only = V6Scope("q9", (V6Terminal("q9.c0", "q9", D("4"), "", "levels",
                                            bands=(("טוב", D("4")), ("חלש", D("2")))),), ())
    count_and_levels = V6Scope("q9", levels_only.terminals + (
        V6Terminal("q9.c1", "q9", D("3"), "", "count", unit_count=6),), ())
    with_monolith = V6Scope("q9", count_and_levels.terminals + (
        V6Terminal("q9.c2", "q9", D("2"), "", "components"),), ())
    assert (levels_only.needs_planner, count_and_levels.needs_planner,
            with_monolith.needs_planner) == (False, False, True)


def test_stage1_is_deterministic(exam):
    name, contract, s1, _v2 = exam
    assert compile_stage1_v6(contract, exam_id=name, rubric_contract_sha256="x") == s1
