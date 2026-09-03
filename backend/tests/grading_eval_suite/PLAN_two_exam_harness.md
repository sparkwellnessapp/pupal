# PLAN — the two-exam harness (exam-2 instruction, item 6)

**Status: BUILT 2026-09-03** — 93 green in the suite, two review findings fixed (§7).

**Target:** exam 2 is a **data drop, not a refactor**. Acceptance: the hobby_tvshow
regression stays byte-identical.
**Owner steer (2026-09-03):** *"The transcription eval suite already solved this problem — it is
multi-rubric capable, and its registry/resolution design is the reference to follow rather than
reinventing."* This plan follows `transcription_eval_suit/exam_resolution.py` deliberately, and
names where it copies and where the two suites legitimately differ.

---

## 1. What is already right — and therefore not being rebuilt

The census matters, because half of item 6 turns out to be **already done** and rebuilding it
would be the refactor the target forbids.

| Asked for | State | Evidence |
|---|---|---|
| fixture registry | **DONE** | `fixtures/<name>.json` already pairs rubric + transcription + gt by manifest. Its docstring already anticipated this: *"grading is inherently multi-exam, so pairing is a manifest fact, never basename magic across directories"* |
| GT loader | **DONE, exam-agnostic** | `_validate_gt` guards totality/bounds/precision/hash-pin/blind against whatever contract it is handed |
| selection_scoring | **DONE** | `scoring.py` already calls the real `score_with_selection` for BOTH the GT and AI sides, compares the exclusion sets, and has a `[T1-SELECTION]` tripwire. bagrut's choose-4-of-6 needs **no new code** — it needs a **test that proves it**, which no fixture could provide until now |
| expressibility guard | **DONE per fixture** | `_load_plan` runs `expressibility_errors` pre-spend for the bundle it is given |

**What is actually missing is one thing: the exam is a property of the RUN, not of the FIXTURE.**
Exactly the theory the transcription suite falsified.

* `config["plan"]` is a single run-level path (`plans/hobby_tvshow.plan.json` in all 20 configs).
* `runner.py:515` takes run-level provenance from **`bundles[0]`** — with two exams that records
  one plan and silently implies it graded all of them.
* Nothing in a manifest says which exam a fixture answers (`provenance.exam` is free text:
  `"hobby_tvshow (corrected, H1-ratified)"` — prose, never routed on).

## 2. The one guard that already makes a two-exam run IMPOSSIBLE rather than wrong

`_load_plan` refuses when `plan.rubric_contract_sha256 != bundle.rubric_contract_hash`. So today a
hobby plan meeting a bagrut fixture **stops the run loudly** — it does not mis-grade. That is the
honest starting point and it is why this work is additive: I am not fixing a silent corruption, I
am lifting a correct refusal into a correct resolution.

## 3. Design — following `exam_resolution.py`

**Resolution order, per fixture** (the reference's exact shape):

1. **`fixtures/<name>.json` → `exam_id`**, then `config["plans"][exam_id]` — the per-fixture fact.
2. **`config["plan"]`** — today's single path, unchanged. **With one exam this resolves
   byte-identically and every existing config needs zero edits.**
3. neither → the existing v5 refusal.

**Copied from the reference, on purpose:**
* a frozen `ResolvedPlan` carrying `ref` + `sha256` + `exam_id`, with `as_provenance()`;
* the manifest names a **shared** artifact by relative path — never N copies of one plan (the
  two-copies-drift shape that produced GT findings F-1..F-3);
* **every failure is LOUD.** A fixture graded under the wrong exam's plan is a silently wrong
  benchmark, which is worse than a crash.

**Where the two suites differ, and why.** The transcription reference resolves *(exam spec,
profile)*; grading resolves *(plan)* — and grading already has a **content pin** the reference
lacks (`rubric_contract_sha256`). So grading does not need the reference's "two fixtures on one
exam must agree" sha comparison: the plan↔contract pin already enforces it, per fixture, harder.
Not copying that part is deliberate, not an omission.

### 3.1 OPEN DECISION → RESOLVED: two `exam_id` sources

The manifest will carry `exam_id`; the exam-2 GT skeletons **already emit one** (`build_bagrut_skeletons.py`).
Two sources of one fact is the drift shape §0.4 forbids.

**Ruling: the MANIFEST routes; the GT's `exam_id` is CROSS-CHECKED and must agree.** A disagreement
is a loud refusal, same discipline as the D5 hash pin. The GT's copy is not redundant — it is what
makes a GT file self-describing when read alone, and the cross-check is what stops it drifting.

### 3.2 What "byte-identical" can and cannot mean — state it before claiming it

Adding exam-2 files under `benchmarks/`, `plans/` and `fixtures/` **changes `suite_hash` by
construction** — `_hashed_paths()` globs those three directories whole. That is **correct**: the
instrument's corpus grew, and `suite_hash` exists to say so. Papering over it would be the lie.

So the regression is defined on the thing that must not move:

> **`hobby-scores-are-byte-identical`** — re-score the published run
> `20260830-205954_sonnet5-v5` through the new code and compare the **`trials` array** byte-for-byte
> against that run's own committed `results.json`.

That isolates the scoring path (where a silent corruption would live) from provenance (where change
is the point). Provenance additionally keeps every existing key at its existing value when a run
resolves a single exam.

## 4. Build list

| # | Item | State |
|---|---|---|
| 1 | `exam_resolution.py` (new) — `ResolvedPlan`, `resolve_plan`, manifest `exam_id` | ☑ |
| 2 | `fixtures.py` — `FixtureBundle.exam_id`; GT↔manifest cross-check | ☑ |
| 3 | `schemas.py` — `FixtureGT.exam_id: Optional[str]` | ☑ |
| 4 | `runner.py` — `_load_plan` resolves by exam; provenance per-exam, not `bundles[0]` | ☑ |
| 5 | exam-2 fixture manifests (7) + `exam_id` on the hobby five | ☑ |
| 6 | tests (§5) | ☑ |

## 5. Named tests

| Name | Pins |
|---|---|
| `two-exam-corpus-loads` | both exams' fixtures assemble in one process, each against its own contract |
| `plan-resolves-by-exam-id` | a fixture gets ITS exam's plan; the run-level `plan` still works alone |
| `expressibility-runs-per-exam` | the pre-spend guard runs against each fixture's own plan, not `bundles[0]`'s |
| `hobby-scores-are-byte-identical` | §3.2 — the acceptance test |
| `gt-exam-id-must-agree-with-the-manifest` | §3.1 — the cross-check refuses, loudly |
| `selection-scoring-is-exercised-by-a-choose-k-exam` | bagrut is the first fixture that can prove the `[T1-SELECTION]` path |
| `unknown-exam-id-refuses-before-any-spend` | a manifest naming an exam no config plans for |

## 6. Out of scope

* Authoring exam-2 GT or its plan — the owner's session; this harness is what receives them.
* Changing any gate, threshold, scorer, or GT file (§17.7 STOP list).

---

## 7. Review findings — both defects were INTRODUCED BY THE SECOND EXAM

Neither existed while the corpus was one exam. That is the interesting part: both
are guards that were true *for free* under a single-exam assumption and quietly
stopped being true when the assumption went, while their code and their
docstrings stayed word-for-word the same.

### F-1 — "pre-spend" stopped meaning pre-spend · FIXED

`_load_plan`'s docstring promises a refusal "before any spend", and the plan
resolution happened inside `build_agent`, i.e. inside the grading loop. With one
exam that was genuinely pre-spend: the only plan was validated before the only
fixture graded. **With two exams it means an unroutable exam-2 plan is discovered
only when exam 2's turn comes — after every exam-1 fixture has already been paid
for.**

Fixed by hoisting resolution into an explicit **pre-spend gate** over ALL bundles
before the loop, which also removes the duplicated validation pass. Pinned twice:
once behaviourally (the gate is one call, so it cannot half-succeed) and once
structurally (`run_grade`'s source has the gate before the loop).

### F-2 — `suite_hash` did not cover exam 2 at all · FIXED

`_hashed_paths()` globs `benchmarks/`, `fixtures/` and `plans/` — exam 1's
layout. Exam 2 landed its contract and seven transcriptions at the **suite root**
(`compiled_rubric_bagrut.json`, `compiled_transcriptions_bagrut/`), so they were
outside the instrument hash entirely: **the exam-2 contract could change and
`suite_hash` would not move.** Silently — which is the one failure a hash exists
to prevent.

Fixed as the CLASS, not the instance: the hash now covers every artifact any
fixture manifest *references*, wherever it lives, resolved from the manifests
rather than by adding a fourth glob. A third exam dropping files somewhere new is
covered by construction, and layout goes back to being a matter of taste. Missing
referents are skipped rather than fatal — a manifest legitimately points at a GT
the owner has not authored yet, and hashing the instrument is not the place to
enforce R1.

Demonstrated, not merely asserted: mutating `compiled_rubric_bagrut.json` moves
`suite_hash`, and restoring it round-trips.

## 8. What exam 2 still needs from the owner

The harness is done; these are data, and it refuses loudly until they exist.

* **GT** → `benchmarks/gt/bagrut_899371/<student>.gt.json` (skeletons already
  generated). `load_bundle(require_gt=True)` refuses until then — R1 working.
* **A ratified plan** → `plans/bagrut_899371.plan.json`, then one line in a
  config: `"plans": {"hobby_tvshow": …, "bagrut_899371": …}`.

Until both land, exam 2 loads and validates but cannot be graded — which is the
correct state, not a gap.
