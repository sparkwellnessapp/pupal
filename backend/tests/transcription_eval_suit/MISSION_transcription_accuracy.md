# MISSION — Transcription accuracy: insertion arrows, Hebrew, trace tables

**Mode:** open loop. You iterate autonomously toward the targets in §2, working top-down through first-principles bets (§6), not bottom-up micro-iterations. Checkpoints with the owner are in §9; everything else is yours to run.

**Read first, in full:**
- CLAUDE.md §0, §2 (FC), §3.3, §3.5a, §17 (the eval-loop contract, amended for this mission in §1), and the transcription notes in §7/§8: the two-phase pipeline, `budget.py`, optional-pass timeouts, the strike check, `PROD_CONFIG`.
- In `tests/transcription_eval_suit/`: `transcription_eval_suit_docs.md`, `P1_EVAL_PLAYBOOK.md`, `P2_EVAL_PLAYBOOK.md`, `RUNLOG.md`, `PREDICTIONS.md`, `TRANSCRIPTION_GT_CONVENTIONS.md`.

---

## 0. The problem, stated once

The eval suite has isolated the transcription wall to **P1 perception**; P2 segmentation is close to solved. Three failure classes now dominate what teachers correct at the transcription gate:

1. **Insertion arrows.** A student writes a piece of the answer somewhere else and links it to where it belongs: an arrow, an asterisk pair, a caret, a numbered star, or «המשך». P1 transcribes it where the ink physically sits, so the answer the grader consumes is out of order. There are two kinds (§3), plus decoys:
   - **Insertion:** answer content spliced into place, between lines or mid-line.
   - **Attachment:** a note hung onto one line.
   - **Decoys:** arrows that are not instructions at all.
2. **Hebrew text.** Short Hebrew sentences (1–3 lines), both free-text answers and code comments, are read less accurately than code.
3. **Trace tables.** Five new Bagrut fixtures, from a second exam with a different rubric, contain trace tables. Table fidelity is measurable for the first time and has never been optimized.

The fixture set is now **n=10 across 2 exams**, with names prefixed by exam (e.g. `hobby_tvshow.yonatan_basiuk`). Cross-exam generalization is testable for the first time: **any win that holds on one exam only is suspect.**

---

## 1. What this mission changes in §17, and what it doesn't

The owner has authorized speed over experimental purity for this mission. For its duration:

- **§17.3 (one variable per run) → ONE BET per run.** A bet may bundle changes that serve one hypothesis, such as a new model plus the prompt adaptation it needs. The per-dimension diagnostics (§4.3) provide attribution, because they measure each failure class separately. **Ablate only on surprise:** a bet that regresses a dimension it wasn't aimed at, or wins far beyond its prediction.
- **§17.7 «escalate the P1/P2 model tier» → LIFTED for experiments.** You may run any model in §7. **Switching PRODUCTION remains the owner's call** (checkpoint 2).

**Unchanged and absolute:**
- §17.1: `check_goal.sh` is not yours to edit.
- §17.7: ground truth is the owner's: `raw_benchmarks/`, `draft_benchmarks/`, and now **`insertion_cases.json`**. So are `scoring.py`, `critical_tokens.py`, `normalize.py`, the gate thresholds and `check_goal.sh`. A suspected GT error is SURFACED with evidence (scan crop + GT + prediction), never fixed.
- §17.5: repeats (P2 changes k≥5; P1 finalists k≥3).
- §17.6: RUNLOG after every run.
- §17.8: the P2 prompt kill criterion.
- Worst doc over mean. Validity before significance.

**New diagnostics are allowed; gate changes are not.** You may ADD reported metrics (§4.3). They are diagnostics, and nothing you add changes what `gate_pass` or `check_goal.sh` computes. If you believe a diagnostic should become a gate, surface it (the rejected-Policy-1 precedent).

---

## 2. Targets and hard constraints

**Hard constraints: a config that violates any of these is dead, regardless of accuracy.**
- **C1 No regression.** Every fixture that clears the conjunctive gate at baseline (§4.5) still clears it at k=5.
- **C2 Cost.** `cost_avg_per_doc` stays ≤ the cost gate in `check_goal.sh` (verify the number; the docs say $0.08). The runner must count EVERY call in the pipeline, including any new pass; verify that before you trust a cost figure.
- **C3 Latency.** Production runs under a 480 s per-document budget (`budget.py`). Report p50/p95 document wall time for every finalist. A config whose p95 exceeds 240 s (half the budget, leaving room for one retry) is surfaced, not shipped.
- **C4 Validity.** Zero parse failures and zero `MAX_TOKENS` truncations on finalists. Check any model with lower output limits against the 3-page chunk.
- **C5 FC.** No bet may normalize what the student wrote: misspelled Hebrew stays misspelled, and a wrong identifier stays wrong. No bet may add characters the student did not write. The one sanctioned exception is the `⟦ ⟧` attachment delimiter (§3.3). Diagnostics are scored against faithful GT, so a «fix» that corrects the student shows up as a loss. It must.

**Targets (speed-of-light: what first principles allow, not what feels safe):**

| Dimension | Metric (§4.3) | Target |
|---|---|---|
| Arrows | placement accuracy over `insertion` + `attachment` cases | **100%**, with **0 false relocations** across all 10 fixtures × k |
| Hebrew | Hebrew-projection ratio, worst doc | **≥ 0.98**; minimum acceptable: halve the baseline error (1 − ratio) on the worst doc |
| Tables | shape exact (rows × cols) / cell exact-match | shape **100%** on every table; cells **≥ 0.97** micro-averaged, worst doc ≥ 0.95 |
| General | `check_goal.sh` over n=10 | **exits 0**; minimum acceptable: strictly more fixtures pass the gate than at baseline, and the worst doc improves |

**A false relocation is worse than a missed one.** A missed insertion is visible on the scan beside the transcription; a false one silently reorders what the grader reads. Weight it that way in every decision, and never trade a false relocation for a found case.

---

## 3. The arrow ground truth (owner-authored, complete)

### 3.1 Where each fact lives

| File | Holds | Arrow rule |
|---|---|---|
| `raw_benchmarks/*.md` | all ink, **where it physically sits** | Unchanged. Arrows, boxes and drawn target marks are drawings and are not transcribed. Reference symbols written as characters (`*`, `*1`, `^`, «המשך בעמוד 4») are ink and stay verbatim where written. |
| `draft_benchmarks/*.md` | the answer **as the student intended** | An insertion's text appears only at its target. An attachment appears as ` ⟦note⟧` at the end of its target line. Reference symbols and continuation notes are excluded (non-answer ink). |
| `tests/transcription_eval_suit/insertion_cases.json` | the instructions | Every case, including decoys. Owner-authored and **complete**. You validate it and never edit it. |

### 3.2 `insertion_cases.json` schema

```json
{
  "version": 1,
  "cases": [
    {
      "id": "hobby_tvshow.yonatan_basiuk#01",
      "fixture": "hobby_tvshow.yonatan_basiuk",
      "kind": "insertion",
      "marker": "arrow",
      "source": { "page": 1, "text": "<verbatim raw-GT text>" },
      "target": { "page": 1, "after": "<raw-GT text up to the point>", "before": "<raw-GT text from the point>" },
      "answer_key": "Q1.ב",
      "note": "free text"
    },
    {
      "id": "<fixture>#02",
      "fixture": "<fixture>",
      "kind": "attachment",
      "marker": "arrow",
      "source": { "page": 2, "text": "<verbatim raw-GT note>" },
      "target": { "page": 2, "line": "<one complete raw-GT line>" },
      "answer_key": "<key>",
      "note": "free text"
    },
    {
      "id": "<fixture>#03",
      "fixture": "<fixture>",
      "kind": "decoy",
      "marker": "arrow",
      "page": 4,
      "near": "<verbatim raw-GT text beside the mark>",
      "reason": "flow arrow inside a trace table"
    }
  ]
}
```

**Kinds are defined by what the text IS, not where it lands:**
- **`insertion`:** answer content, spliced in verbatim, between lines or mid-line.
- **`attachment`:** a note about a line, hung at its end inside `⟦ ⟧`.
- **`decoy`:** a mark that is not an instruction (a flow arrow in a trace table, `->`/`=>` in code, a connector linking text already in reading order).

**Id convention:**
- `<fixture>#<NN>` matching `^[a-z0-9_.]+#\d{2}$`. The prefix before `#` equals `fixture` exactly.
- One sequence per fixture, shared by all kinds. The kind lives in `kind`, never in the id, so reclassifying a case never renames it.
- Ids are frozen: never renumbered, never reused.

**`marker`** ∈ `arrow | asterisk | caret | numbered_star | continuation_note | other`. It is descriptive only; no operation reads it.

### 3.3 Operation semantics (the pure relocation function implements exactly this)

1. **Locate everything in the ORIGINAL page text before changing anything.**
   - Source span: the exact occurrence of `source.text`.
   - Insertion target: the boundary between `after` and `before`, where the concatenation `after + before` occurs exactly once on the target page. `after` alone may repeat (e.g. `{\n`); the pair may not. One of the two may be `""` at an answer's start or end; the other must then be unique.
   - Attachment target: the one complete line equal to `target.line`.
2. **Reject** a case when:
   - any location is missing or ambiguous;
   - the source span and the target overlap, or the target lies inside the source;
   - its spans overlap another case's spans (reject both).
   Source and target MAY sit on the same line (yonatan #01 does); that's legal as long as they don't overlap.
3. **Apply** all accepted cases, using positions computed in step 1:
   - cut each source;
   - **insertion:** splice the text at the boundary, keeping its internal line breaks (they're code structure). Mid-line, separate it with single spaces.
   - **attachment:** append ` ⟦note⟧` to the target line, with the note's internal line breaks collapsed to single spaces (a margin note wraps visually, not semantically).

   Apply per page from the end backwards so earlier offsets stay valid; cross-page cases work on the document's page list.
4. **Return** one relocation record per applied case. The eval runner consumes the records for the arrow metrics (§4.3). In production they go to ONE structured log line per document (count plus case positions), for operations only. They are **never** written to the `TranscriptionDraft` and **never** become an annotation (OD-A2: silent).

Whitespace at splice points never affects scoring, because the normalizer strips all whitespace. Don't spend iterations on it.

### 3.4 Validator (Phase 0, before any run uses the file)

Load-time checks. Each failure is reported by case id.
- Schema, the id regex, unique ids, the fixture exists, and `answer_key` exists in that fixture's draft GT.
- `source.text` / `near` is a verbatim substring of its raw GT page, occurring once. `after + before` is unique on its target page. `target.line` is one complete line, occurring once.
- §3.3 step 2 passes for every non-decoy case.
- **Draft conformance** (against normalized text):
  - insertion: `after + source + before` is a substring of the draft answer at `answer_key`;
  - attachment: `line + "⟦" + source + "⟧"` is.

  This checks the case against the draft GT *locally*. The draft GT also drops headers and margin notes, so the whole page will never equal the draft; don't test for that. A conformance failure means the anchor or the draft GT disagrees with the other. Report it to the owner, who fixes whichever is wrong.

If you believe a case is missing (an instruction mark in a scan with no case), surface it with a crop. Never add it yourself.

---

## 4. Phase 0 — instruments and baseline (before any bet)

**4.1 Fixture validity.** Load all 10 fixtures: GT parses in both formats, gold pages exist, and the P2 exam spec for the new rubric is derived by `spec_from_rubric_draft` plus the same enrichment procedure used for Hobby. Generate the enrichment; never hand-tune it to fixtures, which would be overfitting by construction.

**4.2 Conventions audit.**
- **Tables (OD-T1: the convention already exists in the code).** Find it; don't invent one.
  - Locate every place that writes or reads a transcribed table: the P1 prompt, any parser or detector in the backend, the review UI's table detector (`utils/detect-table-runs.ts` or its transcription-side counterpart), and `TRANSCRIPTION_GT_CONVENTIONS.md`.
  - Report the convention with file:line citations and real examples: row/column layout, header, column order, empty cells, and how a literal `|` inside a cell is written.
  - Report whether the raw and draft GT tables of the new fixtures follow it.
  - If the implementations **disagree with each other**, or the GT doesn't follow them, STOP on tables and surface it. Tables can't be scored against a format that isn't single.
- **Arrows:** run the §3.4 validator and report its full output.

**4.3 Three additive diagnostics.** These are new modules; nothing in the gate path changes. Each ships with self-tests: GT-vs-GT scores exactly 1.0, and hand-perturbed predictions with known errors score as expected. Instrument bugs have silently corrupted conclusions here four times; assume yours has one until the self-tests say otherwise.
- **Hebrew-projection ratio.**
  - Project GT and prediction onto Hebrew-script characters only (U+0590–U+05FF, after the suite's normalizer), then compare with difflib, `autojunk=False`.
  - Report per answer, per page and per doc: P1 against raw GT, e2e against draft GT. Also report Hebrew word error rate.
  - The projection is blind to code and punctuation by design; it isolates the Hebrew canary.
- **Table metric.**
  - Parse tables in GT and prediction with ONE parser for the convention found in §4.2. If the code already has a parser for it, reuse that one rather than writing a second (one concept, one place).
  - Report: tables found vs expected, shape exact per table, and cell exact-match after normalization (micro and per doc).
  - Also report structure breakers: cells containing `|` or `||`, empty cells, ragged rows.
  - The parser must agree with the review UI's table detector (table-editing PR, R5); report any divergence.
- **Arrow metrics.** From `insertion_cases.json`, using the pipeline's own relocation records:
  - **placement:** an insertion's text sits at its boundary; an attachment's ` ⟦note⟧` sits at the end of its line. In both cases the text is gone from its source.
  - **false relocations:** applied relocations matching no insertion or attachment case. Report the subset that landed on a **decoy** separately; that is the prompt's specific failure.
  - **missed:** cases with no applied relocation.

**4.4 Gold arrows for P2.** In `p2_only` mode, apply the §3.3 function to the gold pages using `insertion_cases.json` as the instruction list, then run P2. This makes P2 measured on intended order, exactly as it is measured on gold pages today. It's also a live test of the relocation function: gold pages + gold cases must satisfy every §3.4 conformance check.

**4.5 Baseline.** Current `PROD_CONFIG`, all 10 fixtures, `p1_only` + `p2_only` + e2e, k=3. Record every diagnostic, cost and latency. The arrow metrics at baseline measure what happens with no relocation at all: every case is missed.

**4.6 Error taxonomy.** Read the diffs; this decides the order of the bets.
- **Every Hebrew error, one class each:**
  - **(a)** letter confusion (ר/ד, ה/ח, ו/ז/ן, ב/כ, ס/ם, final forms)
  - **(b)** dropped or added words
  - **(c)** ORDER errors: reversed characters or words in mixed Hebrew/code lines, a classic VLM bidi failure
  - **(d)** normalization: the model «fixed» the student
  - **(e)** suspected GT error
- **Tables:** shape errors vs cell errors, and which cell contents fail.
- **Arrows:** what P1 does today with the ink of each case.

**The taxonomy is a fork:**
- mostly (c) → an order instruction or a deterministic bidi check, not a new model;
- mostly (a)/(b) → focus and resolution (Bet 4);
- (d) → the prompt;
- (e) → surface it.

→ **Checkpoint 1** (§9). Don't wait on it: start Bet 1 immediately.

---

## 5. Hypotheses behind the bets (why this order)

- **H-P1.** Most of the P1 wall is the model. `gemini-3.1-pro` is no longer on the vision frontier of the leaderboard, and newer models from the same family are *cheaper* (§7). A model swap is the one change that can move all three dimensions at once, so it goes first.
- **H-FOCUS.** Hebrew and table errors are FOCUS failures: a code-dominated page read in one pass, at a resolution shared with everything else, starves the small Hebrew lines.
  - A crop gives effective resolution without the full-page cost. (Full-page resolution was already falsified as a lever: 2000→2400 px moved nothing and cost +59%.)
  - Crops are also the only way a frontier model fits the cost gate. Transcription cost is dominated by OUTPUT tokens, and a crop reader emits a line, not a page.
- **H-ARROW.** An arrow is ink, and perception's job is to report ink. P1 should report each instruction as structured data beside the physical text. Applying it is the pure §3.3 function between P1 and P2. This keeps P1 spec-blind and verbatim, keeps raw-GT scoring untouched, and makes false relocations countable instead of implicit.
- **Against merging the Hebrew pass into the strike check (the owner's suggestion, tested rather than assumed).** If H-FOCUS is right, giving one call two jobs is the wrong direction. The merge saves one call per page. Bet 4 runs both variants and the diagnostics decide.

---

## 6. The bets, top-down

For each bet, write the hypothesis, the predicted effect per dimension and the kill criterion in RUNLOG, and the prediction in `PREDICTIONS.md`, *before* running. Skip a later bet if an earlier one already met its dimension's target.

### Bet 1 — P1 model sweep
1. **Cost pre-screen (no API calls).** Reprice the baseline's per-doc input/output tokens (including thinking tokens) with each candidate's price card. Drop any candidate that can't fit C2 even with thinking at its lowest useful setting. Take prices from the providers' own pages, not the leaderboard, and add them to the eval price registry.
2. **Screen.** Survivors × current P1 prompt × all 10 fixtures × k=1, `p1_only`. Rank by the worst doc on each diagnostic plus `doc_ratio_strict`, then by cost.
3. **Finalists (top 2–3).** Each gets ONE prompt-adaptation pass for its family: the prompt was tuned on Gemini, so a fair comparison lets the challenger speak its own dialect. Then k=3, then e2e.
4. **Also sweep, on finalists only:**
   - thinking/reasoning effort, low vs medium;
   - `pages_per_call` 1 vs 3. One page per call is a cheap focus lever: same image tokens, more parallelism, a little prompt overhead.
- **Kill:** no candidate beats the incumbent on the worst doc of any dimension within the cost gate → keep the incumbent and go to Bet 3.

### Bet 2 — Table adherence (after §4.2 has established the convention)
Tighten the P1 prompt's table instruction so it produces the implemented convention exactly: empty cells left empty, header verbatim. Run it on the Bet-1 winner.

**The known hazard is a literal `|` inside a cell,** because trace tables carry `||` conditions. If the implemented convention already says how to write one, enforce it. If it says nothing, surface the gap. Don't invent an escape: it would have to change the review UI's detector too.
- **Kill:** table shape < 100% after one prompt revision → tables need Bet 4's crop machinery.

### Bet 3 — Arrow instructions
- **P1 output schema:** each page object gains
  `instructions: [{kind: "insertion"|"attachment", marker, source: {first_words, last_words}, target: {page, after, before} | {page, line}}]`.
  - Page `text` stays physical and verbatim, so raw-GT scoring is unaffected by construction.
  - The source is identified by first/last words, not full text, to save output tokens. The source span runs from the start of `first_words` to the end of `last_words`, and it must be unique.
- **The relocation function:** a new pure module implementing §3.3 exactly, with zero mocks and exhaustive tests, including every case in `insertion_cases.json` as a fixture. It runs between P1 and P2 over the whole document, not per chunk, so cross-page cases resolve.
  - **Matching is exact after whitespace collapse.** No edit-distance fuzz. Loosening it is a proposal you surface with evidence, because fuzz is how false relocations are born.
  - **Anything unresolved or ambiguous stays in place,** with a flag (review-first, not guess).
- **P1 prompt:** must cover the content below. Adapt the wording to the model family, but not the rules.

> **Instruction marks.** Transcribe every page exactly as written, in its physical position, as you do now. Separately, report any mark by which the student instructs the reader to move text, in `instructions`. Never move text inside `text`, and never add characters the student did not write.
>
> **Insertion.** The student wrote a piece of the answer (code or prose) somewhere else and linked it to where it belongs: with an arrow, a pair of matching symbols (`*`, a numbered star), a caret `^`, or a note such as «המשך». The target may be between two lines or inside a line (e.g. into a condition). Report `kind: "insertion"`:
> - `source.first_words` and `source.last_words`: copied exactly from your own transcription of that page;
> - `target.after` and `target.before`: the text immediately before and after the insertion point, copied exactly from your transcription, with enough words that the pair occurs only once on that page (a full line on each side when possible).
>
> **Attachment.** The student wrote a note (often boxed or in the margin) and drew an arrow onto a specific line. The note comments on that line rather than being part of its content. Report `kind: "attachment"`, with `target.line` set to that complete line exactly as you transcribed it.
>
> **Exact target marks.** Students sometimes mark the exact insertion point with a second mark (a caret, an arrowhead, a small x or a squiggle) separate from where the arrow line ends. When such a mark exists, it defines the target: report the anchors at the mark.
>
> **Not instructions — never report these:**
> - arrows inside a trace table showing flow between rows;
> - `->` or `=>` written as part of code;
> - a connector linking text that is already in reading order (e.g. `{` with an arrow to the statement right after it);
> - arrows pointing at a heading or question number;
> - decorative marks.
>
> **When unsure, don't report.** If you're not sure a mark is an instruction, or not sure exactly where it points, leave it out. The text stays where it is and the teacher checks it against the scan. A missed instruction costs her a glance; a wrong one silently changes the student's answer.

- **Kill:** any false relocation that one prompt revision or a tighter resolution rule can't remove → surface it.

### Bet 4 — The focus pass (Hebrew first, tables second)
This is ONE mechanism, parameterized by region kind (Hebrew line / table), not two passes.
- **Localize.** The P1 winner, or a cheap auxiliary model, returns boxes for Hebrew-script lines (and table regions), keyed to line ids in the P1 page text.
- **Crop and read.** Crop from the full-resolution render, with padding. A specialist reader from §7's crop-reader role gets the crop plus P1's reading of that line, and is told to transcribe verbatim, errors included.
  - Measure (d)-class normalization explicitly. This is exactly where the retired reader-flag layer failed (`i+2` → `i+=2`).
- **Splice by line id.** Deterministic, and it may replace only the text of the line it names.
- **Variant 4b:** the same instruction folded into the existing strike-check call (full page, no crops). Compare 4 vs 4b on the Hebrew worst doc and on cost.
- **Operational class:** OPTIONAL (OD-H1, ruled). It runs under `optional_pass_timeout_s` / `optional_pass_budget_s`, and on any failure or timeout the P1 text stands and the document completes. Never make it essential; that would be a new ruling, not a tuning choice.
- **Kill:** the Hebrew worst doc improves by less than half the gap to target, or (d)-class normalizations appear that one prompt revision can't remove.

### Bet 5 — Only if a dimension is still short and budget remains
Targeted self-consistency: two independent reads of flagged regions only, with disagreement flagged to the teacher. Justify it against the falsification record in `flagging.py` before you build it.

---

## 7. Model shortlist (a prior, not evidence)

The benchlm.ai leaderboard (2026-09-25 snapshot) orders the sweep; it proves nothing.
- Its `multimodalGrounded` column is not handwriting OCR, let alone Hebrew handwriting, and several scores are `estimated`, with wide intervals.
- **When the proxy is weak, sample across model families, not just along the proxy.**
- Resolve exact API model ids from the providers' own model lists; never guess an id.

| Model | $/M in→out | Vision (mm) | Roles | Notes |
|---|---|---|---|---|
| Gemini 3.1 Pro | 2 → 12 | 79.1 (est.) | P1 **incumbent / control** | Baseline for every comparison |
| Gemini 3.8 Flash | 0.75 → 3.75 | 82.9 | P1, aux | Cheaper than the incumbent with a higher proxy score, same family. **Top prior for P1.** |
| Gemini 3.5 Flash | 1.5 → 9 | 86.8 | P1, crop reader | Highest proxy score among Gemini models |
| GPT-6 Sol | 2 → 10 | 82.8 (est.) | P1 | |
| GPT-5.6 Sol | 4 → 20 | 87.6 | P1 (cost-stretch), crop reader | |
| Claude Sonnet 5 | 2 → 10 | 77.4 | P1 | Already in the stack (grader) |
| Claude Opus 5.5 | 4 → 20 | 88.8 | crop reader, P1 (cost-stretch), instruction localization | Strong spatial-reasoning prior; overall score `estimated`. **Top prior for crop reader.** |
| Kimi K3 | 3 → 15 | 89.4 | P1, crop reader | Highest proxy score. Source type «Pending»: verify a paid API exists before spending effort. Weak Hebrew prior — test, don't assume |
| GPT-6 Astra | 10 → 50 | 82.9 | crop reader only | Output price rules it out for full pages; affordable on crops |
| GPT-6 Luna | 0.1 → 0.5 | 71.3 (est.) | aux (localization, strike check), P2 candidate | |
| GPT-5.6 Luna | 0.2 → 1.2 | 67.1 | P2 **incumbent** | Only if a bet touches P2 |

**Excluded, with reason:**
- No usable paid API or price: Qwen3.8 Max, Muse Spark / Spark 1.1, GLM-5.3, dots3, Ornith.
- Vision score null: Fable 5.1, DeepSeek V4, GLM-5.2, Grok 4.6, Muse Spark 1.2.
- Priced far outside any role: GPT-5.x Pro (30 → 180).
- Dominated by a listed model at equal or lower price with a higher proxy score: Opus 5, Opus 4.x, Gemini 3.7/3.6 Flash, Gemini 3 Pro, GPT-5.6 Terra, GPT-5.5, GPT-5.3 Codex, GPT-5.2, Grok 4.5, Fable 5.

If the sweep shows a family systematically beating its proxy score (e.g. on Hebrew), you may add ONE excluded model from that family. Record why.

**Provider plumbing** (new adapters, structured-output handling, price cards) is allowed runner work. Every adapter must record `finish_reason`, tokens (including thinking tokens) and cost per call, or its numbers are invalid.

---

## 8. Decisions

| ID | Decision | Status |
|---|---|---|
| OD-A1 | Raw GT = physical placement; draft GT = intended placement | **Applied** — the owner authored the cases under it. §3.4 confirms the draft GT conforms; nonconformance goes to the owner. |
| OD-A3 | Attachment delimiter `⟦ ⟧` (U+27E6/U+27E7), for every subject. `//` would invent ink (FC) and is CS-only (§3.3 subject leakage). A `//` the student actually wrote stays verbatim wherever it sits | **Applied** — the cases file assumes it; §3.4 confirms the draft GT uses it. |
| OD-T1 | Table serialization | **Ruled: use the convention already implemented in the code.** The agent finds and documents it (§4.2); no new format. |
| OD-A2 | Relocation provenance | **Ruled: silent.** The relocated text simply appears in its place: no annotation, no field on the draft, nothing teacher-facing. Relocation records exist only inside the pipeline run (for the eval metrics) and as one operational log line per document (§3.3 step 4). |
| OD-H1 | The focus pass is OPTIONAL | **Ruled: optional.** On failure or timeout the P1 text stands and the document completes (Bet 4). |

Do not re-open any ruled decision without new evidence. Evidence that could reopen OD-A2 would be a false relocation reaching production that the teacher couldn't have detected from the scan; surface that, don't act on it.

---

## 9. Checkpoints, budget, stopping

- **Checkpoint 1 (after Phase 0).** Report:
  - the baseline with all diagnostics;
  - the taxonomy;
  - the §3.4 validator output and the table conventions audit;
  - suspected GT errors and suspected missing cases, each with a crop;
  - the table-convention finding (§4.2).

  Continue with Bet 1 meanwhile. Bet 2 waits for the §4.2 table finding. Bet 3 can start once the validator is clean.
- **Checkpoint 2 (end).** Report:
  - the recommended config: P1 model and effort, `pages_per_call`, prompts, focus-pass settings, relocation function;
  - e2e k=5 and the `check_goal.sh` output;
  - per-dimension before/after on the worst doc;
  - cost and latency (C2/C3);
  - a **cross-exam breakdown**: every win reported per exam, and a win on one exam only labeled as such;
  - the production change list: provider keys and quotas, the per-model concurrency cap, `budget.py` timeouts for any new pass, `PROD_CONFIG` + engine version bump, the P1 schema change, and the relocation log line (no draft field, no annotation: OD-A2). The identity pass stays untouched.

  **The owner rules the ship.**
- **API spend cap: $60** for the whole mission. Report the running spend in every RUNLOG entry, and surface at 80%.
- **Speed-of-light timeline:**
  - Phase 0: same day.
  - Bet 1 screen: parallel, hours, not days.
  - Checkpoint 2: within 48 h of start.
  - If you're behind, name the step that took longer than it had to, and why.
- **Stop and surface when:**
  - any §1 absolute is about to be crossed;
  - a dimension goes 3 consecutive bets without improving its worst doc (the per-dimension no-progress breaker);
  - a win appears on one exam with a regression on the other;
  - a GT error or a §3.4 failure blocks a dimension;
  - any false relocation survives Bet 3.
