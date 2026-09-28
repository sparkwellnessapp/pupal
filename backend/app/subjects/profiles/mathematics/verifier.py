"""mathematics pack — the v6 VERIFIER fragment (PR_grader_v6_options.md §8, Math row).
Written in option vocabulary (the v6 verifier picks options; it has no met/not_met).
The v5 seam's VERIFY_FRAGMENT (this package's __init__) is untouched and still
serves grader-v5.4+mathematics."""
from __future__ import annotations

VERIFIER_FRAGMENT = """\
- FOLLOW-THROUGH. Judge each step as written, on the student's own prior values: a correct
  method applied to a value carried from an earlier error satisfies that step; a wrong value
  is judged only by the check that names that value.
- Never re-solve, simplify or correct the student's work.
"""
