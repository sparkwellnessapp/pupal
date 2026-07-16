# PR-4 PLAN — Frontend↔backend parity (census-driven), 7 phases, one tree

**Basis:** the pre-PR-4 parity census (frontend-backend_parity_census_pre-pr4.md).
Every phase below cites its census finding. The census's class-naming is adopted:
we fix CLASSES instance-complete, never lone instances.
**Prime rule:** Phase 0 gates everything. Until the duplicated tree is resolved,
every commit is a coin-flip about which copy deploys.

---

## Rulings (recommendation-pre-approved pattern — veto before code)

**R-A — Kill the twin tree.** First verify which directory Vercel actually
builds (`vercel.json` / project settings / deploy logs). Recommendation: the
CLAUDE.md §10 canonical `frontend/` stays; `grader-frontend/` is deleted
(`git rm`), with a CLAUDE.md note naming the episode. If Vercel builds the
twin, repoint it first, then delete. No merged compromise, no "sync script" —
the census calls it correctly: a §0.4 dual-canon violation one layer up.

**R-B — Adopt OpenAPI codegen, incrementally.** Census A3 proved it: the spec
does not reproduce the type lie (Decimal→`string` typed at source), 5,564
clean lines, one backend gap (`response_model` missing on the graded-test
GET). Adoption shape: generated `api-types.ts` committed + npm regen script +
**CI drift check** (regenerate in CI, empty diff required — the frontend's
`suite_hash`). New/touched types consume generated ones; existing hand-written
types migrate opportunistically, marked deprecated. The type-lie class dies at
the source instead of field-by-field patching.

**R-C — Port `compute_achievable_points` client-side; INV-R3 becomes
achievable-aware for real.** The hotfix's abstain was defensible triage, but
it leaves selection rubrics with zero live total-validation while editing —
and the editor header (E10) needs the achievable number anyway. Unlike
grading's best-k-over-awarded-scores (genuinely server-only), rubric
achievable is ~15 lines of pure arithmetic over declared totals. Mirror it
(same name, doc-comment linking the backend function), and guard the mirror
with a parity test: client achievable over each golden fixture ==
GT `total_points`. Two consumers, one function: INV-R3 and the header.

**R-D — Auto-ack dies; explicit warning confirmation replaces it.** C8: the
blanket `!== 'invariant_violation'` filter currently auto-acknowledges
`rubric_mismatch` — the teacher's own flagged error, silently confirmed on her
behalf — and will swallow any future warning class. Replacement: on a
warnings response, render the warnings (Hebrew messages exist) in a
confirmation modal — "ויוי זיהתה אי-התאמות במחוון" + list + "אשר ושמור" —
resend with acked ids only after explicit confirm. This is not UX polish; it
is the product invariant (Vivi proposes, the teacher decides) applied to the
save path.

**R-E — Nested editing scope: edit-in-place only.** Points/text/criteria
editable within existing nested structure; add/remove-nested-part deferred
unless it falls out free of the existing add/remove-SQ machinery (propose in
the phase-3 commit if free; otherwise BACKLOG).

---

## Phase 0 — Canon (R-A). Gate for everything else.
Verify deploy source → keep `frontend/` → delete twin → CLAUDE.md §10 note.
**Acceptance:** one frontend tree in the repo; deploy provably builds it.

## Phase 1 — Codegen foundation (R-B)
1. Backend commit: `response_model` on `GET /grading/graded_test/{id}` —
   minimal `Union[...]` of the status shapes (discriminated union = BACKLOG
   polish; census confirms nothing existing is lost since zero discriminators
   exist today).
2. Generate + commit `api-types.ts`; `npm run gen:api`; CI drift check.
**Acceptance:** CI fails on backend-schema drift; generated `Question.points`
is `string` (the lie dead at source).

## Phase 2 — Round-trip integrity (census B4: the corruption fixes)
1. **`example_solution` carried at Q and SQ level** — hydrate + state +
   dehydrate symmetric. Destroyed today on ALL FIVE archetypes (bagrut: 12
   solutions of real C#; csharp: 7). Render = read-only collapsible block,
   `dir="ltr"` for code inside the RTL page (the display half of the old PR-4
   scope, minimal).
2. Same carry for `evaluation_guidance`, `extraction_confidence`, `notes`
   (null in current fixtures, real fields on the wire — the opaque-carry
   principle applied instance-complete to the criterion node).
3. **The golden round-trip vitest suite, permanent** (census G12 method,
   formalized): `dehydrate(hydrate(x)) ≡ x` over all five benchmark JSONs via
   `fs` + cwd-relative path, modulo declared normalizations (`[]≡null`,
   documented in the test). Bagrut = explicit `xfail` until Phase 3 flips it.
   This is the frontend's golden self-pass; it outlives this PR.
**Acceptance:** four fixtures identity-clean; bagrut xfail documents exactly
the depth-2 loss; a teacher's open-then-save no longer destroys solutions.

## Phase 3 — Depth-2 (B-11 proper; census B4/B6/C7/D9)
1. Types: TWO families, by design (agent finding 3). Codegen serves the WIRE
   layer only (string points); the editor family (RubricQuestion/
   RubricSubQuestion, number points) is hand-edited: recursive
   `sub_questions?: RubricSubQuestion[]`, mirroring the ontology's recursion
   (which settles recursive-over-bounded — the backend's bounded LLM-schema
   rationale is a decoder concern absent here). The transforms' SIGNATURES are
   typed against the generated wire types (hydrate: wire Question → editor
   RubricQuestion) so field/type mismatches are compiler-caught at the seam.
   Stated residual (transform header comment): TS does not enforce
   exhaustiveness — ignoring a wire field is not a type error — so the Phase-2
   golden round-trip suite, not the compiler, is the guard against silent
   drops. That is the division of labor.
2. Hydrate/dehydrate recurse; the round-trip identity extends to nested
   leaves; bagrut xfail → pass (24 points, 6 criteria, 4 leaves preserved).
3. Client validator: INV-R1b → recursive walk mirroring `_walk_sq` semantics
   EXACTLY (branch: Σ children `points` vs declared; leaf: Σ criteria; error
   messages carry full-path ids `q1.א.2`) + the missing StructureExclusivity
   check (XOR — census C7 row 5, no client counterpart today).
4. Recursive render: nested part editor (edit-in-place per R-E), one indent
   level, path ids RTL-safe (census F11 confirms no id-parsing assumptions —
   display via positional labels, ids only concatenated).
**Acceptance:** bagrut renders depth-2; a live edit of q1.א.2's criteria
triggers the recursive validator at the right node; untouched open→save of
bagrut is a structural identity; **the full MVP journey works: extract bagrut
→ see the flagged mismatch → edit 1.5→1.5+1.5 (or adjust declared) → recursive
client validation clears → save → compiler accepts** — the teacher can now fix
in the editor the exact error PR-3 taught the compiler to anchor.

## Phase 4 — Selection parity (R-C; census C7/E10)
1. Client `compute_achievable_points` mirror + golden parity test.
2. INV-R3 achievable-aware (replaces the abstain; the abstain comment's B-5
   discipline is preserved because the mirrored function IS the single
   source client-side).
3. Editor header: total renders achievable (kills the two-disagreeing-totals
   display on selection exams — the census's "client twin of
   calculate_rubric_stats"); stats counts recurse (fixes the depth-1
   undercount).
**Acceptance:** employee editor shows 50 everywhere; no client surface renders
the offered sum as "the total"; parity test pins the mirror to the five GTs.

## Phase 5 — Trust surfaces (R-D; census C8/D9/F11)
1. Auto-ack removed; the warning-confirmation modal per R-D.
2. Compile-error payload: hand-type the COMPILE-ERROR dict emitted by
   `_compile_error_payload` (verified: location/invariant/expected/actual/
   message_he are already on the wire today — this phase is purely frontend
   catch-up), keeping the union with the raw `RubricValidationError` shape,
   which is a different carrier (agent finding 5). HTTPException detail is
   outside OpenAPI — the one deliberate hand-typed exception, comment says
   why. Structured render:
   invariant chip, expected/actual values, and **anchor-scroll**: `location`
   is a full-path id, editor nodes are id-keyed post-Phase-3 → clicking the
   error scrolls/highlights the node. PR-3's payload work finally reaches the
   teacher's eyes.
3. `excluded_by_selection`: scope-header badge ("לא נבחר למענה") + the
   annotation-type union gains the selection member (census F11: today it
   renders bare and untyped).
**Acceptance:** a rubric_mismatch warning is SHOWN and explicitly confirmed,
never auto-acked (grep: the filter is gone); bagrut's rejection screen shows
structured errors with a working jump-to-node.

## Phase 6 — The render-half guard (census G12; ROUTE-MOCKED by design)
Playwright with the extraction/save endpoints route-mocked — not as a
compromise but as the correct harness split: this suite owns the RENDER half
(the census's stated gap) deterministically and free; the live
Cloud-Tasks→OIDC→runner hop stays owned by the manual E2E protocol from
PR-1's deploy verification. Two journeys:
(1) bagrut: mocked job sequence (202 → extracting with advancing stages →
completed → the golden bagrut ExtractRubricResponse) → review renders
depth-2, no white-screen → save → mocked compile 400 (real payload shape
from PR-3's tests) → structured rejection screen with jump-to-node → fix →
mocked success. (2) employee: full journey to saved achievable-50 (mocked
compile 200). Browsers install in the CI substrate; if the local env cannot
fetch Chromium, the spec is CI-only — do not fake a local substitute.
Keep it to two specs; this is a guard, not a suite.

---

## Out of scope (explicit)
Graded-test surface codegen migration + its missing coercion seam (honest
`string` types today — BACKLOG, ride the next grading-UI change);
`_contract_total()` float/string same-value heterogeneity (document + BACKLOG
— changing the wire is churn without a crash); discriminated-union polish;
B-5's full live best-k preview (server-side preview or client best-k — own
item); add/remove nested parts unless free (R-E).

## Cross-cutting acceptance
- [ ] ONE tree; deploy provably builds it
- [ ] Golden round-trip suite green 5/5 — untouched open→save is identity on every archetype
- [ ] CI drift check live for api-types.ts
- [ ] The bagrut end-to-end journey (extract → see → fix → save → compile) works in the browser — this is the MVP's definition of done for the rubric feature
- [ ] No client aggregate can disagree with the server (E10 table: all rows ✅)
- [ ] tsc, vitest (incl. new suites), next build, Playwright — all green
- [ ] CLAUDE.md §10 updated (canon episode, codegen workflow, transform-symmetry rule); BACKLOG updated; census filed as the PR's evidence record