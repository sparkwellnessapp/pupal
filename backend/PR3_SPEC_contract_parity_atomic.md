# PR-3 SPEC — Contract parity for the extended ontology, compiler + consumers, ATOMIC

**Kind:** backend. Touches `ontology_types.py` (compiler checks), `gradable_compiler.py`,
`grading_runner.py`, the compile-error payload. No pipeline.py contact, no migration.
**The one rule that dominates everything (context report §"sequencing warning"):**
the compiler fixes and the grading-consumer fixes land in ONE merge or not at all.
Today's broken compiler is *accidentally safe* — INV-2/INV-4 rejections make the
grader's nesting-blindness and the halved-denominator bug unreachable (prod: 40/40
contracts flat + selection-free). A compiler-only fix would un-gate both. Commits
may be separate for review; the merge is atomic; no intermediate state deploys.
**Grading side has NO eval suite** — the tests in Part D are the only guard on the
consumer half. Treat them as load-bearing, not ceremony.

---

## 0. Purpose, restated from the evidence

The extraction pipeline earned 5/5 producing selection groups, depth-2 nesting,
sub_criteria, and faithful teacher errors. The compiler and grader predate all of
it. Concretely, today:
- Two of five rubric archetypes (selection, nested) CANNOT compile — hard MVP
  dead-ends after a successful extraction (A1).
- The compiler's INV-2 flat loop **masks the faithful teacher error at q1.א.2** —
  the exact rubric-gate moment the product exists for fires at the wrong nodes
  (parents, sum=0) instead of the right one (A1/B3).
- If compiled anyway, a nested rubric grades with its inner scopes silently
  dropped (C6a) and a selection exam halves the student's grade by dividing by
  the offered total (C6b: perfect employee answer = 50%).
- INV-6 fires on 100% of criteria and is auto-acked 100% of the time — a check
  nobody can pass, training the click-through reflex (A1).

Post-PR-3 target: four golden drafts compile CLEAN in one round trip; 899371 is
rejected with exactly one error, anchored at `q1.א.2`, in Hebrew a teacher can
act on; a resolved 899371 compiles; nested and selection contracts GRADE
correctly. The compile-rejection on 899371 is a feature meeting its acceptance
criterion, not a failure.

---

## 1. Rulings (recommendations pre-approved pattern — Noam vetoes here, before code)

**R1 — INV-6 (`is_aligned`): demote to non-blocking INFO.** It cannot be
"given real data" cheaply (extraction produces no skill_targets — that's a
future feature, not a fix), and a 100%-fire/100%-ack check is worse than none:
it trains auto-acknowledgment that will swallow future REAL warnings. Demotion
also collapses the frontend's two-round-trip auto-ack dance to a single compile
call for clean rubrics. Keep the check as INFO for the future skill-mapping
feature; document in §5. (Alternative — delete outright — rejected: the concept
is sound, only the severity is wrong.)
**Related flag, not PR-3 scope:** the frontend auto-ack (`page.tsx` acks every
non-invariant warning) is a bug class — any future warning type gets silently
acknowledged. Goes to PR-4's list; noted in BACKLOG now.

**R2 — Selection scoring semantics (the C7 wiring).** Per group: the student's
best-`k` answered member scores count toward the numerator (student-favorable
default; the alternative "first k answered" is unknowable without reading
order); members beyond `k` are EXCLUDED — reported as "not attempted
(selection)" INFO, never "0 points given"; if fewer than `k` were answered, the
empty slots contribute 0 (that is the exam's own rule). Denominator =
`compute_achievable_points` (mandatory Σ + per-group top-k member totals).
Employee check: perfect 50-pointer, others skipped → 50/50 = 100%.

**R3 — Depth-2 answer alignment: parent-answer fallback.** Leaf scopes
(`q1.א.1`) may face answer docs segmented only to depth 1 (`q1.א`) — the
transcription P2 spec's depth support is its own pipeline with its own eval
suite and CANNOT ride along here. Rule: a leaf scope with no exact-id answer
falls back to its parent's answer text (the student's whole-סעיף answer
contains both parts; the grader receives more context than needed and grades
the leaf's criteria against it — correct, slightly wasteful). Emit an INFO
annotation when fallback fires (observability for the follow-up). Transcription
depth-2 segmentation = named follow-up under the transcription suite's own
discipline, filed in BACKLOG.

**R4 — `total_points` means ACHIEVABLE, everywhere, by definition.** The Draft
already says so (`_achievable_from_extraction`); the Contract now agrees:
compiler sets `contract.total_points = compute_achievable_points(questions,
selection_groups)` and INV-4 becomes `response.total_points ==
compute_achievable_points(...)` within tolerance — which reduces EXACTLY to
the legacy Σ check when no groups exist. Back-compat proof: all 40 stored
contracts are selection-free ⇒ achievable ≡ offered ⇒ zero behavioral change
on re-parse (D9). The Draft/Contract semantic split the report named is
resolved by unification, and §5 documents the definition.

---

## PART A — ContractCompiler

1. **INV-2 recursive.** Mirror the pipeline preflight's `_walk_sq` semantics
   EXACTLY (the preflight/compiler mirror is an established precedent — the two
   must not drift): a node with `sub_questions` → Σ children `sq.points` vs its
   declared points (its own criteria list must be empty — the XOR); a leaf →
   Σ `criteria.points` vs points. Error `target_id` = the FULL path id
   (`q1.א.2`), which is what unmasks the faithful teacher error.
2. **INV-4 achievable-aware + selection_groups populated.** Per R4. The
   compiler's constructor call passes `selection_groups` through (the field and
   its apologetic docstring already exist — B2; update the docstring, it
   currently documents its own non-population).
3. **INV-6 → INFO** per R1; no acknowledgment required; still emitted.
4. **Pre-check, INV-1, INV-3 unchanged** (INV-3 already recurses via
   `all_criteria`; INV-1 uses `sq.points`, nesting-safe — B3).
5. **Error payload, additive on E11's shape:** each error gains `invariant`
   ("INV-2"), `expected`, `actual` (stringified Decimals), and a REAL
   `message_he` (currently English duplicated — write the Hebrew templates per
   invariant; the 899371 one reads: "סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה
   מהניקוד המוצהר (3)"). Existing keys untouched — the current flat-list
   renderer keeps working; PR-4 gets anchors for free via `location`.

## PART B — Grading consumers (the un-gating made safe)

6. **`gradable_compiler`: scopes at LEAVES.** A sub-question with children
   contributes no scope of its own; each leaf (inner part or flat SQ) becomes a
   `GradableScope` with ITS criteria and ITS points. Scope ids = full path.
   Closed-world note for §5: with this, CW-1's guarantee finally covers the
   scope set the grader actually receives (report's "narrower than it reads").
7. **Answer alignment: exact-id first, parent-id fallback** per R3, with the
   INFO annotation on fallback.
8. **`grading_runner`: selection-aware final math** per R2. Implementation
   shape: group scope-outcomes by owning top-level question; apply per-group
   best-k selection; denominator = the contract's achievable `total_points`
   (single source — do NOT re-sum scopes; that re-derivation is exactly how
   C6b happened). Non-selection rubrics reduce to today's math bit-for-bit —
   assert that in tests.
9. **Unanswered-member outcomes** inside a group beyond the counted k:
   excluded + "לא נבחר למענה (שאלת בחירה)" INFO, replacing the misleading
   "ניתנו 0 נקודות" for that class. Mandatory unanswered questions keep
   today's zero-with-NO_ANSWER behavior — that semantics is correct for them.

## PART C — What deliberately does NOT change

`pedagogical_mistakes`/`annotations` stay Draft-only (confirmed deliberate);
`spec_from_rubric_draft` untouched (reads Draft, duck-typed, loud — C6c);
`needs_recompilation` stays a wired no-op (BACKLOG, with D10's note that
graded-test staleness already has a different, working mechanism); no
Draft-type changes; no frontend changes beyond what E11-additive already
tolerates.

## PART D — Tests (offline; the consumer half's ONLY guard)

1. **Golden-fixture compile matrix (the headline acceptance):**
   csharp/hobby/foundations/employee compile CLEAN — zero errors, zero
   blocking warnings, ONE round trip (no ack dance). 899371 rejects with
   EXACTLY ONE error: `invariant=INV-2, location=q1.א.2, expected=3, actual=2`,
   Hebrew message present. A resolved-899371 variant (criteria adjusted
   1.5+1.5=3 in the test fixture) compiles clean — proving the teacher's
   fix-path through the identical gate (F13: update path is the same compile).
2. **Grading-consumer matrix:** nested contract → leaf scopes only, correct
   criteria/points per leaf, parent has no scope; parent-answer fallback fires
   + annotates; employee synthetic grading → perfect-50 student = 100%,
   perfect-15 student = 30% (15/50); bagrut choose-4 with 3 answered →
   denominator 100, fourth slot zero; answered-beyond-k → best-k counted,
   extras excluded-not-zeroed; **regression: a flat selection-free contract
   produces byte-identical scores and percentage vs current code** (golden
   comparison against pre-change output captured in the test).
3. **Back-compat:** all 40-prod-shaped contracts (flat, `selection_groups: []`)
   re-parse and grade unchanged; new-shape contract round-trips
   `model_validate(model_dump())`.
4. Full battery + `import app.main` + collect clean; eval suite untouched by
   construction (no pipeline contact) — run it anyway.

## PART E — Docs, ledger, backlog

CLAUDE.md §5: INV-2 nesting clause; INV-4 achievable definition + the
`total_points := achievable` semantic (naming the resolved Draft/Contract
split); INV-6 added to the table as INFO with its history (fired 100%, demoted,
future skill-mapping hook); CW-1 guarantee note updated; §8 check-list
corrected. RUNLOG: one CHANGE entry (grading-affecting; invalidates comparison
of future grading outputs to pre-PR-3 ones for nested/selection rubrics —
which is an empty set in prod, say so). BACKLOG: frontend auto-ack bug (→PR-4),
transcription depth-2 segmentation (→transcription suite), needs_recompilation
cleanup.

## Acceptance

- [ ] Compile matrix exactly as Part D.1 — including that 899371's rejection IS the pass condition
- [ ] Grading matrix Part D.2 including the byte-identical flat-contract regression
- [ ] Atomic merge: no deployable intermediate where the compiler accepts what the grader mishandles
- [ ] Error payload additive; Hebrew messages real; `location`/`invariant`/`expected`/`actual` present
- [ ] 40-prod-contract back-compat proven in tests
- [ ] One compile round trip for clean rubrics (ack dance gone)
- [ ] CLAUDE.md §5/§8 corrected; RUNLOG + BACKLOG entries written
