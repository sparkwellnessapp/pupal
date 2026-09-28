"""The v6 Stage-1 C1 phrase set (AM-G1). Opt-in: v5 plan builds keep V5_PATTERNS.

AM-G1 extends C1 with the verbs «יורדו», «ירדו», «הורדת» and the worded amounts
«נקודה» (1), «חצי נקודה» (0.5), «שתי נקודות» (2), «שלוש נקודות» (3), written
red-first against the phrase list from both exams' markdowns
(tests/agents/test_plan_v6_stage1_patterns.py). Two rules keep them from widening:

  * a new form is read ONLY after a deduction verb — a bare «נקודה 1» or «(1
    נקודה)» is a component's VALUE, and C4 reads it;
  * a new deduct form always carries an AMOUNT — «יגרור הורדת ניקוד» (the student-
    facing warning in question text, class D, TC-4) never becomes a marker.

«A pattern is never widened to make a plan pass.» The test pins the diff against
v5 over every line of both exams to exactly the ruled lines.
"""
from __future__ import annotations

from decimal import Decimal

from .compile import V5_PATTERNS, DeductionPatterns

_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(?:\s*(?:נקודות|נקודה|נק['׳]?))?"
# every verb a worded amount may follow (the v5 verbs plus AM-G1's)
_VERB = r"(?:יש\s+להוריד|להוריד|מורידים|הורדה\s+של|מינוס|יורדו|ירדו|הורדת)"
_NOT_HEB_AFTER = r"(?![֐-׿])"

V6_PATTERNS = DeductionPatterns(
    no_deduct=V5_PATTERNS.no_deduct + (r"לא\s+יורדו", r"לא\s+ירדו"),
    deduct=V5_PATTERNS.deduct + (
        rf"יורדו\s+{_NUM}{_UNIT}",
        rf"ירדו\s+{_NUM}{_UNIT}",
        rf"הורדת\s+{_NUM}{_UNIT}",
    ),
    worded=(
        (rf"{_VERB}\s+חצי\s+נקודה{_NOT_HEB_AFTER}", Decimal("0.5")),
        (rf"{_VERB}\s+שתי\s+נקודות{_NOT_HEB_AFTER}", Decimal("2")),
        (rf"{_VERB}\s+שלוש\s+נקודות{_NOT_HEB_AFTER}", Decimal("3")),
        (rf"{_VERB}\s+נקודה(?:\s+אחת)?{_NOT_HEB_AFTER}", Decimal("1")),
    ),
    amountless=V5_PATTERNS.amountless,
)
