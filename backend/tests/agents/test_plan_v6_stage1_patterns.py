"""[AM-G1] Stage-1 C1 patterns for v6, written RED-FIRST against the phrase list
drawn from both exams' markdowns. «A pattern is never widened to make a plan pass.»

The strongest form of that rule is a DIFF: over every line of both exams, the v6
scan equals the v5 scan except on exactly the lines the ruling names. A pattern
that starts matching anything else — «יגרור הורדת ניקוד» in the student-facing
question text (class D, TC-4), a component value «נקודה 1» — fails here.
"""
from __future__ import annotations

from decimal import Decimal as D
from pathlib import Path

import pytest

from app.agents.plan_compiler.compile import scan_deductions
from app.agents.plan_compiler.patterns_v6 import V6_PATTERNS

MARKDOWNS = Path(__file__).resolve().parents[1] / "rubric_eval_suite" / "markdowns"


def _scan(text, patterns=None):
    return [(d.polarity, d.amount) for d in scan_deductions(text, patterns=patterns)]


# The lines of both exams the extended patterns must change, and to what. Every
# OTHER line of both markdowns must scan identically under v5 and v6.
CHANGED = {
    # «יש להוריד נקודה» — the worded amount «נקודה» (1) after a deduction verb
    ("bagrut_899371", "אם החזירו את arr או את מערך העזר יש להוריד נקודה."): [("deduct", D("1"))],
    # «לא יורדו נקודות אם …» — a no-deduction statement (the case-sensitivity rule)
    ("bagrut_899371", "הערה: לא יורדו נקודות אם תכתבו בתוכניות אות גדולה במקום אות קטנה"):
        [("no_deduct", None)],
}


def _lines(exam):
    return (MARKDOWNS / f"{exam}.md").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("exam", ["hobby_tvshow", "bagrut_899371"])
def test_stage1_extended_patterns_match_the_exam_phrase_list(exam):
    changed = {text: want for (e, text), want in CHANGED.items() if e == exam}
    seen = set()
    for line in _lines(exam):
        hit = next((t for t in changed if t in line), None)
        if hit is not None:
            seen.add(hit)
            v6 = _scan(line, V6_PATTERNS)
            for want in changed[hit]:
                assert want in v6, (hit, v6)
            continue
        assert _scan(line, V6_PATTERNS) == _scan(line), f"v6 widened on: {line[:120]}"
    assert seen == set(changed), f"phrase list lines not found in {exam}.md: {set(changed) - seen}"


# The forms the ruling names that neither exam happens to use, as synthetic
# clauses — each is read ONLY after a deduction verb, with an amount.
SYNTHETIC = [
    ("אם לא בדקו גבולות יורדו 2 נקודות", [("deduct", D("2"))]),
    ("אם לא בדקו גבולות ירדו 0.5 נקודות", [("deduct", D("0.5"))]),
    ("שימוש בלולאה לא נכונה - הורדת 1 נק'", [("deduct", D("1"))]),
    ("אם לא אתחלו את המונה להוריד חצי נקודה", [("deduct", D("0.5"))]),
    ("אם לא החזירו ערך להוריד שתי נקודות", [("deduct", D("2"))]),
    ("אם השתמשו במערך נוסף יורדו שלוש נקודות", [("deduct", D("3"))]),
    ("אם לא סגרו את הקובץ יורדו נקודה", [("deduct", D("1"))]),
    ("אם הדפיסו פעמיים לא ירדו נקודות", [("no_deduct", None)]),
]


@pytest.mark.parametrize("clause,want", SYNTHETIC)
def test_the_named_forms_read_only_after_a_deduction_verb(clause, want):
    assert _scan(clause, V6_PATTERNS) == want


@pytest.mark.parametrize("clause", [
    "אי שימוש בפעולות פנימיות יגרור הורדת ניקוד.",          # class D: no amount
    "החזרת false נקודה 1",                                     # a component value
    "ספירת התאים שגדולים מ-0 (1 נקודה)",                      # a component value
    "חצי נקודה על כל תא נכון",                                 # a value, no verb
])
def test_worded_amounts_never_stand_alone(clause):
    assert [p for p, _ in _scan(clause, V6_PATTERNS) if p == "deduct"] == []


def test_v5_patterns_are_unchanged_by_default():
    """The production v5 compiler calls scan_deductions with no patterns: its
    behavior must not move (the v6 set is opt-in)."""
    assert _scan("אם החזירו את arr יש להוריד נקודה.") == []
    assert _scan("להוריד 2") == [("deduct", D("2"))]
