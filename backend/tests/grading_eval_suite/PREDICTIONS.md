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
