# P2 / End-to-End Eval Playbook — agent-executable

**Audience:** a coding agent analyzing one Phase-2 (segmentation) or end-to-end
(P1→P2) transcription eval run.
**Goal:** produce the deliverable in §6 — a clear, decision-ready analysis that
ATTRIBUTES every failure to the correct stage. Follow the procedure in order;
apply the decision rules verbatim; never skip the validity or attribution steps.

This playbook assumes you have already internalized `P1_EVAL_PLAYBOOK.md`
(validity-before-significance, the conjunctive gate, the instrument-suspicion
standing rule, the n<10 provisional rule, the worst-doc-over-mean rule). Those
carry over unchanged and are not repeated here. What is NEW in P2 is attribution
across two stages, segmentation correctness, and correction safety.

---

## 1. Context you must hold

**What Phase 2 does.** Phase 2 is INTERPRETATION, not perception. It is
text-only — it never sees the image. It receives the verbatim page text (from
P1, or gold pages in isolation) plus the exam's question structure, and does
exactly one job: SEGMENT the flat transcription into per-(question,
sub-question) answers, joining across pages, routing unlabeled or mislabeled
content by meaning. The P2 prompt is PURE verbatim segmentation: it must not
fix, expand, normalize, or rewrite anything (`Mobby` stays `Mobby`). Correction
is NOT the LLM's job.

**Correction is a deterministic post-pass, never the LLM.** After P2 segments,
`corrector.py` runs as a pure function over each answer, governed by
`correction_policy`:
- `off` — no correction; answers are verbatim segmentation output.
- `impossible` — repairs tokens only toward KEYWORDS (misspelled language
  scaffolding: `privaze`→`private`). Safe tier; keyword targets are never
  graded content. Keyword casing is never touched; tokens <5 chars are not
  keyword-corrected (short-identifier/short-keyword collision guard).
- `spec` — ALSO repairs toward SPEC IDENTIFIERS (`Mobby`→`Hobby`,
  `GetArrShow`→`GetArrShows`). RISKY tier: spec identifiers ARE answer content,
  so this tier can overwrite a real student error. It is ON TRIAL — its
  false-fix rate against faithful GT is its kill criterion.

**Two ground truths, scored on different surfaces. Do not confuse them.**
- `raw_benchmarks/` (raw GT) scores PHASE 1 (perception). Contains all ink:
  headers, margin notes, comments.
- `draft_benchmarks/` (draft GT) scores PHASE 2 / end-to-end (answer content).
  Contains ONLY gradeable answer content per (question, sub-question). It
  DELIBERATELY excludes section markers, margin notes, and non-answer ink. This
  asymmetry is intentional (see `GT_CONVENTIONS.md`). An answer that lacks a
  margin note is CORRECT, not a content-drop bug. Never flag intentional
  draft-GT exclusions as P2 failures.

**The three run modes are an ATTRIBUTION INSTRUMENT — this is the core idea.**
A bad end-to-end answer has up to four possible causes (P1 misread, P2
mis-segmentation, P2 fidelity drift, or a correction error/cancellation). One
number cannot separate them. The modes do:
- `p1_only` — PDF→pages, scored vs raw GT. Pure PERCEPTION signal.
- `p2_only` — GOLD pages→P2, scored vs draft GT. Perception held PERFECT, so
  any failure here is PURE segmentation or correction. The clean P2 signal.
- `per_doc` / `batch` (end-to-end) — PDF→P1→P2, scored vs draft GT. The SHIP
  GATE. Failure here is some mix of the above; you attribute it by comparing
  against `p2_only`.

**The attribution identity (memorize this):** for the same fixture,
`e2e_score` ≈ `p2_only_score` − (perception cost that segmentation can't
recover). Therefore:
- `p2_only` HIGH, `e2e` LOW → the gap is P1 PERCEPTION. P2 is fine; fix P1.
- `p2_only` LOW → P2 SEGMENTATION/CORRECTION is broken independent of
  perception; fix P2. (A low e2e here is mostly P2's fault, not P1's.)
- `e2e` HIGHER than `p2_only` → SUSPICIOUS: correction or cancellation is
  masking something. Investigate before celebrating (§4).

**Metric semantics specific to P2** (in `score_document` → `DocumentScore`):
- `doc_ratio_strict` / `_lenient` — answer-text fidelity vs draft GT (same
  normalizer/`autojunk=False` as P1).
- `coverage` — fraction of draft-GT keys that received predicted content. THE
  segmentation-integrity metric. <1.0 means a key got no content (dropped or
  misrouted).
- `missed_keys` / `extra_keys` — GT keys with no prediction / predicted keys not
  in GT (invented or mis-keyed). The structural segmentation signal.
- `routing_notes` — P2's self-report that it relocated content to a different
  question than labeled. A claim to VERIFY against GT, not to trust.
- per-answer `critical` (operator/structural/method-call recall, abbreviations)
  — same grading-critical fidelity as P1.
- `aggregates.correction` (present only when policy≠off): `n_corrections`,
  `true_fix`, `false_fix`, `neutral`, `false_fix_rate`, `ratio_delta`,
  `by_tier`, `trustworthy`.

---

## 2. Procedure (in order)

### Step 0 — Validity, GT identity, mode
1. Parse failures, model identity, config match — exactly as P1 §0. Contaminated
   docs are excluded from accuracy conclusions.
2. **State which GT scored which surface** (raw→P1, draft→P2/e2e) and confirm
   `correction_policy`. A run that scored e2e against raw GT is invalid.
3. Confirm the mode. If only one of {`p2_only`, end-to-end} was run, say so —
   attribution (§3) requires BOTH for full power; with one, attribution is
   partial and you must mark it.

### Step 1 — Verdict
Gate pass/fail (conjunctive, per doc, against draft GT) · cost vs $0.08 · the
one-sentence headline naming the single most decision-relevant fact.

### Step 2 — Segmentation integrity (P2's core job)
Per doc, from `coverage`, `missed_keys`, `extra_keys`:
- `coverage < 1.0` or `missed_keys` → content for a key was dropped or routed
  elsewhere. In `p2_only` this is unambiguously a P2 segmentation failure (input
  was perfect). In end-to-end, check whether the same key is also empty in
  `p2_only`; if not, the cause is upstream (P1 dropped the page/text).
- `extra_keys` → P2 invented a key or mis-keyed an answer. Inspect the key.
- `routing_notes` present → VERIFY each against draft GT: did P2 correctly move
  mislabeled content (e.g. a student's `ד.` that belongs to `ב.` by content), or
  did it misroute correctly-labeled content? A correct route raises coverage; a
  wrong route shows as a missed_key + extra_key pair.

### Step 3 — Stage attribution (the centerpiece; requires both modes)
Build the per-doc table: `p2_only_ratio`, `e2e_ratio`, `delta = e2e − p2_only`.
Apply the attribution identity (§1). For each failing doc, assign the DOMINANT
cause: PERCEPTION (p2_only high, e2e low), SEGMENTATION/CORRECTION (p2_only low),
or CANCELLATION/MASKING (e2e ≥ p2_only with corrections active). This assignment
is the most decision-relevant output of the whole analysis — it says which stage
the next iteration must target.

If only end-to-end was run: you CANNOT attribute. Report e2e results, flag that
a `p2_only` run is required to separate perception from segmentation, and make
that the recommendation.

### Step 4 — Fidelity & the cancellation trap
For each low-ratio answer with content present (not a coverage failure):
- If `p2_only` ratio for that answer is HIGH → the e2e loss is P1 perception;
  bucket as PERCEPTION (and it belongs in the P1 track, not P2).
- If `p2_only` ratio is also LOW → P2 altered text it should have copied
  verbatim (paraphrase, reorder, drop). This is a P2 FIDELITY failure — the
  prompt's verbatim contract is being violated. Quote the diff.
- **Cancellation check (only when `correction_policy≠off`):** for any answer
  where a correction changed a token AND that change is what made the answer
  match GT, inspect: is the original (pre-correction) token a P1 perception
  error (correction legitimately compensating — benign but masks a P1 weakness)
  OR a faithful student error (correction ERASED a deduction — a false-fix the
  e2e score is now wrongly rewarding)? The faithful draft GT + the false-fix
  referee (§5) is what resolves this; never declare a corrected match "good"
  without checking it isn't a false-fix.

### Step 5 — Correction safety (when policy≠off; the `spec`-tier kill criterion)
From `aggregates.correction`:
- Report `true_fix` / `false_fix` / `neutral` and `ratio_delta`, **split by
  tier** (`by_tier`). `impossible` is expected ~0 false-fix; `spec` is on trial.
- **`false_fix` is the kill count.** A false-fix means a correction overwrote a
  token that faithful GT confirms the student actually wrote. Any non-trivial
  `false_fix` on the `spec` tier KILLS that tier.
- **Trustworthiness gate:** if `trustworthy` is false (n<10 fixtures) OR the
  fixture set contains no deliberately-included student-spec-errors, the
  false-fix rate is UNDERPOWERED. You may NOT conclude "spec tier is safe" — you
  may only report "no false-fixes observed, but underpowered; needs n≥10 with
  included student-spec-errors before any safety claim." Saying "safe" on thin
  data is the failure this gate exists to prevent.
- Net effect: `ratio_delta > 0` means corrections net-helped fidelity; pair it
  with the false-fix count — a positive ratio_delta does NOT license a tier that
  also produced false-fixes (helping most answers while erasing one real error
  is still disqualifying for a grading pipeline).

### Step 6 — GT verification & intentional asymmetry
- List suspected draft-GT bugs (model right, GT wrong) as tasks for Noam.
- BEFORE flagging any "answer is missing content," confirm it isn't an
  INTENTIONAL draft-GT exclusion (margin note, header, comment per convention).
  Intentional exclusions are not P2 failures and must not be reported as such.

### Step 7 — Latency, cost, comparison
P2 adds one text-only call (cheap, fast); end-to-end latency is dominated by P1
(render + p1_call). Report per P1 playbook §4. Compare vs the prior RUNLOG line
if present; one config field per comparison.

---

## 3. Decision rules (apply verbatim)

| Observation | Conclusion you MUST draw | Conclusion you must NOT draw |
|---|---|---|
| coverage<1.0 in `p2_only` | P2 segmentation dropped/misrouted content | "P1 perception problem" |
| coverage<1.0 in e2e, key fine in `p2_only` | upstream P1 lost the text | "P2 segmentation failure" |
| p2_only high, e2e low (same doc) | perception cost; fix P1 | "P2 needs work" |
| p2_only low | P2 segmentation/fidelity broken | "blame the perceiver" |
| e2e ≥ p2_only with corrections on | masking/cancellation — inspect | "correction improved accuracy" |
| answer altered, p2_only also low | P2 verbatim-contract violation | "P1 misread" |
| false_fix>0 on spec tier, trustworthy | kill the spec tier | "net ratio_delta is positive, keep it" |
| false_fix=0 but n<10 / no student-spec-errors | underpowered; no safety claim | "spec tier is safe" |
| routing_note present | verify route against GT | trust the relocation blindly |
| answer missing a margin note/header | intentional draft-GT exclusion (check convention) | "P2 dropped content" |
| only e2e run, no p2_only | attribution impossible; recommend p2_only | any perception-vs-segmentation split |

---

## 4. Standing cautions (P2-specific, additive to P1's)
1. **Attribution needs both modes.** A single end-to-end number is a ship
   verdict, not a diagnosis. Never name a fix surface from e2e alone.
2. **A corrected match can be a false-fix.** End-to-end's biggest trap is an
   answer that matches GT because a correction erased the very student error
   that should have been graded. Faithful GT + the false-fix referee is the only
   thing that catches it; the raw ratio cannot.
3. **n=5 / one exam:** every conclusion provisional; the correction kill
   criterion is meaningless until n≥10 WITH included student-spec-errors.
4. **Read two answer diffs manually per run** as the check on the instrument,
   exactly as in P1 — the segmentation/correction failure nobody anticipated
   shows up in the diff before it shows up in a metric.

---

## 5. The binding question this analysis exists to answer
End-to-end is the SHIP GATE: do the segmented answers match the student's
answers well enough to grade, with no correction having erased a gradeable
error? Every section above feeds one of two decisions: (a) which stage the next
iteration targets (§3 attribution), and (b) whether the active correction tier
lives or dies (§5 false-fix). Keep both in view; do not let a rising e2e ratio
obscure a false-fix underneath it.

---

## 6. REQUIRED OUTPUT — "P2 Eval Analysis" (exact structure)

Produce markdown with exactly these sections, in order. Every claim cites its
number or quotes its diff line. Write "none" where empty; never omit a section.

```markdown
# P2 Eval Analysis — <run_dir>

## 0. Run identity & validity
- config / model_ids / prompt_version / correction_policy / mode / repeats / fixtures
- GT mapping: <which GT scored which surface>  (raw→P1, draft→P2/e2e)
- modes available for attribution: <p2_only? end-to-end? both?>  (if not both, attribution is PARTIAL)
- contaminated docs: <doc: parse failures, finish_reasons, diagnosis> | none
- instrument suspicions (ratio-vs-diff contradictions + recomputation result) | none

## 1. Verdict
- Gate: PASS/FAIL (N/M docs) · Cost: $X.XXXX/doc (Yx headroom)
- Headline: <single most decision-relevant fact>

## 2. Segmentation integrity
| doc | coverage | missed_keys | extra_keys | routing_notes (verified?) |
- per doc; flag every coverage<1.0 with its attributed cause (P2 vs upstream)

## 3. Stage attribution  (REQUIRES both modes; else state PARTIAL)
| doc | p2_only_ratio | e2e_ratio | delta | dominant cause |
(cause ∈ PERCEPTION / SEGMENTATION / FIDELITY / CANCELLATION)
- one sentence per failing doc naming the stage the next iteration must target

## 4. Fidelity & cancellation findings (failing answers only)
- per answer: bucket (PERCEPTION via p2_only / P2-FIDELITY / CANCELLATION), quoted diff line
- every correction that produced a GT-match: benign-compensation or false-fix? (cite §5)

## 5. Correction safety  (omit only if policy=off)
- per tier (impossible / spec): n, true_fix, false_fix, neutral, ratio_delta
- trustworthy? (n≥10 AND included student-spec-errors?)
- VERDICT on the spec tier: LIVE / KILLED / UNDERPOWERED-NO-CLAIM

## 6. GT verification tasks for Noam
- suspected draft-GT bugs | none
- confirmed intentional asymmetries encountered (NOT bugs) | none

## 7. Latency & cost
- end-to-end wall structure; per-doc cost; headroom

## 8. Comparison vs previous run
(only if prior RUNLOG line provided; else "first measured run of this config")

## 9. Recommendation — the ONE next change
- single highest-information change + the metric it must move + the kill criterion
- if attribution was partial: the recommendation IS "run the missing mode"
- secondary candidates as one-liners

## 10. Run-log line (append to RUNLOG.md)
`<date> | <config> | <diff-vs-prev> | gate F (k/m) | attribution: <doc→stage> | worst <doc> e2e <ratio> | spec-tier: LIVE/KILLED/UNDERPOWERED | $<cost> | <one-clause note>`
```

The analysis is DONE when: validity is established and GT mapping stated; every
failing doc is attributed to a stage (or attribution is explicitly marked
PARTIAL with the missing mode named); every coverage failure is assigned to P2
or upstream; the spec-tier verdict is LIVE/KILLED/UNDERPOWERED with its evidence;
every corrected GT-match has been checked for false-fix; intentional GT
asymmetries are excluded from the bug list; and the recommendation names one
change + one target metric + one kill criterion.
