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

**⚠️ BackgroundTasks deployment caveat:** prod Cloud Run runs CPU-throttled post-response with min-instances 0 — a FastAPI BackgroundTask has NO guaranteed CPU after the response returns and dies with scale-in. The grading path (`run_grading` via BackgroundTasks, S8/S11) shares this risk — known, deliberately unfixed in PR-1; migrating grading to the Cloud Tasks pattern is a follow-up. Do not add new long-running work on BackgroundTasks.

**Revision flows (single-test lifecycle complete):** all extend the chain immutably (LCY-2: approved/failed rows are read-only except `regraded_to_id`), via `extend_chain()`:
- **regrade** — approved + leaf + **stale** only; new row pinned to the *new* rubric version; runs the agent.
- **manual_edit** — approved + leaf (any staleness); new `draft` row carrying the prior `draft_json` verbatim; **no agent**.
- **retry** — failed + leaf; new pending row; runs the agent. (`failed` is terminal *for the row*; the chain continues.)

The chain insert uses a **deferrable `regraded_to_id` FK** (migration 010): link R1 → flush → insert R2 → commit. Do not use the naive insert-R2-first order — it trips the one-leaf partial index for same-chain rows.

**Grading agent shape (`app/agents/grader/`):** one LLM call **per scope** (a scope = a direct-criteria question OR one sub-question), bounded-parallel (`asyncio.Semaphore`, `MAX_CONCURRENT_SCOPES`), `return_exceptions=True`. Per-scope failure → flagged zero-outcome (`graded_by="failed"`), never propagates. Deterministic post-validation (closed-world re-check, bounds+precision clamp, sliding-window quote validation via `difflib`). Captures token usage (`include_raw=True`) for per-scope cost. Stamps `model_version` + `prompt_version` into the draft (a grade is a function of rubric+transcription+model+prompt versions — all four are recorded).

> ⚠️ **The grader's "one surgical retry" is a MISSTATEMENT that this doc used to make — the real worst case is 6 API calls per scope, unbounded.** `GraderAgent.__init__` builds `ChatOpenAI(...)` with **no `timeout` and no `max_retries`**, so (a) the OpenAI SDK's hidden `max_retries=2` applies → 3 transport attempts *inside* each `ainvoke`, and (b) LangChain passes `timeout=None` **explicitly**, overriding the SDK default → **httpx `Timeout(None)` = no timeout at all**. Its own GA-3 retry then wraps that: **2 × 3 = 6 unbounded calls per scope.** Two consequences: `openai.APITimeoutError` in its `TRANSIENT_EXCEPTIONS` tuple is a **dead branch** (nothing can ever time out), and `insufficient_quota` — a *permanent* billing 429 — is retried as if transient. **PR-2 fixed exactly this defect family in `docx_v3/pipeline.py` only** (see below); the grader keeps the defect until **PR-7** (its Cloud Tasks migration), where its per-task budget math belongs. `_transport_retry_async/_sync` in `pipeline.py` are written to be reusable there — do not add a *second* retry layer around the grader.

**Extraction transport policy (PR-2, `docx_v3/pipeline.py`):** every LLM attempt is **bounded** (`timeout`, env `EXTRACTION_LLM_TIMEOUT_S`, default **360s**), the SDK's hidden retry layer is **disabled** (`max_retries=0`), and **exactly one** retry layer is owned in-pipeline (`_transport_retry_async` / `_transport_retry_sync`, default 1 retry). Its predicate **fails fast** on permanent conditions — `insufficient_quota` (billing, not rate pressure), 401/403/400 — and re-raises content/parse failures untouched. A wall **deadline** is enforced at three points (validation-loop entry `T+60`; each transport attempt `T+10`; Tier-B entry `T+10`, else **skip** with the distinct warning `"Tier B skipped: time budget…"`), because a logical call is `attempts × T`, not `T`. The runner passes `840 − measured pre-work` (monotonic). **`deadline_seconds=None` ⇒ unbounded ⇒ the eval path**, which is why the gate is untouched by construction. Rationale: an observed attempt ran **1736s** with no timeout — 1.9× the whole task budget. **Never stack another retry layer on top of this one.**

**Batch grading (S11):** a batch is M tests through the same per-test pipeline with `batch_id` set; fan-out is bounded (`BATCH_MAX_CONCURRENT_TESTS`). Transcription review is **triaged** — clean transcriptions bulk-acceptable, flagged ones (low logprob span / VLM low confidence / grounding retry / `[?]` markers / missing-or-unmatched student) handled individually. Student auto-match against the batch's class roster is conservative (normalized-exact, never fuzzy); class is **optional** (first-time teachers have no roster → manual pick + inline create).

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
| `batch_grading.py` | `/api/v0/...` | batch create/upload/detail/list (S11) |
| `rubric_generator.py` | `/api/v0/rubric-generator` | AI rubric generator |
| `auth.py` / `users.py` | `/api/v0/auth`, `/api/v0/users` | auth, profile |

### Services & agents
- `app/services/docx_v3/pipeline.py` — **production** rubric extraction (3-step prompt chain) + the PR-2 transport policy (bounded attempts, one owned retry layer, wall deadline). `parser_render.py` — DOCX→markdown.
  > ⚠️ The `gemini` provider branch in `_get_llm` is **undeployable**: `langchain_google_genai` is **not in `requirements.txt`**, so that branch raises `ImportError` at construction. It is also the one branch PR-2 left **unbounded** (no timeout / no `max_retries=0`), deliberately — bounding a branch that cannot run would be theatre. Adding the dependency is a deliberate decision for a provider sweep, not a side effect of another PR.
- `app/services/contract_compiler.py` — rubric Draft→Contract (INV-1..4, INV-6-as-INFO). Populates `selection_groups` and sets `total_points` to the **achievable** total.
- `app/services/gradable_compiler.py` — RubricContract + TranscriptionContract → `GradableTest`. **Scopes are LEAVES** (PR-3): a sub-question with children contributes no scope of its own; each leaf carries its own criteria and points, with a full-path id (`א.2`). A leaf whose exact id has no transcription answer **inherits its nearest ancestor's answer** (the transcription pipeline segments to depth 1; that fallback is load-bearing for every nested rubric, and each firing is recorded in `GradableTest.parent_answer_fallback_scopes`).
- **`app/services/selection_scoring.py` — the SINGLE source of the grade.** ⚠️ The final score was computed in **two** places and *both* re-derived the denominator as `Σ scope.points_possible`. On a "choose k of N" exam that divides by every question the exam *offered* instead of what the student could *earn*: a student answering the 50-point question perfectly and skipping the other two — **as the exam instructs** — scored 50/100 = **50%**. Both `grading_runner` and `compile_graded_test` now call `score_with_selection(...)` and **neither re-sums anything**; the denominator is `contract.total_points`. **Exclusion is DERIVED state, never an input** — a teacher override can flip which member wins the best-k slot, so the grading-time marks (`graded_by="excluded_by_selection"`) are **provisional display**, and the approval gate **recomputes** from post-override scores; that recomputation is authoritative and is what freezes (`ContractScopeOutcome.counted_in_total`). Unchosen members are **excluded, not zeroed** — on a choose-4-of-6 the two unchosen questions were never owed. *Fixing only one site would have been worse than fixing neither: the teacher would review one percentage and have a different one frozen into the immutable contract.*
- `app/agents/grader/` — the GraderAgent: `grader.py`, `validator.py` (pure), `prompt.py` (`GRADING_PROMPT_VERSION`), `schemas.py`.
- `app/services/graded_test_contract_compiler.py` — approval gate + `GradedTestContract` compile.
- `app/services/grading_runner.py` — `run_grading(graded_test_id)`: request-context-free background task; advances the row; owns its own session.
- `app/services/rubric_extraction_runner.py` — `run_extraction_job(job_id)`: drives a `rubric_extraction_jobs` row `queued→extracting→completed|failed`; owns the queued→extracting CAS (idempotency for both execution modes); short heartbeat sessions, never a transaction across the extraction. `app/services/cloud_tasks_service.py` — the execution substrate in one place: enqueue (cloud_tasks|inline) + OIDC/shared-secret verification of `/internal` calls.
- `app/services/graded_test_revision.py` — `extend_chain()` (the deferred-FK insert).
- `app/services/handwriting_transcription_service.py` — VLM transcription (legacy engine; swappable `VLMProvider`).
- `app/services/transcription/two_phase/` — the two-phase transcription pipeline core (P1 perception → P2 segmentation + prompts/parsing/corrector/instrument; relocated 2026-07-08 from the eval suite, which now shims to it — production runs the exact code the suite measures). `app/services/transcription/flagging.py` + `page_provenance.py` — pure trust-layer modules (cross-reader disagreement flags, deterministic page attribution), shared with the suite's `flag_metrics.py`. `app/services/transcription/two_phase_engine.py` — production entry (models, config mirror of `v1_trust`, TrustRun→TranscriptionDraft adapter); selected by `settings.transcription_engine="two_phase"` (default `"legacy"`). Trust flags are ADVISORY annotations (`reader_disagreement`, `code_lint`) — they never modify draft text.
- `app/services/gcs_service.py`, `document_parser.py`, `email_service.py`, `auth_service.py`, `rubric_management_service.py`.

### Models (`app/models/`)
- `grading.py` — `Rubric` (now carries `extraction_job_id` provenance FK), `GradedTest` (revision chain, JSONB draft/contract, cost columns), `GradingBatch`.
- `rubric_extraction_job.py` — `RubricExtractionJob` (PR-1 async extraction lifecycle).
- `transcription.py` — `Transcription`. `student.py` — `Student`. `classroom.py` — `Class`, `ClassMembership`. `subject_matter.py`, `user.py`, `rubric_share.py`.
- `raw_rubric.py` — **DEPRECATED**: never populated by any code path; its intended purpose (extraction JSON + provenance + filename) is subsumed by `rubric_extraction_jobs`. Do not wire new writes to it; dropping it (+ `rubrics.raw_rubric_id`) is a later cleanup migration.

### Migrations (`backend/migrations/`)
Raw SQL, zero-padded, sequential (`NNN_description.sql`). No Alembic. Current head: **013** (schema_migrations ledger). The schema is created/reshaped by 007 (cleanup) + 008 (new schema); 009 (graded-test cost columns); 010 (revision-chain deferrable FK); 011 (S11 transcription `batch_id` + batch `test_count`); 012 (`rubric_extraction_jobs` + `rubrics.extraction_job_id`); 013 (`schema_migrations` ledger + commit-token convention). Caveat: the `rubrics` and `grading_batches` base tables predate migration 001 (created unversioned via `create_all`) — the numbered series only ALTERs them. The ORM mirrors the migrated schema — it does not generate it. When the DB and a schema doc disagree, the DB is truth.

**Migrations are the only DDL source. `create_all` is a fresh-dev-database bootstrap only.** Two rules, both enforced by `tests/test_schema_canon.py`:

1. **Every migration ENDS with its own commit token** — `INSERT INTO public.schema_migrations (version, note) VALUES ('NNN', '...') ON CONFLICT DO NOTHING;` as the **last statement**. The row is a commit token, not a label: it only lands if every statement before it landed, so a partially-applied file leaves a *gap* the boot check sees. This is not ceremony — migration 011 half-applied in production (statement (a) landed, (b) didn't) and stayed undetected for weeks. A ledger that merely recorded "011 was run" would not have caught it.
2. **Add the version to `EXPECTED_MIGRATIONS` in `app/database.py`.** At boot, `verify_schema_head()` set-compares the ledger to that tuple and logs `SCHEMA OK` or a loud `SCHEMA MISMATCH ... NOT APPLIED` **ERROR** (it never crashes — a deploy landing mid-migration-window must still boot so you can finish applying). The check is set-based, not `MAX(version)`: a max check reads head 013, compares to expected 013, and reports all-clear while 011 is missing from the middle.

`init_db` runs `create_all` **only** when `APP_ENV` is a dev env **AND** the target DB has no `schema_migrations` ledger. The ledger check is the load-bearing half: a dev `.env` routinely carries `APP_ENV=development` *plus* the live `DATABASE_URL` (that is how the integration tests run), so an `APP_ENV`-only gate would still `create_all` **production** from a laptop. The ledger is a property of the *database*, not of the process's opinion about itself.

### Tests
`tests/` mirrors `app/`. Pure compilers/validators (`gradable_compiler`, `graded_test_contract_compiler`, grader `validator`) are tested with **zero mocks**. The agent and endpoints mock the LLM (patch `with_structured_output(...).ainvoke` / inject a fake `VLMProvider`) — **never call OpenAI in tests.** `pytest -q`.

---

## 9. The auth & ownership pattern (every domain endpoint)

Established once, copied everywhere (the rubric endpoints are the reference implementation):
- `current_user: User = Depends(get_current_user)` — required; public endpoints (login/signup/refresh/health) are the only exceptions.
- The owning `user_id` is **always** `current_user.id`, **never** from the request body. A body-supplied `user_id` is a privilege-escalation bug.
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

| Area | Notes |
|---|---|
| `src/app/page.tsx` | Main workflow: rubric-select → upload → transcribe → review → grade → draft-review |
| `src/app/my-rubrics/`, `my-graded-tests/`, `my-classroom/` | Library, graded history, roster (students/classes tabs) |
| `src/components/RubricDocument.tsx` | **The document mirror (PR-5 S2) — the rubric-review surface for the docx flow.** Reads as her DOCX annotated by Vivi (see §11 mirror note) |
| `src/components/RubricEditor.tsx` | **Rollback** rubric editor; owns the save-blocking state machine (§11). Behind `USE_DOCUMENT_MIRROR=false`; the mirror replaces it live |
| `src/components/document/` | Mirror primitives: `EditableText`, `EditablePoints`, `CodeBlock`, `DisclosureRow`, `DataTables` (document-styled trace/context/mini-tables) |
| `src/components/TranscriptionReviewPanel.tsx` | Side-by-side transcription vs. source PDF (the layout reused for graded-test review) |
| `src/components/GradedTestReviewPanel.tsx` | Graded draft review/edit/approve; revision affordances (regrade/manual-edit/retry) |
| `src/components/AnnotationBanner.tsx` | Single severity-differentiated **rubric** annotation renderer (a real standalone file since PR-5 S2 — RubricEditor + the mirror both import it) |
| `src/components/StudentPicker.tsx` | Select-or-create student; reused in single + batch flows |
| `src/lib/api.ts` | API client; `getAuthHeaders()` on every authenticated call |
| `src/types/` | TS mirrors of backend schemas |

**Frontend lockstep:** every backend sprint that changes an endpoint or type ships its frontend change in the same PR. **Subject modularity (§3.3) applies:** shared components and `utils/`/`types/` stay subject-agnostic; CS-specific UX lives in CS-specific surfaces only.

### The fetch seam + error-surface convention (PR-2)

- **One seam.** `src/lib/api.ts` exports `apiFetch<T>` (auth headers in, typed `ApiError`/`ApiAuthError` out, JSON back). **Every ordinary call goes through it** — there are no hand-rolled `fetch` sites left in `api.ts`. Two deliberate carve-outs use non-throwing `apiFetchRaw`: the **streaming** transcription fns (they read `response.body`, which a JSON parse would consume) and the rubric **save/update/compile** fns (they *read* non-OK bodies for the warnings modal / `RubricSaveError`); both still call `throwIfAuthError` so 401 stays terminal.
- **Auth endpoints are NOT on the seam** (`auth.tsx` uses raw `fetch`, on purpose). A wrong password legitimately returns 401 — routing login through `ApiAuthError` would report it as "session expired" and trigger the stash-and-logout flow on a failed login.
- **No silent retries at the seam.** A mutation must never auto-repeat (a retried `POST /grade` is a duplicate grade). Poll-loop retry lives in the hooks, where it is visible, bounded, and **terminal on 401/403** (`useExtractionJob`, `useBatchProgress`).
- **Error-surface convention:** **transport/auth → sonner toast** (`lib/errorSurface.ts`); **domain/validation → the existing inline `setError` banners + the wizard modal**. Do not migrate the ~54 inline sites — a point-sum violation is not a network failure.
- **Session (`lib/session.ts`):** the JWT TTL is 7 days and `POST /auth/refresh` **already existed but was never called**; it is gated on a *valid* token, so it renews **before** expiry only. The client decodes `exp` locally and renews inside a 48h window (on mount / focus / 15-min tick), which makes mid-session expiry effectively unreachable for an active teacher — with **zero backend change**. The backend cannot distinguish expired from malformed (both → 401 "Not authenticated"), but the **client can**, which is how it says "פג תוקף ההתחברות" honestly.
- **Crash-stash:** before any forced logout, in-progress *review edits* are stashed to `localStorage` and offered back after login. PR-1 already made the extraction *result* durable server-side (the job row); the stash protects the teacher's **edits on top of it**. General draft autosave is PR-5.
- **Tests:** `npm test` (vitest — pure logic + SSR render tests) and `npm run test:e2e` (Playwright, PR-4 — the render-half guard, route-mocked; browsers install in CI). There was no frontend test runner before PR-2.

### Codegen — the wire types are GENERATED (PR-4, R-B)

`src/lib/api-types.ts` is **generated** from the backend OpenAPI schema (`npm run gen:api` → `scripts/gen-api-types.mjs` → `backend/scripts/dump_openapi.py` + pinned `openapi-typescript`). **Do not hand-edit it.** A GitHub Actions job (`.github/workflows/api-types-drift.yml`) regenerates it in CI and fails on any diff — the wire contract's `suite_hash`. This kills the Decimal type-lie **at the source**: a `Decimal` types as `string` in the schema (matching the wire), so generated types never claim `number` for a field the wire sends as a string. **Two type families coexist BY DESIGN and are NOT interchangeable:** the generated **wire** types (string points, wide unions) feed `api.ts`; the hand-written **editor** family (`types/rubric.ts`, number points, narrow unions like the `question_type` literal set) is what the editor mutates. The seam (`rubric-transform.ts`) is guarded by the golden round-trip suite, **not** the compiler — TS never errors on ignoring a wire field (§11). New/touched wire types consume the generated ones; hand-written mirrors migrate opportunistically. The one deliberately hand-written response type is `CompileErrorDetail` — the 400 compile-rejection rides an HTTPException `detail`, which FastAPI leaves out of the OpenAPI schema.

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
**Required:** `OPENAI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `DATABASE_URL` (`postgresql+asyncpg://...`).
**Common:** `OPENAI_MODEL`=`gpt-4o`, `OPENAI_VISION_MODEL`=`gpt-4o`, `EXTRACTION_LLM_PROVIDER`/`EXTRACTION_LLM_MODEL`, `GCS_BUCKET_NAME`=`grader-vision-pdfs`, `ALLOWED_ORIGINS`, `LOG_LEVEL`, `APP_ENV`, `FRONTEND_BASE_URL`.
**Transcription:** `PARALLEL_TRANSCRIPTION_ENABLED`, `MAX_PARALLEL_PAGES`, `VLM_TIMEOUT_SECONDS`, `VLM_MAX_RETRIES`.
**Extraction jobs (PR-1):** `EXTRACTION_EXECUTION_MODE` (`cloud_tasks` prod / `inline` local-dev-only), `EXTRACTION_HEARTBEAT_TTL_MINUTES` (15), `CLOUD_TASKS_LOCATION`/`CLOUD_TASKS_QUEUE`/`CLOUD_TASKS_INVOKER_SA`, `SERVICE_BASE_URL` (this service's Cloud Run URL — task target), `INTERNAL_TASK_TOKEN` (dev shared-secret for `/internal`), `EXTRACTION_MAX_UPLOAD_MB` (15). Prod model pin (D-2): `EXTRACTION_LLM_PROVIDER=openai`, `EXTRACTION_LLM_MODEL=gpt-5.5`, `EXTRACTION_LLM_REASONING_EFFORT=medium`, `EXTRACTION_LLM_MAX_TOKENS=32000` — the config the eval gate was earned at; gpt-4o (the code default) was never evaluated against the 3.3.1 prompt.
**LangSmith:** `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`.

---

## 12.5 Repository & deployment layout — READ THIS BEFORE YOU `git push`

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

- **Compile fails INV-1..4** → inspect the failing `Annotation.target_id` for the exact scope; check the `ContractCompiler` validator that raised; verify all point fields are `Decimal` (not late-float-converted). If it came from extraction not teacher edit, check `docx_v3/pipeline.py` totals.
- **Persistent extraction WARNING in the editor** → `annotation_type="rubric_mismatch"` means the source DOCX itself has a sum mismatch the LLM faithfully copied; the teacher fixes it before save.
- **Save/Approve button stuck blocked** → check `hasBlockingAnnotations`; confirm the backend returned ERROR annotations (network tab); confirm every violation has been resolved.
- **`graded_tests` CHECK violation on write** → you set the wrong combination of `status`/`draft_json`/`contract_json`/`approved_at`. The CHECK is correct; fix the write to set all required fields in one commit (esp. approval: all three together).
- **Two-leaf / unique-index violation in a revision flow** → you used insert-R2-first ordering; use `extend_chain()` (link-R1 → flush → insert-R2 → commit) and confirm migration 010's deferrable FK is applied.
- **Grade list crash / null fields** → an endpoint is reading the legacy `rubric_json` column instead of `contract_json`/dedicated columns. Read display fields from the right source (the `total_points` column, the contract), never the dead `rubric_json` blob.
- **Server import error after pull** → `python -c "import app.main"`; a mapper misconfiguration (mismatched `back_populates`, bad self-referential `remote_side`) fails here first.
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