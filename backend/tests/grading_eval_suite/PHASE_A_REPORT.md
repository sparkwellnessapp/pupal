# PHASE A REPORT — Grading Eval Suite v0 (instrument, zero spend)

**Date:** 2026-08-24 · **Gate:** external review (§1.6 reviewer) of this report.
**Also carries:** the B0 mechanical half of F0 — `H1_CORRECTION_PROPOSAL.md` is
STAGED and awaits the owner's H1 ratification [R5].
**Spend this phase: $0. Zero API calls. Zero files under `app/` touched.
Zero Gemini.** Only permitted out-of-suite edit: the eval_common dry-resolve
registration [§2].

---

## 1. Per-item DONE, with proofs

### A0 — Pre-flight census
Read before any file was touched: the mission; `DESIGN_CONTEXT_REPORT.md`
(authored earlier, §10 reading list re-verified); `REPORT_testgrader_state.md`
for the referenced findings (G-3 unbounded call → survived via wall bound;
G-15 unanchored protocol names → every ruling grep-able, see §3 below;
U2/G-21 multi-scope zero evidence → the baseline doubles as the smoke, stamped
in ONBOARDING §5); the SUT (`app/agents/grader/*`, `gradable_compiler`,
`selection_scoring`, `contract_compiler`, `graded_test_draft`, transcription
contract shape, `GoldAnswer` field names); the hobby GT's recorded
`structural_mislabel` fix steps; both sibling batteries' current baselines.

### A8-first — Failing tests before implementation (protocol)
All four guard files were written before `fixtures.py`/`scoring.py`/`runner.py`
existed. Red output (verbatim):
```
E   ModuleNotFoundError: No module named 'grading_eval_suite.fixtures'
ERROR tests/grading_eval_suite/test_gt_loader.py
ERROR tests/grading_eval_suite/test_runner_policy.py
ERROR tests/grading_eval_suite/test_scoring.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!
```
Then implementation; one legitimate test bug found and fixed on the way to
green (a glob in `test_good_trial_single_call_and_draft_persisted` also matched
`.meta.json` sidecars — assertion tightened, behavior unchanged).

### A1 — Skeleton + docs
`__init__.py` · `ONBOARDING.md` (map, run book, **seed-gap register**,
cross-suite integration) · `GRADING_EVAL_PLAYBOOK.md` (STOP list [§10], tier
table, validity taxonomy [§7], standing rules incl. worst-over-mean +
compensating-error + read-two-by-hand, operational definitions with grep tags)
· `GRADING_GT_CONVENTIONS.md` (schema, workflow, **C-1/C-2 OPEN for owner,
C-3/C-5 ratified-by-mission text, C-4 default `{55,65,75,85,95}` awaiting
confirm**) · `RUNLOG.md` seeded with the Phase-A CHANGE entry ·
`PREDICTIONS.md` seeded with **P1 verbatim** + P2 (pre-baseline) + P3 (judge
bar) + Tier-2 threshold placeholders.

### A2 — `schemas.py`
`FixtureGT`/`TerminalGT`/`ScopeUngradable` typed per §5 (incl.
`evidence_exists`, `ungradable`, the `gt_source` D10 hook) + `TerminalScore`/
`TrialScore`/`SuiteResult` (slots=True; Decimals as strings).

### A3 — `fixtures.py`
Per-fixture manifests [F3 — pairing law, no basename magic]; terminal universe
from the REAL `gradable_compiler.compile` (one definition); sha256 hash pins
[D5]; GT guards: totality-both-directions, duplicates, bounds, precision grid,
blind flag, ungradable-key existence [§5]; **R1 mechanics**: `require_gt`
refusal + `assert_blind_sequencing` (GT `authored_at` postdating any cached
draft for the fixture ⇒ refusal). Proofs: 8 loader-guard tests + 3 sequencing
tests green.

### A4 — `scoring.py` (pure; no agent import)
Tier-0 validity per §7 (transport ⇒ invalid; **parse ⇒ valid + scored [R6]**;
unknown class ⇒ transport, conservative). Tier-1: `[T1-FABRICATED]` [DL-2],
`[T1-CW]` (closed world + independent draft-terminal totality), `[T1-SKIP]`
(empty-answer guess + GT-ungradable unflagged award), `[T1-SELECTION]`
(denominator guard), `[T1-COST]`. Tier-2 per R4′/C-4/edit_burden/compensating
[DL-1]. Selection law: totals BOTH sides through the REAL
`score_with_selection`; GT-side excluded scopes never agreement errors;
fabrication still fires on excluded scopes (behavior over arithmetic);
`exclusion_mismatch` recorded. Proofs (each metric caught its injected error):

| Guard | Test | Verdict |
|---|---|---|
| Known-answer self-pass | `test_known_answer_self_pass` | PASS (MAE 0, rates 1.0, Tier-1 pass) |
| Fabricated quote | `test_fabricated_evidence_fails_tier1` | gate FAILS, offender named |
| Closed-world leak | `test_closed_world_leak_fails_tier1` | gate FAILS |
| Empty-answer guess + correct skip | `test_skip_agreement_on_empty_answer` | fails / passes respectively |
| Ungradable unflagged award | `test_gt_ungradable_scope_unflagged_guess_trips` | gate FAILS |
| Cost ceiling | `test_cost_ceiling_gates` | gate FAILS at $0.25 > $0.10 |
| Selection re-derivation | `test_selection_totals_never_rederive_denominator` | GT 13 / AI 14 / possible 15 (naive Σ=16 rejected); mismatch recorded; excluded terminal out of metrics |
| Compensating pair | `test_compensating_error_pair_flagged` | −2/+2 ⇒ total Δ=0, flag FIRES, burden=2 |
| Boundary flip | `test_boundary_flip_detected` | 58.3% vs 50% flips 55 |
| Burden-not-gate distinction | `test_edit_burden_counts_unverified_evidence` | no-quote award = burden, Tier-1 passes |
| Parse vs transport | `test_parse_failure_is_scored_transport_invalidates` | R6 scored / invalid respectively |
| Subset honesty | `test_subset_mode_suppresses_totals` | totals None, stamps set |

### A5 — `reporting.py`
Aggregates: worst-test (median |total Δ|) first; PROVISIONAL stamping (n<10
fixtures / k<5) with reasons; Tier-1 taxonomy; pooled Tier-2 rates; repeat
stability (per-terminal spread); calibration bins + ECE, n-flagged <50;
parse-failure rate with the **R6 escalation line rendered in summary.md**;
per-fixture blocks. Writers: `results.json` / `summary.md` (worst test first)
/ `report_<fixture>.md` (terminal table `gold|ai|Δ|quote|conf|flags|reasoning`,
reasoning pulled from the persisted drafts).

### A6 — `runner.py`
`grade` / `score_only` / `--scopes`; per-trial `asyncio.wait_for` 300 s;
**exactly one re-run**, transport-retryable only, wall counted as transport
hang [DL-3], parse never re-run [R6] — all proven by fake-agent tests
(`_HangingAgent` called exactly 2×; flaky-transport draft re-run once; parse
draft not re-run). Drafts + meta sidecars persisted as they arrive. [DL-4]
model-pin refusal proven both directions. Provenance: suite_hash (suite .py +
tools + benchmarks + fixtures + **shared registry** [D3]; configs excluded) —
`test_suite_hash_covers_registry_and_snapshots` pins the coverage;
model_key/registry_as_of/models block; `GRADING_PROMPT_VERSION`; k=1 stamped
PROVISIONAL. `build_agent` passes the CONTRACT's numeric policy (pinned by
`test_agent_factory_receives_contract_policy`).

### A7 — `configs/gpt-4o.json` + eval_common registration
Deployed pin [R7], `cost_ceiling: 0.10` [§6], notes = experiment record.
`tests/eval_common/test_models_registry.py::_config_model_keys` extended to
this suite's configs dir (same PR) — the offline dry-resolve gate now covers
all THREE suites.

### B0 — F0 mechanical half (staged, NOT ratified)
`tools/f0_hobby_correction.py` run:
```
[F0] original blocked: True
[F0] corrected compiles clean; total=100
[F0] proposal staged -> H1_CORRECTION_PROPOSAL.md
```
Also pinned as tests: original raises `CompilationError` naming q2; corrected
compiles with ב=29✓ (criteria sum 29), q2 subs 15+29+16=60✓, total 100✓,
ג carries `q2.ג.c0` @16 [DL-5], stale diagnostics dropped [DL-6]. The staged
snapshot sits in `benchmarks/contracts/_proposed/`; the ratified path is
untouched until the owner rules.

### B1/B4 — F1 converter + F4 skeleton (built + guarded; execution follows H1)
F1: converter built ON the sibling loader (strongest parity form) +
`test_converter_parity_on_all_five_docs` — **5/5 byte-identical**. F4:
skeleton pre-populates every terminal, judgments null (loader refuses partial
files = completion check). F2 `rebuild_fixtures.py` refuses to run before the
ratified contract exists [R5] and requires `--yes`.

---

## 2. Sanity gates [§11]

| Gate | Result |
|---|---|
| `python -c "import app.main"` | OK |
| `pytest --collect-only` (4 suites) | 221 tests collected |
| Suite battery | **44 passed** (+1 eval_common xfail = the pre-existing D5 sentinel) |
| Transcription battery | 134 passed / 1 skipped |
| Rubric battery | 33 passed / **8 failed = exactly the known Family-D charmap set**, verified by name |

**Sibling-delta attribution (mission said 133/1 and 31 passed):** the +1/+2
passing tests come from the 2026-08-24 gpt-5.6-terra/sol sweep session (its
edits: shared registry entries, rubric `test_llm_policy.py` terra/sol pins,
transcription `runner.py`) — **not from this diff**, whose only out-of-suite
edit is the eval_common registration. No test regressed anywhere.

## 3. Ruling traceability (the G-15 lesson) — grep proof

Every ruling has a textual anchor in code/docs: `R1` (fixtures.py, runner.py,
tests), `R2` (PLAYBOOK STOP 6-7, PREDICTIONS P3), `R3` (convert tool, GT
conventions), `R4'` (scoring.py within_precision/shippable), `R5/H1` (f0 tool,
proposal doc), `R6` (scoring classify + PLAYBOOK + summary escalation), `R7`
(config notes, PREDICTIONS P2), `P1` (PREDICTIONS verbatim), `D1..D10`, `DL-1..6`,
`T1-*`, `C-1..C-5`, `F0..F5`, `G-3/G-15/G-21/U2`, `§7/§9/§10` — all grep-able.

## 4. Adversarial self-review — items I would flag as your reviewer

1. **The R1 timestamp check trusts `authored_at` + run-dir names**, not git
   commit times. An owner who backdates `authored_at` defeats it. I judged
   git-log parsing over-engineering for a single-operator suite; the check
   catches the *accidental* violation (the realistic risk). Flagged, not fixed.
2. **`exclusion_mismatch` is Tier-3, not Tier-1.** Differing best-k winners is
   award disagreement upstream, not an arithmetic offense — but a reviewer
   could argue it deserves louder placement. The synthetic test documents the
   behavior either way.
3. **Skip-agreement passes when a GT-ungradable scope carries ANY flag.** A
   model that flags everything would never trip it; the guard is one-sided by
   design (it catches confident guessing, not over-flagging — over-flagging
   shows up in edit_burden/quote distribution instead).
4. **`contract_version` regenerates per compile**, so the ratified snapshot is
   frozen once and hash-pinned; `rebuild_fixtures` refuses to touch it, and
   `--ratify` refuses to overwrite an existing snapshot. The residual risk is a
   manual overwrite — accepted (guarded by D5 hash failures at load).
5. **Wall-bound re-run doubles worst-case wall time** (2×300 s per stuck trial,
   × k trials). Accepted for k=5 baseline scale; revisit if PR-7 doesn't land
   before larger sweeps.

## 5. What Phase B needs from the owner — the [STOP]s

1. **H1 ratification** — read `H1_CORRECTION_PROPOSAL.md` (diff incl. [DL-5]
   id rename + [DL-6] stale-diagnostic drop + compile proofs). On approval I run
   `--ratify`, then F2 snapshots + manifests.
2. **C-1 and C-2 rulings** (+ C-4 confirm/amend) in `GRADING_GT_CONVENTIONS.md`
   — before F5.
3. **F5: blind-grade the five tests** from the skeletons [R1] (~120–150
   judgments), stamping `authored_at` at completion.
4. Note for your F2 awareness: the terra/sol session left `din_ezra.md` and
   `yonatan_basiuk.md` draft-GTs **modified in the working tree**; the F2
   snapshot will freeze their current state. Confirm that is the intended
   version when ratifying.
