# Rubric Eval Suite — Engineer Onboarding

> A map for someone who has never seen this directory. Read this first, then the
> `RUBRIC_EVAL_PLAYBOOK.md` (how to read the instrument without fooling yourself)
> and `RUNLOG.md` (what has actually happened). When this doc and the code
> disagree, the code wins — fix this doc.

Path: `vivi-codebase/backend/tests/rubric_eval_suite/`

---

## 1. What this suite is and why it exists

It is the **regression gate for `docx_v3` rubric extraction** — the pipeline that
turns a teacher's DOCX rubric into a structured `ExtractRubricResponse` (the Draft
in Vivi's Draft→Contract architecture). The suite is the *instrument* that decides
whether an extraction change ships. Its guiding rule: **if you change extraction
behavior and do not run this suite to a stated kill criterion, the change is
unfalsifiable — do not ship it.**

It is the rubric analog of the older transcription eval suite, and it inherits that
suite's disciplines (worst-case over mean, validity before significance, one
variable per run, k-repeats for non-determinism).

**Status: the mission gate has been MET.** As of the last close-out (run
`20260711-131057`, prompt `3.3.1-tracehdr`), the suite passes **5/5 fixtures** with
every gated metric at 1.0 worst-case. The subsequent run (`20260711-140120`)
verified a pipeline transport change and held 13/13 *valid* trials (2 lost to
transient connection errors, not accuracy). The loop is currently **closed and
handed back to Noam**; open items are cost/transport polish, not accuracy gaps.

---

## 2. The two-stage model (what is being scored)

Extraction is scored as two stages, exactly like the transcription P1/P2 split:

| Stage | Code | Failure meaning |
|---|---|---|
| **RENDER** (perception) | `app/services/docx_v3/parser_render.py` (`render_docx_to_markdown`) | Ink the teacher wrote never reaches the LLM |
| **EXTRACT** (interpretation) | `app/services/docx_v3/pipeline.py` (LLM, 3-step prompt chain) | Content is in the render but mis-structured or dropped |

Every **missed GT criterion is auto-attributed**: present in the rendered markdown
(token-overlap ≥ 0.70) ⇒ `extraction_loss` (fix the prompt/model); absent ⇒
`render_loss` (fix the renderer). `summary.md` reports the split. This tells you
*which half to work on* from a single ground truth.

> The pipeline itself lives in the production app, **not** in this suite. The suite
> imports and drives the real production pipeline (lazily, so `score_only` needs no
> OpenAI). "Production runs the exact code the suite measures."

---

## 3. Directory layout

```
rubric_eval_suite/
├── ONBOARDING.md              ← you are here
├── RUBRIC_EVAL_PLAYBOOK.md    ← the analysis contract (prime directives, gate, scoring semantics)
├── RUNLOG.md                  ← append-only ledger of every run + variable change (the hard memory)
├── PREDICTIONS.md             ← pre-registered predictions (written BEFORE runs; no post-hoc laundering)
├── GT_AUDIT.md                ← ground-truth authoring rules, conventions, rulings, open items
│
├── fixtures/      *.docx      ← 5 source rubric documents (the inputs)
├── benchmarks/    *.json      ← 5 ground-truth ExtractRubricResponse files (type-valid Pydantic)
├── markdowns/     *.md        ← cached renders of each fixture (reference)
├── configs/       *.json      ← experiment configs (model/provider/knobs/prices) — the A/B knob
├── results/       <ts>_<cfg>/ ← one dir per run: results.json + summary.md + report_<rubric>.md + predictions/ (+ traces/ when --trace on)
│
├── runner.py                  ← orchestrates render → extract → score → report; modes: extract | score_only
├── scoring.py                 ← THE scorer: aligns predicted vs GT → RubricScore (pure, no pipeline import)
├── gates.py                   ← the conjunctive gate (pass iff ALL criteria hold)
├── schemas.py                 ← stable results.json shape (RubricScore, ScopeScore, SuiteResult, …)
├── normalize.py               ← NFC/casefold/whitespace + difflib(autojunk=False) + label harmonization
├── reporting.py               ← aggregate() + writes summary.md / report_<rubric>.md / results.json
├── build_benchmarks.py        ← how the GT benchmarks were authored (audit trail in builders + [FLAG]s)
├── tools/populate_texts.py    ← mechanically populated GT question/sq text from renders (PR-1)
│
└── test_*.py                  ← the instrument's own guards (run after any scorer edit):
    ├── test_scoring.py        ← known-answer: perfect extraction scores 1.0/PASS; 7 injected errors FAIL
    ├── test_fp123.py          ← expressibility round-trip + pedagogical-consistency invariant (real Tier A)
    ├── test_pedagogical.py    ← Tier-A/B pedagogical-mistake set-comparison
    ├── test_llm_policy.py     ← per-family LLM constructor policy (temperature/effort/budget)
    └── test_retry_policy.py   ← pipeline retry policy (mismatch-only ⇒ no retry)
```

### How to run

```bash
# Full gate (real pipeline, real OpenAI) — k repeats for non-determinism
PYTHONPATH=. python -m tests.rubric_eval_suite.runner --config gpt-5.5 --repeats 5

# Instrument self-guard (no OpenAI) — run after ANY scorer/gate/schema edit
PYTHONPATH=. python tests/rubric_eval_suite/test_scoring.py

# With the tracelog on (see §11) — capture the LLM's thought process for debugging
PYTHONPATH=. python -m tests.rubric_eval_suite.runner --config gpt-5.5 --repeats 5 --trace failures
```
(Windows: `PYTHONUTF8=1` is needed for the suite scripts — Hebrew content.)

---

## 4. The five fixtures (each covers a distinct failure mode)

The set is deliberately spanning; **missing a mode makes that part of the gate
vacuous.** Do not delete or "clean up" a fixture without understanding what mode it
guards.

| Fixture | Archetype it guards | Shape | Notable GT |
|---|---|---|---|
| **employee_course_select1** | **Selection exam** (choose-k) | 3 Q, 1 selection group, total **50** (achievable, not the 100 offered) | 1 pedagogical (`selection_normalization`) |
| **bagrut_899371** | **Nested (1)(2) + genuine teacher error** | 6 Q, 1 selection group, depth-2 nesting | 1 `rubric_mismatch` annotation **and** 1 pedagogical `point_sum_mismatch` @ q1.א.2 (teacher's 1.5+0.5 under declared 3) — the "never-reconcile" case |
| **foundations_cs** | **Inline/prose criteria** (no rubric table) | 3 Q | clean (0/0); most text spans are open items (null) |
| **hobby_tvshow** | **Nested tables + Tier-B judgment** | 2 Q | 1 pedagogical `structural_mislabel` (LLM adjudication, the non-deterministic surface) |
| **csharp_plane_combine** | **Clean-table control** (regression guard) + 7 verbatim code solutions | 2 Q | clean (0/0); strike-resolution 6→8, 18→20, 4→0-drop |

The **bagrut faithful-error** case is the heart of the product: the extractor
*passes* by **reproducing** the teacher's arithmetic error and **flagging** it
(both as a `rubric_mismatch` annotation and a Tier-A `point_sum_mismatch`
pedagogical mistake). A model that "fixes" the sum **fails** the gate on the
missing expected mistake. This is the rubric analog of "faithful transcription of a
flawed source."

---

## 5. Scoring model & the conjunctive gate

The scorer (`scoring.py`) is **prediction-vs-GT fidelity, never rubric-internal
consistency**. Key semantics:

- **Ids and `index` are IGNORED** — the pipeline generates them and they shift with
  structure. Questions match by canonical number; sub-questions by *harmonized
  label* (א/a/1 collapse to one index); criteria by **description similarity ≥ 0.85**
  (DESCRIPTION-PRIMARY — points are scored separately, not a match key, to keep
  recall/precision orthogonal from point errors).
- **Structure**: `subquestion_structure_match` = 1.0 iff the id-tree is isomorphic
  to GT *including leaf-vs-branch classification* (a GT branch flattened into
  criteria is the `leaf_vs_branch` / FP2 signal).
- **Points**: exact (tolerance 0, 0.25 increments). `total_points_correct` is
  selection-aware (`compute_achievable_points` = Σ mandatory + Σ top-choose_k).
- **Example solutions**: gate-blocking (ratio ≥ 0.85 where GT non-null; must be
  null where GT null).
- **Annotations**: predicted must reproduce the GT-expected `rubric_mismatch`
  annotations (by `(type, target_id)`).
- **Pedagogical mistakes**: predicted must set-equal GT by `(kind, canonical
  target)`. Governed by the **pedagogical consistency invariant**: GT ≡
  TierA(faithful draft) ∪ expected-Tier-B. Zero-mistake GTs are the false-positive
  guard.
- **Text fidelity** (`question_text_fidelity_min` / `subquestion_text_fidelity_min`
  / `text_line_recall_min`): **UNGATED diagnostic** — worst-node, mean forbidden.
  Two numbers by design: `ratio` is the fidelity detector, `line_recall` is the
  omission detector. Not in `gate_pass`; a gate threshold would have to be
  pre-registered from a measured distribution, never guessed.
- **Consistency** (`point_sum_consistency`): reported as **health, never gated** —
  a teacher's rubric may be legitimately inconsistent; gating it would punish
  faithful extraction (`annotation_match` is the correct gate for that case).

**The gate (`gates.py`) is CONJUNCTIVE** — a rubric PASSES iff ALL of these hold
simultaneously: `question_recall/precision == 1`, `subquestion_structure_match ==
1`, `criterion_recall/precision == 1`, `subcriterion_recall/precision == 1`,
`point_exactness == 1`, `total_points_correct`, `selection_match`,
`example_solution_fidelity == 1`, `annotation_match`, `pedagogical_match`, `valid`,
and `cost ≤ ceiling`. Partial improvement that masks a regression must not pass —
that is the entire point.

**Validity gate**: a `None` prediction (parse/transport failure) or `finish_reason
∈ {LENGTH, MAX_TOKENS}` (truncation) ⇒ INVALID — excluded from accuracy aggregates
and fails the gate. Never average a number you can't trust.

---

## 6. The variables you iterate on

There are exactly four kinds of experimental variable. **One change per run.** Each
belongs in one place, and each has its own drift-detection.

| Variable | Where it lives | Drift signal |
|---|---|---|
| **Model / provider / generation knobs** (model, provider, `max_output_tokens`, `reasoning_effort`, prices, `cost_ceiling`) | `configs/<name>.json` — one file = one (model, provider, prices, knobs) pairing | `model_version` stamped in results.json |
| **Prompt** | `app/services/docx_v3/pipeline.py` (`EXTRACTION_SYSTEM_PROMPT`); **bump `EXTRACTION_PROMPT_VERSION`** on every edit | `prompt_version` stamped from that constant |
| **Ground truth** (`benchmarks/*.json`) | authored via rules in `GT_AUDIT.md`; text via `tools/populate_texts.py` | `suite_hash` (covers benchmarks + all `.py`) |
| **Instrument** (scorer / gate / schema / normalize / reporting) | the suite's `.py` files | `suite_hash` |

`suite_hash` deliberately **excludes** configs (the config is *supposed* to differ
between runs). Pipeline-code changes are **not** covered by `suite_hash`, so they
are stamped separately as `pipeline_version` **from the run** (`result.metadata`) —
that stamp is the only tree-drift signal for pipeline changes.

**Config knobs available** (`configs/`): `default.json` (gpt-4o baseline), plus
sweep configs `gpt-5.5.json` (openai, effort=medium, 32k tokens — **the production
pin**), `claude-sonnet-4-6.json` (anthropic), `gemini-3.1-pro-preview.json` (gemini
— note: undeployable, `langchain_google_genai` not installed). Sweep ceilings are
loose ($2.00) for pathology detection, not economy.

> **Determinism caveat**: the models are NOT deterministic at temp 0. Evaluate every
> change at `--repeats k` (k≥5 is the mission bar; Noam amended to k=2 late in the
> loop for budget) and compare **worst runs, not single runs.**

---

## 7. Provenance, cost, and the process discipline

- A result is a function of `(fixtures, config, prompt_version, model_version,
  pipeline_version)` — all five stamped into `results.json`.
- **Cost division of responsibility**: the PIPELINE measures tokens; the CONFIG owns
  the price table; the RUNNER multiplies; the GATE judges dollars vs `cost_ceiling`.
- **Failure isolation**: one doc's transport error becomes an INVALID record (not a
  lost run) — worst-doc discipline. Per-trial predictions are persisted to
  `results/<run>/predictions/` as they arrive, so a crashed run still leaves
  evidence, and a scorer change can be re-scored offline against cached predictions
  (`score_only`) for **$0**.
- **RUNLOG.md is the hard memory.** Append-only. Every run gets an entry; every
  variable change gets an entry (run or not); a convention *ruling* gets an entry
  even when no file changes. An analysis isn't done until its RUNLOG entry exists.
- **PREDICTIONS.md** holds pre-registered predictions written *before* runs.
  Post-hoc registration is "prediction laundering" and is explicitly forbidden.

---

## 8. Current performance state (headline)

**Mission gate: MET — 5/5 fixtures PASS**, every gated metric 1.0 worst-case, at:
- prompt `3.3.1-tracehdr`, model `gpt-5.5` @ effort=medium, pipeline `3.1.0`+
  (transport policy `3.3.0` in prod).

The arc that got there (see RUNLOG for the full ledger):

```
1/5 (20260705 baseline)
 → 3/5  Run A: instrument batch B1–B5 + GT fixes A1–A3 (highlight channel, tokenizer, csharp two-column GT)
 → 4/5  Run B: prompt 3.3.0 (nesting-by-scoring-structure, verbatim pinning, [[hl:]]+marked-option routing)
 → R1+R2 rulings (bagrut q3.ב flatten; pedagogical consistency invariant)
 → 5/5 ex-R3  Run C: k=5 confirmation (only residual: bagrut ex_sol 0.9231, trace-table header row)
 → R3 prompt fix (3.3.1 header-row exclusion) + foundations GT consistency strip
 → 5/5  (20260711-131057 close-out)
 → pipeline 3.1.0 (point-mismatches non-retryable) verified 13/13 valid (20260711-140120)
```

**Cost**: ~$0.16–0.22/doc for clean fixtures; the bagrut faithful-error doc was the
expensive tail (~$0.91–1.40/extraction) due to retries — the reason pipeline 3.1.0
made point-mismatches non-retryable, dropping suite mean/doc from ~$0.38 to ~$0.25.

**Ungated text-fidelity tail** (diagnostic, not failing): worst
`subquestion_text_fidelity_min` ≈ 0.28 / `text_line_recall_min` ≈ 0.07 at bagrut
q1.ב.1 (known item R4). This is measurement, not a gate failure.

### The key insight of the whole cycle

Of every "model failure" investigated, **more turned out to be instrument or GT
bugs than genuine model bugs** (csharp two-column gloss, foundations
highlight-drop + header inconsistency, hobby Tier-B 400, phantom render_loss from a
tokenizer artifact, the pedagogical invariant, the q3.ב phantom split) than model
issues (nesting, trace-table header row, marked-option misroute). "The instrument is
the prime suspect" is the operating assumption, not a slogan.

---

## 9. Open items handed back (not accuracy gaps)

1. **Retry-policy** — trigger armed and shipped as pipeline 3.1.0 (point-mismatch =
   non-retryable). Broader transport retry for the extraction `_call_llm` is still a
   gap (bagrut connection-error fragility = dominant loss mode at k=3).
2. **Tier-B transient-transport retry** — Tier B has no retry; one connection blip
   silently costs the `structural_mislabel` detection for that extraction.
3. **Latent GT** — bagrut q1.ב.1 solution carries a mid-text header line
   (sub-threshold, flagged for next GT audit).
4. **Ungated text-fidelity tail** — bagrut q1.ב.1 (R4).
5. **Parked convention rulings** — P-PARK-1 (SECTION-0 structure-faithfulness
   generalization, purchased against zero observed failure — do not add until a
   fixture breaks), P-PARK-2 ([IMAGE]-marker GT/prompt divergence, unexercised).
6. **`EMPTY_SQ_TEXT` on branch sub-questions** — the validator can fight the prompt's
   own SECTION-8 pure-splitter convention and burn a retry on a legitimate shape
   (candidate future change, pre-register first).

---

## 10. Rules that will bite you if ignored

1. **One variable per run.** Two changes at once = an unattributable result and a
   wasted (paid) run. This has been burned before.
2. **The instrument is the prime suspect.** A surprising metric is a scorer/GT bug
   until proven otherwise. Run `test_scoring.py` after any scorer edit.
3. **Never "fix" a failure by weakening the gate, tolerance, or GT.** A suspected GT
   typo or too-strict gate gets *surfaced with evidence*, never silently patched.
   (This is the §0.5 rule from CLAUDE.md, applied to the eval.)
4. **Worst-rubric over mean, always.** A mean of 0.9 hides a rubric at 0.5.
5. **k-repeats, worst-run comparison** — single runs on a non-deterministic model
   are uninterpretable.
6. **GT text is mechanically derived from the render, never hand-typed** (`GT_AUDIT.md`).
7. Every run/change/ruling goes in **RUNLOG.md** before the next run is planned.

---

## 11. The tracelog — debugging the LLM's thought process

`app/services/docx_v3/trace.py` is a **thin, harness-flexible tracelog** for the
extraction pipeline. Use it when a fixture fails and the score doesn't tell you
*why* — it captures the exact prompt, the raw model output, the reasoning-token
spend, the per-question point/selection **digest**, the validation issues that
fired, and the retry feedback, at every step.

### What it is (the design, in one idea)

A trace is a **tree of spans** with exactly two kinds, each a fixed schema:
- **`generation`** — one LLM interaction: prompt, params, parsed-output digest, raw
  output, usage `{input, output, reasoning, cached}` tokens, finish_reason.
- **`operation`** — one deterministic step: `render`, `validate` (the
  `ValidationIssue`s — *the "why a retry fired"*), `retry_decision` (the feedback
  text sent back), `build`, `pedagogical`.

**The harness decides the tree; the schema per span never changes.** A single
reasoning call with retries and a 3-step prompt chain are just different trees over
the same two schemas — so if the harness changes, only *where you open a span*
changes, never the log format, the reader, or your queries. It is injected exactly
like `on_progress` (§ the pipeline's seam): `NULL_TRACER` by default ⇒ **byte-identical
when off**, every tracer call best-effort/swallowed.

### How to run it

```bash
# off (default, zero overhead) | failures (full detail only for gate failures) | all
PYTHONPATH=. python -m tests.rubric_eval_suite.runner --config gpt-5.5 --repeats 5 --trace failures
```
Traces land in `results/<run>/traces/<fixture>_r<k>.jsonl`, with large payloads
(prompts, raw responses, the render) content-addressed into `traces/blobs/<sha>`.
`trace_id` (= `<fixture>_r<k>`) is stamped into `results.json` per trial — the thin
link from a failing row to its trace.

**Retain-on-failure (why it stays thin):** the skeleton (spans + attrs +
`ValidationIssue`s + tokens + the output digest) is *always* written; the heavy
blobs (full prompts, raw responses) are kept only when the trial **failed** the gate
(`--trace failures`) or always (`--trace all`). A passing run costs almost nothing.

### How to read one

```bash
PYTHONPATH=. python -m app.services.docx_v3.trace results/<run>/traces/<id>.jsonl
```
prints the indented tree with durations, tokens, and — inline — the validation
issues that drove each retry. Example:

```
- render [operation] 0.53s   blobs:{rendered_markdown}
- extract_loop [operation] 55.7s
  * llm_call [generation] 52.1s  finish_reason=stop in=9540 out=3741 reasoning=1025 cached=0
      blobs:{system_prompt, user_message, raw_response, additional_kwargs}
  - validate [operation]  attempt=1 n_issues=1
      · [EMPTY_SQ_TEXT] retryable=True q1.א has no task text
  - retry_decision [operation]  trigger_codes=['EMPTY_SQ_TEXT']  blobs:{feedback_out}
```

The **`output_digest`** on each `llm_call` (per-question `total_points` +
`selection_groups`) is the tool for point/selection bugs: it shows immediately
*which* question came back wrong and *on which attempt* — e.g. a question extracted
as 40 instead of 25, inflating achievable points.

### LangSmith

The LLM calls **auto-trace to LangSmith** when `LANGCHAIN_TRACING_V2` is set (via
LangChain). The tracer additionally **mirrors** the operation/validation spans to a
LangSmith run-tree (best-effort, guarded — degrades to no-op if the SDK differs), so
the same span model feeds both the local JSONL and the hosted view. The runner turns
the mirror on automatically when `LANGCHAIN_TRACING_V2` is truthy.

### What it captures (for debugging "what went wrong")

Per `llm_call`: system-prompt version + full prompt (blob), user message (blob),
raw response + `additional_kwargs` (where a reasoning *summary* appears, if the
provider surfaces one — the hidden chain-of-thought itself is never returned by
reasoning models), `input/output/reasoning/cached` tokens, finish_reason, the output
digest. Per `validate`: every `ValidationIssue{code, message, retryable}`. Per
`retry_decision`: the trigger codes + the correction feedback text. Plus per-step
wall-clocks. `reasoning_tokens`/`cached_tokens` also flow into `ExtractionMetrics`
(the eval instrument surfaces them).
