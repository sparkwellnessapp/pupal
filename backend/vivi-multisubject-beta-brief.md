# Brief: Multi-subject Vivi (English + Math) — One-day functional beta

**Read first, in full:** `CLAUDE.md` (§0, §3.3, §4, §5, §14 load-bearing) and `transcription_evalsuite_skill.md` (§0, §1, §3, §6, §8). Those rules apply without exception, with the explicit constraint-driven deviations listed in §1 of this brief.

**Shape of this task:** research (timeboxed) → plan → **stop for approval** → implement in gated phases → smoke gate → phase-gate report. The plan is short, but it exists and it is approved before code. CLAUDE.md §0.1 is not suspended by the deadline.

---

## 0. The constraint, stated honestly

Deadline: **functional** beta by end of tomorrow.

Available data, in the repo at `backend/tests/rubric_eval_suite/fixtures/`:
- `English_rubrics-solutions/1/`, `/2/`, `/3/` — three English Bagrut **rubric + model-solution pairs**. In each folder: one `.docx` (the rubric, converted to DOCX) and one `.pdf` (the model solution — **typed, not handwritten**).
- `Math_rubrics/` — **one** Math rubric, `.docx`.
- **No student scans for either subject.** Founder-authored handwritten smoke pages arrive tonight (§6). Real graded student data arrives over the coming weeks.

What this data is and is not: four real rubrics (three English, one Math) settle **rubric structure** (D-3, D-8, C4) with evidence instead of conjecture. A model solution is a *ceiling* artifact — a perfect answer — not a graded student test; it can smoke-test extraction→plan→verify→price end to end and pre-register one falsifiable prediction (§5), but it is **not** ground truth for grading accuracy and must never be described as such.

Consequence you must design around: **accuracy cannot be validated in this cycle, but rubric structure can be decided from real artifacts.** The beta is defined by what can be established without student data:

1. **The CS path is a pure refactor.** The existing transcription eval suite, the five ratified GT students, and `pytest -q` are the gate. Any CS regression kills the phase.
2. **Every English/Math-specific choice is data, not code** — prompt fragments, scorer profiles, renderer flags, notation grammar — so being wrong is cheap to fix when data lands.
3. **No subject-availability messaging, anywhere.** There is no in-product text of the form "X is not yet supported for Math/English." Every path a Math or English teacher can reach is functional. Where grading semantics are not yet modeled (deductions, follow-through), the fallback is a *working* path — the teacher's existing override — not a notice. What the system does not yet model is recorded as internal telemetry (§4 C4), never as teacher-facing copy.
4. **Every untestable claim is pre-registered** in `PREDICTIONS.md` with a kill criterion, so the dataset, when it arrives, tests a prediction rather than confirming a belief.

"Beta" means: an English or Math teacher can upload a rubric of any common shape (additive steps, band/level criteria, mixed) and a batch, get a faithful transcription with correct rendering (prose, LaTeX notation, figures), review it, get a draft grade on every criterion, override, and approve — the same complete loop a CS teacher has today. It does *not* mean accuracy is known. Internal docs, `PREDICTIONS.md` and the phase-gate report say so plainly; the product UI does not.

---

## 1. Standing orders (task-specific)

1. **Evidence, not assertion.** Every "X is subject-agnostic" / "Y leaks CS" cites `path:line`. "Likely" is banned from the ledger.
2. **Census before design, timeboxed.** Research completes and is written down before design. Target ≤2 hours; if the census is incomplete at the box, ship it labeled PARTIAL with the unread files listed. An honest partial census beats a confident fabricated one.
3. **Surface, don't decide.** Forks are open decisions with options + recommendation + deciding evidence. But mark each as **DECIDE-NOW** (Noam can rule today with no data) or **DEFERRED** (needs data; beta uses the stated fallback).
4. **Named things stay named.** INV-1..4, CW-1/CW-3, VER-2, RGC-1, ANN-1, Draft→Contract, spec-blind P1, pure-segmentation P2, deterministic corrector, conjunctive gate, worst-doc-over-mean. Changing one is an open decision with the original reasoning restated.
5. **The ontology is extended exactly once, narrowly, and it reopens a §14 rule — flag it as such.** Band/level criteria are *structurally* required for English to be functional (a 0/10/20/30/40 band criterion fails INV-2/INV-3 and hard-blocks compilation — worse than any warning). The extension is `levels` on `Criterion` (§4 D-3). It is **not** the old `ScoringLevel`/`ReductionRule`/`RuleKind` rule-based grading scaffolding that §14 bans — that was grading *rules*; this is rubric *structure* whose grading is still Plan/Verify/Price. Deductions, follow-through and method-agnostic scoring are **not** modeled this cycle; their fallback is a functional one (verifier instruction + teacher override). No other invariant, the verdict vocabulary beyond one new verdict type, or the approval gate beyond one new bounds rule, changes.
6. **The one thing that is not frozen and must not be deferred:** the seam. `subject` (or the profile derived from it) must flow end to end after this cycle. Retrofitting it later means reprocessing history.
7. **Adversarial self-review** is part of the phase-gate report.

---

## 2. The problem (Deutsch form — short)

**Data.** CLAUDE.md §3.3 asserts subject-agnosticism. The eval suite's only profile is `JAVA_BAGRUT`; its critical-token metrics are code metrics; the corrector's safe tier is C# keywords; GT conventions assume code + Hebrew comments; the transcription contract is "verbatim text" with unwritten rendering conventions; all ratified GT is one CS exam.

**Theory under criticism.** "Adding a subject = new prompts + new UX panels." The data above says this was never tested and CS assumptions live in the instrument, the corrector, the conventions, and — from the public formats — provably the ontology: English writing rubrics are band-based, which the additive tree cannot express (INV-2/INV-3 fail); Math marking schemes are step-additive with deduction and follow-through notes, which the additive tree expresses partially. The first is fixed this cycle (D-3); the second falls back to a functional path (D-4).

**Reframe 1.** "Subject" is the wrong primitive. What varies is **modality of ink** — prose, code, math notation, figures — and **grading semantics** — additive, band, deduction, follow-through, method-agnostic. A subject is a bundle. Design against the bundle; Physics later is then free. Criticize this; replace it if you find a harder-to-vary framing.

**Reframe 2.** Modality-aware ≠ spec-aware. P1 may be told "this page contains math notation; use protocol X." P1 may never be told the expected answers. Anti-contamination is preserved. Any proposal giving P1 rubric content is rejected on sight.

---

## 3. Phase A — Census (timebox ≤2h)

Output: `## A. Leakage ledger` — `path:line | what | category | severity | subject(s) | notes`.
Categories: PROMPT · INSTRUMENT · ONTOLOGY · CONTRACT · RENDER · DATA · CONFIG. Severity: BLOCKING · DEGRADED · COSMETIC.

- **A0. Fixture inventory — first, before anything else.** Confirm the expected layout: three English folders each with one rubric `.docx` + one typed-solution `.pdf`, one Math rubric `.docx`. For each rubric DOCX record: language, page count, one-line structural description (band table? step list with points? deduction notes?), and — since the English rubrics were *converted* to DOCX — whether the conversion preserved table structure or flattened bands into paragraphs (this decides whether A4's band-table extraction is tested at all). For each solution PDF confirm it is text-layer, not image (`PyMuPDF` text extraction non-empty). Check whether `tests/rubric_eval_suite/` existed before this drop (runner? conventions?) or is fixtures-only. Write `fixtures/MANIFEST.md` — provenance, format, subject, conversion status, and (after A5) shape classification. **The Math side is n=1.** Note that explicitly wherever a Math structural conclusion is drawn.
- **A1. Trace `subject` end to end.** Where it exists (`subject_matter.py`, `Rubric`, `GradedTest`, transcription rows, `GradingBatch`), where it is passed, where it is dropped. Text data-flow diagram of the full pipeline (rubric DOCX → extract → compile → PDF → P1 → P2 → gradable → plan → verify → price → draft → review → approve → S12 preview), each node PRESENT / ABSENT / IMPLICIT-CS. The ABSENT/IMPLICIT nodes are the seam work.
- **A2. Every prompt.** `docx_v3` three-step chain, `rubric_generator`, P1 (t1.2), P2, grader-v5 Plan and Verify (confirm the pricer has no prompt), any feedback/explanation/language-detection prompt, eval-suite prompts. Quote every subject-bearing token; classify needed-for-CS-only / modality-generic / dead. Record each governing `*_PROMPT_VERSION`.
- **A3. Implicit representation contracts.** From code and ratified GT, not docs: P1 output structure (page schema, `שאלה n` / `א.` markers, `[?]`, fences, line breaks); what each renderer depends on; how P2 builds content signatures (`spec_from_rubric_draft`); what the grader's `difflib` sliding-window quote validation assumes; what the scorer normalizer (NFC → lower → strip-all-whitespace) makes invisible. For each: survives English prose (paragraphs, misspellings, LTR-in-RTL)? Math notation (fractions, exponents, roots, matrices, Hebrew–LTR mixing)? Figures?
- **A4. Rubric ingestion — run it, don't read it.** Run the current ingestion path (`parser_render.py` → `docx_v3` extraction) on all four real rubric DOCX files. Additionally generate a DOCX with `pandoc` from Markdown containing `$\frac{x^2-1}{x-1}$`, an embedded image, and a 3-column band table (pandoc emits real OMML) and run it too. Report exactly what survives in each case: equations, images, tables, band structure, LTR runs.
- **A5. Ontology stress test — against all four real rubrics.** For each: attempt to express it in the current ontology; record exactly where it breaks (`path:line` of the invariant or validator that fires) and which shape features it has: band/level criteria, additive steps, deductions, follow-through notes, "any valid method" clauses, totals ≠ 100, criteria that are alternatives rather than parts. Then express it under the proposed D-3 extension and record what *still* does not fit. Tabulate: `rubric | shape features | breaks-today-at | fits-under-D-3? | residual`. This table is the evidence base for D-3, D-4/D-4b and C4. English is n=3, Math is n=1: enough to decide structure for English, barely enough to *illustrate* it for Math — say so, and pre-register the coverage predictions (§5) for both.
- **A6. Instrument.** Everything in `tests/transcription_eval_suit/` assuming code: `JAVA_BAGRUT`, critical-token regexes, `case_insensitive_keywords`, abbreviations, corrector keyword targets, the normalizer, `GT_CONVENTIONS.md` v1.1, fixture layout, `FLAG_TRUST_MIN_FIXTURES`. Grading eval: `PLAYBOOK §R` buckets, `GT_AUDIT.md`, PL-rulings — which are CS-specific.
- **A7. Frontend.** Every renderer of transcription, rubric (DocumentReview / `RubricEditor`), graded draft (`GradedTestReviewPanel`), S12 preview and dashboard. What is CS-specific and whether it sits in a shared component (§3.3 violation). Bidi handling. Math renderer present? (Expect none; report KaTeX dependency/bundle situation.) CS assumptions in `src/types/`.
- **A8. Grader-v5.** How `GradingPlan` compiles a criterion into checks; verdict vocabulary; pricer mapping. Where subject would enter as data. Confirm nothing here needs to change for the beta beyond prompt-fragment injection.

---

## 4. Phase B — Plan (then STOP for approval)

### C1. Required properties — plan rejected if any fails
- **P-1** No subject branch in core types, invariants, compilers, pipeline interfaces. §3.3 litmus test holds for a hypothetical Physics with zero core edits.
- **P-2** Subject/modality knowledge in exactly one place, injected as data.
- **P-3** P1 modality-aware, never spec-aware.
- **P-4** CS regression gate: transcription suite (`p1_only`, `p2_only`, `per_doc` on the five fixtures), the grading eval on the five ratified students, `pytest -q`, frontend type-check, Playwright journeys — all unchanged before and after each phase. Any delta on a CS number is a kill.
- **P-5** Scorer normalization for Math is **form-preserving, never value-preserving**: canonicalizing `\frac{a}{b}` ↔ `a/b` is allowed; simplifying `2x+3x` → `5x` is not. Written as a named convention in `GT_CONVENTIONS.md` v2.
- **P-6** Review-first where representation is lossy: figures route teacher and grader to the ink, never to a re-drawing.
- **P-7** No teacher-facing subject-availability or "unsupported for this subject" messaging. Rubric-shape signals (§4 C4) are telemetry. Ordinary annotations (INV failures, illegible `[?]` spans, low-confidence transcription) apply to every subject exactly as they do to CS, on the single `annotations` surface (ANN-1).
- **P-8** Every English/Math-specific choice ships with a pre-registered prediction and kill criterion in `PREDICTIONS.md`.

### C2. Starting conjecture — criticize, do not adopt
One typed `SubjectProfile`: enabled modalities `{prose, code, math_notation, figure}`; notation protocol per modality; rubric-ingestion protocol; grading-semantics capabilities (this cycle: `{additive, level_select}`; `deduction`, `follow_through`, `method_agnostic` exist in the enum only so telemetry has a vocabulary); scorer profile (critical-token classes, normalizer rules, corrector policy — `off` for English and Math); renderer capabilities. Stored where A1 found `subject`; flows through every ABSENT node A1 found. Criticize: one concept or four? Leaks into `ontology_types.py`? Physics free? Eval profile inside or beside it?

### C3. Decisions
**DECIDE-NOW (Noam rules today; give options + recommendation):**
- **D-1 Math notation protocol.** Recommend: LaTeX subset with an explicit allow-list grammar (fractions, powers, roots, subscripts, Greek, standard operators/relations, `\begin{cases}`/matrices, `\overline`/`\vec` — enumerate; forbid everything else). Must render in KaTeX, diff under P-5, and pass quote validation as grader evidence (check whether backslashes/braces survive `difflib` windows — A3).
- **D-2 Figures.** Recommend (b): structured description block (figure type, axes/labels, marked points, relations the student wrote) **plus** a bounding-box reference into the source page image; grader and reviewer see the crop. Reject (a) SVG/TikZ re-drawing (unmeasurable, grader consumes fiction). State the invariant question: the `TranscriptionContract` carries a reference into the immutable GCS source — grader still consumes only an approved Contract. Flag if you disagree.
- **D-7 Sequencing within the day.** Recommend: seam → prose modality (English) → math notation → figures → rubric OMML → scorer profiles → renderers, each behind P-4. Give speed-of-light hours per step and name the critical-path item.
- **D-9 Crossed-out ink for Math.** Recommend: omitted, same as CS convention v1.1. Noam rules.
- **D-10 Where `subject` becomes required** and what happens to existing CS rows (backfill to `cs`; migration numbered 011).
- **D-11 English prose contract.** Paragraph breaks are gradeable structure; P1 preserves them as blank lines; the P2 join preserves them; the scorer profile adds a paragraph-count fidelity metric (diagnostic this cycle, gate later).
- **D-3 Level criteria (reopens §14 — state the original reasoning next to your recommendation; ground every claim in the A5 table, not in the public-format assumption).** Recommended design, to criticize: `Criterion.levels: Optional[List[Level]]`, `Level{label, points: Decimal, descriptor}`, mutually exclusive with `sub_criteria` (extend the StructureExclusivity validator). New invariant **INV-5 LevelPointsBound**: `max(level.points) == criterion.points`, level points strictly monotone, ≥2 levels; INV-2/INV-3 unchanged for non-leveled criteria; INV-3 vacuous for leveled ones. Extraction: the V3 pipeline extracts levels from band tables (same rule as SubCriterion — extracted, never generated in code). Rubric gate: `RubricEditor` renders levels as an editable ordered list; the client validator mirrors INV-5. Grader-v5: the Plan compiles a leveled criterion into exactly one **level-select check**; the verifier emits `selected_level` + verbatim evidence, never points; the pricer maps level → points from the plan's table. Approval gate: awarded for a leveled terminal ∈ `{level.points}` (a new bounds rule, not a point-sum rule — CLAUDE.md §5's warning about re-firing sums on awarded points still holds). Teacher override on a leveled terminal selects a level, not a number. Migration 011; existing CS contracts unaffected (`levels` absent ⇒ current behavior byte-for-byte). Alternatives to state and reject with reasons: (i) bands as prose in `description` compiled by the Plan (stringly-typed, Hickey violation, lossy to migrate later); (ii) each band as a SubCriterion (breaks INV-3 semantics — levels are exclusive, not additive).
- **D-4 Verifier/pricer for Math semantics not yet modeled.** Follow-through and alternative methods are handled by *instruction* in the Math verifier fragment ("judge each step as written, consistent with the student's own prior values; never re-solve or simplify") and by teacher override; deductions are teacher override. These are functional paths with no teacher-facing notice. State explicitly that this is instruction, not new semantics, and pre-register how often override will be needed (§5).

**DEFERRED (need data; beta uses a functional fallback, silently):**
- **D-4b Structural deduction / follow-through / method-agnostic modeling** in the ontology and pricer. Fallback: D-4 above.
- **D-5 / D-6 Gate thresholds** for Math and English scorer profiles. Fallback: profiles exist, metrics reported, gate = CS gate minus the code-token terms, labeled UNCALIBRATED in `results.json`.
- **D-8 Rubric input formats beyond DOCX.** All four fixtures are DOCX, but note *why*: Noam converted the English ones by hand from the ministry's PDFs. A teacher will not. The beta is DOCX-only (fallback: reject non-DOCX at upload with a plain, non-subject-specific message — the same message a CS teacher gets today); text-PDF ingestion via PyMuPDF into the same V3 chain is the first post-beta item and should be estimated in the plan. Do not build it this cycle unless the rest of C5 finishes early.

### C4. Shape telemetry (replaces A5 this cycle) — internal only
A deterministic post-extraction classifier that tags rubric shape as `additive | leveled | mixed | deduction_suspected | method_agnostic_suspected` from structural signals (band tables → levels; negative point values; "deduct/הורד/הפחת"; "any valid method/כל דרך נכונה"). It writes to logs/telemetry (and a Draft-side diagnostic field if one exists) — **never** to teacher-facing annotations, never blocking. Purpose: when the real dataset lands, you know how often deductions and method-agnostic clauses appeared and how often teachers overrode on them. This is the calibration data for D-4b.

### C5. Phases (each: goal, files from the ledger, failing tests first, metric, kill = any P-4 delta)
0. **Regression lock.** Run and record the full CS gate as `RUNLOG` baseline. Nothing before this.
1. **Seam.** `SubjectProfile`, subject flows through every ABSENT node, CS backfill (migration 011), CS profile reproduces current behavior byte-for-byte (prompts assembled from profile must equal current prompt text — assert it in a test).
2. **Level criteria (D-3).** Types + INV-5 + StructureExclusivity extension + extraction of band tables + `RubricEditor` levels UI + Plan level-select check + verifier `selected_level` + pricer table + approval bounds rule + leveled override in `GradedTestReviewPanel`. Tests: all three real English rubrics extract and compile (pinned as regression fixtures in `rubric_eval_suite` with the compiled Contract JSON committed as the expected output — an extraction regression suite, keyed by extraction `prompt_version`); the one Math rubric extracts and compiles additively; INV-5 failing cases; pricer table; approval rejects a non-level award. **This is the critical-path item — plan it first, get it approved first.**
3. **Prose modality (English).** P1/P2 paragraph preservation, corrector `off`, English scorer profile, LTR-in-RTL rendering.
4. **Math notation.** D-1 grammar, P1 fragment ("transcribe as written; never solve, simplify, or correct"), KaTeX rendering in every surface from A7, Math scorer profile with form-preserving canonicalizer, `GT_CONVENTIONS.md` v2 section.
5. **Figures.** D-2 description schema + ink-region reference in `TranscriptionDraft`/`Contract`; crop rendering at review; grader receives crop for scopes with figures.
6. **Rubric ingestion.** OMML→LaTeX in `parser_render.py`; images passed to extraction; shape telemetry (C4); DocumentReview renders LaTeX and levels.
7. **Smoke gate** (§6 fixtures), then phase-gate report.

### C6. Risk register — top 10, each with detection signal and reversal path
Must include: P1 solving instead of transcribing; OMML silently dropped; bidi corruption; scorer misreading notation variance as misreads (and someone loosening the gate in response); figure description diverging from ink; `subject` leaking into `ontology_types.py` "just for now"; CS regression via prompt assembly drift; a band table extracted as additive sub-criteria instead of levels (INV-3 fires, or worse, sums by coincidence and grades nonsense); level-select verdicts drifting toward the middle band (the CS "shaving" analogue — pre-register it).

**After writing C1–C6: STOP. Wait for approval. Then implement in C5 order.**

---

## 5. Pre-registration (`PREDICTIONS.md`) — written before implementation
For each of: P1 math fidelity, P1 solving rate, OMML survival, paragraph fidelity, shape-telemetry precision/recall on real rubrics, English misspelling preservation, D-3 coverage ("≥X% of the next 20 real English rubrics fit the levels extension with zero residual"), and the **model-solution ceiling check** ("each of the three English model solutions, typed and fed through transcription-bypass as a perfect answer, receives the top level on every leveled criterion in ≥k/5 repeats; any criterion below top level on ≥3/5 repeats is a plan-compile or verifier defect, not a data problem") — a prediction with a number, a metric, and a kill criterion. These are what the incoming dataset will test. A prediction without a number is not a prediction.

---

## 6. Smoke fixtures (required for Phase 6; not "real data" — say so in every artifact)
Real rubrics (already in `rubric_eval_suite/fixtures/`): three English rubric DOCX + typed-solution PDF pairs (D-3 extraction and INV-5 inputs; the solutions double as ceiling-check inputs, §5 — extract their text with PyMuPDF and feed it through a transcription-bypass path as a typed answer) and one Math rubric DOCX (additive extraction + C4 telemetry input). Derived synthetic essays: from each English model solution produce two perturbed variants — one with five injected misspellings and one with a merged paragraph — as typed inputs for the English grading smoke; label them SYNTHETIC-DERIVED in the manifest, never as student work. Founder-authored tonight: one handwritten Math page (a stacked fraction, an exponent, a sketched graph with a labeled extremum, one deliberate arithmetic error, one crossed-out attempt); one handwritten English paragraph with three misspellings and two paragraph breaks; one Math rubric written in Word with the equation editor. Phone-scanned. Smoke gate passes when: all three real English rubrics extract into leveled criteria, compile, render as levels in the editor, and each model solution plus its perturbed variants get a level verdict with evidence per criterion (ceiling check per §5); the real Math rubric extracts additively and compiles; OMML survives extraction and renders; P1 emits valid D-1 LaTeX that renders; the arithmetic error is transcribed *as written*; the crossed-out attempt is omitted; paragraphs survive P2; misspellings survive P1; the sketch produces a description + crop visible at review. n=1 per subject proves plumbing, not accuracy — label it so.

---

## 7. Deliverables
1. `docs/MULTISUBJECT_PLAN.md` — Summary (≤200 words: the three things that will hurt) · A0 inventory · A ledger + A1 diagram · A5 shape table · C1–C6 · Open decisions (DECIDE-NOW / DEFERRED) · Questions for Noam (only those that block) · Parking lot · Files read.
1b. `backend/tests/rubric_eval_suite/fixtures/MANIFEST.md` and the pinned expected-Contract JSON per rubric (Phase 2). The manifest records that the English DOCX files are hand-converted from ministry PDFs — the conversion is part of the fixture's provenance.
2. `PREDICTIONS.md` entries (§5).
3. `GT_CONVENTIONS.md` v2 (prose + math_notation + figure sections; CS section unchanged).
4. Phase-gate report: per phase, P-4 before/after numbers, tests added, adversarial self-review (≥3 objections, each resolved or left standing and labeled), and an explicit **"What this beta cannot claim"** section.

---

## 8. Do NOT
- Skip the census or the plan-approval stop because of the deadline.
- Touch `ontology_types.py`, the verdict vocabulary, or the approval gate beyond exactly what D-3 specifies — and do not do D-3 without an approved plan.
- Show any teacher-facing "not supported for Math/English" text, banner, or annotation. If a path would need one, the path is not done.
- Loosen any gate or tolerance so a subject "fits."
- Propose a drawing language for figures.
- Give P1 rubric or expected-answer content under any framing.
- Claim subject-agnosticism from CLAUDE.md; claim it from `path:line`.
- Let any CS number move. Any delta is a kill, not a rounding.
- Write anything — code comment, annotation copy, doc — implying English/Math accuracy is known.
- Call a model solution "ground truth," or use it to compute an accuracy number. It is a ceiling check on plumbing.
