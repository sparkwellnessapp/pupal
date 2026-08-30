# GT artifacts — conventions, contracts, and audit findings

> **Scope.** Everything about the ground-truth (GT) artifacts of the transcription eval
> suite: what they are, the rules that govern their form, who owns them, how the code
> consumes them, and where the corpus on disk currently disagrees with itself.
>
> **Status.** Research report, 2026-08-11, written from the code and the corpus. **No GT file was
> modified.** Per `CLAUDE.md` §17.7, everything in §8 was raised as a **verification task for the GT
> author (Noam)** — surfaced with evidence, never silently fixed.
>
> **Resolution (2026-08-11).** The §8 divergences were adjudicated against the source PDFs (§10) and
> the verdicts accepted by the owner, who is applying the edits manually. The remaining open items
> are the two lower-confidence spans flagged in §10. `check_gt_consistency` is the acceptance test:
> it exits 1 today and must exit 0 once the edits land.
>
> **This is not the authoring spec.** For *how to produce* GT artifacts, see the companion
> [TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md), written for agents adding new
> fixtures. This report explains what the artifacts are and why each rule exists; that one says what
> to do. The historical `GT_CONVENTIONS.md` ("locked v1.1") remains missing from the repository (§7.1).

---

## 1. The artifact set

A fixture is a triple joined on one filename stem (`doc_id`):

| Path | Role | Tracked in git? |
|---|---|---|
| `pdfs/<doc_id>.pdf` | The source exam scan — the only true authority | **No** (`backend/.gitignore:198` `*.pdf`) |
| `raw_benchmarks/<doc_id>.md` | **Raw GT** — per-page verbatim ink. Scores Phase 1 | **Yes** |
| `draft_benchmarks/<doc_id>.md` | **Draft GT** — per-answer gradeable content. Scores Phase 2 / end-to-end | **Yes** |

Two further artifacts are GT-adjacent and easy to overlook:

| Path | Role | Tracked? |
|---|---|---|
| `draft.json` | The **exam spec** — defines the answer-key vocabulary P2 routes into | No (`*.json`, `backend/.gitignore:164`) |
| `configs/*.json` | Pipeline configs (models, DPI, token budgets) | No (same rule) |

Five fixtures: `dan_basiuk`, `din_ezra`, `moran_aharon`, `omer_gelber`, `yonatan_basiuk` —
one exam (Hobby / TvShow; two CS questions, sub-questions א/ב/ג), five students.

`raw_benchmarks/` is the **fixture registry**: with no `--fixtures` flag the runner globs
`raw_benchmarks/*.md` and takes the stems ([runner.py:598-601](runner.py#L598-L601)). A doc with
only a draft GT would never be discovered. PDF pairing is a case-insensitive stem match
([runner.py:141-148](runner.py#L141-L148)); the two GT lookups are exact-path (`f"{doc_id}.md"`)
and therefore case-sensitive on a case-sensitive filesystem.

---

## 2. The two ground truths — the central distinction

The suite documentation calls this "the single most important conceptual point"
([transcription_eval_suit_docs.md:199-215](transcription_eval_suit_docs.md#L199-L215)):
**two GTs score two different surfaces.**

| | Raw GT | Draft GT |
|---|---|---|
| Folder | `raw_benchmarks/` | `draft_benchmarks/` |
| Delimiter | `=== PAGE 1 ===` | `=== Q1.א ===` |
| Parsed to | `GoldPageDocument` → `dict[int, str]` | `GoldDocument` → `dict[(int, str\|None), str]` |
| Scores | Phase 1 (perception) | Phase 2 / end-to-end (answer content) |
| Contains | **All ink**: code, comments, section markers (`שאלה 1`, `א.`), margin notes | **Only gradeable answer content**, per `(question, sub-question)` |

The asymmetry is deliberate. An answer that lacks a margin note is *correct*, not a
content-drop bug, so an end-to-end ratio can legitimately exceed the P1 ratio. The docs call
mistaking this "the intentional-asymmetry trap" and warn that an analyst will make it every run
if not warned: *"Never flag an intentional draft-GT exclusion as a P2 failure."* Both playbooks
make confirming this a mandatory step before reporting any missing-content finding.

`dan_basiuk` is the canonical example. The student closed his exam with a thank-you note
([raw_benchmarks/dan_basiuk.md:145-146](raw_benchmarks/dan_basiuk.md#L145-L146)):

```
תודה על הCW והCR() ממש הקל עלי
ותודה שאמרת לי בסוף להוסיף סוגרים בCR ממש הצלת אותי
```

It is ink, so the raw GT keeps it; it is not an answer, so the draft GT drops it. The live P2
correctly reports excluding it as "orphan text … non-code."

> **One documented rationale for the asymmetry is wrong.** Both
> [transcription_eval_suit_docs.md:210](transcription_eval_suit_docs.md#L210) and `RUNLOG.md:38`
> say draft GT "excludes the hard-to-read Hebrew comments." It does not — inline code comments
> are **retained** in draft GT (e.g. [draft_benchmarks/dan_basiuk.md:52](draft_benchmarks/dan_basiuk.md#L52)
> keeps `// אם ספורטיבי`). What draft GT actually drops is *headers, standalone margin notes, and
> identity*. The asymmetry is real; that explanation of it is not.

---

## 3. The conventions

The original statement (`GT_CONVENTIONS.md` v1.1) is missing. What follows is reconstructed from
[ground_truth.py](ground_truth.py)'s module docstrings, `transcription_evalsuite_skill.md` §3, and
the executable assertions in [test_ground_truth.py](test_ground_truth.py). It is a *description* of
the rules; the operational version — decision table, hard cases, verification steps — is
[TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md).

### 3.1 Shared by both formats

| Rule | Where stated |
|---|---|
| Verbatim ink; **student errors preserved** — misspellings, `While`/`Public` capitalization, missing `;`, wrong brackets | `ground_truth.py:20-21` |
| Abbreviations `CW`/`CR` never expanded (they are Bagrut-legal shorthand for `Console.WriteLine`/`ReadLine`) | `ground_truth.py:21` |
| Illegible ink → `[?]`, "one shared vocabulary with model output" | `ground_truth.py:23` |
| Crossed-out ink **dropped entirely, no marker of any kind** | `ground_truth.py:24` |
| Author-mark vocabulary **converted**: literal `[crossed out]` / `[illegible]` must not survive | `test_ground_truth.py:121-124` |
| Student identity (name, כיתה, ID) excluded from both formats | `transcription_evalsuite_skill.md:103,268-271` |
| Printed exam furniture (printed page numbers, form chrome, printed question text) excluded — "not ink" | `transcription_evalsuite_skill.md:115` |
| Case fully preserved. All case tolerance lives in the **scorer**, never in the GT | `scoring.py` `ScoringPolicy` |

### 3.2 Raw GT (per page)

Delimiter ([ground_truth.py:127](ground_truth.py#L127)):

```python
_PAGE_DELIM_RE = re.compile(r"^===\s*PAGE\s+(\d+)\s*===\s*$", re.MULTILINE | re.IGNORECASE)
```

- One delimiter per **physical page**.
- **Includes** the student's section headers — verbatim means verbatim.
- Section markers are normalized to **format** (`שאלה {n}`, sub-question as `א.`) but the
  **letter is kept verbatim even when the student mislabeled it** — a student's `ד.` stays `ד.`.
  This is load-bearing for `omer_gelber` (§4).
- Circled question digits are written as `שאלה {n}`.
- An empty page is `""`.
- Parser-enforced: no duplicate page number, and **numbers contiguous from 1** — a gap "usually
  means an authoring typo" ([ground_truth.py:169-173](ground_truth.py#L169-L173)).

### 3.3 Draft GT (per answer)

Delimiter ([ground_truth.py:40](ground_truth.py#L40)):

```python
_DELIM_RE = re.compile(r"^===\s*Q(\d+)(?:\.([^\s=]+))?\s*===\s*$", re.MULTILINE)
```

- One delimiter per answer; the sub-id is optional (`=== Q3 ===` is a question with no
  sub-questions) and may be any run of non-space, non-`=` characters, so Hebrew letters work.
- Bodies are **answer content only** — markers, headers, margin notes, identity excluded.
- Bodies are verbatim, bugs included; leading/trailing blank lines stripped, internal formatting
  untouched.
- Parser-enforced: **a repeated `(question, sub)` key raises `ValueError`.** No contiguity
  requirement (unlike pages).
- All five fixtures must yield exactly six keys `(1,א)(1,ב)(1,ג)(2,א)(2,ב)(2,ג)`
  ([test_ground_truth.py:132-139](test_ground_truth.py#L132-L139)).

### 3.4 The marker vocabulary is shared with the model

`[?]` and the crossed-out rule are not GT-local conventions — they are the same vocabulary the
VLM prompt instructs the model to use
([two_phase/prompts.py:53](../../app/services/transcription/two_phase/prompts.py#L53)):
*"Use `[?]` for any character or word you cannot read. Never guess."* and *"Crossed-out text is
omitted entirely — no strikethrough, no marker of any kind."* That shared vocabulary is what makes
abstention comparable between GT and prediction instead of being a formatting accident.

---

## 4. Structural properties the corpus exhibits

Page-to-answer is emphatically **not** 1:1, and the fixtures were selected to make that true. The
stated selection criterion is deliberate inclusion of students who misspell spec-named identifiers
(`Mobby`/`Hobby`, `TVshow`, `LowesRateChannel`, `pupulatHobbies`, `minuteS`), *"because those are
what make the correction-safety verdict decidable"* — all five qualify.

Measured directly from the corpus, with each fixture's role as established across the RUNLOG:

| doc | pages | answers | Structure | What it exercises |
|---|---|---|---|---|
| `moran_aharon` | 6 | 6 | 1:1 | **The only doc ever to pass the e2e ship gate (5/5 stable)** — the proof the conjunctive gate is achievable rather than miscalibrated to impossibility. Also the P2 input-dump case and a `MAX_TOKENS` truncation case |
| `dan_basiuk` | 6 | 6 | 1:1 + a non-answer note on page 6 | The margin-note / intentional-asymmetry fixture. Its GT-typo candidates were adjudicated as **real student errors, correctly left in** |
| `omer_gelber` | 6 | 6 | Answers span pages (Q1.ב over 1–2, Q1.ג over 2–3); Q2 answers appear in the **reverse** of key order | **Marker-vs-content routing.** Motivated per-sub-question content signatures in the exam spec. Sole holder of `[?]` |
| `din_ezra` | 5 | 6 | Page 5 holds **two** answers (Q2.ב + Q2.ג) | **Crossed-out ink.** Its page-1 `SchoolHobbies` block ran ~2 weeks as "GT-incomplete" before Noam adjudicated the GT **faithful** — the block was crossed out, so transcribing it is the crossed-out-inclusion error class. The failed t1.3 prompt experiment's target |
| `yonatan_basiuk` | 4 | 6 | Multiple answers per page throughout; the student wrote **no section headers at all** | **Nested-method partitioning.** A `LowestRateChannel` written *inside* the TVshow braces made P2 oscillate between merging and duplicating — this is the doc that **fired the §17.8 P2-prompt kill criterion** |

`omer_gelber` deserves detail, because it is the fixture that encodes the hardest rule. The
student labelled his sections `שאלה 1`, `ב.`, `ג.` and then `שאלה 2`, `ג.`, `ד.` — so his own
markers for question 2 read ג/ד where the rubric's keys are ב/ג. He also wrote
`PrintLowRatingChannel` (page 5, his marker `ג.`) **before** `LowestRateChannel` (page 6, his
marker `ד.`). The raw GT preserves his mislabels and his page order; the draft GT assigns
`Q2.ב = LowestRateChannel` and `Q2.ג = PrintLowRatingChannel`.

So: **the raw GT is keyed by the page and honours the student's markers; the draft GT is keyed by
rubric semantics and ignores them.** Routing is decided by matching the sub-question's declared
signature, never by trusting the handwriting. This is the same phenomenon `segmentation_check.py`
exists to surface in production.

---

## 5. The key vocabulary and where it comes from

The join key is `Key = tuple[int, str | None]` — `(question_number, sub_question_id)`. Both sides
pass through `normalize_key` ([two_phase/keys.py](../../app/services/transcription/two_phase/keys.py))
before joining, which folds `א`/`a`/`A`/`1` → `א` and strips punctuation, so label-format noise
never becomes a false segmentation miss.

The key *vocabulary* comes from the **exam spec**, not from the GT. `check_goal.sh` defaults to
`GOAL_EXAM_SPEC=draft.json`, a rubric `draft_json` drop-in parsed by `spec_from_rubric_draft`.
Note the fragility: its questions carry `question_number: null`, so the parser falls back to
assigning numbers **by position**
([two_phase/parsing.py:207-211](../../app/services/transcription/two_phase/parsing.py#L207-L211)) —
`int(re.sub(r"\D", "", "None") or i)` → `i`. The GT keys `(1,א)…(2,ג)` match the spec only because
those two questions happen to sit in positions 1 and 2. Reordering that JSON would silently
renumber every key.

---

## 6. How the code consumes GT

### 6.1 Loading

`resolve_fixtures` ([runner.py:151-171](runner.py#L151-L171)) loads both corpora for every fixture
whenever the file exists; the mode only decides which is **mandatory**:

| mode | PDF | raw GT | draft GT |
|---|---|---|---|
| `p1_only` | required | required (reference) | unused |
| `p2_only` | not needed | required — **as the model input** | required (reference) |
| `per_doc` / `batch` | required | required (P1 reference) | required (e2e reference) |

The asymmetry that matters: **in `p2_only` the raw GT is fed to the model** rather than compared
against it. It is the only place a GT artifact is an input, and everything downstream inherits its
exact text (§8, F-4).

### 6.2 Scoring

Comparison runs through the single normalizer
([app/services/transcription/normalize.py](../../app/services/transcription/normalize.py)), applied
identically to GT and prediction: **NFC → lowercase → delete all whitespace → optionally delete
`[?]`**.

Three consequences for GT authoring:

1. **Indentation and blank lines are cosmetic.** Whitespace is deleted, not collapsed. Re-aligning
   braces in a GT file changes nothing about any score.
2. **Case is invisible to the difflib ratio** but not to the gate — case-sensitive errors are
   caught by the critical-token metric, which deliberately runs on **raw, un-normalized** text
   ("the exact form IS the signal here").
3. **`[?]` drives the strict/lenient split.** Strict (gated) keeps the marker, so it counts as a
   mismatch against the real character — this measures real teacher-review cost. Lenient drops it,
   measuring what the model committed to. **Only `doc_ratio_strict` is gated**; the lenient number
   is reported but never enforced.

Per-document metrics: `doc_ratio_strict`, `doc_ratio_lenient`, `coverage`, `missed_keys`,
`extra_keys`, plus the micro-averaged critical block (`operator_recall`/`precision`,
`structural_recall`/`precision`, `method_call_recall`/`precision`, `abbreviations_altered`).

A GT key with no prediction produces no `AnswerScore`, drops `coverage` below 1.0, and still
penalizes the ratio (an empty string is substituted at its position). An **extra** predicted key
dilutes the ratio but does **not** reduce coverage — coverage is recall-only, and the gate has no
precision-side key clause. Crossed-out ink transcribed by the model is likewise punished only as
generic ratio divergence and operator/structural *precision*, and since the gate floors only
*recall*, it is not a gate failure by itself.

### 6.3 The gate's demands on GT

`check_goal.sh` requires `--mode per_doc` (so both corpora are exercised), all fixtures (the
default glob — *"you cannot 'pass' by fixing a subset while breaking the rest"*), and **k ≥ 5
repeats per doc**. Validity is checked before accuracy: zero parse failures, `e2e` present, and
`coverage == 1.0` everywhere. The accuracy clause is the conjunction `doc_ratio_strict ≥ 0.98 AND
coverage ≥ 1.0 AND operator_recall = structural_recall = method_call_recall = 1.0 AND
abbreviations_altered empty`.

Worth knowing: **`check_goal.sh` reads only the `e2e` (draft-GT) block.** The P1 gate against raw
GT is computed and serialized but never consulted by the stop gate.

---

## 7. Provenance and governance

### 7.1 The normative spec is missing

Two documents cite a locked GT convention spec as the authority:

- [P2_EVAL_PLAYBOOK.md:47](P2_EVAL_PLAYBOOK.md#L47) — "This asymmetry is intentional (see `GT_CONVENTIONS.md`)."
- [transcription_evalsuite_skill.md:111](transcription_evalsuite_skill.md#L111) — "**GT conventions (`GT_CONVENTIONS.md`, locked v1.1):**"

A search of the entire repository returns **no such file**. Three further cited GT artifacts are
also absent: `GT_TYPO_CANDIDATES`, `GT_VERIFICATION_TASKS_20260627.md`, and
`CALIBRATION_EVIDENCE_20260627.md` (all referenced in `RUNLOG.md`). The conventions survived only
as secondary summaries and as the module docstrings in `ground_truth.py` — which is why §3 above
had to be reconstructed rather than quoted.

**Partially closed (2026-08-11):** [TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md)
now carries the authoring rules in operational form, reconstructed from the parsers, the scorer, the
tests, and the corpus. It stands in for the lost v1.1 spec and should be ratified by the owner. The
two stale citations above still point at the missing filename and should be repointed.

### 7.2 How the GT was produced

Hand-transcribed from the PDFs by the owner, then **machine-converted** into canonical form. The
converter is referenced but no longer present: `ground_truth.py:18` says the rules are "enforced by
this format **and the converter that produces it**"; `test_ground_truth.py:55` calls moran "the real
**converted** fixture"; `test_ground_truth.py:121` asserts "author-marks converted, only `[?]`
remains." The inference the artifacts support is that a human transcribed using a looser vocabulary
(`[crossed out]`, `[illegible]`) and a converter normalized it. **With the converter gone, the tests
are the only remaining enforcement of the conventions.**

### 7.3 The audit trail is RUNLOG, not git

`git log` over both GT folders returns exactly one commit — `9c3b6db` (2026-07-16, "PR-4: track
backend/ + frontend/ on main"). **Every GT edit predates version tracking**, so there are no diffs
to re-inspect and `RUNLOG.md` is the sole history. Documented verification events:

| Date | Event |
|---|---|
| 2026-06 | Verification pass resolved an illegible span in moran Q2.ג — orphaning a test spot-check |
| 2026-06-17 | "GT now binding (omitted name-headers, `minuteS` over-fixed); next = GT audit" |
| 2026-06-27 | GT found **edited between runs, silently** (din `arr(0)`→`arr[0]`; moran `[?]`) — detected only because a test broke. Surfaced; test and GT left untouched |
| 2026-06-27 | Authoritative run — **Noam confirmed GT 100% faithful** |
| 2026-06-28 | Typo batch applied from `GT_TYPO_CANDIDATES`, credited item by item (see F-3) |
| 2026-06-29 | omer `!=`/`==` adjudicated against the PDF; **raw GT edited** |
| 2026-07-08 | din p1 ruling: GT **faithful** — `SchoolHobbies` was crossed out |
| 2026-07-10 | "**GT FIX (Noam):** moran p3 counter declarations — models were RIGHT … raw GT had four lines in transposed order. Fixed in raw_benchmarks" |

Two of these are worth internalizing: **twice the models were right and the GT was wrong**
(moran's transposed lines; the 06-28 typo batch), and **twice a confident "GT is incomplete"
conclusion was reversed by the PDF** (din's crossed-out block; omer's `!=`). Both directions
happen. Only the PDF settles it.

### 7.4 Who may edit GT

`CLAUDE.md` §17.7 puts editing anything under `raw_benchmarks/` or `draft_benchmarks/` on the
STOP-AND-SURFACE list — "ground truth is mine" — alongside `scoring.py`, `critical_tokens.py`,
`normalize.py`, the gate thresholds, and `check_goal.sh`. *"A suspected GT typo or a too-strict
gate gets SURFACED with evidence, never silently 'fixed.'"* Answering a grading question with an
instrument change is the same failure class as loosening an invariant tolerance.

Both playbooks operationalize this: the P1 playbook's fourth diff bucket is "**SUSPECTED GT BUG**
(model right, fixture wrong) … these become verification tasks for Noam, NOT model findings," and
both deliverables carry a mandatory "GT verification tasks for Noam" section. The RUNLOG shows the
rule being obeyed under pressure ("surfaced to Noam, did NOT touch test/GT").

The only GT-authoring action sanctioned for an agent is adding a **new** fixture (§9).

**Precedent worth copying:** the sibling rubric suite keeps an append-only
[`GT_AUDIT.md`](../rubric_eval_suite/GT_AUDIT.md) ledger, bans hand-editing of text fields, and
populates them mechanically from renderer output. The transcription suite has no equivalent ledger
— and F-1 through F-3 below are exactly the drift a ledger is built to catch.

---

## 8. Audit findings

I compared each fixture's raw GT against its draft GT under the real scoring normalizer. Under the
normalizer, **`moran_aharon` is character-identical across the two corpora** and `dan_basiuk`
differs only by the thank-you note (correct by design). The other three diverge in ways the
normalizer does not erase.

> **Reproduce in one command:** `python -m tests.transcription_eval_suit.check_gt_consistency`
> ([check_gt_consistency.py](check_gt_consistency.py)) — exits 1 and prints every divergence with
> context.
>
> **Status:** F-1, F-2 and F-3 were adjudicated against the source PDFs on 2026-08-11 (§10) and the
> verdicts accepted; the owner is applying the edits by hand. The findings below are kept as the
> written record of what was wrong and why, not as an open worklist. F-5 (privacy) and F-6 (stale
> documentation) remain open and are decisions, not edits.

### F-0 · Root cause: verification passes reach raw GT but not draft GT

The individual divergences below share one mechanism. GT corrections have been verified with
**`mode=p1_only` runs**, and `p1_only` scores against the raw GT *only* — the draft GT is not even
loaded. A correction applied to raw and missed in draft therefore produces a credited ratio
improvement and **no signal whatsoever** that the other corpus is now stale.

The 2026-06-28 entry is the clearest instance (`RUNLOG.md:35`, `mode=p1_only`):

> GT FIXES CREDITED (no regressions): din ratio 0.882→0.896 …, **yonatan ratio 0.951→0.958 + mc
> 0.853→0.882 (int-string/double-int fixes)**, dan flat …, omer held …

Those are precisely the `int string` / `double int` tokens that F-3 finds still sitting in
yonatan's **draft** GT. File mtimes corroborate: omer's raw GT was last written 2026-06-29 15:21
(the `!=` adjudication) while its draft GT was last written 2026-06-28 18:18 — the only pair in the
corpus edited more than a minute apart, and the pair with the largest divergence.

Nothing in the suite checks the two corpora against each other. Adding that check is the durable
fix; the individual repairs below are the immediate one.

### F-1 · `omer_gelber` — the two corpora disagree about an illegible span

[raw_benchmarks/omer_gelber.md:22](raw_benchmarks/omer_gelber.md#L22) reads the comment fully:

```csharp
int count=0; // סופר כמה פעמים עדכן משתנה (אם לא עדכן נחזיר fake)
```

[draft_benchmarks/omer_gelber.md:21](draft_benchmarks/omer_gelber.md#L21) still abstains:

```csharp
int count=0; // סופר כמה [?] בתוך מקומות של [?]
```

This is the **only `[?]` in the entire corpus** (all ten files) — which also falsifies
`transcription_evalsuite_skill.md:114`, "the current benchmarks contain none." The parallel case is
recorded in [test_ground_truth.py:68-72](test_ground_truth.py#L68-L72): the 2026-06 verification
pass resolved moran's illegible span and the test's spot-check was updated to match. That pass
appears to have reached omer's raw GT and not its draft GT.

Consequence: the marker sits inside a `//` comment, so it is stripped before critical-token
extraction and cannot fail operator/structural recall. But it **is** visible to strict difflib on
the e2e surface, where it penalizes any model that reads the comment correctly.

### F-2 · `din_ezra` — a `new` keyword present in one corpus, absent in the other

| corpus | text |
|---|---|
| [raw_benchmarks/din_ezra.md:108](raw_benchmarks/din_ezra.md#L108) | `int[] arr = new int[tv]` |
| [draft_benchmarks/din_ezra.md:98](draft_benchmarks/din_ezra.md#L98) | `int[] arr = int[tv]` |

Three characters, and they change what the student is recorded as having written. `new` is not in
the `JAVA_BAGRUT` critical profile, so this costs difflib ratio only (≈0.2% on the doc).

### F-3 · `yonatan_basiuk` — three tokens in the draft GT with no counterpart in the raw ink

| draft GT | raw GT |
|---|---|
| `int string num = "";` ([draft:20](draft_benchmarks/yonatan_basiuk.md#L20)) | `string num = "";` ([raw:20](raw_benchmarks/yonatan_basiuk.md#L20)) |
| `double int sumNoSportive = 0;` ([draft:47](draft_benchmarks/yonatan_basiuk.md#L47)) | `double sumNoSportive = 0;` ([raw:59](raw_benchmarks/yonatan_basiuk.md#L59)) |
| an extra `}` closing `populateHobbies` ([draft:43](draft_benchmarks/yonatan_basiuk.md#L43)) | absent |

`int string num` and `double int sumNoSportive` are not valid C# under any reading. Per F-0 these
are almost certainly the pre-fix text that the 2026-06-28 "int-string/double-int fixes" removed
from the raw GT without propagating to draft — but only the PDF can confirm the direction.

### F-4 · The divergence puts a hard ceiling on `p2_only` — the loop's cheap diagnostic

This is the finding with operational consequences. In `p2_only` the raw GT is the **input** and the
draft GT is the **reference**, so a perfect P2 — one that routes every unit correctly and copies
verbatim — still cannot score above the two corpora's agreement. Measuring the fraction of each
draft answer that exists verbatim in the raw ink:

| doc | ceiling | where |
|---|---|---|
| `dan_basiuk` | 1.0000 | — |
| `din_ezra` | 1.0000 | recall-side clean; F-2 is *surplus* text in raw, so it costs ratio on the precision side instead |
| `moran_aharon` | 1.0000 | — |
| `omer_gelber` | **0.9934** | Q1.ב at 0.9761 — 14 characters of draft GT absent from raw (F-1) |
| `yonatan_basiuk` | **0.9973** | Q1.ב 0.9955, Q1.ג 0.9923 — 3 characters each (F-3) |

Neither ceiling is below the 0.98 gate on its own, so this is not currently why the gate fails. But
`omer_gelber` spends roughly a third of its entire error budget before the model is consulted, and
any `p2_only` measurement on these two docs is reading a floor it cannot cross. Per `CLAUDE.md`
§17.4 that residual belongs to the instrument, not to P2 — and `CLAUDE.md` §17.2 makes `p2_only`
the loop's primary iteration signal, so the mis-attribution risk is live every iteration.

### F-5 · Real student data is committed to two public repositories

The GT markdown carries named students' handwritten exam answers, and both folders are **tracked**
and pushed to `origin` (`sparkwellnessapp/pupal`) and `vivi-origin`
(`sparkwellnessapp/vivi-codebase`) — both public per `CLAUDE.md` §10. The PDFs are correctly ignored
(`*.pdf`); the transcriptions of those same PDFs are not, and `results/` is ignored on the explicit
grounds that it "contains student text."

The suite's own documentation says this should not be the case ([`__init__.py`](__init__.py)):

> `benchmarks/` holds canonical ground-truth markdown; `pdfs/` holds source PDFs. Both contain real
> student data — see the integration notes; long-term they move to a private bucket and are
> git-ignored.

Two test guards state it as though it were already true
([test_ground_truth.py:52](test_ground_truth.py#L52), [:112](test_ground_truth.py#L112)):
`reason="benchmark fixture not present (real student data lives outside git)"`. Those skip reasons
are false today — the fixtures are in git, so the guards never trigger.

This is a policy call for the owner, not a code fix: the files are already in published history, so
`git rm` alone would not undo the exposure.

### F-6 · Documentation about the GT that the fixtures contradict

Worth correcting because each one currently misleads an agent mid-loop:

- `transcription_evalsuite_skill.md:229-231,330-332` still lists "**GT typos** (draft GT
  `getisSportiv`/`pupulateHobbies` vs faithful `getisSportive`)" as live cleanup. Both spellings
  appear **identically in raw and draft** for din_ezra, and Noam confirmed the GT faithful on
  2026-06-27 — they are **real student spellings**, not GT typos. (The doc also misquotes the
  token: the fixture reads `pupulatHobbies`.)
- `transcription_evalsuite_skill.md:114` — "the current benchmarks contain none [`[?]`]" — false
  (F-1).
- `transcription_eval_suit_docs.md:210` — "draft GT excludes the hard-to-read Hebrew comments" —
  false; inline comments are retained (§2).

### F-7 · Two lesser observations

- **`report.py` builds e2e diffs from un-normalized GT keys** (`a.key`) while predictions are keyed
  canonically. Harmless today because the GT sub-ids are already canonical `א/ב/ג`, but a fixture
  authored with Latin `a/b/c` would score correctly and render empty diff blocks.
- **The same exam is decomposed differently in the sibling rubric suite.** The transcription spec
  (`draft.json`) gives question 2 three sub-questions (א/ב/ג), matching all five students' answers;
  `rubric_eval_suite/benchmarks/hobby_tvshow.json` — same exam text — gives it two (א/ב). The
  rubric GT is faithful capture of the teacher's document and may legitimately differ from the
  exam's actual structure, so this is a question, not a defect.

---

## 9. Adding a fixture

**The authoring guide is [TRANSCRIPTION_GT_CONVENTIONS.md](TRANSCRIPTION_GT_CONVENTIONS.md)** — the
decision table, the hard cases, the verification commands, and the definition of done. Hand that
document to anyone producing GT from new PDFs; this section is only the outline.

Drop `pdfs/<id>.pdf`; author `raw_benchmarks/<id>.md` (per-page, `=== PAGE n ===`, all ink verbatim,
headers included, page numbers contiguous from 1) and `draft_benchmarks/<id>.md` (per-answer,
`=== Q1.א ===`, gradeable content only, headers excluded, each key exactly once). Use `[?]` for
illegible ink; drop crossed-out ink. The parsers enforce contiguity and uniqueness.

The rule that prevents the F-1..F-3 defect class: **transcribe the raw GT from the scan, then derive
the draft GT from that text.** Two independent readings of the same handwriting will drift; one
reading, re-scoped, cannot. `check_gt_consistency` is what proves it.

Two traps worth naming here. `raw_benchmarks/` is the fixture registry, so a raw GT landing in that
folder joins every default eval run immediately — land both files together. And
`test_all_draft_fixtures_parse_with_six_answers` hardcodes this exam's six keys for every fixture in
`ALL_FIXTURES`, so a fixture from a **different** exam fails it by construction; restructuring that
test is a change to surface, not to make quietly.

Note the standing context: **n = 5 is below the trust threshold.**
`FLAG_TRUST_MIN_FIXTURES = 10`, so `flag_metrics_trustworthy` is always `False` on the current
corpus, every flag-metric conclusion is provisional by construction, and the corrector
kill-criterion is meaningless until n ≥ 10 *with deliberately-included student-spec errors*.
Growing the corpus is critical-path item 1 in the suite's own roadmap.

---

## 10. Adjudication against the source PDFs (2026-08-11)

Each divergence from §8 was read against the scan. **Verdicts accepted by the owner; the edits are
being applied by hand — no GT file was changed by this report.** In all three the raw GT is correct
and the draft GT is the stale side, which is exactly what F-0 predicts. The two items marked
*medium* / *lower confidence* are the remaining open gaps.

### din_ezra Q2.ב — `new` · verdict: **draft GT is wrong**, restore `new` · high confidence

[pdfs/din_ezra.pdf](pdfs/din_ezra.pdf) page 5, second line of `LowestRateChannel`, reads
`int[]arr = new int[…]` — `new` is plainly written and not struck. The raw GT is correct; the draft
GT lost the token.

*Secondary, lower confidence:* on the same page the first line of the second method
(`printLowChannel`) appears to carry strikethrough over `int[]arr = new int[tv];`. Both corpora
currently include that line. If it is struck, the crossed-out-ink rule says both should drop it.
Worth a second look while you are on this page.

### yonatan_basiuk Q1.ב and Q1.ג — the two `int` tokens · verdict: **draft GT is wrong**, drop them · high confidence

Both are **crossed-out ink that the draft GT retained**, which the convention says to drop:

- [pdfs/yonatan_basiuk.pdf](pdfs/yonatan_basiuk.pdf) page 1, first line of `populateHobbies`: a
  struck `int` precedes `string num = "";` — the student started to write `int`, crossed it out,
  and wrote `string`.
- Page 2, the two declaration lines: `double` is followed by a struck `int` (and further struck
  tokens) before `sumSportive` / `sumNotSportive`.

The raw GT is correct in both places. This matches the F-0 story exactly: the 2026-06-28
"int-string/double-int fixes" removed the struck ink from raw and never reached draft.

*Related, medium confidence:* the draft's extra `}` closing `populateHobbies` is **not** reported by
the checker (it falls under the 2-character floor). Page 2 does appear to open with a `}` at the
left margin, which would make the draft right and the **raw** GT the one missing a brace — the only
divergence in the corpus pointing that direction. Please confirm visually.

### omer_gelber Q1.ב — the `[?]` comment · verdict: **draft GT is stale**, adopt the raw reading · medium confidence

[pdfs/omer_gelber.pdf](pdfs/omer_gelber.pdf) page 1, the Hebrew comment beside `int count=0;`. The
raw GT's reading — `// סופר כמה פעמים עדכן משתנה (אם לא עדכן נחזיר fake)` — is corroborated by two
structural features visible in the scan: a parenthesized clause and the Latin word `fake` at the
end. The draft's `// סופר כמה [?] בתוך מקומות של [?]` has neither, and abstains where the raw GT
commits.

The direction is clear; the exact Hebrew wording is cursive at this resolution, so the transcription
itself deserves your eye rather than mine. Resolving it removes the corpus's last `[?]` and lifts
omer's `p2_only` ceiling from 0.9934 back to 1.0.
