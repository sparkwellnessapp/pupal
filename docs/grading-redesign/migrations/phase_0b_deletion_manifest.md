# Vivi — Phase 0b: Deletion Manifest

**Owner:** Noam
**Status:** LOCKED — derived from Phase 0a architecture
**Locked at:** 2026-05-24
**Scope:** Enumerates every file, function, table, column, and endpoint that is deleted or moved to `/deprecated/` as part of Sprint S0.

---

## 0. How to read this document

Each entry has:
- **Path / identifier** — what to act on
- **Action** — `DELETE` (gone forever) or `MOVE TO /deprecated/` (kept read-only for reference)
- **Rationale** — why
- **Evidence** — which Q-number from the codebase research surfaced this, plus any cross-reference to the architecture lock

**Action definitions:**

- **DELETE** — Hard-remove. No backup, no archive. Reference value is zero (the code is either fully superseded by new architecture, or is dead and has been confirmed unreferenced).
- **MOVE TO /deprecated/** — Move file to a top-level `deprecated/` directory. Add a header comment: `# DEPRECATED — replaced by <new path>. Kept for reference. NEVER import from live code.` These files are valuable as reference (prompts, retry heuristics, edge-case handling worth borrowing from) but are NOT live. CI must enforce: no live code imports anything from `deprecated/`.

**Sprint S0 acceptance criteria** (referenced from Phase 0a §13):
1. Every entry in this manifest is acted upon.
2. CI passes (delete operations don't leave broken imports; moves are isolated).
3. No new code in the same PR (the cleanup is a single concern).
4. A short PR description that lists each section below and the count of items handled, for reviewability.

---

## 1. Backend — Tables and columns

Handles entirely by Noam (owner). You can skip to section 2. 

## 2. Backend — Application code

### 2.1 The deprecated LangGraph TestGraderAgent

The entire `app/agents/test_grader/` tree is the old per-criterion ReAct agent. It is replaced by a new single-call agent introduced in S7. The old code has reference value: its prompt templates, its retry logic, and its quote-validation heuristics are worth borrowing from when building the new agent.

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `app/agents/test_grader/` (entire directory) | MOVE TO `deprecated/agents/test_grader/` | The new GraderAgent (S7) builds from scratch; LangGraph state machine + per-criterion ReAct retries are not the new architecture. Prompts and validation logic worth keeping as reference. | Q25, Q26, Phase 0a §2.1.B |
| `app/agents/test_grader/state.py` | (moved with directory) | `GradingAgentState` TypedDict has no analog in the new agent. | Q25 |
| `app/agents/test_grader/graph.py` | (moved with directory) | LangGraph topology. | Q25, Q26 |
| `app/agents/test_grader/nodes/` (all) | (moved with directory) | Per-node implementations; the new agent has no node graph. | Q26 |
| `app/agents/test_grader/persistence.py` | (moved with directory) | `state_snapshot` / `graded_test_draft_json` serialization. Replaced by direct draft_json writes on `graded_tests`. | Q3, Q4 |

**MUST**: After moving, verify no live code imports from `app/agents/test_grader/`. Search for `from app.agents.test_grader` and `from app.agents import test_grader`; both must return zero matches in non-deprecated code.

### 2.2 Legacy grading services

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `app/services/grading_service.py` | MOVE TO `deprecated/services/grading_service.py` | Contains `save_graded_test()` (legacy writer with two-commit pattern), `grade_student_test()` (the legacy non-agent grading function), `sanitize_for_json()` (legacy serializer). All superseded by the new persistence and the new agent. Some prompt-construction logic for legacy grading worth keeping as reference. | Q7, Q43, Q26 (`grade_student_test` is the "legacy GradingAgent" mentioned in userMemories) |
| `app/services/grading_router.py` | DELETE | Routes between legacy and ontology grading paths. With one new endpoint replacing all of them, the router has no purpose. | Q9, Q34 (this file is one of the writers to `grading_sessions.llm_calls_count`) |
| `app/services/ontology_grading_service.py` | MOVE TO `deprecated/services/ontology_grading_service.py` | Contains `DraftValidator.validate()` (post-LLM closed-world check, currently non-blocking). The new architecture enforces closed-world by construction at GradableTest compile time, plus a hard re-check at approval (CW-3). The validation logic itself is referenceable but does not survive as a runtime concept. | Q35, Phase 0a §5.3 |

### 2.3 Legacy / superseded endpoints

| Endpoint | Path | Action | Rationale | Evidence |
|---|---|---|---|---|
| `POST /grade_tests` | `app/api/v0/grading.py` | DELETE | Legacy batch path that takes PDFs + page-mapping JSON. Replaced by the new `/transcribe` + `/grade` two-step flow. | Q23 #1 |
| `POST /grade_handwritten_test` | `app/api/v0/grading.py` | DELETE | Single-file handwriting path that transcribes-and-grades in one call. Replaced by the explicit two-step flow which gives the teacher review-before-grade. | Q23 #2 |
| `POST /transcribe_handwritten_test` | `app/api/v0/grading.py` | DELETE | Replaced by new `POST /transcribe` which persists the transcription draft to the `transcriptions` table. | Q23 #3, Q18 |
| `POST /grade_with_transcription` | `app/api/v0/grading.py` | DELETE | Replaced by new `POST /grade` which writes the contract side of the transcription and creates the graded_test row. | Q23 #4, Q18 |
| `POST /grade_ontology` | `app/api/v0/grading.py` | DELETE | The ontology agent endpoint. Replaced by `POST /grade`. | Q23 #5 |
| `POST /grade_ontology_batch` | `app/api/v0/batch_grading.py` | DELETE | Replaced by new batch endpoint (S8) that writes directly to `graded_tests` with `batch_id`. | Q23 #6 |
| `GET /batches/{batch_id}/progress` | `app/api/v0/batch_grading.py` | DELETE | Replaced by new progress endpoint that derives counts from `graded_tests GROUP BY status`. | Q23 #7 |
| `POST /annotate_pdf` | `app/api/v0/grading.py` | DELETE | A 501 stub. The annotation feature is deferred to a future PR; the stub adds nothing today. | Q41 |
| `GET /graded_pdfs` | `app/api/v0/grading.py` | DELETE | 501 stub. Same as above. | Q41 |

After deleting endpoints, the `app/api/v0/grading.py` and `app/api/v0/batch_grading.py` files become much smaller. Whatever remains (the `GET /graded_tests` and `GET /graded_test/{id}` list/detail endpoints) stays in place; those are touched in S8 to use the new schema but are not deleted.

### 2.4 Schemas / Pydantic models

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `app/schemas/grading.py` — `GradeItemSchema` | DELETE | Legacy graded-item shape. Replaced by `CriterionOutcome` (existing) in the new draft. | Q1 |
| `app/schemas/grading.py` — `GradedTestSchema` | DELETE | Legacy whole-test shape. Replaced by `GradedTestDraft` (existing) and `GradedTestContract` (new — Phase 0c). | Q1 |
| `app/schemas/grading.py` — `ParsedStudentAnswer` | DELETE | Legacy student-answer shape that's redundant with `TranscribedAnswerWithPages`. The new architecture uses `StudentAnswer` types inside `TranscriptionContract`. | Q2 |
| `app/schemas/grading.py` — `ParsedStudentTest` | DELETE | Same as above. | Q2 |
| `app/schemas/grading.py` — `TranscribedAnswerWithPages` | KEEP (will be renamed and become the building block of `TranscriptionDraft` in S4) | — | Q15 |
| `app/schemas/grading.py` — `TranscriptionReviewResponse` | KEEP (will be replaced by a thinner API-layer response in S4; the type itself moves) | — | Q16 |
| `app/schemas/grading.py` — `StudentAnswerInput` | DELETE | Replaced by inputs to the new `POST /grade` endpoint built in S4/S8. | Q18 |
| `app/schemas/grading.py` — `GradeWithTranscriptionRequest` | DELETE | Replaced by new `POST /grade` request type. | Q18 |
| `app/schemas/ontology_types.py` — `RuleOutcome` override-tracking fields | MODIFY (not deleted) | Per Phase 0a §2.1.C and §10.4, teacher overrides are a separate `TeacherOverride` overlay, not fields on `RuleOutcome`/`CriterionOutcome`. Remove `was_overridden`, `original_level_id`, `override_reason` from the model. | Q30, Q37 |
| `app/schemas/ontology_types.py` — everything else | KEEP | Contracts, criteria, sub_criteria, outcomes, claims, quotations — all stay as the foundation. The new types added in Phase 0c extend this file. | Q5, Q29, Q30, Q31, Q32 |

### 2.5 ORM Models

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `app/models/raw_graded_test.py` (the file) | DELETE | The phantom table is being dropped. | Q7 |
| `app/models/grading.py` — `RawGradedTest` class | DELETE | Same. | Q7 |
| `app/models/grading.py` — `GradedTestPdf` class | DELETE | Phantom table dropped. | Q41 |
| `app/models/grading.py` — `GradingSession` class | DELETE | Table dropped. | Q9 |
| `app/models/grading.py` — `GradedTest` class | MODIFY (in S1) | Restructured per Phase 0a §4. | — |
| `app/models/grading.py` — `GradingBatch` class | MODIFY (in S1) | Slimmed per §1.2 above. | — |
| `app/models/grading.py` — `Rubric` class | MODIFY (drop columns per §1.2) | — | — |

### 2.6 Helper functions and serializers

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `app/services/grading_service.py` — `sanitize_for_json()` | (moves with file to deprecated/) | Legacy permissive serializer. The new path uses Pydantic `model_dump()` directly. | Q43 |
| `app/agents/test_grader/persistence.py` — `serialize_value()` | (moves with directory) | Same. The new path uses Pydantic directly; if Decimal/datetime serialization is needed, it's handled by Pydantic `@field_serializer`. | Q43 |
| `app/agents/test_grader/persistence.py` — `serialize_state()` | (moves with directory) | Same. | Q43 |

---

## 3. Backend — Tests

### 3.1 Tests that are already broken

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `tests/test_ontology_integration.py` | MOVE TO `deprecated/tests/test_ontology_integration.py` | Currently broken — imports `ReductionRule`, `RuleKind`, `ScoringLevel` which are deleted types. The test scenarios (INV enforcement end-to-end) are worth referencing when writing new integration tests in S6/S7. | Q45 |
| `tests/agents/test_grader/test_competency_questions.py` | MOVE TO `deprecated/tests/agents/test_grader/test_competency_questions.py` | Broken — uses old rule-based types. The CQ-1 through CQ-8 test cases (rule eval, quote validation, closed-world, batch consistency, latency) are valuable reference for writing new agent tests in S7. | Q45 |
| `tests/agents/test_grader/__init__.py` | DELETE | Empty fixture init for a module being moved. | Q45 |
| `tests/agents/__init__.py` | DELETE | Empty package marker for a module being moved. | Q45 |

### 3.2 Deprecated DOCX pipeline tests

These test the OLD 8-layer DOCX extraction pipeline, replaced ~6 months ago by the V3 pipeline. They're already deprecated; this PR just makes the deprecation explicit by moving them out of `tests/`.

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `tests/services/docx/` (entire directory) | MOVE TO `deprecated/tests/services/docx/` | Tests for the deprecated DOCX pipeline. | Q45 |

---

## 4. Frontend — Code

### 4.1 Frontend types

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `frontend/src/lib/api.ts` — inline `GradedTestResult` type | DELETE | Untyped inline type that mirrors the legacy `graded_json` shape. Replaced by typed `GradedTestDraft` / `GradedTestContract` from `ontology-types.ts`. | Q46 (mirror map) |
| `frontend/src/lib/ontology-types.ts` — override fields on `RuleOutcome` | DELETE | Mirror the backend change in §2.4: `was_overridden`, `original_level_id`, `override_reason` removed. | Q46 |

### 4.2 Frontend API client methods

| Method | File | Action | Rationale | Evidence |
|---|---|---|---|---|
| `gradeTests(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/grade_tests` which is being deleted. | Q24 (line 726) |
| `gradeHandwrittenTest(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/grade_handwritten_test`. | Q24 (line 795) |
| `transcribeHandwrittenTest(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/transcribe_handwritten_test`. Replaced by new `transcribe()` (S4). | Q24 (line ~?) |
| `gradeWithTranscription(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/grade_with_transcription`. Replaced by new `grade()` (S8). | Q24 (line 969) |
| `gradeOntology(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/grade_ontology`. | Q24 (line 1614) |
| `gradeOntologyBatch(...)` | `frontend/src/lib/api.ts` | DELETE | Hits `/grade_ontology_batch`. | Q24 (line 1647) |

After this pass, `api.ts` retains: rubric management, transcription/grading methods that get rebuilt in S4/S8, user/auth methods. The grading-method block will be empty until S4 starts adding back the new shape.

### 4.3 Frontend components that depend on deleted APIs

| Path | Action | Rationale | Evidence |
|---|---|---|---|
| `frontend/src/components/BatchDashboard.tsx` | KEEP (refactored in S8) | The dashboard concept survives. The polling endpoint changes; the component re-points to the new endpoint. No move/delete needed in S0. | Q39 |
| Any component that calls the deleted API methods | MODIFY (in respective sprints S4/S8) | After S0, calls to deleted methods will be compile errors in the frontend (TypeScript). The S0 cleanup PR's frontend half stops at "ensure no compile errors after deletion" — which means: temporarily comment out the call sites, or remove the components that depend on them, OR (cleanest) defer the frontend half of S0 to be part of S4 onward, since frontend lockstep is the agreed pattern. | T1 lockstep decision |

**Important — clarification on frontend in S0:**

Per the lockstep frontend decision (T1), the frontend pieces of S0 should NOT ship without their replacement. The pragmatic interpretation:

- S0's backend cleanup ships first as a backend-only PR. Frontend is BROKEN at this point (it calls endpoints that no longer exist).
- The first sprint that touches the frontend (S2 — auth) wires up the new auth flow.
- S4 (transcription Draft/Contract) ships the new `transcribe()` and the new review UI.
- S8 (graded test persistence) ships the new `grade()` and the new draft review UI.
- Between S0 and S4, the production frontend cannot reach the grading flow. **This is acceptable pre-launch.**

If we want zero-downtime even pre-launch, the alternative is to defer S0's API-deletion pass until after S8 ships its replacements. I'd argue: pre-launch, the simplicity of "delete first, rebuild" outweighs the brief broken state. Confirm or override.

---

## 5. Schema / Migration cleanup (handled in S1, not S0)

The migration in S1 will do the SQL-level `DROP TABLE`s and `DROP COLUMN`s enumerated in §1. The Phase 0b cleanup PR (S0) does NOT touch the database — it only handles application code. The DB drops happen as part of migration 007 in S1.

Why split: S0 is "delete dead code" in one PR. S1 is "land the new schema" in another. Reviewing them separately is much easier than reviewing them together.

---

## 6. Summary counts

| Category | DELETE count | MOVE TO /deprecated/ count |
|---|---|---|
| Tables (handled in S1 migration) | 3 | 0 |
| Columns (handled in S1 migration) | 7 | 0 |
| Backend modules | 1 (`grading_router.py`) | 3 (`app/agents/test_grader/` + `grading_service.py` + `ontology_grading_service.py`) |
| Backend endpoints | 9 | 0 |
| Backend Pydantic types | 5 | 0 (one MODIFY for RuleOutcome) |
| Backend ORM classes | 3 | 0 |
| Backend tests | 2 + 1 directory + 2 init files | 2 |
| Frontend types | 2 (one inline, one field set) | 0 |
| Frontend API methods | 6 | 0 |

**Total live-code lines deleted, estimated:** 4,000–6,000 lines of Python + ~300 lines of TypeScript.
**Total moved to `deprecated/`:** ~3,000 lines of Python kept for reference, untouched.

This is a substantial cleanup pass. It is also why S0 ships as its own PR.

---

## 7. Out of scope for the cleanup pass

Things that look like dead code but are NOT deleted in S0:

- **`Rubric.rubric_json` column** — already marked nullable in migration 006, but other columns may reference it. Drop happens in S1, not S0.
- **Existing `rubric_shares` / `rubric_share_history` / `rubric_share_tokens` tables** — kept. They're not in scope for this PR's redesign, and they have working code.
- **`subject_matters` / `user_subject_matters` tables** — kept. Used by class subject tagging (future).
- **The V3 DOCX extraction pipeline** (the live, non-deprecated rubric extraction) — kept. Out of scope.
- **`users` table** — unchanged. Auth code (`app/api/v0/auth.py`) unchanged.

---

## 8. Acceptance check before declaring S0 done

A short script run as part of CI for the S0 PR:

```

# 1. Confirm no live code imports from deprecated/
grep -rn "from app.agents.test_grader" backend/app/  → 0 matches
grep -rn "from app.services.grading_router" backend/app/  → 0 matches
grep -rn "from app.services.grading_service" backend/app/  → 0 matches (or only in deprecated/)
grep -rn "from app.services.ontology_grading_service" backend/app/  → 0 matches (or only in deprecated/)

# 2. Confirm Python imports compile
cd backend && python -c "import app.main"  → exit 0

# 3. Confirm tests collect (passing not required; deprecated tests won't run)
cd backend && pytest --collect-only  → exit 0
```

If all four pass, S0 is mergeable. If any fail, the cleanup is incomplete.

---
