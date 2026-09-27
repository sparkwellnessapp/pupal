"""[AM-G14] The eval build tool routes monoliths at the PRODUCTION threshold.

`tools/segment_plan.py` used to call `compile_contract(...)` with no
`route_min_points`, so it took the compiler's default P ≥ 4 while production
(`plan_build_runner`) routes at `settings.plan_route_min_points` = 3. The eval
therefore built and measured a plan production never runs: bagrut routed 8
monoliths instead of 14, hobby 5 instead of 13 (Track B, RUNLOG 2026-09-27).

The rule is that the tool READS the setting — no duplicated constant — so the
test moves the setting and watches the tool follow it.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.plan_compiler import compile_contract
from app.config import settings

from .tools.compile_plan import discover_exams
from .tools.segment_plan import _compile

EXAMS = discover_exams()


def _routed(skeleton):
    return sorted(t.terminal_id for t in skeleton.terminals if t.routed)


@pytest.mark.parametrize("exam", sorted(EXAMS))
def test_segment_plan_routes_at_the_production_threshold(exam):
    contract, skeleton = _compile(exam, EXAMS[exam])
    production = compile_contract(
        contract, exam_id=exam, rubric_contract_sha256="x",
        route_min_points=Decimal(str(settings.plan_route_min_points)))
    assert _routed(skeleton) == _routed(production)


def test_segment_plan_reads_the_setting_not_a_copy(monkeypatch):
    exam = "bagrut_899371"
    _c, at_default = _compile(exam, EXAMS[exam])
    monkeypatch.setattr(settings, "plan_route_min_points", 1000)
    _c, at_huge = _compile(exam, EXAMS[exam])
    assert _routed(at_default), "the production threshold routes bagrut monoliths"
    assert _routed(at_huge) == [], "the tool must follow settings.plan_route_min_points"
