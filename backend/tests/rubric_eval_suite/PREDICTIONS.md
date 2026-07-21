# Pre-registered baseline predictions — written BEFORE the first real run

Registered 2026-07-02, after the GT audit, before any `runner` execution with a
live key. The baseline (`--config default --repeats 5`) is a TEST of these
predictions: confirmations tell us the failure model is right; surprises tell us
the pipeline or the instrument diverges from our theory of it — investigate
before "fixing" anything.

| Fixture | Predicted gate failures | Mechanism |
|---|---|---|
| employee_course_select1 | `selection_match`, `total_points`, `pedagogical_match` | FP1 unfixed: internal `RubricExtraction` schema has no selection fields → predicted `selection_groups` empty → selection fails; `achievable_points` falls back to Σ questions (100) vs GT 50 → total fails; empty draft selection starves Tier A's normalization check → expected `selection_normalization` mistake missing |
| bagrut_899371 | `subquestion_structure_match`, `criterion_recall` | FP2 unfixed: no nested sub-question extraction (q1.א.1/א.2/ב.1/ב.2, q3.ב.1/ב.2) → structure mismatch; q1's prose-only criteria are outside "criteria from rubric tables ONLY" → q1 criteria missed |
| foundations_cs | `criterion_recall` (q1, q3.א) | FP3: inline prose criteria, no rubric table for q1/q3.א |
| hobby_tvshow | `pedagogical_match` UNSTABLE across repeats | GT expects `structural_mislabel` (PrintLowRatingChannel tagged ב, belongs ג) via Tier-B LLM adjudication — a judgment call at temp 0; watch its per-repeat variance specifically |
| csharp_plane_combine | closest to full pass; residual risk: `example_solution_fidelity`, `subcriterion` metrics | 7 verbatim code solutions must be extracted at ratio ≥ 0.85; strike-resolution (6→8, 18→20, 4→0 drop) must hold |

Cross-cutting predictions:
- `pedagogical_match` false-positive guard: the four zero-mistake GTs must stay
  zero; any invented mistake there is a Tier-A/B precision failure.
- Cost/doc well under the $0.40 ceiling (expect $0.02–0.08); any `finish_reason`
  = length/max_tokens invalidates the record — expect none at default max_tokens.
- Determinism: unknown. The k=5 baseline IS the probe. If any metric varies
  across repeats on the same doc, all subsequent comparisons require k-repeats
  worst-run discipline (the P2 lesson).

Falsification discipline after baseline: fix ONE variable per run (FP1 → FP2 →
FP3 order unless the baseline reorders severity), each with a kill criterion
stated before the run.

---

# Addendum — model-sweep predictions (registered 2026-07-05, before any sweep run)

Sweep configs: `gpt-5.5` (openai, effort=high), `claude-sonnet-4-6` (anthropic),
`gemini-3.1-pro-preview` (gemini), vs the `default` gpt-4o baseline. Ceilings
deliberately loosened to 2.00 (functional-first: pathology detection, not economy).

**P-S1 (model-invariant failures).** employee `selection_match`/`total_points`/
`pedagogical_match`, 899371 `subquestion_structure_match`, foundations + 899371-q1
`criterion_recall` fail IDENTICALLY on all four models — these are representational
ceilings (schema/prompt), causally disconnected from capability. Any cross-model
variation on these criteria is noise or a scoring artifact, not signal.
**Falsifier: a model that passes any of them would refute the ceiling analysis
and demand instrument suspicion first.**

**P-S2 (the informative surface).** Cross-model signal lives in: csharp (strike
resolution, 7 verbatim example solutions), hobby (sub_criteria from nested tables,
verbatim fidelity), and per-criterion `text_ratio`/`point_exactness` everywhere.

**P-S3 (reasoning-paraphrase probe).** If gpt-5.5@high shows verbatim `text_ratio`
failures on csharp/hobby that sonnet/gemini do not, reasoning-paraphrase is
implicated; the discriminating experiment is a gpt-5.5@effort=low run. Precedent
for frontier ≠ faithful: gemini-pro case-folding in the transcription suite.

**P-S4 (adjudicator confound).** Tier-B pedagogical adjudication rides the same
model switch. `pedagogical_match` differences across configs conflate extraction
and adjudication changes — do not attribute them to extraction without pinning
the adjudicator (a separate, later variable).

**P-S5 (smoke-stage risks, per provider).** gemini: structured-output schema
translation of RubricExtraction is the likeliest parse failure. gpt-5.5: truncation
(`finish_reason=length`) if reasoning spend crowds the 32k budget — the guard
invalidates the record, raise `max_output_tokens` if seen. anthropic: least risky;
verify non-null finish_reason (stop_reason mapping) on smoke.

Discipline unchanged: k=5 repeats per config, worst-run-per-doc comparison,
validity before significance, one config = one variable.

---

# Addendum — FP1-3 fixes (registered 2026-07-05, before any post-fix run)

Changes landed together (D3): FP1 (selection schema + selection-aware totals/
validation), FP2 (bounded depth-2 nested sub-questions), FP3 (prompt: inline/
prose scoring lines as criteria + never-reconcile; cleaner recalc restricted to
consequence-of-removal). prompt_version: rubric_v3_baseline → rubric_v3.1_fp123.
Expressibility proven offline: perfect-extraction round-trips pass the full gate
on all five fixtures (test_fp123).

**P-F1 (conjunction test of the one-root-cause analysis).** employee's
`selection_match`, `total_points`, and `pedagogical_match` flip to PASS
TOGETHER. A partial flip (e.g. selection passes but total doesn't) falsifies
the single-root-cause claim — investigate the totals path before anything else.

**P-F2.** 899371: `selection_match` passes (choose-4-of-6 now expressible);
`subquestion_structure_match` passes; q1 `criterion_recall` passes; the
spurious RUBRIC-scope annotation is gone and `annotation_match` passes via the
faithful q1.א.2 mismatch (components 1.5+0.5 under declared 3 → rubric_mismatch).
The annotation depends on the model COPYING the inconsistent values — if the
model reconciles them despite SECTION 6, annotation_match fails with a
points-pattern signature (criteria summing exactly to 3): that is a
never-reconcile prompt failure, not a schema failure.

**P-F3.** foundations: `criterion_recall` passes on q1 + q3.א (inline lines,
verbatim incl. point notation).

**P-F4 (JOINT KILL CRITERION — D3).** Any csharp or hobby criterion that passed
the pre-fix worst-run now failing ⇒ schema-bloat / prompt-interaction suspected
⇒ bisect the three patches (they are separable). Watch `criterion_precision`
on csharp/hobby specifically: FP3's prose-criteria rule is the over-extraction
risk (question-body lines misread as scoring lines).

**P-F5 (residual known risks, NOT predicted to pass).** Nothing currently known
blocks full gate passes on all five — this is the first run where 5/5 is the
live hypothesis. Non-determinism (k=5, worst-run) and Tier-B judgment variance
on hobby's pedagogical_match remain the likeliest residual failures.

---

# Addendum — PR-1 text-fidelity instrument (registered 2026-07-06, before the next k≥5 baseline)

**P-T1 (round-trip ceiling — offline falsifier).** With GT texts populated and
placeholder injection removed from the inverse mapper, the expressibility
round-trip must score `question_text_fidelity_min` /
`subquestion_text_fidelity_min` / `text_line_recall_min` at exactly 1.0 on
bagrut/csharp/employee/hobby and None on foundations_cs (no populated text —
all its spans are open items). Any value < 1.0 means the builder or normalizer
mangles long text — an instrument bug found offline before it costs a live run.
*Status: tested in the same PR — CONFIRMED, 1.0/None across all five fixtures
on first execution (test_fp123::test_expressibility_round_trip_all_fixtures).*

**P-T2 (first measured text distribution — baseline expectation).** The next
k≥5 run produces the FIRST live text-fidelity numbers; the ceiling is unknown
and the metrics are UNGATED (gating now would mean guessing a threshold with
zero distribution data). Expected low tail, in order of confidence:
- the four shared-context-between-markers nodes (employee q2.ד, hobby q1.א,
  hobby q2.א, bagrut q5.א) — the prompt currently teaches the OPPOSITE
  convention (context → question_text), so low ratios there measure the known
  GT↔prompt divergence PR-2 will close, not model failure;
- table-encoding nodes (bagrut q1.א.1 trace scaffold, q2/q3 example tables,
  csharp q1, hobby/employee interface tables) — table layout is the weakest
  ratio surface;
- bagrut q4.ב (strike-residue `.` line, R2) and page-continuation noise lines.
No populated GT text contains an `[IMAGE]` marker, so the original
image-marker-reproduction concern is unexercised in this GT revision.

**P-T3 (null-wall removal).** With GT-null ⇒ None semantics, per-node
`text_ratio` 0.0 can now ONLY mean "GT has text, model produced none" — every
0.0 in the next run's reports is a real omission claim, checkable by hand.

**P-PED1 (pedagogical as a second never-reconcile tripwire — post-R2(a)).**
With point_sum_mismatch@2 now EXPECTED in bagrut GT, a model that RECONCILES the
teacher's point error (adjusts 1.5+0.5 to sum 3, or rewrites the declared 3)
silences deterministic Tier A and fails pedagogical_match on the MISSING expected
mistake. Pedagogical now trips on reconciliation from the opposite direction as
annotation_match — two independent tripwires on the same never-reconcile
commitment. Falsifier: a run whose bagrut draft sums q1.א.2 to 3.0 yet passes
pedagogical_match.

**P-PED2 (retro-diagnosis of the 20260705/06/08 bagrut "pedagogical FP").**
Those runs' SPURIOUS point_sum_mismatch (@א when flattened, @2 once nested) is
predicted to be exactly this deterministic Tier A firing on a faithfully-copied
teacher error — not an LLM hallucination. Checkable in the next run's serialized
prediction: the emission will be mistake_id pts:q1.2, target '2', evidence
children_sum=2.0/declared=3.0, byte-identical to the GT entry (probe already
matched the Run-B live draft byte-for-byte).

**P-R1 (retry-policy cost/latency — PIPELINE 3.1.0).** With point-mismatches
non-retryable, bagrut retries → 0 on every draw; worst-doc cost drops from
$0.92–1.40 to ≈$0.45–0.55 (single LLM call) and ~350s of retry latency vanishes;
suite mean/doc drops from ~$0.38 to ~$0.25–0.28. Falsifier: any bagrut draw with
retry_count > 0 absent a NON-mismatch retryable issue.

**P-R2 (behavior invariance — KILL criterion).** Zero gated-metric movement:
5/5 worst-run holds on every valid repeat. ANY gated-metric regression vs the
20260711-131057 baseline ⇒ REVERT the pipeline change.

**P-R3 (faithful-error surfaces identical).** bagrut's rubric_mismatch @ q1.א.2
annotation AND its point_sum_mismatch (pts:q1.2, target '2') pedagogical
expectation appear identical to baseline on every repeat — the no-retry downgrade
path is surface-equivalent to the post-retry path.

**Pre-registered run split (fits remaining ~$4.4):** one run, all 5 fixtures ×
k=3 ≈ $1.25/repeat ≈ $3.75 total. Serves: (1) P-R1..R3 verification; (2) NEW
strip-down reference baseline (supersedes frozen-3.3.1 20260711-131057 — the
retry change moves the cost denominator); (3) bagrut k-caveat top-up: 3
consecutive post-change draws.

---

# PR-2 — transport budget (pipeline 3.1.0 → 3.3.0). Registered 2026-07-13, BEFORE any k-run.

**The variable:** every LLM attempt is now BOUNDED (`timeout`, default **T=360s**),
the OpenAI SDK's hidden 2-retry layer is DISABLED (`max_retries=0`), and ONE owned
retry layer replaces it (1 retry ⇒ 2 transport attempts/logical call) with a
predicate that fails fast on permanent conditions. Prompt UNTOUCHED (3.3.1-tracehdr).

**Scope of the deadline (read before interpreting any of these):** the wall-deadline
path is PRODUCTION-ONLY. The eval runner passes `deadline_seconds=None` ⇒ unbounded
⇒ no entry guard, no Tier-B skip. So the gate and every gated metric are untouched
BY CONSTRUCTION; only the timeout + retry policy are exercised by a k-run.

**P-T1 (quota fails fast).** A quota-class failure (`insufficient_quota`) now fails
in SECONDS with the message "OpenAI quota exhausted — billing issue, not retryable
(RateLimitError: …)". Eval-era behavior was 3 slow SDK attempts then an opaque
string. FALSIFIED IF: a quota failure still burns multiple attempts, or its
invalid_reason does not name billing.

**P-T2 (the 1736s outlier class, on the 360s basis).** The observed per-attempt
distribution is bimodal: all mass ≤235s, one point at 1736s, nothing between. With
T=360 that outlier class is now cut at 360s and retried ONCE. Expected outcome:
either a faster success (reasoning nondeterminism — the retry draws a new sample) or
a clean transport failure named "…failed after 2 transport attempt(s) —
APITimeoutError". In PROD: zero stranded/stale `extracting` rows from this class
(the whole point). In the EVAL (unbounded deadline): this class may newly appear as
an INVALID record — that is the bound working, not a regression.
KILL: if a doc that previously succeeded under 235s now times out, T=360 is too
tight ⇒ raise `EXTRACTION_LLM_TIMEOUT_S` (the #1 knob to watch this run).

**P-T3 (zero gated-metric movement).** Everything else is unchanged: same prompt,
same validation loop, same never-reconcile tripwires. Worst-run gate per fixture
must equal the 3.3.1/3.1.0 baseline.
KILL: any gated regression ⇒ REVERT the transport commits (they are one bisectable
unit: bounded params + retry layer + deadline).

**Derived budget arithmetic (T=360, 1 retry, TASK_BUDGET=840):**
entry guard = T+60 = 420s · transport-attempt floor = T+10 = 370s · worst logical
call = 2×360 + backoff ≈ 725s ⇒ still fits ONE call inside the budget, and a second
is refused rather than started. Overshoot past the 900s Cloud Run kill is therefore
unreachable via the guarded path.

---

# MISSION latency — pre-registered candidates (registered 2026-07-21, BEFORE any candidate run)

Scope note: per the run owner's decision this mission STOPS after baseline + attribution +
pre-registration. These are pre-registrations for FUTURE authorized runs, NOT results. No
candidate was run. Baseline: gpt-5.5/effort=medium/prompt 3.3.1-tracehdr/pipeline 3.3.0,
2 blocks k=3 (20260721-134812 + -142212), 30/30 valid, 5/5 gate. Headline = bagrut
t_doc_median 413.9s. Noise floor (clean fixtures) 1-11% between-block ⇒ MDE ≈ 2×.

**P-L1 (retry elimination — the primary Tier-1 candidate; HIGHEST value × lowest risk).**
Variable (exactly one): `pipeline.py::_validate_extraction` — the `EMPTY_SQ_TEXT` check gains
`and not sq.sub_questions` so it fires ONLY on LEAF sub-questions. A branch/splitter SQ (has
sub_questions, legitimately null text per SECTION-8 — e.g. bagrut q1.א) no longer raises the
retryable EMPTY_SQ_TEXT issue. Bump PIPELINE_VERSION 3.3.0→3.4.0. Prompt/GT/scorer UNTOUCHED.
Term attacked: t_retry_overhead. Measured mechanism: bagrut's null-text branch SQ falsely
triggers a retryable EMPTY_SQ_TEXT ⇒ 1 full extra ~200-230s LLM call; on retry the model
INVENTS splitter text to satisfy the false feedback (a latent accuracy smell, currently
gate-harmless). Fired on 5/7 baseline bagrut draws.
PREDICTED effect: bagrut t_doc_median 413.9s → ~200s (the observed retry-absent regime 186-220s);
headline reduction ≈ 48-55% (clears the 30% target and the 50% stretch). bagrut between-block
variance 104.7% → clean-fixture-like ~10%. bagrut retry_count → 0 on faithful draws. Other 4
fixtures unaffected (they carry no branch SQ / no retry). Cost/doc DROPS (fewer tokens) — not a
cost-for-latency trade.
PREDICTED gated metrics: ZERO movement. The retry today makes the model invent branch-SQ text yet
bagrut still passes 5/5; returning the retry-free first extraction (correct null-text shape) must
also pass. subquestion_text_fidelity at that node is None (GT null ⇒ not-comparable), so it can
only improve or stay — an UNGATED, WATCHED diagnostic.
KILL: (a) ANY gated-metric regression on ANY fixture at k≥5 (5/5 must hold) ⇒ REVERT; (b) bagrut
retry_count not →0 (EMPTY_SQ_TEXT still fires OR a different retryable class now dominates) ⇒ fix
insufficient; (c) validity/transport-failure rate worse; (d) any ungated diagnostic moves
materially ⇒ surface, do not bank.
CONFIRMATION PLAN (for Noam to authorize): screen k=2 on {bagrut, csharp} (~$2.7), then k=8 all-5
(~$9-10, cheaper than baseline because the retry is gone). ~$12 total.

**P-L6/L7 (reasoning_effort — Tier 2, PROPOSE-ONLY, requires Noam).** Decode is ~99% of t_doc and
t_doc ≈ output_tokens/~57 tok/s, so effort (reasoning-token volume) is the biggest RAW knob and
cuts ALL fixtures, not just bagrut. But it is the lever most likely to break bagrut's faithful-
error gate (annotation_match + pedagogical_match never-reconcile tripwires) — the hardest reasoning
in the set. Config-only to screen (gpt-5.5 supports none/low/medium/high/xhigh). L7 (per-step effort
mixing) needs per-step knob plumbing in the LLM constructor policy. Do NOT promote without Noam;
test low before none; bagrut is the make-or-break fixture. Registered as the second front, unrun.

**P-L8 (model swap — Tier 2, PROPOSE-ONLY).** A generation with faster decode or fewer output
tokens is a direct latency win. Config-only to screen (cross-family configs exist). Promotion is a
Noam decision (cost table, prod pin, provider risk). Unrun.

**Ruled out by the latency model (do not spend screens):** L5 render (0.1-0.35s, <0.3%); L2 client
reuse (~100-300ms/call vs 60-410s); L4 prompt-cache (attacks prefill, a minority of decode-dominated
t_doc; cached_tokens not yet measured — a small additive pipeline provenance read would quantify it,
low ceiling). Tier-B second call (hobby only, ~9.5s) is minor and fires only on a structural trigger.
