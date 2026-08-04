# PR: S9 — Teacher overrides, approval gate, `GradedTestContract`

**Sprint:** S9
**Depends on:** S7 (draft + annotations), S8 (draft persistence + review screen) — merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §3.2 (graded_test lifecycle: draft→approved), §10.5 (error annotations block approval), the sparse-overlay override design; `phase_0e_dfd.md` §2 (the approval gate)
**Frontend lockstep:** yes — makes the S8 review screen editable and adds the approve flow

---

## 1. Summary

S9 turns the AI's read-only draft (S8) into a teacher-authored, frozen `GradedTestContract`. It adds:
1. **Typed teacher overrides** — a sparse, **terminal-level** overlay (`{terminal_id → {points_awarded, teacher_comment}}`) the teacher edits in the review screen. AI outcomes stay immutable; the override is a separate layer.
2. **Two endpoints** — `PATCH` to save overrides on the draft (ungated, so partial work survives) and `POST .../approve` (the gate + freeze).
3. **The approval gate** — bounds-per-terminal + branch-aggregation consistency + closed-world + no-unresolved-`error`-annotations. (Notably **not** a re-fire of rubric point-sum invariants — §4.2.)
4. **`GradedTestContract`** — net-new, frozen, provenance-preserving (AI-original + override + resolved final), mirroring the rubric `ContractCompiler` pattern. Advances the row `draft → approved`.

After S9, the loop is complete and authoritative: the teacher reviews the AI draft, adjusts where they disagree, and approves — producing a frozen, human-owned grade. The override data (where teachers changed the AI) is the single richest signal the product generates — the eval suite (E2) consumes it directly.

**S9 does NOT:** build re-grade or manual-edit (S10), or let the teacher edit the AI's `reasoning`/`evidence_quote` (D3 — only points + comment).

---

## 2. Decisions (locked)

| # | Decision | Choice |
|---|---|---|
| D1 | Override granularity | **Terminal-level.** Keyed by `criterion_id` (leaf criteria) or `sub_criterion_id` (sub-criteria) — exactly the grading granularity. |
| D2 | Approval gate | **Bounds-per-terminal + branch-aggregation + closed-world + no-error-annotations.** Does **NOT** re-fire point-sum invariants on *awarded* points (awarded points have no sum constraint — re-firing would wrongly reject legitimate partial credit). §4.2. |
| D3 | What's editable | **Points + teacher_comment only.** The AI's `reasoning`/`evidence_quote` are immutable (the audit record of what the AI said). |
| D4 | Contract shape | **Provenance-preserving.** Stores AI-original + override + resolved-final per terminal, not just flattened finals — it's the eval suite's disagreement signal. |
| D5 | Endpoint shape | **Two endpoints.** `PATCH .../draft` saves overrides (ungated, partial-work-safe); `POST .../approve` gates + freezes. |

---

## 3. Scope

### In scope
- Typed override schemas (`TeacherOverride`, `GradedTestOverrides`) — §4.1.
- `PATCH /graded_test/{id}/draft` — save overrides onto `draft_json.teacher_overrides`, ungated (§5).
- `GradedTestContract` schema (net-new, frozen, provenance) + `compile_graded_test(...)` (§4.3, §4.4).
- The approval gate logic (§4.2).
- `POST /graded_test/{id}/approve` — gate → compile → atomic freeze → `approved` (§6).
- `GradedTestApprovedResponse` + the `approved` branch in the detail endpoint (§7).
- Frontend: editable review screen (point inputs + comment fields), error-annotation surfacing, approve flow, approved state (§8).
- Tests (§9).

### Out of scope
- Re-grade-stale + manual-edit (the revision chain) — **S10**.
- Editing the AI's reasoning/quote (D3).
- Whole-scope or whole-test overrides — overrides are terminal-level only (a teacher zeroing a whole question overrides each of its terminals). If a scope-level shortcut is wanted, that's a UI convenience that still writes terminal-level overrides underneath; don't add a separate scope-override path to the data model.
- Bulk approval — deferred (OD/B6).

---

## 4. Schemas + compilation

### 4.1 Teacher overrides (typed)

`teacher_overrides` on `GradedTestDraft` is currently `Dict[str, Any] = {}`. S9 gives it structure. New types (in `graded_test_draft.py` or a small `overrides.py`):

```
TeacherOverride:
  points_awarded: Decimal          # the teacher's adjusted award for this terminal
  teacher_comment: Optional[str]   # the teacher's own note (their reasoning)

GradedTestOverrides = Dict[str, TeacherOverride]   # key = terminal_id (criterion_id or sub_criterion_id)
```

Update `GradedTestDraft.teacher_overrides` from `Dict[str, Any]` to `GradedTestOverrides` (keyed by terminal_id). It stays `{}` until the teacher edits.

**Sparse by design:** only terminals the teacher actually changed appear in the map. An absent key means "accept the AI's grade for this terminal." This is the overlay — the effective grade is the AI outcome with the override applied where a key exists.

**A comment without a point change is valid:** a teacher may agree with the points but add a note. So `points_awarded` in an override defaults to the AI's value if the teacher only commented — OR (cleaner) the override always carries the effective `points_awarded` (AI's value when unchanged, teacher's when changed) plus the optional comment. Use the latter: an override entry always states the final awarded points for that terminal; its presence means "the teacher touched this." (Avoids a tri-state "is points_awarded meaningful?" ambiguity.)

### 4.2 The approval gate (D2 — get this right)

Before compiling the contract, validate. **The gate is NOT the rubric's point-sum invariants** — those (PTS-R1/R1b/R2) constrain the rubric's *possible* points and were validated at rubric-compile time (S6's domain). The teacher overrides *awarded* points, which have no sum constraint (partial credit means awarded legitimately sums to less than possible). Re-firing point-sum checks on awarded points would reject valid grades. The gate validates:

1. **Bounds per terminal:** every effective `points_awarded` (overridden or AI) is within `[0, terminal.points_possible]`. An override outside bounds → reject with a clear message naming the terminal.
2. **Precision:** every overridden award conforms to `numeric_policy.precision` (round/validate, same as S7's validator — a teacher entering 2.3 when precision is 0.25 → either round or reject; **round**, and surface the rounded value, don't silently store the unrounded).
3. **Branch-aggregation consistency:** for a branch criterion (has sub-criteria), the criterion's effective awarded = Σ its sub-criteria's effective awarded. Since overrides are at the terminal (sub-criterion) level, the parent is always recomputed from children — so this holds by construction, but assert it (defense against a malformed override map that tries to override a parent directly — reject overrides keyed to a branch criterion_id; only leaf terminals are overridable).
4. **Closed-world (CW-3):** every override key is a real terminal_id present in the draft. An override referencing an unknown id → reject (`closed_world_violation`).
5. **No unresolved `error` annotations:** if `draft.annotations` contains any `severity == "error"` entry, **block approval** (Phase 0a §10.5). The teacher must resolve the underlying issue first. `warning`/`info` annotations do not block. (Mirror the rubric `ContractCompiler`, which blocks on ERROR annotations.)

On any gate failure: return a structured error (HTTP 422) listing what failed and where (which terminal, which annotation), so the UI can surface it inline. Do NOT partially compile.

### 4.3 `GradedTestContract` (net-new, frozen, provenance)

New file `app/schemas/graded_test_contract.py`. Mirror `GradingRubricContract`: `model_config = {"frozen": True}`, `Decimal` throughout, `contract_version: str = uuid4()` **inside the JSONB** (no column — consistent with the transcription contract, research Q4).

```
ContractTerminalOutcome:              # the frozen, provenance-preserving per-terminal record
  terminal_id: str                    # criterion_id or sub_criterion_id
  terminal_kind: Literal["criterion", "sub_criterion"]
  description: str
  points_possible: Decimal
  # provenance (D4): all three retained
  ai_points_awarded: Decimal          # what the AI awarded (immutable record)
  ai_reasoning: str                   # what the AI said
  ai_evidence_quote: Optional[AnswerQuotation]
  was_overridden: bool                # did the teacher change the points?
  teacher_comment: Optional[str]      # the teacher's note, if any
  final_points_awarded: Decimal       # the authoritative value (override if present, else AI)

ContractScopeOutcome:
  scope_kind: Literal["direct", "sub_question"]
  question_id: str
  sub_question_id: Optional[str]
  points_possible: Decimal
  final_points_awarded: Decimal       # Σ children's final
  terminal_outcomes: List[ContractTerminalOutcome]

GradedTestContract:
  schema_version: str = "1.0"
  contract_version: str               # fresh uuid4 at approval
  rubric_contract_version: str        # the rubric version this was graded against (pinned)
  transcription_contract_version: str
  model_version: str                  # provenance of the AI draft underneath
  prompt_version: str
  scope_outcomes: List[ContractScopeOutcome]
  total_score: Decimal                # Σ scope final
  total_possible: Decimal
  percentage: Decimal
  approved_at: str                    # ISO timestamp
```

**Provenance (D4) is the point:** every terminal carries both `ai_points_awarded` (what the AI said) and `final_points_awarded` (what was approved), plus `was_overridden`. This makes "where and how did the teacher disagree with the AI" a first-class, queryable property of every approved grade — the exact signal the eval suite (E2) needs, and the audit record for any dispute. Do not flatten to finals-only.

### 4.4 `compile_graded_test(...)`

`app/services/graded_test_contract_compiler.py`:

```
def compile_graded_test(
    draft: GradedTestDraft,
    overrides: GradedTestOverrides,
    rubric_contract: GradingRubricContract,   # for terminal points_possible / structure validation
) -> GradedTestContract
```

Steps (mirror the rubric `ContractCompiler.compile` shape):
1. **Run the approval gate (§4.2).** Raise a structured gate error on failure (the endpoint maps it to 422).
2. **Resolve effective values:** for each terminal, `final = override.points_awarded if terminal_id in overrides else ai.points_awarded`; `was_overridden = (terminal_id in overrides AND override.points_awarded != ai.points_awarded)`; `teacher_comment = override.teacher_comment if present`.
3. **Recompute aggregates:** branch criterion final = Σ sub-criteria final; scope final = Σ criterion final; `total_score` = Σ scope final; `percentage` from total (guard /0).
4. **Build the frozen `GradedTestContract`** with a fresh `uuid4()` `contract_version`, the pinned versions echoed from the draft, `approved_at`.

Pure function (no DB, no I/O) — the endpoint persists the result. Testable in isolation, like S6/S7.

---

## 5. `PATCH /graded_test/{id}/draft` — save overrides (ungated)

Lets a teacher save partial work without approving. Auth + `get_owned_or_404`.

- **Body:** `{ overrides: GradedTestOverrides }` (the full current override map — last-write-wins, simplest; or a partial merge — pick full-map replace for simplicity, document it).
- **Precondition:** row must be `status == 'draft'`. (Can't edit a `pending`/`grading`/`approved`/`failed` row.) 409 otherwise.
- **Validation:** light — keys must be known terminal_ids (closed-world), points within bounds + precision. (We validate even on save so the teacher gets immediate feedback, but this is NOT the approval gate — it doesn't check error annotations or block on them; it just rejects nonsensical overrides.) Actually: keep save-validation minimal (closed-world + bounds) so a teacher can save mid-edit; the full gate fires only at approve. A mid-edit save that's within bounds but leaves an error annotation unresolved is fine — they're not approving yet.
- **Effect:** update `draft_json.teacher_overrides` on the row. `draft_json` otherwise unchanged (AI outcomes immutable). Status stays `draft`.
- **Returns:** the updated draft response (so the UI re-syncs).

**Important — the draft's AI outcomes never change.** Only the `teacher_overrides` sub-object of `draft_json` is rewritten. Use a targeted update, not a wholesale draft replace, to make that immutability obvious and prevent a bug that overwrites AI outcomes. (`model_dump(mode="json")` on the modified draft is fine as long as the AI-outcome fields are untouched in memory.)

---

## 6. `POST /graded_test/{id}/approve` — gate + freeze

Auth + `get_owned_or_404`.

- **Body:** `{ overrides: GradedTestOverrides }` — the final override map (the teacher may have edited since the last PATCH; approve takes the authoritative set). Alternatively approve with no body and use the persisted `draft_json.teacher_overrides` — **pick: accept overrides in the body** (the UI sends the current state; approve is the commit point; this avoids a "did you save before approving?" footgun). Document that approve's body is authoritative and also persists onto the draft.
- **Precondition:** `status == 'draft'`. 409 otherwise (can't approve a pending/failed/already-approved row).
- **Load** the rubric contract (for terminal points_possible / structure) via the row's `rubric_id`.
- **`compile_graded_test(draft, overrides, rubric_contract)`** (§4.4). On gate failure → **422** with the structured failure detail (which terminals/annotations); no state change.
- **Atomic freeze (one commit — the CHECK requires all three together, research Q5):**
  - `draft_json.teacher_overrides` = the final overrides (so the draft reflects what was approved).
  - `contract_json` = `contract.model_dump(mode="json")`.
  - `total_score` / `total_possible` / `percentage` = recomputed post-override values (overwrite the S8 AI-draft aggregates with the approved ones).
  - `approved_at` = now.
  - `status = 'approved'`.
  - `regraded_to_id` stays NULL (the approved row remains the chain leaf until S10 — research Q5).
- **Returns:** `GradedTestApprovedResponse` (§7).

**`model_dump(mode="json")`** for the contract (Decimal → string), same discipline as everywhere.

**The CHECK constraint is the safety net:** `approved` requires `draft_json IS NOT NULL AND contract_json IS NOT NULL AND approved_at IS NOT NULL`. Set all in one commit or the CHECK fires — which is the correct failure (it means the endpoint logic is wrong).

---

## 7. The approved response + detail endpoint branch

Research Q3 flagged the gap: `GET /graded_test/{id}` currently returns `GradedTestDraftResponse` for approved rows (no contract field). S9 fixes it.

- New `GradedTestApprovedResponse` (in `graded_test_responses.py`): the draft response fields + `contract: GradedTestContract` (from `contract_json`) + `approved_at`.
- Add the `status == 'approved'` branch to the detail endpoint → return `GradedTestApprovedResponse`.
- The approved view shows the frozen contract (final grades + provenance), not the live draft.

---

## 8. Frontend — editable review + approve

Extends S8's `GradedTestReviewPanel` (research Q1, Q7).

### 8.1 Make the panel editable
- New props: `editable?: boolean`, `onSaveDraft: (overrides) => Promise<void>`, `onApprove: (overrides) => Promise<void>`.
- `LeafCriterionRow` gains: a **number input** for `points_awarded` (replacing the static display when `editable`), constrained to `[0, points_possible]` with `numeric_policy.precision` step, and a **teacher comment field** below the AI reasoning. The AI's `reasoning` and `evidence_quote` stay **read-only** (D3) — display them as the AI's record, with the teacher's comment as a separate field.
- Branch criteria: only the sub-criterion (leaf) rows are editable; the parent criterion's points are computed (read-only, recomputed live as the teacher edits children). Make the parent's auto-recompute visible so the teacher sees the rollup update.
- Local override state: track edits as a `GradedTestOverrides` map (terminal_id → {points_awarded, teacher_comment}); only changed terminals enter the map.

### 8.2 Error-annotation surfacing (the approval gate, client-side)
- Surface `error`-severity annotations prominently (they block approval). The approve button is **disabled (or warns)** while unresolved `error` annotations exist, with a clear message ("resolve the flagged issues before approving"). The server enforces this too (§4.2.5) — the client just gives immediate feedback.
- `warning`/`info` annotations are shown but don't block.

### 8.3 Save + approve
- **Save draft:** a "save" affordance calls `PATCH .../draft` with the current overrides (so the teacher can leave and return). Optional auto-save on blur — nice-to-have, not required.
- **Approve:** the approve button calls `POST .../approve` with the final overrides. On success → transition to an `approved` step (a confirmation + the frozen totals, or navigate to `/my-graded-tests`). On 422 (gate failure) → surface the structured errors inline.
- Live totals: as the teacher edits, recompute and show the running `total_score / total_possible` so they see the grade taking shape before approving.

### 8.4 API client + types
- `saveGradedTestDraft(id, overrides)` → `PATCH`.
- `approveGradedTest(id, overrides)` → `POST .../approve` → approved response.
- Types: `TeacherOverride`, `GradedTestOverrides`, `GradedTestContract`, `GradedTestApprovedResponse` (research Q7 sketched these).

---

## 9. Testing

### Compiler + gate (pure — zero mocks)
`tests/services/test_graded_test_contract_compiler.py`:
1. **No overrides** → contract finals == AI awards; `was_overridden == False` everywhere.
2. **Leaf override** → that terminal's `final_points_awarded` == teacher value, `was_overridden == True`, `ai_points_awarded` preserved.
3. **Branch recompute** → overriding a sub-criterion updates the parent criterion's final and the scope total.
4. **Provenance preserved** → `ai_points_awarded`, `ai_reasoning`, `teacher_comment`, `final_points_awarded` all present and correct.
5. **Gate — out of bounds** → override > points_possible rejected with terminal-naming error.
6. **Gate — precision** → an off-grid override is rounded to `numeric_policy.precision` (or rejected — match §4.2.2's "round" choice).
7. **Gate — closed-world** → override keyed to unknown terminal_id rejected.
8. **Gate — override on a branch criterion_id** (not a leaf) rejected (only leaves overridable).
9. **Gate — error annotation blocks** → a draft with an `error` annotation cannot compile; `warning`/`info` do not block.
10. **Aggregates** → total_score/possible/percentage correct post-override; /0 guarded.

### Endpoints
`tests/api/test_graded_test_approval.py`:
11. **PATCH auth + ownership** (401, 404 cross-user); **status guard** (409 if not `draft`).
12. **PATCH saves overrides** → `draft_json.teacher_overrides` updated, AI outcomes byte-unchanged, status stays `draft`.
13. **Approve happy path** → row becomes `approved` with `contract_json`, `approved_at`, recomputed aggregates, all in one commit; `regraded_to_id` stays NULL.
14. **Approve gate failure → 422**, no state change (row stays `draft`).
15. **Approve status guard** (409 if not `draft`).
16. **Detail endpoint approved branch** → returns `GradedTestApprovedResponse` with the contract for an approved row.
17. **AI-outcome immutability** → after PATCH and after approve, the draft's AI `points_awarded`/`reasoning`/`evidence_quote` are unchanged from what S8 wrote (only overrides + contract added).

### Frontend
- Editable rows: point inputs bounded + precision-stepped; comment fields; AI reasoning read-only.
- Branch parent recomputes live from sub-criterion edits.
- Approve disabled while `error` annotations unresolved.
- Approve → approved state; 422 surfaces inline.

Tests 9 (error-annotation block), 13 (atomic approve), and 17 (AI-outcome immutability) protect the core invariants.

---

## 10. Acceptance criteria

- [ ] `teacher_overrides` typed as `GradedTestOverrides` (terminal_id → `{points_awarded, teacher_comment}`); sparse; replaces `Dict[str, Any]`.
- [ ] `GradedTestContract` net-new, frozen, Decimal throughout, `contract_version` (uuid4) inside the JSONB; preserves provenance (`ai_points_awarded` + `was_overridden` + `final_points_awarded` + `teacher_comment` per terminal).
- [ ] `compile_graded_test(...)` pure; runs the gate, resolves effective values, recomputes aggregates, freezes.
- [ ] Approval gate: bounds-per-terminal + precision + branch-aggregation + closed-world + no-`error`-annotations; does **NOT** re-fire rubric point-sum invariants on awarded points.
- [ ] `PATCH .../draft`: ungated save of overrides, `draft` only (409 else), AI outcomes untouched.
- [ ] `POST .../approve`: gate → compile → **atomic** freeze (contract_json + draft_json + approved_at + status in one commit), recomputed aggregates, `regraded_to_id` stays NULL; 422 on gate failure with structured detail.
- [ ] `GradedTestApprovedResponse` + detail-endpoint `approved` branch.
- [ ] Frontend: editable point inputs (bounded, precision-stepped) + comment fields; AI reasoning/quote read-only; branch parent recomputes live; error-annotations block approve client-side; save + approve flows; live totals.
- [ ] All tests pass; tests 9, 13, 17 explicitly verified; `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 11. Known follow-ups (do NOT do in this PR)

- **S10** — re-grade-stale + manual-edit (the revision chain). An approved row becomes non-leaf when a successor is created; `regraded_to_id` gets set there. The `rubric_contract_stale` computed flag (Phase 0a §9.2) surfaces when to offer re-grade.
- **Bulk approval** (OD/B6) — when most drafts are approved unedited, a "approve all non-flagged" affordance. Deferred.
- **Eval suite (E2)** — consumes the provenance data (`was_overridden`, `ai_points_awarded` vs `final_points_awarded`) this sprint produces. The override-where-teachers-disagreed signal is exactly E2's golden-comparison input.

If the atomic three-field commit fights the ORM (e.g. the CHECK fires because a field is set in the wrong order or a flush happens mid-update), **flag it** — the fix is to set all fields in memory then commit once, not to relax the CHECK. And if `numeric_policy` isn't readily accessible at the contract-compile site (it's on the rubric contract), confirm the access path before assuming it.
