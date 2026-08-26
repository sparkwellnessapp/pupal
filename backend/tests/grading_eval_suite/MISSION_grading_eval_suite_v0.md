# MISSION — Grading Eval Suite v0 (build)

**Owner:** Noam · **Status:** RATIFIED design → implementation mission
**Audience:** the coding agent. Required reading before any file is touched, in order:
`tests/grading_eval_suite/DESIGN_CONTEXT_REPORT.md` (yours; §10 reading list applies in full), then this spec. Where the two disagree, **this spec wins** — it post-dates the report and encodes the owner's rulings.
**Suite home:** `tests/grading_eval_suite/` (naming per report §7.4 — do not propagate `_suit`).

---

## 0. Purpose

Build the instrument that makes *"grader-v1 on gpt-4o grades at the solid-competent-teacher floor"* falsifiable. CLAUDE.md §15 commits to this suite; bulk-approval and confidence-triggered verification are blocked on its outputs. v0 ends with: a working, guarded instrument; five blind-authored GT fixtures; and one pre-registered baseline k=5 run of the deployed pin. **No grader redesign, no model sweep, no production code changes in this mission.**

---

## 1. Ratified rulings (the spec's constitution)

| ID | Ruling |
|---|---|
| **R1** | **Blind GT is non-negotiable for Tier-A.** The owner authors GT from rubric + transcription only, never having seen grader output for that fixture. Mechanically enforced by sequencing: **no `grade`-mode run on a fixture until its GT file is committed** (loader refuses to score a fixture whose GT commit postdates any cached draft for it — implement as a timestamp/provenance check, and the runner refuses `grade` mode if GT is absent). |
| **R2** | **The judge is diagnostic-only.** Never a gate, never the scorer-of-record. k=3 samples, majority verdict, splits flagged. Anthropic frontier reasoning model (registry-carded before first judge run); **never Gemini** (production quota is untouchable). Promotion to any gating role is pre-registered: n≥50 Tier-A fixtures AND judge–owner agreement ≥ a bar set at bootstrap. |
| **R3** | **GT referent = the draft-GT transcription text** (the faithful transcription), which is exactly what production grading consumes post-review. GT is authored against the *compiled corrected rubric contract* (H1) and pinned to its hash. |
| **R4′** | **Two-level tolerance.** Terminal: `|Δ| ≤ numeric_policy.precision` (0.25 on this exam) → `terminal_within_precision_rate`. Test total: `|Δ_total| ≤ 1.0` → `shippable_grade_rate` (owner's number). Both Tier-2, ungated-watched. |
| **R5/H1** | **hobby_tvshow: grade against the teacher-corrected variant.** Agent produces the corrected rubric (fix_proposal applied to the q2 sum mismatch), presents the **diff vs original GT + compile proof** to the owner, owner ratifies, then snapshot. Provenance recorded: `derived_from`, correction description, `ratified_by`, date. GT authoring waits for this ratification. |
| **R6/D8′** | Parse failure (`parsing_error` at temp 0) is **scored as the failed scope production would show**, AND its rate is a Tier-3 headline with a pre-declared escalation: if rate > 0, bucket the affected fixtures before any model comparison (deterministic model behavior on specific inputs confounds sweeps). |
| **R7** | Baseline approved: **k=5 × 5 fixtures of the deployed pin (gpt-4o + grader-v1)**, ~150 calls, ~$1, pre-registered in PREDICTIONS.md before the run. |
| **P1** | **Owner prior registered in PREDICTIONS.md at seed:** *"gpt-5.6-terra @ reasoning=high will dominate the grading accuracy×cost×latency frontier"* (Noam, 2026-08-24, pre-baseline). Falsified/confirmed only by a future sweep under registry discipline. |
| **D1–D10** | As recommended in the report, with amendments already merged into this spec: D1 (+`evidence_exists`, `ungradable` encoding), D2, D3, D4 (= §6 tiers), D5 (+contract-hash pin), D6 (**deferred to step 3**, seam widened to model **and params** incl. `reasoning_effort`), D7, D8→R6, D9 (k=5), D10 (schema hook only). |

---

## 2. Scope fence

**In scope:** everything under `tests/grading_eval_suite/`; one edit to `tests/eval_common/test_models_registry.py::_config_model_keys` (dry-resolve registration, same PR as the first config); the suite's docs (§10).
**Out of scope — hard STOPs:** any file under `app/` (including `_compute_cost`, the D6 seam, `GRADER_VERSION` — all step-3 territory); sibling suites' GT or code (read + snapshot only); Gemini/Vertex anywhere; the flywheel importer (schema hook `gt_source` only); multi-provider scaffolding; PDF→grade e2e mode; any threshold gating of Tier-2/3 metrics.

---

## 3. Architecture

**Primary mode `grade` (authoritative):** compiled `GradingRubricContract` + gold `TranscriptionContract` → **real** `GraderAgent` → real validator → real `selection_scoring` → score vs GT. This *is* the production-realistic surface (the transcription gate guarantees teacher-approved text in production). Text-only; ~$0.03 and ~5 s per test expected. k≥5 is the authoritative tier; k=1 is labeled PROVISIONAL in every artifact it touches.

**Satellites:** `score_only` (re-score cached drafts; free scorer iteration; the mode used for all instrument debugging); `--scopes` (subset of one fixture, diagnostic); `judge` (separate offline pass over stored disagreement records — never inline with grading; §8).

**Explicitly absent:** e2e-from-PDF (perception is the transcription suite's jurisdiction; coupling recreates the attribution problem the two-phase architecture exists to prevent).

---

## 4. Fixture pipeline (Phase B, gated on H1)

- **F0** — Compile `../rubric_eval_suite/benchmarks/hobby_tvshow.json` through the real `ContractCompiler`. Expected: the q2 mismatch blocks. Apply the fix_proposal → corrected variant → **surface diff + compile proof to owner → ratification (H1)** → snapshot `benchmarks/contracts/hobby_tvshow_corrected.contract.json` with provenance.
- **F1** — Converter: sibling draft-GT markdown (`=== Q{n}.{sub} ===`) → `TranscriptionContract` JSON (`(question_number, sub_question_id)` keys, full-path ids). Deterministic; unit-tested; **parity guard** against the transcription suite's own loader on all five docs (byte-identical answer text or the run aborts).
- **F2** — Snapshot the five transcription contracts into `benchmarks/transcriptions/` (D2: frozen, hash-covered, immune to sibling edits). `rebuild_fixtures.py` regenerates deliberately, never implicitly.
- **F3** — Per-fixture manifest `fixtures/<name>.json`: paths to the three artifacts + provenance (`gt_source: teacher_manual`, source suite paths, compiler version, contract hashes). Per-fixture pairing is the law (B-30f pre-applied); no basename magic.
- **F4** — GT builder: reads the compiled contract, emits a GT skeleton with **every terminal id pre-populated** and judgment fields empty. Owner fills judgments only.
- **F5** — Owner blind-grades five tests (R1). Estimated ~120–150 terminal judgments.

**Registered seed-set gaps (report §6.6 + design session)** — recorded in ONBOARDING so nobody mistakes n=5-one-exam for generalization: no selection-group exam (first expansion: `employee_course_select1` transcription); no depth-2 nested rubric (parent-fallback path unexercised); no fluent-but-wrong answer; no all-blank test. Gate ratification requires n≥10 across ≥2 exams. Note: the baseline doubles as the multi-scope smoke (state-report U2/G-21) — say so in the baseline report.

---

## 5. Ground truth

**Schema (typed JSON, D1):** header `{fixture, rubric_contract_hash, transcription_contract_hash, gt_source, authored_by, authored_at, blind: true}`; per terminal `{terminal_id, awarded: Decimal-string, evidence_exists: bool, note?: str}`; per scope optional `{ungradable: reason}` — the encoding for "correct model behavior is a low-confidence flag, not a guess."

**Loader guards (fail loud):** totality (every contract terminal covered exactly once — the D3-analog); bounds `0 ≤ awarded ≤ possible`; precision-grid membership; contract-hash match (a recompiled rubric cannot silently invalidate the GT authored against it); `blind: true` required for `gt_source: teacher_manual`.

**Totals:** derived by running GT terminals through the **real `selection_scoring`** — never hand-summed; eval totals and production totals share semantics by construction. Never re-derive a denominator; never score an `excluded_by_selection` scope as an error.

**`GRADING_GT_CONVENTIONS.md`** — agent drafts the skeleton; owner rulings fill it *before* F5. Must contain: **C-1** credit-despite-garbled-transcription policy; **C-2** the `ungradable` encoding and when to use it; **C-3** point-values only (ranges deferred until judge-J3 produces `both_defensible` evidence — R4′ note); **C-4** grade-boundary set for the flip metric (default proposal `{55, 65, 75, 85, 95}`, pass line 55 certain; owner confirms or amends); **C-5** how `evidence_exists=false` interacts with non-zero awards in GT (teacher gave credit without quotable evidence — legal, but recorded).

---

## 6. Metrics & gates

| Tier | Contents | Status |
|---|---|---|
| **0 — Validity** | transport failure ⇒ invalid trial (excluded, counted); per-trial wall bound hit ⇒ invalid; provenance completeness | precondition for reading anything |
| **1 — Tripwires** | zero non-zero awards on `not_found` evidence (**fabricated-evidence rule**); zero closed-world survivals; selection exclusion honored; skip-agreement on GT-`ungradable`/empty answers (model must skip/flag, not guess); registry-priced cost/trial ≤ ceiling (default **$0.10/test**, owner-adjustable at step 3) | **gate from run one** — no distribution needed |
| **2 — Agreement** | per-terminal signed Δ, MAE, `terminal_within_precision_rate` (0.25); exact-rate (Δ=0); per-test `total_Δ`, `shippable_grade_rate` (≤1.0, R4′); `grade_boundary_flip_rate` (C-4 set); **`edit_burden`** = count(terminal \|Δ\|>0.25) + count(non-zero award on unverified evidence) per test | **UNGATED-WATCHED**; thresholds pre-registered only after the baseline distribution exists |
| **3 — Diagnostics** | repeat stability (per-terminal award spread, per-test total spread across k); confidence calibration (reliability curve + ECE, n-flagged); parse-failure rate (R6 escalation); `parent_answer_fallback` rate; quote status distribution (exact/fuzzy/not_found); per-scope cost & latency (median/max); judge taxonomy distribution (once §8 runs) | reported every run |

**Standing analysis rules (into the PLAYBOOK):** worst-test over mean, always; per-test **`compensating_error` flag** whenever `|total_Δ|` is small while Σ|terminal Δ| is not — total-level agreement is never trusted alone; read at least two per-fixture terminal tables by hand every run; n<10 ⇒ every rate is PROVISIONAL and stamped so.

---

## 7. Runner & validity

k configurable, baseline k=5. Per-trial `asyncio.wait_for` wall bound (**300 s default** — the SUT has no timeout of its own; G-3 is not this mission's to fix, only to survive). Exactly **one** re-run per trial, on retryable transport failure only, RUNLOG-noted (D7) — **no retry layer around the agent beyond this** (the standing rule; the SDK already hides retries). Validity taxonomy: transport/wall ⇒ invalid trial; `parsing_error` ⇒ **valid** trial scored per R6; `graded_by="failed"` scope inside an otherwise-valid trial ⇒ validity question — transport artifact invalidates, content failure scores. A `skipped_no_answer` is a grading fact, scored against GT.

---

## 8. The judge (offline pass; builds after the baseline exists)

Input: stored disagreement records (terminal-level, |Δ| > 0.25) and a sample of agreements. Judge sees: rubric terminal (description + points), student answer text, AI `{awarded, reasoning, quote, confidence}`, GT `{awarded, note}`. Output schema per item: `verdict ∈ {ai_too_harsh, ai_too_lenient, rubric_misread, evidence_missed, evidence_fabricated, transcription_artifact, gt_questionable, both_defensible}` (disagreements) or `{sound_reasoning, right_answer_wrong_reason, evidence_mismatch}` (agreement audit) + one-sentence rationale. `JUDGE_PROMPT_VERSION` from day one; raw outputs stored; k=3, majority, splits flagged, never averaged.

**Bootstrap:** owner hand-labels the first ~20 disagreement classifications (he reads those diffs anyway); judge–owner agreement reported **before any judge label is used in analysis**; the promotion bar (R2) is then pre-registered in PREDICTIONS.md. Judge cost is registry-priced and reported per run like any other spend.

---

## 9. Provenance & artifacts

`results.json` (stable schema): `suite_hash` (instrument + snapshots + shared registry — D3), `model_key` + `registry_as_of` + `models` block (the cross-suite join keys), `GRADING_PROMPT_VERSION`, config, k, per-record rows (fixture, trial, validity, per-terminal scores, flags, tokens, cost, latency, `finish_reason`-equivalents), aggregates with `worst_test`, `n_provisional` stamp. `summary.md` — the human read, worst-test first. `report_<fixture>.md` — the full terminal table: `gold | awarded | Δ | quote_status | confidence | reasoning(He)` — the manual-review companion; it is the artifact the read-two-by-hand rule consumes.

---

## 10. Instrument guards & docs (same PR as the code)

Guards: **known-answer self-pass** (GT graded against itself scores perfect and passes Tier-1); **injected-error tests** — one per metric, proving each catches its designed failure (a fabricated quote, a closed-world leak, a selection re-derivation, a compensating-error pair, a boundary flip); exact-dict policy pins for anything constructed for the LLM; eval_common dry-resolve extension; **zero real API calls in `pytest -q`**.

Docs: `ONBOARDING.md` (incl. seed-gap register); `GRADING_EVAL_PLAYBOOK.md` with the STOP list — *no GT edits to pass; no scorer edits to pass; no threshold moves without pre-registration; no model/tier escalation without owner; no touching production code; no Gemini*; `GRADING_GT_CONVENTIONS.md` (§5, owner co-authored); `RUNLOG.md` seeded; `PREDICTIONS.md` seeded with **P1** (owner model prior) and a placeholder for the pre-baseline quantitative prediction, authored by owner + reviewer immediately before Phase C.

---

## 11. Phasing & review gates

| Phase | Content | Gate |
|---|---|---|
| **A — Instrument** | suite skeleton, schemas, scorer, runner (`score_only` + `--scopes` functional against synthetic drafts), guards, docs. Zero spend. | External review (§1.6 reviewer) on the phase report |
| **B — Fixtures + GT** | F0→F5. H1 ratification loop inside F0. Owner blind-grades. | GT committed + loader guards green + H1 ratified |
| **C — Baseline** | pre-baseline prediction authored → k=5 × 5 run of deployed pin (R7) → full analysis per PLAYBOOK (validity → worst test → per-terminal reads → Tier-2 distributions → escalations) | Baseline report reviewed; only then are Tier-2 threshold candidates pre-registered |
| **D — Judge bootstrap** | judge pass over Phase-C disagreements; owner labels 20; agreement stat; promotion bar registered | Judge report reviewed |

Per-item execution protocol applies throughout: pre-flight census of touched files; failing test first (red output pasted); implementation inside the scope fence; adversarial self-review; evidence bundle in the phase report. Each phase report carries per-item DONE sections with proofs. Sanity gates every phase: `python -c "import app.main"`, `pytest --collect-only`, both sibling batteries untouched (transcription 133 passed/1 skipped; rubric 8 known Family-D failures, nothing else).

---

## 12. Definition of done (v0)

- [ ] All R/H/P rulings encoded and traceable to mechanism (grep-able IDs in code comments — the G-15 lesson applied at birth).
- [ ] Guards green, including known-answer self-pass and every injected-error test.
- [ ] Five fixtures with blind Tier-A GT, hash-pinned to the ratified corrected contract.
- [ ] Baseline k=5 complete, pre-registered, analyzed per PLAYBOOK; worst test named; Tier-2 threshold candidates pre-registered from its distribution.
- [ ] PREDICTIONS.md carries P1 + the baseline prediction + outcomes.
- [ ] Zero production files touched; zero Gemini calls; total spend ≈ $1 + judge bootstrap.

---

## 13. Step-3 design input — the grading constitution (RECORDED, **NOT AUTHORIZED**)

**Status:** derived from the F5 GT-authoring session (2026-08-25) and recorded here because §12's step-3 work will be designed against it. **Nothing in §13 is authorized for implementation in v0.** It exists so that (a) the baseline's failure buckets are read against a design that already has a shape, and (b) no future agent re-proposes an alternative already rejected here (§13.4). Do not build any part of it without a separate owner authorization.

### 13.1 The problem it solves

A teacher grades one question down the whole class stack — deliberately — because that is how she stays consistent. The current architecture grades one test at a time, one LLM call per scope, with **no knowledge of how the same criterion was treated on any other test in the batch**. Two students who make the identical error can therefore receive different awards.

This is a product-level risk, not an eval nicety. In Bagrut context, inconsistency across a class is appeal (ערר) exposure, and it is the most attackable property of AI grading. It is also empirically confirmed: grading five tests consistently in the F5 session required **ten named precedents**, and the backward audit caught a terminal (AUDIT-2) that had been graded under a superseded form of one of them.

### 13.2 The mechanism — a three-stage loop

**Stage 1 — SEED.** Before any grading, the constitution is seeded from *teacher artifacts*: the model solutions plus the rubric's own guidance and tariffs. In the F5 session the model solutions overturned two proposer priors on first contact (R-β, the getter question; PL-8, return semantics). The constitution starts from the teacher's own materials, never from the grader's guesses.

**Stage 2 — ACCUMULATE.** Tests are graded; wherever the rubric underdetermines a case, a ruling is *proposed* and (in production) *ratified by the teacher*. A ruling is named, scoped to `(rubric_contract, terminal | global)`, and carries: the situation, the ruling, its **boundary** (what it explicitly does *not* cover), and the evidence that produced it.

Observed convergence in F5: dan 6 rulings · din 1 · moran 1 + 1 revision · omer 0 · yonatan 0. **The marginal ruling rate reached zero by the fourth test.** This convergence is the property that makes the design affordable at class scale — teacher input is front-loaded, not per-test.

**Stage 3 — BACKWARD AUDIT.** Once accumulation converges, the **final** constitution is applied to **all** tests, including those graded under earlier forms of it. This stage is load-bearing, not cosmetic: it is what makes the first test graded under the same law as the last. In F5 it caught AUDIT-2 (a terminal graded under PL-10's pre-revision form) and AUDIT-1 (two fixtures at equal awards for unequal severity).

### 13.3 Design consequences

- **(a) Order-independence without serialization.** Phase-1 fan-out stays fully parallel and per-scope isolated (§3.6). The constitution is **pinned per batch**, exactly as `contract_version` is. Determinism is preserved: same constitution + same contracts + same model/prompt versions ⇒ same grades. Stage 3 reconciles what parallel grading could not know.
- **(b) Convergence is the batch's progress signal.** A ruling rate that stays high late in a batch means the rubric is underspecified or the batch is heterogeneous. That is diagnostic, and it belongs in the UI as *"N new situations need your ruling"* — not as per-test flags.
- **(c) The constitution is the compounding artifact.** Rubric-scoped, teacher-owned, human-readable, teacher-editable. Every teacher override in production today creates a precedent and discards it. Captured, it carries her standards forward across batches and years: the next batch needs fewer overrides, and after-school hours fall further. Directly on the §2 north star, and a defensibility asset.
- **(d) Appeal-defensibility.** The answer to a challenged grade stops being *"the model scored it 1.5"* and becomes *"this idiom is behavior-divergent under the ruling the teacher set on <date>, applied identically to all N students"* — with the ruling, its date, and its application record all inspectable.
- **(e) Teacher authority preserved end to end.** The agent **proposes** rulings; the teacher **ratifies**. No entry entering force unratified. Stage-3 audit results surface as *proposed* adjustments, never auto-applied (§2: Vivi proposes; the teacher decides).

### 13.4 Rejected alternatives — do not re-propose without a new argument

- **Batch-scope grading** (all N students' answers for one criterion in a single call). Rejected: destroys per-scope failure isolation (§3.6) — one LLM failure would cost N students; breaks closed-world (whose terminals?); large context and cost; incompatible with `GradableTest`'s per-test construction.
- **Rolling precedent injection** (accumulate exemplars mid-batch, inject into later calls). Rejected: serializes the fan-out, and makes a grade **order-dependent** — the same test scores differently depending on its position in the batch. Fatal for auditability and for re-grade reproducibility.
- **Statistical divergence detection** (embedding similarity + award dispersion + LLM reconciliation) as the *primary* mechanism. Rejected: it can detect that two grades differ but cannot say **which is wrong**; and it requires an embedding index, a clustering threshold, and a reconciliation prompt — none of which a teacher can inspect or correct. It remains available as a *secondary* detector that nominates candidate situations for Stage-2 ruling, never as the arbiter.

### 13.5 Open mechanics — the pending design session (do NOT resolve unilaterally)

1. **Ruling-proposal surface.** Where in the pipeline does the agent detect "the rubric underdetermines this case"? Candidate signals: low per-terminal confidence; `validation_status=not_found` with a non-zero award; a flag with no corresponding rubric tariff.
2. **Ratification UX.** How are proposed rulings surfaced without adding work after 18:00 (§2)? Batched at review time, or at end-of-batch?
3. **Mid-batch churn.** A ruling ratified after some tests are already teacher-reviewed — how is re-audit surfaced without invalidating her completed work?
4. **Injection budget.** Constitution capped how? Scoped per terminal or per scope? Token budget per call?
5. **Schema and provenance.** Fields, versioning, and whether the constitution is hash-pinned into `GradedTestDraft` provenance (**recommendation: yes** — a grade is currently a function of rubric + transcription + model + prompt versions; the constitution becomes the fifth).
6. **Cross-batch inheritance.** Does a constitution follow the rubric contract across batches, terms, years? What happens on rubric recompile?
7. **Conflict resolution.** Two ratified rulings that collide on one situation.
8. **Stage-3 scope.** Whole batch, or only tests touching the changed ruling?

### 13.6 Measurement — registered pre-baseline

- **E5 — pairwise ordering agreement** (Tier-3, computable on the current five-fixture corpus): for each terminal, across all C(5,2)=10 fixture pairs, compare `sign(GT_a − GT_b)` against `sign(AI_a − AI_b)` — 380 comparisons. Detects what MAE structurally hides: internal inconsistency that averages out, and flattening of real between-student differences. **Computable post-hoc from `results.json`; it does not gate the baseline.**
- **E6 — constitution effect** (post-implementation): enabling the three-stage loop improves E5's ordering agreement and reduces terminal disagreement on criteria where the rubric underdetermines, with **no** regression on criteria carrying explicit tariffs, at bounded token cost. Single variable: the constitution.

### 13.7 Evidence base

The F5 session artifacts are the empirical record behind this section and the worked example of the three-stage loop: the five review sheets, the ratified ruling set (PL-1…PL-10, R-α, R-β, C-1…C-5), and `CROSS_FIXTURE_CONSISTENCY_AUDIT`. Any implementation of §13 should be tested first against this corpus, where the correct outcome is already known.