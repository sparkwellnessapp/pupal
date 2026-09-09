# ALPHA_BACKLOG — what the multi-subject beta deliberately did not build

Governs: `vivi-multisubject-execution-plan.md` (Noam's rulings, 2026-09-08). Every gap below was a
**decision**, not an oversight: the beta was a 7.5-hour box, and each of these was ruled out of it
with a reason. This file is the index; the work itself is marked at the exact code sites with a
one-line `ALPHA-GAP A-n (D-x): …` note, so `grep` is a work list rather than a label.

```
grep -rn "ALPHA-GAP" backend/app backend/migrations backend/tests frontend/src
```

**47 notes**, one line each, at the site the work must start. The full index is at the bottom of this file.

---

## The gaps

| id | ruling | what beta does | what alpha must build | first site to open |
|---|---|---|---|---|
| **A-1** | D-3 (i) | A band ladder is FLATTENED: one criterion at the top band, the bands quoted verbatim in its description. The plan compiler keeps it whole (C8-lite). | Discrete levels end to end — a `level_select` check kind, its pricing, its validator arm, a band picker in the review UI, and the selected band frozen into the contract. | `plan_schemas.py:36` |
| **A-2** | D-1 | Mathematics is LINEAR text: `^`, `(num)/(den)`, `sqrt(...)`, `\|x\|`. OMML renders as its raw `m:t` text. The editor is a monospace `dir` island. | The LaTeX grammar: an OMML tree walk, a KaTeX render path, a `math` answer mode, and the v2 GT conventions **written before any Math ground truth is authored**. | `parser_render.py:320` |
| **A-3** | D-13 | `rescale_to_exam` — grid-snapped shares (k=3 → 33.5/33.25/33.25), largest remainder beneath, teacher inconsistencies preserved and flagged. | Real normalization: per-question scale as a first-class idea, the cap rule ("answer any, ≤ 100"), and the chapter minimum the beta drops. This whole file retires. | `rescale_to_exam.py:3` |
| **A-4** | D-2 | A figure is one `[איור: …]` line at its position. Nothing carries a page reference downstream. | Page references through transcription → contract → gradable → the grader message, so a figure scope can show the grader (and the teacher) the crop it is judging. | `transcription.py:124` |
| **A-5** | C4 | No rubric-shape telemetry after the render stage. | `rubric_shape` telemetry on the job row — how many questions, how deep, how many criteria, which render stage — so the next subject is chosen from data. | `rubric_extraction_runner.py:162` |
| **A-6** | D-8 | EVERY PDF is rasterized and read as images, even when it has a perfectly good text layer. | The text-layer fast path: PyMuPDF text → the deterministic renderer, with the image stage as the fallback. Cheaper and lossless where it applies. | `image_render.py:14` |
| **A-7** | D-11 | The transcription eval suite has ONE scorer profile and it is CS (`java_bagrut`). | A scorer profile per subject, BESIDE the instrument — never inside it. §17.7 forbids answering a grading question with an instrument change. | `profiles.py:26` |
| **A-8** | — | P2 segmentation uses the CS base wording for every subject; the seam exists but is inert. The v3 rollback grader prompt is CS-only. | P2 worded per modality, and a subject-aware v3 prompt if v3 is still the rollback target by then. | `two_phase/prompts.py:331` |
| **A-9** | D-4b, D-14(ii) | Deductions and follow-through are handled by INSTRUCTION in the verifier fragment, not modelled. Extraction takes one file. | Deductions as first-class objects with their own overrides, and a second upload (the answer key) merged by item number. | `graded_test_draft.py:59` |

---

## Why each was left out, in one line

* **A-1** — Discrete levels touch the ontology, the compiler, the pricer, the contract and three
  UI surfaces. Beta needed a band rubric to *work*, and the flattened path does that honestly;
  half-built levels would have been worse than none.
* **A-2** — LaTeX is a grammar, and a grammar decided in an afternoon becomes a convention nobody
  can change later. The GT conventions must precede the ground truth, not follow it.
* **A-3** — The grid snap is arithmetic in one pure function with known answers. Normalization is a
  product decision about what a teacher's "33⅓" means, and Noam ruled the simple thing for beta.
* **A-4** — Page references are plumbing through four schemas; the one-line figure description
  gets a Math answer transcribed and reviewable today.
* **A-5** — Telemetry the beta cannot act on is a distraction; it becomes valuable the moment
  subject number four is chosen.
* **A-6** — Two paths are harder to trust than one. Rasterizing everything is slower and costlier
  but has a single failure mode.
* **A-7** — Changing the ruler to make a number look better is the one move the eval contract
  forbids outright.
* **A-8** — Segmentation wording is a measurement problem, and there is no Math or English
  transcription eval to measure it against yet.
* **A-9** — Both are modelling work with no fixture behind them; the instruction line is testable
  today and the model is not.

---

## What is NOT in this backlog, and must not be added to it

The beta made three things **worse than they look**, and they belong in the phase-gate report's
"what this beta cannot claim" rather than here, because they are not deferred work — they are
properties of the shipped thing:

1. No Math or English **transcription** was measured. The P1 fragments are written blind.
2. No Math or English **grade** was measured against a teacher's marks. There is no ground truth.
3. The English and Math rubric paths are proven on **two documents each**, not on a corpus.

---

## The full index

Generated with the grep above, grouped by gap.

| gap | sites |
|---|---|
| **A-1** | `plan_schemas.py:36` · `plan_validator.py:222` · `pricer.py:213` · `verifier_prompt.py:244` · `plan_compiler/compile.py:614` · `graded_test_contract.py:65` · `graded_test_draft.py:58` · `subjects/profiles/english.py:9` · `tests/subjects/test_english_bands.py:5` · `RubricDocument.tsx:236` · `VerdictButton.tsx:22` · `lib/pricing.ts:105` · `types/rubric.ts:67` · `rubric-validation.ts:20` · ministry snapshot MANIFEST |
| **A-2** | `parser_render.py:320` · `parser_render.py:355` · `two_phase/prompts.py:129` · `subjects/profiles/mathematics.py:21` · `TRANSCRIPTION_GT_CONVENTIONS.md:5` · `TranscribedTextEditor.tsx:52` · `utils/answer-mode.ts:63` |
| **A-3** | `ontology_types.py:752` · `contract_compiler.py:414` · `rescale_to_exam.py:3` · `subjects/profiles/mathematics.py:10` |
| **A-4** | `grader_v5.py:164` · `gradable.py:167` · `transcription.py:124` · `gradable_compiler.py:281` · `subjects/profiles/mathematics.py:22` · `TranscriptionReviewSurface.tsx:328` |
| **A-5** | `rubric_extraction_runner.py:162` |
| **A-6** | `image_render.py:14` |
| **A-7** | `tests/transcription_eval_suit/profiles.py:26` · `critical_tokens.py:117` · `PREDICTIONS.md:17` |
| **A-8** | `grader/prompt.py:48` · `two_phase/pipeline.py:727` · `two_phase/pipeline.py:797` · `two_phase/prompts.py:331` · `two_phase/prompts.py:342` · `tests/subjects/test_registry.py:131` · `PREDICTIONS.md:16` |
| **A-9** | `rubric_extraction_jobs.py:150` · `graded_test_draft.py:59` · `subjects/profiles/mathematics.py:35` |

Line numbers drift; the grep does not. Run it.
