# PR: S10 — Revision flows: re-grade-stale, manual-edit, retry-failed

**Sprint:** S10 (completes the single-test lifecycle)
**Depends on:** S8 (`run_grading`, read endpoints), S9 (approval, contract, review panel) — merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §3.3 (revision actions), §5 (LCY-2 read-only-except-`regraded_to_id`, RGC-1 one-leaf-per-chain, VER-2 pinned version), §9.2 (`rubric_contract_stale` computed); `phase_0e_dfd.md` §4 (revision flows)
**Frontend lockstep:** yes — adds revision affordances to the approved/failed review states

---

## 1. Summary

S10 builds the three revision actions, all of which **extend the revision chain and never mutate history** (LCY-2):

1. **Re-grade-stale** — the rubric was recompiled since this test was graded (`rubric_contract_stale`). Create a successor row pinned to the *new* rubric contract version, run the AI fresh (reuse S8's `run_grading`), review+approve via S9.
2. **Manual-edit** — revise an already-approved grade by hand. Create a successor pre-loaded with the previous row's `draft_json` (AI outcomes + the last-approved overrides), **no agent**, the teacher edits and re-approves via S9.
3. **Retry-failed** — re-attempt a `failed` grade (closes the S8 "try again" promise). Mechanically a re-grade with the *same* rubric version; create a pending successor and run the agent.

All three create a new `graded_tests` row, link it via `regraded_from_id`/`regraded_to_id`, and leave the predecessor immutable except for its forward pointer. After S10 the single-test lifecycle is complete.

**S10 does NOT:** mutate any historical row's content; allow revising a non-leaf row; offer AI re-grade on a non-stale approved row (D2); build batch flows (S11) or a full chain-history viewer (D5).

---

## 2. THE central problem — the chain-insert vs. two constraints (read first)

Every revision action must, in one transaction: **INSERT the successor R2** and **link the predecessor R1 forward** (`R1.regraded_to_id = R2.id`). Two constraints collide on the same-chain case, because re-grade/manual-edit/retry all keep the **same `(transcription_id, rubric_id)`** (the rubric *entity* is unchanged; only its contract *version* differs):

- **`idx_graded_tests_one_leaf_per_chain`** — partial unique index on `(transcription_id, rubric_id) WHERE regraded_to_id IS NULL`. **At most one leaf per chain.** Unique indexes in Postgres are **never deferrable** — checked at every statement/flush.
- **`regraded_to_id` / `regraded_from_id` FKs** — currently **non-deferrable** (migration 008, confirmed: `REFERENCES graded_tests(id) ON DELETE SET NULL`, no `DEFERRABLE`). Checked immediately.

Walk both naive orderings for the same chain:

- **INSERT R2 first** (`regraded_to_id=NULL`) → now R1 *and* R2 both have `regraded_to_id IS NULL` → **two leaves → partial unique index fails at the flush.**
- **Link R1 first** (`R1.regraded_to_id = R2.id`) → R2 doesn't exist yet → **non-deferrable FK fails at the flush.**

**Neither order works with both constraints immediate.** This is a real circular dependency, not a sequencing nicety.

> ⚠️ **The "INSERT R2 → flush → set R1" pattern from `test_s1_models.py` does NOT apply here.** That test passes only because its two rows are *different chains* (different `transcription_id`/`rubric_id`), so they're never two leaves of the *same* partial-index key. For S10's same-chain revision, that exact ordering trips `idx_graded_tests_one_leaf_per_chain` at the flush. This is the identical bug class we already hit and fixed in the consulate system (`uq_semesters_one_active`: a new active row inserted before the old one was demoted — the partial index correctly rejected the transient two-active state). Do not copy the `test_s1_models.py` order here.

### The resolution: make `regraded_to_id` deferrable → migration 010 → link-R1-first

Migration **010** alters the `regraded_to_id` FK to `DEFERRABLE INITIALLY DEFERRED`. Then the correct transaction is **delink/relink R1 first, insert R2 second**, with the FK deferred to commit:

```
# R2.id pre-generated in Python (uuid4) so we can point R1 at it before R2 exists
1. R1.regraded_to_id = r2_id        # R1 leaves the partial index (now 0 leaves — valid);
   await db.flush()                 #   FK to R2 is DEFERRED, not checked yet
2. db.add(R2)  # id=r2_id, regraded_from_id=R1.id, regraded_to_id=NULL
   await db.flush()                 # R2 is the sole leaf (1 leaf — valid);
                                    #   R2.regraded_from_id→R1 FK satisfiable (R1 exists, immediate)
3. await db.commit()                # deferred R1→R2 FK checked now; R2 exists → valid
```

Why this is the only clean order:
- The **partial unique index can't be deferred**, so we must never have two leaves at any checkpoint. Delinking R1 *first* means there are 0 leaves between step 1 and step 2, then exactly 1 (R2). The index is satisfied at every flush.
- The **`regraded_to_id` FK can be deferred**, so R1 pointing at a not-yet-existent R2 is tolerated until commit, by which point R2 exists.
- `regraded_from_id` (R2→R1) stays immediate and is always satisfied (R1 exists when R2 is inserted).

**Migration 010 is required.** The flush-ordering trick alone cannot resolve a same-chain insert; the deferrable FK is the right tool, and it's one `ALTER`.

```sql
-- 010_s10_deferrable_regraded_to_fk.sql
ALTER TABLE public.graded_tests
    DROP CONSTRAINT <name_of_regraded_to_id_fkey>,
    ADD CONSTRAINT <same_name>
        FOREIGN KEY (regraded_to_id) REFERENCES public.graded_tests(id)
        ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED;
```
(Find the actual constraint name first — `\d graded_tests` or the migration 008 source. Only `regraded_to_id` needs to become deferrable; `regraded_from_id` stays immediate.)

> If the agent believes there's a migration-free resolution, it must demonstrate it against **both** constraints for the **same-chain** case (same `transcription_id` + `rubric_id`) — not the different-chain case `test_s1_models.py` covers. I don't believe one exists without an ugly sentinel/self-reference hack; the deferrable FK is correct and minimal. **Flag, don't improvise**, if migration 010 seems avoidable.

---

## 3. Scope

### In scope
- Migration 010: `regraded_to_id` FK → deferrable (§2).
- A shared chain-extension helper (the §2 transaction), used by all three actions.
- `POST /graded_test/{id}/regrade` — re-grade-stale (§5).
- `POST /graded_test/{id}/manual_edit` — manual-edit (§6).
- `POST /graded_test/{id}/retry` — retry-failed (§7).
- `rubric_contract_stale` added to read responses (§4).
- Frontend: regrade / manual-edit affordances on approved rows, retry on failed rows, minimal revision note (§8).
- Tests (§9).

### Out of scope
- Mutating historical rows (forbidden by LCY-2).
- Revising a non-leaf row (D4 — 409).
- AI re-grade on a non-stale approved row (D2 — manual-edit only).
- Batch revision (S11), full chain-history viewer (D5 — minimal note only).
- Converting a contract back into a draft shape — manual-edit carries `draft_json` forward verbatim (D3), no conversion.

---

## 4. `rubric_contract_stale` in read responses

Not present anywhere today (research). Add it as a **computed** field (never stored — Phase 0a §9.2): `stale = (graded_tests.rubric_contract_version != rubrics.contract_version)`.

- Add `rubric_contract_stale: bool` to `GradedTestListItem`, `GradedTestDraftResponse`, `GradedTestApprovedResponse`.
- Compute via a join in the read queries: `(GradedTest.rubric_contract_version != Rubric.contract_version).label("rubric_contract_stale")`, joining `Rubric` on `rubric_id`. (Handle the rubric being deleted → treat as not-stale or surface separately; a deleted rubric can't be re-graded against anyway.)
- This flag drives the re-grade affordance (§8): re-grade is offered **only** when `status == 'approved' AND rubric_contract_stale`.

---

## 5. `POST /graded_test/{id}/regrade` — re-grade-stale

**Preconditions** (all → 409 with clear message if violated):
- Source is owned (`get_owned_or_404`).
- Source `status == 'approved'`.
- Source is the **leaf** (`regraded_to_id IS NULL`) — D4.
- Source is **stale** (`rubric_contract_version != rubric.contract_version`) — D2. A non-stale approved row cannot AI-re-grade; 409 directing the teacher to manual-edit.

**Action** (the §2 chain-extension transaction):
- Create successor R2: `status='pending'`, `draft_json=NULL`, `contract_json=NULL`, **`rubric_contract_version = rubric.contract_version`** (the *new* current version — this is the whole point of re-grade), same `transcription_id`/`student_id`/`student_name`/`filename`/`user_id`, `regraded_from_id = R1.id`.
- Link R1 forward via the deferred-FK ordering (§2), commit.
- **Fire `run_grading(R2.id)`** via `BackgroundTasks` (reuse S8 verbatim — research confirms the runner loads `rubric.contract_json`, which is already the new version; "just works", no special case). R2 advances `pending → grading → draft`.
- Return the successor's id + status (the frontend polls `GET /graded_test/{R2.id}` exactly as in S8).

The teacher then reviews and approves R2 through the **existing S9 flow** — no new approval logic.

---

## 6. `POST /graded_test/{id}/manual_edit` — manual-edit

**Preconditions** (→ 409 if violated):
- Owned; source `status == 'approved'`; source is the **leaf** (D4).
- **No staleness requirement** — manual-edit is always available on an approved leaf (it's how you revise a grade whose rubric *hasn't* changed, and the only revision path for non-stale rows).

**Action** (the §2 chain-extension transaction), **no agent**:
- Create successor R2: **`status='draft'`** (not pending — there's nothing to grade), `draft_json = R1.draft_json` **carried forward verbatim** (D3 — AI outcomes + the last-approved `teacher_overrides`), `contract_json=NULL`, **`rubric_contract_version = R1.rubric_contract_version`** (unchanged — same rubric version; manual-edit does NOT re-pin to current, because the teacher is editing the existing grade, not regrading against a new rubric), same identity fields, `regraded_from_id = R1.id`.
- Link R1 forward (§2), commit.
- **No `run_grading`.** R2 is immediately a `draft` the teacher opens in the S9 review panel, pre-populated with the prior AI outcomes and their previous edits, ready to adjust and re-approve.
- Return R2's id + status (`draft`).

**Why carry `draft_json` verbatim and not re-pin the rubric version:** the prior row's `draft_json` already holds the AI outcomes the grade was built on plus the teacher's last overrides — it's the exact starting point for "tweak my previous decision." Re-pinning to the current rubric version would be a lie (the draft's outcomes were produced against the *old* version), and would make the row look non-stale when its content reflects the old rubric. Keep the pinned version matching the content. (If the rubric is *also* stale, the teacher's two distinct intents are: "redo with new rubric" → regrade, or "tweak under the old rubric" → manual-edit. Keep them separate.)

**CHECK-constraint note:** R2 enters as `status='draft'` with `draft_json IS NOT NULL AND contract_json IS NULL` — satisfies `graded_tests_status_consistency`. Good.

---

## 7. `POST /graded_test/{id}/retry` — retry-failed (D1)

**Preconditions** (→ 409 if violated):
- Owned; source `status == 'failed'`; source is the **leaf** (D4).

**Action** (the §2 chain-extension transaction):
- Create successor R2: `status='pending'`, nulls for draft/contract, **`rubric_contract_version = rubric.contract_version`** (current — a retry should use the current rubric; if the rubric changed since the failure, the retry naturally picks it up), identity fields copied, `regraded_from_id = R1.id`.
- Link R1 forward (§2), commit.
- Fire `run_grading(R2.id)` (reuse S8). Poll as usual.
- Return R2's id + status.

Retry is re-grade's mechanical twin (pending successor + `run_grading`); the only differences are the precondition (`failed` not `approved+stale`) and that it's always allowed regardless of staleness. **Implement all three actions on the shared chain-extension helper** so the transaction logic lives once; the actions differ only in (a) precondition checks, (b) the successor's initial `status`/`draft_json`/`rubric_contract_version`, and (c) whether `run_grading` fires.

---

## 8. Frontend — revision affordances

Research confirms the natural slot: `GradedTestReviewPanel` header already has a `{editable && !isApproved && (Save/Approve)}` block; the symmetrical S10 block is `{isApproved && (Regrade?/EditManually)}`. The approved banner already *names* "manual edit" ("עריכה ידנית") but has no button — S10 wires it.

### 8.1 Approved-row affordances
- **"עריכה ידנית" (manual-edit)** — always shown on an approved leaf. Calls `POST .../manual_edit` → gets the new `draft` row → opens it in the (editable) review panel via the S9 flow. (A successor draft is just a normal editable draft.)
- **"בדיקה מחדש" (re-grade)** — shown **only** when `rubric_contract_stale` (the badge condition). Calls `POST .../regrade` → polls the new pending row → draft-review when done (the S8 polling flow). Pair it with a visible **"graded against an outdated rubric"** badge (driven by `rubric_contract_stale`) so the teacher understands *why* re-grade is offered.
- Both should confirm before acting (a successor row is created; cheap, but the teacher should know they're making a new revision).

### 8.2 Failed-row affordance
- **"נסה שוב" (retry)** — on a `failed` row (replaces S8's placeholder "try again"). Calls `POST .../retry` → polls the new pending row.

### 8.3 Minimal revision note (D5)
- On a row that has a `regraded_from_id`, show a small "this is a revision of an earlier grade" note. A link to the predecessor is nice-to-have; a full chain timeline is **out of scope**.
- No history viewer, no diff between revisions — minimal only.

### 8.4 API client + types
- `regradeGradedTest(id)`, `manualEditGradedTest(id)`, `retryGradedTest(id)` → each returns the successor's `{ id, status }`.
- Add `rubric_contract_stale: boolean` to the response types.
- After manual-edit, route into the editable draft review (S9); after regrade/retry, into the polling flow (S8).

---

## 9. Testing

### Chain-extension (the core — DB-level)
`tests/api/test_revision_flows.py` (or services-level for the helper):
1. **Re-grade extends the chain correctly** — after regrade: R1.`regraded_to_id == R2.id`, R2.`regraded_from_id == R1.id`, R2 is the leaf (`regraded_to_id IS NULL`), R1 is no longer the leaf. **Exactly one leaf** for the `(transcription_id, rubric_id)` pair (the partial index holds).
2. **No two-leaf violation** — the transaction commits without tripping `idx_graded_tests_one_leaf_per_chain` (this is the test that proves the §2 ordering + deferred FK works; if migration 010 or the ordering is wrong, this fails with a unique-violation).
3. **History immutable** — after a revision, R1's `draft_json`/`contract_json`/`approved_at`/`status` are byte-unchanged; only `regraded_to_id` was set (LCY-2).
4. **R2 rubric version** — re-grade: R2.`rubric_contract_version == rubric.contract_version` (new). Manual-edit: R2.`rubric_contract_version == R1.rubric_contract_version` (unchanged). Retry: R2 == current.

### Per-action
5. **Re-grade preconditions** — 409 on: not-approved source, non-leaf source, **non-stale** source.
6. **Re-grade runs the agent** — R2 ends in `draft` (mock `run_grading`/agent); `run_grading` was invoked with R2.id.
7. **Manual-edit carries draft forward** — R2.`draft_json == R1.draft_json` (including `teacher_overrides`); R2 status `draft`; **no `run_grading` call** (assert the runner was not invoked).
8. **Manual-edit preconditions** — 409 on non-approved / non-leaf; **allowed on a non-stale approved leaf** (the case re-grade rejects).
9. **Retry preconditions** — 409 on non-`failed` / non-leaf; runs the agent on success.
10. **Leaf-only enforced across all three** — attempting any action on a row that already has `regraded_to_id` set → 409 (can't revise history).
11. **Ownership** — all three: 404 for another user's row.
12. **`rubric_contract_stale` in responses** — an approved row whose rubric was recompiled reports `rubric_contract_stale == true`; an unchanged one `false`.

### Frontend
- Approved leaf shows manual-edit always, re-grade only when stale (+ stale badge).
- Failed row shows retry.
- Manual-edit opens an editable draft pre-filled with prior outcomes+overrides; regrade/retry enter the polling flow.

Tests 2 (no two-leaf violation), 3 (history immutable), and 7 (manual-edit no-agent carry-forward) protect the core invariants.

---

## 10. Acceptance criteria

- [ ] Migration 010 makes `regraded_to_id` `DEFERRABLE INITIALLY DEFERRED`; `regraded_from_id` unchanged.
- [ ] Shared chain-extension helper implements the link-R1-first → insert-R2 → commit ordering (§2); used by all three actions.
- [ ] The transaction never presents two leaves to the partial index (test 2) and never mutates a historical row beyond `regraded_to_id` (test 3, LCY-2).
- [ ] `POST .../regrade`: approved + leaf + **stale** only; successor pinned to **new** rubric version; fires `run_grading`.
- [ ] `POST .../manual_edit`: approved + leaf (any staleness); successor `status='draft'`, `draft_json` carried **verbatim**, rubric version **unchanged**, **no agent**.
- [ ] `POST .../retry`: failed + leaf; successor pinned to current rubric version; fires `run_grading`.
- [ ] All three: leaf-only (409 on non-leaf), ownership (404 cross-user).
- [ ] `rubric_contract_stale` computed (never stored) and added to the three read responses.
- [ ] Frontend: manual-edit (always) + re-grade (stale only, with badge) on approved; retry on failed; minimal revision note; correct routing (manual-edit→editable draft, regrade/retry→polling).
- [ ] All tests pass; tests 2/3/7 explicitly verified; `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 11. Known follow-ups (do NOT do in this PR)

- **S11** — batch grading (the revision actions remain per-test).
- **Full chain-history viewer** — a timeline of all revisions of a test with diffs. S10 ships only the minimal "this is a revision" note.
- **Eval suite (E2)** — the revision chain is rich eval signal: a re-grade after a rubric fix, or a manual-edit, is a teacher correcting the system; E2 can mine "what got revised and why."
- **Stuck-`grading` recovery** — still unaddressed (S8 §4.6); a re-grade is one manual escape hatch for a stranded row, but no automatic sweeper exists.

If migration 010's `ALTER` can't find/drop the existing FK cleanly (constraint-name mismatch), **flag it** — get the real name from the live schema first. And if, contrary to §2, the agent finds the same-chain insert works *without* the deferrable FK, it must prove it against both constraints for the same `(transcription_id, rubric_id)` before removing the migration — I expect it cannot.
