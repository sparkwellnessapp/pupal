"""mathematics pack — the v6 VERIFIER fragment (PR_grader_v6_options.md §8, Math row).
Written in option vocabulary (the v6 verifier picks options; it has no met/not_met).
The v5 seam's VERIFY_FRAGMENT (this package's __init__) is untouched and still
serves grader-v5.4+mathematics.

v2 (owner rulings Oct 18, Item A): VALID METHOD FIRST and the follow-through rule made
operational. v3 (Oct 18, 15:40/15:55): follow-through is R2 — only from a valid method with a
slip — and a part is judged only on the work it asks for.
v4 (2026-10-29): v3's rules were RIGHT but not EXECUTED — every v3 miss was the verifier
judging a step against the example solution's number instead of her own (follow-through not
applied), or crediting a correct operation with a wrong result (no recompute). v4 turns both
into procedures: trace each number to where she produced it, then recompute. Deliberately NO
general leniency or doubt rule — the rejected first draft («in doubt, the higher option»)
leaked credit into a wrong answer (docs/math-rendering/math_pack_v4_REJECTED.md). ≤ 12 lines.
v5 (owner 2026-11-02, «one root mistake is not deducted on several criteria; be more lenient»):
R2 is REPLACED by ONE MISTAKE, ONE CHARGE — the טעות נגררת convention: a wrong value is an input
to every later step whatever caused it, unless it removed what that step tests. The leniency is
scoped to FORM (equivalent forms, the Israeli 12.500, units, a routine step done mentally), never
to the decision a check judges — the v4 lesson. Evidence: batch 192d4743 (q1.ה: a misread 10%
also zeroed the correct computation on her own q).
"""
from __future__ import annotations

VERIFIER_FRAGMENT = """\
- A PART IS JUDGED ON ITS OWN WORK. Values found in earlier parts are inputs, never re-checked here.
- ONE MISTAKE, ONE CHARGE. A mistake costs once, at the check where she made it. Before choosing any option below
  full, find where each number the step uses came from. If she produced it earlier (an earlier part shown above, or
  an earlier line of this part), it is an input, whatever made it wrong — a slip, a misread datum, a wrong formula:
  judge only THIS step's operation on HER number. A correct operation takes the full option even though her number
  and result differ from the example solution. Only when her wrong value removed what this step tests does it earn less.
- VALID METHOD FIRST, AT THIS STEP. A wrong formula, operation or relation in the step itself takes the zero option even when a number or the final answer coincides.
- RECOMPUTE HER ARITHMETIC. A correct operation with a wrong result (a calculation, copying or rounding slip) is never
  the full option: choose the partial for a valid method with a slip; with no such option, the zero option. A number
  copied wrongly from the question into a correct expression is such a slip.
- FORM IS NOT A FAULT: any equivalent value or form, 12.500 written for 12,500, a unit the check does not name; a routine step done mentally is done when her next line uses its result.
- A JUSTIFICATION EARNS ONLY WITH ITS CLAIM: when her choice or conclusion is wrong, the check for justifying the correct one takes its zero option — ONE CHARGE carries her numbers, never her claims. Never re-solve, simplify or correct her work, or substitute correct values.
"""
