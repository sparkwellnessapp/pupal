# EVAL_REPORT_v6 — CS section, after the AM-G19 iteration (Oct 17)

Provisional: n = 12 fixtures on 2 exams (hobby 5, bagrut 7). Every conclusion is provisional.

**Status (Oct 17, evening): this is the STOP-3 package (ruling §8).**
- Ship criteria (1)–(4) hold, (1) by owner override.
- (5) and STOP-3 GO wait on one external fact: Claude quota on Vertex (§10).
- The MVC is built and T1 is green (§11); the v6.1 backlog is §12.

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

**The verdict with the overrides (the STOP-3 package, ruling §8):**

| ship criterion | status |
|---|---|
| (1) kills hold | **met by OWNER OVERRIDE** — K2 15.0% (OO-1), K4 8.5 (OO-2); K1 93/93 ✅. The bars and the gate code are unchanged. |
| (2) G-D1 = G-D2 = 0 | ✅ 0 / 0 |
| (3) K3 and G-Z no worse than v5 | ✅ K3 0.784 (v5 0.693) · G-Z 21.8% (v5 31.6%) |
| (4) cost per test below v5 | ✅ shipping **$0.1454** (verifier + explainer arm B) against v5 $0.1774. Feedback (≈ $0.043, §4) is paid by both architectures and reported separately. |
| (5) Math/English smoke | §6a ✅ ($0, structural). **§6b NOT RUN: blocked on the Vertex quota** (§10). Under ruling §8, STOP-3 GO waits on it. |

**STOP-3 GO conditions (pre-granted when all hold):** §6b passes for Math and English — ⏳ (Vertex quota); the MVC deployed with T2 green — ⏳ (built; T1 green, §11); production Claude on Vertex (§5d) — ⏳ (Vertex quota).

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

| component | v6 · Oct 6 | v6 · Oct 17 (run 10) | **shipping (OO-3)** | v5 |
|---|---|---|---|---|
| verifier (Sonnet 5.5, effort low) | $0.0596 (cache hit 90%) | $0.0625 (90%) | **$0.0625** | $0.1774 |
| explainer | arm A (Haiku 4.5) $0.0419 (59%) | arm A $0.0429 (59%) | **arm B (Sonnet 5.5 lowest) $0.0829** | — |
| **grading total** | $0.1016 | $0.1054 | **$0.1454** | $0.1774 |
| feedback (Sonnet 5, one call per test) — separate | | | **≈ $0.043** (estimate, range $0.037–$0.051) | the same call |
| planner (Opus 5.5, once per rubric) | | $1.06 hobby + $1.06 bagrut | ≈ $1.1–1.2 per rubric | compiled plan |

- The AM-G19 plans carry about 10% more options, which explains the 4% cost rise.
- **Shipping explainer (arm B):** measured at $0.0818 on run 4's recorded payloads (64% cache hit), scaled ×1.015 input / ×1.010 output to run 10's payloads → $0.0829.
- **Feedback, estimated at $0** (`tools/v6_feedback_cost.py`, no provider call). Method:
  - **Input:** the exact message the runner sends, rendered from the 36 recorded run-10 v6 drafts: 12,526 characters mean.
  - **Output:** the only recorded feedback texts (5 hobby tests, Aug 30), per scope, scaled to each draft's 6–10 graded scopes.
  - **Characters → tokens:** 0.606 tokens per character, the slope of total input tokens on message characters over the 226 single-call scope verifications of run 10 (Sonnet 5.5, the same Hebrew + code mix).
  - **Caveat:** it does not count thinking tokens, if the feedback model emits any. D-7 now writes the real figure into each v6 row's `total_cost_usd`, and §10 of the production leg reads it.
- Every v5 production grade also makes this feedback call, but v5's `total_cost_usd` never counted it. So the like-for-like grading comparison is $0.1454 against $0.1774.
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

### 8a · Structural (§6a) — PASSES, $0, no model

Renders: `docs/plans/v6_smoke_structural.md`. Method: the deterministic FALLBACK plan, the real v6 grader on a scripted model, every check set by hand to the option matching the pre-registered class (`smoke/known_answers.json`), priced by THE pricer.

| | Mathematics (math3) | English (Ministry F/G, task 016584) |
|---|---|---|
| Stage 1 | 23 scopes · 31 criteria · 31 checks | 1 scope · 4 criteria · 4 checks |
| fallback plan, V12–V20 · V21 | clean · 0 | clean · 0 |
| `levels` from the C8-lite ladder | — | 8/5/2/0 · 10/6/3/0 · 16/10/5/0 · 6/4/2/0 |
| verifier payload | aliases only, value-invariant ✅ | aliases only, value-invariant ✅ |
| explainer payload | aliases only ✅ | aliases only ✅ |
| blank/wrong → 0 · full → full | ✅ · ✅ | ✅ · ✅ |
| partial | ✅ where expressible | ✅ every band |

**Partials the fallback plan cannot express** (single binary checks): Math A2 `q1.ג.c0`, `q1.ג.c2`, `q2.ב.c0`, `q4.ד.c0`, `q5.ב.c0`. That is expected of a fallback; §6b grades on the planner's plan.

### 8b · Graded (§6b) — NOT RUN: blocked on the Vertex quota

Under ruling §4, an eval call must not go to the Anthropic API, and Vertex refuses every Claude call (§10). The run is ready and pre-registered:
- **Config:** the production configuration (§7): Opus 5.5 planner on `planner-v6.2`, Sonnet 5.5 verifier at effort low, k=1, NO explainer.
- **Order:** plan Math, then English A3 (blank/wrong) → A2 (partial) → A1 (full), with a budget check before each step.
- **Command:** `python -m tests.eval_common.eval_key tests.grading_eval_suite.tools.v6_smoke --confirm-spend --max-usd <remaining of $3>`.
- **Pass criteria:** pre-registered in `PREDICTIONS.md`. There are no pack iterations.
- **Estimate:** ≈ $1.2 Opus planning for Math (English needs no planner call) + ≈ $0.4 grading 6 tests ≈ **$1.6**, inside the $3.

## 9 · The decisions that were yours — resolved by the Oct 17 rulings

1. The K2 residual (21 of 44 cells are verifier misses) → **accepted, OO-1.** The verifier literal-check rule is v6.1.
2. AM-G19 × split (rule 8) → **v6.1**.
3. K4 (din, 8.5) → **accepted, OO-2**; no self-consistency.
4. Budget → **re-ruled (§4):** Anthropic direct = $0 eval spend; GCP at most $3 for this PR.

## 10 · The Vertex route (§5)

**Built and tested offline** (`b540508`):
- **The switch:** `CLAUDE_ROUTE=vertex` (+ `CLAUDE_VERTEX_REGION`, `CLAUDE_VERTEX_PROJECT`) moves every factory-built Claude call: the v6 planner/verifier/explainer, feedback, the v5 grader and the plan builder.
- **Model ids:** from the closed `VERTEX_MODEL_IDS` table, never guessed.
- **Provenance:** the provider is stamped in draft provenance (`llm_provider`, `UsageV6.provider`), the cost ledger and `ContractV6.provider`.
- **The guard** blocks the Vertex hosts in tests.
- **Tests:** 18 route tests.

**Region: `eu`** (decided, pending veto). It is the only EU location that serves all four models production needs: Opus 5.5 and Sonnet 5.5 are also in europe-west1/west4, while Sonnet 5 and Haiku 4.5 are only in `eu`/`global`. It also matches the Frankfurt database's residency.

**Live verification: BLOCKED (STOP §12e).** Every Anthropic base-model quota on project `gen-lang-client-0438328890` is 0. A 16-call probe returned 429 RESOURCE_EXHAUSTED everywhere; $0 was billed.

**The owner must:**
1. Request the `Eu*PerBaseModel` quotas:
   - `anthropic-claude-sonnet`: 300 RPM / 2M input TPM / 200k output TPM;
   - `anthropic-claude-opus`: 30 / 300k / 100k;
   - `anthropic-claude-haiku-4-5`: 30 / 100k / 20k.
2. Confirm that the GCP credits apply to Vertex partner (Anthropic) models.

| per model (planner Opus 5.5 · verifier/explainer Sonnet 5.5 · feedback/v5 Sonnet 5 · Haiku 4.5) | status |
|---|---|
| served in `eu` | ✅ read from the probe (429, not 404) |
| caching (reads/writes in usage) and GCP billing | ⏳ quota |
| effort / adaptive thinking accepted | ⏳ quota |
| structured output for each call shape (planner native `json_schema` on Opus; if refused → an unforced tool + schema validation + the one repair) | ⏳ quota |
| served-model id + usage recorded | ⏳ quota (the code path is tested offline) |

The canary is ≈ $0.002, recorded in the RUNLOG before it runs. §5d, the production switch, is a config-only deploy (`CLAUDE_ROUTE=vertex`, `CLAUDE_VERTEX_REGION=eu`). Its gate is T1 + a health check + the first production call's provider and served-model stamp read from the logs. Rollback is the config.

## 11 · The minimum viable cutover (§7) — status

**Backend: built, $0** (`cc93446`, `af8ad47`):
- The runner writes v6 drafts with the explainer line written at grading time; nothing else writes it.
- `GET /graded_test/{id}/v6` is owner-scoped; a cross-tenant id gets 404.
- `PATCH …/v6/draft` merges (A-3: the stamp survives). CW-3 is extended to checks and options.
- Approval goes through the one pricer. `ContractV6` freezes the plan hash, the provider, each check's model and effective option with its quote status, and each criterion's reasoning line and source.
- Feedback per AM-G7. D-6 and D-7 apply.
- Plans build lazily under the v6 key (migration 035).

**Frontend:** the TS pricer mirror passes every vector (544/544, plus 6,001 extra parity cases). The v6 review surface is in progress.

**Tests:** T1 is 2,033 passed + 2 fixed (`af8ad47`). Both were mine: the overlay-key guard and the stale vectors. T2 runs before the deploy.

**Deploy (authorized):**
1. Apply migration 035 to production.
2. Backend from a clean worktree with `GRADER_ARCHITECTURE=v5`.
3. Frontend.

**The production leg (§10):** `docs/plans/v6_production_leg_query.sql`, pinned by a test.

## 12 · The v6.1 backlog

**Quality**
- **The verifier literal-check rule:** a label's stated bound or form must be checked literally before `full`. It covers 21 of the 44 K2 cells.
- **AM-G19 × split (rule 8):** apply the 2-point line to the criterion rather than to each split credit, or prefer a ladder over a split. It covers 11 of the 17 inexpressible K2 cells.
- **K4 self-consistency** (CL-3, `sc_n = 2`, median).
- **First-person absence pointers.**
- **CL-4..CL-6.**

**Product**
- `/similar`.
- `/explanations` + `criterion_explanations`, with the AM-G15 explanation signature that regenerates only changed lines.
- Typed per-check amounts and the evidence-dispute UI. The MVC refuses both as `not_supported`.
- The legacy v5→v6 view, the G4 parity gate, A-1.

**Other**
- Track C.
- F-4.

**Found while building the MVC**
- **TS pricer:** it relabels a charge `floored` when the relief is 0, which is cosmetic; the totals agree. The vectors are thin on `moved_by_pin` / `superseded`; add some.
- **Feedback `basis_hash` for v6:** its staleness key flattens v5-shaped checks. A v6 draft needs its own key once she can re-request feedback.
- **Plan builds:** they are only lazy (inside the grade job). Build at rubric compile on the plan-build queue, and give plan builds LIV-1's absolute arm (already deferred in CLAUDE.md).
- **Feedback cost:** replace the §4 estimate with D-7's production figure once a v6 batch has run.

**Follow-up (§11):** delete the v5 path after 14 days on v6.

Ledger and run actuals: RUNLOG 2026-10-17.
