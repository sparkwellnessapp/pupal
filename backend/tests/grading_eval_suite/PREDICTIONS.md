# PREDICTIONS — pre-registered, written BEFORE runs (no post-hoc laundering)

## P1 — Owner model prior [mission SS1, registered at seed]

> "gpt-5.6-terra @ reasoning=high will dominate the grading accuracy x cost x
> latency frontier" — Noam, 2026-08-24, PRE-BASELINE.

Falsified/confirmed only by a future sweep under registry discipline (D6 seam
lands first; one variable per run; kill criterion pre-registered here before
that sweep spends a cent).

## P2 — Pre-baseline quantitative prediction [PLACEHOLDER — Phase C gate]

To be authored by owner + reviewer IMMEDIATELY BEFORE the Phase-C baseline run
(k=5 x 5 fixtures, deployed pin gpt-4o + grader-v2 — R7's
"grader-v1" reference AMENDED by the owner's 2026-08-25 evidence-first decode
lever (canonical version name "grader-v2" per the PR-G1 carryover), applied pre-baseline so the first measurement IS the new pin; there is
no grader-v1 baseline and none is owed). Must state, before
any result is seen: predicted terminal_within_precision_rate band, predicted
shippable_grade_rate band, predicted worst fixture, and the surprise threshold.
The baseline report then quotes this section verbatim with outcomes.

## P3 — Judge promotion bar [PLACEHOLDER — Phase D gate]

After the judge bootstrap (owner labels ~20 disagreements), the judge-owner
agreement stat lands here together with the pre-registered promotion bar
(n>=50 Tier-A fixtures AND agreement >= bar) [R2]. Until then the judge is
diagnostic-only, never a gate, never the scorer-of-record.

## Tier-2 threshold candidates [PLACEHOLDER — only AFTER the baseline distribution]

Per the PLAYBOOK STOP list: no threshold gates Tier-2/3 until candidates are
pre-registered HERE from the measured baseline distribution.

## Dispositions (2026-08-25, append-only — predictions registered in the owner's design-partner session)

- **P4 — WITHDRAWN-UNMEASURABLE**
- **E1 — OVERTAKEN-BY-OWNER-ACTION**
- **E3 — RESOLVED-BY-ARGUMENT**

## E4 (registered 2026-08-25, pre-baseline)

"E4 (registered 2026-08-25, pre-baseline): enabling GRADER_PRIOR_CONTEXT_ENABLED
improves terminal agreement specifically on sub-questions whose grading
references prior parts, with no regression on non-referencing terminals and
bounded input-token growth (read from existing per-scope token capture).
Single variable: the flag."

---

## P2 — pre-baseline prediction (registered 2026-08-26, before any grading run)

**Authored by:** reviewer (claude-fable-5, design-partner session). **Owner concurrence:** Noam reviewed and added nothing.
**Subject:** k=5 × 5 fixtures, deployed pin (gpt-4o + grader-v2), prior_context OFF, model solutions rendered.

**Quantitative.** shippable_grade_rate (|Δ_total| ≤ 1.0) = 0/25 trials. terminal_within_precision_rate = 0.55–0.70. Median per-test |Δ_total| = 8–15 points. Parse-failure rate = 0. Cost ≈ $0.03/test, under the $0.10 ceiling. Repeat instability: >30% of terminals show non-zero award spread across k=5.

**Directional — the mechanism under test.** Systematic leniency: positive mean signed Δ, because nearly every deduction in this rubric requires noticing an absence (missing zero-guard, missing null check, missing countHobbies++, missing getter), and absence-detection is materially harder for an LLM than presence-recognition. Counterposed: over-deduction on visible syntax that PL-10 forgives (parens-for-brackets, case mismatch, missing semicolons, truncated getter names). These partially cancel at the test level, so compensating_error fires on ≥2 fixtures.

**Named terminal predictions (falsifiable, specific).** omer/q1.ב.c4 — the inverted != null guard missed entirely, full credit. yonatan/q1.ג.c7 — the copy-pasted wrong variables missed, full credit. moran/q2.ב.c1 — [100] vs [101] missed. q1.ג.c6/q1.ג.c7 zero-guards and q2.ב.c3.s1 null check — over-credited on most fixtures.

**Worst test:** din — his wrong-target Q2.ב is structurally plausible (loop, min-search, return), and I predict the grader over-credits him by +15 to +25 points, failing to register that the scope solves a different problem. **Best agreement:** moran, whose code tracks the model solution most closely.

**Falsifiers of this model of the grader:** shippable_grade_rate > 0.4, OR terminal MAE < 0.3, OR negative mean signed Δ (systematic harshness rather than leniency).

### P2 — OUTCOME (scored 2026-08-26 against run 20260826-174645_gpt-4o)

**P2's own falsifier FIRED: mean signed terminal Δ = −0.3089 (negative ⇒ systematic harshness, not leniency).** The leniency model is falsified in sign.

CONFIRMED: shippable 0/25 · within_precision 0.6589 (band 0.55–0.70) · pooled median |Δ_total| 10.00 (band 8–15; only 2/5 fixture medians in band) · parse-failure 0 · repeat instability 37.4% (>30%) · omer/q1.ב.c4 full credit exactly as named · moran/q2.ב.c1 off-by-one missed · worst test = din.
FALSIFIED: systematic leniency (sign inverted) · compensating_error ≥2 fixtures (actual 0 — errors are one-directional, nothing cancels) · yonatan/q1.ג.c7 · the q1.ג.c6/c7/q2.ב.c3.s1 over-credit class · din over-credited +15..+25 (actual **−22.5**, magnitude in band, sign inverted) · best agreement moran (actual omer).
SPLIT: cost under ceiling CONFIRMED ($0.0698 < $0.10), the $0.03/test estimate FALSIFIED (2.3× high).
INDETERMINATE: the counterposed syntax-over-deduction mechanism (observed harshness signature is wrong-target all-or-nothing zeroing, not syntax nitpicking; no per-terminal attribution without reading 950 reasonings).

Full analysis: `C2_BASELINE_REPORT.md`.

## E7 — cosmetic-slip tariffing (registered 2026-08-27, NOT RUN)

**Authored by:** reviewer, per PLAYBOOK §R.4, from the C2 baseline qualitative read.
**Mechanism claimed:** the grader charges points for surface-form deviation (identifier case, spelling, naming, shorthand IO, malformed-but-referent-unambiguous member access, bracket style) where the teacher's ratified rulings PL-1/PL-2/PL-10/R-α treat these as ink. Evidence: 82% (28/34) of sampled GT-FULL→AI-PARTIAL shaving cases; shaving = 201.75 pts = 68.7% of net harshness.

**Single variable:** add one instruction to `SYSTEM_PROMPT` — *do not deduct for surface-form deviations where the student's intent is unambiguous; deduct only for semantic or behavioural defects.* Same model (gpt-4o), same fixtures, same k=5, `prior_context` OFF.

**The metric that moves:** `mean signed terminal Δ`, currently **−0.3089**.

**Prediction:** mean signed terminal Δ moves toward 0 by **≥0.15** (≥50% of the gap), driven by the GT-FULL→AI-PARTIAL cell falling from **236** to **<120**, with **no regression** on the GT-ZERO row (currently **80/80 = 100% correct zeros**, which must hold) and **no** increase in the GT-PARTIAL→AI-FULL cell beyond +10 (currently 6).

**Falsifiers:** mean signed Δ moves <0.05; OR any false credit appears on GT-ZERO terminals (row ≠ 80/80); OR `terminal_within_precision_rate` falls below the 0.6589 baseline.

**Not run.** Requires owner authorization: it is a prompt change to `app/` (fenced, step-3 territory) plus ~$1.75 of spend.

### E7 — RESTATED 2026-08-27 (owner ruling: authorized, gated on clause ratification)

The original E7 sizing was against the full 201.75 shaving total and was too generous. Stratified bucketing (C2 addendum item 1) shows **42.50 pts (21.1%) of shaving is outside E7's reach**: `q2.ב.c4.s3` rubric self-contradiction 18.50 («סה"כ 2 נקודות» vs `points_possible=3` → `rubric_underdetermined`), `q2.ב.c4.s3` din wrong-target zeroing 15.00, din wrong-target zeroing elsewhere in q2.ב 9.00. **Addressable: 159.25 pts (78.9%).**

**Restated prediction:** mean signed terminal Δ moves from **−0.3089** toward 0 by **≥0.12** (≈75% of the addressable share, allowing partial compliance), with GT-FULL→AI-PARTIAL falling from **236** toward **<130**. The 42.50 out-of-reach points REMAIN; if they vanish, read it as over-compliance, not success.

**Pre-registered kill criteria (any one kills the change):**
- **K1** — GT-ZERO → AI-ZERO must hold at **80/80**. Any false credit kills it regardless of Δ improvement.
- **K2** — GT-PARTIAL → AI-FULL must not exceed the current **2.4%** (6/245).
- **K3** — `terminal_within_precision_rate` must **improve** on 0.6589. A change that moves mean signed Δ without improving within-precision is adding noise, not accuracy.

**Run parameters:** `grader-v3` (version bumped in the same state), k=5, same five fixtures, `prior_context` OFF, ~$1.75. One variable. §R applies in full to the analysis.

**Gated:** clause text in `E7_CLAUSE_PROPOSAL.md`; nothing runs until the owner ratifies it.

## E8 — rubric-tariff exclusivity (registered 2026-08-27, **NOT RUN — queued behind E7**)

> "The rubric's stated tariffs are the only source of deductions — do not invent tariffs the rubric does not name."

Arguably the cleanest single formulation of the whole baseline finding.

**WHY IT IS EXCLUDED FROM E7 (chosen, not overlooked):** E8 would ALSO move `q2.ב.c4.s3` — whose own text says «לא להוריד, לכתוב הערה» and whose 33.50 points E7 deliberately cannot reach. That destroys one-variable attribution and invalidates the "42.50 points must remain" check that makes E7 falsifiable. Queued strictly behind E7.

**Not run.** Requires its own owner authorization, its own single-variable run, and its own kill criteria.

### E7 — OUTCOME (scored 2026-08-27 against run 20260827-191547_gpt-4o)

**Kill criteria: ALL PASS.** K1 GT-ZERO→AI-ZERO **80/80** (zero false credit) · K2 GT-PARTIAL→AI-FULL **2.0%** (baseline 2.4%) · K3 within-precision **0.7232** (baseline 0.6589).

**FALSIFIED** — mean signed terminal Δ improved only **0.0307** (−0.3089 → −0.2782) against the predicted **≥0.12**.
**CONFIRMED** — GT-FULL→AI-PARTIAL fell **236 → 111** (predicted <130).
**Out-of-reach class REMAINED exactly** (63.00 → 63.00): no over-compliance.

**Why the split:** the clause fixed 125 shaves but created **24 new zeros** (GT-PARTIAL→AI-ZERO 54→72; GT-FULL→AI-ZERO 22→28), worth −24.50 against +53.75 of fixes. Mechanism read from the reasoning: the clause told the model *what* is conceptual without telling it *how much* a conceptual defect costs, so over-shaving partly became **over-zeroing** — the model now invokes «פגם קונספטואלי» explicitly and charges to zero where the teacher gave partial or full credit.

Everything else improved: exact-rate 0.6084→0.7137 · MAE 0.34→0.3118 · **shippable 0.0→0.16 (first ever)** · boundary-flip 0.80→0.52 · ECE 0.2438→0.2156 · instability 37.4%→30.0% · E5 inversions 1.6%→0.5%, GT-tie→AI-split 26.3%→20.5%, directional agreement 95.8%→98.6%. 4 of 5 fixtures improved; din regressed −1.5. New: `compensating_error` 0→4.

Full analysis with §R reads: `E7_REPORT.md`. **This run is the evidence for E8** (tariff exclusivity) being the natural successor: the missing half is *how much*.

## E8 — deduction-magnitude authority (registered 2026-08-27, grader-v4)

> **E8 (registered 2026-08-27):** supplying deduction magnitude authority reverses E7's zero-inflation and cuts variance. Predicted: GT-PARTIAL→AI-ZERO falls from 72 toward **≤55**; GT-FULL→AI-ZERO from 28 toward **≤22**; mean signed terminal Δ improves from −0.2782 by **≥0.10**; `terminal_within_precision_rate` improves on **0.7232**; max per-fixture `ai_total_spread` falls below **14.00**. `q2.ב.c4.s3` is expected to move for the first time (rule 4a directly addresses it) — it is no longer out of reach.

**Clause wording note (owner ruling):** rule 4 is *not* "the rubric is the only source of deductions" — that would be false, since the rubric is silent on many cases and would leave no rule there at all. It is an **order of authority**: named tariff → criterion itemisation → share of required work present.

**Kill criteria — K1–K3 unchanged, K4 added:**
- **K1** GT-ZERO→AI-ZERO must hold **80/80**. Any false credit kills, regardless of Δ gain.
- **K2** GT-PARTIAL→AI-FULL must not exceed **2.0%** (E7's value).
- **K3** `terminal_within_precision_rate` must improve on **0.7232**.
- **K4 (new)** max per-fixture `ai_total_spread` must not exceed **14.00**, and the corpus max should fall. Rule 4 removes discretion over magnitudes, so it should reduce variance; if it doesn't, that is diagnostic of **prompt-surface exhaustion**.

**Run:** grader-v4, k=5, same five fixtures, `prior_context` OFF, ~$1.75, one variable.
