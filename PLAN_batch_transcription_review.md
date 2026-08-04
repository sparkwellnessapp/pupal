# PLAN — Batch Transcription Review: port TranscriptionReviewPage (v0.5) into the batch flow

> Research + implementation plan. No code was written or modified in this pass; this document is the only file created.
> Evidence convention: every factual claim about current behaviour carries `path:Lnn-Lnn`. Claims I could not ground are prefixed `UNVERIFIED —`.
> Paths: `v0.5/…` = `C:\Users\ariel\Desktop\vivi-v0.5\pupal\grader-frontend\…` (and `v0.5-backend/…` = `…\pupal\grader-vision-update\…`); everything else is relative to `vivi-codebase/`.

---

## 1. Problem in Deutsch form

**Observations (the data):**

- **O1 — The batch flow's transcription review is blind.** The live batch surface is `frontend/src/app/batches/[id]/page.tsx` (495 lines). A flagged transcription is reviewed inside an inline `FlaggedTestCard` (`frontend/src/app/batches/[id]/page.tsx:L92-L190`): a StudentPicker (L153) plus bare `<textarea>`s per answer (L148-L186). The file contains **zero** page-image fetches or `<img>` renders (grep for `getTranscriptionPage|thumbnail|<img|data:image` over the file: 0 hits). The teacher cannot see the scanned source while editing the transcription of it.
- **O2 — Clean tests are bulk-approved sight-unseen.** `CleanTestsPanel` (`[id]/page.tsx:L195-L261`) shows `filename → matched_student_name` rows (L240-L242) and an "אשר את כולם" button (L249-L256); the server then builds each contract **from the draft as-is** (`backend/app/api/v0/batch_grading.py:L327-L402`). No transcription content is ever displayed.
- **O3 — Teacher edits have no durable home before approval.** Edits exist only in `FlaggedTestCard` component state (`[id]/page.tsx:L96-L186`) until they ride in on the accept request body. A refresh loses them. On the backend there is **no** endpoint to save transcription edits without approving, and no reopen/unapprove path (verified sweep: the only `save_draft_overrides` targets `graded_test`, `backend/app/api/v0/grading.py:L579-L580`; nothing touches transcriptions).
- **O4 — The mandatory gate says otherwise.** "Transcription gate: the transcription is reviewed **against the source PDF** before grading" (`CLAUDE.md` §2, Mandatory review gates). The single-test flow honors this (`TranscriptionReviewPanel` renders source pages side-by-side, `frontend/src/components/TranscriptionReviewPanel.tsx:L407-L452`); the batch flow does not.
- **O5 — A full-screen side-by-side review page already exists** in v0.5 (`v0.5/src/components/TranscriptionReviewPage.tsx`, 1068 lines) and its UX is what the product wants for the batch per-item view.

**Theory under criticism:** *"S11's triaged batch surface is a sufficient transcription gate: flags route attention, inline cards handle the flagged items, bulk-accept handles the clean ones."* O1–O4 falsify it: the triage routes attention correctly, but the destination cannot perform the review the gate requires. Review-against-source is impossible in the batch flow, so the gate silently degrades to trust-the-flags — exactly the "review-first, not guess" failure `CLAUDE.md` §2 forbids.

**Better conjecture:** Keep the triage as the batch front door (it is shipped, live, and load-bearing — §5 OD-5), and make per-item review a first-class, full-screen, deep-linkable route: the v0.5 page's layout and interaction patterns, rebuilt on the current architecture's plumbing (auth seam, answer-shaped draft, page-image proxy, StudentPicker, persisted per-item save), with prev/next navigation over the batch and a defined seam for the deferred batch-grading trigger.

**Criticism of the conjecture:**
- *Is it hard to vary?* Mostly yes: each load-bearing choice traces to a constraint, not taste — the persisted-edits overlay is forced by LCY-1 + the immutable draft (§6 OD-1); the answer-indexed layout is forced by the artifact shape (§6 OD-3); per-item accept-semantics-for-now is forced by the explicit deferral of the batch trigger (§6 OD-2).
- *New contradictions it introduces:* (a) a second review surface next to `TranscriptionReviewPanel` unless unification lands — addressed head-on in the retirement manifest (§6 OD-7); (b) one new column + migration — justified against the quantified loss-risk of client-only edits (§6 OD-1); (c) it does **not** deliver the desired "grading starts only at שליחה" end state — that is precisely the deferred endpoint, and pretending otherwise would half-implement the kickoff (§6 OD-2).

---

## 2. Access & method

- **v0.5 frontend: full read access confirmed** (`C:\Users\ariel\Desktop\vivi-v0.5\pupal\grader-frontend\src\` listed and read). `TranscriptionReviewPage.tsx` read in full (1068 lines); its `@/lib/api` imports read at the cited ranges.
- **v0.5 backend: present and readable** at `C:\Users\ariel\Desktop\vivi-v0.5\pupal\grader-vision-update\` — so the server the component was written against was read directly, not inferred.
- **The screenshots themselves are on disk** (`…\pupal\transcription-review-fullpage.png`) and I viewed the full-page one. Corrections to §3 of the mission brief, from the source: (1) there is **no syntax highlighting** — the transcription body is a plain monospace `<textarea>` (`v0.5/src/components/TranscriptionReviewPage.tsx:L278-L296`); the colored look is just mono text. (2) The flag hint reads `(העבר עכבר לסיבה)` — hover-for-*reason* (L307), not "לסימנה". (3) "נסרק עם CamScanner" is a watermark **inside the scanned page image**, not a card footer — the component renders no such footer (PagePairRow, L412-L480).
- Method: direct reads of every load-bearing file (v0.5 component + api layer + backend endpoints; current `transcription.py` router, `schemas/transcription.py`, `models/transcription.py`, batch endpoints, migrations excerpts, S11/Phase-0a/0e docs), plus two exhaustive read-only census agents (frontend batch flow; backend lifecycle) whose line-referenced findings I spot-verified where they anchor a decision (the blind-review claim was re-verified by direct grep).
- Named protocols were sourced from their defining documents: IDN-2/IDN-3/LCY-1 (`docs/grading-redesign/architecture/phase_0a_architecture.md:L494-L501`), ANN-2 (L532), VER-1 (L538), RD-4 (L790-L791), plus the DFD's single-transaction statements (`docs/grading-redesign/architecture/phase_0e_dfd.md:L424-L426`).

---

## 3. v0.5 component autopsy

`v0.5/src/components/TranscriptionReviewPage.tsx` — a **client component rendered by a parent wizard, not a route**. Two modes: *streaming* (it either starts an SSE transcription itself, or receives the parent's stream state) and *non-streaming* (static `transcriptionData` prop).

| Item | Detail |
|---|---|
| **Props / route params** | Props only, no route params (`:L35-L51`): `transcriptionData?` (static mode), `rubricId? + testFile?` (self-streaming mode), `answeredQuestions?`, `studentName?` (free text), `onContinueToGrading(editedAnswers)`, `onBack`, `isGrading?`, `externalStreamState? + externalTranscriptionData?` (parent-streaming mode). The real caller uses the parent-streaming mode (`v0.5/src/app/page.tsx:L1232-L1243`). |
| **Local state** | `editedTexts: Record<string,string>` keyed either `page-{n}` or `{q}-{sub|'main'}` (`:L670`, `:L734-L735`, `:L1013`); `showConfirmModal` (`:L671`); an internal SSE reducer state + abort ref for self-streaming (`:L656-L657`). Edits are **client-only; nothing persists**. |
| **Network calls** | Exactly one, in self-streaming mode: `streamTranscriptionV2` → `POST {API_BASE}/api/v0/grading/stream_transcription_v2?rubric_id=…&first_page_index=…` with `FormData{test_file}` read as an SSE stream (`v0.5/src/lib/api.ts:L1479-L1510`). **No Authorization header** — raw `fetch` (L1503-L1510); same for `transcribeHandwrittenTest` (L1218-L1221) and `gradeWithTranscription` (L1238-L1244). In non-/parent-streaming mode the page itself makes **zero** network calls; "save" is `onContinueToGrading(editedAnswers)` — a callback, no request (`:L859`). |
| **Response/event shapes it was written against** | v0.5 server (`v0.5-backend/app/api/v0/grading.py:L2723-L3120`) emits per **page**: `page_complete {page_number, page_index, text(marked <Q#>), detected_questions, confidence_scores}` (L2900-L2908) and `review_flags {page, lines_to_review:[int], reasons:{line:reason}}` (L2910-L2921), then per-answer `answer` events where `question_number` is overwritten with `detected_questions[0]` (L2924-L2929). Static shape: `TranscriptionReviewResponse {transcription_id, rubric_id, student_name, filename, total_pages, pages: PagePreview[] (thumbnail_base64 embedded), answers: TranscribedAnswerWithPages[], raw_transcription}` (`v0.5/src/lib/api.ts:L1171-L1180`), answers carrying `{question_number, sub_question_id, answer_text, confidence, transcription_notes, page_indexes(0-based)}` (L1162-L1169). |
| **Child components** | All seven are internal to the file: `StreamingBanner` (L57), `StreamingTextDisplay` (L135), `ConfidenceBadge` (L217; <70% red, <85% amber), `TranscribedTextDisplay` (L243 — the flag-overlay editor), `PagePairRow` (L384 — the side-by-side page card with image-height matching), `AnswerEditor` (L487), `ConfirmationModal` (L559). External: `lucide-react` icons only. Current-day equivalents: `TranscriptionReviewPanel` covers the answer-editor + page-viewer + confidence + annotation roles (`frontend/src/components/TranscriptionReviewPanel.tsx:L295-L452`); nothing today covers the per-line flag overlay or the paired-height page layout. |
| **Styling** | Tailwind utility classes with custom `primary`/`surface` scales — defined in **both** tailwind configs (v0.5 `tailwind.config:L13,L37`; current `frontend/tailwind.config.ts:L32,L56`). UNVERIFIED — whether the two scales' hex values match (parity check is a Phase-3 verification step). Icons `lucide-react ^0.441.0` in both. |
| **React/Next** | Identical stack: `next 14.2.5`, `react ^18` in both `package.json`s. No missing-API risk. |
| **Artifact-shape assumptions** | (a) Transcription text exists **per page** (`pageStates` keyed by page number with full page text + `<Q#>` markers, `:L1011-L1027`) — the current artifact has no per-page text at all (§4.2). (b) Page indexes are 0-based (`page_indexes.map(i => i+1)`, `:L786-L787`) — the current draft uses 1-based `page_numbers` (`backend/app/schemas/transcription.py:L48`; proxy validates `1 ≤ n ≤ page_count`, `backend/app/api/v0/transcription.py:L209`). (c) Page thumbnails arrive embedded base64 in one payload (`PagePreview.thumbnail_base64`, `v0.5/src/lib/api.ts:L14-L22`) — current pages are lazily fetched one at a time behind auth (§4.3.6). (d) Per-line flags arrive as ephemeral stream events, never persisted. |
| **Auth** | None on any transcription call (raw `fetch`, no `getAuthHeaders`) — violates §9 wholesale. |
| **Things the current architecture forbids** | (1) Unauthenticated endpoints calls (§9). (2) **Silent repair heuristics in the save path**: `handleConfirmedContinue` assigns each page's text to the *first* detected question and falls back to **question 1** when none detected (`:L820-L831`), and the answer dedup keeps the *longer* text when duplicates disagree (`:L748-L767`) — both are silent guesses, the exact FC violation class. (3) Free-text `studentName` with no picker — collides with IDN-2/RD-4 (§5). (4) In-request streaming transcription — the current architecture transcribes in background jobs before review (`backend/app/api/v0/batch_grading.py:L70-L91`) and forbids new long-running request work. (5) Client-only edits lost on refresh — collides with the unsaved-state-honesty law. |

**What is actually worth porting** (the honest scope of "the port"): the *layout and interaction patterns* — full-screen document-like review, side-by-side source/transcription with matched heights, the per-line flag overlay technique (`TranscribedTextDisplay`, `:L300-L368`: highlighted backdrop behind a transparent textarea, `dir="ltr"` scoping at L287/L320/L358), the confidence badge, the sticky header, the confirm modal. The *data plumbing must come from the current stack* — the v0.5 plumbing (streaming, no auth, page-shaped text, client-side question assignment) is unusable and forbidden.

---

## 4. Current-state census

### 4.1 Frontend

- **There are two batch stacks; one is dead.** Live: `/batches` (`frontend/src/app/batches/page.tsx:L32`) and `/batches/[id]` (`frontend/src/app/batches/[id]/page.tsx:L349`), polling `GET /api/v0/batches/{id}` every 3s (`:L41`, `:L373-L385`). Dead (no render site anywhere — grep-verified): `frontend/src/components/BatchDashboard.tsx` (the component I was told to find "as BatchDashboard.tsx" **is orphaned**, exported at `:L68`, never rendered), `frontend/src/components/FlaggedItemsReview.tsx` (keyboard triage of *grading* flags, not transcription), and `frontend/src/hooks/useBatchProgress.ts` (`:L50-L182`) — all targeting an older `/api/v0/grading/batches/*/progress` session API (`frontend/src/lib/api.ts:L1780-L1788`).
- **Current batch transcription-review surface:** the "סקירת תמלולים" section of `/batches/[id]` (`[id]/page.tsx:L444-L479`). Triage is **live**: items partition on `flag_verdict.review_needed` (`:L409-L414`); clean ones go to `CleanTestsPanel` bulk-accept (`:L195-L261` → `acceptCleanTranscriptions`, `frontend/src/lib/api.ts:L2470-L2485`); flagged ones each get an inline `FlaggedTestCard` (`:L92-L190`) with flag-reason chips (`:L139-L145`, labels `frontend/src/types/batch.ts:L99-L105`), a StudentPicker pre-seeded from server auto-match (`:L100`, `:L153`), editable textareas, and "אשר תמלול" → `acceptOneTranscription` (`api.ts:L2490-L2508`). Graded tests open `GradedTestReviewPanel` via `GradeReviewSection` (`:L267-L296`, `:L331-L338`).
- **`TranscriptionReviewPanel.tsx` is single-test-only.** Props `{response: TranscribeResponse, onSubmit(answers, studentId), onBack, submitting}` (`TranscriptionReviewPanel.tsx:L14-L19`). Answer-indexed editable cards (`:L295-L363`), page-jump chips from `page_numbers` (`:L318-L326`), confidence % (`:L328-L330`), annotation banners incl. `reader_disagreement` diff + jump-to-page (`:L25-L94`), StudentPicker + `student_name_suggestion` hint (`:L276-L286`), single-page viewer with prev/next + on-demand base64 cache (`:L117-L164`, `:L407-L452`). Rendered **only** by the single-test wizard (`frontend/src/app/page.tsx:L2116-L2139`); the batch page imports it (`[id]/page.tsx:L18`) but never renders it — a dead import.
- **Routes & state movement:** batch id travels as a URL path segment only (`page.tsx:L1114-L1128` push after `createBatch`; `batches/page.tsx:L85-L88` links). All per-test state is server-derived from the polled batch payload; nothing batch-related is in localStorage. `GradeReviewSection`'s open-test is transient component state, not URL (`[id]/page.tsx:L267-L268`) — so today's batch flow has **no deep link to any per-test view**.
- **StudentPicker** (`frontend/src/components/StudentPicker.tsx:L16-L21`): controlled `{value, onChange}`, roster load + inline create (`:L41-L45`, `:L74-L90`). Auto-match is **server-computed** (`matched_student_id/-name` on `BatchTranscriptionItem`, `frontend/src/types/batch.ts:L26-L27`), surfaced by pre-seeding the picker (`[id]/page.tsx:L100`) and by gating bulk-accept to matched items (`:L212-L217`).
- **Page images:** authenticated JSON endpoint returning base64 (`getTranscriptionPage`, `api.ts:L2259-L2271` → `GET /api/v0/transcriptions/{id}/pages/{n}`), rendered as `data:` URIs (`TranscriptionReviewPanel.tsx:L448-L452`). Auth is a Bearer header, never a query token.
- **The seam:** `apiFetchRaw/Checked/apiFetch` with auth injection at the bottom layer (`api.ts:L102-L125`), `ApiAuthError` terminal for polls (`:L62-L70`), crash-stash (`frontend/src/lib/session.ts:L99-L126`, triggered `page.tsx:L578-L596`). All transcription/batch functions go through the seam (several redundantly re-check `res.ok` and re-add headers, e.g. `api.ts:L2226`, `:L2264` — duplication, not bypass). No review component issues raw fetch.
- **Codegen:** `src/lib/api-types.ts` is generated + CI drift-checked, but **imported at runtime nowhere**; the live transcription types are hand-written mirrors (`frontend/src/types/transcription.ts:L25-L71`, consumed by `batch.ts:L6`). Per the PR-4 rule ("new/touched wire types consume the generated ones"), the new endpoint this PR adds must be consumed via `api-types.ts`.
- **Flags:** `frontend/src/lib/flags.ts:L1-L10` contains only `USE_DOCUMENT_MIRROR = true`.

### 4.2 Backend contract & lifecycle

- **The artifact is answer-shaped with page provenance, not page-shaped.** `TranscriptionDraftAnswer {question_number, sub_question_id?, answer_text, confidence, page_numbers: List[int]}`; `TranscriptionDraft {schema_version, student_name_suggestion?, page_count, answers, annotations, model_version?, transcription_duration_ms?}` (`backend/app/schemas/transcription.py:L43-L58`). Contract: frozen `{schema_version, contract_version(uuid default), answers:[{question_number, sub_question_id?, answer_text}]}` (`:L65-L76`) — **no** page provenance, confidence, or annotations survive into the contract. There is no per-page text anywhere in the persisted artifact.
- **`POST /api/v0/transcriptions/grade` statement by statement** (`backend/app/api/v0/transcription.py:L127-L194`): ownership (L135-L137) → 409 unless `status=='transcribed'` (L138-L139, "התמלול כבר אושר") → student ownership (L141) → rubric load to pin VER-2 (L144) → **contract built from `body.answers`** — teacher edits ride in on approval (L147-L156) → one UPDATE sets `contract_json`, `student_id`, `student_name`, `status='approved'`, `approved_at` (L161-L166) → **same transaction** INSERTs one `graded_tests` row `status='pending'` with pinned `rubric_contract_version` (L168-L182) → commit (L184) → `background_tasks.add_task(run_grading, …)` (L189). **Approval, graded-test creation, and grading kickoff are one atomic-then-immediate unit (IDN-3).**
- **CHECK constraints (executed migrations):** `transcriptions.status IN ('transcribed','approved')` (`backend/migrations/008_phase_0c_new_schema.sql:L147-L148`); `transcriptions_approval_consistency` — `'transcribed'` **requires** `contract_json IS NULL AND approved_at IS NULL AND student_id IS NULL`; `'approved'` requires all three NOT NULL (L153-L164). ⚠ Consequence: **the `student_id` column cannot legally be written before approval** — per-item student selection needs a different pre-approval home (§6 OD-1/OD-6). `graded_tests_status_consistency` as documented (L298-L311). `batch_id` added by `011_s11_transcription_batch_id.sql:L26-L29`.
- **Annotations actually emitted** (allowed set `schemas/transcription.py:L27-L34`): legacy adapter (`backend/app/services/transcription_adapter.py`): `vlm_unparseable` (per-answer, WARNING, `[?]` present, L45-L51), `vlm_uncertainty` (per-answer; WARNING on grounding retry L54-L61, INFO on confidence<0.7 L64-L71), `vlm_low_logprob` (**whole-document**, WARNING, L73-L92), `student_name_missing` (whole-document INFO, L94-L101). Two-phase engine (`backend/app/services/transcription/two_phase_engine.py:L130-L213`): `vlm_unparseable` (per-answer, L156-L162), `reader_disagreement` (per-answer or whole-doc; WARNING/INFO; **metadata carries `page`, `char_start`, `char_end`, `line_quote`, `alternatives`** — the only span-level signal in the system, L183-L192), `code_lint` (per-answer INFO, L195-L204). **No per-line annotation exists; span offsets exist only in two-phase `reader_disagreement` metadata.** Engine selection: `settings.transcription_engine`, default `"legacy"` (`CLAUDE.md` §8; selection at `backend/app/services/transcribe_one.py:L70`).
- **Confidence reachable from the frontend:** per-answer `confidence` + `page_numbers` and the full annotations list — all inside `draft`, exposed per item **only** via `GET /api/v0/batches/{batch_id}` (`BatchTranscriptionItem.draft`, `backend/app/schemas/batch.py:L28-L45`, populated `batch_grading.py:L286-L306`). No GET returns a single non-batch transcription's draft.
- **Batch endpoints** (`backend/app/api/v0/batch_grading.py`): create+fan-out (L146-L204), list (L211-L241), detail with rollup + triage verdict (L248-L320; verdict logic `backend/app/services/batch_triage.py:L93-L142` — reasons `unparseable|grounding_retry|low_confidence|low_logprob_span|student_unmatched`, answer-confidence threshold 0.8 at L131-L133), `POST /{id}/accept_clean` (L327-L402), `POST /{id}/accept/{tid}` (L409-L473). **Both accept endpoints approve + INSERT pending graded_test + queue grading per item, immediately.** There is **no batch-level grading trigger** and **no approve-without-graded-test endpoint** anywhere.
- **Failed transcriptions leave no row.** The batch fan-out swallows per-item exceptions with only a log (`batch_grading.py:L87-L91`); the rollup computes `transcribing = test_count − len(rows)` (L129), so a permanently-failed item is indistinguishable from one still running — the batch shows "transcribing" forever and `_derive_batch_status` (L104-L114) keeps it `in_progress`. There is no `failed` status on transcriptions (`backend/app/models/transcription.py:L28-L29`). This is a pre-existing defect this PR must define its gate *around* (§6 OD-6), not silently fix.
- **No edit persistence, no reopen** — grep-verified none exists for transcriptions (only graded-test draft overrides, `grading.py:L579-L580`).

---

## 5. Gap analysis

| Desired capability | What exists today | What's missing | Where it must be built |
|---|---|---|---|
| Full-screen per-item review with source pages | `TranscriptionReviewPanel` does it for the single flow (`:L407-L452`); batch flow has blind inline cards (`[id]/page.tsx:L92-L190`) | A batch-routable surface with the v0.5 layout | Frontend: new route + shared surface component |
| Prev/next across the batch on one page | Nothing; batch per-test views are inline expanders, no deep links (`[id]/page.tsx:L267-L268`) | Cursor, ordering, deep-linkable route, end-of-list behavior | Frontend (route + shell) |
| Per-item save that survives navigation/refresh | Nothing: edits live in component state; approval is the only write (`transcription.py:L127-L194`) | A pre-approval persistence surface + endpoint; CHECK forbids using `student_id`/`contract_json` columns for it (`008:L153-L164`) | **Backend: schema (1 column) + 1 endpoint; frontend: autosave/hydrate** — OD-1 |
| Grading starts only at "שליחה לבדיקת מבחנים" | Opposite: accept ⇒ approve + insert + grade per item (`batch_grading.py:L327-L473`) | The batch-trigger endpoint — **explicitly deferred**; this PR defines the seam only | Backend (later PR); this PR: seam contract + gate computation — OD-2 |
| Page-paired transcription cards (v0.5 layout) | Artifact has no per-page text (`schemas/transcription.py:L43-L58`) | Impossible without pipeline change; answer-indexed layout with page companion is the faithful alternative | Frontend layout decision — OD-3 |
| Per-line "שורות לבדיקה" flags | v0.5 signal was ephemeral stream-only; today: `[?]` in text, per-answer confidence, span offsets only in two-phase `reader_disagreement` metadata (`two_phase_engine.py:L183-L192`) | A deterministic client derivation; honesty about legacy-engine sparseness | Frontend pure util — OD-4 |
| Keep bulk-accept for clean items | **Exists and is live** (`[id]/page.tsx:L195-L261`) | Nothing — keep it | — (OD-5 confirms) |
| Student selection on the review page (RD-4/IDN-2) | Exists in both panels; batch auto-match pre-seeds (`[id]/page.tsx:L100`) | Pre-approval *persistence* of the choice (CHECK forbids the column) | Rides in the OD-1 overlay — OD-6 |
| Correct, inclusive Hebrew copy | v0.5 carries defects ("1 תשובות", masculine imperatives) | Copy pass on every ported string | Frontend — §6 OD-1…/copy table §7.5 |
| One review surface (Simple over Easy) | Two today already: panel (single) + inline cards (batch); plus 3 dead components | Shared core; retirement of inline editor + dead code | Frontend — OD-7 |

---

## 6. Open decisions

Every §5-collision from the mission survives or falsifies as follows. Nothing below is resolved silently; each carries a recommendation for you to accept or override.

### OD-1 — What does per-item "save" mean? (collision 5.1 — CONFIRMED)

LCY-1 makes `approved` terminal and read-only; the CHECK (`008:L153-L164`) forbids any approval field (including `student_id`) on a `'transcribed'` row; `draft_json` is immutable from INSERT. So "save" can be neither "approve" nor "write back to the draft".

| Option | Mechanics | Schema churn | Invariant churn | Failure modes |
|---|---|---|---|---|
| **A. Client-only edits**, committed at accept | sessionStorage/localStorage keyed by transcription_id | none | none | Edits lost on device change, storage eviction, or crash-before-accept. For a 35-test batch reviewed over 2-3 sittings (the realistic after-school pattern), loss probability is per-sitting × per-item — the north-star metric pays for every loss. Also collides with unsaved-state honesty: the UI would claim "saved" for something only cached. |
| **B. Persisted review overlay (RECOMMENDED)** | New nullable `transcriptions.review_json` JSONB + `PATCH /api/v0/transcriptions/{id}/review`, allowed **only** while `status='transcribed'` (409 otherwise), ownership-guarded. Shape: `{schema_version, answers:[{question_number, sub_question_id, answer_text}], student_id: uuid\|null, reviewed: bool, updated_at}`. Exposed on `BatchTranscriptionItem` so refresh/deep-link rehydrates. | 1 column, migration 014 (idempotent, commit-token per §8 rules) | **None.** LCY-1 untouched (writes only pre-approval; at approval the overlay simply stops being writable — optionally nulled). CHECK untouched (student choice lives inside the JSON, not the column). ANN-2 untouched (`review_json` is teacher *input*, not system diagnostics — it is not a second diagnostic surface). IDN-2/IDN-3/VER-1 untouched. | A stale overlay vs. a re-transcribed draft — not reachable today (drafts are never regenerated); guard anyway by 409ing the PATCH on non-`transcribed` status. |
| **C. Third status (`'reviewed'`)** | CHECK rewrite + LCY-1 semantic change | migration + constraint change | **High** — mutates a named lifecycle (LCY-1's read-only line moves) | The classic silent-invariant-mutation trap; rejected. |
| **D. Terminal approval + explicit reopen chain** | approve per item; "reopen" extends a chain like graded-test revisions | new revision mechanism for transcriptions | High — IDN-3 means an approved transcription already has a graded_tests row + grading likely already ran; reopening means orphaning/cancelling grading work | Massive machinery to simulate what B gives for one column; rejected. |

**Recommendation: B.** Note it also *restores* §4 uniformity — the Draft→Contract table says Drafts are "Mutable, teacher-edited", and the transcription domain is currently the outlier whose teacher edits have no persisted home. The AI draft stays immutable (provenance, like the extraction-job result); the overlay is the teacher's working copy (like the saved rubric draft). Sub-decision surfaced: at approval time, the accept request **body remains authoritative** (current pattern, `transcription.py:L146-L156`) and the overlay is UX durability only — the server does not read the overlay at approval. This keeps one writer path per artifact.

### OD-2 — When do approval + grading fire in THIS PR? (collision 5.2 — CONFIRMED; IDN-3, and the DFD single-transaction guarantee `phase_0e_dfd.md:L424-L426`)

Today accept ⇒ (approve + insert graded_tests, one transaction — IDN-3) ⇒ grading queued immediately, per item (`batch_grading.py:L397`, `:L466`). The desired end state moves grading kickoff to a single batch action — but the mission **explicitly defers the batch-grading trigger endpoint** and forbids half-implementing it. That leaves a real fork:

| Option | This PR ships | Consequence |
|---|---|---|
| **A. Keep per-item accept semantics (RECOMMENDED)** | The review page has two distinct actions: **שמירה** (OD-1 overlay, freely repeatable, navigation-safe) and **אישור תמלול** (existing `accept_one` with the edited answers — approve + insert + grade, per item, exactly today's semantics). Accepted items render read-only with an honest "אושר" state (LCY-1 shown, not hidden). The batch page's "everything reviewed" completion state is computed, and the plan documents the future `POST /api/v0/batches/{id}/submit` contract as the seam. | The product works at every commit; the *only* thing the follow-up PR changes is *when* approval+grading fire. No endpoint is half-built. The שליחה button as a single batch-level action does **not** exist yet — deferred with the endpoint. |
| B. Client-side "שליחה" loops accept_one over all reviewed items | A button that fires N sequential requests | This IS the grading kickoff, half-implemented client-side: non-atomic, partial-failure UX undefined, and it forecloses the server-side design (per-item transactions vs batch transaction) the deferred PR should own. Rejected. |
| C. Review-only PR (save exists, nothing approves) | Page + saves only; accepts removed | The batch flow can no longer reach grading at all until the follow-up lands — a shipped regression. Rejected. |

**The seam, defined (for the later PR to plug into):** `POST /api/v0/batches/{batch_id}/submit` — server-side loop over the batch's `'transcribed'` rows; for each: build contract from that row's `review_json` (which the endpoint will then read — a deliberate, flagged extension of OD-1's "body is authoritative"), approve + insert graded_tests **in a per-item transaction** (IDN-3 preserved per item; per-scope failure isolation §3.6 argues per-item commits so one bad row flags rather than throws the batch), queue `_grade_with_cap` per inserted row. Request: `{}` (zero-param submit — Dream-UX). Response: per-item outcomes. Gate (what "all reviewed" means): OD-6. Frontend-side, this PR ships the gate computation and the completion state so the follow-up only swaps the action wiring.

### OD-3 — Page-indexed UI vs answer-indexed artifact (collision 5.3 — CONFIRMED, resolved toward (b))

The artifact is conclusively answer-shaped with per-answer `page_numbers` (`schemas/transcription.py:L43-L48`); per-page text does not exist and never reaches the DB (v0.5's page cards existed only because its SSE stream emitted per-page text, `v0.5-backend/grading.py:L2900-L2908`).

- **(a) Add page provenance / per-page text to the pipeline** — a prompt+schema+pipeline change across both engines, touching the P2 segmentation that the eval suite gates (§17 territory), to serve a layout preference. Cost: high, cross-cutting, eval-gated. Rejected for this PR.
- **(b) Answer-indexed cards + page-image companion (RECOMMENDED)** — right column: the source pages (all pages, scrollable, as in v0.5's visual); left column: one card per answer (the current panel's proven shape, `TranscriptionReviewPanel.tsx:L295-L363`), ordered by first `page_numbers` entry then question number, each carrying `שאלה N` + `עמוד N` chips; clicking the chip scrolls/jumps the source column (the panel's existing jump behavior). The v0.5 *look* (document-like paired cards) is kept; the *indexing* is honest to the artifact. The header counts answers — with correct pluralization.

Honest regression vs the screenshot: no per-page text block pairing, and the `הושלם` per-page chips (a streaming-phase artifact, `:L451-L456`) disappear. Both are recorded as accepted deltas, not papered over.

### OD-4 — Per-line flags with no per-line data (collision 5.4 — PARTIALLY FALSIFIED)

The conjecture "all transcription annotations are whole-document scoped" is falsified: annotations are mostly **per-answer** (`transcription_adapter.py:L45-L71`), and two-phase `reader_disagreement` metadata carries real span offsets (`char_start`/`char_end`/`page`, `two_phase_engine.py:L183-L192`). But no persisted signal is per-*line*, and the default engine is legacy (no spans).

- **A. Derive on the client, deterministically (RECOMMENDED):** a pure util `deriveReviewFlags(answer, annotations) → {line, reason}[]` — lines containing `[?]` → "תו לא ברור"; `reader_disagreement` spans mapped char-offset→line within the answer text → the annotation's message/alternatives; `code_lint` → answer-level (not line) badge. Unit-testable with zero backend change; the overlay renderer is ported as-is (`TranscribedTextDisplay`, `v0.5:L300-L368`). Under the legacy engine this yields `[?]`-lines only — the flag-count header renders **only when flags exist** (the v0.5 component already behaves this way, `:L274-L298`), so sparseness is honest, not misleading.
- B. Plumb span-level confidence from the VLM — new pipeline output, eval-gated territory; deferred (it slots into A without rework when it lands).
- C. Ship without per-line flags — needless: A costs one pure util and keeps the screenshot's most valuable affordance.

### OD-5 — Bulk-accept vs open-every-test (collision 5.5 — FALSIFIED as a risk; the triage EXISTS and is live)

Triage is shipped code, not just a doc claim: partition (`[id]/page.tsx:L409-L414`), bulk-accept (`:L195-L261`), per-flagged handling (`:L92-L190`), per S11 D1 "Model A-minus" (`docs/grading-redesign/sprints/S11_pr_description.md:L29`). Forcing 35 open-and-save round trips would regress the north-star metric against shipped design. **Recommendation (agreeing with, and grounding, the one in the mission):** keep `CleanTestsPanel` bulk-accept exactly as is; the ported page is the **drill-in** — mandatory surface for flagged items (replacing the blind inline editor) and available for any item the teacher wants to inspect (clean rows become links too). Prev/next iterates over the *flagged + opened* set by default (sub-decision in OD-8).

### OD-6 — Student assignment & the submit gate (collision 5.6 — IDN-2, RD-4)

RD-4 locks selection to the review screen; IDN-2 requires `student_id` at approval; the CHECK **forbids** the column before approval (§4.2). Resolution: the picker sits in the review page header region (pre-seeded from `matched_student_id`, falling back to `student_name_suggestion` as hint — both already on the payload); the *choice* persists in the OD-1 overlay's `student_id` field; the column is written only at accept (existing endpoints already do this). "אישור תמלול" stays disabled until a student is chosen (the panel's existing pattern, `TranscriptionReviewPanel.tsx:L381-L394`).

**"All transcriptions reviewed" (the gate), defined precisely:** every transcription **row** of the batch has `status='approved'`. Failed-to-transcribe items have **no row** (§4.2, the swallowed-exception defect) — the gate cannot see them, so batch completion must be computed against rows, with the `transcribing = test_count − rows` residue **surfaced** as "N קבצים לא תומללו" once a staleness horizon passes rather than blocking forever. Open sub-decision for you: (i) this PR only *displays* the residue honestly (recommended — smallest true change), or (ii) this PR adds failure tracking (a transcriptions `failed` status or batch-level failed-files list) — schema + CHECK churn I'd rather not bundle here. Empty transcriptions (0 answers): reviewable and acceptable — the page shows the empty-state and the teacher can type answers in (the v0.5 editor already supports empty text, `:L288`); an all-empty accept is legal today (contract with empty answers is schema-valid, `schemas/transcription.py:L72-L76`) — flagged to you rather than silently allowed or blocked: recommend allowing with a confirm-modal warning.

### OD-7 — Retirement manifest (collision 5.9; Simple over Easy)

End state: **one transcription-review surface concept** — a shared `TranscriptionReviewSurface` component (the adapted port: answer cards + source column + flag overlay + picker), wrapped by two thin shells: the batch shell (cursor/prev-next/save/accept) and the single-test shell (the wizard's submit). In this PR:

| Artifact | Fate | Justification |
|---|---|---|
| `FlaggedTestCard`'s inline editor (`[id]/page.tsx:L92-L190`) | **Deleted** — card becomes a summary row linking into the review route | Replaced by the thing this PR builds |
| `TranscriptionReviewPanel.tsx` | **Rebuilt as a thin wrapper** over the shared surface (single-flow shell), same props seam so `page.tsx:L2116-L2139` is untouched | One surface, per §0.4; the panel's plumbing *is* the shared core's starting point, so this is extraction, not rewrite |
| Dead code: `BatchDashboard.tsx`, `FlaggedItemsReview.tsx`, `useBatchProgress.ts` + barrel exports, orphan api fns `getBatchProgress`/`cancelBatch`/`getSessionDetails` (`api.ts:L1780-L1862`) + their types | **Deleted** (final phase, gated on tsc/vitest/build green) | Census-verified unreferenced; leaving them is exactly the parallel-surface debt §0.4 names |
| The panel's dead import in `[id]/page.tsx:L18` | Deleted with the rewire | — |

If you prefer to decouple risk, the panel-unification row alone can split into an immediate follow-up PR; my recommendation is to keep it in (it is the difference between "one surface" and "three"), sized as its own phase so it is separately revertable.

### OD-8 — Navigation & state mechanics (collision 5.8)

- **Cursor home: URL path segment (RECOMMENDED)** — new route `frontend/src/app/batches/[id]/review/[transcriptionId]/page.tsx`. Deep-linkable, refresh-safe (loads batch detail, locates the item), browser-back returns to `/batches/[id]` naturally. Query-param and component-state options rejected: component state dies on refresh (O3's whole lesson), query params make prev/next replaceState gymnastics for no gain.
- **Ordering:** the batch payload's item order, partitioned flagged-first (matching the dashboard's visual order) — deterministic and stable across polls. Sub-decision: arrows traverse flagged-only vs all items; recommend **all items in flagged-first order** (the teacher who wants to spot-check cleans can keep arrowing; the flagged ones come first anyway).
- **Ends:** prev hidden/disabled at first item; at last item, next becomes "חזרה לסיכום המקבץ" (back to the batch page). No wraparound.
- **Unsaved-changes guard:** save is the OD-1 overlay PATCH. Recommended model: **explicit autosave-on-navigate** — arrowing away (or accepting) first flushes a save of the current item, with an honest per-item saved/dirty indicator ("נשמר"/"שינויים לא שמורים"); `beforeunload` guard only when a save is in-flight or failed. Alternative (modal on every navigation) rejected as tired-skeptic-hostile — but this is a named sub-decision if you want the stricter modal. A failed save **blocks** navigation with the inline error banner (never silent loss).
- **Prefetch:** all drafts + overlays already arrive in the one batch payload — no per-item data fetch needed. Page images are the cost: fetch current item's pages on open (first page eagerly, rest lazily as the source column scrolls — the panel's existing cache pattern), and prefetch **only the first page of the next item** on idle. Rationale: the proxy re-renders the *entire PDF* server-side per page request (`transcription.py:L222` renders all pages, then indexes) — aggressive prefetch multiplies a quadratic server cost. That render inefficiency is recorded as a risk/backlog item (§10 R2), not fixed here.
- **Keyboard:** none in v1 beyond native textarea behavior — arrow keys conflict with editing focus; on-screen edge arrows only. (Future: Alt+←/→, backlog.)

### OD-9 — Which types feed the new code (small but named, per PR-4 R-B)

New/touched wire shapes (`review_json`, the PATCH request/response, `BatchTranscriptionItem` extension) are consumed from **generated** `api-types.ts` (`npm run gen:api` after the backend change), not added to the hand-written mirrors; existing hand-written transcription types stay as-is (opportunistic-migration rule). Surfaced because the current review code is 100% hand-mirrors (§4.1) and continuing that by inertia would be the silent-choice failure.

---

## 7. Proposed architecture

**The one concept in one place:** *the transcription-review surface* is one component; *pre-approval teacher edits* have one persistence location (`review_json`); *approval* keeps its one existing writer path (`/grade` · `accept_one` · `accept_clean`); *diagnostics* stay solely in `draft.annotations` (ANN-2) with the per-line overlay a pure **derivation**, not a new stored surface.

```
GET /api/v0/batches/{id}  (existing; + review_json per item)
        │
        ▼
/batches/[id]  (dashboard: triage, bulk-accept, links)        ── seam ──►  POST /batches/{id}/submit   [DEFERRED PR]
        │  Link per item
        ▼
/batches/[id]/review/[transcriptionId]     ◄── prev/next (URL replace) ──►
        │
   BatchReviewShell  (cursor, autosave-on-navigate, accept wiring)
        │ props: {draft, reviewJson, matchedStudent, flagVerdict, pages via getTranscriptionPage}
        ▼
   TranscriptionReviewSurface  (shared: answer cards + flag overlay + source column + StudentPicker)
        ▲
   SingleReviewShell (= today's TranscriptionReviewPanel props seam, unchanged for page.tsx)

Writes: PATCH /api/v0/transcriptions/{id}/review   (new; only while status='transcribed')
        POST  /api/v0/batches/{id}/accept/{tid}    (existing; approve+insert+grade — unchanged)
```

State ownership: the shell owns cursor + dirty/save state; the surface is controlled (edits up via callbacks, mirroring the mirror/editor convention); server state stays poll-derived on the dashboard and fetch-on-entry on the review route. Subject modularity: the surface stays subject-agnostic (mono `<textarea>`, `dir="ltr"` code region — no language-aware rendering; there is no syntax highlighting to leak, §2).

**RTL/bidi mechanism (named, testable):** the transcription editor and its backdrop are `dir="ltr"` islands inside the RTL page (the v0.5 technique, `:L287`, `:L320`, `:L358`), **plus** `unicode-bidi: plaintext` on the backdrop's per-line divs so a line that *starts* with a Hebrew inline comment (`// תכונות`) keeps its `//` on the left and its punctuation unreordered per-line rather than inheriting the LTR paragraph direction blindly. Verified by the named Playwright test in §9, not asserted.

**Copy inventory (every string the port introduces → final form; nominal, gender-neutral forms per the feminine-majority audience):**

| v0.5 string | Final form |
|---|---|
| `בדיקת תמלול` | keep |
| `אישור והמשך לבדיקה` | split: `שמירה` (overlay) · `אישור תמלול` (accept) · batch-level `שליחה לבדיקת מבחנים` (deferred-seam button) |
| `(1 תשובות)` | `תשובה אחת` / `{n} תשובות` / `אין תשובות` (pluralization helper, unit-tested) |
| `(3 עמודים)` | `עמוד אחד` / `{n} עמודים` |
| `• ניתן לערוך ישירות` | keep |
| `{n} שורות לבדיקה (העבר עכבר לסיבה)` | `שורה אחת לבדיקה` / `{n} שורות לבדיקה` · hint `(מעבר עם העכבר מציג את הסיבה)` |
| `מכיל תווים לא ברורים [?]` | keep |
| `תמלול ריק - ניתן להקליד כאן` | `תמלול ריק — אפשר להקליד כאן` |
| `להמשיך לניקוד?` / `וידאת שהתמלול נכון…` | modal repurposed for accept: `לאשר את התמלול?` + `אישור התמלול ישלח את המבחן לבדיקה` |
| `יש {n} תשובות עם ביטחון נמוך` | `{n} תשובות ברמת ביטחון נמוכה` |
| `חזור` | `חזרה` |
| `מדרג...` | dropped (wrong flow); saving state: `שומר…` → `נשמר` |
| `הושלם` per-page chip | dropped (streaming artifact, OD-3) |
| new | `שינויים לא שמורים` · `אושר` (read-only state) · `חזרה לסיכום המקבץ` · `{n} קבצים לא תומללו` |

---

## 8. Phased implementation plan

Each phase is one reviewable diff, independently green (backend: `python -c "import app.main"` + `pytest -q`; frontend: `npx tsc --noEmit` + `npx vitest run` + `npx next build`).

**Phase 1 — Backend: the review overlay (OD-1).**
Files: `backend/migrations/014_transcription_review_json.sql` (new; idempotent `ADD COLUMN IF NOT EXISTS review_json JSONB`; ends with its schema_migrations commit token) · `backend/app/database.py` (add `'014'` to `EXPECTED_MIGRATIONS`) · `backend/app/models/transcription.py` (column) · `backend/app/schemas/transcription.py` (`TranscriptionReview` model — additive; no existing type forked) · `backend/app/api/v0/transcription.py` (PATCH `/{id}/review`: ownership via `get_owned_or_404`, 409 unless `status='transcribed'`, validate body, write, bump `updated_at`) · `backend/app/schemas/batch.py` + `backend/app/api/v0/batch_grading.py` (expose `review_json` on `BatchTranscriptionItem`) · tests `backend/tests/api/test_transcription_review.py` (ownership-404 cross-tenant, 409-on-approved, shape validation, batch-detail exposure) + regression run of existing accept tests.
Invariants touched: **none changed** — LCY-1/IDN-2/IDN-3/VER-1/ANN-2 all verified untouched by the tests above (explicit test: PATCH on approved row → 409; approve path ignores overlay).
Verify: pytest green; manual curl round-trip on dev DB; `SCHEMA OK` boot log with 014 applied.

**Phase 2 — Frontend: data layer + route scaffold (OD-8, OD-9).**
Files: `npm run gen:api` → regenerated `frontend/src/lib/api-types.ts` · `frontend/src/lib/api.ts` (add `saveTranscriptionReview` via `apiFetch`, consuming generated types) · `frontend/src/types/batch.ts` (extend `BatchTranscriptionItem` mirror with `review_json` — referencing the generated type) · new `frontend/src/app/batches/[id]/review/[transcriptionId]/page.tsx` (shell skeleton: loads batch, resolves cursor/ordering, renders a placeholder body, prev/next with autosave stub, ends behavior) · new `frontend/src/utils/batch-review-cursor.ts` (pure ordering/cursor logic) + `batch-review-cursor.test.ts`.
Verify: tsc/vitest/build green; manual: deep-link, refresh, back-button, first/last-item behavior against a mocked batch.

**Phase 3 — Frontend: the surface (the port itself; OD-3, OD-4, copy, RTL).**
Files: new `frontend/src/components/transcription-review/TranscriptionReviewSurface.tsx` (answer cards + source column: ported layout on the panel's plumbing) · new `.../TranscribedTextEditor.tsx` (the v0.5 overlay editor, `dir="ltr"` + `unicode-bidi: plaintext`) · new `frontend/src/utils/review-flags.ts` (`deriveReviewFlags` — pure) + `review-flags.test.ts` (offset→line math incl. multi-line spans, `[?]` lines, legacy-engine sparse case) · new `frontend/src/utils/hebrew-plural.ts` + test · wire the shell (Phase 2 file) to the real surface with save/accept/read-only-approved states.
Invariants touched: RD-4/IDN-2 surfaced in UI (picker + disabled-accept); ANN-2 respected (derivation only).
Verify: vitest green; manual review journey on a dev batch under both engines (legacy: `[?]`-only flags; two_phase: span flags); tailwind token parity eyeballed against v0.5 (§3 UNVERIFIED item resolved here).

**Phase 4 — Frontend: rewire the batch dashboard (OD-2A, OD-5, OD-6).**
Files: `frontend/src/app/batches/[id]/page.tsx` — `FlaggedTestCard` reduced to a summary row + `<Link>` into the review route (inline editor deleted); clean rows gain the same link; `CleanTestsPanel` bulk-accept untouched; add the gate computation + completion state + honest un-transcribed residue line; remove the dead `TranscriptionReviewPanel` import (L18).
Verify: Playwright journeys (§9) against route mocks; manual full batch walk on dev.

**Phase 5 — Unification + retirement (OD-7).**
Files: `frontend/src/components/TranscriptionReviewPanel.tsx` (rebuilt as thin wrapper over the surface; **props seam unchanged** so `frontend/src/app/page.tsx` has zero diff) · delete `frontend/src/components/BatchDashboard.tsx`, `frontend/src/components/FlaggedItemsReview.tsx`, `frontend/src/hooks/useBatchProgress.ts` (+ its barrel lines in `frontend/src/hooks/index.ts`) · remove `getBatchProgress`/`cancelBatch`/`getSessionDetails` + orphaned types from `frontend/src/lib/api.ts`.
Verify: tsc/build green proves nothing referenced them; single-test flow Playwright regression; visual diff of the single-flow review step.

**Phase 6 — Docs.** `CLAUDE.md` §7/§10 updates (batch review surface, review overlay, the OD-2 seam), `BACKLOG.md` entries (page-render inefficiency; failed-transcription tracking; Alt-arrow keys; span-confidence plumbing). Per §16 this rides with the sprint, not before.

---

## 9. Test plan

**Backend (pytest):** Phase-1 suite as listed; plus an explicit LCY-1 guard test (PATCH review on approved → 409, row byte-identical after).

**Frontend unit (vitest):** `review-flags.test.ts` (span→line mapping, `[?]` detection, empty/legacy cases) · `batch-review-cursor.test.ts` (ordering flagged-first, ends, single-item, missing-id → fallback) · `hebrew-plural.test.ts` (1/2/many/0 for תשובות ועמודים ושורות) · dirty/save state reducer test.

**Playwright (route-mocked), named journeys:**
- `batch-review-walkthrough`: dashboard → open flagged → edit → arrow-next (autosaves) → arrow-back shows persisted edit → accept → read-only `אושר` → next.
- `rtl-bidi-code-comment-rendering` (named per mission): a fixture answer containing LTR Java with inline Hebrew comments and a Hebrew-*initial* line; assert the rendered code region is `dir="ltr"`, that `//` precedes the Hebrew comment text in visual order (screenshot-diff or bounding-box x-comparison), and that punctuation is not reordered.
- `unsaved-changes-guard` (named per mission): edit → kill the PATCH route (500) → arrow → navigation blocked, error banner shown, edit still present; restore route → arrow succeeds.
- Negative cases: `failed-transcription-in-batch` (mock `test_count=3`, 2 rows → residue line renders, gate never claims complete, arrows span 2) · `unmatched-student` (accept disabled until picker set; `student_unmatched` chip shown) · `single-item-batch` (no arrows; next-is-return) · `empty-transcription` (0 answers → empty state, typed answer flows into save + accept payloads).
- Regression: `single-flow-review-unchanged` (wizard step renders via the wrapped panel, submit payload identical).

**Contract/type parity:** CI `check:api-drift` covers the regenerated `api-types.ts`; a vitest asserts the hand-mirror `BatchTranscriptionItem` extension satisfies the generated type (compile-time `satisfies`).

---

## 10. Risks & kill criteria

| # | Risk | Kill criterion (stop and re-plan, don't push through) |
|---|---|---|
| R1 | The review overlay turns out to need approval-time server reads (client can't be trusted to send saved answers) | If any reviewer/requirement forces the accept path to read `review_json`, STOP — that changes the approval writer-path contract (OD-1 sub-decision) and must be re-approved, not slipped in |
| R2 | Page-image latency: the proxy renders the whole PDF per page (`transcription.py:L222`) — a 6-page test costs ~6 full renders to view | If median page load in dev exceeds ~3s, pause Phase 3 and do the small backend fix (render-single-page) as its own flagged mini-phase first |
| R3 | Unification (Phase 5) churns the single-flow wizard | If wrapping the panel requires touching `page.tsx`'s state machine at all, split Phase 5 into a follow-up PR and record the two-surface interim in BACKLOG |
| R4 | Legacy engine makes the flag overlay near-empty and the affordance feels broken | If dev testing shows misleading emptiness, drop the flag-count header entirely under zero flags (already the design) and re-verify; if still misleading, ship without the overlay and record the regression vs screenshot |
| R5 | OD-2 recommendation rejected (per-item accept semantics unacceptable interim) | The PR's shape changes fundamentally — halt after Phase 1 and re-plan around whichever submit semantics you choose |
| R6 | A CHECK constraint fires anywhere during Phase 1 testing | Per §0.5: the constraint is presumed correct; stop and flag, no loosening |

---

## 11. What I am NOT doing in this PR

- **No batch-grading trigger endpoint** (`POST /batches/{id}/submit` is specified as a seam in OD-2 and not implemented; no client-side loop simulates it).
- No change to *when* approval creates graded_tests or fires grading (IDN-3 path byte-identical).
- No S12/S13 batch grade-review dashboard work (UX-interview-gated).
- No bulk grade-approval (eval-gated).
- No transcription-pipeline changes: no per-page text, no new flags, no engine switch, no span-confidence plumbing (backlogged).
- No reopen/unapprove mechanism for approved transcriptions (LCY-1 stands).
- No touch of `contract_compiler`, grading agent, eval suites, ground truth, or any §17 artifact.
- No fix for the swallowed-transcription-failure defect beyond honestly *displaying* the residue (OD-6 sub-decision if you want more).
- No copy overhaul beyond the strings this port introduces (§7 table).

---

*Definition-of-done check (§7 of the mission): §3 answers what the component is and assumes; §4 answers what exists; §6 enumerates every collision with its invariants by name and a recommendation; §8 says what ships where; §9-§10 say how a phase proves itself wrong.*
