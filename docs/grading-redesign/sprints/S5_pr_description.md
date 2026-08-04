# PR: S5 — PDF serving + side-by-side transcription review

**Sprint:** S5
**Depends on:** S4 (transcription `/transcribe` + `/grade`, GCS write side, review screen) — must be merged first
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §2.1.A (Transcription), OD2 (PDF persistence); S4 PR §2 (the S4/S5 read/write split)
**Frontend lockstep:** yes — this PR is primarily a frontend feature (the visual reference) plus one backend proxy endpoint

---

## 1. Summary

S4 uploaded the student's PDF to GCS (the write side) but left the review screen **text-only** — the teacher reviews transcribed text with no way to see the original handwriting. S5 closes that gap: it serves the stored PDF back as per-page images through an authenticated backend proxy, and renders them **side-by-side** with the transcription answers so the teacher can verify the VLM's output against the actual ink.

This is the feature that makes transcription review actually useful. Without it, the teacher is reviewing transcription text blind. With it, they compare answer-against-source and catch VLM errors quickly — which is the entire point of the human-review gate.

**The serving design is a backend proxy, not signed URLs.** Research established three independent blockers to signed URLs (no bucket CORS, unverified/never-executed IAM `signBlob` path, no expiry-refresh story — see §2). The proxy pattern sidesteps all three by fetching PDF bytes backend-to-backend and rendering thumbnails the frontend already knows how to display.

---

## 2. Why proxy, not signed URLs (the rejected design)

Recorded so this isn't relitigated. Signed URLs were the obvious first instinct; they're wrong for S5 pre-launch. Three independent blockers, any one fatal:

1. **No bucket CORS.** A signed URL points at `storage.googleapis.com` — a different origin from the frontend. The browser blocks the cross-origin fetch unless the bucket has CORS headers allowing the frontend origin. No CORS is configured, and fixing it is a `gcloud`/terraform change outside the codebase.
2. **IAM `signBlob` unverified.** The ADC signing path (`generate_signed_url`) has never executed in production. If the Cloud Run service account lacks `roles/iam.serviceAccountTokenCreator` on itself, signing fails at runtime with no fallback.
3. **No expiry-refresh story.** 60-minute hardcoded expiry, no re-sign endpoint, no client-side refresh. A long review session silently breaks.

The proxy pattern (`GET /transcriptions/{id}/pages/{n}` → backend fetches from GCS → renders → returns image) avoids all three: backend-to-backend GCS fetch has no CORS issue, no signing is involved, and there's no URL to expire. The only cost is backend bandwidth + CPU for thumbnail rendering — negligible for 1–3 page handwritten tests.

---

## 3. Scope

### In scope
- **Backend proxy endpoint** serving per-page PDF renders as images, on demand, at 150 DPI (§4).
- **Frontend side-by-side review layout** — transcription answers in one pane, the source page in the other; clicking an answer's page badge shows that page (§5).
- **Dead-code cleanup** — remove the now-orphaned streaming `TranscriptionReviewPage` and the no-op `onPagesReady` (§6).
- Tests (§7).

### Out of scope (explicitly deferred)
- **Signed URLs / bucket CORS / IAM signing.** Not pursued (§2). If a future feature genuinely needs direct browser-to-GCS access, that's its own infrastructure PR.
- **GCS object lifecycle / retention / cleanup.** Objects still accumulate (no delete policy). Noted as a known gap; not S5's job. A future cleanup job sweeps orphans.
- **Text-selectable PDF (pdf.js).** Handwritten tests are images of ink — there's no text to select. Thumbnails lose nothing here. pdf.js is not added.
- **Anything touching grading.** Still no agent (S6/S7/S8). S5 is purely the transcription review experience.
- **Per-page image storage in GCS.** Renders are produced on demand from the stored PDF, not pre-stored. (Storing per-page renders would be premature — on-demand render of a 1–3 page PDF is cheap.)

---

## 4. Backend — the page-serving proxy

### 4.1 Endpoint

`GET /api/v0/transcriptions/{transcription_id}/pages/{page_number}`

- **Auth:** `Depends(get_current_user)`.
- **Ownership:** `get_owned_or_404` on the transcription (must belong to `current_user`). This is the access gate — a teacher can only fetch pages of their own transcriptions.
- **Returns:** the rendered page image. Two viable response shapes — pick per the frontend's existing consumption pattern:
  - **(a) `image/png` bytes** with `Content-Type: image/png` — the browser can use it directly in `<img src={blobUrl}>` after fetching with the auth header. Cleaner HTTP semantics.
  - **(b) JSON `{ page_number, thumbnail_base64 }`** — matches the existing `PageThumbnail` / `generate_pdf_previews` pattern (base64 PNG in JSON), which the frontend already renders via `<img src="data:image/png;base64,...">`.

  **Recommendation: (b) base64 JSON**, because it reuses the shipped `PageThumbnail.tsx` rendering path unchanged and the frontend has no existing blob-fetch pattern (research Q11 — every current endpoint is JSON). Going with (a) means introducing a blob-fetch pattern (fetch → `arrayBuffer`/`blob` → object URL) that doesn't exist yet. Reuse the JSON+base64 path the codebase already knows. The payload cost (base64 is ~33% larger than raw) is acceptable for single-page on-demand fetches.

### 4.2 Flow

1. `get_owned_or_404` on the transcription.
2. Read `gcs_object_path` from the row.
3. Fetch the raw PDF bytes from GCS (backend-to-backend — use the existing `GCSService` download primitive; if none exists for "fetch bytes by object path", add a thin `download_bytes(object_path) -> bytes`).
4. Render **only the requested page** to a PNG at **150 DPI** via the existing `generate_pdf_previews` infrastructure (or the underlying `pdf2image` call it wraps). Render one page, not all — on-demand, page-at-a-time.
5. Return the base64 PNG (shape (b)).
6. Validate `page_number` is in range `[1, page_count]`; out of range → 404.

### 4.3 On-demand, single-page rendering

Render the requested page only — do not render and return all pages in one call. Rationale: the teacher views one source page at a time (the page a given answer came from). Single-page render keeps each response small (~1.3MB base64 for a 150 DPI page) and lets the DPI be generous without ballooning a multi-page payload. If `generate_pdf_previews` currently renders all pages, either add a single-page variant or call the underlying `pdf2image` with a `first_page=last_page=n` bound.

### 4.4 Caching consideration (optional, recommended)

Rendering the same page repeatedly (teacher clicks back and forth) re-fetches from GCS and re-renders each time. A small optimization: set HTTP cache headers (`Cache-Control: private, max-age=...`) on the response so the browser caches the page image for the session. The frontend should also cache fetched pages in component state (don't re-request a page already loaded). Both are cheap; the component-state cache is the more important one. Not a blocker — flag if it expands scope.

---

## 5. Frontend — side-by-side review

### 5.1 The layout change

The S4 `TranscriptionReviewPanel` is a single-column `max-w-3xl` scroll layout. S5 converts the review screen to **two panes side-by-side** (RTL: the orientation follows the existing RTL convention — answers and source pane arranged per what reads naturally in Hebrew):

- **Answers pane** — the existing review content (editable answer cards, annotations, student picker), in one column.
- **Source pane** — the rendered original PDF page, in the other column, visible simultaneously.

This is the frontend's first split-view layout (research Q12 — no existing primitive). Build it cleanly; it sets the precedent that S8 (graded-test review) will reuse for its own answer-against-source pairing. A simple two-column flex/grid with independent scroll on each pane is sufficient — no need for a resizable-splitter library unless one is trivially available.

### 5.2 Page selection interaction

The answer cards already display a page badge (`עמ׳ {page_numbers}`) — currently static text (research Q8). S5 makes it interactive:

- The badge becomes clickable. Clicking it sets `selectedPage` state and loads that page into the source pane.
- When the teacher focuses/clicks an answer card, the source pane shows the page(s) that answer came from (from the answer's `page_numbers`). If an answer spans multiple pages, default to the first and let the teacher page through.
- The source pane has simple page navigation (prev/next or a page selector) so the teacher can move through all pages independent of which answer is selected.

### 5.3 Rendering the page

Reuse `PageThumbnail.tsx` (renders base64 PNG via `<img>`). Fetch the page via the new API client method (§5.4), hold fetched pages in component state keyed by page number (don't re-fetch a page already loaded — §4.4).

A loading state while a page fetches (the proxy renders on demand, so there's a brief delay on first view of each page).

### 5.4 API client method

Add to `api.ts` (with `...getAuthHeaders()`):
- `getTranscriptionPage(transcriptionId, pageNumber)` → `{ page_number, thumbnail_base64 }`

Type in the appropriate types file.

### 5.5 RTL / responsive

- Side-by-side on wide screens. On narrow/mobile, the two panes can't sit side-by-side usefully — fall back to a stacked or toggleable layout below a breakpoint. (The research flagged ~3MB-for-3-pages as marginal on mobile; on-demand single-page fetch at 150 DPI mitigates this — only the viewed page loads.)
- Follow the existing RTL conventions of the review screen.

---

## 6. Dead-code cleanup (in scope per request)

Fold these into S5 since they live in the files S5 touches:

- **Remove the old streaming `TranscriptionReviewPage`** — dead for the handwritten path after S4 (research Q18). Confirm nothing still routes to it before deleting.
- **Remove the no-op `onPagesReady`** in `PdfProcessingPage` (research Q18).
- If removing these surfaces other now-orphaned imports/components, clean those too — but keep the cleanup bounded to what's genuinely dead. If the cleanup balloons beyond the review-flow files, stop and leave the rest for a dedicated cleanup pass (flag it).

---

## 7. Testing

### Backend
1. **Auth required** — `GET /transcriptions/{id}/pages/{n}` returns 401 without a token.
2. **Ownership** — user A fetching user B's transcription page returns 404.
3. **Happy path** — for an owned transcription, fetching page 1 returns a base64 PNG; the image is non-empty and decodes. (Use a real small test PDF fixture; the rendering is `pdf2image`, no external API — no mocking needed, but ensure the test environment has the `pdf2image`/poppler dependency available, same as the transcription service requires.)
4. **Out-of-range page** — fetching page 99 of a 3-page PDF returns 404.
5. **150 DPI** — assert the rendered image dimensions correspond to 150 DPI (or at least that DPI is the configured value — a constant the test can assert against).

### Frontend
- The review screen renders two panes; the answers pane shows the editable cards (unchanged from S4); the source pane renders a page image.
- Clicking an answer's page badge loads that page into the source pane.
- A page already fetched is not re-requested (component-state cache).
- Narrow-screen fallback renders without breaking.

---

## 8. Acceptance criteria

- [ ] `GET /transcriptions/{id}/pages/{n}` exists, auth-gated, ownership-scoped (404 cross-user), renders on demand at 150 DPI, returns base64 PNG JSON.
- [ ] Out-of-range page → 404; valid page → decodable PNG.
- [ ] Single-page rendering (not all-pages-per-call).
- [ ] Review screen is side-by-side: answers pane + source pane, both visible on wide screens.
- [ ] Answer page badges are clickable and drive the source pane.
- [ ] Source pane has independent page navigation.
- [ ] Fetched pages cached in component state; no redundant re-fetches.
- [ ] Narrow-screen fallback (stacked/toggle) works.
- [ ] Old streaming `TranscriptionReviewPage` and the `onPagesReady` no-op removed; no dead routes left behind.
- [ ] No signed-URL / CORS / IAM code introduced.
- [ ] All tests pass; `import app.main` succeeds; frontend type-checks.

---

## 9. Known follow-ups (do NOT do in this PR)

- **GCS object lifecycle / retention.** PDFs accumulate with no cleanup. A future job sweeps orphaned/old objects. Not S5.
- **S6** — `GradableTest` schema + compiler (consumes the `TranscriptionContract` + `RubricContract`).
- **S7** — the GraderAgent.
- **S8** — grading endpoint + the graded-test review screen, which **reuses the side-by-side layout S5 establishes** (answer + source pairing). Building the split-view cleanly here pays off there.
- **Signed URLs**, if ever needed for a direct-download feature, are a separate infrastructure PR (bucket CORS + IAM `signBlob` grant + verification + refresh story).

If the on-demand single-page render proves too slow in practice (GCS fetch + render latency per page click), the fallback is to render all pages once on first source-pane open and cache them — but start with on-demand single-page and only change if latency is a real problem. Flag if you observe it.
