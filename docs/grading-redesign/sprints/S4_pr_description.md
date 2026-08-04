# PR: S4 — Transcription Draft/Contract + `/transcribe` and `/grade`

**Sprint:** S4
**Depends on:** S1 (ORM models), S2 (auth pattern), S3 (students/classes + `StudentPicker` component) — all merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §2.1.A (Transcription artifact), §3.1 (transcription lifecycle), §10.2 (transcription annotations); `phase_0c_target_ddl.md` §4 (transcriptions schema); `phase_0e_dfd.md` §2 (end-to-end flow)
**Frontend lockstep:** yes — ships the transcription review screen and wires in the S3 `StudentPicker`

---

## 1. Summary

S4 makes the pipeline come alive. It builds:
- **Two minimal modifications** to `handwriting_transcription_service.py` (page attribution + retry flagging — both pre-approved, §4).
- **The transcription Pydantic schemas** (`TranscriptionDraft`, `TranscriptionContract`) that serialize into the `transcriptions` JSONB columns.
- **`POST /transcribe`** — uploads the PDF, runs the VLM service, builds and persists a `TranscriptionDraft`, returns it for review.
- **`POST /grade`** — writes the teacher-approved `TranscriptionContract`, assigns the student, and creates the pending `graded_tests` row. **Does not invoke a grading agent** (that's S6/S7/S8).
- **The transcription review UI** — displays the draft, lets the teacher edit answers, surfaces annotations, and uses the S3 `StudentPicker` for student selection.

After S4, a teacher can: upload a PDF → review the transcription → correct it → select the student → submit. The submitted test lands as a `graded_tests` row in `status='pending'`. It stays pending until S8 builds the grading trigger — that's expected and correct (the row is genuinely pending; grading just isn't built yet).

---

## 2. Sequencing note — read this first (the S4/S5 boundary)

The original plan put "PDF persistence to GCS" in S5. But there's a hard constraint that forces the **write** side into S4:

`transcriptions.gcs_uri`, `gcs_bucket`, and `gcs_object_path` are all **NOT NULL** (migration 008, `phase_0c_target_ddl.md` §4). `POST /transcribe` inserts the `transcriptions` row. Therefore `/transcribe` **must** upload the PDF to GCS and have the URI in hand before the insert — there is no way to insert the row otherwise without making the columns nullable (which contradicts the shipped schema and the architecture's intent).

**Resolution (flag for confirmation): split GCS work across S4 and S5 by read/write side.**
- **S4 owns the GCS write:** upload the PDF at `/transcribe` time, store `gcs_uri`/`gcs_bucket`/`gcs_object_path` on the row. This is the minimal upload needed to satisfy the schema.
- **S5 is reframed as the GCS read/serve side:** a signed-URL endpoint to fetch the stored PDF, and rendering the original PDF pages alongside the transcription in the review screen (the visual reference the teacher needs to spot VLM errors).

**Consequence for the S4 review screen:** it is **text-only** — transcribed answers + annotations + student picker, but NOT the original PDF pages beside them. The teacher reviews transcription text without the handwriting reference until S5 adds it. This is sufficient to test the pipeline end-to-end; it is a degraded-but-functional review experience that S5 completes.

If you'd rather pull PDF display into S4 (making it one bigger sprint) or handle the NOT NULL differently, say so. Otherwise this PR proceeds with S4 = GCS write + text-only review, S5 = GCS read + visual review.

---

## 3. Scope

### In scope
- Service modifications: `page_numbers` and `needed_grounding_retry` on `TranscribedAnswer` (§4).
- Pydantic schemas: `TranscriptionDraft`, `TranscriptionContract`, nested answer + annotation types (§5).
- The draft adapter: `TranscriptionResult` → `TranscriptionDraft`, including annotation generation (§6).
- `POST /transcribe` (§7): auth, rubric validation, GCS upload, VLM call, draft build, row insert.
- `POST /grade` (§8): auth, transcription + student validation, contract write, student assignment, pending `graded_tests` insert — atomic, no agent.
- Frontend: rebuilt transcription review screen, `StudentPicker` wired in, upload flow, submit flow (§9).
- Tests (§10), with the VLM mocked via provider injection.

### Out of scope (explicitly deferred)
- **Any grading.** No agent, no `GradableTest` compile, no advancing the `graded_tests` row past `'pending'`. S6/S7/S8.
- **Serving the PDF back / rendering original pages in review.** S5 (per §2).
- **The `/transcribe` page-thumbnail previews** the old endpoint returned. The original PDF display is S5.
- **Re-transcription.** A given PDF is transcribed once. (Determinism analysis confirms re-transcription would legitimately differ; if ever added, it creates a new `transcriptions` row, never overwrites — per `phase_0a` §3.1. Not built now.)
- **Modifying `graded_tests` read endpoints** (stubbed in S2; rebuilt in S8).

---

## 4. Service modifications (pre-approved, minimal)

Two changes to `app/services/handwriting_transcription_service.py`. Both were analyzed and approved. Keep them surgical — these are the only service changes; everything else lives in the endpoint adapter.

### 4.1 `TranscribedAnswer` — two new fields

```python
@dataclass
class TranscribedAnswer:
    question_number: int
    sub_question_id: Optional[str]
    answer_text: str
    confidence: float = 1.0
    transcription_notes: Optional[str] = None
    page_numbers: List[int] = field(default_factory=list)        # NEW (Decision 1)
    needed_grounding_retry: bool = False                          # NEW (Decision 2)
```

### 4.2 Propagate the retry flag in `_transcribe_page_grounded`

When the consistency check fails and a forced-grounding retry fires (~line 1000), tag the result so the merge can see it:

```python
if result and not self._verify_consistency(result):
    logger.warning(f"  Page {page_number}: Consistency mismatch detected, retrying...")
    result = self._retry_with_forced_grounding(page_b64, page_number, result, question_context)
    if result is not None:
        result["_needed_grounding_retry"] = True   # NEW
```

### 4.3 Populate both fields in `_merge_grounded_results`

In the per-page-part loop (~line 1203), capture the page's retry flag alongside the existing `page`:

```python
needed_retry = result.get("_needed_grounding_retry", False)   # NEW
answers_by_question[key].append({
    "text": answer_text,
    "confidence": confidence,
    "page": page_idx + 1,
    "needed_retry": needed_retry,                              # NEW
})
```

When building each final `TranscribedAnswer` (~line 1218):

```python
page_numbers = sorted({part["page"] for part in answer_parts})          # NEW
needed_grounding_retry = any(part["needed_retry"] for part in answer_parts)  # NEW
final_answers.append(TranscribedAnswer(
    question_number=q_num,
    sub_question_id=sub_id,
    answer_text=combined_text,
    confidence=min_confidence,
    page_numbers=page_numbers,                  # NEW
    needed_grounding_retry=needed_grounding_retry,  # NEW
))
```

**Do not** make any other change to the service. The `_transcribe_with_mappings` legacy path is untouched (S4 never calls it — see §7). `raw_transcription` stays as-is (always None on the live path; S4 doesn't use it).

### 4.4 Recommended (optional) — gate the debug file dumps

The service unconditionally writes PNGs to `debug_handwritten_pages/` and `.txt` files to `debug_vlm_responses/` on every call (D1 in the research). In a deployed endpoint this writes to container storage on every transcription. **Recommended:** gate both behind an env flag (e.g. `TRANSCRIPTION_DEBUG_DUMP`, default off in production). This is optional — flag it, implement if low-cost, skip if it expands the diff meaningfully. Not an acceptance blocker.

---

## 5. Pydantic schemas

New file `app/schemas/transcription.py`. These serialize into the `transcriptions` JSONB columns. Use the project's Decimal/serialization conventions (match `ontology_types.py` style).

### 5.1 Draft side (→ `transcriptions.draft_json`)

```
TranscriptionDraftAnswer:
  question_number: int
  sub_question_id: Optional[str]
  answer_text: str
  confidence: float
  page_numbers: List[int]

TranscriptionAnnotation:
  id: str                     # default uuid4 short
  severity: Literal["error", "warning", "info"]
  target_id: str              # "transcription" (whole) or "q{n}" / "q{n}.{sub}"
  annotation_type: str        # "vlm_uncertainty" | "vlm_unparseable" | "student_name_missing"
  message: str                # Hebrew, user-facing
  metadata: Dict[str, Any] = {}

TranscriptionDraft:
  schema_version: str = "1.0"
  student_name_suggestion: Optional[str]   # VLM guess — a hint, NOT authoritative
  page_count: int
  answers: List[TranscriptionDraftAnswer]
  annotations: List[TranscriptionAnnotation]
  model_version: Optional[str]             # the VLM model used
  transcription_duration_ms: Optional[int]
```

### 5.2 Contract side (→ `transcriptions.contract_json`)

```
TranscriptionContractAnswer:
  question_number: int
  sub_question_id: Optional[str]
  answer_text: str            # the teacher-approved final text

TranscriptionContract:
  schema_version: str = "1.0"
  contract_version: str       # fresh UUID at approval (per RD-3 — lives INSIDE the JSONB, no column)
  answers: List[TranscriptionContractAnswer]
```

**Why the contract answer is minimal:** the contract is what the GradableTest compiler (S6) consumes. The grader needs `question_number`, `sub_question_id`, `answer_text` — nothing else. `confidence`, `page_numbers`, and annotations are draft-review concerns and stay out of the contract. Keep it lean; the contract is the grading input, not the review artifact.

**`contract_version` placement:** inside the JSONB, not a column (Phase 0a RD-3). Generate a fresh UUID when the contract is written.

---

## 6. The draft adapter

A pure function, `build_transcription_draft(result: TranscriptionResult, page_count: int, model_version: str, duration_ms: int) -> TranscriptionDraft`. Lives in the endpoint module or a small `app/services/transcription_adapter.py`. This is where the annotation generation lives — the service stays annotation-agnostic; the adapter derives annotations from the service's signals.

### Mapping
- Each `TranscribedAnswer` → `TranscriptionDraftAnswer` (carry `page_numbers` through, per §4).
- `student_name_suggestion` = `result.student_name`.

### Annotation generation (per `phase_0a` §10.2)
For each answer (with `target = "q{question_number}"` + `".{sub_question_id}"` if present):
- **`[?]` markers present in `answer_text`** → `vlm_unparseable`, severity `warning`. Message e.g. `"חלקים מהתשובה לא היו קריאים בתמלול"`.
- **`needed_grounding_retry == True`** → `vlm_uncertainty`, severity `warning`. Message e.g. `"התמלול של שאלה זו דרש אימות נוסף — מומלץ לבדוק מול המקור"`.
- **`confidence < 0.7`** → `vlm_uncertainty`, severity `info`. Message e.g. `"רמת ביטחון נמוכה בתמלול"`. (Threshold 0.7 is a starting value; make it a module constant so it's tunable.)

Whole-transcription scope (`target_id = "transcription"`):
- **`student_name_suggestion` empty/None** → `student_name_missing`, severity `info`. Message e.g. `"לא זוהה שם תלמיד — נא לבחור תלמיד"`. (Low-frequency because the service falls back to a filename-derived name; fine as an info hint.)

None of these are `error` severity — transcription annotations never block submission (the teacher can always submit; they're advisory). This matches `phase_0a` §10.5: only grading-side `error` annotations block, and those come later.

---

## 7. `POST /transcribe`

**Auth:** `Depends(get_current_user)`.

**Input:** multipart — `file` (the PDF) + `rubric_id`.

**Flow:**
1. `get_owned_or_404` on the rubric (must belong to `current_user`).
2. **Validate the rubric is compiled** — `rubric.contract_json IS NOT NULL`. If not → **400** with a clear message (`"המחוון לא עבר קומפילציה — יש להשלים אותו לפני בדיקת מבחנים"`). Rationale: grading will need the compiled contract; fail fast rather than letting the teacher transcribe against an uncompilable rubric and hit a wall at grade time.
3. Read the uploaded PDF bytes.
4. **Transcribe** — call `service.transcribe_pdf(pdf_bytes, filename, rubric_questions=<optional hint>, question_mappings=None)`. **`question_mappings` MUST be None** — passing it routes to the legacy path (B2 in the research). Wrap the sync call: `await run_in_threadpool(service.transcribe_pdf, ...)`. Do this **first** — it's the most failure-prone step; if it fails, nothing is persisted.
   - On VLM API error (propagates from the service, C4) → **502** with a clear message; no GCS upload, no row insert.
   - On PDF parse error (`pdf2image` raises) → **400**; no persistence.
5. **Upload the PDF to GCS** — use the existing `GCSService.upload_bytes`. Object path convention: `transcriptions/{user_id}/{uuid4}.pdf`. Capture `gcs_uri = f"gs://{bucket}/{path}"`, `gcs_bucket`, `gcs_object_path`.
6. **Build the draft** — `build_transcription_draft(result, page_count, model_version, duration_ms)` (§6).
7. **Insert the `transcriptions` row** — `status='transcribed'`, `draft_json = draft.model_dump()`, `contract_json = NULL`, `student_id = NULL`, `gcs_*` set, `user_id = current_user.id`, `rubric_id`, `filename`. (The DB CHECK `transcriptions_approval_consistency` requires NULL contract/student/approved_at in `'transcribed'` status — the insert naturally satisfies this.)
8. **Return** `TranscribeResponse { transcription_id, draft: TranscriptionDraft }`.

**Ordering rationale (transcribe → upload → insert):** the VLM call is slowest and most likely to fail, so it runs before any persistence — a failed transcription leaves nothing behind. A failed GCS upload after a successful transcription returns an error with no row (acceptable). A failed insert after upload leaves an orphaned GCS object (rare, pre-launch-acceptable; a future cleanup job can sweep orphans).

---

## 8. `POST /grade`

This is **phase 1 of `/grade`** — the transcription-approval + pending-row creation. S8 extends it to compile the `GradableTest` and run the agent. S4 stops at `'pending'`.

**Auth:** `Depends(get_current_user)`.

**Input (JSON):**
```
{
  transcription_id: UUID,
  answers: [{ question_number, sub_question_id, answer_text }],   # teacher-edited
  student_id: UUID
}
```

**Flow (one transaction):**
1. `get_owned_or_404` on the transcription. Must be `status='transcribed'` (not already approved) → else **409** (`"התמלול כבר אושר"`).
2. `get_owned_or_404` on the student (must belong to `current_user`).
3. Load the rubric (via the transcription's `rubric_id`) to read its current `contract_version`.
4. Build `TranscriptionContract` from the submitted `answers` (fresh `contract_version` UUID).
5. **UPDATE the transcription:** `contract_json = contract.model_dump()`, `student_id`, `student_name` (denormalized from the student), `status='approved'`, `approved_at = now()`.
6. **INSERT the `graded_tests` row:** `status='pending'`, `transcription_id`, `rubric_id`, `student_id`, `student_name` (denormalized), `filename` (from the transcription), `rubric_contract_version = rubric.contract_version` (pinned now, per VER-2), `regraded_from_id = NULL`, `regraded_to_id = NULL` (this is the chain leaf), `user_id = current_user.id`.
7. Commit. Both writes in one transaction — if either fails, neither applies (IDN-3: every graded_test has an approved transcription).
8. **Return** `GradeQueuedResponse { graded_test_id, status: "pending" }`.

**No agent invocation.** The row sits at `'pending'`. S8 adds the step that advances it. Do not stub a fake grade or auto-advance the status.

**Note on answer validation:** `/grade` stores the teacher's answers as submitted. It does NOT validate that `question_number`s match the rubric — that's the GradableTest compiler's identity-resolution job (S6). Keep `/grade` simple: freeze what the teacher approved.

---

## 9. Critical implementation notes

### Note 1 — `question_mappings=None` is mandatory
Passing `question_mappings` to `transcribe_pdf` routes to the legacy per-question path with a different prompt and no grounding logic (B2). The live grounded path requires `question_mappings=None`. Pass `rubric_questions` only as an optional soft hint (it just adds a hint string to the prompt; harmless, doesn't change the schema).

### Note 2 — wrap the sync service in a threadpool
`transcribe_pdf` is synchronous and uses an internal `ThreadPoolExecutor` (D3). From the async endpoint, call it via `run_in_threadpool` (Starlette/FastAPI helper) so it doesn't block the event loop. Nested executors are fine.

### Note 3 — the draft is immutable; the contract carries the edits
`transcriptions.draft_json` is written once at `/transcribe` and **never updated** (Phase 0a §3.1). The teacher's edits do NOT modify the draft — they flow into `contract_json` at `/grade`. The review UI edits a local copy; submission sends the edited answers to `/grade`, which writes them as the contract. The original VLM output is preserved forever in the draft. This is the audit guarantee — do not write edits back to `draft_json`.

### Note 4 — `student_id` from validated ownership, denormalize `student_name`
The `student_id` comes from the request but MUST be ownership-validated (`get_owned_or_404`) — a teacher cannot assign another teacher's student. `student_name` is denormalized onto both the transcription and the graded_tests row from the validated student record (not from the request).

### Note 5 — the CHECK constraints are your safety net
`transcriptions_approval_consistency` and `graded_tests_status_consistency` (migration 008) will reject malformed state at the DB level. Build the endpoints to satisfy them naturally; if a CHECK fires during testing, that's a signal the endpoint logic is wrong, not that the constraint is wrong.

### Note 6 — VLM provider from config
Per E2, the provider is injectable. The endpoint should construct the service with a provider driven by config (e.g. an env var), not hard-code `"openai"` at the call site. This also makes testing clean (inject a fake provider).

---

## 10. Frontend

Per lockstep. Rebuilds the transcription flow against the new endpoints. RTL Hebrew.

### 10.1 Upload + transcribe
- The existing upload entry point (where the teacher picks a rubric and uploads a PDF) calls the new `transcribe()` API method instead of the deleted `transcribeHandwrittenTest`.
- While `/transcribe` runs (synchronous, can take seconds), show a loading state. (No polling — it's a blocking call, returns the draft when done.)

### 10.2 The transcription review screen
Rebuilt against `TranscribeResponse`. Shows:
- **Editable answers:** one controlled `<textarea>` per answer, keyed by `(question_number, sub_question_id)`, prefilled from the draft. (Same pattern as the old `TranscriptionReviewPage`.)
- **Annotations:** surface the draft's annotations next to the relevant answer (matched by `target_id`), color-coded by severity. Whole-transcription annotations (`target_id="transcription"`) shown at the top.
- **`StudentPicker` (from S3):** wired in here for selecting/creating the student. This is the S3→S4 handoff — the picker built in S3 drops in unmodified.
- **NO original PDF display** — text-only review (per §2; S5 adds the visual reference).

### 10.3 Submit
- Gather the edited answers + selected `student_id`, call `grade()`.
- On success (`{ graded_test_id, status: "pending" }`), navigate to a confirmation / "queued for grading" state. There is no grade to show yet (S8). A simple confirmation ("המבחן נשלח לבדיקה") + navigation back to a list or the upload screen is sufficient. This confirmation is additive, not throwaway — S8 replaces the post-submit destination with the real grading-progress → draft-review flow.
- Surface 409 (transcription already approved) and 400 (rubric not compiled, at the transcribe step) as inline messages.

### 10.4 API client methods
Add to `api.ts` (with `...getAuthHeaders()`):
- `transcribe(rubricId, file)` → `TranscribeResponse`
- `submitGrade({ transcriptionId, answers, studentId })` → `GradeQueuedResponse`

TypeScript types mirroring §5 in `frontend/src/types/transcription.ts`.

---

## 11. Testing

Backend tests in `tests/api/` and `tests/services/`. **The VLM must be mocked** — inject a fake `VLMProvider` that returns canned JSON. No real OpenAI calls in tests.

### Service tests (`tests/services/test_transcription_service.py`)
1. **`page_numbers` populated.** Fake provider returns a 2-page response where Q1 appears on both pages; assert the merged answer's `page_numbers == [1, 2]`.
2. **`needed_grounding_retry` propagated.** Fake provider returns a result that fails `_verify_consistency` on one page; assert the affected answer has `needed_grounding_retry == True` and an unaffected answer has `False`.
3. **Multi-page merge unchanged.** Text joined with `\n`, confidence is the min — verify the §4 changes didn't alter existing merge behavior.

### Adapter tests (`tests/services/test_transcription_adapter.py`)
4. **`[?]` → `vlm_unparseable` annotation** at the right `target_id`.
5. **retry flag → `vlm_uncertainty` annotation.**
6. **low confidence (<0.7) → info annotation.**
7. **missing student name → `student_name_missing` annotation** at `target_id="transcription"`.

### `/transcribe` tests
8. **Auth required** (401 without token).
9. **Rubric ownership** (404 for another user's rubric).
10. **Uncompiled rubric → 400.**
11. **Happy path** (fake VLM): inserts a `transcriptions` row with `status='transcribed'`, `draft_json` populated, `student_id` NULL, GCS fields set (mock the GCS upload), returns the draft.
12. **VLM failure → 502, no row inserted** (fake provider raises).

### `/grade` tests
13. **Auth required.**
14. **Transcription ownership + status** (404 for another user's; 409 if already approved).
15. **Student ownership** (404 / cross-tenant: cannot assign another teacher's student).
16. **Happy path:** transcription → `'approved'` (contract_json, student_id, student_name, approved_at set); a `graded_tests` row inserted with `status='pending'`, correct `rubric_contract_version`, `regraded_to_id` NULL; both in one transaction.
17. **Draft immutability:** after `/grade`, the transcription's `draft_json` is byte-identical to what `/transcribe` wrote (edits went to `contract_json`, not the draft).

Tests 15 (cross-tenant student) and 17 (draft immutability) are the ones that protect core invariants.

### Frontend
- Upload → transcribe → review renders editable answers + annotations + `StudentPicker`.
- Edit + select student + submit → calls `grade()` with the edited answers and `student_id`.
- 400/409 surface as inline messages.

---

## 12. Acceptance criteria

- [ ] `TranscribedAnswer` has `page_numbers` and `needed_grounding_retry`; `_merge_grounded_results` and `_transcribe_page_grounded` populate them; no other service change (except optional §4.4).
- [ ] `TranscriptionDraft` / `TranscriptionContract` schemas exist; contract answer is minimal (no confidence/pages); `contract_version` lives inside the JSONB.
- [ ] The adapter generates the four annotation types per §6; none are `error` severity.
- [ ] `POST /transcribe`: auth, rubric ownership + compiled check, `question_mappings=None`, transcribe→upload→insert ordering, returns the draft. VLM failure → 502 with no row.
- [ ] `POST /grade`: auth, transcription + student ownership, status check, atomic contract-write + pending `graded_tests` insert, correct `rubric_contract_version` pinning, no agent invocation.
- [ ] The draft is never mutated after `/transcribe`; edits flow to the contract.
- [ ] GCS upload uses the existing `GCSService`; object path scoped by `user_id`.
- [ ] Service called via `run_in_threadpool`; VLM provider from config.
- [ ] Frontend: review screen with editable answers, annotations, `StudentPicker` wired in; submit → `/grade` → confirmation. Text-only (no PDF display).
- [ ] All tests pass; VLM mocked throughout; tests 15 and 17 explicitly verified.
- [ ] `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 13. Known follow-ups (do NOT do in this PR)

- **S5** — GCS read/serve side: signed-URL endpoint + render original PDF pages alongside the transcription in the review screen (completes the review experience S4 leaves text-only).
- **S6** — `GradableTest` schema + compiler: consumes the `TranscriptionContract` + `RubricContract`, resolves identity (`question_number` → `question_id`), produces the closed-world agent input.
- **S7** — the GraderAgent.
- **S8** — extends `/grade` to compile the `GradableTest`, run the agent, advance the `graded_tests` row `pending → grading → draft`; rebuilds the stubbed graded-test read endpoints; replaces the S4 post-submit confirmation with the real grading-progress → draft-review flow.

If the existing upload/review frontend structure makes a cleaner integration than §10 describes, flag it — §10 is the intended shape, but established patterns win where they conflict. And if anything in the migrated DB or the service contradicts this spec, **stop and flag** rather than reconciling silently.
