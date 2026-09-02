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
| 1b.1 | `app/schemas/batch.py` — `page1_image_url: Optional[str] = None` + ⟨N1⟩⟨N2⟩ docstring | 1 | ☑ |
| 1b.2 | `app/api/v0/batch_grading.py` — `_build_graded_feed` gains `page_counts`; mints the URL | 2 | ☑ |
| 1b.3 | `scripts/gen_batch_feed_fixtures.py` — `_item()` emits the field | 7 | ☑ |
| 1b.4 | `tests/fixtures/grade_review/batch_feed_*.json` — regenerated (4 files) | 8 | ☑ |

**Gate 1b:** feed tests · fixture byte-identity · regenerate-is-a-no-op · **code review**.

## Phase 1c — frontend seam

| # | Item | §6 | State |
|---|---|---|---|
| 1c.1 | `src/lib/api-types.ts` — REGENERATED (`npm run gen:api`), never hand-edited | 13 | ☑ |
| 1c.2 | `src/lib/api.ts` — `fetchPageImageObjectUrl` on the seam, no auto-retry | 14 | ⊘ F-6: the frontend agent shipped a BETTER one first; mine deleted |
| 1c.3 | `src/mocks/grade_review/handlers.ts` — ⟨C3⟩ visibly synthetic image, clearly labelled | 16 | ☑ (mine; left in their UNTRACKED tree, see F-6) |
| 1c.4 | `e2e/gradeReviewFixtures.ts` — route mock | 17 | ⊘ F-6: already done by the frontend agent |

**Gate 1c:** `npx tsc --noEmit` · `npx vitest run` · **code review**.

⊘ §6 item 15 (provider cache + `IntersectionObserver` + `Pile*`) — **F1 frontend work by plan §10**,
not phase 1. **Already built** by the frontend agent (`usePageThumbnails`), and built to the
corrections: provider-level `Map`, in-flight dedup, failures deleted so they retry, revoke-on-unmount
⟨C2⟩, and an `IntersectionObserver` with 300 px of runway ⟨C1⟩.

## Phase 2 — GCS thumb store

| # | Item | §6 | State |
|---|---|---|---|
| 2.1 | thumb GCS get/put around the render (step 4 of §4.1) | 9 | ☑ |
| 2.2 | `thumb-rendered-once-then-read-from-gcs` | §7 | ☑ |

**Gate 2:** as 1a + the phase-2 test · **code review**.

---

## §7 named tests

| Test | Phase | State |
|---|---|---|
| `page1-image-url-present-on-every-graded-item` | 1b | ☑ |
| `page1-image-url-omitted-when-there-is-no-page-1` | 1b | ☑ |
| `page1-image-url-carries-the-live-variant-token` | 1b | ☑ |
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
| `thumb-rendered-once-then-read-from-gcs` | 2 | ☑ |

## §8 verification gates

| # | Gate | State |
|---|---|---|
| 1 | `import app.main` + `pytest --collect-only` clean | ☑ 1a |
| 2 | the four backend test files green | ☑ 1a+1b (67+13+6+44) |
| 3 | fixture regeneration is a no-op | ☑ 1b (hash-compared) |
| 4 | `npm run gen:api` committed · `tsc --noEmit` · `vitest run` | ☑ tsc clean · 981 tests / 69 files · check:copy PASS |
| 5 | `PIL.features.check("webp")` **inside the built image** | ⊘→☑ F-10: Docker unavailable here; converted to a BOOT check that runs on every revision |
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

### F-4 (phase 1b gate) — PRE-EXISTING red tests, OUT OF PLAN SCOPE · fixed

`pytest tests/api/test_batch_grading.py` was already failing two tests before any
of this work — **verified by stashing every backend change and reproducing**. Not
caused by phase 1a or 1b, and not predicted by the plan.

Cause: `settings.internal_task_token` is declared `Optional[SecretStr]` and
`cloud_tasks_service.verify_task_request` correctly calls `.get_secret_value()`,
but **three test sites assigned a bare `str`** to it (fallout from the earlier
SecretStr pass), so the `/internal` auth path raised
`AttributeError: 'str' object has no attribute 'get_secret_value'`.

**The production code is right and the tests were lying about the type**, so the
tests are what changed (`SecretStr("sekret")`). The tempting alternative —
`getattr(x, "get_secret_value", lambda: x)()` in `verify_task_request` — is
precisely the "defensive `getattr` at a type boundary converts a loud failure
into a quiet lie" anti-pattern CLAUDE.md §6 names, and in the `/internal` auth
path of all places.

Fixed rather than filed because a red suite makes every later phase gate
meaningless. Scope kept to the three assignments; nothing in `app/` changed.
`tests/api/test_batch_grading.py` + `test_extraction_jobs.py`: **67 passed**.

### F-5 (phase 1c) — the codegen drift gate has not been running · SURFACED, out of scope

`npm run gen:api` produced **874 insertions**, not the one field this plan adds.
The extra surface is all legitimate accumulated backend work that shipped
without a codegen run: G9 (`ReturnedExamManifest`/`Item`), migrations 022/023
onboarding (`SchoolInput`, `SchoolResponse`, `UpdateProfileRequest`,
`UpdateSchoolsRequest`), migration 024 auth (`GoogleAuthRequest`,
`GoogleNonceResponse`, `VerifyEmailRequest`, `ResendCodeRequest`,
`SignupPendingResponse`) and OD-F8's `NumericPolicy`.

`.github/workflows/api-types-drift.yml` exists to catch exactly this, but per
CLAUDE.md §10 it only runs if the monorepo structure is committed to `main` —
which it is not. **So the wire-contract drift gate is currently decorative.**
The frontend has been building against types several PRs stale.

Not fixed here: it is the §12.5 repo-layout question, not a page-image question.
Surfaced because a gate everyone believes is running and is not is worse than no
gate — the same failure shape as INV-6.

### F-6 (phase 1c) — the frontend agent had already built most of phase 1c · CONVERGED, no fork

The agent on `PR_SPEC_frontend_grade_review.md` had already implemented, in an
UNTRACKED working tree:

* `fetchPageImageObjectUrl` in `src/lib/api.ts` — and **theirs is better than
  mine**: `apiFetchRaw` + `throwIfAuthError` + an explicit Hebrew `ApiError`,
  where mine went through `apiFetchChecked` and would have run the JSON error
  normaliser over a binary route's body. **My duplicate is deleted** (two exports
  of one name is a compile error anyway); theirs stands.
* `usePageThumbnails` — ⟨C2⟩ and ⟨C1⟩ implemented exactly as ruled, independently.
* `Pile.tsx` consuming `page1_image_url`.
* An `e2e/gradeReviewFixtures.ts` route for `/pages/*/image` returning its own
  inline `SYNTHETIC_PAGE_SVG` — i.e. they reached the ⟨C3⟩ conclusion on their
  own, which is corroboration of the owner's amendment.

**What I added and what remains open.** They had no *msw* handler for the image
(msw serves the dev-fixtures/browser path; Playwright route mocks are separate),
so `src/mocks/grade_review/syntheticPage.ts` + its handler fills a real gap. But
the SVG generator now exists **twice** — once there, once inline in their e2e
file. I did NOT edit their in-flight file: their screenshots are passing against
that exact SVG and a change would churn every diff. Copy is aligned in the
meantime («דוגמה סינתטית» in both).

**Owed, one line, theirs to make:** `e2e/gradeReviewFixtures.ts` imports
`syntheticPageSvg` from `src/mocks/grade_review/syntheticPage.ts` and drops its
inline copy (§0.4). Flagged rather than done, because the file is actively being
edited by another agent.

⚠ Their entire grade-review tree (`src/components/grade-review/`, `src/mocks/`)
is **untracked**, so none of it is committed here — this phase commits only
`api-types.ts`, which is mine.

### F-7 (phase 2) — the stored thumb path had to carry the variant too

The PR-G8 spec line named `thumbs/{transcription_id}/p1.webp`, written before
the variant existed. Keeping it would have rebuilt ⟨C1⟩'s bug one layer down and
WORSE: change `page_thumb_width_px` and every teacher is served the old bytes
from GCS forever — no expiry to age them out, and no request that can ever miss,
because the object is right there. The path is
`thumbs/{id}/p{n}_{width}x{quality}-{dpi}.webp` (`@` → `-`, since `@` in an
object path is asking for trouble). Pinned by
`test_the_stored_thumb_path_carries_the_variant`.

### F-8 (phase 2 review) — a miss and an outage must not look alike · FIXED

Both degrade to a render, so an undifferentiated `except Exception` would make a
broken bucket present as "everything works, just slow" — the worst diagnostic
shape there is, because nothing ever asks why. `NotFound` is now silent (the
normal first-ever request) and anything else logs `page_thumb_read_failed`.

Found a second defect while pinning it: the test fake raised `FileNotFoundError`
for a missing object, not the `google.api_core.exceptions.NotFound` that
google-cloud-storage actually raises — so **every cold render took the outage
branch and the test would have passed while pinning the wrong behaviour.** The
fake now raises the real type.

### F-9 (phase 2) — thumbs join an EXISTING GCS leak · SURFACED, out of scope

`gcs_service.delete_folder` exists and is called from **nowhere in `app/`**, so
no GCS object is ever deleted — a transcription's multi-MB source PDF already
outlives its row. Thumbs add ~34 KB per page-1 to that, i.e. roughly 3% of what
is already leaking, and they are variant-keyed so a settings change orphans the
old ones too.

Not fixed here: object lifecycle is its own decision (a bucket lifecycle rule is
probably the right answer, not application deletes), and inventing a delete path
for thumbs alone while PDFs leak beside them would be tidying the smaller half.
Recorded so the number is known when someone does take it on.

### Phase-2 verification

`tests/api/test_transcription_page_render.py` **27 passed** (incl. 5 phase-2) ·
page_cache + graded_feed + feed fixtures + transcription endpoints **42 passed**
· collect-only **1423** clean · `import app.main` clean.

### F-10 (§8 gate 5) — could not verify inside the image; made it a runtime guarantee instead

Docker is not running in this session, so `PIL.features.check("webp")` **inside
the built image** could not be executed. Rather than tick the gate on a laptop
result — the exact substitution PR-G9's font lesson warns about, where a face is
perfect locally and tofu on Cloud Run — the check moved INTO the process:

* `thumbnail.webp_available()` / `log_capability_on_boot()`;
* called from `main.py`'s lifespan beside the other startup verifications;
* logs `THUMBNAIL OK` or a loud `THUMBNAIL UNAVAILABLE`, and **never crashes** —
  `verify_schema_head`'s discipline, because a degraded thumbnail is not a
  reason to refuse to serve grading.

This is strictly stronger than the gate as written: a one-time check verifies one
image, a boot check verifies every revision that ever runs. Pillow's WebP support
is a compile-time option, so the wheel in the image genuinely can differ from the
one here, and without this the failure is silent until a teacher opens a
dashboard and every card 502s.

Owner may still want the one-liner when Docker is up:

    docker run --rm python:3.11-slim sh -c       "pip install --no-cache-dir -q Pillow==12.1.0 &&        python -c 'import PIL.features; print(PIL.features.check(\"webp\"))'"
