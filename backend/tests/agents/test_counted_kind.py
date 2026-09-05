"""
The `counted` kind — R-E Case 1 made a kind (PLAN COMPILER v2, C3).

Red-first against the ratified semantics: a counted check prices
snap(points × units_correct / unit_count), is the ONLY check on its terminal,
and the verifier reports a COUNT, never points. The canonical trigger is
bagrut q1.א.1.c0 — «17 תאים 0.7 כל תא», 12 points — and the faithfulness case
is noam's 10.5 (15 of 17 cells), which must be PRODUCIBLE, not merely reachable.
Zero mocks, zero I/O.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
from app.agents.grader.plan_validator import validate_plan
from app.agents.grader.pricer import AssessedVerdict, price_scope
from app.schemas.ontology_types import FlagReason, QuoteValidationStatus

P = Decimal("0.25")


def _counted(cid="t.k1", points="12", n=17, **kw):
    return PlanCheck(check_id=cid, description_he="טבלת מעקב", kind="counted",
                     points=Decimal(points), unit_count=n, **kw)


def _plan(checks, possible="12"):
    return GradingPlan(plan_version="test/v1", exam_id="x", rubric_contract_sha256="0" * 64,
                       terminals=[TerminalPlan(terminal_id="t", points_possible=Decimal(possible),
                                               checks=checks)])


def _validate(plan):
    return validate_plan(plan, contract_terminal_points={"t": plan.terminals[0].points_possible},
                         terminal_scopes={"t": "s"}, precision=P)


def _av(verdict, units=None, quote="ink", status=QuoteValidationStatus.EXACT):
    return AssessedVerdict(check_id="t.k1", verdict=verdict, confidence=0.9, basis_he="",
                           quote_text=quote, quote_status=status, units_correct=units)


# ── validator (V12) ──────────────────────────────────────────────────────────

def test_a_well_formed_counted_check_passes():
    assert _validate(_plan([_counted()])) == []


def test_counted_must_price_the_whole_terminal():
    errs = _validate(_plan([_counted(points="6")]))
    assert any("V12" in e and "whole terminal" in e for e in errs), errs


def test_counted_must_be_alone_on_its_terminal():
    other = PlanCheck(check_id="t.k2", description_he="x", kind="required", points=Decimal("1"))
    errs = _validate(_plan([_counted(points="11"), other]))
    assert any("V12" in e and "ONLY check" in e for e in errs), errs


@pytest.mark.parametrize("n", [None, 0, 1])
def test_counted_needs_at_least_two_units(n):
    errs = _validate(_plan([_counted(n=n)]))
    assert any("V12" in e and "unit_count" in e for e in errs), errs


def test_counted_may_not_carry_tariff_group_or_partial_override():
    errs = _validate(_plan([_counted(tariff_amount=Decimal("1"))]))
    assert any("tariff_amount" in e for e in errs)
    errs = _validate(_plan([_counted(charge_group="g")]))
    assert any("charge_group" in e for e in errs)
    errs = _validate(_plan([_counted(partial_fraction=Decimal("0.25"))]))
    assert any("partial_fraction" in e for e in errs)


# ── pricing ──────────────────────────────────────────────────────────────────

def test_noam_10_5_is_producible_not_merely_reachable():
    """The faithfulness case: 15 of 17 cells at 12 points → 12 × 15/17 = 10.588
    → 10.5 on the 0.25 grid. By-row decomposition could only reach 10.5 by
    accident; the counted kind PRODUCES it from the count the verifier reports."""
    tp = _plan([_counted()]).terminals
    out = price_scope(tp, {"t.k1": _av("partially_met", units=15)}, P)
    assert out["t"].points_awarded == Decimal("10.5")
    assert "15 מתוך 17" in out["t"].reasoning


def test_counted_met_and_not_met_are_the_two_ends():
    tp = _plan([_counted()]).terminals
    assert price_scope(tp, {"t.k1": _av("met")}, P)["t"].points_awarded == Decimal("12")
    assert price_scope(tp, {"t.k1": _av("not_met", quote="", status=None)}, P
                       )["t"].points_awarded == Decimal("0")


def test_counted_partial_without_a_count_earns_nothing_and_flags():
    """Inventing a count would be a number the model never emitted."""
    tp = _plan([_counted()]).terminals
    out = price_scope(tp, {"t.k1": _av("partially_met", units=None)}, P)
    assert out["t"].points_awarded == Decimal("0")
    assert any(f.reason == FlagReason.UNVERIFIED_CHECK for f in out["t"].flags)
    assert any(a.annotation_type == "count_missing" for a in out["t"].annotations)


def test_counted_count_is_clamped_into_range():
    tp = _plan([_counted()]).terminals
    assert price_scope(tp, {"t.k1": _av("partially_met", units=99)}, P)["t"].points_awarded == Decimal("12")
    assert price_scope(tp, {"t.k1": _av("partially_met", units=-3)}, P)["t"].points_awarded == Decimal("0")


def test_counted_credit_is_evidence_gated_like_required():
    tp = _plan([_counted()]).terminals
    out = price_scope(tp, {"t.k1": _av("partially_met", units=15,
                                       status=QuoteValidationStatus.NOT_FOUND)}, P)
    assert out["t"].points_awarded == Decimal("0")
    assert any(f.reason == FlagReason.EVIDENCE_UNVERIFIED for f in out["t"].flags)


def test_the_wire_record_carries_the_count():
    tp = _plan([_counted()]).terminals
    out = price_scope(tp, {"t.k1": _av("partially_met", units=15)}, P)
    rec = out["t"].checks[0]
    assert rec.kind == "counted" and rec.unit_count == 17 and rec.units_correct == 15


# ── expressibility ───────────────────────────────────────────────────────────

def test_reachable_set_is_every_snapped_fraction():
    from tests.grading_eval_suite.plan_expressibility import reachable_awards

    reach = reachable_awards(_plan([_counted()]).terminals[0], P)
    assert Decimal("10.5") in reach and Decimal("12") in reach and Decimal("0") in reach
    assert len(reach) <= 18
    # 12 × 16/17 = 11.29 → 11.25 ; 12 × 1/17 = 0.706 → 0.75
    assert Decimal("11.25") in reach and Decimal("0.75") in reach


# ── the hand plan is untouched by the new kind ───────────────────────────────

def test_the_ratified_hand_plan_still_parses_and_validates():
    import io
    from tests.grading_eval_suite.fixtures import load_bundle

    plan = GradingPlan.model_validate_json(
        io.open("tests/grading_eval_suite/plans/hobby_tvshow.plan.json", encoding="utf-8").read())
    assert plan.compiler_version is None, "a hand plan must not claim a compiler"
    b = load_bundle("dan_basiuk")
    errs = validate_plan(
        plan,
        contract_terminal_points={t: i.points for t, i in b.terminal_infos.items()},
        terminal_scopes={t: (i.question_id if i.sub_question_id is None
                             else f"{i.question_id}.{i.sub_question_id}")
                         for t, i in b.terminal_infos.items()},
        precision=b.rubric_contract.numeric_policy.precision)
    assert errs == [], errs
