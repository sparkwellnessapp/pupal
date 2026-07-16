# Vivi — Phase T0: Transcription Optimization & Redesign Plan

**Owner:** Noam
**Status:** DRAFT — pending approval to implement
**Scope:** The handwriting transcription internals only — `handwriting_transcription_service.py`, the VLM provider interface, `transcription_adapter.py`, the thumbnail storage tactic, and a new `transcription_eval_suit/`. The `TranscriptionContract` shape, grading pipeline, DB schema (except thumbnail/PDF lifecycle), and review-panel design are **out of scope** and untouched.
**Method:** Measure first. Strip to the lowest essentials. Add one falsifiable layer at a time, keep only what the eval suite pays for. Bottoms-up.

---

## 0. Problem definition (Deutsch form)

**Data (the contradiction).** A single transcription takes ~90s. The most common workload is a batch of 20–30 PDFs on the lowest provider tiers. We require ≥98% transcription accuracy and mistake-flagging accurate enough that review is fast. The current pipeline's design choices (gpt-4o, `detail:high`, 4000-token budget, a visual-grounding block, an inline consistency-retry, per-page calls, sequential CPU preprocessing, synchronous debug disk I/O, a dead async path) are an *unvalidated theory* that "this is what accuracy costs." That theory contradicts the latency requirement and, worse, **is not measured** — we cannot currently falsify any of it.

**The theory under criticism.** "High accuracy requires the current stack." This is easy-to-vary: it survives every observation because we have no instrument. The redesign's first act is to build the instrument, so each component becomes a falsifiable conjecture with a kill criterion.

**Better conjecture.** The minimum-latency pipeline that holds ≥98% accuracy is *discovered*, not designed — by a measurement harness that lets us strip everything, establish a floor, and re-add only layers that pay. Most of the current latency is removable without touching accuracy; the accuracy-sensitive levers (model, image fidelity, grounding) are decided by the eval, not by belief.

**Success criteria.**
1. **Latency:** minimize, no fixed target. Optimize **time-to-first-draft** under a 20–30 PDF batch on lowest tiers, and report time-to-last-draft + throughput.
2. **Accuracy gate (CONJUNCTIVE — difflib alone is provably insufficient):** `doc_ratio_strict ≥ 0.98` **AND** `coverage = 1.0` **AND** critical-token recall floors (operators / structural / method-calls, default 1.0) **AND** no abbreviation alterations. A 0.9959-difflib document was demonstrated to carry three grading-critical errors (`==`→`=`, dropped `;`, `CW` expansion); the conjunction is what makes the gate honest. Thresholds live in one `GateConfig`. Reported per-doc with the **worst** doc surfaced, not hidden behind the mean.
3. **Flagging:** recall-first detection of real transcription errors, with review burden (flagged span fraction) held low enough that review stays fast.
4. **The difflib gate is a proxy.** The real metric is teacher-approval rate and edit count. The harness supports manual side-by-side eval and a production harvester to grow the labeled set toward the real metric.

---

## 1. Invariants for this work

- **The eval suite gates every accuracy-affecting change.** No model swap, prompt change, image change, or layer ships without a measured delta. Latency-only changes with zero accuracy surface (debug I/O, parallelization) may ship on wall-clock evidence alone.
- **Teacher is the authority.** Flags direct attention; they never silently rewrite the draft or auto-resolve into the contract.
- **Subject-agnostic core.** Java + Hebrew is the first vertical, not a hardcode. Prompts take subject/language as input; no `if subject == "cs"` in shared code.
- **Simple over Easy (Hickey).** One normalizer function. One provider method. One timing primitive. One results schema. One pipeline factory parameterized by config. No parallel surfaces.
- **Draft immutability preserved.** The `TranscriptionDraft` remains the frozen historical record; the draft↔contract diff is the production label source (§2.7).

---

## 1b. The two-phase pipeline (locked after Layer 1)

The pipeline is split into two independently evaluated phases:

**Phase 1 — perception (image → verbatim per-page text).** Transcribe exactly as written, page by page, no interpretation: headers included (they're ink), `[?]` for illegible, crossed-out dropped, circled question digits written as `שאלה {n}`. Output schema `{pages: [{page_number, text}]}` (typed, sortable — not string keys). This phase carries all image cost and all rate-limit pressure; its unit is the page, so the chunk-boundary merge problem dissolves (cross-page answers are Phase 2's job).

**Phase 2 — interpretation (pages + question spec → TranscriptionDraft).** Text-only: segments per-page text into per-question/sub-question answers using the exam spec as context, and surfaces spec-anchored discrepancies. Cheap, fast models; near-free harness iteration (no images).

**The correction guardrail (locked).** Phase 2 NEVER silently rewrites. A spec-anchored discrepancy (`Mobby` vs spec's `Hobby`) is *not* "for sure" an OCR error — it may be a real student mistake whose "correction" erases a Bagrut deduction (the fixtures prove this class exists: `TvShow`/`TVshow` vs `TVShow`, `chlRate` vs `chlRates`, `Hobbyy`, `pupulateHobbies`, `LowesRateChannel`, `minuteS`). Every such finding is a `spec_mismatch` annotation `{original, suggested, reason}` feeding the existing annotation surface; whether the suggestion is pre-applied is `correction_mode ∈ {off, flag_only, auto}` — a **measured variable**, with `flag_only` as the prior (a silent wrong fix corrupts a grade invisibly; a missed fix costs one teacher edit). `spec_mismatch` doubles as the highest-precision review flag we have.

**Three eval surfaces.**
1. **Phase-1 eval** — GT: `raw_benchmarks/*.md` (`=== PAGE n ===`, verbatim incl. headers). Score: per-page difflib strict/lenient + per-page critical tokens; coverage = matched pages. Same conjunctive gate (shared field names).
2. **Phase-2 eval** — input: **gold** Phase-1 pages (isolation from perception noise); GT: `draft_benchmarks/*.md` (`=== Q{n}.{sub} ===`, headers excluded). Score: the existing per-question engine (coverage/segmentation is the core job) + correction counts (true-fix / false-fix / missed-fix). Phase-2-only fixtures can be synthesized cheaply (text-only).
3. **End-to-end eval** — PDF → P1 → P2 → draft vs `draft_benchmarks`. **The only surface that gates shipping.** Running P2 on gold input vs real P1 output decomposes end-to-end error into perception vs interpretation.

**Fixture selection criterion:** deliberately include tests where students misspell spec-named identifiers, so `correction_mode` is decidable by data (all five current fixtures qualify).

**GT authoring scheme:** per-page raw file is the superset and the only authored artifact going forward; the per-question file is derived from it (tool-assisted) and human-verified. Both live as fixtures: `raw_benchmarks/` (Phase 1) and `draft_benchmarks/` (Phase 2 + e2e).

---

## 2. The measurement layer — built FIRST, nothing else ships without it

This is the keystone. Layout (new top-level `transcription_eval_suit/`, importable by both harness and prod where shared — the normalizer, provider interface, and scheduler are shared; scoring and the runner are harness-only):

```
transcription_eval_suit/
  benchmarks/                 # fixtures: one folder per test
    moran_aharon/
      source.pdf
      ground_truth.md         # canonical segmented format (§2.1)
    .../
  normalize.py                # the one pure normalizer (§2.2) — SHARED with prod
  scoring.py                  # accuracy + flag scoring, pure (§2.3, §2.4)
  instrument.py               # stage timing + usage primitives (§2.5)
  pipelines.py                # pipeline-under-test factory, config-parameterized (§3)
  runner.py                   # orchestrates repeats, emits artifact (§2.7)
  report.py                   # human-readable + manual-eval companion (§2.7)
  baselines/                  # committed result snapshots for the gate
  test_eval_gate.py           # thin pytest gate, opt-in, real API calls (§2.7)
```

### 2.1 Ground-truth format (canonical, segmented)

The current freeform markdown is not safely parseable (leaked headers, duplicate header lines, mixed conventions). Replace with one unambiguous delimiter format that maps directly to the `answers[]` shape and lets us measure **segmentation** error separately from **character** error:

```
=== Q1.א ===
public class Hobby
{ ... }

=== Q1.ב ===
public class SchoolHobbies
{ ... }

=== Q2.ב ===
{ ... }
```

Rules: one `=== Q{n}[.{sub}] ===` delimiter per answer; everything between delimiters is the answer body verbatim; **no Hebrew section headers inside bodies**; illegible/unreadable source is marked `[?]` (single shared vocabulary with the model output); crossed-out source is dropped (matches "transcribe visible ink"). A pure parser turns this into `Dict[(q_num, sub_id) -> answer_text]`.

**Action:** I'll write the parser + a one-time converter and convert `moran_aharon.md` (and you author the rest in this format up to n=30). Authoring stays human-friendly; parsing stays trivial; one source format.

### 2.2 The normalizer (one pure function)

`normalize(text: str, strip_illegible: bool) -> str`, used by **every** comparison, nowhere duplicated:

1. Unicode NFC normalize (matters for Hebrew + combining marks).
2. `lower()` (no-op on Hebrew, correct for Java identifiers).
3. If `strip_illegible`: remove `[?]` tokens (lenient mode).
4. Remove **all** whitespace (`\s+` → ``), so indentation/blank-line differences never count.

This single function defines "equal." If the metric ever needs to change, it changes here, once.

### 2.3 Accuracy scoring (pure)

- **Document strict (the gate):** concat answers in canonical key order, `normalize(strip_illegible=False)`, `difflib.SequenceMatcher.ratio()`. `[?]` counts as a miss (real review cost).
- **Document lenient (watch):** same with `strip_illegible=True` — accuracy of what the model *committed* to.
- **Per-answer:** align prediction↔GT by `(q_num, sub_id)`; ratio per matched answer.
- **Coverage / segmentation:** `coverage = |matched| / |GT keys|`; count **missed** keys (GT not predicted) and **extra** keys (predicted not in GT). A high document score with low coverage = mis-segmentation. Secondary diagnostic: bag score (concat all, ignore keys) vs keyed score — a large gap localizes the failure to routing, not characters.
- **Per-doc + worst-doc reported.** Mean alone is forbidden at small n.

**Acknowledged blind spots (stated, not hidden):**
- *Single-char criticality.* `=`↔`==`, `<`↔`<=`, a dropped `!` flips grading correctness while barely moving the ratio. A 0.98 doc score does **not** guarantee a correct grade — it guarantees low bulk edit effort. This is precisely why flag **recall** is weighted heavily (catch it before grading). Optional v1 secondary metric: a small grading-critical-token diff (operators, boundaries, negation) reported alongside the ratio. **Decision needed:** in v1 or deferred.
- *Mis-segmentation* is invisible to a concatenated metric; the coverage/extra metrics above are the guard.

### 2.4 Flag-detection scoring (pure)

- **Label (disjunctive — decided after the corruption demo):** an answer is an "error" iff `ratio_strict < 0.98` **OR** any critical-token miss is present in it. The difflib clause alone is length-dependent (one bad char trips a short answer but not a long one) and provably missed all three injected grading-critical errors; the critical-token clause is length-independent and catches them. A flag firing on a critical-token miss is a **true** positive.
- **Key joining:** prediction↔GT joining happens on **canonically normalized keys** (Hebrew/Latin/numeral sub-ids collapse to one form, punctuation stripped), so label-format mismatch never pollutes coverage; remaining misses are real routing errors.
- **Detector:** each flag/uncertainty signal is a binary predictor over answers. Compute precision, recall, F1.
- **PR curve:** retain each signal's *continuous* value (confidence, logprob span-min, self-consistency disagreement, verifier score) and sweep the threshold to draw the precision/recall frontier.
- **Operating point (recall-first, but review-aware):** choose the threshold that **maximizes precision subject to recall ≥ floor** on error-answers (proposed floor: 0.95; confirmable from data). Report the precision and the **review-burden proxy** at that point.
- **Review-burden proxy:** the resolution of the recall-vs-review tension is *localization*. A flag that highlights the 3 uncertain characters costs near-zero review even at high recall; a flag that paints the whole answer red does not. Metric = `Σ(flagged span length) / Σ(total length)` for span-localized signals, or fraction-of-answers-flagged for answer-level signals. Recall-first and fast-review stop being contradictory once flags are span-localized.
- **Honesty:** at n=3 (~18 answers) flag PR curves are noise — this is a *correctness smoke test for the scorer*, not calibration. Real flag tuning needs n ≥ 30. Stated explicitly in every flag report.

### 2.5 Latency & usage instrumentation

- **Stage spans:** one `StageTimer` context manager records `{stage, ms}` into a per-doc trace. Stages: `pdf_render`, `image_encode`, `vlm_call` (× chunk, with TTFT when streaming), `parse`, `verify_retry`, `merge`, `thumbnail_render`, `gcs_upload`, `db_write`. This is what makes "iterate on latency" possible — you see *which* stage moved.
- **Batch metrics:** time-to-first-draft, time-to-last-draft, docs/min throughput, and **scheduler queue-wait** per call (time blocked on the concurrency limit — the dominant term at low tier).
- **Repeats & stats (honest at small n):** default 3 repeats/doc; **temp 0**; **cold vs warm** separated. Per-doc latency reports **median + min/max** — a p95 from 9 samples is not a p95 and is forbidden. p95 is computed only for **batch runs**, where sample counts are real. The batch benchmark is defined as the available fixtures replicated and shuffled to 25 docs (accuracy is correlated across replicas — fine; the batch benchmark measures the *scheduler*, not the model).
- **Usage primitive:** capture `{input_tokens, output_tokens, image_tiles}` per call as raw data. A swappable price table (`provider/model → $/Mtok in, $/Mtok out, $/image`) computes $ when configured. The core never rots when prices drift.

### 2.6 The lightweight VLM provider interface

Replace the current 4-method ABC (`transcribe_images` / `_with_logprobs` / `_stream` / `_async`, inconsistent across providers, async path dead) with **one async method, one structured return** — measurement built into the contract:

```python
@dataclass(frozen=True)
class Usage:        input_tokens: int; output_tokens: int; image_tiles: int | None
@dataclass(frozen=True)
class CallTiming:   ttft_ms: float | None; total_ms: float
@dataclass(frozen=True)
class VLMResponse:  text: str; usage: Usage; timing: CallTiming; token_logprobs: list[float] | None

class VLMProvider(Protocol):
    name: str
    async def complete(self, *, images_b64, system, user,
                       max_tokens, temperature, want_logprobs=False) -> VLMResponse: ...
```

Async-native (real timeout cancellation, real batch concurrency). Logprobs opt-in, `None` when unsupported (you've approved dropping logprob-dependence if the best model lacks it). Thin adapter per SDK (OpenAI, Gemini, Anthropic, + room for specialized OCR models). **Routing and rate-limiting live *above* this interface** (§5), not inside it — one concept per place.

### 2.7 Runner, artifact, gate, manual companion

- **Runner:** standalone, makes **real** API calls, takes a pipeline config, runs all fixtures × repeats, emits a structured `results.json` (per-doc × per-repeat raw records + aggregates + stage breakdown) and a `summary.md`.
- **pytest gate (`test_eval_gate.py`):** thin; asserts current run vs committed `baselines/` snapshot — document strict ≥ 0.98 (and ≥ baseline − tol), p95 latency ≤ baseline + tol, flag recall ≥ floor. Because it calls real APIs it is **opt-in and excluded from `pytest -q`** (CLAUDE.md forbids OpenAI in the default suite) — run via `pytest -m eval` / a make target.
- **Manual-eval companion:** `report.py` emits per-answer **prediction | ground-truth | diff** in a readable layout so you can eyeball and record approve/edit-count — because difflib is the proxy and your read is the real metric.
- **Production harvester (grows the set toward the real metric):** a job that turns approved `(draft, contract)` diffs into new labeled fixtures (the corrected contract *is* the label) + records edit-count and approved/unedited rate. This is how n=3 → n≥30 → statistically meaningful, and how the proxy converges on the real metric.

---

## 3. The v0 baseline — strip everything

v0 establishes the latency floor and the accuracy starting point. Every later layer must beat v0 by enough to justify its cost.

- PDF → images, **no enhancement**, DPI as a measured variable (start 200).
- **Chunked, page-count-adaptive** calls (§ your note): `chunk_size = f(total_pages)`, start at **3–4 pages/call**; a 5–8 page test → ~2 calls. Sweep later.
- **One plain prompt:** "transcribe exactly; preserve bugs/typos/missing tokens; `[?]` for illegible, never guess; exclude Hebrew section headers from answer text; output JSON `answers:[{question_number, sub_question_id, answer_text, confidence}]`." **No** grounding block, **no** consistency check, **no** retry, **no** logprobs.
- **Default fast current model** (NOT gpt-4o — chosen from the first model sweep, §4).
- Merge by canonical `(q_num, sub_id)`; adapter → draft. **Chunk-boundary rule (defined, not improvised):** same-key fragments from adjacent chunks **concatenate in chunk order — never dropped** — and carry a `chunk_boundary_merge` marker, which doubles as an uncertainty signal (boundary merges are where errors concentrate; the eval measures whether the marker predicts them).
- **Parse-failure is a v0 metric, not an L3 concern.** One malformed JSON response silently destroys a third of a 3-doc eval. Every call records a parse outcome; one bounded re-request on parse failure (transport-style, mirroring the grader's transient-only retry rule); the report shows the rate. Structured-output *enforcement* remains the L3 experiment; counting failures is v0 infrastructure.
- **Removed from the hot path:** all debug disk I/O, the double JSON parse, the sync-client logprob path, the nested threadpool, image enhancement.

v0's purpose is not to be good — it's to be *measured*, so we know what each re-added layer buys.

---

## 4. Iteration roadmap — ordered, falsifiable layers

Each layer is a conjecture with a predicted cost and a kill criterion. The model sweep runs continuously (it reframes everything: a better base model can make grounding/retry unnecessary).

| Layer | Conjecture | Predicted cost | Keep-if / Kill-if | Gated on |
|---|---|---|---|---|
| **Model sweep** | A current model beats gpt-4o on accuracy *and* latency | — (it is the search) | Adopt the model(s) on the accuracy≥0.98 ∩ latency ∩ cost Pareto frontier | harness |
| **L1 — image** | Enhancement + high DPI + `detail:high` don't raise accuracy on clean scans; they cost encode + image tiles | −ms/page | Kill enhancement / drop DPI / lower detail if Δaccuracy < +0.005 at the op point | harness |
| **L2 — chunking** | Bigger chunks cut call-count (rate limit) and latency; accuracy may degrade past K pages | varies | Pick the chunk policy on accuracy≥0.98 ∩ min batch-time; encode as `f(total_pages)` | harness + batch metrics |
| **L3 — prompt / structured output** | Schema-enforced JSON cuts parse failures and output tokens; explicit bug-preservation raises fidelity | neutral/−ms | Keep if parse-failure↓ or accuracy↑ at no latency cost | harness |
| **L4 — visual grounding** | Forcing identification-first raises accuracy enough to justify extra output tokens | +output tokens (+ms) | Keep only if Δaccuracy ≥ its latency cost; else kill (it is currently belief, not measurement) | harness |
| **L5 — flag signals** | Some signal predicts <0.98 answers at recall≥floor with acceptable precision/review-burden | +0 to +1 call | Adopt signal(s) on the recall-floor ∩ max-precision frontier; prefer span-localized; combine signals to cut false positives | harness (trust needs n≥30) |
| **L6 — targeted verify** | A signal-triggered re-pass on flagged spans, run **concurrently** (speculative), raises accuracy without extending the critical path | +calls (parallel) | Keep if Δaccuracy pays and p95 unchanged; this replaces the old serial inline retry | L5 |
| **L7 — multi-provider routing** | Spreading calls across ≥2 *passing* providers raises batch throughput at low tier | − batch time | Only route among models that each independently clear 0.98; measure throughput gain | harness + batch |

Note on L2/L6 vs the old design: the deleted inline retry was the worst case — a *serial* second call on the critical path, triggered by a *brittle* heuristic, that doubled tail latency. L6 keeps the useful idea (re-verify uncertain content) but makes it concurrent and signal-triggered, so it serves both goals at once: the same uncertainty signal drives the flag *and* the escalation.

---

## 5. Batch & storage architecture

**Workload reality:** 20–30 PDFs, lowest tiers. At per-page granularity that is 150–210 calls per batch — the rate limit, not the model, is the wall. Hence:

- **One bounded-concurrency scheduler** (configurable semaphore + adaptive 429 backoff), **shared by harness and prod**, so measured throughput reflects real limits. Sync/real-time API only — provider batch/async endpoints (minutes–hours) are useless for interactive review.
- **Scheduler policy: depth-first per document.** Prefer completing in-flight documents' remaining chunks over starting new documents. Breadth-first maximizes time-to-first-draft (everything finishes late together); depth-first minimizes it. Both orderings are measurable in the harness; depth-first is the default conjecture.
- **Tier upgrades are an explicit lever, weighed before engineering.** At lowest tiers, queue-wait dominates batch latency by arithmetic (25 docs × 2 calls at ~10 RPM ≈ a 5-minute floor no code can beat). Spending tens of dollars to move one tier up is measured against weeks of routing work — the harness's queue-wait metric makes the comparison concrete.
- **Per-PDF pipelines run concurrently** up to the scheduler limit; each PDF commits its draft **independently** as it finishes. **Time-to-first-draft ≈ one PDF's latency**, not the batch's — the teacher reviews draft 1 while 2–30 finish. Drafts stream in as rows land (the existing batch path already commits per-`transcribe_one`; we make completion observable, no schema change).
- **Multi-provider routing (L7)** multiplies effective RPM/TPM by running passing models on separate per-provider semaphores — the cleanest fix for low-tier limits.
- **Chunking (L2)** is also a rate-limit lever: fewer, larger calls = fewer RPM hits. The chunk policy is chosen jointly for accuracy and batch throughput.

**Thumbnails (temporary, never long-term):**
- Render display thumbnails **once, during transcription, from the page images already in memory** (no later re-render of the PDF).
- **Fire-and-forget** upload to a `tmp/` GCS prefix with an object-lifecycle TTL as a safety net. This must **not block** returning the text draft — text first (what the teacher needs), images on click via **short-lived signed URLs** (browser loads from GCS directly, killing the current download→re-render→base64→proxy round trip).
- **Delete on draft approval.** 
- **Source PDF: harvest-then-delete (resolves a contradiction caught in review).** Deleting PDFs on approval and growing the eval set from production are mutually exclusive as originally written — a harvested fixture is *PDF + corrected text*, and without the PDF there is nothing to re-run future pipeline configs against. So the approval hook runs in order: (1) a **sampling policy** (e.g. 1-in-N, plus all teacher-heavily-edited cases — the most informative fixtures) copies PDF + contract to the private eval bucket, gated on student-name anonymization; (2) everything else is deleted as planned. Regrade still runs against the Transcription JSON, never the PDF; the harvested copy serves the eval suite only. Until approval, PDF + thumbnails live under TTL so nothing leaks if approval never comes.

---

## 6. Dead code to delete (cleanup, in scope)

- `_transcribe_with_mappings`, `_build_single_question_prompt`, the page-mapping `QuestionMapping` path, and legacy prompts (`HANDWRITING_SYSTEM_PROMPT`, `build_extraction_prompt`) — confirmed dead.
- `_save_debug_pages`, `_save_debug_response`, `DEBUG_RESPONSES_DIR` writes, the double `_parse_json` — off the hot path (gate behind an explicit debug flag if useful for local dev, never in prod).
- The 4-method provider ABC and the sync-client logprob path — replaced by §2.6.
- The nested `ThreadPoolExecutor` + `run_in_threadpool(transcribe_pdf)` — replaced by the async scheduler.

---

## 7. Sequencing & deliverables

1. **Measurement layer (§2)** — ✅ pure core landed (normalizer, GT format + parser + converted `moran_aharon`, scoring with conjunctive gate + per-answer critical tokens + canonical keys; 33 tests green). Remaining: instrument, provider interface, runner, gate, manual companion.
1b. **Fixture authoring — parallel track, Noam-only, starts NOW.** Every keep/kill decision is made against the eval; at n=3 (~18 answers) those decisions are noise. The **model sweep is gated on n≥10** (≈60+ answers — enough to *rank* models with real separation; n≥30 remains the bar for the public 98% claim). n=3 stays the inner-loop smoke set. This is the binding constraint on the calendar and it parallelizes perfectly with harness work.
2. **v0 baseline (§3)** wired into the harness; first **model sweep** (once n≥10). Commit the baseline snapshot.
3. **Layers L1→L7 (§4)**, each as a config diff measured against the committed baseline; keep/kill by the table.
4. **Batch + storage (§5)** folded in once the per-doc pipeline is settled.
5. **Production harvester (§2.7)** to grow n→30+ and converge proxy→real metric.
6. **Cleanup (§6)** as each replacement lands.

I will **describe the approach and wait for approval before writing code at each significant step** (§ CLAUDE.md), starting with the measurement layer's concrete module designs.

---

## 8. Open risks & honest limitations

- **The instrument itself was caught lying three ways in review** — single-metric gate (passed a corrupted doc at 0.9959), length-dependent error label (labeled zero of three corrupted answers), and a cross-answer cancellation bug in document-level multiset scoring (a dropped `;` masked by a spurious `;` elsewhere). All three fixed and pinned by regression tests before any model was measured. The lesson stands: validate the measuring device on known corruptions before trusting any number it produces.
- **Harness location:** `tests/transcription_eval_suit/` now holds importable library code, not just tests. Acceptable at current size; if/when instrument+providers+runner land, prefer moving the library to `backend/eval/transcription/` with only the thin pytest gate under `tests/`. Decide before the next layer makes the move costlier.

- **n=3 is a smoke test, not a validation set.** One hard page swings the mean 33%; we *will* overfit to these three PDFs. The 98% claim is only meaningful at n≥30 — the harvester is how we get there. Until then, report per-doc + worst-doc and treat conclusions as provisional.
- **The difflib gate is a proxy.** It rewards bulk character match and is blind to single-char grading-critical errors and to mis-segmentation. Flag recall and the coverage metrics are the compensating instruments; your manual read is the arbiter; teacher-approval/edit-count is the real target.
- **Flag calibration needs scale.** L5/L6 thresholds set on n=3 are guesses; they harden only as the labeled set grows.
- **Provider variance.** Latency has a fat tail and prices/limits drift; that is why we measure median+p95 over repeats and keep usage (not $) as the primitive.
