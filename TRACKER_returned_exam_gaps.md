# TRACKER — returned-exam gaps (PR-G9 follow-up)

Plan: `PLAN_returned_exam_gaps.md` (APPROVED 2026-09-04; OD-1 adopt, OD-2 Option A).
**A row is ticked only when its gate has run**, not when the code is written.

Legend: ☐ todo · ◐ in progress · ☑ done+verified · ⊘ deliberately not done (reason)

---

## Phase A — the dead key (Finding 1a)

| # | Item | State |
|---|---|---|
| A.1 | `grading.py:887` reader → `teacher_overrides` | ☑ |
| A.2 | `batch_grading.py:753` reader → `teacher_overrides` | ☑ |
| A.3 | `returned_exam.py:420/:426` read+write → `teacher_overrides` | ☑ |
| A.4 | `overlay-writer-and-readers-agree-on-one-key` (structural) | ☑ |

## Phase B — the write path (OD-1)

| # | Item | State |
|---|---|---|
| B.1 | `PATCH /graded_test/{id}/stamp_position` — approved+draft, server sets `source="manual"` | ☑ |
| B.2 | invalidates `returned_exam_key` | ☑ |
| B.3 | response shape in `graded_test_responses.py` | ☑ |
| B.4 | `api-types.ts` REGENERATED | ☐ |

## Phase C — the stamp (OD-2, Option A)

| # | Item | State |
|---|---|---|
| C.1 | `draw_stamp` → round, score-bearing; `_STAMP_WORD` retired | ☑ |
| C.2 | score in the vendored face, trimmed-never-rounded | ☑ |
| C.3 | corner arithmetic converges with `stampBox` | ☑ |
| C.4 | frontend divergence test REMOVED (the proof it closed) | ☐ frontend, next |

## Phase D — the appendix (Finding 2)

| # | Item | State |
|---|---|---|
| D.1 | `AppendixScope` record replaces the widening tuple | ☑ |
| D.2 | total (from the contract, never re-summed) | ☑ |
| D.3 | per-scope points | ☑ |
| D.4 | Hebrew scope titles, RTL base | ☑ |
| D.5 | `scopes_for_render` docstring becomes true | ☑ |
| D.6 | `RENDERER_VERSION` bumped | ☑ |

## Phase E — tests rebuilt through the real types

| # | Item | State |
|---|---|---|
| E.1 | `test_returned_exam_endpoints.py` — no hand-built overlay | ☑ |
| E.2 | `test_returned_exam.py` — same | ☑ |
| E.3 | `no-test-hand-builds-a-draft-overlay` (structural) | ☑ |

---

## §7 named tests

| Test | Phase | State |
|---|---|---|
| `overlay-writer-and-readers-agree-on-one-key` | A | ☑ |
| `stamp-set-on-an-approved-exam-reaches-the-pdf` | B | ☑ |
| `stamp-set-on-an-approved-exam-reaches-the-batch-zip` | B | ☑ |
| `apply-to-all-reports-a-count-that-is-true` | A/B | ☑ |
| `no-test-hand-builds-a-draft-overlay` | E | ☑ |
| `appendix-carries-the-total-and-per-scope-points` | D | ☑ |
| `appendix-titles-are-hebrew-prose-not-raw-ids` | D | ☑ |
| `appendix-total-comes-from-the-contract-not-a-resum` | D | ☑ |
| `appendix-hebrew-title-with-a-digit-renders-in-order` | D | ☑ |
| `points-render-trimmed-never-rounded` | C/D | ☑ |
| `renderer-version-bump-invalidates-every-cached-render` | D | ☑ |
| `stamp-is-round-and-carries-the-score` | C | ☑ |

## Gates

| # | Gate | State |
|---|---|---|
| 1 | `import app.main` + `pytest --collect-only` | ☐ |
| 2 | pytest in TWO invocations, green | ☐ |
| 3 | `npm run gen:api` + `tsc --noEmit` + `vitest run` | ☐ |
| 4 | one rendered appendix page + one stamped page 1 eyeballed | ☐ |

## Findings log

Anything the plan did not predict, with its disposition.

### Phase A/B code review (2026-09-04) — four findings, all fixed

Reviewed by probing what was most likely wrong, not by re-reading the diff
approvingly. Two of the four were real defects; one concern was closed by
measurement rather than argument.

**F-1 · REAL BUG · fixed.** `PATCH …/stamp_position` answered
`returned_exam_state: "stale"` unconditionally. On an exam nobody has rendered
that is a lie, and not a harmless one — the frontend drives P8's re-sign banner
off this state, so it would have asked her to re-sign something that was never
rendered. Now derived from whether a key existed to invalidate.
**Mutation-tested:** restoring the unconditional "stale" fails the new test.

**F-2 · MISSING COVERAGE · fixed.** The DoD requires the stamp to reach the PDF
**and the batch ZIP**; the first pass only covered the row. The ZIP is the OTHER
reader that was on the dead key, so it was the half more likely to still be
broken. The new test drives the real endpoint and asserts the archive addresses
the object keyed for HER position. **Mutation-tested:** reverting
`batch_grading.py` to the dead key fails it.

**F-3 · MISSING COVERAGE · fixed.** Finding B's second half was untested:
`stamp_applied_count` feeds `settings_changed`, which is what drops
`returned_exam_key`. While the key was dead, «apply to all» not only reported 0
— it never invalidated a single cached render. Now asserted on both halves.

**F-4 · LAYERING · fixed.** `OVERLAY_KEY` was defined in `returned_exam.py`, a
RENDERING service, though it states where a SCHEMA field is persisted. Moved to
`graded_test_draft.py` beside the model that declares it and re-exported;
`override_attribution.py` — a fifth site, and the one that always had the key
RIGHT — now uses the constant instead of its own literal.

**Closed by measurement, not a defect:** the endpoint round-trips
`draft_json` through `GradedTestDraft.model_validate(...).model_dump(...)`, and
pydantic's default `extra='ignore'` would silently drop unknown keys. Checked
against a real published draft: **zero keys dropped, zero added.** No data loss.

52 green across the endpoints, service, overlay-key and approval suites.

### Phase C/D findings

**F-5 · the golden "layout guard" could not fire · FIXED.** It tolerated 2% of
ALL sampled pixels on a page that is **0.40% ink** — five times more slack than
there is ink to move. It duly passed through this very rewrite, which changed
every heading and added a points line to every scope (1.04% of pixels moved).
A guard calibrated against the background is decorative. Now measured against
the golden's INK: the same change registers **262%**, and the tolerance is 25%.
Golden regenerated, since the content changed by ruling.

**F-6 · A PRE-EXISTING BIDI DEFECT IN WRAPPED FEEDBACK · SURFACED, NOT FIXED.**
Found while eyeballing the rendered appendix (§8 gate 4 earning its place).

`_bidi_for_pymupdf` reorders a WHOLE paragraph into one visual line — its END is
the logical START. That is correct for a line, and the Story then WRAPS it
left-to-right, so the tail of the visual string (the logical beginning) lands on
the LAST line. Measured:

    logical:  "המחלקה Hobby הוגדרה נכון עם … durationInMinutes."
    visual  :  ".durationInM…"                     ← starts here
    visual  :  "… Hobby המחלקה"                    ← the FIRST word, at the end

Short paragraphs fit one line and render perfectly, which is why it hid. **Every
paragraph that wraps reads with its first line last** — and feedback prose
almost always wraps. It affects the feedback and summary text only; the header,
total, titles, points and breakdown are single-line and correct.

NOT caused by this work (`<p>{feedback}</p>` and `_bidi_for_pymupdf` are
untouched) and NOT fixed here, deliberately: correct bidi under wrapping means
line-breaking BEFORE reordering, i.e. owning the line breaks with the font
metrics — and this is the module CLAUDE.md §8 explicitly warns against
re-deriving from first principles ("three alternatives were falsified against a
real render"). It needs its own decision, and it blocks the pilot as squarely as
the two gaps this task named.
