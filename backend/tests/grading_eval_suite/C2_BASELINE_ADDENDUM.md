# C2 BASELINE ADDENDUM — §R qualitative read + two corrections (2026-08-27)

**Supersedes the mechanism reading in `C2_BASELINE_REPORT.md`.** Run
`20260826-174645_gpt-4o`, k=5 × 5, unchanged data — this is re-analysis, not
re-measurement. **Zero spend. No grader change, no threshold, no GT amendment,
no `app/` touch.** All rates remain **PROVISIONAL** (n=5, one exam).

---

## 1. CORRECTION — the mechanism I reported was wrong

My report named *"confident all-or-nothing annihilation"* as the mechanism, on
the strength of din's zeroed q2.ב. **That reading is falsified by my own
results.json.** din's zeroing is real (4/5 trials; trial 3 awarded 3.0) but it
is **one scope in one fixture**, not the general case.

### R.3 partial-credit cross-tab (independently computed, n=950 observations)

| GT \ AI | ZERO | PARTIAL | FULL | row total |
|---|---|---|---|---|
| **ZERO** | **80 (100.0%)** | 0 (0.0%) | 0 (0.0%) | 80 |
| **PARTIAL** | 54 (22.0%) | 185 (75.5%) | 6 (2.4%) | 245 |
| **FULL** | 22 (3.5%) | **236 (37.8%)** | 367 (58.7%) | 625 |

**AI partial-credit share 44.3% vs GT's 25.8%.** My cells match the owner's
expected figures exactly.

### The corrected mechanism: the grader is more granular than the teacher

**Shaving dominates.** GT gave full marks and the AI deducted **258 times**
(236 FULL→PARTIAL + 22 FULL→ZERO), **median 0.5 pts**, totalling **201.75
points = 68.7% of net harshness**.

> **Denominator reconciliation (my first pass differed; the data did not).**
> Gross negative Δ = 308.25; positive Δ = 14.75; **net signed harshness =
> 293.50**. 201.75 / 293.50 = **68.7%** — exactly the owner's figure. My
> earlier 54.7% counted only FULL→PARTIAL against the gross-negative
> denominator. Same data, different grouping; the owner's framing is the
> correct one and is used throughout below.
>
> **I must also correct an arithmetic error in my first report:** I wrote
> "Q2 = −243 of −264". The net total is **−293.50**, not −264, and
> Q2 = **−243.25 = 82.9%**. The conclusion (harshness concentrated in Q2)
> survives; the numbers were wrong and are restated here.

Annihilation (GT PARTIAL → AI ZERO) is **54 cases, 49.5 pts, 16.9% of net
harshness** — real, but a quarter the size of shaving.

### Headline positive: zero false credit

**Where the teacher gave nothing, the grader gave nothing — 80/80, 100%.**
Not one over-credit on a GT-ZERO terminal in 950 observations. The grader
never invents merit. Its entire error budget is spent taking away.

## 2. CORRECTION — calibration, in two registers

"Non-monotone" was **noise**, and I should not have called it a property. The
0.8-vs-0.7 inversion is **38.7% (n=111) vs 45.1% (n=164)**, and the sub-0.7
band is n=20. Reporting it as a structural finding over-read small cells.

**Register 1 — absolute calibration (unchanged verdict): ECE 0.2438**, with
465/950 terminals emitted at exactly 1.0 while that band is 86.2% accurate.
The model over-claims certainty. **Auto-verification stays blocked.**

**Register 2 — rank usefulness (new, and materially different):**

| band | n | within-precision |
|---|---|---|
| conf = 1.0 | 465 | **86.2%** |
| 0.9 ≤ c < 1.0 | 190 | 55.8% |
| 0.8 ≤ c < 0.9 | 111 | 38.7% |
| 0.7 ≤ c < 0.8 | 164 | 45.1% |
| c < 0.7 | 20 | 10.0% |

**Flag rule `confidence < 1.0`:** reviews **51.1%** of terminals, captures
**76.3%** of total |Δ| — **lift 1.49×**. Residual risk if a teacher trusts
conf=1.0: **13.8%** of those terminals fall outside precision.

These are **different properties**. The grader is badly calibrated in absolute
terms *and* carries a usable ranking signal. **Review triage on `conf < 1.0`
is defensible today; automatic verification is not.**

## 3. Harshness concentration (R.3)

Per-terminal mean signed Δ over 25 trials, worst 14:

| terminal | total Δ | mean Δ/trial |
|---|---|---|
| **q2.א.c1** | **−49.00** | **−1.96** |
| **q2.ב.c4.s3** | **−33.50** | −1.34 |
| q2.ג.c0.s3 | −23.50 | −0.94 |
| q2.ג.c0.s0 | −16.50 | −0.66 |
| q2.ב.c3.s0 | −16.00 | −0.64 |
| q2.ב.c0 | −15.75 | −0.63 |
| q2.ב.c3.s3 | −13.00 | −0.52 |
| q2.ג.c0.s1 | −13.00 | −0.52 |
| q2.ב.c3.s2 | −11.50 | −0.46 |
| q1.ב.c2 | −10.50 | −0.42 |
| q1.א.c0 | −9.50 | −0.38 |
| q2.א.c0 | −9.50 | −0.38 |
| q1.א.c1 | −8.75 | −0.35 |
| q2.ב.c4.s2 | −8.50 | −0.34 |

**Top-3 terminals = −106.00 = 36.1% of net harshness. Worst scope q2.ב =
−129.75 = 44.2%. Q2 = −243.25 = 82.9%.** By scope: q2.ב −129.75 · q2.א −58.50
· q2.ג −55.00 · q1.ג −18.50 · q1.א −18.25 · q1.ב −13.50.

Two terminals deserve naming:

- **`q2.א.c1` (−1.96/trial, ~17% of all harshness)** — the 10-point
  `UpdateRate` monolith with no itemized guidance. GT gave three students
  10/10; the grader shaved every one. A single un-itemized 10-pointer is the
  most expensive terminal in the corpus.
- **`q2.ב.c4.s3` (−33.50)** — the criterion whose own rubric text says
  **«לא להוריד, לכתוב הערה»** (*do not deduct, write a note*). The grader
  deducts anyway, on 3 of 5 fixtures, at confidence 1.00.

## 4. §R qualitative reads

### R-1 — worst test's worst scope, all k (din_ezra q2.ב)

GT 9.5 → AI 0 in 4/5 trials; trial 3 awarded 3.0. **Stable, not stochastic.**
Reasoning at confidence 1.00, r0: *"אין בדיקה האם התא מתאים לערוץ הנוכחי של
TvShow בתוך מערך הצוברים. הבדיקה מתבצעת על מערך אחר ולא על מערך צוברים"* — the
grader correctly identifies that din indexes the wrong array, then withholds
all credit for the loop/min-search/return structure the teacher paid 9.5 points
for. This is genuine annihilation — **but it is this scope, not the corpus.**

### R-2 — best-agreement fixture's disagreements (omer_gelber)

7/8 terminals in q1.ב exact and stable across k=5. The single disagreement,
`q1.ב.c4` (GT 1.5 → AI 3.00 ×5/5, conf 1.00), is the inverted `!= null` guard
missed — P2's named prediction landing exactly. Elsewhere omer's shaving is
cosmetic: `q1.ג.c0` −0.25 for *"'Void' צריך להיות 'void'"*; `q2.ב.c0` −0.5 for
*"TVRate במקום TvRate"* — **the exact slip the owner's AUDIT-2 named as full
credit.**

### R-3 — right-for-wrong-reason audit (3 exact matches sampled of 104)

**One of three is a genuine `right_award_wrong_reason`.** `moran/q2.ג.c0.s3`,
GT=AI=6.00, conf 0.75, quote exact — award perfect, reasoning **self-
contradictory**: *"הסטודנט בדק אם התוכנית אינה null … **עם זאת, לא נבדק אם
התוכנית אינה null**, ולכן יש להוריד נקודות על כך"* — it asserts the null check
is present, then asserts it is absent, then deducts for the absence, and still
lands on the right number. **Invisible to every Tier-1/2/3 metric.** The other
two sampled (dan `q1.ב.c2`, yonatan `q2.ב.c5`) are sound.

### R-4 — every Tier-1 violation in full (dan r2) — **the flag is misclassified**

Both violations are in **one scope of one trial** — report as **one bad
scope-call, not two independent events**.

| terminal | GT | AI | conf | quote_status | validator ratio |
|---|---|---|---|---|---|
| q1.ג.c1 | 1 | 1.00 | 1.00 | not_found | **0.7190** |
| q1.ג.c7 | 0.5 | 1.00 | 0.80 | not_found | **0.8370** |

**All four constituent lines are present verbatim in dan's answer.** Verified
against the transcription:

- `q1.ג.c1` quote = `int counterS = 0;   // כמה ספורט יש` + `int counterNS = 0;   // כמה לא ספורט`
  — both lines real, but **separated by two other lines** in the source.
  Reasoning: *"הסטודנט יצר שני מונים … ואיתחל אותם ל-0, כפי שנדרש"* — sound.
- `q1.ג.c7` quote = `double AvgNS = totaldurationNS / counterNS;` +
  `cw("the non spotiv Avg is: " + AvgNS);` — both real and **adjacent**;
  validator ratio **0.837, just 0.013 below the 0.85 bar**.
  Reasoning: *"חישב את הממוצע והדפיס אותו, אך לא בדק אם המונה שונה מאפס"* — sound.

**The model did not invent evidence. It stitched non-contiguous real ink**, and
`_best_substring_ratio`'s contiguous window cannot distinguish a stitched-real
quote from an invented one. `T1-FABRICATED`'s DL-2 definition — *"the model
invented evidence"* — **does not describe what happened here.** Surfaced, not
acted on: the validator is `app/` (fenced) and the tripwire definition is
instrument (STOP-list item 2). **Two candidate follow-ups for owner ruling, no
change made:** (a) a multi-fragment quote check before declaring `not_found`;
(b) a prompt line forbidding concatenation of non-adjacent lines.

### R-5 — highest |Δ| at confidence ≥ 0.9

`din_ezra/q2.ב.c4.s3`, GT 3 → **AI 0, |Δ|=3, confidence 1.00, in 4 separate
trials.** The most confident, largest, most repeated single error in the run —
and it lands on the criterion whose rubric text **explicitly forbids
deducting**. Confident error against an explicit written tariff is the most
dangerous class this corpus contains.

### R-6 — instability, award spread ≥ 1.0

**14 terminals** move ≥ 1.0 points across k=5. Worst: `din/q2.ב.c3.s0` spread
2.5 (`0,0,0,2.00,0`); `dan/q2.ב.c4.s2` spread 2.0; `din/q2.ב.c4.s0` and
`q2.ב.c4.s4` spread ~1.0 — **all concentrated in din's wrong-target scope**,
where the grader oscillates between annihilation and partial credit. This is
**prompt underspecification about wrong-target answers**, not genuine ambiguity:
the rubric is clear; the grader has no rule for *"solves a different problem
with correct structure."*

## 5. Shaving bucketed — 34 sampled across all five fixtures (§R.2)

| Bucket | Count | Share |
|---|---|---|
| **`interpretive_divergence`** | **34** | **100%** |
| `rubric_underdetermined` | 0 | — |
| `evidence_miss` | 0 | — |
| `evidence_fabricated` | 0 | — |
| `right_award_wrong_reason` | 0 (in this sample; see R-3) | — |
| `gt_questionable` | 0 | — |
| `transcription_artifact` | 0 | — |

Sub-classified against the owner's ratified rulings:

| Sub-class | n | Example (grader's own words) |
|---|---|---|
| **PL-1 cosmetic** — case / spelling / naming | **19** | *"השם צריך להיות … PrintAverages ולא printAverages"* · *"'Public' ו-'Static'"* · *"שגיאת כתיב במילה Return"* |
| **PL-10** — malformed but unambiguous | 3 | *"ניגש לערוץ באמצעות get.chl(), אך התחביר שגוי"* (**the exact AUDIT-2 case**) · *"סוגריים עגולים במקום מרובעים"* |
| **PL-2** — CW/CR shorthand | 3 | *"השימוש ב-CW במקום Console.WriteLine … לכן אני מוריד מעט מהניקוד"* |
| **R-α** — contradicted by the model solution | 3 | *"durationInMinutes אינו תואם את הדרישה לשם 'minutes'"* — **the teacher's own model solution declares `durationInMinutes`** |
| **Explicit tariff violated** | 3 | q2.ב.c4.s3, rubric says «לא להוריד, לכתוב הערה» |
| Other interpretive | 3 | loop bounds the owner ruled equivalent; for-vs-while; scope bleed |

**82% (28/34) is the grader charging surface form that PL-1/PL-2/PL-10/R-α
explicitly treat as ink.** Not one sampled case was an evidence failure, a GT
problem, or a transcription artifact.

## 6. E5 — pairwise ordering agreement (§13.6, post-hoc, zero spend)

**Aggregation choice:** per terminal, the **median AI award across k=5** (one
value per fixture-terminal), compared over all C(5,2)=10 fixture pairs ×
38 terminals = **380 comparisons**. Median chosen over per-trial pairing so
run-to-run noise does not masquerade as ordering error.

| Outcome | n | share |
|---|---|---|
| Both tie (GT equal, AI equal) | 129 | 33.9% |
| **GT tie → AI splits** (grader invents a difference) | **100** | **26.3%** |
| GT differs → AI ties (grader flattens) | 9 | 2.4% |
| Ordered both, **agree** | 136 | 35.8% |
| Ordered both, **inverted** | 6 | 1.6% |

**Directional agreement where both order: 136/142 = 95.8%.**

**Reading:** the shaving is **largely order-preserving** — only 1.6% of
orderings invert, and flattening is rare (2.4%). Student *ranking* is
substantially intact. **But 26.3% of comparisons are the grader manufacturing
a distinction between two students the teacher graded identically.** That is
not a level error; it is precisely the cross-student inconsistency §13.1 calls
appeal (ערר) exposure — and it is invisible to MAE, which sees only levels.
E5 earns its place: it measures a product risk no Tier-2 metric can see.

## 7. §R.4 deliverable — one mechanism, one change, one metric

**Named mechanism: `cosmetic-slip tariffing`.** The grader applies a
consistent, defensible-in-the-abstract standard the teacher does not hold: it
charges points for surface-form deviation — identifier case, spelling, naming,
shorthand IO, malformed-but-referent-unambiguous member access, bracket style —
where the teacher's ratified rulings (PL-1, PL-2, PL-10, R-α) treat these as
ink. This is `interpretive_divergence`, the highest-value bucket, and it
accounts for 82% of sampled shaving and ~69% of all harshness.

**The single change that would test it (ONE variable):** add one instruction to
`SYSTEM_PROMPT` — *do not deduct for surface-form deviations where the
student's intent is unambiguous (identifier case, spelling, shorthand IO,
malformed-but-referent-clear member access, bracket style); deduct only for
semantic or behavioural defects.* Nothing else changes: same model, same
fixtures, same k, `prior_context` OFF.

**The one metric that would move: `mean signed terminal Δ`** (currently
**−0.3089**).

**Registered as E7 in PREDICTIONS.md — not run.**

---

## What did not change

The baseline's accepted findings stand: 25/25 valid · Tier-1 24/25 · parse-rate
0 (no R6 escalation) · cost under ceiling · U2/G-21 smoke passed · every fixture
under-scored · 0/25 shippable · 80% boundary-flip rate · worst test din ·
P2 falsified in sign by its own falsifier. **What changed is the mechanism
story** — and per §R.0, that is exactly the thing aggregates could not deliver.

**Surfaced for owner ruling, no action taken:** (1) the `T1-FABRICATED`
stitched-quote misclassification (R-4); (2) `q2.ב.c4.s3` — the grader deducting
against an explicit «לא להוריד» tariff; (3) `q2.א.c1` — the un-itemized
10-point monolith as the single most expensive terminal. **No GT amendment is
proposed; no `gt_questionable` finding arose in the sample.**
