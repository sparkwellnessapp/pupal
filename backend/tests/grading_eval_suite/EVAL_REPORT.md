# EVAL_REPORT — grader-v5 closed loop (H-2 halt, 2026-08-29)

**Mission:** `MISSION_grader_v5_closed_loop.md` · **Halt:** H-2 (trial ceiling
reached with the §3 space exhausted; both confirmation candidates killed at
k=5) · **Spend:** $32.53 of $60 · **Fences:** GT untouched · thresholds
untouched · plan v2 as ratified · batteries green · every run kills-first with
EVAL_ANALYSIS.md in its results dir.

---

## 1. Executive verdict

**No configuration in the ratified search space is adoptable, and the mission
knows exactly why — that is the deliverable.** Eleven Stage-1 screens, one
Stage-2 variant, and two k=5 confirmations produced zero all-green boards, two
k=3 "kill-clean" boards that both died at the authoritative tier (nano by K4
spread 5.0→11.5; terra-medium by K1 77/80 — three din wrong-target cells that
three draws never sampled), and a residual-defect map so concentrated that the
paths to H-1 are enumerable on one hand — every one owner-gated:

1. **Plan v3, two cells** — the teacher's PL-1 wrong-identifier tariff on
   `q1.א.c1` (rule 5 currently *instructs* every capable model to vote met
   there) and an access-site-precise tariff text on `q2.ב.c3.s0`.
   Counterfactual on measured verdicts: **opus5 K2 3.40%→1.36%, sonnet5
   3.40%→2.04%, gemini-pro 4.08%→2.04% — all under the 2.4% bar.**
2. **The wrong-target verdict clause** (rule-6 hardening: *work aimed at a
   different requirement is not_met; partial credit never applies to it*) —
   kills the ONLY K1 class observed anywhere (hedged ◐ on wrong-target
   machinery: haiku, luna, gpt-5.5 ×5, terra-high ×3, terra-medium@k=5 ×3 —
   100% din-concentrated, §7.4's named hardest test).
3. **A GA-7 ruling** — at frontier tiers the ceiling is an OUTPUT-token
   constraint (sonnet5's basis_he output alone bills $0.102/test; caching
   cannot touch it). Either a terser-basis prompt ruling, or the ceiling
   ruling §7.2 anticipated.

**What a teacher gets from the best board measured (opus5, killed on 2
plan-side cells + cost):** moran graded to the teacher's exact total (Δmed
0.0), MAE 0.09/terminal, zero invented credit in 720 GT-ZERO cells across the
whole mission's frontier cohort, every awarded point tied to a verbatim span
of the student's own ink, spread 1.5 points across five re-grades. The
architecture holds; the remaining distance is two plan cells, one clause, and
a cost ruling.

## 2. The frontier map (all runs; k=3 = SCREENING, k=5 = authoritative)

| config | arch | K1 | K2 | K4 | GA-2 | GA-3 | GA-4 | GA-5 | GA-6 | $/test | fate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| haiku45 | v5 | **45/48** | 2.04% | 4.5 | .663 | 0 | .80 | 4.5 | 11/25 | .085⁺ | K1 dead |
| flashlite | v5 | ✓ | **23.8%** | 6.25 | .844 | .07 | .20 | 6.25 | 5/14 | **.031** | K2 dead (systematic) |
| nano k=3 | v5 | ✓ | 0.68% | 5.0 | .723 | 0 | .80 | 5.0 | 10/19 | **.025** | kill-clean → conf |
| **nano k=5** | v5 | ✓ | **0.00%** | **11.5** | .717 | 0 | .80 | 11.5 | 12/19 | **.024** | **K4 at confirmation** |
| luna | v5 | **47/48** | 0.00% | 5.5 | .809 | .13 | .60 | 5.5 | 5/19 | **.015** | K1 dead |
| gpt4o (control) | v5 | ✓ | **18.4%** | 6.0 | .761 | 0 | .20 | 6.0 | 8/19 | .079 | K2 dead |
| sonnet5 | v5 | ✓ | **3.40%** | 3.5 | .840 | .07 | .20 | 3.5 | 6/15 | .171⁺ | K2 dead |
| gemini-3.1-pro | v5 | ✓ | **4.08%** | 2.75 | **.890✓** | .40 | .20 | **2.75✓** | 1/13 | .362⁺ | K2 dead |
| gpt-5.5@med | v5 | **43/48** | 0.00% | 3.5 | .863✓ | .27 | .20 | 3.5 | 4/14 | .389⁺ | K1 dead |
| terra@med k=3 | v5 | ✓ | 0.68% | 6.25 | .763 | 0 | .67 | 6.25 | 8/18 | .115⁺ | kill-clean → conf |
| **terra@med k=5** | v5 | **77/80** | 0.41% | 8.25 | .775 | 0 | .52 | 8.25 | 6/20 | .112⁺ | **K1 at confirmation** |
| terra@high | v5 | **45/48** | 2.72% | **9.75** | .754 | 0 | .73 | 9.75 | 8/17 | .168⁺ | TRIPLE kill |
| opus5 | v5 | ✓ | **3.40%** | **1.5** | **.905✓** | **.53✓** | .20 | **1.5✓** | 3/11 | .407⁺ | K2 dead; best board |
| nano-SC3 | v5 | ✓ | 0.00% | 6.25 | .737 | 0 | .79 | 6.25 | 11.5/19 | .076 | SC-3 falsified |
| nano×v3 (attrib) | v3 | ✓ | 4.08% | 7.75 | .581 | 0 | 1.0 | 7.75 | — | .010 | attribution only |

⁺ = OVER-CEILING, ran for information. OpenAI $/test already at ~81% measured
auto-cache; Anthropic measured at 0% cache (explicit `cache_control` unbuilt —
analytically sonnet5 lands ≈$0.121 cached, still output-bound over the $0.08
hard ceiling; opus ≈$0.28).

**The intelligence–cost frontier at $0.08 (the §7.2 statement):** inside the
ceiling you can buy flashlite's accuracy (GA-2 .844) with a 10× K2 violation,
or nano's kill-cleanliness with GA-2 .72 and a K4 blowup at k=5. The accuracy
winner (opus, .905) costs 5× the ceiling and its output tokens alone exceed
it. **The gates as written are jointly unreachable at ≤$0.08 in this search
space; the cheapest frontier-quality seat is sonnet5 at ≈$0.12 cached.**

## 3. Predictions scored

- **P1** (owner, pre-baseline: *terra@high dominates the accuracy×cost×latency
  frontier*): **FALSIFIED on every axis.** Terra@high posted the screen's
  worst kill record (triple, incl. the only spread above the E8 record);
  accuracy went to opus (.905 vs .754), stability to opus (1.5 vs 9.75), cost
  to luna/flashlite. Extraction excellence did not transfer to teacher-like
  partial-credit judgment.
- **P-S5** (owner: *sonnet5 top-2 on the GA-2/GA-5-weighted screen*):
  **FALSIFIED** — sonnet5 is 5th on GA-2 (.840) and 3rd on GA-5 (3.5); the
  top-2 are opus5 and gemini-3.1-pro. (Sonnet5 remains the cheapest
  frontier-quality seat, which is a different claim.)
- **P-ARCH** (*v5-on-gpt-4o beats grader-v3 on K2 and spread*): **HALF EACH
  WAY.** Spread: CONFIRMED (6.0 vs v3's 8.25–14.0; every v5 config beat every
  v3 run on spread at k=3). K2: FALSIFIED for gpt-4o (2.9%→18.4% — discrete
  verdicts EXPOSE the loose met-threshold that points-emission blurred). On
  nano the full sweep favors v5 on every gate (§5). Refined law: **the
  architecture guarantees the code-enforceable properties (zero-false-credit
  on capable models, variance, citations, cost truth); verdict quality it can
  only reveal, and it scales with capability.**
- All 14 HYPOTHESIZE lines dispositioned in RUNLOG (S1-1…S1-11, S2-1,
  CONF-1…3); the SC-3 hypothesis explicitly falsified (median-of-3 harsh
  draws is harsher: GA-5 5.0→6.25, annihilation deepened).

## 4. The confirmations, in depth (there is no confirmed champion)

**nano k=5 — K4 fires (11.5).** Kills 1–2 hold at 25 trials (K1 80/80, K2
0/245); GA-2 holds .717; $0.024/test. The spread lives in yonatan (11.5) and
din (7.5): nano's verdict flips are per-terminal small but correlated
per-paper. The SCREENING stamp did its job — three draws showed 5.0.

**terra-medium k=5 — K1 fires (77/80).** The three cells are din's
`q2.ב.c1` / `q2.ב.c4.s2` — the OpenAI-family wrong-target hedge, appearing
only in draws r3/r4. A 0.68%-K2, kill-clean-looking screen concealed a
~2%-per-draw K1 leak class. **Both confirmation kills generalize: k=3
under-samples exactly the two tail properties the kills exist to catch.**

**The din story (residual failure mode #1).** Every frontier model's largest
per-fixture error is din — the wrong-target paper: gemini-pro Δmed 17.5,
sonnet5 13.5, opus 9.75 (harsh side: refusing wrong-target partial credit the
teacher granted under H1-era rulings the rubric never wrote down); the OpenAI
family + haiku err the OTHER way (hedged ◐ credit on the same wrong-target
machinery — the K1 class). One paper, two failure directions, all vendors.
The plan cannot express a policy the rubric never stated: **wrong-target
credit policy is the single biggest unencoded teacher ruling** and the
strongest argument for fixture expansion (n≥10, ≥2 exams) before any gate
ratification.

**§R buckets across the mission** (hand-read cells, per the PLAYBOOK):
`interpretive_divergence` dominates (the met-threshold families);
`rubric_underdetermined` next (din wrong-target policy; `q2.ב.c4.s3`'s Q-1
class, owner-ruled at H-4); `evidence_miss` near-zero at frontier tier;
`evidence_fabricated` ZERO on every capable model (the pricer's gating + the
refusal tripwires held: 720 GT-ZERO cells, zero invented credit);
`right_award_wrong_reason` not surveyed at k=5 (registered gap).

## 5. Attribution (architecture vs model)

- **nano, v5 vs v3 (same model, same fixtures, k=3):** GA-2 .581→.723 · K2
  4.08%→0.68% · spread 7.75→5.0 · GA-4 1.0→0.8 — **v5 better on every gate.**
- **gpt-4o, v5 vs its own E-series v3 record:** spread 6.0 vs 8.25–14.0 ✓;
  GA-2 .740→.761 ≈; K2 2.9%→18.4% ✗.
- Net: the architecture is worth most where the model is weakest, and its
  code-side guarantees (GA-1 via evidence-gated pricing, citation integrity,
  charge-once, cost truth) held on every capable entrant with zero
  fabricated-evidence events.

## 6. Production recommendation

**Adopt nothing today.** The recommended sequence to H-1, every step an owner
decision:

1. **Ratify plan v3** (PL-1 tariff on `q1.א.c1`; access-site text on
   `q2.ב.c3.s0`) — the expressibility guard re-runs automatically; the
   measured counterfactual puts opus/sonnet/gemini-pro under the K2 bar.
2. **Ratify the wrong-target clause** (rule-6 hardening) — targets the only
   K1 class observed; verifiable cheaply on the killed-family exemplars (din
   scopes, one k=3 + score_only).
3. **Rule on GA-7** — three honest options: (a) a terser-basis prompt ruling
   (cuts the output term for every entrant), (b) accept ≈$0.12 cached sonnet5
   as the ceiling's real frontier price, (c) hold $0.08 and accept that H-1
   requires (a). R2 note: an Anthropic champion makes Anthropic both grader
   and (future) judge vendor — the judge-independence concern transfers.
4. **Then one k=3 across {opus5, sonnet5, gemini-3.1-pro} under the amended
   plan/clause + k=5 on the winner.** Estimated $12–18, inside the remaining
   envelope ($27.47).
5. **Standing next investment regardless:** fixture expansion (n≥10, ≥2
   exams) — every rate in this report is PROVISIONAL on one exam, and the din
   finding shows exactly which teacher rulings the corpus is missing.
6. Production stays pinned to grader-v3/gpt-4o meanwhile (zero behavior
   change shipped; the v5 path lives dark behind the config seam).

## 7. Appendix

- Per-trial analyses: `results/<run>/EVAL_ANALYSIS.md` ×13 + `gates.md` (the
  kills-first tool output) per evaluated run.
- Predictions: `PREDICTIONS.md` (P1, P-S5, P-ARCH, S2-1, CONF outcomes).
- Spend: `COST_TRUTH_LEDGER.md` (authoritative; mission $32.53 = tool total
  $38.09 − $5.57 pre-mission E-series; the RUNLOG running tally drifted $0.17
  and is superseded). Dashboard reconciliation per `COST_TRUTH.md` awaits
  provider-console access (owner-side step).
- Decisions & incidents ledger: `RUNLOG.md` (mission-start → H-4 → S1-1…
  CONF-3): the grader-v3 byte-restore proof, the DL-2 splitter fix, the
  provenance stamp fix, the Claude-5 temperature 400, the §1.7 reversal
  execution, the sonnet-4.6 cache-card correction.
