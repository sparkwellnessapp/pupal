# RUNLOG — Multi-subject beta

Append-only. Every run: what ran, at which commit, the number, and where the artefacts are.
Suite-level runs are ALSO logged in their own suite RUNLOGs by the runners; this file is the
cross-suite index for the P-4 gate.

## Phase 0 — baseline (2026-09-08)

Tree: `perf/rubric-extraction-latency`, HEAD `4ee8a5b` (= `52855ab` + the Q7 WIP commit of the
grade-review module; no product code changed between them).

### Zero-spend gates

| gate | command | result | artefact |
|---|---|---|---|
| backend pytest (main) | `pytest --ignore=tests/transcription_eval_suit -q` | pending | scratch `phase0/backend_gates.log` |
| backend pytest (transcription suite) | `pytest tests/transcription_eval_suit -q` | pending | same |
| A0 compiler guard | `pytest tests/grading_eval_suite/test_compiled_plan_guard.py -q` | pending | same |
| CS prompt pins | `pytest tests/subjects/test_prompt_identity.py -q` | 6 passed (pinned at this commit) | `tests/subjects/test_prompt_identity.py` |
| vitest | `npm test` | pending | scratch `phase0/frontend_gates.log` |
| tsc | `npx tsc --noEmit` | pending | same |
| copy gate | `npm run check:copy` | pending | same |
| Playwright | `npm run test:e2e` | pending | same |

### Spend runs (D-17 lifted)

| run | command | result | artefact |
|---|---|---|---|
| rubric eval k=1 | `runner --config gpt-5.6-terra-high --repeats 1` | **4/5 pass** (same pass count as the 2026-08-24 verdict's per-run 4/5; per-fixture gate in the summary) | `tests/rubric_eval_suite/results/20260908-192219_gpt-5.6-terra-high/` |
| transcription `check_goal.sh` k=5 | `bash tests/transcription_eval_suit/check_goal.sh` (config v0, exam spec draft.json) | **GOAL: FAIL** — the standing state of the transcription goal, not a regression. Per doc, k=5, byte-identical across repeats on the gated recalls: dan `doc_ratio 0.947–0.950`, `op 0.985`, `struct 0.991`, `mc 0.903`; din `doc_ratio 0.905–0.942`, `struct 0.988`, `mc 0.926`; moran `struct 0.988–0.992`, `mc 0.973` (rep4 passed); omer `op 0.985`, `struct 0.992–0.996`; yonatan `doc_ratio 0.958–0.961`, `op 0.985`, `struct 0.988`, `mc 0.889`. **This distribution is the P-4 transcription baseline**: the CS P1/P2 text is sha-pinned, so a post-seam rerun must reproduce it within P1's own repeat spread. | `tests/transcription_eval_suit/results/20260908_194545_v0/` |
| A3 grading k=5 | `compile_plan.py --exam hobby_tvshow` (A0 184/190, byte-identical) → `segment_plan.py --stage both --confirm-spend` (route $0.069, 9 calls, 1 failed `q2.א.c0`; segment $0.113, 8 calls, expressible 188/190) → `runner --config sonnet5-v54-compiled -k 5 --fixtures <5 hobby>` | **BLOCKED before spend by the runner's own guard** (owner H-4 item 3, `runner.py:374-383`): `plan 'hobby_tvshow/compiled-5cafe7d77698' cannot express din_ezra's GT — q2.א.c0 award 4 UNREACHABLE (reachable 0 / 2.5 / 5)`. Cause: the router refused `q2.א.c0` (the A2 stage's one failure), so the terminal stayed a monolith — the OD-13 routed-miss class, a plan-compiler item, not a seam item. **Consequence for P-4:** the grading gate for this beta is A0 (compiler-only, byte-pinned) + the sha-pinned CS verifier prompt; no measured CS grading number exists for the compiled-plan architecture until OD-13 closes. A hand-plan run was NOT bought: with the CS verifier bytes pinned it would measure only model noise. | `tests/grading_eval_suite/plans/compiled/hobby_tvshow.routed+segmented.{plan,wording,run}.json`; config `configs/sonnet5-v54-compiled.json` (kept for the rerun once OD-13 closes) |
