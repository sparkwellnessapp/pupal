# PLAN COMPILER v2 — implementation record

**Governs:** `PR_plan_compiler_v2.md` (RATIFIED 2026-09-05). This is the engineering record beneath
it: what the research found, what the PR does not settle, and the decisions surfaced.
**Status:** IMPLEMENTING · phase order §5 · tracker `TRACKER_plan_compiler_v2.md`.

---

## 1. Deutsch form

**Data.** Across two exams, the plan's algebra — terminals, points, tariffs, notes, `counted`,
reconciliation, enumerated splits — is a deterministic function of contract text. The Opus
decomposer's measured failures (no `counted`, Case 4 ignored, Q6 under-decomposed, 7/13 scopes
exhausting repairs on V1 arithmetic) are rule-holding and arithmetic failures.

**Theory under criticism.** *"Decomposition is a language task, so an LLM does it."* Falsified: the
LLM failed exactly the parts that are not language.

**Conjecture.** Compile the algebra; segment the language. Stages 0/1/3 pure; Stage 2 stochastic in
text only; two compilations of one contract yield byte-identical algebra.

**Criticism.** Hard to vary? The split is forced by what failed. New contradictions? Three the PR
leaves open (§4) — each surfaced, each with a recommendation, none silently taken.

## 2. What research found that the PR assumes otherwise

| # | PR assumes | Found | Consequence |
|---|---|---|---|
| F-1 | `counted` "reportedly exists in the pricer" | **Absent everywhere** — schema, validator, composer, pricer, verdict, verifier, expressibility, `Check` wire | C3 needs the kind end-to-end (§3.2) |
| F-2 | R-2 zeros landed with `authored_at` | `authored_at` stamped 2026-09-03; **nulls remain** (15–22/file); R-3 amendments HAVE landed (itay 2, din 5) | A0 reads GT through a selection-aware reader, not the loader (§3.3); no schema change |
| F-3 | A0 hobby bar ≥189/190 compiler-only | 5 hobby awards sit on C7-routed terminals and are unreachable with one check (dan q1.א.c1 3.5 & q2.א.c1 9; din q1.א.c1 3, q2.א.c0 4, q2.א.c1 8) + yonatan's ruling tariff → **≈184/190 before A2** | OD-13 |
| F-4 | C7 routes hobby 4 / bagrut 7 | Measured: hobby 4 **+ q2.ב.c3.s3** (single required + tariff, P=5); bagrut: **q2.ב.c3 is NOT a monolith** (C4 explicit values 0.5/2/1/1), **q1.ב.1.c0, q6.c5 ARE** (one value == P, degenerate) | OD-14 — reported as the PR instructs |
| F-5 | C1 «לקנוס» has an amount | q4.ב.c4's «לקנוס פעם אחת אם לא בדקו…null» names **no number**; the diagnosis read it as the null-check component's own 1 | OD-15 |
| F-6 | separator heuristics on prose | criterion text carries C# tails (`j++`, `for (...)`) — a naive `+`/`.` split misfires | C4 parses the prose prefix, ignoring code spans |
| F-7 | R-E Case 3 documented | only in my skeleton tool's notes; reconstructed and **verified against both references** with the STRICT reading (§3.4) | — |
| F-8 | verifier prompt unchanged | `counted` needs the verifier to emit `units_correct`; `VERIFIER_PROMPT_VERSION = grader-v5.3` is the production pin | OD-18 |

## 3. Design, per component

### 3.1 Package
`app/agents/plan_compiler/` — `skeleton.py` (types), `compile.py` (Stage 1, C1–C7), `assemble.py`
(Stage 3), `segment.py` (Stage 2, A1), `route.py` (Stage 2b, A2). **Kept as compiler components:**
`plan_gen.prompt.detect_deductions` (+ `לקנוס`/`קנס`), `scope_corpus`, `plan_gen.generator.
contract_scopes`/`terminals_of`, the validator V1–V11. **Retired (R-4):** `PlanGenerator`, the
repair loop, `dispositions.py`, `plan-gen/v2`'s prompt; V11 becomes a Stage-3 assertion.

### 3.2 The `counted` kind (C3 / R-E Case 1)
- `PlanCheck.kind += "counted"`, `unit_count: Optional[int]`; a counted check is the **only** check
  on its terminal and carries `points == points_possible` (V1 holds; new **V12**: alone, `unit_count
  ≥ 2`, no tariff/group, `partial_fraction` untouched).
- `CheckVerdict.units_correct: Optional[int]` (decoded after `verdict`); `AssessedVerdict` carries
  it; consensus rides the median-verdict vote.
- Pricing (the ONE composer): `earned += points × units_correct / unit_count`, grid-snapped by the
  existing terminal snap (`12 × 15/17 → 10.5` on 0.25). `met` ⇒ N, `not_met` ⇒ 0; `partially_met`
  without a count ⇒ 0 + `COUNT_MISSING`. Evidence gating as for `required`.
- Expressibility: reachable = {snap(P·k/N) : 0 ≤ k ≤ N}.
- `Check` wire gains `unit_count`/`units_correct` (additive). **TS mirror owed** (OD-17).

### 3.3 R-2 companion guard — selection from the transcription
`unattempted_scope_keys(bundle)`: a question in a selection group whose **every** leaf scope has
empty `student_answer_text`. Hobby (no groups) has none by construction — an empty answer there is
a real skip the grader must match. `TerminalScore.unattempted` (additive); **per-terminal**
exclusion (Tier-2, K1's denominator via `gates._included_rows`, calibration) keys on
`unattempted ∨ ungradable`; **totals** keep best-k `excluded_by_selection`. The two sets coincide
for every current fixture (all seven attempted exactly 4) and diverge only for a 5-attempt student,
which is exactly the case R-2 forbids conflating. A0's GT reader yields judgments on attempted
scopes only and refuses a null on an attempted one.

### 3.4 Case 3, verified (q4.ב.c4 → 1,2,1,1 · q4.ב.c7 → 0.5,0.5,2,1,1)
1. Whole-point absorption, classes descending, members in textual order, a member may drop only
   while it stays **strictly above** the next lower class (`v−1 > next`); repeat while over ≥ 1.
2. Residual: the largest class that can take it; within it the **fewest** members in textual order,
   evenly, each staying on-grid, > 0 and strictly above the next class. Flag.
The non-strict reading (`≥`) merges classes and yields 1,1,1,1,1 — falsified by reference 2.

### 3.5 Stage 3 provenance
`GradingPlan` gains optional `compiler_version`, `segmenter_prompt_version`, `segmenter_model`,
`router_model` (additive; the hand plan re-parses). `plan_version` = `<exam>/compiled-<sha256[:12]>`.
Committed append-only under `tests/grading_eval_suite/plans/compiled/`.

## 4. Open decisions surfaced (continue on everything else)

- **OD-13 · A0 and routed terminals.** A0 cannot reach ≥189/190 on hobby before A2 (F-3).
  *Recommend:* A0 reports **routed-class** misses as their own class beside granularity, and the bar
  applies to non-routed terminals; A2 closes the class. Alternative: run A0 after A2 (spends first).
- **OD-14 · what is a monolith for C7.** *Recommend:* a terminal whose C4 result is exactly one
  component — including a single stated value equal to P, and regardless of tariffs on it — routes.
  Yields hobby 5 (+q2.ב.c3.s3), bagrut q1.ב.1.c0 + q6.c5 in, q2.ב.c3 out. Without this q6.c5 is a
  guaranteed decomposition-class A0 failure.
- **OD-15 · amountless «לקנוס».** *Recommend:* amount = the stated points of the component whose
  clause carries the phrase (q4.ב.c4 → 1, the reading the diagnosis used), flagged.
- **OD-16 · hobby byte-identity baseline.** `unattempted` is an additive row field; the published
  baseline predates it. *Taken:* the guard normalises the baseline forward (adds the default), never
  the other way. Recorded in the test.
- **OD-17 · `counted` in the frontend pricing mirror** — production-wiring boundary, out of §9's
  fence. Owed to F-phase; `pricing_vectors.json` unaffected (no fixture carries a counted check).
- **OD-18 · verifier prompt version under `counted`.** The counted instruction renders in the
  per-scope user message only when such a check exists; `VERIFIER_PROMPT_VERSION` stays v5.3.
  *Needs a ruling before A3* — a v5.3 stamp on a counted-bearing message is a version fork.

- **OD-19 · per-terminal denominators under R-2.** `unattempted` (transcription-derived) is the only
  per-terminal exclusion; best-k `excluded_by_selection` stays a totals fact. The old pin dropped an
  ATTEMPTED best-k loser from MAE; amended (`test_selection_totals_never_rederive_denominator`). Live
  delta zero on both exams.
- **OD-20 · «- N נק'» value vs tariff.** A dash-number hit with no deduction verb in its clause is the
  component's value (q1.ב.2.c0). Flagged `tariff_reclassified_as_value`.
- **OD-21 · fold.** amount == the modified component's own (stated) value ∧ not charge-once ⇒ no slot.
  Calibrated on the hand plan (q1.ב.c6, q1.ג.c6/c7); folds bagrut q5.א.c0, q6.c0.
- **OD-22 · OD-9's unit.** 2×grid, or V4 refuses. 5/3 → 2/1.5/1.5. Refused splits keep one check, flagged.
- **OD-23 · OD-10's anchor.** First child that can CARRY the amount (V3) — s3 for hobby q2.ב.c4, the
  hand plan's anchor.
- **OD-24 · OD-11's threshold.** *Recommend* P ≥ 3: closes the seven bagrut decomposition-class misses
  (q3.ב.c5/c6) as routed-class and would let A2 reproduce hobby's q1.ב.c2/c4 hand splits. Reported as a
  counterfactual in `A0_REPORT.md`; the compiled artefacts use the ratified 4.

## 5. Phase order
P1 algebra (`counted`) · P2 R-2 guard · P3 Stage 1 compiler (C1–C7, calibrated on the hand plan —
legitimate per PLAYBOOK §270) · P4 Stage 3 + A0 driver + `A0_REPORT.md` · P5 retire the generator ·
P6 segmenter/router (A1/A2, spend-gated) · hold before A3. Each phase: tests, then review.
