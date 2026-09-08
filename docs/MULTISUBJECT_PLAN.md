# Multi-subject Vivi (English + Math) — census, plan, and open decisions

**Status: PLAN — awaiting approval. No code has been written.** (CLAUDE.md §0.1; brief §4 "STOP".)
Written 2026-09-05 from a census run that day against the working tree at `perf/rubric-extraction-latency`
(HEAD `1c5db38`). **Revised 2026-09-08 after D-12 landed** (commits `a1a3273` → `52855ab`: PLAN COMPILER
v2, `grading_plans` migration 026, grader-v5 for every rubric, production revision `00040`); every
grader/plan citation below was re-read against HEAD `52855ab` today and the sections that D-12 changed are
marked **[revised 2026-09-08]**. Every `path:line` was read or executed in one of the two sessions; the
ledger contains no "likely". Census timebox: ~2h wall, six parallel read-only sweeps + four live runs
(parser render on all five DOCX, production extraction on four inputs, an OMML probe, two ministry PDFs
fetched); the 2026-09-08 re-check was ~30 min of reads, zero spend.

---

## 0. Summary — the three things that will hurt

1. **[revised 2026-09-08] The grading loop is now v5 for every rubric, but the grader still has no
   subject seam and its prompt package is pinned byte-for-byte.** D-12 is RESOLVED: PLAN COMPILER v2
   builds a plan per contract hash at rubric compile (`app/api/v0/rubric_management.py:155,235,379` →
   `plan_store.kick_plan_build`), `grader_kind_for` returns v5 unless the rollback knob says v3
   (`app/services/grader_selection.py:33-38`), and production runs it (`GRADER_ARCHITECTURE` unset =
   v5, `ANTHROPIC_API_KEY` from Secret Manager, verified on the service today). What remains for this
   beta: `subject` reaches neither the verifier (`grader_v5.py:139,157`; `build_grader`,
   `grader_selection.py:71-105`) nor the compiler; the verify SYSTEM prompt keeps v5.3's CS rules 3–5
   verbatim because v5.4 is defined as "v5.3 byte-for-byte + a user-message rule" (OD-W6,
   `verifier_prompt.py:49-54`); and the only accuracy number for the architecture (A3) is still owed
   with spend HELD (`TRACKER_plan_compiler_v2.md`). The S9 rollback panel still sends a `points_awarded`
   shape the backend refuses (`GradedTestReviewPanel.tsx:108` vs `graded_test_draft.py:57`), so the
   `v3` rollback loses overrides — a rollback fact, no longer the beta's critical path.
2. **The Math fixtures are ink — and they ARE rubrics.** *(Corrected 2026-09-08 per the execution
   plan §1: pages 7+ are the teacher's handwritten worked solution with per-step weights — the
   marking scheme — not a student's answers.)* A Math rubric is printed questions + a handwritten
   model solution whose steps carry point weights: a step-weighted additive rubric the ontology
   already represents. Both Math DOCX are page scans (0 text); `parser_render.py` yields
   `[IMAGE: …]` × N and extraction fails. Word equations are **silently dropped** even from a typed
   rubric (OMML probe). Neither is prompt work — both are render stages.
3. **The English fixtures contain no bands.** They are exam booklets plus answer keys (additive, one
   criterion per item). Band structure is real but comes from the ministry's public writing rubric,
   which explicitly allows in-between grades — so D-3's `awarded ∈ {level.points}` gate rule would
   refuse a value the source rubric permits. D-3 is still required for English writing; it is not
   evidenced by the drop, and it does nothing for Math.

---

## A0. Fixture inventory

Full manifest: `backend/tests/rubric_eval_suite/fixtures/MANIFEST.md`. The brief-vs-files deltas:

| brief says | files are | consequence |
|---|---|---|
| 3 English rubric+solution pairs | 2 distinct **exam booklets** (Module F 016584 ×2 identical, Module B 016384) + 3 **answer keys** (G 016582, F 016584, B 016384); folder 1 mis-paired (F booklet, G key) | no rubric DOCX exists for English; the booklet carries points per item, the key carries acceptable answers, the *writing* band descriptors are in neither |
| 1 Math rubric DOCX | **2** school-authored tests (3-unit 35173, 4-unit 35472), each as DOCX **and** PDF, all four image-only; pages 7+ are one student's handwritten answers with the teacher's percent marks | no text path ingests them; "מחוון" = the teacher's handwritten weights, not a criteria table |
| `rubric_eval_suite` possibly fixtures-only | full suite pre-existed (runner, scorer, 13-clause gate, 5 CS benchmarks, PREDICTIONS/RUNLOG) | the English/Math drop sits in subdirectories the runner's non-recursive glob (`runner.py:71-81`) never sees |
| "migration 011" for subject backfill | migration head is **026** (`026_grading_plans.sql`, applied in production 2026-09-06; `database.py:149-153`) | the subject column is migration **027** |

Solution PDFs: all three have a text layer (3,705 / 2,103 / 2,091 chars). Math PDFs: 0 chars.

---

## A. Leakage ledger (condensed; the six sweeps' full tables are in this session's transcript and can be appended on request)

Category · Severity · Subject(s). BLOCKING = a non-CS teacher cannot complete the loop; DEGRADED = completes with wrong/CS-shaped behaviour; COSMETIC = copy/dead code.

### A1 — `subject` end to end (ONTOLOGY / CONTRACT / CONFIG / DATA)

| path:line | what | cat | sev | subj |
|---|---|---|---|---|
| `backend/app/schemas/ontology_types.py:909-910` | `ExtractRubricResponse.subject = "computer_science"` default; `programming_language=None` | ONTOLOGY | BLOCKING | all non-CS — any draft saved without the key silently becomes CS |
| `ontology_types.py:1030-1031` | `GradingRubricContract.subject`, `programming_language` — present, **zero downstream consumers** | CONTRACT | COSMETIC | all |
| `ontology_types.py:1202-1283` | `SubjectProfile` dataclass, `SUBJECT_PROFILES` {computer_science, **math**, english}, `get_subject_profile`, `validate_rubric_against_profile` — **all dead, no caller in `app/`** | ONTOLOGY | DEGRADED | all — key `math` ≠ the seeded `subject_matters.code` `mathematics` (`migrations/001:61-83`) |
| `app/models/grading.py:14-67` | `Rubric` has **no subject column**; subject lives only inside `draft_json`/`contract_json` | DATA | BLOCKING | all — unfilterable, unjoinable |
| `app/api/v0/rubric_extraction_jobs.py:150,201` | `subject: str = Form("computer_science")` | CONFIG | BLOCKING | all non-CS |
| `app/services/rubric_extraction_runner.py:138`, `docx_v3/pipeline.py:92,555` | three more `"computer_science"` defaults; `:555` is inside the **LLM structured-output schema** | CONFIG | DEGRADED | all non-CS |
| `docx_v3/pipeline.py:619,1148` | `EXTRACTION_SYSTEM_PROMPT` is a static literal; `config.subject` never reaches the model | PROMPT | BLOCKING | all non-CS |
| `app/services/rubric_management_service.py:187` | `model_validate(draft)` — a missing `subject` key becomes CS, not an error | CONTRACT | BLOCKING | all non-CS |
| `app/services/gradable_compiler.py` (whole), `app/schemas/gradable.py:74-121,140-165` | `GradableTest`/`GradableScope` carry no subject — **the hard drop point** | CONTRACT | BLOCKING | all |
| `app/services/grading_runner.py:146,154-156` | `rubric_contract` is in hand; only `.numeric_policy` is forwarded to `build_grader` | CONTRACT | BLOCKING | all |
| `app/services/transcription/two_phase_engine.py:173-179`, `two_phase/parsing.py:216-256` | `transcribe_two_phase` has no subject; `spec_from_rubric_draft_data` reads only `questions` | CONTRACT | BLOCKING | all |
| `two_phase/parsing.py:94-103,112` | `_CSHARP_KW` frozenset is **LIVE** in `_extract_identifiers` for every exam | CONFIG | BLOCKING | all non-CS |
| `frontend/src/app/page.tsx:547`, `src/lib/api.ts:964` | zero-param `submitExtractionJob(file)`; `formData.append('subject', config.subject \|\| 'computer_science')` | CONFIG | BLOCKING | all non-CS — the teacher is never asked |
| `frontend/src/app/page.tsx:872-887,682-686` | the save `draft` omits `subject`/`programming_language`; `handleRubricMetadataChange` applies only `rubric_name` | CONTRACT | BLOCKING | all non-CS |
| `frontend/src/components/RubricMetadataEditor.tsx:100-123` | free-text subject box with placeholder `computer_science`; "שפת תכנות" field | RENDER | DEGRADED | all |
| `app/models/user.py:122-126`, `classroom.py:20,30` | `User.subject_matters`, `Class.subject_matter_id` — real subject data, **never joined to a rubric** | DATA | COSMETIC | all |

**A1 data-flow diagram** (P = subject present, A = absent, I = implicit-CS):

```
DOCX ─[1] upload  I  (page.tsx:547 → api.ts:964 'computer_science' → rubric_extraction_jobs.py:150)
     ─[2] runner  P/I (rubric_extraction_runner.py:138 carries the default)
     ─[3] docx_v3 P-as-data / A-in-prompt / I-in-text (pipeline.py:92,555,619,655,737,2065; question_type defaults to coding_task — observed on both English booklets)
     ─[4] review  I  (RubricEditor gets no subject prop, page.tsx:1512-1524; mirror emits rubric_name only, RubricDocument.tsx:953)
     ─[5] compile P  (contract_compiler.py:195-196 — last node that carries it; rubrics table has no column)
PDF  ─[6] batch   A  (batch_grading.py, GradingBatch, TranscriptionJob: no subject)
     ─[7] P1      A + I-mild (prompts.py:54-63 `While`/`Public`/`CW`/`CR`/`//`)
     ─[8] P2      A + I-heavy (prompts.py:150-291 "code UNITS", "class-wrapper", braces; parsing.py:94-103 C# keywords)
     ─[9] gradable A  ◀ HARD DROP (gradable.py:140-165)
     ─[10] plan compile (LIVE, PLAN COMPILER v2 — revised 2026-09-08) A but NEUTRAL BY CONSTRUCTION: compile.py is pure algebra; router/v1 + segmenter/v1 prompts carry no subject token (segment.py:103 "the rules do not depend on the subject"); `subject` appears nowhere in app/agents/plan_compiler/ (grep, 0 hits) — no leak, and no seam either
     ─[11] grader v5 (LIVE for every rubric since 2026-09-06) A + I (verifier_prompt.py:73-170 rules 3–5 "code… compiled… semicolon", pinned byte-for-byte to v5.3 by OD-W6; no subject parameter on PlanVerifyGrader grader_v5.py:109 or build_grader grader_selection.py:71-72); grader v3 = rollback only (prompt.py:63-73, same CS payload)
     ─[12] pricer  neutral (pricing.py:91-125 branches on kind/verdict/units only)
     ─[13] approve neutral (graded_test_contract_compiler.py: 0 hits)
     ─[14] returned exam neutral (returned_exam.py: 0 hits)
```

### A2 — prompts (PROMPT)

Governing versions: extraction `3.10.0-fixsource` (`pipeline.py:617`; ledger comment stops at 3.7.0 — 3.8–3.10 entries missing), Tier-B `1.1.0-fixsource` (`pedagogical_mistakes.py:331`), P1/P2 `t1.4-tables` (`two_phase/prompts.py:16`), strike-check `sc1.3`, identity **unversioned** (`identity.py:102`), grader v3 `grader-v3` (`prompt.py:29`), verify `grader-v5.4` (`verifier_prompt.py:54` — v5.3's SYSTEM prompt byte-for-byte plus the `counted` rule rendered in the USER message only when a counted check exists, OD-W6/OD-18 at `:49-52,63-66`), plan compiler `plan-compiler/v2.0` (`plan_compiler/compile.py:59`) + `router/v1` (`route.py:31`) + `segmenter/v1` (`segment.py:41`), feedback `feedback-v1`. **[revised 2026-09-08]** `plan-gen/v2` is retired (generator deleted in `808e012`; `plan_gen/prompt.py` survives only for the deduction regexes C1 re-scans, `compile.py:13`; `plan_gen/constitution.py` has no consumer outside its own package — grep). The pricer has no prompt (`pricer.py:2`). No language-detection prompt exists. `rubric_generator.py` (the router) contains no LLM call; the "AI rubric generator" prompts (`rubric_generator_service.py`, `rubric_service.py`, `vlm_rubric_extractor.py`) are **dead** (no importer). The legacy handwriting engine prompts (`handwriting_transcription_service.py:617-733`) are CS-shaped down to their `visual_grounding` schema (class/method/field) — but production runs `TRANSCRIPTION_ENGINE=two_phase` (verified on the Cloud Run service today), so they are out of scope.

| path:line | subject-bearing token (verbatim) | class |
|---|---|---|
| `docx_v3/pipeline.py:655` | "GIVEN CODE is context, not solution… (a class skeleton, a function to analyze)" | NEEDED-FOR-CS-ONLY |
| `pipeline.py:663,726,789,848` | "trace scaffold", "class interface", "trace table task" | NEEDED-FOR-CS-ONLY |
| `pipeline.py:669-697,735-750,778-782` | worked examples `SchoolHobbies`, "הגדרת לולאה על מערך TvShows", `//Q2 - ב - START`, "A closing brace } is NOT a stop signal" | NEEDED-FOR-CS-ONLY |
| `pipeline.py:635,723-725,794-842` | "נק'/נקודות", "ענו על 4 מתוך 6", "סעיף א", "פתרון:/תשובה:" | MODALITY-GENERIC |
| `two_phase/prompts.py:54-63` | "`While`, `Public`, `minuteS`", "`\\` instead of `//`", "NEVER expand `CW`/`CR`", "code, comments" | NEEDED-FOR-CS-ONLY |
| `prompts.py:64-69,76,93-95` | `שאלה {n}`, `א.`, `[?]`, "no markdown, no code fences" | MODALITY-GENERIC |
| `prompts.py:79-92` | pipe-grid rule with `arr[i]` example; "never reformat code that contains `\|`" | grid rule GENERIC; example CS |
| `prompts.py:150-291,343-403` | "assign the transcribed **code**", "distinct code UNITS (class, method, or block)", "class-wrapper lines", "count the braces", `Mobby`/`Hobby`, `LowestRateChannel` | NEEDED-FOR-CS-ONLY (the P2 job description itself) |
| `agents/grader/prompt.py:63-73` (v3, LIVE) | "never compiled… wrong algorithm… getter… loop bound… semicolon… garbled braces… what the code would do" | NEEDED-FOR-CS-ONLY |
| `agents/grader/verifier_prompt.py:81-108` (v5) | "VERIFY WHAT THE WRITTEN CODE DOES", "inverted guard writes the wrong cell", "חיפשתי השוואת null בגוף הלולאה", same rule-5 list | NEEDED-FOR-CS-ONLY; rule-5 strings pinned by `tests/agents/test_grader_v5_agent.py:222-223` |
| `agents/plan_compiler/route.py` (`router/v1`), `segment.py` (`segmenter/v1`) **[revised 2026-09-08]** | no subject-bearing token: a grep for code/class/method/loop/semicolon/brace/C#/java/לולאה/מחלקה/פעולה/קוד returns only Python identifiers; `segment.py:103` "EXAMPLES (different subjects on purpose — the rules do not depend on the subject)" | MODALITY-GENERIC — the two live wording prompts need no fragment |
| `agents/plan_gen/constitution.py:82-89` **[revised]** | PL-2 "קיצורי כתיב (cw, CR)" keyed `subject="computer_science"` | DEAD — `clauses_for` has no caller outside `plan_gen/` since the generator was retired; the v5.4 verify prompt inlines its own PL clauses (`verifier_prompt.py:43-48`) |
| `agents/grader/verifier_prompt.py:66-71` (`_COUNTED_RULE`) | a kind-specific instruction rendered in the USER message only when the plan has that kind | MODALITY-GENERIC — and the precedent for how a subject fragment can ride without forking the pinned system prompt (D-16) |
| `agents/feedback/prompt.py:21,29` | "ההגדרה תקינה / חסרה בדיקת טווח", "לא פתרון, לא קוד" | NEEDED-FOR-CS-ONLY (examples) |
| `two_phase/strike_check.py:59` | "an abandoned class or method" | NEEDED-FOR-CS-ONLY (one clause) |

P1 anti-contamination confirmed: `two_phase/pipeline.py:435-451` injects exactly `page_numbers`, packing mode, and page images; `exam_spec` is a parameter of `run_phase2` only (`:684-686`). P2 reads from the rubric draft only `questions[].{number, sub_questions[].{id, signature}, context}` (`parsing.py:243-253`) — never `example_solution`, criteria, or points.

### A3 — implicit representation contracts (CONTRACT / INSTRUMENT / RENDER)

| contract | path:line | prose? | math? | figures? |
|---|---|---|---|---|
| P1 page = one free string, `{"pages":[{page_number,text}]}`; empty page `""` | `prompts.py:98-120,95-96` | YES | YES (no linearization prescribed for fractions/roots/matrices — the `t1.4-tables` note `:23-44` documents exactly this "emergent convention" failure for tables) | **NO** — no field for a non-text region |
| markers `שאלה n` / `א.` on their own lines | `prompts.py:64-69`; parser `segmentation_check.py:43-49`, `_MAX_MARKER_LEN=12` `:40` | **NO** — "Question 1", "1.", "a)" silently parse to `None` (`:88`, skip `:129`) | two-line form composes; one-line "שאלה 1 סעיף א" (13 chars) rejected | n/a |
| P2 join: lines joined with a single `\n`; internal blank lines survive; edge blank lines stripped | `spans.py:203-206` | YES — paragraphs survive P2 | YES | NO (spans are line ranges) |
| draft answer = P2 text verbatim; `page_numbers` on the draft, **dropped from the contract** | `two_phase_engine.py:288-298`; `schemas/transcription.py:44-50,118-123` | YES | YES | NO — no figure/region/bbox/modality field anywhere; annotation types are a closed 7-literal set (`transcription.py:23-37`) |
| grader quote validation: `" ".join(x.lower().split())` both sides, `in` else sliding window ratio ≥ 0.85 | `agents/grader/validator.py:105-117,77-102` | YES (a short misspelled quote can fall under 0.85 → NOT_FOUND) | **YES unchanged** — no regex touches the quote; `\ { } ^ _` are ordinary chars; a quote spanning `\n\n` matches (whitespace collapsed) | NO — a figure has no text to quote |
| plan-quote grounding splits on `...` and drops fragments < 10 chars | `plan_validator.py:54-55,72` | YES | DEGRADED — a series ellipsis splits a math citation | n/a |
| scorer normalizer NFC → lower → **delete all whitespace** → (lenient) drop `[?]` | `app/services/transcription/normalize.py:59-63` | DEGRADED — paragraph breaks invisible | DEGRADED — `\frac{a}{b}` vs `a/b` costs ratio; braces are gated structural tokens | NO |
| `critical_tokens.py` regexes: `//[^\n]*\n`, `'…'` char literal, `ident(` calls; `JAVA_BAGRUT` only profile | `critical_tokens.py:88-136`; `profiles.py:24-28` | DEGRADED — prose `(` `)` enter the gated multiset | **NO** — `x'` opens a char literal and swallows to the next `'`; bare `+ - * /` deliberately excluded (`:49-51`) | NO |
| editor: `<textarea dir="ltr" font-mono whiteSpace:pre-wrap>`; per-line divs split on `\n`; flags by 1-based line via trimmed-exact `line_quote` match | `TranscribedTextEditor.tsx:77-83,114-127,148-155`; `review-flags.ts:20-22,36-38` | DEGRADED — Hebrew/English prose pinned LTR mono | DEGRADED — raw LaTeX as literal text; no highlighting library | NO |
| grader answer feed: whole `answer_text` under `STUDENT ANSWER`, no line numbers; leaf inherits parent answer | `gradable_compiler.py:108,127,179-181`; `prompt.py:213-225` | YES | YES | NO |

### A4 — rubric ingestion, RUN (RENDER / DATA)

| input | `parser_render` result | production extraction (gpt-5.6-terra/high, prompt 3.10.0-fixsource) |
|---|---|---|
| English F booklet (016584) | 14,814 chars, 7 tables, 44 `[IMAGE]` placeholders, no loss | OK 72 s, 26.6k in / 6.4k out. **q1 `question_type=coding_task`** (60 pts, 9 sub-questions, each ONE criterion whose description is the literal `"(6 points)"` — a criterion invented from the points label because a leaf must carry criteria for INV-2); **q2 writing 40 pts with 0 criteria** → INV-1 fires at compile (`contract_compiler.py:247-256`); `pedagogical_mistakes: point_sum_mismatch`; no `example_solution` anywhere (the key is a separate PDF, never fed) |
| English B booklet (016384) | 10,826 chars, 5 tables, 35 placeholders | OK 68 s. One q (100) with 10 sub-questions, each one `"(9 points)"` criterion; item 7 `"(2x9=18 points)"` as one criterion; `coding_task` again |
| Math 3-unit DOCX (10 JPEG pages) | **180 chars: `[IMAGE: Image n]` × 10, zero text** | **FAILS** 21 s: `RubricExtraction.questions.0.total_points: Input should be greater than 0` |
| Math 4-unit DOCX (16 JPEG pages) | 294 chars, zero text | not run (same shape) |
| OMML probe DOCX (fraction with superscript + PNG + 3-column band table) | **equation silently DROPPED** — "חשבו את הגבול של" ⟶ (nothing) ⟶ "כאשר x שואף ל-1."; image → `[IMAGE: Picture 1]`; band table survives as a 4×3 markdown table | OK 8 s. The band table became **3 additive criteria** `תוכן: מלא / חלקי / חסר: 10 / 5 / 0` (10), `ארגון…` (6), `שפה…` (4) — **sums by coincidence** (max column = criterion points) and the band semantics are flattened into the description string. `rubric_mismatch` WARNING "סכום … 20 במקום 100" (a hardcoded 100 expectation) |

Pandoc is not installed; the OMML DOCX was hand-built with python-docx + raw `<m:oMath>` (real OMML, same XML Word emits). `parser_render.py` (767 lines) never visits the `m:` namespace — the drop is by omission, not by a bug in a branch.

### A6 — instrument (INSTRUMENT / DATA / CONFIG)

| path:line | what | sev |
|---|---|---|
| `tests/transcription_eval_suit/critical_tokens.py:88-114` | `JAVA_BAGRUT`: 17 operators, `; { } ( ) [ ]` structural, `CW`/`CR`, 27 C# keywords | BLOCKING for any non-CS gate |
| `critical_tokens.py:119-153` | comment/string/char/call regexes are **module-level, not profile fields** — a new profile can swap vocabulary but not C-family syntax | BLOCKING |
| `profiles.py:24-28`; `exam_resolution.py:181-190,202-208` | one-entry registry; profile from per-fixture manifest key `"profile"` (no fixture sets it) else `DEFAULT_PROFILE` | DEGRADED — the seam exists |
| `two_phase/pipeline.py:101-161` (`PipelineConfig`) and all 9 `configs/*.json` | **no** subject/profile/modality field; `correction_policy` default `"off"` | BLOCKING for profile selection at run level |
| `scoring.py:49,139-176`; `runner.py:73,78,79` | gate 0.98 / =1.0 recalls / abbreviations empty; cost ≤ $0.08; `FLAG_TRUST_MIN_FIXTURES=10` | — |
| `flag_metrics.py:19-21,145`; `app/services/transcription/flagging.py:58-62,151-177` | trust-gate `critical_recall` = code-kind labels; "Hebrew never appears in this domain's code" (`:161`) | BLOCKING for the (retired) reader layer |
| `TRANSCRIPTION_GT_CONVENTIONS.md:10-14` | the "locked v1.1 GT_CONVENTIONS.md" **does not exist**; this file is the 2026-08-11 reconstruction "to be ratified" | DEGRADED — v2 must be built on a reconstruction |
| `TRANSCRIPTION_GT_CONVENTIONS.md:301-360,487-491` | `[?]`-in-code, trace-table, `CW`/`CR` rules — all derived from the C# token set | CS-specific |
| `keys.py:27-43`; `ground_truth.py:36,40` | key `(int, str\|None)`, sub-ids canonicalised onto א..י only; question part must be an integer | DEGRADED (Bagrut structure, any subject) |
| `tests/grading_eval_suite/scoring.py:50-75` | quote fragments split on newline **and `;`** ("statement boundaries") | DEGRADED (C-family) |
| `GRADING_EVAL_PLAYBOOK.md §R.2:232-242`; `GRADING_GT_CONVENTIONS.md` | 8 buckets, all subject-neutral (one CS example); conventions C-1…C-5 subject-neutral | — |
| PL rulings: `plan_gen/constitution.py:39-95` | canonical text is subject-neutral except PL-2 (`:84-87`, CS-keyed); **but as USED in GT notes** (`benchmarks/gt/*.gt.json`, `E7_CLAUSE_PROPOSAL.md:36`) "PL-1" = identifier case/spelling and "PL-10" = missing semicolon/brace ink — CS in practice and not the constitution's own text | DEGRADED (vocabulary drift) |
| `tests/rubric_eval_suite/build_benchmarks.py:159,237,282,321,408`; all 5 benchmarks | `subject="computer_science", programming_language="csharp"` | DATA |
| `rubric_eval_suite/runner.py:222` | `ExtractionConfig(subject=config.get("subject","computer_science"))` — the only subject knob in any suite; no config sets it | CONFIG |
| `rubric_eval_suite/gates.py:25-79` | 13-clause conjunctive gate; `example_solution_fidelity ≥ 1.0` | — |

Five ratified grading GT students: `tests/grading_eval_suite/benchmarks/gt/{dan_basiuk,din_ezra,moran_aharon,omer_gelber,yonatan_basiuk}.gt.json`, one exam (`hobby_tvshow`), `validated_by: Noam`, 2026-08-26. A second exam (`bagrut_899371`, 7 students) is staged, unratified.

### A7 — frontend (RENDER / DATA)

| path:line | what | sev | shared? |
|---|---|---|---|
| `src/utils/answer-mode.ts:23,37-39` | `CODE_CHARS = /[A-Za-z0-9{}();=<>+\-*/[\]]/` — **any Latin letter or digit** makes an answer "code" → LTR mono island in the live S12 review (`grade-review/AnswerBlock.tsx:99-133`) | **BLOCKING** for English essays and every Math answer | SHARED |
| `src/utils/document-text.ts:41,44,62-64,85-97,112-125` | C#/Java/Python keyword table; `//` and `/* */` only; `isCodeLine` = ≥3 symbols from `[(){}\[\];=<>+\-*/%&\|]` → `2x + 3y = 12` is "code"; `looksLikeCode` ≥2 lines or ≥40% | DEGRADED (Math prose → CodeBlock in the rubric mirror) | SHARED |
| `batch-review/TranscribedTextEditor.tsx:77,82-83,114-127,148-155` | `font-mono`, `dir="ltr"`, `border-l-4` flag rail | DEGRADED (Hebrew/English prose pinned LTR mono) | SHARED |
| `batch-review/TranscribedAnswerView.tsx:49,55-60,68-71`; `batch/CleanPanel.tsx:179-181`; `ExampleSolutionEditor.tsx:65`; `MarkdownTextRenderer.tsx:127-137` | more unconditional mono/LTR | DEGRADED | SHARED |
| `RubricDocument.tsx:505` | `code_blocks[]` → `<CodeBlock>` unconditionally (CS-only wire field in the shared mirror) | DEGRADED | SHARED |
| `RubricDocument.tsx:717,953` | `onMetadataChange` typed with subject/programming_language, emits `rubric_name` only | DEGRADED | SHARED |
| `src/types/batch.ts:178` → `src/copy/batch.ts:330` | `code_lint: 'סוגריים לא מאוזנים'` in the shared batch vocabulary | COSMETIC | SHARED |
| `src/app/page.tsx:1261-1275`; `LanguageSelector.tsx:12-23,71-134`; `RubricMetadataEditor.tsx:115-123` | "שפת תכנות" selects (Java/Python/C++/C#/JS/Pseudocode) on the main wizard; `בחר`/`הקלד` masculine imperatives outside the `check:copy` gate | DEGRADED | shared surface |
| `PdfProcessingPage.tsx:26` | live progress copy "משייך כל קטע **קוד** לשאלה" | COSMETIC | SHARED |
| `package.json:18-38`, `next.config.js` | **no KaTeX/MathJax/remark/rehype**; no `$…$` handling anywhere; no plugin seam | — | global |
| `src/types/rubric.ts` | no `programming_language`, no `subject`, no `levels`; `sub_criteria` at `:67`; `code_blocks` at `:123` | — | SHARED |
| `grade-review/VerdictButton.tsx:17-24`; `utils/verdict-cycle.ts:35-43`; `lib/pricing.ts:70` | ✓ / ½ / ✗ verdict control, "NO numeric input anywhere in this module" — points derived client-side from verdicts | — (this IS the level-select seam) | SHARED |
| `GradedTestReviewPanel.tsx:99-113,108` **[revised 2026-09-08]** | S9 rollback panel: numeric override `step=0.25`, sends `points_awarded` — a shape `TeacherOverride` (`graded_test_draft.py:57`) refuses | DEGRADED — only reachable under `GRADER_ARCHITECTURE=v3` + `USE_GRADE_REVIEW_MODULE=false`; that rollback pair grades but cannot override | S9 only |
| `grade-review/GradeReviewSurface.tsx:54`; `utils/grade-review-model.ts:419` **[revised]** | "A draft with no checks (a pre-v5 grade) is REFUSED, not rendered" | consistent with v5-for-every-rubric; COSMETIC now. ⚠ the whole `src/components/grade-review/` module, `lib/pricing.ts` (`CheckKind` incl. `counted` at `:72`, `units_correct` at `:121`) and `utils/grade-review-*.ts` are **UNTRACKED in git** (working tree, 2026-09-08) — the frontend P-4 baseline must be taken on that tree or after it is committed | SHARED |
| `lib/onboarding.ts:99-103`; `onboarding/steps/SubjectsStep.tsx:100-118` | subjects offered `english / mathematics / computer_science`, labels from the API; stored per USER, never reaches a rubric | — | onboarding |
| `lib/flags.ts:10,46` | `USE_DOCUMENT_MIRROR = true`, `USE_GRADE_REVIEW_MODULE = true` | — | — |
| P-4 frontend gate | `npm test` (73 vitest files, node SSR), `npx tsc --noEmit`, `npm run check:copy` (scoped to 5 batch surfaces + grade-review + onboarding), `npm run test:e2e` (21 specs; bidi guards `batch-review-journeys.spec.ts:245`, `grade-review.spec.ts:106,135`) | — | — |

### A8 — grader-v5 (CONTRACT / PROMPT)

**[revised 2026-09-08 against HEAD `52855ab`]** Arithmetic is subject-neutral and needs no change: pricer `app/services/pricing.py:91-125` branches on `kind`×`verdict`×`units_correct` only; `CheckKind = required|tariff|note_only|counted` (`plan_schemas.py:36`, mirrored at `graded_test_draft.py:145` and `frontend/src/lib/pricing.ts:72`); verdict `met|partially_met|not_met` (`plan_schemas.py:130`) is still mirrored in seven Literals (`graded_test_draft.py:57,158`; `graded_test_contract.py:65-66`; `grader_v5.py` ordinal; `pricer.py`; `pricing.py`); the verifier never emits points (V10; `test_grader_v5_agent.py`); approval gate does not re-fire INV-1/2/3 (`graded_test_contract_compiler.py:9-11`); `score_with_selection` denominator is `contract.total_points` (`selection_scoring.py:120,148`).

**Selection and plans are now production paths.** `grader_kind_for` (`grader_selection.py:33-38`) returns v5 unless `GRADER_ARCHITECTURE=v3`; `build_grader(rubric_id, numeric_policy, gradable_test=None, *, plan, plan_wording_source)` (`:71-105`) validates the plan against the test then constructs `PlanVerifyGrader(plan, numeric_policy, llm=…, model_version=…, plan_wording_source=…)` (`:105-107`). The runner resolves the plan first: `grading_runner.py:175-183` → `plan_build_runner.resolve_plan_for_grade(rubric_id, contract_json)` (ready → use; live builder → wait ≤ `PLAN_WAIT_S`; else build in place). Plans live in `grading_plans` (migration 026), keyed by `plan_store.contract_sha256` — canonical contract JSON with `contract_version` blanked (`plan_store.py:46-53`) — so **any field added to the contract (`levels`, a required `subject`) changes the hash and rebuilds the plan automatically on the next compile; no plan migration is needed.** Builds are kicked at the three contract-writing endpoints (`rubric_management.py:155,235,379`) on their own queue (`cloud_tasks_service.py:206-215`).

**The compiler is where a leveled criterion must be handled.** `plan_compiler/stage0.py:70-75` `terminals_of` makes each criterion (or its sub-criteria) a terminal; `compile.py:553-600` `compile_terminal` runs C3 first as an **early-return kind** (`counted` → one `Slot(kind="counted", points=points, unit_count=n)`, deductions dropped with a flag, `routed=False`); C4–C7 then split prose into `required` slots. Validator V12 (`plan_validator.py:33-35,222-241`) pins the counted shape (only check on its terminal, `points == points_possible`, no tariff/group). The verifier reports `units_correct` (`plan_schemas.py:132-136`) and the pricer derives credit (`pricing.py:60-70,117-125`); the `Check` wire record carries `unit_count`/`units_correct` (`graded_test_draft.py:149-153`) so the client re-derives (`pricing.ts:119-121,175`). **`TeacherOverride` carries no `units_correct`** (`graded_test_draft.py:56-60`) — an override on a counted check is verdict-only today; the same gap would apply to a level override unless a field is added (D-3 below).

**Still absent:** a subject parameter anywhere on the verify path (`grader_v5.py:109-115` ctor, `:139` `SystemMessage(content=VERIFIER_SYSTEM_PROMPT)`, `:157` `build_verifier_message(scope, terminal_plans)`; `verifier_prompt.py:173` builder takes no subject). `Criterion` has no `levels` (`ontology_types.py:419-465`); `ScoringLevel` is a dangling docstring reference (`:235,673`). `plan_gen/generator.py` is gone; the plan-gen subject injection I cited on 2026-09-05 no longer exists. The frontend half of `counted` is uncommitted (see A7).

---

## A5. Ontology stress test — all five real artifacts + the public English writing rubric

| rubric | shape features | breaks-today-at | fits under D-3? | residual |
|---|---|---|---|---|
| **English F reading** (016584 Part I, 60) | additive; 9 items (6/8/7/7/5/8/6/5/8); acceptable answers with `OR` alternatives and bracketed optional stems in the key; "Any … from lines 13–17" | does not break; extractor invents `"(6 points)"` criteria because the key is not fed and a leaf needs criteria (INV-2 `contract_compiler.py:281-330`); `question_type=coding_task` | n/a (additive) | alternatives are prose in `example_solution` (the grader's `OR` handling is untested on prose); key must be ingested as `example_solution` per item (a second input, not modelled today) |
| **English F writing** (016584 Part II, 40) | no criteria in the drop → 0 direct criteria under 40 pts | **INV-1** `contract_compiler.py:247-256` at compile | **YES** under the public F/G rubric: 4 leveled criteria (C&O 8/5/2/0, Vocab 10/6/3/0, Lang 16/10/5/0, Mech 6/4/2/0 = 40); `max(level.points)==criterion.points` holds on all four | "Markers can give in-between grades e.g. 7 pts" (page 2 §1); length deductions by word count (page 2 §7–8: a **tariff** by a deterministic count); "zero for the entire task" gates (§3); the booklet's own "על כתיב שגוי יופחתו נקודות" (`render:198`) → `deduction_suspected` |
| **English B reading** (016384, 100) | additive; 10 items; item 7 "2×9=18" (two sub-answers); "Any two of the following"; version-free | does not break (same invented-criterion shape) | n/a | item 7 should be 2 sub-criteria of 9 — extractor produced one 18-pt criterion; multi-answer items = partial-credit substrate the key implies but does not state |
| **English G key** (016582, no booklet) | versions A/B with different item orders and one differing answer (item 6, 7) | no booklet → no points → not extractable | n/a | a rubric with per-version answer variants has no representation (`version` is not a concept) |
| **Math 3-unit** (35173, school) *(corrected 2026-09-08)* | **step-weighted additive**: the teacher's handwritten worked solution carries a weight per sub-question and per step as % of the question (e.g. Q1: 10/20/40/25…); 5 Q × 24 = 120 offered, **"answer any, capped at 100"**; Q3 has depth-2 items (א.1–3, ב.1–3); figures in questions | (a) ingestion: 0 text → `pipeline.py` fails; (b) **INV-4** `contract_compiler.py:409-420`: achievable 120 ≠ 100 and no `SelectionGroup` expresses a cap; (c) `NumericPolicy.precision=0.25` (`ontology_types.py:147`) cannot hold 10% of 24 = 2.4 | **NO** — nothing leveled here | cap rule (ruled D-13: represented as choose-4-of-5 at 25 each; the cap semantics proper are alpha A-3); percent weights need the grid-snap post-pass (`rescale_to_exam`) |
| **Math 4-unit** (35472, school) *(corrected)* | **step-weighted additive**: weights in the margin per sub-question (Q5: 10/10/7/39/9/15/10 = 100) and per step inline (5%, 3%, 15%); 2 chapters, 5 Q, answer **3 with ≥1 per chapter**, 33⅓ each; typeset math in question text (fractions, `ln`, superscripts, vectors), three printed graphs to choose among | (a) ingestion: 0 text; (b) INV-4: 3 × 33.33 = 99.99 vs 100 sits exactly at `sum_tolerance=0.01` (`contract_compiler.py:413` — fragile, not a fit); (c) the per-chapter minimum is inexpressible in `SelectionGroup` (`ontology_types.py:735-760`); (d) OMML in the question text would be dropped even if typed | **NO** | chapter minimum (alpha A-3); fractional shares → grid-snap 33.5/33.25×4 (D-13 ruling); figures in the *question*; percent weights → `rescale_to_exam` |

**Reading of the table** *(corrected 2026-09-08)*. English n=3 (2 booklets + 3 keys): reading parts fit today (with an invented-criterion artefact and a missing answer-key input); the writing part needs D-3 and the evidence for its shape is the ministry's **public** rubric, not the drop. Math n=2, one school: the rubrics are **step-weighted additive** — the shape the ontology already represents — and the blockers are ingestion (ink, OMML) and **selection/cap/fractional-point arithmetic**, none of which D-3 addresses; D-13's grid-snap ruling handles the arithmetic for the beta. The evidence is the teacher's marking scheme, n=2, one school. Both are provisional at n=2.

---

## B. Plan

### C1. Required properties — checked against this plan

| P | holds? | how |
|---|---|---|
| P-1 no subject branch in core | YES | `subject: str` becomes a *field* on `GradableTest` and a column on `rubrics`; no `if subject == …` anywhere in ontology/compilers/pipeline; Physics = a new profile module + prompts + (optionally) UX, zero core edits |
| P-2 one place, injected as data | YES | `app/subjects/` registry (§C2); every prompt is assembled from `(generic core, modality fragments)`; the eval scorer profile is a registry entry *beside* it keyed by the same string |
| P-3 P1 modality-aware, never spec-aware | YES | P1 gets the profile's `p1_fragment` (notation protocol, paragraph rule) and nothing from the rubric; `two_phase/pipeline.py:435-451` stays the only P1 assembly site and gains one string argument |
| P-4 CS gate unchanged | YES by construction — with one honest gap | prompt assembly for `computer_science` is asserted **byte-identical** to today's constants (sha256 pinned in a test) before any other subject exists; Phase 0 records the baselines. **[revised 2026-09-08]** The grading half of the CS gate is A3 (grader-v5.4 + compiled plans on the five ratified students), which has never run and is spend-HELD — until it runs, "any delta on a CS grading number" has no number to delta against; the compiler-only A0 (`tests/grading_eval_suite/test_compiled_plan_guard.py`, zero spend, byte-pinned 184/190) is the gate that exists today |
| P-5 form-preserving scorer | YES | `math_notation` canonicalizer: `\frac{a}{b}`↔`a/b`, `\cdot`↔`*`, `\times`↔`*`, `^{2}`↔`^2`, `\left( \right)`↔`( )`; **no** algebraic simplification; named `MN-1` in GT_CONVENTIONS v2 |
| P-6 figures route to the ink | YES | D-2(b′): description block in text + **page reference** into the immutable GCS source; reviewer and grader see the page image, never a re-drawing |
| P-7 no subject-availability copy | YES | shape/cap/deduction signals are telemetry (`rubric_shape` log + job-result metadata); the only teacher-facing diagnostics are the existing INV annotations |
| P-8 pre-registered | YES | §5 table → the three PREDICTIONS.md files, committed in Phase 0 |

### C2. `SubjectProfile` — the conjecture, criticized

**Adopted framing (Reframe 1, hardened): a subject is a *key*; what varies is a bundle of *modalities* and *grading capabilities*.** Prompt fragments are keyed by **modality**, not by subject; a profile lists which modalities it enables and the assembler concatenates. CS = `{code, prose}`, English = `{prose}`, Math = `{math_notation, prose, figure}`. Physics later = `{math_notation, prose, figure}` with its own key and zero core edits — that is the litmus test passing on paper, and it is harder to vary than per-subject prompt blobs (a per-subject blob for Physics would duplicate Math's math fragment).

**One concept or four?** Four layers, **one key**, and the layers must not be one object:

| layer | lives in | why not in `ontology_types.py` |
|---|---|---|
| ontology-level `SubjectProfile` (valid `question_type`s, taxonomy key) | `ontology_types.py:1202-1253` — **already exists, dead**; keep, fix its key (`math`→`mathematics`), wire its validator | it IS ontology |
| prompt/modality profile (`modalities`, `p1_fragment`, `p2_fragment`, `extraction_fragment`, `verify_fragment`, `grading_capabilities`, `renderer_caps`) | **new** `app/subjects/registry.py` + `app/subjects/profiles/{computer_science,english,mathematics}.py` (frozen dataclasses of strings and enums) | prompt text in the ontology is the Hickey violation the brief warns about; the ontology must not import prompt fragments |
| scorer profile (`CriticalProfile` + normalizer rules + corrector policy) | `tests/transcription_eval_suit/profiles.py` registry gains `english_prose`, `math_notation`; selected by the fixture manifest `"profile"` key that already exists (`exam_resolution.py:181`) | the instrument stays **beside** the product (the ruler must not import the thing it measures beyond `normalize.py`, which it already does) |
| storage key | `rubrics.subject` column (migration 027) + the existing JSONB field | one durable key; downstream rows reach it through the rubric FK — no new columns on `graded_tests`/`transcriptions`/`grading_batches`/`grading_plans` (a plan is keyed by the contract hash, and the contract carries the subject) |

**Where it leaks if we are careless:** (i) `subject` on `GradableTest` is a string field, fine; a `modalities` list there would be the profile leaking into the contract — refuse it, the grader looks the profile up by key. (ii) The extraction structured-output schema (`pipeline.py:555`) carries a `subject` default; it must become required-with-no-default so the model cannot "choose" CS. (iii) The seeded `subject_matters.code` values (`computer_science`, `mathematics`, `english`) are the keys; the onboarding step already stores them per user — the upload step defaults the rubric's subject from the teacher's onboarding pick when she has exactly one, else asks.

**[revised 2026-09-08] Where a fragment RIDES on a pinned prompt — the OD-18 precedent.** v5.4 is defined as v5.3's system prompt byte-for-byte plus a kind-specific rule rendered in the per-scope USER message only when that kind is present (`verifier_prompt.py:49-52,63-71,186-195`), and the tracker records that stamping v5.3 on a message that carries the extra rule is a version fork needing a ruling. The same question arises for every subject fragment on every pinned prompt (extraction 3.10.0, P1/P2 t1.4, verify v5.4). Two placements: (a) **system-prompt assembly** — `verifier_system_prompt(profile)`; CS reproduces the constant byte-for-byte (sha-pinned), non-CS gets a generic core with rules 3–5 rewritten per modality; (b) **user-message rider** — the CS system prompt is sent to every subject unchanged and a fragment in the user message says what rules 3–5 mean for prose/math. (b) keeps one system prompt but sends English essays a rule that says "the code was never compiled"; (a) is the honest prompt and costs one version stamp per subject. **Recommendation: (a), with the stamp `<base>+<profile_key>` for non-CS and the base unchanged for CS** — surfaced as D-16 because it is the very fork OD-18 flagged.

### C3. Decisions

#### DECIDE-NOW

**D-12 — RESOLVED (landed 2026-09-05/06, owner instruction "pin now regardless"; `PLAN_production_wiring.md` rulings W-1..W-4).** What landed is option (a) in a stronger form than this plan proposed: a *compiled* plan per contract hash (pure algebra + two bounded wording stages with a substitution policy), append-only `grading_plans` (026), built at compile and in place at grade time, hidden from the teacher (W-3), v5 always (W-4). Residue this plan inherits, none of it blocking Phase 0:
- The verify path has no subject parameter (A8) — Phase 1 adds one kwarg through `build_grader` → `PlanVerifyGrader` → `verifier_system_prompt(profile)` / `build_verifier_message`.
- A3 (the grading accuracy number for this architecture) is owed and spend-HELD; A0 (compiler-only, zero spend) is byte-pinned. Phase 0's grading baseline is therefore A0 today and A3 once the hold lifts (§6 Q1).
- `TeacherOverride` has no `units_correct`; a level override needs `selected_level` (D-3 below) — one additive field, no second pricing path.
- The `counted` frontend half is uncommitted; Phase 2b builds on that tree.

**D-3 — level criteria (reopens §14; original reasoning restated).** §14 bans `ReductionRule`/`ScoringLevel`/`RuleKind` because they were *grading rules* — a rule engine deciding points from matched levels, replacing the agent's judgement with brittle scaffolding (the v1 grader, `app/grading_agent.py`, dead). `levels` here is *rubric structure*: what the teacher wrote in a band table, faithfully captured, graded by the same Plan/Verify/Price path. Evidence that it is structurally required: the OMML probe — today a band table is captured as additive criteria whose description flattens the bands, and it **sums by coincidence** (C6 risk realised on the first try). Design, as in the brief, with two amendments:

- `Criterion.levels: Optional[List[Level]]`, `Level{label: str, points: Decimal, descriptor: Optional[str]}`; XOR with `sub_criteria` (extend `validate_structure_exclusivity`, `ontology_types.py:1051`, and the `Criterion` model validator); **INV-5 LevelPointsBound**: `len(levels) ≥ 2`, `levels[0].points == criterion.points`, points strictly decreasing in written order, `levels[-1].points ≥ 0`. INV-2/INV-3 unchanged; INV-3 vacuous for leveled criteria. Extraction: `LevelExtraction` on `CriterionExtraction` (`pipeline.py:444`) + one prompt rule ("a row whose cells are alternative bands with descending points is ONE criterion with `levels`, never sub-criteria") — extracted, never generated, same rule as SubCriterion. Editor: `RubricDocument` renders levels as an ordered editable list; client INV-R5 mirrors INV-5; codec carries `levels` as a modeled key (round-trip suite extended). **Grader side [revised 2026-09-08 — follows the `counted` precedent exactly, so no verdict value is added and the seven mirrored Literals are untouched]:** PLAN COMPILER v2 gets rule **C8 leveled** as a second early-return kind beside C3 (`compile.py:553-600`): a terminal whose criterion carries `levels` → ONE `Slot(kind="level_select", points=criterion.points, levels=((label, points), …))`, `routed=False`, wording = the level descriptors verbatim (no router, no segmenter call — the teacher wrote the wording), any deduction phrase dropped with a flag `leveled_terminal_extra_slots`; `SlotKind`/`CheckKind` gain the fifth kind (`skeleton.py:23`, `plan_schemas.py:36`, `graded_test_draft.py:145`, `pricing.ts:72`); validator **V13** mirrors V12 (`plan_validator.py:222-241`): a `level_select` check is the only check on its terminal, `levels[0].points == points_possible`, strictly decreasing, `len ≥ 2`. Verifier: `_LEVEL_RULE` rendered in the USER message only when a leveled check exists (the OD-18 placement, `verifier_prompt.py:186-195`), `CheckVerdict.selected_level: Optional[str]` beside `units_correct` (`plan_schemas.py:132-136`); the verdict stays `met|partially_met|not_met` and is *derived* (top level → met, bottom → not_met, else partially_met), as `counted` derives it from the count. Pricer: `elif check.kind == "level_select": earned += level_points[selected_level]` beside the counted branch (`pricing.py:116-125`, mirrored in `pricer.py:213` and `pricing.ts:175`); a `partially_met` with no `selected_level` → no credit + flag, the `count_missing` analogue (`graded_test_draft.py:115`). `Check` wire record gains `levels` + `selected_level` (`graded_test_draft.py:149-153` pattern). **Teacher override:** `TeacherOverride.selected_level: Optional[str]` (additive; the approval gate's CW-3 check-set closed world already covers the check id) and a level picker beside `VerdictButton` in S12; the gate's existing bounds rule needs no change because the pricer can only emit a level's points. A `between_levels` numeric override does not exist and is DEFERRED (Amendment 1).
- **Amendment 1 — the approval bounds rule.** The brief's `awarded ∈ {level.points}` would refuse the ministry's own "in-between grades e.g. 7 pts" (public F/G rubric p.2 §1). Options: (i) discrete — the gate rule as specified; an in-between mark is impossible, the teacher picks the nearer level (pre-register the rate); (ii) anchors — levels bound the AI's choice; the gate keeps the existing `0 ≤ awarded ≤ possible` + grid rule (`graded_test_contract_compiler.py:251-255`, unchanged), and an in-between value needs a numeric override path that v5 deliberately lacks — so in practice (ii) collapses to (i) for the beta. **Recommendation: (i) for the beta, with the in-between rate pre-registered (§5 P-7)**; if the rate is material, the follow-up is a `between_levels` override, not a numeric one.
- **Amendment 2 — `question_type` for leveled criteria.** Extraction returned `coding_task` for English reading; the ontology-level profile validator (`ontology_types.py:1265`) must run at compile and the extraction prompt must receive the subject's valid types (a profile fragment) — otherwise `writing_task`/`reading_comprehension` never appear.
- Alternatives rejected, as in the brief: (i) bands as prose in `description` compiled by the Plan — stringly-typed, and the probe shows what it produces; (ii) each band a SubCriterion — INV-3 forces Σ = criterion points, but levels are exclusive, so a 4-band 8-pt criterion would need bands summing to 8 (8+5+2+0 = 15 ≠ 8 → refused, or "fixed" by inventing values — the exact FC violation).

**D-1 — Math notation protocol.** Recommend the brief's LaTeX subset, enumerated: `\frac{}{}`, `^{}`, `_{}`, `\sqrt{}`/`\sqrt[n]{}`, `\pm`, `\cdot`, `\times`, `\div`, `\le`, `\ge`, `\ne`, `\approx`, `\infty`, `\pi`, Greek letters, `\sin\cos\tan\ln\log`, `\int_{}^{}`, `\sum_{}^{}`, `\lim_{}`, `\to`, `\vec{}`, `\overline{}`, `\begin{cases}…\end{cases}`, `\begin{pmatrix}…\end{pmatrix}`, `\left( \right)`, `|x|`, degrees `^\circ`. **Forbidden:** `\text{}` (Hebrew goes outside math, never inside — bidi), `\displaystyle`, alignment environments, custom macros, `$` delimiters (math is delimited by `\( … \)` on the line, chosen because `$` appears in ordinary text and `\(` never does in Hebrew/English prose). Renders in KaTeX 0.16 (all listed commands are in KaTeX's supported set); diffs under P-5 via the `MN-1` canonicalizer; survives quote validation unchanged (A3: `validator.py` applies no regex). One pinned test: every grammar production renders in KaTeX without `\htmlClass`/error output.

**D-2 — Figures.** Recommend **(b′)**: P1 emits, at the figure's position in the ink, a description block `[איור: <type>; <axes/labels>; <marked points>; <relations the student wrote>]` (one line, verbatim labels), **plus a page reference** — not a bounding box. VLMs are unreliable at coordinates (`SpanPointer` docstring, `ontology_types.py:159-161`); `page_numbers` already exists on the draft answer (`transcription.py:49`) and only needs to survive into `TranscriptionContractAnswer` (`:118-123`). The grader receives the page image(s) for a scope whose answer contains a figure block (multimodal `HumanMessage`; the contract still names only the immutable GCS object). The invariant question stands as the brief states it: the contract carries a *reference* into the immutable source; the grader consumes only an approved contract. Reject (a) re-drawing. If the day runs out, the fallback is the description block alone with the reviewer's existing source-page view (`TranscriptionReviewSurface`) — degraded, pre-registered.

**D-7 — Sequencing (speed-of-light hours, one engineer, no interruptions) [revised 2026-09-08: 2a is gone].** Total ≈ 33 h; the day has ≤ 20. The cut line is explicit.

| # | phase | h | on critical path? |
|---|---|---|---|
| 0 | regression lock (backend `pytest -q` two-invocation, `check_goal.sh` k=5 ≈ $2, compiler A0 guard (zero spend) + A3 grading eval k=5 on the compiled hobby plan (≈ $6, **spend-HELD — needs the hold lifted**), rubric eval k=1 ≈ $1, `npm test` + `tsc` + `check:copy`, Playwright) | 1.5 (+ A3 wall) | yes |
| 1 | seam: registry + prompt assembly (extraction, P1, P2, verify, v3) with CS sha-pins; migration 027 + backfill; `GradableTest.subject`; one kwarg through `grading_runner.py:179` → `build_grader` → `PlanVerifyGrader` → `verifier_system_prompt`/`build_verifier_message`; upload-step subject picker; draft envelope carries subject; codegen | 5 | yes |
| 2b | D-3: types/INV-5/exclusivity/extraction/codec/editor; compiler C8 + V13 + `_LEVEL_RULE` + `selected_level` on `CheckVerdict`/`Check`/`TeacherOverride` + pricer branch (py + ts) + S12 level picker; pin 2 English booklets + the public-rubric writing part as fixtures | 8 | yes (English writing) |
| 2c | Math ingestion: OMML→LaTeX walker in `parser_render.py` (D-1 subset, else raw `m:t` text) + image-only render stage (`render_pages_to_markdown` over the existing P1 provider with a *rubric-read* prompt, chosen when rendered text < 200 chars and media ≥ 1) | 5 | yes (Math) |
| 3 | prose: P1/P2 prose fragments (paragraph = blank line, preserved through `spans.py:203`), `english_prose` scorer profile + `paragraph_count_fidelity` metric, editor `dir` from profile | 3 | English |
| 4 | math notation: P1 fragment ("transcribe as written; never solve, simplify, or correct"), KaTeX renderer (npm `katex`, one `MathText` component used by the transcription read-only view, `AnswerBlock`, `RubricDocument` prose), `math_notation` scorer profile + `MN-1`, GT_CONVENTIONS v2 | 5 | Math |
| 5 | figures D-2(b′) | 4 | **below the cut line**; fallback = description block only |
| 6 | shape telemetry (C4); mirror renders levels + LaTeX (mostly in 2b/4) | 2 | — |
| 7 | smoke gate + phase-gate report | 3 | yes |

Recommended order: 0 → 1 → 2b → 2c → 3 → 4 → 6 → 7, with 5 only if 2c finishes early. **Critical-path items: 2b (English writing) and 2c (any Math rubric at all).** Every leveled or subject-stamped contract gets a fresh plan for free through the contract-hash key — 2b needs no plan migration and no rebuild tooling.

**D-9 — Crossed-out ink for Math.** Recommend: omitted, as CS v1.1 (`TRANSCRIPTION_GT_CONVENTIONS.md:272`). Observed: the 3-unit student's Q5 has a magenta strike through three lines — by the *teacher's* pen, not the student's. Convention v2 must say "omit strikes by any pen" or "omit only the student's"; recommend **any pen** (a teacher's strike is not the student's answer either), pre-registered.

**D-10 — where `subject` becomes required.** `rubrics.subject TEXT NOT NULL DEFAULT 'computer_science'` (migration **027** — head is 026 since `026_grading_plans.sql`; idempotent, commit token, `EXPECTED_MIGRATIONS` bump), backfilled from `contract_json->>'subject'` (all six production rows are CS); **no DB CHECK** on the value set (a CHECK per new subject fails the Physics test) — validated at the API boundary by the registry (422 on unknown). Required on `POST /rubrics/extraction-jobs` submit (the Form default removed; the client sends the picked key). `ExtractRubricResponse.subject` keeps its default this cycle (removing it would 422 every stored draft on re-parse); the save path (`rubric_management_service.py:187`) writes the column from the draft and refuses a mismatch. `GradedTest`/`Transcription`/`GradingBatch` get no column.

**D-11 — English prose contract.** As the brief: paragraph break = one blank line; P1 fragment says so; P2 span join already preserves internal blank lines (`spans.py:203`); `TranscribedTextEditor` keeps `pre-wrap`; scorer profile adds `paragraph_count_fidelity` = |pred paragraphs − gold paragraphs| per answer (diagnostic only this cycle). Misspellings: the corrector is already `off` in production (`two_phase_engine.py:145`); the `english_prose` profile sets `correction_policy="off"` explicitly and has no keyword targets.

**D-4 — Math semantics not yet modelled.** Instruction, not semantics: the `mathematics` verify/v3 fragment says "judge each step as written, consistent with the student's own prior values; never re-solve, simplify, or correct; a correct method on a carried error is met for the method step". Deductions and follow-through are the teacher's override. Pre-registered: the override rate on Math terminals (§5 P-8).

**D-13 (new) — Math selection/cap semantics.** Both Math fixtures need what `SelectionGroup` cannot say (cap; per-chapter minimum; fractional per-question totals). **DEFERRED** (ontology change beyond D-3); beta fallback is functional and silent: the teacher declares the offered total (120) with no groups and the grade is shown out of 120; telemetry `cap_suspected`/`chapter_constraint_suspected` records each occurrence. Not a notice, not a banner.

**D-14 (new) — the English answer key as a second rubric input.** The key is a separate PDF. Options: (i) the teacher pastes the key into `example_solution` per item in the editor (works today, manual); (ii) accept an optional second file at upload and merge by item number (new). **Recommend (i) for the beta**, (ii) parked.

**D-15 (new) — `SUBJECT_PROFILES` key rename `math` → `mathematics`.** Trivial, dead code, aligns with the seeded `subject_matters.code`. Recommend yes.

**D-16 (new, 2026-09-08) — version stamping for subject-assembled prompts.** See C2's OD-18 paragraph. Recommend: system-prompt assembly per profile; CS stamps unchanged (`3.10.0-fixsource`, `t1.4-tables`, `grader-v5.4`, `grader-v3`) and sha-pinned to today's bytes; non-CS stamps `<base>+<profile_key>` (e.g. `grader-v5.4+english`), so `results.json`, `graded_tests.prompt_version` and the tracker can never confuse a CS number with a non-CS one. This is the ruling OD-18 asked for, generalised.

**D-17 (new, 2026-09-08) — the spend hold.** Phase 0's grading baseline is A3 (grader-v5.4 + Sonnet 5 + the compiled hobby plan, k=5, ≈ $6 per the tracker); it is owed for the architecture regardless of this beta and is spend-HELD. Options: (i) lift the hold for A3 now — Phase 0 then has a real CS grading number to delta against; (ii) keep the hold — Phase 0 records A0 (compiler-only, zero spend, already byte-pinned) as the grading baseline and the phase-gate report says the CS grading gate was structural, not measured. **Recommend (i).**

#### DEFERRED (functional fallback, silent)

- **D-4b** structural deduction / follow-through / method-agnostic — fallback D-4.
- **D-5 / D-6** Math and English gate thresholds — profiles exist, metrics reported, gate = CS gate minus code-token terms, `results.json` stamped `"gate_calibration": "UNCALIBRATED"`.
- **D-8** non-DOCX rubrics — beta is DOCX-only at upload; **note the image-only DOCX is the real Math format** (2c covers it); text-PDF ingestion is `render_pdf_to_markdown` via PyMuPDF into the same chain — est. 3 h, first post-beta item.
- **D-13** cap/chapter selection semantics; **D-14(ii)** key-file merge; the `between_levels` override.

### C4. Shape telemetry

`app/services/rubric_shape.py` — pure function `classify(ExtractRubricResponse, rendered_markdown) -> RubricShape{tags: set, signals: list}` with tags `additive | leveled | mixed | deduction_suspected | method_agnostic_suspected | cap_suspected | chapter_constraint_suspected | percent_weights_suspected`, from: `levels` present; any negative `points`; regexes `הורד|הפחת|יופחת|deduct|minus|−\s*\d+\s*נק`; `כל דרך נכונה|any valid method|בכל דרך`; `לא יעלה על|capped|סך .* לא יעלה`; `לפחות .* מכל פרק`; `\d+%` near sub-question labels. Written to the extraction job's result `metadata` (already a dict, `pipeline.py:2165`) and logged as `rubric_shape` with the rubric id — never into `annotations`, never blocking, never rendered. **[2026-09-08] The tags go in the log MESSAGE string, not in `extra=`:** this service's logging is `basicConfig` with no structured formatter, so `extra` fields are never rendered (CLAUDE.md §8, the Stage-D lesson) — a telemetry line nobody can query is the same as no telemetry. Precision/recall pre-registered on the seven artifacts (§5 P-5).

### C5. Phases — each: goal · files · failing tests first · metric · kill = any P-4 delta

0. **Regression lock [revised 2026-09-08].** Run and record in `RUNLOG.md` (transcription, grading, rubric suites) + `docs/MULTISUBJECT_RUNLOG.md`: `pytest --ignore=tests/transcription_eval_suit -q` and `pytest tests/transcription_eval_suit -q`; `bash tests/transcription_eval_suit/check_goal.sh` (k=5); grading: the compiler-only A0 guard (`tests/grading_eval_suite/test_compiled_plan_guard.py`, zero spend) always, and A3 — `python -m tests.grading_eval_suite.runner --config <v5 config with the compiled hobby plan> -k 5` — only if D-17 lifts the hold; `python -m tests.rubric_eval_suite.runner --config gpt-5.6-terra-high --repeats 1`; `npm test`, `npx tsc --noEmit`, `npm run check:copy`, `npm run test:e2e` — on the working tree as it stands (the grade-review module is untracked; record the tree's `git stash`-free state, do not commit someone else's in-flight work). Commit the §5 predictions to the three PREDICTIONS.md files. Nothing before this.
1. **Seam [revised].** Files: `app/subjects/{__init__,registry,profiles/*}.py`; `docx_v3/pipeline.py` (prompt assembly + `subject` required in the LLM schema + valid question types fragment); `two_phase/prompts.py` (`p1_system(profile)`, `p2_system_prompt(profile)`), `two_phase/pipeline.py:435,707,773` (one arg), `two_phase_engine.py:173` (subject param), `transcribe_one.py`/`transcription_job_runner.py` (read subject from the rubric row); `parsing.py:112` (identifier filter from the profile's keyword set — empty for prose/math); `agents/grader/prompt.py` (v3 builder), `verifier_prompt.py:73,173` (`verifier_system_prompt(profile)`, `build_verifier_message(scope, terminal_plans, profile)`), `grader_v5.py:109-115,139,157` (ctor kwarg + both call sites), `grader_selection.py:71-72,105-107` (`build_grader(..., subject=)`), `grading_runner.py:179-183` (pass `rubric_contract.subject`); `gradable.py` + `gradable_compiler.py` (`subject`); `migrations/027_rubrics_subject.sql` + `database.py:149-153` `EXPECTED_MIGRATIONS`; `api/v0/rubric_extraction_jobs.py:150` (required Form), `rubric_management_service.py:187` (column write); frontend: upload step subject picker (default from onboarding), `page.tsx:547,872-887,682-686`, `api.ts:964`, `gen:api`. The plan compiler needs nothing (A1 node [10]). Tests first: `tests/subjects/test_prompt_identity.py` — for `computer_science`, every assembled prompt sha256 == the pinned sha256 of today's constant (pin the constants' hashes **before** refactoring — including `VERIFIER_SYSTEM_PROMPT` at v5.4, whose byte-identity to v5.3 is itself a ruling); `test_registry_unknown_subject_422`; migration test in `test_schema_canon`; the non-CS stamp rule (D-16). Metric: all Phase-0 numbers byte-identical.
2b. **Level criteria (D-3) [revised].** Files: `ontology_types.py` (Level, `levels`, INV-5, exclusivity — the ONE ontology edit), `contract_compiler.py`, `docx_v3/pipeline.py` (`LevelExtraction`, `_build_criterion`, one prompt rule); compiler: `plan_compiler/skeleton.py:23-34` (`SlotKind` + `levels` on `Slot`), `compile.py:553-600` (C8 early return beside C3), `assemble.py` (level slot → check with `levels`), `segment.py`/`route.py` (skip leveled terminals); `plan_schemas.py:36,70,132-136` (`CheckKind`, `levels`, `selected_level`), `plan_validator.py:222-241` (V13 beside V12), `verifier_prompt.py:56-71,186-195` (`_KIND_HE` + `_LEVEL_RULE`, user-message only), `pricing.py:116-125` + `pricer.py:213` (branch), `graded_test_draft.py:56-60` (`TeacherOverride.selected_level`), `:115` (a `level_missing` annotation type beside `count_missing`), `:145-153` (`Check.levels`/`selected_level`), `graded_test_contract.py` (carry `selected_level`), `graded_test_contract_compiler.py` (no new rule needed — see D-3), `rubric_management.py::AnnotationSchema` untouched (no new `Annotation` field); frontend `types/rubric.ts`, `rubric-transform.ts` (`levels` modeled), `rubric-validation.ts` (INV-R5), `RubricDocument.tsx` (levels list), `grade-review/VerdictButton.tsx` + `CheckRow.tsx` (level picker) + `lib/pricing.ts:72,175` (`level_select` branch), `gen:api`. Tests first: INV-5 failing cases (1 level; non-monotone; top ≠ points; levels + sub_criteria), band-table extraction on the OMML probe → one leveled criterion (the coincidence-sum case becomes a failing test), C8 + V13 known-answers, pricer level table (py and ts, cross-pinned like `counted`), `partially_met` without `selected_level` → no credit, override with `selected_level` reprices, codec round-trip with levels, the two English booklets + the public writing rubric (as a DOCX authored from the PDF, labelled) compile → pinned Contract JSON in `rubric_eval_suite/benchmarks/`, keyed by `EXTRACTION_PROMPT_VERSION`; the A0 guard stays byte-identical on both CS exams (no leveled criteria there). Metric: CS benchmarks + A0 unchanged; English fixtures pass their pinned contracts.
2c. **Math ingestion.** Files: `parser_render.py` (OMML walker; `[IMAGE]` count + text length exposed on `RenderStats`), `services/docx_v3/image_render.py` (page images → markdown via the P1 provider, rubric-read prompt `rr1.0`, one call per page, deadline-aware), `rubric_extraction_runner.py` (render-stage choice), PDF path for image-only PDFs reuses the same stage. Tests first: OMML probe → `\(\frac{x^{2}-1}{x-1}\)` in the render; image-only DOCX → non-empty markdown containing "שאלה 1" (mocked provider); 3-unit fixture end-to-end with the real provider recorded once as a snapshot.
3. **Prose.** Files: `app/subjects/profiles/english.py` fragments; `tests/transcription_eval_suit/profiles.py` (`english_prose`), `scoring.py` (paragraph metric), `TranscribedTextEditor.tsx` (`dir` prop from profile, default unchanged). Tests first: fragment assembly; paragraph metric known-answer; `english_prose` profile has empty operator/structural sets and no abbreviations (gate reduces to ratio + coverage + paragraph diagnostic).
4. **Math notation.** Files: `profiles/mathematics.py`, `tests/transcription_eval_suit/{profiles,normalize_math}.py` (`MN-1`), `TRANSCRIPTION_GT_CONVENTIONS.md` v2 (prose + math_notation + figure sections; CS section byte-unchanged), frontend `katex` dep + `components/MathText.tsx` + call sites (`TranscribedAnswerView`, `AnswerBlock`, `DocumentText` Prose), `answer-mode.ts` (mode from profile: `prose` for english, `math` for mathematics; CS heuristic untouched). Tests first: every D-1 production renders; `MN-1` canonicalizer known-answers (form-preserving, never value-preserving — `2x+3x` ≠ `5x` pinned); e2e bidi test for a Hebrew line containing `\(x^2\)`.
5. **Figures** (below the cut line). Files: `transcription.py` (`page_numbers` on the contract answer), `gradable.py`/`gradable_compiler.py` (page refs per scope), `grader_v5.py` (multimodal message when a scope's answer has a figure block), `TranscriptionReviewSurface` (page chip on figure blocks). Tests first: contract carries page refs; the grader message contains the page image only for figure scopes.
6. **Telemetry + mirror.** `rubric_shape.py` + its known-answer tests on the seven artifacts.
7. **Smoke gate + report.** §6 fixtures; `docs/MULTISUBJECT_PHASE_GATE.md` with per-phase P-4 before/after, tests added, ≥3 adversarial objections, "What this beta cannot claim".

### C6. Risk register (top 10)

| # | risk | detection | reversal |
|---|---|---|---|
| 1 | P1 **solves** instead of transcribing (Math) | smoke page: the deliberate arithmetic error must appear as written; §5 P-2 | fragment revert (one string), `TRANSCRIPTION_PROMPT_VERSION` bump back |
| 2 | OMML silently dropped (already true today) | render test asserts the `\(…\)` token; `RenderStats.omml_seen` vs `omml_rendered` logged per job | none needed — today's behaviour is the failure |
| 3 | bidi corruption of `\(…\)` inside Hebrew lines | Playwright bounding-box test (the `rtl-bidi-code-comment-rendering` pattern) | `MathText` renders LTR-isolated; fallback to raw text island |
| 4 | scorer reads notation variance as misreads — and someone loosens the gate | `math_notation` profile results stamped UNCALIBRATED; §17.7 forbids touching `scoring.py` thresholds; `MN-1` is the only canonicalizer and is pinned | revert the profile; the CS profile is untouched |
| 5 | figure description diverges from ink | the crop/page is always beside the description in review; §5 P-9 | D-2 fallback (description only) |
| 6 | `subject` leaks into `ontology_types.py` "just for now" | grep guard test: `ontology_types.py` imports nothing from `app/subjects/`; no string `"english"`/`"mathematics"` outside `SUBJECT_PROFILES` | — |
| 7 | CS regression via prompt-assembly drift | sha256 pins on all five assembled CS prompts; Phase-0 numbers | any delta = revert the assembler |
| 8 | band table → additive sub-criteria that sum by coincidence (**observed today**) | the probe is a failing test until 2b lands; telemetry `leveled` vs `additive` on band-shaped tables | — |
| 9 | level-select verdicts drift to the middle band | §5 P-10 on the ceiling check; per-level histogram in eval `results.json` | verify fragment tweak, k≥5, one variable |
| 10 | **[revised 2026-09-08]** the CS grading gate has no measured number (A3 owed, spend held) and a non-CS fragment forks the v5.4 package silently | Phase-0 record says "A0 only"; `prompt_version` stamps without a `+<profile>` suffix on a non-CS grade (D-16 test) | D-17(i) lifts the hold; the stamp rule is a unit test; `GRADER_ARCHITECTURE=v3` remains the one-flip rollback (and loses overrides — A7) |

---

## 5. Pre-registration (to be committed to the PREDICTIONS.md files in Phase 0, in each file's existing entry format)

| id | claim | metric | number | kill |
|---|---|---|---|---|
| P-1 P1 math fidelity | founder's handwritten Math page under the `mathematics` P1 fragment | `doc_ratio_strict` vs a hand-authored raw GT under `MN-1` | ≥ 0.90 on ≥ 4/5 repeats | < 0.80 on ≥ 3/5 ⇒ the D-1 grammar or the fragment is wrong, not the page |
| P-2 P1 solving rate | the deliberate arithmetic error is transcribed as written | error present verbatim | 5/5 | any repeat that "corrects" it kills the fragment |
| P-3 OMML survival | Word-equation-editor rubric (founder's) | equations in source vs `\(…\)` tokens in render | 100% of `m:oMath` nodes render, ≥ 90% valid D-1 | any silent drop (count mismatch) kills 2c's walker |
| P-4 paragraph fidelity | founder's English paragraph (2 breaks) + 3 derived merged-paragraph variants | `paragraph_count_fidelity` | exact on ≥ 4/5 | off by ≥ 2 on any repeat ⇒ P2 join or fragment |
| P-5 shape telemetry | the seven artifacts | precision / recall of tags vs the A5 table | P ≥ 0.85, R ≥ 0.85 | either < 0.7 ⇒ the regexes, not the artifacts |
| P-6 misspelling preservation | 5 injected misspellings × 3 keys (typed) + 3 handwritten | misspellings surviving P1+P2 | 100% typed; ≥ 2/3 handwritten | any typed correction kills (corrector must be off) |
| P-7 D-3 coverage | next 20 real English writing rubrics | fit with zero residual | ≥ 80% (16/20) | < 60% ⇒ the extension is the wrong shape; also record the in-between-grade override rate — > 25% ⇒ Amendment-1(i) was wrong |
| P-8 Math override rate (D-4) | first 20 real Math graded tests | terminals overridden / terminals | ≤ 30% | > 50% ⇒ D-4b cannot stay deferred |
| P-9 figure description | founder's sketched graph | reviewer confirms the description matches the ink | 5/5 | any invented point/label kills (b′) → description-only |
| P-10 ceiling check | 3 English keys + the public F rubric, typed, transcription-bypass, graded by grader-v5.4+english on a C8-compiled plan | top level on every leveled criterion | ≥ 4/5 repeats per criterion | any criterion below top on ≥ 3/5 ⇒ C8/V13 or the verifier, not data; also the middle-band histogram must be 0 |
| P-11 Math cap fallback | 3-unit exam under D-13 fallback | compile succeeds at total 120, no groups | yes | INV-4 fires ⇒ the fallback is not functional |

---

## 6. Questions for Noam (blocking only) — [revised 2026-09-08; D-12 removed, resolved]

1. **D-17 spend hold:** lift it for A3 (≈ $6, k=5, compiled hobby plan) so Phase 0 has a measured CS grading baseline? If not, Phase 0 records A0 only and the report says the CS grading gate was structural.
2. **D-3 Amendment 1:** discrete levels (i) with the in-between rate pre-registered — approve? (The grader side now mirrors `counted`: no new verdict value, `selected_level` beside `units_correct`, one additive `TeacherOverride` field.)
3. **D-16 stamping:** system-prompt assembly per profile, CS stamps unchanged and sha-pinned, non-CS stamps `<base>+<profile_key>` — approve? This is the OD-18 fork ruling, generalised.
4. **D-7 cut line:** figures (Phase 5) below the line with the description-only fallback — approve? (Or name what else should fall off.)
5. **The Math fixtures:** may I hand-author a DOCX transcript of the 3-unit test's five printed pages (labelled HAND-TRANSCRIBED, pages cited) as a compile fixture so 2b/2c/D-13 have a text input, in parallel with the VLM render stage?
6. **The English writing rubric:** may I author a DOCX from the public F/G PDF (labelled PUBLIC-MINISTRY, URL + fetch date) as the D-3 extraction fixture? The drop has no band table.
7. **The uncommitted grade-review tree:** Phase 2b's frontend work (level picker, `pricing.ts` branch) lands on top of the untracked `src/components/grade-review/` + `lib/pricing.ts` — build on that tree as-is, or wait for it to be committed first?

---

## 7. Parking lot

- `pricer.py:79-81` dead `_snap`; `grader_v5.py:72` unused import; the seven mirrored verdict Literals (one `Verdict` type — done inside 2b).
- `rubric_management.py::AnnotationSchema` gains nothing (no new Annotation field) — confirmed by the plan; the fidelity test stays green.
- Legacy prompts (`handwriting_transcription_service.py`, `rubric_service.py`, `vlm_rubric_extractor.py`, `app/grading_agent.py`, `app/services/grading_agent.py`, `app/document_parser.py`) — dead or off-engine; retirement is B-28-class cleanup, not this cycle.
- `identity.py:102` unversioned prompt.
- `EXTRACTION_PROMPT_VERSION` ledger comment stops at 3.7.0 (`pipeline.py:612-617`).
- `subject_matters` seed has 4 duplicate codes and `hebrew` seeded twice (`migrations/001:61-83`).
- The English booklet's "answer lines" are printed graphics: students write **on the booklet**; P1's printed-furniture exclusion (`GT_CONVENTIONS` §3) meets form-fill pages for the first time — a modality (`form_fill`) worth a prediction when scans arrive.
- `TRANSCRIPTION_GT_CONVENTIONS.md` v1.1 file is missing; v2 will be written on the reconstruction and say so.
- Frontend `check:copy` does not gate `LanguageSelector.tsx`/`RubricMetadataEditor.tsx`/`page.tsx` masculine imperatives.
- Two of the three "English rubric" folders hold the same booklet; folder 1's key is Module G.

---

## 8. Files read (this session)

Brief `backend/vivi-multisubject-beta-brief.md`; `CLAUDE.md`; `tests/transcription_eval_suit/transcription_evalsuite_skill.md`; `tests/rubric_eval_suite/RUBRIC_EVAL_PLAYBOOK.md` (§0–4); `app/schemas/ontology_types.py` (1–760, 895–1060, 1195–1300); `app/services/contract_compiler.py` (88–225, 385–425); `app/services/docx_v3/pipeline.py` (def index, 91–108, 617); `app/services/docx_v3/parser_render.py` (API index); `tests/rubric_eval_suite/runner.py` (71–81, 170–260, 470–486); `tests/rubric_eval_suite/configs/default.json`; `tests/rubric_eval_suite/benchmarks/` listing + `hobby_tvshow.json` head; `app/config.py` (grep); `app/schemas/graded_test_draft.py` (45–62); `app/services/graded_test_contract_compiler.py` (179–206); `app/api/v0/grading.py` (grep); `frontend/src/lib/flags.ts`; `frontend/src/app/batches/[id]/page.tsx` (105–125); `frontend/src/components/GradedTestReviewPanel.tsx` (grep); `frontend/src/components/grade-review/GradeReviewSurface.tsx:46`; all five English/Math fixture files (structure + 15 page images viewed); the two ministry PDFs (fetched, text-extracted). Six read-only sweeps covered: models/migrations/api/services (A1), every prompt file (A2), transcription contracts + GT + validator + scorer (A3), all three eval suites (A6), the frontend tree (A7), the grader package + pricing + gate (A8) — their UNREAD lists are in the transcript and none touches a cited claim.

**Not run:** the grading eval, `check_goal.sh`, Playwright (Phase 0 owns them). **Spent:** ≈ $0.6 (four extraction calls).

**Re-read 2026-09-08 (D-12 revision, zero spend):** `git log` `a1a3273..52855ab`; `app/agents/plan_compiler/{compile.py (1-90, 553-600, def index), skeleton.py (20-70), stage0.py (grep), route.py + segment.py (grep for subject/CS tokens)}`; `app/agents/plan_gen/` listing + `PLAN_production_wiring.md` (1-60) + `TRACKER_plan_compiler_v2.md` (rulings grep) + `A0_REPORT.md` (1-30); `app/agents/grader/{plan_schemas.py, verifier_prompt.py (45-72, grep), grader_v5.py (grep), plan_validator.py (grep), prompt.py (grep)}`; `app/services/{grader_selection.py (33-107), grading_runner.py (160-185), plan_store.py (46-53, 176-215), pricing.py (grep), cloud_tasks_service.py (grep)}`; `app/schemas/graded_test_draft.py (45-66, grep)`; `app/config.py` (grep); `app/database.py:149-153`; `migrations/` listing; `app/api/v0/rubric_management.py` (grep); `frontend/src/lib/pricing.ts` (grep), `GradeReviewSurface.tsx:54`, `GradedTestReviewPanel.tsx:108`; `git status` of `frontend/src`; the Cloud Run service env (names + grader/plan values).
