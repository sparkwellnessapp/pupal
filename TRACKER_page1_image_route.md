# TRACKER — `page1_image_url` implementation

Plan: `PLAN_page1_image_route.md` (APPROVED 2026-09-02). Every row here maps to a §6 blast-radius
item or a §7 named test. **A row is only ticked when its gate has actually run**, not when the code
is written.

Legend: ☐ todo · ◐ in progress · ☑ done+verified · ⊘ deliberately not done (reason given)

---

## Phase 1a — backend core (config · thumbnail · cache · route)

| # | Item | §6 | State |
|---|---|---|---|
| 1a.1 | `app/config.py` — `page_thumb_width_px/quality/render_dpi`, `page_cache_max_bytes`, `page_thumb_legacy_variants` | 6 | ☑ |
| 1a.2 | `app/services/thumbnail.py` (new) — `ThumbVariant` (token grammar, parse, allow-set) + `render_page_thumbnail` | 5 | ☑ |
| 1a.3 | `app/services/page_cache.py` — variant key, `MAX_BYTES` replaces `MAX_ENTRIES`, value `bytes \| str` | 4 | ☑ |
| 1a.4 | `app/api/v0/transcription.py` — new `/image` route; existing route's 2 cache calls take the variant key | 3 | ☑ |

**Gate 1a:** `python -c "import app.main"` · `pytest --collect-only` · new+existing page tests ·
`tests/services/test_page_cache.py` · **code review**.

## Phase 1b — the feed field

| # | Item | §6 | State |
|---|---|---|---|
| 1b.1 | `app/schemas/batch.py` — `page1_image_url: Optional[str] = None` + ⟨N1⟩⟨N2⟩ docstring | 1 | ☐ |
| 1b.2 | `app/api/v0/batch_grading.py` — `_build_graded_feed` gains `page_counts`; mints the URL | 2 | ☐ |
| 1b.3 | `scripts/gen_batch_feed_fixtures.py` — `_item()` emits the field | 7 | ☐ |
| 1b.4 | `tests/fixtures/grade_review/batch_feed_*.json` — regenerated (4 files) | 8 | ☐ |

**Gate 1b:** feed tests · fixture byte-identity · regenerate-is-a-no-op · **code review**.

## Phase 1c — frontend seam

| # | Item | §6 | State |
|---|---|---|---|
| 1c.1 | `src/lib/api-types.ts` — REGENERATED (`npm run gen:api`), never hand-edited | 13 | ☐ |
| 1c.2 | `src/lib/api.ts` — `fetchPageImageObjectUrl` on the seam, no auto-retry | 14 | ☐ |
| 1c.3 | `src/mocks/grade_review/handlers.ts` — ⟨C3⟩ visibly synthetic image, clearly labelled | 16 | ☐ |
| 1c.4 | `e2e/gradeReviewFixtures.ts` — route mock | 17 | ☐ |

**Gate 1c:** `npx tsc --noEmit` · `npx vitest run` · **code review**.

⊘ §6 item 15 (provider cache + `IntersectionObserver` + `Pile*`) — **F1 frontend work by plan §10**,
not phase 1. The seam (1c.2) is what F1 consumes.

## Phase 2 — GCS thumb store

| # | Item | §6 | State |
|---|---|---|---|
| 2.1 | thumb GCS get/put around the render (step 4 of §4.1) | 9 | ☐ |
| 2.2 | `thumb-rendered-once-then-read-from-gcs` | §7 | ☐ |

**Gate 2:** as 1a + the phase-2 test · **code review**.

---

## §7 named tests

| Test | Phase | State |
|---|---|---|
| `page1-image-url-present-on-every-graded-item` | 1b | ☐ |
| `page1-image-url-omitted-when-there-is-no-page-1` | 1b | ☐ |
| `page1-image-url-carries-the-live-variant-token` | 1b | ☐ |
| `page-image-returns-webp-bytes-not-json` | 1a | ☑ |
| `page-image-sets-immutable-cache-headers-only-with-a-variant` | 1a | ☑ |
| `page-image-refuses-an-unknown-variant-token` | 1a | ☑ |
| `page-image-requires-auth` | 1a | ☑ |
| `page-image-refuses-another-tenants-transcription` | 1a | ☑ |
| `page-image-bounds-and-renderer-guards-match-the-json-proxy` | 1a | ☑ |
| `thirty-cards-cost-one-pdf-download` | 1a | ☑ |
| `webp-variant-does-not-evict-or-answer-for-the-review-png` | 1a | ☑ |
| `page-cache-is-bounded-by-bytes-not-entries` | 1a | ☑ |
| `json-page-proxy-bytes-are-unchanged` | 1a | ☑ |
| `thumb-rendered-once-then-read-from-gcs` | 2 | ☐ |

## §8 verification gates

| # | Gate | State |
|---|---|---|
| 1 | `import app.main` + `pytest --collect-only` clean | ☑ 1a |
| 2 | the four backend test files green | ☐ |
| 3 | fixture regeneration is a no-op | ☐ |
| 4 | `npm run gen:api` committed · `tsc --noEmit` · `vitest run` | ☐ |
| 5 | `PIL.features.check("webp")` **inside the built image** | ☐ |
| 6 | one thumbnail eyeballed at the pinned settings | ☑ done pre-plan (§4.3) |

---

## Findings log

Anything discovered during implementation that the plan did not predict goes here, with its
disposition — so a deviation is a recorded ruling, not a silent drift (§0.2/§0.3).

### F-1 (phase 1a review) — non-canonical variant tokens were accepted · FIXED

`600x072@110`, `0600x72@110` and `600x72@0110` all parsed to the same three
numbers as `600x72@110`, so `resolve_variant` reported them **allowed**. No
server-side harm — they map to the same canonical cache key — but a caller could
mint unbounded distinct URLs for identical bytes, which defeats the **browser**
cache that is the entire reason ⟨C1⟩ puts the variant in the URL, and it made
"the URL and the cache key cannot disagree" *nearly* true rather than true.
**Fix:** `_TOKEN_RE` rejects leading zeros (`[1-9]\d{0,4}`). One spelling per
resource. Pinned by `test_variant_token_round_trips_and_rejects_junk`.

### F-2 (phase 1a review) — byte accounting under threads · VERIFIED, pinned

The running total is mutated from many threads and FastAPI renders in a
threadpool, so drift would silently un-bound the cache — the exact defect §2
just fixed. Measured: 8 threads × 400 mixed ops, reported total **exactly**
equals the recomputed truth and stays under budget. Pinned permanently by
`test_byte_accounting_does_not_drift_under_concurrent_use`.

### F-3 (phase 1a review) — blast radius confirmed complete for `page_cache`

`page_cache` has exactly ONE production caller (`api/v0/transcription.py`), both
of whose call sites were updated; `MAX_ENTRIES` has no remaining references
anywhere; `PAGE_RENDER_DPI == 150` is still asserted by
`test_transcription_endpoints.py` and still true. OpenAPI re-dumped: the new
route emits `content: {"image/webp": {}}` with a unique operationId, `v` as an
optional query param, and both page paths coexisting.
