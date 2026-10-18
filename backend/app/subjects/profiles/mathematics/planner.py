"""mathematics pack — the v6 PLANNER fragment (PR_grader_v6_options.md §8, Math row).

v2 (owner rulings Oct 18, Item A): OPERATIONS NOT RESULTS, PARTIALS NEED A VALID METHOD and
FOLLOW-THROUGH, after the §6b smoke showed partial options that rewarded invalid methods and
step options keyed to the expected number (so a carried value could never earn). General
rules; the examples are deliberately outside the rubric's topics. ≤ 12 lines (the pack guard)."""
from __future__ import annotations

PLANNER_FRAGMENT = """\
- STEPS AS CHECKS. Each step the teacher names, or her example solution shows as a separate
  result, is its own credit, so a later step can earn while an earlier one failed.
- ALTERNATIVE METHODS. Describe the milestones every valid method reaches, never a step of one method only.
- OPERATIONS, NOT RESULTS. Describe each step by the operation on its inputs, never by the number
  it should produce («the distance is speed × time», not «150 km»); a step that uses an earlier
  result names that input. The expected value may appear only as an example with the given data.
- PARTIALS NEED A VALID METHOD. A partial is a valid method with a flaw that keeps it valid (an
  arithmetic slip, a mis-copied number, rounding, an unfinished last step). An invalid method (a
  wrong formula or operation, a relation that does not hold, e.g. a time as speed × distance) is
  the zero option, even when a number or the final answer coincides.
- FOLLOW-THROUGH. The correct operation on the student's own earlier value is the step's full
  option; the earlier error is charged only at the step where it occurred.
"""
