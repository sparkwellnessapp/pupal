"""
PLAN COMPILER v2 — Stage 1 calibration (PR §3 C1–C7, §7 A0's algebra half).

Two kinds of pin:

  * RULES, on synthetic text — Case 3 (both references), OD-9's residual, Case 2,
    Case 4, OD-10, OD-15, the code tail, the value-vs-tariff reading of «- N נק'».
  * THE HAND PLAN, terminal by terminal — the ratified `hobby_tvshow.plan.json` is
    the reference the compiler is calibrated against (PLAYBOOK: calibrating a NEW
    rule against the ratified plan is legitimate; relaxing a gate is not). Every
    hobby terminal's algebra is pinned, including the three places the compiler
    deliberately differs from the hand plan (recorded, with the reason).
  * BAGRUT, the numbers the PR names: counted 1, notes 2, Case 4 → 1 on q6.c6,
    Case 3 → (1,2,1,1)/(0.5,0.5,2,1,1), the routed set (OD-14).

Zero I/O beyond the two committed contracts. Zero spend.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Dict, List, Tuple

import pytest

from app.agents.plan_compiler import (CompilerBug, compile_contract, compile_terminal)
from app.agents.plan_compiler.compile import (case3_reconcile, even_split, scan_deductions)
from app.agents.grader.plan_schemas import GradingPlan
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

D = Decimal
G = D("0.25")


def _alg(t) -> List[Tuple]:
    """The comparable algebra of one terminal: (kind, points|amount, grouped?)."""
    out = []
    for s in t.slots:
        if s.kind in ("required", "counted"):
            out.append((s.kind, str(s.points)) if s.kind == "required"
                       else (s.kind, str(s.points), s.unit_count))
        elif s.kind == "tariff":
            out.append(("tariff", str(s.tariff_amount), s.charge_group is not None))
        else:
            out.append(("note_only",))
    return out


def _compile_one(text, points, *, has_solution=False, tid="t", scope="q1.א"):
    return compile_terminal(terminal_id=tid, scope=scope, text=text, points=D(points),
                            grid=G, has_solution=has_solution)


# ══════════════════════════════════════════════════════════════════════════
# Rules on synthetic text
# ══════════════════════════════════════════════════════════════════════════

class TestCase3:
    def test_reference_1_whole_point_absorption(self):
        vals, broke = case3_reconcile([D(1), D(3), D(1), D(1)], D(5), G)
        assert vals == [D(1), D(2), D(1), D(1)] and not broke

    def test_reference_2_minimal_residual_break(self):
        vals, broke = case3_reconcile([D(1), D(1), D(3), D(1), D(1)], D(5), G)
        assert vals == [D("0.5"), D("0.5"), D(2), D(1), D(1)] and broke

    def test_non_strict_reading_is_falsified(self):
        """`≥` would merge the 3 into the 1-class and yield 1,1,1,1,1 — reference 2
        says otherwise. Pinned so nobody relaxes the strict inequality."""
        vals, _ = case3_reconcile([D(1), D(1), D(3), D(1), D(1)], D(5), G)
        assert vals != [D(1)] * 5


class TestEvenSplit:
    def test_od9_on_the_partial_safe_lattice(self):
        """[OD-22] The PR's worked 1.75/1.75/1.5 halves to 0.875 — off the grid,
        refused by V4. On the ½-lattice 5 over 3 is 2/1.5/1.5, residual first."""
        vals, resid = even_split(D(5), 3, G)
        assert vals == [D(2), D("1.5"), D("1.5")] and resid

    def test_a_split_that_cannot_keep_halves_on_the_grid_is_refused(self):
        assert even_split(D("0.5"), 2, G) is None
        t = _compile_one("משתנים משמעותיים + קוד קריא", "0.5")
        assert _alg(t) == [("required", "0.5")]
        assert any(f.code == "split_below_partial_grid" for f in t.flags)

    def test_clean_split_has_no_residual(self):
        vals, resid = even_split(D(1), 2, G)
        assert vals == [D("0.5"), D("0.5")] and not resid


class TestC4Components:
    def test_paren_values(self):
        t = _compile_one("בדיקה (1)+ צבירה (1)+ קידום (1 כ\"א)", "3")
        assert _alg(t) == [("required", "1")] * 3

    def test_nk_values_and_worded_paren(self):
        t = _compile_one("הגדרת משתנה + _ + אתחול (אתחול 1 נקודות)", "2")
        assert _alg(t) == [("required", "1"), ("required", "1")]
        assert any(f.code == "case2_unvalued_fill" for f in t.flags)

    def test_reversed_inline_values_inside_a_paren(self):
        t = _compile_one("בדיקה, להחזיר false (if נק' 1, החזרת false נקודה 1) if (x % 2 != 0) return false;", "2")
        assert _alg(t) == [("required", "1"), ("required", "1")]
        assert any(f.code == "code_tail_ignored" for f in t.flags)

    def test_bare_values_only_when_they_sum_to_P(self):
        t = _compile_one("לולאה 0.5 אם חיובי 2 העתק 1 קידום 1 for (int i = 0; i < n; i++) { }", "4.5")
        assert [s.points for s in t.earn_slots] == [D("0.5"), D(2), D(1), D(1)]
        t2 = _compile_one("מערך בגודל 31 ואיפוס ל-0 עד 20", "2")
        assert _alg(t2) == [("required", "2")]

    def test_a_single_bare_number_never_becomes_a_value(self):
        t = _compile_one("קליטה של 3 נתוני התחביב (name, isSportive, minutes)", "3")
        assert _alg(t) == [("required", "1")] * 3        # the identifier list, not «3»
        assert any(f.code == "identifier_list_split" for f in t.flags)

    def test_plus_separators_even_split(self):
        t = _compile_one("כותרת הפעולה + טיפוס מוחזר bool", "2")
        assert _alg(t) == [("required", "1"), ("required", "1")]

    def test_each_marker_applies_to_every_component(self):
        t = _compile_one("יצירת 2 מונים + אתחולם ב-0 (0.5 כ\"א)", "1")
        assert _alg(t) == [("required", "0.5"), ("required", "0.5")]

    def test_case2_remainder_slot_when_everything_stated_is_short(self):
        t = _compile_one("בדיקת הקיבולת עצמה 1 נקודה", "5")
        assert [s.points for s in t.earn_slots] == [D(1), D(4)]
        rem = t.earn_slots[1]
        assert rem.summary == "" and "case2_remainder" in rem.flags
        assert rem.source_span == "בדיקת הקיבולת עצמה 1 נקודה"      # quotes the whole criterion

    def test_total_claim_is_not_a_value(self):
        t = _compile_one("והאם סה\"כ הדירוגים קטן מהמינימום - סה\"כ 2 נקודות", "3")
        assert _alg(t) == [("required", "3")]
        assert any(f.code == "text_total_disagrees" for f in t.flags)

    def test_numbered_list_splits_evenly(self):
        t = _compile_one("1. הגדרה 2. אתחול 3. קידום", "3")
        assert _alg(t) == [("required", "1")] * 3


class TestC1Deductions:
    def test_clause_is_the_if_sentence_not_the_paragraph(self):
        text = ("הגדרת לולאה מ-0 עד length אם התחילו מ-1 במקום מ-0 להוריד 0.5 "
                "אם ניגשו למערך בלי Getter להוריד 1 אם טעו בגבול העליון להוריד 0.5")
        deds = scan_deductions(text)
        assert [d.clause for d in deds] == [
            "אם התחילו מ-1 במקום מ-0 להוריד 0.5",
            "אם ניגשו למערך בלי Getter להוריד 1",
            "אם טעו בגבול העליון להוריד 0.5"]
        t = _compile_one(text, "3")
        assert _alg(t) == [("required", "3"), ("tariff", "0.5", False),
                           ("tariff", "1", False), ("tariff", "0.5", False)]

    def test_identical_phrases_are_not_deduped(self):
        text = "בדיקה 1 נקודה אם לא השתמשו בפעולה להוריד 2, אם לא השתמשו באף אחת להוריד 3 אם לא עדכנו להוריד 2"
        assert [d.amount for d in scan_deductions(text)] == [D(2), D(3), D(2)]

    def test_case4_takes_the_lenient_end(self):
        t = _compile_one("הדפסת מספר המכינה אם הדפיסו את הכמות להוריד 2 (או 1?)", "2")
        assert _alg(t) == [("required", "2"), ("tariff", "1", False)]
        assert any(f.code == "case4_lenient" for f in t.flags)

    def test_charge_once_makes_a_group_shared_by_identical_hosts(self):
        text = "חישוב הממוצע והדפסה (1) אם לא המירו לממשי להוריד 0.5 (רק פעם אחת)"
        a = _compile_one(text, "1", tid="a")
        b = _compile_one(text, "1", tid="b")
        ga, gb = a.tariff_slots[0].charge_group, b.tariff_slots[0].charge_group
        assert ga and ga == gb

    def test_fold_when_the_deduction_is_the_components_own_failure(self):
        """«בדיקה … שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1» — the hand plan
        carries no tariff here: a 1-point check whose miss costs 1 IS the check."""
        t = _compile_one("בדיקה האם המונה שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1"
                         "חישוב הממוצע והדפסה (1) (אם טעו בחישוב מתמטי להוריד 0.5)", "2")
        assert _alg(t) == [("required", "1"), ("required", "1"), ("tariff", "0.5", False)]
        assert any(f.code == "tariff_folded_into_component" for f in t.flags)

    def test_a_dash_value_closing_a_clause_is_not_a_tariff(self):
        t = _compile_one("זיהוי שמדובר בפעולת סכימה – 2 נק'", "2")
        assert _alg(t) == [("required", "2")]
        assert any(f.code == "tariff_reclassified_as_value" for f in t.flags)

    def test_amountless_lknos_takes_the_value_of_the_component_it_names(self):
        text = ("בדיקה אם המערך במקום ה- i שונה מ- null (1 נקודות) זימון של פעולה פנימית "
                "TotalEarnings עבור המערך במקום ה- i (3 נקודות) (לקנוס פעם אחת אם לא בדקו אם "
                "arr[i]!=null , הערה למטה) השוואה אם התוצאה גבוהה מהפרמטר (1 נקודה) קידום המונה (1 נקודה)")
        t = _compile_one(text, "5")
        assert [s.points for s in t.earn_slots] == [D(1), D(2), D(1), D(1)]        # Case 3
        assert _alg(t)[-1] == ("tariff", "1", True)
        assert any(f.code == "tariff_amount_inferred" for f in t.flags)

    def test_amountless_once_without_a_condition_takes_the_preceding_component(self):
        text = ("לולאה שנייה (B) נכונה (1 נקודה) בדיקה אם המערך במקום ה- i שונה מ- null(1 נקודות), "
                "להוריד רק פעם אחת שימוש ב-Getter (3 נקודות) השמה במערך החדש (1 נקודה) "
                "תוך קידום אינדקס נפרד (namesIndex)(1 נקודה)")
        t = _compile_one(text, "5")
        assert [s.points for s in t.earn_slots] == [D("0.5"), D("0.5"), D(2), D(1), D(1)]
        assert _alg(t)[-1] == ("tariff", "1", True)


class TestC3Counted:
    def test_uniform_units(self):
        t = _compile_one('ניקוד טבלת מעקב סה"כ 12 נקודות: 17 תאים  0.7 כל תא', "12")
        assert _alg(t) == [("counted", "12", 17)]
        assert any(f.code == "counted_per_unit_rounding" for f in t.flags)   # 17 × 0.7 ≠ 12


class TestC7Routing:
    def test_routes_only_a_monolith_at_or_above_4_with_a_solution(self):
        assert _compile_one("פעולה בונה", "5", has_solution=True).routed
        assert not _compile_one("פעולה בונה", "3", has_solution=True).routed
        assert not _compile_one("פעולה בונה", "5", has_solution=False).routed
        assert not _compile_one("כותרת + טיפוס", "5", has_solution=True).routed


def test_v1_is_asserted_as_a_compiler_bug(monkeypatch):
    import app.agents.plan_compiler.compile as c
    monkeypatch.setattr(c, "even_split", lambda p, n, g: ([D(1)] * n, False))
    with pytest.raises(CompilerBug):
        _compile_one("כותרת + טיפוס", "5")


# ══════════════════════════════════════════════════════════════════════════
# The hand plan — hobby, every terminal
# ══════════════════════════════════════════════════════════════════════════

def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def hobby():
    b = load_bundle("dan_basiuk")
    return compile_contract(b.rubric_contract, exam_id="hobby_tvshow",
                            rubric_contract_sha256=_sha(SUITE_DIR / "compiled_rubric_1.json")
                            if (SUITE_DIR / "compiled_rubric_1.json").exists() else "0" * 64)


@pytest.fixture(scope="module")
def bagrut():
    b = load_bundle("bagrut_899371.din_ezra", require_gt=False)
    return compile_contract(b.rubric_contract, exam_id="bagrut_899371",
                            rubric_contract_sha256="0" * 64)


HOBBY_EXPECTED: Dict[str, List[Tuple]] = {
    # q1.א — two monoliths, both routed (PR C7 list)
    "q1.א.c0": [("required", "4")],
    "q1.א.c1": [("required", "4")],
    # q1.ב
    "q1.ב.c0": [("required", "1"), ("required", "1")],
    "q1.ב.c1": [("required", "1")],
    "q1.ב.c2": [("required", "3")],            # hand: 1.5/1.5 on «או» — DIVERGENCE-1
    "q1.ב.c3": [("required", "1")] * 3,
    "q1.ב.c4": [("required", "3")],            # hand: 1.5/1.5 at «בתא» — DIVERGENCE-2
    "q1.ב.c5": [("required", "1")],
    "q1.ב.c6": [("required", "1"), ("required", "1")],   # «להוריד 1» folded (hand agrees)
    "q1.ב.c7": [("required", "1")],
    # q1.ג
    "q1.ג.c0": [("required", "0.5"), ("required", "0.5")],
    "q1.ג.c1": [("required", "0.5"), ("required", "0.5")],
    "q1.ג.c2": [("required", "0.5"), ("required", "0.5")],
    "q1.ג.c3": [("required", "3"), ("tariff", "1", False)],
    "q1.ג.c4": [("required", "1")] * 3,
    "q1.ג.c5": [("required", "1")] * 3,
    "q1.ג.c6": [("required", "1"), ("required", "1"), ("tariff", "0.5", False), ("tariff", "0.5", True)],
    "q1.ג.c7": [("required", "1"), ("required", "1"), ("tariff", "0.5", False), ("tariff", "0.5", True)],
    # q2.א — routed
    "q2.א.c0": [("required", "5")],
    "q2.א.c1": [("required", "10")],           # the hand's owner tariff is a ruling, not text
    # q2.ב
    "q2.ב.c0": [("required", "2")],
    "q2.ב.c1": [("required", "2")],
    "q2.ב.c2": [("required", "3")],
    "q2.ב.c3.s0": [("required", "3"), ("tariff", "0.5", False), ("tariff", "1", False), ("tariff", "0.5", False)],
    "q2.ב.c3.s1": [("required", "2")],
    "q2.ב.c3.s2": [("required", "2"), ("tariff", "1", False)],
    "q2.ב.c3.s3": [("required", "5"), ("tariff", "1", False)],
    # DIVERGENCE-3/4: «הגדרת מינימום דירוג + אתחול» / «הגדרת ערוץ מינימלי +אתחול» —
    # C4's « + » rule (PR §3, ratified) splits; the hand plan priced each as ONE
    # check of 1. The compiler's set {0,.25,.5,.75,1} is a superset of the hand's.
    "q2.ב.c4.s0": [("required", "0.5"), ("required", "0.5")],
    "q2.ב.c4.s1": [("required", "0.5"), ("required", "0.5")],
    "q2.ב.c4.s2": [("required", "2")],         # the hand's 0.5 tariff is an owner ruling
    # OD-10 → the parent's 3-point tariff, on the first child that can CARRY it
    # (V3): s3 — exactly the hand plan's anchor (OD-23).
    "q2.ב.c4.s3": [("required", "3"), ("tariff", "3", True), ("note_only",)],
    "q2.ב.c4.s4": [("required", "1")],
    "q2.ב.c4.s5": [("required", "1")],
    "q2.ב.c5": [("required", "1")],
    # q2.ג
    "q2.ג.c0.s0": [("required", "2")],
    "q2.ג.c0.s1": [("required", "3")],
    "q2.ג.c0.s2": [("required", "3"), ("tariff", "1", False)],
    "q2.ג.c0.s3": [("required", "2")] * 4,
}


def test_hobby_every_terminal_matches_the_hand_plan_algebra(hobby):
    got = {t.terminal_id: _alg(t) for t in hobby.terminals}
    assert set(got) == set(HOBBY_EXPECTED)
    diff = {k: (got[k], v) for k, v in HOBBY_EXPECTED.items() if got[k] != v}
    assert diff == {}, "\n".join(f"{k}: got {g} expected {e}" for k, (g, e) in diff.items())


def test_hobby_tariffs_12_of_12_and_one_note(hobby):
    assert sum(len(t.tariff_slots) for t in hobby.terminals) == 12
    assert sum(len(t.note_slots) for t in hobby.terminals) == 1
    assert sum(1 for t in hobby.terminals for s in t.slots if s.kind == "counted") == 0


def test_hobby_routed_set_is_the_pr_list_plus_the_od14_finding(hobby):
    routed = {t.terminal_id for t in hobby.terminals if t.routed}
    assert routed == {"q1.א.c0", "q1.א.c1", "q2.א.c0", "q2.א.c1", "q2.ב.c3.s3"}


def test_od10_parent_tariff_anchors_on_the_first_child_that_can_carry_it(hobby):
    """OD-10 as ratified says «first child»; V3 forbids a 3-point tariff on a
    1-point terminal. s3 is the first sibling with P ≥ 3 — and the hand plan's
    own anchor. Surfaced as OD-23."""
    s3 = hobby.terminal("q2.ב.c4.s3")
    g = s3.tariff_slots[0].charge_group
    assert g and g.startswith("q2.ב:q2.ב.c4:")
    assert not hobby.terminal("q2.ב.c4.s0").tariff_slots
    assert any(f.code == "parent_tariff_first_child_group" and f.terminal_id == "q2.ב.c4.s3"
               for f in hobby.flags)


def test_the_cast_once_group_is_shared_across_c6_and_c7(hobby):
    g6 = [s.charge_group for s in hobby.terminal("q1.ג.c6").tariff_slots if s.charge_group]
    g7 = [s.charge_group for s in hobby.terminal("q1.ג.c7").tariff_slots if s.charge_group]
    assert g6 == g7 and len(g6) == 1


def test_hobby_expressibility_matches_the_hand_plan_where_the_algebra_agrees(hobby):
    """Where the compiler and the hand plan agree on the algebra, the reachable
    award sets must be identical — the pricer sees the same numbers."""
    from tests.grading_eval_suite.plan_expressibility import reachable_awards
    from app.agents.plan_compiler.assemble import assemble_placeholder_plan
    from app.agents.grader.plan_schemas import TerminalPlan
    hand = GradingPlan.model_validate_json(
        (SUITE_DIR / "plans" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    plan = assemble_placeholder_plan(hobby)
    compared = 0
    for tp in plan.terminals:
        ht = hand.terminal(tp.terminal_id)
        # the two owner RULINGS cite no rubric text; the compiler cannot see them
        gen = TerminalPlan(terminal_id=ht.terminal_id, points_possible=ht.points_possible,
                           checks=[c for c in ht.checks if c.source == "generated"])
        # order-insensitive: the hand plan lists q2.ב.c4.s3's note before its
        # tariff, the compiler emits earn → tariffs → notes; same algebra
        same = (sorted((c.kind, c.points, c.tariff_amount or D(0)) for c in gen.checks)
                == sorted((c.kind, c.points, c.tariff_amount or D(0)) for c in tp.checks))
        if same:
            compared += 1
            assert reachable_awards(tp, G) == reachable_awards(gen, G), tp.terminal_id
    # 38 hobby terminals − 4 routed (the hand decomposed them by hand) − the
    # four recorded divergences (q1.ב.c2, q1.ב.c4, q2.ב.c4.s0, q2.ב.c4.s1) = 30
    assert compared == 30


def test_compilation_is_byte_identical(hobby):
    b = load_bundle("dan_basiuk")
    again = compile_contract(b.rubric_contract, exam_id="hobby_tvshow",
                             rubric_contract_sha256=hobby.rubric_contract_sha256)
    assert again == hobby


# ══════════════════════════════════════════════════════════════════════════
# Bagrut — the PR's named numbers
# ══════════════════════════════════════════════════════════════════════════

def test_bagrut_counted_notes_case4_case3(bagrut):
    assert _alg(bagrut.terminal("q1.א.1.c0")) == [("counted", "12", 17)]
    assert sum(1 for t in bagrut.terminals for s in t.slots if s.kind == "counted") == 1
    assert sum(len(t.note_slots) for t in bagrut.terminals) == 2
    assert _alg(bagrut.terminal("q6.c6")) == [("required", "2"), ("tariff", "1", False)]
    assert [s.points for s in bagrut.terminal("q4.ב.c4").earn_slots] == [D(1), D(2), D(1), D(1)]
    assert [s.points for s in bagrut.terminal("q4.ב.c7").earn_slots] == [D("0.5"), D("0.5"), D(2), D(1), D(1)]


def test_bagrut_null_check_once_group_is_shared_by_c4_and_c7(bagrut):
    g4 = [s.charge_group for s in bagrut.terminal("q4.ב.c4").tariff_slots if s.charge_group]
    g7 = [s.charge_group for s in bagrut.terminal("q4.ב.c7").tariff_slots if s.charge_group]
    assert g4 and set(g4) & set(g7)


def test_bagrut_routed_set(bagrut):
    routed = {t.terminal_id for t in bagrut.terminals if t.routed}
    pr_list = {"q2.א.c4", "q2.ב.c3", "q3.ב.c4", "q4.א.c1", "q5.א.c1", "q5.ב.c2", "q6.c8"}
    # OD-14: q2.ב.c3 carries explicit values (0.5/2/1/1) and is NOT a monolith;
    # q1.ב.1.c0 («ניקוד: 6 נקודות») and q6.c5 («(4 נקודות)») are degenerate monoliths.
    assert routed == (pr_list - {"q2.ב.c3"}) | {"q1.ב.1.c0", "q6.c5"}


def test_bagrut_tariff_composition(bagrut):
    """The PR counted 10 detections. The compiler DETECTS all of them and adds
    two the sentence-level detector lost (the second «להוריד 2» on q5.ב.c4 and
    c7's «להוריד רק פעם אחת»); three are dispositioned, each flagged:
    «– 2 נק'» on q1.ב.2.c0 is a value (OD-20); q5.א.c0/q6.c0's «כל טעות להוריד 1»
    on a 1-point terminal is the component's own failure (OD-21)."""
    by = {t.terminal_id: t for t in bagrut.terminals}
    amounts = {tid: [str(s.tariff_amount) for s in t.tariff_slots] for tid, t in by.items()
               if t.tariff_slots}
    assert amounts == {
        "q4.ב.c4": ["1"],
        "q4.ב.c7": ["1", "3"],
        "q5.ב.c2": ["2", "1"],
        "q5.ב.c4": ["2", "3", "2"],
        "q6.c6": ["1"],
    }
    folded = {f.terminal_id for f in bagrut.all_flags if f.code == "tariff_folded_into_component"}
    assert folded == {"q5.א.c0", "q6.c0"}
    assert not by["q1.ב.2.c0"].tariff_slots and _alg(by["q1.ב.2.c0"]) == [("required", "2")]


def test_bagrut_every_terminal_sums_and_sits_on_the_grid(bagrut):
    for t in bagrut.terminals:
        assert sum(s.points for s in t.earn_slots) == t.points_possible, t.terminal_id
    assert len(bagrut.terminals) == 61
