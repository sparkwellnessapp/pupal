"""
Grading eval suite — the third eval suite (CLAUDE.md §15's keystone).

Measures the GraderAgent's judgment against blind-authored teacher grades:
(GradingRubricContract, TranscriptionContract) -> real GraderAgent -> scored
vs typed GT. The LLM call is the only nondeterministic stage; everything
around it (compilers, validator, selection scoring) is production code
exercised as-is — one definition, never a reimplementation [§3 of the mission].

Governed by MISSION_grading_eval_suite_v0.md (ratified) + GRADING_EVAL_PLAYBOOK.md
(STOP list). Model identity/prices via tests/eval_common/models_registry.py.
"""
