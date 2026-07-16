# P1 Eval Playbook — agent-executable

**Audience:** a coding agent analyzing one Phase-1 transcription eval run.
**Goal:** produce the analysis deliverable defined in §5 — clear, decision-ready,
in under one pass over the artifacts. Follow the procedure in order; apply the
decision rules verbatim; never skip the validity step.

---

## 1. Context you must hold while analyzing

**What is being measured.** Phase 1 of a two-phase pipeline: image → VERBATIM
per-page transcription of handwritten Israeli CS (Bagrut) exams — Java-like code
+ Hebrew comments. "Verbatim" is load-bearing: student errors (misspellings,
`While`/`Public` capitalization, missing `;`, wrong brackets, abbreviations
`CW`/`CR`) are GRADED CONTENT. A transcription that fixes them is WORSE than one
that misreads, because it silently erases Bagrut deductions. The downstream
grade depends on fidelity, not fluency.

**The metric semantics (each number isolates one failure mode):**
- `doc_ratio_strict` — difflib ratio after NFC + lowercase + strip ALL
  whitespace; `[?]` counts as a miss. The bulk-perception signal.
- `doc_ratio_lenient` — same with `[?]` removed. `lenient − strict` = honest
  abstention. Abstention is reviewable; confident error is invisible.
- `coverage` / `missing_pages` — structural integrity. Empty/whitespace-only
  predictions count as MISSING (an empty page can never hide behind a ratio).
- `operator/structural/method_call_recall`, `abbreviations_altered` —
  case-SENSITIVE grading-critical fidelity. These catch unauthorized edits the
  ratio is blind to (`==`→`=`, dropped `;`, `CW`→`Console.WriteLine`).
- The gate is CONJUNCTIVE: ratio ≥0.98 AND coverage=1.0 AND critical recalls
  =1.0 AND no abbreviation alterations. A doc passes only if ALL hold.
- `parse_ok` / `finish_reason` per call: `length`/`MAX_TOKENS` on a failed
  parse = truncation (config problem); other reasons = malformed output
  (model/schema problem).
- Stage timing: `pdf_render`, `image_encode`, `p1_call_sum` (total model time),
  `p1_call_max` (≈ wall, chunks run concurrently), `queue_wait_ms` (scheduler
  limit, not model).

**Instrument history — why you must stay suspicious.** This instrument has been
caught lying four times before any model decision was made on its numbers:
single-metric gate, mis-specified error label, cross-answer cancellation, and
difflib `autojunk` silently corrupting ratios on pages ≥200 chars (a
0.88-similar page scored 0.21). All fixed and pinned by regression tests. The
standing rule it teaches: **when a score contradicts its own diff, suspect the
instrument before the model**, and verify with a 5-line recomputation before
concluding anything.

**Files per run** (under `tests/transcription_eval_suit/results/<run>/`):
`results.json` (machine truth), `summary.md` (human digest),
`report_<doc>.md` (per-page gold|pred diffs + named misses).

---

## 2. Procedure (in order, no skipping)

### Step 0 — Validity before significance
1. `parse_failure_total > 0`? → for each record with `parse_failures > 0`, mark
   that doc **INVALID — contaminated** for accuracy purposes. Read
   `parse_failure_finish_reasons`: `length`/`MAX_TOKENS` → diagnose TRUNCATION
   (fix: raise `p1_max_tokens` or shrink `p1_pages_per_call`); anything else →
   malformed output (fix: model/schema).
2. Confirm `models.*.model_id` is the intended model. Wrong model = whole run
   invalid.
3. Confirm `config` matches the intended config diff (one field vs the
   comparison run).

### Step 1 — Classify each failing doc into a failure family
From `gate.reasons` per doc, assign families (a doc can have several):
- **STRUCTURAL** — `coverage < 1.0` / `missing_pages` non-empty. Suspect, in
  order: parse degradation (check step 0), chunk-boundary correlation (missing
  pages at multiples of `p1_pages_per_call`), page-number misattribution.
  Fix surface: config/parsing, NOT image or model quality.
- **PERCEPTION** — `doc_ratio_strict < 0.98` with diffs showing misread
  characters. Fix surface: model choice, DPI, image params.
- **FIDELITY (instruction-following)** — critical-recall floors or
  `abbreviations_altered`. The model edits while reading. Fix surface: model
  choice first, prompt-hardening second. Image quality is irrelevant here.

### Step 2 — Cheap high-information diagnostics
- `lenient − strict` gap per doc: near-zero gap + low strict = confidently
  wrong (worse); large gap = honest abstention (better, reviewable).
- Worst doc: judge any config change by whether it moves the WORST doc, not
  the mean. Note whether the worst doc is stable across runs (fixture
  difficulty) or moved (config effect).

### Step 3 — Diff reading (failing docs only, worst pages first)
Classify every meaningful discrepancy into exactly one bucket, quoting the
evidence line:
1. **MISREAD** (perception): `chlRates`→`chlRate`, `getisSportive`→`getisSortive`.
2. **UNAUTHORIZED EDIT** (fidelity — the dangerous bucket): added/fixed
   punctuation, `While`→`while`, `CW`→`Console.WriteLine`, `Tv Show`→`TvShow`,
   quote-insertion (`y`→`'y'`), bracket "fixes". Each erases a potential
   deduction.
3. **LAYOUT DRIFT** (usually metric-invisible): line merges, RTL/Hebrew
   reordering. Eyeball for Hebrew mangling; difflib underpenalizes it.
4. **SUSPECTED GT BUG** (model right, fixture wrong): extra ink the GT lacks
   (student margin notes, printed page numbers), author typos. These become
   verification tasks for Noam, NOT model findings.
Heuristic at repeats>1: same page failing with the SAME diff across repeats =
systematic; DIFFERENT diffs = provider instability (a finding at temp 0).
Plus the standing rule: any ratio that contradicts its own diff → recompute it
standalone (autojunk-class instrument check) before reporting it.

### Step 4 — Latency & cost, structurally
- Wall structure ≈ `pdf_render + image_encode + p1_call_max`. If
  render/encode ≥ ~20% of wall → name it as free latency (parallel render /
  faster renderer / DPI) before any accuracy-relevant change.
- `queue_wait_ms` high → scheduler/tier is the bottleneck; no model swap helps.
- Cost: `cost_avg_per_doc_usd` vs $0.08 ceiling AND per-page (÷ pages) for
  transferability; state the headroom multiple (matters for escalation design).
- Honesty: per-doc latency is median/min/max only; never report a p95 outside
  batch mode; a cross-run "trend" must exceed the min–max spread of either run.

### Step 5 — Cross-run comparison (when a previous run-log line is provided)
One config field per comparison, identical fixtures/repeats. Demand the delta
appear in the metric the change targets; a delta in a different metric =
confound, flag it. Update the one-line run log.

---

## 3. Decision rules (apply verbatim)

| Observation | Conclusion you MUST draw | Conclusion you must NOT draw |
|---|---|---|
| parse failure on doc | doc invalid this run; diagnose via finish_reason | "model can't read this student" |
| missing pages at chunk boundaries | chunking/attribution failure | perception failure |
| critical-recall floor failed, ratio high | fidelity failure (model edits) | "image quality issue" |
| ratio contradicts its own diff | instrument suspect — verify by recomputation | accept the number |
| worst doc unmoved, mean improved | change did nothing for real risk | "config improved accuracy" |
| gate passes | "≥98% on these N students" | "98% accurate" |
| n < 10 fixtures | conclusions provisional, overfit risk to this exam | any generalized model ranking |

---

## 4. Standing epistemic cautions
(1) n=5 docs, one exam: every conclusion provisional against handwriting
variance and this exam's identifier vocabulary. (2) Difflib + critical tokens
passing ≠ grade-safe; it means the measurable failure modes didn't fire — read
two diffs manually per run as the check on the instrument itself. (3) The
binding resource is iteration cycles: misattributing a failure family wastes
one; the deliverable exists to prevent that.

---

## 5. REQUIRED OUTPUT — "P1 Eval Analysis" (exact structure)

Produce a markdown document with exactly these sections, in this order.
Every claim must cite its number or quote its diff line. No section may be
omitted; write "none" where empty.

```markdown
# P1 Eval Analysis — <run_dir>

## 0. Run identity & validity
- config / model_id / prompt_version / repeats / fixtures: ...
- contaminated docs: <doc: n parse failures, finish_reasons, diagnosis> | none
- instrument suspicions raised: <ratio-vs-diff contradictions + verification result> | none

## 1. Verdict
- Gate: PASS/FAIL (N/M docs) · Cost: $X.XXXX/doc (PASS/FAIL vs $0.08, Yx headroom)
- One-sentence headline: <the single most decision-relevant fact of this run>

## 2. Failure-family classification
| doc | ratio_strict | lenient−strict | families | invalid? |
|---|---|---|---|---|
(one row per doc; families ∈ STRUCTURAL / PERCEPTION / FIDELITY)

## 3. Evidence (failing docs only)
Per doc: 2–5 bucket-classified findings, each with the quoted diff line.
Mark UNAUTHORIZED EDITS explicitly — they are the grade-corrupting class.

## 4. GT verification tasks for Noam
- <fixture, page, what to check against the PDF> | none

## 5. Latency & cost structure
- wall ≈ render X s + encode Y s + p1_call_max Z s; queue_wait: W
- free-latency findings; per-page cost; headroom multiple

## 6. Comparison vs previous run
(only if prior log line provided; else "first measured run of this config")

## 7. Recommendation — the ONE next change
- The single highest-information config/code change, the metric it must move,
  and the kill criterion. Secondary candidates as one-liners.

## 8. Run-log line (append to RUNLOG.md)
`<date> | <config> | <diff-vs-prev> | gate F (k/5) | worst <doc> <ratio> | med <s> | $<cost> | <one-clause note>`
```

The analysis is DONE when: every doc is classified, every contaminated doc is
excluded from conclusions, every UNAUTHORIZED EDIT instance is quoted, the
recommendation names one change + one target metric + one kill criterion, and
the run-log line is written.