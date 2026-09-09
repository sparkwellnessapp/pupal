# Batch upload latency — implementation plan, v2 (strict no-regression bar)

> Status: **APPROVED 2026-09-04 (owner) — ALL OPEN DECISIONS RULED; NOT STARTED.** Supersedes the
> diagnosis artifact "The 57 MB Wait" (2026-09-03). That artifact's measurements are kept and
> credited (§1); its five-stage plan is replaced by the stages in §3 because the owner set the bar
> at **zero regressions to existing features and zero change to what the transcription model sees
> without the eval gate proving non-inferiority first.** Every "verified" claim below was checked
> in the working tree, the live Cloud Run service, the live bucket, and the eval RUNLOG on
> 2026-09-03/04. Owner rulings are §0 and are the spec; deviating from one is an open decision,
> not an edit (CLAUDE.md §0.2, §0.3). The five questions that were open at approval time were
> ruled the same day (R9–R13); §4 keeps them as the record of what was asked and why.
>
> **IMPLEMENTED 2026-09-04/05: Stages A, B, C1 and D are in the working tree**, each followed by
> an independent adversarial review whose findings were fixed and pinned (§5 records what "done"
> meant for each). **Stage C2 is one `gcloud` flag and Stage E is a paid eval run —
> both are owner actions, listed in §8 and NOT performed from here.** Stage F remains conditional
> on E. Nothing in this plan has been deployed: the migration is applied to the TEST database
> only.

---

## 0. Owner rulings (the spec)

| # | Decision | Ruling |
|---|---|---|
| R1 | **The model's input is frozen.** | Nothing that changes the pixels the transcription model receives ships without the eval suite proving non-inferiority at k≥5 on every fixture and every repeat (CLAUDE.md §17). A passing single run is noise. |
| R2 | **No regression to existing features.** | The returned-exam PDF (stamp + appendix), the review page proxy, the thumbnail store, the identity pass, the eval suite's input path, the append idempotency and 422 verdicts all keep working unchanged. |
| R3 | **Decision 4 is superseded.** | "Auto-navigate only when everything landed" ([page.tsx:1063](../../frontend/src/app/page.tsx#L1063), [copy/batch.ts:225](../../frontend/src/copy/batch.ts#L225)) is replaced by "navigate on create; the upload continues in the background; failures surface on the dashboard with the same reasons and the same retry." |
| R4 | **Byte reduction (the artifact's Stage 2) is deferred until proven.** | It becomes a research run (§3 Stage E). Only a setting that clears R1 becomes a schedulable feature (Stage F), and then only as **JPEG pages inside a PDF** produced in the browser. **WebP is ruled out for the stored artefact** (§1.4). |
| R5 | **The service split (the artifact's Stage 3) is replaced by two cheaper fixes.** | Encode off the event loop + 2 vCPU (§3 Stage C). A second Cloud Run service is revisited only if the append tail persists after both (§6). |
| R6 | **Direct-to-GCS signed uploads (the artifact's Stage 4) are dropped.** | Rebuilds validation and idempotency the append path already has, for ~2 s per batch by the artifact's own numbers. |
| R7 | **"Page images become the primitive" (the artifact's Q2) is dropped.** | Largest blast radius in the plan: pipeline input, page proxy, thumb store, returned exam, eval-suite input. |
| R8 | **The 2 MB resumable GCS chunk policy stays.** | It was set after a real lost transcription ([gcs_service.py:21](../../backend/app/services/gcs_service.py#L21)). After Stage F every file fits one chunk anyway. |
| R9 | **A file that never lands (was D1).** | **Client re-declares** `expected_test_count = landed + still-queued` on every terminal event (422, "remove"). **Server backstop:** if `uploading > 0` and the batch has had no append for `UPLOAD_DECLARATION_TTL_MINUTES` (90, the dispatch-TTL precedent), the missing count is reported as `not_received` (its own rollup field, a fact by omission) and counted like a dead doc, so `_derive_batch_status` yields `partially_completed` in today's vocabulary rather than an eternal `in_progress`. **Never silently lower `expected`.** |
| R10 | **Second batch while one is uploading (was D2).** | **One uploading batch at a time** in this release: the upload page shows a banner with a link to the in-flight batch and does not start another. Lift later only on teacher evidence. |
| R11 | **Transport for the client-observed upload duration (was D3).** | The `X-Upload-Started-Ms` request header on each append. Coarse, skew-tolerant, **log only** — nothing acts on it. |
| R12 | **The returned exam after Stage F (was D4).** | **Accept 200 DPI second-generation JPEG pages.** The artefact the teacher sends each student **remains one PDF with every page inside** (stamp on page one + feedback appendix, both vector, unchanged) — Stage F builds a real PDF in the browser; "loose images" was the dropped R7 path. Rationale recorded: no visible difference on screen, marginal in print; the per-student PDF and the class ZIP shrink by the same ratio as the upload (roughly 1 MB and 30 MB instead of 3–10 MB and ~200 MB), which is a UX gain for emailing/WhatsApp on the same weak link. **Acceptance step (approved, in Stage F's DoD):** before the flag goes on, render one repacked returned exam, print it, and put it beside the original; ship only if they cannot be told apart. If they can, the fallback is a repack that keeps the original resolution and only re-encodes (smaller savings, still a single PDF, still eval-gated). **"Upload both" (repacked for the pipeline, original for the return) is rejected** — doubles bytes and storage, two objects and two cache keys per document, and the return cannot render until the original lands. |
| R13 | **The 2 vCPU per-document cost (was D5).** | **Accepted.** About a tenth of a cent per document at list price; nothing when idle. Stated here so it is never a surprise on the bill. |

---

## 1. What was verified (the diagnosis, condensed)

### 1.1 The artifact's measurements — credited, not re-measured

| Fact | Value | Source |
|---|---|---|
| Bytes per 10-test batch today | 57.2 MB (66 pages, ~260 DPI RGB JPEG per page) | artifact §Evidence 1, 3 (GCS census n=198) |
| Same pages re-encoded at 200 DPI WebP q72 | 7.4 MB | artifact §Evidence 3 |
| Measured teacher uplink | 3.67 Mbps on a live 8-file batch; ~2 Mbps reproduces the reported 4–6 min | artifact §Evidence 2 |
| Appends that overlap a transcription job on the same instance | 0.43 s → 5.3 / 5.9 / 15.6 s | artifact §Evidence 2 (Cloud Run request log 2026-08-24) |

### 1.2 Verified live (2026-09-03)

| Claim | Verified value |
|---|---|
| Cloud Run `gradervision-backend` | `cpu=1000m`, `memory=2Gi`, `containerConcurrency=4` |
| Bucket CORS | `http://localhost:3000`, `https://pupal.vercel.app` only — stale vs `vivi-assistant.com` (matters only for R6, which is dropped) |
| Live bucket name | `grader-vision-pdfs-0438328890`. CLAUDE.md §12 and `config.py` default say `grader-vision-pdfs` (404s). **Doc drift — fix in §7.** |

### 1.3 Verified in code

| Claim | Where | Note |
|---|---|---|
| Pipeline rasterizes at 200 DPI | [two_phase_engine.py:115](../../backend/app/services/transcription/two_phase_engine.py#L115) | `PROD_CONFIG.dpi=200` |
| **The model does NOT see 200 DPI.** Pages are resized to a **2000 px long edge** | [pipeline.py:106](../../backend/app/services/transcription/two_phase/pipeline.py#L106) `image_max_px=2000` | ≈171 DPI on A4. The honest "parity" target for any re-encode is 2000 px long edge, not 200 DPI. |
| Wire format to P1 is PNG | [pipeline.py:155](../../backend/app/services/transcription/two_phase/pipeline.py#L155) (`PROD_CONFIG` does not override) | see §1.4 |
| PDF render runs in the executor | [pipeline.py:417](../../backend/app/services/transcription/two_phase/pipeline.py#L417) | off the loop ✔ |
| **Resize + PNG encode + base64 run ON THE EVENT LOOP** | [pipeline.py:343](../../backend/app/services/transcription/two_phase/pipeline.py#L343) (`_phase1_chunk`), again at [pipeline.py:529](../../backend/app/services/transcription/two_phase/pipeline.py#L529) (strike check, every page a second time) | PNG measured 1269 ms / 6 pages in the encoder docstring. On 1 vCPU with 4 concurrent job requests this starves appends — the cheap half of Defect C. |
| Identity crop renders page 1 at 200 DPI in a threadpool | [identity.py:42](../../backend/app/services/transcription/identity.py#L42), `_extract` | unaffected by anything here |
| Batch is created with `test_count=0`; appends increment it; rollup `total = len(jobs)` | [batch_grading.py:417](../../backend/app/api/v0/batch_grading.py#L417), [:528](../../backend/app/api/v0/batch_grading.py#L528), [:192](../../backend/app/api/v0/batch_grading.py#L192) | Defect D is real: a batch cannot say "still uploading". `BatchRollup.total`'s comment "= batch.test_count" ([schemas/batch.py:91](../../backend/app/schemas/batch.py#L91)) is stale. |
| Redirect gated on the last byte | [page.tsx:1063](../../frontend/src/app/page.tsx#L1063) `settleUploadQueue` → `allDone(s)` | Defect B is real, and it is a named decision (R3). |
| Three poll gates key off `transcribing` only | [batch-dashboard.ts:192](../../frontend/src/utils/batch-dashboard.ts#L192) `pollCadenceMs`/`completionReached`; [BatchReviewContext.tsx:153](../../frontend/src/components/batch-review/BatchReviewContext.tsx#L153); [batch-list.ts:93](../../frontend/src/utils/batch-list.ts#L93) | all three must learn `uploading` (Stage A) or the dashboard stops refreshing while files still land |
| Returned exam opens the stored PDF as-is | [returned_exam.py:329](../../backend/app/services/returned_exam.py#L329) `render_returned_exam(original_pdf)` | **whatever the browser uploads is what the student gets back** (stamp + appendix are vector, unaffected) |
| Review page proxy: 150 DPI PNG; card thumb: WebP 600 px @110 DPI | [transcription.py:52](../../backend/app/api/v0/transcription.py#L52), `thumbnail.py` | both rasterize from the stored PDF; unchanged by a JPEG-page PDF |
| Eval runner reads `pdfs/*.pdf` from a hardcoded dir | [runner.py:174](../../backend/tests/transcription_eval_suit/runner.py#L174) | Stage E needs a `--pdf-dir` flag (runner plumbing, allowed by §17.10) |

### 1.4 Two facts the artifact did not have — they reshape Stages 2 and 3

1. **A milder compression change than the artifact proposes already FAILED the gate.** RUNLOG
   2026-08-19 ([RUNLOG.md:72](../../backend/tests/transcription_eval_suit/RUNLOG.md#L72)): PNG → JPEG
   q90 on the wire to P1, paired A/B, p1_only k=3 × 5 docs: dan ratio 0.9334 < gate; yonatan
   structural floor .9962→.9731 and method-call floor .8824→.8529. Declined despite payload −75% and
   p1_call −40%. (Caveat recorded there: k=3, an AI-Studio daily quota of 250 req/day cut the
   run; a k=5 rerun was the top follow-up and never happened. ⚠ The 250-req/day cap that cut that run short was **AI Studio**; the transcription models have since moved to **Vertex** (`GOOGLE_GENAI_USE_VERTEXAI=true`, key commented out), whose quotas are per-minute. That caveat is history, not a current constraint.) WebP q72 + a resample is a far larger
   perturbation than JPEG q90. **The 7.7× figure is a hope until the gate says otherwise.**
2. **PDF cannot hold WebP, and the deployed PyMuPDF 1.25.5 cannot even read it.** Tested in the
   backend venv 2026-09-03: `fitz.Pixmap(webp)` and `page.insert_image(stream=webp)` both raise
   `FzErrorFormat: unknown image file format`. **JPEG embeds byte-for-byte** (`DCTDecode` present,
   no transcode). So WebP forces either a server transcode (a third lossy generation + ~1.3 s/doc
   CPU on the starved box) or R7. JPEG-in-PDF forces nothing.

---

## 2. The rule that shapes the plan

There is **no lossless way to shrink these files**: the pages are already JPEGs, and a lossless PNG
of a rasterized page is larger, not smaller (~1.1 MB/page). Any client-side re-encode changes the
pixels the model receives — a different resampler, then new codec artifacts. So under R1 every
byte-reduction idea is an eval question first and a feature second (Stage E before Stage F).

The biggest **felt** win does not need bytes: once the redirect stops waiting for the last byte,
the teacher's perceived wait is about one second on any link (the artifact's own conclusion), and
the first transcription is reviewable shortly after its own file lands. Stages A–C deliver that
with zero model-input change. What they do **not** deliver is "ten tests fully landed in 30 s" on a
2 Mbps link — that stays ~4 min until Stage F proves itself (§6).

---

## 3. Stages

Ordered so each ships and pays on its own. **A → B → C → D** are the approved release. **E** is
research. **F** is conditional on E.

### Stage A — a batch can say "still uploading" (amends the artifact's Stage 0)

*Backend + migration + frontend types. No model-input change. Prerequisite for B.*

- **Migration 025** `025_batch_expected_test_count.sql`: `grading_batches.expected_test_count
  INTEGER NULL` (NULL for every pre-025 batch → rollup arithmetic is bypassed for them, so history
  is untouched). Idempotent (`ADD COLUMN IF NOT EXISTS`); ends with its commit token; add `'025'` to
  `EXPECTED_MIGRATIONS` in `app/database.py`.
- `BatchCreateRequest.expected_test_count: int` (≥ 0). `create_batch` persists it. It is
  **re-declarable**: `PATCH /batches/{id}` accepts `expected_test_count` (owner-scoped, ≥ current
  `COUNT(jobs)`), which is how the client handles a file that will never land (R9). The R9
  server backstop (`UPLOAD_DECLARATION_TTL_MINUTES`, `not_received`) lives in the same rollup
  builder, computed from `updated_at`-style facts, never stored (the liveness precedent).
- Rollup: `BatchRollup.uploading: int = 0` = `max(0, expected − len(jobs))` when `expected` is
  not NULL; the `total` reported to the client becomes `expected` when declared (the honest
  denominator), `len(jobs)` otherwise. Fix the stale `total` comment while there.
- `_derive_batch_status`: **refuses `completed` and `partially_completed` while
  `uploading > 0`** → `in_progress`. This is the "in flight is a fact, never inference over
  absence" doctrine applied to the upload stage.
- Frontend: regenerate `api-types.ts` (`npm run gen:api`); extend the three poll gates
  (`completionReached`/`pollCadenceMs`, `BatchReviewContext` line 153, `listActionLine`) to treat
  `uploading > 0` as in-flight; the dashboard's honesty bar gets an `uploading` segment; the list's
  action line says "N files still uploading" (copy through `check:copy`, feminine imperative).
- **Tests:** `tests/api/test_batch_grading.py` — `uploading > 0 ⇒ status == 'in_progress'` even
  with every landed doc approved; pre-025 batch (`expected` NULL) rollup byte-identical to today;
  `PATCH` refuses `expected < COUNT(jobs)`. Frontend vitest for `pollCadenceMs` and
  `listActionLine` with `uploading`. e2e: `batch-dashboard-matrix.spec.ts` gains an "uploading"
  cell.

**Buys:** correctness only. Without it Stage B ships a batch that claims to be finished while nine
files are still climbing the wire.

### Stage B — redirect on create; upload in the background (the artifact's Stage 1, under R3)

*Frontend only. No backend risk. This is the change the teacher feels.*

- New `src/contexts/UploadQueueProvider.tsx`, mounted in `src/app/layout.tsx` inside
  `AuthProvider`. It owns what `page.tsx` owns today: the U3 reducer state, the `File` handles
  (references, not bytes), the abort handles, `pumpUploads`, `classifyUploadError`, and the
  `beforeunload` guard. **`utils/batch-upload.ts` is untouched** — the reducer, the
  `client_file_id` lifetime (minted once per selected file, reused by retries — B9), and the
  "422 is terminal" rule move house, they do not change.
- `page.tsx` calls `createBatchMetadata(…, expected_test_count = files.length)`, hands the files
  to the provider, and `router.push('/batches/{id}')` **immediately**. `settleUploadQueue`'s
  navigation branch is deleted; the "explicit continue" affordance and its copy are retired.
- `batches/[id]/page.tsx` renders an **upload lane** from the provider for its own batch id:
  per-file progress, terminal failures **with the same §3.2 reasons and the same retry button**
  (same `client_file_id`), and a "remove" for a rejected file that triggers the R9 re-declare.
  Uploads for a batch the teacher is not looking at keep running.
- **One uploading batch at a time (R10).** While the provider holds an in-flight queue, the upload
  page renders a banner with a link to that batch and does not start another. The provider is
  therefore single-queue in this release; no interleaving semantics exist to test.
- Known limits, stated not hidden: a **hard** navigation (full reload, the session-expiry
  stash-and-logout in `lib/session.ts`, `OnboardingGate`) still kills in-flight XHRs. The
  `beforeunload` guard covers the reload; the logout flow must consult the provider and warn
  before navigating (one `if`). Mid-session expiry is already effectively unreachable (48-h renew
  window), so this is a guard, not a path.
- **Tests:** e2e `batch-upload-journeys.spec.ts` — navigation on create; XHRs **not** aborted by
  the route change (assert the mocked appends complete after the push — the artifact's central
  claim, pinned); a 422 mid-batch surfaces on the dashboard lane with reason + retry; retry reuses
  the same `client_file_id`. `batch-review-freeze.spec.ts` stays green (the cursor lives in the
  review layout; the provider lives above it — no reshuffle).

**Buys:** perceived wait 241 s → ~1 s on any uplink (artifact's number, unchanged by this plan).

### Stage C — CPU relief without touching model input (replaces the artifact's Stage 3, under R5)

*Backend plumbing + one Cloud Run flag. Zero change to the bytes the model receives.*

- **C1 — encode off the loop.** In `_phase1_chunk` ([pipeline.py:343](../../backend/app/services/transcription/two_phase/pipeline.py#L343))
  and the strike-check encode ([pipeline.py:529](../../backend/app/services/transcription/two_phase/pipeline.py#L529)),
  wrap the existing `_resize` + `_to_b64_image` (+ `_stitch`) calls in
  `await loop.run_in_executor(None, …)`. **Same functions, same arguments, same bytes, different
  thread.** Pillow releases the GIL inside its resize/encode loops, so this is real relief even on
  one core.
  **Test (the byte-identity guard, precedent `tests/api/test_transcription_page_render.py`):** for
  a fixture page, the base64 produced by the executor path equals the base64 produced by calling
  the encoder inline. This is the R1 proof for C1.
- **C2 — 2 vCPU.** `gcloud run deploy … --cpu=2` (existing env preserved). One flag; no code.
  Cloud Run bills vCPU-seconds only while requests are in flight, so idle cost is unchanged;
  per-document cost rises by roughly one extra vCPU × job duration — **about a tenth of a cent per
  document at list price**, negligible next to the LLM spend per document (accepted, R13). Record
  the dial in `SCALING_ROADMAP.md`'s table (§7).
- **Measure before and after** with Stage D's log line: the append p50 and p95 on an instance that
  is also running a transcription. Kill criterion for "C is enough": the contended-append p95
  stays above ~2 s after C1+C2 across a week of real batches → §6 reopens the split.

**Buys:** the artifact's append tail (15.6 s outliers) and the transcription slowdown
(20–27 s → 44–59 s under overlap), without a second service to keep in sync.

### Stage D — instrumentation (the artifact's own "one cheap step")

- The client stamps each append with `X-Upload-Started-Ms` (its own `performance.timeOrigin +
  now()` at XHR open). The server logs `batch_file_appended` with `bytes`, `client_elapsed_ms`
  (`now − header`, coarse, skew-tolerant), and the derived Mbps. **Log only, never act on it
  (R11).**
- Purpose: turn "one teacher at 3.67 Mbps and an inferred 2 Mbps" into a fleet distribution.
  This is what decides whether Stage F is worth its eval risk at all.

### Stage E — the byte-reduction research run (the artifact's Stage 2, demoted to research under R4)

*Nothing ships from this stage. It answers one question: is there a JPEG-in-PDF re-encode that is
non-inferior on every fixture, every repeat?*

- **The variant corpus must be produced by the encoder that would ship.** A browser's JPEG encoder
  (Skia) is not Pillow's (libjpeg-turbo): different quantization → different bytes → an eval on
  Pillow output measures nothing about production. So: write the client transform first as a pure
  utility (`src/utils/page-repack.ts`: pdf.js render at 200 DPI → `canvas.toBlob('image/jpeg', q)`
  → pdf-lib embeds each JPEG as a page of the same size), and drive it under **Playwright/Chromium**
  (the artifact already benchmarked this way) to write `pdfs-variants/<setting>/*.pdf` from the ten
  fixtures in `tests/transcription_eval_suit/pdfs/`. The utility does **not** get wired into the
  upload flow in this stage.
- Candidates, one variable each (§17.3): `jpeg@200dpi q95`, `q90`, `q85`. (Lower qualities are not
  candidates: the August evidence says q90 was already marginal.)
- Runner plumbing (allowed, §17.10): `--pdf-dir` on `runner.py` (default unchanged). **Nothing
  under `raw_benchmarks/`, `draft_benchmarks/`, `scoring.py`, `normalize.py`,
  `critical_tokens.py`, thresholds, or `check_goal.sh` is touched (§17.7).**
- Protocol: paired `p1_only`, `--repeats 5`, champion vs each candidate, same config otherwise
  (exactly the 2026-08-19 protocol, at the k it was missing). Then **one** `check_goal.sh` on the
  best candidate that held on every fixture and every repeat.

  **Measured scale** (recorded per-record costs, `results/20260823_164702_v0_p1_only` and
  `results/20260821_141039_v0`): **~$0.029 per document-run for `p1_only`, ~$0.031 end-to-end**.
  So the A/B (10 docs × 5 repeats × 4 arms = 200 runs) is **≈$6**, the gate (15 fixtures × 5 =
  75 runs) is **≈$2**, and the whole stage lands near **$10 including a rerun**. Wall clock is
  hours, not days: the binding limit is the scheduler's `PROD_MAX_CONCURRENT_PER_MODEL=5` against
  a ~19 s P1 call, and the models run on **Vertex** (per-minute quotas), not AI Studio.
- **Outcome routes:** every fixture/every repeat non-inferior → Stage F is schedulable at that
  setting, with the measured ratio (expect 3–5×, not 7.7×). Anything less → Stage F is off the
  roadmap; the RUNLOG entry closes it. Either way, the run is appended to RUNLOG.md (§17.6).
- **STOP-and-surface** applies verbatim (§17.7): a suspected GT typo, a "too strict" gate, or the
  temptation to try q80 "just to see" are surfaced, not acted on.

### Stage E — STATUS 2026-09-05: RUN (k=3 diagnostic). No arm is shippable; one is worth finishing.

**The diagnostic ran** — $1.96, 60 document-runs, four arms. Full record in
`tests/transcription_eval_suit/RUNLOG.md`; re-read with
`python -m tests.transcription_eval_suit.tools.compare_repack_arms`.

| arm | valid | accuracy vs champion | median doc latency | cost/doc | verdict |
|---|---|---|---|---|---|
| champion | 15/15 | — | 52.2 s | $0.0299 | baseline |
| q95 | **12/15** | 1 doc regressed | 71.1 s | $0.0412 | NOT PROMISING |
| q90 | 15/15 | all within ±0.005 | **13.6 s** | $0.0296 | PROMISING (floors moved) |
| q85 | 15/15 | 1 doc regressed (−0.0059) | **14.0 s** | $0.0299 | NOT PROMISING |

**q95 died of `MAX_TOKENS`, not blur** — 3 truncated records where the champion had none. For this
corpus q95 output is LARGER than the source, so the model got more image, thought longer, and spent
its output budget before answering. A bigger picture is not a better one.

**⚠ RETRACTED — the "~3.7× faster reading" was a TIME-OF-DAY ARTIFACT, not a corpus effect.**
The k=5 champion re-run settles it: the SAME corpus with the SAME config measured **52.2 s median
at 17:21 and 11.2 s median at 21:53**, a 4.7× swing with nothing changed — larger than the speedup
that was credited to the re-encode. Provider latency improved between the second and third arm,
and because the arms ran SEQUENTIALLY with the champion FIRST, the whole confound loaded onto the
champion and manufactured the result.

The rule to take from it: **a latency comparison across sequential arms is worthless against a
provider whose latency moves on its own.** The 2026-08-19 run avoided this by being a true paired
A/B — one render per repeat, encoded both ways, so both arms shared a moment in time. Any future
comparison that intends to measure TIME must interleave the arms or re-run the champion next to
each one. The ACCURACY findings are unaffected; accuracy is not time-dependent. Full record in
`RUNLOG.md` under the 2026-09-05 retraction.

**But nothing here is decisive, for a reason no amount of k fixes** (see the coverage limit below):
the only scorable documents are the five this transform would DECLINE to touch in production.

### Stage E — the tooling (built 2026-09-05)

The transform (`frontend/src/utils/page-repack.ts`), its browser acceptance tests
(`e2e/page-repack.spec.ts`, 4 passing in real Chromium), the corpus generator
(`frontend/scripts/build-eval-corpus.mjs`) and the runner's `--pdf-dir` flag are all in the tree.
`results.json` now records `pdf_dir`, so a variant run can never be mistaken for the champion.
45 variant PDFs are written under `tests/transcription_eval_suit/pdfs-variants/` with a manifest.

**And the corpus build already answered part of the question, for $0.**

| quality | bagrut (10 docs, the artifact's corpus) | hobby (5 docs) | all 15 | docs made BIGGER |
|---|---|---|---|---|
| q95 | 57.2 → 36.1 MB (1.6×) | 11.6 → 22.1 MB (**0.5×**) | 1.18× | 6 |
| q90 | 57.2 → 25.8 MB (2.2×) | 11.6 → 15.9 MB (**0.7×**) | 1.65× | 6 |
| q85 | 57.2 → 20.8 MB (2.8×) | 11.6 → 12.9 MB (**0.9×**) | 2.04× | 5 |

Two findings, neither of which needed a model call:

1. **The 7.7× was WebP's number, and WebP is ruled out.** On the same fixtures, JPEG-in-PDF at
   q90 gives **2.2× on the bagrut set**, not 7.7×. The gap is codec plus quality level: the
   artifact measured WebP at q72, and R4/§1.4 rule WebP out because a PDF cannot carry it. So
   Stage F's ceiling is roughly **2–3×, not 7.7×** — a 10-test batch goes from ~4 minutes to
   ~1.5–2 on a 2 Mbps link, not to 30 seconds.
2. **Re-encoding HURTS documents whose scans are already compressed harder than our output.**
   All five hobby fixtures came out larger at every quality, and so did one bagrut document.
   ⚠ The tempting explanation — "those scans are below 200 DPI, so we upsample them" — is FALSE,
   and was checked: both sets scan at ~255–282 DPI. What actually happens is that the transform
   normalises every page to a roughly CONSTANT ~400–600 KB at q90, so a heavier original shrinks
   and a lighter one grows:

   | set | KB/page before | KB/page after (q90) | ratio |
   |---|---|---|---|
   | bagrut (10 docs) | 892 | 406 | 2.2× |
   | hobby (5 docs) | 442 | 606 | 0.73× |

   The decider is the scanner app's own compression, which varies per teacher — so the SPREAD of
   savings across a real fleet is much wider than one corpus suggests. `chooseSmaller` (same
   module) is the guard: keep the original whenever the repack is not smaller. It caps the damage
   at zero and lifts the whole-corpus q90 figure from 1.65× to 1.86× purely by declining to hurt.
   A document that keeps its original is the champion input byte-for-byte and needs no accuracy
   evidence.

**⚠ A COVERAGE LIMIT THE PLAN DID NOT ANTICIPATE, found while running it.** The transcription
suite has P1 ground truth for **five documents, all `hobby_tvshow`** — `raw_benchmarks/` holds
exactly those five. The ten bagrut PDFs are present but have no transcription ground truth (the
bagrut GT that exists belongs to the GRADING and RUBRIC suites), so `--mode p1_only` cannot score
them at any k or any cost. Consequences, stated plainly:

* The eval measures accuracy **only on the five documents that `chooseSmaller` would decline to
  transform**, since all five grow under every quality tested. Nothing it scores is a document
  Stage F would actually repack.
* The evidence is therefore ASYMMETRIC, and worth reading that way: a FAILURE on the hobby arm is
  strong evidence against Stage F, because those documents get the GENTLER perturbation (442 →
  606 KB/page, i.e. more bytes than the original). A PASS is weak evidence for it, because the
  bagrut documents would get the harsher one (892 → 406 KB/page) and are unmeasured.
* Closing this properly needs new P1 ground truth for bagrut documents — teacher-verified verbatim
  transcriptions, which is owner work and not a code task. Until that exists, Stage F cannot be
  evidence-backed for the population it targets, whatever this run says.

**What this changes about the decision.** The upside is real but roughly a third of what the
diagnosis promised, and the teacher already stopped waiting when Stage B shipped — so what Stage F
now buys is bytes, storage and weak-link robustness, not felt latency. The paid run is still worth
its ~$10 to answer the accuracy question honestly, but it is no longer plausibly a 30-second batch.

### Stage F — JPEG-in-PDF in the browser (conditional on E; D4 ruled as R12)

*Only if E passes. Frontend only; backend contracts untouched by construction (§1.4 fact 2). The
artefact the student receives stays one PDF with every page inside (R12).*

- **Acceptance step (R12, approved):** before `USE_CLIENT_REPACK` goes on in production, render
  one repacked returned exam through the real `render_returned_exam` path, print it, and put it
  beside the original scan's returned exam. Ship only if they cannot be told apart. If they can,
  the fallback is a repack that keeps the original resolution and only re-encodes — smaller
  savings, still a single PDF, and it goes back through Stage E's gate as a new candidate.

- Behind `src/lib/flags.ts::USE_CLIENT_REPACK` (default `false`; the flag-flip-and-deploy
  precedent of `USE_DOCUMENT_MIRROR`).
- The provider runs `page-repack.ts` pipelined against uploads (document i+1 encodes while i is on
  the wire). JPEG at 43 ms/page needs **no worker pool** and works on phones and Safari (WebP
  encoding does not exist there). **If pdf.js fails to render a document, the original file is
  uploaded** — never block a teacher on a codec (§3.5a: degrade by omission).
- The server sees a PDF exactly as today: same `%PDF-` check, same size ceiling, same `422`
  vocabulary, same GCS path, same job row. The pipeline rasterizes it at 200 DPI as today (a JPEG
  page at 200 DPI renders 1:1). The returned exam, page proxy, thumb store and identity pass read
  it unchanged.
- **Tests:** vitest golden — for a fixture PDF the repacked page count, page sizes and the embedded
  stream type (`DCTDecode`) are asserted; e2e — the flag off produces today's upload bytes exactly.

---

## 4. Open decisions — ALL RULED 2026-09-04 (the record; the rulings themselves are §0 R9–R13)

None remain open. Kept so the question each ruling answers is not lost.

| # | Question that was open | Outcome |
|---|---|---|
| D1 | How a file that never lands (422-rejected, tab closed mid-upload, teacher gave up) stops blocking completion. | Recommendation approved as written → **R9**. |
| D2 | A second batch started while the first is still uploading. | Recommendation approved as written → **R10**. |
| D3 | Transport for Stage D's client-observed duration. | Recommendation approved as written → **R11**. |
| D4 | The student's returned exam after Stage F is a second-generation 200 DPI JPEG, not the original scan. | Owner consulted on the UX concern that the teacher must be able to send each student **one PDF with all pages** — clarified that Stage F preserves exactly that (the "images" path was the dropped R7); the real tradeoff is page quality vs. bytes, and the only way to keep the original is not to shrink the upload at all or to upload twice. **Ruled: accept 200 DPI second-generation JPEG, with the print-comparison acceptance step in Stage F's DoD** → **R12**. |
| D5 | Accept the 2 vCPU per-document cost. | Recommendation approved as written → **R13**. |

---

## 5. Definition of done, per stage

| Stage | Done when |
|---|---|
| A | **DONE 2026-09-04** (test DB; production migration not yet applied — see §9). Migration 025 applied to the test database, ledger at 025, `verify_schema_head()` returns `SCHEMA OK`, whole file re-runs clean (idempotent). Backend: 23 new tests + 84 existing batch tests green. Frontend: 1050 unit tests green (32 new), 63 batch e2e green, `check:copy` green, `tsc --noEmit` clean, `import app.main` + `pytest --collect-only` (1341) clean. Pre-025 batches render byte-identically — proven at the wire by the regenerated `batch_feed_*.json` fixtures, whose entire diff is the two new fields at 0. All three poll gates count `uploading`. |
| B | **DONE 2026-09-05.** The queue lives in `contexts/UploadQueueProvider.tsx`, mounted in the root layout; `handleGradeAsBatch` creates, hands off and navigates. e2e pins the central claim — the appends COMPLETE AFTER the route change — plus the 422 verdict verbatim with no retry, a network retry reusing the same `client_file_id`, R10's refusal linking to the live batch, and the dismiss settling the declaration. `batch-review-freeze.spec.ts` green; 65 batch e2e green; `check:copy` and `check:tokens` green. |
| C | **C1 DONE 2026-09-05** — both encode sites (P1 chunk + the strike-check second pass) run in the executor, pinned by a byte-identity test across 6 format×size combinations plus an event-loop-responsiveness test. **C2 NOT DONE**: `--cpu=2` is a `gcloud run deploy` flag, listed in §8 as an owner action. |
| D | **Code DONE 2026-09-05** — the client stamps `X-Upload-Started-Ms`, the server logs `bytes` + `uplink_kbps` on `batch_file_appended`, and drops the figure rather than fabricating one whenever the arithmetic is unsound (9 pure tests). **Not yet in prod**; the first distribution still owes §9. |
| E | RUNLOG entry with per-fixture, per-repeat results for each candidate, and a one-line verdict: "F schedulable at q=…" or "F closed". |
| F | Stage E verdict "schedulable" on file; vitest golden + e2e green; **the R12 acceptance step done and recorded here: one repacked returned exam printed beside the original, judged indistinguishable by the owner**; only then the flag goes on in prod. |

Sanity gate before any "done": `python -c "import app.main"`, `pytest --collect-only`, frontend
type-check (CLAUDE.md §12).

---

## 6. What this plan deliberately does not do

- **The wall-clock target is not met by A–D.** Ten tests fully landed on a 2 Mbps link still take
  ~4 min. The teacher does not wait for it (she is reviewing the first transcription), but the
  number is what it is until Stage F proves itself. This is the honest trade under R1.
- **No service split (R5).** Revisit trigger: contended-append p95 > ~2 s after C1+C2 over a week
  of real batches. If reopened: `JobKind` gains a per-kind `base_url`, the OIDC audience follows,
  and **both services' env vars must be diffed on every deploy** — the production pins live in
  service env vars (CLAUDE.md §12), and a second copy is a drift waiting to happen.
- **No direct-to-GCS (R6), no page-image primitive (R7), no WebP in the stored artefact (R4).**
- **No change to the GCS chunk policy (R8).**
- **No `image_format="jpeg"` on the P1 wire.** It is the exact change that failed on 2026-08-19.
  Its k=5 rerun is a separate eval question and is not bundled here (§17.3).

---

## 7. Doc updates owed by this plan

All DONE except the one that depends on a deploy:

- ✅ CLAUDE.md §12: the live bucket is `grader-vision-pdfs-0438328890` (set by the service env
  var; `config.py`'s default is the dead name, and a `gcloud storage` command against it 404s).
- ✅ CLAUDE.md §7 batch transcription: the "`Σ jobs == test_count` ALWAYS" claim is replaced —
  since B9 the batch is created EMPTY and appends grow it, and after Stage A the declared count
  is `expected_test_count` with `uploading = max(0, expected − COUNT(jobs))` as the in-flight
  fact. Migration head → 025.
- ✅ CLAUDE.md §8 `transcription_job.py` row: jobs are what ARRIVED, not what she declared.
- ✅ CLAUDE.md §10: Decision 4 superseded (R3); new rows for `UploadQueueProvider` and
  `UploadLane`; the upload-seam bullet now names the queue's real home and the Stage D header.
- ✅ CLAUDE.md §8 pipeline: the Stage C1 executor note, including why `stitch` is positional.
- ✅ `schemas/batch.py`: the `total` comment (it said "= batch.test_count", untrue since B9.5).
- ⬜ `SCALING_ROADMAP.md` deployed-dials table: add `--cpu` — **after** C2 is actually deployed.
  Writing "2" into the table before the flag is set would make the doc lie about production,
  which is the drift this list exists to prevent.

---

## 7a. What the reviews caught (kept, because each one is a rule)

Every stage was reviewed by an independent adversarial pass. None of these was found by the
tests as written; each is now pinned by one.

**Stage A**
* **The completion hero fired over a batch that received nothing.** After the backstop, an
  abandoned ten-file batch reads `uploading 0` with every other counter 0, so `completionReached`
  said yes and the green ✓ announced «כל 10 המבחנים אושרו» three lines under a red «נכשל» chip.
  Unreachable before Stage A — `total` was `COUNT(jobs)`, so the `total > 0` guard held. Making
  `total` the DECLARED count is what opened it, so `not_received === 0` joins that gate.
* **The batches LIST still said «ממתין להחלטות»** over its own «4 קבצים בהעלאה» line: the label
  gained an `uploading` arm and the detail page was threaded, the list was not.
* **`not_received` folded into the «נכשל» segment**, so the dashboard called a file that never
  arrived a failure while the list said "it never arrived, send it again", and pointed her at an
  empty FailedZone. It has its own segment now.
* **The declaration had no server-side ceiling.** A client number promoted to the batch's
  authoritative denominator (§9 says a request body never gets to be that unvalidated).

**Stage B**
* **Dismissing the lane abandoned files and misreported them for 90 minutes.** `declaredCount`
  keeps a RETRYABLE failure in the declaration because she may still retry — true only while the
  queue exists. The X said "close this list" and also meant "abandon this file". Letting go is
  now one of R9's terminal events: it settles the declaration and hands the filenames to the
  dashboard's existing one-shot notice. Starting a second batch over a drained-with-failures
  queue had the same hole.
* **The re-declare gate advanced before the PATCH landed, and the failure was swallowed.**
  `declaredCount` only decreases and the gate is pure equality, so one lost request retired that
  value forever: the client knew a file was dead, told nobody, and had no way left to say it. On
  the 2 Mbps link this plan exists for, that request is exactly the one likely to fail. The gate
  reopens on failure.
* **`settleAndForget` was defined below its callers** — a temporal-dead-zone crash on first
  render, caught only because the fix was read back.
* **An all-422 batch polled a dead dashboard every 3 seconds forever** (`total === 0` can never
  satisfy `completionReached`'s own `total > 0` guard). Newly reachable because Stage B always
  lands her there.
* **Every XHR progress event allocated a new state object**, hence a new context value, hence a
  full dashboard re-render tens of times a second during exactly the window Stage B exists to
  make usable. An unchanged rounded percent is now a no-op, which this reducer's contract already
  promised.
* Plus the dead code the move left behind: six orphaned imports, `UPLOAD_CONTINUE`, and the whole
  U3 per-row branch in `UploadFilePanel` — deleted, with its render pins re-homed to the lane's
  own test (the §4.4a precedent).

**Stage C1**
* **`stitch` was keyword-only.** `loop.run_in_executor` forwards positional arguments only, so
  every transcription would have raised `TypeError` inside the executor — on a path no unit test
  of the pure encoder would ever reach. The byte-identity test caught it on its first run.
* **Offloading the encode also made it AWAIT, which reordered chunk dispatch.** The P1 chunks run
  under one `asyncio.gather`, so whichever finished ENCODING first dispatched first — and that is
  not random: the smaller chunk finishes sooner, so a 5-page document at 3-per-call reliably
  issued its 2-page call before its 3-page one (8/8 trials). Caught by the transcription eval
  suite's own `test_pipeline_chunking_and_packing`, whose fake serves responses positionally.
  Nothing the model receives changes and the merge is by page number, so the transcription is
  identical either way — **but the bar for C1 is "same behaviour, different thread", and a
  dispatch order that flips is not that.** Fixed with a per-Pipeline `_encode_lock` rather than by
  editing the test: encodes were ALREADY serial before C1 (inline on the loop, no await between
  them), so the lock reproduces exactly that sequence at no cost, while leaving the loop free —
  which is the entire point. The Pipeline is built per document, so it never serializes one
  teacher's batch against another's.
* **Encodes were queueing behind 6-minute LLM calls.** `run_in_executor(None, …)` is the
  process-wide default pool — `min(32, cpu_count+4)` = **5 threads at cpu=1000m** — and
  `asyncio.to_thread` resolves to the same one, which `docx_v3/pipeline.py` and `rubric_service`
  use for blocking `.invoke` calls bounded at 360s×2. An instance at containerConcurrency=4 could
  park every thread in an extraction while a transcription's encodes sat in an unbounded, untimed
  FIFO — a latency regression in exactly the dimension C1 exists to improve, and one that reads as
  slow model calls in the stage timings. Now a dedicated 2-thread pool.
* **The GIL claim was checked, not assumed:** two threads through the real encoders ran 1.79×
  faster than serial (0.275s vs 0.494s), and a 4-page executor encode let a 5 ms heartbeat tick 59
  times where the inline version let it tick zero.

**Stage D — the stage collected NOTHING, silently**
* **`extra=` never reaches the log.** This service configures logging once —
  `basicConfig(format='…%(message)s')`, no dictConfig, no JSON formatter, no
  google-cloud-logging — so the line Cloud Run captured was the bare `batch_file_appended` and
  nothing else. Every test passed, the code looked right, and §9's deliverable would simply have
  been absent when someone queried it a week later. The numbers now go in the MESSAGE (`extra` is
  kept for a future formatter), pinned by a test that asserts the RENDERED text through the real
  format string. Note this is codebase-wide: every other `extra=` in this file is invisible too.
* **`nan` in the header 500'd an append whose side effects had already committed.**
  `float("nan")` parses, and NaN loses every comparison silently, so control reached
  `int(x / nan)`. The raise landed at the log line — after the GCS upload, after the job row
  committed, after the task was enqueued — so the file was accepted and would transcribe while
  the teacher got a 500 and re-uploaded megabytes. The existing test's `"NaN-ish"` was false
  comfort: it fails `float()`, which is the opposite case.
* **The "uplink" was measuring the server's own work.** The clock stopped at the log line, folding
  the GCS upload, the insert, the commit and the enqueue into the number. Under exactly the
  contention Stage C exists to fix, a 3 MB file on a fast link would report ~1.6 Mbit/s instead of
  ~20 — plausible, guard-passing, and biased LOW, i.e. biased toward arguing FOR the eval-risky
  byte reduction the number exists to judge. The clock now stops when `read()` returns. An upper
  bound was added too: a client clock 1 ms fast yielded tens of Gbit/s and passed every check.
* **CORS was verified, not assumed** (the one item that could have broken every upload):
  `allow_headers=["*"]` echoes the requested headers, the real app answers the real preflight 200
  with `x-upload-started-ms` allowed, and the request was already preflighted for `Authorization`
  anyway.

---

## 8. Deploy steps this plan does NOT perform

Implementation stops at the working tree and the test database. These actions are
production-facing or spend real money, and belong to the owner — listed here so none of them is
discovered later:

1. **Apply migration 025 to production** before (or with) the backend deploy. The boot check
   logs `SCHEMA MISMATCH … NOT APPLIED` and keeps serving if it is missed, so the failure is
   loud and non-fatal — but every batch created in that window records no declaration and
   behaves exactly as it did pre-Stage-A (the NULL population), which is the intended
   degradation and not a data problem.
2. **Deploy order is free.** The wire field is additive and the client reads it as `?? 0`, so
   backend-first and frontend-first are both safe. Backend-first is marginally better: the
   column exists before any client declares into it.
3. **Stage C2's `--cpu=2`** (ruling R13) is a `gcloud run deploy` flag. Code-side C1 is done in
   the tree; the flag is not set from here. Measure the contended-append p95 with Stage D's log
   line before AND after, so the two halves are attributable separately (§3 Stage C's kill
   criterion depends on telling them apart).
4. **Stage E is not started** — but it is CHEAP (≈$10, hours of wall clock; see §3 Stage E for
   the measured arithmetic). It is left to the owner for two reasons that are not cost: its whole
   value is the VERDICT, so running it half-way or at the wrong k produces a number that looks
   like evidence and is not; and it needs the client transform driven under real Chromium first,
   because a corpus encoded by Pillow measures nothing about what a browser would ship. Nothing in
   Stages A–D depends on it — they are shipped and their value is independent.
5. **Stage F cannot be scheduled until E returns a pass**, and then still needs the R12
   print-comparison before its flag goes on.

---

## 9. Measurements to paste back here

- Stage D: first week's per-append Mbps distribution (p10 / p50 / p90).
- Stage C: contended-append p50 / p95 before vs after C1, and after C2.
- Stage E: per-candidate ratio on the ten fixtures, and the gate verdicts.
