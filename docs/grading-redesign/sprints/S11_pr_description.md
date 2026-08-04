# PR: S11 — Batch grading (fan-out) + triaged batch transcription review

**Sprint:** S11
**Depends on:** S4 (`/transcribe`), S8 (`run_grading`, polling), S9 (approval), S10 (revision) — merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §2.2.C (Batch), §3.1 (transcription lifecycle), §10.2 (transcription annotations as triage signal); `phase_0e_dfd.md` §7.2 (batch is the same per-test pipeline with `batch_id` set)
**Frontend lockstep:** yes — batch upload + the batch transcription-review screen (functional, not final-polished; polish → S13)

---

## 1. Summary

S11 turns the single-test pipeline into a batch pipeline **without duplicating it** — a batch is M tests, each flowing through the exact S4→S10 machinery with `batch_id` set. The mechanical fan-out is easy (S8's `run_grading` is already a per-id background task). The hard part — and the focus of this PR — is the **human review gate under batch**: 30 tests must not become 60 sequential review sessions.

The design (Model A-minus, locked):
- **Two batched gates preserved** (transcription-review → grade-review), because grading must consume a *teacher-approved* transcription contract (the architecture's core invariant — a mis-transcribed answer grades wrong no matter how good the grader).
- **Transcription review is triaged:** clean transcriptions (no flags, confident student match) are bulk-acceptable in one action; only flagged ones demand individual attention. This collapses the tedium while keeping every transcription contract teacher-approved.
- **Student auto-matching:** the VLM's `student_name_suggestion` is matched against the batch's class roster, pre-filling the student so the teacher confirms rather than picks.

The triage is only as good as the **flagging accuracy** underneath it. A chunk of this PR (§5) upgrades the transcription service's confidence/flagging so that clean transcriptions are correctly *not* flagged (so bulk-accept is safe) and bad ones are correctly flagged (so they don't slip into grading). That accuracy work is what makes the triage trustworthy rather than theater.

**S11 does NOT:** build the polished batch grade-review dashboard (S13, UX-interview-gated — S11 ships a functional grade-review, reusing S9's per-test panel + a basic roll-up), or bulk approval (deferred until eval-validated).

---

## 2. Decisions (locked)

| # | Decision | Choice |
|---|---|---|
| D1 | Gate model | **Model A-minus:** two batched gates; transcription review triaged (bulk-accept clean, individually handle flagged). Preserves "grading consumes an approved transcription contract." Requires the §5 flagging-accuracy work. |
| D2 | Student assignment | **Auto-match `student_name_suggestion` against the batch's class roster; teacher confirms.** Uncertain matches fall to manual pick (`StudentPicker`). |
| D3 | Batch ↔ class | **Class is OPTIONAL.** A batch may be tied to a class (enables roster auto-match). First-time teachers have no classes/students yet → a class-less batch falls back to the whole student set / manual pick, and student creation inline. Build the class-selection in endpoint + UI. |
| D4 | Frontend scope | **Batch transcription-review frontend IS in S11** (functional, not final). Grade-review dashboard polish → S13. |
| D5 | Lifecycle | **Eager:** uploading PDFs to a batch fans out transcription immediately; roll-up status reflects progress. |

---

## 3. Scope

### In scope
- Batch endpoints: create batch (optional class) + upload PDFs → eager fan-out transcription; batch detail/roll-up; batch list (§6).
- Bounded fan-out for both transcription and grading (a batch-level concurrency cap — §4.3, the research-flagged cascade risk).
- Triaged batch transcription review: per-test flag triage + student auto-match + bulk-accept-clean + individual-handle-flagged → batch submit-to-grade (§7).
- **Transcription flagging-accuracy upgrade** (§5) — logprob-based span confidence + the existing grounding check, tuned for high flag precision/recall.
- Batch grading fan-out (reuse `run_grading`) + roll-up status (§8).
- Frontend: multi-file batch upload, batch transcription-review screen, batch progress + basic grade roll-up (§9).
- Migration 011 if needed for batch-progress fields (§6.4).
- Tests (§10).

### Out of scope
- Polished batch grade-review dashboard — **S13** (UX interview first).
- Bulk **approval** of grades — deferred until eval-validated high unedited-approval rate.
- Self-consistency multi-sampling / cross-model verification for transcription (§5 considers and *defers* these as too costly for now — logprobs + grounding are the S11 mechanism).
- Fuzzy Hebrew name matching beyond normalized exact match (§7.2 — uncertain → manual).

---

## 4. Backend — fan-out architecture

### 4.1 Batch transcription fan-out (eager, on upload)

A new batch-transcribe path. On `POST /batches` (create) + PDF upload, for each PDF: run the **same transcription work** S4's `/transcribe` does (VLM → GCS upload → build draft → INSERT `transcriptions` row), but with `batch_id` set on the row and **fanned out in the background** rather than blocking the request.

Extract S4's transcription body into a reusable `transcribe_one(pdf_bytes, filename, rubric_id, user_id, batch_id) -> transcription_id` service function (research confirms `/transcribe` is loop-safe and self-contained — each call owns its session, commits independently). The batch endpoint fires M of these as bounded background tasks (§4.3). The single-test `/transcribe` endpoint is refactored to call the same `transcribe_one` (no behavior change for single-test — just shared code).

### 4.2 Batch grading fan-out

When the teacher submits the reviewed batch to grade (§7), for each test: the same `/grade` phase-1 work (write transcription contract + insert pending `graded_tests` row with `batch_id`) then fire `run_grading(graded_test_id)` — the S8 path verbatim. M grades fan out (bounded, §4.3).

### 4.3 Bounded concurrency (the research-flagged cascade)

**Critical:** research flagged that firing 30 `run_grading` tasks at once → up to 30 × MAX_CONCURRENT_SCOPES(5) = 150 concurrent OpenAI calls, with no app-level throttle (only the OpenAI rate limiter and the asyncpg pool as backstops). Same risk for batch transcription (M concurrent VLM calls). Unbounded, this trips rate limits and exhausts the connection pool.

**Add a batch-level concurrency cap.** Two viable shapes:
- A module-level `asyncio.Semaphore(BATCH_MAX_CONCURRENT_TESTS)` (e.g. 5–8) that each per-test coroutine acquires before its VLM/grading work, OR
- A simple worker-queue fan-out: a bounded pool of N workers drains a queue of test-ids.

**Recommendation: the semaphore** — simpler, matches the GraderAgent's existing intra-test semaphore pattern, no new queue infra. Set `BATCH_MAX_CONCURRENT_TESTS` conservatively (start 5) as a config constant. This bounds *both* the transcription fan-out and the grading fan-out. Note the nesting: batch-cap(5) × grader-scope-cap(5) = 25 worst-case concurrent LLM calls — acceptable, bounded, tunable.

**`BackgroundTasks` durability caveat (carried from S8):** background tasks die on process restart. For a batch of 30, a mid-batch restart strands the in-flight and not-yet-started tests. Pre-launch acceptable, but the roll-up status (§8) must make stranded tests *visible* (a test stuck in `pending`/`grading` past a timeout), and the per-test retry (S10) is the manual recovery. Do not build a durable queue now; do make stranding visible. (This is the trigger, when volume grows, to move to a real queue — `transcribe_one` and `run_grading` are already queue-agnostic.)

---

## 5. Transcription flagging accuracy (the foundation of the triage)

Model A-minus's bulk-accept is only safe if flagging is accurate: **clean transcriptions must not be flagged (or bulk-accept is useless), and bad ones must be flagged (or errors slip silently into grading).** The dangerous case is the **false negative** — a confidently-wrong transcription. Research on black-box VLM error detection (the model can't be probed internally — it's the OpenAI API) gives a clear, cost-ordered signal set. S11 implements the cheap, high-value layers and defers the expensive ones.

### 5.1 The signals, and what S11 uses

| Signal | Cost | S11 |
|---|---|---|
| **Token logprobs** — low per-token logprob localizes uncertain spans (single forward pass; OpenAI `logprobs:true` is supported on gpt-4o chat completions, confirmed) | ~free (one call) | **USE** — primary new signal |
| **Grounding cross-check** — the service's existing `_verify_consistency` against `visual_grounding` (→ `needed_grounding_retry`, S4) | already paid | **USE** — already wired; surface it as a flag |
| `[?]` illegible markers in the answer text (S4) | free | **USE** — already wired |
| VLM self-reported `confidence` per answer (S4) | free | **USE** — already wired |
| Missing `student_name_suggestion` (S4) | free | **USE** — already wired (drives student triage) |
| **Self-consistency** — sample each page 2–3× at temp>0, flag disagreement | N× calls | **DEFER** — too costly per page at batch scale; also has mode-collapse blind spot (a confidently-wrong model reproduces the same error, evading consistency) |
| **Cross-model verification** — a second model verifies | 2× calls + 2nd model | **DEFER** — the eval-suite (E3) confidence-triggered verification is the right home for this, gated on calibration data |

### 5.2 The logprob upgrade (the one new mechanism)

The transcription service currently discards logprobs (research: `with_structured_output`-style call returns only parsed content). S11 adds a logprob-based span-confidence signal:

- **Request logprobs** on the VLM transcription call (`logprobs: true`). (If the current call path can't surface them — e.g. a structured-output wrapper strips them, as it did for the grader in S8 — switch to the raw call + manual parse, mirroring S8's `include_raw=True` fix. Flag if the path fights it.)
- **Compute a low-confidence span signal** per answer: aggregate token logprobs over the answer's tokens; identify the **lowest-confidence span** (a sliding-window min over token logprobs — the research's "Lowest Span Confidence" idea, which localizes uncertainty better than a whole-answer average). An answer whose lowest span falls below a threshold gets a `vlm_low_logprob` annotation.
- **Why span-min, not mean:** a single garbled word in an otherwise-confident answer is exactly the dangerous case (one wrong variable name flips a grade); a mean washes it out, a span-min surfaces it. This matches the research finding that uncertainty is *localized*.

### 5.3 Flag aggregation → the triage verdict

Per transcription, compute a **review-needed** verdict from the signals: a transcription is **flagged-for-review** if ANY of:
- has a `vlm_unparseable` (`[?]`) annotation,
- `needed_grounding_retry` is true,
- any answer's VLM `confidence` < threshold,
- any answer's lowest-logprob-span < threshold (new),
- `student_name_suggestion` is missing or didn't confidently match the roster (§7.2).

Otherwise it's **clean** (bulk-acceptable). Expose this verdict (a boolean + the contributing reasons) on the batch transcription-review payload (§7) so the UI can triage. Make the thresholds **named config constants** (tunable; the eval suite will later calibrate them against real teacher corrections — that's the E2 connection).

### 5.4 Honest scope note

S11 implements the *cheap, single-call* signals (logprobs + the already-present grounding/marker/confidence signals) and the aggregation. It does **not** implement multi-sample self-consistency or cross-model verification — those are deferred to the eval-gated E3 work, where calibration data justifies the cost. The §5 goal is "materially better flag precision/recall than S4's confidence-only flagging, at ~zero added cost," not "optimal." The thresholds are guesses until E2 calibrates them against real teacher corrections — the PR should say so, and make them trivially tunable.

---

## 6. Backend — batch endpoints

New router `app/api/v0/batch_grading.py` (the slate is blank — research confirms no batch endpoints survive). Auth + ownership throughout (S2 pattern).

### 6.1 `POST /batches` — create + upload (eager)
- **Body:** multipart — multiple PDF `files[]` + `rubric_id` + optional `class_id` + optional `name`.
- Validate rubric owned + compiled; if `class_id` given, validate class owned.
- Create `grading_batches` row: `status='in_progress'`, `started_at=now`, `rubric_contract_version = rubric.contract_version` (pinned), `class_id` (nullable), `name`.
- For each PDF: fire `transcribe_one(..., batch_id=batch.id)` as a bounded background task (§4.3).
- Return `{ batch_id, test_count }` immediately. The frontend polls the batch detail for transcription progress.

### 6.2 `GET /batches/{id}` — detail + roll-up
- `get_owned_or_404`. Returns the batch + a **roll-up** over its `graded_tests` and `transcriptions`: counts by state (transcribing, transcribed, awaiting-review, grading, draft, approved, failed), and the per-test list with enough for the review/dashboard (test id, filename, student_name/suggestion, the §5.3 flag verdict + reasons, status).
- This is the poll target for both the transcription-review phase and the grading phase.

### 6.3 `GET /batches` — list
- Scoped to user; summary rows (id, name, class, status, counts, created_at).

### 6.4 Migration 011 (if needed)
The `grading_batches` schema exists (research). Likely sufficient as-is. **Only** add a migration if a batch-progress field is genuinely missing (e.g. a denormalized `test_count`). Prefer computing roll-up counts at query time (join over `graded_tests`/`transcriptions` by `batch_id`) — consistent with the "derive counts, don't store" principle (Phase 0a §2.2.C). Likely **no migration needed**; confirm and skip if so.

### 6.5 Batch status roll-up semantics
`grading_batches.status` (CHECK: pending|in_progress|completed|partially_completed|failed). Compute/advance:
- `in_progress` while any test is mid-pipeline.
- `completed` when all tests reached `approved`.
- `partially_completed` when all tests are terminal but some `failed` (or some abandoned).
- `failed` only if the batch itself couldn't start.
Recompute on transitions (or derive at read time — simpler, no write-back races). **Recommendation: derive at read time** from the child counts; only persist `started_at`/`completed_at` milestones. Avoids the stuck-status problem `BackgroundTasks` could otherwise cause.

---

## 7. Batch transcription review (the gate — Model A-minus)

This is the UX heart of S11. The teacher has uploaded a batch; transcription has fanned out; now they review **efficiently**.

### 7.1 The triaged review flow
The batch transcription-review screen (after transcription completes) shows the M tests **split by the §5.3 verdict**:
- **Clean tests** (no flags, confident student match): collapsed/summarized, **bulk-acceptable**. A "accept all clean (N)" action approves their transcription contracts in one go — each still goes through the real contract-write (it's a genuine teacher approval, just batched), assigning the auto-matched student.
- **Flagged tests:** surfaced individually for attention, each showing *why* it's flagged (the §5.3 reasons) and the side-by-side transcription/source (reuse S5's panel) so the teacher can correct the transcription and/or fix the student assignment before accepting.

This preserves the invariant (every transcription contract is teacher-approved) while making the common case (clean) one action — the whole point of A-minus.

### 7.2 Student auto-matching (D2)
For each transcription, match `student_name_suggestion` against the **batch's class roster** (if `class_id` set; else the teacher's full student set):
- **Confident match** (normalized exact match — trim/casefold/Hebrew-niqqud-strip; NOT fuzzy): pre-fill the student; the test counts as "confident student match" for triage.
- **No/ambiguous match:** the test is flagged; the teacher picks via the existing `StudentPicker` (reusable as-is per research, supports inline create — important for first-time teachers with an empty roster, D3).
- Keep matching **conservative** — a wrong auto-match silently mis-attributes a grade, worse than asking. Normalized-exact only; anything uncertain → manual. (Fuzzy Hebrew matching is explicitly out of scope; revisit if the manual rate is high.)

### 7.3 Submit batch to grade
Once all transcriptions are accepted (clean bulk + flagged individually), a **"grade batch"** action submits: for each test, write the transcription contract + assign student + insert pending `graded_tests` (the S4 `/grade` phase-1, per test) + fire `run_grading` (bounded, §4.3). Transition to the grading-progress view.

### 7.4 Class-less batches (D3)
If the batch has no `class_id` (first-time teacher): no roster to auto-match against → all student assignments are manual (`StudentPicker` with inline create). The triage still works on the transcription-quality signals; only the student-match dimension degrades to manual. The flow must be fully usable with zero pre-existing students/classes.

---

## 8. Batch grading + roll-up

After submit (§7.3), grades fan out (bounded). The batch detail (§6.2) roll-up shows progress. For S11, the **grade review** is functional-not-polished (D4):
- The batch detail page lists tests with their grading status + score; clicking a `draft` test opens the **existing S9 `GradedTestReviewPanel`** (per-test review/edit/approve — already built). 
- A basic roll-up (N approved / N draft / N grading / N failed) and per-test rows.
- The *polished* batch grade-review dashboard (bulk views, batch-level confidence ordering, etc.) is **S13** after the UX interview. S11 just wires the functional path: see the batch, open each draft, approve via S9.

No bulk grade-approval (deferred). Each grade is approved through the existing per-test S9 flow.

---

## 9. Frontend

### 9.1 Batch upload
Extend the existing upload (research: `MultiFileUpload` already accepts ≤50 PDFs; the current flow just processes one at a time). Add a "grade as batch" path: select rubric → **optionally select a class** (dropdown of the teacher's classes, with a clear "no class / first time" option, D3) → select multiple PDFs → `POST /batches`. Transition to batch-transcription-progress (poll `GET /batches/{id}`).

### 9.2 Batch transcription-review screen (functional, D4)
The triaged review (§7): clean tests bulk-acceptable, flagged tests individual with reasons + S5 side-by-side + `StudentPicker`. Auto-matched students pre-filled. "Accept all clean" + per-flagged-test accept → "grade batch" submit. **Functional over polished** — the UX refinement is S13, but it must be genuinely usable (the triage must work, bulk-accept must work, student assignment must work).

### 9.3 Batch grading progress + functional review
Poll batch detail; show roll-up; per-test rows; click a draft → S9 panel. Failed tests show the S10 retry.

### 9.4 API client + types
`createBatch(files, rubricId, classId?)`, `getBatch(id)`, `listBatches()`, `acceptCleanTranscriptions(batchId, testIds)` / `acceptTranscription(...)`, `submitBatchToGrade(batchId)`. Types for the batch detail/roll-up + per-test flag verdict.

---

## 10. Testing

### Backend
1. **Fan-out creates rows** — `POST /batches` with 3 PDFs (mocked VLM) → 3 `transcriptions` rows with `batch_id` set; batch `in_progress`.
2. **Bounded concurrency** — the semaphore caps concurrent transcription/grading coroutines at `BATCH_MAX_CONCURRENT_TESTS` (assert no more than N run simultaneously — e.g. via a counting mock).
3. **`transcribe_one` shared** — single-test `/transcribe` and batch both call it; single-test behavior unchanged (regression).
4. **Flag verdict** — a transcription with `[?]` / low confidence / low logprob span / grounding-retry / missing student → flagged with correct reasons; a clean one → not flagged. (Mock VLM outputs to construct each case.)
5. **Logprob span signal** — a mocked low-logprob span → `vlm_low_logprob` annotation; a confident one → none. (The §5.2 mechanism.)
6. **Student auto-match** — exact-normalized suggestion matches a roster student → pre-filled; no match → flagged-for-manual; class-less batch → all manual.
7. **Bulk-accept clean** — accepting N clean tests writes N transcription contracts + assigns auto-matched students + inserts N pending graded_tests; each is a real contract write.
8. **Submit to grade** — fires `run_grading` per test (mocked); graded_tests advance.
9. **Roll-up** — batch detail counts reflect child states; derived at read time; `partially_completed` when some failed.
10. **Class optional** — a batch with no `class_id` works end-to-end; ownership (404 cross-user) on batch + class.

### Frontend
- Batch upload with/without class; multi-file.
- Transcription review: clean bulk-accept, flagged individual with reasons + student picker; auto-matched pre-fill.
- Grading progress + per-test S9 review; failed→retry.

Tests 2 (bounded concurrency), 4 (flag verdict), and 7 (bulk-accept writes real contracts) protect the cascade-safety and the A-minus invariant.

---

## 11. Acceptance criteria

- [ ] `transcribe_one` extracted + shared by single-test `/transcribe` (unchanged behavior) and batch fan-out.
- [ ] `POST /batches` (multi-PDF, optional class) eagerly fans out transcription with `batch_id` set; returns immediately.
- [ ] **Bounded** concurrency cap (`BATCH_MAX_CONCURRENT_TESTS`) on both transcription and grading fan-out; no unthrottled 150-call cascade.
- [ ] Transcription flagging upgraded: logprob span-min signal added (§5.2) + existing signals aggregated into a per-test review-needed verdict (§5.3); thresholds are tunable config constants.
- [ ] Triaged batch transcription review: clean tests bulk-acceptable, flagged tests individual with reasons + S5 side-by-side + student picker; every accepted transcription is a real teacher-approved contract write (A-minus invariant).
- [ ] Student auto-match against the batch's class roster (normalized-exact, conservative); class-less batches fall back to manual + inline create (D3).
- [ ] Batch grading fan-out reuses `run_grading`; roll-up status derived at read time; stranded tests visible.
- [ ] Functional grade review: batch detail → per-test S9 panel; no bulk approval.
- [ ] Frontend: batch upload (optional class), functional triaged transcription review, batch progress + per-test review.
- [ ] Migration 011 only if a field is genuinely missing (likely none).
- [ ] All tests pass; tests 2/4/7 explicitly verified; `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 12. Known follow-ups (do NOT do in this PR)

- **S13** — polished batch grade-review dashboard (UX-interview-gated). S11 ships the functional path; S13 designs the real review UX (bulk views, batch confidence ordering, navigation).
- **Bulk grade-approval** — deferred until the eval suite validates a high unedited-approval rate (per the roadmap note). S11 approves grades one-by-one via S9.
- **Self-consistency / cross-model transcription verification** (§5.4) — deferred to the eval-gated E3 work; logprobs + grounding are the S11 mechanism.
- **Threshold calibration** — the §5.3 flag thresholds are guesses until E2 calibrates them against real teacher corrections; they're config constants so calibration is a config change, not a code change.
- **Durable job queue** — when batch volume grows, swap `BackgroundTasks` for a real queue (`transcribe_one`/`run_grading` are queue-agnostic).
- **Fuzzy Hebrew name matching** — if the manual-student-assignment rate is high, revisit (S11 is normalized-exact only).

If the VLM call path can't surface logprobs cleanly (§5.2) or if `BackgroundTasks` + the bounded semaphore interact badly with the async session lifecycle, **flag it** rather than working around it. And if firing the batch fan-out from within the request (even bounded) proves to block or exhaust the pool, the fallback is a single coordinator background task that drains the batch sequentially-with-bounded-parallelism — flag and discuss before improvising.
