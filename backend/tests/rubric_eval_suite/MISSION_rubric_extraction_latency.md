# MISSION — Reduce rubric-extraction latency at zero benchmark regression

**Owner:** Noam · **Executor:** you (autonomous coding agent) · **Surface:** `vivi-codebase/backend/tests/rubric_eval_suite/` + `app/services/docx_v3/`

---

## 0. The mission in one sentence

Find and prove a change that **materially reduces wall-clock time to rubric extraction** while the suite still passes **5/5 fixtures with every gated metric at 1.0 worst-case** — or prove, with the same rigour, that no such change exists inside the lever space you were able to search.

**Both of these are successful terminations.** A documented negative result ("these seven levers were tested and falsified, here is the latency model that explains why") is a *win*. A latency number obtained by weakening the instrument is a *catastrophic failure* — worse than doing nothing, because it silently destroys the regression gate the whole product trusts. If at any point the only path to the target runs through the ground truth, the scorer, the gate, or the fixture set: **stop and report, do not take it.**

---

## 1. Read before you touch anything

In this order, and quote back the three things you learned that most change your plan:

1. `tests/rubric_eval_suite/ONBOARDING.md` — the map.
2. `tests/rubric_eval_suite/RUBRIC_EVAL_PLAYBOOK.md` — the analysis contract. Its prime directives bind you.
3. `tests/rubric_eval_suite/RUNLOG.md` — read the **whole** ledger. Most of the prompt sections and GT rulings were *purchased* with a failing run. You must know which, because deleting one is how you regress.
4. `tests/rubric_eval_suite/PREDICTIONS.md` and `GT_AUDIT.md`.
5. `CLAUDE.md` (repo root) — §0 rules 1–5 apply to this mission verbatim.
6. The code: `runner.py`, `schemas.py`, `reporting.py`, `gates.py`, and `app/services/docx_v3/pipeline.py`.

**When this brief and the code disagree, the code is truth and this brief is a bug** — say so in your report.

---

## 2. Definitions — make the goal measurable before you optimise it

You cannot optimise what the instrument does not measure, and the suite currently measures **cost**, not **time**. Fix that first (Phase 0), then use these definitions everywhere.

**Primary metric — `t_doc`:** wall-clock seconds from pipeline entry for one fixture to the returned `ExtractRubricResponse`, measured with a monotonic clock, including every LLM round trip, every retry, and local render/validation. One number per (fixture, trial).

**Required decomposition** (this is the latency model; see Phase 2):

```
t_doc ≈ t_render_local
      + Σ_over_chain_steps [ t_queue + t_prefill(input_tokens, cached_tokens) + t_decode(output_tokens + reasoning_tokens) ]
      + t_retry_overhead
      + t_validate_local
```

Record per step: `input_tokens`, `cached_tokens`, `output_tokens`, `reasoning_tokens` (if exposed), `finish_reason`, retry count, and the wall-clock of the call itself.

**Aggregates — worst-case discipline, mean forbidden as a headline:**
- `t_doc_median[fixture]` — median over k trials, per fixture.
- `t_doc_max[fixture]` — worst trial, per fixture (the teacher's bad day).
- **Headline = `max over fixtures of t_doc_median`** (the slowest document a teacher actually waits on).
- **Tail = `max over fixtures of t_doc_max`.**

**Noise band:** the run-to-run spread of the *unchanged* baseline, measured in Phase 1 by running the pinned baseline as two independent blocks. Any claimed improvement smaller than **2×** this band is noise, not a result.

**"No regression" means, precisely:**
- Every gated metric in `gate_pass` at **1.0 worst-case** across all trials, 5/5 fixtures PASS, **0 INVALID trials**. The gate is conjunctive; a partial pass is a fail.
- `cost_per_doc` not above the baseline (a latency win bought with money is a decision for Noam, not for you — surface it, do not bank it).
- Ungated diagnostics (`point_sum_consistency`, `*_text_fidelity_min`, `text_line_recall_min`) are **watched**: a material move in either direction is reported, never silently accepted, never used as justification.
- Validity/retry behaviour not worse: report retry counts and transport-failure rate per candidate.

---

## 3. The immutable set — and the forbidden moves

**Files you may NOT modify, for any reason, on this mission:**

**A. Ground truth — total prohibition.** No GT artifact may be created, edited, deleted, regenerated, refreshed, reordered, or reformatted. Not one character.

```
tests/rubric_eval_suite/benchmarks/*.json      ← the ground truth itself
tests/rubric_eval_suite/fixtures/*.docx        ← the source inputs GT was authored from
tests/rubric_eval_suite/markdowns/*.md         ← cached renders (GT's derivation source)
tests/rubric_eval_suite/GT_AUDIT.md            ← GT rules, conventions, rulings
tests/rubric_eval_suite/build_benchmarks.py    ← the GT authoring chain
tests/rubric_eval_suite/tools/populate_texts.py ← GT text derivation
```

This extends to **running** them: do not execute `build_benchmarks.py` or `tools/populate_texts.py`, and do not regenerate cached markdowns even if a renderer change makes them stale. A stale cached render is a **finding**, not a file to refresh. Do not add new fixtures or benchmarks either — expanding the set mid-mission changes what "5/5" means and destroys comparability with the baseline.

**B. The instrument — no threshold, semantic, or guard changes.**

```
tests/rubric_eval_suite/scoring.py             ← the scorer
tests/rubric_eval_suite/gates.py               ← the gate
tests/rubric_eval_suite/normalize.py           ← thresholds/harmonisation
tests/rubric_eval_suite/test_*.py              ← the instrument's own guards
```

If you believe any file in A or B contains a bug that is blocking you — a GT typo, a too-strict threshold, a stale render — that is a **finding to report with evidence**, not a change to make. (§10 of ONBOARDING, rule 3.) The one and only sanctioned edit inside the suite is the **purely additive latency instrumentation** of Phase 0, confined to `schemas.py`, `reporting.py`, `runner.py`.

> Why this is absolute: latency is the *only* thing you are optimising, and every file above is a term in the definition of "no regression". An agent permitted to edit its own success criterion will eventually edit it. Your entire result rests on those files being byte-identical at the end of the mission to what they were at the start — and §9 requires you to prove it.

**Forbidden moves — each of these "achieves" the goal while destroying it:**

1. Touching ground truth in any form — editing a benchmark, "correcting" a GT typo you are confident about, regenerating benchmarks, refreshing cached markdowns, amending `GT_AUDIT.md`, or running the authoring tools. Including when the GT is genuinely wrong. **Especially** then: a GT bug that a latency candidate happens to expose is the most valuable finding available to you, and editing it destroys both the finding and the gate.
2. Removing, shrinking, or adding to the fixture set; lowering `--repeats`; or excluding a fixture from an aggregate because it was slow, expensive, or awkward.
3. Caching, memoising, replaying, or stubbing LLM responses anywhere in the measured path. **Every measured trial must issue fresh API calls.** Prove it: non-zero uncached token counts and distinct request IDs per trial.
4. Presenting `score_only` output as latency evidence. `score_only` measures nothing about time.
5. Deleting a prompt SECTION, guard, or convention whose purchase is recorded in RUNLOG, on the grounds that the current fixtures do not exercise it.
6. Changing two variables in one run and attributing the result to one of them.
7. Registering a prediction after seeing the result ("prediction laundering" — explicitly forbidden by the playbook).
8. Adding a latency threshold to `gate_pass`. Latency becomes a *reported* metric now; a gate threshold must be pre-registered from a measured distribution and approved by Noam later, never guessed into existence mid-mission.
9. Merging to `main` or editing the production config pin. Your deliverable is a **branch plus evidence**, not a shipped change.

**Work on a dedicated branch:** `perf/rubric-extraction-latency`. One atomic commit per accepted change, message naming the hypothesis ID.

---

## 4. Operating parameters

| Parameter | Value |
|---|---|
| Screening repeats | `k = 2` (cheap, wide, hypothesis-generating only) |
| Confirmation repeats | `k = 5` (candidate shortlist, all 5 fixtures) |
| Final confirmation repeats | `k = 8` on the single promoted candidate only, all 5 fixtures |
| Target — headline | ≥ **30%** reduction in `max over fixtures of t_doc_median` vs. the re-baselined pin |
| Target — stretch | ≥ 50%, and/or a reduction in the tail (`t_doc_max`) |
| Minimum detectable effect | > 2 × the Phase-1 noise band. Below that, report "indistinguishable from noise" |
| Hard spend ceiling | **$35** total API spend. Print a running total after every run. At **$28**, stop and report before starting another paid run |
| Turn bound | Stop and report after 60 turns regardless of state |

### The budget is tight and binding — plan the whole campaign before spending a cent

At the current suite mean of roughly **$0.25/doc-extraction**, one full-suite run costs about `5 × k × $0.25`:

| Run | Cost |
|---|---|
| Full suite, k=2 | ~$2.50 |
| Full suite, k=3 | ~$3.75 |
| Full suite, k=5 | ~$6.25 |
| Full suite, k=8 | ~$10.00 |

$35 buys roughly **one serious candidate carried all the way through confirmation**, plus a handful of cheap screens. A reference allocation that fits:

```
Phase 1  baseline, 2 blocks × k=3, all fixtures      ~$7.50
Phase 4  ~5 screens on the 2-fixture screening set   ~$5.00
Phase 5  one shortlist confirmation, k=5, all 5      ~$6.25
Phase 5  final confirmation, k=8, all 5              ~$10.00
         reserve (transport failures, one re-run)     ~$6.25
                                                    -------
                                                     $35.00
```

**This is a reference, not a mandate — but you must print your own campaign plan in Phase 0, summing to ≤ $35 with a reserve of ≥ $5, before any paid run.** Re-print the remaining balance after every run and re-plan explicitly when a run overruns its estimate.

The direct consequence: **you cannot brute-force the lever space.** You get about five screening shots. That makes Phase 2 attribution the highest-value work in the mission — the latency model is what buys you the right five, and guessing from the §6 menu instead is how you spend the budget and learn nothing.

If a single run's estimate exceeds **$10**, or the plan no longer fits the ceiling, stop and ask.

---

## 5. Phase plan — each phase has an exit criterion you must print

### Phase 0 — Instrument (no API spend beyond one smoke trial)

The suite measures cost, not time. Add latency measurement as a **purely additive** instrument change: new fields in `results.json` / `schemas.py` / `reporting.py`, new columns in `summary.md`. Nothing about scoring, gating, prompts, or model behaviour changes.

Also determine and record, as facts: does the runner execute fixtures concurrently? Is a fresh HTTP client constructed per call? Is timing measured around a `gather`? A latency instrument that measures contention instead of work is worse than none.

**Exit criteria (print all):**
- `test_scoring.py` and every `test_*.py` guard pass.
- A `score_only` re-score of cached predictions from a pre-instrumentation run reproduces **byte-identical** scores — proof the instrument is additive.
- The new `suite_hash` is recorded in RUNLOG with a note that pre-instrumentation runs are no longer hash-comparable (scores remain comparable).
- The measurement protocol is written down: clock, boundaries, concurrency setting, warm/cold handling, and whether trial 1 is treated differently.
- **The campaign budget plan** (§4): every planned run, its k, its fixture scope, its estimated cost, summing to ≤ $35 with ≥ $5 reserve.

> **The instrument is the prime suspect — including this one.** A surprising latency number is a measurement bug until proven otherwise.

### Phase 1 — Re-baseline and measure the noise floor

Instrumented baseline at the production pin (`gpt-5.5`, effort=medium, prompt `3.3.1-tracehdr`), run as **two independent blocks of k=3**, separated in time (different hours, ideally different parts of the day). Two blocks is not a luxury: one block gives you a baseline, two give you the noise band, and without the noise band every later delta is uninterpretable.

**Exit criteria:** the baseline table (per fixture: median, max, per-step decomposition, token counts, retries, cost), the observed noise band, and confirmation that the baseline still passes 5/5. If the baseline does **not** reproduce 5/5, stop — you have found a drift bug and that is now the report.

### Phase 2 — Attribution before intervention

Fill in the latency model from Phase 1 data. Answer, with numbers: **where does the time actually go?** Local render vs. queueing vs. prefill vs. decode; which chain step dominates; what fraction of the tail is retries; what fraction of decode is reasoning tokens; what the current cache-hit rate is.

**Exit criterion:** a printed latency budget summing to `t_doc` per fixture, and a ranked shortlist of levers *derived from the largest terms* — not from the lever menu in §6. §6 is a checklist against which you verify you have not missed something obvious; the model is what tells you where to spend.

> Naming a fix surface from an end-to-end number alone is the failure mode this phase exists to prevent.

### Phase 3 — Pre-register

Append to `PREDICTIONS.md`, **before** the run: hypothesis ID, the exact single variable changed, the mechanism (which term of the latency model it attacks), the **predicted** effect size on the headline metric, the **kill criterion**, and the predicted effect on gated metrics. One variable per run. No exceptions.

### Phase 4 — Screen (k=2)

Cheap, wide, hypothesis-generating. A k=2 result is **never** promotable and never quoted as a no-regression claim — the models are non-deterministic and 2 trials cannot distinguish "safe" from "lucky". Screening output is a *shortlist* and nothing else.

**Design the comparison to cancel network noise:** interleave baseline and candidate trials in the same session (A/B/A/B per fixture) rather than running baseline in one block and candidate an hour later. Time-of-day API variance is large enough to manufacture or erase a 20% "result".

**Screening fixture scope — the single narrow exception to §3.2.** Because the budget buys about five screening shots, screening (and *only* screening) may run on a fixed, named two-fixture subset:

- `bagrut_899371` — the hardest reasoning in the set, the faithful-error case, and the expensive/slow tail. Any lever that breaks something will most likely break it here.
- `csharp_plane_combine` — the clean-table control and the verbatim-`example_solution` guard.

Three conditions, all binding: the subset is **fixed in advance and never re-chosen** to suit a candidate; every screening result is labelled `SCREEN (2-fixture subset) — NON-PROMOTABLE`; and **no candidate advances or is reported as a result without a full 5-fixture run at k ≥ 5**. A subset screen that passes proves nothing except "worth paying to test properly."

### Phase 5 — Confirm (k=5, then k=8 on one winner)

Only candidates that survive screening. Then pick **one** and run the final k=8 confirmation.

State the power honestly: 40 clean trials with zero failures bounds the true per-trial failure rate at roughly ≤7% (rule of three), it does not prove equivalence to baseline. Say so in the report. Do not write "proven identical".

### Phase 6 — Adversarial review

Before declaring done, have a **fresh subagent** review the full branch diff with no memory of your reasoning. Its brief: *"Find every way this diff could reduce measured latency without reducing real latency, or could pass the gate without preserving extraction quality. Report only findings that bear on correctness or the stated constraints."* Print its findings and your responses. Then run `git diff --stat main...HEAD` and prove no immutable-set file appears.

### Phase 7 — Report and stop

---

## 6. Lever inventory — a checklist, not a plan

Ranked by expected leverage × inverse risk. **Tier 1** you may test autonomously. **Tier 2** you may *propose with evidence* but must not promote without Noam.

### Tier 1 — no change to model-visible content

| # | Lever | Term attacked | Notes / risk |
|---|---|---|---|
| L1 | **Retry elimination.** Quantify retry contribution to the tail. ONBOARDING §9.6 flags `EMPTY_SQ_TEXT` firing on branch sub-questions against the prompt's own SECTION-8 convention — a burned round trip on a *legitimate* shape. | `t_retry_overhead` | Highest-confidence structural win. A retry is a full extra chain step. Must show validity rate does not degrade. |
| L2 | **Transport and client reuse.** One shared async client, connection pooling, no per-call TLS handshake or client construction; check for accidental serialisation. | `t_queue` | Often 100–300 ms/call, free. |
| L3 | **Intra-document parallelism.** Are any of the 3 chain steps independent? Anything sequential that need not be? | `Σ over steps` | Only genuinely independent work. Do not parallelise a dependency and paper over the race. |
| L4 | **Prompt-cache exploitation.** Cache hits need an *exact prefix match*; static content (system prompt, structured-output schema) must precede the variable rendered document, and `prompt_cache_key` should be set consistently. Measure `cached_tokens`, do not assume. | `t_prefill` | Real but bounded: caching cuts prefill, and for a reasoning model **decode usually dominates**. Predict the ceiling from Phase 2 before spending a run on it. |
| L5 | **Local render.** Measure `parser_render.py`. Probably milliseconds — verify rather than assume, then stop thinking about it. | `t_render_local` | Cheap to rule out. |

### Tier 2 — changes model-visible content or the production pin (propose only)

| # | Lever | Term attacked | Notes / risk |
|---|---|---|---|
| L6 | **`reasoning_effort` reduction.** `gpt-5.5` supports `none / low / medium (default) / high / xhigh`. Reasoning tokens are decode time; this is the largest single knob. | `t_decode` | Test `low` before `none`. Config-only, so screening is trivial — but it is exactly the lever most likely to break the bagrut faithful-error case, which is the hardest reasoning in the set. |
| L7 | **Per-step effort mixing** — the non-obvious one. The 3 steps are not equally hard: structure/nesting inference may need `medium` while verbatim `example_solution` copying may not need reasoning at all. A per-step effort policy can beat any global setting on the latency/accuracy frontier. | `t_decode` | Requires the per-family LLM constructor policy (`test_llm_policy.py`) to express per-step knobs. Highest expected value in the whole list; treat it as the main event. |
| L8 | **Model swap.** Newer OpenAI generations advertise frontier quality at *fewer output tokens*, which is a direct latency win rather than a trade. Cross-family configs already exist (`claude-sonnet-4-6.json`). | `t_decode`, `t_prefill` | Config-only to screen. Promotion is a Noam decision (cost table, prod pin, provider risk). |
| L9 | **Output-size control** (`verbosity` or equivalent), and sanity-check `max_output_tokens=32k` is not inducing verbosity. | `t_decode` | Output is structured JSON, so the effect may be small — cheap to screen. |
| L10 | **Hedged requests.** Fire the slow step twice concurrently, take the first response. Classic tail-latency technique (Dean & Barroso, *The Tail at Scale*, CACM 2013). | tail | Cuts `t_doc_max` hard, at ~2× cost. **Caveat that must be stated:** taking the first returner biases the sample toward shorter/less-reasoned generations — this is an accuracy risk, not a free lunch, and must clear the full gate. |
| L11 | **Prompt compression.** Fewer input tokens = less prefill. | `t_prefill` | **Do this last, if at all.** Each SECTION was purchased against a specific failure. Prefill is likely a minority of `t_doc`. The expected value is low and the regression risk is the highest in the list. Any edit bumps `EXTRACTION_PROMPT_VERSION`. |
| L12 | **Chain restructuring** (3 steps → 2). | one fewer round trip | Architectural. Write the proposal, do not build it. |

### Out of scope but you must name it in the report

The suite measures *pipeline* latency. A teacher waits on **Cloud Run cold start at `min-instances 0`, Cloud Tasks dispatch, and frontend polling**, none of which this suite can see. If the product goal is "the teacher waits less", a meaningful share of the win may live entirely outside your measurement surface. Quantify what you can, flag the rest, do not chase it here.

---

## 7. Per-run output contract

The transcript is the audit trail. After **every** run, print exactly this block:

```
RUN <timestamp>_<config>   HYP <id>   MODE extract   k=<n>
Variable changed (one):   <exact field/file/value, old → new>
Pre-registered prediction: <effect + kill criterion>  [PREDICTIONS.md line <n>]
Gate:   <p>/5 fixtures PASS   INVALID trials: <n>   worst-case per gated metric: <table>
Latency: headline t_doc_median(worst fixture) = <s>  (baseline <s>, Δ <±%>)
         tail     t_doc_max(worst fixture)    = <s>  (baseline <s>, Δ <±%>)
         per-step decomposition: <table>
Tokens/retries: <in/cached/out/reasoning, retries, finish_reasons>
Fixture scope: ALL 5 | SCREEN (2-fixture subset) — NON-PROMOTABLE
GT artifacts touched: NONE  (assert explicitly, every run)
Cost:   $<per doc> / $<run>   Running total: $<x> of $35   Remaining plan: $<y>
Verdict: CONFIRMED | FALSIFIED | INDISTINGUISHABLE-FROM-NOISE | INVALID-RUN
RUNLOG entry: <appended? y/n>
```

An analysis is not done until its RUNLOG entry exists. Append-only. Every run, every variable change, every ruling — including rulings that changed no file.

---

## 8. Stop and ask Noam when

- The baseline does not reproduce 5/5 (drift bug — that is the report).
- A candidate hits the latency target but moves an **ungated** diagnostic materially.
- The only remaining path requires touching the immutable set.
- A latency win requires a cost increase.
- You want to promote a Tier-2 lever, change the production pin, or restructure the chain.
- Spend reaches $28, turn 55, or a run overruns its estimate enough to break the campaign plan.
- You have found a genuine GT, fixture, render-cache, or scorer bug — report with evidence and stop; **do not fix it, do not route around it, do not exclude the affected fixture.**

---

## 9. Definition of Done

Terminate when **A** or **B** holds and the evidence for it is printed in the transcript.

**A — Promotable candidate.** All of:
1. `git diff --stat main...HEAD` printed; **no** immutable-set file (§3.A or §3.B) appears in it.
2. `git status --porcelain tests/rubric_eval_suite/benchmarks tests/rubric_eval_suite/fixtures tests/rubric_eval_suite/markdowns` printed and **empty**, plus a printed checksum comparison of `benchmarks/*.json` against `main` showing them byte-identical.
3. All `test_*.py` guards pass, printed.
4. A single k=8 confirmation run **on all 5 fixtures** shows **5/5 fixtures PASS, every gated metric 1.0 worst-case, 0 INVALID trials**.
5. That run's headline `t_doc_median` on the worst fixture is **≥30% below** the Phase-1 re-baseline, and the delta exceeds 2× the measured noise band.
6. `cost_per_doc` not above baseline, or the increase explicitly surfaced as an open decision.
7. Every run has a RUNLOG entry; every run has a PREDICTIONS.md entry written before it.
8. Phase-6 adversarial review findings and responses printed.
9. `LATENCY_REPORT.md` written (§10), and total spend ≤ $35 reported.

**B — Falsified.** The pre-registered hypothesis list is exhausted, or the budget/turn bound is reached, and `LATENCY_REPORT.md` documents: the latency model, every hypothesis with prediction/result/verdict, why each failed (regression vs. no effect vs. noise-limited), and what instrument or fixture change would be needed to search further. **This is a legitimate success.**

Anything else — partial passes, k=2 evidence, subset-screen evidence, "looks faster", a win with one fixture excluded, or any result obtained after a GT artifact moved — is **not done**.

---

## 10. Deliverables

1. Branch `perf/rubric-extraction-latency`, atomic commits, not merged.
2. `tests/rubric_eval_suite/LATENCY_REPORT.md`:
   - The latency model with real numbers (the durable artifact — it outlives every lever).
   - Hypothesis ledger: ID, variable, prediction, kill criterion, result, verdict.
   - The promoted candidate (or the negative result), with its evidence and its honest power statement.
   - Residual risk: what this change could break that the current 5 fixtures cannot detect.
   - Recommendation for a future *latency* gate threshold, derived from the measured distribution — proposed, never self-applied.
   - Out-of-suite latency items (cold start, dispatch, polling) with whatever quantification you could get.
3. RUNLOG.md and PREDICTIONS.md updated in place.
4. A short "what I would do next with $200 and 20 more fixtures" section.

---

## Appendix — compact stop condition (≤4000 chars, for `/goal` if you use it)

> Reduce rubric-extraction latency on branch `perf/rubric-extraction-latency` with zero regression and zero ground-truth movement, and prove it in the transcript. DONE requires ALL of: (1) `git diff --stat main...HEAD` printed, containing NO file under `tests/rubric_eval_suite/benchmarks/`, `fixtures/`, `markdowns/`, and not `GT_AUDIT.md`, `build_benchmarks.py`, `tools/populate_texts.py`, `scoring.py`, `gates.py`, `normalize.py`, or any `test_*.py`; (2) `git status --porcelain` over `benchmarks/`, `fixtures/`, `markdowns/` printed and empty, plus a printed checksum comparison showing `benchmarks/*.json` byte-identical to `main`; (3) all `tests/rubric_eval_suite/test_*.py` pass, output printed; (4) one confirmation run of `PYTHONPATH=. python -m tests.rubric_eval_suite.runner --config <candidate> --repeats 8` over all 5 fixtures whose printed summary shows 5/5 fixtures PASS, every gated metric 1.0 worst-case, and 0 INVALID trials; (5) the printed per-fixture median `t_doc` on the worst fixture is at least 30% below the instrumented baseline median printed earlier in this transcript, with the delta exceeding 2× the baseline noise band also printed earlier; (6) cost per doc not above baseline and total spend ≤ $35, printed; (7) a RUNLOG.md entry exists for every run and a PREDICTIONS.md entry was written before each run, both printed; (8) `tests/rubric_eval_suite/LATENCY_REPORT.md` exists and its contents are printed. ALTERNATIVELY, DONE if the pre-registered hypothesis list is exhausted or $35 spend / 60 turns is reached AND `LATENCY_REPORT.md` documents the latency model, every hypothesis with its prediction, result and verdict, and why no promotable candidate exists — a documented negative result is a valid completion. Constraints that must hold throughout: no ground-truth artifact created, edited, deleted, regenerated or refreshed, and `build_benchmarks.py` / `tools/populate_texts.py` never executed; one variable per run; predictions registered before runs; no cached, stubbed or replayed LLM responses in any measured path; no change to the fixture set or repeat count, and no promotable claim from a subset screen; no edit to scorer, gate, or tolerances; no merge to main; no change to the production config pin. Stop after 60 turns.
