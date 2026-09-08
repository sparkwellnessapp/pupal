# Fixture manifest — `tests/rubric_eval_suite/fixtures/`

Written 2026-09-05 (multisubject beta, Phase A0). Every claim below was established by
opening the file (`zipfile` over the DOCX, PyMuPDF over the PDF, and looking at the page
images), not by reading the brief. Where the brief and the files disagree, the files win
and the disagreement is recorded.

**None of the English or Math artifacts below is student work usable as grading ground
truth.** The English PDFs are ministry *answer keys* (ceiling artifacts). The Math scans are
each a printed test plus the **teacher's handwritten worked solution with weights** (the
marking scheme) — real rubrics, image-only, from one school; they are ingestion inputs, not
accuracy data. (Corrected 2026-09-08 — see §3.)

---

## 1. Pre-existing CS fixtures (the extraction regression set — unchanged)

| file | subject | provenance | benchmark |
|---|---|---|---|
| `bagrut_899371.docx` | computer_science / csharp | teacher-authored DOCX rubric (selection exam, choose 4 of 6) | `benchmarks/bagrut_899371.json` |
| `csharp_plane_combine.docx` | computer_science / csharp | teacher-authored DOCX rubric (clean-table control) | `benchmarks/csharp_plane_combine.json` |
| `employee_course_select1.docx` | computer_science / csharp | teacher-authored DOCX rubric (selection) | `benchmarks/employee_course_select1.json` |
| `foundations_cs.docx` | computer_science / csharp | teacher-authored DOCX rubric | `benchmarks/foundations_cs.json` |
| `hobby_tvshow.docx` | computer_science / csharp | teacher-authored DOCX rubric (the ratified grading exam) | `benchmarks/hobby_tvshow.json` |

The suite existed before the English/Math drop: `runner.py`, `scoring.py`, `gates.py`,
`build_benchmarks.py`, `RUBRIC_EVAL_PLAYBOOK.md`, `PREDICTIONS.md`, `RUNLOG.md`. It is
**not** fixtures-only. `runner.py:71-81` pairs `fixtures/<name>.docx` with
`benchmarks/<name>.json` by basename, **non-recursively** — everything under the two
subdirectories below is currently unreachable by the runner.

---

## 2. English drop — `English_rubircs-solutions/{1,2,3}/`  (folder name typo is in the repo)

**What the brief said:** three rubric + model-solution pairs; the DOCX is "the rubric,
converted to DOCX"; the PDF is "the model solution, typed".

**What the files are:**

| folder | DOCX | what the DOCX actually is | PDF | what the PDF actually is |
|---|---|---|---|---|
| `1/` | `016584-HEB-1500-1645.docx` (2,471,035 B) | **Ministry exam BOOKLET** (מחברת בחינה) for English **Module F**, questionnaire 016584, summer 2026 מועד ב — cover, instructions, reading passage *Last-Chance Tourism*, 9 questions with printed point values, Part II writing task (40 pts), lined draft pages. 437 paragraphs, 2 tables, 44 embedded PNGs (answer-line graphics), 0 OMML. | `pitron-016582-00-HEB.pdf` (3 pp, text layer YES, 3,705 chars) | Ministry **answer key** (הצעה לפתרון) for **Module G**, questionnaire **016582** — a *different exam* from the DOCX beside it. Versions A and B. Reading items 1–8 with acceptable answers (`OR` alternatives, bracketed optional stems). Part II: "write the task as specified in the questionnaire" — **no descriptor, no bands, no points**. |
| `2/` | `016584-HEB-1500-1645 (1) (1).docx` (2,471,035 B) | **The same booklet as folder 1.** `word/document.xml` is byte-identical; only `docProps/core.xml` differs (a re-save). Rendered markdown identical (14,814 chars). | `pitron-016584-00-HEB.pdf` (2 pp, text YES, 2,103 chars) | Answer key for **Module F 016584** — the matching key for the DOCX. 9 reading items. Part II: same one-line pointer, no bands. |
| `3/` | `016384-HEB-1500-1645.docx` (2,497,620 B) | Ministry exam BOOKLET for English **Module B**, questionnaire 016384, summer 2026 מועד ב — reading only (*People Help Young Puffins*), 10 questions (9/9/10/9/9/9/2×9=18/9/9/9 = 100), no writing task. 447 paragraphs, 2 tables, 35 PNGs, 0 OMML. | `pitron-016384-00-HEB.pdf` (2 pp, text YES, 2,091 chars) | Answer key for Module B 016384. 10 items; item 7 "Any two of the following". No points in the key. |

So the drop is **2 distinct exam booklets** (F, B) and **3 distinct answer keys** (G, F, B).
The Module G booklet is absent. Folder 1 is mis-paired.

**Conversion status.** These DOCX files are not hand-converted *rubrics*; they are the
booklet as a Word document (`app=Microsoft Office Word`, 114 `<w:bidi>` marks, real tables
for the points summary and the bilingual instruction row). `parser_render.py` renders them
cleanly: all question text, point labels `(6 points)`, and the two tables survive; every
embedded image becomes an `[IMAGE: …]` placeholder. Nothing was flattened.

**Band structure: absent from the drop.** No band/level table appears in any of the six
files. The writing rubric the ministry actually uses for F/G is a separate public document
(`https://meyda.education.gov.il/files/Pop/0files/english/Chativa-Elyona/Bagrut/FGExternalInternal2020.pdf`,
fetched 2026-09-05): 4 criteria × 4 bands — Content & Organization 8/5/2/0, Vocabulary
10/6/3/0, Language Use 16/10/5/0, Mechanics 6/4/2/0 = 40, with "Markers can give in-between
grades e.g. 7 pts", word-count deduction tables, and zero-for-entire-task conditions. It is
**not** a fixture; it is cited as public evidence in `docs/MULTISUBJECT_PLAN.md` §A5.

**Shape classification (after A5):** reading parts = *additive, one criterion per item,
alternatives-as-prose*; writing part (F) = *leveled* under the public rubric, *unmodeled* in
the drop (0 criteria under a 40-point question — INV-1 fires at compile).

**Provenance note for the manifest:** the brief states Noam converted the English files by
hand from ministry PDFs. The files themselves are Word exports of the booklets; the
conversion did not introduce or remove structure. Recorded as stated + as observed.

---

## 3. Math drop — `Math_rubrics/`

**What the brief said:** one Math rubric, `.docx`.

**What the files are:** two exams, each as a DOCX **and** a PDF, all four **image-only**.

> **Correction (2026-09-08, `vivi-multisubject-execution-plan.md` §1).** The first reading of these
> files (2026-09-05) called pages 7+ "one student's handwritten answers with the teacher's marks".
> Noam opened the 4-unit file page by page: pages 7–15 are **the teacher's own handwritten worked
> solution — the marking scheme** — with per-sub-question weights in the margin and per-step weights
> inline; page 16 is a further solution page (CamScanner). The 3-unit file has the same shape. The
> earlier reading is retracted; what follows is the corrected one.

| file | pages | text layer | what it is |
|---|---|---|---|
| `3 יחל מבחן ומחוון.docx` (2,312,939 B) | 10 JPEG pages embedded, 19 paragraphs, **0 text**, 0 tables, 0 OMML | none | School-authored (Mosenson Youth Village) **3-unit** math test, questionnaire 35173, "מסכם סמסטר ב – מבחן 1", May 2026. Pages 1–5 printed test (5 questions × 24 pts, "answer as many as you wish, total capped at 100"; geometry with figures, trig, linear models with a graph). Page 6 blank. Pages 7–10: **the teacher's handwritten model solution = the marking scheme**, with per-sub-question weights as percentages of the question (e.g. Q1: 10%, 20%, 40%, 25%…) and per-step weights inline. |
| `3 יחל מבחן ומחוון.pdf` (1,392,752 B) | 10 | **NO** (0 chars, 10 images) | The same pages as a scanned PDF. |
| `4 יחל מבחן ומחוון.docx` (4,092,647 B) | 16 JPEG pages, 31 paragraphs, **0 text**, 0 tables, 0 OMML | none | School-authored **4-unit** math test, questionnaire 35472, "מתכונת 2", April 2026. Pages 1–6 printed test (2 chapters, 5 questions, answer 3 with at least one per chapter, 33⅓ each = 100; sequences, 3-D vectors with a pyramid figure, growth/decay, calculus with `ln`, fractions, superscripts, three printed derivative graphs to choose from). Pages 7–15: **the teacher's handwritten worked solution — the marking scheme** — per-sub-question weights in the margin (Q5: 10%, 10%, 7%, 39%, 9%, 15%, 10% = 100) and per-step weights inline (5%, 3%, 15%). Page 16: a further solution page (CamScanner). |
| `4 יחל מבחן ומחוון.pdf` (2,419,790 B) | 16 | **NO** (0 chars, 16 images) | The same pages as a scanned PDF. |

**So a Math rubric is: printed questions + a handwritten model solution whose steps carry
point weights** — a step-weighted additive rubric, the shape `Question/SubQuestion/Criterion(points)`
already represents. The problem is ingestion only: the pages are images and some are handwriting.
`parser_render.py` yields `[IMAGE: Image n]` × N and **zero characters** for both DOCX files, and the
production extraction pipeline fails on it (`RubricExtraction.questions.0.total_points` "Input should
be greater than 0") — see `docs/MULTISUBJECT_PLAN.md` §A4. The image-render stage (`rubric-read/rr1.0`,
execution plan Phase 2a) is what reads them.

**Shape classification (corrected):** *step-weighted additive, weights as % of the question*;
selection "answer 3 of 5 with ≥ 1 per chapter" (4-unit) / "answer any, capped at 100" (3-unit).
Residual after the execution plan: the chapter minimum and the true cap rule (D-13 → alpha A-3);
the fractional 33⅓ share is handled by grid-snapping (`rescale_to_exam`, Phase 2b). **n=2, both
school-authored, one school** — enough to illustrate Math shape, not to decide it. The evidence is
the teacher's scheme, not student marks.

---

## 4. Derived / synthetic artifacts (to be added in Phase 6/7 — none exist yet)

| planned file | label | source | purpose |
|---|---|---|---|
| `derived/eng_016584_key.txt`, `eng_016384_key.txt`, `eng_016582_key.txt` | CEILING-ARTIFACT | PyMuPDF text of the three answer keys | typed input for the transcription-bypass ceiling check (§5 of the plan) — *never* an accuracy number |
| `derived/eng_016584_key.misspelled5.txt`, `.mergedpara.txt` (× 3 keys) | SYNTHETIC-DERIVED | perturbation of the above | English grading smoke; not student work |
| `probe_omml.docx` | SYNTHETIC-PROBE | hand-written OMML + image + 3-column band table | the A4 OMML/image/band-table survival probe (currently in the session scratchpad; committed here in Phase 6 as a regression fixture) |
| founder-authored phone scans (Math page; English paragraph; Word math rubric) | SMOKE (n=1 per subject) | arrive 2026-09-05 evening | Phase 7 smoke gate — proves plumbing, not accuracy |
