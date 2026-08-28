"""
grader-v5 Plan/Verify/Price — validator + pricer injected-error tests.

RED-FIRST (mission V5-A): these tests were written before plan_validator.py and
pricer.py existed and encode the ratified semantics:
  - over-sum plan rejected (V1)
  - note_only carrying points rejected (V3)
  - double-charged charge_group deducts ONCE (charge-once precedent)
  - fabricated-quote-on-met earns NOTHING (per-span evidence gating; GA-1's
    zero-false-credit property enforced in code, not prompt)
Zero mocks, zero I/O — the validator and pricer are pure.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
from app.agents.grader.plan_validator import validate_plan
from app.agents.grader.pricer import AssessedVerdict, price_scope
from app.schemas.ontology_types import FlagReason, QuoteValidationStatus

P = Decimal("0.25")   # the hobby_tvshow precision grid


def _check(cid, kind="required", points="1", tariff=None, group=None, frac="0.5"):
    return PlanCheck(
        check_id=cid, description_he=f"בדיקה {cid}", kind=kind,
        points=Decimal(points),
        tariff_amount=None if tariff is None else Decimal(tariff),
        partial_fraction=Decimal(frac),
        charge_group=group,
    )


def _plan(terminals):
    return GradingPlan(plan_version="test/v1", exam_id="test_exam",
                       rubric_contract_sha256="0" * 64, terminals=terminals)


def _contract_maps(plan):
    """Derive (terminal points, terminal->scope) maps as the runner would from a
    contract — here every terminal sits in scope 's1' unless the test overrides."""
    pts = {t.terminal_id: t.points_possible for t in plan.terminals}
    scopes = {t.terminal_id: "s1" for t in plan.terminals}
    return pts, scopes


def _av(cid, verdict="met", quote="ink", status=QuoteValidationStatus.EXACT,
        conf=0.9, basis="נמצא"):
    return AssessedVerdict(check_id=cid, verdict=verdict, confidence=conf,
                           basis_he=basis, quote_text=quote, quote_status=status)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_valid_plan_passes():
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("3"), checks=[
        _check("t1.k1", points="2"),
        _check("t1.k2", points="1"),
        _check("t1.k3", kind="tariff", points="0", tariff="1", group="g1"),
        _check("t1.k4", kind="note_only", points="0"),
    ])])
    pts, scopes = _contract_maps(plan)
    assert validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P) == []


def test_over_sum_plan_rejected():
    """[injected error, mission V5-A] Σ required != points_possible."""
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("3"), checks=[
        _check("t1.k1", points="2"), _check("t1.k2", points="2")])])
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert any("V1" in e and "t1" in e for e in errs), errs


def test_note_only_carrying_points_rejected():
    """[injected error, mission V5-A] note_only must never carry points."""
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("3"), checks=[
        _check("t1.k1", points="3"),
        _check("t1.k2", kind="note_only", points="1")])])
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert any("V3" in e and "note_only" in e for e in errs), errs


def test_tariff_shape_rules():
    # tariff with earn-points AND tariff without amount both rejected
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("2"), checks=[
        _check("t1.k1", points="2"),
        _check("t1.k2", kind="tariff", points="1", tariff="1"),
        _check("t1.k3", kind="tariff", points="0", tariff=None)])])
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert sum("V3" in e for e in errs) >= 2, errs


def test_tariff_larger_than_terminal_rejected():
    """A defect never costs more than the component it belongs to."""
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("2"), checks=[
        _check("t1.k1", points="2"),
        _check("t1.k2", kind="tariff", points="0", tariff="3")])])
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert any("V3" in e and "tariff_amount" in e for e in errs), errs


def test_off_grid_partial_rejected():
    """points * partial_fraction must land on the precision grid (V4)."""
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("0.25"), checks=[
        _check("t1.k1", points="0.25", frac="0.5")])])   # 0.125 off-grid
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert any("V4" in e for e in errs), errs


def test_duplicate_check_id_rejected():
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("2"), checks=[
        _check("t1.k1", points="1"), _check("t1.k1", points="1")])])
    pts, scopes = _contract_maps(plan)
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes=scopes, precision=P)
    assert any("V5" in e for e in errs), errs


def test_totality_against_contract():
    plan = _plan([TerminalPlan(terminal_id="t1", points_possible=Decimal("2"), checks=[
        _check("t1.k1", points="2")])])
    # contract has an extra terminal t2, and t1's points differ
    errs = validate_plan(plan,
                         contract_terminal_points={"t1": Decimal("3"), "t2": Decimal("1")},
                         terminal_scopes={"t1": "s1", "t2": "s1"}, precision=P)
    assert any("V6" in e and "t2" in e for e in errs), errs          # missing terminal
    assert any("V6" in e and "points_possible" in e for e in errs), errs  # points mismatch


def test_charge_group_must_stay_inside_one_scope():
    plan = _plan([
        TerminalPlan(terminal_id="t1", points_possible=Decimal("1"), checks=[
            _check("t1.k1", points="1"),
            _check("t1.k2", kind="tariff", points="0", tariff="1", group="g")]),
        TerminalPlan(terminal_id="t2", points_possible=Decimal("1"), checks=[
            _check("t2.k1", points="1"),
            _check("t2.k2", kind="tariff", points="0", tariff="1", group="g")]),
    ])
    pts = {"t1": Decimal("1"), "t2": Decimal("1")}
    errs = validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes={"t1": "s1", "t2": "s2"}, precision=P)
    assert any("V7" in e and "'g'" in e for e in errs), errs
    # same group inside ONE scope is legal
    assert validate_plan(plan, contract_terminal_points=pts,
                         terminal_scopes={"t1": "s1", "t2": "s1"}, precision=P) == []


# ---------------------------------------------------------------------------
# Pricer
# ---------------------------------------------------------------------------

def _one_terminal(checks, possible="3"):
    return [TerminalPlan(terminal_id="t1", points_possible=Decimal(possible),
                         checks=checks)]


def test_all_met_earns_full():
    tp = _one_terminal([_check("t1.k1", points="2"), _check("t1.k2", points="1")])
    out = price_scope(tp, {"t1.k1": _av("t1.k1"), "t1.k2": _av("t1.k2")}, P)
    assert out["t1"].points_awarded == Decimal("3")
    assert out["t1"].flags == []


def test_partial_earns_fraction_and_not_met_earns_zero():
    tp = _one_terminal([_check("t1.k1", points="2"), _check("t1.k2", points="1")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1", verdict="partially_met"),
        "t1.k2": _av("t1.k2", verdict="not_met", quote="", status=None),
    }, P)
    assert out["t1"].points_awarded == Decimal("1")     # 2*0.5 + 0


def test_missing_verdict_prices_zero_and_flags():
    tp = _one_terminal([_check("t1.k1", points="3")])
    out = price_scope(tp, {}, P)
    assert out["t1"].points_awarded == Decimal("0")
    assert any(f.reason == FlagReason.UNVERIFIED_CHECK for f in out["t1"].flags)
    assert out["t1"].confidence == 0.0


def test_fabricated_quote_on_met_earns_nothing():
    """[injected error, mission V5-A] met with an unverifiable span NEVER earns.
    The zero-false-credit property (GA-1) is enforced by the pricer, and the
    refusal is loud: EVIDENCE_UNVERIFIED flag + annotation, never silent."""
    tp = _one_terminal([_check("t1.k1", points="3")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1", verdict="met", quote="never wrote this",
                     status=QuoteValidationStatus.NOT_FOUND)}, P)
    assert out["t1"].points_awarded == Decimal("0")
    assert any(f.reason == FlagReason.EVIDENCE_UNVERIFIED for f in out["t1"].flags)
    assert any(a.annotation_type == "evidence_unverified" for a in out["t1"].annotations)


def test_met_with_empty_quote_earns_nothing():
    """'' is legal only for not_met; an empty span on met is unverified evidence."""
    tp = _one_terminal([_check("t1.k1", points="3")])
    out = price_scope(tp, {"t1.k1": _av("t1.k1", verdict="met", quote="",
                                        status=None)}, P)
    assert out["t1"].points_awarded == Decimal("0")
    assert any(f.reason == FlagReason.EVIDENCE_UNVERIFIED for f in out["t1"].flags)


def test_fuzzy_evidence_earns_with_flag():
    tp = _one_terminal([_check("t1.k1", points="3")])
    out = price_scope(tp, {"t1.k1": _av("t1.k1", status=QuoteValidationStatus.FUZZY)}, P)
    assert out["t1"].points_awarded == Decimal("3")
    assert any(f.reason == FlagReason.FUZZY_MATCH for f in out["t1"].flags)


def test_tariff_fires_once_per_charge_group():
    """[injected error, mission V5-A] the double-charged group: two tariffs in
    one group, both fired -> ONE deduction (the max), the duplicate annotated."""
    tp = [
        TerminalPlan(terminal_id="t1", points_possible=Decimal("2"), checks=[
            _check("t1.k1", points="2"),
            _check("t1.k2", kind="tariff", points="0", tariff="1", group="g")]),
        TerminalPlan(terminal_id="t2", points_possible=Decimal("2"), checks=[
            _check("t2.k1", points="2"),
            _check("t2.k2", kind="tariff", points="0", tariff="0.5", group="g")]),
    ]
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1"), "t2.k1": _av("t2.k1"),
        "t1.k2": _av("t1.k2", verdict="not_met", quote="bad ink"),
        "t2.k2": _av("t2.k2", verdict="not_met", quote="bad ink"),
    }, P)
    # group charged ONCE, at the first terminal in document order, at the MAX amount
    assert out["t1"].points_awarded == Decimal("1")     # 2 - 1
    assert out["t2"].points_awarded == Decimal("2")     # NOT charged again
    assert any(a.annotation_type == "charge_group_dedup" for a in out["t2"].annotations)


def test_tariff_not_fired_deducts_nothing():
    tp = _one_terminal([
        _check("t1.k1", points="3"),
        _check("t1.k2", kind="tariff", points="0", tariff="1")])
    out = price_scope(tp, {"t1.k1": _av("t1.k1"), "t1.k2": _av("t1.k2")}, P)
    assert out["t1"].points_awarded == Decimal("3")


def test_tariff_partially_met_is_coerced_to_fired():
    tp = _one_terminal([
        _check("t1.k1", points="3"),
        _check("t1.k2", kind="tariff", points="0", tariff="1")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1"),
        "t1.k2": _av("t1.k2", verdict="partially_met", quote="bad ink")}, P)
    assert out["t1"].points_awarded == Decimal("2")
    assert any(f.reason == FlagReason.TARIFF_COERCED for f in out["t1"].flags)


def test_note_only_annotates_and_never_deducts():
    tp = _one_terminal([
        _check("t1.k1", points="3"),
        _check("t1.k2", kind="note_only", points="0")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1"),
        "t1.k2": _av("t1.k2", verdict="not_met", quote="bad ink",
                     basis="חסר סוגריים")}, P)
    assert out["t1"].points_awarded == Decimal("3")
    assert any(a.annotation_type == "note_only" for a in out["t1"].annotations)


def test_deductions_clamp_at_zero_with_flag():
    tp = _one_terminal([
        _check("t1.k1", points="1"),
        _check("t1.k2", kind="tariff", points="0", tariff="1"),
        _check("t1.k3", kind="tariff", points="0", tariff="1")], possible="1")
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1"),
        "t1.k2": _av("t1.k2", verdict="not_met", quote="x1 bad ink"),
        "t1.k3": _av("t1.k3", verdict="not_met", quote="x2 bad ink"),
    }, P)
    assert out["t1"].points_awarded == Decimal("0")     # 1 - 2 -> clamp 0
    assert any(f.reason == FlagReason.BOUNDS_CLAMPED for f in out["t1"].flags)


def test_grid_snap_is_belt_and_braces():
    """The validator forbids off-grid partials, but the pricer must still be
    deterministic if handed one (defense in depth): snap ROUND_HALF_UP + flag."""
    tp = _one_terminal([_check("t1.k1", points="1", frac="0.3")], possible="1")
    out = price_scope(tp, {"t1.k1": _av("t1.k1", verdict="partially_met")}, P)
    assert out["t1"].points_awarded == Decimal("0.25")   # 0.3 -> nearest grid step
    assert any(f.reason == FlagReason.BOUNDS_CLAMPED for f in out["t1"].flags)


def test_confidence_is_min_over_checks_and_evidence_collected():
    tp = _one_terminal([_check("t1.k1", points="2"), _check("t1.k2", points="1")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1", conf=0.9, quote="span one"),
        "t1.k2": _av("t1.k2", conf=0.4, quote="span two")}, P)
    t = out["t1"]
    assert t.confidence == 0.4
    assert [q.quote_text for q in t.evidence_quotes] == ["span one", "span two"]
    # the same span cited by two checks is collected once
    tp2 = _one_terminal([_check("t1.k1", points="2"), _check("t1.k2", points="1")])
    out2 = price_scope(tp2, {
        "t1.k1": _av("t1.k1", quote="same span"),
        "t1.k2": _av("t1.k2", quote="same span")}, P)
    assert [q.quote_text for q in out2["t1"].evidence_quotes] == ["same span"]


def test_reasoning_names_every_check():
    tp = _one_terminal([_check("t1.k1", points="2"), _check("t1.k2", points="1")])
    out = price_scope(tp, {
        "t1.k1": _av("t1.k1"),
        "t1.k2": _av("t1.k2", verdict="not_met", quote="", status=None,
                     basis="חיפשתי בכל הקוד — אין בדיקת null")}, P)
    r = out["t1"].reasoning
    assert "בדיקה t1.k1" in r and "בדיקה t1.k2" in r
    assert "חיפשתי בכל הקוד" in r
