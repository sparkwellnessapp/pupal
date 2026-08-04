# PR: S8 — Grading endpoint, draft persistence, read endpoints, cost capture, draft-review UI

**Sprint:** S8
**Depends on:** S4 (`/grade` phase 1), S5 (side-by-side layout), S6 (compiler), S7 (agent) — all merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §3.2 (graded_test lifecycle), §8 (GradableTest in-memory); `phase_0e_dfd.md` §2 (the end-to-end flow this sprint completes)
**Frontend lockstep:** yes — replaces the S4 post-submit placeholder with the grading-progress → draft-review flow

---

## 1. Summary

S8 connects the grading half of the pipeline to the request flow. It extends `/grade` into its second phase: after the pending `graded_tests` row is created (S4), grading runs **asynchronously** (FastAPI `BackgroundTasks`), compiling the `GradableTest` (S6), running the `GraderAgent` (S7), persisting the `GradedTestDraft`, and advancing the row `pending → grading → draft` (or `→ failed`). It rebuilds the two 501-stubbed read endpoints, adds **per-scope cost/token capture** (which requires a small change to the S7 agent's LLM call site), and builds the **read-mostly draft-review screen** reusing S5's side-by-side layout.

After S8, the full loop works end-to-end: upload → transcribe → review-against-source → submit → **grade runs → teacher reviews the AI draft**. The `teacher_overrides` *editing* and approval are S9; S8's review screen displays the draft, its flags, and its annotations, ordered to surface the least-confident scopes first.

**S8 does NOT:** edit `teacher_overrides` (S9), compile the `GradedTestContract` / approve (S9), or build re-grade/manual-edit (S10). It produces and displays the AI draft; it does not finalize grades.

---

## 2. Key decisions (locked)

| # | Decision | Choice |
|---|---|---|
| D1 | Sync vs async grading | **Async via FastAPI `BackgroundTasks`.** `/grade` returns immediately (row already `pending` from S4); a background task runs the agent and advances the row. Frontend polls. Introduces `BackgroundTasks` (no prior precedent — §4.3 documents its limits). |
| D2 | The `grading → draft` advance + failure | **S8 owns the full advance**, including a `failed` terminal state if grading throws catastrophically (distinct from S7's per-scope degradation — §4.4). |
| D3 | Status polling | **Reuse `GET /graded_test/{id}`.** It returns `status`; when `status=='draft'` it returns the full draft. No separate status route. |
| D4 | Cost granularity | **Per-scope** (one LLM call = one scope, so per-scope is the measurable unit). Per-test aggregate stored on the row. No per-criterion isolation (would contradict GA-1). Requires capturing token usage at the agent call site (§5). |
| D5 | Review screen scope | **Read-mostly.** Display the draft, flags, annotations, confidence-ordered. `teacher_overrides` editing → S9. |

---

## 3. Scope

### In scope
- Extend `/grade`: fire async grading after the pending-row commit (§4).
- The background grading task: compile → grade → persist → advance row, with `failed` handling (§4).
- Agent change: capture per-scope token usage (§5) — a scoped modification to S7's call site.
- Migration 009: token/cost columns on `graded_tests` (§6).
- Row-level aggregates: `total_score`/`total_possible`/`percentage` + cost (§4.5, §6).
- Rebuild `GET /graded_tests` and `GET /graded_test/{id}` (§7).
- Frontend: grading-progress (poll) → draft-review screen, reusing S5's side-by-side layout (§8).
- Tests (§9).

### Out of scope
- `teacher_overrides` editing, the approval gate, `GradedTestContract` compilation — **S9**.
- Re-grade / manual-edit flows — **S10**.
- A durable job queue (Celery/RQ). `BackgroundTasks` is the deliberate pre-launch choice (§4.3); the seam is clean to swap later.
- SSE/push for completion — polling is sufficient pre-launch (OD7 deferred).
- Per-criterion cost isolation (D4).

---

## 4. Extending `/grade` — async grading

### 4.1 The plug-in point

S4's `/grade` ends with `await db.commit()` / `await db.refresh(graded_test)` and returns `GradeQueuedResponse`. S8 inserts, **after the commit**, the scheduling of a background grading task keyed by `graded_test.id`. The endpoint still returns immediately — the response shape is unchanged (`{ graded_test_id }`); the row is `pending` when the response is sent.

```python
@router.post("/grade", response_model=GradeQueuedResponse)
async def grade(body, background_tasks: BackgroundTasks, db, current_user):
    # ... S4 logic: validate, write transcription contract, INSERT pending row, commit ...
    await db.commit()
    await db.refresh(graded_test)
    background_tasks.add_task(run_grading, graded_test_id=graded_test.id)   # NEW
    return GradeQueuedResponse(graded_test_id=str(graded_test.id))
```

### 4.2 The background grading task

A new function `run_grading(graded_test_id: UUID)` in a new service module (e.g. `app/services/grading_runner.py`). It owns its **own DB session** (the request's session is closed by the time it runs — background tasks run after the response). Flow:

1. Open a fresh `AsyncSession`.
2. Load the `graded_tests` row by id. If not `pending`, abort (idempotency guard — §4.6).
3. Advance `status = 'grading'`, set a `grading_started_at` (use `draft_created_at`? no — see §6; add a column or reuse). Commit this transition so a poller sees `grading`.
4. Load the transcription's `contract_json` → `TranscriptionContract.model_validate(...)` and the rubric's `contract_json` → `GradingRubricContract.model_validate(...)`.
5. `compile()` the `GradableTest` (S6).
6. `await GraderAgent().grade(gradable_test)` (S7) → `GradedTestDraft`.
7. Persist: `draft_json = draft.model_dump(mode="json")`, `draft_created_at = now`, compute and set the row aggregates (§4.5) and cost columns (§6), `model_version`, `prompt_version` (now on the draft — store on the row too for queryability, or read from draft_json), `llm_calls_count`, `grading_duration_ms`.
8. Advance `status = 'draft'`. Commit.

**`model_dump(mode="json")` not `model_dump()`** — the draft has `Decimal` fields; plain `model_dump()` leaves `Decimal` objects that break JSONB serialization. (This is the latent risk flagged repeatedly across prior sprints — get it right here.)

### 4.3 `BackgroundTasks` — limits, documented

`BackgroundTasks` runs in the same process after the response is sent. Its limits, accepted for pre-launch:
- **Not durable.** If the process restarts mid-grade (deploy, crash, Cloud Run scale-down), the task is lost and the row is stranded in `grading`. Mitigated by §4.6 (a stuck-row recovery path) and acceptable with no real users.
- **No retry/backoff at the task level.** S7's per-scope retry handles transient LLM blips; a whole-task failure goes to `failed` (§4.4), and the teacher can re-grade (S10) or the row can be re-driven.
- **Shares process resources.** Concurrent grades compete for the same event loop. Pre-launch volume makes this a non-issue; at scale this is the trigger to move to a real queue.

The seam is `background_tasks.add_task(run_grading, ...)`. Swapping to Celery/RQ later means changing only that line and the worker entry point — `run_grading` itself is queue-agnostic. **Write `run_grading` so it has no dependency on FastAPI request context** — it takes an id and builds everything it needs. That's what keeps the swap cheap.

### 4.4 The `failed` terminal state

S7's agent isolates *per-scope* failures (a failed scope → flagged zero-outcome, the grade survives). S8 handles *whole-grade catastrophic* failure — the agent throws, contract validation fails, the DB is unreachable mid-task, etc. On any unhandled exception in `run_grading`:
- Set `status = 'failed'`, `error_message` = a concise diagnostic (exception class + message — NOT a full traceback with PII).
- Commit. Do not leave the row in `grading`.
- Log loudly (structured: graded_test_id, exception class, where in the flow).

`failed` is terminal for this row; recovery is a re-grade (S10) or operator action. The frontend shows a failure state with a retry affordance (the retry itself is S10; S8's UI just surfaces that it failed).

### 4.5 Row-level aggregates

From the `GradedTestDraft`, compute and store on the row (all `Decimal` → `Numeric`):
- `total_possible` = Σ `scope_outcome.points_possible` across scopes.
- `total_score` = Σ `scope_outcome.points_awarded`.
- `percentage` = `total_score / total_possible * 100` (guard divide-by-zero → 0 or NULL if `total_possible == 0`).

These are denormalized for fast listing (the `GET /graded_tests` list shouldn't parse every draft JSON to show a score). They are the *AI draft* totals; S9 recomputes them post-override at approval.

### 4.6 Idempotency & stuck-row recovery

- **Idempotency:** `run_grading` re-checks `status == 'pending'` (or `'grading'` for a resumed run) before proceeding, and aborts if the row is already `draft`/`approved`. Prevents double-grading if the task somehow fires twice.
- **Stuck rows:** a row stranded in `grading` (process died mid-task) is detectable (status `grading` + a stale `grading_started_at`). S8 doesn't need an automatic sweeper pre-launch, but: document the recovery (an operator can reset such a row to `pending` and re-fire, or it becomes a re-grade in S10). Flag the stranding risk; don't build the sweeper now.

---

## 5. Token/cost capture — the agent call-site change

**This is the one place S8 modifies merged S7 code, and it must be surgical.**

The problem (research Q5): S7 calls `self._structured_llm.ainvoke(...)` where `_structured_llm = llm.with_structured_output(QuestionGradingResponse)`. The structured-output wrapper returns the parsed Pydantic object directly and **strips the `AIMessage` that carries `.usage_metadata`** — so token counts are invisible to the caller. `llm_calls_count` today is just a count of grade-path scopes, not tokens.

**The fix:** switch the agent's call site to a form of `with_structured_output` that preserves usage metadata, then thread per-scope token usage up into the result. LangChain supports `include_raw=True`:

```python
structured = llm.with_structured_output(QuestionGradingResponse, include_raw=True)
result = await structured.ainvoke([...])
# result is now {"raw": AIMessage(...), "parsed": QuestionGradingResponse(...), "parsing_error": ...}
parsed = result["parsed"]
usage = result["raw"].usage_metadata    # {input_tokens, output_tokens, total_tokens}
```

Scope of the change (keep it minimal):
- `_grade_scope` (or wherever the LLM call lives) uses `include_raw=True`, extracts `parsed` for grading and `usage_metadata` for accounting.
- Handle `parsing_error` (with `include_raw=True`, a parse failure no longer raises — it populates `parsing_error`; treat a non-None `parsing_error` as the failure path, consistent with S7's existing failure handling, and do NOT retry it per GA-3 — it's a content/parse failure, not transient).
- Carry per-scope `input_tokens`/`output_tokens` onto the `ScopeOutcome` (add two optional fields) or into a parallel per-scope usage list returned from the agent. **Recommendation: add `input_tokens`/`output_tokens` to `ScopeOutcome`** (observability data, belongs with the scope; small; persists into draft_json for later analysis). Skipped/failed scopes → 0/0.
- The agent sums per-scope usage into draft-level totals.

**Watch the `include_raw=True` behavior change:** it changes the return shape (dict, not the bare model) AND it changes failure semantics (parse errors surface in `parsing_error` instead of raising). S7's existing tests that mock `ainvoke` to return a bare `QuestionGradingResponse` or to raise **will need updating** to the new dict shape. Update them; this is expected churn from the call-site change. Re-run S7's full test suite after the change — all 20 must still pass (adapted).

**Cost computation:** a pricing constant (e.g. `GRADING_MODEL_PRICING = {"input_per_1k": ..., "output_per_1k": ...}` in config or a constants module) converts tokens → dollars. Store `total_input_tokens`, `total_output_tokens`, and computed `total_cost_usd` on the row (§6). Per-scope tokens live in the draft; the row carries the test-level aggregate for fast listing/reporting.

If `include_raw=True` proves to misbehave with the installed LangChain version (the metadata isn't populated, or the dict shape differs), **flag it** — the fallback is to drop to the raw `llm.ainvoke` with a manual JSON-schema response format and parse + extract usage by hand, but try `include_raw=True` first (it's the documented, lowest-churn path).

---

## 6. Migration 009 — token/cost columns

`backend/migrations/009_s8_graded_test_cost_columns.sql`. Add to `graded_tests`:
- `total_input_tokens` INTEGER NULL
- `total_output_tokens` INTEGER NULL
- `total_cost_usd` NUMERIC(10,4) NULL
- `grading_started_at` TIMESTAMPTZ NULL — set when the row enters `grading` (supports stuck-row detection §4.6 and grading-duration measurement)

Update the `GradedTest` ORM model to match. All nullable (existing rows / pending rows have no cost yet). Per-scope token counts live inside `draft_json` (on each `ScopeOutcome`), not as columns — only the test-level aggregate is columnar (for fast listing without parsing JSON).

`prompt_version`: it's already on the draft (S7). Optionally add a `prompt_version` column too if you want to query/filter grades by prompt version (useful for the future eval suite). **Recommendation: add it** — `prompt_version VARCHAR(50) NULL` — cheap, and the eval sprint (E2) will want to slice by it without parsing JSON.

---

## 7. The read endpoints

Rebuild both in `grading.py` (replace the 501 stubs). Auth + ownership per the S2 pattern (`get_owned_or_404`).

### `GET /graded_test/{id}`
- `get_owned_or_404` on the row.
- Response depends on `status`:
  - `pending` / `grading` → status-only response (`{ id, status, ... }`) — this is what the frontend polls.
  - `draft` → full draft response: the `GradedTestDraft` (from `draft_json`) + row aggregates (score/possible/percentage) + the denormalized fields (student_name, filename) + cost (optional in the response; useful for an admin view).
  - `failed` → status + `error_message`.
  - `approved` → the contract (S9 territory; for S8, an approved row can return its draft + a note, or defer — but since S8 doesn't produce approved rows, just handle it gracefully).
- This single endpoint is the poll target (D3) AND the draft fetch. One endpoint, status-driven response.

### `GET /graded_tests`
- List the current user's graded tests (scoped by `user_id`).
- Return list-summary shape: `id`, `student_name`, `filename`, `status`, `total_score`, `total_possible`, `percentage`, `created_at` — the denormalized row columns, NOT the full draft JSON (fast listing).
- Optional filters (nice-to-have, not required): by `status`, by `student_id`, by `rubric_id`.
- Order by `created_at` desc (most recent first) — confirm against the frontend's needs.

Response schemas in `app/schemas/` — a `GradedTestListItem` and a `GradedTestDetailResponse` (status-driven). Keep the list item lean.

---

## 8. Frontend — grading progress → draft review

### 8.1 Replace the post-submit placeholder
S4's `grading_queued` step (the static "המבחן נשלח לבדיקה" confirmation) is replaced by a **polling progress state**:
- After `submitGrade` returns `{ graded_test_id }`, transition to a "grading in progress" view.
- **Poll `GET /graded_test/{id}`** every ~2–3s. While `status ∈ {pending, grading}`, show progress (a spinner + "הבדיקה מתבצעת..."; if `grading`, optionally "בודק..."). 
- On `status == 'draft'` → transition to the draft-review screen (§8.2).
- On `status == 'failed'` → show a failure state with the `error_message` and a "try again" affordance (the actual re-grade is S10; for S8, "try again" can route back to re-submit or just surface the failure clearly).
- Cap polling (e.g. stop after N minutes → show "this is taking longer than expected" with a manual refresh). Don't poll forever.

### 8.2 The draft-review screen (read-mostly)
Reuse S5's side-by-side layout (`TranscriptionReviewPanel`'s two-pane structure — answers/source on wide, tab-toggle on mobile). The graded draft-review mirrors it:
- **Outcomes pane:** per scope, show the criteria with `points_awarded / points_possible`, the AI `reasoning` (Hebrew), the evidence quote (with its validation status — exact/fuzzy/not-found styling), and any flags/annotations. For branch criteria, show the sub-criterion outcomes nested.
- **Source pane:** the original PDF page(s) (reuse S5's `getTranscriptionPage` proxy + `PageThumbnail`), so the teacher can verify the AI's grade against the handwriting — same value proposition as transcription review.
- **Confidence ordering:** surface the least-confident scopes first (or visually flag low `min_confidence` scopes), so the teacher's attention goes where the AI is least sure (per S7 §5.1 — confidence is a review-triage signal). This is the read-time payoff of the confidence work.
- **Totals:** show `total_score / total_possible` and percentage prominently.
- **Annotations:** surface `error`/`warning`/`info` annotations near their `target_id`; `error`-severity ones get prominent treatment (they'll block approval in S9).
- **READ-MOSTLY:** no editing of points/comments in S8. Display only. An "approve"/"edit" affordance can be present but stubbed/disabled with a note that it's coming (S9), OR omitted — your call; don't build the editing.

### 8.3 API client + types
- `getGradedTest(id)` → status-driven detail (already partially exists? confirm; add/update).
- `listGradedTests(filters?)` → list items.
- The `/my-graded-tests` route (exists in nav per S3 research) wires to `listGradedTests`; clicking a row opens the draft-review (or, for non-draft rows, the appropriate status view).
- TypeScript types mirroring §7's response shapes.

---

## 9. Testing

### Backend — grading runner
1. **Happy path (mocked agent):** a `pending` row → `run_grading` → row becomes `draft` with `draft_json` populated, aggregates computed (`total_score`/`total_possible`/`percentage`), `grading_started_at` set. Mock `GraderAgent.grade` to return a canned draft (don't call the LLM).
2. **Status transitions visible:** assert the row passes through `grading` before `draft` (commit the `grading` transition).
3. **Failed path:** mock `GraderAgent.grade` to raise → row becomes `failed` with `error_message`, not stranded in `grading`.
4. **Idempotency:** `run_grading` on an already-`draft` row aborts without re-grading.
5. **Aggregates correct:** `total_score == Σ scope.points_awarded`, `total_possible == Σ scope.points_possible`, percentage correct; divide-by-zero guarded.
6. **Decimal JSONB:** the persisted `draft_json` round-trips (`model_validate(row.draft_json)` works — proves `model_dump(mode="json")` was used).

### Backend — cost capture (agent change)
7. **Token capture:** with a mocked `include_raw=True` response carrying `usage_metadata`, per-scope `input_tokens`/`output_tokens` are captured and summed to the row's `total_input_tokens`/`total_output_tokens`; `total_cost_usd` computed from the pricing constant.
8. **Parse-error path:** a mocked `parsing_error` (non-None) is treated as the scope failure path, NOT retried (GA-3), and doesn't crash the grade.
9. **S7 regression:** all 20 S7 tests pass after the call-site change (adapted to the `include_raw=True` dict shape).

### Backend — read endpoints
10. **Auth + ownership:** 401 without token; 404 for another user's row; list scoped to current user.
11. **Status-driven detail:** `pending`/`grading` → status-only; `draft` → full draft + aggregates; `failed` → status + error_message.
12. **List shape:** returns lean summary items (no full draft JSON), ordered by recency.

### Frontend
- Post-submit polls the detail endpoint; transitions to draft-review on `draft`, failure state on `failed`.
- Draft-review renders outcomes + source pane (S5 layout), confidence-ordered, totals shown; no editing controls active.

Tests 3 (failed path), 6 (Decimal JSONB), and 9 (S7 regression after the agent change) are the ones most likely to catch real bugs.

---

## 10. Acceptance criteria

- [ ] `/grade` fires async grading via `BackgroundTasks` after the pending-row commit; response unchanged, returns immediately.
- [ ] `run_grading` is request-context-free (takes an id, owns its session); compile → grade → persist → advance.
- [ ] Row advances `pending → grading → draft`; `grading` transition is committed (pollable).
- [ ] Catastrophic failure → `status='failed'` + `error_message`; never stranded in `grading`; idempotency guard present.
- [ ] `draft_json` persisted via `model_dump(mode="json")`; round-trips.
- [ ] Row aggregates (`total_score`/`total_possible`/`percentage`) computed and stored; divide-by-zero guarded.
- [ ] Agent captures per-scope token usage via `include_raw=True`; `parsing_error` handled as failure (no retry); per-scope tokens on `ScopeOutcome`, summed to row; `total_cost_usd` computed.
- [ ] All 20 S7 tests pass after the call-site change (adapted).
- [ ] Migration 009 adds token/cost + `grading_started_at` (+ optional `prompt_version`) columns; ORM updated.
- [ ] Both read endpoints rebuilt: auth + ownership, status-driven detail, lean list.
- [ ] Frontend: polling progress → draft-review (S5 side-by-side), confidence-ordered, totals, annotations; **no override editing** (S9).
- [ ] `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 11. Known follow-ups (do NOT do in this PR)

- **S9** — approval: `teacher_overrides` editing in the review screen, the approval gate (reads S7's `error`-severity annotations), `GradedTestContract` compilation, row → `approved`. The S8 review screen's read-only outcomes become editable here.
- **S10** — re-grade-stale + manual-edit flows (the revision chain). The `failed`-row "try again" affordance gets its real implementation here.
- **Durable job queue** — when volume warrants, swap `BackgroundTasks` for Celery/RQ; `run_grading` is already queue-agnostic.
- **Stuck-row sweeper** — automatic recovery of rows stranded in `grading` by a process restart. Documented (§4.6), not built.
- **Eval suite (E2)** — consumes the cost data and `prompt_version` this sprint records.

If `include_raw=True` doesn't surface `usage_metadata` cleanly in the installed LangChain version (§5), or if `BackgroundTasks` interacts badly with the async session lifecycle (§4.2 — the task must own its own session, not borrow the request's), **stop and flag** rather than working around it silently. The session-ownership point is the most likely place for a subtle bug: a background task that captures the request's `db` session will fail because that session is closed once the response is sent.
