"""
grader-v6 pricer-parity vectors — `tests/fixtures/grade_review/pricing_v6_vectors.json`.

The v6 pricer (`app/services/pricing_v6.py`) and its TypeScript mirror
(Phase 5) must agree on every vector, byte for byte (PRC-7). Two families:

  hand       the worked examples of §4.5 (E1–E10; E3 dropped by AM-G9) and
             the amendments' named cases (AM-G2 gate, AM-G3 amounts, Q-10
             notes, charge groups, floors, selection groups, and AM-G13's
             BehaviorCap / joint group assignment — both sides of each PRC-6
             move that was a Phase-1 counterexample, …)
  generated  500 random cases from the ONE case builder
             (`tests/services/pricing_v6_cases.build_random_case`), driven by
             a seeded PRNG. Not Hypothesis's engine: its example stream is not
             stable across library versions, and this file must regenerate
             byte-identically from a clean checkout (A-2).

    python scripts/gen_pricing_v6_vectors.py            # write
    python scripts/gen_pricing_v6_vectors.py --check    # fail on any diff
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

OUT = BACKEND / "tests" / "fixtures" / "grade_review" / "pricing_v6_vectors.json"
SEED = 20260927
N_GENERATED = 500


def _hand_cases() -> List[Tuple[str, object, Optional[object]]]:
    from app.agents.grader.plan_schemas import PartialFraction
    from app.services.pricing_v6 import CheckDecision
    from tests.services.pricing_v6_cases import (
        E10_TID, Sel, binary, count, e10_checks, fault, ladder, levels, note, overlay, term,
        view)

    A = "A"
    c4 = binary("A.c1", A, 4, desc="עדכון התכונה people")
    f2 = fault("A.f1", A, [("m1", 2, "העדכון בגישה ישירה במקום SetPeople")], requires="A.c1")

    def e1(c, f, q="exact"):
        return view([term(A, 4)], [Sel(c4, c, q), Sel(f2, f, q)])

    tiers = fault("A.f1", A, [("m1", 2, "t1"), ("m2", 3, "t2"), ("m3", 4, "t3")], requires="A.c1")
    lad = ladder("A.c1", A, 2, [("half", PartialFraction.HALF)])
    c2 = binary("A.c2", A, 2)
    capped = fault("A.f1", A, [("m1", 2, "x")], requires="A.c1")
    lv = levels("A.c1", A, [("מצוין", 40), ("טוב", 30), ("בינוני", 20), ("חלש", 10), ("אין", 0)])
    lv_absent = levels("A.c1", A, [("מצוין", 4), ("טוב", 3)])
    cnt = count("A.c1", A, 3, 8)
    g1c, g2c = binary("T1.c1", "T1", 2), binary("T2.c1", "T2", 2)
    g1f = fault("T1.f1", "T1", [("m1", 1, "חסר public")], group="g")
    g2f = fault("T2.f1", "T2", [("m2", 1, "חסר public")], group="g")
    big1c, big2c = binary("T1.c1", "T1", 4), binary("T2.c1", "T2", 4)
    big1f = fault("T1.f1", "T1", [("m1", 1, "x")], group="g")
    big2f = fault("T2.f1", "T2", [("m2", 3, "x")], group="g")
    ungated = fault("A.f1", A, [("m1", 3, "x")])
    two_a = fault("A.f1", A, [("m1", 2, "x")])
    two_b = fault("A.f2", A, [("m2", 2, "y")])
    c3 = binary("A.c1", A, 3)
    legacy = fault("A.f1", A, [("m1", 2, "x")], evidence_required=False)
    gated_fault = fault("A.f1", A, [("m1", 2, "x")], requires="A.c1")
    nt = note("A.n1", A, "לא נבדק שימוש בערוץ")
    q1c, q2c = binary("q1.c0.c1", "q1.c0", 10), binary("q2.c0.c1", "q2.c0", 10)
    q3c = binary("q3.c0.c1", "q3.c0", 5)
    cap, upd, e10 = e10_checks()
    t10 = term(E10_TID, 5, q="q5", sq="ב")
    inactive_group_a = fault("T1.f1", "T1", [("m1", 3, "x")], requires="T1.c1", group="g")
    inactive_group_b = fault("T2.f1", "T2", [("m2", 1, "x")], group="g")
    # AM-G13 (census Q-22 / Q-23)
    fl_ac, fl_af = binary("A.c1", "A", "0.25"), fault("A.f1", "A", [("m1", 1, "x")], group="g")
    fl_bc, fl_bf = binary("B.c1", "B", 5), fault("B.f1", "B", [("m2", 1, "x")], group="g")
    floor_view = view([term("A", "0.25"), term("B", 5)],
                      [Sel(fl_ac, "full"), Sel(fl_af, "f1"), Sel(fl_bc, "full"), Sel(fl_bf, "f1")])
    bc_lad = ladder("A.c1", A, 4, [("p", PartialFraction.THREE_QUARTERS), ("q", PartialFraction.QUARTER)])
    bc_beh = binary("A.c2", A, "3.5")
    bc_f1 = fault("A.f1", A, [("m1", 4, "x")], requires="A.c2")
    bc_f2 = fault("A.f2", A, [("m2", 6, "y")], requires="A.c2")
    bc_view = view([term(A, "7.5")], [Sel(bc_lad, "p1"), Sel(bc_beh, "absent"),
                                      Sel(bc_f1, "f1"), Sel(bc_f2, "f1")])
    jx, jy = binary("X.c1", "X", 2), binary("Y.c1", "Y", 2)
    joint_view = view([term("X", 2), term("Y", 2)], [
        Sel(jx, "full"), Sel(jy, "full"),
        Sel(fault("X.f1", "X", [("m1", 2, "x")], group="g1"), "f1"),
        Sel(fault("Y.f1", "Y", [("m2", 2, "x")], group="g1"), "f1"),
        Sel(fault("X.f2", "X", [("m3", 2, "y")], group="g2"), "f1"),
        Sel(fault("Y.f2", "Y", [("m4", 2, "y")], group="g2"), "f1")])
    pin_view = view([term("Y", 2), term("X", 5)], [
        Sel(ladder("Y.c1", "Y", 2, [("half", PartialFraction.HALF)]), "p1"),
        Sel(fault("Y.f1", "Y", [("m1", 2, "x")], group="g"), "f1"),
        Sel(binary("X.c1", "X", 5), "full"),
        Sel(fault("X.f1", "X", [("m2", 2, "x")], group="g"), "f1")])

    return [
        ("E1:direct-access", e1("full", "f1"), None),
        ("E1:no-update", e1("absent", "f1"), None),
        ("E1:correct", e1("full", "none"), None),
        ("E2:one-tier", view([term(A, 4)], [Sel(c4, "full"), Sel(tiers, "f2")]), None),
        ("E4:group-tie-earliest", view([term("T1", 2), term("T2", 2)],
                                       [Sel(g1c, "full"), Sel(g1f, "f1"),
                                        Sel(g2c, "full"), Sel(g2f, "f1")]), None),
        ("E4:group-largest", view([term("T1", 4), term("T2", 4)],
                                  [Sel(big1c, "full"), Sel(big1f, "f1"),
                                   Sel(big2c, "full"), Sel(big2f, "f1")]), None),
        ("E5:cap-by-behavior", view([term(A, 4)], [Sel(lad, "p1"), Sel(c2, "full"),
                                                   Sel(capped, "f1")]), None),
        ("E6:floor-single", view([term(A, 2)], [Sel(binary("A.c1", A, 2), "full"),
                                                Sel(ungated, "f1")]), None),
        ("E6:floor-reverse-order", view([term(A, 3)], [Sel(c3, "full"), Sel(two_a, "f1"),
                                                       Sel(two_b, "f1")]), None),
        ("E7:levels-L2", view([term(A, 40)], [Sel(lv, "L2")]), None),
        ("E7:levels-absent-added", view([term(A, 4)], [Sel(lv_absent, "absent")]), None),
        ("E8:count-half-up", view([term(A, 3)], [Sel(cnt, "n5")]), None),
        ("E8:count-top", view([term(A, 3)], [Sel(cnt, "n8")]), None),
        ("E9:overlay-absent", e1("full", "f1"), overlay({"A.c1": CheckDecision(option_id="absent")})),
        ("E9:terminal-override", e1("full", "f1"), overlay(pins={A: 3})),
        ("E10:din-roni", view([t10], [Sel(cap, "full"), Sel(upd, "full"), Sel(e10, "f1")]), None),
        ("E10:yahli", view([t10], [Sel(cap, "absent"), Sel(upd, "absent"), Sel(e10, "f2")]), None),
        ("E10:neither-used", view([t10], [Sel(cap, "full"), Sel(upd, "full"), Sel(e10, "f2")]), None),
        ("E10:capacity-only", view([t10], [Sel(cap, "full"), Sel(upd, "absent"), Sel(e10, "f3")]), None),
        ("PRC-1:missing", e1(None, None), None),
        ("PRC-1:foreign-option", e1("zz_foreign", "none"), None),
        ("AM-G2:gated-credit", e1("full", "none", "not_found"), None),
        ("AM-G2:confirmed-by-her", e1("full", "none", "not_found"),
         overlay({"A.c1": CheckDecision(option_id="full")})),
        ("AM-G2:gated-fault", view([term(A, 4)], [Sel(c4, "full", "exact"),
                                                  Sel(gated_fault, "f1", "not_found")]), None),
        ("AM-G2:legacy-fault-ungated", view([term(A, 4)], [Sel(c4, "full", "exact"),
                                                           Sel(legacy, "f1", "not_found")]), None),
        ("AM-G2:fuzzy-is-verified", e1("full", "f1", "fuzzy"), None),
        ("AM-G3:amount-activates-fault", e1("absent", "f1"),
         overlay({"A.c1": CheckDecision(amount=Decimal("1.5"))})),
        ("AM-G3:amount-partial", e1("full", "none"),
         overlay({"A.c1": CheckDecision(amount=Decimal("2.5"))})),
        ("Q-10:note-observed", view([term(A, 3)], [Sel(c3, "full"), Sel(nt, "observed")]), None),
        ("Q-10:note-none", view([term(A, 3)], [Sel(c3, "full"), Sel(nt, "none")]), None),
        ("PRC-5:upper-clamp-logic-bug", view([term(A, 4)], [Sel(binary("A.c1", A, 5), "full")]), None),
        ("PRC-2:inactive-member-leaves-group", view(
            [term("T1", 4), term("T2", 4)],
            [Sel(binary("T1.c1", "T1", 4), "absent"), Sel(inactive_group_a, "f1"),
             Sel(binary("T2.c1", "T2", 4), "full"), Sel(inactive_group_b, "f1")]), None),
        ("selection:choose-1-of-2", view([term("q1.c0", 10, q="q1"), term("q2.c0", 10, q="q2")],
                                         [Sel(q1c, "full"), Sel(q2c, "absent")],
                                         groups=[(["q1", "q2"], 1)]), None),
        ("selection:mandatory-plus-group", view(
            [term("q1.c0", 10, q="q1"), term("q2.c0", 10, q="q2"), term("q3.c0", 5, q="q3")],
            [Sel(q1c, "absent"), Sel(q2c, "full"), Sel(q3c, "full")],
            groups=[(["q1", "q2"], 1)]), None),
        ("primary:tie-plan-order", view([term(A, 4)], [Sel(binary("A.c1", A, 2), "full"),
                                                       Sel(binary("A.c2", A, 2), "full")]), None),
        ("override:clamped", e1("full", "none"), overlay(pins={A: 9})),
        ("AM-G13:group-meets-a-floor", floor_view, None),
        ("AM-G13:group-meets-a-floor/cleared", floor_view,
         overlay({"A.f1": CheckDecision(option_id="none")})),
        ("AM-G13:behavior-cap/absent", bc_view, None),
        ("AM-G13:behavior-cap/raised", bc_view, overlay({"A.c2": CheckDecision(option_id="full")})),
        ("AM-G13:groups-assigned-jointly", joint_view, None),
        ("AM-G13:pinned-member", pin_view, overlay(pins={"X": 4})),
        ("AM-G13:pinned-member/raised", pin_view,
         overlay({"Y.c1": CheckDecision(option_id="full")}, pins={"X": 4})),
    ]


def _dump(model) -> object:
    return json.loads(model.model_dump_json())


def _vector(case: str, kind: str, view, ov) -> dict:
    from app.services.pricing_v6 import price
    priced = price(view, ov)
    return {"case": case, "kind": kind,
            "input": {"view": _dump(view), "overlay": _dump(ov) if ov is not None else None},
            "expected": _dump(priced)}


def _strip_text(view):
    """Pricing never reads labels, descriptions or spans; the generated vectors
    drop them so the committed file stays small. Hand cases keep their real
    text (E10 carries the teacher's own words)."""
    checks = []
    for vc in view.checks:
        plan = vc.plan.model_copy(update={
            "description_he": "", "source_span": "",
            "options": [o.model_copy(update={"label_he": ""}) for o in vc.plan.options]})
        checks.append(vc.model_copy(update={"plan": plan}))
    return view.model_copy(update={"checks": checks})


def all_vectors() -> List[dict]:
    from tests.services.pricing_v6_cases import PrngDraw, build_random_case
    vectors = [_vector(name, "hand", v, ov) for name, v, ov in _hand_cases()]
    for i in range(N_GENERATED):
        v, ov = build_random_case(PrngDraw(SEED + i), max_questions=2, max_subs=1,
                                  max_terminals=2)
        vectors.append(_vector(f"generated:{i:03d}", "generated", _strip_text(v), ov))
    return vectors


def render(vectors: List[dict]) -> str:
    """One compact vector per line: small, and a pricer change diffs by case."""
    lines = [json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
             for v in vectors]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="regenerate and fail on any diff (fixtures-regenerate-clean)")
    args = ap.parse_args()
    text = render(all_vectors())
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if args.check:
        if current != text:
            raise SystemExit(f"{OUT.name} is stale — rerun without --check")
        print(f"{OUT.name}: clean")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(BACKEND)} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
