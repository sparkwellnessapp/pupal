"""grader-v6 Phase 1 — the pricer (PR_grader_v6_options.md §4, as amended:
AM-G1 no reduction terminals, AM-G2 evidence gate in Resolve, AM-G3 typed
amounts, AM-G4 half-up values, AM-G9 E10 on the real text, Q-10 note checks).

Pure, zero mocks. Each worked example of §4.5 is a named test (§14)."""
from __future__ import annotations

import ast
import itertools
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.agents.grader.plan_schemas import PartialFraction
from app.services.pricing_v6 import CheckDecision, price
from tests.services.pricing_v6_cases import (
    E10_TID,
    Sel,
    binary,
    count,
    e10_checks,
    fault,
    ladder,
    levels,
    note,
    overlay,
    term,
    view,
)

A = "A"


def _e1(c1_opt, f1_opt, quote="exact"):
    c1 = binary("A.c1", A, 4, desc="עדכון התכונה people")
    f1 = fault("A.f1", A, [("m1", 2, "העדכון בגישה ישירה במקום SetPeople")],
               requires="A.c1", desc="אופן העדכון")
    return view([term(A, 4)], [Sel(c1, c1_opt, quote), Sel(f1, f1_opt, quote)])


def _t(priced, tid=A):
    return next(t for t in priced.terminals if t.terminal_id == tid)


def _charge(priced, cid):
    for t in priced.terminals:
        for ch in t.charges:
            if ch.check_id == cid:
                return ch
    raise KeyError(cid)


# ── §4.5 worked examples ─────────────────────────────────────────────────────

def test_e1_present_behavior_with_fault_nets_partial():
    p = price(_e1("full", "f1"))
    assert _t(p).awarded == D("2")
    ch = _charge(p, "A.f1")
    assert (ch.status, ch.amount, ch.charged) == ("applied", D("-2"), D("-2"))
    assert price(_e1("full", "none")).terminals[0].awarded == D("4")      # correct → 4
    assert _t(price(_e1("full", "none"))).chip == "full"
    assert _t(p).chip == "partial"


def test_e1_absent_behavior_skips_its_fault():
    for f_opt in ("f1", "none"):
        p = price(_e1("absent", f_opt))
        assert _t(p).awarded == D("0")                                     # not −2
        assert _charge(p, "A.f1").status == "inactive"
        assert _charge(p, "A.f1").charged == D("0")
        assert _t(p).chip == "zero"
        assert _t(p).primary_check_id is None


def test_e2_ladder_charges_exactly_one_tier():
    c1 = binary("A.c1", A, 4)
    f1 = fault("A.f1", A, [("m1", 2, "t1"), ("m2", 3, "t2"), ("m3", 4, "t3")], requires="A.c1")
    p = price(view([term(A, 4)], [Sel(c1, "full"), Sel(f1, "f2")]))
    assert _t(p).awarded == D("1")
    assert [c.charged for c in _t(p).charges] == [D("-3")]


def test_e4_charge_group_charges_once_earliest_on_tie():
    t1c = binary("T1.c1", "T1", 2)
    t1f = fault("T1.f1", "T1", [("m1", 1, "חסר public")], group="g")
    t2c = binary("T2.c1", "T2", 2)
    t2f = fault("T2.f1", "T2", [("m2", 1, "חסר public")], group="g")
    p = price(view([term("T1", 2), term("T2", 2)],
                   [Sel(t1c, "full"), Sel(t1f, "f1"), Sel(t2c, "full"), Sel(t2f, "f1")]))
    assert _charge(p, "T1.f1").status == "applied" and _charge(p, "T1.f1").charged == D("-1")
    assert _charge(p, "T2.f1").status == "superseded" and _charge(p, "T2.f1").charged == D("0")
    assert p.total_score == D("3")


def test_charge_group_keeps_the_largest_magnitude_on_its_own_terminal():
    t1c = binary("T1.c1", "T1", 4)
    t1f = fault("T1.f1", "T1", [("m1", 1, "x")], group="g")
    t2c = binary("T2.c1", "T2", 4)
    t2f = fault("T2.f1", "T2", [("m2", 3, "x")], group="g")
    p = price(view([term("T1", 4), term("T2", 4)],
                   [Sel(t1c, "full"), Sel(t1f, "f1"), Sel(t2c, "full"), Sel(t2f, "f1")]))
    assert _charge(p, "T1.f1").status == "superseded"
    assert _charge(p, "T2.f1").charged == D("-3")
    assert (_t(p, "T1").awarded, _t(p, "T2").awarded) == (D("4"), D("1"))


def test_e5_fault_capped_by_behavior():
    lad = ladder("A.c1", A, 2, [("half", PartialFraction.HALF)])
    other = binary("A.c2", A, 2)
    f1 = fault("A.f1", A, [("m1", 2, "x")], requires="A.c1")
    p = price(view([term(A, 4)], [Sel(lad, "p1"), Sel(other, "full"), Sel(f1, "f1")]))
    ch = _charge(p, "A.f1")
    assert (ch.amount, ch.charged, ch.status) == (D("-2"), D("-1"), "capped")    # [AM-G13]
    assert _t(p).awarded == D("2")                   # T's portion 0, the rest untouched


def test_e6_floor_reduces_latest_charge_and_flags():
    c1 = binary("A.c1", A, 2)
    f1 = fault("A.f1", A, [("m1", 3, "x")])                               # ungated
    p = price(view([term(A, 2)], [Sel(c1, "full"), Sel(f1, "f1")]))
    ch = _charge(p, "A.f1")
    assert (ch.charged, ch.status) == (D("-2"), "floored")
    assert _t(p).awarded == D("0")
    assert "bounds_clamped" in _t(p).flags
    # two charges: the LATER one in plan order is reduced first
    f2 = fault("A.f2", A, [("m2", 2, "y")])
    c = binary("A.c1", A, 3)
    f1b = fault("A.f1", A, [("m1", 2, "x")])
    p = price(view([term(A, 3)], [Sel(c, "full"), Sel(f1b, "f1"), Sel(f2, "f1")]))
    assert (_charge(p, "A.f1").status, _charge(p, "A.f1").charged) == ("applied", D("-2"))
    assert (_charge(p, "A.f2").status, _charge(p, "A.f2").charged) == ("floored", D("-1"))
    assert _t(p).awarded == D("0")


def test_e7_levels():
    lv = levels("A.c1", A, [("מצוין", 40), ("טוב", 30), ("בינוני", 20), ("חלש", 10), ("אין", 0)])
    p = price(view([term(A, 40)], [Sel(lv, "L2")]))
    assert _t(p).awarded == D("30")


def test_e8_count():
    c = count("A.c1", A, 3, 8)
    p = price(view([term(A, 3)], [Sel(c, "n5")]))
    assert _t(p).awarded == D("2.00")                # AM-G4: half-up, was floor 1.75


def test_e9_overlay_option_and_terminal_override():
    v = _e1("full", "f1")
    p = price(v, overlay({"A.c1": CheckDecision(option_id="absent")}))
    assert _t(p).awarded == D("0")
    assert _charge(p, "A.f1").status == "inactive"
    p = price(v, overlay(pins={A: 3}))
    assert _t(p).awarded == D("3") and _t(p).overridden
    assert _charge(p, "A.f1").status == "applied"    # charge statuses kept for display


def test_e10_setpeople_real_text_one_charge_din_roni_3_yahli_0():
    capacity, update, tiers = e10_checks()
    t = term(E10_TID, 5, q="q5", sq="ב")
    # (1) every verifier selection: at most one charge among the three phrases
    for c_opt, u_opt, f_opt in itertools.product(
            ("full", "absent"), ("full", "absent"), ("none", "f1", "f2", "f3")):
        p = price(view([t], [Sel(capacity, c_opt), Sel(update, u_opt), Sel(tiers, f_opt)]))
        charged = [c for c in _t(p, E10_TID).charges if c.charged != 0]
        assert len(charged) <= 1
        assert D("0") <= _t(p, E10_TID).awarded <= D("5")
    # (2) din / roni: capacity met, update present, one tier (no SetPeople) → 3/5
    p = price(view([t], [Sel(capacity, "full"), Sel(update, "full"), Sel(tiers, "f1")]))
    assert _t(p, E10_TID).awarded == D("3")
    # (3) yahli: update absent → 0, every fault inactive
    for f_opt in ("none", "f1", "f2", "f3"):
        p = price(view([t], [Sel(capacity, "absent"), Sel(update, "absent"), Sel(tiers, f_opt)]))
        assert _t(p, E10_TID).awarded == D("0")
        assert all(c.status == "inactive" for c in _t(p, E10_TID).charges)


# ── resolve (PRC-1 as amended) ───────────────────────────────────────────────

def test_missing_selection_defaults_and_flags():
    p = price(_e1(None, None))
    assert _t(p).awarded == D("0")
    res = {r.check_id: r for r in p.checks}
    assert res["A.c1"].option_id == "absent" and res["A.c1"].missing
    assert res["A.f1"].option_id == "none" and res["A.f1"].missing
    assert "unverified_check" in _t(p).flags
    # an option id that is not the check's own is treated as missing (§6.3)
    p = price(_e1("zz_foreign", "none"))
    assert {r.check_id: r for r in p.checks}["A.c1"].missing


def test_evidence_gate_refuses_unverified_model_selection_only():
    # AM-G2: the model's credit on a not_found quote resolves to the default…
    p = price(_e1("full", "none", quote="not_found"))
    res = {r.check_id: r for r in p.checks}
    assert (res["A.c1"].option_id, res["A.c1"].source) == ("absent", "gated")
    assert res["A.c1"].claimed_option_id == "full"            # the claim stays on the record
    assert "evidence_unverified" in _t(p).flags
    assert _t(p).awarded == D("0")
    # …but HER selection of the same option is never gated (v5 evidence_confirmed)
    p = price(_e1("full", "none", quote="not_found"),
              overlay({"A.c1": CheckDecision(option_id="full")}))
    assert _t(p).awarded == D("4")
    # the same gate applies to a v6 fault: an unverified fault is not charged
    c1 = binary("A.c1", A, 4)
    f1 = fault("A.f1", A, [("m1", 2, "x")], requires="A.c1")
    v = view([term(A, 4)], [Sel(c1, "full", "exact"), Sel(f1, "f1", "not_found")])
    assert _t(price(v)).awarded == D("4")
    # a LEGACY fault (evidence_required=False) is charged as v5 charged it
    f_legacy = fault("A.f1", A, [("m1", 2, "x")], evidence_required=False)
    v = view([term(A, 4)], [Sel(c1, "full", "exact"), Sel(f_legacy, "f1", "not_found")])
    assert _t(price(v)).awarded == D("2")
    # fuzzy is verified
    assert _t(price(_e1("full", "f1", quote="fuzzy"))).awarded == D("2")


def test_typed_amount_resolves_credit_and_is_bounded():
    # AM-G3: her amount on a credit check is its value; activity follows it
    p = price(_e1("absent", "f1"), overlay({"A.c1": CheckDecision(amount=D("1.5"))}))
    assert _charge(p, "A.f1").status == "capped"                 # [AM-G13] BehaviorCap
    assert _charge(p, "A.f1").charged == D("-1.5")           # capped by her 1.5
    assert _t(p).awarded == D("0") and _t(p).typed
    p = price(_e1("full", "none"), overlay({"A.c1": CheckDecision(amount=D("2.5"))}))
    assert _t(p).awarded == D("2.5") and _t(p).typed
    res = {r.check_id: r for r in p.checks}["A.c1"]
    assert (res.source, res.value, res.option_id) == ("amount", D("2.5"), None)


def test_note_checks_never_price():
    c1 = binary("A.c1", A, 3)
    n1 = note("A.n1", A, "לא נבדק שימוש בערוץ")
    p = price(view([term(A, 3)], [Sel(c1, "full"), Sel(n1, "observed")]))
    assert _t(p).awarded == D("3")
    assert _t(p).notes_observed == ["A.n1"]
    p = price(view([term(A, 3)], [Sel(c1, "full"), Sel(n1, "none")]))
    assert _t(p).notes_observed == []


def test_upper_clamp_is_logged_as_logic_bug():
    # V13 makes raw > P impossible from a valid plan; a corrupt plan (credit
    # max above the terminal) must clamp AND surface for the caller to log.
    c1 = binary("A.c1", A, 5)
    p = price(view([term(A, 4)], [Sel(c1, "full")]))
    assert _t(p).awarded == D("4")
    assert "bounds_clamped" in _t(p).flags
    assert any(f.startswith("upper_clamp_logic_bug:") for f in p.flags)


def test_primary_check_is_the_highest_resolved_credit_ties_to_plan_order():
    c1, c2 = binary("A.c1", A, 2), binary("A.c2", A, 2)
    assert _t(price(view([term(A, 4)], [Sel(c1, "full"), Sel(c2, "full")]))).primary_check_id == "A.c1"
    assert _t(price(view([term(A, 4)], [Sel(c1, "absent"), Sel(c2, "full")]))).primary_check_id == "A.c2"


def test_selection_groups_aggregate_unchanged():
    q1c, q2c = binary("q1.c0.c1", "q1.c0", 10), binary("q2.c0.c1", "q2.c0", 10)
    v = view([term("q1.c0", 10, q="q1"), term("q2.c0", 10, q="q2")],
             [Sel(q1c, "full"), Sel(q2c, "absent")], groups=[(["q1", "q2"], 1)])
    p = price(v)
    assert (p.total_score, p.total_possible) == (D("10"), D("10"))
    excluded = [s for s in p.scopes if not s.counted]
    assert [s.question_id for s in excluded] == ["q2"]


def test_price_is_invariant_under_list_order():
    c1 = binary("A.c1", A, 4)
    f1 = fault("A.f1", A, [("m1", 2, "x")], requires="A.c1")
    a = view([term(A, 4)], [Sel(c1, "full"), Sel(f1, "f1")])
    b = a.model_copy(update={"checks": list(reversed(a.checks))})
    assert price(a) == price(b)


# ── PRC-8 purity ─────────────────────────────────────────────────────────────

_ALLOWED_IMPORTS = {"__future__", "dataclasses", "decimal", "itertools", "typing", "types", "enum",
                    "pydantic", "app.agents.grader.plan_schemas",
                    "app.schemas.ontology_types", "app.services.selection_scoring"}


def test_pricer_module_is_pure():
    """PRC-8: no I/O, DB, LLM, clock, logging or randomness — by import scan."""
    src = Path(__file__).resolve().parents[2] / "app" / "services" / "pricing_v6.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    assert mods <= _ALLOWED_IMPORTS, f"impure imports: {sorted(mods - _ALLOWED_IMPORTS)}"
    banned = {"open", "print", "input", "__import__", "eval", "exec"}
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (calls & banned)


# ── Q-22 → AM-G13: BehaviorCap and a jointly chosen group charge ────────────
# Both examples were strict xfails at Phase 1: each lowered a total when the
# answer got better (PRC-6). They are ordinary tests now, and hand vectors too.

def test_prc6_charge_group_meets_a_floor():
    """[AM-G13 PRC-4] The group's one charge lands where it lowers the scope total
    most. On A (0.25 earned) it could only take 0.25; on B it takes the full 1 —
    so B pays, before and after A's fault is cleared (was 5.00 → 4.25)."""
    a_c = binary("A.c1", "A", "0.25")
    a_f = fault("A.f1", "A", [("m1", 1, "x")], group="g")
    b_c = binary("B.c1", "B", 5)
    b_f = fault("B.f1", "B", [("m2", 1, "x")], group="g")
    v = view([term("A", "0.25"), term("B", 5)],
             [Sel(a_c, "full"), Sel(a_f, "f1"), Sel(b_c, "full"), Sel(b_f, "f1")])
    before = price(v)
    after = price(v, overlay({"A.f1": CheckDecision(option_id="none")}))
    assert before.total_score == D("4.25")
    assert (_charge(before, "A.f1").status, _charge(before, "B.f1").status) == (
        "superseded", "applied")
    assert after.total_score == D("4.25")
    assert after.total_score >= before.total_score


def test_prc6_two_faults_on_one_behavior():
    """[AM-G13 PRC-3] BehaviorCap: the two faults on A.c2 together never cost more
    than its 3.5; the excess comes off the LATEST fault first (was 3.0 → 0.0)."""
    lad = ladder("A.c1", A, 4, [("p", PartialFraction.THREE_QUARTERS), ("q", PartialFraction.QUARTER)])
    beh = binary("A.c2", A, "3.5")
    f1 = fault("A.f1", A, [("m1", 4, "x")], requires="A.c2")
    f2 = fault("A.f2", A, [("m2", 6, "y")], requires="A.c2")
    v = view([term(A, "7.5")], [Sel(lad, "p1"), Sel(beh, "absent"), Sel(f1, "f1"), Sel(f2, "f1")])
    before = price(v)
    after = price(v, overlay({"A.c2": CheckDecision(option_id="full")}))
    assert before.total_score == D("3")
    assert after.total_score == D("3")
    assert [(c.check_id, c.charged, c.status) for c in _t(after).charges] == [
        ("A.f1", D("-3.5"), "capped"), ("A.f2", D("0"), "capped")]


def test_charge_groups_are_assigned_jointly():
    """[AM-G13 PRC-4] Two groups share two terminals. Chosen one group at a time
    (earliest member each), both charges land on X and one is absorbed by X's
    floor (total 2); chosen jointly, one lands on each (total 0). Enumeration is
    lexicographic — g1 then g2, members in plan order — and the FIRST minimum,
    (x1, y2), is kept."""
    xc = binary("X.c1", "X", 2)
    yc = binary("Y.c1", "Y", 2)
    x1 = fault("X.f1", "X", [("m1", 2, "x")], group="g1")
    y1 = fault("Y.f1", "Y", [("m2", 2, "x")], group="g1")
    x2 = fault("X.f2", "X", [("m3", 2, "y")], group="g2")
    y2 = fault("Y.f2", "Y", [("m4", 2, "y")], group="g2")
    v = view([term("X", 2), term("Y", 2)],
             [Sel(xc, "full"), Sel(yc, "full"), Sel(x1, "f1"), Sel(y1, "f1"),
              Sel(x2, "f1"), Sel(y2, "f1")])
    p = price(v)
    assert p.total_score == D("0")
    assert {cid: _charge(p, cid).status for cid in ("X.f1", "Y.f1", "X.f2", "Y.f2")} == {
        "X.f1": "applied", "Y.f1": "superseded", "X.f2": "superseded", "Y.f2": "applied"}


def test_prc6_holds_when_a_group_member_is_pinned():
    """[AM-G13, census Q-23] The group objective is the scope total WITH her
    terminal overrides. Measured before them, the charge would sit on the pinned
    X (where it costs nothing) until raising Y's credit made the two tie, then
    jump to Y by plan order: 5 → 4 for a better answer."""
    yc = ladder("Y.c1", "Y", 2, [("half", PartialFraction.HALF)])
    yf = fault("Y.f1", "Y", [("m1", 2, "x")], group="g")
    xc = binary("X.c1", "X", 5)
    xf = fault("X.f1", "X", [("m2", 2, "x")], group="g")
    v = view([term("Y", 2), term("X", 5)],
             [Sel(yc, "p1"), Sel(yf, "f1"), Sel(xc, "full"), Sel(xf, "f1")])
    pins = {"X": 4}
    before = price(v, overlay(pins=pins))
    after = price(v, overlay({"Y.c1": CheckDecision(option_id="full")}, pins=pins))
    assert after.total_score >= before.total_score
    assert (before.total_score, after.total_score) == (D("4"), D("4"))


def _pin_view():
    yc = ladder("Y.c1", "Y", 2, [("half", PartialFraction.HALF)])
    yf = fault("Y.f1", "Y", [("m1", 2, "x")], group="g")
    xc = binary("X.c1", "X", 5)
    xf = fault("X.f1", "X", [("m2", 2, "x")], group="g")
    return view([term("Y", 2), term("X", 5)],
                [Sel(yc, "p1"), Sel(yf, "f1"), Sel(xc, "full"), Sel(xf, "f1")])


def test_moved_by_pin_names_the_terminal_her_pin_displaced_the_charge_from():
    """[AM-G15] Unpinned, the group charge lands on X (it lowers the scope most
    there). She pins X at 4, so a charge on X would cost nothing: it lands on Y,
    and Y's fault row says why — naming X, the criterion she set by hand."""
    unpinned = price(_pin_view())
    assert _charge(unpinned, "X.f1").status == "applied"
    assert not any(c.moved_by_pin for t in unpinned.terminals for c in t.charges)

    pinned = price(_pin_view(), overlay(pins={"X": 4}))
    moved = _charge(pinned, "Y.f1")
    assert (moved.status, moved.moved_by_pin, moved.moved_from_terminal_id) == (
        "floored", True, "X")
    assert _charge(pinned, "X.f1").moved_by_pin is False          # superseded, not moved


def test_a_pin_that_does_not_move_the_charge_marks_nothing():
    """A pin on a terminal the charge never sat on moves nothing."""
    pinned = price(_pin_view(), overlay(pins={"Y": 1}))
    assert _charge(pinned, "X.f1").status == "applied"
    assert not any(c.moved_by_pin for t in pinned.terminals for c in t.charges)


def test_the_moved_by_pin_row_names_the_criterion_by_its_first_40_chars():
    from app.agents.explainer.copy import MACHINE_VOCABULARY, moved_by_pin_row_he
    row = moved_by_pin_row_he("  " + "א" * 45 + "  ")
    assert row == "נוכה כאן: אותה טעות, והציון ב«" + "א" * 40 + "» נקבע ידנית"
    assert not any(w in row for w in MACHINE_VOCABULARY)


def test_a_charge_group_across_scopes_is_refused():
    """V7 is a precondition of the joint assignment: a group spanning two scopes
    would be charged once in each. The pricer refuses rather than mis-price."""
    xc, xf = binary("X.c1", "X", 2), fault("X.f1", "X", [("m1", 1, "x")], group="g")
    yc, yf = binary("Y.c1", "Y", 2), fault("Y.f1", "Y", [("m2", 1, "x")], group="g")
    v = view([term("X", 2, q="q1"), term("Y", 2, q="q2")],
             [Sel(xc, "full"), Sel(xf, "f1"), Sel(yc, "full"), Sel(yf, "f1")])
    with pytest.raises(ValueError) as refused:
        price(v)
    assert str(refused.value) == (
        "charge group 'g' spans scopes ('q1', None) and ('q2', None) (V7): "
        "the pricer assigns a scope's groups jointly (AM-G13)")


def test_primary_check_ignores_non_credit_checks_listed_first():
    """The primary is the best CREDIT check, wherever faults and notes sit in
    plan order (mutation survivor 259: `continue` → `break` stopped the scan at
    the first non-credit check, which no builder had ever listed first)."""
    n1 = note("A.n1", A, "הערה")
    f1 = fault("A.f1", A, [("m1", 1, "x")])
    c1 = binary("A.c1", A, 1)
    c2 = binary("A.c2", A, 3)
    p = price(view([term(A, 4)], [Sel(n1, "none"), Sel(f1, "none"), Sel(c1, "full"), Sel(c2, "full")]))
    assert _t(p).primary_check_id == "A.c2"


# ── the pricer's I/O contract (declarative; the TS mirror parses the same JSON)

def test_pricer_models_are_frozen():
    from app.services import pricing_v6 as pv
    for model in (pv.ViewTerminal, pv.ViewCheck, pv.SelectionGroupView, pv.SelectionView,
                  pv.DraftV6View, pv.CheckDecision, pv.PricingOverlay, pv.ResolvedCheck,
                  pv.PricedCharge, pv.PricedTerminal, pv.PricedScope, pv.PricedTest):
        assert model.model_config.get("frozen") is True, model.__name__
    t = term(A, 4)
    with pytest.raises(Exception):
        t.points_possible = D("5")                                  # type: ignore[misc]


def test_absent_optional_fields_take_their_documented_defaults():
    """A field absent from the JSON must mean the same thing in Python as in
    the TS mirror: these defaults are part of the wire contract (PRC-7)."""
    from app.services import pricing_v6 as pv
    assert pv.ViewTerminal(terminal_id="t", question_id="q",
                           points_possible=D("1")).sub_question_id is None
    vc = pv.ViewCheck(plan=binary("t.c1", "t", 1), plan_index=0)
    assert vc.model_option_id is None and vc.quote_status is None
    assert pv.SelectionView(total_points=D("1"), question_order=["q"]).groups == []
    d = pv.CheckDecision()
    assert (d.option_id, d.amount, d.comment, d.evidence_disputed) == (None, None, None, False)
    o = pv.PricingOverlay()
    assert o.checks == {} and o.terminal_points == {}
    r = pv.ResolvedCheck(check_id="x", option_id=None, value=D("0"), source="default")
    assert r.missing is False and r.claimed_option_id is None
    ch = pv.PricedCharge(check_id="x", option_id="none", amount=D("0"), charged=D("0"),
                         status="no_fault")
    assert ch.moved_by_pin is False and ch.moved_from_terminal_id is None        # [AM-G15]
    # the quote vocabulary is closed: anything else is refused at the boundary
    with pytest.raises(Exception):
        pv.ViewCheck(plan=binary("t.c1", "t", 1), plan_index=0, quote_status="close")
