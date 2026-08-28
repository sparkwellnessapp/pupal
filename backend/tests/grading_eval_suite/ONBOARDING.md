# ONBOARDING — Grading Eval Suite

**Read in order:** `MISSION_grading_eval_suite_v0.md` (the ratified constitution)
→ `GRADING_EVAL_PLAYBOOK.md` (STOP list + analysis contract) → this map →
`RUNLOG.md` (every iteration starts by reading it). GT authors also read
`GRADING_GT_CONVENTIONS.md`. Background: `DESIGN_CONTEXT_REPORT.md`.

## 1. What this suite measures

The GraderAgent's grading judgment against blind teacher grades:
`(GradingRubricContract, TranscriptionContract) → real GraderAgent → real
validator → real selection_scoring → scored vs typed GT`. The LLM call is the
only nondeterministic stage; the pure surround is production code exercised
as-is (never reimplemented) and separately pinned by zero-mock batteries.
**Explicitly absent:** e2e-from-PDF — perception is the transcription suite's
jurisdiction; coupling them recreates the attribution problem the two-phase
architecture exists to prevent [§3].

## 2. Map

```
grading_eval_suite/
  MISSION_grading_eval_suite_v0.md   the ratified spec (wins over everything here)
  GRADING_EVAL_PLAYBOOK.md           STOP list, tiers, validity taxonomy, definitions
  GRADING_GT_CONVENTIONS.md          GT authoring rules; C-1..C-5 owner rulings
  RUNLOG.md / PREDICTIONS.md         hard memory / pre-registered predictions
  TRACKER_v0.md                      per-item implementation tracker + decision log
  H1_CORRECTION_PROPOSAL.md          the staged F0 correction awaiting owner ratification
  schemas.py                         FixtureGT (typed GT) + TrialScore (results row)
  fixtures.py                        manifests, hashes [D5], GT guards [§5], R1 sequencing
  scoring.py                         THE scorer (pure; tier tripwires; grep the [T1-*]/[DL-*] tags)
  reporting.py                       aggregates (worst-test first) + results/summary/reports
  runner.py                          grade | score_only | --scopes; wall+one-rerun [D7]
  configs/gpt-4o.json                the deployed pin [R7]; model_key + ceiling only
  tools/f0_hobby_correction.py       F0: correction proposal + H1 ratification
  tools/convert_transcription_gt.py  F1: sibling draft-GT -> TranscriptionContract
  tools/rebuild_fixtures.py          F2: deliberate snapshot/manifest regeneration
  tools/build_gt_skeleton.py         F4: GT skeleton, terminals pre-populated
  fixtures/<name>.json               per-fixture manifest — THE pairing law [F3]
  benchmarks/contracts|transcriptions|gt/   frozen snapshots + GT (hash-pinned)
  results/<ts>_<config>/             results.json + summary.md + report_<fixture>.md + drafts/
  test_*.py                          instrument guards (zero API calls; run in pytest -q)
```

## 3. How to run

From `vivi-codebase/backend/` (module mode; suite imports are package-relative):

```bash
# authoritative baseline (spends ~$1): k=5 over all fixture manifests
python -m tests.grading_eval_suite.runner --config gpt-4o --mode grade -k 5

# diagnostic: one fixture, one scope, one trial (PROVISIONAL everywhere)
python -m tests.grading_eval_suite.runner --mode grade --fixtures dan_basiuk -k 1 --scopes "q2.א"

# $0 instrument iteration: re-score a cached run
python -m tests.grading_eval_suite.runner --mode score_only --score-run tests/grading_eval_suite/results/<run>

# guards (zero API calls)
python -m pytest tests/grading_eval_suite -q
```

Prerequisites for `grade`: `OPENAI_API_KEY` in `backend/.env`; the config's
`model_key` must resolve to the SUT's live `settings.openai_model` pin (v0 has
no model seam — D6 deferred; mismatch refuses before any spend [DL-4]).
**Grade mode is refused for any fixture without committed blind GT [R1].**

## 4. The fixture pipeline (Phase B) — state

DONE (2026-08-24): sibling GT edits committed (6337fbc) → H1 RATIFIED
(`benchmarks/contracts/hobby_tvshow_corrected.contract.json` + provenance) →
F2 snapshots + F3 manifests written → C-1..C-5 ruled/confirmed → F4 skeletons
emitted (`benchmarks/gt/<name>.gt.skeleton.json`).
**Current [STOP]: F5 — owner blind-grades the 5 tests from the skeletons [R1]**
(fill judgments only; stamp `authored_at`; delete `_instructions`; save as
`benchmarks/gt/<name>.gt.json`). Phase C then waits on P2 (pre-baseline
prediction in PREDICTIONS.md).

## 5. Registered seed-set gaps — so nobody mistakes n=5-one-exam for generalization

| Gap | Consequence | First expansion |
|---|---|---|
| ONE exam (hobby_tvshow corrected), n=5 students | every rate PROVISIONAL; exam-specific quirks invisible | `employee_course_select1` transcription (also closes the next gap) |
| No selection-group exam | best-k/exclusion path live only in synthetic guards | same as above |
| No depth-2 nested rubric | `parent_answer_fallback` path unexercised in real runs | a bagrut-style nested fixture |
| No fluent-but-wrong answer | over-award blind spot | targeted authoring |
| No all-blank test | mass-skip behavior unexercised | cheap to add |
| **No tabular answer** (finding, 2026-08-26) | **C-1's ratified table-interpretation clause ships UNTESTED** — this exam contains no tabular answers, so the `[C1-TABLE]` path has zero corpus coverage | fixture expansion must deliberately include a **trace-table answer** |
| **No illegible scope** (finding, 2026-08-26) | **C-2's ratified `ungradable` path ships UNTESTED** — `ungradable_scopes` is empty in all five GTs, so the reason vocabulary, the totals-only participation, and the Tier-1 ungradable tripwire have zero corpus coverage (synthetic guards only) | fixture expansion must deliberately include one **genuinely illegible scope** |

Gate ratification (Tier-2 thresholds) requires **n>=10 across >=2 exams**.
The k=5 baseline doubles as the **multi-scope smoke** (state-report U2/G-21:
multi-scope grading has zero production evidence — say so in the baseline report).

## 5b. H1-A2 provenance note (2026-08-25)

From H1-A2 onward, compiled scopes carry the teacher's RATIFIED MODEL SOLUTIONS
(source artifact: `benchmarks/contracts/_sources/model_solutions_transcription.md`)
— the baseline measures the grader **with the EXAMPLE SOLUTION section
rendered** (production-realistic; referent and SUT symmetric). E4/prior_parts
unaffected — the flag stays off for the baseline.

## 6. Design inputs for step 3 (recorded, NOT v0 gates)

- **[C-1 model-side expectation, ratified 2026-08-24]:** the grader is expected
  to interpret confidently-reconstructible garbled tables and surface a
  teacher-facing note explaining the interpretation. Evidence quotes remain
  verbatim from the transcription — interpretation lives in reasoning — so
  T1-FABRICATED is unaffected. A dedicated FlagReason for degraded-input
  interpretation is a step-3 grader-design item; v0 measures table-terminal
  agreement through ordinary Tier-2, which is exactly what tells us whether the
  current grader under-interprets tables. No new gate exists for this.
- D6 model/params seam (incl. `reasoning_effort`) · `GRADER_VERSION` constant ·
  `_compute_cost` stale prices — all step-3, per the mission scope fence.

## 7. Cross-suite integration

Model identity/prices: `tests/eval_common/models_registry.py` (`model_key` is
the cross-suite join key; this suite's configs are covered by eval_common's
offline dry-resolve test). Cost: the ONE shared `cost_usd`. Sibling GT is read
+ snapshotted only — never edited [§2].

## Mission era: grader-v5 closed loop (2026-08-28 →)

`MISSION_grader_v5_closed_loop.md` governs. The suite now drives TWO
architectures through one runner: `architecture: "v3"` (GraderAgent,
points-emitting) and `"v5"` (PlanVerifyGrader — Plan/Verify/Price: the model
emits verdicts per plan check, `app/agents/grader/pricer.py` computes every
point). Start with: the mission file → `GRADING_EVAL_PLAYBOOK.md` §0/§1b →
`K2_FORENSICS.md` → `plans/hobby_tvshow_plan_review.md` (the H-4 artifact).
Every run's analysis starts with `python -m tests.grading_eval_suite.tools.gates
<results_dir>` — kills first. Google entrants RUN (owner reversal 2026-08-28;
Vertex adapter with `vivi-workload: grading-eval` billing labels); xAI is
excluded by default. Spend honesty: `COST_TRUTH.md`.
