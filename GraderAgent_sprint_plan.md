# Sprint Plan — Student Test Grading Backend

**Date:** 2026-05-19
**Owner:** Noam
**Goal:** Ship every backend piece needed to grade a student test end-to-end —
from `GradingRubricContract` + `TranscriptionReviewResponse` → graded test
stored under the student.

**Scope:** Tasks 1–6 as defined in the kickoff message.
**Estimate:** Realistically 6–8 focused hours. Aggressive but doable if
decisions are made up-front and we don't yak-shave.

---

## Operating principles for today

1. **Stupid-simple beats clever.** No agent loops, no ReAct, no multi-step
   reasoning unless we hit a problem that demands it. One LLM call per
   question, structured output, deterministic post-validation.
2. **Closed-world by construction, not by convention.** Contract-side types
   should not *be able to express* draft-only fields. Strip via type
   replacement, not via `model_copy(update={...None...})`.
3. **One file = one concept.** New schemas live in their own files. New
   compilers live in their own files. New agents live in their own files.
4. **Describe approach → wait → write code.** Each phase has a STOP gate.
   Don't push past a STOP without explicit confirmation.
5. **Deprecated `agents/test_grader/*` is reference only.** We are not
   refactoring it. We are writing a new agent from first principles. The
   old one's per-criterion-with-ReAct architecture is the *thing we're
   moving away from*, not a target to match.

---

---

## Invariant taxonomy — read this before reading the rest

The frontend live validators (PR1 — rubric editor) and the backend compile-time
invariants (this sprint — contract compiler) share the same underlying math but
use parallel naming. To avoid confusion, this sprint plan uses the frontend
naming throughout. The mapping:

| Concept | Naming used in this plan | Where it fires |
|---|---|---|
| Σ children.points == parent.total_points (question scope) | **INV-R1** | Editor live + contract compile |
| Σ sq.criteria.points == sq.points (per sub-question slice of INV-R1) | **INV-R1b** | Editor live + contract compile |
| Σ sub_criterion.points == criterion.points | **INV-R2** | Editor live + contract compile (replaces the old `Σ rule.max_points == criterion.points`) |
| Σ q.total_points == rubric.total_points | **INV-R3** | Editor live only — by the time the rubric reaches the contract compiler, this is already enforced |
| `LevelCoverage` (every scoring level is reachable) | **INV-5 — deprecated** | Removed entirely; no scoring levels in the new ontology |
| `CriterionAlignment` (criterion is well-formed for grading) | **INV-6** | Backend only; no frontend equivalent (LLM-assessed alignment check) |

All references below to "INV-R1", "INV-R2", etc. mean the math above, enforced
at contract-compile time unless otherwise stated.

---

## Pre-decided design choices — APPROVED 2026-05-19

| # | Decision | Choice |
|---|----------|--------|
| A | `GradedTestPreview` name | ✅ Use `GradedTestPreview` everywhere — clearer than `GradedTestDraft` for the editable artifact teachers see; `GradedTestContract` stays for the frozen post-approval form. Old `GradedTestDraft` is renamed and its compile() method is preserved. |
| C | Contract field set | ✅ See "Contract field decisions" below — keep `sub_criteria`, `example_solution`, `trace_tables`, `context_tables` everywhere. `proposals` and `title` (sub-question UX metadata, added in PR2) are stripped at the draft→contract boundary. |
| D | `GradableTest` persistence | ✅ New column `gradable_test_json` on existing `GradedTest` row. No new table. |
| E | Student grouping | ✅ Add `student_id: Optional[str]` everywhere (forward-compat for a future Student model), keep `student_name` as today's grouping key. Each field gets an inline comment marking it as forward-compat. |
| F | Identity resolution | ✅ At `GradableTest` compile time, NOT at transcription time. Transcription stays "naive" (question_number + sub_question_id). The compiler resolves to contract identities. Reason: keeps transcription service rubric-agnostic; identity resolution failures surface as compile errors with clear diagnostics. |
| G | Sub-question grading granularity | ✅ β — require an answer for each scope that has criteria. If missing, the agent skips the LLM call entirely and awards 0 across that scope with `FlagReason.NO_ANSWER`. Uniform shape for the agent. |

### GraderAgent decisions — APPROVED

| # | Decision | Choice |
|---|----------|--------|
| GA-1 | LLM call granularity | ✅ One call per question (not per criterion, not per test) |
| GA-2 | Missing-answer handling | ✅ Skip LLM call entirely on `all_missing_answers`; deterministic 0-point outcomes + `FlagReason.NO_ANSWER` |
| GA-3 | Retry policy | ✅ No ReAct retries. Quote-validation failures get flagged, never retried |
| GA-4 | LLM provider | ✅ OpenAI. Read model from `settings.openai_model` (default `gpt-4o`). Matches existing TestGraderAgent and rubric_generation_model conventions. |

### Contract field decisions (Decision C) — APPROVED with revisions

**MAJOR ONTOLOGY SHIFT (per Q1 answer):** `rules` / `ReductionRule` /
`ScoringLevel` are **deprecated entirely** in the contract. The lowest
grading unit is now `Criterion` (when no sub_criteria) or each
`sub_criterion` (when present, recursively). A new field `extra_notes`
captures grading instructions with no positive point value (e.g.,
"if they searched for the max but logic is correct, deduct 3").

For each draft-side type, fields that survive into the contract-side type:

**`ContractCriterion`** ← from `Criterion`:
- KEEP: `criterion_id`, `index`, `description`, `points`,
  `evaluation_guidance`, `skill_targets`, `requirements`,
  `measurability_status`, `evidence_policy`
- **NEW SHAPE:** `sub_criteria: Optional[List[ContractCriterion]]` —
  recursive type, replaces the old `List[Dict[str, str]]`
- **NEW FIELD:** `extra_notes: Optional[str]` — deduction guidance,
  no innate positive point value
- **DROP:** `rules` (deprecated entirely)

**`ContractSubQuestion`** ← from `SubQuestion`:
- KEEP: `sub_question_id`, `index`, `text`, `points`,
  `criteria` (now `List[ContractCriterion]`), `example_solution`
- DROP: `proposals`
- DROP: `title` — editable display label for the sub-question, added in PR2
  as pure UX metadata. Strictly editor-only by design (D3-c): the grader,
  the agent, and the graded-preview UI all derive sub-question labels from
  positional defaults via `getDisplayLabel`. Stripped at the contract
  boundary so it never leaks into grading or the compiled artifact.

**`ContractQuestion`** ← from `Question`:
- KEEP: `question_id`, `question_type`, `question_text`, `total_points`,
  `allow_multiple_valid_forms`, `skill_targets`, `requirements`,
  `criteria`, `sub_questions`, `example_solution`, `trace_tables`,
  `context_tables`
- DROP: `proposals`

**Invariant changes** (taxonomy: see "Invariant taxonomy" section above):
- Old `INV-2 (PointSumCriterion)` — which checked `Σ(rule.max_points) == criterion.points` — is replaced by **INV-R2**: `Σ(sub_criterion.points) == criterion.points` when sub_criteria is present. Vacuously satisfied otherwise.
- Old `INV-5 (LevelCoverage)` is **deprecated entirely** — no scoring levels in the new ontology.
- **INV-R1** (Σ children.points == question.total_points) and **INV-R1b** (Σ sq.criteria.points == sq.points) are enforced at compile time, with the same shape-split logic the frontend uses (sub-question-bearing questions check Σ sq.points; direct-criteria questions check Σ q.criteria.points).
- **INV-6 (CriterionAlignment)** unchanged — backend LLM-assessed check.

**On the draft side (NOT changing today):** `ExtractRubricResponse` /
`Criterion` keeps `rules: List[ReductionRule]` for backward compat with
the V3 extraction pipeline (which still produces stub binary rules).
The compiler will discard rules at contract-compile time. Removing
rules from the draft side is a follow-up sprint that requires updating
the V3 prompt and any code that touches `criterion.rules`.

**On `sub_criteria` semantics:** the agent reads the parent criterion's
description as context, then grades each sub_criterion individually
(points_awarded in `[0, sub_criterion.points]`, respecting numeric_policy
precision). `extra_notes` are read as deduction guidance during grading.

Only `proposals` and `title` (sub-question UX metadata) are stripped at
the draft→contract boundary. Everything else carrying student-context is
preserved.

The compiler builds contract types from draft types via explicit
construction. No `model_copy(update={...})` tricks.

---

## LLM configuration — locked in

The new `GraderAgent` follows the existing `TestGraderAgent` convention:

```python
# In app/agents/grader/grader.py
from app.config import settings

model = settings.openai_model  # defaults to "gpt-4o"
```

For reference, the codebase-wide registry (do not change today):

| Subsystem | Config key | Default |
|-----------|------------|---------|
| New `GraderAgent` (today) | `settings.openai_model` | `gpt-4o` |
| Deprecated `TestGraderAgent` | `settings.openai_model` | `gpt-4o` |
| Legacy `GradingAgent` | hardcoded fallback | `gpt-4-turbo-preview` |
| DOCX v3 extraction | `EXTRACTION_LLM_PROVIDER` / `EXTRACTION_LLM_MODEL` env vars | `openai` / `gpt-4o` |
| Legacy DOCX classifier | `settings.CLASSIFIER_MODEL_OPENAI` | `gpt-5.2-2025-12-11` |
| Rubric generator | `settings.rubric_generation_model` | `gpt-4o` |
| Vision/transcription | `settings.openai_vision_model` | `gpt-4o` |

**Inconsistency to revisit later (not today):** the DOCX v3 pipeline
reads raw env vars, not `settings`. Means `.env` edits to `openai_model`
won't affect it. Worth fixing in a future sprint.

---

## Phase A — Strip & seal `GradingRubricContract` (Task 1)

### Goal
Make the contract closed-world by *construction*, not by stripping
fields that the type still permits. Deprecate `rules` from the contract
ontology entirely. Introduce `extra_notes` and recursive `sub_criteria`.

### Deliverables

1. **New file:** `app/schemas/grading_contract.py` containing:
   - `ContractCriterion` (recursive — `sub_criteria: Optional[List[ContractCriterion]]`)
   - `ContractSubQuestion`
   - `ContractQuestion`
   - `GradingRubricContract` (rewritten to use `ContractQuestion[]`)
   - Helper: `iter_all_contract_criteria(contract) -> Iterator[(question_id, sub_q_id|None, ContractCriterion)]`
   - Helper: `iter_terminal_criteria(criterion) -> Iterator[ContractCriterion]`
     — yields either the criterion itself (if no sub_criteria) or its
     sub_criteria one by one. This is the actual *grading unit* iterator.

2. **Update `app/schemas/ontology_types.py`:**
   - Remove `GradingRubricContract` definition (now imported from `grading_contract.py`)
   - Add `extra_notes: Optional[str] = None` to **draft-side `Criterion`**
     (so the V3 pipeline can populate it once its prompt is updated)
   - Keep `ExtractRubricResponse`, `Question`, `SubQuestion`, `Criterion`,
     `ReductionRule`, `ScoringLevel` for now — draft side still uses rules
   - Re-export `GradingRubricContract` from `grading_contract` for backward
     compatibility with existing imports

3. **Update `app/services/contract_compiler.py`:**
   - Replace `q.model_copy(update={...})` strip pattern with
     explicit `_to_contract_question(q: Question) -> ContractQuestion`
     translation
   - **Drop `rules` entirely** during translation — they don't appear in
     ContractCriterion
   - **Drop `title` from sub-questions during translation** — D3-c
     (editor-only UX metadata; never appears in compiled contract)
   - **Implement INV-R2 validation:** the old logic checked
     `Σ(rule.max_points) == criterion.points`. New logic: if
     `criterion.sub_criteria` is non-empty, check
     `Σ(sub_criterion.points) == criterion.points`. Vacuously satisfied
     when sub_criteria is empty/None.
   - **Implement INV-R1 / INV-R1b validation** with the shape-split logic
     used by the frontend (see `frontend/src/utils/rubric-validation.ts`
     for the reference implementation):
       - Sub-question-bearing question: `Σ sq.points == q.total_points` (INV-R1) AND, per sub-question, `Σ sq.criteria.points == sq.points` (INV-R1b)
       - Direct-criteria question: `Σ q.criteria.points == q.total_points` (INV-R1)
   - **Drop INV-5 (LevelCoverage) logic** — no levels exist
   - **INV-6 (CriterionAlignment)** unchanged

4. **Backward-compat reads for existing DB rows:**
   - Existing `contract_json` rows have `rules`, no `sub_criteria` (or
     have `sub_criteria` as `List[Dict[str, str]]`).
   - Pydantic `model_validate` on the new contract types will drop
     unknown fields (`rules`) silently — good.
   - Old `sub_criteria` shape (`List[Dict[str, str]]`) will FAIL
     validation against the new `List[ContractCriterion]` type — bad.
   - **Solution:** add a `model_validator(mode="before")` on `ContractCriterion`
     that detects the old dict shape and either (a) converts each dict
     into a minimal `ContractCriterion` with `description`/`points` fields,
     or (b) discards it (since old dicts were "display-only" anyway).
     My recommendation: (b) — discard, mark the row as `needs_recompilation=True`.
   - **Coding agent task:** write a one-off migration script to flag all
     existing `Rubric` rows with `needs_recompilation=True`. Teachers
     re-save their rubrics to populate new sub_criteria via UI.

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| `app/schemas/ontology_types.py` | I have it | Direct edit |
| `app/services/contract_compiler.py` | I have it | Direct edit |
| `app/schemas/grading_contract.py` | New file | Direct create |
| V3 pipeline output of `sub_criteria` | UNKNOWN | **Coding agent task:** locate `app/services/docx_v3/` and any prompt that produces sub_criteria. Today V3 most likely produces NO sub_criteria (or empty `List[Dict[str, str]]`). Confirm and report. Do NOT update V3 today. |
| Frontend reads of `rules` | OUT OF SCOPE | The editor's old rules UI is gone; the frontend stopped reading `rules` in PR1 of the rubric-editor work. Verify `hydrateAnyQuestions` is not still carrying a `rules` field through; if it is, saved-rubric reads will silently drop it (correct, but worth confirming). **Out of today's scope** — flag for follow-up if the verification surfaces an issue. |
| Frontend reads of `sub_criteria` | NO RISK | The frontend already treats `sub_criteria` as objects (`.points`, `.sub_criterion_id`, `.description`) — see `frontend/src/utils/rubric-validation.ts`'s INV-R2 validator and `SubCriteriaEditor` component. The contract-side `List[ContractCriterion]` shape is structurally compatible from the frontend's perspective. The legacy-row backward-compat handled in Phase A step 4 covers the only real risk: rubrics saved with the old `List[Dict[str, str]]` shape are dropped or flagged for recompilation. |
| Tests in `tests/test_contract_compiler*.py` | UNKNOWN | **Coding agent task:** locate, update fixtures to remove `rules` from contract-side assertions and add sub_criteria fixtures. |
| Migration to flag existing rubrics for recompilation | New | **Coding agent task:** write the one-off script after Phase A core is in place. |
| Any service that constructs a `GradingRubricContract` programmatically | UNKNOWN | **Coding agent task:** grep for `GradingRubricContract(` constructor calls outside the compiler. Likely only in tests. |

### Acceptance criteria
- `GradingRubricContract.questions[0].criteria[0]` has type `ContractCriterion`
- `ContractCriterion` has no `rules` field at all
- `ContractCriterion.sub_criteria` is `Optional[List[ContractCriterion]]`
- `ContractCriterion.extra_notes` is `Optional[str]`
- `ContractSubQuestion` has no `title` field (stripped from draft per D3-c)
- INV-R1 / INV-R1b enforced with shape-split logic; INV-R2 enforced (sub_criteria point-sum); INV-5 removed; INV-6 unchanged
- Existing `Rubric.contract_json` rows either (a) load via `model_validate` with the dict-shape sub_criteria silently discarded, OR (b) get flagged `needs_recompilation=True` by the migration script
- All existing tests in `tests/test_contract_compiler*.py` pass (after fixture updates by coding agent)

### **STOP** — Confirm Noam approves Phase A scope before writing code

---

## Phase B — Design `GradableTest` (Task 2)

### Goal
Spec the marriage object: one well-typed input the GraderAgent consumes,
with all per-question context pre-sliced.

### Deliverable
**Inline schema spec** (no code yet, just the structure):

```
GradableTest                                    (frozen)
├── gradable_test_id: UUID
├── rubric_id: str
├── contract_version: str               # pinned for reproducibility
├── subject: str
├── programming_language: Optional[str]
├── student_name: str
├── student_id: Optional[str]           # forward-compat (Decision E)
│                                        # Today: always None; group by student_name.
│                                        # Future: populate from a Student model.
├── filename: str
├── transcription_id: str               # back-reference
├── total_pages: int
├── questions: List[GradableQuestion]
├── total_points_possible: Decimal
└── unmatched_transcription_answers: List[dict]
    # Diagnostic: answers in transcription that didn't match any
    # question in the contract. Surfaces transcription/contract
    # drift to the teacher.

GradableQuestion                                (frozen)
├── question_id: str
├── question_type: QuestionType
├── question_text: str
├── question_total_points: Decimal
├── example_solution: Optional[str]
├── trace_tables: Optional[List[Dict]]
├── context_tables: Optional[List[Dict]]
├── direct_criteria: List[ContractCriterion]    # criteria not in any sub_q
│                                                # each carries its own
│                                                # sub_criteria + extra_notes
├── sub_questions: List[GradableSubQuestion]
├── direct_answer: Optional[GradableAnswer]
│   # The student's answer for direct criteria scope.
│   # None if no answer transcribed for the question's direct part.
└── alignment_status: AlignmentStatus
    # matched | partial_missing_answers | all_missing_answers

GradableSubQuestion                             (frozen)
├── sub_question_id: str
├── index: int
├── text: Optional[str]
├── points: Decimal
├── example_solution: Optional[str]     # NEW — kept per Decision C
├── criteria: List[ContractCriterion]
├── answer: Optional[GradableAnswer]    # None if no answer transcribed
└── alignment_status: AlignmentStatus

GradableAnswer                                  (frozen)
├── answer_text: str
├── page_indexes: List[int]
├── transcription_confidence: float
└── transcription_notes: Optional[str]

AlignmentStatus (enum)
├── matched
├── answer_missing            # scope has criteria, no answer transcribed
└── scope_not_in_contract     # transcription has answer for non-existent scope
```

### Notes on the new criterion shape

A `ContractCriterion` inside `direct_criteria` or `sub_questions[].criteria`
now carries:
- `points`, `description`, `evaluation_guidance` (positive guidance)
- `extra_notes` (deduction guidance — read by the agent)
- `sub_criteria: Optional[List[ContractCriterion]]` — if present, the
  agent grades each sub_criterion individually; the parent criterion's
  description provides context but is not itself graded

The GraderAgent's prompt template, when handed a `GradableQuestion`,
walks the criterion tree and asks the LLM to award points at the
**terminal nodes** (leaves of the criterion tree — either a criterion
with no sub_criteria, or each sub_criterion under one that has them).

### Design rationale 

The current path passes `contract_json` (full rubric) + `answers` (raw
list) to the agent. The agent does identity resolution + scope slicing
+ context assembly *inside its LLM call orchestration*. This complects
three concerns (data preparation, prompt construction, LLM call) into
one place — and is the source of every dict-soup bug in
`grade_with_ontology_agent`.

**New conjecture:** all data preparation happens *before* the agent runs,
in a deterministic, testable function. The agent's input is fully
typed and per-question pre-sliced. The agent only does grading.

This is hard-to-vary (the schema is forced by the grading task's
structure), solves the problem (one well-typed input), and creates no
contradictions (closed-world is preserved because the criteria come
from the frozen contract).

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| Schema design | Self-contained | No external deps to verify |

### **STOP** — Confirm schema before writing code

Questions worth answering before Phase D:
- Anything missing from `GradableAnswer` we'd want for the agent prompt?
- Should `alignment_status` block grading at compile time (raise an error)
  or pass through (let the agent skip with NO_ANSWER flag)? **My answer:** pass through, never block — the teacher should be able to grade what was answered, with flags on what wasn't.

---

## Phase C — Strip `TranscribedAnswerWithPages` (Task 3)

### Goal
Make the transcription artifact lean and self-contained, ready for clean
composition into `GradableAnswer`.

### Current state (`schemas/grading.py:553`)
```python
class TranscribedAnswerWithPages:
    question_number: int           # 1-based
    sub_question_id: Optional[str] # "א", "ב"
    answer_text: str
    confidence: float
    transcription_notes: Optional[str]
    page_indexes: List[int]
```

### Verdict
**Keep all six fields.** They are all used downstream. No noise to strip.

Per Decision F (identity resolution at GradableTest compile time, not
transcription time), we do NOT add `question_id` here. The transcription
stays rubric-agnostic.

### Small cleanups
- Tighten the docstring to make it clear this is the *unbound*
  transcription artifact — identity binding happens in the
  GradableTest compiler.
- Add a `model_config = {"frozen": False}` (explicit) and a brief
  comment that it stays editable because teachers correct it before
  grading.

### Acceptance criteria
- No structural changes to the type
- Docstring is accurate about its role in the pipeline

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| `app/schemas/grading.py` | I have it | Direct edit (docstring only) |
| Transcription service callers | UNKNOWN | **Coding agent task:** verify nothing relies on the old docstring's wording. Trivial. |

### **STOP** — Skip if Noam agrees nothing meaningful changes here

---

## Phase D — Implement `GradableTest` (Task 4)

### Goal
Schemas + compiler + DB persistence for the marriage object.

### Deliverables

1. **New file:** `app/schemas/gradable_test.py`
   - All types from Phase B's spec
   - `AlignmentStatus` enum
   - `GradableTest.compile_summary() -> dict` for logging

2. **New file:** `app/services/gradable_test_compiler.py`
   - `class GradableTestCompiler`:
     - `compile(contract: GradingRubricContract,
                 transcription: TranscriptionReviewResponse,
                 student_meta: StudentMeta) -> GradableTest`
   - Responsibilities:
     - Iterate the contract's questions
     - For each question's direct criteria scope: find the matching
       transcription answer where `sub_question_id is None`
     - For each sub-question: find the matching transcription answer
     - Build `GradableQuestion` and `GradableSubQuestion` objects
     - Compute `alignment_status` per scope
     - Collect `unmatched_transcription_answers` (transcribed answers
       whose `(question_number, sub_question_id)` doesn't map to any
       contract scope)
     - Never raise — always produce a `GradableTest`. Misalignments
       become flags, not exceptions.

3. **Identity resolution helper:**

   The contract's `question_id` is NOT uniformly the `"q{N}"` shape.
   Two formats coexist in production data:
   - **`q{N}` shape** (e.g. `"q1"`, `"q12"`) — produced by the V3
     extraction pipeline at initial extraction.
   - **`q_{uid}` shape** (e.g. `"q_mxyz12ab"`) — produced by
     `addQuestion` in the frontend editor whenever a teacher adds a
     question after extraction. Any rubric that was edited has mixed IDs.

   Identity resolution is a deterministic two-pass match — **both passes
   are happy paths, neither emits a warning:**

   - **Pass 1 (direct match):** for each contract question, look up the
     transcription answer whose `question_number` matches the integer
     parsed from a `q{N}`-format `question_id`. Direct equality of
     digits.
   - **Pass 2 (positional fallback):** any contract question whose
     `question_id` does not parse as `q\d+` (e.g. teacher-added
     `q_<uid>`) is matched by its 0-based index in the contract's
     `questions` array, against the transcription answer whose
     `question_number` equals `index + 1`. This is the common case for
     edited rubrics, not an error case.

   A genuine identity-resolution failure (a transcription answer that
   matches no contract question by either pass) is recorded in
   `unmatched_transcription_answers` on the resulting `GradableTest` —
   it is data for the teacher to see, not a warning emitted from the
   compiler.

   Sub-question IDs match directly between transcription and contract
   (both sides use the same `sub_question_id` string).

4. **DB migration:**
   - Add `gradable_test_json: JSONB` column to `GradedTest` table
   - Nullable for backward compatibility with existing rows

5. **Smoke test:**
   - One golden test fixture: load a real saved rubric's contract_json
     + a hand-crafted TranscriptionReviewResponse, run the compiler,
     assert the resulting GradableTest has the expected shape.

### Acceptance criteria
- `GradableTest` compiles successfully from any saved contract + a
  valid transcription
- Misalignments produce flags, never exceptions
- DB migration applies cleanly

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| `app/schemas/gradable_test.py` | New file | Direct create |
| `app/services/gradable_test_compiler.py` | New file | Direct create |
| `app/models/grading.py` (SQLAlchemy `GradedTest` model) | UNKNOWN | **Coding agent task:** locate, share the `GradedTest` model definition. I'll then write the new columns. |
| Alembic migrations directory | UNKNOWN | **Coding agent task:** locate `alembic/versions/`, run `alembic revision --autogenerate -m "..."` after I update the model. |
| Existing fixtures for testing | UNKNOWN | **Coding agent task:** locate a real saved `contract_json` from the dev DB or fixtures to use as golden test input. |
| `app/schemas/ontology_types.py` `iter_terminal_criteria` helper | I'll add it in Phase A | Cross-phase dep — Phase D's compiler relies on the helper from Phase A. |
| Identity convention for `question_id` | KNOWN | Two formats coexist: `q{N}` from V3 extraction, `q_{uid}` from frontend `addQuestion`. Both are normal. See "Identity resolution helper" above for the two-pass match. Do NOT assume a single canonical format. |

### **STOP** — Confirm Phase D approach before writing code

---

## Phase E — Design, implement, test `GraderAgent` (Task 5)

### Goal
A stupid-simple LLM agent that consumes a `GradableTest` and produces
a `GradedTestPreview`.

### Architecture (stupid-simple v1)

**One LLM call per question.** Not per criterion, not per test.

For each `GradableQuestion`:
1. **Skip path:** if `alignment_status == all_missing_answers`,
   deterministically emit 0-point outcomes for every terminal criterion
   in the question, with a `FlagReason.NO_ANSWER` flag. Skip the LLM
   call entirely.
2. **Grading path:** call the LLM with a structured-output schema.
   Pass the question's text, the criteria tree (parent criterion descriptions
   as context + their sub_criteria as grading units, OR plain criteria
   when no sub_criteria), `extra_notes` per criterion, the student's
   answer text(s), and any pedagogical context (example_solution,
   trace_tables, context_tables).
   The LLM returns, per **terminal criterion** (leaf of the criterion tree):
   `{terminal_criterion_id, points_awarded, reasoning, quote_text}`.

### The terminal-criterion grading model

A criterion tree has two shapes:

**Shape 1: Leaf criterion (no sub_criteria)**
```
Criterion "Loop correctness" (5 pts)
  → graded as a whole
  → LLM awards points_awarded ∈ [0, 5]
```

**Shape 2: Branch criterion (with sub_criteria)**
```
Criterion "Function correctness" (10 pts)  ← context only, not graded
  ├── Sub-criterion "Correct signature" (3 pts) ← graded
  ├── Sub-criterion "Correct loop" (4 pts)      ← graded
  └── Sub-criterion "Correct return" (3 pts)    ← graded
  extra_notes: "if they searched for max but logic correct, deduct 3"
```

The agent grades each leaf (terminal criterion). The parent criterion's
description, evaluation_guidance, and extra_notes are passed as context
to the LLM but the parent's `points` field is NOT directly graded —
it's the sum of its children.

For Shape 2, `extra_notes` is shown to the LLM as deduction guidance:
"if these conditions apply, deduct N points from the otherwise-awarded total."

### Partial credit precision

The LLM's `points_awarded` is constrained to `[0, terminal_criterion.points]`
with precision per `numeric_policy.precision` (default: 0.5 increments).
Post-validation rounds to precision and clamps to bounds.

**Deterministic post-validation per question:**
- **Closed-world check:** every `terminal_criterion_id` returned by the
  LLM exists in the question's contract slice. Extra IDs are flagged
  with `FlagReason.CLOSED_WORLD_VIOLATION`. Missing IDs are flagged
  with `FlagReason.UNGRADED_CRITERION` and get 0 points.
- **Bounds & precision:** clamp `points_awarded` to `[0, max]`, round
  to `numeric_policy.precision`. If clamping was needed, flag.
- **Quote validation:** substring search in student answer (case-folded,
  whitespace-normalized). If not found, Levenshtein fuzzy match with
  ratio ≥ 0.85. If still not found, flag with `FlagReason.QUOTE_NOT_FOUND`.
  Status flag set on the quote (`EXACT`, `FUZZY`, `NOT_FOUND`).

**Transform to ontology types:**
- Each LLM result → `CriterionOutcome` (now carries `points_awarded`,
  `reasoning`, `evidence_quote`, optionally `sub_criterion_outcomes`)
- For branch criteria: `points_awarded = Σ(sub_criterion_outcomes.points_awarded)`
- Aggregate to `QuestionOutcome` (sum of criterion outcomes, includes
  sub-question outcomes)

**Aggregate all questions → `GradedTestPreview`.**

### Why this is right (Deutsch test)

- **Hard-to-vary:** the LLM sees one self-contained question with
  the criterion tree (parent descriptions for context, leaves for grading).
  The only thing varying is the LLM's choice of points + reasoning + quote.
- **Solves the problem:** every leaf criterion gets a points_awarded,
  every grade has evidence, all points are bounded by the contract.
- **No contradictions:**
  - Closed-world: enforced by post-validation against the question's contract slice
  - Evidence: enforced by structured output (quote_text required)
  - Points bounds: enforced deterministically post-LLM
  - Point sums: enforced by INV-R1 (question total) and the branch-criterion
    sum rule (parent.points_awarded = Σ children.points_awarded)

### Ontology types being deprecated (Phase E touches these)

- `RuleOutcome` — gone, replaced by recursive `CriterionOutcome`
- `ClaimType` enum — gone (no rule_kind to dispatch on)
- `RuleKind`, `LevelSelectionMode`, `ScoringType` enums — gone from
  contract types; may stay in `ontology_types.py` for draft-side until
  the V3 pipeline migrates off rules
- `EvidenceClaim`, `AnswerQuotation` — kept, useful for evidence

### `CriterionOutcome` new shape

```
CriterionOutcome (Pydantic)
├── criterion_id: str
├── description: str                    # denormalized for display
├── points_possible: Decimal
├── points_awarded: Decimal             # bounded [0, points_possible]
├── reasoning: str                      # Hebrew claim
├── evidence_quote: AnswerQuotation     # student-answer quote + validation status
├── sub_criterion_outcomes: Optional[List[CriterionOutcome]]
│                                        # Recursive: present iff the contract criterion had sub_criteria
└── flags: List[FlaggedOutcome]
```

### What we're explicitly NOT doing
- No ReAct loops. If a quote doesn't validate, FLAG, don't retry.
- No multi-step "reflection." One shot per question.
- No LangGraph orchestration. Just a `for question in questions: grade(question)` loop.
- No `agents/test_grader/*` reuse. We're not refactoring; we're writing fresh.
- No rule/level grading paradigm. The agent never sees ScoringLevel or rule_id.

### Deliverables

1. **New file:** `app/schemas/graded_test_preview.py`
   - `GradedTestPreview` (the editable artifact)
   - Updated `CriterionOutcome` (recursive, per shape above)
   - `QuestionOutcome` (updated to reflect criterion-only grading)
   - Reuse `EvidenceClaim`, `AnswerQuotation`, `FlaggedOutcome`,
     `GradedTestStatus` from `ontology_types.py`
   - `GradedTestPreview.compile(approved_by: str) -> GradedTestContract`
     for the approval path

2. **New file:** `app/agents/grader/schemas.py`
   - `QuestionGradingRequest` (the LLM input bundle for one question)
   - `TerminalCriterionGrade` (LLM output per leaf: criterion_id, points_awarded, reasoning, quote_text)
   - `QuestionGradingResponse` (LLM output: list of TerminalCriterionGrade)

3. **New file:** `app/agents/grader/prompt.py`
   - One prompt template, Hebrew-aware, that takes a
     `QuestionGradingRequest` and renders the LLM input
   - Walks the criterion tree, showing parent context + leaf grading units
   - Includes `extra_notes` per criterion as deduction guidance
   - Includes the student answer (and per-sub-question answers if applicable)
   - Includes pedagogical context (example_solution, trace_tables, context_tables)

4. **New file:** `app/agents/grader/validator.py`
   - `validate_question_grading(grading: QuestionGradingResponse,
                                  gradable_question: GradableQuestion,
                                  numeric_policy: NumericPolicy) -> ValidationResult`
   - Closed-world, bounds/precision, and quote validation
   - Pure function, no LLM calls

5. **New file:** `app/agents/grader/grader.py`
   - `class GraderAgent`:
     - `async def grade(gradable_test: GradableTest) -> GradedTestPreview`
   - Iterates questions, calls `_grade_question` per question
   - Aggregates outcomes, builds `GradedTestPreview`
   - Tracks `llm_calls_count`, `grading_duration_ms`

6. **New file:** `app/agents/grader/__init__.py`
   - Re-exports `GraderAgent`

7. **Tests:**
   - `tests/agents/test_grader_validator.py` — pure unit tests for
     closed-world, bounds, and quote validation
   - `tests/agents/test_grader_integration.py` — golden test with
     a real (rubric, transcription) fixture: assert structural
     properties of the output
   - Mock the LLM in the integration test by replaying a recorded
     LLM response

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| `app/config.py` `settings.openai_model` | UNKNOWN | **Coding agent task:** verify `settings.openai_model` exists and defaults to `gpt-4o`. |
| OpenAI client / SDK setup | UNKNOWN | **Coding agent task:** locate the existing OpenAI client initialization pattern (likely a shared helper). If it exists, reuse it. If not, set up one. |
| Structured-output helper | UNKNOWN | **Coding agent task:** grep for `response_format` and `json_schema` usage across the codebase. If a helper exists that wraps OpenAI's strict JSON schema output, reuse it. |
| Hebrew prompt style examples | UNKNOWN | **Coding agent task:** find existing Hebrew prompts in `app/services/` or `app/agents/`. Match the system prompt style (header conventions, instruction tone, JSON output framing). |
| `tests/agents/` directory existence | UNKNOWN | **Coding agent task:** verify the test directory pattern, pytest fixtures location, async test conventions. |
| `ontology_types.py` — `CriterionOutcome` & `RuleOutcome` | I have it | I'll update `CriterionOutcome` to the new recursive shape. RuleOutcome stays in the file (deprecated, will be removed when graded_json column is removed in a future sprint). |
| Levenshtein library | UNKNOWN | **Coding agent task:** check if `rapidfuzz` or `python-Levenshtein` is already in `pyproject.toml`. If not, use `difflib.SequenceMatcher` (stdlib). |

### **STOP — Final sub-decisions for Phase E**

GA-1 through GA-4 are locked. Three implementation-detail decisions remain:

1. **Prompt language?** Vivi rubrics are Hebrew; student answers are Hebrew;
   the deprecated agent's `claim_statement` was Hebrew. My default would be
   Hebrew system prompt + Hebrew user message + Hebrew strings in the
   structured output schema. Confirm or override.
2. **OpenAI structured output mechanism?** Three options in modern OpenAI:
   - `response_format={"type": "json_schema", "json_schema": {"strict": True, ...}}` (recommended for new code)
   - Tool/function calling with strict schemas
   - Raw JSON parsing with retries

   What does the rest of Vivi use? Coding agent task above will surface this.
3. **Partial credit precision.** Default to `numeric_policy.precision`
   (typically 0.5). LLM is constrained to multiples of precision via
   the structured-output schema (`"multipleOf": 0.5` in JSON Schema).
   Confirm.

### Acceptance criteria
- A single (rubric, transcription) fixture goes through the agent and
  produces a `GradedTestPreview` with valid structure
- Closed-world violations are caught and flagged, not crashed
- Quote validation produces `EXACT`/`FUZZY`/`NOT_FOUND` correctly
- Branch criteria correctly aggregate sub_criterion_outcomes
- LLM call count = (number of questions with at least one transcribed answer)
- No agent loop / no retries / no ReAct

---

## Phase F — Store `GradedTestPreview` under student (Task 6)

### Goal
Persist the graded preview, expose it for the teacher to review and
approve, and group by student.

### Deliverables

1. **DB migration on `GradedTest`:**
   - Add columns:
     - `gradable_test_json: JSONB` (already added in Phase D)
     - `preview_json: JSONB` (the GradedTestPreview)
     - `contract_version: str` (for reproducibility)
     - `status: str` (GradedTestStatus enum value)
     - `student_id: Optional[str]` (per Decision E — nullable for now)
   - Keep `graded_json` for legacy compatibility; new flow writes to `preview_json`

2. **New service:** `app/services/graded_test_service.py`
   - `save_graded_test_preview(db, preview: GradedTestPreview,
                                 gradable_test: GradableTest,
                                 rubric_id: UUID,
                                 user_id: UUID|None) -> GradedTest`
   - `approve_graded_test(db, graded_test_id: UUID,
                            edited_preview: GradedTestPreview,
                            approved_by: str) -> GradedTestContract`
     - Validates the edited preview
     - Compiles to GradedTestContract
     - Updates the row: sets `status = SAVED`, stores the contract,
       fresh `contract_version`

3. **Update endpoint** `POST /grade_with_transcription` (`grading.py:1170`):
   - Replace the current `grading_router.grade_test` legacy fallback with:
     - Build `GradableTest` via the compiler
     - Run `GraderAgent.grade(gradable_test)`
     - Save via `graded_test_service.save_graded_test_preview`
     - Return the `GradedTestPreview` to the frontend for review
   - Delete the legacy `try/except GradingValidationError` fallback —
     it's the deprecated path

4. **New endpoint:** `POST /graded_tests/{id}/approve`
   - Body: the (possibly edited) `GradedTestPreview`
   - Calls `approve_graded_test`
   - Returns the `GradedTestContract`

5. **New endpoint:** `GET /students/{student_name}/graded_tests`
   - Lists graded tests for a student (grouped by name today;
     by student_id when the Student model exists)
   - Filters by rubric_id, status, etc.

### Acceptance criteria
- A grade-and-save round-trip works end-to-end via the new endpoint
- A teacher can fetch their student's graded tests
- Approval path produces a frozen GradedTestContract
- Deprecated `grade_ontology` and legacy `grade_student_test` paths
  are NOT touched (we leave them alive as a fallback; we don't delete
  until the new path is battle-tested)

### Codebase touch points & coding-agent tasks

| Touch point | Status | Action |
|---|---|---|
| `app/api/v0/grading.py` | I have it | Direct edit — replace the body of `grade_with_edited_transcription` (around line 1170) with the new pipeline. Keep legacy endpoints alive. |
| `app/models/grading.py` GradedTest model | UNKNOWN | **Coding agent task:** add columns (gradable_test_json, preview_json, contract_version, status, student_id). Cross-phase with Phase D's migration. |
| `app/services/graded_test_service.py` | New file | Direct create |
| Auth middleware / `Depends(...)` patterns | UNKNOWN | **Coding agent task:** copy the auth pattern from existing endpoints in `grading.py` (likely `get_current_user` dependency). |
| Router registration | UNKNOWN | **Coding agent task:** ensure new endpoints are registered. Likely auto-registered via the existing router in `app/api/v0/__init__.py` or similar. |
| Frontend client (`api.ts`) | OUT OF SCOPE | **Note:** frontend will need updates to call new endpoints, render `GradedTestPreview` shape, send back edited preview to `/approve`. **Out of today's scope** — flag for follow-up. |
| Existing student-grouping queries | UNKNOWN | **Coding agent task:** check if any service already lists tests by student_name. If yes, refactor to a shared query. If not, write fresh. |

### **STOP** — Confirm Phase F endpoint surface before writing code

---

## Cross-cutting concerns

### Files I still need (won't block start, but flag)
- `agents/test_grader/__init__.py` — for confirmation of what's being deprecated
- `models/grading.py` (the SQLAlchemy `GradedTest` model) — needed for Phase F migration
- Any existing prompt files for Hebrew grading — needed for Phase E prompt style decisions

### What we're NOT changing today
- The rubric pipeline (Phase 1 of the system). Untouched.
- The transcription service itself. Untouched (just the schema docstring).
- The legacy `grade_student_test` and `grade_ontology` endpoints. Left alive as fallback.
- The Student model. Deferred (per Decision E).

### Logging discipline
- Every phase that writes to the DB logs: rubric_id, contract_version,
  student_name, timestamps, and any flag/warning counts
- The GraderAgent logs per-question: llm_call_duration_ms,
  llm_token_counts (if available), validation flag count
- No logging the full LLM response — that's an artifact; log a hash + count

### What "done for the day" looks like
End-to-end:
1. Pick a saved compiled rubric in the DB
2. Run a transcription against a real student PDF (or use a saved one)
3. Hit `/grade_with_transcription` with the (possibly edited) transcription
4. Get back a `GradedTestPreview`
5. Optionally hit `/graded_tests/{id}/approve` to freeze it
6. Hit `/students/{student_name}/graded_tests` and see the result

If steps 1–6 work against one real student test, the sprint is done.

---

## Execution order (recommended)

| Order | Phase | Est. time | Why |
|------:|-------|-----------|-----|
| 1 | **A** — Strip contract + new ontology | 120 min | Foundation; bigger than originally estimated because of rules deprecation + recursive sub_criteria + INV-R2 rewrite + backward-compat for existing DB rows |
| 2 | **B** — Design GradableTest | 15 min | Pure design; lock the shape before code |
| 3 | **C** — Trim TranscribedAnswerWithPages | 10 min | Trivially small |
| 4 | **D** — Implement GradableTest | 90 min | Bulk schema + compiler + migration |
| 5 | **E** — GraderAgent | 150 min | Simpler than originally estimated thanks to rules deprecation; spec → prompt → validator → grader → tests |
| 6 | **F** — Persistence & endpoints | 90 min | Wire it all up |

Buffer: ~60 min for integration and a real end-to-end test.

**Total: ~7.75 hours.** Tight but plausible if STOP gates are answered fast
and the coding agent runs the codebase-exploration tasks in parallel
with my schema work.

## Working with the coding agent

Each phase has a **"Codebase touch points & coding-agent tasks"** table.
Items marked **UNKNOWN** are where I don't have direct visibility and
need the coding agent to:
- Locate a file/pattern in the codebase
- Verify an assumption I made
- Run a migration or update fixtures
- Surface an existing helper I should reuse

The pattern is: I describe approach + write the core schemas/services;
the coding agent does the surrounding integration work (locating files,
updating tests, generating migrations, verifying conventions). Each
phase's STOP gate is the right time to fan out coding-agent tasks for
that phase.

---

## Decision log

| Decision | Choice | Made by | At |
|----------|--------|---------|-----|
| A — GradedTestPreview naming | Approved | Noam | 2026-05-19 |
| C — Contract field set (sub_criteria kept, rules deprecated) | Approved | Noam | 2026-05-19 |
| D — GradableTest persistence | Approved | Noam | 2026-05-19 |
| E — Student model | Approved (forward-compat student_id) | Noam | 2026-05-19 |
| F — Identity resolution | Approved | Noam | 2026-05-19 |
| G — Sub-question granularity | Approved | Noam | 2026-05-19 |
| GA-1 — One call per question | Approved | Noam | 2026-05-19 |
| GA-2 — Skip LLM on missing answer | Approved | Noam | 2026-05-19 |
| GA-3 — No ReAct retries | Approved | Noam | 2026-05-19 |
| GA-4 — OpenAI gpt-4o via settings.openai_model | Approved | Noam | 2026-05-19 |
| **Q1a — sub_criteria replaces rules** | **Approved (rules deprecated entirely)** | Noam | 2026-05-19 |
| **Q1b — sub_criteria as nested Criterion[]** | **Approved (upgrade in Phase A)** | Noam | 2026-05-19 |
| **Q1c — INV-R2 replaces old sub_criterion sum check** | **Approved** | Noam | 2026-05-19 |
| **NEW — extra_notes field on Criterion** | **Approved** | Noam | 2026-05-19 |
| **POST-PR2 — `SubQuestion.title` stripped at contract boundary** | **Approved (i — accept the regression)** | Noam | post-PR2 review |
| **POST-PR2 — INV taxonomy aligned to frontend INV-R\* naming** | **Approved** | Noam | post-PR2 review |
| **POST-PR2 — Phase D identity resolution treats both `q{N}` and `q_{uid}` formats as happy paths** | **Approved** | Noam | post-PR2 review |
| GA-5 — Prompt language | (pending — default Hebrew) | | |
| GA-6 — Structured output mechanism | (pending — coding agent will surface existing pattern) | | |
| GA-7 — Partial credit precision (0.5 step?) | (pending — default `numeric_policy.precision`) | | |
| Q2 — GradedTestDraft.to_legacy_format() fate | (pending — default keep+dual-write) | | |

---

## Open questions before Phase E starts

The Q1 cluster is resolved — rules are deprecated, sub_criteria is the
recursive grading unit, extra_notes captures negative-only guidance.
Three smaller items still need confirmation. None of them block Phases
A through D.

### GA-5 — Prompt language
Default Hebrew throughout (system prompt + user message + structured
output strings). Confirm or override.

### GA-6 — Structured output mechanism
Surfaces from the coding agent's exploration of existing OpenAI usage.
My recommendation: `response_format={"type": "json_schema",
"json_schema": {"strict": True, ...}}`. Will confirm pattern when the
coding agent reports.

### GA-7 — Partial credit precision
Default to `numeric_policy.precision` (typically 0.5). LLM constrained
to multiples via the JSON Schema's `multipleOf` keyword. Confirm.

### Q2 — `GradedTestDraft.to_legacy_format()` fate
Existing method flattens outcomes to a `grades[]` shape for legacy
`graded_json` compatibility. My default: keep it (renamed) and dual-write
to both `graded_json` and the new `preview_json` columns for one sprint,
then deprecate.

---

## Deferred to follow-up sprints (explicitly NOT today)

These come up as I work through the plan. Listing them so we don't lose
them and don't accidentally scope-creep them in.

1. **V3 pipeline prompt update.** Teach the extraction LLM to populate
   `sub_criteria: List[Criterion]` (recursive shape) and `extra_notes`
   from the teacher's DOCX rubric. Until this lands, teachers must
   manually add sub_criteria via the editor UI. Today the agent will
   only grade meaningfully on rubrics where sub_criteria exists.
2. **V3 pipeline — stop producing stub rules.** Remove the binary stub
   rule machinery once `rules` is gone from the draft side.
3. **Draft-side `rules` removal.** Once V3 stops producing rules and
   the editor UI no longer displays them, remove `rules` /
   `ReductionRule` / `ScoringLevel` / `RuleKind` / `LevelSelectionMode` /
   `ScoringType` from `ontology_types.py`.
4. **Frontend updates for new contract shape.** The editor needs to:
   - Display `sub_criteria` as nested Criterion editing (not the old
     flat dict)
   - Display + edit `extra_notes` per criterion
   - Stop showing `rules` and `scoring_levels`
5. **Frontend updates for new graded preview shape.** The grading UI
   needs to display `CriterionOutcome` with optional recursive
   `sub_criterion_outcomes`.
6. **Student model.** Build a proper `Student` table with teacher FK and
   external_id, backfill from existing `student_name` strings, migrate
   `GradedTest.student_id` to FK.
7. **DOCX v3 pipeline config consistency.** Migrate `EXTRACTION_LLM_PROVIDER`
   / `EXTRACTION_LLM_MODEL` env vars into `settings` for consistency
   with the rest of the codebase.
8. **Deprecate legacy `grade_ontology` and `grade_student_test`
   endpoints.** Once the new pipeline is battle-tested, remove the
   fallback paths.
9. **Remove `RuleOutcome` from `ontology_types.py`.** Once `graded_json`
   column is no longer being written to, drop the legacy outcome types.

---

# FUTURE SPRINTS — AI quality & evaluation (added 2026-06-02)

> **Context.** The S1–S7 redesign built a deterministic harness around a
> stochastic grading core: a pure compiler (S6), a pure validator (S7), and
> a quarantined LLM call between them. The harness is exhaustively unit-tested.
> The *grading judgment itself* — the one non-deterministic component — has no
> quality gate yet. This section specs the missing half: measuring and improving
> grading quality. It is the highest-ROI work remaining, and it is deliberately
> deferred (not forgotten) because building a golden eval set requires real
> teacher-graded tests that don't exist pre-launch.

---

## Sprint E1 — Grading non-determinism: documentation & UX contract

**Status:** documentation/design sprint, no code. Do before any "why did the grade change?" confusion arises.

### The fact to internalize

A `GradedTestDraft` is **not reproducible**. The pipeline pins
`rubric_contract_version` + `transcription_contract_version`, recomputes the
`GradableTest` deterministically, and validates deterministically — but the
grading step calls an LLM at `temperature=0.0`, which is *low-variance, not
zero-variance*. The same `(rubric, transcription)` pair can produce different
grades across runs.

**The determinism boundary, stated precisely:**

| Stage | Deterministic? |
|---|---|
| Rubric contract compile (S6 upstream) | Yes — pure |
| `GradableTest` compile (S6) | Yes — pure function of two pinned contracts |
| Grading (S7 agent / LLM) | **No** — stochastic, even at temp 0 |
| Post-validation (S7 validator) | Yes — pure |
| Contract compile at approval (S9) | Yes — pure |

The non-determinism is isolated to exactly one stage, and that stage's output
is **frozen into an artifact** (`graded_tests.draft_json`) the moment it's
produced. So a given *stored* grade is stable; what's non-reproducible is
*re-running* the grader.

### UX / architecture implications (the contract this imposes)

1. **Re-grade creates a new row, never mutates.** Already locked
   (Phase 0a §3.3, the revision-chain design). This is the *correct* response
   to non-determinism: a re-grade is a new attempt with its own provenance
   (`model_version`, `prompt_version`, contract versions), linked via the
   revision chain. Never overwrite a grade in place — you'd destroy the audit
   trail and surprise the teacher.
2. **The teacher's edits are the source of truth, not the AI grade.** The
   `teacher_overrides` overlay (Phase 0a) means the *approved* grade is
   deterministic and human-owned even though the *AI draft* underneath it
   isn't. The UI must make clear: the AI produced a draft; the teacher's
   approval is what's authoritative.
3. **Never show "the grade" as if it were canonical before approval.** The
   draft UI should frame AI outcomes as *suggestions to review*, surfaced
   lowest-confidence-first (using `ScopeOutcome.min_confidence` from S7), not
   as a settled result. Reproducibility-sensitive language ("the grade is X")
   belongs only post-approval.
4. **Provenance is displayable.** Every draft carries
   `model_version` + `prompt_version` + the two contract versions. The UI
   should be able to show "graded by {model}/{prompt} against rubric {v}" so a
   teacher (or a future support conversation) can reason about why two attempts
   differ.

### Deliverable

A short design doc (`docs/architecture/grading_nondeterminism.md`) stating the
boundary table above, the four implications, and the explicit UX rule:
**AI grades are reviewable drafts, not reproducible verdicts; the teacher's
approved contract is the authoritative, stable artifact.** No code; this exists
so the frontend (S8+ review UI) and any future "regrade" feature are designed
around the fact rather than tripping over it.

---

## Sprint E2 — Grading eval suite (golden set + agreement metrics + regression gate)

**Status:** the keystone AI-quality sprint. **Blocked on data** — needs a set
of real student tests graded by a trusted teacher. Build the moment that data
exists (target: shortly after first real usage, when the first cohort of
teacher-graded tests is available). Until then, S8+ ships with an explicit
"grades are unverified" posture.

### Why this is the highest-ROI remaining work

Everything built so far verifies that the grader's *plumbing* is correct
(closed-world holds, bounds clamp, quotes validate, failures isolate). Nothing
yet measures whether the grader *grades correctly*. That is the actual product.
Without this sprint you cannot:
- safely change the prompt (every tweak is a blind change),
- safely change or downgrade the model (no regression signal),
- tell a teacher how much to trust the AI draft,
- know whether `confidence` means anything.

This sprint closes the feedback loop. It converts "I built a grader" into "I
built a grader I can *improve* with evidence."

### Deliverable 1 — the golden set

A versioned dataset of `(rubric_contract, transcription_contract) → teacher_grade`
triples. Requirements:
- **Real data.** Actual student tests, actual rubrics, graded by a teacher whose
  judgment is the ground truth. Not synthetic.
- **Coverage of the hard cases**, not just easy ones: partial credit, ambiguous
  answers, sub-question-bearing questions, branch criteria (sub_criteria),
  empty/missing answers, answers that are correct-but-unconventional
  (`allow_multiple_valid_forms`), and answers where the *evidence* is subtle.
- **Stored as fixtures**, version-controlled, with the teacher's per-terminal
  points as the gold label. Start small (10–20 tests is enough to be useful);
  grow over time.
- **Provenance captured:** which teacher, when, against which rubric version.
- **PII posture:** these are real student answers — store them in a access-controlled location, scrub names, treat as sensitive. Decide retention explicitly.

### Deliverable 2 — agreement metrics

A harness that runs the grader over the golden set and reports, against the
teacher's gold labels:
- **Points MAE** — mean absolute error in points, at the terminal-criterion
  level and aggregated to scope and whole-test. The headline number.
- **Within-precision rate** — % of terminals where the agent's award is within
  `numeric_policy.precision` of the teacher's.
- **Exact-match rate** — % of terminals graded identically.
- **Direction bias** — does the agent systematically over- or under-grade?
  (A grader that's wrong but *consistently lenient* is a different problem than
  one that's randomly wrong.)
- **Per-cohort breakdowns** — by question type, by branch-vs-leaf criteria, by
  answer-present-vs-missing, by `allow_multiple_valid_forms`. Reveals *where*
  the grader is weak, not just that it is.
- **Confidence calibration** — bucket terminals by the agent's self-reported
  `confidence` and plot actual agreement per bucket. Answers "does low
  confidence actually predict disagreement with the teacher?" This is what
  tells us whether `confidence` is trustworthy enough to drive the review queue
  and the E3 verification trigger.
- **Evidence quality (manual-assisted)** — sample N graded terminals and have a
  human check: does the cited quote actually *justify* the points awarded?
  This catches the failure the deterministic quote-validator cannot — a real
  quote that's irrelevant to the criterion. Can't be fully automated; sample
  and track a rate.

### Deliverable 3 — regression gate & prompt-iteration loop

- A repeatable command that runs the eval and emits a scorecard, keyed by
  `(model_version, prompt_version)` so results are attributable (this is *why*
  S7 stamps `prompt_version` into the draft).
- A **baseline scorecard** committed to the repo; prompt/model changes are run
  against the golden set and compared to baseline **before merge**. A change
  that regresses points MAE or within-precision rate beyond a threshold is
  rejected or requires explicit sign-off.
- This makes prompt engineering *empirical*: change the prompt → run the eval →
  see the delta → keep or revert. No more vibes-based prompt edits.

### Deliverable 4 — eval as a development tool

The eval harness should be runnable locally against a single test for fast
prompt iteration (grade one golden test, diff against gold, inspect the
reasoning), and in batch for a full scorecard. The single-test mode is the
inner loop of prompt development.

### Acceptance criteria
- Golden set exists, versioned, covering the hard cases, with gold labels.
- The harness produces the agreement metrics above, attributable to
  `(model_version, prompt_version)`.
- A committed baseline scorecard.
- A documented regression-gate procedure for prompt/model changes.
- Confidence calibration is measured (informs E3).

---

## Sprint E3 — Confidence-triggered verification pass

**Status:** depends on E2 (needs the confidence-calibration data to set the
threshold defensibly). Builds on S7's per-terminal `confidence`.

### The idea

S7 produces a self-assessed `confidence` per terminal but uses it only to order
the review queue — it never acts on it, because raw LLM confidence is weakly
calibrated until E2 measures it. E3 turns confidence into action: **terminals
whose confidence falls below a calibrated benchmark trigger a second LLM
verification call** whose sole job is to validate-or-fix that specific grade and
its evidence quote.

### Design

- **Trigger:** after the first-pass grade, any terminal with
  `confidence < CONFIDENCE_VERIFICATION_THRESHOLD` (a constant set from E2's
  calibration data — the confidence level below which agreement-with-teacher
  drops materially) is queued for verification.
- **The verification call is narrow and adversarial:** it receives the single
  terminal — criterion text, the student answer, the first-pass grade, the
  first-pass reasoning, and the cited quote — and is asked: *is this grade
  justified by this evidence? If not, correct the points and/or the quote, and
  explain.* It's a focused second opinion on one terminal, not a re-grade of the
  scope.
- **Surgical, like the S7 retry:** per-terminal, not per-scope or per-test. Only
  low-confidence terminals incur the second call, so cost scales with
  uncertainty, not test size. A confident grade costs one call; an uncertain one
  costs two.
- **Outcome handling:**
  - Verifier agrees → keep the first-pass grade, mark it `verified`, raise
    effective confidence.
  - Verifier corrects → replace the grade/quote with the verified one, record
    *both* (the first-pass and the verified) in the outcome for auditability,
    annotate that a verification correction occurred.
  - Verifier itself low-confidence or disagrees-without-clear-fix → flag for
    teacher review with both opinions surfaced. Never loop a third time
    (bounded, like GA-3's spirit).
- **Cost/quality tradeoff is measurable:** E2's harness re-runs with E3 enabled
  and reports the agreement-improvement vs. the added-cost. E3 ships only if the
  eval shows it actually improves agreement enough to justify the extra calls —
  otherwise the threshold is tuned or E3 is shelved. **E3 is a hypothesis to be
  validated by E2's metrics, not an assumed win.**

### Why gate it on E2

Setting the threshold without calibration data is guessing. If low confidence
doesn't actually predict teacher-disagreement (E2's calibration curve is flat),
then E3 fires verification calls on the wrong terminals and wastes money for no
quality gain. E2 tells us whether confidence is a usable trigger and where to
set the line. Build E3 only after E2 proves confidence is informative.

### Acceptance criteria
- Threshold derived from E2's calibration data, not hand-picked.
- Verification is per-terminal, bounded (one second pass, no loops).
- Corrections preserve both opinions for audit; teacher-review fallback on
  unresolved disagreement.
- E2 harness quantifies agreement-gain vs. added-cost; E3 ships only if the
  tradeoff is favorable.

---

## Cost instrumentation (note — implemented in S8, not here)

Per-test / per-question / per-criterion cost capture (token counts × model
pricing) is part of **S8's scope** (where the agent is wired into the live
`/grade` flow and real calls happen). Listed here only so the eval sprints can
*consume* that cost data: E2's regression scorecard and E3's cost/quality
tradeoff both read the cost-per-grade that S8 records. The instrumentation
itself lands in S8.
