# Transcription Eval Suite — Module Documentation

> **Audience:** an engineer or coding agent with ~zero prior knowledge of the
> transcription / question-segmentation feature and its evaluation harness.
> After this doc you should understand *what the feature does and why*, *what the
> eval suite measures and how*, *how to run it*, *how to read its output*, and
> *how to extend it* — with enough context to make a safe change or run a trial.
>
> **Companion docs (read after this):** `p1_eval_playbook.md` and
> `P2_EVAL_PLAYBOOK.md` — the step-by-step procedures for analyzing a single run.
> This doc is the *map*; the playbooks are the *driving instructions*.

---

## 0. TL;DR

This folder is a **golden-set evaluation harness** for Vivi's handwritten-exam
**transcription + question-segmentation** feature. It runs the real two-phase
pipeline (or isolated phases) over 5 hand-graded student exams, scores the output
against two ground truths, and emits machine-truth + human-readable reports plus a
pass/fail gate. It exists so we can **iterate the pipeline (model, prompt, config)
with measured evidence instead of vibes**, and so a change that helps one student
but silently corrupts another's grade is caught before it ships.

It is a **test/eval harness, not production code** — but it calls the *real*
production providers (OpenAI / Gemini / Anthropic), so a run costs real money and
needs real API keys.

---

## 1. The product feature under evaluation

### 1.1 What the feature is
Vivi is an AI **Teacher's Assistant** (see `vivi-codebase/CLAUDE.md`). One of its
three pipelines turns a **scanned PDF of a student's handwritten exam** into
**structured, per-question answers** the grader can consume. That conversion is two
jobs:

1. **Phase 1 — Transcription (perception):** image → VERBATIM text, page by page.
   "Read the ink exactly as written."
2. **Phase 2 — Segmentation (interpretation):** the flat per-page transcription +
   the exam's question structure → text assigned to each `(question, sub-question)`
   answer. "Decide which code belongs to Q1.א vs Q2.ב, joining across pages."

The first vertical is **Israeli CS Bagrut exams**: handwritten Java/C#-like code
with Hebrew comments and section markers (`שאלה 1`, `א.`).

### 1.2 Where it sits in the product (the review gate)
```
student PDF ─► /transcribe (P1 VLM)  ─►  TranscriptionDraft
                                          │  TEACHER REVIEWS vs source PDF  (TRANSCRIPTION GATE)
                                          ▼  /grade → TranscriptionContract (frozen)
                                     grading consumes the APPROVED contract
```
Transcription is a **mandatory review gate**: the teacher checks the transcription
against the source PDF *before* grading runs. Grading only ever consumes an
*approved, frozen* `TranscriptionContract`. (Phase-2 segmentation is the structure
that makes that contract per-question.)

### 1.3 The UX goal and its load-bearing tradeoff
**North-star UX goal:** reduce a teacher's after-school grading hours while keeping
the teacher the authority. The product never finalizes a grade; it proposes,
the teacher decides. So the transcription/segmentation output must be **fast to
review and trustworthy**, not "creative."

**The load-bearing tradeoff — VERBATIM FIDELITY over fluency:**
> A student's *errors are graded content.* A misspelling, a `While`/`Public`
> miscapitalization, a missing `;`, a wrong bracket, an abbreviation `CW`/`CR` — each
> is a Bagrut deduction. A transcription that "helpfully" fixes `Mobby`→`Hobby` or
> expands `CW`→`Console.WriteLine` is **WORSE than one that misreads**, because it
> *silently erases a deduction the teacher would have taken.* The downstream grade
> depends on fidelity, not fluency.

This is why every prompt in this pipeline says "copy exactly, fix nothing," why the
metrics are case-sensitive and catch unauthorized edits, and why correction is a
*separate, deterministic, defaulted-off* post-pass (§7) rather than something the
LLM is allowed to do.

### 1.4 Functional requirements (what "correct" means)
- **F1 — Verbatim:** P1 transcribes ink exactly (errors preserved); P2 copies text
  verbatim into answers (never edits, expands, or normalizes).
- **F2 — Complete coverage:** every page is transcribed; every spec answer key
  receives its content (no dropped page, no empty answer, no refusal).
- **F3 — Correct segmentation:** each code unit lands in exactly one answer
  (a *partition* — no merge, no duplication), routed **by content** (which spec
  entity its signature implements), not by the student's possibly-wrong marker.
- **F4 — Abstention over guessing:** illegible ink is marked `[?]`, never invented
  — an `[?]` is reviewable; a confident wrong read is invisible.
- **F5 — Identity/chrome excluded:** student name/class/ID and section markers are
  not answer content.

### 1.5 Non-functional requirements
- **N1 — Cost:** ≤ **$0.08 / document** average (the locked cost gate).
- **N2 — Latency:** end-to-end is dominated by P1 (render + VLM call); P2 is one
  cheap text-only call. Per-doc latency is reported median/min/max (a p95 is only
  honest in `batch` mode).
- **N3 — Per-unit failure isolation:** a bad page/answer degrades that unit, never
  the batch (a parse failure is a *recorded metric*, not a thrown run).
- **N4 — Determinism boundary:** the LLM call is the only non-deterministic stage;
  everything around it (parsing, scoring, gating) is pure and exhaustively tested.
- **N5 — Subject-agnostic engine:** the scoring engine and pipeline are
  subject-neutral; CS-specific token vocabulary lives in a swappable
  `CriticalProfile` (`JAVA_BAGRUT`), never hardcoded in the engine.

---

## 2. The pipeline under test (production code it exercises)

The harness drives the production transcription pipeline, re-implemented as a
config-parameterized factory in `pipelines.py` (it reuses the production PDF
renderer, VLM providers, and scheduler).

```
PDF bytes
  │  pdf_render (dpi)                         [pipelines.Pipeline.run_phase1]
  ▼
page images ──► image_encode (resize ≤ image_max_px, pack multi_image|stitched)
  │  chunked by p1_pages_per_call, dispatched CONCURRENTLY through the scheduler
  ▼
PHASE 1  (VLM, image+text)  ── P1_SYSTEM prompt, JSON schema ──►  per-page verbatim text
  │
  ▼
PHASE 2  (LLM, TEXT ONLY)   ── P2 prompt + exam spec ──►  per-(question,sub) answers
  │  [pipelines.Pipeline.run_phase2]   never sees the image
  ▼
corrector.py  (deterministic, pure, governed by correction_policy; OFF by default)
  ▼
PipelineRun { pages, answers, corrected_answers, routing_notes, spec_mismatches, trace }
```

Key shapes (`pipelines.py`):
- **`PipelineConfig`** (frozen) — every knob (§6). `v0` is a config; every later
  variant is a *config diff*, never a code branch.
- **`Pipeline`** — `run_phase1(pdf)→pages`, `run_phase2(pages, spec)→answers`,
  `run(pdf, spec)` = both. Phase 1 chunks pages and runs chunks concurrently under a
  document priority through `ProviderScheduler`.
- **Parse policy (D2):** each VLM call's text goes through one defensive parser
  (`parsing.parse_model_json`); on failure → ONE re-request; on second failure →
  a degraded empty result recorded with `parse_ok=False` (truncation on a
  `MAX_TOKENS`/`length` finish_reason is *not* re-requested — it's deterministic;
  raise `p1_max_tokens` instead).

### Phase 1 prompt (`prompts.P1_SYSTEM`, version `TRANSCRIPTION_PROMPT_VERSION`)
"Transcribe ink VERBATIM." Preserve every student error (misspellings, wrong
capitalization, wrong comment delimiters, wrong identifiers); **never expand `CW`/`CR`**;
fix nothing; output section markers as `שאלה {n}` / `א.`; **exclude printed material
and the student identity block** (name/class/ID); `[?]` for illegible; preserve line
breaks; plain text only. Output `{"pages":[{"page_number","text"}]}`.

### Phase 2 prompt (`prompts._P2_BASE`)
"SEGMENTATION ONLY — never correct/complete/improve." Two explicit steps:
**STEP 1 find boundaries** (split into distinct code units), **STEP 2 label by
content** (assign each unit to the `(question, sub-question)` whose spec names its
class/method). **Content is the sole labeling authority** — a section marker is a
*hint*, never authority; on a marker-vs-content conflict, *content wins, always*.
**Exclusivity** — a correct segmentation is a partition: every unit in exactly one
answer, no unit dropped, no unit duplicated. Must emit best-effort output for every
target (never refuse / never all-empty). Output includes a `segmentation_plan`,
`answers[]` (each with an `anchor` = the spec entity it implements), and
`routing_notes[]` (self-reported relocations — *a claim to verify, not trust*).

---

## 3. Eval-suite architecture (module map)

> **2026-07-08 relocation:** the pipeline CORE (pipeline, prompts, parsing,
> keys, corrector, instrument) moved to `app/services/transcription/two_phase/`
> — production now runs the exact code the suite measures. The suite files
> below marked *(shim)* re-export from there; the suite's import surface,
> tests, and configs are unchanged. Eval-only pieces (GTs, scoring, gate,
> registry, runner) remain here.

| File | Responsibility |
|---|---|
| `runner.py` | **Orchestrator + CLI.** Resolves fixtures, builds the pipeline, runs the chosen mode, scores, writes artifacts. `python -m tests.transcription_eval_suit.runner …` Registers ONE provider adapter PER MODEL KEY (aliased) — never per vendor. |
| `pipelines.py` *(shim)* | The pipeline-under-test: `PipelineConfig`, `Pipeline`, image prep, parse-retry policy, the deterministic-correction call. Trust layer: `reader_model_keys` runs diverse second-reader models over the same pages. |
| `prompts.py` *(shim)* | Versioned P1 + P2 prompts and their JSON schemas. `TRANSCRIPTION_PROMPT_VERSION` stamps every result. |
| `flag_metrics.py` | **The trust-gate instrument** (separate from `scoring.py`; the accuracy gate is untouched): scores the trust layer's disagreement flags against raw GT — error/critical flag recall, burden by severity, missed-critical details. Flags come from `app/services/transcription/flagging.py`; page provenance from `page_provenance.py`. |
| `parsing.py` | Defensive VLM-JSON parser; **exam-spec loader** (`ExamSpec`, `ExamQuestion`, `ExamSubQuestion`) from a canonical spec JSON or a rubric `draft.json`. Each sub-question carries a **content signature** (the method it expects) — what P2 routes by. |
| `ground_truth.py` | The two GT formats + pure parsers: `GoldDocument` (per-answer, draft GT) and `GoldPageDocument` (per-page, raw GT). |
| `keys.py` | `normalize_sub_id` / `normalize_key` — collapses label formats (`א`/`a`/`A`/`1`/`א.`) so *label noise* never pollutes the *segmentation* metric. |
| `normalize.py` *(in `app/services/transcription/`)* | The ONE shared text normalizer used by scoring: NFC → lowercase → strip ALL whitespace; lenient also drops `[?]`. Shared with production (one definition of "equal"). |
| `critical_tokens.py` | The grading-critical signature: `CriticalProfile` (`JAVA_BAGRUT`), `extract_signature` (operators / structural / method-calls / abbreviations). Case-sensitive except two narrow folds (§5.3). |
| `scoring.py` | The pure scorer: `score_document` (P2/e2e), `score_page_document` (P1), `ScoringPolicy`, `GateConfig`, `gate_pass`, `measure_corrections`. Defines the **conjunctive gate**. |
| `corrector.py` | The deterministic post-pass (`off`/`impossible`/`spec`) and its safety model (§7). |
| `report.py` | `write_summary` (the one-screen scoreboard) + `write_doc_report` (per-answer/page gold\|pred diffs). |
| `instrument.py` | `Trace`, `CallRecord`, `Span`, `cost_usd`, `PriceCard` — timing + cost accounting. |
| `models_registry.py` | The model registry: key → provider/model_id/`PriceCard`/tier/capabilities. The only file that rots when prices/models change. |
| `configs/*.json` | Named `PipelineConfig` presets (`v0`, `v0_p1_only`, `v0_p2_correct_spec`). |
| `pdfs/`, `raw_benchmarks/`, `draft_benchmarks/` | The 5 fixtures: source PDF + raw GT + draft GT, one file each, stem = `doc_id`. |
| `draft.json` | The rubric draft used as the exam spec (`--exam-spec draft.json`). |
| `results/<ts>_<config>/` | Per-run artifacts (gitignored — they contain student text). |
| `RUNLOG.md` | One line per run: the append-only history of what changed and what it did. |
| `p1_eval_playbook.md`, `P2_EVAL_PLAYBOOK.md` | The analysis procedures. |
| `test_*.py` | Zero-mock unit tests of the pure parts; provider/LLM tests inject fakes (never call a real API). |

---

## 4. The two ground truths (do not confuse them)

The single most important conceptual point: **two GTs score two different surfaces.**

| GT | Folder | Format | Scores | Contains |
|---|---|---|---|---|
| **Raw GT** | `raw_benchmarks/` | `=== PAGE n ===` (`GoldPageDocument`) | **Phase 1** (perception) | ALL ink: code, comments, section markers, margin notes. Verbatim. |
| **Draft GT** | `draft_benchmarks/` | `=== Q1.א ===` (`GoldDocument`) | **Phase 2 / end-to-end** (answer content) | ONLY gradeable answer content per `(question, sub)`. **Deliberately excludes** section markers, margin notes, identity. |

This asymmetry is **intentional**. An answer that lacks a margin note is *correct*,
not a content-drop bug. Because draft GT excludes the hard-to-read Hebrew comments
and headers, an end-to-end ratio can legitimately be *higher* than the P1 ratio —
that is GT-scope asymmetry, **not** correction masking. Never flag an intentional
draft-GT exclusion as a P2 failure.

Both formats: errors preserved verbatim, `[?]` for illegible, crossed-out ink
dropped, contiguous numbering enforced by the parser.

---

## 5. Metrics & the gate

### 5.1 The difflib ratio (bulk perception)
`doc_ratio_strict` — `difflib.SequenceMatcher(autojunk=False).ratio()` after the
shared normalizer (NFC + lowercase + **strip all whitespace**). Whitespace- and
case-insensitive by design, so layout/indentation and case are *not* penalized here.
`doc_ratio_lenient` = same with `[?]` removed; `lenient − strict` = honest abstention.
**`autojunk=False` is load-bearing** (the default once scored a 0.88-similar page at
0.21).

### 5.2 Segmentation integrity (P2's core job)
- **`coverage`** = fraction of draft-GT keys that received predicted content (after
  `normalize_key` canonicalization). `<1.0` ⇒ a key got dropped or misrouted.
  *Caveat:* an answer emitted with empty text still counts toward coverage — coverage
  is **key-present, not content-correct**; read it alongside the per-answer ratio.
- **`missed_keys` / `extra_keys`** = GT keys with no prediction / predicted keys not
  in GT. The structural segmentation signal.
- **`routing_notes`** = P2's self-reported relocations — verify against GT, never
  trust blindly.

### 5.3 Critical-token fidelity (`critical_tokens.py`)
Run on **RAW** (whitespace-preserving) text — the opposite of the difflib normalizer
— because exact form *is* the signal. Per answer, micro-averaged to the doc:
- **`operator_recall`** — `==`, `!=`, `<=`, `&&`, `=`, `+=`, `++`, … (flipping one
  changes control flow).
- **`structural_recall`** — `; { } ( ) [ ]` (a dropped `;` or `()` is a deduction).
- **`method_call_recall`** — set of identifiers immediately followed by `(`
  (a misread `GetRate`→`GetRates` is a deduction).
- **`abbreviations_altered`** — `CW`/`CR` whose count dropped (a drop or an
  EXPANSION to `Console.WriteLine`, which erases a deduction).

Two narrow, grade-irrelevant **case folds** (both fold *only* letter case, never an
expansion or identifier-content change):
- **Change A (abbreviations, unconditional):** `\bCW\b` matches case-insensitively →
  `CW`→`cw` is *not* flagged (pure case); `CW`→`Console.WriteLine` removes the token
  and *is* still flagged.
- **Change B (method-call keywords, `ScoringPolicy.case_insensitive_keywords`,
  default ON):** `For()`/`for()` compare equal; a real identifier (`GetRate`) stays
  case-exact. ⚠ **A run with this ON is NOT comparable on `method_call_recall` to a
  case-sensitive baseline** — the RUNLOG marks the break.

### 5.4 The gate (`GateConfig` / `gate_pass`) — CONJUNCTIVE
A document passes only if **ALL** hold:
```
doc_ratio_strict ≥ 0.98
AND coverage == 1.0
AND operator_recall == 1.0
AND structural_recall == 1.0
AND method_call_recall == 1.0
AND abbreviations_altered == ∅
```
Floors start at 1.0 by deliberate choice (every miss is a potential mis-grade); the
*burden of proof is on relaxing them with eval evidence*. `is_error` per answer =
`ratio_strict < 0.98 OR any critical miss`. Thresholds live in one place
(`GateConfig`) so they're calibratable. Cost gate is separate: `cost_avg_per_doc ≤
$0.08`.

> **Why the gate is so strict (and the standing tension):** for a Bagrut grader a
> single wrong method-name or dropped `;` can mis-grade, so 1.0 is the principled
> default. Multiple runs (model + resolution + prompt sweeps) show `method_call_recall`
> plateaus ~0.7–0.87 on this handwriting even when the remaining misses are case or
> GT typos — so "is the 1.0 floor calibrated to achievable handwriting fidelity?" is
> a live, evidence-backed open question, not a settled fact.

---

## 6. Run modes — the attribution instrument

A bad end-to-end answer has up to four causes (P1 misread, P2 mis-segmentation, P2
fidelity drift, correction error). One number can't separate them; **the modes do.**
Set with `--mode`:

| mode | data flow | scored vs | isolates |
|---|---|---|---|
| **`p1_only`** | PDF → P1 pages | raw GT | **pure perception** (no spec/draft GT needed) |
| **`p2_only`** | **gold pages** → P2 | draft GT | **pure segmentation** (perception held perfect) |
| **`per_doc`** | PDF → P1 → P2 | draft GT (+ P1 vs raw GT) | **the SHIP GATE** (the real mix) |
| **`batch`** | fixtures replicated to `--batch-size`, shuffled, run concurrently | draft GT | throughput/latency under load (the only honest p95) |

**The attribution identity (memorize it):** for the same fixture, `e2e ≈ p2_only −
(perception cost segmentation can't recover)`. Therefore:
- `p2_only` HIGH, `e2e` LOW → the gap is **P1 perception**; fix P1.
- `p2_only` LOW → **P2 segmentation/correction** is broken independent of perception;
  fix P2.
- `e2e ≥ p2_only` with corrections on → **masking/cancellation**; investigate before
  celebrating.

`per_doc`/`batch` run P2 (`p2_model_key` set) so they require `--exam-spec`. `p1_only`
needs none. **Attribution needs both `p2_only` and `per_doc`**; with only one, mark
the analysis PARTIAL.

---

## 7. The deterministic corrector (`correction_policy`)

After P2, `corrector.py` runs as a **pure function over each answer** (the LLM never
sees correction logic — that keeps the verbatim/anti-contamination property intact
while letting prod-realistic post-repair numbers appear). It repairs *artifact*
tokens without overwriting *gradeable student errors*. Governed by `correction_policy`:

| policy | repairs toward | risk |
|---|---|---|
| **`off`** (default, all current runs) | nothing (no-op) | none |
| **`impossible`** | language **keywords** only (`doble`→`double`, `pubic`→`public`), edit-distance ≤2, unique target, length ≥5 | **safe** — keywords are never answer content |
| **`spec`** | keywords **+ spec identifiers** (`Mobby`→`Hobby`, `GetArrShow`→`GetArrShows`) | **ON TRIAL** — spec identifiers ARE answer content, so this tier can erase a real student error |

Guardrails (always): `CW`/`CR` protected; keyword *casing* never corrected; a token
corrects only if exactly one target is within edit budget (ties/none → left, flagged).

**The `spec`-tier kill criterion (`measure_corrections` → `aggregates.correction`):**
a **false-fix** (correction overwrote a token the faithful GT confirms the student
wrote) is the kill count — any non-trivial `false_fix` on the `spec` tier kills it.
And **`trustworthy` is false at n<10 or with no deliberately-included
student-spec-errors** — then `false_fix=0` is *underpowered, not safe*; you may not
claim safety. A positive `ratio_delta` does not license a tier that produced any
false-fix.

---

## 8. Configs (`configs/*.json` → `PipelineConfig`)

One JSON per named config; `--config v0` loads `configs/v0.json`. Fields:

| field | meaning |
|---|---|
| `p1_model_key` | P1 model (registry key, e.g. `gemini-3.1-pro-preview`) |
| `p1_pages_per_call` | pages per P1 VLM call (chunk size; fewer = more calls) |
| `p1_image_packing` | `multi_image` (separate images, resolution-preserving) or `stitched` (one tall PNG, downscale risk) |
| `dpi` | PDF render DPI (200) |
| `image_max_px` | longest-edge resize cap. *Note:* at dpi 200 an A4 page renders ~2338 px, so 2000 downscales; **raising it to 2400 was trialed and FALSIFIED** — no `method_call_recall` gain, +cost/latency, a truncation (see RUNLOG). |
| `p1_max_tokens` | P1 output cap (×`pages_per_call` at call time). Too low → `MAX_TOKENS` truncation → page loss → invalid doc. |
| `p2_model_key` | P2 model (empty ⇒ Phase 2 disabled = `p1_only`) |
| `correction_policy` | `off` / `impossible` / `spec` (§7) |
| `p2_max_tokens` | P2 output cap |
| `temperature` | 0.0 (still not perfectly deterministic for preview models) |
| `use_json_schema` | enforce the response JSON schema where the provider supports it |
| `timeout_s` | per-call timeout |

Current presets: **`v0`** (full e2e: gemini-3.1-pro-preview P1 + gpt-5.4-nano P2,
correction off), **`v0_p1_only`** (P1 isolation, `p2_model_key=""`),
**`v0_p2_correct_spec`** (flash-lite P1 + nano P2 with `correction_policy="spec"` —
the spec-tier trial config; note its `p2_model_key` may need a registry-key refresh),
**`v1_trust`** (v0 + trust layer: `reader_model_keys` = haiku-4.5 + 4o-mini +
flash-lite; runs under the separately-authorized $0.10/doc trust envelope —
the $0.08 accuracy cost gate is unchanged for v0 configs; `reader_image_max_px`
is the standing cost-reduction knob).

---

## 9. Models registry (`models_registry.py`)

Maps a stable **key** → provider, `model_id`, `PriceCard` (USD/M-tok), tier
(`cheap`/`frontier`), and capabilities (`supports_json_schema`, `supports_logprobs`).
The harness fails LOUDLY on an unknown key (the desired behavior — `model_id`s drift,
e.g. `-preview` suffixes). Cost is computed from provider-reported `Usage` × the card
(`instrument.cost_usd`), honoring cached-input rates. **This is the only file that
rots when a provider changes prices/models.**

---

## 10. Artifacts produced per run

Written to `results/<YYYYMMDD_HHMMSS>_<config>/` (gitignored — student text):

- **`results.json`** — machine truth (the regression-gate input). Top-level:
  `prompt_version`, `registry_as_of`, `config_name`, `config` (the full
  `PipelineConfig`), `mode`, `repeats`, `models`, `records[]`, `aggregates`. Each
  **record**: `doc_id`, `cost_usd`, `parse_failures` + `parse_failure_finish_reasons`,
  `stage_ms`, `routing_notes`, `spec_mismatches`, and `p1` / `e2e` blocks (each a
  serialized `DocumentScore`/`PageDocumentScore` with `doc_ratio_strict/_lenient`,
  `coverage`, `missed/extra_keys`, per-answer `critical`, and `gate{passed,reasons}`).
  `aggregates`: `per_doc`, `worst_doc`, `latency_ms{median,min,max}`,
  `cost_avg_per_doc_usd`, `cost_gate_pass`, `parse_failure_total`,
  `accuracy_gate_pass_all_docs`, `n_fixtures`, `flag_metrics_trustworthy`, and
  `correction` (only when policy≠off).
- **`summary.md`** — one-screen scoreboard: gate verdicts, per-doc table (P1 + E2E
  ratio, Δ, coverage, both gates), a **Phase-2 segmentation-health** block
  (coverage / missed / extra / routing notes + the "segmentation tax" P1→E2E delta),
  named gate failures grouped by doc, latency, stage breakdown.
- **`report_<doc>.md`** — the manual-review companion: per answer (E2E) and per page
  (P1), a gold\|pred unified diff + named critical-token misses + coverage/routing.
  **Reading these by eye is required** — the failure nobody anticipated shows up in
  the diff before it shows up in a metric.

`RUNLOG.md` (folder root, *not* per-run) — one appended line per run, the cross-run
memory: `date | config | diff-vs-prev | gate | attribution | worst doc | cost | note`.

---

## 11. How to run

From `vivi-codebase/backend/` (the module is run with `-m`; it uses relative imports):

```bash
# Phase-1 perception only (no spec needed):
python -m tests.transcription_eval_suit.runner --config v0_p1_only --mode p1_only

# Phase-2 segmentation in isolation (gold pages → P2):
python -m tests.transcription_eval_suit.runner --config v0 --mode p2_only --exam-spec draft.json

# Full end-to-end SHIP GATE over the 5 fixtures:
python -m tests.transcription_eval_suit.runner --config v0 --mode per_doc --exam-spec draft.json

# Throughput/latency under load (replicate the 5 fixtures to 25, concurrent):
python -m tests.transcription_eval_suit.runner --config v0 --mode batch --batch-size 25 --exam-spec draft.json
```
Flags: `--config` (required), `--mode` (`per_doc`|`p1_only`|`p2_only`|`batch`),
`--exam-spec` (required for every mode except `p1_only`; `draft.json` is parsed via
the tolerant rubric-draft loader), `--fixtures` (comma-sep `doc_id`s; default = all),
`--repeats` (default 1), `--batch-size` (default 25).

**Prerequisites:** real provider keys in `backend/.env` — `OPENAI_API_KEY` (P2 nano)
and the Gemini credential (P1). `make_default_pipeline` constructs a provider for
every model key in the config (so both are needed even though `p2_only` never calls
P1). **Cost/latency (current `v0`):** ~$0.03/doc, ~75–85 s/doc end-to-end (P1 ≈ 80%
of wall); `p2_only` is ~$0.003/doc, ~10 s/doc.

---

## 12. Instrument history — why you must stay suspicious

This instrument has been **caught lying** before any model decision was made on its
numbers (all now fixed and pinned by regression tests):
1. a single-metric gate, 2. a mis-specified error label, 3. cross-answer
cancellation (a dropped `;` in Q1 masked by a spurious `;` in Q2 — fixed by
per-answer scoring), 4. difflib `autojunk` corrupting ratios on pages ≥200 chars,
5. the `//`-comment stripper devouring a flattened single-line prediction, 6. the
report rendering a faithful single-line prediction as 100%-different.

Standing rules it teaches:
- **When a score contradicts its own diff, suspect the instrument before the model**
  — verify with a ≤5-line standalone recomputation before concluding.
- **`doc_ratio_strict` has a blind spot:** it scores a gold-key-ordered
  *concatenation*, so a boundary-preserving misroute (e.g. Q2 sub-answers shifted, one
  emitted empty) can keep the doc ratio ~1.0 while per-answer ratios and critical
  recalls collapse. Trust the per-answer view for P2.
- **n = 5 docs, one exam:** every conclusion is provisional against handwriting
  variance and this exam's identifier vocabulary; never generalize a model ranking.
- **Read two diffs by hand every run** as the check on the instrument itself.

---

## 13. Tests (`pytest -q` from `backend/`)

Pure parts are tested with **zero mocks**; provider/LLM paths inject fakes (a
`FakeProvider`) — **no test calls a real API**. Coverage:
- `test_scoring.py` — the scoring engine: the difflib-vs-critical thesis, dropped
  `;` / call-without-`()` / misread name / abbreviation expansion, layout-invariance,
  coverage/keys, no-cross-answer-cancellation, the case-fold policy.
- `test_ground_truth.py`, `test_normalize.py` — the GT parsers and the normalizer.
- `test_corrector.py`, `test_eval_gate.py` — corrector tiers + the gate.
- `test_pipeline_and_runner.py`, `test_providers_and_scheduler.py` — pipeline/runner
  on fakes, exam-spec loading (canonical + rubric-draft, sub-question signatures),
  scheduler.
- `test_prompts.py`, `test_report.py` — prompt-rendering invariants, report rendering.
> Note: provider-import tests may fail locally if an optional SDK (e.g.
> `google.genai`) isn't installed — that's an environment gap, unrelated to harness
> logic.

---

## 14. Fixtures

5 student exams (`dan_basiuk`, `din_ezra`, `moran_aharon`, `omer_gelber`,
`yonatan_basiuk`), each: `pdfs/<id>.pdf` + `raw_benchmarks/<id>.md` (raw GT) +
`draft_benchmarks/<id>.md` (draft GT). One exam, two CS questions, sub-questions
א/ב/ג. **n=5 is below the `flag_metrics_trustworthy` threshold of 10** — conclusions
are provisional and the correction kill-criterion is meaningless until n≥10 *with
deliberately-included student-spec-errors.* GT bugs are tracked as verification tasks
for the GT author (Noam), not as model findings.

---

## 15. Extending the suite

- **Add a fixture:** drop `pdfs/<id>.pdf`, author `raw_benchmarks/<id>.md` (per-page,
  `=== PAGE n ===`, all ink verbatim) and `draft_benchmarks/<id>.md` (per-answer,
  `=== Q1.א ===`, gradeable content only). The parsers enforce contiguity/uniqueness.
- **Add a model:** add a `ModelSpec` to `models_registry.py` (key, provider,
  `model_id`, `PriceCard`, tier, capabilities), then reference the key in a config.
- **Add a config:** copy a `configs/*.json`, change *one* field (the playbooks demand
  one-field comparisons), run, append a RUNLOG line.
- **Add a subject (e.g. a new vertical):** add a `CriticalProfile` (operators /
  structural / abbreviations / keywords) — the scoring engine reads the profile and
  never knows the language (subject modularity, CLAUDE.md §3.3).
- **Change the gate:** edit `GateConfig` (one place). Relaxing a floor requires eval
  evidence per §5.4.

---

## 16. Current state & open issues (as of the latest runs — see RUNLOG)

Snapshot of what's known, so a new agent doesn't re-discover it:
- **P2 segmentation is mostly solved.** The per-sub-question **content signatures** in
  the exam spec fixed omer's Q2 ב/ג swap; the content-first prompt + boundary step
  fixed most routing; an anti-dump/orphan guard fixed moran's input-dump and dan's
  margin-note inclusion.
- **The remaining P2 bug is nested-method handling.** When a student writes a method
  (e.g. `LowestRateChannel`) *inside* another unit's braces (the TVShow class) that
  the spec maps to a different sub-question, P2 oscillates between **merging** (drops a
  target → empty answer) and **duplicating** (exclusivity violation → bloated answer).
  The fix it needs is to **SPLIT** — extract the method into its own answer and remove
  it from the enclosing unit. Also watch for a **refusal mode**: an over-strict
  "don't fabricate" prompt once made P2 emit *nothing* for a messy doc (E2E 0.0) —
  best-effort, never-empty output is a hard requirement.
- **The dominant SHIP blocker is P1 perception, not P2.** `method_call_recall` tops out
  ~0.79–0.87 *even with keyword case-folding*; the residual is genuine handwritten
  identifier misreads (`getisSportive`→`getisSortive`, `Tv Show`→`TvShow`) and is
  unmoved by model escalation (flash-lite→pro) AND by resolution (2000→2400 falsified).
- **The looming decision is gate calibration.** Given the multi-run evidence that
  `method_call_recall == 1.0` is unmet by any configuration and that many residual
  misses are case or GT typos, the open question is whether the conjunctive floor is
  calibrated to achievable handwriting fidelity — to be decided *with* the false-fix
  discipline, never by quietly loosening a grade-critical floor.
- **`correction_policy` remains `off`** and the `spec` tier remains
  **UNDERPOWERED-NO-CLAIM** until the fixture set grows to n≥10 with included
  student-spec-errors.
