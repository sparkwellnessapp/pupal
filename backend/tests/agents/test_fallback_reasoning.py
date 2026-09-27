"""grader-v6 Phase 1 — the fallback reasoning composer (§7.5). Pure, zero mocks.

The composer is the line a teacher sees when the explainer fails; it must be
deterministic, ≤ 200 chars, and free of machine vocabulary (CWV-5)."""
from __future__ import annotations

from app.agents.explainer.fallback import (
    FULLY_EARNED_HE,
    MACHINE_VOCABULARY,
    compose_reasoning_he,
)
from app.agents.grader.plan_schemas import PartialFraction
from app.services.pricing_v6 import price
from tests.services.pricing_v6_cases import Sel, binary, fault, ladder, term, view

A = "A"


def _line(sels, p=4):
    v = view([term(A, p)], sels)
    return compose_reasoning_he(price(v), v, A)


def test_fallback_reasoning_all_branches_and_truncation():
    c1 = binary("A.c1", A, 2, desc="הגדרת לולאה")
    lad = ladder("A.c2", A, 2, [("הלולאה עוצרת איבר אחד לפני הסוף", PartialFraction.HALF)],
                 desc="גבולות הלולאה")
    f1 = fault("A.f1", A, [("m1", 1, "גישה ישירה לתכונה")], requires="A.c1")
    # fully earned, no charges
    assert _line([Sel(c1, "full"), Sel(lad, "full"), Sel(f1, "none")]) == FULLY_EARNED_HE
    # zero credit → «חסר: …»; partial → «desc: label»; applied fault → «נוכה: label»
    line = _line([Sel(c1, "full"), Sel(lad, "p1"), Sel(f1, "f1")])
    assert line == "גבולות הלולאה: הלולאה עוצרת איבר אחד לפני הסוף · נוכה: גישה ישירה לתכונה"
    line = _line([Sel(c1, "absent"), Sel(lad, "full"), Sel(f1, "f1")])
    assert line == "חסר: הגדרת לולאה"                       # inactive fault is not «נוכה»
    # truncation at the last « · », then « …»
    many = [binary(f"A.c{i}", A, 1, desc="רכיב ארוך מאוד " * 3 + str(i)) for i in range(1, 9)]
    line = _line([Sel(c, "absent") for c in many], p=8)
    assert len(line) <= 200 and line.endswith(" …")
    assert " · " in line and not line.startswith(" ·")


def test_fallback_reasoning_carries_no_machine_vocabulary():
    c1 = binary("A.c1", A, 4, desc="עדכון התכונה")
    f1 = fault("A.f1", A, [("m1", 2, "גישה ישירה")], requires="A.c1")
    for sels in ([Sel(c1, "full"), Sel(f1, "f1")], [Sel(c1, "absent"), Sel(f1, "none")],
                 [Sel(c1, "full"), Sel(f1, "none")]):
        line = _line(sels)
        assert not any(w in line for w in MACHINE_VOCABULARY), line
