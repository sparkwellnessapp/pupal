# Backlog — surfaced findings not owned by the PR that found them

Each item names its evidence and its trigger. Do not fold these into an unrelated PR.

---

## ⚠️ A pattern worth naming: **the consumer that silently drops the payload**

PR-3 hit this **five times in one day**, and the deploy-day E2E is what forced every one of
them out. Four were invisible to a 200-test green suite:

1. **The wizard dropped `selection_groups` on save.** The compiler was correct; the *save
   payload* never carried the groups, so the backend recomputed "achievable" as the full
   offered sum and rejected the rubric on INV-4. PR-3's headline win — *a selection exam
   compiles* — was **unreachable through the product** despite being green in every test.
2. **The API dropped the Hebrew.** The compiler wrote real `message_he`; the payload
   builder overwrote it with the *English* string — an RTL UI confidently rendering
   English at the one moment a teacher is told her rubric is wrong.
3. **The wizard dropped the error list.** `RubricErrorDisplay` renders node + numbers +
   Hebrew beautifully… and the wizard never called it, flattening a precise rejection to
   the generic sentence "שגיאה בהכנת המחוון".
4. **`AnnotationSchema` dropped four fields.** A parallel API mirror of `Annotation`
   carrying 5 of its 9 fields. `_annotation_to_schema` fed it, so the compiler's
   `invariant`/`expected`/`actual`/`message_he` fell off the truck on the way out. The
   deployed API answered a real INV-2 violation with `invariant: null, expected: null,
   actual: null` and an **English** sentence in the field named `message_he`. Two things
   conspired: the duplicate schema (a §0.4 violation), and my own `getattr(err, ..., None)`
   defensiveness in the payload builder, which turned a **type error into a silent
   truncation**. Fixed by making the mirror total, and pinned by a structural test that
   set-compares the two field lists so the *next* added field cannot go missing.
5. **`calculate_rubric_stats` was the FIFTH re-summing site.** It Σ'd every question's
   `total_points` — the OFFERED sum — reporting 100 for an exam achievable at 50. Not
   cosmetic: the save path writes it to the **`rubrics.total_points` column**, so the row
   contradicted its own `contract_json` and the rubric card advertised a total the grader
   would never award. It also counted only depth-1 criteria (18 → reported 6 on a nested
   rubric): the same nesting-blindness INV-2 had. Now the contract's total is passed in as
   authoritative and nothing is re-summed. **Blast radius audited: exactly 1 row, an E2E
   artifact of our own; all 41 real compiled rubrics agree with their contracts** — because
   before PR-3 no selection exam could compile, so no teacher was ever exposed.

**The lesson:** *"no deployable state where the compiler accepts what a consumer
mishandles"* has to include consumers **upstream** of the compiler (the save payload),
**downstream of the response** (the renderer), and **alongside it** (a schema mirror, a
stats function, a persisted column). A green backend test suite proves the engine works; it
says nothing about whether the value reaches the teacher. **When a PR changes what a payload
MEANS, grep every producer and every consumer of that payload, and drive the real path
once.** Findings 4 and 5 were invisible to 200 passing tests and took one live request to
expose.

**Two smaller rules fell out of it:**
- **A duplicate schema is not a style problem, it is a truncation waiting to happen.** §0.4
  says one concept one place; `AnnotationSchema` is the counter-example, still standing.
  Deleting it (serve `Annotation` directly) is the real fix — filed as **B-10**.
- **Defensive `getattr(x, "field", None)` at a type boundary converts a loud failure into a
  quiet lie.** Prefer the attribute access that raises.

All five fixes shipped with PR-3, because a fix whose value cannot reach a teacher is not
shipped. B-5 (below) is the same family, deliberately left to PR-4 because its full form is
genuinely new work rather than a dropped field.

**Sixth instance (browser E2E, deploy day + 1).** Uploading bagrut through the actual
browser white-screened with `TypeError: e.toFixed is not a function`. Same class exactly:
`ExtractRubricResponse.total_points` is *typed* `number` but arrives as the Decimal string
`"100.0"`, and `page.tsx` stored it raw — the one rubric point value that bypassed the
`safeParseFloat` hydration boundary. It reached `formatPoints(n.toFixed(2))` and crashed the
review screen the moment INV-R3 fired (which is only when a rubric has a real discrepancy —
so the screen died precisely when it had something to tell the teacher). TypeScript "confirmed"
it was a number and everyone believed it, just like `getattr(..., None)` did on the backend.
Fixed at the boundary (coerce) + a formatter seatbelt (never let display code unmount the
app). Two lessons reinforced: **a `number` type on a field that crosses the wire is a claim,
not a guarantee — coerce at the boundary**; and **the curl E2E that "passed" bagrut only
exercised the server's compile response, never the browser's client-side validation** — the
real path includes the render.

---

## B-10. Delete `AnnotationSchema` — serve `Annotation` directly

**Found by:** PR-3 deploy day (finding 4 above). **Owner:** PR-4 (it already owns the
annotation-rendering surface).

`app/schemas/rubric_management.py::AnnotationSchema` is a hand-maintained mirror of
`ontology_types.Annotation`. It has already silently truncated the teacher's diagnosis once.
The structural test (`tests/services/test_payload_fidelity.py::
test_annotation_schema_mirrors_every_annotation_field`) now *detects* divergence, but the
right fix is to remove the second copy, per §0.4. Requires deciding what the API should
*not* expose (`confidence`, `source_span`, `metadata`) — a `model_dump(exclude=...)` or a
response-model `include`, rather than a parallel class.

---

## B-11. Nested sub-question round-trip integrity — ✅ SHIPPED (MVP)

**Status: IMPLEMENTED.** The frontend is now a faithful codec for nested rubrics, framed as
round-trip integrity: `dehydrate(hydrate(x))` is a structural identity for all five golden
fixtures (pinned by a permanent vitest suite, `rubric-transform.test.ts`). What landed:
- **Types recursive** — `RubricSubQuestion.sub_questions?: RubricSubQuestion[]` (self-ref, not
  bounded depth-2), `example_solution?` on sub-questions, `_carry?` on every node; wire
  `SubQuestion` gains the same. (`types/rubric.ts`, `lib/ontology-types.ts`)
- **Codec recursive + opaque-carry** — `hydrate/dehydrateSubQuestion` recurse; a typed `_carry`
  bag (modeled ⊎ carried, disjoint by `MODELED_*_KEYS`) preserves unmodeled/future wire fields;
  `example_solution` is emitted (fixing a live edit-loss bug); `recalculateParentsFromCriteria`
  cascades bottom-up at any depth. (`rubric-transform.ts`)
- **Validator recursive** — INV-R1b mirrors `_walk_sub_question` exactly (parent: Σ children ==
  node.points; leaf: Σ criteria == node.points; full-path `target_id` `q1.א.2`), INV-R2 reach
  recurses, and a new `INV-R-XOR` mirrors StructureExclusivity. (`rubric-validation.ts`)
- **Editor recursive** — `SubQuestionNode` renders/edits at any depth (points/text/title/criteria),
  path-addressed ops, full-path `data-scope-id` anchoring; SSR render test on real depth-2 bagrut.
  (`RubricEditor.tsx`, `rubric-editor-ops.ts`, `rubric-display.ts`)

**Deliberately deferred (surfaced, not silently dropped):**
- **B-11b — document-envelope preservation.** my-rubrics / rubric-generator still drop
  `selection_groups` and re-sum `total_points` as Σ offered on save (corrupts a saved SELECTION
  rubric's achievable total on re-edit); `programming_language` is dropped on every save path.
  Witnessed by a red/todo test in `rubric-transform.test.ts`. This is payload assembly, a
  different concern from the codec.
- **Nested-node CRUD.** Add/remove of a *nested* sub-question node and leaf↔parent conversion.
  The extraction produces the nesting; MVP edits within it. Top-level add/remove still work.

Plan of record: `~/.claude/plans/sunny-sleeping-avalanche.md`. Original problem statement retained
below for the archaeological record.

---

### (original finding) The rubric editor was DEPTH-1 ONLY — it could not represent a nested bagrut

**Found by:** browser E2E on `bagrut_899371` (deploy day + 1), while fixing the `toFixed`
crash. **Owner:** its own PR — this is a type + hydration + validation + render change, not a
bug fix. **Blocked:** the bagrut archetype end-to-end in the browser.

The backend models rubrics to depth 2 (`q1.א.2`) and PR-3 made the compiler, gradable
compiler, and INV-2 all recurse. **The frontend never followed.** `RubricSubQuestion`
(`types/rubric.ts`) has `criteria` but **no `sub_questions` field**, so a sub-question cannot
carry nested sub-questions. Consequently:

- **`hydrateSubQuestion` (`rubric-transform.ts`) does not recurse** — it maps `sq.criteria`
  and silently drops `sq.sub_questions`. Real bagrut `q1.א` (15 pts, two nested leaves) and
  `q1.ב` (10 pts, two nested leaves) arrive with `criteria: []` and their point-bearing
  children **gone**.
- **`validateQuestion` (`rubric-validation.ts`) is depth-1** — it checks
  `question.sub_questions[].criteria` (INV-R1b) but never a sub-question's sub-questions, so
  it is blind to the exact node the backend rejects (`q1.א.2`: criteria sum 2 vs declared 3).
- **The editor render** has no affordance for a third level.

Net effect after the crash fix: bagrut no longer white-screens and shows no false error, but
q1 renders as two sub-questions with points and **no grading detail**, and a save attempt is
rejected by the backend (`q1.א` has points but no children/criteria → INV-2). Safe, but not
usable. The depth-1 **selection** archetype (`employee_course_select1`) IS fully fixed by the
same-day changes; bagrut needs this.

**Shape of the fix (plan before code — §0.1, it touches types):** add `sub_questions?:
RubricSubQuestion[]` to the type; make `hydrateSubQuestion`/`dehydrateSubQuestion` recurse;
make `validateQuestion` recurse mirroring `pipeline._walk_sq` / the compiler's
`_walk_sub_question` (INV-2 is the spec — do not invent a parallel rule); and give
`RubricEditor` a recursive sub-question renderer. Consider whether depth is bounded at 2 or
arbitrary — the backend recursion is arbitrary-depth; match it rather than hard-code 2.

---

## B-1. `RubricEditor` "enhance criteria" calls a RELATIVE URL — the feature may be silently dead

**Found by:** PR-2 context sweep (D11), while inventorying fetch call sites.
**Owner:** unassigned. **Not PR-2** (it is a pre-existing bug, not a resilience change).

`src/components/RubricEditor.tsx:377` is the only `fetch` in the codebase that does not
build its URL from `API_BASE`:

```ts
const response = await fetch(`/api/v0/rubrics/${rubricId}/enhance-criteria`, { ... });
```

A relative path resolves against the **Next.js origin** (`localhost:3000` / the Vercel
domain), **not the backend** (`localhost:8080` / Cloud Run). Every other call in the app
goes to `${API_BASE}/...`.

**Repro / open question (one command):** with the app running, click the enhance-criteria
action and watch the network tab — does `/api/v0/rubrics/{id}/enhance-criteria` 404
against the Next origin, or is there a rewrite/proxy that rescues it? Also grep the
backend for the route: if no `enhance-criteria` endpoint exists at all, the feature is
dead on both ends and the question becomes "remove it or build it," not "fix the URL."

**Why it was not fixed in PR-2:** PR-2's seam migration covers `api.ts`. Touching this
call means either (a) changing a component's behavior from "silently fails" to "actually
calls the backend" — a functional change with unknown blast radius, or (b) deleting a
feature. Both need a decision, not a drive-by.

---

## B-2. Integration tests write to the PRODUCTION database

**Found by:** PR-1 deploy verification (19 job rows in prod, of which ~9 are test
artifacts: 5 orphan `queued` + 4 `completed` `test.docx` rows from interrupted runs).
**Owner:** needs a Noam ruling on test-DB strategy. **Not PR-2.**

`tests/api/*` run against whatever `DATABASE_URL` is in `.env` — which is the live
Supabase instance. The tests clean up in `finally`, but an interrupted run leaks rows.
This is also what made the `create_all` footgun reachable from a laptop (see the PR-1
deploy checklist + migration 013).

**Needs:** a decision (ephemeral test DB / schema-per-run / testcontainers) + a one-time
cleanup of the leaked rows.

---

## B-4. Transcription tests mock a symbol nobody calls — the transcribe→grade path has NO working e2e test

**Found by:** PR-2 final gates (14 failures + 31 errors in `tests/api`).
**Owner:** unassigned. **Not PR-2** (PR-2 touched none of these surfaces; the control
`tests/api/test_extraction_jobs.py` is 18/18).

**Previously mislabelled** in RUNLOG (2026-07-10) as "PDF page-count **env**". It is not an
environment problem. Poppler is installed and genuine locally (`pdfinfo 24.04.0, The Poppler
Developers`), and prod's Dockerfile installs `poppler-utils`. Calling it "env" is what let it
sit unexamined for three days.

**Actual root cause — patch-where-it's-used drift.** The tests patch:

```python
patch("app.api.v0.transcription.pdf_to_images")        # tests/api/test_transcription_endpoints.py:70
```

but the real caller was refactored into the service layer, which holds its own binding:

```python
# app/services/transcribe_one.py:24
from ..services.document_parser import pdf_to_images
# app/services/transcribe_one.py:107
page_count = len(await run_in_threadpool(pdf_to_images, pdf_bytes, 72))
```

Patching the name in the *router* module does not rebind it in the *service* module. So the
mock misses, the REAL parser runs, and it is handed `FAKE_PDF = b"%PDF-1.0 fake content"`
(21 bytes of junk, line 26). Poppler correctly refuses — `Unable to get page count` →
`transcribe_one` raises → the endpoint returns 502 `{"detail":"שגיאה בתמלול — נסה שנית"}`.

**Blast radius:** the happy-path transcribe is the fixture the rest depend on, so it cascades:
`test_11_transcribe_happy_path`, `test_16_grade_happy_path`, `test_17_draft_immutable_after_grade`,
`test_14_grade_already_approved_returns_409`, plus the cross-tenant ownership checks (which
fail in *setup*, hence "errors").

**Why this matters more than a red test:** the transcribe→grade path currently has **no working
end-to-end coverage at all**. A stale mock does not just fail — it hides.

**Fix (pick one):**
1. Repoint the patch: `patch("app.services.transcribe_one.pdf_to_images")`.
2. **Preferred:** replace `FAKE_PDF` with a real minimal one-page PDF so the parser succeeds
   honestly. This stops the test depending on a mock target that the next refactor can silently
   invalidate again.

---

## B-5. Live best-k preview in the review panel (→ PR-4)

**Found by:** PR-3 (the spec asked for this grep explicitly — it exists).
**Status: PARTIALLY CLOSED IN PR-3.** The *lie* is gone; the *feature* is still owed.

**What PR-3 already did (the minimal, non-improvised half).** The review panel is the
FOURTH consumer of the score, and it was computing its own. `runningTotal` sums EVERY
scope, while the (now selection-aware) server counts only the best-k and divides by the
achievable total — the wrong numerator over the right denominator. So on a selection exam
PR-3 **suppresses the client-side aggregate entirely** and shows the server's last
computed figure, explicitly labelled `סה״כ סופי מחושב בשמירה (מבחן בחירה)`. Per-scope
points stay live. The invariant is written into the component and pinned by
`hasSelectionExclusions` + vitest:

> **Never display an aggregate that could disagree with what approval would freeze. When
> that number is not computable client-side, show NO live aggregate rather than a wrong
> one.**

Note the trap that shaped this: simply "showing the server value" is *also* wrong, because
during override editing that value is stale — a stale number rendered as current is just a
different disagreement. Hence the explicit of-last-computation label rather than a bare
number.

**What is still owed (PR-4).** A genuine LIVE preview on selection exams. It is not a
one-liner: exclusion is DERIVED and can flip mid-edit (bump the 15-pointer above the
50-pointer and best-k membership changes), so a correct preview must re-run the best-k
logic — either ported client-side, or exposed as a server-side preview endpoint. Choose
deliberately; do not reintroduce a client-side sum.

`GradedTestReviewPanel.tsx:358-371` derives a live total client-side while editing:

```ts
const runningTotal = useMemo(() => sortedScopes.reduce((total, scope) => /* Σ ALL scopes */ ), ...);
const totalPossible = parseFloat(response.total_possible ?? '0');   // ← from the SERVER
```

The numerator sums **every** scope; the denominator now comes from the (selection-aware)
server. On a "choose k of N" exam the teacher would therefore see a live percentage that
over-counts the excluded members against an achievable denominator — a third number
disagreeing with both fixed server sites.

**Non-trivial to fix, hence PR-4:** because exclusion is DERIVED and can flip when the
teacher overrides a score (bump the 15-pointer above the 50-pointer and best-k
membership changes), a *correct* live preview must re-run the best-k logic client-side.
The cheap alternative is to stop showing a live running total on selection exams and
render the server's value with "יעודכן בשמירה". Decide in PR-4; do not bodge it here.

---

## B-6. Frontend auto-acknowledges every non-invariant warning — ✅ SHIPPED (PR-4)

**Found by:** PR-3 §A1 (it is why nobody ever saw INV-6's 24-32 warnings per rubric).
**Closed by:** PR-4 Phase 5 (R-D).

The blanket `page.tsx` filter `w.annotation_type !== 'invariant_violation'` is **gone**.
A save that returns warnings now renders `RubricWarningsModal` and resends acked ids ONLY
after an explicit teacher confirm — the held draft is re-sent on confirm, nothing is
acked silently. Verified by the render tests + grep (the filter no longer exists). The
bug class (any future warning type silently swallowed) is closed: the teacher is shown
every warning and confirms it herself (Vivi proposes, the teacher decides).

---

## B-7. Transcription depth-2 segmentation (→ transcription eval suite)

**Found by:** PR-3 R3. **Owner:** the transcription pipeline, under its own eval-suite
discipline. Cannot ride along in a grading PR.

The rubric now grades at depth 2 (`q1.א.2`) but the transcription segments answers only
to depth 1 (`q1.א`). PR-3 bridges this with a **parent-answer fallback**: a leaf with no
exact-id answer inherits its nearest ancestor's text. This is **load-bearing for every
nested rubric, not a graceful degradation** — without it, both leaves would grade against
an empty answer.

**The metric for urgency already exists:** every firing is recorded in
`GradableTest.parent_answer_fallback_scopes` and logged as `gradable_parent_answer_fallback`.
When that rate is high on real nested rubrics, depth-2 segmentation becomes urgent.

---

## B-8. `needs_recompilation` is a wired no-op

Column exists, `Rubric.is_compiled` reads it, list endpoints filter on it — but **nothing
ever sets it to True** and nothing auto-recompiles. Note that graded-test staleness has a
*different*, working mechanism (`rubric_contract_version` pinning), so this is dead weight
rather than a missing safety net. Either wire it (a rubric edit should mark dependents
stale) or delete it; do not leave a third half-truth in the schema.

---

## B-9. Two score sites round percentages differently (pre-existing, cosmetic)

`grading_runner` quantizes with the default ROUND_HALF_EVEN; `compile_graded_test` uses
ROUND_HALF_UP. For a value like 66.665 the draft shows 66.66 and the frozen contract says
66.67. PR-3 deliberately did **not** unify these, because doing so would have broken the
byte-identical-regression guarantee it was asserting at the same time. Worth one line to
fix; pick a rounding mode and use it in both.

---

## B-3. GraderAgent transport: 6 unbounded calls per scope

**Found by:** PR-2 context sweep (A1/A2). **Owner: PR-7** (the grader's Cloud Tasks
migration), where its per-task budget math belongs.

`GraderAgent` builds `ChatOpenAI(...)` with no `timeout` and no `max_retries`, so the SDK's
hidden 2 retries apply *inside* each call and LangChain's explicit `timeout=None` removes
any bound. Its own GA-3 retry then wraps that: **2 × 3 = 6 unbounded API calls per scope.**
Its `openai.APITimeoutError` branch is consequently **dead** (nothing can time out), and
`insufficient_quota` (permanent billing) is retried as if transient.

PR-2 fixed this defect family in `docx_v3/pipeline.py` only, and documented the real worst
case in CLAUDE.md. `_transport_retry_async/_sync` are written to be reusable here — PR-7
should adopt them, **not** add a second layer.

---

## B-12. Migrate the graded-test surface to codegen'd types (→ next grading-UI change)

**Found by:** PR-4 (R-B, deliberately scoped out). **Owner:** whoever next touches the
graded-test review UI.

PR-4 generated `src/lib/api-types.ts` and wired the drift-check CI, but only the rubric
wire types are consumed opportunistically. `types/graded_test.ts` is still a hand-written
mirror (honest today — its point fields are typed `string`, matching the wire — so there is
no lie to fix, just duplication). When the graded-test UI is next edited, migrate its types
to the generated ones and delete the mirror (§0.4). Related: that surface also has **no
coercion seam** — every consumer `parseFloat`s at the point of use (census A2). A single
hydrate boundary (as the rubric editor has) would be the clean fix, but it is real work, not
a drive-by.

---

## B-13. `_contract_total()` ships the rubric total as BOTH a string and a number

**Found by:** PR-4 census A1. **Owner:** unassigned (document-only until it bites).

The saved-rubric GET emits the same rubric total twice in one response, in two types:
`contract_json.total_points = "50"` (string, via the Decimal field_serializer) and
`stats.total_points = 50.0` (number, because `rubric_management_service._contract_total()`
float-casts it and `RubricStatsSchema.total_points: float`). Not a crash today — a real
float `toFixed`es fine — but it is a same-value type heterogeneity that invites the next
"is this a string or a number?" bug. Changing the wire is churn without a crash, so this is
documented, not fixed. If touched: make `stats.total_points` a string too (Decimal
serializer) and drop the `float()` cast, so the value has ONE wire type.

---

## B-11b. The re-edit save payload drops `selection_groups` / `programming_language` / re-sums the total

**Found by:** PR-4 (witnessed by the `it.todo` in `rubric-transform.test.ts`). **Owner:** its own PR.

The PR-4 codec (Layer A) makes the questions-array round-trip a structural identity. But the
**document-envelope** assembly in the re-edit pages (`my-rubrics`, `rubric-generator`) still
drops `selection_groups`, re-sums `total_points` as the offered Σ (corrupting a saved
selection rubric's achievable total on re-edit), and drops `programming_language`. That is
payload assembly, not the codec — a separate ticket. The main wizard (`page.tsx`) already
round-trips the envelope correctly (PR-3); this is the *re-edit* surfaces only.

---

## B-14. `excluded_by_selection` has no teacher-facing annotation (backend)

**Found by:** PR-4 Phase 5.3. **Owner:** a grading-side PR.

PR-4 added the scope-header badge, but the backend signals a best-k exclusion PURELY via
`ScopeOutcome.graded_by="excluded_by_selection"` — it emits **no** `annotation`. The PR-3
spec (R2/B-9) called for an INFO annotation ("לא נבחר למענה (שאלת בחירה)"); it was never
implemented. Low urgency (the badge covers the display need), but if richer per-scope
messaging is wanted, emit the INFO annotation in `grading_runner` and add its
`annotation_type` to the frontend `GradingAnnotation` union.

---

## B-15. `RubricEditor.updateCriterion` mutates a shared question object in place

**Found by:** PR-5 Sprint 2 (verified while pressure-testing the undo stack). **Owner:** whoever
next touches `RubricEditor` (it dies with the old editor once the docx flow retires it).

`RubricEditor.updateCriterion` ([RubricEditor.tsx](vivi-codebase/frontend/src/components/RubricEditor.tsx)) does
`const newQuestions = [...questions]` (a SHALLOW copy) then `newQuestions[qIndex].criteria[cIndex] = {...}`
— which mutates the `criteria` array of the **shared** question object (`newQuestions[qIndex] === questions[qIndex]`).
`addCriterion` has the same shape. It is benign **today only because nothing holds a reference to the prior
`questions`** — but it becomes real corruption the moment anything does: an undo/history stack, `React.memo`,
or any concurrent feature. This is exactly why PR-5's mirror (`RubricDocument`) routes **all** edits through the
pure `*AtPath` ops (immutable, structural-sharing) and made "ops imported, never forked" a **correctness
invariant**, not a style rule — its page-level undo pushes snapshots by reference. Fix: rewrite `updateCriterion`/
`addCriterion` immutably (or delete them when `RubricEditor` retires). Do NOT wire an undo/memo onto the old
editor without fixing this first.

---

## B-16. Document-mirror deferrals (PR-5 Sprint 2, conscious scope fences)

**Found by:** PR-5 Sprint 2. **Owner:** follow-up mirror sprints (S3+).

The mirror (`RubricDocument`) shipped the criteria-points-centric core. Deliberately deferred, each a
clean extension point, not a gap:
1. **Prose editing is read-only.** Question/sub-question text renders via `RichBody` (with table detection)
   but isn't editable this sprint (the Dream DoD is criteria-points-centric; editing rich text with embedded
   tables needs a display-vs-raw-edit split). The "הוסיפי טקסט" affordance (⋯ menu) and sub-question **title**
   editing are also deferred.
2. **Solutions are read-only (D-2).** `ExampleSolutionEditor` can mount into `SolutionBlock` later.
3. **Node add/remove** (question / sub-question) and leaf↔parent conversion are deferred — the ops exist
   (`addSubQuestion`/`removeSubQuestion` depth-1; nested-node CRUD absent) but the document metaphor makes
   them heavy. Criterion add/remove IS shipped.
4. **Trace/context tables were NOT shared-lifted.** The spec said "lift TraceTablesDisplay/QuestionContextTablesDisplay
   from RubricEditor"; instead the mirror got **fresh document-aesthetic** renderers (`document/DataTables.tsx`)
   and RubricEditor kept its inline card-styled copies (byte-stable for the rollback). Only `AnnotationBanner`
   was truly lifted+shared. If unifying is wanted, extract a shared component with a `variant` prop.
5. **Undo is undo-only** (no redo at MVP — ruled).

None of these block the Dream DoD; all are extension points.
