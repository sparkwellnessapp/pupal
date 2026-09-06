# TRACKER — plan compiler v2

Plan: `PLAN_compiler_v2_impl.md` · PR: `PR_plan_compiler_v2.md`. A row is ticked only when its
gate has run. Legend: ☐ todo · ◐ in progress · ☑ done+verified · ⊘ deliberately not done (reason)

## P1 — the `counted` kind (algebra, end-to-end)

| # | Item | State |
|---|---|---|
| 1.1 | `plan_schemas`: kind, `unit_count`, `CheckVerdict.units_correct`, provenance fields | ☑ `units_correct` appended LAST (decode-order pin extended, F-9) |
| 1.2 | `plan_validator`: V3 counted shape, V12 alone, V1 includes counted points | ☑ V12 (7 shape rules) + V1 sums counted |
| 1.3 | `pricing.py` composer + `pricer.py` per-check + `AssessedVerdict.units_correct` | ☑ `counted_units()` in pricing.py is the one arithmetic; pricer flags/lines only |
| 1.4 | `graded_test_draft.Check` wire fields | ☑ + `count_missing` in the annotation vocabulary (F-10) |
| 1.5 | `grader_v5` passes `units_correct`; verifier renders counted (OD-18) | ☑ system prompt byte-identical; `_COUNTED_RULE` in the user message only when present |
| 1.6 | `plan_expressibility` counted branch | ☑ |
| 1.7 | tests: shape, alone, pricing 12×15/17→10.5, expressibility, missing-count flag | ☑ `tests/agents/test_counted_kind.py` (14) · agents 151 · services 452 |

## P2 — R-2 companion guard

| # | Item | State |
|---|---|---|
| 2.1 | `fixtures.unattempted_scope_keys` + `read_gt_judgments` | ☑ transcription-derived; raw reader refuses null-on-attempted |
| 2.2 | `TerminalScore.unattempted`; scoring/reporting/gates key on it | ☑ (OD-19: best-k-excluded-but-ATTEMPTED terminals now stay IN per-terminal metrics) |
| 2.3 | `unselected-scopes-never-enter-any-denominator` (298, not 403) | ☑ `test_r2_selection_guard.py` (5) — 298 measured |
| 2.4 | hobby byte-identity guard normalised forward (OD-16) | ☑ baseline normalised FORWARD only; eval suite 98 |

## P3 — Stage 1 compiler

| # | Item | State |
|---|---|---|
| 3.1 | `skeleton.py` types (`Slot`, `TerminalSkeleton`, `PlanSkeleton`, flags) | ☑ `skeleton.py` — Slot carries verbatim `source_span` + marker-free `summary` + tariff `anchor_span` |
| 3.2 | C1 tariffs (+לקנוס/קנס, OD-10 parent→first child + sibling group, Case 4) | ☑ positional clauses; לקנוס/קנס + «להוריד רק פעם»; Case 4; OD-10 on the first child that can CARRY it (OD-23); folds (OD-21); value-reclassify (OD-20); amountless → stated value of the modified component (OD-15) |
| 3.3 | C2 notes | ☑ |
| 3.4 | C3 counted trigger | ☑ «17 תאים 0.7 כל תא» → counted N=17, per-unit rounding flagged |
| 3.5 | C4 enumeration parser (values / separators / monolith; code-span aware) | ☑ paren/inline/reversed/bare(Σ==P)/separators/numbered/identifier-list; code tail cut at the first `;`/`{` |
| 3.6 | C5 points: Case 2, Case 3 (strict), even split + OD-9 residual | ☑ Case 2 fill + remainder slot; Case 3 strict (both references); even split on the ½-lattice (OD-22) |
| 3.7 | C6 groups («פעם אחת») | ☑ «פעם אחת» → group; scope-level merge by anchor-token Jaccard ≥ 0.5 |
| 3.8 | C7 routing (OD-14) | ☑ literal OD-11; hobby +q2.ב.c3.s3, bagrut +q1.ב.1.c0 +q6.c5 −q2.ב.c3 (OD-14) |
| 3.9 | V1 asserted by construction | ☑ `CompilerBug` on Σ≠P or off-grid |
| 3.10 | calibration tests vs the hand plan (every hobby terminal's algebra) | ☑ `tests/agents/test_plan_compiler_stage1.py` (39): every hobby terminal pinned, 4 divergences recorded; agents 189 |

## P4 — Stage 3 + A0

| # | Item | State |
|---|---|---|
| 4.1 | `assemble.py`: skeleton → `GradingPlan` (placeholder text), validate, V11 assertion | ☑ `assemble.py` — placeholder + wording entry points; V9 short-quote widening; V10 `point_blind` |
| 4.2 | `tools/compile_plan.py` A0 driver, both exams | ☑ `tools/compile_plan.py` — validator 0/0, R-2 reader, classified misses, OD-24 counterfactual |
| 4.3 | `A0_REPORT.md`: scorecard, every miss classified, every flag | ☑ `A0_REPORT.md` regenerated deterministically; verdicts computed |
| 4.4 | 488-judgment expressibility guard standing | ☑ `test_compiled_plan_guard.py` — 488 = 190 + 298; every miss pinned by class |
| 4.5 | compiled plans committed append-only with provenance | ☑ committed with the compiler (append-only; `.gitignore` negation for `plans/**/*.json`) |

## P5 — retire · P6 — segmenter/router (spend-gated)

| # | Item | State |
|---|---|---|
| 5.1 | retire `PlanGenerator`, repair loop, `dispositions.py`, its tests (recorded) | ☑ `generator.py`, `schemas.py`, `dispositions.py`, `tools/gen_plan.py`, `test_plan_gen_structure.py` removed; Stage 0 → `plan_compiler/stage0.py`; the ratified depth-2 guards re-pointed; detector tests keep their detector half |
| 6.1 | `segment.py` + `segmenter/v1` prompt; A1 ≤ $2 | ◐ `segment.py` + `segmenter/v1` + fake-model tests; dry-run estimate hobby ≈ $0.06 · bagrut ≈ $0.12 (envelope $2). **Spend HELD** — A0 gates all spend and bagrut A0 is not green as ratified |
| 6.2 | `route.py`; A2 ≤ $1; reference structures reproduced | ◐ `route.py` + `router/v1` + fake-model tests (apply_routing on the ½-lattice, tariffs kept, monolith kept on failure); dry-run estimate hobby ≈ $0.03 · bagrut ≈ $0.04 (envelope $1). **Spend HELD** |

## Findings log
(appended per phase)

- **F-9** `CheckVerdict.units_correct` had to go LAST: `test_check_verdict_decode_order_is_evidence_first`
  pins the five-field decode prefix byte-for-byte. Appended after `confidence`; the pin now names
  six fields and additionally asserts `units_correct` is ABSENT from `VERIFIER_SYSTEM_PROMPT`
  (the grader-v5.3 package is untouched) and PRESENT in `_COUNTED_RULE` (user message, OD-18).
  ⚠ The structured-output JSON schema sent to the production verifier now carries an optional
  trailing field — harmless on a plan with no counted check, but it IS a change to the pinned
  request shape. Surfaced, not decided.
- **F-10** `GradingAnnotation.annotation_type` is a closed Literal; `count_missing` added at its
  tail. `frontend/src/lib/api-types.ts` regen is owed (with the stamp-endpoint regen already owed).
- **OD-19** (P2, surfaced) R-2 keys every per-terminal denominator on `unattempted`
  (transcription-derived). The OLD rule also dropped best-k-EXCLUDED-but-attempted terminals from
  agreement metrics (`test_selection_totals_never_rederive_denominator` pinned MAE = (6+0)/2).
  Under R-2 those judgments are real (a 5-attempt student's weakest attempted question), so the
  pin moved to (6+6+0)/3. Live delta: ZERO — hobby has no selection groups; every bagrut
  fixture attempted exactly 4 of 6, so best-k excludes exactly the unattempted pair. Owner may
  rule the other way; it is a one-line change in `scoring.py::included` + `gates._included_rows`.

- **A0 (2026-09-05, zero spend).** hobby **184/190** — routed 5 (OD-13) + ruling 1 (PR-exempt); non-routed
  164/165. bagrut **284/298** — routed 4, granularity-floor 2, granularity-ladder 1,
  **decomposition 7** (q3.ב.c5 ×1, q3.ב.c6 ×6 — both P=3 monoliths «לולאה … הסורקת ומדפיסה …»,
  one point under OD-11's threshold). Validator 0/0 on both. Named outcomes ✓ except the routed set
  (OD-14, predicted) and «tariffs 10» (12 phrases detected ⊇ the PR's 10; 9 slots after 2 folds + 1
  value-reclassification). **Bagrut A0 is NOT green as ratified**; the OD-24 counterfactual is in the report.
- **OD-20** «X – 2 נק'» is a VALUE closing a component, not a tariff (q1.ב.2.c0); a `[-–] N נק'` hit with
  no deduction verb in its clause is reclassified and flagged.
- **OD-21** a deduction worth exactly the component it modifies (and not charge-once) is that component's
  own failure — no tariff slot. Reproduces the hand plan on q1.ב.c6 and q1.ג.c6/c7 («חלוקה באפס»);
  folds bagrut q5.א.c0 / q6.c0 («כל טעות להוריד 1» on 1-point terminals).
- **OD-22** OD-9's unit must be 2×grid or V4 refuses the plan (1.75 → 0.875). 5 over 3 = 2/1.5/1.5, not
  the PR's 1.75/1.75/1.5. A split that cannot keep halves on the grid is refused (0.5 over 2 → one check).
- **OD-23** OD-10's «first child» collides with V3 (3-point tariff on a 1-point child). Anchored on the
  first child that can carry it — s3, the hand plan's own anchor.
- **OD-24** (recommendation) route monoliths at **P ≥ 3** with a solution: the 7 decomposition misses become
  routed-class; hobby's two hand-plan divergences (q1.ב.c2/c4, both P=3 split 1.5/1.5 by hand) would also
  route. A ruling, not a compiler change — reported as a counterfactual, default untouched.
- **A1/A2 dry run (zero spend, 2026-09-05).** `tools/segment_plan.py --stage both --dry-run`: router 5 + 8
  monoliths, ≈ $0.03 + $0.04 (Sonnet 5); segmenter 6 + 13 scope calls, ≈ $0.06 + $0.12 (Haiku 4.5).
  Both far inside the envelopes. Held: **A0 gates all spend** and the bagrut verdict is NOT GREEN as
  ratified (OD-24 open). Running them is one command once the owner rules.
- **OD-25** (surfaced) the segmenter message includes the scope's example solution whenever one exists,
  not «only if a slot needs an equivalence note» (PR §4) — the need is not knowable before the call, and
  the licence check on the note is what actually gates it. Measured cost of the inclusion is in the
  dry-run estimate above.

## W — production wiring (owner instruction 2026-09-05/06; PLAN_production_wiring.md)

Rulings: W-1 `grading_plans` append-only by contract hash (026) · W-2 built at compile, substitution
guarantees a plan · W-3 hidden from the teacher, auto-accept · W-4 v5 always. OD-W1 both paths · OD-W2 own
queue `plan-build-jobs` · OD-W3 wait ≤240 s on a live heartbeat then take over (the queue split does not
remove the grade-arrives-while-building case) · OD-W4 hash with `contract_version` blanked · OD-W5 P ≥ 3 ·
OD-W6 `grader-v5.4` · OD-W7 file pin retired · OD-W8 frontend counted mirror · OD-W9 first grade builds ·
OD-W10 $1/rubric · OD-W11 placeholder stays, no auto-rebuild (fallback provider later) · OD-W12 8 scopes.

| # | Item | State |
|---|---|---|
| W0 | migration 026 + ORM + ledger/canon + `plan_store` (hash, CAS lifecycle, supersede) | ☑ applied to Vivi-Test; 7 store tests on the real DB |
| W1 | `plan_build_runner` (compile→route→segment→assemble→validate; placeholder on any model failure; `failed` only on CompilerBug) · `PLAN_BUILD_KIND` + `plan-build-jobs` · `/internal/plan-jobs/{id}/run` · `plan_job_liveness` + startup sweep · the three endpoints kick after commit | ☑ 11 builder tests (fake model, real DB) · kick · internal route · trigger tests; root conftest forbids a provider inside any plan build |
| W2 | `grader_selection` v5-always (v3 = rollback knob only) · runner resolves ready/wait/build-in-place · `plan_wording_source` stamped · cost priced by model · `VERIFIER_PROMPT_VERSION = grader-v5.4` · file pin + `app/agents/grader/plans/` retired | ☑ selection/runner/pin tests; V9/V10 calibration re-pointed to the eval copy |
| W3 | frontend: `pricing.ts` counted branch + `divideContext` (CPython 28-digit HALF_EVEN) · `CheckRow` «k מתוך N» · model pass-through · parity tests · `api-types.ts` regen | ☑ tsc clean · vitest 1083 |
| W4 | deploy: `ANTHROPIC_API_KEY` secret (absent on the service today) · queue `plan-build-jobs` · migration 026 on prod · env `GRADER_MAX_CONCURRENT_SCOPES=8` · smoke | ☑ 2026-09-06: secret `anthropic-api-key` v1 + SA binding · queue `plan-build-jobs` (20/3/10s) · 025 AND 026 applied to prod (025 was missing — owner-ruled apply) · revision `gradervision-backend-00040-b88` at 100%, boot `SCHEMA OK: migration head 026` · env `GRADER_MAX_CONCURRENT_SCOPES=8`, `CLOUD_TASKS_PLAN_BUILD_QUEUE` |
| W5 | A1/A2 on the eval exams, then A3 (~$6) against the 08-31 bars | ◐ A1+A2 ran for REAL in production on `bagrut_899371` (rubric 09cb31da): queued→task→ready in 4:35, **$0.3488** (2× the dry-run estimate), segmented, 1/111 slots substituted, router 9/14 monoliths split (q6.c8 → 3, the reference shape), 5 kept whole. A3 still owed (B-34) |
- **Production smoke (2026-09-06 06:10–06:15 UTC).** `grading_plans` row `41f9f636…` for rubric `09cb31da…`:
  Cloud Task dispatched in 10 s, builder wall 4:35, cost $0.3488, wording `segmented`, 61 terminals /
  111 checks (99 required · 9 tariff · 2 note · 1 counted), substituted 1, router split 9/14 (five
  refusals kept whole — reasons now persisted in `skeleton_json.build.router_notes`). Flags: 14 routed,
  13 code tails, 4 splits refused below the ½-lattice, 3 charge-once groups, 2 Case 3, 1 Case 4.
