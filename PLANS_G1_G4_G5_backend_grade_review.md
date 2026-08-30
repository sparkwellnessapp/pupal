# PLANS — PR-G1, PR-G4, PR-G5 (schema-touching → plan before code, §0.1)

**Spec:** `PR_SPEC_backend_grade_review.md` rev 2. **Tracker:** `TRACKER_backend_grade_review.md`.
**Gate:** the owner's ratification. Nothing below is implemented yet.
**Standing:** OD-B1 closed (gemini-3.1-pro, plan `hobby_tvshow/v3` + `grader-v5.1`).

---

## PR-G1 — v5 checks on the production wire

### Problem, in Deutsch form

**Data.** The verifier already produces, per check, exactly the record the wire
needs: `AssessedVerdict{check_id, verdict, confidence, basis_he, quote_text,
quote_status}` (`pricer.py:49-59`). `PricedTerminal` (`pricer.py:62-68`) keeps
none of it, and `_leaf_fields` (`grader_v5.py:195-207`) serialises six aggregate
fields onto the outcome. Meanwhile production does not run the v5 agent at all:
`grading_runner.py:117` constructs `GraderAgent()` unconditionally and no
`GRADER_MODEL_KEY` exists.

**Theory under criticism.** "Check-level review needs the grader to produce
something new." It does not. The theory that the data must be re-derived is
falsified by the pricer's own input.

**Better conjecture.** Two independent changes, neither of which touches the
model: (a) a config seam that constructs the v5 agent under the ratified pin —
the owed R-4 PR; (b) a pass-through that stops discarding the verdicts.

**Criticism.** Hard to vary: any other way of getting `checks[]` onto the wire
either re-runs the model (cost, non-determinism, and a second source of truth
for a verdict already decided) or re-derives verdicts from points (impossible —
the map is lossy). One new contradiction is possible and is called out as OD-G1.2
below: the draft grows by ~80 check rows per test, which is a JSONB size change,
not a semantic one.

### Deliverable

- **(a)** `GRADER_MODEL_KEY` + plan/prompt pin in `config.py`; `grading_runner`
  builds through `llm_factory.build_chat_model` and constructs `PlanVerifyGrader`
  when the pin names a v5 architecture. Default stays v3 until the owner flips
  the env — the flip is config, not a deploy.
- **(b)** `PricedTerminal` gains `checks: List[CheckRecord]`; `price_scope`
  fills it from the `AssessedVerdict`s it already holds; `_leaf_fields` passes it
  to `TerminalOutcome.checks[]`.
- **(c)** `ContractCheck` mirror on `ContractTerminalOutcome` (§1.4).
- **(d)** codegen (`npm run gen:api`), TS regenerated, drift job green.
- **(e)** `scripts/gen_grade_review_fixtures.py` + the §1.7 fixture set.

`Check` uses the **existing** `AssessedVerdict` names per rev 2 — `basis_he`
(rendered as the grey line) and `confidence` (carried for the eval suite, never
rendered). No `equivalence_note`.

### Files

`app/agents/grader/pricer.py` · `grader_v5.py` · `app/schemas/graded_test_draft.py`
· `graded_test_contract.py` · `app/services/graded_test_contract_compiler.py` ·
`grading_runner.py` · `app/config.py` · `scripts/gen_grade_review_fixtures.py` (new)
· `frontend/src/lib/api-types.ts` (generated).

### Invariants

`test_terminal_grade_decode_order_is_evidence_first` untouched (it pins the v3
`TerminalGrade`, which this PR does not modify). `flags`/`annotations` untouched
(§6) — `quote_status` is the check-level view of the same event, not a competing
surface. All four versions stamped: model, prompt, plan, contract.

### Open decisions

| ID | Decision | Recommendation |
|---|---|---|
| OD-G1.1 | Does the config flip to the v5 pin ship in this PR, or land dark behind a default-off flag? | **Dark, default-off.** The pin is evidence-backed but production has never run v5. One env var flips it after the fixtures are reviewed. |
| OD-G1.2 | `checks[]` grows `draft_json` by ~80 rows/test. Store in full, or store and prune `basis_he` on `met`? | **Store in full.** basis-lean already makes `basis_he` empty on `met`; pruning a second time invents a third representation of the same lean rule. |
| OD-G1.3 | v3 drafts have no `checks[]`. Optional field, or required-under-v5-pin only? | **Optional on the type, required by a validator when `plan_version` is set.** A hard-required field would make every existing draft unparseable. |

### Tests (red first)

`draft-persists-v5-checks` · `contract-mirrors-checks` · `fixtures-regenerate-clean`
· `production-pin-is-config-driven` · `draft-stamps-all-four-versions`.

---

## PR-G4 — feedback at four layers

### Problem, in Deutsch form

**Data.** No feedback field exists at any granularity (grep-verified). The
teacher writes the same three sentences on thirty papers.

**Theory under criticism.** "Feedback is a property of the grade, so the grader
should emit it." That theory produces a grader that argues for its own numbers:
the same call that decides a verdict would also justify it in prose, and the
prose then anchors the verdict.

**Better conjecture.** Feedback is a property of the **priced result**, not of
the grading decision. One separate call per test, strictly after pricing, whose
input is the priced verdicts + quotes + rubric text and which can therefore
only describe what was already decided.

**Criticism.** Hard to vary: moving the call before pricing re-creates the
anchoring problem; folding it into the grader's call does too and additionally
breaks the decode-order pin. The residual risk is cost, which OD-B3 bounds.

### Deliverable

`app/agents/feedback/` — one structured call per test after pricing; C2 prompt
rules (2nd-person past tense / nominal forms, credited → missing → one pointer;
summary = two patterns + one pointer; never restate the total); `FeedbackBlock`
on the draft, effective form on the contract; `POST …/feedback/regenerate`; cost
stamped into the existing per-test columns.

### Invariants

Never before pricing. Never touches `TerminalGrade`. **A failed feedback call
lands the draft with `feedback = None` + an INFO annotation and never blocks the
test** — review-first, not guess.

### Open decisions

| ID | Decision | Recommendation |
|---|---|---|
| OD-B3 | Model tier | Cheapest tier that passes the gender-neutral lint, same provider family as the pin, inside the $0.15 ceiling. Measured on the five fixtures before it is fixed. |
| OD-G4.1 | `basis_hash` input set | The **ordered effective verdict vector** only (not points, not quotes). Points are derived from verdicts, so including them makes the hash change when nothing the text depends on changed. |
| OD-G4.2 | Regenerate when an overlay text exists | Per §1.6 return the text for the UI to offer, never overwrite. The teacher's words are hers. |

### Tests

`feedback-call-runs-after-pricing-once-per-test` · `feedback-contract-carries-effective-text`
· `feedback-stale-derived-from-basis-hash` (pure) · `feedback-failure-does-not-block-draft`
· `feedback-gender-neutral-lint`.

---

## PR-G5 — override overlay v2 + pricing composition

### R-2 COUNT — measured, production, read-only (census item G)

```
graded_tests total                                        : 0
by status                                                 : (no rows)
unapproved (status='draft')                               : 0
R-2: unapproved + v3-era (no plan_version) + overlay      : 0
context: ANY status + v3-era + overlay                    : 0
context: approved rows (frozen contracts)                 : 0
```

**The count is 0, and the stronger fact is that `graded_tests` is empty in
production.** So R-2's first branch applies, with no caveat: **remove
`points_awarded`, make `verdict` required, one representation of an override, no
dual-path pricer, no legacy-overlay migration** — there is nothing to migrate and
no approved contract to preserve. The overlay data migration listed in spec §4
becomes a no-op and should be struck rather than written.

### Problem, in Deutsch form

**Data.** `GradedTestOverrides = Dict[str, TeacherOverride]` — a bare alias
(`graded_test_draft.py:46`) — with one override per terminal and a required
`points_awarded`. The teacher now decides at check level, and a terminal has
several checks.

**Theory under criticism.** "An override is a points value on a terminal."
Under check-level review that is not expressible: two teachers can reach the
same terminal points through different verdicts, and the contract would record
neither.

**Better conjecture.** An override is a **verdict on a check**; points are
derived by the same pricer that derives them from the model's verdicts. One
pricer, one direction of derivation, everywhere.

**Criticism.** Hard to vary: keeping points as a parallel input means two ways
to say the same thing and a pricer that must reconcile them — which is exactly
the dual-path R-2 rules out now that the count is 0.

### Read-site enumeration (the type change's blast radius, paid once, in the open)

| file | hits | what it does | change |
|---|---|---|---|
| `app/schemas/graded_test_draft.py` | 4 | defines `TeacherOverride`, the alias, and the draft field | **the change itself** — alias → Pydantic model |
| `app/api/v0/grading.py` | 11 | `/draft` save, `/approve`, revision flows read+write the overlay | rewrite against the model; server re-prices on save |
| `app/services/graded_test_contract_compiler.py` | 5 | approval gate; CW-3; `was_overridden` | CW-3 extended to `check_id`; contract fields §1.4 |
| `app/agents/grader/grader.py` | 1 | writes `teacher_overrides={}` at S7 | one-line: empty model instead of `{}` |
| `app/agents/grader/grader_v5.py` | 1 | same | one-line |
| `app/services/override_attribution.py` | 1 | jsonb expansion of the overlay (PR-G6, landed) | path changes to `…->'terminals'` |
| `tests/services/test_graded_test_contract_compiler.py` | 14 | the gate's own suite | update fixtures, do **not** loosen assertions |
| `tests/api/test_revision_flows.py` | 2 | chain carries the overlay verbatim | update fixtures |
| `tests/api/test_graded_test_approval.py` | 1 | approval | update fixtures |
| `tests/agents/test_grader_agent.py` | 3 | empty-overlay assertions | update fixtures |
| `tests/grading_eval_suite/synth.py` | 1 | synthetic drafts | update |

**Total: 44 references across 11 files.** No hit sits in a frozen contract type,
which is why the count being 0 matters: nothing already-approved is reshaped.

### Open decisions

| ID | Decision | Recommendation |
|---|---|---|
| OD-G5.1 | Where `pricer.compose(draft, overlay)` lives | `app/services/pricing.py` per spec, importing the grader's pricer rather than re-implementing it — one pricer, used by grading, `/draft`, `/approve`, the batch feed and the fixture generator. |
| OD-G5.2 | `/approve` on a pricing mismatch | ERROR annotation, never a silent server win (spec §1.6). The teacher reviewed a number; freezing a different one is the §5 catastrophe in miniature. |
| OD-G5.3 | Spec §4's overlay data migration | **Strike it.** The R-2 count is 0; writing an idempotent migration for zero rows is ceremony that will rot. |

### Tests (zero-mock, pure)

`pricer-override-composition` (the 12 §1.7 vectors) · `override-preserves-proposal-provenance`
· `revert-clears-override-and-note` · `approve-rejects-pricing-mismatch` ·
`cw3-rejects-unknown-check-id`. **`overlay-migration-wraps-lists` is struck with
OD-G5.3** — it would test a migration that must not exist.
