# GRADING_EVAL_PLAYBOOK — the analysis contract

**Governs every run and every analysis of this suite.** The mission
(`MISSION_grading_eval_suite_v0.md`) is the constitution; this file is the
operating manual. Where they disagree, the mission wins.

---

## 0. THE STOP LIST — never do these; halt and surface to the owner [§10]

1. **No GT edits to pass.** Ground truth is owner-authored, blind [R1]. A suspected
   GT error is surfaced with evidence — never "fixed" to make a number move.
2. **No scorer edits to pass.** `scoring.py`, the loader guards, the Tier-1
   tripwires and their operational definitions are the instrument. Answering a
   grading question with an instrument change is forbidden (the §17.7 discipline;
   same failure class as loosening an invariant).
3. **No threshold moves without pre-registration.** Tier-2/3 are UNGATED-WATCHED
   until thresholds are pre-registered in PREDICTIONS.md from a measured
   distribution (the INV-6/A4 lesson: a check nobody can pass trains click-through).
4. **No model or tier escalation without the owner** — *amended 2026-08-28 by
   `MISSION_grader_v5_closed_loop` (the mission wins):* the §3 roster and its
   params (reasoning_effort, SC-3) are owner-RATIFIED and run without per-trial
   approval; anything beyond the roster stays an owner decision.
5. **No production code changes** — *amended 2026-08-28 by the same mission:*
   V5-A's grader-path scope (the D6 seam, the Plan/Verify/Price modules, the
   additive draft-schema fields, the grader-v3 restore) is ratified app/ work,
   recorded in the mission-start RUNLOG entry and pinned by `sut_hash`.
   Everything else under `app/` stays frozen.
6. **No Gemini, anywhere in this suite** — *WITHDRAWN by owner ruling
   2026-08-28 (second amendment; supersedes the same-day skip):* the isolation
   condition is withdrawn — DSQ headroom dwarfs three months of launch volume,
   so eval traffic on the production Vertex project is immaterial. Google
   entrants run via `llm_factory`'s google-genai/Vertex adapter, and every
   call carries the `vivi-workload: grading-eval` request label so the
   COST_TRUTH reconciliation can split eval spend from production in the GCP
   billing view (Vertex has no per-key split).
7. **The judge never gates and is never the scorer-of-record** [R2]. Promotion to
   any gating role has a pre-registered bar (n>=50 Tier-A fixtures AND judge-owner
   agreement >= the bootstrap bar).

## 1. Tiers [mission §6]

| Tier | What | Status |
|---|---|---|
| 0 Validity | transport failure / wall-bound hit => INVALID trial (excluded, counted); provenance completeness | precondition for reading anything |
| 1 Tripwires | `[T1-FABRICATED]` zero positive awards on ABSENT ink · `[T1-STITCHED]` zero positive awards on real-but-NON-CONTIGUOUS ink presented as one span · `[T1-CW]` zero closed-world survivals (+ draft-terminal totality) · `[T1-SKIP]` skip-agreement on empty answers and GT-`ungradable` scopes · `[T1-SELECTION]` denominator is contract.total_points, exclusion honored by construction · `[T1-COST]` registry-priced cost/trial <= ceiling ($0.10 default) | **GATE from run one** |
| 2 Agreement | signed Δ, MAE, `terminal_within_precision_rate` (precision=0.25 [R4']), exact rate, `total_Δ`, `shippable_grade_rate` (<=1.0 [R4']), `grade_boundary_flip_rate` [C-4], `edit_burden` | **UNGATED-WATCHED**, except the GA-gated subset below |
| 3 Diagnostics | repeat stability (award spread across k), calibration (reliability + ECE, n-flagged <50), parse-failure rate [R6], `parent_answer_fallback` rate, quote-status distribution, per-scope cost & latency, exclusion mismatch | reported every run |

### 1b. The grader-v5 mission era (2026-08-28): kills and GA gates

`MISSION_grader_v5_closed_loop` §1.1/§2 promoted a subset to GATES for the
closed loop, evaluated by `tools/gates.py` (mechanized — hand arithmetic has
erred twice) FIRST in every analysis, before any headline number:

- **Kills (per trial):** K1 = GA-1 (any GT-ZERO→AI-nonzero kills the config
  permanently) · K2 GT-PARTIAL→AI-FULL ≤ the C2 baseline 2.4% (6/245) ·
  K4 max per-fixture `ai_total_spread` ≤ 8.25.
- **GA gates (adoption = all green on k=5):** GA-1 100% · GA-2 within-precision
  ≥0.85 · GA-3 STRICT shippable (|Δ|≤1 AND no compensating_error) ≥0.50 ·
  GA-4 boundary-flip ≤0.10 · GA-5 max spread ≤3.0 · GA-6 edit_burden ≤4
  median /≤8 max · GA-7 ≤$0.08/test hard, $0.05 target.
- k=3 runs are stamped SCREENING in provenance and never justify adoption.
- The expressibility guard (H-4 item 3) is permanent: every fixture GT award
  must be reachable under the plan algebra — `plan_expressibility.py`, wired
  into `_load_plan` pre-spend and the standing pytest.
- COST_TRUTH (H-4 item 4) governs spend honesty: registry unit test ·
  per-trial served-model truth-check · per-day ledger (`tools/cost_truth.py`)
  diffed against provider dashboards after each Stage — protocol in
  `COST_TRUTH.md`.
- **grader-v5 evidence semantics:** declared multi-span citations
  (`evidence_quotes`) validate PER SPAN; separate spans over non-adjacent ink
  are the honest citation (never T1-STITCHED); an `evidence_unverified`
  refusal (met claimed on an unverifiable span — the pricer refused credit)
  still GATES, classified fabricated/stitched by the DL-2 fragments signal.
  The bar is thus STRICTER than v3: zero met-claims on absent ink, award or no
  award.

## 2. Validity taxonomy [mission §7]

- **Transport failure** (openai transport classes in a failed scope's
  `llm_failure` annotation) => trial INVALID. One re-run per trial [D7].
- **Wall-bound hit** (300 s default; the SUT has no timeout — G-3) => counts as a
  transport hang [DL-3]: one re-run; a second hit => INVALID.
- **Parse failure** (`ValueError` from `parsing_error` at temp 0) => trial VALID,
  scored exactly as production would show it (zero awards, flagged scope) [R6].
  Deterministic model behavior — NEVER re-run. Tier-3 headline; **escalation:
  rate > 0 => bucket the affected fixtures before ANY model comparison** (a
  deterministic per-input failure confounds sweeps).
- `skipped_no_answer` is a grading FACT, scored against GT.
- Unknown failure class => transport (conservative: invalidate, never silently score).

## 3. Standing analysis rules [mission §6]

- **Worst-test over mean, always.** The summary names the worst test first; the
  analysis starts there.
- **`compensating_error`** is flagged whenever the total looks shippable while
  terminal disagreement is large — total-level agreement is NEVER trusted alone.
  Operational definition [DL-1, PROVISIONAL until revisited with baseline data]:
  `|total_Δ| <= 1.0 AND (Σ|terminal Δ| − |total_Δ|) >= 2.0`.
- **A shippable trial that also fires `compensating_error` is reported as
  CANCELLATION, never as a pass** [owner ruling 2026-08-27]. `shippable_grade_rate`
  is not evidence of terminal correctness; **`edit_burden` is the honest cost
  metric**. (E7: all four "first ever" shippable trials were one fixture and all
  four were compensating — total_Δ 0.00 on 3.00 points of cancelled terminal error.)
- **Instability is reported in BOTH measures, every run** [owner ruling
  2026-08-27]: how MANY terminals move across k, and how FAR the per-test total
  moves (`max_ai_total_spread`). Never one alone — E7's terminal-count measure
  improved 37.4%→30.0% while dan's per-test spread went 3.25→14.00, crossing two
  grade boundaries on identical input.
- **Read at least two per-fixture terminal tables by hand every run**
  (`report_<fixture>.md` exists for exactly this).
- **n<10 fixtures => every rate is PROVISIONAL and stamped so.** The seed set is
  n=5, ONE exam — see the ONBOARDING gap register. Gate ratification needs n>=10
  across >=2 exams.
- **k=1 is PROVISIONAL in every artifact it touches** [§3]. Authoritative = k>=5.
- One variable per run; kill criterion pre-registered in PREDICTIONS.md before
  spend; RUNLOG entry after every run and every variable change.
- **The analysis is DONE only when** the above hold **…and §R is complete, with
  its bucket counts and R.3 tables in the report body.**

## 4. Operational definitions the scorer implements (grep the tags in scoring.py)

- **[DL-2, SPLIT by owner ruling 2026-08-27]** awarded > 0 AND a quote is PRESENT
  with `validation_status == not_found` is **two different defects**, and the
  classification signal is *whether the quote's constituent fragments exist
  VERBATIM in the answer*:
  - **`[T1-FABRICATED]` evidence_fabricated** — cited ink is ABSENT. Trust catastrophe.
  - **`[T1-STITCHED]` evidence_stitched** — the ink is REAL but non-contiguous,
    misrepresented as a single span. A citation defect: it breaks span-highlighting
    in the review UI and shows a teacher a broken citation.
  **Both gate Tier-1.** The 0.85 fuzzy bar is NOT touched by the split — 0.837 is
  exactly what mostly-real stitched text *should* score, and moving a threshold so
  a case passes is the rejected Policy-1 pattern. The scorer re-LABELS an
  already-failed quote; it never re-scores one.
  Award-without-any-quote remains `burden_evidence` (edit_burden + Tier-3
  distribution), NOT a gate: a prompt violation, but not a citation defect.
  *Step-3 design input (do NOT build): the structural fix is likely allowing the
  model to return MULTIPLE quote spans rather than forcing one.*
- **[T1-SKIP] ungradable-guess**: on a GT-`ungradable` scope [C-2], a positive
  award with ZERO flags anywhere in the scope. A flagged or skipped outcome is
  the correct review-first behavior and passes.
- **[C-2, ratified 2026-08-24] ungradable-scope terminals**: reason vocabulary
  `illegible | ambiguous_student_intent | missing_content | garbled_structure`.
  The owner's best-guess `awarded` participates ONLY in totals (via
  `score_with_selection`); excluded from ALL Tier-2 agreement metrics (MAE,
  within-precision, exact, edit_burden, compensating-error input) AND from the
  calibration input (correctness vs a best-guess GT is noise by construction —
  the exclusion logic extends to it; RATIFIED 2026-08-24, reviewer verdict +
  owner approval — Phase-B ruling D3). Fixtures carrying them are marked
  "total includes N ungradable-scope terminals" in their report block.
- **[C-1, ratified 2026-08-24] table exception**: GT may award per confidently-
  reconstructed intent on structurally garbled tabular content; such terminals
  carry a `[C1-TABLE]` note (displayed in the fixture report; counted per
  fixture in Tier-3). Not confidently reconstructible => C-2 `garbled_structure`.
- **[C-4] boundary flip**: gt_pct and ai_pct on opposite sides of any boundary in
  `{55, 65, 75, 85, 95}` (CONFIRMED as defaulted, 2026-08-24); pass convention
  `>= b` passes ("pass line 55 certain").
- **`edit_burden`** per test = count(terminal |Δ| > precision) + count(positive
  award on unverified evidence). The teacher's expected correction workload.
- **Selection**: totals on BOTH sides through the REAL `score_with_selection`;
  denominator = `contract.total_points`, never re-derived; GT-side excluded
  scopes never count as agreement errors; fabrication still fires on excluded
  scopes (behavior, not arithmetic); differing GT/AI exclusion sets =>
  `exclusion_mismatch` (Tier-3 — it is award disagreement upstream, not a gate).

## 5. Modes and their honesty labels [mission §3]

- `grade` — authoritative at k>=5. The only mode that spends money.
- `score_only` — $0 re-score of cached drafts; the mode for ALL instrument
  debugging. R1 checks still apply.
- `--scopes` — diagnostic subset: totals suppressed, PROVISIONAL stamped.
- The judge [§8] is a SEPARATE offline pass (Phase D); never inline with grading.

## R. The qualitative read (MANDATORY, gating)

> Inserted 2026-08-27 by owner ruling, verbatim. This is a **gate**, not an appendix:
> a run analysis is NOT done until §R is complete and its findings appear in the report body.

---

### R.0 Why this exists

The transcription suite's standing rule — *read at least two diffs by hand every run; the failure nobody
anticipated shows up in the diff before it shows up in a metric* — applies here with **greater** force,
for a reason specific to grading.

In transcription, ground truth is **fact**: ink either says `Mobby` or it doesn't, and a scorer that
computes the ratio correctly has extracted essentially everything the artifact contains. In grading,
ground truth is **judgment**, and the artifact carries three layers a number cannot see:

1. **the award** — the only layer the scorer reads;
2. **the reasoning** — whether the award was reached for a defensible cause;
3. **the evidence quote** — whether the cited ink actually supports the reasoning.

A grader can be right in layer 1 and catastrophically wrong in layers 2-3 (the *right-for-wrong-reason*
failure), and no Tier-1/2/3 metric in this suite will fire. Conversely, a systematic *interpretive*
error — one that a single prompt sentence would fix — appears in the metrics only as diffuse
non-actionable harshness, and is identifiable **only** by reading what the model wrote.

**The baseline proved this empirically.** The scorer said: harsh, MAE 0.34, worst test din. Reading the
distribution and the per-terminal reasoning said: *the grader shaves ~0.5 points off answers the teacher
called complete, 258 times, for 68.7% of all harshness* — a different defect with a different fix. The
numbers were correct and the mechanism read off them was wrong.

### R.1 The protocol — minimum per run

Per fixture, the analyst opens `report_<fixture>.md` and reads the **full terminal table**: `gold | ai |
Δ | quote_status | confidence | flags | reasoning`. Not the summary. Not the aggregates. The text.

**Mandatory reads (all five, every run):**

| # | Selection rule | What it is for |
|---|---|---|
| R-1 | The **worst test's** worst scope, all k trials | The dominant failure, and whether it is stable or stochastic |
| R-2 | The **best-agreement** fixture's disagreements | Distinguishes "grader is fine, GT is arguable" from real error |
| R-3 | **Three terminals where AI == GT exactly**, sampled across fixtures | The right-for-wrong-reason audit. Agreement is not evidence of soundness; only the reasoning is |
| R-4 | Every **Tier-1 violation**, in full, with surrounding scope | A tripwire tells you *that*; only the text tells you *why* |
| R-5 | The **highest-|Δ| terminal at confidence >= 0.9** | Confident error is the most dangerous class for a teacher-facing product |
| R-6 | Any terminal on the **instability list** whose award spread >= 1.0, across all k | Separates genuine ambiguity from prompt underspecification |

**Additional reads triggered by conditions:**
- any `quote_status = not_found` or `fuzzy` carrying a positive award — read the quote against the answer text;
- any scope zeroed in full — read every terminal in it (a zeroed scope is a *decision*, and the reasoning states it);
- any fixture whose `mean signed Δ` sign differs from the corpus — read two of its terminals;
- any `[C1-TABLE]` or `ungradable_scopes` terminal — these rulings are otherwise untested (registered corpus gap).

### R.2 What the analyst is looking for — the taxonomy

Every disagreement read by hand gets classified into exactly one bucket, and **the counts go in the report**:

| Bucket | Definition | Implication |
|---|---|---|
| `rubric_underdetermined` | Rubric text genuinely admits both awards | → constitution ruling (§13), not a grader fix |
| `interpretive_divergence` | Grader applied a consistent standard the teacher does not hold (e.g. charging syntax the teacher treats as ink) | → **prompt-level fix**; the highest-value bucket |
| `evidence_miss` | The supporting ink exists; the grader did not find it | → retrieval/attention problem |
| `evidence_fabricated` | Cited quote is not in the answer | → Tier-1; trust-critical |
| `right_award_wrong_reason` | Award matches GT; reasoning does not support it | → invisible to every metric; only R-3 finds it |
| `reasoning_incoherent` *(sub-bucket, added 2026-08-27)* | Award **and** deduction cause both match GT, but the reasoning is internally contradictory (asserts P and ¬P). Distinct from `right_award_wrong_reason`, where the cause diverges | → the number is right; the artifact a teacher reads is not. **Phase-D J2 exemplar.** Exemplar: `moran/q2.ג.c0.s3` (C2 baseline) |
| `gt_questionable` | Reading the text, the teacher's own award looks arguable | → GT amendment candidate, ratified by owner only |
| `transcription_artifact` | Disagreement traces to garbled transcription, not grading | → upstream, not this suite's fix |

### R.3 The distribution read (do this before the fixture reads)

Numbers alone under-determine mechanism. Before reading text, compute and state:

- **Partial-credit cross-tab**: GT ∈ {ZERO, PARTIAL, FULL} × AI ∈ {ZERO, PARTIAL, FULL}. This single
  table distinguishes *nitpicking* (GT=FULL → AI=PARTIAL) from *annihilation* (GT=PARTIAL → AI=ZERO)
  from *over-credit* (GT=ZERO → AI>0). Report it every run.
- **Harshness concentration**: what share of total signed Δ comes from the top 3 terminals, and from
  the single worst scope. Diffuse ≠ concentrated, and they have different fixes.
- **Confidence as a ranking signal**, separate from ECE: within-precision rate per confidence band, and
  the error captured by flagging `confidence < 1.0`. Absolute miscalibration and rank-usefulness are
  different properties, and a product can use the second without the first.

### R.4 Report contract

The run report must contain a **§Qualitative read** section with: the six mandatory reads named and
summarized (2-4 sentences each, quoting the grader's own reasoning where it is the evidence); the
bucket counts from R.2; the R.3 tables; and — the deliverable — **one named mechanism hypothesis with
the single change that would test it and the metric that would move.** One variable. Stated as a
falsifiable prediction, registered in `PREDICTIONS.md` before any run that tests it.

**The analysis is not done without §R.** A report that cites only aggregates is incomplete regardless
of how many aggregates it cites.
