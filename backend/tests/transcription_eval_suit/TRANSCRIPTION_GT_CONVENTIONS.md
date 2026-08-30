# TRANSCRIPTION_GT_CONVENTIONS.md

**How to produce ground-truth artifacts for the transcription eval suite.**

> **Read this before you transcribe a single page.** You are authoring the *ruler*, not a
> measurement. Every error you introduce becomes a permanent, invisible penalty on every model
> that reads the page correctly — and the suite has already lost weeks to exactly that
> (`GT_ARTIFACTS_REPORT.md` §7.3).
>
> **Status.** Reconstructed 2026-08-11 from the parsers, the scorer, the tests, and the existing
> corpus, after an audit that found three raw↔draft divergences. It restates the rules the code
> actually enforces and the ones the corpus actually follows. The historical `GT_CONVENTIONS.md`
> ("locked v1.1") is missing from the repository; this document stands in for it and should be
> ratified by the GT owner.
>
> **Companion:** `GT_ARTIFACTS_REPORT.md` explains *why* each rule exists and what broke without
> it. This document tells you *what to do*.

---

## 0. The one-paragraph version

For each student PDF you produce **two** markdown files that describe the **same ink at different
scopes**. `raw_benchmarks/<id>.md` is every mark on every page, page by page, verbatim — it scores
the model's *perception*. `draft_benchmarks/<id>.md` is only the gradeable answer content, keyed by
`(question, sub-question)` — it scores the model's *segmentation*. Transcribe the raw file first and
**derive** the draft file from it, because the two must agree wherever they cover the same ink and
the only defects this corpus has ever had came from treating them as independent transcriptions.
Never normalize, correct, or complete what the student wrote. When you cannot decide, stop and ask —
do not guess.

---

## 1. Before you start

### 1.1 Inputs you need

| You need | Why |
|---|---|
| The PDFs, one per student, at `pdfs/<doc_id>.pdf` | The scan is the **only** authority. Not your memory of it, not the other GT file |
| The **exam spec** for these PDFs | It defines the answer keys the draft GT must use, and its sub-question text is the routing signature |
| Confirmation these fixtures may be committed | See §1.3 |

`doc_id` is the filename stem and it joins every artifact: `pdfs/<id>.pdf`,
`raw_benchmarks/<id>.md`, `draft_benchmarks/<id>.md`, `fixtures/<id>.json`. The PDF lookup is
case-insensitive but the GT lookups are exact-path, so keep them byte-identical.

**`doc_id` = `<exam_id>.<student>`** (2026-08-29). The corpus spans several exams, so a bare
student name no longer identifies a fixture — `hobby_tvshow.dan_basiuk`, `bagrut_899371.<student>`.
The exam_id matches its `exams/<exam_id>.json`. Lowercase `snake_case` either side of the dot;
`Path.stem` strips only the final suffix, so the dot is safe in every lookup.

### 1.2 Same exam, or a new one?

This matters more than it looks.

- **Same exam as the existing five** (Hobby / TvShow, keys `(1,א)(1,ב)(1,ג)(2,א)(2,ב)(2,ג)`): reuse
  `draft.json` as the exam spec. Nothing else to build.
- **A new exam**: SUPPORTED since 2026-08-28 (`PLAN_multi_rubric_fixtures.md`, which amends
  BACKLOG B-30f). One run may span several exams; each fixture declares its own. Two files:

  1. **`exams/<exam_id>.json`** — the exam artifact, ONE per exam, shared by all its fixtures.
     A verbatim rubric `draft_json` export is the production-faithful shape (production builds
     its spec the same way, `two_phase_engine::spec_from_rubric_draft_data`); a canonical
     harness spec also drops in.
  2. **`fixtures/<doc_id>.json`** — the per-fixture manifest, naming that artifact:

     ```json
     {"exam_spec": "exams/bagrut_899371.json",
      "profile": "java_bagrut",
      "provenance": {"exam": "…", "rubric_source": "…", "authored": "2026-08-28"}}
     ```

     `profile` is optional (default `java_bagrut`, the Israeli-CS/C# profile). The manifest
     states **only** what the tree cannot — the exam and the profile. `pdfs/`,
     `raw_benchmarks/` and `draft_benchmarks/` stay pure basename convention.

  With no manifest a fixture falls back to the run-level `--exam-spec`, which is why the five
  seed fixtures and `check_goal.sh` need no new files and behave byte-identically.

  **Keys come from the spec, and the test enforces it.**
  `test_all_draft_fixtures_conform_to_their_exam_spec` asserts a fixture's draft-GT keys equal
  its own exam's declared keys, in spec order (the old six-key hardcode is gone). Derive the
  expected keys before you author anything:

  ```bash
  python -c "
  from pathlib import Path
  from tests.transcription_eval_suit.exam_resolution import load_spec_file, spec_keys
  print(spec_keys(load_spec_file(Path('tests/transcription_eval_suit/exams/<exam_id>.json'))))"
  ```

  A question with **no** sub-questions contributes one whole-question key — `=== Q6 ===`.

  ⚠️ **Check the routing signatures before you transcribe.** Every sub-question must carry a
  non-empty signature naming what it asks for, or P2 can only guess order.
  `test_every_in_use_exam_gives_p2_a_routing_signature` fails the moment a manifest points at
  an exam that does not. A rubric whose sub-questions nest TWO levels (its own `text` is
  `null`, the prompt lives in ITS `sub_questions`) now composes its signature from those
  children — fixed 2026-08-29 in `two_phase/parsing.py::_signature_from_children`, so
  `bagrut_899371`'s Q1 routes on `Check` / `What` instead of a bare letter.

The spec's per-sub-question text is not decoration: it is the **content signature** P2 routes by
("write a method named `LowestRateChannel` …"). A spec with empty sub-question text makes routing
guesswork.

### 1.3 Privacy — confirm before you commit

The GT files contain named students' handwritten exam answers, and both benchmark folders are
**tracked in git and pushed to two public GitHub remotes** (`GT_ARTIFACTS_REPORT.md` §8, F-5). The
PDFs are gitignored; the transcriptions of those PDFs are not. Adding fixtures adds more student
data to a public repository. **Get an explicit ruling from the owner before committing new
fixtures** — this is a policy decision, not a technical one.

### 1.4 Do not add a half-finished fixture to the folder

The runner discovers fixtures by globbing `raw_benchmarks/*.md`
([runner.py:598-601](runner.py#L598-L601)). The moment a raw GT lands there it joins **every default
eval run**, and a missing draft GT raises `FileNotFoundError` in `per_doc` mode. Author both files
somewhere else, or author them together and land them in one step.

---

## 2. The workflow

**Author raw first. Derive draft from raw. Never transcribe the same ink twice.**

This is the core discipline and it exists for a specific reason: every historical defect in this
corpus (`GT_ARTIFACTS_REPORT.md` §8, F-1 through F-3) is a place where raw and draft were edited
independently and drifted. Two independent transcriptions of the same handwriting will disagree.
One transcription, mechanically re-scoped, cannot.

1. **Transcribe the raw GT**, page by page, from the PDF. This is the only place you read
   handwriting. Follow §3 and the decision table in §5.
2. **Derive the draft GT** from the raw text you just wrote: select the answer spans, drop the
   excluded ink, order them **by key** (§4.2), join spans that cross page boundaries. This is text
   selection and reordering — not re-reading the scan.
3. **Verify** with the commands in §7. The consistency checker must exit 0.
4. **Re-read the scan only** for the spans the checker flags, or for anything you marked uncertain.

Deriving does not mean the draft is a naïve copy: answers span pages, a page can hold several
answers, and draft order follows the rubric rather than the paper (§6). But every character in the
draft must trace back to a character you transcribed in the raw file.

---

## 3. Raw GT — format and rules

`raw_benchmarks/<doc_id>.md`. Scores Phase 1 (perception). **Contains all ink.**

### 3.1 Format

```
=== PAGE 1 ===
שאלה 1
א.
public class Hobby
{
    private string hobbyName;
}

=== PAGE 2 ===
...
```

Enforced by the parser ([ground_truth.py:145-176](ground_truth.py#L145-L176)):

- One `=== PAGE n ===` delimiter per **physical page** of the PDF.
- Page numbers must be **unique and contiguous from 1**. A gap raises — it almost always means you
  skipped a page.
- Everything between delimiters is that page's body, verbatim. Leading and trailing blank lines are
  stripped; internal formatting is kept.
- An empty page is an empty body (`""`), not an omitted delimiter. Page numbering stays contiguous.
- `test_all_raw_fixtures_parse` requires **at least 3 pages** per fixture.

### 3.2 What goes in

Everything the student's pen put on the page: code, inline comments, section headers, margin notes,
asides, corrections. If it is ink and it is not struck out, it is in the raw GT.

### 3.3 Section markers — normalize the format, never the letter

Student section headers **belong in the raw GT**. Write them in canonical format:

- Question headers as `שאלה {n}` — including when the student circled a bare digit.
- Sub-question markers as `א.` (letter, period), on their own line, as the corpus does.

But the **letter itself is verbatim, even when the student is wrong**. In `omer_gelber` the student
labelled question 2's parts `ג.` and `ד.` where the rubric's keys are ב and ג. The raw GT preserves
`ג.` and `ד.`. Silently "fixing" a mislabel destroys the exact signal the marker-vs-key machinery
(`segmentation_check.py`) exists to detect.

---

## 4. Draft GT — format and rules

`draft_benchmarks/<doc_id>.md`. Scores Phase 2 and end-to-end. **Contains only gradeable answer
content.**

### 4.1 Format

```
=== Q1.א ===
public class Hobby
{
    private string hobbyName;
}

=== Q1.ב ===
public bool PopulateHobbies()
...
```

Enforced by the parser ([ground_truth.py:71-102](ground_truth.py#L71-L102)):

- One `=== Q{n}.{sub} ===` delimiter per answer. The sub-id is optional — `=== Q3 ===` is a question
  with no sub-questions — and may be any run of non-space, non-`=` characters, so Hebrew letters work.
- **A repeated `(question, sub)` key raises `ValueError`.** Each key appears exactly once.
- No contiguity requirement (unlike pages), but the keys must match the exam spec.
- `test_all_draft_fixtures_conform_to_their_exam_spec` additionally asserts **the literal string `שאלה`
  appears nowhere in any answer body** ([:143](test_ground_truth.py#L143)) — including inside a
  student's own code comment. If a student writes `// שאלה קשה` inside an answer, that assertion
  fires. Surface it rather than deleting the student's comment.

### 4.2 Keys follow the rubric, not the handwriting

This is the rule people get wrong.

**The raw GT is keyed by the page and honours the student's markers. The draft GT is keyed by rubric
semantics and ignores them.** Assign each answer to the key whose **spec signature the content
matches** — the method or class the sub-question asked for — regardless of what the student wrote in
the margin and regardless of where it sits on the paper.

`omer_gelber` is the worked example. He wrote `PrintLowRatingChannel` on page 5 (marked `ג.`) and
`LowestRateChannel` on page 6 (marked `ד.`). The draft GT assigns:

```
=== Q2.ב ===     ← LowestRateChannel   (from page 6, the student's "ד.")
=== Q2.ג ===     ← PrintLowRatingChannel (from page 5, the student's "ג.")
```

Content order in the draft file follows key order, not page order.

### 4.3 What is excluded

Answer content only. Drop: section markers, question headers, standalone margin notes, student
identity, and any ink that is not part of an answer.

**Inline code comments stay.** A `// אם ספורטיבי` sitting inside a method body is part of the answer
and belongs in the draft GT. Two suite documents claim draft GT "excludes the hard-to-read Hebrew
comments" — that is wrong and the corpus contradicts it (`GT_ARTIFACTS_REPORT.md` §2). What draft GT
drops is *headers, standalone notes, and identity*, not comments.

`dan_basiuk` is the canonical exclusion: his closing thank-you note is ink, so it is in the raw GT,
and it is not an answer, so it is absent from the draft GT.

---

## 5. The decision table

For every mark on the page:

| Ink | Raw GT | Draft GT | Notes |
|---|---|---|---|
| Answer code | ✅ verbatim | ✅ verbatim | |
| Inline code comment (`// …`), any language | ✅ | ✅ | Part of the answer |
| Question header (`שאלה 1`) | ✅ format-normalized | ❌ | |
| Sub-question marker (`א.`) | ✅ letter verbatim | ❌ | Preserve mislabels (§3.3) |
| Standalone margin note / aside / thank-you note | ✅ | ❌ | |
| Student identity — name, כיתה, ID | ❌ | ❌ | Excluded from both |
| Printed exam furniture — printed page numbers, form chrome, printed question text | ❌ | ❌ | Not ink |
| **Crossed-out ink** | ❌ | ❌ | Dropped entirely, **no marker of any kind** |
| **Illegible ink** | `[?]` | `[?]` | One marker per unreadable character or word. Read §5.2 first |
| Empty page | `""` body | — | Delimiter stays; numbering contiguous |
| An answer the student never wrote | — | delimiter + **empty body** | Ruled 2026-08-28; the norm on a selection exam (§5.3) |

### 5.1 Crossed-out ink

Transcribe **visible ink only**. Struck text is dropped completely — no `[struck]`, no
strikethrough, no placeholder. The literal strings `[crossed out]` and `[illegible]` are banned in
both corpora and asserted against by the tests.

This rule is load-bearing and it has already been litigated. `din_ezra`'s page-1 `SchoolHobbies`
block ran for two weeks as a suspected GT gap before the owner adjudicated the GT **faithful** — the
block was crossed out, and models transcribing it were committing the crossed-out-inclusion error
class. Getting this wrong converts a real model defect into a phantom GT bug.

Watch for the inverse too: two of the three defects found in the 2026-08 audit were **struck tokens
the draft GT retained** (`int string num`, `double int sumNoSportive` in `yonatan_basiuk`). A student
who writes a type, strikes it, and writes another is common. Only the surviving token goes in.

### 5.2 Illegible ink — prefer resolving it, and know the cost

`[?]` is the shared vocabulary: it is exactly what the VLM prompt tells the model to emit
([two_phase/prompts.py:53](../../app/services/transcription/two_phase/prompts.py#L53), *"Use `[?]`
for any character or word you cannot read. Never guess."*). Using the same token on both sides is
what makes abstention comparable.

It is not free, and it is asymmetric:

- **Strict ratio.** `doc_ratio_strict` is the gated metric and it keeps the marker, so a `[?]` in
  gold is a guaranteed penalty against any model that reads the character correctly.
- **Structural tokens — the sharp edge.** The critical profile counts `[` and `]` as structural
  tokens, extracted by a per-character scan
  ([critical_tokens.py](critical_tokens.py)). Comments and string literals are stripped first, so a
  `[?]` inside a `// …` comment is invisible. **A `[?]` in code is not**: it adds `[` and `]` to the
  gold structural counter, and since the gate demands `structural_recall == 1.0`, a model that reads
  the character correctly now *misses* two structural tokens and fails the gate. The failure is an
  artifact of your abstention, not a model error.
  (One edge: the comment stripper requires a terminating newline, so a `//` comment on the final
  line of an answer is *not* stripped.)

So: zoom in, rotate, compare against the same student's other pages, and resolve the character if
you honestly can. Reserve `[?]` for ink you genuinely cannot read — and never use it in code where a
resolution is achievable. The current corpus contains exactly two `[?]` markers, both in one comment,
both flagged as stale by the audit.

### 5.2a Trace tables and other hand-drawn grids — RULED 2026-08-29

Write a hand-drawn table as **bare, space-padded, fully-bounded pipe rows** — one row per
line, no marker, no separator:

```
| x | i | arr[i] | arr[i]!=1 && arr[i]!=x && x % arr[i]==0 | ערך מוחזר |
| 6 | 0 | 8 | F |  |
|  | 1 | 5 | F |  |
|  | 4 | 3 | T | T |
```

Four rules, each measured (`PLAN_multi_rubric_fixtures.md` D9), not chosen for looks:

1. **RECTANGULAR BY CONSTRUCTION.** Every row carries exactly one cell per column. A cell
   with no ink is written EMPTY — **never omitted**. The grid is uniform; the content is
   sparse. A 4×4 table whose last column holds one value is 4 full rows with empty cells,
   and it renders exactly right. *Omit* a cell instead and the review surface pads at the
   END, so a table whose sparse column is FIRST — the common shape, where `x` is written
   once — shows every later value under the wrong header, silently.
2. **No `[TABLE n: RxC]` marker.** P1's own prompt forbids markdown, the marker is ink the
   student never wrote, and `[` `]` are structural tokens gated at recall 1.0 — two
   fabricated tokens the model must then reproduce exactly.
3. **No `|---|` separator row.** Its dashes read as the `--` (decrement) OPERATOR — five
   fabricated operator tokens on the real bagrut table, also gated at 1.0.
4. **Always space-pad; never `||`.** Two adjacent pipes fail twice over: `||` is the
   logical-OR operator on the critical-token metric, and it is a code-token that makes the
   review surface refuse to render the table at all.

Pipes themselves are free — `|` is in neither the operator nor the structural vocabulary —
so the delimiters cost nothing. Do **not** use a whitespace-aligned grid instead: the scorer
deletes all whitespace, so every column boundary would vanish.

**This shape is PINNED IN THE P1 PROMPT** (`t1.4-tables`, 2026-08-29): the model is told to
emit exactly it, including the worked example above, so GT and prediction agree by
construction rather than by luck. The pin is cross-tested —
`frontend/src/utils/p1-table-contract.test.ts` renders the prompt's own example and asserts
the exact 4×4 grid, so the prompt and the review surface cannot drift apart.

Still confirm it on the real pages before authoring a table fixture: a prompt rule is a
model instruction, not a guarantee. Run `--mode p1_only` on the page and read the output. A
format mismatch is a gate failure by itself — gold-vs-prediction across two
faithful-but-differently-shaped readings measured 0.9648, under the 0.98 bar.

### 5.3 A question the student skipped — RULED: emit the key with an empty body

**Owner ruling, 2026-08-28.** A question the student left blank still gets its
`=== Q{n}.{sub} ===` delimiter, with **nothing** between it and the next one. Do not omit
the block. `test_all_draft_fixtures_conform_to_their_exam_spec` enforces this: your keys
must equal the exam's declared keys exactly.

**This is the normal case on a SELECTION exam** ("ענו על 4 מתוך 6" — `selection_groups`
with `choose_k`), where the student is *instructed* to leave whole questions blank. Nothing
about those blanks is an error, and the eval says so: the span contract emits every spec
target's key regardless, filling unassigned ones with `""`
([spans.py:210-214](../../app/services/transcription/two_phase/spans.py#L210)), so an empty
gold meets an empty prediction, `coverage` stays 1.0, the ratio is 1.0, and the
critical-token clauses are vacuous.

**Why not the other option.** Omitting the block would put a model's *invented* answer for
an unanswered question into `extra_keys`, where it dilutes the document ratio and fails
nothing. Emitting the empty key makes that invention score **0.0** on that answer and raise
`is_error` — which is what you want a benchmark to do with a hallucinated answer, and
doubly so on a selection exam where two questions are blank on every single paper.

Two things to know while authoring:

- A blank body is not the same as an illegible one. Nothing on the page ⇒ empty body. Ink
  you cannot read ⇒ `[?]` (§5.2).
- The `summary.md` of a run over a selection exam states `is a SELECTION exam (choose k of
  N)`, so a later reader does not mistake a correct empty answer for a segmentation failure.

---

## 6. Structural cases you will hit

None of these are exceptions to the rules — they are the rules applied to messy paper. All four
appear in the existing corpus.

**An answer spans pages.** The raw GT splits it at the page break, exactly where the paper does. The
draft GT joins it into one body. `omer_gelber` Q1.ב spans pages 1–2 and Q1.ג spans pages 2–3.

**A page holds several answers.** The raw GT keeps them in one page body, in the order written. The
draft GT splits them into separate keys. `din_ezra` page 5 holds Q2.ב and Q2.ג.

**The student wrote no headers at all.** Fine — the raw GT simply has no marker lines, and the draft
GT is keyed entirely by content signature. `yonatan_basiuk` has four pages, six answers, and zero
section markers.

**Answers are nested or interleaved.** `yonatan_basiuk` wrote `LowestRateChannel` *inside* the
`TVshow` class braces. Transcribe what is there, in the order it is there. Then assign each unit to
its key by signature, and do not duplicate a span across two keys — each key gets its own content,
and a body can appear in exactly one place.

---

## 7. Verify before you hand anything over

Run all four, **from `backend/`**. The first three are cheap and offline.

**1 — Both files parse.**

```bash
python -c "
from tests.transcription_eval_suit.ground_truth import load_page_ground_truth, load_ground_truth
r = load_page_ground_truth('tests/transcription_eval_suit/raw_benchmarks/<id>.md')
d = load_ground_truth('tests/transcription_eval_suit/draft_benchmarks/<id>.md')
print('pages:', [p.page_number for p in r.pages])
print('keys :', d.keys_in_order())
"
```

Page numbers contiguous from 1; keys exactly the exam spec's, each once, in rubric order.

**2 — The two corpora agree.** This is the acceptance test for §2's derive-don't-retranscribe rule:

```bash
python -m tests.transcription_eval_suit.check_gt_consistency <id>
```

**Must exit 0.** Every reported span is a place where your two files disagree about the same ink,
which means at least one of them is wrong. Go back to the scan — not to the other GT file — and
resolve it. (Known limitation: the checker's 2-character floor means single-character divergences,
such as a lone brace, are not reported.)

**3 — The suite's own fixture assertions.**

```bash
python -m pytest tests/transcription_eval_suit/test_ground_truth.py -q
```

Add your `doc_id` to `ALL_FIXTURES` ([test_ground_truth.py:107](test_ground_truth.py#L107)) — a guard
test now requires that list and `raw_benchmarks/` to agree, so a half-landed fixture fails loudly — or these
assertions never run against your fixture. If you are on a new exam, re-read §1.2 first.

**4 — A real run, once you have the PDF in place.**

```bash
python -m tests.transcription_eval_suit.runner --config v0 --mode per_doc \
    --exam-spec draft.json --repeats 1 --fixtures <id>
```

Then read `results/<timestamp>_v0/report_<id>.md` — the `gold | pred` diffs. You are not checking
whether the model scored well. You are checking whether the *diffs make sense*: if the model and
your GT disagree everywhere, or the diff for a key is empty, or coverage is below 1.0, suspect your
GT before you suspect the model.

---

## 8. What must be exact, and what is free

The scorer normalizes both sides identically — **NFC → lowercase → delete all whitespace** — before
computing the difflib ratio
([normalize.py](../../app/services/transcription/normalize.py)). Critical tokens are extracted from
**raw, un-normalized** text.

**Free — do not spend time on it:**

- Indentation and internal blank lines. Whitespace is *deleted*, not collapsed. Matching the
  student's exact column alignment buys nothing.
- Letter case, *for the ratio*. `While` versus `while` costs nothing there.

**Exact — every character counts:**

- **Structural characters:** `;` `{` `}` `(` `)` `[` `]`. Gated at `recall == 1.0`. A missing
  semicolon in your GT is a permanent gate failure for a model that read the page correctly.
- **Operators:** `==` `!=` `<=` `>=` `&&` `||` `!` `<` `>` `+=` `-=` `*=` `/=` `%=` `++` `--` `=`.
  Also gated at 1.0. The `!=` versus `==` distinction has already been adjudicated once in this
  corpus against the PDF — look twice.
- **Method and identifier spelling.** Case folds, content does not: `GetArrShows` → `GetArrShow` is
  a miss. Transcribe the student's misspellings exactly — `LowesRateChannel`, `pupulatHobbies`,
  `getisSportiv` are all real student spellings in the corpus and all correct as GT.
- **`CW` / `CR`.** Never expand them to `Console.WriteLine` / `Console.ReadLine`. Expansion is
  detected and fails the gate on its own. They are legitimate Bagrut shorthand.

So: letter case for its own sake is not worth agonizing over, but *what letters are present* always
is.

---

## 9. Do not

- **Do not correct the student.** No fixing syntax, closing an unclosed brace, completing a
  truncated line, or making code compile. Their errors are the measurement.
- **Do not transcribe crossed-out ink**, and do not mark that it existed.
- **Do not guess at illegible ink.** `[?]`, or resolve it honestly — never a plausible invention.
- **Do not expand abbreviations** (`CW`, `CR`).
- **Do not relabel a student's section marker** to match the rubric in the raw GT.
- **Do not order draft answers by page.** Order by key.
- **Do not edit one corpus without the other.** This is the single defect class this corpus has;
  the 2026-06-28 fix batch landed in raw, missed draft, and went undetected because it was verified
  with a `p1_only` run that never loads the draft corpus.
- **Do not touch the existing five fixtures.** They are the owner's (`CLAUDE.md` §17.7). Adding a
  *new* fixture is the only sanctioned GT-authoring action.
- **Do not adjust the scorer, the profile, the thresholds, or a test assertion** to make your
  fixture fit. That is answering a measurement question with an instrument change, and it is on the
  STOP list.

---

## 10. Stop and ask, rather than deciding

Escalate these to the GT owner with the page image and your reading. A wrong answer here corrupts
the benchmark quietly, which is worse than a delay:

- You cannot tell whether ink is struck out or merely messy.
- A student's answer content contradicts every spec signature, so no key clearly fits.
- One physical unit of code plausibly satisfies two keys, or one key's content is split across
  non-adjacent places on the paper.
- The student wrote the literal string `שאלה` inside an answer body (§4.1).
- A rubric whose sub-questions nest two levels deep, so its depth-1 routing signatures come out
  EMPTY (§1.2, and `PLAN_multi_rubric_fixtures.md` D7 — a production parser fix, not a GT workaround).
- An answer that is a TRACE TABLE or any other non-code shape: no convention exists yet
  (`PLAN_multi_rubric_fixtures.md` D9). Do not invent one mid-fixture.
- Anything you would resolve by editing a file outside `raw_benchmarks/` or `draft_benchmarks/`.

---

## 11. Definition of done

- [ ] `pdfs/<id>.pdf`, `raw_benchmarks/<id>.md`, `draft_benchmarks/<id>.md` — stems identical
- [ ] Raw GT: one delimiter per physical page, numbers contiguous from 1, ≥3 pages
- [ ] Raw GT: all ink present — headers, comments, margin notes — identity and printed furniture absent
- [ ] Draft GT: one delimiter per answer, keys match the exam spec exactly, each key once
- [ ] Draft GT: keys assigned by content signature, ordered by key, headers and standalone notes absent
- [ ] No crossed-out ink in either file; no `[crossed out]` / `[illegible]` literals
- [ ] `[?]` used only where genuinely unreadable, and not inside code where it would be structural
- [ ] `check_gt_consistency <id>` exits 0
- [ ] `exams/<exam_id>.json` present and `fixtures/<id>.json` names it (new exam only)
- [ ] `<id>` added to `ALL_FIXTURES`; `pytest tests/transcription_eval_suit -q` green
- [ ] One `per_doc` run inspected — diffs are sensible, coverage 1.0
- [ ] Every uncertain span either resolved against the scan or listed for the owner (§10)
- [ ] Privacy ruling obtained before committing (§1.3)
- [ ] A line appended to `RUNLOG.md` recording what was added and any open questions
