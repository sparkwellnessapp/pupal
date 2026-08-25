# GRADING_GT_CONVENTIONS — ground-truth authoring rules

**Status: RATIFIED 2026-08-24 (Phase-B ruling) — C-1/C-2 ruled, C-4 confirmed,
C-3/C-5 mission-ratified. F5 (blind grading) is unblocked.** Ruling text below
is verbatim-binding.

---

## 1. What the GT is

Per fixture: the owner's blind judgment of one student test, authored from the
**corrected rubric contract** (H1-ratified) + the **draft-GT transcription text**
[R3 — the faithful transcription is exactly what production grading consumes
post-review]. Format: `benchmarks/gt/<fixture>.gt.json`, typed as
`schemas.FixtureGT` [D1]:

- header: `fixture`, `rubric_contract_hash`, `transcription_contract_hash`
  (sha256 of the snapshot files — the D5 pin), `gt_source: teacher_manual`,
  `authored_by`, `authored_at` (ISO-8601 — the R1 blind-sequencing anchor),
  `blind: true`;
- per terminal: `{terminal_id, awarded (Decimal string, on the 0.25 grid),
  evidence_exists (bool), note?}`;
- per scope, optional: `ungradable_scopes: [{question_id, sub_question_id,
  reason}]` [C-2].

**Workflow:** `python -m tests.grading_eval_suite.tools.build_gt_skeleton
--fixture <name>` emits a skeleton with every terminal pre-populated
(`points_possible` + `description` shown as authoring aids); the owner fills
judgments ONLY, stamps `authored_at`, removes `_instructions`. The loader
refuses partial files — that is the completion check.

**Blindness [R1] is mechanical:** author from rubric + transcription only, never
having seen grader output for that fixture. The runner refuses to score any
fixture whose GT `authored_at` postdates a cached grader draft for it.

## 2. Totals

Derived by running the GT terminals through the REAL `selection_scoring` —
never hand-summed [§5]. Do not write a total anywhere in the GT file.

---

## C-rulings (owner) — OPEN until filled

### C-1 (ratified 2026-08-24)

Grade the text, not the intent. Where the teacher would need the paper to decide, use C-2.
Table exception (owner caveat): when tabular content — trace tables especially — is structurally garbled by transcription (uneven column×row matrices, spanning cells collapsed, row-alignment lost) and the intent is confidently reconstructible from the garbled text, GT awards credit per the reconstructed intent. The terminal's note records [C1-TABLE] plus one line stating the interpretation basis. If the intent is not confidently reconstructible → C-2, reason garbled_structure.
Model-side expectation (step-3 design input — NOT a v0 gate): the grader is expected to interpret confidently-reconstructible garbled tables and surface a teacher-facing note explaining the interpretation. Evidence quotes remain verbatim from the transcription — interpretation lives in reasoning — so T1-FABRICATED is unaffected. A dedicated FlagReason for degraded-input interpretation is a step-3 grader-design item; v0 measures table-terminal agreement through ordinary Tier-2, which is exactly what tells us whether the current grader under-interprets tables.

### C-2 (ratified 2026-08-24)

Use sparingly. Reason vocabulary: illegible · ambiguous_student_intent · missing_content · garbled_structure (structurally mangled tabular content, not confidently reconstructible — see C-1). Terminals on an ungradable scope still carry the owner's best-guess awarded (totals require a number) but are excluded from all Tier-2 agreement metrics (MAE, within-precision, exact, edit_burden, compensating-error input). The best-guess participates only in totals via score_with_selection; any fixture containing ungradable scopes is marked in its report block ("total includes N ungradable-scope terminals"). Tier-1 behavior tripwire unchanged: an unflagged confident award by the model on a GT-ungradable scope gate-fails.

### C-3 — Point values only (RATIFIED by the mission)

GT records point VALUES, not acceptable ranges. Ranges are deferred until the
judge's `both_defensible` verdicts produce evidence they are needed [R4' note].

### C-4 — Grade-boundary set (CONFIRMED as defaulted, 2026-08-24)

`{55, 65, 75, 85, 95}`, pass convention `>= b` passes; the 55 pass line is
certain. Implemented as `scoring.C4_BOUNDARIES`. Changing it later is an
instrument change (suite_hash shifts, RUNLOG entry required).

### C-5 — `evidence_exists=false` with a non-zero award (RATIFIED by the mission)

Legal, and recorded: the teacher may give credit without quotable evidence
(e.g. diffuse correctness across the answer). The scorer does NOT penalize the
model's award for GT `evidence_exists=false`; the field exists so the judge and
later analyses can separate "model found evidence the teacher didn't quote"
from "model fabricated evidence" [DL-2 stays a model-side rule].

---

## 3. Registered seed-set gaps [mission §4 — copied to ONBOARDING]

n=5, ONE exam (hobby_tvshow corrected). No selection-group exam; no depth-2
nested rubric (parent-fallback unexercised); no fluent-but-wrong answer; no
all-blank test. Every rate is PROVISIONAL until n>=10 across >=2 exams.


---

# AMENDMENT M1 (owner-ratified 2026-08-25) — GT provenance classes

`gt_source ∈ {teacher_manual, teacher_validated, production_approval}`:

| Class | Requirements | Gating |
|---|---|---|
| `teacher_manual` | `blind: true` [R1] — owner authors from rubric + transcription only | gates (original class) |
| `teacher_validated` | `blind: false` + `proposed_by` + `validated_by` — agent-proposed judgments, owner-validated, both parties on record | **v0 gates on this class per owner ruling** |
| `production_approval` | flywheel imports [D10] | stays NON-gating |

Loader enforcement (fixtures.py): `teacher_validated` with `blind: true` is
refused (a validated GT must not claim blindness); missing attribution is
refused. `gt_source` is surfaced per fixture in `results.json` provenance and
`summary.md`. The session-emitted GTs carry
`gt_source: teacher_validated, proposed_by: "claude-fable-5 (design-partner
session)", validated_by: "Noam", blind: false`. Skeleton-header regeneration
to M1 form is optional (owner grading in progress); the loader accepts both
header forms since the M1 fields default to null.
