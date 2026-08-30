# PLAN — Multi-rubric transcription fixtures (implements / amends BACKLOG **B-30f**)

> **Status: PROPOSAL. Not implemented. Owner-gated.**
> This edits the `/goal`-governed suite (CLAUDE.md §17), so it is plan-first by rule.
> It also proposes a **deviation from the filed B-30f design** (§3, D1) — a named
> protocol, so per CLAUDE.md §0.3 that is surfaced here as an open decision, never a
> silent substitution.
>
> **Diff scope commitment.** Nothing in this plan edits `scoring.py`, `normalize.py`,
> `check_goal.sh`, any `GateConfig` threshold, the `JAVA_BAGRUT` profile's contents, or
> any existing GT file. Those are the §17.7 STOP list. Verifiable as a one-line
> `git diff --stat` assertion in the DoD (§7).

---

## 0. The problem, in Deutsch form (§3.1)

**Data.** The suite must grow past `n=5`. `FLAG_TRUST_MIN_FIXTURES = 10`
([runner.py:72](runner.py#L72), consumed at [:462](runner.py#L462)) means `flag_metrics_trustworthy` is `False` on every run
the corpus has ever produced, and `CorrectionMeasure.trustworthy`
([scoring.py](scoring.py)) is `False` for the same reason — so the trust layer's recall
numbers and the corrector's false-fix kill-criterion are *provisional by construction*.
Growing the corpus is critical-path item 1 in the suite's own roadmap
([docs §14](transcription_eval_suit_docs.md)). The fixtures available to grow it belong
to a **different rubric** than the five seeds.

**Theory under criticism.** *"The exam is a property of the suite."* It is encoded that
way in three places: one `--exam-spec` per run, one hardcoded `JAVA_BAGRUT` profile, one
hardcoded six-key assertion. That theory was true when the corpus was one exam and is
falsified the moment a second one exists.

**Better conjecture.** *The exam is a property of the fixture.* A fixture declares which
exam it answers and which critical-token profile scores it; the runner resolves that
per doc_id; `results.json` records it per record so a mixed-exam run self-describes.

**Criticism of the conjecture.** Is it hard to vary? Yes — the declaration lives in
exactly one artifact per fixture, and its absence falls back to today's behaviour, so
every existing invocation (`check_goal.sh`, the whole RUNLOG history, the eval gate)
stays byte-identical with **zero new files**. Does it introduce new contradictions? One,
and it is consequential rather than technical: adding fixtures to the default glob
changes what the `/goal` STOP gate *means* (§3, D6). That is surfaced, not absorbed.

---

## 1. What I verified (not assumed)

| Claim | Evidence |
|---|---|
| One exam binds the whole run | [runner.py:174-187](runner.py#L174) `load_spec(plan)` → one `ExamSpec`, handed to every fixture at [:249](runner.py#L249), [:268](runner.py#L268), [:274](runner.py#L274) |
| One profile scores every fixture | `JAVA_BAGRUT` imported at [runner.py:41](runner.py#L41), passed at [:253](runner.py#L253), [:262](runner.py#L262), [:278](runner.py#L278), [:279](runner.py#L279) |
| The six-key assertion is per-corpus, not per-fixture | [test_ground_truth.py:107](test_ground_truth.py#L107) `ALL_FIXTURES`, [:135-141](test_ground_truth.py#L135) hardcodes `(1,א)…(2,ג)` for **every** fixture |
| The exam spec is an untracked file | `backend/.gitignore:164` `*.json` swallows `draft.json` **and** all of `configs/*.json`; `git ls-files` confirms neither is tracked |
| `draft.json` is a production artifact shape | It is a rubric `draft_json`; production builds its spec the same way — `two_phase_engine.py:193` `spec_from_rubric_draft_data(rubric_draft_json, …)` |
| Everything below the spec is already exam-agnostic | `spec_targets` ([spans.py:47](../../app/services/transcription/two_phase/spans.py#L47)), the P2 prompt, `keys.normalize_key`, `ground_truth.py`, `check_gt_consistency.py`, `report.py`, `flag_metrics.py` derive structure from the spec/GT — none names an exam |
| `resolve_fixtures` / `load_spec` have no external callers | grep over `tests/`: only [runner.py:378-379](runner.py#L378) and [:572](runner.py#L572) |
| The sibling grading suite already solved this fork | [grading_eval_suite/fixtures.py:5-7](../grading_eval_suite/fixtures.py#L5) — *"paired by a PER-FIXTURE manifest `fixtures/<name>.json` [F3 — **the B-30f lesson pre-applied**: grading is inherently multi-exam, so pairing is a manifest fact, never basename magic across directories]"* |
| The corpora are cross-consumed | `grading_eval_suite/tools/convert_transcription_gt.py` reads `draft_benchmarks/*.md`; `test_fixture_tools.py::FIVE_DOCS` pins the five |

### 1.1 The five blockers, precisely located

1. **Run-level spec.** [runner.py:174-187, 378-379](runner.py#L174).
2. **Hardcoded profile.** [runner.py:41, 253, 262, 278, 279](runner.py#L41).
3. **Six-key test.** [test_ground_truth.py:135-141](test_ground_truth.py#L135).
4. **`results.json` cannot say which exam scored a record** — a mixed run is
   un-auditable, and `report.py`'s per-doc table would silently merge two exams into one
   scoreboard.
5. **`.gitignore` swallows the exam artifact.** Pre-existing; it becomes *load-bearing*
   the moment the spec is per-fixture provenance rather than a CLI argument.

`check_goal.sh` needs **no edit**: `GOAL_EXAM_SPEC=draft.json` survives untouched as the
fallback (§3.2), which is exactly why the fallback exists.

---

## 2. Non-goals

- No change to what the instrument measures. No new metric, no threshold move, no
  profile-content edit. If exam B fails the gate, **that is a result** (§6, D6).
- No restructuring of `raw_benchmarks/` / `draft_benchmarks/` / `pdfs/` into
  per-exam subdirectories. It is the eventually-correct shape, but it moves the owner's
  GT files and invalidates every path in the docs, the RUNLOG and the sibling suite —
  disproportionate blast radius for the benefit. Filed in §8, not done.
- No new fixtures for the *grading* eval suite (its `FIVE_DOCS` list is explicit and
  unaffected). Named as a follow-on in §8.

---

## 3. Decisions (surface, don't decide — §3.5)

> **Owner rulings, 2026-08-28 (Noam).**
> **D1 — AMENDED.** The hybrid (`exams/` + optional `fixtures/<doc_id>.json` manifest) is
> ratified; B-30f's `specs/<doc_id>.json` copy-per-doc is superseded. BACKLOG B-30f is
> amended to match, not closed as-filed.
> **D2 — COMMIT.** The four `.gitignore` un-ignore lines land.
> **D4 — COMMIT.** New student GT may be committed to the tracked benchmark folders.
> **D5 — `JAVA_BAGRUT`, unchanged.** Exam B is an Israeli CS exam in C#; manifests omit
> `profile`. One caveat carried forward — see the D5 entry.
> **D3 — OPTION A**, plus a new hard requirement: the suite must support **selection
> rubrics** ("answer 4 of 6"), which is exam B's structure. See D3 for why the two
> compose, and for the three consequences that fall out.
> **D6 — sequencing accepted:** exam B is measured diagnostically before any decision
> about admitting it to the STOP-gate partition.
>
> **Phase 1 is IMPLEMENTED and green** (148 passed / 1 skipped). Two findings surfaced
> during it — **D7** (exam B's q1 is unroutable) and **D9** (no GT convention for trace
> tables) — both due before Phase 3, neither blocking what has shipped.

### D1 · The declaration mechanism — **amend B-30f** — ✅ **RULED: amended**

B-30f as filed
([PLAN_model_registry_normalization.md §9](../rubric_eval_suite/PLAN_model_registry_normalization.md))
specifies `specs/<doc_id>.json` — a **full spec copy per document**, on the grounds that
a manifest "would be a second registry of facts the directory tree already states."

That rationale is right about *pairing* and wrong about *exams*. The tree states
`doc_id → {pdf, raw GT, draft GT}`. It does **not** state `doc_id → exam`, and it cannot:
that is a fact about the paper, not the filesystem. Something must carry it.

Under B-30f, N students of one exam carry **N byte-identical copies** of a ~26 KB rubric
`draft_json`. Two copies of one fact that drift is precisely the defect class this corpus
has already been burned by — F-0 through F-3 in
[GT_ARTIFACTS_REPORT.md §8](GT_ARTIFACTS_REPORT.md) are all "raw and draft were edited
independently and drifted," and the §2 discipline in
[TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md) exists to forbid
exactly that shape. A divergence between two fixtures' spec copies would be **invisible**
in today's `results.json`.

The sibling grading suite reached this fork first and ruled the other way, in writing, in
its own module docstring — *"the B-30f lesson pre-applied … pairing is a manifest fact,
never basename magic across directories."* It ships `fixtures/<name>.json` naming shared
artifacts by relative path, with `sha256` pins and a `provenance` block.

**Recommendation — the hybrid: B-30f's *fallback semantics*, F3's *manifest shape*.**

```
transcription_eval_suit/
  exams/<exam_id>.json         # NEW — the exam artifact, one per exam (rubric draft_json
                               #       copy, or canonical harness spec). Shared by N fixtures.
  fixtures/<doc_id>.json       # NEW — per-fixture manifest. OPTIONAL.
  pdfs/<doc_id>.pdf            # unchanged
  raw_benchmarks/<doc_id>.md   # unchanged
  draft_benchmarks/<doc_id>.md # unchanged
```

```jsonc
// fixtures/<doc_id>.json
{
  "exam_spec": "exams/hobby_tvshow.json",   // required; relative to the suite dir
  "profile": "java_bagrut",                 // optional; default "java_bagrut"
  "provenance": {                           // free-form, never read by the runner
    "exam": "תשפ\"ו כיתה יא' מחצית ב' מבחן 1",
    "rubric_source": "rubrics.id=0b621e6d-…  (draft_json export)",
    "exam_spec_sha256": "…",
    "authored": "2026-08-28"
  }
}
```

The manifest states **only what the tree cannot** — exam, profile, provenance. It does
*not* restate `pdf`/`raw`/`draft` paths; those stay basename convention exactly as today.
That is the direct answer to §9's objection: this is not a second registry of tree facts,
it is the one fact the tree is silent about.

*Alternative if the owner prefers to hold the line on B-30f as filed:* `specs/<doc_id>.json`
full copies, plus (mandatory, to close the drift hole B-30f leaves open) a per-record
`exam_spec_sha256` in `results.json` and a pure test that reports the distinct spec hashes
in the corpus. Everything else in this plan is unchanged — only the resolver's second
line differs.

*Sub-decision (naming):* `fixtures/` matches the sibling suite and the suite's own
`--fixtures` / `Fixture` vocabulary. `manifests/` is unambiguous but idiosyncratic.
Recommend `fixtures/`.

### D2 · Commit the exam artifacts (`.gitignore`) — ✅ **RULED: commit**

`backend/.gitignore:164` `*.json` currently makes `draft.json` and every `configs/*.json`
untracked. **The `/goal` STOP gate's default invocation therefore depends on a file that
does not exist in a fresh clone.** With the spec becoming per-fixture provenance, that hole
stops being cosmetic.

Two un-ignore precedents already exist in the same file — `!tests/rubric_eval_suite/benchmarks/*.json`
(:172) and `!tests/grading_eval_suite/{configs,fixtures,benchmarks}/…` (:176-178), both
justified as *"SOURCE … NOT eval output."* The exam spec, the configs and the manifests are
the same category.

**Recommendation:** add

```
!tests/transcription_eval_suit/exams/*.json
!tests/transcription_eval_suit/fixtures/*.json
!tests/transcription_eval_suit/configs/*.json
!tests/transcription_eval_suit/draft.json
```

**Privacy note:** exam specs are *teacher rubric* content, not student data. This adds no
exposure class beyond the student GT already tracked in both public remotes
([GT_ARTIFACTS_REPORT.md F-5](GT_ARTIFACTS_REPORT.md)). It is still an owner call, and it
is a *smaller* one than D4.

### D3 · A question the student skipped — ✅ **RULED: Option A (emit the key, empty body)**

**Ruling (Noam, 2026-08-28):** the blank question gets its `=== Q.. ===` block with
an empty body. **And the suite must handle SELECTION rubrics**, where the student answers
only a declared subset — which is the structure of exam B
(`bagrut_899371`: `selection_groups: [{choose_k: 4, of_question_ids: [q1..q6]}]`).

That combination is what makes Option A the right call rather than merely a valid one.
Under a choose-4-of-6 exam, whole unanswered questions are the *norm*, not an anomaly, so
the two options behave very differently:

- **Option A (ruled).** Gold carries every declared key; the unanswered ones are empty. The
  span contract emits **every spec target's key regardless** — an unassigned target becomes
  an empty answer ([spans.py:210-214](../../app/services/transcription/two_phase/spans.py#L210);
  the unparseable path likewise returns `{t.key: "" for t in targets}`). So coverage holds
  at 1.0 structurally, empty gold meets empty prediction and scores 1.0, and the
  critical-token clauses are vacuous. **And a model that INVENTS content for a question the
  student never answered scores 0.0 on that answer and is flagged `is_error`** — a sharp,
  correct signal.
- **Option B** would have put exactly that invention into `extra_keys`, where it dilutes the
  document ratio slightly and *fails nothing*. On a selection exam — where 2 of 6 questions
  are always blank — that is the difference between catching hallucinated answers and
  systematically hiding them.

Consequences recorded, not designed around:

1. **`spec_keys` == `spans.spec_targets`.** GT is authored against the first, P2 is asked
   for the second; they must not drift, and a test now pins it. A question with no
   sub-questions (exam B's q6) contributes one whole-question key `(6, None)`.
2. **A selection exam costs a second P2 call, every document.** `parse_and_slice` records
   an unassigned target as a `problem`, which triggers the one targeted re-request; the
   legitimately-unanswered questions can never be assigned, so the map is never `ok` and
   every doc lands via the deterministic salvage with routing notes. It *works*, but it is
   noisy and pays a call. Making P2 selection-AWARE (or teaching the span contract that a
   target may be a declared skip) is the obvious fix and is a **separate single-variable
   experiment** (§17.3) — measured in Phase 4, not bundled here.
3. **Legacy P2 contract caveat.** The always-emit-every-key guarantee is a property of
   `p2_output_contract: "spans"`. `v0` (the ship config and `check_goal.sh`'s default) uses
   it; `v1_trust` and `v0_p2_correct_spec` still default to `"text"`, where an unanswered
   key may simply be absent and coverage would fail. Selection-exam fixtures are meaningful
   under `spans` configs only until that is addressed.
4. The generalized GT test asserts **equality** with the exam's declared keys (not the
   subset the earlier draft recommended) — which is what mechanically enforces Option A.

### D3 (superseded analysis) · why the question existed

**The situation.** The exam has six answer slots. A student answers five and leaves one
completely blank — no ink at all. When you write that student's `draft_benchmarks/<id>.md`,
do you write a header for the blank one or not?

**Option A — write the header, leave the body empty.** The file has six blocks; one is
empty. The scorer then counts six *gold keys*, and `coverage = matched keys / gold keys`
demands the model produce all six. So the model must **explicitly report the blank
question as empty**. If it instead stays silent about it — the natural thing to do when
there is nothing on the page — coverage drops below 1.0 and the fixture fails the gate
forever, through no fault of the transcription.

**Option B — omit the block entirely.** The file has five blocks. If the model emits a
sixth key anyway (stray ink routed there), that key lands in `extra_keys`: it dilutes the
document ratio slightly but does **not** fail coverage.

**So the real question is a product question, not a formatting one:** facing a question
the student never answered, must the transcriber *say so explicitly* (A), or is silence
acceptable (B)? [Conventions §5.3](TRANSCRIPTION_GT_CONVENTIONS.md) leaves it open and
forbids the GT author from picking; `score_document` has no special handling for an empty
gold answer either way.

**Why it appears in this plan at all:** §4.3's new test compares a fixture's GT keys
against its exam spec's keys. Under A they are equal (6 = 6); under B the GT is a strict
subset (5 ⊂ 6). The test has to assert one or the other.

**Superseded by the ruling above (Option A).** Kept because it states what the two options
mean, which the ruling assumes.

### D4 · Privacy ruling for the new student GT — ✅ **RULED: commit**

§1.3 of the conventions requires an explicit owner ruling before new student GT is
committed, because both benchmark folders are tracked and pushed to two **public**
remotes. **Granted (Noam, 2026-08-28):** exam B's `raw_benchmarks/` and
`draft_benchmarks/` files are committed on the same terms as the existing five. PDFs stay
gitignored (`*.pdf`), unchanged. Phase 3 is unblocked.

### D5 · Does exam B need a new `CriticalProfile`? — ✅ **RULED: no — `JAVA_BAGRUT`, unchanged**

> **What a `CriticalProfile` is, for a reader meeting it here first.** The headline
> accuracy number is a difflib character-overlap ratio, and it is blind in a specific,
> dangerous way: a transcription can be 99.6% character-identical to the truth and still
> be wrong in the only way that matters — `==` read as `=`, a dropped `;`, `GetRate` read
> as `GetRates`, `CW` expanded to `Console.WriteLine`. Each is one or two characters out
> of hundreds, invisible to the ratio, and each one is a Bagrut deduction. The suite has a
> worked case: a **0.9959-ratio document carrying three grading-critical errors**
> ([scoring.py](scoring.py) header).
>
> So the gate is a **conjunction**, and its second half ignores bulk entirely: extract from
> each answer only the tokens that can change a grade — a *signature* — and compare gold
> against prediction on that signature at **recall 1.0, zero misses tolerated**. A
> `CriticalProfile` is simply *the list of which tokens those are for a given subject*:
> `operators` (`==` `!=` `&&` `++` `=` …), `structural` (`;` `{` `}` `(` `)` `[` `]`),
> `abbreviations` (`CW`, `CR` — legitimate Bagrut shorthand whose expansion both corrupts
> the text and erases a deduction), and `keywords` (C# reserved words whose letter-case is
> *not* graded, so `For` and `for` compare equal).
>
> It is a separate object so the scoring engine stays subject-agnostic (CLAUDE.md §3.3):
> `scoring.py` never knows a language, it just reads the profile handed to it. A future
> vertical is a new profile and zero engine change — which is exactly the mechanism this
> plan makes per-fixture.

Exam B is an Israeli CS exam in C#, the same subject and language the profile was built
for. Its manifests omit `profile` and inherit the default. No profile is written, and
`JAVA_BAGRUT` is not edited.

**One caveat carried into Phase 4, not acted on now.** `JAVA_BAGRUT.abbreviations` is
`("CW", "CR")`, seeded from `moran_aharon` with the standing comment *"Grow as fixtures
reveal more standard Bagrut shorthands"* ([critical_tokens.py:97](critical_tokens.py#L97)).
If exam B's students use a shorthand outside that pair, its expansion by the model is
**undetectable** — the gate's `abbreviations_altered` clause simply never fires for it, so
the transcription silently loses both the student's text and a Bagrut deduction. That is a
**finding to surface with evidence after the GT is authored**, never a pre-emptive edit:
`critical_tokens.py` is STOP-listed (§17.7), and widening the vocabulary changes what the
instrument measures for the existing five as well.

### D6 · When does exam B join the `/goal` STOP-gate partition? — ⏳ open (a Phase-4 decision)

> **Correction to the first draft of this plan.** It said the gate "can never exit 0" if
> exam B does not clear. That was wrong and overstated. Exit 1 is the gate's ordinary,
> productive verdict, and the loop has its own breakers for an unfixable failure (below).

**How it works, and how exam A's failures worked.** `check_goal.sh` is the `/goal` loop's
stop condition, not a build check: **exit 0 = the loop may stop, exit 1 = keep iterating.**
Every unsuccessful exam-A run exited 1 — that is the normal state — and the loop did its
job: change one variable, re-test cheaply with `p2_only`, spend the expensive gate only
when the cheap signal says it will likely pass. Exit 1 was productive there because the
failures were reachable by the levers the loop is allowed to pull (§17.10 — P1/P2 prompts,
configs, the corrector): the per-sub-question content signatures fixed omer's Q2 ב↔ג swap,
the anti-dump guard fixed moran's input dump, and so on.

**What actually changes when exam B lands.** The fixture set is whatever
`raw_benchmarks/*.md` globs and §17.1 makes the gate the full partition — you cannot pass
by fixing a subset. So:

1. **~2× cost and wall-clock** on the authoritative run (10 fixtures × k=5, and P1 is the
   slow image-heavy call).
2. **The gate goes back to red, and stays red until exam B is also cleared.** That is
   correct — the benchmark got harder and more honest — but it means the "we're done"
   signal is withdrawn the moment the files land, before anyone has seen a single number
   from exam B.
3. `flag_metrics_trustworthy` flips to `True` at n≥10, changing how every trust-layer
   number in `summary.md` should be read.

**And if exam B has a failure the loop's levers cannot reach?** The loop does not spin
forever — it surfaces. §17.8 fires the moment a prompt change fixes one doc and breaks a
previously-working one ("the prompt surface is exhausted"), and §17.9 fires after three
iterations without worst-doc improvement. Both hand the decision — typically "escalate the
model tier" — back to you. So the risk is not an infinite loop; it is spending expensive
gate runs to discover something one cheap diagnostic run would have told you first.

**Recommendation — sequence, not quarantine.** Land exam B's files, then run the cheap
`p2_only --repeats 5` and one full `check_goal.sh` **as a diagnostic** (§6 Phase 4) and
read the numbers before deciding anything. If you then want exam B held out of the default
partition while it is worked on, the honest mechanism already exists and is already
documented: set `GOAL_FIXTURES`. **Never** edit `check_goal.sh` — it is STOP-listed
(§17.7), and a gate that quietly excludes its hard cases is not a gate.

---

### D7 · RESOLVED 2026-08-29 — the content is there; the PARSER FIX is still the answer

**Test run (owner-directed):** fed `rubric_eval_suite/fixtures/bagrut_899371.docx` to the
live `docx_v3` pipeline (`EXTRACTION_PROMPT_VERSION=3.10.0-fixsource`, gpt-5.6-terra/high),
207 s, 2 retries, 59.7k/29.6k tokens. Artifact kept in the scratchpad, **not** landed.

**Answer to the question asked — yes, the Q1 text IS in the DOCX.** The fresh draft gives
Q1.א a 494-char text naming `Check` and Q1.ב a 329-char text naming `What`; `BLIND: none`.
So the blindness is *not* an irrecoverable property of the rubric.

**But the fresh draft is a WORSE artifact and was not placed.** It fixes Q1's text and
regresses Q1's structure and points:

| | stale GT (rubric-suite, human-ratified) | fresh extraction |
|---|---|---|
| q1 total | **25** | **40.0** |
| q1.א | 15 → children (1:12, 2:3) | 12.0 → children (1:3.0, 2:0.5) **+ 1 direct criterion** |
| q1.ב | 10 → children (1:6, 2:4) | 6.0, **children dropped entirely** |
| rubric total | **100** (6×25 offered, choose 4) | **115.0** |
| compiles? | fails on **1** (the known teacher `point_sum_mismatch` at q1.א.2) | fails on **4** |
| Q1 routable? | no | yes |

It also violates StructureExclusivity (`q1.א` carries criteria *and* children) — the
pipeline warned and shipped it anyway. 115 is not a reachable bagrut total.

**The right fix is the one originally proposed, applied to the GOOD artifact.** Composing a
text-less depth-1 sub-question's signature from its children — the three-line change to
`spec_from_rubric_draft_data` — was run against the stale GT and **measured**:

```
q1.א  own=EMPTY -> composed [711] methods=['Check']
q1.ב  own=EMPTY -> composed [345] methods=['What']
BLIND after composition: none        keys unchanged (11)
```

So the structurally-correct artifact becomes fully routable with **no re-extraction, no GT
edit, and no regression**. It remains a PRODUCTION change (any nested rubric transcribes
blind today) and therefore still wants its own review — but it is now proven, not proposed.

**Correction to this section's first draft (owner, 2026-08-29).** It judged the extraction
by "does the raw draft compile", and that is the wrong bar. A draft is *supposed* to carry
the teacher's errors; the product is capture → surface → one-click fix → teacher accepts →
*then* it compiles (FC, CLAUDE.md §2). Measured: neither artifact compiles in one pass, and
each proposed fix opens the next level's mismatch (the stale GT's `set_points q1.א.2 → 2.0`
leaves `q1.א` at 14 vs 15) — which is the cascade the review UI runs, not a defect.
**Compilability of a raw extraction is not an extraction-quality metric.**

**What survives that correction is one specific misreading, and it is not about sums.**
Rendering the DOCX shows why:

```
line 42:  פרק ראשון (40 נקודות)      <- a CHAPTER header
line 44:  שאלה 1
line 17:  … (100 נקודות) יש לענות על 4 שאלות מתוך 6 … כל שאלה - 25
```

The extractor attached the **chapter's** 40 to Question 1, while the exam header states
plainly that every question is 25. The ratified GT says 25; the document says 25.

This matters more than an ordinary miss because **`total_points` is the grading denominator
and the fix machinery cannot recover it**: the pipeline's own warning reads *"Do NOT change
Q1.total_points — it is set by the document header and is authoritative"*, and the
`point_sum_mismatch` proposals then drive the teacher to reallocate sub-question points
*toward* 40. The surface-and-propose loop is only as good as the anchor it trusts, and here
the anchor is wrong. Worth a precise line in the RUBRIC suite's RUNLOG — chapter-level
point headers are a distinct confusion class from question-level ones. Not this suite's fix.

**Also on the record:** exam B's rubric carries a real teacher point error (q1.א.2: criteria
2.0 vs declared 3), faithfully captured. Irrelevant to transcription (production feeds
`rubric.draft_json`, uncompiled) but live if exam B is ever wanted for the grading suite.

### D7 (original analysis) · how the gap was found

Found by resolving the real artifact, not by inspection. `exams/bagrut_899371.json` yields
11 keys — `(1,א)(1,ב)(2,א)(2,ב)(3,א)(3,ב)(4,א)(4,ב)(5,א)(5,ב)(6,None)` — and Q2–Q6 carry
rich routing signatures (`IsMirror`, `ArrangeMirror`, `DiceStatistics`, `PrintStatistics`,
`TotalEarnings`, `TopEarners`, `IsSimilarWorkshop`, `HandleNewWorkshop`). **Q1 carries
none:**

```
Q1  context[0]: ''
   .א  signature[0]: ''
   .ב  signature[0]: ''
```

Cause: Q1 nests **two levels** (`q1 → א → {1,2}`). Its depth-1 nodes carry `"text": null`
because the content lives one level down, and `parsing.spec_from_rubric_draft_data` reads
depth 1 only. Q1's own `question_text` is `null` too, so the context is empty as well. P2
would route 25 points of that exam by guessing order — the exact failure the signature
machinery was built to prevent (the omer Q2.ב↔ג swap).

**This is a PRODUCTION gap, not an eval one:** production builds its spec through the same
function (`two_phase_engine:193`), so any nested rubric transcribes blind today.

**Proposed fix (small, additive, its own review):** when a depth-1 sub-question has no text
of its own but does have children, compose its signature from theirs — three lines in
`spec_from_rubric_draft_data`. It changes what P2 receives for nested rubrics in
production, so it is not folded into an eval-plumbing PR.

**Gate, already in place:** `test_every_in_use_exam_gives_p2_a_routing_signature` asserts
every sub-question of every **in-use** exam has a non-empty signature. It scopes itself to
exams a `fixtures/<doc>.json` manifest actually points at, so it passes today and starts
failing the moment exam-B fixtures are landed with Q1 still blind. **You cannot land exam
B's fixtures while P2 is blind on Q1** — which is the correct order.

### D8 · Should P2 be told the exam is choose-k? ⏳ Phase-4 experiment, not now

`selection_groups` is now **recorded** (results.json provenance + a summary line), which
changes no prompt and no score. Making P2 selection-*aware* would change model behaviour
and is therefore one variable, one experiment (§17.3), motivated by the measurement in D3
consequence 2 (every selection-exam doc currently burns a second P2 call). Two candidate
levers, cheapest first: teach the **span contract** that a target may be a declared skip
(deterministic, harness-side, `spans.py`), or teach the **prompt** (stochastic). Measure
before choosing.

### D9 · Trace-table convention — RESEARCHED 2026-08-29, recommendation below

Exam B's Q1.א.1 and Q1.ב.1 ask for **trace tables** (the rubric scores "17 cells, 0.7
each"). Every existing fixture is pure code, and nothing in the conventions or the parsers
says how a handwritten grid becomes GT text. Researched across all three surfaces; the
numbers below are measured on the real bagrut Q1 table, not argued.

#### What the stack already fixes

- **P1 emits no markers by contract.** `P1_SYSTEM`: *"Page text is PLAIN TEXT only: no
  markdown, no strikethrough syntax, no code fences."* The pipe grid a handwritten table
  arrives as is the model's **emergent** convention, not an instructed one. The prompt says
  nothing about tables at all.
- **The review surface already renders them.** `utils/detect-pipe-tables.ts` +
  `TranscribedAnswerView` — a second detector written specifically because the rubric
  mirror's two (`parseMarkdownText`, needs a `[TABLE]` marker; `detectTableRuns`, splits on
  whitespace) both miss the transcription shape. It documents the observed reality: *"bare
  rows, no marker, no separator, and RAGGED."* Direction is pinned `ltr` (owner-ruled
  2026-08-23). Ragged rows are padded **at the end only** (FC).

#### Measured — what each candidate costs

**(a) Fabricated critical tokens** (gate: `structural_recall == 1.0`, `operator_recall == 1.0`):

| convention | structural | operators | fabricated? |
|---|---|---|---|
| `[TABLE 1: 6x5 ltr]` + `\|---\|` + rows | 10 | 10 | **+2 structural** (the marker's `[` `]`) and **+5 `--` operators** (the separator's dashes read as DECREMENT) |
| bare bounded pipes | 8 | 5 | none — all 8/5 are the student's own `arr[i]` / `!=` / `==` / `%` |
| bare ragged pipes | 8 | 5 | none |
| whitespace grid | 8 | 5 | none |

`|` is in **neither** the operator nor the structural vocabulary, so **pipes are free**.
But `||` — two *adjacent* pipes, i.e. an unpadded empty cell — **is** the logical-OR
operator and injects one fabricated token per occurrence.

**(b) Cross-format ratio** (gate: `doc_ratio_strict ≥ 0.98`), gold vs a faithful reading in
another convention:

|gold ＼ pred|marker|bounded|ragged|whitespace|
|---|---|---|---|---|
|marker|1.0000|0.8512|0.8170|0.5701|
|bounded|0.8512|1.0000|**0.9648**|0.6742|
|ragged|0.8170|0.9648|1.0000|0.7018|
|whitespace|0.5421|0.6742|0.7018|1.0000|

**Every mismatch fails.** Even the closest pair — bounded vs ragged, differing only in edge
pipes — is 0.9648, under the gate. *The GT convention is not a style choice: it must be
exactly what P1 emits, or every table answer fails for pure format reasons.*

**(c) `normalize()` deletes all whitespace**, so a space-aligned grid collapses to
`608f--15f--24f--315f--43tt` — every column boundary gone. Whitespace grids are
disqualified for tables (they remain fine for the array index/value rows already in the
corpus, which `detectTableRuns` owns).

**(d) What the real frontend detector does** (measured against `segmentAnswerText`):

| input | rendered |
|---|---|
| `\| a \| b \|` space-padded, bounded | ✅ table, 6×5, header detected |
| `[TABLE…]` + separator + rows | ⚠️ table, but the marker line survives as a **stray text segment** above it |
| ragged (what P1 emits today) | ⚠️ table, but **7 columns instead of 5** — mixed edge pipes shear the grid |
| `\|a\|b\|` unpadded | ❌ **not a table** — the `\|\|` from empty cells trips the code-token guard; renders as `<pre>` |

#### Recommendation

**The convention: bare, space-padded, fully-bounded pipe rows. One row per line. No marker,
no separator row. An empty cell is `\|  \|` — never `\|\|`.**

```
| x | i | arr[i] | arr[i]!=1 && arr[i]!=x && x % arr[i]==0 | ערך מוחזר |
| 6 | 0 | 8 | F |  |
|  | 1 | 5 | F |  |
|  | 4 | 3 | T | T |
```

Each rule earns its place:

- **No `[TABLE]` marker** — it is ink the student never wrote, P1's own prompt forbids
  markdown, it costs 2 structural tokens at recall 1.0, and the surface leaves it as stray
  text above the grid.
- **No `|---|` separator** — costs **5 fabricated `--` (decrement) operators**, and the
  surface infers the header without it (an all-non-numeric first row).
- **Pipes, not whitespace** — whitespace is normalized away; pipes survive and cost nothing.
- **Always space-pad** — the one rule that must be stated explicitly, because `||` fails
  **twice independently**: a fabricated `||` operator on the gate, *and* a code-token that
  makes the surface refuse to render the table at all.
- **Bound both edges on every row** — `splitCells` strips edge pipes only when *every* row
  is bounded; consistent bounding yields an exact rectangle, while today's ragged output
  sheared a 5-column table into 7.

#### The load-bearing half: pin it in the P1 PROMPT, do not just document it

Because a format mismatch fails the gate (0.9648 < 0.98) and P1's shape is currently
*emergent*, a GT-side-only convention would be a coin flip per document. P1 prompts are
explicitly a permitted lever (§17.10 — they change model behaviour, not the ruler). One
added rule makes all three parties agree by construction:

```
- A hand-drawn table (e.g. a trace table) is transcribed one row per line: cells
  separated by " | ", with a leading "| " and a trailing " |" on every row. Write an
  empty cell as two spaces between pipes — NEVER two adjacent pipes. Do not add a
  header separator line, and do not add any table marker.
```

Then GT is authored in exactly that shape and `TranscribedAnswerView` already renders it.
This is **one variable** → its own `p1_only` run at k≥5 on the exam-B table pages, before
any GT is authored (§17.3/§17.5).

#### NON-UNIFORM TABLES (owner caveat, 2026-08-29) — the rule that makes them work

Real trace tables are sparse: a 4×4 grid whose 4th column carries one value has 10 filled
body cells, not 12. The convention must express that, and it does — but only if one thing
is stated as a hard rule:

> **Rectangular by construction. Every row carries exactly one cell per column. A cell with
> no ink is written EMPTY (`|  |`) — never omitted.**
>
> The *grid* is uniform; the *content* is sparse. Non-uniform ink is empty cells, never
> missing cells.

Measured against the live detector, this is not a preference — omitting a cell corrupts the
table, and how badly depends on *where* the gap is:

| the student's sparse column is… | rendered result |
|---|---|
| written as **empty cells** (the rule) | ✅ exact 4×4; every value under its own header |
| omitted, and it is the **last** column | ⚠️ 6 columns instead of 4 — two phantom columns, whole table offset |
| omitted, and it is the **first** column | ❌ **silent shift** — `\| 1 \| 5 \|` renders `1` under `x` and `5` under `i`, when the ink says `i=1, arr[i]=5` |
| omitted, **mid-table** | ❌ same silent shift |

The third row is the bagrut Q1 shape exactly: `x` is column 1 and is written once, so every
subsequent row is short at the FRONT. `buildTable` pads at the END, so **every value in
every sparse row is displayed under the wrong header, with nothing to indicate it.**

`detect-pipe-tables.ts` states the right principle in its own docstring — *"where the
missing cell BELONGS is unknowable from the text, and guessing it is the silent relocation
the product exists to refuse"* — and then end-pads, which **is** a guess about where it
belongs. This is §3.5a's named failure: a degradation that keeps computing produces
something that still looks like an answer. The teacher is reviewing against the source PDF,
so a shifted grid actively misleads her at the one moment she is checking correctness.

**Recommended sequence (order matters — reversing it regresses the live product):**

1. **Pin P1's prompt** to emit rectangular rows with explicit empty cells (the rule above).
   Today's raggedness is emergent, and `detect-pipe-tables.ts` records it as "the norm".
2. **Measure** with a `p1_only` k≥5 run on the exam-B table pages that P1 now complies.
3. **Then tighten the renderer**: a run whose rows disagree in cell count should NOT be
   tableized — fall back to the `<pre>` the module already uses as its honest fallback.
   After step 1 a short row means *the transcription is incomplete*, which is exactly the
   thing worth showing rather than papering over.

Until step 3, ragged input renders shifted. That is a **live defect on the transcription
review surface today**, independent of exam B — worth its own decision on urgency.

#### Residual risks to record, not solve

- A student's own `||` inside a cell breaks the surface's table detection (code-token
  guard). Rare, real, and the honest fallback (`<pre>`) is acceptable.
- Cells longer than 12 chars count against `shortCellRatio ≥ 0.7`; bagrut's 38-char
  condition header is 1 of 30 cells, so it passes — a table of long cells would not render.
- **A trace table's correctness is per-CELL, but difflib scores a flattened string.** One
  dropped empty cell shifts the whole row. Table fixtures will be the noisiest in the
  corpus. Fixing that means changing the instrument, which is STOP-listed — so it is
  recorded here as a known limit, not designed around.
- A cross-pinned fixture (the `segmentation-check.ts` TS-mirror precedent) should pin the
  same table text on both sides, so the GT convention and the renderer cannot drift.

---

## 4. The design

### 4.1 Resolution — one function, loud on every failure

```python
# runner.py
@dataclass
class Fixture:
    doc_id: str
    pdf_path: Path | None
    raw_gold: GoldPageDocument | None
    draft_gold: GoldDocument | None
    exam_spec: ExamSpec | None       # NEW — resolved per fixture
    profile: CriticalProfile         # NEW — resolved per fixture
    exam_spec_ref: str | None        # NEW — provenance: what path was resolved
    exam_spec_sha256: str | None     # NEW — provenance: content pin
```

Per `doc_id`, in order:

1. `fixtures/<doc_id>.json` exists → load it; `exam_spec` is **required** (missing key →
   `ValueError` naming the file); resolve the path relative to the suite dir (missing
   target → `FileNotFoundError`); `profile` optional, defaults `"java_bagrut"`, unknown
   key → `ValueError` listing the known keys.
2. no manifest → the run-level `--exam-spec` (**today's behaviour**, byte-identical) with
   the default profile.
3. `mode == "p1_only"` and neither → `None`, as today (P1 needs no spec).
4. `mode in {per_doc, p2_only, batch}` and neither → the existing loud
   `ValueError(f"mode={mode} requires --exam-spec.")`, now naming the doc_id.

Spec **loading** keeps today's exact tolerance: `load_exam_spec` first, falling back to
`spec_from_rubric_draft` on `(ValueError, KeyError)` ([runner.py:183-187](runner.py#L183)) —
so both the canonical harness shape and a raw rubric `draft_json` drop in, unchanged.

Resolution lives **inside `resolve_fixtures`**, whose signature becomes
`resolve_fixtures(plan: RunPlan) -> list[Fixture]`. This matters: `run_plan` calls it a
second time at [:572](runner.py#L572) to write the per-doc reports, and both call sites
must agree about which exam scored which doc. `load_spec` collapses into it.

### 4.2 The profile registry — a **new** module, so a STOP-listed file stays untouched

```python
# profiles.py  (NEW, ~15 lines)
"""Name -> CriticalProfile. Same role models_registry.py plays for models:
one place that rots, loud failure on an unknown key."""
from .critical_tokens import JAVA_BAGRUT, CriticalProfile

PROFILES: dict[str, CriticalProfile] = {"java_bagrut": JAVA_BAGRUT}
DEFAULT_PROFILE = "java_bagrut"

def profile(name: str) -> CriticalProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            f"unknown critical-token profile {name!r}; known: {sorted(PROFILES)}"
        ) from None
```

B-30f proposed putting this dict *inside* `critical_tokens.py`. That file is on the §17.7
STOP list by name. A separate module gets the identical behaviour with a **zero-line diff
to a STOP-listed file** — and it matches the suite's own precedent, where the model
registry is its own module rather than living inside the thing it names.

`runner.py` then imports `profile` instead of `JAVA_BAGRUT`, and the four scoring sites
take `profile=fx.profile`.

### 4.3 Tests — replace the hardcode with something *stronger*

`test_ground_truth.py:135-141` asserts six literal keys for every fixture. Replace with a
**spec-conformance** assertion, which is generic *and* checks something nothing checks
today (that a fixture's GT keys agree with the exam it claims to answer):

```python
def test_every_draft_fixture_conforms_to_its_exam_spec():
    for name in ALL_FIXTURES:
        fx_spec = resolve_exam_spec(name)                 # the runner's own resolver
        spec_keys = [normalize_key((q.number, sq.id))
                     for q in fx_spec.questions for sq in q.sub_questions] or \
                    [normalize_key((q.number, None)) for q in fx_spec.questions]
        gt_keys = [normalize_key(k)
                   for k in load_ground_truth(DRAFT / f"{name}.md").keys_in_order()]
        assert set(gt_keys) <= set(spec_keys)             # D3: subset, order-preserving
        assert gt_keys == [k for k in spec_keys if k in set(gt_keys)]
        assert gt_keys                                    # non-empty
```

Both sides pass through `keys.normalize_key`, so `א`/`a`/`1` label formats never
manufacture a false failure — the same discipline `score_document` already applies.

Plus one new guard that closes the §1.4 half-landed-fixture trap:

```python
def test_all_fixtures_list_matches_the_folder():
    """raw_benchmarks/ IS the runner's fixture registry — a raw GT landing there joins
    every default eval run immediately. Making the list and the folder agree turns a
    half-landed fixture into a loud `pytest -q` failure instead of a silent corpus change."""
    assert set(ALL_FIXTURES) == {p.stem for p in RAW_BENCHMARKS.glob("*.md")}
```

### 4.4 Provenance — a mixed run must self-describe

- `RunRecord` gains `exam_spec: str | None` and `profile: str`.
- `results.json` gains a top-level
  `"fixtures": {doc_id: {"exam_spec", "exam_spec_sha256", "profile"}}`.
- `report.write_summary` prints one `exams:` line always, and adds an **Exam** column to
  the per-document table **only when the run spans more than one exam** — so every
  existing single-exam summary stays byte-identical, and a mixed run cannot quietly read
  as one scoreboard.
- The conjunctive gate is already per-fixture; **no gate arithmetic changes.**
  `check_goal.sh`'s independent per-record read (`by_doc`, per-repeat `gate.passed`)
  keeps working verbatim.

---

## 5. Files touched

| File | Change | Risk |
|---|---|---|
| `profiles.py` | **NEW** ~15 lines | none — additive |
| `runner.py` | `Fixture` +4 fields; `resolve_fixtures(plan)` absorbs `load_spec`; per-fixture `exam_spec`/`profile` threaded to [:249/:268/:274](runner.py#L249) and the 4 scoring sites; `RunRecord` +2 fields; `results["fixtures"]` block | medium — the one real code change |
| `report.py` | `exams:` header line + conditional Exam column | low |
| `test_ground_truth.py` | six-key hardcode → spec conformance; + folder/list guard | low |
| `test_pipeline_and_runner.py` | new: manifest resolution, fallback identity, unknown-profile raises, missing-spec-target raises, mixed-exam two-fixture `p2_only` on fakes | low |
| `exams/hobby_tvshow.json` | copy of `draft.json` (**keep `draft.json` in place** so `check_goal.sh`'s default and the RUNLOG history stay reproducible) | none |
| `backend/.gitignore` | 4 un-ignore lines (D2) | none |
| `TRANSCRIPTION_GT_CONVENTIONS.md` §1.2, §7, §11 · `docs.md` §9/§11/§14/§15 · `transcription_evalsuite_skill.md` §3 · `GT_ARTIFACTS_REPORT.md` §9 · `BACKLOG.md` B-30f · `RUNLOG.md` | doc truth-up | none |

**Untouched, and asserted so in the DoD:** `scoring.py`, `critical_tokens.py`,
`normalize.py`, `keys.py`, `ground_truth.py`, `check_goal.sh`, `check_gt_consistency.py`,
`flag_metrics.py`, every existing GT file, every `configs/*.json`, and all production code
under `app/`.

---

## 6. Phases

Each phase ends in a state that is green and shippable on its own.

### Phase 0 — decisions · **done, except D3/D6 which do not block**

D1 amended, D2 commit, D4 commit, D5 `JAVA_BAGRUT` unchanged (all ruled 2026-08-28).
D3 stays open and is neutralised by §4.3's subset assertion; it becomes due only if one of
exam B's students skipped a question. D6 is taken in Phase 4, with numbers in hand.
Phase 1 is unblocked.

### Phase 1 — instrument plumbing · ✅ **SHIPPED 2026-08-28 · zero behaviour change**

§4.1–4.4 + the `.gitignore` lines. No new GT, no manifests for the five seeds (they keep
resolving through the `--exam-spec` fallback — that is what proves the fallback).

**Acceptance — a null result was the pass condition. Met:**

1. ✅ `pytest tests/transcription_eval_suit -q` → **148 passed, 1 skipped** (133 baseline
   + 15 new). `python -c "import app.main"` clean. The sibling grading suite's cross-suite
   guards (`test_fixture_tools.py`, `tests/eval_common`) still green.
2. ✅ Diff scope verified, not assumed: `scoring.py`, `critical_tokens.py`, `normalize.py`,
   `keys.py`, `ground_truth.py`, `check_goal.sh`, `check_gt_consistency.py`,
   `flag_metrics.py`, `raw_benchmarks/`, `draft_benchmarks/` — **all untouched**. Zero
   production (`app/`) diff.
3. ✅ **Behavioural identity proven offline instead of by a noisy k=5.** For all five seed
   fixtures the fallback resolves to a spec `==` the retired `load_spec`'s, with
   **byte-identical `to_prompt_json()`** — the actual bytes P2 receives, so the model
   cannot behave differently — and the same `JAVA_BAGRUT` object. Pinned permanently by
   `test_seed_corpus_resolves_exactly_as_the_historical_loader_did`. This is a *stronger*
   claim than the k=5 the plan originally asked for, and it costs nothing; the API run is
   therefore not spent on a question already settled.
4. ✅ `results.json` gains only the `fixtures` provenance block and two per-record fields;
   `summary.md` is unchanged on a single-exam run (pinned by
   `test_summary_renders_a_pre_multi_exam_results_json` and the existing report tests).

**Also landed:** `exams/bagrut_899371.json` staged as evidence for D7 (a teacher rubric, no
student data). It is **not yet in use** — no manifest points at it — so it is inert.

### Phase 2 — the exam artifact

Export exam B's rubric `draft_json` → `exams/<exam_id>.json`. Verify offline, no API:
`spec_from_rubric_draft` yields the right question/sub-question skeleton, and — the
lesson of the omer Q2.ב↔ג swap, pinned today by
`test_real_draft_subquestion_signatures_name_the_methods` — **every sub-question's
signature names its discriminating method**, and reaches `to_prompt_json()`. A spec with
empty sub-question text makes P2's routing guesswork. Generalize that test to run over
every `exams/*.json`. Answer D5 here.

### Phase 3 — author the GT

Strictly [TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md). Two rules
dominate: **transcribe raw first, derive draft from it** (§2 — the F-1..F-3 defect class),
and **stage outside the folders** (§1.4 — a raw GT in `raw_benchmarks/` joins every eval
run the instant it lands).

Per fixture, landed **atomically** as one commit: `pdfs/<id>.pdf` +
`raw_benchmarks/<id>.md` + `draft_benchmarks/<id>.md` + `fixtures/<id>.json` + the
`ALL_FIXTURES` entry. Per-fixture DoD = the conventions' §11 checklist, plus:

- `check_gt_consistency <id>` exits 0;
- the manifest's `exam_spec_sha256` matches its target;
- one `--mode per_doc --repeats 1 --fixtures <id>` run, **read by eye** — you are checking
  the diffs make sense, not the score (a nonsense diff means suspect your GT first);
- every §10 uncertainty either resolved against the scan or listed for the owner.

**Watch for:** exam B's Hebrew section-header shapes vs `check_gt_consistency`'s
`_HEADER_RE` (tuned to `שאלה \d+` / `[א-ת].`) — a different header idiom needs that regex
extended, which is an instrument edit and therefore a surface, not a silent fix.

### Phase 4 — validate the mixed corpus

1. Cheap: `p2_only --repeats 5 --fixtures <new docs>`. Attribution per §17.4 —
   `p2_only` high + e2e low ⇒ P1 perception; `p2_only` low ⇒ P2 segmentation.
2. Then **one** `check_goal.sh` over the full partition. Expensive; spend it once.
3. Report the numbers. **If exam B fails, that is the finding** — record it, attribute it,
   and take D6 with the evidence. Do **not** answer it with an instrument change (§17.7);
   do **not** relax a floor.
4. Note the two things that changed meaning at n≥10: `flag_metrics_trustworthy` → `True`,
   and the corrector's false-fix rate becomes readable *if* the new fixtures contain
   deliberately-included student-spec errors (they may not — say so rather than implying
   the kill-criterion is now armed).

### Phase 5 — truth-up the docs

The five doc sites in §5, plus a RUNLOG entry in the established shape: what changed, what
did **not**, the before/after cheap-tier numbers, the decisions taken and by whom, and the
open questions carried forward.

---

## 7. Definition of done

- [x] D1 (amend), D2 (commit), D4 (commit), D5 (`JAVA_BAGRUT`) ruled 2026-08-28
- [ ] D3 revisited only if an exam-B student skipped a question; D6 taken in Phase 4
- [ ] `pytest tests/transcription_eval_suit -q` green; `python -c "import app.main"` clean
- [ ] `git diff --stat` carries **no** STOP-listed file (§0 commitment) — checked, not assumed
- [ ] Five-seed `p2_only k=5` before/after Phase 1: identical gates, Δratio ≤ 0.0091
- [ ] `check_goal.sh` runs **unedited** and, with no manifests present, behaves byte-identically
- [ ] Every new fixture: conventions §11 checklist + manifest + `check_gt_consistency` = 0
- [ ] `results.json` names the exam and profile per fixture; `summary.md` shows the Exam
      column on mixed runs and is unchanged on single-exam runs
- [ ] One full `check_goal.sh` executed; verdict recorded in RUNLOG **whatever it says**
- [ ] BACKLOG B-30f closed or amended to match what actually shipped
- [ ] `TRANSCRIPTION_GT_CONVENTIONS.md` §1.2's "blocked at the RUNNER" paragraph replaced
      with the how-to

---

## 8. Deliberately not in this plan (filed, not done)

- **Per-exam directory layout** (`exams/<id>/{raw,draft,pdfs}/`) — the eventually-correct
  shape; moves the owner's GT and every documented path. Revisit at ~3 exams.
- **Manifests for the five seed fixtures.** Would remove the implicit fallback, but the
  fallback is what keeps `check_goal.sh`'s default and the RUNLOG history reproducible.
  If done later, it is a separate zero-behaviour-change step with a test proving the
  resolved spec is byte-identical to `draft.json`.
- **Grading-suite fixtures for exam B.** Its `fixtures/<name>.json` manifests already
  point at a shared `benchmarks/contracts/hobby_tvshow_corrected.contract.json`, so the
  shape extends cleanly — but it needs exam B's *rubric contract* and *teacher GT*, which
  is its own owner-gated authoring effort.
- **`configs/*.json` and `draft.json` being untracked** is fixed by D2's un-ignore lines,
  but the deeper question — whether a fresh clone can reproduce any historical run — is
  bigger than this plan.
- **§5.3 (skipped question)** stays open by design; §4.3's subset assertion is correct
  under either ruling.
