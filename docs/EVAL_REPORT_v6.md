# EVAL_REPORT_v6 — CS section, after the AM-G19 iteration (Oct 17)

Provisional: n = 12 fixtures on 2 exams (hobby 5, bagrut 7). Every conclusion is provisional.

## 1 · Verdict

**STOP (a) again: two kills fire on the AM-G19 run.** Per ruling §7.6, this is a STOP with the cell-level residual. There is no smoke, no second iteration and no diagnosis re-run.

- **K2:** 44/294 = **15.0%**, against the re-based bar of ≤ v5 = 10.2%.
- **K4:** **8.5**, against ≤ 8.25. All of it is one student, hobby din_ezra.
- **K1 now holds:** 93/93 (it was 90/93).

**What AM-G19 bought:** every gate now holds, and the totals moved again.

| | v5 (production pin) | v6 Oct 6 (v6.1 plans) | v6 Oct 17 (AM-G19 plans) |
|---|---|---|---|
| G-Z | 31.6% | 32.7% | **21.8%** |
| K3 | 0.693 | 0.767 | **0.784** |
| mean total shortfall vs GT | 14.5 points | 7.4 points | **5.3 points** |

Every one of the 12 students is closer to the teacher than under v5.

| ship criterion | v6 · Oct 6 (v6.1 plans, Sonnet 5.5) | v6 · Oct 17 (AM-G19 plans, Opus 5.5) |
|---|---|---|
| (1) kills hold | ❌ K1 90/93 · K2 17.0% | ❌ **K2 15.0%** (bar 10.2%) · **K4 8.5** (bar 8.25) · K1 ✅ |
| (2) G-D1 = G-D2 = 0 | ✅ | ✅ |
| (3) K3 and G-Z no worse than v5 | ❌ (G-Z +1.1 pt) | ✅ K3 0.784 · G-Z 21.8% |
| (4) cost per test below v5 | ✅ $0.1016 | ✅ $0.1054 |
| (5) Math/English smoke | not run | **not run** (STOP first). Prepared and pre-registered (`smoke/known_answers.json`, PREDICTIONS) |

### 1a · Owner overrides (2026-10-17, 17:30) — overrides, NOT bar changes; the gate code is unchanged

| | override | the recorded trade |
|---|---|---|
| **OO-1** | **K2 15.0% (44/294) accepted on n=12.** | Points over-credited 36 (v5 22); G-Z points lost 68.5 (v5 82); total gap 5.3 (v5 14.5); K3 0.784 (v5 0.693). Rationale (owner): the teacher reviews every grade, and over-credit is visible on expand. |
| **OO-2** | **K4 8.5 accepted on n=12** (one student, hobby din_ezra). No self-consistency. | |
| **OO-3** | **Explainer: Sonnet 5.5 at its lowest effort (arm B)**, by the owner's read; this overrides the cheapest-qualifier rule. | **Shipping cost per test: $0.1454.** The verifier is $0.0625 (run 10, cached). Arm B is $0.0829: it was measured at $0.0818 on run 4's payloads, and run 10's payloads are 1.5% larger on input and 1.0% on output. This is below v5's $0.1774 and above the $0.10 aspiration. |
| **OO-4** | **Minimum viable cutover:** the §7 scope replaces the G3–5 remainder. OD-G6 is reversed for this PR: `/similar` moves to v6.1. | |

With OO-1 and OO-2, ship criterion (1) is met by override. (5) is the Math/English smoke: §6a passes ($0, `docs/plans/v6_smoke_structural.md`); §6b waits on the Vertex quota.

## 2 · Kills and gates

| | v5 production pin | v6 · Oct 6 (v6.1, Sonnet 5.5 verifier) | v6 · Sonnet 5 diagnosis | **v6 · Oct 17 (AM-G19)** | bar |
|---|---|---|---|---|---|
| **K1** GT-ZERO→AI-ZERO | 62/62 | 90/93 ❌ | 62/62 | **93/93 ✅** | 100% |
| **K2** GT-PARTIAL→AI-FULL | 20/196 = 10.2% | 50/294 = 17.0% | 37/196 = 18.9% | **44/294 = 15.0% ❌** | kill ≤ v5 (10.2%) · target 2.4% |
| **K4** max total spread | 10.25 | 5.25 | 9.5 | **8.5 ❌** | ≤ 8.25 |
| K3 within-precision | 0.693 | 0.767 | 0.734 | **0.784** | ≥ v5 |
| G-Z GT-PARTIAL→AI-ZERO | 62/196 = 31.6% | 96/294 = 32.7% | 53/196 = 27.0% | **64/294 = 21.8%** | ≤ v5 |
| G-D1 / G-D2 | — | 0 / 0 | 0 / 0 | **0 / 0** | 0 |
| G-B bounds_clamped | — | 0 | 0 | 0 | report |
| valid trials · model_fallback | 24/24 · 0 | 36/36 · 0 | 24/24 · 0 | **36/36 · 0** | |

- **Runs:**
  - v5 = `results/20261006-172751_trackb-sonnet5-v54_rescore` (k=2);
  - Oct 6 = `…20261006-172019_v6-cs-sonnet55` (k=3);
  - diagnosis = `…173328_v6-cs-sonnet5-diag` (k=2);
  - **Oct 17 = `…20261017-162850_v6-cs-sonnet55-amg19` (k=3)**.
- All use the same instrument, with contested cells excluded.
- One Oct 17 trial (dan r0) lost 4 scopes to a connection error and was re-run once by the runner, so all 36 trials are valid.
- **The K2 kill is re-based** (owner, Oct 6 evening §4). The 2.4% was calibrated on 5 hobby fixtures and fails the production pin. The Oct 6 run fails the re-based bar too (17.0%), so the change rescues no result.

## 3 · Plan health (item 7.3)

| planner | prompt | inexpressible GT cells | planner / repaired / fallback | cost (both exams) | wall |
|---|---|---|---|---|---|
| Sonnet 5.5 | v6.1 (Oct 6 pin) | 34 | 18 / 0 / 0 | $1.13 | 497 s |
| Opus 5.5 | v6.1 | 26 | 17 / 1 / 0 | $2.33 | 697 s |
| Sonnet 5.5 | **v6.2 (AM-G19)** | 29 | 18 / 0 / 0 | $1.12 | 436 + 242 s |
| **Opus 5.5** | **v6.2 (AM-G19) — pinned by §13.1** | **21** | 18 / 0 / 0 | $2.12 | 511 + 340 s |

- **§13.1 choice:** Opus 5.5 (21 against 29, outside the 1-cell band). Pinned: hobby `f068fa66…` (85 checks) and bagrut `773ea231…` (109 checks).
- 0 validator messages and 0 rule-7 downgrades on either planner.
- **The Oct 6 run's own residual cells, re-read against each plan** (how many can the plan price at all?):

  | plan | the Oct 6 run's 50 K2 cells | its 96 G-Z cells |
  |---|---|---|
  | the v6.1 plan that run used | 16 (32%) | 51 (53%) |
  | Sonnet 5.5 v6.2 | 16 (32%) | 61 (64%) |
  | **Opus 5.5 v6.2 (pinned)** | **27 (54%)** | **72 (75%)** |

Renders: `docs/plans/<exam>_v6_render.md`. Every plan check now shows its `element`.

## 4 · Cost per test (registry cards, cache writes at 1.25×)

| component | v6 · Oct 6 | **v6 · Oct 17** | v5 |
|---|---|---|---|
| verifier (Sonnet 5.5, effort low) | $0.0596 (cache hit 90%) | **$0.0625** (90%) | $0.1774 |
| explainer arm A (Haiku 4.5) | $0.0419 (59%) | **$0.0429** (59%) | — |
| **total** | $0.1016 | **$0.1054** | $0.1774 |

- The AM-G19 plans carry about 10% more options, which explains the 4% cost rise.
- **Planner:** $2.12 per rubric pair on Opus, one-time per rubric. The system prompt is now cached.
- E-1..E-5: 1450/1464 = 99.0% (14 E-4, replaced by the fallback line).

## 5 · The twelve students — test totals (range across repeats; Δ = mean − GT; s = spread)

| student | GT | v5 | v6 · Oct 6 | **v6 · Oct 17** |
|---|---|---|---|---|
| bagrut din | 91.5 | 58.00–64.25 (−30.4) | 67.75–73.00 (−21.5) | **75.00–78.00 (−14.7)** s 3.0 |
| bagrut itay | 79.5 | 62.00–62.75 (−17.1) | 69.25–74.25 (−7.1) | **65.50–71.00 (−10.8)** s 5.5 |
| bagrut noam | 83.75 | 77.25–79.50 (−5.4) | 74.75–77.25 (−7.6) | **78.50–80.50 (−4.1)** s 2.0 |
| bagrut raz | 82.25 | 68.00–69.25 (−13.6) | 71.75–76.75 (−7.2) | **76.00–79.00 (−5.1)** s 3.0 |
| bagrut roni | 94.0 | 71.25–72.50 (−22.1) | 88.75 (−5.2) | **95.00–96.50 (+1.8)** s 1.5 |
| bagrut yael | 91.0 | 63.50–73.75 (−22.4) | 83.00–84.50 (−7.3) | **87.50–89.50 (−2.7)** s 2.0 |
| bagrut yahli | 70.5 | 54.75–59.75 (−13.2) | 66.25–67.25 (−3.6) | **65.00–67.50 (−4.0)** s 2.5 |
| hobby dan | 84.0 | 71.50–73.50 (−11.5) | 74.50–75.50 (−9.0) | **73.50–74.00 (−10.3)** s 0.5 |
| hobby din | 55.5 | 43.25–45.75 (−11.0) | 45.75–48.75 (−8.6) | **42.75–51.25 (−7.4)** **s 8.5** |
| hobby moran | 92 | 82.00–84.50 (−8.8) | 85.50–88.50 (−4.5) | **91.00–92.00 (−0.3)** s 1.0 |
| hobby omer | 89.0 | 82.50–83.50 (−6.0) | 83.00–84.50 (−5.5) | **86.50–87.50 (−2.2)** s 1.0 |
| hobby yonatan | 92.5 | 79.25–80.75 (−12.5) | 89.00–92.00 (−1.8) | **85.50–90.00 (−4.2)** s 4.5 |

Mean shortfall: **v5 14.5 → v6 Oct 6 7.4 → v6 Oct 17 5.3 points.** Roni is now over GT, by 1.8.

## 6 · The residual, cell by cell (the STOP's evidence)

Full detail: every K2 cell with the plan's options and the verifier's pick and quote, plus din's K4 cells, is in `docs/plans/v6_amg19_residual_cells.md`.

### 6.1 K2 and G-Z by full value (ruling §9; for reading, never for tuning)

| run | band | GT-partial cells | K2 cells | K2 points over-credited | G-Z cells | G-Z points lost |
|---|---|---|---|---|---|---|
| v5 | < 2 | 18 | 6 (33.3%) | 4 | 8 (44.4%) | 4 |
| v5 | ≥ 2 | 178 | 14 (7.9%) | 18 | 54 (30.3%) | 78 |
| v6 Oct 6 | < 2 | 27 | 12 (44.4%) | 7.5 | 9 (33.3%) | 4.5 |
| v6 Oct 6 | ≥ 2 | 267 | 38 (14.2%) | 46 | 87 (32.6%) | 122 |
| v6 diag | < 2 | 18 | 9 (50.0%) | 5.5 | 7 (38.9%) | 3.5 |
| v6 diag | ≥ 2 | 178 | 28 (15.7%) | 32.5 | 46 (25.8%) | 58.5 |
| **v6 Oct 17** | **< 2** | 27 | **7 (25.9%)** | 3.5 | **15 (55.6%)** | 9 |
| **v6 Oct 17** | **≥ 2** | 267 | **37 (13.9%)** | 32.5 | **49 (18.4%)** | 59.5 |

- **Reading:** AM-G19 moved the error where its rule says it would.
  - On ≥ 2 cells, G-Z falls 32.6% → 18.4% (122 → 59.5 points lost). The new partials catch partial work.
  - On < 2 cells (no partial allowed by 7(b)), K2 falls 44% → 26% and G-Z rises 33% → 56%. A small criterion is now all-or-nothing in both directions. That is 9 points in all.
  - K2 at ≥ 2 barely moves (14.2% → 13.9%). That is the residual that fires the kill.

### 6.2 The 44 K2 cells, by cause

**17 sit on GT values the plan cannot express** (P-v6-12: 38.6%, down from 68%, not under 30%):

| cells | where | why it is inexpressible |
|---|---|---|
| 11 | bagrut `q3.ב.c6` (GT 2.5/3 ×7), `q3.ב.c5` (GT 2.5 ×3, 1.5 ×1) | Opus **split** each 3-point criterion into three 1-point binary credits. Each is under 2, so rule 7(b) gives it no partial, and the teacher's half-point deductions have no option. **An interplay of AM-G19 with rule 8 (split):** the 2-point line applies to each split credit, not to the criterion. |
| 3 | hobby `q2.ב.c5` (GT 0.5/1) | a 1-point binary «return», by rule. |
| 3 | hobby `q2.ב.c4.s2` (yonatan, GT 1.5/2) | an UNWRITTEN-RULING cell (A-5), reported apart in every run. |

**27 had the GT value as an option, and the verifier picked full:**

| cells | where | what happened |
|---|---|---|
| 6 | bagrut `q3.ב.c6` (GT 2/3) | The credit reads «a loop over the counter array **from index 1 to 20**»; loops `for (i = 0; …)` were credited full. The verifier ignored a constraint its own label states. |
| 4 | bagrut `q6.c6` (GT 1/2) | The fault «printed the count instead of the index» was not selected (raz prints `big`). |
| 4 | bagrut `q6.c7` (GT 3/4) | `new int[count * 2 + 1]` credited as «size twice the count». |
| 3 | hobby `q2.ב.c3.s0` (GT 2/3) | The getter fault (direct `tvRate.Length` access) was not selected. |
| 3 | bagrut `q3.א.c2` (GT 1/2) | **The plan's own label** accepts allocation `new int[21]` as zeroing; the teacher took 1 off. Plan wording against teacher, not the verifier. |
| 3 | hobby `q2.ב.c4.s1` (GT 0.5/1) | **The plan's own label** accepts any initialization (`" "`); the teacher took half off. |
| 2 | hobby `q2.ג.c0.s1` (din, GT 1.5/3) | `LowestRateChannel == …getName()` (a comparison, not a call) credited as «calls LowestRateChannel». |
| 1 + 1 | hobby `q1.ב.c2` (din r1), bagrut `q6.c1` | single-trial picks. |

So **21 of the 44 K2 cells are verifier misses of a constraint or a fault its options state.** 17 are split-induced or rule-induced inexpressibility; 6 are plan wording.

### 6.3 K4 — one student

hobby din_ezra totals 51.25 / 42.75 / 42.75, a spread of 8.5. Nine cells oscillate across the three trials: `q1.ב.c2` 0/3/0, `q2.ב.c4.s3` 3/0/0, `q2.ג.c0.s1` 3/3/1.5, `q2.ב.c4.s4` 1/0/0, `q1.ב.c3` 2/3/2, `q2.ב.c0`, `q2.ב.c4.s2`, `q2.ג.c0.s0`, `q1.ב.c7`. Din's answer is the messiest transcription in the set. Every other student's spread is ≤ 5.5.

## 7 · Predictions

| | prediction | result |
|---|---|---|
| **P-v6-11** | under AM-G19: K2 ≤ 10.2%, G-Z ≤ 31.6%, K1 = 100%, K4 ≤ 8.25 | **FALSIFIED**: K2 15.0% ❌, K4 8.5 ❌; G-Z 21.8% ✅, K1 100% ✅ |
| **P-v6-12** | K2 cells on inexpressible GT fall from 68% to < 30% | **FALSIFIED**: 38.6% (17/44); it moved the predicted way |
| P-v6-1 | K2 below the v5 baseline | FALSIFIED (15.0% vs 10.2%) |
| P-v6-2 | G-Z not above v5 | **CONFIRMED** (21.8% vs 31.6%) |
| P-v6-4 | G-D1 = G-D2 = 0 | CONFIRMED |
| P-v6-7 | ≤ $0.10 per test without CL-3..5 | FALSIFIED by $0.0054 ($0.1054) |
| P-v6-9 | v6 + 5.5 holds K1/K2/K4, K3 and G-Z no worse than v5, cheaper | FALSIFIED on K2 and K4; holds on everything else |

## 8 · Math / English smoke

Not run: STOP (a) came first. It is ready to run at $0 of preparation.
- **Data:** `smoke/known_answers.json`. Math is math3, 19 criteria × 3 answers, including one follow-through error. English is the Ministry F/G rubric with exam 016584's own writing task, a 4 band-ladder × 3 answers.
- **Tool:** `tools/v6_smoke.py`.
- **Pre-registration:** the intended classes and the ruled pass bar are in PREDICTIONS.md.
- **Estimate:** ≈ $2.3 with the Opus planner (23 Math scopes, no English planner call) plus grading 6 tests. It does **not** fit the $2.61 left without risk; ≈ $1.5 with Sonnet 5.5.

## 9 · The decisions that are yours

1. **The K2 kill at ≥ 2 is now mostly the verifier** (21 cells of 44: stated constraints and faults not applied).
   - The verifier text is frozen during the eval (ruling 8).
   - Options: (a) a verifier rule that a label's stated bound or form must be checked literally before `full`; this is a REVIEW-able verifier change plus one re-run (≈ $3.9); (b) accept K2 at ~15% given G-Z −10 pts, K3 +0.09 and a mean shortfall of 5.3 (a gate change, yours); (c) both.
2. **AM-G19 × split (rule 8):** 11 of the 17 inexpressible K2 cells come from 3-point criteria split into 1-point binaries.
   - Options: apply the 2-point line to the criterion rather than to each split credit, or prefer a ladder over a split when the parts would fall under 2.
   - Either is a planner change, so one re-plan (≈ $2.1 Opus) and one re-run.
3. **K4 (din, 8.5 vs 8.25):** self-consistency (`sc_n = 2`, median) is the built lever (CL-3), at about 2× verifier cost on the scopes it covers. Or accept K4 at 8.5 on n = 12.
4. **Budget:** **$22.39 of $25 spent.** Any of (1)–(3) plus the smoke needs about $6–8 more.

Ledger and run actuals: RUNLOG 2026-10-17.
