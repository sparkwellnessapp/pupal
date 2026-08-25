# PR-G1 v2 ADDENDUM — prefix-context seam + round-0 carryover (2026-08-25)

**Commit: `71305dc`** (16 files, +515/−22). Zero spend · zero Gemini ·
validator untouched · D6 model seam remains step-3.

---

## 0. Carryover confirmations (round-0 gate — was NOT previously landed; landed here first)

| Item | Status |
|---|---|
| M1 provenance classes | LANDED. `gt_source ∈ {teacher_manual, teacher_validated, production_approval}`; `teacher_validated` requires `blind: false` + `proposed_by` + `validated_by`; loader refuses `blind: true` on it and refuses missing attribution; gating sentence amended in schema comment + GT_CONVENTIONS **Amendment M1** (appended; ratified text untouched): *v0 gates on the teacher_validated class per owner ruling; production_approval stays non-gating*. `gt_sources` surfaced per fixture in `results.json` provenance + `summary.md` |
| Landed before first GT commit? | YES — `benchmarks/gt/` verified to hold skeletons only; the session's `teacher_validated` GTs will be accepted on arrival |
| `GRADING_PROMPT_VERSION` → `grader-v2` | LANDED (canonicalized from the interim `grader-v2-evidence-first`; decode-order lever unchanged; its pin test green) |
| PREDICTIONS dispositions (append-only) | LANDED: **P4 WITHDRAWN-UNMEASURABLE · E1 OVERTAKEN-BY-OWNER-ACTION · E3 RESOLVED-BY-ARGUMENT** |
| Skeleton-header regen to M1 form | SKIPPED per ruling (optional; owner grading now; M1 fields default null so both header forms load) |

## 1. Reds (verbatim, captured pre-implementation)

```
FAILED tests/agents/test_prior_context.py::test_compiler_prefix_only_document_order
FAILED tests/agents/test_prior_context.py::test_flag_on_renders_priors_in_ruled_order
FAILED tests/agents/test_prior_context.py::test_version_is_pure_function_of_code_and_flag
FAILED tests/grading_eval_suite/test_gt_loader.py::test_m1_teacher_validated_accepted
FAILED tests/grading_eval_suite/test_gt_loader.py::test_m1_teacher_validated_refuses_blind_true
FAILED tests/grading_eval_suite/test_gt_loader.py::test_m1_teacher_validated_requires_attribution
6 failed, 17 passed
```
Green-affirmation pins (green pre AND post, by design): the off-path byte pin
and OV-1.

## 2. Off-path byte-equality proof (item 3)

`build_user_message(dan_basiuk q1.ב)` sha256 captured **before** the seam:
`c575112f6d85237e5946cff8b5cbee601b6d37f8f3c331dbb4502648d1a9b95a` — embedded
in `test_flag_off_prompt_byte_identical_to_prechange`, **green after** the
seam landed: the flag-off render is byte-identical to today's. The flag-on
empty-priors case is additionally pinned equal to flag-off.

## 3. The seam, as ruled

- **Schema**: `PriorPartContext` — the ratified shape verbatim; docstring
  records the exclusion ruling (*prior criteria and prior awarded points are
  deliberately excluded; do not add them*). `GradableScope.prior_parts`
  additive with `default_factory=list`.
- **Compiler**: `prior_acc` threaded per question through `_emit_leaf_scopes`;
  each leaf snapshots the prefix BEFORE joining it. Prefix-only, document
  order; direct-criteria + first parts `[]` — all pinned by (i). Nested-rubric
  semantics documented in-code: preceding LEAVES in exam reading order (equals
  "preceding sub-questions" at depth-1, the entire current fixture set).
  Sliced from the two frozen contracts only — determinism boundary unmoved,
  closed-world terminal lists untouched (item 6 proof below).
- **Prompt**: flag-gated block between the parent stem and the current part —
  ruled header «חלקים קודמים — להקשר בלבד: אין לנקד אותם ואין לצטט מתוכם»,
  per part: text → example solution (if present) → answer / «לא נענה».
  Pinned order (iii): stem < header < א-text < א-solution < א-answer < ב-text
  < «לא נענה» < current part < GRADE THESE.
- **Version integrity (iv)**: `grader-v2` off / `grader-v2+priorctx` on —
  pure function of code + flag, stamped in drafts and provenance. Dry proof:
  `{prior_context: false}→'grader-v2'`, `{prior_context: true}→'grader-v2+priorctx'`,
  `{}→'grader-v2'` (env set explicitly both ways — no ambient leakage).
- **OV-1 pin (v)**: two terminals in one scope quoting the identical span →
  both `exact`, zero flags, zero annotations. The ruling is recorded verbatim
  in the test body (existence check, never exclusivity; within-scope overlap
  legal for v0; any future constraint = owner ruling + Tier-3 counter first,
  never a validity gate).

**One disclosed touch outside the named files:** `grader.py`'s two
`prompt_version` stamp sites now call `effective_prompt_version()` — item 4
("stamped prompt_version is a pure function of code + flag") is unsatisfiable
without it; 3-line diff, nothing else in the file moved.

## 4. Universe assertion (item 6)

`test_terminal_universe_unchanged_after_prior_context_seam`: all five bundles
load, **38 terminals/fixture, 190 total**, hash pins green — `prior_parts` is
compiler output; nothing the suite hashes moved.

## 5. E4 registered (item 7)

Verbatim in PREDICTIONS.md, plus the baseline discipline in the config itself:
`configs/gpt-4o.json` now carries explicit `"prior_context": false` — the
baseline runs the seam OFF; the E4 run's single variable is the flag flip,
same fixtures, same k.

## 6. Batteries

| Battery | Result |
|---|---|
| grading suite + eval_common + agents | **81 passed, 1 xfailed** (the D5 sonnet sentinel) |
| zero-mock compiler + grading-runner | **25 passed** (the compiler change broke nothing it pins) |
| transcription | **134 / 1 skipped — baseline-identical** |
| rubric | unchanged from the prior report: 8 Family-D + 9 in the concurrent session's mid-edit files; zero overlap with this diff |
| `import app.main` | clean |

RUNLOG CHANGE entry appended (suite_hash shift noted — harmless, no baseline
exists). **State: [STOP] F5 unchanged — owner grading; the session's
`teacher_validated` GT files will now load.**
