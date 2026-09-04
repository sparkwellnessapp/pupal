# PLAN — the two pilot-blocking gaps in the returned exam (PR-G9)

**Status: APPROVED BY NOAM, 2026-09-04.** Both open decisions ruled — see §3 and §4.

> **OD-1 RULED — adopt as proposed.** A dedicated `PATCH /graded_test/{id}/stamp_position`
> accepting `approved` and `draft` rows, not extending the chain, invalidating
> `returned_exam_key`. (Implementation carries the §3 amendment: the server sets
> `source="manual"`.)
>
> **OD-2 RULED — Option A.** The PDF stamp becomes **round and score-bearing**, matching the
> spec, the mockup and the shipped frontend. The «נבדק» ellipse goes.

Every claim in the task was checked against source on `perf/rubric-extraction-latency`. **All of
them hold.** Two corrections and three additional findings are recorded below — the corrections
matter because one of them changes the OD-1 argument.

---

## 1. The problem, in Deutsch form

**Data.** The S12 preview exists so that *what she previews and signs is what the student
receives*. Two observations falsify that today:

1. A stamp dragged on the preview can never reach the PDF — the readers key on
   `draft_json["overrides"]`, a key nothing writes, and the only endpoint that writes a stamp
   refuses the only status the preview renders.
2. The rendered appendix carries **no total and no per-scope points**, and labels every question
   with the internal id `q1.א`. The preview carries all three.

**Theory under criticism.** *"The returned exam is rendered; the preview shows the render."* It is
encoded that way — one renderer, one preview, a parity test between `stampBox` and `draw_stamp`.
The theory is falsified twice: the two artefacts disagree about the stamp's **position** (gap 1)
and about the page's **content** (gap 2), and in both cases the preview is the one that matches
the spec.

**Better conjecture.** The renderer and the preview must be two views of ONE content model: the
same fields, in the same order, from the same frozen contract. Gap 1 is a key mismatch plus a
missing write path; gap 2 is a renderer that was built before the spec's §4.3 P4 content list.

**Criticism.** Is it hard to vary? Two things are load-bearing. The appendix content list is
already pinned on the frontend by `buildAppendix`, so "matching" is checkable, not a matter of
taste. And the cache key covers every input that can change a pixel — so any content change is
inert on already-rendered exams unless `RENDERER_VERSION` moves, which makes the version bump part
of the fix rather than an afterthought. Does it introduce new contradictions? One, and it is
OD-1: writing a stamp onto an approved row touches LCY-2.

---

## 2. Verification — every claim, checked

| Claim | Verdict | Evidence |
|---|---|---|
| Writers use `teacher_overrides` | ✅ | `grading.py:715`, `:818` |
| Readers use `overrides` (4 sites) | ✅ | `grading.py:887`, `batch_grading.py:753`, `returned_exam.py:420` + write at `:426` |
| A real draft has no `overrides` | ✅ | `draft_dan_basiuk.json` — `teacher_overrides` present, `overrides` absent |
| `PATCH /draft` refuses non-draft | ✅ | `grading.py:641-644`, 409 |
| Returned-exam endpoint requires approved | ✅ | `grading.py:877-880`, 409 |
| Tests hand-build the wrong shape | ✅ | `test_returned_exam_endpoints.py:79-88`, `test_returned_exam.py:207-230` |
| Appendix carries no total / no points | ✅ | `render_appendix_pdf:203-245` |
| `scopes_for_render` docstring lies | ✅ | `:458` promises "with its points"; returns `(sid, text, criteria_or_None)` |
| Stamp is a 2:1 ellipse bearing «נבדק» | ✅ | `_STAMP_WORD:55`, `_STAMP_FRACTION = 0.16`, height `w * 0.5` |

### Correction 1 — one cited symptom is not a bug

The task lists `tests/api/test_graded_test_approval.py` among the hand-built-overlay offenders (via
the `"overrides"` grep). **It is not.** Those are `PATCH /draft` **request bodies**, where
`overrides` is the correct and declared field name (`body.overrides`). The DoD phrase "no test
constructs `draft_json["overrides"]`" is the right rule; the request-body sites are compliant with
it already. Only the two named files are offenders.

### Correction 2 — `source: "auto"` is never persisted

`auto_stamp_position` is computed at RENDER time (`returned_exam.py:338`) and flows straight into
`draw_stamp`; it is never written to `draft_json`. Consequence for the design: the new endpoint
should **stamp `source="manual"` server-side** rather than trust the client, because that field
gates whether «apply to all» may clear the position — a client that sent `auto` could make the
teacher's own placement erasable. (It also means `apply_stamp_default_to_draft`'s auto-clearing
branch is reachable only by legacy sourceless rows, which its own test already covers. Noted, not
changed.)

### NEW FINDING A — the LCY-2 exception already exists, and is currently dead

`rename_batch`'s «apply to all» selects the batch's graded tests with **no status filter** and
writes `row.draft_json` (`batch_grading.py`, the `apply_stamp_default_to_draft` loop). So the
codebase **already mutates approved rows' `draft_json` for exactly this purpose.** OD-1 is
therefore not "add a new exception to LCY-2" — it is "make an exception that already exists
coherent, by giving the per-test case the write path the batch case has." That is a materially
stronger argument than the one the task offers, and it is the reason I think the recommendation is
right rather than merely convenient.

### NEW FINDING B — `stamp_applied_count` is worse than 0

It is not merely "permanently 0". `rename_batch` sets `settings_changed = settings_changed or
stamp_applied > 0`, and `settings_changed` is what invalidates `returned_exam_key`. So the dead key
also means **«apply to all» never invalidates any cached render** — a batch-default change can
leave already-rendered exams serving the old stamp. Same root cause, a second and quieter symptom.

### NEW FINDING C — the appendix omits the excluded scopes correctly, and must keep doing so

`scopes_for_render` skips `counted_in_total == false`, and `buildAppendix` mirrors it. Adding a
TOTAL must not reintroduce them: the total comes from `contract.total_score` /
`contract.total_possible`, never from re-summing the rendered scopes (§5 — no consumer re-derives
the total; that re-derivation is what halved every selection exam). On exam 2 (choose-4-of-6) the
difference is not cosmetic.

---

## 3. OD-1 — how an approved row's stamp gets written · **RULED: ADOPT (Noam, 2026-09-04)**

**Proposal (the task's):** a dedicated `PATCH /graded_test/{id}/stamp_position` accepting `approved`
and `draft` rows, not extending the chain, invalidating `returned_exam_key`.

**I recommend adopting it.** Critique, as asked:

* **The LCY-2 argument is sound and stronger than stated** — see Finding A. The stamp is not part
  of what LCY-2 froze: the frozen artefact is `contract_json`, which contains no stamp. And the
  batch path already writes `draft_json` on approved rows.
* **`returned_exam_key` invalidation is mandatory**, and the task is right to insist. The stamp is
  in the cache key, so without it the next fetch serves the old page — §3.5a's "a stale returned
  exam looks entirely correct", the one failure this feature cannot have. Mechanism: set
  `returned_exam_key = None`, the same move `rename_batch` already uses.
* **Amendment I propose: the server sets `source="manual"`**, per Correction 2. The client's value
  is not trusted for a field that decides whether the teacher's own placement is erasable.

**The tempting wrong answer, named so it is not chosen later:** relaxing `PATCH /draft` to accept
approved rows. That endpoint also writes `terminals` and `feedback` overrides — i.e. the grading
decision — so relaxing it *would* be a real LCY-2 violation, on the same request that legitimately
moves a stamp. A separate endpoint is what keeps the narrow exception narrow.

Rejected alternatives: `manual_edit` (un-signs the exam and creates a version for a cosmetic
change); batch-default only (§4.3 P3 requires per-test drag); a new column (new DDL for data that
already has a home).

**Wire shape proposed:** `PATCH /api/v0/grading/graded_test/{id}/stamp_position`, body
`{"stamp_position": StampPosition | null}` (null clears), response `{"stamp_position": …,
"returned_exam_state": "stale"}`. Regenerating `api-types.ts` is part of the work.

## 4. OD-2 — the stamp draws «נבדק»; the preview draws the SCORE · **RULED: OPTION A (Noam, 2026-09-04)**

The PDF becomes round and score-bearing. The divergence was real and had been documented on the
frontend as reported-not-resolved (`AppendixPage.tsx` carries the same note for the appendix); it
is now resolved in the PDF's favour of the spec.

| | Option A — PDF becomes round + score-bearing | Option B — preview becomes «נבדק» ellipse |
|---|---|---|
| Matches | spec §4.3, the mockup, the shipped frontend | today's PDF |
| Student sees | their grade on page 1, in a teacher's red pen | a «checked» mark, grade only in the appendix |
| Frontend work | none | rewrite `StampSvg`, re-shoot every P3 screenshot |
| Side effect | `stampBox`'s corner arithmetic converges with `draw_stamp` exactly; the pinned divergence test in `returned-exam.test.ts` becomes removable | the divergence test stays forever |
| Risk | the score must render in the vendored Hebrew face at stamp size — a new render to verify | none |

**Ruled A.** Three of the four artefacts that describe this feature (spec, mockup, shipped
frontend) already said round-and-score-bearing; the PDF was the outlier.

**Geometry consequence, now in scope:** the ellipse's height is `w * 0.5` while the frontend
assumes a square box of side `w`, so corner placement differs by `w/4` vertically. That is exactly
what the pinned divergence test in `returned-exam.test.ts` measures — with A the two renderers'
corner arithmetic converges and that test becomes removable. **Removing it is part of this work**,
and its removal is the proof the divergence closed rather than moved.

**What the stamp must now carry:** the score, formatted by the same trimmed-never-rounded rule as
the appendix, in the vendored Hebrew face at stamp size — `helv` cannot render it and the face is
already vendored for the appendix. `_STAMP_WORD` («נבדק») is retired.

---

## 5. Gap 2 — the appendix content

The contract to meet is `frontend/src/utils/returned-exam.ts::buildAppendix` +
`AppendixPage.tsx`, in content and order:

```
header:  {student_name} · «משוב על המבחן»
TOTAL:   {total} / {possible}          ← red, absent today
per scope (counted_in_total only, in contract order):
         «שאלה 1, סעיף א»              ← Hebrew title, raw id today
         {awarded} / {possible}         ← absent today
         optional breakdown             ← present today, gated on include_criteria
         {feedback}                     ← present today
«סיכום» {summary}
footer   «הופק על ידי Vivi. הציון נקבע על ידי המורה.»
```

**Design points, deliberate:**

* `render_appendix_pdf`'s `scopes` parameter is a 3-tuple. Adding points would make it a 5-tuple
  positional — the shape where a caller silently swaps two strings. I propose a small frozen
  `AppendixScope` record instead (§0.4: a real type over a widening tuple), mirroring the
  frontend's own `AppendixScope`.
* **Points formatting must match `formatPoints`** — trailing zeros trimmed, never rounded
  (`79.50` → `79.5`, `8` stays `8`). The Decimal is what freezes; only the display is trimmed. A
  shared helper, tested against the frontend's own table.
* **The total comes from the contract** (`total_score` / `total_possible`), never from re-summing
  rendered scopes — Finding C.
* **Bidi:** `שאלה 1, סעיף א` is PROSE, not an identifier, so it takes an RTL base — unlike the raw
  scope id, which takes LTR for the documented reason. A title containing a digit next to Hebrew
  is exactly the shape that exposed the half-bidi defect, so it gets a rendered per-character
  assertion, not an eyeball.
* **`scopes_for_render`'s docstring becomes true** rather than being edited to match the omission.
* **`RENDERER_VERSION` bumps.** Without it every already-rendered exam keeps serving the old page.

---

## 6. File changes

| File | Change |
|---|---|
| `app/api/v0/grading.py` | key fix `:887`; NEW `PATCH …/stamp_position` (OD-1) |
| `app/api/v0/batch_grading.py` | key fix `:753` |
| `app/services/returned_exam.py` | key fix `:420`/`:426`; appendix content; `AppendixScope`; `RENDERER_VERSION` bump; docstring |
| `app/schemas/graded_test_responses.py` | the new endpoint's response shape |
| `frontend/src/lib/api-types.ts` | REGENERATED (`npm run gen:api`) |
| `tests/api/test_returned_exam_endpoints.py` | rebuilt through the real schema + endpoints |
| `tests/services/test_returned_exam.py` | same; plus the appendix-content assertions |

**No migration.** 020 and 021 supply everything; head stays 024.

## 7. Named tests

| Name | Pins |
|---|---|
| `stamp-set-on-an-approved-exam-reaches-the-pdf` | the DoD round-trip, through the real endpoint |
| `stamp-set-on-an-approved-exam-reaches-the-batch-zip` | the second reader |
| `apply-to-all-reports-a-count-that-is-true` | Finding B, both halves — count AND cache invalidation |
| `no-test-hand-builds-a-draft-overlay` | structural: greps the test tree for `draft_json["overrides"]` |
| `overlay-writer-and-readers-agree-on-one-key` | structural: the four sites and the writer |
| `appendix-carries-the-total-and-per-scope-points` | gap 2 |
| `appendix-titles-are-hebrew-prose-not-raw-ids` | gap 2 |
| `appendix-total-comes-from-the-contract-not-a-resum` | Finding C, on a selection exam |
| `appendix-hebrew-title-with-a-digit-renders-in-order` | per-character bbox, the bidi shape |
| `points-render-trimmed-never-rounded` | parity with `formatPoints` |
| `renderer-version-bump-invalidates-every-cached-render` | the staleness guard |

## 8. Gates

`import app.main` · `pytest --collect-only` · pytest in TWO invocations · `npm run gen:api` +
`tsc --noEmit` if the wire shape lands · one rendered appendix page eyeballed.
