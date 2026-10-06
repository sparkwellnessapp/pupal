"""grader-v6 explainer (PR_grader_v6_options.md §7): the teacher's one-line reasoning per
credit criterion. `explainer.explain_test` (prompt `explainer-v1.0`, validators E-1..E-5)
writes the lines after the whole test is priced; any line that fails, is late or is never
written falls back to the deterministic composer (`fallback.py`, copy in `copy.py`).
`replay.replay_payloads` re-runs recorded payloads for the §13.4 arms."""
