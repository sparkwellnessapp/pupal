# PRE-REGISTRATION — AI Studio → Vertex serving-surface A/B

**Written:** 2026-08-20, BEFORE either arm was executed.
**Authority:** MISSION_gemini_quota_launch_blocker.md §1.5 step 1, §8.
**Signed off by Noam (2026-08-20):** Q0 criterion = "§1.5 recommended, verbatim".

> This file is written before any result is observed. Post-hoc rationalisation of
> a result already seen is not evidence (§1.5.1). If the outcome contradicts what
> is written below, the outcome wins and the path is closed — the prediction is
> not to be edited after the fact.

---

## 1. The single variable under test

**Serving surface only.** AI Studio (Gemini Developer API, API-key auth) →
Vertex AI (`aiplatform.googleapis.com`, ADC auth), at `location=global`.

Held fixed, verified before the run:

| Held fixed | Value | Evidence |
|---|---|---|
| Model ID | `gemini-3.1-pro-preview` | identical string on both surfaces; `PROD_CONFIG.p1_model_key` and `configs/v0_p1_only.json` both already pin it |
| `prompt_version` | `t1.2` | stamped in `results.json`; unchanged |
| Config | `v0_p1_only.json` | untouched |
| `p1_pages_per_call` | 3 | untouched |
| `dpi` / `image_max_px` | 200 / 2000 | untouched |
| `temperature` | 0.0 | untouched |
| Source code | **zero lines changed** | migration is env-var only; `genai.Client(api_key=None)` ⇒ Vertex |

**Nothing else moves in the same run** (§1.5.3). Not a config tweak, not a
"while I'm here" fix, not the P2 model.

## 2. Protocol

- Mode `p1_only` (primary surface — this is where the variable actually moved).
- `k=5` repeats, **all 5 fixtures**: dan_basiuk, din_ezra, moran_aharon,
  omer_gelber, yonatan_basiuk.
- Baseline arm on AI Studio first, then the surface switch, then the post arm.
- Secondary: `per_doc` (end-to-end) at k=5 pre and post. Any e2e-only movement is
  attributed to P2 (`gpt-5.6-luna`), which is non-deterministic at temperature 0
  and varies run-to-run independently of this change.
- Cost per arm: 5 fixtures × 2 P1 calls × 5 repeats = **50 P1 calls**, ≈ $0.64
  at the measured $0.0254/doc.

## 3. PREDICTION (recorded before the run)

**Primary prediction: NO REGRESSION on any fixture, on any metric.**

Rationale, stated so it is falsifiable: the model ID is byte-identical on both
surfaces, and both are Google-served inference of the same published checkpoint.
The migration changes the authentication and routing layer, not the weights.
I therefore predict per-fixture `doc_ratio_strict` medians to land within normal
P1 run-to-run variance (the observed band on the 2026-08-19 din_ezra k=3 run was
a ~1.5% spread in latency and a stable ratio), with no change in `gate_pass()`
status for any fixture.

**Specific sub-predictions:**

1. `parse_failure_total` = 0 on the Vertex arm (no new truncation).
2. No fixture returns empty content. *If any does, §10.2 applies: investigate
   Vertex safety-filter defaults BEFORE concluding a quality regression.*
3. `cost_avg_per_doc_usd` unchanged within rounding — Vertex is at price parity
   with AI Studio on the **global** endpoint (the ~10% uplift documented from
   2026-07-01 applies to regional endpoints only, and `global` is the sole
   location where `gemini-3.1-pro-preview` resolves for this project).
4. Latency per P1 call: no material change. Median P1 doc latency ~31.8 s on the
   2026-08-19 baseline; I predict the Vertex arm lands in the same band.

**What would surprise me:** a systematic shift on *one* fixture only. That would
point to content filtering (§10.2) rather than a surface difference, because a
genuine serving difference should move all fixtures or none.

## 4. KILL CRITERION (Q0 — signed off before the run)

The gate FAILS, the swap is reverted, and the path is reported closed if **any**
of the following is true:

> For **every fixture** and **every benchmark** in the conjunctive gate —
> `doc_ratio_strict`, `coverage`, `operator_recall`, `structural_recall`,
> `method_call_recall`, `abbreviations_altered` — both must hold across the k=5
> distributions:
> - the **median** post-change value is not worse than the median pre-change value, **and**
> - the **worst-of-k** post-change value is not worse than the worst-of-k pre-change value.
>
> Additionally, **no fixture that passed `gate_pass()` before may fail it after.**

The mean is explicitly **not** an acceptable aggregate on its own — the suite's
standing rule is *worst doc over mean*, because a single catastrophic document
hides inside a healthy average.

**On failure:** revert, report the evidence, treat the path as closed. Do **not**
tune, retry, or explain the regression away — that is motivated measurement, and
the suite exists precisely to prevent it (§1.5). Whether to accept a re-baseline
instead is Noam's ruling, not the executor's (§8).

## 5. What this run does NOT license

- No instrument change. `scoring.py`, `critical_tokens.py`, `normalize.py`, the
  gate thresholds, and `check_goal.sh` are untouched (CLAUDE.md §17.7).
- No model change (§1.3).
- No prompt change (§1.1).
- If the cost constant needs revisiting, that is `Q4` — flagged, not implemented.

---

# ADDENDUM — PRE-REGISTRATION 2: the within-surface CONTROL arm

**Written 2026-08-21, BEFORE the control arm was executed.**
**Ruled by Noam 2026-08-21 after the primary gate returned FAIL.**

## Why

The primary A/B (AI Studio "arm A" vs Vertex "arm V") failed Q0 on 5 metric-rows
across 3 fixtures, all between 0.03% and 1.15%, **bidirectional**, with **no
`gate_pass()` regression** on any fixture. That is consistent with either
(a) P1 run-to-run non-determinism, or (b) a genuine serving-surface difference.
The archive cannot separate them: historical p1_only runs mix prompt versions and
configs, so their spread measures config churn, not noise.

## The test

Re-run `p1_only`, k=5, all fixtures, **on AI Studio again** (arm C). Same config
(`v0_p1_only`), same prompt version (t1.2), same day. Arm A and arm C are the
**same surface**, so any "regression" the Q0 comparator flags between them is
**noise by construction** — there is no surface variable to explain it.

## DECISION RULE (fixed before the result is seen)

Let `R_AV` = the set of Q0 regressions between arm A and arm V (observed: **5**).
Let `R_AC` = the set of Q0 regressions between arm A and arm C (unknown).

- **If `R_AC` is comparable to `R_AV`** in count and magnitude — i.e. the same
  criterion flags same-surface pairs about as often and about as hard — then Q0
  at k=5 **lacks the resolving power** to distinguish serving surfaces. The 5
  flagged rows are then not evidence of a Vertex difference, and the correct
  finding is that the *criterion* needs a noise band, established from `R_AC`.
- **If `R_AC` is clean (0 regressions) or clearly milder than `R_AV`**, then the
  Q0 criterion *can* discriminate at k=5, and the arm-V regressions are evidence
  of a **real surface difference**. The path is then **closed**: report and stay
  on AI Studio.

This rule is symmetric and can falsify the migration. It is recorded before the
run precisely so the outcome cannot be reinterpreted afterwards.

**Not licensed by this run:** editing the gate, the scorer, the thresholds, or
`check_goal.sh` (CLAUDE.md §17.7). Any noise band derived from `R_AC` is a
*proposal to Noam*, never a unilateral instrument change.
