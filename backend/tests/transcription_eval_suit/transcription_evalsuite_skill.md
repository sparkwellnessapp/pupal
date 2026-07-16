# Transcription Eval Suite — Engineering & Analysis Skill
 
> **This is a briefing for a future thread (or coding agent) that has never seen this work.**
> Read it before touching the transcription pipeline, its prompts, its scorer, or analyzing any run.
> It carries the architecture, the analysis methods, the benchmarks, the locked decisions, and the
> hard-won lessons. **When this document and the code disagree, the code is truth — fix the doc.**
> Implementation specifics (exact field names, line numbers) drift; verify against the suite before
> relying on them. The *reasoning* here is the durable part.
 
Location: `vivi-codebase/backend/tests/transcription_eval_suit/` (note: `suit`, not `suite`).
Run anything with `PYTHONPATH=.` from `backend/`. Tests: `python -m pytest -q tests/transcription_eval_suit`.
 
---
 
## 0. The prime directives (failure-mode-ordered — internalize these first)
 
These are the rules that, when violated, have actually produced wrong conclusions in this project.
 
1. **Measure first; one variable per run.** No optimization ships without a falsifiable eval gating it.
   Every change is a hypothesis with a stated kill criterion. Change exactly ONE field per run, or you
   cannot attribute the result. (We have already burned runs on prompt+scorer moving together — the
   analysis had to disentangle by surface, which is luck, not method.)
2. **Validity before significance.** Before reading any accuracy number: check parse failures,
   `finish_reason` (truncation = `MAX_TOKENS`), model identity, config match, and exclude contaminated
   docs. A truncated or unparsed doc is INVALID and must be dropped from accuracy conclusions, not
   averaged in.
3. **The instrument is the prime suspect.** When a ratio contradicts its own diff, suspect the scorer
   before the model. Four+ instrument bugs have silently corrupted conclusions here (see §5). A number
   you cannot reconcile with the raw diff is a number you do not yet understand.
4. **Attribute before fixing.** A bad end-to-end answer can come from perception (P1), segmentation
   (P2), correction, or cancellation between them. The three run modes are the instrument that tells you
   which. Never name a fix surface from an end-to-end number alone (§2, §3).
5. **Worst doc over mean.** The mean is forbidden as the only aggregate. One catastrophic doc (a dump, a
   refusal, an empty answer) is the signal; it hides inside a healthy mean.
6. **n<10 is provisional; one exam is provisional.** All five current fixtures are one exam. Flag/recall
   metrics are noise below n=10 (`FLAG_TRUST_MIN_FIXTURES`). The correction-safety verdict is
   meaningless until n≥10 with deliberately-included student-spec-errors.
7. **Don't answer a grading question with an instrument change.** "This token won't be graded" is a
   grading judgment; it does not belong in a perception metric. Tuning the ruler until docs pass is
   motivated measurement (the rejected Policy 1, §8).
8. **Locked decisions are the spec.** The decisions in §8 were made deliberately, often against an
   intuitive alternative. Do not silently reverse one. To change it, surface it as an open decision with
   the reasoning, the way it was originally made.
---
 
## 1. What the suite measures, and the two-phase architecture
 
**The product.** Vivi transcribes handwritten Israeli Bagrut CS exams (Java/C#-like code + Hebrew
comments) so teachers can grade them fast. The transcription must be faithful enough to grade against
and must flag its own likely errors for quick teacher review. The north-star metric is **teacher
after-school hours eliminated** — every gate and proxy below ultimately answers to that, which matters
when deciding whether a proxy is too strict (§4, §10).
 
**The pipeline is two independently-evaluated phases. This split is the spine of everything.**
 
- **Phase 1 — PERCEPTION.** Image → verbatim per-page text. **Spec-blind by design.** P1 is never told
  the exam structure or expected identifiers. This is the *anti-contamination property*: a model that
  never saw the spec cannot "helpfully" normalize a student's `Mobby` toward the spec's `Hobby` and
  silently erase a gradeable error. Output schema: `{"pages":[{"page_number","text"}]}` (typed page
  numbers, sortable). P1 carries all image cost and rate-limit pressure; its unit is the page, so the
  cross-page-answer problem doesn't exist at this layer (it's P2's job).
- **Phase 2 — INTERPRETATION.** Text-only (never sees the image). Pages + exam spec → per-(question,
  sub-question) answers. **Pure verbatim SEGMENTATION** — it routes and joins, it never rewrites. Cheap,
  fast, near-free harness iteration.
- **Correction is a DETERMINISTIC POST-PASS** (`corrector.py`), never the LLM (§6). The LLM stays
  spec-blind for rewriting; correction is a pure function the scorer runs after segmentation. This is
  what lets the corrected (prod-realistic) numbers appear in scores without contaminating the model.
**Why this matters for every analysis:** perception fidelity and grading relevance are *different
questions on different surfaces*. Keep them separate. The single most common analysis error is letting a
downstream (grading) judgment move an upstream (perception) measurement.
 
---
 
## 2. The three run modes ARE the attribution instrument (the core analytical tool)
 
The runner (`runner.py`) has four modes; three are the attribution triad. A low end-to-end score has
multiple possible causes; one number cannot separate them. The modes do:
 
- **`p1_only`** — PDF → pages, scored vs **raw GT**. Pure PERCEPTION signal.
- **`p2_only`** — **gold** pages → P2, scored vs **draft GT**. Perception held PERFECT, so any failure
  here is pure SEGMENTATION or CORRECTION. The clean P2 signal.
- **`per_doc` / `batch`** — PDF → P1 → P2, scored vs **draft GT**. End-to-end. **The only surface that
  gates shipping.** Failure is some mix of the above; you attribute it by comparing to `p2_only`.
**The attribution identity (memorize):**
- `p2_only` HIGH, `e2e` LOW → the gap is **P1 perception**. P2 is fine; fix P1.
- `p2_only` LOW → **P2** (segmentation/fidelity) is broken independent of perception; fix P2.
- `e2e` ≥ `p2_only` with correction ON → **masking / cancellation**; investigate before celebrating (§6).
**Attribution requires BOTH modes.** A single end-to-end run is a ship verdict, not a diagnosis. If only
end-to-end was run, the correct output is "attribution PARTIAL — run `p2_only`," not a guess at the stage.
 
`gate_pass()` is **duck-typed**: `PageDocumentScore` (P1) and `DocumentScore` (P2/e2e) expose the same
field names (`doc_ratio_strict`, `coverage`, `critical`), so the same conjunctive gate applies to both
surfaces unchanged.
 
---
 
## 3. The benchmarks and the two ground truths (do not confuse them)
 
Two GT folders, scoring two different surfaces. **The asymmetry between them is intentional.**
 
- **`raw_benchmarks/*.md`** — format `=== PAGE n ===`. Scores **Phase 1**. Contains ALL ink: section
  markers, headers, margin notes, comments, everything the student wrote. (Student *identity* —
  name/class/ID — is excluded per Policy 2, §8.)
- **`draft_benchmarks/*.md`** — format `=== Q{n}.{sub} ===`. Scores **Phase 2 / end-to-end**. Contains
  ONLY gradeable answer content per key. DELIBERATELY excludes section markers, margin notes, and
  non-answer ink. An answer that lacks a margin note is CORRECT, not a content-drop bug.
**The intentional-asymmetry trap:** when scoring e2e against draft GT, never flag "the answer is missing
the margin note / header" as a P2 failure — draft GT excludes those on purpose. This is the inverse of a
GT bug and an analyst will make this mistake every run if not warned.
 
**GT conventions (`GT_CONVENTIONS.md`, locked v1.1):**
- Verbatim ink. Crossed-out text omitted entirely, no marker.
- Section markers normalized to FORMAT (`שאלה {n}`, sub-question as `א.`) but the LETTER is kept verbatim
  even if the student mislabeled it (a student's `ד.` stays `ד.`).
- Printed furniture (printed page numbers, exam-form chrome, printed question text) excluded — not ink.
- `[?]` for illegible (the current benchmarks contain none). Empty page → `""`.
- **Draft-body rule:** draft answer bodies are answer CONTENT only — markers/headers/margin notes
  excluded. (Confirmed example: dan's margin note is in raw GT, absent from draft GT, by design.)
**The fixtures (n=5, ONE exam — Hobby/TvShow):** `moran_aharon`, `dan_basiuk`, `din_ezra`,
`omer_gelber`, `yonatan_basiuk`. Each has six keys: (1,א)(1,ב)(1,ג)(2,א)(2,ב)(2,ג). The exam spec for P2
is loadable from the rubric `draft_json` via `spec_from_rubric_draft`; per-sub-question content
signatures were added ("enrichment") and proved decisive for routing (§7).
 
**Fixture selection criterion:** deliberately include students who misspell spec-named identifiers
(`Mobby`/`Hobby`, `TVshow`/`TVShow`, `LowesRateChannel`, `pupulateHobbies`, `minuteS`), because those are
what make the correction-safety verdict decidable. All five current fixtures qualify; the open need is
*more exams*.
 
---
 
## 4. The metrics and the conjunctive gate
 
Scoring (`scoring.py`) uses difflib with **`autojunk=False`** (load-bearing — see §5) and a normalizer
(NFC → lower → strip-all-whitespace). Each surface produces:
 
- **`doc_ratio_strict` / `_lenient`** — document-level text fidelity (lenient = illegible-stripped).
- **`coverage`** — fraction of gold keys (P2) or gold pages (P1) that got predicted content. The
  segmentation/perception-integrity metric.
- **`missed_keys` / `extra_keys`** (P2), `missing_pages` / `extra_pages` (P1) — structural signal.
- **Critical-token recalls** (profile `JAVA_BAGRUT`), micro-averaged: **`operator_recall`**,
  **`structural_recall`**, **`method_call_recall`**, plus **`abbreviations_altered`** (the set of
  abbreviations whose form changed). These are the grading-critical fidelity signals.
- **`routing_notes`** (P2) — the LLM's self-report of relocations. A claim to VERIFY against GT, not trust.
**The conjunctive gate (`gate_pass`), per doc — ALL must hold:**
`doc_ratio_strict ≥ 0.98` AND `coverage = 1.0` AND `operator_recall = 1.0` AND `structural_recall = 1.0`
AND `method_call_recall = 1.0` AND `abbreviations_altered` empty. **Cost gate:** `cost_avg_per_doc ≤ $0.08`.
 
**The doc-ratio blindspot (a known instrument limitation, not a bug — but it WILL fool you):**
`doc_ratio_strict` concatenates answers in gold-key order, so it is *blind to a boundary-preserving
merge*. A doc can show `doc_ratio 0.985` while one answer key is empty (its content merged into a
neighbor). Observed live: omer e2e 0.985 with Q1.ג = 0.0. The per-answer ratios and critical recalls
expose it; the doc-ratio alone hides it. **Always read per-answer, never trust the doc-ratio alone.**
 
**The proxy-vs-product question (live, unresolved — §10):** is `method_call_recall = 1.0` the right
floor, or too strict for a *teacher-review* pipeline? The north star is hours saved, and the real metric
is teacher edit-count at review, not difflib recall. A pipeline at 0.95 method-call recall that *flags*
the rest may already deliver the time saving. This is a gate-threshold decision to make in the open — not
by quietly loosening the scorer.
 
---
 
## 5. Instrument integrity — the load-bearing discipline
 
**The eval harness is itself under test.** Every conclusion rides on the instrument being correct, and
the instrument has been wrong, silently, repeatedly. Each bug below was caught, pinned with a regression
test, and is the reason for a current design choice. A future thread WILL trust a number it shouldn't
unless it carries this suspicion.
 
Bugs caught (the catalog — "validate the instrument" is a standing rule):
- **`difflib` `autojunk` corrupting ratios** — the most dangerous one. On strings ≥200 chars, difflib's
  autojunk heuristic silently dropped "popular" characters and read a true 0.88 ratio as 0.21. Fix:
  `autojunk=False` everywhere. If a ratio looks impossibly low, this is the first suspect.
- **Single-metric gate** — a lone ratio passed docs with grading-critical token misses. Fix: the
  conjunctive gate.
- **Length-dependent error label** — the `is_error` threshold behaved differently by answer length.
- **Cross-answer critical-token cancellation** — a miss in one answer was masked by a hit in another
  under naive aggregation. Fix: per-answer critical scoring.
- **Empty-page-as-covered** — a blank prediction counted as a covered page. Fix: empty page = missing
  for coverage.
- **`p1_call` sum-vs-max** — summing concurrent per-page call times misrepresented wall time. Both
  `p1_call_sum` and `p1_call_max` are now recorded; max reflects concurrent wall time.
- **Corrector short-token over-correction** — `foo`→`for` (edit distance 1). Fix: keyword-target
  correction requires token length ≥5 (§6).
- **Provenance** — `finish_reason` recorded on every call so truncation is diagnosable (it surfaced
  moran's `MAX_TOKENS` truncation that invalidated a doc).
**The standing rule:** when a ratio contradicts its diff, recompute it standalone before believing it.
Read at least two answer diffs by hand every run — the failure nobody anticipated shows up in the diff
before it shows up in a metric.
 
---
 
## 6. The corrector and the false-fix referee (`corrector.py`)
 
Deterministic two-tier post-pass. `correction_policy ∈ {off, impossible, spec}`, default `off`. Reframed
(locked) from "fix spec-divergent identifiers" to **two tiers by target safety**:
 
- **`impossible`** — corrects ONLY toward C# **keywords** (misspelled scaffolding: `privaze`→`private`).
  Safe: keyword targets are never graded content. Guards: keyword-target requires token length ≥5
  (defeats `foo`→`for`); casing never touched; protected tokens (`CW`/`CR`) never altered.
- **`spec`** — ADDS spec-identifier targets (`Mobby`→`Hobby`). **RISKY and ON TRIAL.** Spec identifiers
  ARE answer content, so this tier can overwrite a real student error — the exact deduction-erasing
  failure the whole spec-blind architecture exists to prevent. Edit distance ≤2, uniqueness required,
  ties flag rather than fix.
**The false-fix referee (`measure_corrections`)** classifies each correction against *faithful* GT:
`true_fix` (moved toward GT — good), `false_fix` (overwrote a token GT confirms the student wrote — the
**kill count**), `neutral`. **Any non-trivial `false_fix` on the `spec` tier KILLS that tier.**
 
**Trustworthiness gate:** the verdict is `UNDERPOWERED-NO-CLAIM` until n≥10 fixtures WITH deliberately-
included student-spec-errors. "No false-fixes observed" at low n is NOT "safe." Report it as the three-way
verdict: **LIVE / KILLED / UNDERPOWERED-NO-CLAIM.** A positive net `ratio_delta` does NOT rescue a tier
that produced any false-fix — helping most answers while erasing one real error is disqualifying for a
grading pipeline.
 
**The cancellation trap (links correction to attribution):** end-to-end's subtlest failure is an answer
that matches GT *because a correction erased the very student error that should have been graded*. The
raw ratio cannot see it; faithful GT + the false-fix referee is the only detector. Never declare a
corrected GT-match "good" without checking it isn't a false-fix.
 
---
 
## 7. What we've learned empirically (the findings that should shape the next move)
 
**P2 segmentation is ~solved; P1 PERCEPTION is the dominant ship wall.** Across model and resolution
sweeps, `method_call_recall` sits ~0.68–0.81 on the perception surface and does not move. P2 routes 4/5
docs correctly under real input once the spec carried per-sub-question signatures.
 
**The P1 perception wall decomposes — and most of it is NOT genuine misreads.** Reading the diffs,
`method_call_recall` misses are three buckets: **case-only** (`For`→`for`, `CW`→`cw`), **GT typos**
(draft GT `getisSportiv`/`pupulateHobbies` vs faithful `getisSportive`), and **genuine misreads**
(`Tv Show`→`TvShow` join). Only the last is real perception. This is why the live levers are gate
calibration + GT cleanup, not more perception tuning (§10).
 
**Resolution is FALSIFIED as a lever.** `image_max_px` 2000→2400 moved `method_call_recall` on zero valid
docs, regressed din (page-1 over-read), triggered a moran truncation, and cost +59% / +25% latency.
Reverted to 2000. (Caveat: din's "regression" may be the model reading *real* ink that stale GT lacks —
an unresolved GT-completeness question, not necessarily a model loss.) The easy P1 knobs are spent: model
already escalated to frontier (gemini-pro), resolution falsified.
 
**P1 has a measurable normalization floor.** gemini-pro lowercases `CW`→`cw`, `For`→`for` *despite* an
explicit, emphasized "preserve capitalization" instruction. The prompt cannot fully suppress it. This is
benign for casing but is direct evidence that "the prompt says verbatim" ≠ "the model is verbatim" — keep
that in mind for fidelity on things that DO change grades.
 
**The cheap P2 model (gpt-5.4-nano) is NON-DETERMINISTIC at temperature 0.** The same input has produced
a swap one run, a merge the next, a refusal the next. **Consequence: single-run P2 prompt comparisons are
uninterpretable** — you cannot tell "the fix worked" from "nano landed a better guess." Any P2 prompt
change must be tested with **k≥5 repeats** on the affected docs, pre and post. A single clean run is a
lucky draw.
 
**The P2 prompt-iteration pattern (the most important strategic signal).** The sequence has been:
dump (moran absorbs whole doc) → fixed via exclusivity/partition → swap (omer follows marker over
content) → fixed via content-first authority → refusal (din emits nothing) + merge (yonatan) → degraded-
path fix. **Every prompt fix solved its target and surfaced a new failure on a different doc — and they
are all the same root cause:** nano cannot reliably locate unit boundaries on messy input, so prompt
pressure just *redistributes* the failure (dump and refusal are the same boundary-uncertainty, inverted).
 
**The real kill criterion for the P2 prompt surface** (wider than "if din still refuses"): **if a P2
prompt fix surfaces ANY new boundary-failure on a previously-working doc, the prompt surface is exhausted
→ escalate the P2 model to frontier.** Watch the whole partition, not just the targeted doc. The prompt
surface still has traction (content-authority genuinely fixed omer's swap), so attempts remain warranted —
but one more redistribution closes the case for prompting and the model escalation becomes evidence-based,
not asserted. Escalating also *restores measurability* (a deterministic P2 model makes prompt comparison
interpretable again).
 
---
 
## 8. Locked decisions (do NOT silently reverse — §0.8)
 
- **Policy 2 — drop student identity from transcription (APPROVED).** P1 prompt excludes handwritten
  name/class(כיתה)/ID; keeps `שאלה {n}` / `א.` markers (load-bearing for attribution). Prompt-side,
  eval-only, identity-only. Bumped P1 prompt t1.1→t1.2.
- **Policy 1 — drop Hebrew comments from scoring (REJECTED).** It answers a grading question with an
  instrument change, deletes the only Hebrew/code-switching perception signal, and its selling point
  ("ratios will rise") was motivated measurement. Comments stay in the P1 ratio as a DIAGNOSTIC (the
  Hebrew canary). If a comment-blind view is ever wanted, add it as an *additional* reported metric, never
  a default-on replacement — and gate end-to-end (where draft GT may already exclude comments) rather than
  mutilating P1.
- **Case-folding (the abbreviation/keyword ruling).** Abbreviation check is case-insensitive on CASE ONLY
  (`CW`/`cw` not flagged) but MUST still flag `CW`→`Console.WriteLine` *expansion* (case-fold and
  expansion-detection are different; preserve the latter). Critical-token recall is case-insensitive for
  **C# KEYWORDS ONLY** (`For`/`for`) via `case_insensitive_keywords` (default ON). **Identifier casing
  stays case-SENSITIVE** (Noam's ruling: Bagrut may grade method-name PascalCase). This change forced a
  `method_call_recall` re-baseline — prior numbers are not cross-run comparable to post-change ones.
- **Architecture locks:** spec-blind P1; pure-segmentation P2; correction is a deterministic post-pass
  (not an LLM instruction); `autojunk=False`; two GTs with intentional asymmetry; the conjunctive gate;
  worst-doc-over-mean; depth-first scheduler for time-to-first-draft.
---
 
## 9. How to run an eval and produce the analysis
 
**Run** (real API calls): `PYTHONPATH=. python -m tests.transcription_eval_suit.runner --config <name>
--mode <p1_only|p2_only|per_doc|batch> --repeats <k>`. Configs are small JSON files under `configs/`
matching `PipelineConfig` fields (note: the field is `correction_policy`, values `off|impossible|spec` —
a stale config with the old `correction_mode` key fails loudly at load, which is correct).
 
**Artifacts** land in `results/<timestamp>_<config>/`: `results.json` (stable schema, the regression-gate
input — stamps `prompt_version`, `config`, `models{id,tier}`, per-record scores+gates+cost+`finish_reason`,
aggregates with `worst_doc` and `flag_metrics_trustworthy`), `summary.md` (the human read), and
`report_<doc>.md` (per-answer gold | pred | diff — the manual-review companion; read it, don't just read
the summary).
 
**The analysis deliverable** follows the playbooks (kept alongside this doc):
`P1_EVAL_PLAYBOOK.md` (perception, 8-section contract) and `P2_EVAL_PLAYBOOK.md` (two-stage attribution,
11-section contract with the LIVE/KILLED/UNDERPOWERED correction verdict and the cancellation-trap
section). A run analysis is DONE only when: validity is established and contaminated docs excluded; every
failing doc is attributed to a stage (or attribution explicitly marked PARTIAL with the missing mode
named); the doc-ratio blindspot is checked (per-answer, not just doc-ratio); intentional GT asymmetries
are excluded from the bug list; and the recommendation names ONE change + ONE target metric + ONE kill
criterion.
 
**Provenance principle:** a result is a function of `(fixtures, config, prompt_version, model_versions)` —
all four are recorded. P1 and P2 prompts version independently (P1 at t1.2; a separate `P2_PROMPT_VERSION`
should track the P2 prompt, since the two evolve separately — conflating them is a smell).
 
---
 
## 10. The critical path / open questions
 
In rough priority — the next thread should weigh these against gate-leverage (how many docs a lever moves
across the gate), not tractability:
 
1. **Fixtures to n≥10 across ≥2 exams.** This is the highest-leverage *unblocker*: it gates generalization
   of every perception conclusion, the entire correction-safety verdict (still UNDERPOWERED-NO-CLAIM), AND
   the overfitting risk that the spec-enrichment win fit one exam's vocabulary. Cannot be deferred much
   longer — most other conclusions are provisional until it lands.
2. **Gate / metric calibration.** Decompose every `method_call_recall` miss across docs into
   {case-only, GT-typo, genuine-misread} to quantify how much of the `=1.0` floor is even grade-relevant;
   then decide whether `=1.0` serves the after-school-hours north star or just the proxy (§4). This is
   plausibly the lever that "passes" docs, because much of the wall is not genuine error.
3. **GT cleanup.** Recurring draft-GT typos (din's `getisSportiv`/`pupulateHobbies`) penalize faithful P2
   output. Reconcile draft↔raw against the PDFs. Also resolve din's page-1 SchoolHobbies block (real ink
   the model finally read vs over-read) — it decides whether a "regression" was a GT-completeness bug.
4. **The P2 model-escalation trigger.** Hold the kill criterion in §7: if the next P2 prompt fix surfaces
   a new boundary-failure on a working doc, escalate P2 to frontier (which also restores measurability).
   Until then, test every P2 prompt change with k≥5 repeats on the affected docs.
5. **The spec-tier correction verdict.** Gated entirely on (1). Run `correct_spec` against the audited
   fixtures and read the false-fix count; it is LIVE/KILLED/UNDERPOWERED by the referee, not by argument.
**The one-paragraph orientation for whoever picks this up:** the harness has done its job — it proved P2
segmentation is ~solved and isolated the wall to P1 perception, most of which is case-folding and GT
typos rather than genuine misreads. So the frontier is no longer "tune perception"; it is calibrate the
gate against the grading reality, clean the GT, expand the fixtures to make any of it generalize, and
escalate the P2 model the moment prompt-iteration starts redistributing rather than reducing failure.
Keep the instrument under suspicion, change one variable at a time, trust the worst doc over the mean, and
never let a number outrun the diff it came from.