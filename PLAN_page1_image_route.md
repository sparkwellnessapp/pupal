# PLAN — `page1_image_url`: a real WebP page-image route

**Status:** proposed, awaiting one owner ruling (§3). **Owner directive 2026-09-02:** option (b) —
"a real `page1_image_url` image route returning `image/webp` bytes with immutable cache headers,
and putting its path in the field."
**Closes:** the last unimplemented half of PR-G8's §1.5 deliverable, and the frontend agent's
blocker #1 on `PR_SPEC_frontend_grade_review.md` (`Pile`/`PileCard`).

---

## 1. The problem, in Deutsch form

**Data.** `BatchGradedItem` carries eleven fields and `page1_image_url` is not among them, so the
Pile's top-bar thumbnail renders an empty frame. The only page-serving path that exists is
`GET /api/v0/transcriptions/{tid}/pages/{n}`, which returns `{page_number, thumbnail_base64}` —
**JSON carrying a base64 PNG**, not an image resource.

**Theory under criticism.** "The page proxy is the page-image capability; the feed just needs to
name it." Measured on the six real bagrut scans (`tests/transcription_eval_suit/pdfs/`, 1.7–9.2 MB,
p50 of 3 runs each, this machine):

| variant | p50 KB | max KB | p50 ms | max ms |
|---|---:|---:|---:|---:|
| **PNG-base64 @150 dpi — today's proxy** | **1168.5** | **1870.3** | **1226.9** | **1806.4** |
| webp 72 dpi → w=300 q=72 | 10.8 | 15.4 | 144.4 | 266.9 |
| webp 72 dpi → w=600 q=72 | 31.7 | 42.8 | 223.1 | 293.0 |
| **webp 110 dpi → w=600 q=72 (recommended)** | **33.6** | **45.4** | **259.1** | **327.8** |
| webp 150 dpi → w=600 q=72 | 34.5 | 46.3 | 420.6 | 488.8 |
| webp 110 dpi → w=600 q=82 | 43.8 | 57.2 | 305.5 | 412.6 |
| webp 110 dpi → w=900 q=72 | 57.8 | 76.4 | 475.0 | 601.1 |

A thirty-card dashboard on today's path is **≈34 MB of base64 over the wire and ≈37 s of render**.
The theory is falsified: this is not a thumbnail capability wearing the wrong URL, it is a
full-resolution review-image path being asked to do a thumbnail's job.

**Conjecture.** A second, separate representation — one bounded, downscaled WebP resource per page —
served as bytes with a long immutable cache lifetime, named by a path on the feed item. **≈35×
fewer bytes and ≈4.7× less render time per card**, and (phase 2) rendered once in the product's
lifetime rather than once per cache miss.

**Criticism.** Is it hard to vary? Two things are load-bearing and neither is a free parameter:
the resource must be *bytes* (a JSON envelope re-introduces the base64 inflation and defeats HTTP
caching), and it must be *separately keyed* from the review-resolution render (sharing a key
serves a 600 px thumb to the review pane or a 1.1 MB PNG to a card). Does it introduce new
contradictions? One, and it must be ruled on — §3.

---

## 2. What the measurement also found (not caused by this change; made worse by it)

`app/services/page_cache.py` is bounded **by entry count**, `MAX_ENTRIES = 256`, and its docstring
justifies that with: *"a rendered page is tens of KB, so the cap is the memory bound."*

**Measured: 1168 KB p50, 1870 KB max — the docstring is wrong by ~40×.** A full cache is therefore
**≈300 MB, worst case ≈480 MB**, in a container with a 2 GiB limit whose concurrency was already
taken 5→4 on an OOM measurement (≈260 MB/doc + ≈480 MB fixed — `CLAUDE.md` §12). This is live
today. Adding a second variant to a count-bounded cache would compound it.

**In scope for this plan:** re-bound the cache **by bytes**, not by entries. One budget, honestly
shared by both variants, LRU-evicted on total size. The count cap is not "tightened" — it is the
wrong unit, and keeping it while adding a variant would be exactly the "loosen a tolerance to make
the new thing fit" move §0.5 forbids.

---

## 3. THE OPEN DECISION — how the browser authenticates the image GET

**This blocks nothing else in the plan, but it must be ruled before the frontend half is written.**

Every domain endpoint in this codebase authenticates with `Authorization: Bearer <jwt>` via
`HTTPBearer` (§9). There is no cookie auth anywhere. **A browser `<img src="/api/v0/…">` sends no
Authorization header** — so the naive reading of "a real image route" (add the route, point `<img>`
at it) returns 401 on every card and reproduces the empty frame it was meant to fix, with a
different cause. There is no existing precedent in this repo: the returned-exam ZIP is the only
other byte-serving route and its client half is not built yet.

| | how it works | `<img src>` direct? | cache | security posture |
|---|---|---|---|---|
| **B1 — blob fetch (recommended)** | field carries the path; client `fetch`es it through the existing seam with the Bearer header, `URL.createObjectURL(blob)` → `<img src={objectUrl}>` | no (blob URL) | yes — the repeat `fetch` is a private-cache hit under `Cache-Control: private, max-age=…, immutable` | unchanged; the route keeps `get_current_user` + `get_owned_or_404` |
| **B2 — signed capability URL** | feed mints `…/image?sig=<HMAC(tid,page,uid)>`; route accepts the signature instead of a session | yes | yes (URL is stable) | **new bearer-capability surface**: anyone holding the URL sees a student's exam page, with no revocation |
| **B3 — GCS signed URL** | field carries a signed GCS URL; browser talks to GCS directly | yes | **no** — the signature rotates every 5 s poll, so the `src` changes and the browser re-downloads every time | exposes bucket + object naming; time-bounded |

**Recommendation: B1.** It is the only one that leaves §9 literally true, it keeps the immutable
cache header doing real work, and the ~15 lines of client code it needs (one hook, `revokeObjectURL`
on unmount) are the same pattern D8/D9's ZIP download will need anyway — so it is a seam the
frontend owes itself regardless. B3 is actively counter-productive here: it defeats the caching
that is the whole point. B2 is the only one that makes a bare `<img src>` work, and it buys that by
creating an unrevocable capability URL for a page of a named student's exam — which is the category
`CLAUDE.md` §2 says does not ship without an explicit ruling.

**The plan below assumes B1** and is written so that switching to B2 later changes only the URL
built in `_build_graded_feed` plus one dependency on the route — no schema, no client-shape change.

---

## 4. Design

### 4.1 The route

```
GET /api/v0/transcriptions/{transcription_id}/pages/{page_number}/image
    → 200 image/webp  ·  Cache-Control: private, max-age=31536000, immutable
```

**Path shape is deliberate.** A `.webp` *suffix* on the existing route (`…/pages/1.webp`) would be a
trap: `page_number` is typed `int`, so `1.webp` fails validation with **422 and does not fall
through** to a later route — making registration order load-bearing, the same hazard `CLAUDE.md`
records for `rubric_extraction_jobs` vs `rubric_management`. A distinct trailing segment collides
with nothing at any registration order.

Behaviour, mirroring the existing proxy exactly so the two cannot drift:
1. `get_owned_or_404(db, Transcription, …, current_user.id)` — ownership before anything else.
2. Range check against `draft_json.page_count` → 404.
3. Cache lookup (§4.2). Hit → return bytes.
4. GCS download → `render_page_thumbnail` → cache put → return bytes.
5. Renderer `ValueError` (draft claims more pages than the PDF has) → 404, as today.

`response_class=Response`, `responses={200: {"content": {"image/webp": {}}}}`. **Verified**: the
OpenAPI dump emits `content: {"image/webp": {}}` with no schema, which `openapi-typescript` consumes
without a schema entry — so codegen is a no-op beyond the new `BatchGradedItem` field.

### 4.2 Cache

`page_cache` generalises from `(tid, page, dpi) → str` to `(tid, page, variant) → bytes | str`,
where `variant` is `"png-b64@150"` (the review path, unchanged behaviour) or `"webp@600"`.

Bound becomes **`MAX_BYTES` (default 64 MiB)**, evicting LRU until under budget, with `len()` of the
value as the charge. `MAX_ENTRIES` is removed, not merely lowered: the entry count was never the
memory bound and pretending otherwise is what hid §2.

### 4.3 Rendering

New pure module `app/services/thumbnail.py`:

```python
def render_page_thumbnail(pdf_bytes, page_number, *, width_px, quality, render_dpi) -> bytes
```

Render via the one rasterizer (`pdf_render.render_page` — no fourth copy), convert to RGB, LANCZOS
down to `width_px`, encode WebP. Pure and mock-free, so it is testable the way `gradable_compiler`
is.

**Recommended pins, from §1's table:** `render_dpi=110`, `width_px=600`, `quality=72` →
**33.6 KB p50 / 45.4 KB max, 259 ms p50.** The 110 dpi is *supersampling for sharpness*, not
resolution: rendering at 110 and downscaling to 600 beats rendering at 72 directly for ~2 KB and
~36 ms. 600 px (not the spec's "≈300 px") because the Pile card is retina-doubled; a page-1 thumb
was rendered at these settings and inspected — the student's name and handwritten code are legible,
so the card can also serve the "is this the right test?" recognition job.

`Pillow==12.1.0` WebP support **verified present** (`PIL.features.check("webp") is True`, encode
round-tripped). The Docker image installs the same wheel, so support ships with it; the plan's
verification step re-checks inside the image rather than assuming.

### 4.4 The field

```python
# app/schemas/batch.py :: BatchGradedItem
page1_image_url: Optional[str] = None
```

A **relative path** (`/api/v0/transcriptions/{tid}/pages/1/image`), because `apiFetchRaw` already
prefixes `NEXT_PUBLIC_API_URL`; an absolute URL here would hard-code the environment into a payload.

`None` when the test's transcription has no page 1 — **degrade by omission (§3.5a)**: a URL that is
known to 404 produces a broken-image glyph, which reads as "this test is damaged" rather than "we
have no preview". `get_batch` already loads the batch's transcriptions and already indexes
`gt_by_tid`, so the page-count gate costs no query: `_build_graded_feed` takes a
`page_counts: dict[str, int]` argument.

---

## 5. Phasing

**Phase 1 — unblocks the frontend.** Field + route + thumbnail module + byte-bounded cache. After
this the Pile renders, and a cold card costs one PDF download + 259 ms instead of one PDF download
+ 1227 ms + 1.1 MB.

**Phase 2 — the census-E fix at scale.** Persist `thumbs/{transcription_id}/p1.webp` to GCS on first
miss (and, later, at transcription completion), so the steady state is a ~34 KB GCS read instead of
a multi-MB PDF download + render. This is what the PR-G8 spec line already ratified, and it is what
makes the in-process cache a *latency* optimisation rather than the only thing standing between the
pilot and 30 full-PDF downloads per dashboard load on a school connection — Cloud Run runs up to 60
instances, so a process-local cache has a poor hit rate by construction.

Phase 2 is separable and **should not gate the frontend**. It touches only step 4 of §4.1
(`GCS thumb → miss → render → GCS put`) and adds no new wire shape.

---

## 6. Blast radius — every file

### Backend — changed

| # | File | Change | Risk |
|---|---|---|---|
| 1 | `app/schemas/batch.py` | `page1_image_url: Optional[str] = None` on `BatchGradedItem` | none — optional, additive |
| 2 | `app/api/v0/batch_grading.py` | `_build_graded_feed(...)` gains `page_counts`; populates the field; `get_batch` passes the map it already has | call site is single; `_count_leaf_scopes`/ETA untouched |
| 3 | `app/api/v0/transcription.py` | new route; existing route's two `page_cache` calls take the new variant key | **the existing route's bytes must not change** — pinned by the byte-equality test |
| 4 | `app/services/page_cache.py` | variant key; `MAX_BYTES` replaces `MAX_ENTRIES`; value `bytes \| str` | §2 — this is the memory fix |
| 5 | `app/services/thumbnail.py` **(new)** | `render_page_thumbnail` | pure |
| 6 | `app/config.py` | `page_thumb_width_px=600`, `page_thumb_quality=72`, `page_thumb_render_dpi=110`, `page_cache_max_bytes=67108864` | defaults only; no Cloud Run env change needed |
| 7 | `scripts/gen_batch_feed_fixtures.py` | `_item()` emits `page1_image_url` | fixtures regenerate |
| 8 | `tests/fixtures/grade_review/batch_feed_{landing,running,done,complete}.json` | **regenerated** — `test_fixture_is_byte_identical_to_a_fresh_generation` fails until they are | the diff *is* the frontend's breaking-change notice |
| 9 | Phase 2 only: `app/services/thumbnail.py` + the route | GCS get/put around the render | `gcs_service.upload_bytes`/`download_bytes` already exist — **no `gcs_service.py` change** |

### Backend — tests

| # | File | Change |
|---|---|---|
| 10 | `tests/api/test_transcription_page_render.py` | new cases (§7); existing four must stay green untouched |
| 11 | `tests/api/test_batch_grading.py` | feed asserts the field on every item and its absence when page-1 is absent |
| 12 | `tests/services/test_page_cache.py` **(new)** | byte budget, variant isolation, LRU |

### Frontend — changed

| # | File | Change | Risk |
|---|---|---|---|
| 13 | `src/lib/api-types.ts` | **REGENERATED** via `npm run gen:api`. Never hand-edited | `.github/workflows/api-types-drift.yml` fails until committed |
| 14 | `src/lib/api.ts` | `fetchPageImageObjectUrl(path)` on the seam (B1) — `apiFetchRaw` → `blob()` → `createObjectURL`; **no auto-retry** | must not go through `apiFetch<T>` (that JSON-parses the body) |
| 15 | `src/components/grade-review/Pile*` | consume the field; revoke the object URL on unmount; Hebrew `alt` | F-phase work, the frontend agent's |
| 16 | `src/mocks/grade_review/handlers.ts` | a handler for the image path. The fixtures carry **no image bytes**, so it must **refuse explicitly** (`notPublished`), never invent a placeholder — `registry.ts`'s stated rule | inventing bytes here is the "adapting to a backend gap" the spec forbids |
| 17 | `e2e/gradeReviewFixtures.ts` | route mock for the image path |

### Not changed — and why

- **`grader-frontend/`** — deploy mirror, regenerated by robocopy at deploy time. Never hand-edited.
- **`app/services/pdf_render.py`, `document_parser.py`, `handwriting_transcription_service.py`** —
  the thumbnail goes *through* `render_page`; adding a fourth rasterizer copy is the exact drift
  `pdf_render.py`'s docstring exists to prevent.
- **`app/services/gcs_service.py`** — phase 2 uses `upload_bytes`/`download_bytes` as they are.
- **`returned_exam.py`** — renders from the contract for print; unrelated resolution and lifecycle.
- **`scripts/check-copy.mjs` / copy gates** — one Hebrew `alt` string, no new surface copy.
- **Migrations** — none. No column, no DDL.

---

## 7. Named tests (the acceptance bar)

| Name | Pins |
|---|---|
| `page1-image-url-present-on-every-graded-item` | the field is populated for every feed item whose transcription has a page 1 |
| `page1-image-url-omitted-when-there-is-no-page-1` | `None`, not a URL that 404s (§3.5a) |
| `page-image-returns-webp-bytes-not-json` | `content-type: image/webp`, body starts `RIFF`…`WEBP` |
| `page-image-sets-immutable-cache-headers` | `private`, a year, `immutable` |
| `page-image-requires-auth` | no header → 401 |
| `page-image-refuses-another-tenants-transcription` | 404, never 403 (§9) |
| `page-image-bounds-and-renderer-guards-match-the-json-proxy` | 0 / `page_count+1` / claimed-but-absent page all 404 |
| `thirty-cards-cost-one-gcs-download` | the census-E pin, webp variant (mirrors the existing PNG one) |
| `webp-variant-does-not-evict-or-answer-for-the-review-png` | variant isolation — the review pane never receives a 600 px thumb |
| `page-cache-is-bounded-by-bytes-not-entries` | §2: 300 large entries must not exceed the byte budget |
| `json-page-proxy-bytes-are-unchanged` | the existing byte-equality baseline still holds after the key change |
| Phase 2: `thumb-rendered-once-then-read-from-gcs` | render count 1 across N instances-worth of requests |

---

## 8. Verification gates (before "done")

1. `python -c "import app.main"` and `pytest --collect-only` clean.
2. `pytest tests/api/test_transcription_page_render.py tests/api/test_batch_grading.py tests/services/test_page_cache.py tests/api/test_batch_feed_fixtures.py -q`.
3. `python scripts/gen_batch_feed_fixtures.py` then re-run (2) — regeneration must be a no-op.
4. `npm run gen:api` → commit `api-types.ts`; `npx tsc --noEmit`; `npx vitest run`.
5. **Inside the built image**, not on this laptop: `PIL.features.check("webp")` is `True`.
6. One rendered thumbnail eyeballed at the pinned settings before the numbers are frozen.

## 9. Rollback

The field is `Optional[str] = None`. Phase 1 reverts by returning `None` from `_build_graded_feed` —
one line, no schema change, no migration; the Pile falls back to its no-image state. The route can
stay live and unreferenced. Phase 2 reverts by skipping the GCS get/put and rendering as in phase 1.

## 10. Explicitly out of scope

- The `{page_number}` **JSON** proxy keeps its shape and its consumers (review pane, page strip).
  Migrating those to bytes is a separate, larger change with its own measurement.
- Pre-warming thumbs at transcription completion (phase 2 does first-miss only).
- Any `<img src>`-direct scheme (B2/B3) unless §3 is ruled that way.
