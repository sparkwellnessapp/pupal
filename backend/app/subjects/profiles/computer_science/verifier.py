"""computer_science pack — the v6 VERIFIER fragment ([AM-G5], owner 2026-09-27).

NO NEW VERIFIER TEXT. Both constants are the grader-v5.4 verifier's own bytes,
sliced from `app/agents/grader/verifier_prompt.py::VERIFIER_SYSTEM_PROMPT`:

  RULES_3_5        rules 3-5 (code trace · absence audit · surface form)
                   — verifier_prompt.py:99-128; the same text as its `_CS_RULES_3_5`
  RULE_6_CLAUSES   rule 6's PL-9, R-1 (PL-9 boundary) and C-1 clauses
                   — verifier_prompt.py:141-150

`tests/subjects/test_subject_packs.py` asserts each is a verbatim substring of the
pinned v5 prompt, so the two cannot drift while both stacks live. They speak the
v5 verdict vocabulary (met / partially_met / not_met) and v5's rule numbering
(«כלל 6») — verbatim by ruling; how the v6 core verifier prompt frames them is
Phase 3's to decide. The precedents never reach the verifier (AM-G5).
"""
from __future__ import annotations

RULES_3_5 = """\
3. VERIFY WHAT THE WRITTEN CODE DOES, NOT WHAT MACHINERY APPEARS. The presence
   of a right-looking line is not satisfaction of the requirement: trace the
   actual behavior against the check. A correct-looking assignment inside an
   inverted guard writes the wrong cell — that check is not met, however
   familiar the line looks. Before returning met, confirm the traced behavior
   satisfies the requirement; a variable initialized with the wrong kind of
   value, a loop that can never enter, a condition that selects the opposite
   case — these are not_met even when every token looks conventional.

4. THE ABSENCE AUDIT. Before returning not_met for a missing element, search
   the ENTIRE answer for it — including inside loops, after the main body, and
   in unconventional placements. basis_he must state, in Hebrew, what you
   searched for and where (e.g. "חיפשתי השוואת null בגוף הלולאה ובכל הפעולה —
   אין"). Never assert that an element is present without quoting it: a check
   claiming a null-test exists must cite the null-test itself, not neighboring
   code.

5. SURFACE FORM IS NEVER A DEFECT. This is a handwritten exam that was never
   compiled. Judge conceptual substance: absent machinery, a wrong algorithm,
   a missing guard or check, direct attribute access where a getter is
   required, a wrong loop bound or range — these fail their checks. Do NOT
   fail a check for how the student wrote it when the intent is unambiguous:
   identifier case, spelling, an obvious local left undeclared, parentheses
   where brackets belong, a truncated or malformed but clearly-referring name,
   a missing semicolon, garbled braces. The test is behavioural: if only the
   written form is wrong and the intended computation is unambiguous, the
   check is met; if what the code would do differs from what the check
   requires, it is not. When the EXAMPLE SOLUTION is present, it — not your
   own convention — is the authority on naming and form: a student whose
   naming matches the example solution has made no naming error.
"""

RULE_6_CLAUSES = """\
   - [PL-9] partially_met מחייב שהרכיב הנדרש של הבדיקה עצמו קיים בצורה כלשהי
     בתשובה. דמיון מבני לחישוב אחר אינו נוכחות חלקית: אם הרכיב הנדרש נעדר —
     not_met, עם ציון מה חופש.
   - [PL-9 boundary, R-1] כלל 6 חל על רכיב שנעדר; הוא אינו שולל רכיב שקיים
     ותקף במונחי עצמו אך פועל על יעד שגוי — במקרה כזה הרכיב present, והקריאה
     השגויה מחויבת פעם אחת, בבדיקת המנגנון הנעדר.
   - [C-1, R-D] כל בדיקה נבחנת אך ורק מול האובייקט או המבנה הנקוב בה. מבנה
     הפועל על אובייקט אחר — גם אם הוא משרת את אותה מטרה — אינו מקיים את
     הבדיקה: מדרגים את הדיו, לא את הכוונה. אם האובייקט הנקוב אינו קיים
     בתשובה כלל — not_met, בציון מה נעדר.
"""

VERIFIER_FRAGMENT = RULES_3_5 + "\n" + RULE_6_CLAUSES
