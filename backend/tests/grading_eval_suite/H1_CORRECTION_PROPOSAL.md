# H1 — hobby_tvshow corrected-rubric proposal [R5, awaiting OWNER ratification]

**Status:** STAGED — nothing under `benchmarks/contracts/` (ratified path) is written.
GT authoring [F5] waits for this ratification. Ratify by replying, then the agent
runs `python -m tests.grading_eval_suite.tools.f0_hobby_correction --ratify`.

## 1. The error is real — the ORIGINAL blocks compilation (proof)

```
Compilation blocked by 2 validation error(s):
[invariant_violation] Question q2: Criteria sum (44) differs from declared total (60) by 16
[invariant_violation] Sub-question q2.ב: criteria sum (45) differs from declared points (29) by 16
```

## 2. The fix applied — EXACTLY the GT's own recorded fix_proposal

| step | content |
|---|---|
| move_text | new sub-question **ג** created with the recorded question text (PrintLowRatingChannel task) |
| move_criterion | `q2.ב` criteria[6] — "פעולה חיצונית PrintLowRatingChannel", **16 pts** — moved to ג |
| set_points | ג.points = **16** |

**Agent-surfaced consequences requiring your ratification:**
- **[DL-5] id rename:** the moved criterion becomes `q2.ג.c0` (was `q2.ב.c6`) — ids
  stay path-honest; your GT judgments will be authored against `q2.ג.c0`.
- **[DL-6] stale diagnostics dropped:** the 2 `rubric_mismatch` WARNINGs + the 2
  `point_sum_mismatch` mistakes + the applied `structural_mislabel` are removed from
  the corrected draft (they describe the pre-fix state; keeping them would force
  fake warning-acknowledgments at compile).

## 3. The corrected variant compiles CLEAN (proof)

- total_points: **100** (= 100)
- q2 sub-questions: {'א': '15', 'ב': '29', 'ג': '16'}  (15 + 29 + 16 = 60 = q2 declared)
- ב criteria sum: **29** (= 29 declared — INV-2 resolves)
- ג criteria: [('q2.ג.c0', '16')]

One teacher fix resolves all three shadows together — the FC worked example, closed.

## 4. Provenance to be stamped at ratification

`derived_from: ../rubric_eval_suite/benchmarks/hobby_tvshow.json` ·
`correction: structural_mislabel fix_proposal (recorded in the GT) applied verbatim + DL-5 id rename + DL-6 stale-diagnostic drop` ·
`ratified_by: Noam` · `date: <ratification date>`

Staged artifacts: `C:\Users\ariel\Desktop\vivi-v1 - 11.04\vivi-codebase\backend\tests\grading_eval_suite\benchmarks\contracts\_proposed\hobby_tvshow_corrected.contract.json` (+ the corrected draft beside it).
