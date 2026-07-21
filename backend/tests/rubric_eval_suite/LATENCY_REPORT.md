# Rubric-Extraction Latency Report

**Mission:** `MISSION_rubric_extraction_latency.md` — reduce wall-clock time to rubric
extraction at zero benchmark regression, or prove the lever space with the same rigour.
**Branch:** `perf/rubric-extraction-latency` · **Executor:** agent · **Owner:** Noam
**Scope executed (owner's decision):** Phase 0 (instrument) → Phase 1 (baseline + noise
band) → Phase 2 (attribution) → Phase 3 (pre-registration), then **STOP before any
candidate run**. No candidate was executed; one strong Tier-1 candidate (P-L1) is
pre-registered and ready for a future authorized confirmation.
**Total API spend:** **$10.56** of $35 (33 valid billed trials). No GT artifact touched.

---

## 0. Headline

- **Baseline (production pin: gpt-5.5 / effort=medium / prompt 3.3.1-tracehdr / pipeline
  3.3.0):** 2 blocks × k=3, all 5 fixtures, **30/30 valid, 5/5 gate PASS every trial.**
- **Headline metric** `max-over-fixtures of t_doc_median` = **bagrut_899371 ≈ 414 s.**
- **The single dominant, movable term is a false retry on `bagrut`** (the `EMPTY_SQ_TEXT`
  validator firing on a *legitimate* null-text branch sub-question). It fires on ~71% of
  bagrut draws and **≈ doubles** that document. Eliminating it (candidate **P-L1**, Tier-1,
  zero model-visible change) is predicted to cut the headline **~48–55%** — past both the
  30% target and the 50% stretch — and to collapse bagrut's 105% run-to-run variance.
- **This candidate is pre-registered, not run** (owner scope). Everything below is the
  evidence that makes it the right next spend.

---

## 1. The latency model (the durable artifact — outlives every lever)

```
t_doc ≈ t_render_local                                   (0.07–0.35 s, < 0.3%  — RULED OUT as a lever)
      + t_step1_llm  = Σ over attempts [ t_prefill(input_tok) + t_decode(output_tok incl. reasoning) ]
      + t_tierB_llm                                        (hobby only, ~9.5 s — a 2nd LLM call in Step 2c)
      + t_local      (clean+validate+build+Tier-A)         (~0.001–0.002 s — negligible)
```

**Empirical core:** the pipeline is **decode-bound**. For every fixture, `t_doc ≈ t_step1_llm`
and `t_step1_llm ≈ output_tokens / ~55 tok/s`. Render is 90 ms, local compute is ~1 ms.
There is essentially **one knob that matters: the number of output tokens the model emits
(visible completion + hidden reasoning), and the decode rate.**

Measured decode rate (output_tokens / step-1 LLM seconds), no-retry draws:
csharp 55 · employee 53 · foundations 54 · hobby 53 · bagrut(retry) 62 → **~53–62 tok/s.**

### 1.1 Baseline per-fixture table (2 blocks k=3 + 1 salvaged bagrut draw; VALID only)

| fixture | n | t_doc median (s) | t_doc max (s) | render (s) | step-1 llm (s) | Tier-B/local (s) | out_tok median | retries | $/doc median |
|---|---|---|---|---|---|---|---|---|---|
| **bagrut_899371** | 7 | **413.9** | **451.2** | 0.28 | 413.6 | 0.002 | 25,691 | {1×5, 0×2} | 0.956 |
| foundations_cs | 6 | 111.3 | 119.4 | 0.09 | 111.3 | 0.001 | 6,015 | {0×6} | 0.228 |
| hobby_tvshow | 6 | 107.4 | 112.3 | 0.13 | 96.4 | **9.47** (Tier-B call) | 5,184 | {0×6} | 0.210 |
| csharp_plane_combine | 6 | 76.9 | 84.2 | 0.11 | 76.7 | 0.000 | 4,245 | {0×6} | 0.175 |
| employee_course_select1 | 6 | 76.4 | 110.8 | 0.07 | 76.3 | 0.002 | 4,074 | {0×6} | 0.170 |

**Headline = 413.9 s (bagrut). Tail (max-over-fixtures of t_doc_max) = 451.2 s (bagrut).**

### 1.2 The noise band (why any claimed win must clear ~2×)

Between-block spread of the **unchanged** baseline (per-fixture median, block A2 vs block B):

| fixture | block A2 median | block B median | between-block spread |
|---|---|---|---|
| csharp_plane_combine | 77.6 | 76.2 | **1.8%** |
| employee_course_select1 | 76.0 | 76.8 | **1.1%** |
| hobby_tvshow | 110.3 | 104.4 | **5.6%** |
| foundations_cs | 107.8 | 119.2 | **10.6%** |
| bagrut_899371 | 220.4 | 413.9 | **104.7%** |

- **Clean-fixture noise floor ≈ 1–11%** (pure decode nondeterminism: reasoning-token count
  varies run to run; e.g. employee has one 110.8 s outlier among ~76 s draws). **Minimum
  detectable effect ≈ 2× ≈ up to ~22%.**
- **bagrut's 105% is not noise in the usual sense — it is the nondeterministic retry.**
  A2 retried 1/3 draws (median 220 s); B retried 3/3 (median 414 s). The retry is a bimodal
  switch: present ⇒ ~393–451 s (out ~24–26k), absent ⇒ ~186–220 s (out ~12k). **The headline
  fixture is also the noisiest number in the suite, and both properties have the same cause.**

---

## 2. Attribution → ranked levers (derived from the model, not guessed from a menu)

| rank | lever | term | expected leverage | risk | verdict |
|---|---|---|---|---|---|
| 1 | **P-L1 retry elimination** (branch-SQ `EMPTY_SQ_TEXT`) | t_retry_overhead | **~48–55% headline** | **low** (Tier-1, no model-visible change) | **PRE-REGISTERED — the recommended next spend** |
| 2 | P-L6/L7 reasoning_effort | t_decode (the ~99% term) | large, all fixtures | **high** (bagrut faithful-error gate) | Tier-2, PROPOSE-ONLY (Noam) |
| 3 | P-L8 model swap | t_decode / t_prefill | potentially large | medium (prod pin, provider) | Tier-2, PROPOSE-ONLY (Noam) |
| — | L9 output verbosity | t_decode | small (output already structured JSON) | low | cheap to screen if L6 pursued |
| — | L4 prompt-cache | t_prefill | low ceiling (prefill ≪ decode) | low | measure `cached_tokens` first (see §5) |
| — | L2 client reuse | t_queue | ~100–300 ms vs 60–410 s | low | not worth a screen |
| — | L5 local render | t_render | **0.1–0.35 s — RULED OUT** | — | closed |
| — | Tier-B 2nd call (hobby) | one LLM call | ~9.5 s, only on a structural trigger | — | minor |

**Why L1 is #1 and not the bigger raw knob (L6):** decode is ~99% of t_doc, so effort *looks*
like the biggest lever — but it is Tier-2 (touches model-visible reasoning) and it is the lever
most likely to break the one fixture the whole product exists for (bagrut's faithful-error
never-reconcile tripwires). L1 attacks a **pure defect** — a retryable validator firing on a
shape the pipeline's own SECTION-8 convention declares legitimate — so it removes an entire
~200 s round trip **with no change to what the model is asked to produce.** Highest value ×
lowest risk. It is also the exact candidate RUNLOG (140120) had already flagged and deferred.

---

## 3. Hypothesis ledger

| ID | variable (one) | predicted effect | kill criterion | result | verdict |
|---|---|---|---|---|---|
| smoke | — (instrument validation) | capture t_doc | — | csharp 62.6 s, decode 99.9% | instrument CONFIRMED |
| baseline | none (prod pin) | reproduce 5/5 + measure | 5/5 must hold | 30/30 valid, 5/5, headline 414 s | CONFIRMED (no drift) |
| **P-L1** | `EMPTY_SQ_TEXT` `and not sq.sub_questions` | headline −48–55%, retry→0, 0 gated move | any gated regression / retry not→0 / ungated move | **NOT RUN (scope)** | **PRE-REGISTERED** |
| P-L6/L7 | reasoning_effort low; per-step mix | large decode cut, all fixtures | any gated regression (bagrut) | NOT RUN | PROPOSE-ONLY (Noam) |
| P-L8 | model id | faster/fewer-token decode | gated regression; cost/prod-pin | NOT RUN | PROPOSE-ONLY (Noam) |

Full pre-registration text (mechanism, exact code line, confirmation plan): `PREDICTIONS.md`
§"MISSION latency". Every run has a `RUNLOG.md` entry.

---

## 4. The recommended candidate (P-L1) — evidence and honest power statement

**Exact change (one line, `app/services/docx_v3/pipeline.py::_validate_extraction`, ~line 1192):**
```python
for sq in q.sub_questions:
    if not sq.sub_questions and (not sq.text or sq.text.strip() == ""):   # only LEAF SQs need task text
        issues.append(ValidationIssue(code="EMPTY_SQ_TEXT", ..., retryable=True))
```
A branch/splitter SQ (carries `sub_questions`, legitimately null text per SECTION-8 — bagrut's
q1.א) stops raising the retryable issue. Bump `PIPELINE_VERSION` 3.3.0→3.4.0. Prompt/GT/scorer
untouched. This is a pipeline change and must be pre-registered and bisected (it is — P-L1).

**Evidence it is the right lever:** across 7 baseline bagrut draws the retry fired on 5; when it
fires, output tokens ~double (11.6k→25.7k) and t_doc ~doubles (186–220 s → 393–451 s). No other
fixture carries a branch SQ, so no other fixture retries — the headline lives entirely here.

**Honest power statement (for the eventual confirmation):** the pre-registered confirmation is
k=8 all-5. **40 clean trials with zero failures bound the true per-trial failure rate at ≲7%
(rule of three) — they do NOT prove equivalence to baseline.** A latency win must be reported as
"≥30% headline reduction, delta > 2× noise band, 5/5 across 8 trials, 0 INVALID", never as
"proven identical." The bagrut faithful-error gate is the fixture to watch on every repeat.

**Residual accuracy nuance (a reason to run it, not a risk against it):** today the false retry
makes the model *invent* splitter text for the branch SQ to satisfy the correction feedback —
text the SECTION-8 convention says should not exist. It is currently gate-harmless (bagrut passes
5/5) because that node's GT text is null (ungated). P-L1 makes the model keep the correct null
shape. So L1 is expected to *improve* faithfulness at that node while cutting latency.

---

## 5. Residual risk — what this change could break that the 5 fixtures cannot detect

1. **Only one fixture (bagrut) exercises branch sub-questions.** P-L1's whole effect and its
   entire regression surface live on n=1 document. A second nested/splitter fixture is the
   highest-value GT addition for de-risking L1 (out of mission scope — GT is immutable).
2. **The retry occasionally re-rolls a *gated* field by luck.** A retry re-runs the whole
   extraction; on rare draws its second sample could fix something gated that the first got
   wrong. k=8 is the guard; a single gated regression kills L1.
3. **`cached_tokens` / `reasoning_tokens` are not measured.** The instrument sees aggregate
   input/output tokens, not the prefill-cache hit rate or the reasoning/visible split. L4 and
   L6 attribution are therefore partially blind. Exposing them is a small additive read in
   `_call_meta_from_raw` (`usage_metadata['input_token_details']['cache_read']` and
   `['output_token_details']['reasoning']`) — deferred; it is itself a (tiny) pipeline touch.
4. **Transport fragility dominates run reliability, not the pipeline.** Block A lost 14/15
   trials to an `APIConnectionError` window (the pipeline's transport layer does 1 retry / 2
   attempts). Any real deployment or long eval over this connection will lose trials; this is
   orthogonal to extraction latency but it is the thing most likely to make a teacher wait or a
   run fail. See §6.

---

## 6. Out-of-suite latency (named, per mission §6 — the teacher's real wait)

The suite measures **pipeline** latency only. A teacher's wall-clock also includes, none of
which this instrument can see:
- **Cloud Run cold start at `min-instances 0`** — seconds of container spin-up before the
  pipeline entry this report measures from.
- **Cloud Tasks dispatch** (PR-1 async extraction path) — enqueue + OIDC round trip.
- **Frontend polling interval** — the job-status poll cadence adds up to one interval of
  perceived latency after completion.
- **Transport retries/failures** — observed here as a 14/15 INVALID cascade; in prod this is a
  durable-job retry, i.e. minutes.

Given the pipeline itself is 60–450 s of decode, cold start and polling are likely a **minority**
of the teacher's wait today — but if extraction latency is cut ~50% by L1, their *relative* share
grows and they become the next target. Quantifying them needs a deployed-service probe (out of
this mission's surface).

---

## 7. Recommendation for a future *latency* gate threshold (PROPOSED — never self-applied)

Latency is now a **reported** metric (`results.json`/`summary.md`), deliberately **not** in
`gate_pass` (mission §3, forbidden move #8). From the measured distribution, a *future* gate that
Noam could pre-register and approve:
- **Per-fixture `t_doc_max` ceiling**, not a mean — worst-case discipline. Provisional values
  from this baseline: clean fixtures ≤ ~130 s; bagrut ≤ ~250 s **after L1** (the retry-free
  regime). Setting it at today's ~451 s bagrut would gate nothing.
- It must be pre-registered from ≥2 blocks of measured data (as here), keyed to
  `(model, prompt, pipeline_version)` since decode rate is model-specific, and re-baselined on
  any pin change. Do **not** guess it into existence mid-change.

---

## 8. Instrument provenance (additive, proven)

Phase-0 instrument confined to `schemas.py` / `reporting.py` / `runner.py` (commit `efc92fc`).
Per-step timing via the pipeline's existing pure-data `on_progress` seam (injected, **zero
pipeline edits**; `PIPELINE_VERSION` unchanged) + a monotonic wall cross-check. **Additivity
proven:** all `test_*.py` guards pass; a `score_only` re-score of all 5 cached 20260711-131057
predictions is **byte-identical on every scoring field.** `suite_hash` 50994d2a97e3accf →
77db3bb9aea7658b (instrument changed; scores comparable, hash not). **Immutable set untouched:**
`git diff --name-only main...HEAD` over benchmarks/fixtures/markdowns/GT_AUDIT/scoring/gates/
normalize/build/tools/test_* is **empty**; all 5 `benchmarks/*.json` are byte-identical to the
pre-mission sha snapshot.

> **Branch note (finding, not mine to fix):** the branch also carries an unrelated commit
> `64fa19a "PR-5: document mirror…"` (46 app/frontend files) committed by another actor during
> this mission's background runs. It touches **no** immutable-set file. I did not author it and
> did not reset/rebase it away (don't delete what you didn't create). Handed to Noam.

---

## 9. What I would do next with $200 and 20 more fixtures

1. **Run P-L1 to confirmation first** (~$12): screen k=2 {bagrut,csharp}, then k=8 all-5. It is
   the highest value × lowest risk and needs no new fixtures. Expected: headline −~50%, 5/5.
2. **Add 3–5 nested/splitter fixtures** so P-L1's regression surface isn't n=1, and so
   `subquestion_structure_match` / branch-SQ behaviour is exercised across documents. (Requires
   GT authoring — out of this mission.)
3. **Expose `cached_tokens` + `reasoning_tokens`** (tiny additive pipeline provenance read), then
   run a proper **L4 vs L6 frontier**: measure prefill-cache hit rate, then sweep
   `reasoning_effort` ∈ {low, medium} at k=5 across all fixtures, plotting the
   latency/accuracy frontier with bagrut as the gate canary. Promote per-step effort mixing (L7)
   only if a global setting can't hold 5/5.
4. **Screen one model swap (L8)** config-only across the enlarged fixture set — a faster-decode
   generation is the only lever that beats L1's ceiling without touching reasoning depth.
5. **Instrument the out-of-suite terms** (cold start, dispatch, polling) with a deployed-service
   probe, since after L1 they become the teacher's dominant wait.
6. **Harden transport for long eval runs** (the 14/15 cascade): a wider retry/backoff *in the
   eval runner only* (never the gate path) so a network window doesn't cost a whole baseline.
