# CENSUS B0 — backend grade review (S12)

**Spec:** `PR_SPEC_backend_grade_review.md` §6. **Date:** 2026-08-31.
**Rule:** answers are file+line citations, not recollection. Where the spec's premise
is wrong, the census says so — the spec is then the bug (§0 of the spec itself).

---

## A. Does `grader_v5.py` persist check-level verdicts, `plan_version`, `quote_status`?

**Partly: `plan_version` YES; `checks[]` and `quote_status` NO — the data exists and is
deliberately discarded at one seam.**

The verdicts survive validation and reach the pricer as `AssessedVerdict`
(`app/agents/grader/pricer.py:49-59`) — this is exactly the record §1.1 `Check` wants:

```python
@dataclass(frozen=True)
class AssessedVerdict:
    check_id: str
    verdict: str                              # met | partially_met | not_met
    confidence: float
    basis_he: str
    quote_text: str
    quote_status: Optional[QuoteValidationStatus]   # None when quote_text == ""
```

`price_scope` consumes them and returns `PricedTerminal` (`pricer.py:62-68`), which keeps
**no per-check data at all**:

```python
@dataclass
class PricedTerminal:
    points_awarded: Decimal
    reasoning: str
    confidence: float
    evidence_quotes: List[AnswerQuotation] = field(default_factory=list)
    flags: List[FlaggedOutcome] = field(default_factory=list)
    annotations: List[GradingAnnotation] = field(default_factory=list)
```

and the serialization into the draft (`grader_v5.py:195-207`, `_leaf_fields`) copies exactly
those six fields onto `CriterionOutcome` / `SubCriterionOutcome`. `grep -n "checks"` over
`app/schemas/graded_test_draft.py` and `graded_test_contract.py` returns **nothing**.

`plan_version` IS already on the draft (`graded_test_draft.py:192`), added during FP2.

**Consequence for PR-G1(b):** this is a *plumbing* change, not a modelling one. The check
record is fully computed today and thrown away between `price_scope` and `_assemble`. The
work is: carry per-check rows on `PricedTerminal`, surface them as `TerminalOutcome.checks[]`,
and mirror to the contract. No new model call, no prompt change, no re-grade.

## B. Date of the champion config-switch

**Not scheduled — the switch does not exist in code.** `grading_runner.py:117` constructs the
v3 agent unconditionally:

```python
agent = GraderAgent(numeric_policy=rubric_contract.numeric_policy)
```

There is no `GRADER_MODEL_KEY`, no grader model/plan/prompt setting in `app/config.py`
(`openai_model: str = "gpt-4o"` at `config.py:14` is the only related knob), and no call
into `llm_factory` from the production path. **This is the R-4 pilot-bridge PR, owed since
FP2 and still unbuilt** — PR-G1(a) *is* that PR.

**OD-B1 is already closed by the owner** (ruling 2026-08-31): gemini-3.1-pro, plan
`hobby_tvshow/v3` + `grader-v5.1`. Regression-checked 2026-08-31 (run
`20260830-154903`, k=2): K1 32/32 · K2 1.02% · K4 1.75 · GA-2 0.9053 · $0.3534/test.

**Hold-vs-slip:** no slip risk from evidence — the pin is confirmed and re-verified. The
risk is that the pin's SUT bytes are not reconstructible from git (recorded in RUNLOG);
production must be pinned by *version identity* (model + plan sha + prompt version), which
is what a config seam gives us anyway.

## D. The audit today

**There is no audit.** No emitter, no runner, no table, no writer. Searches over `app/` and
`tests/` for `audit_delta`, `consistency_audit`, `AuditDelta` return zero hits; every `audit`
match in the tree is unrelated vocabulary (the verifier prompt's "absence-audit" rule,
`flagging.py`, `parser_render.py`).

**Consequence for PR-G7:** the spec's stated risk ("if it mutates drafts directly today,
A1 and A4′ are violated") **cannot be true — nothing runs.** G7 therefore builds the *applier*
and the `audit_deltas` table against a producer that does not yet exist. That is coherent
(the applier is pure and testable from fixture deltas) but it must be stated: G7 ships a
mechanism with no live input, and "the guard never fires on the fixture audit deltas"
(phase B3 gate) is a test-fixture claim, not a production claim. **Runtime for 30 tests is
unmeasurable — there is nothing to measure.**

## E. PDF libraries in the image; page-image proxy

**Present** (`requirements.txt`): `PyMuPDF==1.25.5`, `reportlab==4.4.7`, `PyPDF2==3.0.1`,
`Pillow==12.1.0`. **Absent:** WeasyPrint, Playwright, pdfkit, cairo.

**OD-B6 recommendation: PyMuPDF for both halves.** It is already in the image, it can draw
the vector stamp directly onto the original page (no rasterise-and-reflow), and it can
append rendered appendix pages into the same document. reportlab is the fallback for the
appendix if RTL shaping proves inadequate; adding WeasyPrint or Playwright means new system
libraries in the Cloud Run image and is a deliberate decision, not a side effect.

**Page-image proxy — a finding the spec does not anticipate**
(`app/api/v0/transcription.py:299-320`): every page request **downloads the entire PDF from
GCS** and renders on the fly. There is **no cache**. §1.5's `page1_image_url` on 30 batch
cards therefore costs 30 full-PDF downloads per dashboard load. p50 for 30 renders is not
measured (it needs a live batch and is a G8/G9 input, not a P0 blocker), but the shape of
the cost is now on the record and I recommend a page-1 cache be scoped into G8 rather than
discovered during the pilot.

## F. Writers of `draft_json` after `draft` status

**Exactly two, both intentional, both in `app/api/v0/grading.py`:**

| site | line | what it writes |
|---|---|---|
| `save_draft_overrides` (PATCH `/graded_test/{id}/draft`) | `grading.py:662` | rewrites `draft_json.teacher_overrides` only; AI outcomes untouched (docstring, `grading.py:589`) |
| `approve_graded_test` | `grading.py:729` | writes overrides + contract in the one approval transaction |

`manual_edit` (`grading.py:866`) does **not** write an existing row — it copies `draft_json`
verbatim into a **new** row via `extend_chain()`. No other writer exists.

**Consequence for PR-G7:** the applier will be the third writer, and the first that mutates
`scope_outcomes` after `draft`. That is a genuinely new capability and is why `audit.applied_as`
must be written in the same statement as the check it changes.

---

## Discrepancies between the spec and the code (spec is the seam; these need a ruling)

1. **`/draft` is `PATCH`, not `PUT`** (`grading.py:579`). §1.6 says `PUT`. The frontend
   consumes §1 as written, so either the backend adds/moves to `PUT` (breaking the existing
   client) or the spec is corrected to `PATCH`. **Recommendation: correct the spec to
   `PATCH`** — the method is not load-bearing and the existing client works.
2. **Migration head is 017, not 016** (`migrations/017_transcription_jobs_client_file_id.sql`,
   `database.py:140-143`). §4's "next numbers after current head" therefore starts at **018**.
   CLAUDE.md §8 also says head 016 and is stale — that doc fix rides this PR (§16).
3. **`GradedTestOverrides` is a bare alias**, `Dict[str, TeacherOverride]`
   (`graded_test_draft.py:46`), not a model. §1.2 turns it into an object with `terminals`,
   `feedback`, `stamp_position`. The migration in G5 is therefore a *type* change, not just a
   value reshape, and every read site of `teacher_overrides` is in its blast radius.
4. **`TeacherOverride.points_awarded` is REQUIRED** (`graded_test_draft.py:37`). §1.2 makes it
   optional with "exactly one of verdict/points_awarded". Old overlays all carry points, so
   the migration is safe in that direction; the new optionality needs a validator.

---

## Blast-radius index (files this PR will touch, with their current state)

| file | current state | items |
|---|---|---|
| `app/agents/grader/pricer.py` | `AssessedVerdict` has everything; `PricedTerminal` drops it | G1 |
| `app/agents/grader/grader_v5.py` | `_leaf_fields` copies 6 fields; `MAX_CONCURRENT_SCOPES` imported from v3 | G1, G3 |
| `app/agents/grader/grader.py` | `MAX_CONCURRENT_SCOPES = 5`; unbounded `ChatOpenAI` | G2, G3 |
| `app/agents/grader/llm_factory.py` | seam exists, bounded, anthropic `effort` passthrough landed | G1, G2 |
| `app/schemas/graded_test_draft.py` | `plan_version` present; no `checks`/`feedback`; overrides = bare dict alias | G1, G4, G5 |
| `app/schemas/graded_test_contract.py` | `ContractTerminalOutcome` has ai/final points, no checks | G1, G4, G5 |
| `app/services/graded_test_contract_compiler.py` | approval gate; CW-3 on terminal ids | G1, G5 |
| `app/services/grading_runner.py` | hardcoded v3 agent; selection-aware scoring intact | G1, G2 |
| `app/api/v0/grading.py` | PATCH `/draft` (662), approve (729), revisions | G1, G5, G7, G8 |
| `app/api/v0/batch_grading.py` | batch feed; no grading section per §1.5 | G8 |
| `app/schemas/batch.py` | `graded_test_id`/`graded_test_status` only | G8 |
| `app/api/v0/transcription.py` | page proxy, no cache, full-PDF download per page | G8/G9 |
| `app/config.py` | no grader pin knobs | G1, G2, G3 |
| `migrations/` | head 017 | G6..G9 (018+) |
| `app/services/` (new) | `pricing.py`, `look_count.py`, `audit_applier.py` absent | G5, G7, G8 |
| `app/agents/feedback/` (new) | absent | G4 |
| `scripts/gen_grade_review_fixtures.py` (new) | absent; `scripts/dump_openapi.py` exists | G1 |
| `frontend/scripts/gen-api-types.mjs` | exists; TS is generated, never hand-edited | G1 |
