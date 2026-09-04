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
| B.1 | `PATCH /graded_test/{id}/stamp_position` — approved+draft, server sets `source="manual"` | ☐ ☑ |
| B.2 | invalidates `returned_exam_key` | ☐ ☑ |
| B.3 | response shape in `graded_test_responses.py` | ☐ ☑ |
| B.4 | `api-types.ts` REGENERATED | ☐ |

## Phase C — the stamp (OD-2, Option A)

| # | Item | State |
|---|---|---|
| C.1 | `draw_stamp` → round, score-bearing; `_STAMP_WORD` retired | ☐ |
| C.2 | score in the vendored face, trimmed-never-rounded | ☐ |
| C.3 | corner arithmetic converges with `stampBox` | ☐ |
| C.4 | frontend divergence test REMOVED (the proof it closed) | ☐ |

## Phase D — the appendix (Finding 2)

| # | Item | State |
|---|---|---|
| D.1 | `AppendixScope` record replaces the widening tuple | ☐ |
| D.2 | total (from the contract, never re-summed) | ☐ |
| D.3 | per-scope points | ☐ |
| D.4 | Hebrew scope titles, RTL base | ☐ |
| D.5 | `scopes_for_render` docstring becomes true | ☐ |
| D.6 | `RENDERER_VERSION` bumped | ☐ |

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
| `stamp-set-on-an-approved-exam-reaches-the-batch-zip` | B | ☐ |
| `apply-to-all-reports-a-count-that-is-true` | A/B | ☐ |
| `no-test-hand-builds-a-draft-overlay` | E | ☑ |
| `appendix-carries-the-total-and-per-scope-points` | D | ☐ |
| `appendix-titles-are-hebrew-prose-not-raw-ids` | D | ☐ |
| `appendix-total-comes-from-the-contract-not-a-resum` | D | ☐ |
| `appendix-hebrew-title-with-a-digit-renders-in-order` | D | ☐ |
| `points-render-trimmed-never-rounded` | C/D | ☐ |
| `renderer-version-bump-invalidates-every-cached-render` | D | ☐ |
| `stamp-is-round-and-carries-the-score` | C | ☐ |

## Gates

| # | Gate | State |
|---|---|---|
| 1 | `import app.main` + `pytest --collect-only` | ☐ |
| 2 | pytest in TWO invocations, green | ☐ |
| 3 | `npm run gen:api` + `tsc --noEmit` + `vitest run` | ☐ |
| 4 | one rendered appendix page + one stamped page 1 eyeballed | ☐ |

## Findings log

Anything the plan did not predict, with its disposition.
