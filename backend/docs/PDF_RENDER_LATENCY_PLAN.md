# PDF render latency — implementation plan (2026-08-19)

**Status: PLAN — no implementation code written. Awaiting approval (§0.1).**

---

## 0. Problem, in Deutsch form

**Data.** `pdf_render` is the single largest stage in a transcription. Measured
across all August eval runs (n=76 records): **median 30.8 s, range 12.3–61.5 s**
per document — larger than the P1 model call (~14.7 s), the strike-check pass
(~7.8 s) and P2 (~7.0 s) combined. It is pure local compute: no model, no
network, no accuracy contribution.

**Theory under criticism.** "Rendering a scanned PDF to page images inherently
costs seconds per page." FALSIFIED by direct measurement (§2): the same pages
rasterize **18× faster** with a library already in `requirements.txt`.

**Better conjecture.** The cost is not rasterization — it is `pdf2image`'s
architecture: a **subprocess spawn to Poppler per call**, serialising every page
through **PPM/PNG pipes** which Python then re-decodes. The pixels are cheap;
the plumbing is not.

**Criticism of the conjecture.** It predicts an in-process rasterizer is
dramatically faster at no quality cost. The first half is confirmed (§2.1). The
second half is **not** — measurement shows the pixels differ slightly (§2.3).
So no change here may ship on a latency argument alone; each must clear an
accuracy gate. That is the entire design of §5.

---

## 1. Blast radius — every file that renders a PDF

Established by grep over the whole backend, not from memory. **Three independent
implementations of `pdf_to_images` exist in live code**, plus two dead copies.

### 1.1 Live render call-sites

| # | Symbol | File | Consumers | DPI | Risk |
|---|---|---|---|---|---|
| **A** | `pdf_to_images` | `app/services/document_parser.py:34` | **P1 transcription** via `two_phase/pipeline.py::_default_renderer` — production **and** the eval suite; `transcribe_one.py:215`; `pdf_preview_service`; `grading.py:386`; legacy parsers; `rubric_service.py:1601` | 150 default, **200** for P1 | **HIGHEST** — the eval-gated path |
| **B** | `pdf_to_images` | `app/services/handwriting_transcription_service.py:515` | legacy VLM engine (`transcribe_pdf:926`) | 200 | Medium — legacy engine still selectable |
| **B2** | `render_pdf_page` | same file:522 | **page-image proxy** (`api/v0/transcription.py:327`, `PAGE_RENDER_DPI=150`); **identity channel** (`transcription/identity.py`) | 150 | Medium — user-facing latency |
| **B3** | `pdf_path_to_images` | same file:542 | no callers found | 200 | None (dead?) |
| **C** | `pdf_to_images_optimized` | `app/services/vlm_rubric_extractor.py:572` | own module only (docx V3 is the production rubric path) | — | Low — legacy |

**Dead copies — OUT OF SCOPE, do not touch:** `app/document_parser.py`,
`deprecated/document_parser.py`, `deprecated/rubric_service.py`.

### 1.2 Tests that pin current behaviour (the tripwires)

| Test | What it pins | Consequence |
|---|---|---|
| `tests/api/test_transcription_page_render.py:51` | `render_pdf_page(pdf,n,150)` is **byte-identical** to `pdf_to_images(pdf,150)[n-1]` | **A and B/B2 must migrate together.** Moving one rasterizer and not the other breaks byte-equality. This test is a *useful* consistency guard — keep it, do not weaken it |
| `tests/api/test_transcription_endpoints.py:88,250` | patches `app.services.transcribe_one.pdf_to_images` | If R2 removes that import, the patch target vanishes → test errors. Must be updated in the same commit |
| `tests/services/test_identity.py:31,111` | patches `identity.render_pdf_page` | Signature must not change |
| eval suite (`test_pipeline_and_runner`, `test_spans`, `test_strike_check`, `test_trust_layer`) | inject `_fake_renderer` | Unaffected by construction — they never touch a real rasterizer |

### 1.3 Wire & deployment constraints

- **All three provider adapters hardcode `image/png`**: `anthropic_provider.py:63`
  (`media_type`), `gemini_provider.py:135` (`mime_type`), `openai_provider.py:63`
  (`data:image/png;base64,`). Any encode-format change (R4) needs a mime type
  plumbed through the `VLMProvider` protocol — a shared-interface change, not a
  local edit.
- **`Dockerfile` installs `poppler-utils`.** It can only be dropped once *every*
  `pdf2image` caller including legacy is migrated. **Recommend keeping it.**
- `two_phase/pipeline.py` owns `_resize` (LANCZOS → `image_max_px=2000`) and
  `_to_b64_png`. The strike-check pass added a **second** encode + upload of
  every page, so payload size now costs twice per document.

---

## 2. Measured baseline (this machine, the 5 eval fixtures, 27 pages)

### 2.1 Rasterizer
| path | total | per doc | speedup |
|---|---|---|---|
| `pdf2image`/Poppler @200 DPI (**current**) | **82.80 s** | ~16.6 s | 1× |
| PyMuPDF @200 DPI | **4.61 s** | ~0.92 s | **18.0×** |
| PyMuPDF @fit-DPI (171 → exactly 2000 px) | 4.28 s | ~0.86 s | 19.3× |

### 2.2 What these PDFs actually are
All fixtures are **CamScanner** output (`intsig.com pdf producer`): every page is
**two embedded JPEGs** (a ~2100×3000 scan + a 912×130 watermark), with **zero
text and zero vector drawings**. Consequences:
- Rendering is decode-JPEG + resample + composite. ~3 s/page for that is
  plumbing overhead, not pixel work — which is what the 18× confirms.
- The current path **resamples twice**: native ~3000 px → Poppler 2338 px
  (200 DPI) → LANCZOS 2000 px. Rendering at fit-DPI would resample once.
- Raw JPEG extraction (skipping rasterization entirely) is **rejected**: it drops
  the watermark image and any page composition. Rasterizing is the safe path.

### 2.3 Pixel delta — why an accuracy gate is mandatory
PyMuPDF@200 + resize vs Poppler@200 + resize, per page, grayscale:
**mean Δ 1.30–4.30** (of 255), **2–7 % of pixels differ by >16**, max ~200.
Differences concentrate on stroke edges (antialiasing). fit-DPI differs more
(mean up to 7.3, ~11 % of pixels). **Not pixel-equivalent ⇒ must be eval-gated.**

### 2.4 Encode + payload (6-page doc — the images the VLM receives)
| format | encode | payload | per page |
|---|---|---|---|
| PNG (**current**) | **1269 ms** | **12.65 MB** | 2109 KB |
| PNG `optimize=True` | 4869 ms | 12.18 MB | 2030 KB |
| JPEG q95 | 101 ms | 4.35 MB | 725 KB |
| JPEG q90 | 92 ms | 3.08 MB | 514 KB |
| JPEG q85 | 92 ms | 2.51 MB | 418 KB |

PNG is the worst available choice for photographic scans: **13.8× slower to
encode and 4.1× larger on the wire** than JPEG q90. That payload is uploaded
inside `p1_call` **and again** inside every strike-check call, and
`two_phase_engine` cites multi-MB uploads as the reason for its 240 s timeout on
weak links.

### 2.5 Parity checks already run
- **Rotation** `/Rotate` 0/90/180/270: output dimensions **match Poppler exactly**.
- **Page count** without rendering: `fitz.open(...).page_count` — instant.
- **Error behaviour differs**: fitz raises `FileDataError` / `EmptyFileError`
  where Poppler raises `PDFPageCountError`; out-of-range page → `IndexError`.
  Call-sites that catch today must keep catching (normalise in R1).

---

## 3. The changes — ranked by measured value, each independently gated

| id | change | measured win | image change? | gate |
|---|---|---|---|---|
| **R1** | Rasterizer Poppler → PyMuPDF (A + B + B2 together) | **−15.7 s/doc** | yes, small (§2.3) | **Full eval gate** |
| **R2** | Page count without rendering — `transcribe_one:215` renders the whole PDF at 72 DPI *just to count pages* | −2–5 s on the single-flow path | **none** | Unit tests only |
| **R3** | Page-proxy + identity via single-page PyMuPDF | ~3 s → ~0.2 s **per page view** | yes (same as R1) | Rides R1 + byte-equality test |
| **R4** | Encode PNG → JPEG q90 on the wire | −1.2 s encode, **−75 % upload bytes** (×2 call sites) | yes (lossy) | **Full eval gate, separate** |
| **R5** | Render once at fit-DPI (skip double resample) | −0.1 s + one LANCZOS pass | yes, largest | **Separate gate — expected decline** |

**Expected end state:** `pdf_render` ~30.8 s → **~1 s**; encode 1.3 s → 0.1 s;
upload bytes −75 %. Composed doc latency ~52 s → **~35 s** in a fast-render
window, ~68 s → ~36 s at the median render. Render stops being the bottleneck
and the P1 model call becomes dominant — the correct place for the cost to sit.

---

## 4. Open decisions (surfaced with a recommendation, not decided)

**D1 — Renderer library.** PyMuPDF (`fitz`), already pinned at 1.25.5. No new
dependency, no system package.
→ **Recommend: yes.** *Licensing caveat worth your ruling: PyMuPDF is
AGPL-3.0-or-commercial. It is already a dependency so this changes nothing
legally, but if AGPL is a concern for a closed-source deploy, say so and I will
benchmark `pypdfium2` (BSD-3) as the alternative before committing.*

**D2 — Where the implementation lives.** One new module
`app/services/pdf_render.py` exposing `render_pages(pdf_bytes, dpi)` and
`render_page(pdf_bytes, page_number, dpi)`; the three existing entry points
(A, B, B2) become **thin delegates**.
→ **Recommend: yes.** Every import path and mock target keeps working (§1.2
tripwires stay green) while there is exactly one implementation — §0.4, one
concept one place. Editing three functions in place would re-create the
three-copies problem this repo already suffers from.

**D3 — Kill switch.** `PDF_RENDERER=poppler|pymupdf` in `config.py`.
→ **Recommend: yes, defaulting to `poppler` until the gate passes, then flip.**
This is what makes "zero regressions" *verifiable* rather than asserted: prod
reverts with one env var and no redeploy, and the eval suite can A/B both arms
in one session.

**D4 — DPI strategy.** Keep 200 DPI + existing `_resize`; R1 changes *only* the
rasterizer.
→ **Recommend: yes.** Smallest image delta ⇒ cleanest attribution.

**D5 — Encode format (R4).** JPEG q90 with mime plumbed through `VLMProvider`.
→ **Recommend: yes, but strictly after R1 lands.** Second-biggest win and the
one that most helps weak-uplink teachers. Bundling it with R1 would repeat the
sc1.2 mistake from this session — two changes, unattributable result.

**D6 — Remove poppler from the Docker image.**
→ **Recommend: no, not now.** Keeping it is what makes D3's revert real.

---

## 5. The accuracy gate — non-inferiority protocol

**The methodological constraint that shapes this whole section:** the
strike-check work could use a *paired* design (same P1 output scored before and
after), which made its effect exactly attributable. **A renderer swap cannot be
paired** — it changes the model's input, so the two arms see different images and
P1 is stochastic. Measured natural variance at unchanged config: `op`
0.9701↔0.9851 (yonatan), `st` 0.9711↔0.9827 (din). So the gate compares
**distributions across k reps**, and the tolerance is **the baseline's own
measured spread** — never a threshold I invent.

**Protocol, applied per gated change (R1, then R4):**

1. **Baseline arm** — current renderer, `p1_only`, all 5 fixtures, **k=5**
   (25 records), same session, **interleaved in time** with the candidate arm so
   machine drift cancels.
2. **Candidate arm** — identical config except the one flag. **k=5.**
3. **Per-doc decision rules — all must hold:**
   - `coverage == 1.0` and `parse_failures == 0` on every record; any failure
     invalidates that record and is diagnosed before continuing;
   - candidate **mean** `doc_ratio_strict` ≥ baseline mean **− 0.005**;
   - candidate **min** of each critical recall (`operator`, `structural`,
     `method_call`) ≥ the baseline **min** for that doc — the candidate may not
     introduce a worse floor than the baseline already exhibits;
   - **no new `abbreviations_altered`** on any doc that was clean;
   - moran's `op=st=mc=1.0` gate PASS survives on ≥ the baseline's number of
     passing reps. It is the suite's only full-gate doc — the canary.
4. **Kill criterion:** any rule violated on any doc ⇒ the change does not ship.
   Record it in RUNLOG with evidence and stop. **Do not tune the gate** (§17.7).
5. **Cheap-first escalation** (§17.2): run **k=1** on both arms as a smoke test
   (~$0.14/arm); spend the k=5 arms only if no doc moved beyond its baseline
   band. Same discipline as the k=1→k=3 rule set for the strike-check work.

**Cost:** k=1 smoke ≈ $0.3 total; full k=5 both arms ≈ $1.4; ~25 min wall (and
the candidate arm runs much faster, which is the point).

---

## 6. Implementation phases — each ends at a decision point

### Phase 0 — Instrumentation (no behaviour change)
Record `pdf_render` timing in the same artifact as accuracy so the win and the
risk are read together. **Exit:** baseline k=5 in RUNLOG.

### Phase 1 — R2, the free win (no image change)
Replace `transcribe_one:215`'s full 72-DPI render-to-count with a page-count
call. Update the `test_transcription_endpoints` patch target in the same commit
(§1.2). **Exit:** unit tests green. **No eval run needed** — no image reaches any
model differently.

### Phase 2 — R1, the main event
1. Write `app/services/pdf_render.py` (D2) with both backends behind D3's flag;
   normalise fitz's exception types to the existing contract (§2.5).
2. Point A, B, B2 at it as delegates. Handle `pm.n` (grayscale/alpha) explicitly.
3. Offline gates: full suite + `test_transcription_page_render` byte-equality
   (**each arm self-consistent**) + `import app.main` + `pytest --collect-only`.
4. **Feedback loop:** k=1 smoke both arms → read per-doc deltas → if any doc
   moves beyond its band, **stop and attribute** (rasterizer? resize? one
   specific page?) using the §2.3 pixel-diff harness *before* changing anything.
5. k=5 both arms → apply §5 → **decision: flip the default, or revert.**

### Phase 3 — R3, page proxy + identity
Rides Phase 2's flag; byte-equality is the guard. **Exit:** proxy latency
measured before/after. No eval run — same rasterizer, already gated.

### Phase 4 — R4, JPEG on the wire (its own gate)
1. Plumb `image_mime` through `VLMProvider` + all three adapters, defaulting to
   PNG so the change is inert until a config opts in.
2. Flag `P1_IMAGE_FORMAT=png|jpeg` with configurable quality.
3. Run §5's protocol standalone. Quality ladder q95→q90→q85 **only if** q90
   passes; stop at the first failure.
4. **Exit:** flip or revert, with payload and latency deltas recorded.

### Phase 5 — R5, fit-DPI (expected: decline)
Only if Phases 2 and 4 landed clean and residual render cost still matters. On
current numbers it buys ~0.1 s for the largest image delta of any change here.
I expect to recommend against it — stated up front rather than discovered late.

### Stopping rule (what "lowest possible latency" means here)
Stop when the next candidate's measured wall-clock win is **< 5 % of total doc
latency**, or its image delta exceeds that of the previous gated change —
whichever comes first. After R1 + R4, `pdf_render` is ~1 s of a ~35 s document;
at that point the bottleneck is the P1 model call and further render work is
optimising a rounding error. Say so and stop rather than chase it.

---

## 7. Rollback & risk

- **Rollback:** one env var (D3), no redeploy, no data migration. Poppler stays
  installed (D6). R4 carries its own independent flag.
- **Risk — concurrency:** Poppler ran as subprocesses (true parallelism);
  PyMuPDF is in-process. Under batch fan-out this shifts CPU into the worker.
  Mitigation: keep rendering inside `run_in_executor`, and **measure a 4-doc
  concurrent batch before/after in Phase 2** rather than assuming.
- **Risk — memory:** pixmaps must be released per page; 6 pages × 2000 px RGB
  ≈ 51 MB peak per doc. Verify under batch fan-out.
- **Risk — untested PDF classes:** every eval fixture is a CamScanner raster.
  Text-native and vector PDFs are covered only by synthetic tests. Before
  flipping the production default, render a **text-native** and a **rotated**
  PDF under both backends and compare — the fixtures cannot speak for those.
- **Risk — the eval suite and production share renderer A.** By design (the
  suite measures what prod runs); it is why the flag governs both.

---

## 8. What this plan will NOT do

- Not touch `deprecated/` or `app/document_parser.py` (dead copies).
- Not remove `pdf2image`/poppler (D6).
- Not change DPI, `image_max_px`, or any prompt.
- Not bundle two gated changes into one run (§17.3).
- Not modify the scorer, gate thresholds, or any benchmark (§17.7).
