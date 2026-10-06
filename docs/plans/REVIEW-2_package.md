# REVIEW-2 — the v6 planner package (Oct 6)

**What to review:** whether the plans read as *her rubric, checked fairly*. Each criterion's checks, options, partials and faults are on the render pages. The prompt that produced them is in `prompt.py`, and its worked examples are in `examples.py`.

**What it gates:** Phase-6 spend only. It does **not** gate the CS eval (Oct 6 amendment C).
- An AMEND that changes the pinned plans (any check, option, value, `requires` or charge group) means re-running the CS eval on the amended plans. That re-run is pre-approved within the $19 cap.
- An AMEND limited to wording, with the plan algebra unchanged, needs no re-run.
- No AMEND within 24 h of delivery counts as GO.

## The package

| Item | File |
|---|---|
| hobby render (38 criteria · 78 checks · plan_hash `1d74b46a…`) | `docs/plans/hobby_tvshow_v6_render.md` |
| bagrut render (61 criteria · 109 checks · plan_hash `229c46a8…`) | `docs/plans/bagrut_899371_v6_render.md` |
| the planner prompt (planner-v6.1) | `backend/app/agents/planner/prompt.py` |
| the three domain-shifted examples | `backend/app/agents/planner/examples.py` |
| per-model detail: every inexpressible cell, with the plan decision behind it | `docs/plans/v6_planner_rerecord_report.md` |

**How the plans were made:**
- The planner is Sonnet 5.5, adaptive thinking at effort `high`, on prompt `planner-v6.1`. That prompt is AM-G17's opaque ids plus your approved line in rule 4: «A fault check lives on one criterion. The same mistake at two criteria is two fault checks; code links them.»
- Code assigns every id and every value. The model never wrote a number.

## Health table — Sonnet 5.5 against the recorded G2 Sonnet 5 result

| | G2 Sonnet 5 (planner-v6.0) | **Sonnet 5.5 (planner-v6.1) — pinned** |
|---|---|---|
| scopes planned first time / repaired / fell back | hobby 5 / 1 / 0 · bagrut 11 / 0 / 1 | hobby **6 / 0 / 0** · bagrut **12 / 0 / 0** |
| validator messages (the repair inputs) | — (not recorded for G2's final run) | **0** |
| V19 fault-leak candidates (telemetry) | — | 1 (hobby) |
| GT cells the plan can express | hobby 180/190 · bagrut 275/298 | hobby **180/190** · bagrut **274/298** |
| cost (both exams) | $2.97 | **$1.13** |
| build latency (both exams) | 970 s | **497 s** |
| served by the requested model | ✓ | ✓ (model_fallback 0) |

**Notes:**
- **Pre-registered P-v6-8:** FALSIFIED on cells (34 inexpressible against the same-prompt Sonnet 5 re-record's 32), CONFIRMED on repairs (0 against 3).
- **Opus 5.5 comparison:** because Sonnet 5.5 is one bagrut cell worse than G2, the ruling calls for it. It runs within the cap once the eval key is in place, and is reported beside this table. The pinned plans stay Sonnet 5.5's (ruling §3.8).
- **What the misses are:** most inexpressible cells, on both models, are criteria planned as all-or-nothing (binary) where the teacher gave partial credit. For example, bagrut `q3.ב.c6` is binary[3/0] while GT is 2.5 / 2 / 1.5. This is rule 7 (*concrete partials only*) meeting teachers' partial awards. It is the main thing for your read: where a partial the teacher evidently uses deserves an option, say so and the plan changes (an algebra AMEND).
- **The two unwritten-ruling cells** (dan `q2.א.c1`, yonatan `q2.ב.c4.s2`) rest on rulings written nowhere in the rubric. No planner can reach them; they are reported apart.
