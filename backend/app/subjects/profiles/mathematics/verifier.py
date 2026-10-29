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
"""
from __future__ import annotations

VERIFIER_FRAGMENT = """\
- A PART IS JUDGED ON ITS OWN WORK. Values found in earlier parts are inputs, never re-checked here.
- FOLLOW-THROUGH, STEP BY STEP. Before choosing any option below full for a step, find where each number the step
  uses came from. If she produced it in an EARLIER PART (shown above) by a valid method, it is an input: judge only
  this step's operation on HER number, as if it were right — a correct operation takes the full option even though
  her number and result differ from the example solution. Only a value from an INVALID method (a wrong operation,
  model or equation) earns nothing in the steps built on it.
- VALID METHOD FIRST. A wrong formula, operation or relation takes the zero option even when a number or the final answer coincides.
- RECOMPUTE HER ARITHMETIC. A correct operation with a wrong result (a calculation, copying or rounding slip) is never
  the full option: choose the partial for a valid method with a slip; with no such option, the zero option. A number
  copied wrongly from the question into a correct expression is such a slip.
- A JUSTIFICATION EARNS ONLY WITH ITS CLAIM: when her choice or conclusion is wrong, the check for justifying the
  correct one takes its zero option. Never re-solve, simplify or correct her work, or substitute correct values.
"""
