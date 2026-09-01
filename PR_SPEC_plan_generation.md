# Generatable grading plans — design + implementation plan

**Rev 2, 2026-08-31.** Rev 1 reviewed by the owner; all eight change requests
and all eight OD verdicts are incorporated below. **Status: awaiting final
approval. Nothing implemented.**

Two findings from verifying the review are new and change the plan:

- **P-0 (blocking, §6).** Criterion IDs are **positional** —
  `criterion_id = f"{qid}.{sid}.c{i}"` over `enumerate(...)`. Inserting one
  criterion shifts every later ID, so a durable ruling keyed to `q1.א.c2`
  silently re-attaches to a different criterion. The review predicted this; it
  is confirmed, and it blocks the ruling ledger (not the experiment).
- **Good news (§4, Phase 0).** `tests/grading_eval_suite/plan_expressibility.py`
  **already exists**, with exactly the semantics the review describes, already
  wired as a standing pytest *and* as the runner's pre-spend refusal. The
  cheapest, most decisive Phase-0 test is a reuse, not a build.

---

## 1. The problem

The v5 grader is handed a checklist — a `GradingPlan` — and rules met / partly /
not per item; a deterministic pricer turns verdicts into points. Exactly one
plan exists, hand-authored for one exam by a 448-line one-off script. **No code
in `app/` can produce a plan for any other rubric**, so v5 — and with it the
Sonnet-5 pin and the whole review module — works for one exam and no other.

## 2. What makes it tractable

**The terminal set is derived, never generated** (validator V6 forces
`plan.terminals == contract.terminals`). The generator only decomposes each
terminal into checks such that `Σ required.points == points_possible` exactly —
an arithmetic constraint, which is where LLMs are worst and the existing
`plan_validator` (V1–V8, pure and total) is perfect. Generate → verify → bounded
repair, with the validator's already-human-readable tagged errors fed back
verbatim.

Reference shape (the hand-authored plan): 38 terminals, 80 checks, avg 2.1 per
terminal (range 1–5), 65 `required` / 14 `tariff` / 1 `note_only`, 11
`equivalence_note`, 2 `charge_group`.

---

## 3. Architecture — two layers, one frozen artifact

Rev 1's single mistake was treating the constitution as a static module the
generator "may attach." It is not static: **most of a rubric's rulings do not
exist at generation time.** They surface later, from grading disagreements and
teacher overrides, and none of them are derivable from rubric text. Under rev 1,
regenerate-on-edit would have discarded every accumulated ruling along with the
decomposition it was attached to.

**The decomposition is volatile. The rulings are the asset.**

```
     LAYER 1 — RULING LEDGER (durable, append-only, survives regeneration)
     keyed to (rubric lineage, STABLE terminal identity)
     sources: owner constitution · teacher overrides · audit
                     │
                     │  merged at compile
                     ▼
     LAYER 2 — DECOMPOSITION (volatile, per scope, regenerable)
     generated from the contract; replaced wholesale for CHANGED scopes only
                     │
                     ▼
        plan_compiler  ──►  GradingPlan (frozen)  ──►  stored APPEND-ONLY by plan_version
```

### 3.1 Layer 1 — the ruling ledger

Two ruling kinds, because the review's OD-1 loop needs both:

| kind | what it carries | who creates it |
|---|---|---|
| `policy` | a clause appended to the check text (PL-10, R-β …) | owner constitution; audit |
| `decomposition` | a **pinned check set** for one terminal, overriding generation | the teacher, via OD-1's lazy ratification |

`decomposition` is what makes "her override becomes a durable ruling" real: once
she edits the 1.5 + 1.5 split, that terminal is **pinned** and regeneration must
never re-roll it.

**RL-1 (RulingAnchorResolves) — a new named invariant.** Every ruling's anchor
must resolve to exactly one live terminal (and, for check-scoped policy, exactly
one check) at compile. An unresolvable anchor is a **loud compile failure**,
never a silent drop. This mirrors CW-3 ("every override key is a real terminal")
and exists because the alternative — quietly dropping a ratified ruling during a
routine rubric edit — is the confidently-wrong class §3.5a is about.

### 3.2 Layer 2 — the decomposition

One LLM call **per scope** (not per terminal): V7 (`charge_group` never spans
scopes) becomes structurally impossible rather than a rule to remember, siblings
stay in view for charge-once statements, and hobby_tvshow is 6 calls not 38.

**Regeneration is per scope, diffed against the previous contract** (review
item 6). A rubric edit touching one criterion must not re-roll the other five
scopes: stochastic regeneration would silently change grading behaviour on
criteria the teacher never touched, mid-semester. Unchanged scopes are carried
**byte-identically**. Terminals with a `decomposition` ruling are never
regenerated at all.

### 3.3 Storage — append-only (review item 2)

A `plan_json` column overwritten on regeneration destroys the audit trail. Every
graded draft pins `plan_version`, and appeal-defensibility requires that exact
artifact to still exist — "applied identically to all N students under the
ruling set of *date*" is not a claim you can make from a plan that was
overwritten.

- `grading_plans` table, append-only, keyed by `plan_version`
- `rubrics.current_plan_version` points at the live one
- ruling ledger is its own table, also append-only (a ruling is retired by a
  superseding entry, never by deletion)

### 3.4 Two new validator rules (review item 5)

- **V9 — rubric-quote grounding.** Every check's `rubric_quote` must be a
  verbatim span of its terminal's criterion text (or its parent scope's
  `example_solution`). The plan-level analogue of evidence-quote validation: a
  hallucinated check becomes structurally impossible, and it is what makes
  OD-1's "this came from your text, here" display honest rather than decorative.
- **V10 — point-blindness.** `description_he` may not contain point values. The
  verifier is point-blind by design; leaking the number into the check text
  hands it the answer.

Both pure, both cheap, both in the same validator as V1–V8.

### 3.5 Binding (OD-4)

`GradingPlan` gains `rubric_contract_version` (the UUID already minted per
compile, the mechanism VER-2 uses for grades) and `constitution_version`.
`rubric_contract_sha256` stays optional for the eval suite's file-based flow.
Staleness becomes derivable, and `grader_plan_rubric_id` — the manual stand-in
blocking the Sonnet pin — retires.

### 3.6 Generation model (review item 7)

**The plan is the quality ceiling**, and it is a one-time amortised cost: six
scopes at ~$2 per rubric version against a whole class's grading. Generation
runs on the strongest available tier (Opus 5 or gemini-pro at default thinking),
**not** the grading pin. Sonnet-5 rates are the wrong optimisation target here.

### 3.7 Subject modularity (review item 8a)

The generator's core prompt is subject-agnostic (§3.3 of CLAUDE.md). CS-flavoured
authoring heuristics and subject-scoped clauses (PL-2's `cw`/`CR` shorthand)
attach **by `contract.subject`**, never in the core. Litmus: a new subject is a
new clause pack and new prompt fragments, with no change to the generator, the
validator, or the ledger.

---

## 4. Phase 0 — the experiment (gates everything)

Generate a plan for `hobby_tvshow` **from its own compiled contract** and
compare against the hand-authored plan on ground truth we already own.

**Order matters — the free test runs first.**

**0a. Expressibility, before a single dollar of grading.** Reuse
`plan_expressibility.expressibility_errors`: for every one of the 190 ratified
GT awards (38 terminals × 5 students), is there *any* verdict assignment the
plan algebra can produce it with? The hand plan scores 190/190. A plan that
cannot express the teacher's award can never reproduce it on any model, at any k.

Misses partition cleanly, and the partition is the measurement:
- **decomposition-class miss** — the split itself is wrong. A failure.
- **ruling-class miss** — an exam-specific judgement the generator could not
  have known. Expected, and a **direct measurement of what layer 1 is worth**.

**0b. Two variants, because rev 1's A/B was contaminated** (review item 4). If
the generator attaches PL-9/PL-10/R-β — rulings *derived from this exam's GT* —
the comparison says nothing about generalisation.

| variant | attaches | measures |
|---|---|---|
| **V-rubric** | nothing but the rubric | pure decomposition quality |
| **V-const** | + the general constitution (OD-5 classes 1–3) | the general-clause delta |
| hand plan | everything incl. exam-specific | the residual = exam-specific ruling value |

**0c. Grading A/B** on the pinned model at k≥3, scored against OD-2's bar.

**0d. Report** (review item 8b): equivalence-note count against
`example_solution` presence, per scope. Equivalence notes come from the model
solution; a rubric without one will produce harsher plans on alternative student
designs, which makes solution-image ingestion a **prerequisite for plan
quality**, not a nice-to-have.

Named tests: `generated-plan-passes-the-validator`,
`generated-plan-terminals-match-contract-exactly`,
`generated-plan-is-expressible-over-gt`, `repair-loop-is-bounded`,
`generation-never-invents-a-terminal`, `checks-carry-no-point-values` (V10),
`rubric-quote-is-a-verbatim-span` (V9).

**Phase 0 does not need P-0.** It operates on one frozen contract; stable
identity only matters once contracts change. The experiment is unblocked today.

---

## 5. Phases 1–4

**Phase 1 — the two layers.** Ruling ledger (schema, RL-1, append-only),
`PlanDraft` → `plan_compiler` → `GradingPlan`, append-only `grading_plans`,
`rubrics.current_plan_version`. **Requires P-0.**
Tests: `ruling-survives-regeneration`, `pinned-decomposition-is-never-re-rolled`,
`unresolvable-ruling-anchor-fails-loudly`, `plan-history-is-append-only`,
`compiler-is-the-only-path`.

**Phase 2 — the job.** `JobKind.plan_generation`, `/internal/plan-jobs/{id}/run`,
enqueue after compile, `LivenessRule` instance, retry endpoint, **contract-diff
per-scope regeneration**.
Tests: `plan-job-cas-claim-is-idempotent`, `plan-job-expiry-is-terminal-on-read`,
`unchanged-scopes-are-carried-byte-identically`.

**Phase 3 — the seam.** `grader_kind_for` consults the stored plan; the manual
binding retires; OD-6 fallback.
Tests: `v5-selected-when-a-fresh-plan-exists`, `stale-plan-never-grades`,
`manual-binding-is-gone`, `refusal-enqueues-a-retry-and-never-shows-an-error`.

**Phase 4 — generalisation, named honestly** (review item 8c). This *is* the
fixture-expansion mission wearing a different hat: it means **authoring ground
truth on a second exam**. It is the prerequisite for any claim that generation
generalises, and until it lands, every Phase-0 result is quoted with "proven on
one exam."

---

## 6. P-0 — stable criterion identity (PREREQUISITE, resolve once)

**Confirmed defect.** `docx_v3/pipeline.py`:

```python
criterion_id     = f"{qid}.{sid}.c{i}"   # for i, c in enumerate(sq.criteria)
sub_criterion_id = f"{cid}.sc{i}"
```

IDs are **positional**. Insert a criterion at position 0 and every later ID
shifts by one. Consequences, all silent:

- a layer-1 ruling re-attaches to a **different criterion**;
- `TeacherOverride.check_id` (CW-3) and the audit key
  `(rubric_id, question_id, criterion_id, check_id, plan_version)` have the same
  exposure — this is one root cause behind several features.

**Recommendation: mint a stable `uid` per criterion / sub-criterion at
extraction, carried verbatim through every edit.** The frontend codec already
has the mechanism — every wire field is either modeled or carried through the
typed `_carry` bag (CLAUDE.md §11), so a carried `uid` survives an untouched
open→save as a structural identity, a reorder preserves it, and only a genuinely
new criterion mints a new one.

Rejected alternatives: content-hash identity (breaks exactly when she edits the
text, which is when she is most likely also ratifying a ruling); fuzzy re-anchor
with a surfaced mismatch (adds a new judgement call to every edit).

`criterion_id` stays the display/path identity — nothing about `q1.א.c2` as an
anchor for humans changes. `uid` is the machine identity for durable references.

**This is an ontology change and therefore an owner decision.** It blocks
Phase 1, not Phase 0.

---

## 7. Open decisions — owner verdicts (2026-08-31), as ruled

**OD-1 — no upfront gate; lazy ratification at the point of disagreement.**
When she overrides a 1.5-of-3 award, the review shows the split
(1.5 יצירה + 1.5 תא נכון) and editing it *there* is the ratification: her edit
becomes a durable `decomposition` ruling in layer 1. The plan becomes
teacher-owned without ever becoming teacher homework. V9 is what makes the
display honest.

**OD-2 — the bar measures decomposition, not accumulated rulings.**
- Expressibility **≥ 180/190**, and **every miss attributable to an owner ruling
  not derivable from rubric text**. A decomposition-class miss fails outright.
- **K1 = 80/80 — inviolable, no margin.**
- K2 ≤ hand + 1 cell · K4 ≤ hand + 1.0 · GA-2 ≥ hand − 0.05.
- **Tariff recall 14/14, note_only recall 1/1** — named deductions are literal
  text extraction and must not miss.

**OD-3 — async after compile**, plus **recompile (not regenerate) on ruling
ratification**, plus on-demand retry.

**OD-4 — yes**, additive and optional; add `constitution_version`; keep
`rubric_contract_sha256` for the eval flow. Prerequisite P-0 (§6).

**OD-5 — the ruling split, as authored:**

| class | rulings | attached by |
|---|---|---|
| **General** | PL-1, PL-3, PL-10, R-α (solution is naming authority), R-β (a named tariff applies at every access site), A-6 (a tariff never compounds on a demoted verdict), charge-once / credit-once, and the authoring rule behind P-A (criterion text naming N components → N checks) | generator |
| **General-default, teacher-overridable** | PL-9 — a genuine pedagogical stance on structural credit that most Bagrut graders share and some will not | generator, overridable via layer 1 |
| **Subject-scoped (CS-Israel)** | PL-2 (`cw`/`CR` shorthand) | generator, by `contract.subject` |
| **Exam-specific — never promoted** | PL-8 (an instance of PL-3 the equivalence notes already capture), Q-1, din's credit-side note, P-B's tariff | layer 1 only |

**OD-6 — (b) refuse once v5 is default; (a) v3 fallback during the pilot.**
A refusal **auto-enqueues a regeneration retry and surfaces to ops**; the
teacher sees "grading is being prepared", never an error.

**OD-7 — auto, per-scope, ruling-preserving**, triggered on **compile** (already
the deliberate save gate), so editing sessions do not thrash.

**OD-8 — sunset criterion set now, decision after Phase 4.** v3 retires once
**10 production rubrics** have graded under v5 with kill parity and **no OD-6
refusals for a month**. One grading path, one prompt surface, one eval target —
with a date attached rather than an open question.

---

## 8. Cost, latency, risk

**Cost.** ~6 calls per rubric version on a top-tier model ≈ **$2**, once,
amortised over a class. Regeneration is per changed scope, so a one-criterion
edit costs a fraction of that.

**Latency.** ~1–2 min per rubric, off the teacher's critical path as a job.

**Risks, honestly:**
- *Decomposition differs from a human's.* Totals match while partial-credit
  behaviour differs. 0a catches this mechanically, before spend.
- *Tariffs missed.* 14 of 80 checks are named deductions read out of her own
  guidance text; a miss silently stops applying a deduction she wrote down.
  Hence OD-2's 14/14, separate from any aggregate.
- *No example solution.* Harsher plans on alternative designs. Measured in 0d;
  solution ingestion is a prerequisite for plan quality.
- *One exam's ground truth.* Phase 0 proves it there. Generalisation needs
  Phase 4, and the limit is quoted with every result until then.

---

## 9. P-0 implementation plan (posted before code, per the 2026-09-01 ruling)

Stable identity for criteria and sub-criteria. Ruled 2026-09-01; blocks Phase 1.

### 9.1 The change

`Criterion` and `SubCriterion` gain `uid: Optional[str]` — a **server-minted
UUID4**, distinct from `criterion_id`, which stays exactly what it is today: a
positional display/path identity (`q1.ב.c4`). Nothing about how a human refers
to a criterion changes.

| | `criterion_id` | `uid` |
|---|---|---|
| shape | `q1.ב.c4` — positional | UUID4 |
| stable across insert/reorder | **no** | **yes** |
| used for | display, paths, `data-scope-id`, annotations | durable references: ruling anchors, overrides, audit keys |

### 9.2 Where it is minted (server only)

1. **Extraction** (`docx_v3/pipeline.py::_build_criterion`) mints on first build.
2. **Save / compile** backfills: any criterion arriving without one is minted a
   `uid` at that moment. Idempotent, and it is what covers the six existing
   production rubrics on their next compile without a data migration.
3. **The client never mints.** A client-minted id is a client-controlled
   database key, and the frontend already carries unmodelled wire fields
   verbatim through the `_carry` bag (CLAUDE.md §11) — so a carried `uid`
   survives an untouched open→save as structural identity with no editor change.

### 9.3 Invariants and named tests

- `uid` unique within a rubric — validator rule, loud.
- **`uid-survives-open-save-compile`** — byte-for-byte across a round trip.
- **`uid-survives-reorder`** — moving a criterion preserves it; `criterion_id`
  changes and that is correct.
- **`uid-minted-for-a-new-criterion`** — insert mints exactly one new uid.
- **`delete-and-recreate-mints-a-new-uid`** — re-adding "the same" criterion is
  a NEW criterion; silently re-attaching old rulings to it would be the
  positional bug wearing a different hat.
- **`backfill-is-idempotent`** — compiling twice mints nothing the second time.
- **`contract-carries-uid`** — `ContractCompiler` copies it into the frozen
  contract. Without this the plan compiler cannot resolve a ruling anchor
  against the artefact it actually compiles.

### 9.4 Blast radius, stated

Same OD-4 class (additive, optional, defaulted) across: `ontology_types`
(`Criterion`, `SubCriterion`), the V3 pipeline's builders, `ContractCompiler`,
`rubric_management` save/compile, the generated TS wire types (`npm run
gen:api`), and the frontend codec's carry manifest. The editor family needs no
change — a carried field is already invisible to it by design.

**Not in P-0:** re-keying `TeacherOverride.check_id` or the audit key onto
`uid`. Both have the same positional exposure and both should move, but they are
live surfaces with their own migrations; P-0 establishes the identity, and those
cut over in their own PRs. Naming that here so the exposure is not mistaken for
closed.
