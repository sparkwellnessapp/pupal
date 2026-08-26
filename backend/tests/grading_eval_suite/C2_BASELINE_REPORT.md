# C2 BASELINE REPORT — gpt-4o + grader-v2, k=5 × 5 fixtures (2026-08-26)

**Run:** `results/20260826-174645_gpt-4o` · **25/25 valid** · **spend $1.75**
**Config:** deployed pin `gpt-4o`, `prior_context: OFF`, model solutions rendered, `prompt_version: grader-v2`, `suite_hash: 8e66db31f1df7490`
**⚠ EVERY RATE BELOW IS PROVISIONAL** — n=5 fixtures, one exam (`n_fixtures=5<10`, stamped by the instrument).
**No grader change is proposed here. Threshold pre-registration comes after this report.**

---

## Tier 0 — Validity (first, per PLAYBOOK)

| | |
|---|---|
| Trials | **25 valid / 0 invalid** |
| D7 re-runs fired | **0** |
| Wall-bound hits | 0 |
| Parse failures | **0** → **R6 escalation NOT triggered** |
| Cost | mean **$0.0698**/test, max $0.0726 — **under the $0.10 ceiling** |
| Latency | median 12.3 s, max 17.8 s |
| Total spend | **$1.7462** |

**Multi-scope smoke (U2/G-21) — PASSED.** This baseline is the first multi-scope
evidence in the system's history (all 50 production drafts were single-scope).
150 scope-gradings across 25 trials: `graded_by` = **150 llm, 0 failed, 0
skipped**; `len(scope_outcomes) == len(scopes)` held on **all 25 trials** (D3
totality); `parent_answer_fallback` never fired (correct — depth-1 rubric).

## Tier 1 — Tripwires

**24/25 valid trials pass.** One failure, one taxonomy entry:

| Tripwire | Result |
|---|---|
| `T1-FABRICATED` | **2 violations, both in `dan_basiuk` r2** — `q1.ג.c1` (GT 1, AI 1.00, quote `not_found`, conf 1.00) and `q1.ג.c7` (GT 0.5, AI 1.00, quote `not_found`, conf 0.80) |
| `T1-CW` closed world | clean |
| `T1-SKIP` skip agreement | clean |
| `T1-SELECTION` | clean |
| `T1-COST` | clean |

dan's other four trials are clean — this is a **1-in-25 stochastic fabrication**,
not a systematic one. Quote-status distribution across all 950 terminals:
**878 exact · 64 none · 6 fuzzy · 2 not_found**. Evidence discipline is strong;
the failure mode is rare but real, and it is exactly what the tripwire exists to catch.

## Worst test — `din_ezra`

| fixture | GT | AI median [min,max] | signed Δ | shippable | edit_burden | boundary flips |
|---|---|---|---|---|---|---|
| **din_ezra** | 55.5 | **33.00** [31.50, 38.25] | **−22.50** | 0/5 | 20 | 5/5 |
| dan_basiuk | 84.0 | 68.00 [67.25, 70.50] | −16.00 | 0/5 | 16 | 5/5 |
| moran_aharon | 92 | 82.25 [82.00, 85.00] | −9.75 | 0/5 | 10 | 4/5 |
| yonatan_basiuk | 92.5 | 83.75 [78.75, 84.50] | −8.75 | 0/5 | 12 | 5/5 |
| omer_gelber | 89.0 | 87.00 [84.75, 87.75] | −2.00 | 0/5 | 6 | 1/5 |

**Every fixture is under-scored. Not one is over-scored.**

## Two hand-read terminal tables

### Table 1 — `din_ezra` q2.ב (the worst test's diagnostic core)

```
terminal     GT    AI across k=5              med Δ   quote  conf
q2.ב.c0      1     0 0 0 0 0                  −1      exact  1.00
q2.ב.c3.s0   2     0 0 0 2.00 0               −2      -      1.00
q2.ב.c4.s0   1     0 0 0 0.50 0               −1      exact  1.00
q2.ב.c4.s3   3     0 0 0 0 0                  −3      exact  1.00
q2.ב.c4.s4   1     0 0 0 0.50 0               −1      exact  1.00
q2.ב.c4.s5   0.5   0 0 0 0 0                  −0.5    exact  1.00
q2.ב.c5      0.5   0 0 0 0 0                  −0.5    exact  1.00
             ...   (7 further terminals: GT 0, AI 0, exact agreement)
  scope totals: GT = 9.5   AI_med = 0   Δ = −9.5
```

**This is the single most important finding in the run.** The grader
**zeroed the entire scope at confidence 1.00**. It *did* register that din
solved a different problem — but its response was all-or-nothing annihilation,
where the teacher awarded 9.5 points of partial credit for the structural
components that *were* correct (the loop, the min-search, the return). The
failure is not "missed the wrong target"; it is **"detected the wrong target
and then refused to credit anything at all, with maximal confidence."**

### Table 2 — `omer_gelber` q1.ב (best-agreeing fixture)

```
terminal     GT    AI across k=5                    med Δ   quote  conf
q1.ב.c0      2     2.00 2.00 2.00 2.00 2.00         +0      exact  1.00
q1.ב.c1      0     0 0 0 0 0                        +0      exact  0.75
q1.ב.c2      1.5   1.50 1.50 1.50 0 1.50            +0      exact  0.75
q1.ב.c3      3     3.00 3.00 3.00 3.00 3.00         +0      exact  1.00
q1.ב.c4      1.5   3.00 3.00 3.00 3.00 3.00         +1.5    exact  1.00
q1.ב.c5      1     1.00 1.00 1.00 1.00 1.00         +0      exact  1.00
q1.ב.c6      1     1.00 1.00 1.00 1.00 1.00         +0      exact  0.75
q1.ב.c7      1     1.00 1.00 1.00 1.00 1.00         +0      exact  1.00
  scope totals: GT = 11.0   AI_med = 12.50   Δ = +1.5
```

Seven of eight terminals exact and stable across all five trials. The lone
disagreement, `q1.ב.c4`, is **P2's named prediction landing exactly**: the
inverted `!= null` guard was missed and full credit given (3.00 vs 1.5), at
confidence 1.00, five times out of five. **Absence-detection leniency is real —
it is just not the dominant effect.**

## Tier 2 — Agreement (UNGATED-WATCHED, PROVISIONAL)

| Metric | Value |
|---|---|
| `terminal_within_precision_rate` | **0.6589** |
| `terminal_exact_rate` | 0.6084 |
| `terminal_mae` | 0.34 |
| **mean signed terminal Δ** | **−0.3089** |
| direction census (n=950) | **over 20 · under 352 · exact 578** |
| `shippable_grade_rate` | **0.0** (0/25) |
| pooled median \|Δ_total\| | 10.00 (mean 11.74; min 1.25, max 24.00) |
| `boundary_flip_rate` | **0.80** |
| `compensating_error_count` | **0** |
| `exclusion_mismatch_count` | 0 |

**Harshness attribution by scope** (summed signed Δ, negative = grader harsher):

```
q2.ב  −129.75      q1.ג   −18.50
q2.א   −58.50      q1.א   −18.25
q2.ג   −55.00      q1.ב   −13.50
```

Q2 accounts for **−243 of the −264 total**. The harshness is concentrated in
the question with the model-solution-heavy, multi-part scopes — not spread evenly.

## Tier 3 — Diagnostics

- **Repeat stability:** **71/190 terminals (37.4%)** show non-zero award spread
  across k=5. Worst per-fixture terminal spread: din 2.5, dan 2.0, omer 1.5,
  yonatan 1.5, moran 1.0 points. Per-test total spread up to **6.75 points**
  (din) on identical input.
- **Calibration:** **ECE = 0.2438** over n=950 (not n-flagged). The curve is
  severely overconfident everywhere:

| bin | n | mean conf | accuracy |
|---|---|---|---|
| [0.9,1.0) | 655 | 0.972 | **0.774** |
| [0.8,0.9) | 111 | 0.803 | **0.387** |
| [0.7,0.8) | 164 | 0.744 | **0.451** |
| [0.5,0.6) | 19 | 0.500 | **0.105** |

  **465 of 950 terminals were emitted at confidence exactly 1.00.** Confidence
  is close to useless as a triage signal in this state — the 0.8 band is *less*
  accurate than the 0.7 band, so it is not even monotone.
- **Quote status:** 878 exact · 64 none · 6 fuzzy · 2 not_found.
- **`parent_answer_fallback`:** never fired.

## R6 escalation check

**Parse-failure rate = 0.0 → escalation NOT triggered.** No fixture bucketing is
owed before future model comparisons.

---

## P2 scored — line by line

### Quantitative

| # | Prediction | Actual | Verdict |
|---|---|---|---|
| 1 | `shippable_grade_rate` = 0/25 | **0/25** | **CONFIRMED** |
| 2 | `terminal_within_precision_rate` 0.55–0.70 | **0.6589** | **CONFIRMED** |
| 3 | Median per-test \|Δ_total\| = 8–15 | pooled median **10.00** (but only **2 of 5** fixture medians in band; din 22.5 and dan 16.0 above, omer 2.0 below) | **CONFIRMED on the pooled reading** — recorded with the caveat, since the per-fixture spread is wider than the band implies |
| 4 | Parse-failure rate = 0 | **0.0** | **CONFIRMED** |
| 5 | Cost ≈ $0.03/test, under ceiling | **$0.0698**/test, max $0.0726, under $0.10 | **SPLIT — under-ceiling CONFIRMED; the $0.03 estimate FALSIFIED** (2.3× high) |
| 6 | Repeat instability >30% of terminals | **37.4%** | **CONFIRMED** |

### Directional — the mechanism under test

| # | Prediction | Actual | Verdict |
|---|---|---|---|
| 7 | **Systematic leniency: positive mean signed Δ** | **−0.3089** (over 20 / under 352) | **FALSIFIED — and it fires P2's own named falsifier** |
| 8 | Counterposed over-deduction on PL-10-forgiven syntax | harshness is real but attributable in the read tables to **wrong-target zeroing**, not syntax nitpicking; no per-terminal syntax attribution available without reading 950 reasonings | **INDETERMINATE** |
| 9 | `compensating_error` fires on ≥2 fixtures | **0** — errors are one-directional, so nothing cancels | **FALSIFIED** |

### Named terminal predictions

| # | Prediction | Actual | Verdict |
|---|---|---|---|
| 10 | omer/`q1.ב.c4` — inverted `!=null` missed, full credit | GT 1.5 → **AI 3.00 ×5/5** | **CONFIRMED (exactly)** |
| 11 | yonatan/`q1.ג.c7` — copy-paste wrong vars missed, full credit | GT 0.5 → AI [0.5, 1.0, 0, 0, 0.5], median **0.50** | **FALSIFIED** |
| 12 | moran/`q2.ב.c1` — [100] vs [101] missed | GT 1 → AI **1.00** median (off-by-one missed, full credit) | **CONFIRMED** |
| 13 | `q1.ג.c6`/`q1.ג.c7`/`q2.ב.c3.s1` over-credited on most fixtures | c6: over 1/5, under 1/5, exact 3/5 · c7: over 1/5, under 1/5, exact 3/5 · c3.s1: **exact 5/5** | **FALSIFIED** |

### Worst / best

| # | Prediction | Actual | Verdict |
|---|---|---|---|
| 14 | Worst test = **din** | **din**, median \|Δ_total\| 22.5 | **CONFIRMED** |
| 15 | Grader **over**-credits din by +15 to +25 | **−22.50** — under-credits, magnitude in band, **sign inverted** | **FALSIFIED** |
| 16 | Best agreement = moran | **omer** (\|Δ\| 2.0); moran 9.75 | **FALSIFIED** |

### Falsifier check (P2's own kill criteria)

| Falsifier | Fired? |
|---|---|
| `shippable_grade_rate` > 0.4 | No (0.0) |
| terminal MAE < 0.3 | No (0.34 — close, but not fired) |
| **negative mean signed Δ (systematic harshness)** | **YES — FIRED (−0.3089)** |

**P2's model of the grader is falsified by its own named falsifier.** The
prediction that the grader would be systematically *lenient* — because
absence-detection is hard — was wrong in sign. Absence-leniency exists and was
even caught at the exact terminal P2 named (omer/`q1.ב.c4`), but it is swamped
roughly 17:1 by a much larger harshness effect concentrated in Q2, whose
signature in the read tables is **confident all-or-nothing zeroing of scopes
that solve the wrong problem**.

This is a good outcome, recorded plainly. A pre-registered prediction with named
falsifiers produced a clean, unambiguous falsification on first contact with
data — which is exactly what the instrument was built to make possible.

---

## What this run establishes (facts, not proposals)

1. **The instrument works end to end on real data**: 25/25 valid, tripwires
   caught a genuine 1-in-25 fabrication, artifacts complete, provenance stamped.
2. **The grader under-scores every student** in this corpus — 0/25 shippable,
   boundary flips on 80% of trials. On a 55-pass-line exam, din moves 55.5 → 33.
3. **Confidence is not yet a usable triage signal** (ECE 0.24, non-monotone,
   49% of terminals at exactly 1.00) — the confidence-triggered-verification
   feature remains correctly blocked.
4. **Non-determinism is material**: 37.4% of terminals move across k=5, up to
   6.75 points per test on identical input.
5. **Q2 carries −243 of −264 signed points** — the harshness is concentrated,
   not diffuse.

**Not proposed here:** any grader change, any threshold. Tier-2 threshold
candidates are pre-registered *after* this report, from this distribution;
step-3 work waits for it.
