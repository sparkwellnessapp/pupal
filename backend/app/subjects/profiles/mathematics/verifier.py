"""mathematics pack — the v6 VERIFIER fragment (PR_grader_v6_options.md §8, Math row).
Written in option vocabulary (the v6 verifier picks options; it has no met/not_met).
The v5 seam's VERIFY_FRAGMENT (this package's __init__) is untouched and still
serves grader-v5.4+mathematics.

v2 (owner rulings Oct 18, Item A): VALID METHOD FIRST and the follow-through rule made
operational. v3 (Oct 18, 15:40/15:55): follow-through is R2 — only from a valid method with a
slip — and a part is judged only on the work it asks for. General rules; the examples are
deliberately outside the rubric's topics. ≤ 12 lines (the pack guard)."""
from __future__ import annotations

VERIFIER_FRAGMENT = """\
- A PART IS JUDGED ON ITS OWN WORK. Values found in earlier parts are inputs, never re-checked here.
- FOLLOW-THROUGH, FROM A VALID METHOD ONLY. When a step uses a value the student obtained earlier
  by a VALID method with a slip (a calculation or copying error), check the operation on HER value:
  a correct operation earns the step even though the number differs, and the slip is charged only
  where it occurred. A value obtained by an INVALID method (a wrong operation, model or equation)
  earns nothing in the steps built on it: they take the zero option. (A distance found as
  speed × time with a multiplication slip carries into the fuel step; one found as speed ÷ time
  does not.)
- VALID METHOD FIRST. Before selecting a partial option, confirm the student's method for that
  step is mathematically valid; a wrong formula, operation or relation takes the zero option even
  when a number or the final answer coincides.
- Never re-solve, simplify or correct her work, and never substitute the correct values for hers.
"""
