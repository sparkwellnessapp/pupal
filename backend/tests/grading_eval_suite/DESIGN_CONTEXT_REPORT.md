# DESIGN CONTEXT REPORT — the Test-Grading Eval Suite

**Purpose:** full context for the engineer who will design `grading_eval_suite` — the
third eval suite, and the one CLAUDE.md §15 names "the keystone AI-quality work."
This report documents the two existing suites' architecture, the patterns they earned
through recorded failures, the anti-patterns they shipped and later paid for, the
grading pipeline you will be measuring, and the open design decisions that are yours
to make (with recommendations, per §0.2: surface, don't decide).

**Written:** 2026-08-23, immediately after the model-registry normalization
(`../rubric_eval_suite/PLAN_model_registry_normalization.md`) unified both suites'
model interface — your suite adopts that interface on day one, not as a retrofit.

**Authority notes:** the two existing suites are governed artifacts — the
transcription suite by CLAUDE.md §17 (STOP list, owner-gated instrument), the rubric
suite by its RUBRIC_EVAL_PLAYBOOK. Your suite will need its own equivalent contract;
§10 lists what it must contain. Ground truth is ALWAYS owner-authored or
owner-ratified; the eval instrument is never edited to make a number pass.

---

## 1. The assignment (what CLAUDE.md §15 already commits to)

> **Eval suite (the keystone AI-quality work)** — a golden set of
> `(rubric, transcription) → teacher grade` triples, agreement metrics (points MAE,
> within-precision rate, per-criterion match, **confidence calibration**), and a
> regression gate keyed by `(model_version, prompt_version)`. Blocked on real
> teacher-graded data. This is the loop that turns "I built a grader" into "I built
> a grader I can improve." The per-outcome `flags`, the `was_overridden` provenance
> in `GradedTestContract`, and the cost/version stamps all exist to feed it.

Two product decisions are **gated on this suite existing**: bulk grade-approval
(deferred until the suite validates a high unedited-approval rate) and
confidence-triggered verification (threshold must come from measured calibration,
never guessed). Your suite is not a nice-to-have; it is the unblocking artifact for
both.

Also relevant: the grader currently runs `settings.openai_model` (default
**gpt-4o**) with prompt `grader-v1` — and has **never been evaluated**. There is no
baseline. The first honest k-run of your suite is itself a product milestone.

---

## 2. The landscape today — three units, two maturities

| Unit | Path | Measures | Maturity |
|---|---|---|---|
| Transcription suite | `tests/transcription_eval_suit/` *(sic — historical typo, kept)* | PDF → P1 perception → P2 segmentation vs two GT surfaces | Most mature: conjunctive gate + `check_goal.sh` ship gate, stage-attribution run modes, per-call `CallRecord` cost, batch/latency mode, trust-layer metrics, §17 governance |
| Rubric suite | `tests/rubric_eval_suite/` | DOCX → V3 extraction vs 5 golden `ExtractRubricResponse` GTs | Mature: conjunctive gate, render-vs-extraction loss attribution, faithful-teacher-error metrics (annotation/pedagogical match), latency instrument, tracelog; coarser cost (cumulative, not per-call) |
| Shared home | `tests/eval_common/` | — | New (2026-08-23): `models_registry.py` (ONE model identity/price/tier registry for all suites) + its invariant tests, incl. the offline dry-resolve gate over every suite's configs |

Both suites converge on the same skeleton, which your suite should inherit unless a
grading-specific reason says otherwise:

```
<suite>/
  ONBOARDING.md / docs         ← entry doc for future agents
  <PLAYBOOK>.md                ← the analysis contract (prime directives, gate semantics)
  RUNLOG.md                    ← append-only hard memory: every run, every variable change
  PREDICTIONS.md               ← pre-registered predictions, written BEFORE runs
  <GT CONVENTIONS>.md          ← GT authoring rules + rulings (owner-owned content)
  fixtures/ + benchmarks/      ← inputs + golden truths, paired by basename
  configs/*.json               ← experiment configs: model_key + knobs + ceiling + notes
  runner.py                    ← orchestrate → score → gate → report; cheap + authoritative modes
  scoring.py                   ← THE scorer: pure, no pipeline import, instrument-immutable
  gates.py                     ← conjunctive gate
  schemas.py                   ← stable results.json row type
  reporting.py                 ← results.json (machine) + summary.md (human) + per-fixture reports
  results/<ts>_<config>/       ← one dir per run, artifacts persisted as they arrive
  test_*.py                    ← the instrument's own guards (known-answer tests, policy pins)
```

---

## 3. The system under test — grading pipeline anatomy

Read these files before designing anything; line references verified 2026-08-23.

### 3.1 Data flow

```
GradingRubricContract (frozen)  ──┐
                                  ├─► gradable_compiler.compile()  ─► GradableTest (in-memory, CW-1 closed world)
TranscriptionContract (frozen) ───┘         │
                                            ▼
                              GraderAgent.grade(gradable_test)      ← THE nondeterministic stage
                                            │  one LLM call PER SCOPE, Semaphore(5), return_exceptions=True
                                            ▼
                              validate_scope_grading()  (pure)      ← closed-world recheck, Decimal bounds+precision
                                            │                          clamp, difflib sliding-window quote validation
                                            ▼
                              GradedTestDraft  (+ score_with_selection for the display score)
                                            │  teacher reviews/overrides (GRADING GATE)
                                            ▼
                              compile_graded_test()  (pure)         ← approval gate; recomputes selection; freezes
                              GradedTestContract  (was_overridden per outcome)
```

### 3.2 Facts your design leans on

- **The determinism boundary is exceptionally clean (§3.6).** Everything around the
  per-scope LLM call is pure and already unit-tested with **zero mocks**
  (`tests/services/test_gradable_compiler.py`, `test_graded_test_contract_compiler.py`,
  `tests/agents/test_grader_validator.py`, `test_selection_expectation.py`). The agent
  itself is tested with a mocked `agent._structured_llm.ainvoke`
  (`tests/agents/test_grader_agent.py`). **Your suite measures the LLM's grading
  judgment — not the validator, not the compilers.** Do not re-test what the
  zero-mock batteries pin; do exercise the real code path end-to-end so drift in it
  surfaces.
- **Grading unit = the scope** (`GradableScope`: a direct-criteria question or one
  leaf sub-question, full-path ids since PR-3). **Judgment unit = the terminal**
  (leaf criterion or sub-criterion). The LLM returns one `TerminalGrade` per terminal:
  `points_awarded` (float at the LLM boundary, Decimal everywhere after),
  `reasoning` (Hebrew), `quote_text` (verbatim evidence), `confidence` (0.0–1.0
  self-assessed **per terminal** — calibration measurement is feasible from day one).
- **Per-scope failure isolation is built in** (`_build_failure_result` /
  `_build_skip_result` in `grader.py`): a failed scope is a flagged zero-outcome
  (`graded_by="failed"`), a missing answer is `graded_by="skipped_no_answer"` +
  `FlagReason.NO_ANSWER`. `len(scope_outcomes) == len(scopes)` always (D3). Your
  scorer must treat these as *observations*, not crashes — a `failed` scope in a
  record is a validity question (transport artifact ⇒ invalid trial) but a
  `skipped_no_answer` is a legitimate grading fact to score.
- **Per-scope token capture exists** (`include_raw=True`; `ScopeOutcome.input_tokens/
  output_tokens`). This is *finer* than the rubric pipeline's cumulative metrics —
  your suite gets per-scope cost attribution for free. No cached/reasoning split, and
  no logprobs.
- **Provenance stamps exist on the draft**: `model_version` (= `settings.openai_model`),
  `prompt_version` (= `GRADING_PROMPT_VERSION`, currently `"grader-v1"`,
  `app/agents/grader/prompt.py:15`), both contract versions. The §15 gate key
  `(model_version, prompt_version)` is already in the artifact.
- **Selection scoring is a separate pure stage** (`app/services/selection_scoring.py`
  — read its docstring in full; it records the 50%-catastrophe history). The grade
  denominator is `contract.total_points`, NEVER re-summed; unchosen choose-k members
  are **excluded, not zeroed**; exclusion is derived state recomputed after overrides.
  Your metrics must respect this: **never re-derive a denominator**, and never score
  an `excluded_by_selection` scope as a wrong grade.
- **Awarded points have NO sum constraint** (§5 approval-gate note). Partial credit
  legitimately sums below possible. A "point-sum consistency" metric on awarded
  points would be wrong by design — the rubric suite's deliberate non-gating of
  `point_sum_consistency` is the precedent.
- **`parent_answer_fallback_scopes`** (`GradableTest`): leaf scopes that inherited an
  ancestor's answer because transcription segments to depth 1. Load-bearing for
  nested rubrics; its *rate* is an explicitly requested metric (it triggers the
  depth-2 segmentation follow-up, BACKLOG B-7).

### 3.3 Known defects in the system under test (measure around them, don't inherit them)

1. **The grader's transport policy is the codebase's documented worst offender**
   (CLAUDE.md §7 warning box): `ChatOpenAI` constructed with **no timeout, no
   `max_retries=0`** ⇒ hidden SDK retries × GA-3 retry = up to 6 unbounded calls per
   scope; `APITimeoutError` in `TRANSIENT_EXCEPTIONS` is a dead branch;
   `insufficient_quota` retried as transient. Fix is owned by **PR-7** (its Cloud
   Tasks migration) using the reusable `_transport_retry_*` from `docx_v3/pipeline.py`.
   **Your runner must not stack another retry layer around the agent** (the standing
   rule), but it needs its own *per-trial* resilience: one bounded re-run of a trial
   on retryable transport failure only (the transcription job-runner's pattern), and
   trial-level wall bounds so one hung scope cannot hang a k-run.
2. **A fourth split-brain price table, stale** (found 2026-08-23 during this
   research): `grading_runner.py:45-47` hardcodes gpt-4o at $5.00/$15.00 per Mtok;
   the registry's verified card is **$2.50/$10.00**. Production
   `graded_tests.total_cost_usd` is therefore computed from prices ~2× the verified
   ones. Your suite must compute cost via the shared `cost_usd` + registry card
   (never touch `_compute_cost`), and the discrepancy should be surfaced to the
   owner as its own finding — candidate follow-up alongside BACKLOG B-30a.
3. **No model-injection seam.** `GraderAgent.__init__` hardwires
   `ChatOpenAI(model=settings.openai_model, …)`. Model sweeps (the rubric suite's
   bread and butter) require either (a) an env-driven seam like the rubric runner's
   `EXTRACTION_LLM_*` hop — but `settings` is a cached pydantic object, so env
   mutation at runtime does NOT propagate the way `os.environ` does for
   `_get_llm_config()` — or (b) a constructor parameter. **This is a production-code
   change your plan must include as its own reviewed step** (see D6, §8). Until it
   lands, the suite can only evaluate the deployed pin.
4. **The grader is OpenAI-only** (direct `openai` exception classes, `ChatOpenAI`).
   Multi-provider sweeps are a *later* capability; do not build for them
   speculatively (the rubric suite added providers one evidence-driven branch at a
   time).

---

## 4. The pattern catalog — what the two suites earned, and the incident behind each

These are not style preferences. Each was paid for. Your design should either adopt
each pattern or explicitly argue why grading differs.

**P1 — Conjunctive gate, worst-fixture-over-mean.** A record passes iff ALL criteria
hold; the headline aggregate is the worst fixture, never the mean. *Why:* partial
improvement masking a regression must not pass; "a single catastrophic document hides
inside a healthy average" (both playbooks; the Vertex A/B kill criterion is written
in exactly these terms).

**P2 — Validity before significance.** Truncated/unparseable/transport-failed trials
are `valid=False`: excluded from accuracy aggregates, failing the gate outright.
*Why:* the rubric suite's truncation guard exists because a truncated extraction
scores plausibly-low and silently poisons comparisons. Grading analog: a trial with
any `graded_by="failed"` scope from transport is invalid; a *content* parse failure
is a real observed behavior — decide its class explicitly (see D8).

**P3 — Provenance completeness.** A result is a function of
`(fixtures, config, prompt_version, model_version, pipeline/code version)` — all
stamped in `results.json`. Plus `suite_hash` (content hash over instrument + goldens,
configs deliberately excluded, shared registry deliberately INCLUDED) and
`registry_as_of` + `model_key` + the `models` block. *Why:* the pedagogical-field
drift had to be reverse-engineered from missing keys; the hash makes a mixed tree
announce itself. Note grading has no `PIPELINE_VERSION` constant — the closest
analogs are `GRADING_PROMPT_VERSION` + `GradedTestDraft.schema_version`; your plan
should propose a code-version stamp for the grader (a `GRADER_VERSION` constant is a
one-line production change worth requesting).

**P4 — The shared model registry (adopt on day one).** Configs name a `model_key`
only; `tests/eval_common/models_registry.py` owns identity/price/tier; cost via the
ONE `cost_usd(Usage, PriceCard)`; unknown key fails offline via the eval_common
dry-resolve test — **extend `_config_model_keys()` in
`tests/eval_common/test_models_registry.py` to read your configs dir in your first
PR.** *Why:* the rubric suite's config-owned prices silently disabled its cost gate
for two configs (F1), let provider leak from ambient env (F2), and let typos reach
the provider as 4xx (F3). All fixed 2026-08-23; do not regress the pattern.

**P5 — Instrument immutability.** The scorer/gate/thresholds are never edited to
make a number pass; "answering a grading question with an instrument change is
forbidden" (§17.7 — the same failure class as loosening an invariant, §0.5). A
suspected GT error is SURFACED with evidence, never silently fixed. Your suite needs
its own STOP list (§10).

**P6 — One variable per run; kill criterion before the run.** Two changes at once
are unattributable; runs were burned learning this (rubric RUNLOG's first entry is a
contaminated 2-variable run). PREDICTIONS.md holds pre-registered predictions — the
Vertex A/B prereg (`../transcription_eval_suit/PREREG_vertex_migration_2026-08-20.md`)
is the current gold standard of the form: single variable, held-fixed table,
falsifiable prediction, signed kill criterion, "what this run does NOT license."

**P7 — RUNLOG.md as hard memory, append-only.** Context compaction is assumed; every
run and every variable change gets an entry (hypothesis, variable, pre/post k-results,
attribution, decision, cost). An analysis isn't done until its entry exists.

**P8 — Repeats because temp-0 is not deterministic.** k≥5 is the bar (owner may
amend for budget); a change is confirmed only if it holds across all repeats; compare
worst runs. Grading raises the stakes: per-terminal award variance across repeats is
not just noise to average over — it is itself a product metric (see §6.4).

**P9 — Cost-tiered run modes + attribution identity.** The transcription suite
iterates on near-free `p2_only` and spends `check_goal.sh` only to confirm; its
attribution identity (`p2_only` high + e2e low ⇒ P1's fault) prevents fixing the
wrong stage. Grading analogs: score-cached-drafts mode ($0), single-scope/
single-fixture modes (cents), full k-run (dollars). Design the cheap diagnostic
FIRST; see D9.

**P10 — Per-trial failure isolation + artifacts-as-they-arrive.** One trial's crash
becomes an INVALID record, never a lost run; predictions/drafts persist to
`results/<run>/` as produced, so a crashed run leaves evidence and a scorer change
re-scores cached outputs for $0 (`score_only`). *Why:* "twice a conclusion had to be
INFERRED because predictions vanished" (rubric runner comment). For grading:
**persist every produced `GradedTestDraft` JSON per trial** — it is your re-scoring
substrate and your qualitative-review substrate.

**P11 — Machine + human artifact split.** `results.json` (stable schema — dataclass
with `slots=True` so a typo'd field is an `AttributeError`, not silent drop) +
`summary.md` (gate verdicts with named reasons, worst fixture) + per-fixture reports
that enforce the read-the-diffs-by-hand rule. For grading, the per-fixture report
should render terminal-by-terminal: GT award | model award | Δ | confidence |
quote-validity | flags — the review surface for deciding the *next* change.

**P12 — GT encodes the product's philosophy, not just correct answers.** The rubric
suite's GT encodes faithful-capture: a teacher error must be *reproduced and
flagged*, and the never-reconcile tripwires (annotation_match + pedagogical_match)
caught grok silently "fixing" a teacher's arithmetic — the product's foundational
invariant, tested as a metric. The grading equivalent (§6.3) is just as important:
the GT must encode what a *correct grader* does with garbled transcription, missing
answers, and evidence-less awards — review-first behaviors, not just point values.

**P13 — The suite exercises production code, one definition.** The transcription
suite imports the production pipeline through shims; the rubric suite drives the real
`extract_rubric_from_docx`. Your suite must call the REAL `gradable_compiler.compile`,
REAL `GraderAgent.grade`, REAL `validate_scope_grading` (inside the agent), REAL
`score_with_selection` — never a reimplementation. The only fake allowed anywhere is
the LLM in the *suite's own unit tests* (mock `agent._structured_llm.ainvoke`, the
established target).

**P14 — Config = experiment record.** Loud failure on unknown/legacy keys; `notes`
carries the experiment rationale and verdicts (see `grok-4.6.json` for the form);
dead fields are deleted, not tolerated.

**P15 — Windows-proof I/O.** Every `read_text`/`open` passes `encoding="utf-8"`;
console prints are ASCII (a `→` in the rubric runner's final print crashed the
process after artifacts were written, 2026-08-23; BACKLOG Family D is 8 tests of the
same class). Paths via `Path(__file__)`, never CWD-relative.

**P16 — Statistics honesty rules.** Median/min/max for per-doc latency (p95 only in
batch mode where it's honest); subset runs stamped NON-PROMOTABLE (`--only` prints
the screening banner and provenance records the subset); cold-start marked on the
first record.

---

## 5. Anti-pattern ledger — shipped, paid for, fixed (or still open)

| # | Anti-pattern | Where it bit | Status |
|---|---|---|---|
| A1 | Config-owned prices (split brain) | rubric configs — silently disabled cost gate (F1), ambient provider leak (F2), typo-as-4xx (F3) | Fixed 2026-08-23 (registry). **A1 lives on in `grading_runner._compute_cost` — stale prices in production** (§3.3.2) |
| A2 | Cost blindness of secondary LLM calls | Tier-B adjudicator lacks `include_raw` ⇒ every rubric cost number is a lower bound (F5, BACKLOG B-30a) | Open. Grading is CLEAN here (per-scope capture exists) — keep it that way if the suite adds any auxiliary LLM call (judge, verifier) |
| A3 | Cached tokens measured then ignored in cost | rubric legacy formula (F4) | Fixed. Grading captures no cached split at all — acceptable v0, note it |
| A4 | A check nobody can pass | INV-6 fired on 100% of criteria → 100% auto-ack → click-through training | Demoted to INFO. Grading trap: gating on `confidence` or flag-rates before a measured distribution exists would recreate it — thresholds are pre-registered from data, never guessed (the rubric suite's ungated text-fidelity metrics are the template) |
| A5 | Retry layers stacking invisibly | grader's 6 unbounded calls/scope; the 1736s extraction attempt | PR-2 fixed extraction; PR-7 owns the grader. Suite rule: never wrap the agent in another retry |
| A6 | Verifier layer with ~100% false positives | cross-reader flags retired in prod (cheap readers "fixed" faithful student errors) | Standing lesson for any LLM-judge stage your suite might add: eval-gate the judge itself first (B-24 precedent) |
| A7 | Silent GT edits to fit the model | never shipped — §17.7 exists because the temptation recurs | Your STOP list must forbid it explicitly |
| A8 | Single-exam coupling hardcoded in the runner | transcription: one `--exam-spec` + `JAVA_BAGRUT` at 4 sites (B-30f) | Open there. **Design yours per-fixture from day one**: grading fixtures inherently span exams (a fixture = one rubric + one transcription), so the pairing must be a per-fixture manifest fact, not a run-level flag |

---

## 6. What the grading domain CHANGES vs the existing suites

### 6.1 The golden triple, and where its parts already exist

A fixture is `(rubric contract, transcription contract, teacher grade GT)`.

**Finding (verified 2026-08-23): the first two thirds of a 5-fixture seed set
already exist in the sibling suites.** The five transcription draft-GTs
(`../transcription_eval_suit/draft_benchmarks/{dan_basiuk, din_ezra, moran_aharon,
omer_gelber, yonatan_basiuk}.md`) are five real students' answers to the **Hobby/
TvShow exam**, and `../rubric_eval_suite/benchmarks/hobby_tvshow.json` is that
exam's type-valid rubric GT (`ExtractRubricResponse` — compilable to a
`GradingRubricContract` via the real `ContractCompiler`). Five genuine
`(rubric, transcription)` pairs, assembled from owner-ratified GT, are one
compile-step away. **The only missing ingredient is the teacher's grade for each —
five hand-graded tests from the owner unblocks the seed set.** (§15's "blocked on
real teacher-graded data" is therefore a ~5-artifact ask, not a data-pipeline
project.) Caveats: (a) hobby_tvshow contains a deliberate teacher error (q2 —
the FC worked example) — verify the GT *compiles* before assuming; if a blocking
ERROR annotation fires, the seed rubric needs the teacher-corrected variant, an
owner decision to surface, not to make; (b) reusing sibling GT means your
`suite_hash` should cover those files too, or snapshot them in (see D3).

**The second GT source is the production flywheel** — designed-in, per §15:
`GradedTestContract` stamps `was_overridden` per terminal outcome, so every teacher
approval yields a labeled record: the draft is the model's answer, the approved
contract is the teacher's truth, the diff is the label. Design your GT format so
harvested triples and hand-authored triples are the same shape. **Bias warning to
document prominently:** an unedited approval is only a true "model was right" label
if teachers actually review before approving — the bulk-approve deferral exists
precisely because that rate is unvalidated. Early flywheel data over-represents
agreement; treat harvested labels as a distinct provenance class
(`gt_source: "teacher_manual" | "production_approval"`) and gate only on the manual
class until the owner rules otherwise.

### 6.2 The metric set (from §15 + the artifacts that exist to feed it)

Committed by §15: **points MAE** (per-terminal and per-test), **within-precision
rate** (|Δ| ≤ `numeric_policy.precision`, default 0.25), **per-criterion match**
(exact-award agreement per terminal), **confidence calibration** (per-terminal
confidence vs empirical correctness — reliability curve / ECE; this is the metric
the confidence-verification feature is waiting on).

Strongly implied by the artifact design (the "flags are the richest eval signal"
note, §6 of CLAUDE.md): **flag quality** — precision/recall of `NO_ANSWER`,
`CLOSED_WORLD_VIOLATION`, bounds-clamp, quote-not-found flags vs GT; **quote
validity** — rate of evidence quotes that actually appear in the student answer
(the validator's difflib status is recorded per outcome, and a grader that awards
points on fabricated evidence is a trust failure regardless of the points being
right); **fallback + skip accounting** — `parent_answer_fallback_scopes` rate,
skip-vs-GT agreement (did the model skip what the teacher skipped?).

Plus the standard rails: cost/trial vs a ceiling (registry-priced), latency
(median/max per fixture), retry/failure counts, and **repeat stability** (§6.4).

Direction-of-error matters pedagogically: over-award and under-award are not
symmetric for teacher trust. Report signed bias alongside MAE (ungated until a
distribution exists — A4).

### 6.3 GT must encode grading *philosophy*, not just numbers (the P12 analog)

The teacher-grade GT needs per-terminal: awarded points, and (at minimum) whether
evidence exists in the answer. The conventions doc — which the owner authors with
you, before the first benchmark — must rule on: how the GT records "the teacher
gave credit despite garbled transcription" vs "withheld credit"; whether GT encodes
acceptable-award *ranges* or point values only (recommend: point values; ranges are
a scorer complication to earn with evidence); how a scope the teacher marked
un-gradable is encoded (the review-first principle: the correct model behavior is a
low-confidence flag, not a guess — and the GT must make that scoreable). This is
the exact analog of the rubric suite's faithful-error tripwires: the metrics that
verify the grader *escalates instead of guessing* are the product's trust floor.

### 6.4 Non-determinism is a first-class metric here, not just noise

The suites treat repeats as variance to survive. For grading, award stability
across k repeats on identical input is itself a product property (a teacher who
sees the same answer get 2 then 3.5 stops trusting the system). Report per-terminal
award spread and per-test total spread as headline diagnostics (ungated v0 — A4).

### 6.5 Fixture pairing is per-fixture by nature (the B-30f lesson, pre-applied)

Unlike transcription (one exam per run today), a grading run naturally mixes exams:
each fixture names its own rubric + transcription. Encode the triple per fixture —
recommend a per-fixture manifest (`fixtures/<name>.json` naming the three artifact
paths + provenance) rather than basename-magic across three directories and two
sibling suites. This is the one place the sibling convention (pure basename pairing)
genuinely doesn't stretch; say so in your plan rather than forcing it.

### 6.6 Selection ("choose k of N") must be in the seed set early

The catastrophic-denominator history (§3.2) lives exactly at grading. At least one
fixture must exercise selection groups so the suite pins: excluded scopes not
counted as errors, denominator = contract total, `graded_by="excluded_by_selection"`
handled. `employee_course_select1` is the rubric suite's selection fixture — a
future transcription for it is the natural second exam (and your suite should be
*born* multi-exam per §6.5, so this is cheap).

---

## 7. Cross-suite integration points (concrete, day-one)

1. **Registry**: configs carry `model_key`; costs via
   `cost_usd(Usage(...), spec(key).price)`; add your configs dir to
   `tests/eval_common/test_models_registry.py::_config_model_keys` (the dry-resolve
   gate) in the same PR that creates your first config.
2. **`model_key` as the join key**: stamp `model_key` + `registry_as_of` + the
   `models` block into provenance and per-record rows exactly as the other two do —
   this is what makes per-model metrics roll up across all three suites (the
   B-30d rollup CLI is waiting on exactly this).
3. **Sibling GT reuse** (§6.1): compile `hobby_tvshow.json` through the real
   `ContractCompiler`; parse draft-GT text through the transcription suite's
   loader or a snapshot (D3).
4. **Naming**: recommend `tests/grading_eval_suite/` (matches `rubric_eval_suite`;
   do not propagate the `_suit` typo).
5. **Docs cross-pointers**: on landing, add your suite to the landscape notes the
   way B-30f pointers were threaded (both sibling RUNLOGs / onboarding docs know
   about cross-suite couplings; keep that discipline).

---

## 8. Open design decisions for YOUR plan (surface these; recommendations attached)

- **D1 — GT format & authoring workflow.** Markdown-per-fixture (human-authorable,
  like transcription GT) vs typed JSON (machine-checkable, like rubric GT).
  *Recommendation:* typed JSON mirroring the terminal-outcome shape (award +
  evidence-exists + optional teacher note per terminal id), with a small builder
  that pre-populates terminal ids from the compiled contracts so the owner fills
  only judgments — plus a `check_gt_consistency`-style guard (ids match contract,
  awards within bounds/precision).
- **D2 — Trial input: contracts or sibling drafts?** Store compiled contract JSON
  snapshots in your `benchmarks/`, or compile from sibling GT at runtime.
  *Recommendation:* snapshot the compiled contracts into your suite (frozen,
  hash-covered, immune to sibling edits) + record the source + compiler version in
  the fixture manifest; a `rebuild_fixtures.py` tool regenerates them deliberately.
- **D3 — `suite_hash` scope** given cross-suite inputs. *Recommendation:* hash your
  instrument + your snapshots (D2 makes sibling drift a non-issue) + the shared
  registry (the rubric suite's precedent).
- **D4 — Gate criteria and thresholds.** Which metrics gate v0 vs report-only?
  *Recommendation:* v0 gates only validity + cost ceiling + the behavioral
  tripwires that need no distribution (e.g. zero fabricated-evidence awards, no
  closed-world violations surviving, selection exclusion honored); MAE/calibration/
  stability start UNGATED-WATCHED (A4), with thresholds pre-registered after the
  first k≥5 baseline — the §15 "validated high unedited-approval rate" question is
  then answered with data.
- **D5 — Per-terminal alignment identity.** Terminal ids come from the contract on
  both sides (GT authored against the same contract), so alignment should be exact
  id-match — no fuzzy alignment layer (a major simplification vs the rubric suite's
  criterion matcher; say it explicitly and assert it).
- **D6 — The model seam (production change).** Constructor injection
  (`GraderAgent(model=..., api_key=...)`) vs env-hop. *Recommendation:* constructor
  param defaulting to `settings.openai_model` — smallest honest change, testable,
  no cached-settings trap; ship it as its own reviewed step with an exact-dict
  construction test (the `test_llm_policy.py` pattern), and only then sweep models.
  Bundle the `GRADER_VERSION` constant (P3) into the same small PR.
- **D7 — Runner resilience vs PR-7.** Until PR-7 bounds the agent, decide the
  trial-level wall bound + one-re-run policy (P9/A5). *Recommendation:* per-trial
  `asyncio.wait_for` at the runner + one re-run on retryable transport only,
  RUNLOG-noted; revisit when PR-7 lands.
- **D8 — Validity taxonomy for grading.** Transport failure ⇒ invalid trial;
  but a *parse* failure (`parsing_error`) at temp 0 is deterministic model behavior
  — arguably a scored defect, not an invalid trial. *Recommendation:* score it as a
  failed scope (it's what production teachers would see) but track its rate as its
  own headline metric; owner ratifies.
- **D9 — The cheap diagnostic mode.** *Recommendation:* `--scopes` (grade a subset
  of scopes of one fixture) + `score_only` over cached drafts; full-fixture k-runs
  are the authoritative tier. Also decide k for the baseline (k≥5 bar, owner may
  amend for budget as precedented).
- **D10 — Where the harvested-flywheel importer lives** (later phase; the schema
  hooks — `gt_source` — are cheap now, the importer is not v0).

---

## 9. Process requirements for the implementation plan itself

The plan you write is subject to the repo's standing discipline:

1. **Plan before code** (§0.1): state the problem, the file changes, and every open
   decision (§8) with a recommendation; owner approves before implementation.
   Production-code changes (D6 seam, `GRADER_VERSION`, and *not* touching
   `_compute_cost` without a ruling) are flagged as their own steps.
2. **Write the suite's contract docs in the same PR as the code**: ONBOARDING,
   PLAYBOOK (with the STOP list: no GT edits, no scorer edits to pass, no threshold
   moves without pre-registration, no model-tier escalation without owner), GT
   CONVENTIONS (owner co-authored), empty RUNLOG + PREDICTIONS seeded with the
   baseline-run prediction.
3. **The instrument ships with its own guards**: a known-answer test (GT graded
   against itself scores perfect and passes the gate), injected-error tests (each
   metric catches its designed failure), a golden self-pass, policy pins with
   exact-dict assertions, and the eval_common dry-resolve extension. Zero real API
   calls in `pytest -q`.
4. **Baseline before iteration**: the first spend is a k≥5 run of the deployed pin
   (gpt-4o + grader-v1) on the seed fixtures, pre-registered in PREDICTIONS.md.
   Everything after is one-variable-per-run against it.
5. **Sanity gates**: `python -c "import app.main"`, `pytest --collect-only`, both
   sibling batteries untouched (their baselines: transcription 133 passed/1 skipped;
   rubric 8 known Family-D failures, nothing else).

---

## 10. Reading list (ordered)

| Priority | Artifact | Why |
|---|---|---|
| 1 | CLAUDE.md §3.6, §4, §5, §6, §7 (grading agent + selection scoring), §15 | the commitments your suite serves |
| 2 | `app/agents/grader/` (all four files, ~1000 lines) | the system under test |
| 3 | `app/services/selection_scoring.py` docstring; `app/services/gradable_compiler.py`; `app/services/graded_test_contract_compiler.py` | the pure surround + the denominator history |
| 4 | `app/schemas/gradable.py`, `graded_test_draft.py`, `graded_test_contract.py` | the artifact shapes (incl. `was_overridden`, `counted_in_total`) |
| 5 | `../rubric_eval_suite/ONBOARDING.md` + `RUBRIC_EVAL_PLAYBOOK.md` + `gates.py` + `schemas.py` + `runner.py` | the closest structural template (same "drive real pipeline, score vs typed GT" shape) |
| 6 | `../transcription_eval_suit/transcription_eval_suit_docs.md` §5–§12 + `PREREG_vertex_migration_2026-08-20.md` | gate design, run modes, instrument-suspicion history, the prereg gold standard |
| 7 | `../rubric_eval_suite/PLAN_model_registry_normalization.md` + `tests/eval_common/` | the shared model interface you adopt + §9's fixture-coupling analysis |
| 8 | `tests/agents/test_grader_agent.py`, `test_grader_validator.py`, `tests/services/test_gradable_compiler.py`, `test_selection_expectation.py`, `test_grading_runner.py` | what is already pinned (don't re-test), and the established LLM-mock seam |
| 9 | Both RUNLOGs (skim for entry form + failure history) | the process you're inheriting |
