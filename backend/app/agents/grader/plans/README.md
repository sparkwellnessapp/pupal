# Ratified grading plans (production copies)

These ship **inside the image**. The Dockerfile copies `app/` and nothing else,
so a plan that lives only under `tests/` does not exist in production — the pin
resolves to `v3` with a `grader_pin_incomplete` warning, and the fallback looks
like a working system.

The eval suite keeps its own copy under
`tests/grading_eval_suite/plans/`; that one is the SUT the gate measures. These
two must stay byte-identical — `tests/agents/test_grader_pin.py` compares them.

A plan is ratified against ONE rubric contract. Adding a file here does not
ratify it; `GRADER_PLAN_RUBRIC_ID` names the rubric it was ratified for, and
every other rubric is graded by v3 (a fallback, never a guess).
