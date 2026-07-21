# PR-5 SPRINT 1 SPEC — The Session Spine

**Design source:** PR5_DREAM_UX.md (deviations need rulings). **Evidence base:**
pr5_context_answers.md (all file:line refs below are from it). **Scope:** flow
mechanics end-to-end — no rebuild. The existing RubricEditor remains the review
surface this sprint; Sprint 2 replaces it. Everything here is independent of
the mirror.
**Discipline:** verify-before-implement holds — surface any census-vs-code
divergence found during work before coding around it. The 8 vitest suites
(E12 list) and both Playwright journeys stay green (updated where the flow
changes, never deleted).

---

## S1-1 — Kill the purpose interstitial

Death list per B4 (page.tsx): the `'purpose'` union member (:84); state
`pendingDocxFile`/`preflightQuestions`/`preflightDetectedTitle` (:271-274) and
their resets (:475-476, :1143-1145); `handlePurposeConfirm`/`handlePurposeSkip`
(:653/:658); JSX :1254-1277; `RubricPurpose.tsx` + `RubricPurposeValues` +
imports (:57-58); the `question_purposes`/`test_topic` fields from
`submitExtractionJob`'s FormData (api.ts:920-923 — frontend stops sending;
backend fields stay accepted/optional, zero backend change).
New flow: `handleRubricFileChange` → validate → submit → `'extracting'`
directly. Accepted loss (ruled): the free-text testTopic input — the only live
input the step contributed (B4's load-bearing nuance: `preflightQuestions` is
always `[]`; the per-question UI was already inert).

## S1-2 — Zero-param submit + the capture card

1. Submit on file-drop with the file only. Client no longer sends `name`
   (backend derives its default from `source_filename`; verify `name` is
   optional server-side — if not, a one-line backend change makes it so).
2. **Backend: metadata-patch endpoint** — `PATCH
   /api/v0/rubrics/extraction-jobs/{id}` accepting `{name?,
   programming_language?}`, merged into `request_params`. Auth + ownership
   (404 cross-tenant); allowed while `queued|extracting|completed`; rejected
   on `failed`. METADATA-ONLY by contract: the runner never reads these
   mid-flight (census B5 proves language was never an extraction input on the
   async path — the contract formalizes existing reality).
3. **The capture card** (extracting screen, movement 1): rubric-name field
   pre-filled with the filename-derived suggestion; language select with
   options from the existing list (B5 :1230-1245) plus default "זיהוי
   אוטומטי". Confirm or skip → card collapses into movement 2 (calm waiting).
   ONE combined PATCH on card-confirm (never per-field racing requests);
   toast-on-error via the errorSurface convention. Implementation (agent
   caveat 4): atomic JSONB merge (`request_params || :patch`), column-
   targeted update only — the runner writes `progress_stage`/heartbeat on the
   same row concurrently.
4. Name precedence at save: captured (state) > extraction-inferred
   (`result.rubric_name`) > filename-derived. The upload-step language
   `<select>` (:1230-1245) dies with this — language now lives only in the
   capture card and the editor metadata panel.

## S1-3 — The wait, redesigned (page.tsx:1313-1334 branch)

1. Promise copy: "עלול לקחת 4–5 דקות" replaces "בדרך כלל 2–4 דקות".
2. Stage rendering: keep the live single current-stage line
   (`getExtractionStageLabel`), and add a compact **stage checklist** —
   completed stages as small ✓ lines, current one active. Honest texture,
   zero fake progress (stages render only when the server reports them).
3. Threshold reassurances, client render logic off the server's
   `elapsed_seconds` (:1323-1329 — no new timer): ≥180s appends "עדיין עובדת —
   מחוונים מפורטים לוקחים יותר"; ≥360s "כמעט שם — המחוון שלך עשיר במיוחד".
4. **Completion signals (net-new app-wide per B6):** on transition to
   `completed` while `document.visibilityState === 'hidden'`: set
   `document.title = "✓ המחוון מוכן — Vivi"` (restore on visibility) and play
   a single gentle chime (small bundled asset; she interacted at upload, so
   autoplay policy is satisfied; wrap in try/catch — a blocked chime must be
   silent, never an error).

## S1-4 — Failure screen (rework of :1281-1312)

Two one-click actions only: «לנסות מחדש» (existing retry wiring) and «דיווח
תקלה» — a `mailto:` link pre-filled with subject "תקלה בחילוץ מחוון" + job id
+ timestamp (zero backend; upgrade path noted for later). Copy: map the known
`error_message` classes from PR-2 (transport/timeout/budget) to
blame-correct teacher language — "תקלה זמנית אצלנו — לא בקובץ שלך. הקובץ שמור,
אין צורך להעלות שוב."; unknown classes get honest-generic. Raw English
`error_message` never renders as the headline (may remain in a collapsed
"פרטים טכניים").

## S1-5 — Arrival summary card

New `rubricStep` value `'arrival'`, entered from `applyExtractionResult`
(:507) before `'review'`. Client-computed from already-hydrated state — zero
backend: selection line first-class from `selectionGroups` ("מבחן בחירה: מענה
על 4 מתוך 6 שאלות"); achievable points via the PR-4 `rubric-achievable.ts`
util; question count; recursive criteria count (write the small recursive
counter — the census shows existing counts are depth-1); findings count = **distinct findings after extraction+live dedup by
`target_id`** (ruling on agent flaw 1: an extraction `rubric_mismatch` and a
live sum-invariant on the same node are one event — live = blocker,
extraction = residual; bagrut counts as "ממצא אחד"). Small pure helper
`countFindings(annotations)` with tests; Sprint 3's card model consumes the
same pairing rule. One primary button: «עברי על המחוון» → `'review'`.
(The one-click fix on this card is Sprint 3; this sprint the card informs.)

## S1-6 — Save overlay + completion card

1. Overlay while saving (isLoading): modal-light with spinner and ONE honest
   static line — "ויוי בודקת עקביות ומרכיבה את חוזה הניקוד…". Deliberately no
   staged animation: the client cannot observe compile stages, and fake
   progression violates the never-lie law (this is a ruled deviation from the
   Dream doc's two-stage phrasing — honesty beats theater).
2. Completion (`'saved'` block :1403-1417 rebuilt): rubric NAME (the resolved
   name per S1-2.4 — the UUID display dies), facts line (questions ·
   achievable points · criteria), the partnership beat verbatim: "המחוון מוכן
   — עברת על הכל ואישרת. מכאן ויוי בודקת לפיו.", primary «המשיכי לבדיקת
   מבחנים», secondary «לדף הבית».

## S1-7 — Carry-through (kills RubricSelection from this journey) + the dead deep-link

1. The primary CTA constructs the `RubricListItem` from save-success state
   (`savedRubricId`, resolved name, `rubricDeclaredTotal`, stats from the
   save response, `is_compiled: true`) → `setSelectedRubric(item)`;
   `setMainMode('grading')`; `setGradingStep('upload_batch')` — replacing the
   current state-flip that discards `savedRubricId` (C8 :1409-1412). She
   lands on upload-tests with her rubric in the header (:1443-1444 reads
   `selectedRubric` directly — no other changes needed).
2. **Wire the dead deep-link** (C8): `page.tsx` reads `?rubric=<id>` on mount
   (read `window.location.search` inside the existing mount effect — NOT `useSearchParams`, which breaks the static build in Next 14.2.5 without a Suspense boundary; agent flaw 3); if present → `getRubric(id)` → on success
   `setSelectedRubric` + jump to `upload_batch` (my-rubrics' existing
   "בדקי מבחנים עם מחוון זה" button starts working); on failure → home,
   toast. One shared `enterGradingWithRubric(item)` helper serves both paths.
3. `RubricSelector` itself remains (it is still the entry for
   grading-without-a-fresh-save); only the post-save journey bypasses it.

## S1-8 — Navigation guard (net-new per E12)

Dirty tracking: a ref set on any `onQuestionsChange`/metadata change after
`applyExtractionResult`, cleared on successful save. Two layers: (a)
`beforeunload` when dirty (browser-native prompt); (b) in-app guards on the
review-step BackButton (:1382) and `goToHome` (:1125): confirm dialog "יש
שינויים שלא נשמרו — לצאת בכל זאת?" before the state flip. Note the census
fact: "navigation" here is state flips, not routes — so the in-app guard is a
wrapper on those two handlers, not router machinery.

## S1-9 — Copy pass + the `scopeLabel` utility

1. **`scopeLabel(targetId, questions)` util** (new, with tests) — a
   positional TREE resolver, not token parsing (ruling on agent flaw 2):
   prefer the node's paper identity when the id token is human-meaningful
   (`q2` → "שאלה 2", `א` → "סעיף א"); fall back to ordinal position ("סעיף
   2") for generated ids (`q_*`, `sq_*`, `c<ts>`). `q1.א.2` → "שאלה 1 · סעיף
   א · תת-סעיף 2"; null/`rubric` → "המחוון". Technical ids must be
   unreachable by construction, including on teacher-added nodes. Apply immediately to the two places raw ids reach her eyes
   today: the summary banner's jump buttons (A3 :651 renders `a.target_id`
   raw) and `RubricErrorDisplay`'s location line. Sprints 2–3 consume the
   same util everywhere — built once here.
2. Sweep: feminine imperatives consistently (העלי/גררי/בחרי/המשיכי); a
   pluralization helper (שגיאה אחת/2 שגיאות, ממצא אחד/N ממצאים) applied to
   the "N שגיאות" badge (:741-749) and the new arrival card; the promise
   copy; the failure copy.

## Tests & acceptance

- Playwright: `driveToReview` (:10-24) updated — no purpose step; assert the
  arrival card; new assertions: completion card shows name not UUID;
  carry-through lands on upload_batch with the rubric header visible; both
  existing journeys green.
- Vitest: capture-card patch calls (mocked), `scopeLabel` table, pluralization
  helper, dirty-guard logic, name-precedence resolution. The 8 existing
  suites untouched and green.
- Backend: patch-endpoint tests (auth/ownership/status-guard/merge
  semantics); zero-param submit accepted.
- Manual session test (the Dream doc §6 subset for this sprint): drop file →
  name it during the wait → honest wait with thresholds → arrival card →
  review → save → completion with name + partnership line → land on
  upload-tests pre-selected; abandoning mid-review prompts the guard; a
  background-tab completion flips the title and chimes.

## Known accepted gap (S4 closes)

A mid-extraction refresh loses the client copy of a captured name; save then
falls back to inferred/filename although the server holds the patched value.
Accepted for this sprint; Sprint 4's resume rework is the first reader of the
PATCH data and closes it.

## Out of scope (S2–S4)

The document-mirror and everything rendering-related inside review;
finding-cards/fix/undo/tracker/survivor-gate (the RubricWarningsModal stays
as-is this sprint); home banner / my-rubrics chip / resume rework (the
existing resume-hijack effect :634-651 stays as-is until Sprint 4);
mini-table parsing.