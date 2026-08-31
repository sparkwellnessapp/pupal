# Generatable grading plans — design + implementation plan

**Status: DESIGN, awaiting owner rulings. Nothing implemented.**
Author: agent, 2026-08-31. Blocking questions in §5.

---

## 1. The problem, precisely

The v5 grader does not read a rubric and decide what to check. It is *handed* a
checklist — a `GradingPlan` — and only rules "met / partially met / not met" per
item. A deterministic pricer turns those verdicts into points.

Today exactly one plan exists: `hobby_tvshow.plan.json`, **hand-authored** by
`tests/grading_eval_suite/tools/build_hobby_plan.py`, a 448-line one-off script
for one exam. Its shape:

| | |
|---|---|
| terminals | 38 (mirrors the contract exactly — validator rule V6) |
| checks | 80 — avg 2.1 per terminal, range 1–5 |
| kinds | 65 `required`, 14 `tariff`, 1 `note_only` |
| `equivalence_note` | 11 |
| `charge_group` | 2 |

**There is no code in `app/` that can produce a plan for any other rubric.** So
v5 — and with it the Sonnet-5 pin, check-level review, and the whole PR-G1…G9
review module — works for one exam and no other. Every other teacher falls back
to v3/gpt-4o.

That is the gap this spec closes.

---

## 2. What makes this tractable

**The terminal set is not generated — it is derived.** Validator rule V6 forces
`plan.terminals == contract.terminals` exactly, with `points_possible` matching
per terminal. So the generator never invents structure; it only decomposes each
terminal into checks.

Per terminal the task is bounded: given the rubric text, the point value `P`,
the teacher's guidance, the example solution, and the numeric precision, emit
checks such that `Σ required.points == P` **exactly**.

That last constraint is arithmetic — the thing LLMs are worst at and validators
are perfect at. `plan_validator.validate_plan` already enforces all of it, pure
and total:

- **V1** Σ required.points == points_possible exactly
- **V2** every points / tariff_amount on the precision grid
- **V3** kind shape (required ⇒ points>0, no tariff; tariff ⇒ points==0, 0 < amount ≤ possible; note_only ⇒ no points)
- **V4** points × partial_fraction on the grid
- **V5** ids unique · **V6** totality vs contract · **V7** charge_group never spans scopes · **V8** 0 < partial_fraction < 1

This is the ideal generate-then-verify shape: a stochastic proposer inside a
deterministic, already-written, exhaustively-testable gate.

**Inputs available per terminal** (all already on the compiled contract):
`criterion.description`, `.points`, `.evaluation_guidance`, `.notes`,
`sub_criteria[].description/.points`, and from the parent scope
`example_solution`, `question_text` / sub-question `text`, plus
`contract.numeric_policy.precision`, `.programming_language`, `.subject`.

The example solution is where `equivalence_note` comes from — the hand-authored
plan's notes are literally of the form "names matching the example solution
(e.g. `durationInMinutes`) are valid".

---

## 3. Design

### 3.1 It is a Draft → Contract domain (§3.4), like everything else

| | |
|---|---|
| **Draft** | `PlanDraft` — mutable, may be invalid, carries per-terminal diagnostics and the model's rationale |
| **Contract** | `GradingPlan` — already exists, `frozen=True` |
| **Compiler** | `plan_compiler.py` — runs `validate_plan`; the only path Draft → Plan |

No new architectural pattern. The existing validator becomes the compiler's
invariant set.

### 3.2 Generation unit: the SCOPE, not the terminal

One LLM call per scope (a direct-criteria question or one sub-question), not per
terminal. Three reasons:

1. **V7 falls out for free.** A `charge_group` may never span scopes. Generating
   per scope makes that structurally impossible rather than a rule to remember.
2. Criteria inside a scope interact — "deduct once across this question" is a
   scope-level statement, and the model needs the siblings in view to write it.
3. Cost and latency: hobby_tvshow is 6 scopes, not 38 terminals.

### 3.3 The loop

```
compiled GradingRubricContract
        │
        ├─ derive terminal set + points  (pure, from the contract — never the LLM)
        │
        ▼
  per scope:  propose checks  ──►  validate_plan (pure)
        │                              │
        │                        errors│  (bounded repair: ≤2 attempts,
        │                              ▼   errors fed back verbatim)
        │                          re-propose
        ▼
  assemble PlanDraft ──► plan_compiler ──► GradingPlan (frozen)
```

Repair is per scope, so one bad scope never re-runs the other five. Errors are
fed back verbatim — they are already written as human-readable, tagged strings
(`"V1: q1.א.c0 required sum 3 != points_possible 4"`).

### 3.4 The constitution — general rulings, separate from exam content

The hand-authored plan has owner rulings appended into check text: PL-10
(assignment to an undeclared target is a material defect → partially_met), PL-9
(a component valid in its own terms still counts; credit once, as charge is
once), R-β (the penalty applies at every access site).

These are **general grading policy**, not facts about the Hobby exam. They
accumulated from eval iterations. Design: a versioned `PLAN_CONSTITUTION`
module holding them as reusable clauses the generator may attach, with the
constitution version stamped into `plan_version`. This keeps them auditable and
stops them being re-derived per exam.

**Which rulings are general vs exam-specific is an owner call — see OD-5.**

### 3.5 Where it runs, and where it is stored

Generation is a **Cloud Tasks job** (`JobKind.plan_generation`), fired after a
rubric compiles — the established substrate, and the only one that guarantees
CPU outside a request. The teacher never waits: by the time she uploads tests,
the plan is ready.

Storage: `rubrics.plan_json` JSONB + the plan's own `rubric_contract_version`
inside the JSONB, mirroring exactly how `contract_version` lives inside
`contract_json` (no parallel column — CLAUDE.md §4).

### 3.6 The binding bug this must fix

`GradingPlan.rubric_contract_sha256` pins to contract **file bytes**. Production
contracts live in a JSONB column; those bytes do not exist, which is why
`grader_plan_rubric_id` exists as a manual stand-in (OD-G1.4).

A generated plan should bind to `contract_version` — the UUID already minted per
compile and already the pinning mechanism everywhere else (VER-2). That makes
staleness derivable rather than configured, and retires the manual binding.

`rubric_contract_sha256` stays optional for the eval suite's file-based flow.
**This edits a frozen contract type — OD-4.**

---

## 4. Implementation plan

### Phase 0 — THE EXPERIMENT (gates everything else)

Before any production wiring: generate a plan for `hobby_tvshow` **from its own
compiled contract**, and run the existing grading eval with it, against the same
GT, at the same k, on the pinned model. Compare to the hand-authored plan.

This is the whole bet, and it is cheap and decisive because the GT already
exists. If a generated plan cannot approach the hand-authored one on a corpus we
have fully characterised, no amount of production wiring helps.

Deliverables: `app/agents/plan_gen/` (schemas, prompt, generator, repair),
`tools/gen_plan.py`, and a RUNLOG entry with a **pre-registered** prediction and
kill criterion (OD-2 sets the bar).

Named tests: `generated-plan-passes-the-validator`, `generated-plan-terminals-match-contract-exactly`, `repair-loop-is-bounded`, `generation-never-invents-a-terminal`.

### Phase 1 — Draft → Contract plumbing
`PlanDraft`, `plan_compiler.py`, `rubrics.plan_json` (migration 022), plan
staleness derived from `contract_version`.
Tests: `plan-compiles-only-when-valid`, `plan-is-stale-when-contract-version-moves`, `compiler-is-the-only-path`.

### Phase 2 — the job
`JobKind.plan_generation`, `/internal/plan-jobs/{id}/run`, enqueue after compile,
`LivenessRule` instance, retry endpoint. Mirrors extraction exactly.
Tests: `plan-job-cas-claim-is-idempotent`, `plan-job-expiry-is-terminal-on-read`.

### Phase 3 — the seam
`grader_kind_for` consults the stored plan instead of `grader_plan_rubric_id`;
the manual binding is retired. Fallback per OD-6.
Tests: `v5-selected-when-a-fresh-plan-exists`, `stale-plan-never-grades`, `manual-binding-is-gone`.

### Phase 4 — widen the evidence
Generate plans for the other production rubrics; hand-score a sample. Phase 0
proves it on one exam; this is the first evidence it generalises — and the honest
limit of what we can claim until then.

---

## 5. OPEN DECISIONS — owner rulings needed before Phase 0

**OD-1 (product/UX, the big one). Does the teacher review the generated plan?**
The plan decides how a 4-point criterion splits — 1+3 or 2+2 — and that is a
pedagogical choice she never made. But it is also an internal artifact she never
asked for, and 80 checks is a lot of screen for someone whose north-star metric
is *less* after-school work.
*Options:* (a) no gate — validated arithmetically, and her authority is exercised
at the existing grading gate where she reviews the actual awards; (b) a review
surface for the plan; (c) no gate, but every check carries its `rubric_quote` so
the grading review can show "this came from your text here".
*Recommendation:* (c). It preserves "Vivi proposes, the teacher decides" at the
moment she is already reviewing, without inventing a second gate for an artifact
she did not author.

**OD-2. What is the acceptance bar for a generated plan?**
The validator proves arithmetic, never intent. A plan can be perfectly valid and
pedagogically wrong.
*Recommendation:* generated-vs-hand-authored A/B on hobby_tvshow at k≥3, and the
generated plan must not lose more than a named margin on the existing gates
(K1/K2/K4, GA-2). **The owner sets the margin — I will not pick a number that
decides whether my own work passes.**

**OD-3. When does generation run?**
*Recommendation:* async Cloud Tasks job after compile (§3.5). Alternatives:
lazily at first grade (the first student waits ~1–2 min) or synchronously at
compile (the teacher waits at save).

**OD-4. May the frozen `GradingPlan` gain `rubric_contract_version`?**
Required to bind plans to production contracts (§3.6). Additive and optional, but
it edits a frozen contract type and retires `grader_plan_rubric_id`.

**OD-5. Which accumulated rulings are GENERAL policy?**
PL-9, PL-10, R-β were owner rulings from eval iterations on one exam. Promoting
the wrong one to the constitution bakes an exam-specific decision into every
future plan; omitting a general one loses hard-won correctness.
*This is owner judgement — I can propose a split, but I should not make it.*

**OD-6. Fallback when no valid plan exists.**
*Options:* (a) fall back to v3 (grading proceeds, quality silently differs);
(b) refuse to grade and surface it (review-first, not guess).
*Recommendation:* (b) once v5 is the default — a silent quality switch is exactly
the confidently-wrong-output class §3.5a warns about. (a) is right only while v5
is still a pilot.

**OD-7. Regeneration on rubric edit.** Every edit mints a new `contract_version`,
staling the plan. Auto-regenerate (cost per edit, ~$0.20) or on demand?
*Recommendation:* auto, on the same job — the cost is trivial and a stale plan
blocks grading under OD-6(b).

**OD-8. Does this retire v3?** If every rubric can have a plan, the v3 grader
becomes dead code — a real simplification (one grading path, one prompt surface,
one eval target). Or v3 stays as the fallback forever.
*Recommendation:* decide after Phase 4, not now; but flagged because it changes
how much of the old path is worth maintaining meanwhile.

---

## 6. Cost, latency, risk

**Cost:** ~6 calls per rubric (one per scope) + bounded repairs. At Sonnet-5
rates and hobby-sized scopes, **~$0.20 per rubric version** — once per rubric,
amortised over an entire class. Negligible against the $0.15/test grading cost.

**Latency:** ~1–2 min per rubric, off the teacher's critical path as a job.

**Risks, honestly:**
- *Points split differently than a human would.* Totals can match while
  partial-credit behaviour differs. Phase 0's A/B is what surfaces this.
- *Tariffs missed.* 14 of 80 checks are named deductions read out of the
  teacher's own guidance text. A missed tariff silently stops applying a
  deduction she wrote down. Worth its own metric in Phase 0.
- *Over- or under-decomposition.* One check per terminal makes grading
  all-or-nothing and destroys partial credit; too many makes it brittle. The
  hand-authored distribution (1–5, avg 2.1) is the reference.
- *We have exactly one exam's ground truth.* Phase 0 can prove generation works
  *there*. Claiming it generalises needs Phase 4, and until then that limit
  should be stated wherever the result is quoted.
