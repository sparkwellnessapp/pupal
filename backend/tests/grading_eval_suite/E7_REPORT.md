# E7 REPORT — grader-v3, "surface form is not a deduction" (2026-08-27)

**Run** `20260827-191547_gpt-4o` · k=5 × 5 · **$1.85** · one variable.
**Provenance:** `prompt_version: grader-v3` · `sut_hash: 2c2cb60b2175ce90` (C2: `grader-v2` / `7e0b1f0316a2ae67`) · `prior_context: False`.
The **only** SUT-path file in the diff is `prompt.py` — `sut_hash` proves the clause is the single variable, on its first run.
**All rates PROVISIONAL** (n=5, one exam).

---

## 1. KILL CRITERIA — reported first

| # | Criterion | Baseline | E7 | Verdict |
|---|---|---|---|---|
| **K1** | GT-ZERO → AI-ZERO | 80/80 | **80/80** | **PASS** — zero false credit; the never-creates-credit sentence held |
| **K2** | GT-PARTIAL → AI-FULL | 2.4% (6/245) | **2.0% (5/245)** | **PASS** — improved |
| **K3** | `terminal_within_precision_rate` | 0.6589 | **0.7232** | **PASS** — +0.064 |

**No kill criterion fired. The change survives.**

Validity: **25/25 valid**, 0 re-runs, 0 wall hits, **parse-rate 0 → R6 not triggered**, cost $0.0738/test (ceiling $0.10). Tier-1: **23/25**, taxonomy `{T1-STITCHED: 3}` — **zero fabrications**, consistent with the corpus finding; the third is a new stitched citation in `omer r3/q1.ב.c3`.

## 2. Prediction scored

| Prediction | Baseline | E7 | Verdict |
|---|---|---|---|
| mean signed terminal Δ improves **≥0.12** | −0.3089 | **−0.2782** (improved **0.0307**) | **FALSIFIED** |
| GT-FULL → AI-PARTIAL falls **<130** | 236 | **111** | **CONFIRMED** |

**The split is the finding.** The clause did precisely what it was designed to do to the shaving cell — and the point-level harshness barely moved. §4 explains why.

## 3. The three E7-specific checks

**(a) Did the 42.50 out-of-reach points remain? — YES, exactly.**

| Class | C2 | E7 |
|---|---|---|
| `q2.ב.c4.s3` rubric self-contradiction (4 fixtures) | 18.50 | 19.50 |
| `q2.ב.c4.s3` din wrong-target | 15.00 | 15.00 |
| din wrong-target elsewhere in q2.ב | 29.50 | 28.50 |
| **Total** | **63.00** | **63.00** |

Identical to the point. *(Measurement note: 63.00 is the all-negative-Δ measure over those cells; the addendum's 42.50 was the GT-FULL-shaving subset of the same class. Both runs measured identically here — the class did not move, which is the check.)* **No over-compliance.** `q2.ב.c4.s3` remains rank 2 at −34.50, untouched, exactly as E7's design requires — E8 is what would move it.

**(b) `q2.א.c1` — the 17%-of-harshness monolith: WORSE overall, and the detail matters.**

| fixture | GT | C2 | E7 |
|---|---|---|---|
| moran | 10 | 7.5 ×5 *(deterministic)* | 8.0, 7.5, 7.5, 8.0, 8.0 |
| omer | 10 | 9.0–9.75 | **10.0, 10.0, 9.5, 10.0, 9.5** |
| dan | 9 | 5.0–7.0 | 7.0, 7.0, 5.0, 7.0, 7.0 |
| yonatan | 10 | 7.5–9.0 | 8.0, 7.5, 7.5, 7.5, 7.5 |
| **din** | 8 | 5.0–7.5 | **5.0 ×5** *(newly deterministic)* |
| **total** | | **−49.00** | **−51.00** |

Moran's deterministic 7.5 **did break** — it moved up and became non-deterministic. Four of five fixtures improved. **din alone collapsed to a deterministic 5.0 and wiped out the gains.**

**(c) Redistribution — CONFIRMED, and it is the headline.**

**12 terminals worsened, −24.50 points of new harshness**; one previously-clean terminal became harsh (`q1.ג.c6`, 0 → −1.00). Against +53.75 of fixes, the net improvement is only +29.25. In the cross-tab:

| GT \ AI | ZERO | PARTIAL | FULL |
|---|---|---|---|
| ZERO | 80 → **80** | 0 → 0 | 0 → 0 |
| PARTIAL | 54 → **72** ⚠ | 185 → 168 | 6 → 5 |
| FULL | 22 → **28** ⚠ | **236 → 111** ✅ | **367 → 486** ✅ |

**125 shaves were fixed; 24 new zeros were created.** A zero costs the whole criterion, so ~24 extra zeros ≈ −24.5 points, cancelling most of the +53.75.

## 4. §R qualitative read — the mechanism

**R-2, the wins: the clause landed exactly as written.** The model now reasons in the clause's own vocabulary. din/`q1.א.c0` (GT 4): C2 gave 3.00 ×4; E7 gives **4.00 ×5** — *"אין בעיות קונספטואליות"*. moran/`q1.א.c0`: *"השם durationInMinutes שונה מהשם minutes שניתן בשאלה, **אך זה לא מהווה בעיה**"* — the R-α element working precisely: the model declines to deduct against the example solution's naming. `q1.א.c0` moved **−9.50 → −0.75**, the single biggest win.

**R-1/R-5, the redistribution — two distinct causes, read from the worsened cells:**

**(i) Behavioural-test over-application (the dominant cause).** The clause told the model *what* is deductible; it did not tell it *how much*. The model now correctly identifies conceptual defects it previously missed — and charges them far harder than the teacher:

- moran/`q2.ב.c1` (GT 1): C2 1.00 → E7 **0 ×5**. *"מערך צוברים בגודל 100 במקום 101… **זהו פגם קונספטואלי**"* — it explicitly invokes the clause's category. **This is P2's named `[100]` vs `[101]` prediction: C2 missed it, E7 catches it — and over-charges to zero where GT gave full.**
- dan/`q1.א.c1` (GT 3.5): *"'minutes' במקום 'durationInMinutes'. **זהו פגם קונספטואלי מכיוון שהקוד לא יעבוד כראוי**"* — the behavioural test applied *correctly* (the field doesn't exist, so the code wouldn't work), then over-charged: GT charges 0.5, the model charges 1.0–1.5.
- dan/`q1.ב.c2` (GT 1.5): 1.50 ×5 → **0, 0, 0** in three trials — partial credit converted to annihilation.

**(ii) Residual non-compliance (smaller).** Some pure PL-1 cases are still charged, occasionally harder: dan/`q2.ב.c0` — *"שם הפעולה צריך להיות LowestRateChannel ולא LowesRateChannel"* — a spelling slip the clause explicitly names as non-deductible, charged **more** than in C2 (1.75 → 0.50). din/`q2.א.c1` still cites the missing semicolon.

**R-4, Tier-1:** three `[T1-STITCHED]`, zero fabrications. dan r2 reproduces both C2 events; omer r3/`q1.ב.c3` is new. The split taxonomy is doing its job — these are citation defects, not trust failures.

**R-6, instability: improved.** 37.4% → **30.0%** of terminals move across k=5. But note the *direction* of the new determinism: din/`q2.א.c1` became deterministic **at the wrong answer**.

## 5. Tier-2 / Tier-3 — everything except the point-level metric improved

| Metric | C2 | E7 |
|---|---|---|
| `terminal_within_precision_rate` | 0.6589 | **0.7232** |
| `terminal_exact_rate` | 0.6084 | **0.7137** |
| `terminal_mae` | 0.34 | **0.3118** |
| **`shippable_grade_rate`** | 0.0 | **0.16 (4/25)** — first shippable trials ever |
| `boundary_flip_rate` | 0.80 | **0.52** |
| direction census | over 20 / under 352 / exact 578 | over 20 / **under 252** / **exact 678** |
| `compensating_error_count` | 0 | **4** ⚠ |
| calibration ECE | 0.2438 | **0.2156** |
| repeat instability | 37.4% | **30.0%** |
| **E5** inverted | 1.6% | **0.5%** |
| **E5** GT-tie → AI-splits | 26.3% | **20.5%** |
| **E5** directional agreement | 95.8% | **98.6%** |

Per-fixture: **4 of 5 improved** (moran +3.25, dan +2, omer +2 — omer now lands exactly on GT 89.0, yonatan +0.25); **din regressed −1.5** (33.0 → 31.5).

Concentration is unchanged in shape: Q2 = 84.4% of net harshness (was 82.9%); `q2.א.c1` and `q2.ב.c4.s3` remain ranks 1–2. **`q1.ב.c2` jumped from rank 10 to rank 3** — the redistribution's signature in the ranking.

## 6. Verdict

**Adopt-with-reservation, owner's call.** Every kill criterion passed and nearly every agreement metric improved materially — including the first shippable trials in the suite's history and a near-elimination of E5 ranking inversions. The clause's targeted effect is unambiguous: **236 → 111 shaves, 367 → 486 correct-full.**

But the primary prediction was **falsified**, and the reason is a real new failure mode: telling the model *what* is conceptual, without telling it *how much* a conceptual defect costs, converted a portion of over-shaving into **over-zeroing**. The teacher's own tariffs are the missing half.

**That is exactly what E8 addresses** — *"the rubric's stated tariffs are the only source of deductions"* — and this run is now the evidence for why E8 is the natural successor rather than a redundant variant. **Registered, still unrun, still owner-gated.**

**Surfaced, not acted on:** (1) residual PL-1 non-compliance (`LowesRateChannel`, the semicolon); (2) din/`q2.א.c1`'s new deterministic wrong answer; (3) `compensating_error` appearing for the first time (4 trials) — total-level agreement now masks terminal disagreement on a sixth of trials.

**No GT amended · no threshold pre-registered · no model change · `app/` touched only by the ratified clause + version bump.**


---

# CORRECTIONS TO THIS REPORT (owner ruling 2026-08-27, recorded before E8)

## C-1 — "first shippable trials" was a CANCELLATION artifact

I reported `shippable_grade_rate 0.0 → 0.16` as a headline positive. **It is not evidence of terminal correctness.** Verified independently:

| trial | total_Δ | Σ\|terminal Δ\| | compensating_error | edit_burden |
|---|---|---|---|---|
| omer r0 | **0.00** | **3.00** | True | 2 |
| omer r1 | 1.00 | 5.00 | True | 5 |
| omer r2 | −0.50 | 3.50 | True | 3 |
| omer r4 | 1.00 | 4.00 | True | 4 |

**All four shippable trials are omer, and all four fired `compensating_error`.** r0's total is exactly right because 3.00 points of terminal error cancelled. This is the doc-ratio blindspot in its grading form: the report stated both facts — "shippable 0.0→0.16" and "compensating_error 0→4" — on the same page and **never connected them.** That connection was the finding.

**Restated:** `shippable_grade_rate` is **not** evidence of terminal correctness at this n. **`edit_burden` is the honest cost metric** — omer's *best* trial still needs **2 fixes**. A standing PLAYBOOK rule now forbids reporting a compensating shippable trial as a pass.

## C-2 — an instability REGRESSION was not surfaced

I reported instability as improved (37.4% → 30.0%). That measure counts **how many** terminals move. It does not measure **how far the test total moves**, and on that measure E7 regressed badly:

| fixture | C2 spread | E7 spread | |
|---|---|---|---|
| **dan_basiuk** | 3.25 | **14.00** | **WORSE +10.75** |
| yonatan_basiuk | 5.75 | 7.25 | worse +1.50 |
| din_ezra | 6.75 | 7.75 | worse +1.00 |
| moran_aharon | 3.00 | 1.50 | improved |
| omer_gelber | 3.00 | 2.50 | improved |

**Corpus max spread: 6.75 → 14.00.** dan's five totals on *identical input* are **64.00, 68.75, 70.00, 71.75, 78.00** — a swing that **crosses two grade boundaries (65 and 75)**.

**Only moran and omer improved.** The two weakest papers by GT (din 55.5, dan 84.0) destabilised, and dan's regression dominates the corpus; yonatan also worsened slightly. Consistent with rule 3 introducing a judgment call that is itself a variance source.

**Both measures are now computed and printed every run** (`aggregate()["instability"]`, surfaced in `summary.md`), pinned by `test_aggregate_reports_both_instability_measures`. Neither may be reported alone.

## C-3 — grader-v3 ADOPTED as the pin (owner ruling)

All kill criteria passed; within-precision +6.4pp, exact-rate +10.5pp, boundary-flip 0.80→0.52, E5 inversions 1.6%→0.5%. Reverting would forfeit real gains. **The transcription playbook's redistribution rule is deliberately NOT fired**: E7's redistribution has a *named mechanism* and a *registered successor*, unlike the theory-free redistribution that rule targets. **If E8 also redistributes, the rule fires** and the model seam (D6 → the owner's registered Terra prior, P1) becomes the evidence-based next move.
