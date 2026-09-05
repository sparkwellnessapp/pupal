# PR — PLAN COMPILER v2: "Compile · Segment · Route"

**Owner:** Noam · **Status:** RATIFIED — implementation PR, **fully unblocked** (all ODs ruled §8) · **Date:** 2026-09-05
**Supersedes** `PR_SPEC_plan_generation.md` §3.3 (the per-scope LLM decomposer + repair loop) and the pending items 3–4 of the 2026-09-04 instruction (wiring `counted` / Case 4 into the old generator). **Do not start those; they are compiler rules now.** Everything else in the plan-generation spec — Draft→Contract, layer-1 rulings ledger, RL-1, append-only plans, `current_plan_version`, P-0, the phases and ODs — stands.

---

## §0 — Rulings that unblock immediately

**R-1 · V9 clause (c) WITHDRAWN.** Dashes remain elision markers. Clause (a) grounds the dash case; dropping dashes would cost the ratified hand plan 73→71 and would be an instrument change answering a grounding question. Refinement = (a) + (b) only, as you shipped. The scope-label collision fix and its two depth-2 guards are **ratified**.

**R-2 · GT null terminals → `awarded: "0"` by hand (owner ruling).** For all seven `bagrut_899371` GTs, every terminal of an unselected question becomes `awarded: "0"`, `evidence_exists: false`, note unchanged («Question not selected…»). No schema change. **Companion guard, required:** the scorer must **exclude unselected scopes from every per-terminal metric** — Tier-2 rates, K1's GT-ZERO denominator, exact-rate, within-precision, calibration — deriving selection from the transcription contract (empty `answer_text` on a whole question) and `selection_rules`, never from the GT's zeros. Test: `unselected-scopes-never-enter-any-denominator` (expect 298 scored cells, not 403). Owner stamps `authored_at: "2026-09-03"` in the same commit.

**R-3 · Two GT amendments — RATIFIED; the owner applies them himself.** itay_kraft `q3.ב.c2` 1→2 (78.5→**79.5**); din_ezra `q5.ב.c2` 3→5 (89.5→**91.5**). Both were reviewer-fabricated tariffs (no source text), exposed by the plan's disagreement. **You do not edit these files.** When the owner's amended files land, re-run the guard suite and the corpus pin, re-anchor the pin to the new totals, and record the amendment in RUNLOG with the reason. The 488-judgment expressibility guard uses the amended values.

**R-4 · The Opus decomposer is retired, not repaired.** No further work on `plan-gen/v2`'s prompt, repair loop, or the unwired `counted`/Case-4 hooks. Keep the v2 **detector** (`detect_deductions`), the validator (V1–V11), and the corpus builder — they are compiler components now.

---

## §1 — The thesis

A GradingPlan is a **compilation target**, not a creative artifact. Measured across two exams, ~80% of a plan is a deterministic function of the contract text: terminals, points, tariffs (12/12 and 10/10 detected by regex), notes, `counted`, reconciliation, and the point split wherever the text enumerates. The frontier model's measured failures (no `counted`, Case 4 ignored, Q6 under-decomposed, 7/13 scopes exhausting repairs on V1 arithmetic) are **rule-holding and arithmetic failures — the two things determinism fixes and intelligence doesn't.** The LLM's irreducible job is *language*: turning a prose criterion into N checkable statements and phrasing them. That is small-model work on ~1.5k tokens.

**Design law:** the model never emits a number, a kind, an amount, an anchor, or a count. It emits text.

---

## §2 — Architecture

```
GradingRubricContract
   │
   ▼
[Stage 0] DERIVE      terminals + points_possible            (pure, exists — V6)
   │
   ▼
[Stage 1] COMPILE     per terminal → PlanSkeleton            (pure, zero spend)
   │                  tariffs · notes · counted · components · points · groups · flags
   │
   ├──► [Stage 2b] ROUTE   monoliths only → propose N components   (Sonnet 5, minority)
   │
   ▼
[Stage 2] SEGMENT     per terminal → description_he + rubric_quote per slot   (Haiku 4.5)
   │
   ▼
[Stage 3] ASSEMBLE    PlanDraft → validate (V1…V11 + expressibility) → GradingPlan (frozen)
```

Stages 0, 1, 3 are pure. Stage 2 is stochastic **only in text**. Two compilations of the same contract yield **byte-identical algebra** — identical expressibility, identical pricing — differing only in wording. (This retires P-G2d for the algebra; it remains a wording question only.)

---

## §3 — Stage 1: the compiler, rule by rule

Input per terminal: its `description`, `evaluation_guidance`, `notes`, sub-criteria text, `points_possible`, the scope's `example_solution` (structure only, for Case 1 table shapes), `numeric_policy.precision`.

**C1 · Deductions → tariff slots.** `detect_deductions` (v2 patterns **+ `לקנוס` / `קנס`**). Amount copied verbatim. Anchor = the terminal whose own text contains the phrase. Parent-level phrase over sub-criteria → tariff slot on the **first** child with a `charge_group` spanning all siblings, so it fires at most once for the whole criterion — flagged — **OD-10 RATIFIED (a)**. Live reference case: hobby `q2.ב.c4` («להוריד 3», max-instead-of-min) over six sub-criteria → tariff on `s0`, group across `s0…s5`. Pin it: this reproduces the ratified Q-2 outcome on the hand plan.

**C2 · Note-only → note slots.** «לא להוריד» / «אין להוריד» → `note_only`, zero points.

**C3 · Uniform units → `counted` (R-E Case 1).** Patterns: «N תאים p כל תא», «N × p», «p נק' לכל [יחידה]» with a count, «כל [יחידה] p», or a trace-table shape in the scope's solution (rows×cols − header) when the criterion is the table. Emit one `counted` slot: `unit_count = N`, `points = points_possible`; the stated per-unit value goes to `rubric_quote` metadata. No other slots on that terminal.

**C4 · Component enumeration (P-A, deterministic).** Parse the criterion text into named components, in order:
- **explicit values** — «(1)», «(1 כ"א)», «2 נק'», «- 2 נקודות», «X נקודות» attached to a clause → components with stated points;
- **explicit separators without values** — clauses split by « + », «וגם», « ו-…» chains of requirements, numbered «1.»/«2.», bullets → N components, no values;
- **neither** → one component (monolith) → C7.
Every component records its **source span** (the exact clause) as the `rubric_quote` default.

**C5 · Points (R-E, deterministic).** Stated values: Case 2 (Σ<P → remainder slot for the unenumerated rest) / Case 3 (Σ>P → largest-class-first absorption, symmetry-preserving, order-preserving, flag on residual). No values: **even split** of P over N on the grid; a residual that cannot divide evenly goes **+1 grid unit to each of the first k components in textual order** (k = residual ÷ grid unit), flagged — **OD-9 RATIFIED (a)**. Worked reference: 5 points over 3 components → 1.75 / 1.75 / 1.5, flagged. Case 4 («X (או Y?)») → lenient amount, flagged.

**C6 · Groups.** Rubric text «פעם אחת» / «רק פעם 1» spanning siblings → `charge_group`. Same-ink credit conventions stay in layer 1 (R-D), not here.

**C7 · Monolith routing — OD-11 RATIFIED: `points_possible ≥ 4` AND a scope `example_solution` present → Stage 2b.** Below 4 points, or no solution → stays a single check (`partially_met` carries partial credit). Expected routing on the two contracts: **hobby 4 terminals** (`q1.א.c0`, `q1.א.c1`, `q2.א.c0`, `q2.א.c1`), **bagrut 7** (`q2.א.c4`, `q2.ב.c3`, `q3.ב.c4`, `q4.א.c1`, `q5.א.c1`, `q5.ב.c2`, `q6.c8`) — ~11 router calls total. Report the actual routed set; a divergence from this list is a C4 enumeration-parser finding to surface, not to silently accept.

**Output — `PlanSkeleton`:** per terminal, ordered slots `{slot_id, kind, points|tariff_amount|unit_count, partial_fraction (default 0.5), charge_group, source_span, flags[]}`. **V1 holds by construction — assert it, and treat a failure as a compiler bug.**

---

## §4 — Stage 2: the segmenter (Haiku 4.5)

One call per terminal (batch sibling terminals of a scope into one call where it keeps context < ~2k tokens). **Input:** the terminal's criterion text; the ordered slots with their `source_span`s and kinds; the scope's `example_solution` **only if any slot needs an equivalence note** (see below). **Not** input: points, amounts, counts. **Output, exactly N entries in slot order:** `description_he` (phrased so `met` = satisfied; for tariff slots, the requirement whose absence fires the tariff — «בדיקת null מבוצעת», not «לא בדקו null»), `rubric_quote` (verbatim; defaults to `source_span`, may elide within it), `equivalence_note` (**only** with a licensing citation from the solution or criterion text — «מותר X כי הפתרון לדוגמה עושה X»; otherwise empty).

Schema-enforced: no `points`, `kind`, `tariff_amount`, `unit_count` fields exist in the output type. V10 (no point-denoting text) and V9 (refined a+b) run on the output; a failure retries **once** with the error verbatim, then the compiler **substitutes the `source_span` itself as `description_he`** and flags — a plan is never blocked on wording.

Prompt: `segmenter/v1`, subject-agnostic, three principles (cite-then-claim; met-means-satisfied; equivalence only with a licensing citation), 2–3 domain-shifted examples. Model per verified card: `claude-haiku-4-5` primary; Flash tier fallback. Sonnet 5 only if Haiku's V9/V10 failure rate on the calibration set exceeds 10% of slots.

---

## §5 — Stage 2b: the monolith decomposer (Sonnet 5, routed minority)

For C7 terminals only (expected 5–15% of criteria): one call with the criterion text + the scope's `example_solution`. **Output:** N ≤ 5 component names, each with a verbatim span **from the solution or criterion** that evidences it. No points. The compiler then even-splits P over N (C5) and Stage 2 phrases them. Reference cases the output must reproduce structurally: hobby `q2.א.c1` (UpdateRate → header / loop / read-parse / accumulate-to-existing), bagrut `q6.c8` (selection / pair-write / advance-by-2).

---

## §6 — Stage 3: assemble and validate

`PlanDraft` → `plan_compiler` → `GradingPlan`. Validators: V1 (assert), V2–V8, V9 refined (a)+(b), V10, V11 (now an assertion — every detected deduction is a slot by construction). Then the **expressibility + faithfulness guard against every ratified GT** — hobby 190 + bagrut 298 = **488 judgments** (after R-2/R-3 land). Provenance: `plan_version` (sha256 of the plan), plus `compiler_version`, `segmenter_prompt_version`, `segmenter_model`, `router_model`.

---

## §7 — Acceptance, in order (Phase 0 redux, cheap and decisive)

**A0 · Compiler-only, zero spend.** Run Stages 0/1/3 with `source_span` as placeholder descriptions on **both** contracts, against the GTs **as amended (R-3)**. This measures the algebra alone. Bars: hobby expressibility ≥ 189/190 (the hand plan's 190 includes one owner tariff no text yields); bagrut ≥ 295/298 with **every miss granularity-class** (a decomposition-class miss fails A0 and is a compiler bug to fix — calibration against the ratified reference, legitimate class). Tariff 12/12 · 10/10; notes 1/1 · 2/2; `counted` 0 · 1; Case 4 → 1 on `q6.c6`; Case 3 → (1,2,1,1) / (0.5,0.5,2,1,1) on `q4.ב.c4/c7`; OD-10 → hobby `q2.ב.c4` tariff on `s0` with sibling group; OD-11 → the routed sets in C7. **A0 gates all spend.** Deliver A0 as `A0_REPORT.md`: per-exam scorecard, every miss classified, every flag listed.

**A1 · Segmenter, ≤ $2 envelope.** Both contracts on Haiku. Report: V9/V10 clean rate, substitution count, cost per rubric (target **≤ $0.50**, expected ≈ $0.20–0.40), latency. Owner spot-reads 10 random `description_he` for verifier-readiness.

**A2 · Router.** C7 terminals only; verify hobby `q2.א.c1` and bagrut `q6.c8` reproduce their reference component structure.

**A3 · The two-exam A/B** on the pinned grader under OD-2 as ratified — now against a compiled plan whose algebra is deterministic. Register predictions before spend; EVAL_ANALYSIS.md per trial; propose an envelope before A3.

---

## §8 — Decisions: all ruled (2026-09-05). Nothing here blocks implementation.

- **OD-9 — RATIFIED (a):** even-split residual → +1 grid unit to each of the first k components in textual order, flagged. (C5)
- **OD-10 — RATIFIED (a):** parent-level tariff over sub-criteria → first child + sibling `charge_group`, fires at most once. Live case: hobby `q2.ב.c4`. (C1)
- **OD-11 — RATIFIED:** monolith routing at `points_possible ≥ 4` with a scope solution present; 4 hobby + 7 bagrut terminals expected. (C7)
- **R-3 — RATIFIED:** the two GT amendments; owner applies them. (§0)
- **OD-12** `partial_fraction` floor for structure-only credit — **deferred by design**; a policy knob, not a compiler bug. Do not implement; the three bagrut granularity misses remain expected and are excluded from A0's failure count as granularity-class.

**Surface, don't decide:** anything not covered above that changes a number, a kind, an anchor, or a count — post it as an open decision with a recommendation and continue on the parts that don't depend on it.

---

## §9 — Fence and definition of done

Zero spend for A0; A1 ≤ $2; A2 ≤ $1; A3 envelope proposed before running. No production wiring (plan-gen Phases 2–4 stay gated on P-0 and the ledger). GT untouched except R-2 (owner-ruled) and R-3 (owner-gated). No bar or gate moves. **Retire:** `plan-gen/v2` prompt, the repair loop, the `dispositions` draft field (V11 becomes an assertion). **Done when:** A0 green on both exams · A1 cost and clean-rate reported · A2 reference structures reproduced · compiled plans for both exams committed append-only with full provenance · expressibility 488-judgment guard standing · RUNLOG + batteries green · hold before A3.
