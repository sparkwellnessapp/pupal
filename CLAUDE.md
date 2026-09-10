# CLAUDE.md — Vivi Engineering Briefing

> **This is not a README. It is a briefing for a contractor — you — who has never seen this codebase. Read it before touching anything substantive. When this document and the code disagree, the code is truth and this document is a bug: fix the doc.**

---

## 0. The five rules that matter most

If you read nothing else, internalize these. They are the failure modes we have actually hit, in priority order.

1. **Plan before code on anything touching types, invariants, schema, or architecture.** State the problem, list open decisions with a recommendation, wait for approval. Mechanical edits (rename, log line) are exempt.
2. **Surface, don't decide.** Ambiguity becomes an *open decision in the plan with your recommendation* — never a silent choice. Silent choices are undocumented decisions nobody remembers making.
3. **Named protocols are the spec.** If a task says "INV-3" or "CW-1" or "RGC-1," your plan contains that exact name — not a renamed substitute, not "effectively covered by X." To change a named protocol, flag it as an open decision first. Silent mutation of named invariants is our #1 observed failure.
4. **One concept, one place (Hickey: Simple over Easy).** No parallel diagnostic surface when `annotations` exists. No duplicate schema when `ontology_types.py` exists. No stringly-typed transport when a real type fits. Easy compounds into maintenance debt; Simple is the standing order.
5. **When the DB or a frozen contract contradicts your plan, STOP and flag.** Do not reconcile silently by loosening a constraint, relaxing a tolerance, or papering a column. A CHECK constraint firing is usually *correct* and means your logic is wrong.

Everything below is detail in service of these five.

---

## 1. What Vivi is

An AI **Teacher's Assistant**. It ingests teacher rubrics (DOCX) and student tests (PDF; handwritten or typed), then:

- **Extracts** structured grading rubrics from teachers' DOCX files.
- **Transcribes** handwritten student answers, with teacher review against the source.
- **Grades** student answers against a frozen rubric contract, with teacher review and override.
- **Will evolve** into insights and personalized learning (not in scope today).

Workspace layout:
- `vivi-codebase/backend/` — FastAPI backend (Python, async SQLAlchemy, Supabase Postgres, GCP Cloud Run).
- `vivi-codebase/frontend/` — Next.js 14 (App Router) + TypeScript + Tailwind, RTL Hebrew, Vercel.
- `marketing-website/` — Next.js marketing site.

**CS is the first vertical, not the only one.** Launches into Israeli CS classrooms; the architecture must support arbitrary subjects without rework (§3.3).

---

## 2. North Star (product invariants)

Vivi exists because education systems asked teachers to do **machine-shaped work at industrial scale** (grading, rubrics, documentation) and then blamed them for burning out. Vivi is **not an AI teacher** — it is **the teacher's assistant**. We remove low-impact, high-volume work so human attention returns to students. **Validation beats repetition:** teachers want reliability, speed, calm, and control — not machine creativity.

Non-negotiable:
- **The teacher is always the authority.** Vivi proposes; the teacher decides. AI never finalizes a grade.
- **Reduce after-school work hours** is the north-star metric. A feature that adds work after 18:00 does not ship.
- **Never make teachers "manage AI."** No prompting gymnastics, no retry-until-it-works, no cognitive overhead disguised as flexibility.
- **Trust is non-negotiable.** If a feature risks student outcomes or privacy, it does not exist. If we cannot provide auditable evidence for a decision, the system degrades to **review-first, not guess**.
- **Accuracy floor:** a solid competent teacher. **Ceiling:** a world-class educator in that subject. Below the floor is worse than useless.
- **Faithful capture, never silent repair (FC).** Vivi reproduces **exactly what the teacher wrote** — every value, label, placement, and structure, **errors included** — and **surfaces** every resulting inconsistency as diagnostics (annotations + pedagogical mistakes) with a proposed fix the teacher confirms or rejects. It **never invents a value the teacher did not write** to make a rubric "add up", and **never silently relocates, relabels, or edits** content to reconcile an error. This is the whole product: *capture the error, identify the probable fix, let the teacher decide* — never guess it away. **One teacher error can cast several shadows across several surfaces** — e.g. a criterion mislabeled onto the wrong sub-question produces a `structural_mislabel` judgment **and** point-sum mismatches, on **both** the draft-review `annotation` surface (`rubric_mismatch`) **and** the teacher-education `pedagogical_mistakes` surface — and the faithful representation (and its ground truth) documents **all** of them; the single teacher fix then resolves them together. Generalizes to **any** error class, not just points or misallocation. (Corollary for the eval GT: `RUBRIC_EVAL_PLAYBOOK.md §4`, worked example hobby q2.)

**Mandatory review gates** (validation *is* the product):
- **Rubric gate:** the extracted rubric is reviewed/edited by the teacher **before compilation to Contract**.
- **Transcription gate:** the transcription is reviewed against the source PDF **before grading** (grading consumes an *approved* transcription contract).
- **Grading gate:** the graded draft (reasoning + evidence quotations) is reviewed/edited **before approval**.

**Brand voice:** caring, human, calm. Never hype, never fear, never dismissive of teachers' expertise. *Less grading. More teaching. Validation beats repetition. Teachers are irreplaceable; busywork is not.*

---

## 3. Working principles for agents

Load-bearing filters, not style preferences. (§0 is the short form; this is the rationale.)

### 3.1 Define the problem in Deutsch form first
For any non-trivial problem: state the **data** (observations producing the contradiction); name the **theory under criticism** (the current explanation the data falsifies); propose a **better conjecture**; **criticize** it (is it hard to vary? does it introduce new contradictions?). Skipping this is how an agent pattern-matches a surface symptom, "fixes" it, and silently violates a system-level commitment.

### 3.2 Simple over Easy (Hickey)
One concept, one location. Real types over stringly-typed transports. No "verify later" — research conclusions go into plans as concrete statements; if you don't know, say so and re-research rather than hedging.

### 3.3 Subject modularity — CS is the first vertical, not the only one
Backend types, prompts, data models, pipeline interfaces are **subject-agnostic by default**. Subject-specific UX (code-aware rendering, language detection, CS skill badges) lives only in subject-specific surfaces, never in shared components or core flows. Prompts take the subject as input; a prompt that "knows about CS" is a smell. The schema and Contract types never embed `subject == "computer_science"` as a special case.
**Litmus test:** *could a new subject be added with new prompts and new UX panels, without modifying any ontology type, compiler invariant, or pipeline interface?* If no, that's subject leakage — flag it.

### 3.4 Draft → Contract is universal (§4)
Every domain involving teacher review has a Draft (mutable, may be invalid, teacher-edited) and a Contract (frozen, validated, the only thing the AI consumes downstream). The compiler is the only path between them. New review domains default to this pattern.

### 3.5 Surface, don't decide; describe approach before code
Two defensible options → list both, recommend one, wait. Ambiguous spec → name it, propose an interpretation. Unexpected complexity in research → flag it, don't smooth it. For non-trivial tasks: (1) state your understanding, (2) list clarifying questions, (3) describe the approach and file changes, (4) wait for approval.

### 3.5a Display paths tolerate; consuming paths refuse (owner-ruled 2026-08-21)
The same malformed input deserves **opposite** handling depending on what the code is about to DO with it. A path that **consumes** the data — grading, compilation, contract freezing — must **refuse loudly**: a firing guard there usually means the logic is wrong (§0.5), and proceeding means the agent eats garbage. A path that only **displays** a derived figure must **degrade**, because blinding the teacher to everything is a catastrophic response to a cosmetic need — and it typically fails in the worst direction, since the broken surface is often how she would navigate to fix the cause.

**A degradation that keeps COMPUTING is more dangerous than one that stops, because the output still looks like an answer.** Worked evidence: the first version of the `needs_eyes` degradation substituted empty selection groups and carried on — which does not merely blur the number, it inflates it in a *specific direction* (every "choose k of N" empty reads as a missing answer), sending the teacher hunting for problems that do not exist with no way to discover the figure was fiction. The reviewer predicted a confidently-wrong zero; the real defect was a confidently-wrong over-count. Neither is acceptable, and the shape of the fix does not depend on guessing which one you would get.

Degradation is **by omission, never by guessing**: publish *no* number rather than one computed from substituted inputs (D10's hero duration and `needs_eyes` both follow this), log the offending id so the bad row is findable without reproducing the render, and mark the divergence in code as a *policy* so the next reader sees a ruling rather than an inconsistency to "clean up."

*Worked example:* `answer_space_groups` raises on a malformed contract. `get_batch` (consuming — the grading path) lets it raise. `list_batches` (display — a navigation surface) records the rubric as degraded, omits that batch's `needs_eyes` (wire type `Optional[int]`, `null`), and the client renders one merged "awaiting decision" segment instead of an invented clean|eyes split. Both halves are pinned by tests.

### 3.6 Per-scope failure isolation & determinism boundaries
Expensive, parallel, or stochastic operations (grading, transcription) must degrade per-unit, not per-batch: one scope's LLM failure becomes a flagged outcome, never a thrown batch. And know where determinism stops — the LLM call is the only non-deterministic stage in an otherwise pure pipeline; everything around it (compilers, validators) is pure and exhaustively testable.

---

## 4. THE architectural commitment: Draft → Contract

The load-bearing pattern across **rubrics, transcriptions, and graded tests**, uniformly.

| Artifact | Mutability | Validity | Consumer |
|---|---|---|---|
| **Draft** | Mutable | May be invalid; violations surface as `Annotation`/flags | The teacher (for editing) |
| **Contract** | Frozen (`model_config = {"frozen": True}`) | Pydantic-validated; invariants absolute | The downstream agent / next stage |

The Contract is produced from the Draft by **compilation**, which runs the invariant validators. Compilation fails if any invariant is violated. **The agent never sees a Draft** — agent/grading inputs are always Contracts. This closed-world property is what makes grading auditable instead of vibes-based.

Per-domain artifacts and compilers (all types in `app/schemas/`):

| Domain | Draft | Contract | Compiler |
|---|---|---|---|
| **Rubric** | `ExtractRubricResponse` (`ontology_types.py`) | `GradingRubricContract` (`ontology_types.py`) | `contract_compiler.py::ContractCompiler` |
| **Transcription** | `TranscriptionDraft` (`transcription.py`) | `TranscriptionContract` (`transcription.py`) | written at `/grade` (transcription approval) |
| **GradableTest** (in-memory only) | — | `GradableTest` (`gradable.py`) | `gradable_compiler.py` (marries RubricContract + TranscriptionContract) |
| **Graded test** | `GradedTestDraft` (`graded_test_draft.py`) | `GradedTestContract` (`graded_test_contract.py`) | `graded_test_contract_compiler.py::compile_graded_test` (at teacher approval) |

Implications: Contract types are `frozen=True`; contracts carry a fresh `contract_version` UUID **inside the JSONB** (no column) per compile; the compiler is the only path; Drafts carry diagnostic baggage (annotations, confidence), Contracts are minimal.

**`GradableTest` is in-memory only — never persisted.** It is a pure function of two pinned contract versions, recomputed on demand (closed-world by construction: the agent can only reference IDs the compiler sliced in). Do not add a table for it.

---

## 5. Invariants — the trust boundary

If any is violated, Vivi stops being a high-trust grading system. **These names are the spec (§0.3).**

### Rubric-compile invariants (enforced in `ContractCompiler`, ERROR-severity annotations, block compilation)
| ID | Name | Statement |
|---|---|---|
| INV-1 | QuestionPointSum | Question with sub-questions: `Σ sub_questions.points == question.total_points`. Without: `Σ direct_criteria.points == question.total_points`. Nesting-safe: it sums the sub-questions' *declared* points, never their contents. |
| INV-2 | CriteriaPointSum | **RECURSIVE (PR-3), over the criteria-XOR-sub_questions tree.** A **parent** node: `Σ children.points == node.points`. A **leaf**: `Σ criteria.points == node.points`. `target_id` is the **full path** (`q1.א.2`). Mirrors `pipeline.py::_walk_sq` — the preflight/compiler pair must not drift. |
| INV-3 | SubCriteriaPointsSum | Per criterion with sub-criteria: `Σ sub_criteria.points == criterion.points`. Vacuous when `sub_criteria` empty/null. (Already recursed, via `all_criteria`.) |
| INV-4 | RubricPointsSum | **ACHIEVABLE-aware (PR-3):** `compute_achievable_points(questions, selection_groups) == rubric.total_points`. With no selection groups this reduces *exactly* to the legacy `Σ question.total_points` check. |
| INV-6 | CriterionAlignment | Every criterion links to a skill target or requirement. **INFO — non-blocking (PR-3).** |

> **`total_points` means ACHIEVABLE, everywhere, by definition (PR-3).** The Draft always did (`_achievable_from_extraction`); the Contract now agrees. This resolves a semantic split in which Draft and Contract disagreed about what the number *meant*, and which made every "choose k of N" exam a hard dead-end after a successful extraction. `contract.total_points` is the **single source** of the grading denominator — **no consumer re-sums scopes** (see the grading section below for why that re-derivation was catastrophic). That includes the *display* consumers: `calculate_rubric_stats` takes the contract's total as an argument and does not recompute it, because the save path writes that number into the **`rubrics.total_points` column** — a re-sum there put a row in permanent disagreement with its own `contract_json`. The only place the offered Σ still appears is the stats estimate for an **uncompiled** draft, where no contract exists to consult.
>
> **Why INV-2 had to become recursive:** the flat version validated only depth-1, so a *parent* (whose criteria live on its children) summed to 0 and always failed, while its children were never visited. It rejected every nested rubric **and masked the faithful teacher error one level down** — the exact rubric-gate moment the product exists for. It fired at the wrong nodes and stayed silent at the right one.
>
> **INV-6's history (do not re-promote it):** as a WARNING it fired on **100% of criteria** (extraction produces no `skill_targets`/`requirements` — that is a future feature, not a defect) and the frontend auto-acknowledged **100% of them**. A check nobody can pass is worse than no check: it trains the click-through reflex that will swallow the next *real* warning. Demoted to INFO; kept as the hook for the future skill-mapping feature.

### Closed-world & versioning (enforced in the grading/approval path)
| ID | Name | Statement | Where |
|---|---|---|---|
| CW-1 | ClosedWorldByConstruction | `GradableTest` carries only the criteria sliced from the Contract; the agent cannot reference anything else. **Since PR-3 scopes are LEAVES at any depth**, so this guarantee finally covers the scope set the grader actually receives (previously it held over ids the grader never saw). | `gradable_compiler.py` (structural) |
| CW-3 | ClosedWorldAtApproval | Every teacher override key is a real terminal in the draft. | `compile_graded_test` (approval gate) |
| VER-2 | ContractVersionPin | `graded_tests.rubric_contract_version` is pinned at row creation, never mutated. Re-grade creates a *new* row with the new version. | `/grade`, revision flows |
| RGC-1 | OneLeafPerChain | Exactly one leaf (`regraded_to_id IS NULL`) per `(transcription_id, rubric_id)`. | partial unique index `idx_graded_tests_one_leaf_per_chain` |
| VER-3 | TranscriptionContractPin | `graded_tests.transcription_contract_version` records the OTHER half of the grading input (migration 029). NULLABLE and **never back-filled** — NULL means "predates the pin", and a guessed provenance is worse than a recorded absence. | `/grade`, both batch accepts; carried (never re-read) by `extend_chain` |
| EVD-1 | WhatWasGradedIsWhatIsShown | The answer rendered at the grading gate is the text the grader actually consumed — recorded on `ScopeOutcome.student_answer` at grade time, frozen into the contract at approval. **Never re-derived by the reader.** | `gradable_compiler` → grader → `graded_test_contract_compiler` |

### The approval gate (what `compile_graded_test` actually checks)
Bounds per terminal (`0 ≤ awarded ≤ possible`) + precision (round to `numeric_policy.precision`) + branch-aggregation consistency + CW-3 + **no unresolved `error`-severity annotations**. It does **NOT** re-fire INV-1/2/3 on *awarded* points — awarded points have no sum constraint (partial credit legitimately sums below possible). Re-firing point-sum on awarded points would reject valid grades; don't.

### Structural constraints (Pydantic shape, not invariants)
- **StructureExclusivity:** a `Question` has either `sub_questions` (no direct criteria) or direct `criteria` (no sub_questions), never both. Pydantic validator on `Question`.
- **SubCriterion is a flat leaf:** `Criterion.sub_criteria: Optional[List[SubCriterion]]`. `SubCriterion` does **not** nest further. The "criterion tree" is at most two levels. When `None`/empty, the criterion grades as one unit (INV-3 vacuous).
- **SubCriteria are extracted from the source DOCX, never generated.** Constructing a `SubCriterion` in code outside the V3 pipeline's `_build_criterion` is a smell — stop.

---

## 6. Diagnostics: annotations vs. flags (read this — it gets re-flagged)

There are **two intentional, non-competing** diagnostic representations. They are not a violation of "one concept, one place" — they are a denormalization, like a stored `total_score` column that mirrors what's computable from JSON.

- **`annotations: List[Annotation/GradingAnnotation]`** — the **teacher-facing, rolled-up diagnostic surface.** This is what the review UI reads and what the approval gate inspects for `error` severity. ANN-1 ("single diagnostic surface") governs *this*: do not add a competing `warnings`/`blockers`/`rubric_warnings_by_scope` dict alongside it.
- **`flags: List[FlaggedOutcome]` on outcome objects** (`ScopeOutcome`, `CriterionOutcome`, `SubCriterionOutcome`) — **structured per-terminal grading data, co-located with the outcome it describes.** This is what renders "this criterion was bounds-clamped" next to that criterion, and what the eval suite mines for per-criterion flag rates.

The relationship: a flag event (closed-world, bounds-clamped, no-answer, quote-not-found, …) is recorded as a structured `flag` on the outcome **and** rolled up into a teacher-facing `annotation`. Same event, two granularities, by design (specified in the GraderAgent grading spec). Do **not** "consolidate" by deleting `flags` — you'd lose per-criterion rendering and the richest eval signal. If you find flags and annotations *disagreeing* for the same event, that's a real bug; fix the population logic, not the design.

### The Annotation object (`ontology_types.py`)
`severity: ERROR | WARNING | INFO` · `message` (Hebrew/English) · `message_he` · `target_id` (scope anchor: question/sub-question/criterion/sub-criterion id, or `None` for global) · `annotation_type` · and, for invariant violations, `invariant` / `expected` / `actual` (PR-3 — the named invariant and the arithmetic, so the editor can anchor the rejection and the teacher can act on it).

> ⚠️ **`rubric_management.py::AnnotationSchema` is a hand-maintained MIRROR of this type, and it has already lied once.** It carried 5 of the 9 fields, so `_annotation_to_schema` silently dropped `invariant`/`expected`/`actual`/`message_he` — the deployed API answered a real INV-2 violation with three nulls and an **English** sentence in the field named `message_he`, on an RTL screen. **Add any new `Annotation` field to `AnnotationSchema` and to `_annotation_to_schema`**; a structural test (`tests/services/test_payload_fidelity.py`) set-compares the two and fails if you don't. Deleting the mirror outright is B-10 — a duplicate schema is not a style problem, it is a truncation waiting to happen (§0.4). Related: **defensive `getattr(x, "field", None)` at a type boundary converts a loud failure into a quiet lie** — that is exactly what hid this one.

| Severity | Compilation / Approval | UI |
|---|---|---|
| ERROR | Blocks compilation / blocks approval | Red banner; blocks Save/Approve |
| WARNING | Proceeds; teacher should acknowledge | Amber banner; non-blocking |
| INFO | Proceeds silently | Neutral banner |

Rendered by a single `<AnnotationBanner />`, severity-differentiated; `target_id`-anchored annotations render inline, `None` renders in a top-level summary.

---

## 7. The pipeline, end to end

```
DOCX rubric ──► V3 extract ──► ExtractRubricResponse (Draft)
                                   │ teacher reviews/edits (RUBRIC GATE)
                                   ▼ ContractCompiler (INV-1..4)
                              GradingRubricContract ───────────────┐
                                                                   │
student PDF ──► /transcribe (VLM + GCS upload) ──► TranscriptionDraft
                                   │ teacher reviews vs source + assigns student (TRANSCRIPTION GATE)
                                   ▼ /grade  (writes TranscriptionContract, inserts pending graded_tests)
                              TranscriptionContract ───────────────┤
                                                                   ▼
                              gradable_compiler.compile() ──► GradableTest (in-memory, closed-world)
                                                                   ▼ run_grading (BackgroundTasks, S8)
                              GraderAgent.grade() ──► GradedTestDraft  (status: pending→grading→draft│failed)
                                   │ teacher reviews/edits overrides (GRADING GATE)
                                   ▼ /approve  compile_graded_test (gate §5)
                              GradedTestContract  (status → approved)
```

**graded_tests lifecycle:** `pending → grading → draft → approved`, or `→ failed`. CHECK constraint `graded_tests_status_consistency` enforces which JSON columns are set per status (`draft` requires `draft_json`; `approved` requires `draft_json + contract_json + approved_at`, all in one commit).

**Async rubric extraction (PR-1):** extraction is a durable job, not a request. `rubric_extraction_jobs` (`queued → extracting → completed|failed`; CHECK `rubric_extraction_jobs_status_consistency`) holds the source doc (GCS, content-addressed by sha256), progress heartbeat, result payload, and provenance (prompt/pipeline/model/tokens/duration). Execution: Cloud Tasks → `POST /internal/extraction-jobs/{id}/run` — extraction runs INSIDE that request so CPU is guaranteed (`EXTRACTION_EXECUTION_MODE=inline` is local-dev only). Submit is idempotent: partial unique index `idx_extraction_jobs_one_active_per_source` (one ACTIVE job per `(user_id, source_sha256)` — the RGC-1 precedent) makes a duplicate submit return the existing job. Recovery is heartbeat-staleness (computed from `updated_at`, never stored) + the explicit `/retry` endpoint — never blind task redelivery (`maxAttempts=1`). The result is NEVER auto-saved as a rubric: the teacher reviews it and `save_ontology_draft` (unchanged invariant: a saved rubric is a compiled rubric) stamps `rubrics.extraction_job_id`. The old sync `POST /grading/extract_rubric_docx` is deprecated pending frontend cutover.

**Cloud Tasks migration (2026-08-13/15) — BackgroundTasks is EXTINCT in this codebase.** All three long-running work types are durable jobs executed as authenticated HTTP POSTs back to this service (CPU guaranteed inside the request; prod Cloud Run throttles CPU post-response, which is why BackgroundTasks kept losing work). One substrate, several kinds (`cloud_tasks_service.JobKind`): extraction (`rubric_extraction_jobs`, PR-1), **batch transcription** (`transcription_jobs`, migration 016), **grading** (`graded_tests` rows — already row-first; only the substrate changed), plan builds (`grading_plans`, migration 026), and **the onboarding sheet projection** (028 — the one kind with NO job row: its "job id" is a `users.id`, because the projection is a derived view of that row and a task that never runs costs a stale spreadsheet cell, not lost work). Do not add new work on BackgroundTasks — declare a JobKind.
- **Batch transcription:** `create_batch` is metadata-only (B9 intake v2 — the every-PDF-in-one-multipart body hit Cloud Run's 32MB ceiling at ~5 scans); files arrive ONE PER REQUEST via `POST /batches/{id}/files`, each landing its own `TranscriptionJob` under a FOR-UPDATE serialized insert, and each enqueuing its own task. **Jobs are what ARRIVED; `grading_batches.expected_test_count` (migration 025) is what she DECLARED, and the gap is the upload stage** — `uploading = max(0, expected − COUNT(jobs))`, derived at read time, never stored. Without it the rollup's denominator was COUNT(jobs) alone, so a ten-file batch with one file in reported a total of one and could derive "completed" while nine files were still on the wire (Defect D). `_derive_batch_status` now refuses every terminal status while `uploading > 0`. **The server NEVER lowers `expected`**: the client re-declares it downward via `PATCH /batches/{id}` on a TERMINAL upload event (a 422 verdict or an explicit remove — never a retryable failure, which keeps its slot), refused below COUNT(jobs); and when she is simply gone, `upload_declaration_ttl_minutes` (90, clocked on the newest append) reports the remainder as `not_received` — dead, so the batch reaches `partially_completed`/`failed` instead of an eternal `in_progress`. `expected_test_count` NULL is the LEGACY population (pre-025 batches, and any client that does not declare): the whole overlay is bypassed and the rollup is byte-identical. Worker (`transcription_job_runner`): CAS `queued→running` → GCS download → pipeline (untouched) → **ONE transaction: transcriptions INSERT + job→completed** (zombie completions roll back, never double). Failure → `failed` + error + net_diag verdict on the row. Per-doc **retry without re-upload**: `POST /batches/{id}/jobs/{job_id}/retry` (failed or expired only, CAS).
- **Grading:** all five kickoff sites (`accept_clean`, `accept_one`, single `/grade`, `/regrade`, `/retry`) call `enqueue_grading_task_or_log` after their commit; `run_grading` claims by **atomic CAS pending→grading** (duplicate delivery = no-op — the old load-then-check guard had a double-grade race). Enqueue failure needs no row write: the pending row is durable and liveness-reaped.
- **Liveness (LIV-1 generalized, `job_liveness.LivenessRule`):** one rule, instantiated per domain (`extraction_job_liveness` unchanged API, `transcription_job_liveness`, `grading_job_liveness`). Every ACTIVE status runs a clock: queued/pending on `created_at` (90-min dispatch **backstop** — batch backlog makes long waits honest, so NOT extraction's 5-min window), running on `updated_at` (transcription: 60s heartbeat sidecar, 5-min TTL; grading: no in-run heartbeat, 30-min TTL > the 900s dispatch deadline). Doors: `get_batch` reaps batch-scoped BEFORE reading statuses; startup sweeps all three kinds. Expiry is TERMINAL on read → `failed` → the retry affordances.
  - **LIV-1 grew an ABSOLUTE arm (2026-09-10, owner-ruled).** A heartbeat clock proves the worker PROCESS exists — never that the work is progressing, that it can still land, or that the request owning it is still alive — and *the worker is the thing refreshing it*. So a coroutine orphaned past its Cloud Run request deadline keeps beating, the reaper keeps declining, and the rule's own purpose («a row that cannot be falsified is a row that traps the teacher forever») is satisfied in letter and defeated in fact. `ActiveArm` therefore takes an optional second clock the worker cannot touch — `absolute_clock_attr` / `absolute_ttl` / `absolute_reason` — and `transcription_jobs.running` uses it on **`started_at`, 20 min** (`TRANSCRIPTION_JOB_ABSOLUTE_TTL_MINUTES`). It can only catch corpses: the document budget is 480 s and Cloud Run kills the request at 900 s. The reason is DISTINCT from the heartbeat one on purpose — "the worker died" and "the worker overran" are different facts and she may act on them differently — and both the SQL and Python forms test the absolute clause FIRST (the module's two-forms-must-agree invariant, pinned by `tests/services/test_liveness_absolute_arm.py`). ⚠ **DEFERRED, awaiting implementation:** extraction, plan-build and grading have the identical heartbeat shape and the identical hole; the mechanism exists but they do NOT use it (noted in each module).
- **Redelivery (owner-ratified deviation from the extraction ADR):** the transcription/grading queues run `maxAttempts=3` — the CAS claim makes duplicates provable no-ops, and redelivery is the only healer for dispatch-level failures under backlog. Extraction keeps `maxAttempts=1`. `/internal` handlers always return 200 on auth success (non-2xx would redeliver work the row already accounts for).
- **Rollup:** jobs-based when job rows exist (`transcribing` = active jobs, `transcription_failed` = failed jobs); the migration-015 ledger + `test_count − rows` inference survive ONLY as the read-only legacy fallback for pre-016 batches (ledger writes retired; Δ15 client residue heuristic deleted). Dropping the 015 column is B-27.
- **Modes:** `JOBS_EXECUTION_MODE` (`cloud_tasks`|`inline`) governs the two new kinds and **falls back to `EXTRACTION_EXECUTION_MODE`** when unset — existing dev (.env inline) and prod (cloud_tasks) need zero new env. Inline = `asyncio.create_task` (dev only; dies with the process — that's what the sweeps are for).

**Shared provider infrastructure (2026-08-12):** `two_phase_engine._shared_infra()` — ONE provider set + ONE `ProviderScheduler` per (process, event loop), NEVER per document (per-doc schedulers made the per-model cap a no-op: parallel batches fired 3×N+N concurrent multi-MB uploads and starved their own identity calls). Global cap `PROD_MAX_CONCURRENT_PER_MODEL=5`; `doc_priority` is meaningful batch-wide (depth-first); the identity pass rides the same scheduler at its doc's priority (the scheduler owns its retry); the job runner re-runs a document ONCE on retryable transport failure only (the eval runner's resilience pattern). Do not construct per-doc schedulers again. Batch-wide concurrency is the queue's `maxConcurrentDispatches` (the in-process semaphore is gone); per-instance LLM pressure stays capped by this scheduler. The GCS upload story: single-flow `/transcribe` still overlaps upload with the pipeline inside `transcribe_one`; batch uploads happen at intake (before the jobs commit) on the patient weak-uplink policy (`gcs_service`: resumable 2MB chunks, 120s/request, 300s retry budget).
**⚠️ Sessions × background work (2026-08-07 incident, rules still standing):** the Supabase transaction pooler RESETs connections held idle-in-transaction 60s+ — this detonated ASGI teardown and lost a finished transcription's INSERT (a batch landed 0/4) back when BackgroundTasks ran inside the dependency `AsyncExitStack`. The substrate changed; the disciplines did not: (1) `transcribe_one` is a TWO-SESSION design — read rubric/release, pipeline with no connection held, fresh checkout for the INSERT (the job runner inherits this shape); (2) endpoints `await db.close()` after their final commit, before enqueue round-trips (idempotent; teardown no-ops); (3) `get_db`/`get_db_context` teardown never raises on a dead connection (log + invalidate; `get_db_context` preserves the ORIGINAL exception over a rollback failure) — pinned by `tests/test_database_teardown.py`. Do not "simplify" any of these back.

**Revision flows (single-test lifecycle complete):** all extend the chain immutably (LCY-2: approved/failed rows are read-only except `regraded_to_id`), via `extend_chain()`:
- **regrade** — approved + leaf + **stale** only; new row pinned to the *new* rubric version; runs the agent.
- **manual_edit** — approved + leaf (any staleness); new `draft` row carrying the prior `draft_json` verbatim; **no agent**.
- **retry** — failed + leaf; new pending row; runs the agent. (`failed` is terminal *for the row*; the chain continues.)

The chain insert uses a **deferrable `regraded_to_id` FK** (migration 010): link R1 → flush → insert R2 → commit. Do not use the naive insert-R2-first order — it trips the one-leaf partial index for same-chain rows.

**Production grader pin — LIVE (owner instruction 2026-09-05/06, `app/agents/plan_gen/PLAN_production_wiring.md`): `claude-sonnet-5` + `grader-v5.4` + a COMPILED plan per rubric.** grader-v5 grades EVERY rubric (ruling W-4). The plan is no longer a hand-ratified file bound to one rubric id: it is a **derived artefact of the contract**, built by PLAN COMPILER v2 (`app/agents/plan_compiler/` — compile the algebra purely, route monoliths on Sonnet 5, segment the wording on Haiku 4.5, assemble, validate) and stored in **`grading_plans`** (migration 026), keyed by the **content hash of the contract with `contract_version` blanked** (one place: `plan_store.contract_sha256`), append-only — a `ready` row's `plan_json` is never rewritten; a rebuild inserts and supersedes. **Built at rubric compile** (the three contract-writing endpoints kick a `PLAN_BUILD` job on its own `plan-build-jobs` queue after their commit) **and in place at grade time** when no ready plan exists (`plan_build_runner.resolve_plan_for_grade`: ready → use; a live builder → wait ≤240 s on its heartbeat; queued / failed / dead builder → build under the grade job). **The substitution policy is structural (W-2):** a provider outage, an envelope overrun ($1/rubric) or a validator surprise degrade only the WORDING to the compiler's own spans (`wording_source='placeholder'`, stamped into the draft as `plan_wording_source`) — never the algebra; the only way to a `failed` row is a `CompilerBug`. **The teacher never sees a plan (W-3)** — no route, no field, no annotation. Model and prompt are a PACKAGE: `grader-v5.4` is v5.3's system prompt byte-identical plus the `counted` rule in the user message only when a counted check exists. **Rollback is one env flip:** `GRADER_ARCHITECTURE=v3` (the only knob left; `grader_plan_path`/`grader_plan_rubric_id` and `app/agents/grader/plans/` are gone). ⚠ The service needs `ANTHROPIC_API_KEY` (Secret Manager) — absent on Cloud Run as of 2026-09-05 — and migration 026; without them every v5 grade fails loudly and every build degrades to a placeholder. ⚠ This pin shipped WITHOUT an A3 number (owner's call, on record in `TRACKER_plan_compiler_v2.md`); A1/A2/A3 run right after deploy. Tests: no provider is ever constructed inside a plan build in the test process — `tests/conftest.py` replaces the model factory for every test; builder tests inject fakes.

**Grading agent shape (`app/agents/grader/`):** one LLM call **per scope** (a scope = a direct-criteria question OR one sub-question), bounded-parallel (`asyncio.Semaphore`, `effective_scope_concurrency(scope_count)`), `return_exceptions=True`. **[PR-G3] The width is a DIAL** (`GRADER_MAX_CONCURRENT_SCOPES`, default 16), read at call time and capped by the scope count, so the kill criterion's «revert to 5» is an env change on a running service. It is bounded by the PINNED PROVIDER's request rate, not by appetite — a provider at 25 RPM cannot absorb 16 concurrent calls from one test. **Three consumers divide by this same number and must never be left behind:** the ETA's wave count (`eta.py`), the row budget that declares a hung grade failed (`grading_runner._row_budget_s` — computing it narrower than the grader runs kills HEALTHY grades), and the latency profile, which must be RE-MEASURED whenever the dial moves. Per-scope failure → flagged zero-outcome (`graded_by="failed"`), never propagates. Deterministic post-validation (closed-world re-check, bounds+precision clamp, sliding-window quote validation via `difflib`). Captures token usage (`include_raw=True`) for per-scope cost. Stamps `model_version` + `prompt_version` into the draft (a grade is a function of rubric+transcription+model+prompt versions — all four are recorded).

> ⚠️ **The grader's "one surgical retry" is a MISSTATEMENT that this doc used to make — the real worst case is 6 API calls per scope, unbounded.** `GraderAgent.__init__` builds `ChatOpenAI(...)` with **no `timeout` and no `max_retries`**, so (a) the OpenAI SDK's hidden `max_retries=2` applies → 3 transport attempts *inside* each `ainvoke`, and (b) LangChain passes `timeout=None` **explicitly**, overriding the SDK default → **httpx `Timeout(None)` = no timeout at all**. Its own GA-3 retry then wraps that: **2 × 3 = 6 unbounded calls per scope.** Two consequences: `openai.APITimeoutError` in its `TRANSIENT_EXCEPTIONS` tuple is a **dead branch** (nothing can ever time out), and `insufficient_quota` — a *permanent* billing 429 — is retried as if transient. **PR-2 fixed exactly this defect family in `docx_v3/pipeline.py` only** (see below); the grader keeps the defect until **PR-7** (its Cloud Tasks migration), where its per-task budget math belongs. `_transport_retry_async/_sync` in `pipeline.py` are written to be reusable there — do not add a *second* retry layer around the grader.

**Extraction transport policy (PR-2, `docx_v3/pipeline.py`):** every LLM attempt is **bounded** (`timeout`, env `EXTRACTION_LLM_TIMEOUT_S`, default **360s**), the SDK's hidden retry layer is **disabled** (`max_retries=0`), and **exactly one** retry layer is owned in-pipeline (`_transport_retry_async` / `_transport_retry_sync`, default 1 retry). Its predicate **fails fast** on permanent conditions — `insufficient_quota` (billing, not rate pressure), 401/403/400 — and re-raises content/parse failures untouched. A wall **deadline** is enforced at three points (validation-loop entry `T+60`; each transport attempt `T+10`; Tier-B entry `T+10`, else **skip** with the distinct warning `"Tier B skipped: time budget…"`), because a logical call is `attempts × T`, not `T`. The runner passes `840 − measured pre-work` (monotonic). **`deadline_seconds=None` ⇒ unbounded ⇒ the eval path**, which is why the gate is untouched by construction. Rationale: an observed attempt ran **1736s** with no timeout — 1.9× the whole task budget. **Never stack another retry layer on top of this one.**

**Batch grading (S11):** a batch is M tests through the same per-test pipeline with `batch_id` set; fan-out is bounded (`BATCH_MAX_CONCURRENT_TESTS`). Transcription review is **triaged** — clean transcriptions bulk-acceptable, flagged ones (low logprob span / VLM low confidence / grounding retry / `[?]` markers / missing-or-unmatched student) handled individually. Student auto-match against the batch's class roster is conservative (normalized-exact, never fuzzy); class is **optional** (first-time teachers have no roster → manual pick + inline create).

**Batch transcription review (batch-review PR, 2026-08):** the batch flow's transcription gate is a full-screen, deep-linkable per-item route — `/batches/[id]/review/[transcriptionId]` — replacing the blind inline cards; the dashboard keeps the triage front door (bulk-accept clean, summary rows + links for the rest). Named concepts:
- **Marker↔key mismatch + reassignment (2026-08-07):** P2's assigned key is the GRADING route, and nano sometimes renumbers answered questions sequentially when the student skipped one (observed live: every block one question early). `segmentation_check.py` (+ TS mirror `segmentation-check.ts`, cross-pinned fixtures) parses each answer's LEADING student marker ("שאלה 5", "א) 3") — a declared-digit contradiction emits a `segmentation_mismatch` WARNING annotation + triage reason, and the review surface recomputes it LIVE with a one-click **SWAP** proposal (exact key → bare-question fallback, owner-ruled). Reassignment = content exchange between frozen keys (never overwrite, chain-safe in any order; page chips travel with content in-session), riding the overlay/accept full-snapshot semantics with zero backend write-path change. Card titles stay key-derived BY DESIGN — they must tell the truth about the grading destination; the banner is what surfaces the disagreement. Never auto-remap (FC). Single-test flow: the surface hides the whole affordance when `onSwapAnswers` is not passed.
- **`transcriptions.review_json` — the teacher review overlay** (migration 014): her persisted working copy. Writable ONLY while `status='transcribed'` (PATCH `/transcriptions/{id}/review`; 409 otherwise); a **FULL snapshot** whose answer-key multiset must equal the draft's (422 on mismatch — **no merge semantics exist anywhere**); **nulled inside the approval-transition UPDATE in all three approval paths** (`/grade`, `accept_one`, `accept_clean` — part of the transition write, so LCY-1 is untouched); **never read at approval** by the per-item accepts (their request body is authoritative); and **its presence excludes an item from bulk-accept** (teacher-touched ⇒ not "clean" — server-enforced in `accept_clean`).
- **Viewing is not commitment (Δ14):** hydration and the StudentPicker auto-match pre-seed are never dirt; only a keystroke or an explicit picker change is. The autosave-on-navigate flush fires only when dirty — a glance at a clean item must never create an overlay (which would silently pull it out of bulk-accept). Do not "simplify" this away.
- **Per-item grading kickoff is the PERMANENT design, not an interim** (product ruling): accept = approve + insert pending `graded_tests` + queue grading, per item — grading runs while the teacher reviews the rest. The future `POST /batches/{id}/submit` changes **coverage** (accept-everything-remaining-acceptable + completion ceremony, reading `review_json` since it has no body), never **timing**.
- ⚠️ **Grading-seam caveat (updated 2026-08-15):** "accept fires grading" now means "accept enqueues a grading Cloud Task for a durable pending row" — the pending-INSERT itself works (the bare-`JSONB`-`None` CHECK failure was fixed with `none_as_null=True`; the accept→pending→CAS-claim seam is integration-tested), and a stuck/failed run is reaped + retryable. But the GRADING RUN itself (`_do_grade` → GraderAgent against real contracts) remains **live-unverified end-to-end in batch**; the grading-endpoint PR still owns proving it. Do not read the DFD claim as tested beyond the seam.

---

## 8. Repo map — backend (`vivi-codebase/backend/`)

### Canonical source of truth — DO NOT DUPLICATE
- **`app/schemas/ontology_types.py`** — the single source for `ExtractRubricResponse`, `GradingRubricContract`, `Question`, `SubQuestion`, `Criterion`, `SubCriterion`, `Annotation`, `FlagReason`, and related enums. Import from here; never fork a rubric/contract type elsewhere.

### Schemas (`app/schemas/`)
| File | Holds |
|---|---|
| `ontology_types.py` | Rubric Draft/Contract + all shared ontology types + `FlagReason` |
| `transcription.py` | `TranscriptionDraft`, `TranscriptionContract` |
| `gradable.py` | `GradableTest` and its scope/criterion types (in-memory) |
| `graded_test_draft.py` | `GradedTestDraft`, `ScopeOutcome`, `CriterionOutcome`, `SubCriterionOutcome`, `TeacherOverride`, `GradedTestOverrides` |
| `graded_test_contract.py` | `GradedTestContract` + frozen provenance-bearing outcome types |
| `graded_test_responses.py` | API response shapes (list / draft / approved / failed) |

> Note: `FlaggedOutcome` currently lives in `ontology_types.py` (a known coupling smell — a grading type in the rubric module). Moving it to a grading schema module is acceptable cleanup when you're already editing those imports.

### API routers (`app/api/v0/`) — all enforce auth + ownership (§9)
| Router | Prefix | Purpose |
|---|---|---|
| `transcription.py` | `/api/v0/transcriptions` | `/transcribe`, `/grade`, page-image proxy |
| `grading.py` | `/api/v0/...` | graded-test read endpoints, `/draft` (save overrides), `/approve`, `/regrade`, `/manual_edit`, `/retry`, rubric list/extract |
| `rubric_management.py` | `/api/v0/rubrics` | rubric Draft lifecycle (save/update/compile/get/list) |
| `rubric_extraction_jobs.py` | `/api/v0/rubrics/extraction-jobs` + `/internal/extraction-jobs` | async extraction jobs: submit/status/result/retry/list + Cloud Tasks target (PR-1). **Registered BEFORE rubric_management in main.py — order is load-bearing** (its prefix nests under `/api/v0/rubrics`, which rubric_management catches with `GET /{rubric_id}`; Starlette is first-match-wins) |
| `classroom.py` | `/api/v0/classroom` | students + classes + memberships |
| `batch_grading.py` | `/api/v0/batches` + `/internal/transcription-jobs` | batch create (uploads→jobs→enqueue)/detail/list, accepts, per-doc job retry, + the transcription Cloud Tasks target |
| `rubric_generator.py` | **`/api/v0/rubrics`** (NOT `/rubric-generator` — the doc said so and was wrong) | AI rubric generator. ⚠️ **All five of its routes carry NO auth dependency and collide path-for-path with `rubric_management`'s authenticated routes** (`save_ontology_draft`, `{id}/draft`, `{id}/compile`, `GET /{id}`, `GET /`). They are unreachable *only* because main.py registers `rubric_management` first and Starlette is first-match-wins — the same order-is-load-bearing property as the row above, but here it is the sole thing standing between the internet and five unauthenticated rubric endpoints. FastAPI logs this as `Duplicate Operation ID …` on every OpenAPI dump. Pinned by `tests/api/test_users_auth.py::test_rubric_paths_require_auth`. Retiring this router is **B-28** |
| `auth.py` / `users.py` | `/api/v0/auth`, `/api/v0/users` | auth (login/signup/**profile**/logout/refresh/**verify-email**/**resend-code**/**google** + **google/nonce**) · users: subject matters, the user's rubric + graded-test lists, rubric sharing, and the **onboarding writes** (`PUT /me/schools`, `PATCH /me/profile` — the ONLY writer of `full_name`, `POST /me/onboarding/complete`, **`PATCH /me/onboarding-exam`** (028); none mounts at `/users/me`, which would turn its 404 guard into a 405). It also carries an `internal_router` (`POST /internal/onboarding-sheet/{user_id}/upsert`) — the sheet projection's Cloud Tasks target, authenticated by `verify_task_request` and NOT by `get_current_user`, which is why the two structural auth guards in `test_users_auth.py` (both iterate `users.router`) do not cover it; `test_onboarding_exam.py` pins its 403 separately. **The profile read lives at `GET /auth/me` and only there** — `users.py` carried a caller-less byte-identical duplicate at `GET /users/me`, deleted 2026-08-17 |

### Services & agents
- `app/services/docx_v3/pipeline.py` — **production** rubric extraction (3-step prompt chain) + the PR-2 transport policy (bounded attempts, one owned retry layer, wall deadline). `parser_render.py` — DOCX→markdown.
  > ⚠️ The `gemini` provider branch in `_get_llm` is **undeployable**: `langchain_google_genai` is **not in `requirements.txt`**, so that branch raises `ImportError` at construction. It is also the one branch PR-2 left **unbounded** (no timeout / no `max_retries=0`), deliberately — bounding a branch that cannot run would be theatre. Adding the dependency is a deliberate decision for a provider sweep, not a side effect of another PR.
- `app/services/contract_compiler.py` — rubric Draft→Contract (INV-1..4, INV-6-as-INFO). Populates `selection_groups` and sets `total_points` to the **achievable** total.
- `app/services/gradable_compiler.py` — RubricContract + TranscriptionContract → `GradableTest`. **Scopes are LEAVES** (PR-3): a sub-question with children contributes no scope of its own; each leaf carries its own criteria and points, with a full-path id (`א.2`). A leaf whose exact id has no transcription answer **inherits its nearest ancestor's answer** (the transcription pipeline segments to depth 1; that fallback is load-bearing for every nested rubric, and each firing is recorded in `GradableTest.parent_answer_fallback_scopes`).
- **`app/services/selection_scoring.py` — the SINGLE source of the grade.** ⚠️ The final score was computed in **two** places and *both* re-derived the denominator as `Σ scope.points_possible`. On a "choose k of N" exam that divides by every question the exam *offered* instead of what the student could *earn*: a student answering the 50-point question perfectly and skipping the other two — **as the exam instructs** — scored 50/100 = **50%**. Both `grading_runner` and `compile_graded_test` now call `score_with_selection(...)` and **neither re-sums anything**; the denominator is `contract.total_points`. **Exclusion is DERIVED state, never an input** — a teacher override can flip which member wins the best-k slot, so the grading-time marks (`graded_by="excluded_by_selection"`) are **provisional display**, and the approval gate **recomputes** from post-override scores; that recomputation is authoritative and is what freezes (`ContractScopeOutcome.counted_in_total`). Unchosen members are **excluded, not zeroed** — on a choose-4-of-6 the two unchosen questions were never owed. *Fixing only one site would have been worse than fixing neither: the teacher would review one percentage and have a different one frozen into the immutable contract.*
- **`app/services/grading_inputs.py` — the two pinned inputs to a grade, and EVD-1's translator.** Holds `transcription_contract_version` (read once, used by all three graded-test creation sites), `scope_answer` (GradableScope → `ScopeAnswer`, used by BOTH graders so v3 and v5 record evidence identically), and `backfill_scope_answers` — the READ-ONLY legacy resolver for rows graded before EVD-1.
  > ⚠️ **The backfill REFUSES rather than guesses, and the refusals are the design.** It resolves nothing when the rubric contract is **stale** (`rubrics.contract_json` keeps only the LATEST contract, so the scope tree the grader used is *unrecoverable* — this is why the answer is stored and not merely recomputed), when the row's pinned transcription contract no longer matches the transcription's (VER-3 earning its keep), when either contract will not parse, or when the recompiled scope set lacks that scope id. Each refusal logs the graded-test id **in the message string** (`extra=` renders nowhere in this service, §8).
  > **The surface then says «לא ניתן להציג את התשובה שנבדקה», NOT «אין תשובה».** Those are different claims and must never be swapped: the first admits our gap, the second accuses the student of leaving it blank. `answerViewOf` returns `missing` **only** when `graded_by == "skipped_no_answer"` — i.e. only when the grader itself found no answer.
- `app/agents/grader/` — the GraderAgent: `grader.py`, `validator.py` (pure), `prompt.py` (`GRADING_PROMPT_VERSION`), `schemas.py`.
- `app/services/graded_test_contract_compiler.py` — approval gate + `GradedTestContract` compile.
- `app/services/grading_runner.py` — `run_grading(graded_test_id)`: request-context-free; **atomic CAS pending→grading** (duplicate-delivery no-op), then advances the row; owns its own session. Runs inside `/internal/grading-jobs/{id}/run`.
- `app/services/transcription_job_runner.py` — `run_transcription_job(job_id)`: CAS `queued→running` → GCS download → pipeline → ONE transaction (transcriptions INSERT + job→completed; zombie completions rolled back); heartbeat sidecar (~60s); bounded doc re-run on retryable transport failure, **now gated on the remaining budget**; failures land on the row with the net_diag verdict. Runs inside `/internal/transcription-jobs/{id}/run`.
- **`app/services/transcription/budget.py` — the per-document wall budget (2026-09-10). THE transcription analogue of PR-2's `extraction_task_budget_s`, and it exists because transcription stacked THREE retry layers that could not see each other and therefore MULTIPLIED:** the scheduler's transport retry (×2) × `Pipeline._call_and_parse`'s parse re-request (×2) × the runner's doc-level re-run (×2), all on one global `timeout_s` of 240 s = **1,920 s worst case against a 900 s Cloud Run request timeout**. `transcription_task_budget_s` (480 s) is clocked from the CAS claim — so the GCS download is inside it, never assumed away — and threaded down as `deadline_seconds`. **Its enforcement shape is what makes a short number safe: it NEVER cancels a call in flight.** It only `clamp`s the next call's timeout and `require`s that a phase not BEGIN work it cannot finish, so a slow-but-succeeding upload keeps its patience and a document dies at a phase boundary. Optional passes treat exhaustion as their own defined degradation (skip, keep the text); ESSENTIAL phases (P1, P2) raise `BudgetExceeded` → a `failed`, retryable row, because transcription feeds grading (a consuming path, §3.5a) and a partial transcription presented as complete is a silent repair (FC). **`deadline_seconds=None` ⇒ unbounded ⇒ the eval path** (PR-2's seam), so `check_goal.sh` is untouched by construction.
- `app/services/rubric_extraction_runner.py` — `run_extraction_job(job_id)`: drives a `rubric_extraction_jobs` row `queued→extracting→completed|failed`; owns the queued→extracting CAS (idempotency for both execution modes); short heartbeat sessions, never a transaction across the extraction.
- `app/services/cloud_tasks_service.py` — the execution substrate in one place: `JobKind` (extraction/transcription/grading — path, queue, mode, inline runner), `enqueue_job` (cloud_tasks|inline), `enqueue_grading_task_or_log` (shared by all five grading kickoff sites), OIDC/shared-secret verification of every `/internal` call. `app/services/job_liveness.py` — the generic LIV-1 `LivenessRule` (arms of status+clock+TTL+reason, SQL and Python forms from one rule); instantiated by `extraction_job_liveness` (public API unchanged), `transcription_job_liveness`, `grading_job_liveness`.
- `app/services/graded_test_revision.py` — `extend_chain()` (the deferred-FK insert).
- **`app/services/plan_store.py` + `plan_build_runner.py` + `plan_job_liveness.py` — the compiled-plan store and builder (PLAN COMPILER v2, migration 026).** `plan_store` is the ONLY writer of `grading_plans` and the only place the contract hash is computed; `plan_build_runner` runs a build (Cloud Tasks target `/internal/plan-jobs/{id}/run`, inline in dev) and resolves a plan for a grade; `plan_job_liveness` is the LIV-1 instance (queued 90-min backstop, building 5-min heartbeat TTL). `app/agents/plan_compiler/` is the compiler itself (`compile.py` C1–C7, `segment.py`, `route.py`, `assemble.py`, `models.py` — the two Anthropic price cards, pinned equal to the eval registry).
- `app/services/handwriting_transcription_service.py` — VLM transcription (legacy engine; swappable `VLMProvider`).
- ⚠️ **Page ENCODING runs in the executor, not on the event loop (Stage C1, 2026-09-05).** `pdf_render` always did; the resize + encode + base64 that follows it did not — twice per page since the strike-check pass. At `cpu=1000m` with `containerConcurrency=4` that CPU sat on the loop and starved the teacher's interactive uploads on the same instance (appends 0.43s → 5.3/5.9/15.6s exactly when they overlapped a transcription with the same `instanceId`). Both sites now call `_encode_pages_sync` through `run_in_executor`. **`stitch` is POSITIONAL on purpose** — `run_in_executor` forwards only positional arguments, and a keyword-only parameter there raises `TypeError` on every call, inside the executor, on a path no unit test of the pure encoder reaches. **`Pipeline._encode_lock` is load-bearing too**: offloading also made the encode AWAIT, and the chunks run under one `gather`, so whichever finished encoding first dispatched first — the SMALLER chunk, reliably (a 5-page/3-per-call doc issued its 2-page call before its 3-page one, 8/8 trials; caught by the eval suite's `test_pipeline_chunking_and_packing`). Encodes were already serial before C1 (inline, no await between them), so the lock costs nothing and restores the exact dispatch order; it is per-instance and a Pipeline is per document, so it never serializes one teacher's batch against another's. It runs on a **dedicated 2-thread `_ENCODE_POOL`, never `run_in_executor(None, …)`**: the default pool is `min(32, cpu_count+4)` = 5 threads at cpu=1000m, `asyncio.to_thread` resolves to the same one, and `docx_v3/pipeline.py` + `rubric_service` push blocking `.invoke` calls bounded at 360s×2 through it — so encodes could queue for minutes behind an extraction, which is the exact latency this stage exists to remove. Two threads because the per-document lock already bounds each doc to one encode, encoding is not the bottleneck (~1s/chunk vs 20–60s model calls), and concurrent encodes are NEW transient memory the 2026-08-23 `--concurrency=4` measurement did not include (BACKLOG B-31f). The bytes are unchanged BY TEST (`tests/services/test_pipeline_encode_offload.py` — byte-identity across formats and sizes, page order, a loop-responsiveness check, and the dispatch-order pin), because ruling R1 freezes what the model sees.
- `app/services/transcription/two_phase/` — the two-phase transcription pipeline core (P1 perception → P2 segmentation + prompts/parsing/corrector/instrument; relocated 2026-07-08 from the eval suite, which now shims to it — production runs the exact code the suite measures). `app/services/transcription/flagging.py` + `page_provenance.py` — pure trust-layer modules (cross-reader disagreement flags, deterministic page attribution), shared with the suite's `flag_metrics.py`. **⚠ The pipeline has TWO transport timeouts, and conflating them was a live defect.** `PipelineConfig.timeout_s` (240 s) is the ESSENTIAL-call timeout, and its own comment earns that number entirely on P1's multi-MB image uploads over congested uplinks. `optional_pass_timeout_s` (**40 s**, owner-ruled 2026-09-10) governs the strike check and the readers, plus `optional_pass_budget_s` (**120 s**) as a whole-phase belt via `asyncio.wait_for`. **WHY:** on 2026-09-10 five documents were submitted together; four landed in 47–78 s and one took ~600 s, leaving ONE log line — `strike_check page 2 vote 1 failed; casting no ranges`, written 521.8 s after the claim. The strike check (7.8 s median, result free to discard) had inherited P1's 240 s ceiling and spent 240 + backoff + 240 on one hung call before discarding its own result exactly as designed. **«checker must never sink the doc» had been implemented as "never RAISE", not as "never DELAY".** An optional pass must be bounded in TIME, not merely in blast radius — the policy `identity.py` already had (`CALL_TIMEOUT_S` 60 s + `TOTAL_TIMEOUT_S` 150 s belt, both measured; identity KEEPS its 60 s, owner-ruled), now generalized. The entry guard `can_start(optional_pass_budget_s)` is the strong one and the clamps sit under it, so **`optional_pass_budget_s ≥ optional_pass_timeout_s` is load-bearing** (pinned). `app/services/transcription/two_phase_engine.py` — production entry (models, `PROD_CONFIG`, TrustRun→TranscriptionDraft adapter); selected by `settings.transcription_engine="two_phase"` (default `"legacy"`). ⚠ **The cross-reader flag layer is RETIRED in production (2026-08-07, owner-ruled):** `PROD_CONFIG` = `v1_trust` minus `reader_model_keys`, with P2 switched to **gpt-5.6-luna at `p2_reasoning_effort="medium"`** (owner decision 2026-08-07/11, mirroring the suite's `v0.json`; the effort knob is a `PipelineConfig` field plumbed through the provider protocol — P2-only, non-OpenAI adapters ignore it; nano kept in `_MODELS` as the one-line revert target; engine version `two_phase/v3_p2-luna`) — on real docs where the baseline reads correctly, reader flags were ~100% false (cheap readers normalize faithfully-captured student errors, `i+2`→`i+=2`; evidence in the engine docstring), the exact click-through-training failure INV-6's history warns about. **Student identity travels a SEPARATE channel** (B-25, 2026-08-12): `identity.py` — one gemini-pro call over a top-35% crop of page 1, filename as name-plausibility fallback, concurrent with the pipeline, never-raises → `student_name_suggestion` → the conservative exact match; the P1 verbatim prompt still excludes the identity block by design (do NOT fold identity back into P1 — t1.3 precedent). The engine still emits `vlm_unparseable` + `code_lint`; the flag→annotation adapter is kept dormant (pre-retirement drafts render; the frontend severity-gates `reader_disagreement` to warning-tier only); the eval suite still measures the full layer via `configs/v1_trust.json`. Re-enabling is config-only but eval-gated (B-24 — any new verifier must beat the falsification record in `flagging.py`). `batch_triage.compute_flag_verdict` speaks both engines' vocabularies: empty answers → `missing_answers` (a fact, never `low_confidence` — two_phase `confidence` is page-attribution similarity, 0.0 for skipped questions). ⚠ **`code_lint` is NOT a triage reason (owner-ruled 2026-09-06)** — a brace imbalance is usually the STUDENT's own missing brace, so it fired on most CS documents (52 annotations over 35 docs in one production run) and sent them all to needs-eyes: the same click-through-training failure as the reader flags above. The engine still WRITES the INFO annotation and the review surface still renders it as an answer-level badge (`review-flags.ts`) — it just no longer decides where a document lives. Removing it from `compute_flag_verdict` means removing it from the cross-pinned `tests/fixtures/flag_reason_vocabulary.json` too, or its twin tests fail in both languages.
- **`app/services/returned_exam.py` — the artefact the STUDENT receives (PR-G9).** Renders from the CONTRACT only: original pages + a vector stamp on page 1 + paginated RTL feedback appendix. Three things here are load-bearing and were each established by MEASUREMENT, not assumption:
  - **The Hebrew face is VENDORED** (`app/assets/fonts/Assistant-Regular.ttf`, OFL licence beside it). `pymupdf-fonts` carries no Hebrew face at all, and without an embedded one PyMuPDF silently falls back to a machine font — perfect on a laptop, tofu on Cloud Run. It is instanced to weight 400 because PyMuPDF ignores CSS `font-weight` on a variable font and would otherwise embed ExtraLight. `helv` cannot render Hebrew either: the stamp word came out `????` until it took the vendored face. Pinned by `appendix-has-no-notdef-glyphs` and the stamp-face test.
  - **PyMuPDF's Story does HALF the bidi algorithm** — it reverses characters inside a directional run but lays the runs out left-to-right in logical order. A pure-Hebrew paragraph is one run and looks perfect, which is why this hides; add one code token (`i+=2`) and the sentence reads backwards. `_bidi_for_pymupdf` runs the real algorithm (`python-bidi`, already a dependency) and flips each RTL run back, because PyMuPDF is about to flip it again; for pure Hebrew the transform is the identity. **Three alternatives were falsified against a render — do not retry from first principles:** U+2066/U+2069 isolates, plain `get_display()` with no flip-back, and splitting runs on any neutral (which reversed the word order of pure Hebrew). `insert_textbox` is a different path that does NO bidi and takes the visual string. Identifiers (`q1.א`) get an LTR base so they read the same in the PDF as on her screen.
  - **Staleness is by omission.** The cache key covers every input that can change a pixel; a row whose key does not match is EXCLUDED from the ZIP and named in the manifest, never re-served. A returned exam rendered under a superseded contract looks entirely correct and would be the one failure this feature cannot have (§3.5a).
- `app/services/gcs_service.py`, `document_parser.py`, `email_service.py`, `auth_service.py`, `rubric_management_service.py`.

### Models (`app/models/`)
- `grading.py` — `Rubric` (now carries `extraction_job_id` provenance FK), `GradedTest` (revision chain, JSONB draft/contract, cost columns), `GradingBatch`.
- `rubric_extraction_job.py` — `RubricExtractionJob` (PR-1 async extraction lifecycle).
- `transcription_job.py` — `TranscriptionJob` (Cloud Tasks migration, migration 016): one durable row per landed batch PDF (B9: created by the append, not by `create_batch`; `expected_test_count` — migration 025 — is what she declared, jobs are what arrived, and the difference is the upload stage); CHECK `transcription_jobs_status_consistency`; `grading_batches.transcription_failures` (015 ledger) is DORMANT — legacy read-only, dropping it is B-27.
- `transcription.py` — `Transcription`. `student.py` — `Student`. `classroom.py` — `Class`, `ClassMembership`. `subject_matter.py`, `user.py`, `rubric_share.py`.
- `raw_rubric.py` — **DEPRECATED**: never populated by any code path; its intended purpose (extraction JSON + provenance + filename) is subsumed by `rubric_extraction_jobs`. Do not wire new writes to it; dropping it (+ `rubrics.raw_rubric_id`) is a later cleanup migration.

### Migrations (`backend/migrations/`)
Raw SQL, zero-padded, sequential (`NNN_description.sql`). No Alembic. Current head: **028**. The schema is created/reshaped by 007 (cleanup) + 008 (new schema); 009 (graded-test cost columns); 010 (revision-chain deferrable FK); 011 (S11 transcription `batch_id` + batch `test_count`); 012 (`rubric_extraction_jobs` + `rubrics.extraction_job_id`); 013 (`schema_migrations` ledger + commit-token convention); 014 (`transcriptions.review_json`); 015 (`grading_batches.transcription_failures` ledger — dormant since 016); 016 (`transcription_jobs` — the Cloud Tasks batch fan-out); 017 (`transcription_jobs.client_file_id`); 018 (`schools` + `users.school_id`, PR-G6); 019 (`graded_tests.opened_at`, PR-G8); 020 (`grading_batches.appendix_include_criteria` + `stamp_position_default`, PR-G9); 021 (`graded_tests.returned_exam_key`, PR-G9); 022 (onboarding: `users.gender` + `users.onboarding_completed_at` + the ordered `user_schools` junction); 023 (`schools.ministry_symbol` + its partial unique index; 018's whole-table name index narrowed to the symbol-less rows); 024 (auth: `users.email_verified_at` + `email_verification_codes` + `auth_nonces`); 025 (`grading_batches.expected_test_count` — the upload-stage in-flight fact); 026 (`grading_plans` — compiled GradingPlans keyed by contract hash, PLAN COMPILER v2 production wiring); **027 (`rubrics.subject` — the multi-subject seam: NOT NULL, server-default `computer_science`, backfilled from the contract/draft JSON, indexed. ⚠ APPLIED TO Vivi-Test ONLY as of 2026-09-09 — production needs it before any rubric read succeeds)**; **028 (the onboarding next-exam step + outreach queue: `users.next_exam_date` / `next_exam_answered_at` / `next_exam_reask_email_sent_at` / `phone` / `whatsapp_opt_in` / `guided_session_requested_at`, plus the partial index `idx_users_reask_candidates`. ⚠ APPLIED TO Vivi-Test ONLY as of 2026-09-09 — it lands on top of 027, which production also lacks)**. Caveat: the `rubrics` and `grading_batches` base tables predate migration 001 (created unversioned via `create_all`) — the numbered series only ALTERs them. The ORM mirrors the migrated schema — it does not generate it. When the DB and a schema doc disagree, the DB is truth.

> **PR-G6 attribution under multi-school (022, owner-ruled 2026-08-31).** A teacher may list
> several schools. `users.school_id` REMAINS the single override-attribution key and holds
> `user_schools.position = 0`; the junction is the full truth, the column is the key drawn from
> it. `override_attribution.py` is unchanged and still reads one column. **`position` is not
> decoration** — a many-to-many has no inherent order, so without it a profile read can name a
> different "first" school than the key points at, and a teacher re-submitting the list she was
> shown silently moves her own attribution. Both surfaces are written by ONE function
> (`school_resolution.set_user_schools` / `ensure_user_school`); the `User.schools` relationship
> is `viewonly` precisely so a second writer cannot exist. Pinned by
> `tests/api/test_onboarding.py::test_schools_first_is_the_attribution_key`.
>
> **School IDENTITY is the Ministry symbol, not the name (023, owner-ruled 2026-08-31).**
> `schools.ministry_symbol` (סמל מוסד) is THE identity when present; the normalized name governs
> only rows that lack one (a school the teacher typed herself). Measured against the real export:
> 2,194 institutions carry unique 6-digit symbols, but **82 normalized names are shared by 213
> rows, and 15 of those groups share a CITY too** — thirteen pairs plus two triples, the largest
> being three «ישיבת חזון נחום» in בני ברק (541201 / 541847 / 541854) — so name+city cannot
> separate them either. Two consequences worth knowing before touching this:
> * **018's index HAD to be narrowed, not merely supplemented.** It was UNIQUE on the normalized
>   name across the whole table, i.e. it forbade the second «בית אקשטיין» outright — adding the
>   column alone would have achieved nothing. 023 replaces it with two partial uniques, each
>   naming its population: symbol-bearing rows unique by symbol, symbol-less rows unique by name.
>   Both are pinned in `EXPECTED_PARTIAL_INDEXES`; recreating either without its `WHERE` silently
>   restores the old bug while still being "present" by name.
> * **A symbol NEVER adopts a name match.** Stamping a symbol onto an existing symbol-less row
>   with the same name would invent exactly the identity the column exists to establish. The
>   honest outcome is two rows — one known institution, one "a school someone typed" —
>   reconciled later by an operator with evidence, never by an automatic UPDATE.
> Pinned by `tests/api/test_onboarding.py` (the rules) and
> `tests/api/test_onboarding_real_dataset.py` (the same rules driven with the real 2,194-row
> export, read in place from `frontend/src/data/israeli-schools.ts`).
>
> **The onboarding outreach queue (028, 2026-09-09).** Six columns on `users` feed one Google
> Sheet a human works. The named protocols, which ARE the spec (§0.3):
> * **ONB-1 MinimalValidation** — the exam step never blocks and the endpoint refuses exactly
>   two things: a date outside `today−7d … today+18mo`, and consent with no phone. **There is no
>   phone-format validation anywhere** — the column stores what she typed, and normalisation to
>   E.164 happens on READ, in `onboarding_reask.normalize_phone_e164`, where failing costs a link
>   and not a record.
> * **ONB-2 UnknownIsAnAnswer** — «עוד לא יודעת» stamps `next_exam_answered_at` with a NULL date.
>   That pair is the whole state machine: there is deliberately no `unknown` boolean, no
>   `reask_due_at` (it is `answered_at + 14 days`) and no step-completion stamp. Re-adding any of
>   them is an open decision, not a convenience.
> * **ONB-3 DBIsTheRecord** — the sheet is a DERIVED VIEW. Nothing ever reads it back, and
>   `python -m app.scripts.rebuild_onboarding_sheet` reconstructs A:J from `users` alone. That is
>   what makes `ONBOARDING_SHEET_ID` unset a supported no-op rather than an outage.
> * **ONB-4 OwnedFactsOnly** — we store that she ASKED for a guided session, never when the call
>   was scheduled for: Cal.com owns the booking, she can reschedule there, and a mirrored date
>   would go stale while still being believed.
> * **ONB-5 UpsertOnUserId / ONB-6 DBColumnsOnly / ONB-7 RawAndISO / ONB-8 NeverThrows** — the
>   sheet rules, all four enforced in `onboarding_sheet_service.py`. **K:M are a HUMAN's**
>   (סטטוס פנייה / שיחת ליווי / הערות) and every write range is built by `_row_range`, which
>   cannot name a column past J; a write that reached K would erase the note explaining why a
>   teacher must not be called again.
> * **The consent gate is a legal boundary, not a preference (owner ruling OD-2).** Storing a
>   phone is NOT consent to message it — she may have given it to be CALLED. `whatsapp_opt_in` is
>   the only thing that may authorise a WhatsApp message, and BOTH consumers read it: the digest
>   emits a `wa.me` link only when true, and sheet column E spells out «ואטסאפ: מאושר» or
>   «ואטסאפ: לא מאושר» beside the number, because a bare number would be read as permission by
>   whoever works the queue. Column E carrying the consent state is a deliberate deviation from
>   the spec's "blank if none": a new column is not available, since inserting one before K
>   shifts the human-owned columns, which ONB-6 forbids.
> Pinned by `tests/api/test_onboarding_exam.py`, `tests/services/test_onboarding_sheet.py` and
> `tests/services/test_onboarding_reask.py`.

**Migrations are the only DDL source. `create_all` is a fresh-dev-database bootstrap only.** Two rules, both enforced by `tests/test_schema_canon.py`:

1. **Every migration ENDS with its own commit token** — `INSERT INTO public.schema_migrations (version, note) VALUES ('NNN', '...') ON CONFLICT DO NOTHING;` as the **last statement**. The row is a commit token, not a label: it only lands if every statement before it landed, so a partially-applied file leaves a *gap* the boot check sees. This is not ceremony — migration 011 half-applied in production (statement (a) landed, (b) didn't) and stayed undetected for weeks. A ledger that merely recorded "011 was run" would not have caught it.
2. **Add the version to `EXPECTED_MIGRATIONS` in `app/database.py`.** At boot, `verify_schema_head()` set-compares the ledger to that tuple and logs `SCHEMA OK` or a loud `SCHEMA MISMATCH ... NOT APPLIED` **ERROR** (it never crashes — a deploy landing mid-migration-window must still boot so you can finish applying). The check is set-based, not `MAX(version)`: a max check reads head 013, compares to expected 013, and reports all-clear while 011 is missing from the middle.

`init_db` runs `create_all` **only** when `APP_ENV` is a dev env **AND** the target DB has no `schema_migrations` ledger. The ledger check is the load-bearing half: a dev `.env` routinely carries `APP_ENV=development` *plus* the live `DATABASE_URL` (that is how the integration tests run), so an `APP_ENV`-only gate would still `create_all` **production** from a laptop. The ledger is a property of the *database*, not of the process's opinion about itself.

> ⚠️ **`logger.info(..., extra={...})` fields are NEVER RENDERED in this service.** `app/main.py` configures logging exactly once — `basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')` — with no dictConfig, no JSON formatter and no `google-cloud-logging`. `extra` attaches attributes to the LogRecord; rendering them needs a formatter that names them, and there isn't one. So the line Cloud Run captures is the MESSAGE alone. This silently voided Stage D's entire measurement (the code looked right, the tests passed, and the data was simply absent a week later). **Anything you intend to QUERY goes in the message string**; `extra` is fine as documentation for a future structured formatter. Adding one is BACKLOG B-31g.

### Tests
`tests/` mirrors `app/`. Pure compilers/validators (`gradable_compiler`, `graded_test_contract_compiler`, grader `validator`) are tested with **zero mocks**. The agent and endpoints mock the LLM (patch `with_structured_output(...).ainvoke` / inject a fake `VLMProvider`) — **never call OpenAI in tests.** `pytest -q`.
⚠️ **Tests never send real mail, and this is now pinned in `tests/conftest.py`** (`EMAIL_PROVIDER=console`, set with the DATABASE_URL redirect, BEFORE `app.config` is imported). §9's "every test process is an unconfigured environment" stopped being true the day `backend/.env` grew `EMAIL_PROVIDER=resend` for local development: from then on every signup in `tests/api/` sent a REAL verification email to a fabricated `@s2test.com` address. It went unnoticed because it WORKED — until Resend rate-limited the sender mid-suite (429 → the signup endpoint's 502), which ERRORED every fixture that signs a user up. An explicit override still wins, so a test that means to exercise a provider can ask for one.

**Tests run ONLY against the Vivi-Test database** (Supabase `eqnbojbxsdafwtxvuyuy`): `tests/conftest.py` redirects via `TEST_DATABASE_URL` and hard-aborts any session whose resolved (host, pooler-tenant) is not allow-listed — production can never be reached from pytest again (2026-08-23; the s2test.com residue this prevented has been purged). ⚠️ **Run the full suite in two invocations** (`pytest --ignore=tests/transcription_eval_suit` + `pytest tests/transcription_eval_suit`, or per-directory like CI): a single-process all-907 run executes every test green but then WEDGES in the session-scoped TestClient teardown — the app lifespan's loop-close hangs in Windows `IocpProactor._poll` on an orphaned pooled-connection op after ~700 tests of churn (py-spy-verified 2026-08-23; survives `engine.dispose()`). Windows-only, teardown-only; prod (Linux, SIGTERM) unaffected.

---

## 9. The auth & ownership pattern (every domain endpoint)

> **⚠️ AUTHENTICATION ITSELF (migration 024, owner-ruled 2026-09-01).** Two ways in, one session.
> * **Sign in with Google** is the ID-TOKEN flow, not the code flow: the GIS button hands the
>   browser a signed JWT, `POST /auth/google` verifies it and mints our ordinary HS256 session.
>   No client secret, no redirect URIs, no refresh tokens — do not add them without a reason to
>   call Google APIs as the teacher. `users.google_id` holds the token's **`sub`**, never the
>   email: a Google account's address can change, and keying on it would fork her account.
> * **A nonce is mandatory and stateful.** `auth_nonces` makes a Google credential single-use;
>   `consume_nonce` is ONE atomic UPDATE with its conditions in the WHERE clause, because a
>   read-then-write there is the exact race the nonce exists to prevent.
> * **THE LINKING RULE (A3), and it is a security boundary.** A Google identity is linked to an
>   existing account only when that account's email was PROVEN. Matching emails is how a candidate
>   is FOUND; it is never why a link is allowed. Signup writes a row for any address, so an
>   attacker can pre-register `victim@school.org` — linking on a bare email match hands him her
>   Google identity (Microsoft "nOAuth" 2023; Sign in with Apple 2020). The decision is the pure
>   `google_identity.decide_link` — four inputs, four outcomes — so it is enumerable without
>   mocking Google. Pinned by `tests/services/test_google_identity.py` and
>   `tests/api/test_google_auth.py::test_REFUSES_to_link_into_an_UNVERIFIED_account`.
> * **Signup no longer returns a session (A4).** `POST /auth/signup` answers
>   `{verification_required: true}`; `POST /auth/verify-email` is what issues the JWT. **And
>   `/auth/login` refuses an unverified account with 403** — without that half the ruling is
>   decorative, since the attacker just logs in with the password he chose. 403 and not 401 is
>   load-bearing: the password was RIGHT, and the client opens the code panel instead of claiming
>   she mistyped it. Rows predating 024 are grandfathered by the migration.
> * The **code** is 6 digits, 10 minutes, bcrypt at rest, 5 attempts, 60s resend cooldown — and the
>   counters live on the ROW, because Cloud Run runs up to 60 instances and an in-process counter
>   would hand an attacker 60x the budget while the logs claimed the limit held.
> * `/resend-code` always answers **202 with the same body** (unknown, verified, cooling down, or
>   sent) so it cannot be used to ask whether an address has an account.
> * Email goes through `EMAIL_PROVIDER` (`resend` | `gmail` | `console`), defaulting to
>   **console** — an unconfigured environment, and every test process is one, must not send real
>   mail. Resend needs only DNS on vivi-assistant.com; the Gmail provider needs Workspace
>   domain-wide delegation and remains uncalled.


Established once, copied everywhere (the rubric endpoints are the reference implementation):
- `current_user: User = Depends(get_current_user)` — required; public endpoints (login/signup/refresh/health) are the only exceptions.
- The owning `user_id` is **always** `current_user.id`, **never** from the request body **or a query parameter**. A caller-supplied `user_id` is a privilege-escalation bug.
- **`get_current_user` is imported from `api/v0/auth.py`. Never define a local one.** ⚠️ `users.py` did, for a month, and it is the worst bug this codebase has shipped: a `user_id` **query parameter** it simply trusted (`TODO: Replace with proper JWT authentication`), reading no header, verifying no signature, checking no expiry. It failed in **both** directions at once — rejecting valid session tokens (`GET /users/me` → 401 on a good token) *and* serving anonymous callers who guessed a UUID (`?user_id=<victim>` with **no** `Authorization` header → 200, including an unauthenticated **write** via `PUT /me/subject-matters`, and rubric-share creation that let an attacker share a victim's rubric to themselves). Fixed 2026-08-17 by **deletion, not repair** — two auth implementations cannot stay in agreement, which is the entire reason this section exists. The 401 half hid the 200 half for a month because the only person who tested it held one of the two `active` accounts. Structural guards: `tests/api/test_users_auth.py::test_users_routes_use_canonical_auth` (every route carries the canonical dependency, and any look-alike named `*current_user*` is an offender) and `::test_no_route_accepts_a_user_id_parameter`. **Never fake the auth dependency in tests** — the harness signs up real users and sends real Bearer tokens (`tests/api/conftest.py`); a `dependency_overrides` fake would have bypassed exactly the broken code and this bug would still be live.
- Reads scoped by `user_id`. Detail/update/delete go through `get_owned_or_404` (`app/api/deps.py`).
- Cross-tenant access returns **404, not 403** (403 leaks existence).
- `IntegrityError` (e.g. duplicate-name unique constraints) → **409** with a clear message, after session rollback — never a bare 500. Caveat: `rubrics` has NO `(user_id, name)` unique constraint (unlike `students`/`classes`), so duplicate rubric names insert silently today — the 409 path applies only where a constraint exists. One deliberate exception: extraction-job submit maps its active-job conflict to an idempotent reuse (returns the existing job), not a 409.

---

## 10. Repo map — frontend (`vivi-codebase/frontend/`)

Next.js 14 App Router + TypeScript + Tailwind, RTL Hebrew, Vercel.

> **⚠️ CANON — repo layout & deploy (verified PR-4).** GitHub: **`github.com/sparkwellnessapp/pupal`** (public). Two branches matter:
> - **`main`** — the working branch. Its committed tree is the **`grader-frontend/`** directory (the deployable Next.js app) + `grader-vision-update`. It does **NOT** track `backend/` or the local `frontend/` working copy — those live in the working tree only.
> - **`frontend-deployment`** — the branch **Vercel builds** (its *root* IS the Next.js app). It is a **git subtree of `main:grader-frontend/`** (identical tree hash), maintained by `git subtree push`. There is **no `grader-frontend` branch** — that name refers to the *directory*.
>
> **`frontend/` is the canonical dev source; `grader-frontend/` is its DEPLOY MIRROR.** Develop in `frontend/`; never hand-edit `grader-frontend/` (it is overwritten). **To deploy the frontend:**
> ```
> # 1. mirror dev → deploy dir (exclude node_modules/.next/test-results)
> #    e.g. robocopy frontend grader-frontend /MIR /XD node_modules .next ...
> git add grader-frontend && git commit -m "…"
> git subtree push --prefix grader-frontend origin frontend-deployment   # → triggers the Vercel prod build
> git push origin main
> ```
> **To deploy the backend** (separate — Cloud Run, not Vercel): service **`gradervision-backend`**, project **`gen-lang-client-0438328890`**, region **`europe-west1`**, deployed from the local `backend/`:
> ```
> gcloud run deploy gradervision-backend --source backend \
>   --project gen-lang-client-0438328890 --region europe-west1
> ```
> Existing env/config on the service is preserved (pass `--set-env-vars` only to change it). The census caught `frontend/`↔`grader-frontend/` byte-identical; letting them drift makes every deploy a coin-flip — the mirror-then-subtree-push discipline is the fix, NOT a `git rm` (the subtree is load-bearing). **CI caveat:** the PR-4 workflows in `.github/` assume a monorepo root (`backend/` + `frontend/`); `main` does not track those, so they run only if that structure is committed to `main` (a deliberate restructuring, not done here).
>
> **Remotes (2026-08-04):** this clone has TWO remotes.
> - **`origin`** → `github.com/sparkwellnessapp/pupal` (public) — the historical repo; all the deploy flows above (Vercel subtree push, `git push origin main`) run against it.
> - **`vivi-origin`** → `github.com/sparkwellnessapp/vivi-codebase` (public) — secondary remote holding the **full monorepo** (backend + frontend + grader-frontend + docs). Sync with `git push vivi-origin <branch>`. Nothing deploys from `vivi-origin` — Vercel and Cloud Run are wired to `origin` only.
> - ⚠️ Both remotes are **public**: never commit `.env`, `gen-lang-client-*.json` service-account keys, or seed credentials (the root `.gitignore` is the belt-and-braces net; seed-user migrations were redacted 2026-08-04).

| Area | Notes |
|---|---|
| `src/app/page.tsx` | Main workflow: rubric-select → upload → transcribe → review → grade → draft-review. ⚠️ **It no longer owns the upload queue** (Stage B, ruling R3): it selects files, creates the batch, hands them to the provider and navigates IMMEDIATELY |
| `src/contexts/UploadQueueProvider.tsx` | **THE upload queue, mounted in the root layout** (Stage B). It moved out of `page.tsx` because a page component's XHRs `abort()` on unmount, which is the only reason the redirect used to wait for the LAST BYTE (~4 min on a 2 Mbps uplink) when nothing downstream needed it — jobs enqueue per landed file. `utils/batch-upload.ts` is untouched: the U3 reducer, the `client_file_id` lifetime and "422 is terminal" moved house, not behaviour. **R10: one uploading batch at a time** — `begin()` refuses while a queue is live and NAMES the blocker (reading `batchId` off the context there reads a closure captured before the click). **Letting go of a queue is one of R9's terminal events**: `clear()` and a replacement inside `begin()` settle the declaration to what actually landed and hand the lost filenames to the dashboard's one-shot notice — without that, dismissing the lane abandoned a retryable file and misreported it as "uploading" for 90 minutes. The re-declare change-gate **reopens on failure**: `declaredCount` only decreases, so advancing past a lost PATCH retires that value forever. Still fatal to a transfer: a HARD navigation (reload, logout) — `beforeunload` covers the first, `SidebarLayout` confirms the second |
| `src/components/batch/UploadLane.tsx` | The queue's surface, on the batch dashboard (Stage B). Per-file progress, the server's §3.2 reason verbatim, retry ONLY where a retry can heal (a 422 is terminal), and a REMOVE that re-declares at once. Renders only for its own batch id, and **outlives the transfers when files were left behind** — a batch that is quietly short is the silent drop U4 exists to kill |
| `src/app/onboarding/` + `src/components/onboarding/` | **The onboarding flow (migrations 022 + 028)** — SIX steps in one non-dismissible centered dialog (welcome → subjects → schools → name+gender → **next exam** → ready), on the `batch/Modal` primitive (`dismissible={false}`, `size="lg"`; both props default to the old behavior). Each step COMMITS when she advances past it, so a drop-off keeps her answers; `POST /me/onboarding/complete` stamps the end. `components/OnboardingGate.tsx` (mounted in the root layout) redirects any authenticated teacher whose `onboarding_completed_at` is null. ⚠️ **Every e2e user fixture must carry that stamp** or the gate redirects the whole Playwright suite — `e2e/fixtures.ts::USER` and `e2e/seedBatch.ts::AUTH_ME` do.

**[028] The exam step is the one place where OMISSION IS A VALUE.** `PATCH /me/onboarding-exam` reads `model_fields_set`, not None, and `lib/onboarding.ts::examPayload` returns **null** when she touched nothing. Three facts ride on that and each was a live defect in the first draft: an ABSENT `next_exam_date` leaves her date alone and does NOT re-stamp `next_exam_answered_at` (the app-shell «קבעי שיחה עם נועם» link posts `guided_session_requested` ALONE, and would otherwise erase her date and silently push her 14-day re-ask out by however long she took to click); a `next_exam_date: null` is «עוד לא יודעת», a REAL answer (ONB-2); and a skip sends no request at all, because an empty body would still stamp `answered_at` and claim she answered. `whatsapp_opt_in` is the consent gate and is sent explicitly `false` rather than omitted — storage of a phone is NOT consent to message it (owner ruling OD-2) |
| `src/data/israeli-schools.ts` | The school display index for the onboarding picker. **Dynamic-imported only** (`await import(...)`) — a static import puts a multi-hundred-KB list in every route's shared chunk. Its `id` is DISPLAY-ONLY, never a `schools.id`: a pick commits by NAME and the server resolves it under 018's normalized-exact rule, which is what makes two teachers picking the same school converge on one row. Search lives in the pure `utils/school-search.ts` |
| `src/app/my-rubrics/`, `my-graded-tests/`, `my-classroom/` | Library, graded history, roster (students/classes tabs) |
| `src/components/RubricDocument.tsx` | **The document mirror (PR-5 S2) — the rubric-review surface for the docx flow.** Reads as her DOCX annotated by Vivi (see §11 mirror note) |
| `src/components/RubricEditor.tsx` | **Rollback** rubric editor; owns the save-blocking state machine (§11). Behind `USE_DOCUMENT_MIRROR=false`; the mirror replaces it live |
| `src/components/document/` | Mirror primitives: `EditableText`, `EditablePoints`, `CodeBlock`, `DisclosureRow`, `DataTables` (document-styled trace/context/mini-tables) |
| `src/components/batch-review/` | **THE transcription-review surface**: `TranscriptionReviewSurface` (answer cards + source pages, consumes the DRAFT — serves both flows), `TranscribedTextEditor`, `ReviewItemController` (framework-free Δ4/Δ11/Δ14 state machine), `BatchReviewContext` (the segment-layout entry holder: ONE `mergePayload` writer feeding the **OD2 append-only cursor**, the Δ9 page cache, the R11 soft note, and a 5s poll that runs only while documents are in flight), `ReviewInterstitialModal` (R4) |
| `src/app/batches/[id]/review/` | The per-item review route + its layout. **The cursor MUST live in the layout** — pages remount per dynamic-param value, layouts persist; a page-held ref silently reshuffles (empirically proven; `e2e/batch-review-freeze.spec.ts` is the standing guard). **Δ10 was amended to OD2 (batch-redesign P3): the cursor is PREFIX-STABLE and APPEND-ONLY** — existing entries never move even when their verdicts change; late arrivals append (flagged at the partition boundary, clean at the tail) and the counter bump is the only signal |
| `src/app/batches/page.tsx` | The batches **list** (P5/L1) — mini `SegmentBar` honesty bar + one action line per row, all copy from C1. ⚠️ The list payload carries `rollup` only (no `transcriptions[]`), so the dashboard's clean\|needs-eyes split is **not derivable here**; `utils/batch-list.ts` tells a coarser truth deliberately rather than inventing one |
| `src/components/TranscriptionReviewPanel.tsx` | Single-test review — a ~130-line wrapper over the shared surface, prop seam unchanged; batch behaviors (autosave/accept/indicators) inert by construction. ⚠️ **QUARANTINED since batch-redesign P4/U1: the upload step always batches, so nothing sets the `gradingStep` values that render this.** Its guard is now `TranscriptionReviewPanel.render.test.tsx` — the `single-flow-review-unchanged` e2e was retired with its invariants re-homed (the §4.4a precedent), because it drove the deleted mode-toggle journey |
| `src/components/GradedTestReviewPanel.tsx` | Graded draft review/edit/approve; revision affordances (regrade/manual-edit/retry) |
| `src/components/AnnotationBanner.tsx` | Single severity-differentiated **rubric** annotation renderer (a real standalone file since PR-5 S2 — RubricEditor + the mirror both import it) |
| `src/components/StudentPicker.tsx` | Select-or-create student; reused in single + batch flows |
| `src/components/grade-review/` | The grading gate. ⚠️ **The student's answer is READ from `scope.student_answer` on the graded-test wire (EVD-1) — never joined client-side.** `utils/grade-review-model.ts` used to hold an `answerForScope` that re-implemented `gradable_compiler`'s nearest-ancestor fallback as "exact, else whole-question". Its own header comment claimed parity with the backend and named `q1.א.2` as the example; it silently failed at DEPTH 2, so a leaf inheriting its parent's answer rendered «אין תשובה בתמלול המאושר» **next to a 12/12 grade and a verbatim quotation from the answer it said did not exist**. The join was DELETED, not fixed — the §9 precedent (two auth implementations "cannot stay in agreement", repaired by deletion) applies verbatim to two answer-resolution implementations. `answerViewOf` returns a discriminated `own \| inherited \| missing \| unavailable`, so the contradiction is unrepresentable rather than merely absent, and an INHERITED answer says so on screen (FC — presenting a parent's words as the leaf's own is a silent repair).

**The QUESTION TEXT had the same root cause and a different shape.** `GradeReviewContext.extractQuestions` walked exactly ONE level and emitted BARE sub-question ids, while scope outcomes are keyed by the FULL PATH (`א.1`) — so on a two-deep rubric it produced no entry for the graded scope AT ALL, and the «השאלה» disclosure rendered the whole-question stem or, when the parent carried no prose of its own, nothing. It now recurses with full paths, and `questionTextForScope` walks the chain via the shared `ancestorPaths` (own → nearest ancestor → whole question) instead of probing exact-then-null. Unlike the answer this is NOT evidence — it is rubric content the client already holds — so resolving it client-side is legitimate; resolving it at only two depths was not. Pinned by `extractQuestions.test.ts`, driven by the real reported rubric |
| `src/lib/api.ts` | API client; `getAuthHeaders()` on every authenticated call |
| `src/types/` | TS mirrors of backend schemas |

**Frontend lockstep:** every backend sprint that changes an endpoint or type ships its frontend change in the same PR. **Subject modularity (§3.3) applies:** shared components and `utils/`/`types/` stay subject-agnostic; CS-specific UX lives in CS-specific surfaces only.

### The fetch seam + error-surface convention (PR-2)

- **One seam.** `src/lib/api.ts` exports `apiFetch<T>` (auth headers in, typed `ApiError`/`ApiAuthError` out, JSON back). **Every ordinary call goes through it** — there are no hand-rolled `fetch` sites left in `api.ts`. Two deliberate carve-outs use non-throwing `apiFetchRaw`: the **streaming** transcription fns (they read `response.body`, which a JSON parse would consume) and the rubric **save/update/compile** fns (they *read* non-OK bodies for the warnings modal / `RubricSaveError`); both still call `throwIfAuthError` so 401 stays terminal.
- **Auth endpoints are NOT on the seam** (`auth.tsx` uses raw `fetch`, on purpose). A wrong password legitimately returns 401 — routing login through `ApiAuthError` would report it as "session expired" and trigger the stash-and-logout flow on a failed login.
- **No silent retries at the seam.** A mutation must never auto-repeat (a retried `POST /grade` is a duplicate grade). Poll-loop retry lives in the hooks/holders, where it is visible, bounded, and **terminal on 401/403** (`useExtractionJob`; the batch dashboard's own poll; `BatchReviewContext`'s in-flight-only poll). ⚠️ *This line used to cite `useBatchProgress` — that hook exists only in the stale `grader-frontend/` deploy mirror, never in `frontend/src/`.*
- **Upload is a bounded XHR queue, not `fetch`** (P4/U3): `appendBatchFileXHR` exists because `fetch` cannot observe upload progress. The `client_file_id` is minted ONCE per selected file and reused by retries — that is B9's idempotency contract, and it is why a retry cannot duplicate a test. A 422 is a validation verdict: **terminal, never auto-retried.** It also carries `X-Upload-Started-Ms` (Stage D/R11) so the server can log a real uplink distribution; **log only**, and the server omits the figure rather than fabricating one when the arithmetic is unsound. The queue that drives it lives in `UploadQueueProvider` (above), not in the page.
- **Copy gates are executable** (P5): `npm run check:copy` (`scripts/check-copy.mjs`) enforces OD4 (`אצווה` → `מקבץ`), no raw status enums as text, LTR-isolated file sizes, and feminine imperatives **blocking on the five batch surfaces** / reported as inherited debt elsewhere. It strips comments before matching and anchors on word boundaries (`נבחר`/`לאשר`/`תיצור` are not violations).
- **Error-surface convention:** **transport/auth → sonner toast** (`lib/errorSurface.ts`); **domain/validation → the existing inline `setError` banners + the wizard modal**. Do not migrate the ~54 inline sites — a point-sum violation is not a network failure.
- **Session (`lib/session.ts`):** the JWT TTL is 7 days and `POST /auth/refresh` **already existed but was never called**; it is gated on a *valid* token, so it renews **before** expiry only. The client decodes `exp` locally and renews inside a 48h window (on mount / focus / 15-min tick), which makes mid-session expiry effectively unreachable for an active teacher — with **zero backend change**. The backend cannot distinguish expired from malformed (both → 401 "Not authenticated"), but the **client can**, which is how it says "פג תוקף ההתחברות" honestly.
- **Crash-stash:** before any forced logout, in-progress *review edits* are stashed to `localStorage` and offered back after login. PR-1 already made the extraction *result* durable server-side (the job row); the stash protects the teacher's **edits on top of it**. General draft autosave is PR-5.
- **Tests:** `npm test` (vitest — pure logic + SSR render tests) and `npm run test:e2e` (Playwright, PR-4 — the render-half guard, route-mocked; browsers install in CI). There was no frontend test runner before PR-2.

### Codegen — the wire types are GENERATED (PR-4, R-B)

`src/lib/api-types.ts` is **generated** from the backend OpenAPI schema (`npm run gen:api` → `scripts/gen-api-types.mjs` → `backend/scripts/dump_openapi.py` + pinned `openapi-typescript`). **Do not hand-edit it.** A GitHub Actions job (`.github/workflows/api-types-drift.yml`) regenerates it in CI and fails on any diff — the wire contract's `suite_hash`. This kills the Decimal type-lie **at the source**: a `Decimal` types as `string` in the schema (matching the wire), so generated types never claim `number` for a field the wire sends as a string. **Two type families coexist BY DESIGN and are NOT interchangeable:** the generated **wire** types (string points, wide unions) feed `api.ts`; the hand-written **editor** family (`types/rubric.ts`, number points, narrow unions like the `question_type` literal set) is what the editor mutates. The seam (`rubric-transform.ts`) is guarded by the golden round-trip suite, **not** the compiler — TS never errors on ignoring a wire field (§11). New/touched wire types consume the generated ones; hand-written mirrors migrate opportunistically. The one deliberately hand-written response type is `CompileErrorDetail` — the 400 compile-rejection rides an HTTPException `detail`, which FastAPI leaves out of the OpenAPI schema.

### Code-in-RTL editors — the bidi standing rule (batch-review PR, empirically adjudicated)

Transcription/code editors inside the RTL app are **pure `dir="ltr"` islands — nothing more**. `unicode-bidi: plaintext` was proposed for per-line direction and **empirically falsified**: plaintext resolves paragraph direction from the FIRST STRONG character, so a Hebrew-initial comment line (`// תכונות`) goes RTL-base and the `//` migrates to the RIGHT of the Hebrew — the exact defect it was meant to prevent. The Playwright test `rtl-bidi-code-comment-rendering` (bounding-box x-comparison) is the standing guard; do not reintroduce plaintext from first principles — run that test against any new mechanism.

### Trust surfaces — the teacher decides (PR-4)

- **No silent auto-ack.** A save that returns warnings now shows `RubricWarningsModal` and resends acked ids ONLY after an explicit teacher confirm (`page.tsx`). The old blanket `annotation_type !== 'invariant_violation'` filter is gone — it silently confirmed the teacher's *own* flagged mismatch and would swallow any future warning class (§0.2; Vivi proposes, the teacher decides).
- **The structured compile rejection reaches the teacher.** `RubricErrorDisplay` renders the invariant chip + expected/actual + a **jump-to-node** anchor (clicking `location` scrolls to the full-path `data-scope-id`). The fields were always on the wire (`_compile_error_payload`); PR-4 typed (`CompileErrorDetail`) and rendered them.
- **Selection is achievable-aware CLIENT-side.** `utils/rubric-achievable.ts::computeAchievablePoints` mirrors the backend `compute_achievable_points` (the INV-4 arithmetic; pinned by a golden parity test). Client INV-R3 uses it (no longer *abstains* on selection exams), and the editor header/stats show the **achievable** total and recurse — no client aggregate renders the offered sum as "the total" (the census E10 class). `graded_by="excluded_by_selection"` renders a scope badge; the backend emits no annotation for it, so the badge is the only surface.

---

## 11. The save-blocking UX state machine (`RubricEditor.tsx`)

Load-bearing, easy to get wrong. `hasBlockingAnnotations = annotations.some(a => a.severity === 'ERROR')`. When true: the Save button shows a **blocked-but-clickable** state (clicking reveals the blockers list, does **not** submit), a top-level summary banner lists every ERROR with anchored navigation, and inline ERROR banners render at each violating scope. When false, Save compiles Draft → Contract. **A native `<button disabled>` cannot be clicked** — use a custom `blocked` prop that styles as disabled but keeps `onClick` wired to the show-blockers handler. The client validator is early-warning; **the Contract compiler is the authority** — server-returned ERROR annotations trigger the same UX. The graded-test approval screen (`GradedTestReviewPanel`) follows the same principle: unresolved `error` annotations block Approve.

### The frontend rubric codec is RECURSIVE and must stay a faithful round-trip (B-11)

The frontend mirrors the backend's arbitrary-depth ontology (`q1.א.2`), not a depth-1 subset. Three coupled pieces recurse and **must not drift** from each other or the backend:
- **Codec** (`utils/rubric-transform.ts`): `hydrate/dehydrateSubQuestion` recurse over nested `sub_questions`. Every wire field is either **modeled** (emitted by name — points, structure, editable scalars) or **carried** (moved verbatim through a typed `_carry` bag), disjoint by the `MODELED_*_KEYS` manifests. This is what makes an untouched open→save a **structural identity** (`resolve` at the boundary; never strip). The lone exception is ephemeral `proposals` (modeled, never re-emitted). `recalculateParentsFromCriteria` is the **only** silent correction and cascades bottom-up at any depth (leaf: Σ criteria; parent: Σ children; `q.total_points` never auto-touched).
- **Validator** (`utils/rubric-validation.ts`): INV-R1b/INV-R2 recurse via `walkSubQuestion`, mirroring `contract_compiler._walk_sub_question` **exactly** (full-path `target_id`). `INV-R-XOR` mirrors StructureExclusivity. Change one side, change the other.
- **Editor** (`RubricEditor.tsx::SubQuestionNode`): recursive render, path-addressed ops (`*AtPath` in `rubric-editor-ops.ts`), full-path `data-scope-id` so a `q1.א.2` annotation anchors.

**The acceptance bar is a test:** `utils/rubric-transform.test.ts` round-trips all five golden benchmarks (read in place from `backend/tests/rubric_eval_suite/benchmarks/`) under a Decimal-aware comparator. If you touch the codec, that suite is the golden self-pass — keep it green. **Deferred (B-11b):** the my-rubrics / rubric-generator save payload still drops `selection_groups` / re-sums the total / drops `programming_language` (document-envelope leak, witnessed by a `todo` test).

### The document mirror is the review surface (PR-5 Sprint 2)

`RubricDocument.tsx` replaces `RubricEditor` as the rubric-review UI for the docx flow — the review must read as *her DOCX annotated by Vivi*, not form furniture. It is a **NEW SIBLING VIEW**: same prop seam as `RubricEditor` **plus** `selectionGroups`, consuming `questions`/`annotations`/`errorBannerRef` and emitting through `onQuestionsChange`/`onTotalPointsChange`/`onMetadataChange`. It **never touches `rubric-transform.ts`** or its golden suite.

- **Kill-switch:** `src/lib/flags.ts::USE_DOCUMENT_MIRROR` (a plain boolean — there is **no** PDF-rubric flow, so no `sourceType` guard). `false` reverts to `RubricEditor`, which stays in-tree as the rollback target. Flip nothing else. **Flip-and-deploy (the 22:00 rollback):** edit the one line `export const USE_DOCUMENT_MIRROR = false;` in `frontend/src/lib/flags.ts`, then ship the frontend the normal way (§12.5 — mirror `frontend/`→`grader-frontend/`, commit, `git subtree push --prefix grader-frontend origin frontend-deployment` to trigger the Vercel prod build). No backend change, no env var, no data migration — the old editor is already deployed code behind the flag, so the rollback is a one-line diff + one deploy.
- **CORRECTNESS INVARIANT — "ops imported, never forked":** every mirror edit routes through the pure `*AtPath` ops (`rubric-editor-ops.ts`) + `recalculateParentsFromCriteria`. This is not style — the page-level **undo stack** (`utils/rubric-history.ts`, E-1) pushes snapshots of the tuple `{questions, declaredTotal, name}` **by reference** and relies on structural sharing (50 snapshots is trivial). One in-place mutation would retroactively corrupt earlier snapshots. (RubricEditor's own `updateCriterion` still has that landmine — see BACKLOG B-15; do NOT wire undo/memo onto the old editor without fixing it.)
- **Living sums (E-3):** the teacher edits LEAVES (criterion points/descriptions, sub-criteria); sub-question points and direct-criteria question totals are **read-only cascaded sums**. A parent question's declared total stays editable (INV-R1 surfaces mismatch).
- **The one interpretation site:** `utils/detect-table-runs.ts` re-recognizes flattened DOCX tables at RENDER only (pure, precision-biased — when unsure, don't tableize). `findingSectionsByQuestion` (E-2 rail dots) and `countFindings` share one severity+dedup module (`utils/finding-severity.ts`).
- **Deferred (BACKLOG B-16):** prose/title/solution editing, nested-node CRUD, and shared-lifting the trace/context tables (the mirror got fresh document-styled `document/DataTables.tsx`; only `AnnotationBanner` was truly lifted). All are extension points, none block the DoD.

---

## 12. Local development

**Backend** (from `vivi-codebase/backend/`):
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
pytest -q
```

**Frontend** (from `vivi-codebase/frontend/`):
```bash
npm install && npm run dev
```

**Sanity gate before declaring done:** `python -c "import app.main"` succeeds, `pytest --collect-only` succeeds (no import errors), frontend type-checks. A green collect-only catches the mapper/import breakage that is the most common "it merged but the server won't boot" failure.

### Environment (backend `.env`, via `app/config.py`)
**Required:** `OPENAI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `DATABASE_URL` (`postgresql+asyncpg://...`). ⚠️ The DB lives in Supabase **eu-central-1** (project `ngkqawsyqqbhqthgdkpk`, migrated from ap-south-1 2026-08-23 — the Mumbai hop cost ~300 ms *per query* through the pooler and made a 10-round-trip append take ~6 s; Frankfurt took it to ~0.5 s). Cloud Run reads it from Secret Manager `database-url:latest`. The Mumbai project was RETIRED 2026-08-23 (dump archived + restore-verified at `gs://grader-vision-pdfs/db-archive/vivi_premigration_20260822.dump`; a pre-cleanup Frankfurt dump sits beside it) — `database-url:1` now points at a deleted project; forensic recovery = restore the archived dump.
**Common:** `OPENAI_MODEL`=`gpt-4o`, `OPENAI_VISION_MODEL`=`gpt-4o`, `EXTRACTION_LLM_PROVIDER`/`EXTRACTION_LLM_MODEL`, `GCS_BUCKET_NAME`=**`grader-vision-pdfs-0438328890`** (⚠️ the live value, verified on the service 2026-09-03; `config.py`'s default is the bare `grader-vision-pdfs`, which **does not exist** — a `gcloud storage` command against it 404s. The service env var is what production runs on), `ALLOWED_ORIGINS`, `LOG_LEVEL`, `APP_ENV`, `FRONTEND_BASE_URL`.
**Transcription:** `PARALLEL_TRANSCRIPTION_ENABLED`, `MAX_PARALLEL_PAGES`, `VLM_TIMEOUT_SECONDS`, `VLM_MAX_RETRIES`.
**Extraction jobs (PR-1):** `EXTRACTION_EXECUTION_MODE` (`cloud_tasks` prod / `inline` local-dev-only), `EXTRACTION_HEARTBEAT_TTL_MINUTES` (15), `CLOUD_TASKS_LOCATION`/`CLOUD_TASKS_QUEUE`/`CLOUD_TASKS_INVOKER_SA`, `SERVICE_BASE_URL` (this service's Cloud Run URL — task target), `INTERNAL_TASK_TOKEN` (dev shared-secret for `/internal`), `EXTRACTION_MAX_UPLOAD_MB` (15). Prod model pin (D-2, **FLIPPED 2026-08-24, owner-ordered**): `EXTRACTION_LLM_PROVIDER=openai`, `EXTRACTION_LLM_MODEL=gpt-5.6-terra`, `EXTRACTION_LLM_REASONING_EFFORT=high`, `EXTRACTION_LLM_MAX_TOKENS=32000` — was gpt-5.5/medium. Evidence (RUNLOG `VERDICT 2026-08-24`): same prompt, same pipeline, same instrument, k=3 all-5 — **identical 12/15 with identical pass sets** and every terra draw clean (0 spurious, 0 missed, example_solution 1.000, 0 retries), at **headline latency −17.4%, suite −18.7%, $/doc −63.9%**. ⚠ **The model and the prompt are a PACKAGE**: terra-high is 12/15 on prompt `3.9.0-blockend` but **10/15 on `3.7.0`** (it emits point-total label rows as criteria there → false `rubric_mismatch` alarms on correct nodes). Never set this pin on an image built before `EXTRACTION_PROMPT_VERSION=3.9.0-blockend`. gpt-5.5 scores 12/15 on BOTH prompts, which is what makes the model half a safe one-line rollback. ⚠ These four live as **Cloud Run service env vars**, which OVERRIDE `config.py`'s defaults (the bridge uses `setdefault`) — changing the code default alone does NOT change production. gpt-4o (the pipeline's own code default) was never evaluated against any current prompt.
**Onboarding outreach (028):** `ALERT_EMAIL` (where the 14-day re-ask digest goes — it had sat in `backend/.env` since before this PR with NO code reading it, so it typed as an undeclared `extra` string; now DECLARED in `config.py`, and unset ⇒ the digest refuses to run rather than sending nowhere), `ONBOARDING_SHEET_ID` (unset ⇒ the sheet projection is a logged no-op, which is a supported state: the DB is the record), `CLOUD_TASKS_ONBOARDING_SHEET_QUEUE` (`onboarding-sheet` — its own queue, because it is the only kind whose work calls a THIRD-PARTY API with its own quota, and a Sheets rate limit must not be able to throttle a grade). Frontend-side, `NEXT_PUBLIC_BOOKING_URL` and `NEXT_PUBLIC_WHATSAPP_NUMBER` are inlined at BUILD time and therefore belong in `frontend/.env.local` and in Vercel's project env — they were found in `backend/.env`, where Next.js never reads them, and the exam step renders neither affordance without them (a dead link is worse than no link).

**The 14-day re-ask digest runs as a Cloud Run JOB, not a route (028 §7).** `onboarding-reask` (europe-west1) runs `python -m app.scripts.onboarding_reask`; Cloud Scheduler `onboarding-reask-daily` fires it at **08:00 Asia/Jerusalem** (`0 8 * * *`, retry 3). Both are created by the committed, idempotent `backend/deploy/onboarding_reask_job.sh` — re-run it after every backend deploy, because it re-points the job at the service's CURRENT image digest. Two things it exists to get right:
> * **A Cloud Run JOB inherits NOTHING from the Service.** They are separate resources: a shared image shares the CODE, not the configuration. A job created with `--image` alone has an empty environment — no `DATABASE_URL`, and no `OPENAI_API_KEY`, which `config.py` declares WITHOUT a default, so the process dies at import before any of the PR's code runs. The script restates every variable and re-uses the same Secret Manager secrets (no new credentials). `ALERT_EMAIL` lives on the JOB, not the service — the digest is its only consumer.
> * ⚠️ **`backend/.gcloudignore` patterns are unanchored by default, and one silently un-deployed a package.** Its `scripts/` line was meant for the repo-root dev tooling (`backend/scripts/dump_openapi.py`) but matches a directory of that name at ANY depth, so when `app/scripts/` was added it was dropped from the source upload. **The deploy SUCCEEDED and the service ran perfectly** — nothing imports `app.scripts` at request time — and the only symptom was the job dying on `ModuleNotFoundError: No module named 'app.scripts'` against a freshly built image. Both entries are now anchored (`/tests/`, `/scripts/`). Anchor any directory pattern you add there, and treat gcloud's "Some files were not included in the source upload" line as something to read rather than scroll past.

**Email (production, wired 2026-09-06):** `EMAIL_PROVIDER=resend`, `EMAIL_FROM=Vivi <noreply@vivi-assistant.com>`, `RESEND_API_KEY` from Secret Manager `resend-api-key` — set as Cloud Run service env (they override `config.py`'s `console` default); without them signup's verification mail silently goes to the console log and no teacher can verify.
**Plan builds (PLAN COMPILER v2):** `CLOUD_TASKS_PLAN_BUILD_QUEUE` (`plan-build-jobs`, own queue — OD-W2), `PLAN_BUILD_ENVELOPE_USD` (1.0 per rubric; overrun → placeholder wording), `PLAN_ROUTE_MIN_POINTS` (3 — OD-W5), `PLAN_WAIT_S` (240 — how long a grade waits on a live builder), `PLAN_BUILD_HEARTBEAT_TTL_MINUTES` (5), `PLAN_BUILD_DISPATCH_TTL_MINUTES` (90); `ANTHROPIC_API_KEY` is required for the builder AND the v5 grader; `GRADER_ARCHITECTURE` defaults to `v5` (`v3` = rollback); ship `GRADER_MAX_CONCURRENT_SCOPES=8` on Anthropic until the rate is measured (OD-W12).
**Cloud Tasks migration (batch transcription + grading):** `JOBS_EXECUTION_MODE` (`cloud_tasks`|`inline`; unset ⇒ falls back to `EXTRACTION_EXECUTION_MODE`, so existing envs need nothing), `CLOUD_TASKS_TRANSCRIPTION_QUEUE` (`transcription-jobs`), `CLOUD_TASKS_GRADING_QUEUE` (`grading-jobs`), `TRANSCRIPTION_JOB_HEARTBEAT_TTL_MINUTES` (5), `TRANSCRIPTION_JOB_DISPATCH_TTL_MINUTES` (90), **`TRANSCRIPTION_JOB_ABSOLUTE_TTL_MINUTES` (20 — the LIV-1 arm the heartbeat cannot refresh)**, **`TRANSCRIPTION_TASK_BUDGET_S` (480 — the per-document wall budget; keep it under the Cloud Run `--timeout`, always)**, `GRADING_JOB_RUNNING_TTL_MINUTES` (30 — must exceed the 900s dispatch deadline), `GRADING_JOB_DISPATCH_TTL_MINUTES` (90). Queues (DEPLOYED 2026-08-22, sized for 100 users/evening): `transcription-jobs` maxConcurrentDispatches=25, `grading-jobs`=20, both maxAttempts=3/min-backoff=10s; `rubric-extraction`=20 (was 1000 until 2026-08-22 — an unthrottled 3-LLM-call handler was the exact runaway the budget tripwire can only *notify* about), maxAttempts=1; Cloud Run `--concurrency=4 --memory=2Gi --max-instances=60` (8→5 2026-08-23 for OOM safety; 5→4 + maxScale 40→60 2026-08-23 after the two-arm memory measurement: ≈260 MB/doc + ≈480 MB fixed, so C=5 sat AT the 85% line with zero margin for a 7-page-heavy packing draw — C=4 = 74% measured, and throughput is queue-bound so the change is free; the maxScale headroom covers simultaneous-uploader bursts, which scale per teacher while transcription is queue-capped). Capacity math + the tier ladder for raising these: **`SCALING_ROADMAP.md`** (keep it in sync with the live dials). `BATCH_MAX_CONCURRENT_TESTS` was REMOVED with the in-process semaphore.
**LangSmith:** `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`.

---

## 12.5 Repository & deployment layout — READ THIS BEFORE YOU `git push`

> **⚠️ ADDENDUM (2026-08, batch-review PR): the "rename trap" below is RESOLVED on `perf/rubric-extraction-latency`** — commit `d47018a` snapshotted the full working tree, so `frontend/`, `backend/`, `CLAUDE.md`, and `BACKLOG.md` are all TRACKED there; ordinary `git add <paths>` + commit is the workflow on that branch. `grader-frontend/` is the **stale pre-PR deploy mirror** (received zero writes from the batch-review PR; flagged for deletion — BACKLOG **B-21** — pending confirmation of the live Vercel wiring below). The pre-snapshot description that follows still governs `main`'s layout and the deploy flows until the branch lands.

The git layout does **not** match this working tree, and a naive `git add -A` will
**delete the backend from the repo**. Internalize this before pushing anything.

**The repo.** `.git` lives at `vivi-codebase/.git`; remote is
`github.com/sparkwellnessapp/pupal.git`. Two branches matter:

| Branch | Layout | Who builds it | Push frontend how |
|---|---|---|---|
| `main` | two tracked dirs at repo root: **`grader-frontend/`** (the Next.js app) + **`grader-vision-update/`** (the FastAPI backend) | reference/source-of-record | copy changed files into `grader-frontend/…` and commit **only those paths** |
| `frontend-deployment` | a **subtree split**: the Next.js app at the **repo ROOT**, no backend | **Vercel builds THIS branch** (root dir = `/`) | put the same files at the **root** of that branch (use a temporary `git worktree`) — fast-forward only |

**The rename trap (why `git add -A` is dangerous).** This local working tree renamed the two
tracked dirs to **`frontend/`** and **`backend/`** and that rename was **never committed**. So
`git status` on `main` shows *all 139 tracked files as deleted* and the real code as *untracked*.
Never `git add -A` / `git commit -a`. Instead:
- **To ship a frontend change to `main`:** `cp` each changed file from `frontend/…` to the matching
  `grader-frontend/…` path, `git add grader-frontend/<those files>`, verify
  `git diff --cached --name-only` shows **only** `grader-frontend/…` (backend untouched: `grader-vision-update`
  should still have its ~99 files in HEAD), then commit + `git push origin main`.
- **To ship the same change to `frontend-deployment`:** `git worktree add <tmp> frontend-deployment`,
  copy the files to the **root** of that worktree (not under `grader-frontend/`), commit, confirm it is a
  fast-forward (`git merge-base --is-ancestor origin/frontend-deployment HEAD`), `git push origin
  frontend-deployment`, then `git worktree remove <tmp>`.
- Skip `node_modules`, `.next`, `.env*`, `.vercel`, `*.tsbuildinfo` (all gitignored anyway).
- Gate before pushing: `npx tsc --noEmit` + `npx vitest run` + `npx next build` all clean.

**The backend does NOT deploy from git.** `grader-vision-update/` on `main` is a stale reference copy;
production backend ships via `gcloud run deploy --source=.` from the local `backend/` tree to Cloud Run
(service `gradervision-backend`, project `gen-lang-client-0438328890`, region `europe-west1`). See the
PR-1 deploy checklist for the full env/secret flags.

**Vercel env:** the deployed frontend needs `NEXT_PUBLIC_API_URL` set for production, or `api.ts` falls
back to `http://localhost:8080` and the live site silently calls localhost. Project root dir on Vercel is
the repo root of `frontend-deployment`.

**This file (`CLAUDE.md`) and `BACKLOG.md` are untracked** working-tree context — they are not in either
tracked subtree and are not pushed by the frontend flow. Edit them in place; they load into every agent
session from the working tree.

---

## 13. Debugging playbook

- **One document in a batch takes 5–10× the others and the logs look clean** → almost certainly an OPTIONAL pass burning its timeout, not P1 or P2. Filter Cloud Run on the FILENAME and read three things: `strike_check page N … failed; casting no ranges` (the pass gave up — the interesting number is how long AFTER the claim it was written), `provider returned in Xms (queue_wait=Yms, call-attempts=N)` (a big `total_ms` is a hung provider; a big `queue_wait_ms` is us starving our own document behind the per-model cap), and the scheduler's `[doc] provider: call failed (kind) after Ns; retrying once` — that line carries the doc id only since 2026-09-10; before that the 481 s that explained the outage was in the logs but unjoinable to the document. `transcription_created … wall_s=` is the honest end-to-end figure; `transcription_duration_ms` is NOT — it is reset per pipeline entry, so a discarded attempt vanishes from it by design.

- **Compile fails INV-1..4** → inspect the failing `Annotation.target_id` for the exact scope; check the `ContractCompiler` validator that raised; verify all point fields are `Decimal` (not late-float-converted). If it came from extraction not teacher edit, check `docx_v3/pipeline.py` totals.
- **Persistent extraction WARNING in the editor** → `annotation_type="rubric_mismatch"` means the source DOCX itself has a sum mismatch the LLM faithfully copied; the teacher fixes it before save.
- **Save/Approve button stuck blocked** → check `hasBlockingAnnotations`; confirm the backend returned ERROR annotations (network tab); confirm every violation has been resolved.
- **`graded_tests` CHECK violation on write** → you set the wrong combination of `status`/`draft_json`/`contract_json`/`approved_at`. The CHECK is correct; fix the write to set all required fields in one commit (esp. approval: all three together).
- **Two-leaf / unique-index violation in a revision flow** → you used insert-R2-first ordering; use `extend_chain()` (link-R1 → flush → insert-R2 → commit) and confirm migration 010's deferrable FK is applied.
- **Grade list crash / null fields** → an endpoint is reading the legacy `rubric_json` column instead of `contract_json`/dedicated columns. Read display fields from the right source (the `total_points` column, the contract), never the dead `rubric_json` blob.
- **Server import error after pull** → `python -c "import app.main"`; a mapper misconfiguration (mismatched `back_populates`, bad self-referential `remote_side`) fails here first.
- **`TypeError: can't compare offset-naive and offset-aware datetimes` — a 500 *after* the work succeeded** → **every timestamp column in this DB is `TIMESTAMPTZ`, but the ORM models declare bare `DateTime` (naive).** The driver therefore returns **aware** datetimes for anything read from the DB, while anything just built in Python (`datetime.utcnow()`) is **naive** — so `utcnow() < row.some_timestamp` raises. Signature: the row was fetched from the DB (a freshly constructed, not-yet-reloaded object works fine, which is why signup passed while login failed). This 500'd `/auth/login`, `/auth/me` and `/auth/refresh` for **271 of 273 live users** via `User.is_subscription_active` — invisible to the two `active` accounts, whose branch short-circuits before touching a datetime. Fixed 2026-08-17 with `models/user.py::_as_utc`. **Rule: never compare a stored timestamp against a bare `utcnow()`** — normalize both sides to aware UTC (`datetime.now(timezone.utc)`). The same latent mismatch exists in other model properties (e.g. `RubricShareToken.is_expired`); fix them as you touch them.
- **New table exists in DB but missing its CHECKs/partial indexes/ALTERs** → the `create_all` footgun: startup auto-created a BARE table from a new ORM model before its migration was applied (bit PR-1's `rubric_extraction_jobs`). Signature: `ix_*`-named indexes instead of the migration's `idx_*` names. **Structurally closed by migration 013** — `create_all` now runs only on a ledger-less dev DB. If you see this on a DB that *has* a `schema_migrations` ledger, something re-enabled `create_all`; check `_should_bootstrap()`. Remediation is unchanged: drop the bare table (verify 0 rows first) + apply the real DDL.
- **`SCHEMA MISMATCH: N migration(s) NOT APPLIED` in the boot logs** → exactly what it says; the running code assumes DDL this database doesn't have. Apply the listed migrations from `backend/migrations/`. A migration that ran *halfway* reports as a missing version (its commit-token INSERT is the last statement, so it never landed). To finish one: the already-landed statements will fail on a naive re-run (011/012 use bare `ADD COLUMN` / `CREATE TABLE`), so apply the remainder statement-by-statement, or re-run with `IF NOT EXISTS` added. **Write new migrations idempotent** (`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`) so re-running the whole file is always the answer.

---

## 14. Do / Do NOT

**Do**
- Treat `ontology_types.py` as the single source of truth; import types from it.
- Compile before grading; only ever grade against a Contract.
- Emit teacher-facing diagnostics as `Annotation`s (severity-differentiated); record per-outcome structured diagnostics as `flags` (§6).
- Use `Decimal` for all points; convert at the edges only.
- Enforce auth + ownership on every domain endpoint (§9).
- Plan before code; surface ambiguity as open decisions.
- Keep extraction, compilation, grading, and approval as separate concerns.
- Design backend interfaces and shared frontend components subject-agnostic.

**Do NOT**
- Add rubric/contract types outside `ontology_types.py`, or duplicate schemas.
- "Fix" invariant failures by loosening tolerances or skipping validation.
- Add a parallel teacher-facing diagnostic surface (`warnings`/`blockers` dict) competing with `annotations` — but do NOT delete per-outcome `flags`, which are a different, intentional thing (§6).
- Reintroduce `ReductionRule`, `ScoringLevel`, `RuleKind`, or any rule-based grading scaffolding.
- Construct a `SubCriterion` in code outside the V3 pipeline (they're extracted, never generated).
- Persist `GradableTest`, or read a Draft into the grading agent.
- Read the legacy `rubric_json` / `graded_json` columns — use the Draft/Contract JSONB + dedicated columns.
- Use the naive insert-R2-first order in revision flows — use `extend_chain()`.
- Re-fire INV-1/2/3 on *awarded* points at approval (§5 approval gate).
- Call OpenAI in tests; retry content/validation failures; or persist anything from the GraderAgent (S7 produces in-memory; S8 persists).
- Silently rewrite named invariants, contracts, or UX state machines — flag deviations as open decisions.
- Hardcode CS-specific behavior in shared interfaces or shared components.

---

## 15. Where the roadmap is going (so you don't rebuild it wrong)

- **Scaling the batch pipeline** — the capacity model, deployed dials, and per-tier upgrade ladder (queue concurrency → fairness sharding → global provider rate limiter → SSE read path) live in **`SCALING_ROADMAP.md`**. Triggers, not dates: raise dials at p95 evening t_first > 3 min or queue depth ~1,000; the 1000s-tier items are design-before-need.
- **S12** — polished batch grade-review dashboard. **Blocked on a UX interview**; do not design it speculatively.
- **Bulk grade-approval** — deferred until the **eval suite** validates a high unedited-approval rate. Until then, grades are approved one-by-one. Bulk-approving an unvalidated grader is a footgun, not a feature.
- **Eval suite (the keystone AI-quality work)** — a golden set of `(rubric, transcription) → teacher grade` triples, agreement metrics (points MAE, within-precision rate, per-criterion match, **confidence calibration**), and a regression gate keyed by `(model_version, prompt_version)`. Blocked on real teacher-graded data. This is the loop that turns "I built a grader" into "I built a grader I can improve." The per-outcome `flags`, the `was_overridden` provenance in `GradedTestContract`, and the cost/version stamps all exist to feed it.
- **Confidence-triggered verification** — a calibrated low-confidence second-pass on individual terminals; gated on the eval suite's calibration data (don't set the threshold by guessing).

---

## 16. Maintenance

This document is **living context loaded into every agent session — keep it lean and true.** When an agent makes the same mistake twice, write down the rule it violated in the relevant section. The codebase teaches future agents.

**Update when:** a named invariant/protocol is added/removed/changed; an architectural pattern is introduced or retired; a directory becomes dead/deprecated/production; a failure mode recurs; a sprint ships something that changes the maps above.
**Do not update for:** routine feature additions that don't change architecture; renames/refactors that don't change concepts; personal style.
**When this file and the code disagree, the code wins — and fixing the doc is part of the task that caused the drift.**
---

## 17. The /goal eval-loop contract (read this if you are running the autonomous loop)

> **Scope:** this section governs ONLY the autonomous loop that drives the transcription
> eval suite toward its benchmark. It is not about the grading pipeline above. If you were
> launched by a `/goal` invocation against the eval suite, this is your operating contract —
> it overrides any shortcut you might infer from the objective text. The detailed reasoning,
> metrics, and failure history live in `tests/transcription_eval_suit/transcription_eval_suit_docs.md`,
> `P1_EVAL_PLAYBOOK.md`, and `P2_EVAL_PLAYBOOK.md`. **Read all three before your first action.**

**Glossary (state who is who, so nobody is confused):** *You* = the agent making changes.
*Me / Noam* = the human; the only one who may make the judgment calls on the STOP list.
*The loop* = do-the-work → verify → record → repeat, until `check_goal.sh` passes or a STOP
condition fires.

**17.1 DONE is a script, not your judgment.** The benchmark is met only when
`bash tests/transcription_eval_suit/check_goal.sh` exits 0. That script runs a full k≥5
end-to-end eval over all fixtures and passes only when every fixture clears the conjunctive
gate on every repeat, with validity clean and the instrument self-consistent. You may not
edit, weaken, or bypass it or anything it calls. "I believe it's done" is a signal, never a
verification.

**17.2 Cost-tier your runs — do not burn `check_goal.sh` every iteration.** It is the
expensive, authoritative confirmation (the slow P1 image calls, ×5). Iterate with the CHEAP
diagnostic: `p2_only` with `--repeats 5` on the affected docs (text-only, near-free, fast).
Use `p2_only` to form and test hypotheses; spend `check_goal.sh` only when your cheap signal
says the end-to-end gate will likely pass, and as the final word on stopping.

**17.3 One variable per iteration.** Change exactly ONE thing — one prompt OR one config
field, never two. Two changes at once make the result unattributable (we have already burned
runs on prompt+scorer moving together). State the hypothesis and its kill criterion BEFORE
you run.

**17.4 Attribute before fixing; read the diagnostic, not just the gate.** A bad end-to-end
number can be perception (P1), segmentation (P2), or correction. Run `p2_only` AND
end-to-end and apply the attribution identity from the playbook: `p2_only` high + e2e low →
P1 perception; `p2_only` low → P2. Never name a fix surface from an end-to-end number alone.

**17.5 Repeats, because the cheap P2 model is non-deterministic at temp 0.** It has produced
a swap on one run, a merge the next, a refusal the next, on identical input. Test every change
with k≥5 repeats on the affected docs, pre and post. A change is "confirmed" only if it holds
across all repeats. A single clean run is a lucky draw — treat it as noise.

**17.6 RUNLOG.md is your memory.** Context will be compacted; do not rely on it surviving.
Read `tests/transcription_eval_suit/RUNLOG.md` at the start of every iteration. Append after
every run: the hypothesis, the one variable changed, the pre/post k=5 result, the stage
attribution, the decision, and whether the kill criterion fired.

**17.7 STOP-AND-SURFACE list — never do these; instead halt and ask me (`AskUserQuestion`).**
These are judgment calls, not loop work. Doing any of them "passes" the gate by corrupting the
target, which is worse than not passing.
- Edit anything under `raw_benchmarks/` or `draft_benchmarks/` (ground truth is mine).
- Edit `scoring.py`, `critical_tokens.py`, `normalize.py`, the gate thresholds (`0.98`, the
  `=1.0` recalls, the abbreviation rule), or `check_goal.sh` — or otherwise change what the
  gate measures. **Answering a grading question with an instrument change is forbidden** (it
  is the same failure as "fix invariant failures by loosening tolerances," §0.5). A suspected
  GT typo or a too-strict gate gets SURFACED with evidence, never silently "fixed."
- Escalate the P1 or P2 model tier. That is an evidence-based decision I make.
- Bundle more than one variable into a run.
- Conclude the spec-tier corrector is safe — it is UNDERPOWERED until n≥10 fixtures with
  deliberately-included student-spec-errors.

**17.8 Kill criterion for the P2 prompt surface (watch the WHOLE partition).** Every P2 prompt
fix so far has solved its target doc and surfaced a NEW boundary-failure (dump / swap / merge /
refusal) on a different doc — the same root cause (the cheap model cannot reliably locate unit
boundaries on messy input), just redistributed. So: **if a prompt change introduces any new
boundary-failure on a doc that was previously working, the prompt surface is exhausted.** Stop,
record it in RUNLOG.md, and surface "escalate the P2 model" to me. Do not write another prompt.

**17.9 No-progress breaker.** If 3 consecutive iterations do not improve the worst-doc stable
pass-rate, stop and surface. Redistributing failure between docs is not progress; it is the
signal that the lever you are pulling is spent.

**17.10 What you MAY freely change:** P1/P2 prompts, `configs/`, the corrector logic, and
runner/report plumbing — anything that changes MODEL BEHAVIOR rather than what the ruler
measures. Plan-before-code (§0.1) and surface-don't-decide (§0.2) still apply.

**Summary instructions for compaction:** when summarizing this loop's conversation, always
preserve: the current hypothesis and its kill criterion; the one variable under test; what has
already been tried and its result (or the RUNLOG pointer); which STOP conditions have fired;
and the path to `check_goal.sh` and the playbooks.