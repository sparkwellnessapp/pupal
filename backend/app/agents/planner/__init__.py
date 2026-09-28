"""grader-v6 PLANNER (PR_grader_v6_options.md §5): one call per scope that needs
language, turning the pure compiler's skeleton and markers into options per check.

  schemas.py   the planner's structured output (§5.3) — no numeric field anywhere
  inputs.py    the per-scope input (§5.2) — no amount, no student work
  prompt.py    the assembled prompt: core constitution (§5.4) + the subject
               pack's planner fragment and precedents (§8) + the few-shots
  examples.py  the three domain-shifted few-shots, as data (§5.4)
"""
