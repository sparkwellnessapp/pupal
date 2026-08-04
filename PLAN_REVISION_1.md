# PLAN_REVISION_1 — deltas to PLAN_batch_transcription_review.md

> Revision pass required by the feedback rulings. **Deltas only** — every Δ cites the section of the original plan it amends. Nothing outside these deltas is reopened. No implementation code was written; two evidence items (Δ6, Δ10) required fresh code reads, cited inline. Phase 1 begins only after this revision is approved.

---

## Δ1 — The accept_clean × overlay exclusion rule *(feedback §2.1; amends plan §6 OD-1, §6 OD-5, §8 Phase 1, §8 Phase 4, §9, §7 copy table)*

**The hole, acknowledged:** OD-1B ("נשמר" + server never reads the overlay at approval) × OD-5 (clean rows openable/editable) × `accept_clean` (contract built from the draft as-is, `backend/app/api/v0/batch_grading.py:L327-L402`) compose into a silent discard of honestly-confirmed saves. This was a real gap in the plan, not a ruled trade-off.

**Rule (as ruled):** an item with `review_json IS NOT NULL` is **excluded from the bulk-accept set**. Teacher-touched ⇒ not "clean" ⇒ individual accept only.

- **Server-side enforcement point (authoritative):** inside `accept_clean`'s item-selection loop (`batch_grading.py:L327-L402`) — a row is skipped when `review_json IS NOT NULL`, regardless of what the client sent. The response gains a per-item skipped outcome (`skipped_reason: "has_review_edits"`) alongside the accepted list, so the client renders truth, not assumption.
- **Client-side (cosmetic, not the guard):** `CleanTestsPanel`'s selection filter (`frontend/src/app/batches/[id]/page.tsx:L207-L225`) additionally excludes items with a non-null overlay, and the panel renders the excluded-count line (copy in Δ13). The button count reflects the post-exclusion set.
- **Named test (backend, Phase 1):** `clean-item-edited-then-bulk-accept` — save an overlay on a clean item → call `accept_clean` → assert that item remains `status='transcribed'` with `review_json` intact, the untouched clean items are approved, and the response reports the skip.

Phase placement: the server filter + test land in **Phase 1** (it ships with the column, so the invariant "an overlay is never silently discarded" holds from the first deployable commit); the dashboard copy/count lands in Phase 4.

---

## Δ2 — Overlay shape: full snapshot, no `reviewed`, explicit rejection semantics *(feedback §2.2, §3.3 concurrency; amends plan §6 OD-1 shape, §8 Phase 1, §9)*

Amended `review_json` shape:

```
{schema_version, answers: [{question_number, sub_question_id, answer_text}], student_id: uuid|null, updated_at}
```

- **Full snapshot, always.** Every PATCH carries the complete answer set (client hydrates draft → editor → saves complete state). **No merge semantics exist anywhere** — not in the PATCH, not in the future submit endpoint.
- **`reviewed: bool` is deleted from the shape.** Under per-item accept semantics it gates nothing (the gate is `status='approved'`); an inert field becomes silently load-bearing later. If the future שליחה endpoint needs a marker, that PR adds it with its own justification.
- **Rejection semantics (endpoint spec, pinned by test):** a PATCH body whose answer key set (the multiset of `(question_number, sub_question_id)`) does not exactly equal the draft's key set is **rejected with 422** — never normalized, filled, pruned, or reordered silently. Named test in the Phase-1 suite: full-snapshot mismatched-key-set rejection (missing key, extra key, duplicate key).
- **Concurrency rule (stated, not tested, per feedback §3.3):** concurrent overlay PATCHes from two tabs are **last-write-wins**. Acceptable and now written into the endpoint spec rather than discovered.

---

## Δ3 — Overlay lifecycle at approval: nulled, in all three paths *(feedback §2.3; amends plan §6 OD-1 lifecycle, §8 Phase 1, §9)*

The original "optionally nulled" is replaced by a decision: **`review_json` is set to `NULL` in the same UPDATE that performs the approval transition**, in all three approval paths — `POST /transcriptions/grade` (`backend/app/api/v0/transcription.py:L161-L166`), `accept_one` (`batch_grading.py:L409-L473`), and `accept_clean` (`:L327-L402`; per Δ1 it only ever approves rows whose overlay is already NULL, but the write still nulls defensively so the invariant is uniform).

**LCY-1 reasoning, stated explicitly as required:** the null-out is part of the `'transcribed'→'approved'` **transition write** — the same statement that sets `contract_json`/`student_id`/`approved_at`. It is not a mutation of an approved row; once the row *is* approved, nothing writes `review_json` again (the PATCH 409s). LCY-1's read-only guarantee over approved rows is therefore untouched.

**Extended Phase-1 LCY-1 guard test:** after approval via **each** of the three paths — `review_json IS NULL` and a subsequent PATCH returns 409.

---

## Δ4 — The accept-robustness property + post-accept PATCH suppression *(feedback §2.4; amends plan §7 stated properties, §9)*

Added to §7 as a **stated architectural property**: because accept remains body-authoritative (`transcription.py:L146-L156` pattern, unchanged), *a failed or in-flight autosave can never corrupt an accept* — the accept body carries the current editor state regardless of overlay state. The overlay is durability; the body is authority.

**Sequencing rule added to the batch shell spec:** after a successful accept of an item, all overlay PATCHes for that item are **suppressed client-side** (the shell marks the item accepted and the autosave-on-navigate flush becomes a no-op for it) — otherwise every accept-then-arrow fires an autosave into the guaranteed 409. **Named test:** `overlay-patch-suppressed-after-accept` (vitest on the shell's save logic: accept → navigate → assert no PATCH issued; the 409 path is never exercised in the happy journey).

---

## Δ5 — The seam, rewritten under the re-decided end state *(feedback §2.5; REPLACES the seam contract in plan §6 OD-2; amends §11)*

**Product ruling recorded:** per-item grading kickoff is the **permanent** design, not an interim. Grading in parallel with the teacher's remaining review is a north-star latency win; batch-deferred grading is rejected ceremony. "שליחה לבדיקת מבחנים" is **not** a grading-kickoff mover.

**The seam contract (ruled end state — deferred and unimplemented in this PR):**

`POST /api/v0/batches/{batch_id}/submit` = **accept everything remaining that is acceptable + completion ceremony.**

- Server-side loop over the batch's remaining `'transcribed'` rows that are *acceptable*: content = `review_json` when present, else the draft; student = overlay's `student_id` when present, else the server auto-match — an item with no resolvable student is skipped, not guessed.
- Per item it performs **today's exact accept semantics**: approve + INSERT pending `graded_tests` in a **per-item transaction** (IDN-3 preserved per item) + queue `_grade_with_cap` — per-scope failure isolation per §3.6: one bad row becomes a reported skip, never a thrown batch.
- Reading `review_json` at approval is a deliberate property **of this future endpoint only** (it has no request body to be authoritative); the per-item accept endpoints this PR uses remain body-authoritative (Δ4). Flagged so the two writer conventions are a documented contrast, not drift.
- Request: `{}` (zero-param submit). Response: per-item outcomes — accepted (with `graded_test_id`) and skipped (with reason: `student_unresolvable`, `already_approved`, …).

Everything this PR ships under OD-2A is unchanged: the two actions on the review page (שמירה / אישור תמלול), the gate computation, the completion state. §11's non-goals line is amended from "no change to *when* grading fires (deferred)" to: **grading-kickoff timing is permanently per-item by product ruling; the deferred endpoint changes coverage (accept-the-rest), not timing.**

---

## Δ6 — Span-offset frame of reference: FINDING *(feedback §2.6; amends plan §6 OD-4, §8 Phase 3 spec of `deriveReviewFlags`)*

The suspicion was correct; the original plan's "mapped char-offset→line within the answer text" was wrong.

**Finding, with line refs:**
- `char_start`/`char_end` index into the **baseline page text**, not the answer text: `FlagSpan` declares `char_start: int  # char offsets on the baseline page text` (`backend/app/services/transcription/flagging.py:L93-L94`).
- The metadata's `line_quote` is the **baseline line containing the span**: `context_line: str  # the baseline line containing the span` (`flagging.py:L99`), computed by `_line_of(base_text, cs, ce)` (`:L214-L216`, populated `:L270-L274`).
- The backend itself never translates offsets to answer coordinates. It anchors a flag to an answer by **fuzzy line matching**: `anchor_flags` normalizes `context_line` and compares against each answer's normalized lines, attaching `anchor_key` when best-match ≥ `ANCHOR_THRESHOLD = 0.75` (`flagging.py:L300-L327`), recording `anchor_similarity`. The engine then copies `page/line_quote/char_start/char_end/anchor_similarity` into annotation metadata verbatim (`backend/app/services/transcription/two_phase_engine.py:L183-L192`).

**Consequence — `deriveReviewFlags` respecified:**
- **`char_start`/`char_end` are not used at all** (they are page-frame; using them against answer text produces silent garbage).
- The answer-relative line is located by **trimmed-exact match of `metadata.line_quote` against the draft answer's lines**. Found → that line gets the highlight + the annotation's message. Not found → the flag **degrades to an answer-level badge** (the annotation banner the current panel already renders).
- Deliberately **no client-side reimplementation of `norm_line`/`best_line_match` fuzzy matching** — a drifting client mirror of backend normalization is the `AnnotationSchema` failure class. Cost, recorded as an accepted delta: a minority of span flags (where the backend's fuzzy match succeeded but a trimmed-exact match fails) render as answer-level badges instead of line highlights. They remain visible; nothing is dropped.
- `review-flags.test.ts` gains the frame-of-reference cases: `line_quote` present-and-matching → correct line index; `line_quote` not matching → answer-level badge; offsets deliberately ignored (a fixture with misleading offsets must not influence the output).

---

## Δ7 — Flag behavior under edit *(feedback §2.7; amends plan §6 OD-4, §9)*

Ruled behavior, added to the `deriveReviewFlags`/editor spec:

- **`[?]` flags recompute live** against the current editor content (content-derived, cheap).
- **Span-derived (`reader_disagreement`) line flags render only while the answer's editor text is identical to the draft text.** On any divergence they **dissolve permanently for that answer** — the teacher editing the flagged region *is* the review the flag requested. No re-anchoring attempts, ever. (Per-answer, not per-line: divergence anywhere in the answer dissolves that answer's span flags — line indexes below an edit are unstable, and per-line survival would be re-anchoring by another name.)
- Dissolution is session-permanent per answer (tracked by the shell's per-item state; reverting text to the original does not resurrect flags — the teacher has demonstrably reviewed).
- `review-flags.test.ts` additions: unedited → span + `[?]` flags present; any edit → span flags gone while `[?]` flags track the live content (including a `[?]` typed *by the teacher* appearing as a new flag).

---

## Δ8 — Residue staleness horizon *(feedback §2.8; amends plan §6 OD-6 gate definition)*

- The residue line (copy in Δ13) appears when `now − batch.created_at > 10 minutes` **and** `rows < test_count`. Before the horizon, the residue renders as in-progress exactly as today.
- The constant lives in one named place: `UNTRANSCRIBED_RESIDUE_HORIZON_MS` in a frontend constants module (`frontend/src/lib/constants.ts`, new — or the existing config module if one is preferred at review time; either way one definition, imported, never inline).
- The gate/completion computation counts **rows only**, at every point in time — phantom (never-created) items are never reviewable, never traversable by the cursor, and never counted toward "everything reviewed"; they exist solely as the residue line.

---

## Δ9 — Phase 1.5: single-page rendering in the page proxy *(feedback §2.9; REPLACES plan §10 R2; inserts into §8; amends §6 OD-8 prefetch policy)*

R2 is withdrawn as a contingency and becomes a planned phase.

**Phase 1.5 — Backend: render only the requested page.** (Independently green diff between Phases 1 and 2.)

- **Files:** `backend/app/services/handwriting_transcription_service.py` — add `render_pdf_page(pdf_bytes, page_number, dpi) -> Image.Image` using the **same rasterizer** as today: `pdf_to_images` is pdf2image's `convert_from_bytes(pdf_bytes, dpi=dpi, fmt='PNG')` (`handwriting_transcription_service.py:L515-L519`), and `convert_from_bytes` accepts `first_page=n, last_page=n` — so the helper is the identical call bounded to one page. · `backend/app/api/v0/transcription.py` — the proxy (`:L197-L232`) calls `render_pdf_page(pdf_bytes, page_number, PAGE_RENDER_DPI)` instead of rendering all pages and indexing (`:L222-L225`); the 1-based bounds validation against `draft_json.page_count` (`:L208-L210`) is unchanged. · tests `backend/tests/api/test_transcription_page_render.py`.
- **Tests (as ruled):** correct page returned for first/middle/last page of a multi-page fixture PDF; 1-based bounds validation unchanged (0, page_count+1 → 404); equivalence of the single-page render vs. the current full-render-then-index implementation for the fixture — byte-equality of the PNG payload if poppler proves deterministic across the two call shapes, else pixel-equivalence (decoded-image comparison); the test asserts whichever the spike on the fixture establishes, stated in the test's docstring.
- **Invariants touched:** none — response shape, route, auth, and DPI unchanged.

**Prefetch policy, re-stated under the linear cost model** (amends §6 OD-8): with per-page rendering, one page request costs one page render — prefetching no longer multiplies a quadratic. New policy: on item open, fetch page 1 eagerly and **warm the item's remaining pages in the background** (sequential, low priority); on idle, prefetch **page 1 of the next item**. The cache stays per-item component/shell state as in the current panel (`TranscriptionReviewPanel.tsx:L147-L164`). Arrow-next should typically land on an already-warm first page. (Unbounded cross-item prefetch is still declined — Cloud Run CPU is shared with transcription/grading work.)

---

## Δ10 — Ordering: evidence, fix, and freeze *(feedback §3.1; amends plan §6 OD-8, §8 Phases 1–2, §9)*

**Evidence (the missing line ref — and it falsifies the original claim):** the batch-detail query has **no ORDER BY**: `select(Transcription).where(Transcription.batch_id == batch_id)` (`backend/app/api/v0/batch_grading.py:L260-L262`). Postgres row order without ORDER BY is unspecified and may change between polls. The original plan's "deterministic and stable across polls" was wrong; withdrawn.

**Fix, both layers:**
1. **Backend (Phase 1, one line in a file already in that diff):** add `.order_by(Transcription.created_at, Transcription.id)` to the batch-detail query — deterministic, immutable keys; `created_at` order is upload order, which is teacher-meaningful. (The graded_tests query at `:L264-L266` feeds a dict lookup and needs no ordering.)
2. **Cursor frozen at route entry (Phase 2):** the review shell computes the ordered, flagged-first-partitioned item list **once on route entry** and freezes it for the session. Verdicts and statuses changing as items get accepted must not reshuffle the arrows mid-review; newly-appearing rows (late transcriptions) join only on a fresh route entry. The frozen list is keyed by `transcription_id`, so item *state* (accepted, overlay) stays live while item *order* does not.

**Named test:** `cursor-order-frozen-under-refresh` in `batch-review-cursor.test.ts` — simulate a payload refresh that flips flag verdicts and statuses; assert the cursor order is unchanged and prev/next land on the same ids.

---

## Δ11 — The review route does not poll *(feedback §3.2; amends plan §7 architecture / OD-8)*

Stated as a constraint, not an implication: **the review route performs no polling.** It fetches the batch payload once on entry (and refetches only as a direct consequence of an explicit user action — e.g. after an accept, to reflect the new status). No poll-derived rerender may touch editor state; the editor's text state is owned by the shell and written only by keystrokes and hydration-on-item-entry. The dashboard (`/batches/[id]`) keeps its 3s poll (`[id]/page.tsx:L41`, `:L373-L385`); the poller is not shared, imported, or reachable from the review route. A background refresh clobbering an in-progress textarea edit is the canonical form of the bug this PR exists to kill; this constraint is verified by the `unsaved-changes-guard` journey plus a shell unit test (hydration occurs on item change only, never on payload identity change).

---

## Δ12 — Consolidated test-plan delta *(feedback §3.3; amends plan §9)*

Added to §9 (named as ruled):

| Test | Layer | From |
|---|---|---|
| `clean-item-edited-then-bulk-accept` | backend (pytest) | Δ1 |
| full-snapshot mismatched-key-set rejection (missing / extra / duplicate key → 422) | backend | Δ2 |
| overlay-nulled-at-approval — across **all three** approval paths, + PATCH 409 after | backend | Δ3 |
| `overlay-patch-suppressed-after-accept` | frontend unit (shell) | Δ4 |
| frame-of-reference cases for `deriveReviewFlags` (line_quote match / no-match / offsets ignored) | frontend unit | Δ6 |
| flag-dissolution-on-edit (span flags dissolve; `[?]` tracks live content; no resurrection on revert) | frontend unit | Δ7 |
| Phase-1.5 page-render suite (first/middle/last, bounds unchanged, render equivalence) | backend | Δ9 |
| `cursor-order-frozen-under-refresh` | frontend unit | Δ10 |
| no-polling hydration guard (hydrate on item change only) | frontend unit | Δ11 |

Stated-not-tested (written into the endpoint spec): overlay PATCH concurrency is last-write-wins (Δ2).

---

## Δ13 — Copy-table delta *(feedback §3.4; amends plan §7 copy table)*

| Context | String (1 / many / other) |
|---|---|
| Δ1 excluded-from-bulk count (CleanTestsPanel) | `מבחן אחד נערך ידנית — דורש אישור פרטני` / `{n} מבחנים נערכו ידנית — דורשים אישור פרטני` |
| Δ8 residue line (replaces the plan's provisional `{n} קבצים לא תומללו`) | `קובץ אחד לא תומלל` / `{n} קבצים לא תומללו` |
| Δ8 pre-horizon state | unchanged from today's in-progress rendering (no new string) |
| Δ9 Phase 1.5 | introduces **no** user-facing strings (existing proxy error strings unchanged: `שגיאה בטעינת הקובץ`, `שגיאה בעיבוד הדף`, `transcription.py:L218`, `:L230`) |

All additions follow the existing table's standards (1/2/many/0 pluralization via the `hebrew-plural` helper; nominal, gender-neutral forms).

---

## Δ14–Δ19 — Inline amendments per the Phase-1 GO ruling *(appended per that ruling; no PLAN_REVISION_2)*

### Δ14 — Dirty-gated autosave: viewing must never create an overlay *(amends Δ1 × Δ4 / OD-8)*
The flush-on-navigate autosave fires **only when the item is dirty**. Dirt = a keystroke in an answer editor or an explicit StudentPicker change by the teacher — nothing else. Hydration and the picker's `matched_student_id` pre-seed do **not** count as dirt. Rationale (the composed hole): an unconditional flush would mean a glance at a clean item creates an overlay, which per Δ1 silently removes it from the bulk-accept set with a "נערכו ידנית" label on an item never edited — inspection must not be commitment. **Named test (added to Δ12):** `view-without-edit-creates-no-overlay` (open clean item → arrow away with zero edits → no PATCH issued → item remains bulk-acceptable).

### Δ15 — Residue horizon is progress-based, not age-based *(AMENDS Δ8's trigger, by ruling)*
The residue line appears when `rows < test_count` **and** more than 10 minutes have passed since the **later of** (`batch.created_at`, the newest transcription row's `created_at`). A batch making progress never shows the line; a batch with no new row for 10 minutes is genuinely stuck. (The original age-since-creation rule false-alarms on any large batch whose bounded fan-out legitimately runs past 10 minutes.) Item-level `created_at` is exposed on the batch payload — additive field, **Phase 1**, alongside the `review` exposure already in that diff. Constant name/definition point unchanged from Δ8.

### Δ16 — PATCH validates `student_id` ownership at write time *(amends Δ2 endpoint spec)*
A non-null `student_id` in the PATCH body is ownership-validated at write time — the same `get_owned_or_404` check `/grade` performs (`transcription.py:L141`) — so a cross-tenant or stale id cannot sit in the overlay and detonate at accept. Cross-tenant → **404**, per the §9 convention. Cross-tenant-student case added to the Phase-1 suite.

### Δ17 — Dissolution memory is session-scoped: stated consequence *(amends Δ7; behavior statement, no change)*
Shell state dies on refresh. An answer edited (span flags dissolve), reverted to byte-identical draft text, then refreshed, shows its span flags again — the dissolution memory is gone and the text equals the draft. **Accepted behavior, not a bug:** flags rendered on text identical to the draft are truthful. Recorded so it is never filed as a defect.

### Δ18 — accept_clean response change: additive tolerance confirmed *(amends Δ1)*
Verified: the pre-Phase-4 client tolerates the additive skip field. `acceptCleanTranscriptions` parses with a plain `res.json()` under a TS cast (`frontend/src/lib/api.ts:L2470-L2485` — no strict/exhaustive parsing, unknown fields ignored at runtime), and its only caller ignores the response body entirely (`handleAcceptAll` awaits the call then invokes `onAccepted()`, `frontend/src/app/batches/[id]/page.tsx:L207-L225`). The Phase-1 response addition is safe before Phase 4 lands.

### Δ19 — Backlog: persist the anchor line index server-side *(from Δ6; recorded as BACKLOG B-17, not implemented)*
The backend already computes the answer/line anchor (`best_line_match` → `anchor_key`, `flagging.py:L300-L327`) and discards the line index, shipping only baseline-frame offsets. Persisting the matched answer-line index into `reader_disagreement` metadata would make client line-highlighting exact with zero fuzzy logic anywhere. Recorded in `BACKLOG.md` as **B-17** with the Δ6 line refs, tagged as prerequisite polish for any future two-phase-default switch.

---

## Definition-of-done mapping *(feedback §5)*

(1) Δ1 — exclusion rule, server enforcement point, named test. (2) Δ2+Δ3 — amended overlay spec: full snapshot, `reviewed` deleted, nulled-at-approval in all three paths with LCY-1 reasoning, 422 rejection semantics, last-write-wins stated. (3) Δ5 — seam rewritten as the ruled end state. (4) Δ6 — frame-of-reference finding with line refs (`flagging.py:L93-L94`, `:L99`, `:L214-L216`, `:L270-L274`, `:L300-L327`; `two_phase_engine.py:L183-L192`) and the respecified `deriveReviewFlags`. (5) Δ7 — dissolution rule. (6) Δ9 — Phase 1.5 file-by-file with tests + re-stated prefetch policy. (7) Δ10 — ordering evidence (no ORDER BY at `batch_grading.py:L260-L262`), backend fix + frozen-at-entry rule + test. (8) Δ11 — no-polling constraint. (9) Δ12 + Δ13 — consolidated test and copy deltas. Nothing else in the plan is reopened; §4's unchanged approvals are left untouched.
