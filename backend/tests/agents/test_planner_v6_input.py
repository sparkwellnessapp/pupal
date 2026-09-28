"""Stage 1 → planner input, and the exact inverse of the amount mask (§5.2, D-LAW-2)."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.inputs import AMOUNT_MASK
from app.agents.planner.prompt import render_scope_input
from app.agents.planner.stage1_input import scope_planner_input, unmask_span
from tests.grading_eval_suite.fixtures import load_bundle

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}


@pytest.mark.parametrize("exam", sorted(EXAMS))
def test_every_scope_of_both_exams_renders_without_its_marker_amounts(exam):
    s1 = compile_stage1_v6(load_bundle(EXAMS[exam], require_gt=False).rubric_contract,
                           exam_id=exam, rubric_contract_sha256="x")
    for scope in s1.scopes:
        inp = scope_planner_input(scope)
        text = render_scope_input(inp)
        assert scope.scope in text
        for m in inp.markers:
            assert m.text_span in text
        for m in scope.markers:
            # the marker's own span reaches the planner only masked
            if m.amount is not None and any(ch.isdigit() for ch in m.text_span):
                assert m.text_span not in text or AMOUNT_MASK in m.text_span


def test_unmask_span_is_the_exact_inverse_of_the_mask():
    teacher = "אם לא בדקו null להוריד 2 ; אם רצו עד length להוריד 1"
    assert unmask_span(f"אם לא בדקו null להוריד {AMOUNT_MASK}", [teacher]) == "אם לא בדקו null להוריד 2"
    assert unmask_span("אין מסכה כאן", [teacher]) == "אין מסכה כאן"
    assert unmask_span(f"להוריד {AMOUNT_MASK}", [teacher]) is None          # ambiguous: two matches
    assert unmask_span(f"משפט שלא קיים {AMOUNT_MASK}", [teacher]) is None
