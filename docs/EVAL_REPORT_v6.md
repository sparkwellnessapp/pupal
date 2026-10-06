# EVAL_REPORT_v6 — CS section (Oct 6)

Provisional: n = 12 fixtures on 2 exams (hobby 5, bagrut 7). Every conclusion is provisional.

## 1 · Verdict

**STOP (a): kills fire after the pre-approved diagnosis.** v6 is not yet shippable on ship criteria (1)–(4).

- K2 fires under **every** configuration measured, including today's production pin.
- K1 fires on one cell with the Sonnet 5.5 verifier.

What v6 *does* show:
- the totals sit much closer to the teacher's;
- K3 is better than v5;
- K4 holds on Sonnet 5.5;
- there is no double charging (G-D1 = G-D2 = 0);
- it costs 43% less than v5.

The cause of the kills is located (§6): **mostly the PLAN, not the verifier.** Two thirds of the K2 cells are partial grades the pinned plan has no option for.

| ship criterion | v6 + Sonnet 5.5 verifier | met |
|---|---|---|
| (1) kills hold | K1 90/93 · K2 17.0% · K4 5.25 | ❌ |
| (2) G-D1 = G-D2 = 0 | 0 · 0 | ✅ |
| (3) K3 and G-Z no worse than v5 | K3 0.767 vs 0.693 ✅ · G-Z 32.7% vs 31.6% ❌ (+1.1 pt) | ❌ |
| (4) cost per test below v5 | $0.1016 vs $0.1774 | ✅ |
| (5) Math/English smoke | not run: STOP (a) came first | — |

## 2 · Kills and gates

Runs:
- v6 = `results/20261006-172019_v6-cs-sonnet55` (k=3);
- the diagnosis = `…173328_v6-cs-sonnet5-diag` (k=2);
- v5 = `…172751_trackb-sonnet5-v54_rescore` (k=2).

All three use the same instrument. Contested cells are excluded. There were 0 model_fallback scopes and every trial was valid (36/36, 24/24, 24/24).

| | v6 · Sonnet 5.5 | v6 · Sonnet 5 (diagnosis) | v5 production pin | bar |
|---|---|---|---|---|
| **K1** GT-ZERO→AI-ZERO | **90/93 ❌** (1 cell × 3 trials) | 62/62 ✅ | 62/62 ✅ | 100% |
| **K2** GT-PARTIAL→AI-FULL | **50/294 = 17.0% ❌** | **37/196 = 18.9% ❌** | **20/196 = 10.2% ❌** | ≤ 2.4% |
| **K4** max total spread | 5.25 ✅ | **9.5 ❌** | **10.25 ❌** | ≤ 8.25 |
| K3 within-precision | **0.767** | 0.734 | 0.693 | ≥ v5 |
| G-Z GT-PARTIAL→AI-ZERO | 96/294 = 32.7% | **53/196 = 27.0%** | 62/196 = 31.6% | ≤ v5 |
| G-D1 / G-D2 (cell set D) | 0 / 0 | 0 / 0 | — | 0 |
| G-B bounds_clamped | 0 | 0 | — | report |

**The K2 bar (2.4%) was set on the hobby-only C2 baseline.** On the 12-fixture set, today's production pin is at 10.2%. The bar is yours; it has not been moved.

## 3 · Plan health (item 4)

| planner | inexpressible GT cells (both exams) | scopes planned / repaired / fallback | cost | wall |
|---|---|---|---|---|
| **Sonnet 5.5 — pinned (ruling §3.8)** | **34** (hobby 10 · bagrut 24) | 18 / 0 / 0 | $1.13 | 497 s |
| Opus 5.5 (the item-4 comparison) | **26** (hobby 9 · bagrut 17) | 17 / 1 / 0 | $2.33 | 697 s |
| Sonnet 5 (re-record) | 32 | 15 / 3 / 0 | $1.97 | 1,774 s |
| G2 Sonnet 5 (Sep 28) | 33 | 16 / 1 / 1 | $2.97 | 970 s |

Renders and the health table are in the REVIEW-2 package (`docs/plans/REVIEW-2_package.md`). Every inexpressible cell is listed with the plan decision behind it in `docs/plans/v6_planner_rerecord_report.md`.

## 4 · Cost per test (registry cards, cache writes at 1.25×)

| component | v6 · Sonnet 5.5 | v5 production pin |
|---|---|---|
| verifier | $0.0596 (cache hit 90%) | $0.1774 (verifier incl. basis_he, uncached) |
| explainer arm A — Haiku 4.5 | $0.0419 (cache hit 59%) | — |
| explainer arm B — Sonnet 5.5, lowest | $0.0818 (cache hit 64%) | — |
| **total with arm A** | **$0.1016** (target $0.10) | **$0.1774** |
| student feedback | not run in the eval harness (G3–5) | — |

- The diagnosis verifier (Sonnet 5, no thinking) cost $0.072 per test.
- Prompt caching (CL-2) was added for this run. Without it, the M3 proof cost $0.18 per test.

## 5 · The twelve students — test totals (GT → AI range across repeats; Δ = mean − GT)

| student | GT | v5 | v6 · Sonnet 5.5 | v6 · Sonnet 5 |
|---|---|---|---|---|
| bagrut din | 91.5 | 58.00–64.25 (−30.4) | 67.75–73.00 (−21.5) | 67.00–67.25 (−24.4) |
| bagrut itay | 79.5 | 62.00–62.75 (−17.1) | 69.25–74.25 (−7.1) | 72.00–75.00 (−6.0) |
| bagrut noam | 83.75 | 77.25–79.50 (−5.4) | 74.75–77.25 (−7.6) | 75.25–79.50 (−6.4) |
| bagrut raz | 82.25 | 68.00–69.25 (−13.6) | 71.75–76.75 (−7.2) | 73.00–73.25 (−9.1) |
| bagrut roni | 94.0 | 71.25–72.50 (−22.1) | 88.75 (−5.2) | 84.50–88.00 (−7.8) |
| bagrut yael | 91.0 | 63.50–73.75 (−22.4) | 83.00–84.50 (−7.3) | 80.00–81.00 (−10.5) |
| bagrut yahli | 70.5 | 54.75–59.75 (−13.2) | 66.25–67.25 (−3.6) | 55.25–64.75 (−10.5) |
| hobby dan | 84.0 | 71.50–73.50 (−11.5) | 74.50–75.50 (−9.0) | 78.00–80.50 (−4.8) |
| hobby din | 55.5 | 43.25–45.75 (−11.0) | 45.75–48.75 (−8.6) | 42.75–43.75 (−12.2) |
| hobby moran | 92 | 82.00–84.50 (−8.8) | 85.50–88.50 (−4.5) | 89.00–90.00 (−2.5) |
| hobby omer | 89.0 | 82.50–83.50 (−6.0) | 83.00–84.50 (−5.5) | 86.50–88.00 (−1.8) |
| hobby yonatan | 92.5 | 79.25–80.75 (−12.5) | 89.00–92.00 (−1.8) | 82.75–85.00 (−8.6) |

The mean shortfall against GT drops from **14.5 points (v5) to 7.4 points (v6 · Sonnet 5.5)**. 11 of 12 students are closer; noam is the exception.

## 6 · Residual failure classes

1. **Inexpressible teacher partials: the main cause of K2 and a large share of G-Z.**
   - **34 of the 50 K2 cells (68%)** and **45 of the 96 G-Z cells (47%)** sit on a GT award the pinned plan has no option for.
   - On those cells the verifier must pick full or zero, whatever it sees.
   - The largest: bagrut `q3.ב.c6`, binary [3/0] against GT 2.5 / 2 / 1.5 (12 K2 + 9 G-Z cells); bagrut `q1.א.2.c0` (6 K2); hobby `q2.ב.c4.s1` and `q1.ב.c6` (4 K2 each).
   - This is the planner's rule 7 (*concrete partials only*) meeting how these teachers actually grade. It is a REVIEW-2 matter.
2. **K1, one cell: din `q2.ב.c1` (the accumulator array), 3/3 trials on Sonnet 5.5.**
   - The plan gives that credit a partial option. The Sonnet 5.5 verifier took it for `int[] arr = new int[tv]`, a wrong-target array that GT zeroes under PL-9.
   - The Sonnet 5 verifier did not (K1 62/62). The partial's label is too permissive for a wrong-target answer.
3. **G-Z on folded deduction cells.** hobby `q1.ג.c7` / `q1.ג.c3` / `q1.ג.c6` (the zero-guard and null-loop cells, census App. B) are zeroed where the teacher took off a point.
4. **K4 depends on the verifier.** Sonnet 5.5 is stable (5.25); Sonnet 5 is not (9.5, yahli 55.25 ↔ 64.75).
5. **Cosmetic:** the verifier's absence pointers come back in the first person («חיפשתי…»). That wording comes from the CS fragment's v5 *absence audit* rule, read through the vocabulary map. Pointers are evidence, not teacher copy, but they would surface in the expanded row.

## 7 · Math / English smoke

Not run. STOP (a) came first, and the remaining budget is $3.65.

## 8 · Explainer (§13.4)

| arm | lines passing E-1..E-5 | cost per test |
|---|---|---|
| A — Haiku 4.5 | **1449/1464 = 99.0%** (15 failed E-4, replaced by the fallback line) | $0.0419 |
| B — Sonnet 5.5, lowest (thinking `between_tools`, effort low) | 1436/1464 = 98.1% | $0.0818 |

**Your read:** `docs/plans/v6_explainer_read_sheet.md`.
- 80 lines: 40 terminals × 2 arms (10 full · 10 partial · 10 zero · 10 with a deduction), blind and shuffled.
- The arm key is stored apart, in the run directory.
- An arm ships iff faithful 40/40, clear ≥ 36 and concise ≥ 36; the cheapest qualifying arm wins. If arm A qualifies, it is also the cheaper.

## 9 · Recommendation and the decisions that are yours

The architecture result is encouraging: totals land much closer to the teacher's, at 43% lower cost, with no double charging. The kills are concentrated in plan decisions you can see and amend. My recommendation, in order:

1. **REVIEW-2 AMEND on the plans (algebra):**
   - give the criteria in §6.1 the partial values the teachers actually use, starting with bagrut `q3.ב.c6` and `q1.א.2.c0`, and hobby `q2.ב.c4.s1` and `q1.ב.c6`;
   - tighten din `q2.ב.c1`'s partial so a wrong-target array is not a partial.

   Or decide whether the planner's rule 7 should allow the partials teachers grade by, which is a prompt change, re-pinned via REVIEW-2.
2. **Planner model:**
   - Opus 5.5 plans express 8 more GT cells for +$1.20 per rubric build (one-time per rubric, about $0.04 per test over a class of 30).
   - Ruling §3.8 pins Sonnet 5.5, so switching is your call.
3. **The K2 bar:** at 2.4% it fails today's production pin (10.2%) on this fixture set. Keep it, or re-base it on the 12-fixture v5 baseline. Gates are yours.
4. **Budget:**
   - A CS re-run on amended plans is pre-approved, but costs about $3.70 against $3.65 left. The Math/English smoke needs about $2 as well.
   - A cap raise of about $3, or dropping one of the two, is needed.

Ledger: **$15.35 of $19** (RUNLOG).
