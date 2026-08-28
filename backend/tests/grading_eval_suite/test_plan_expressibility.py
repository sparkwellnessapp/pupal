"""
Expressibility guard — standing test [owner H-4 item 3, 2026-08-28].

Any future plan or GT amendment re-runs this automatically: every ratified GT
award of every fixture must be reachable under the committed plan's algebra.
Red-first record: against plan v1 this failed on exactly the two known cases
(dan/q1.א.c1 3.5 under the 2+2 split; yonatan/q2.ב.c4.s2 1.5 with no start-
index tariff); v2 (A-1/A-2) went 190/190.
"""
from __future__ import annotations

from decimal import Decimal

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan

from .fixtures import SUITE_DIR, load_bundle
from .plan_expressibility import expressibility_errors, reachable_awards

FIXTURES = ("dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber",
            "yonatan_basiuk")


def test_committed_plan_expresses_every_fixture_gt():
    plan = GradingPlan.model_validate_json(
        (SUITE_DIR / "plans" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    all_errs = []
    for fx in FIXTURES:
        b = load_bundle(fx)
        all_errs += expressibility_errors(
            plan, b.gt, b.terminal_infos,
            b.rubric_contract.numeric_policy.precision)
    assert all_errs == [], all_errs


def test_reachability_algebra():
    """The algebra itself: {0, partial, full} per required, tariff on/off,
    clamp + grid. The known v1 counterexample shape is pinned red."""
    tp = TerminalPlan(terminal_id="t", points_possible=Decimal("2"), checks=[
        PlanCheck(check_id="t.k1", description_he="x", kind="required",
                  points=Decimal("2")),
        PlanCheck(check_id="t.k2", description_he="y", kind="tariff",
                  points=Decimal("0"), tariff_amount=Decimal("0.5")),
    ])
    reach = reachable_awards(tp, Decimal("0.25"))
    assert Decimal("1.5") in reach          # full − tariff (the A-2 fix shape)
    assert Decimal("0.5") in reach          # partial − 0.5
    assert Decimal("2") in reach and Decimal("0") in reach
    # the v1 failure shape: single required 2, no tariff -> 1.5 unreachable
    tp_v1 = TerminalPlan(terminal_id="t", points_possible=Decimal("2"), checks=[
        PlanCheck(check_id="t.k1", description_he="x", kind="required",
                  points=Decimal("2"))])
    assert Decimal("1.5") not in reachable_awards(tp_v1, Decimal("0.25"))
