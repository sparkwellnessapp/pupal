"""mathematics pack — the v6 VERIFIER fragment (PR_grader_v6_options.md §8, Math row).
Written in option vocabulary (the v6 verifier picks options; it has no met/not_met).
The v5 seam's VERIFY_FRAGMENT (this package's __init__) is untouched and still
serves grader-v5.4+mathematics.

v2 (owner rulings Oct 18, Item A): VALID METHOD FIRST and the follow-through rule made
operational. General rules; the examples are deliberately outside the rubric's topics."""
from __future__ import annotations

VERIFIER_FRAGMENT = """\
- FOLLOW-THROUGH. Judge each step on the student's own prior values: when a step uses a value
  she obtained earlier, check the operation on HER value; a correct operation earns the step —
  select the option describing it even though the number differs from the expected one. The
  earlier error is charged only by the check where it occurred.
- VALID METHOD FIRST. Before selecting a partial option, confirm the student's method for that
  step is mathematically valid. A wrong formula or operation, or a relation that does not hold,
  takes the zero option even when a number or the final answer coincides (a time found as
  distance ÷ speed is valid; as speed × distance it is not, whatever number results).
- Never re-solve, simplify or correct her work, and never substitute the correct values for hers.
"""
