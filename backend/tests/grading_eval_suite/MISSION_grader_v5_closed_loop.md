# MISSION — grader-v5 CLOSED LOOP: iterate to the gates, then present

**Owner:** Noam · **Status:** RATIFIED · **Supersedes:** `PR_grader_v5_feature_sprint.md` (this document is complete on its own; do not merge instructions from the superseded file).
**Agent:** you are running on a frontier model and are trusted with judgment *inside* this mission's fences. Sequencing latitude is yours (§4 search policy is a default, not a cage — deviations allowed with a one-line RUNLOG rationale). The fences themselves (§1) are not yours to move.

---

## §0 — Mission statement, success, and halting

**Objective:** produce a grading agent configuration that turns every GA gate (§2) green on a **k=5 confirmation run**, then present the working implementation plus a final **EVAL_REPORT.md** (§7). We optimize for reaching a working feature fast — not for per-change attribution (owner ruling; Feature-First Mode).

**You halt and summon the owner when — and only when — one of these fires:**
- **H-1 SUCCESS:** all GA gates green on a k=5 confirmation → present per §7.
- **H-2 EXHAUSTION:** search space (§3) exhausted or **12 trials** run or **envelope $60** spent → present the best k=5-confirmed candidate per §7, with a plain gap analysis of every red gate.
- **H-3 AMBIGUITY:** a kill fires whose interpretation is genuinely unclear, or a fence conflict arises, or anything would touch GT.
- **H-4 PLAN REVIEW:** the V5-B checkpoint (§5) — the one scheduled mid-mission stop.

Nothing else stops the loop. No per-trial approval. EVAL_ANALYSIS.md (§6) is the owner's window into every cycle.

## §1 — Non-negotiables (anti-self-deception machinery; never traded for speed)

1. **Kills evaluated first, every trial, before any headline number:** K1 = GA-1 (any false credit kills the config) · K2 GT-PARTIAL→AI-FULL vs the **C2 baseline 2.4%** · K4 max per-fixture `ai_total_spread` ≤ 8.25.
2. **GT files immutable.** A `gt_questionable` finding is surfaced in the trial's analysis, never applied.
3. **Full provenance every run:** `suite_hash` · `sut_hash` · `model_key` + params (`reasoning_effort` etc.) · `prompt_version` · `plan_version` · k · config · cached/uncached token counts.
4. **Gates decide adoption.** k=3 results are stamped SCREENING and never justify adoption. Adoption = k=5 confirmation.
5. **No threshold or gate moves.** GA numbers are owner-editable only.
6. **Spend fence:** $60 envelope, hard. Per-trial spend logged to a running ledger in RUNLOG.
7. **Google quota isolation:** before the first Gemini call, verify the eval path uses a key/project **isolated from the production transcription quota**. If isolation cannot be positively established, skip all Google entrants and report the skip. The launch resource is never put at risk for an eval.
8. §R qualitative reads still gate each trial's analysis; EVAL_ANALYSIS.md is their human-facing distillation.

## §2 — Gates (the definition of "working")

**Cost ruling (owner, final): intelligence and reliability outrank cost.** The ceiling is the constraint; within it, select on GA-2/GA-5, never on cheapness. Adoption ceiling **$0.08/test hard, $0.05 target** (caching counted at batch-realistic hit rates). OVER-CEILING trials run for information and are stamped as such.

| Gate | Definition | Baseline (grader-v3) | Target |
|---|---|---|---|
| **GA-1** | GT-ZERO→AI-ZERO (zero false credit) | 100% | **100%** — inviolable |
| **GA-2** | `terminal_within_precision_rate` | 0.7232 | **≥ 0.85** |
| **GA-3** | strict shippable: \|total Δ\| ≤ 1.0 AND no `compensating_error` | 0.00 | **≥ 0.50** of trials |
| **GA-4** | `grade_boundary_flip_rate` | 0.52 | **≤ 0.10** |
| **GA-5** | max per-fixture `ai_total_spread` (reliability) | 8.25 | **≤ 3.0** |
| **GA-6** | `edit_burden` median / max per test | ~6 / ~20 | **≤ 4 / ≤ 8** |
| **GA-7** | cost per test (adoption) | $0.0698 | **≤ $0.08 hard / $0.05 target** |

All PROVISIONAL (n=5, one exam) — stamped on every artifact. Latency p95 ≤ 60 s/test, watched not gating.

## §3 — Search space

**Architecture (fixed for this mission):** grader-v5 Plan/Verify/Price (§5). The model emits **verdicts + evidence only — never a number**; a deterministic pricer converts verdicts to points via the plan.

**Axis A — model roster** (registry price cards, verified, before any call; reasoning-token billing checked; exact model strings come from the cards, never from memory):

| Provider | Entrants | Role / rationale |
|---|---|---|
| OpenAI | `gpt-5.6-terra @ high` · `@ medium` | Owner prior P1 (frontier bet); medium is the cost-viable variant — distinct configs via the params seam |
| OpenAI | `gpt-5.5 @ medium` | House-known (extraction uses it); mid-price reasoning |
| OpenAI | current mini/nano tier (per cards; incl. `gpt-5.4-nano`) | Cheap tier; nano's known nondeterminism at temp 0 makes it a deliberate GA-5 probe |
| Anthropic | `claude-sonnet-5` | Owner hypothesis: Hebrew reasoning quality, instruction hierarchy, verbatim extraction |
| Anthropic | `claude-haiku-4.5` | **Prime cheap-tier candidate** — checklist verification is exactly the task class small Claude models are strong at |
| Anthropic | `claude-opus-5` | Frontier intelligence probe; expected OVER-CEILING; screened anyway per the owner's priority ruling |
| Google | `gemini-3.1-pro` · current Flash tier (per cards) | Pro: house-known from transcription; Flash: potentially the cheapest viable entrant (~$0.01–0.03/test) — **all conditional on §1.7 isolation** |
| xAI | Grok tier | **Excluded by default** (owner skepticism). One-line owner flip to include. |

**Axis B — inference configs (uniquely enabled by discrete verdicts):**
- **SC-3 self-consistency:** 3 independent verifier calls per scope, per-check verdict = **median on the ordinal scale** (`met > partially_met > not_met`), evidence from the median-agreeing call. Cheap-tier models only (3× cheap ≤ ceiling). Direct GA-5 play: voting collapses stochastic verdict flips.
- **Cascade (reserve — Stage 3 only):** cheap model verifies everything; checks with low confidence or SC-3 splits escalate to a frontier model. Classic cost/intelligence router; built only if no single config clears the gates.
- Prompt caching on the stable prefix (rubric/question/solution), measured at batch-realistic hit rates — this is Sonnet-5's and Opus-5's realistic path under the ceiling; reasoning tokens are output-side and uncacheable, which is Terra@high's structural handicap.

**Search-order policy (default; deviate with rationale):**
**Stage 1** — k=3 screens, cheap→expensive within each provider (fast signal first): Haiku 4.5 → Flash tier → mini/nano → gpt-4o control → Sonnet 5 → gemini-3.1-pro → gpt-5.5@medium → Terra@medium → Terra@high → Opus 5.
**Stage 2** — top-2 by gate-distance (weighted: GA-2, GA-5 first per the priority ruling): targeted variants — SC-3 on the best cheap model; caching measurement on the best Anthropic/OpenAI entrant; effort sweep refinement if a Terra variant leads.
**Stage 3** — cascade, only if Stages 1–2 leave gates red.
**Confirmation** — k=5 on the champion; plus one k=3 of the champion model × grader-v3 (best-effort architecture-vs-model attribution; not gating).

## §4 — The loop (run this verbatim)

```
while not (H-1 | H-2 | H-3):
    1. HYPOTHESIZE  — one line in RUNLOG: config + expected gate movement + why
    2. RUN          — k=3 screen (k=5 only for confirmation), kills evaluated FIRST
    3. ANALYZE      — §R reads → EVAL_ANALYSIS.md into the trial's results dir
    4. DECIDE       — next config per §3 policy (or a reasoned deviation)
    5. LEDGER       — spend, cumulative, remaining envelope
```
A config that fires K1 is dead permanently. A config that fires K2/K4 may return only in a variant that plausibly addresses the firing, stated in the HYPOTHESIZE line.

## §5 — Build phases (before the loop starts)

**V5-A — Instrument & schemas (zero spend).** `GradingPlan` / `Check` / `CheckVerdict` schemas per the architecture: checks carry `{check_id, description_he, points, kind: required|tariff|note_only, tariff_amount, equivalence_note, charge_group}`; verdicts carry `{check_id, verdict: met|partially_met|not_met, evidence_quote (verbatim span, "" only for not_met), basis_he (for not_met: what was searched), confidence}`. Deterministic **plan validator** (per-terminal required-points sum exactly to points_possible; rubric tariffs verbatim; note_only carries no points; grid; totality) and **pricer** (met→100% · partially_met→50% default, plan-overridable · not_met→0 · tariffs applied once per charge_group · grid-snap · bounds · note_only→annotation), red-first with injected-error tests (double-charged group; over-sum plan; note_only carrying points; fabricated-quote-on-met caught by per-span validation). **Multi-provider model seam:** `GraderAgent(model_key, params)` resolved through a provider-agnostic factory (OpenAI/Anthropic/Google adapters; structured output per provider's native mechanism), defaulting to current behaviour with a **byte-identity pin** on the grader-v3/gpt-4o path. Provenance carries model params + `plan_version`. Verifier prompt (`grader-v5`) carries forward only the two *proven* clauses — form-vs-behaviour as verdict guidance, example-solution-as-authority; magnitude language is deleted (it's code now).

**V5-B — Plan for hobby_tvshow → [STOP H-4] owner review (~30 min).** Compile, validate, render human-readably (per terminal: checks, points, tariffs, equivalence notes). The owner hand-graded these 38 criteria twice; he will spot a wrong decomposition on sight. Ratification pins `plan_version`. This is the single scheduled human gate before the loop.

**F — K2 forensics (parallel, ≤30 min, zero spend, non-blocking):** the 7 E8 + 5 E7 + 6 C2 K2 cases side by side (terminal, fixture, reasoning text; concentrated vs scattered; defect-undercharged vs defect-unfound) — feeds the verifier's absence-audit wording.

## §6 — Per-trial deliverable: EVAL_ANALYSIS.md (owner-ordered; unchanged contract)

In every trial's results directory, written after the §R reads, from `results.json` **and all five fixture reports**. ≤2 pages, plain language, every term glossed once, every claim traceable. Structure, in order: **(1)** Verdict line (ADOPT-CANDIDATE / KILLED / ITERATE / GATE-PASS + one sentence). **(2)** Gates & kills table — target · this run · previous · baseline · PASS/FAIL · trend. Nothing precedes this table. **(3)** Top-5 improved / top-5 regressed, in points-per-test and plain words. **(4)** The five students, one line each: GT→AI (k-range), biggest miss + terminal id, one representative quote of the model's own reasoning. **(5)** Best working theory: mechanism, §R evidence, stated confidence. **(6)** Recommended next: one primary (expected gate effect + cost), one alternative, and what evidence distinguishes them.

## §7 — Final deliverable: EVAL_REPORT.md (presented at H-1 or H-2)

1. **Executive verdict** — one page: champion config, gates green/red, what a teacher gets.
2. **The frontier map** — every config run, plotted on the gates (table): accuracy (GA-2), reliability (GA-5), cost (GA-7), OVER-CEILING stamps. **If the accuracy winner is over-ceiling, state the intelligence–cost frontier plainly: exactly what each gate forfeits at $0.08** — so the owner can rule on the ceiling with numbers.
3. **Predictions scored:** P1 (Terra@high dominance) and the Sonnet-5 hypothesis, CONFIRMED/FALSIFIED with the numbers; every loop HYPOTHESIZE line dispositioned.
4. **The champion, in depth:** k=5 confirmation results; per-fixture story (din especially — the wrong-target paper is the architecture's hardest test); stability analysis; §R bucket counts; residual failure modes with examples.
5. **Attribution (best-effort):** champion-model × grader-v3 comparison — how much came from the architecture vs the model.
6. **Production recommendation:** rollout config, fallback pin, R2 judge-vendor consequence if the champion is Anthropic, open risks, and the recommended next investment (fixture expansion n≥10/≥2 exams is the standing candidate).
7. **Appendix:** links to every EVAL_ANALYSIS.md, PREDICTIONS.md fully scored, spend ledger, RUNLOG index.

## §8 — Definition of done

- [ ] V5-A green (schemas, validator, pricer injected-error tests, multi-provider seam, byte-identity pin, provenance).
- [ ] V5-B plan ratified by owner (H-4).
- [ ] Loop executed per §4 inside the envelope; every trial has kills-first analysis + EVAL_ANALYSIS.md; ledger complete.
- [ ] Halt via H-1 or H-2 with EVAL_REPORT.md delivered and the working implementation presented (H-1) or the best confirmed candidate + gap analysis (H-2).
- [ ] GT untouched · fences intact · batteries green · RUNLOG complete · zero production-quota Gemini risk.
