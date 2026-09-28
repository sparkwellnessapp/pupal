"""computer_science pack — the v6 PLANNER fragment (PR_grader_v6_options.md §8, CS row).

Two clauses: mechanism vs. target (PL-9, generalized) and form vs. behavior. The
constitution clauses the §8 row also names ride separately, as the pack's
PRECEDENTS (`precedents.py`, AM-G5), so they are one object with one source.
"""
from __future__ import annotations

PLANNER_FRAGMENT = """\
- MECHANISM AND TARGET. A monolith that reads as an action over a target (sums the values
  of a collection; counts the elements that satisfy a condition) is split into two credits,
  the mechanism and the target, whenever an answer could plausibly run the right mechanism
  on the wrong target. A right mechanism on a wrong target then earns the mechanism only,
  and the wrong target is charged once, at the target.
- FORM AND BEHAVIOR. Describe what the code must DO, never how it must be spelled. Identifier
  case, spelling, a missing semicolon or a garbled brace is never a check or an option unless
  the teacher wrote it as one; a label describes behavior, not syntax.
"""
