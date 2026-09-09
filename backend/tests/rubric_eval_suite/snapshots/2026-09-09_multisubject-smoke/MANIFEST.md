# REAL-PROVIDER SNAPSHOT — the multi-subject beta's smoke gate (Phase 5)

**Snapshots, not ground truth.** Two recorded runs kept so the smoke-gate rows in
`docs/MULTISUBJECT_PHASE_GATE.md` can be checked without paying for them again. Hand-ratified
goldens live in `../../benchmarks/`; nothing here is one.

Both runs: `gpt-5.6-terra` / reasoning `high` / max_tokens 32000, via `run_any.py` (kept here),
which sets the production pin explicitly because the pipeline otherwise falls through to its own
`gpt-4o` code default.

## `math4_pdf/` — the D-8 PDF path

The SAME 4-unit Math document as `../2026-09-09_multisubject-math4/`, as a **PDF** rather than a
DOCX, so the rasterize → `rubric-read/rr1.0` path is exercised end to end.

| | |
|---|---|
| render | `stage=image_read source=pdf`, 16 pages read, **0 failed**, **$0.1473** |
| extraction | 15,692 in / 10,306 out, **0 retries**, 344 s, prompt `3.10.0-fixsource+mathematics` |
| shares | **33.5 / 33.25 / 33.25 / 33.25 / 33.25**, `SelectionGroup` choose 3 of 5, `question_type` `computation` |
| total | **100** |
| compile as extracted | BLOCKED at 7 nodes — the teacher's own weights disagreeing with themselves |
| compile after the rubric-gate fix | **OK total=100.00** (`teacher_fix_report.json`, `contract.json`) |

**This run is why the off-grid guard exists.** The model's per-question totals came back as
33.333333…, summing to **99.99999999989998**. The post-pass snaps that denominator once to 100,
keeps the written value in the stamp, and names the change — without it, the shares themselves
would have landed off the 0.25 grid the whole product rounds to.

Independent draw from the DOCX run, so a slightly different set of her inconsistencies surfaced
(7 nodes rather than 5). The shares, the total and the group are identical, which is the point.

## `english_1/` — a real bagrut English booklet

`fixtures/English_rubircs-solutions/1/016584-HEB-1500-1645.docx`, a teacher's own file.

| | |
|---|---|
| render | `stage=docx_text` — the DOCX has a text layer, so the image stage never fired |
| extraction | 26,896 in / 7,022 out, **1 retry**, 108 s, prompt `3.10.0-fixsource+english` |
| shape | q1 60 + q2 40 = **100**, `question_type` `short_answer` (not `coding_task`), 9 criteria |
| post-pass | `rescale_to_exam` correctly **absent** — the flag keeps English out of the Math path |
| compile | **BLOCKED**: `Question q2: Criteria sum (0) differs from declared total (40.0)` |

**The block is the correct reading of the document.** q2 is the WRITING task, and this booklet does
not contain its rubric — that is the ministry band table, a separate file (see
`../2026-09-09_multisubject-ministry-fg/`). `ZERO_CRITERIA` on q2 says exactly that. Merging a
second document by item number is **ALPHA-GAP A-9** (D-14 ii).

Read the two English runs together: the document that carries its own rubric extracts and compiles;
the one whose rubric lives elsewhere extracts correctly and then refuses, naming the gap. A teacher
cannot yet grade a full bagrut English exam from her own two files alone.
