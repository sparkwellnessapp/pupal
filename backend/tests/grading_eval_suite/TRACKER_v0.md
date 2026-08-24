# TRACKER — Grading Eval Suite v0 implementation

**Mission:** `MISSION_grading_eval_suite_v0.md` (RATIFIED; wins over the report on conflict)
**Protocol:** per-item — pre-flight census → failing test first → implement inside the fence →
adversarial self-review → evidence in the phase report. Sanity gates every phase.
**Scope fence reminder:** nothing under `app/` (import-only); sibling suites read+snapshot only;
one edit to `tests/eval_common/test_models_registry.py::_config_model_keys`; zero Gemini; zero
API calls in `pytest -q`; Phase A = zero spend.

Statuses: `[ ]` todo · `[~]` in progress · `[x]` done (evidence in phase report) · `[STOP]` owner gate

---

## Phase A — Instrument (zero spend) → gate: external review (§1.6) of PHASE_A_REPORT.md

| # | Item | Mission trace | Status |
|---|---|---|---|
| A1 | Suite skeleton: `__init__.py`; docs: `ONBOARDING.md` (+seed-gap register), `GRADING_EVAL_PLAYBOOK.md` (STOP list, tiers, validity taxonomy, standing rules, provisional definitions), `GRADING_GT_CONVENTIONS.md` (C-1..C-5 skeleton, owner-to-rule markers, C-4 default), `RUNLOG.md` seeded, `PREDICTIONS.md` seeded (P1 verbatim + baseline placeholder) | §10, §11-A, P1, C-1..C-5 | [x] |
| A2 | `schemas.py`: GT types (`FixtureGT`/`TerminalGT`/`ScopeUngradable`, D1 incl. `evidence_exists` + `ungradable` + `gt_source` hook D10) + result rows (`TerminalScore`, `TrialScore`, slots=True) | §5, R3, D1, D10 | [x] |
| A3 | `fixtures.py`: manifest loader (per-fixture pairing — F3 law), contract loaders + sha256 pinning (D5), GT loader guards (totality/bounds/precision-grid/hash/blind — §5), R1 blind-sequencing enforcement (grade refused w/o GT; scoring refused when any cached draft predates GT.authored_at) | R1, R3, D5, F3, §5 | [x] |
| A4 | `scoring.py` (pure, no agent import): per-terminal Δ/within-precision/exact/quote-status; Tier-1 tripwires (fabricated-evidence, closed-world, skip-agreement, GT-ungradable guess, cost ceiling); Tier-2 (MAE, rates, total_Δ via REAL `score_with_selection` both sides, shippable ≤1.0 R4′, boundary flips C-4, edit_burden); Tier-3 (parse-rate R6, fallback rate, quote distribution, calibration inputs); compensating_error flag; validity taxonomy (transport ⇒ invalid, parse ⇒ scored R6) | §6, §7, R4′, R6, C-4 | [x] |
| A5 | `reporting.py`: aggregates (worst-test first, repeat stability, ECE n-flagged, PROVISIONAL stamps n<10/k=1), `results.json` + `summary.md` + `report_<fixture>.md` (terminal table: gold\|awarded\|Δ\|quote\|conf\|reasoning) | §6, §9 | [x] |
| A6 | `runner.py`: modes `grade`/`score_only`, `--scopes` (diagnostic, PROVISIONAL), k configurable; per-trial `asyncio.wait_for` 300 s; exactly ONE re-run on retryable transport (wall counted as transport-hang) — RUNLOG-noted; drafts persisted as they arrive; provenance (suite_hash D3 incl. snapshots+registry, model_key/registry_as_of/models, `GRADING_PROMPT_VERSION`); config = model_key + ceiling (legacy-key refusal); settings-pin assertion (spec.model_id == settings.openai_model) | §3, §7, §9, D3, D7, G-3 | [x] |
| A7 | `configs/gpt-4o.json` (deployed pin, ceiling $0.10) + eval_common dry-resolve extension (same PR) | §2, R7, Tier-1 | [x] |
| A8 | Guards (`test_*.py`, zero API): known-answer self-pass; injected-error per metric (fabricated quote, closed-world leak, selection re-derivation, compensating pair, boundary flip, skip-agreement, cost ceiling); loader guards; R1 refusal tests; runner policy pins (numeric_policy passthrough, pin assertion, wall/retry policy) | §10 | [x] |
| A9 | Sanity gates: `import app.main`; `pytest --collect-only`; sibling batteries baseline-identical (transcription 133/1, rubric 8 Family-D only); suite battery green | §11 | [x] |
| A10 | `PHASE_A_REPORT.md`: per-item DONE sections with proofs (red-first outputs, guard results, census) | §11 | [x] |

## Phase B — Fixtures + GT → gate: GT committed + guards green + H1 ratified

| # | Item | Mission trace | Status |
|---|---|---|---|
| B0 | F0 mechanical half: compile original hobby GT (expect q2 block — proof), apply recorded fix_proposal (move_text ג, move_criterion ב.c6→ג, set_points 16; id rename ב.c6→ג.c0 surfaced), compile proof clean, produce `H1_CORRECTION_PROPOSAL.md` (diff + proofs + provenance draft) | F0, R5/H1 | [x] proposal staged |
| B0-gate | **Owner ratified H1** (Phase-B ruling item 1) → snapshot + provenance written (`ratified_by: Noam, 2026-08-24`; DL-5 + DL-6 accepted) | R5/H1 | [x] ratified |
| B1 | F1 converter: sibling draft-GT md → `TranscriptionContract` JSON; deterministic; unit-tested; parity guard vs `ground_truth.load_ground_truth` on all 5 docs | F1 | [x] built; parity 5/5 green |
| B2 | F2 snapshots: 5 transcription contracts → `benchmarks/transcriptions/` (6 answers each), sources committed first (6337fbc) | F2, D2 | [x] |
| B3 | F3 manifests ×5 (paths + provenance + sha256 pins; verified loading post-commit) | F3 | [x] |
| B4 | F4 GT builder: 5 skeletons emitted, 38 terminals each (190 judgments total — above the ~120-150 estimate; flagged) | F4 | [x] |
| B5 | **Owner blind-grades 5 tests** (R1; 190 judgments from the skeletons); C-1..C-5 RULED 2026-08-24 (verbatim in GT_CONVENTIONS) | F5, R1, §5 | [STOP] owner — THE active gate |

## Phase C — Baseline (≈$1) → gate: baseline report reviewed; Tier-2 thresholds pre-registered after

| # | Item | Trace | Status |
|---|---|---|---|
| C1 | Pre-baseline quantitative prediction authored (owner + reviewer) into PREDICTIONS.md | §11-C | [STOP] owner |
| C2 | k=5 × 5 deployed pin run (R7); doubles as multi-scope smoke (U2/G-21) — say so in report | R7, G-21 | [ ] |
| C3 | Full analysis per PLAYBOOK: validity → worst test → ≥2 hand-read terminal tables → Tier-2 distributions → R6 escalation check → threshold candidates pre-registered | §6, R6 | [ ] |

## Phase D — Judge bootstrap → gate: judge report reviewed

| # | Item | Trace | Status |
|---|---|---|---|
| D1 | Judge pass (offline, Anthropic frontier reasoning, registry-carded; k=3 majority; `JUDGE_PROMPT_VERSION`; raw stored) over Phase-C disagreements | §8, R2 | [ ] |
| D2 | Owner labels ~20; agreement stat reported BEFORE any judge label used; promotion bar pre-registered | §8, R2 | [STOP] owner |

---

## Decision log (agent-level, surfaced in phase report)

- **DL-1** Compensating-error operational definition (provisional, PLAYBOOK-documented): flag iff
  `|total_Δ| ≤ 1.0` AND `Σ|terminal Δ| − |total_Δ| ≥ 2.0` (≥2 pts of cancelled disagreement).
- **DL-2** Fabricated-evidence tripwire = awarded > 0 AND quote PRESENT with `validation_status == not_found`.
  Award-without-quote (evidence_quote None) is edit_burden + Tier-3 distribution, NOT the Tier-1 gate
  (the prompt violation is real but distinct from evidence fabrication).
- **DL-3** Wall-bound hit counts as retryable transport (the SUT has no timeout — G-3 — so a hang IS the
  transport failure mode); still exactly one re-run total per trial.
- **DL-4** v0 model seam absent (D6 deferred): config's `model_key` must RESOLVE to `settings.openai_model`
  or grade mode refuses — provenance may never claim a model the SUT didn't run.
- **DL-5** F0 id rename `q2.ב.c6 → q2.ג.c0` when the criterion moves (path-honest ids; GT is authored
  against the corrected ids) — explicitly in the H1 diff for the owner to accept or amend.
- **DL-6** Corrected draft drops the two stale `rubric_mismatch` WARNINGs + the two `point_sum_mismatch`
  pedagogical mistakes + the applied `structural_mislabel` (they describe the pre-fix state; keeping
  them would force fake acknowledgments at compile). In the H1 diff.
- **DL-7 (Phase B finding, surfaced not decided):** `q2.ג.c0` is a BRANCH criterion — its four
  sub-criteria are the actual terminals and retain the pre-move ids `q2.ב.c6.s0..s3` (DL-5 renamed
  only the criterion id, exactly as ratified). Internally consistent (universe = compiled contract;
  GT authors against these ids) — but the prefix lies about the path. Owner option BEFORE F5:
  re-stage with sub-ids `q2.ג.c0.s0..s3` + re-ratify (cheap now, expensive after GT lands).
  RULED 2026-08-24 (H1-A1): fix now — executed as a supersede; class closed by the path-honesty structural guard.
- **DL-8 (fence deviation, justified):** backend/.gitignore's broad `*.json` credential net silently
  dropped every fixture artifact from commit 3f675db; extended with suite-scoped un-ignores (the
  rubric suite's PR-4 precedent) + root `.gitattributes` `-text` pins so EOL normalization can never
  break the D5 sha256 guards on a fresh clone. Without this the ruling's "snapshots point at
  committed state" is unsatisfiable. Commits 3edbf15 + 624337f.
