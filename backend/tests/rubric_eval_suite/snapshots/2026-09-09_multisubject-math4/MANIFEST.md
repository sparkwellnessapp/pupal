# REAL-PROVIDER SNAPSHOT — 4-unit Math DOCX, multi-subject beta Phase 2.t

**This is a SNAPSHOT, not ground truth.** Nothing here is hand-ratified. It is one recorded run
of the real pipeline against a real teacher document, kept so the numbers in
`docs/MULTISUBJECT_PHASE_GATE.md` can be checked without paying for the run again. The
hand-ratified goldens live in `../../benchmarks/` and this directory must never be read as one.

* **Fixture** `tests/rubric_eval_suite/fixtures/Math_rubrics/4 יחל מבחן ומחוון.docx` — a printed
  4-unit bagrut-format test (35472, מתכונת 2) plus the teacher's **handwritten** marking scheme,
  the whole document stored as 16 page images.
* **Date** 2026-09-09 · **HEAD** see `git_head.txt` · branch `perf/rubric-extraction-latency`.
* **Render** `rubric-read/rr1.0` on `gemini-3.1-pro-preview` — 16 pages read, 0 failed,
  **$0.1472**, 36.0 s. Paid ONCE and replayed into every extraction attempt.
* **Extraction** `gpt-5.6-terra` / reasoning `high` / max_tokens 32000 — the production D-2 pin,
  set explicitly (see the warning below). Prompt `3.10.0-fixsource+mathematics` (the D-16 stamp:
  base version + profile key). 15,668 in / 9,915 out tokens, 217.8 s, 0 retries.

## Files

| file | what it is |
|---|---|
| `render.md` | what the reader saw — 16 `=== PAGE n ===` blocks, weights on their step lines |
| `render_report.json` | the render stage's own record (stage, counts, cost, model) |
| `draft.json` | the `ExtractRubricResponse` as the teacher would first see it, AFTER `rescale_to_exam` |
| `summary.json` | shares, groups, annotations, warnings, token counts, the compile verdict |
| `teacher_fix_report.json` | the rubric-gate move: which nodes she resolves, and the compile result |
| `contract.json` | the `GradingRubricContract` produced after that fix — **total 100.00** |
| `render_math4.py` · `run_math4_cached.py` · `teacher_fix.py` | exactly what was run, in order |

## What the run establishes

1. **The exam is scored out of its own real total.** `total_points` **100**, shares
   **33.5 / 33.25 / 33.25 / 33.25 / 33.25**, one `SelectionGroup` choosing **3 of 5** — the D-13
   ruling's target values, with every criterion on the 0.25 grid. No invented denominator.
2. **The teacher's own arithmetic is surfaced, not repaired.** The draft does NOT compile as
   extracted, and that is the designed outcome. Five nodes are flagged, each a fact about her
   document: **q2** carries no marking scheme at all (the vectors question — her omission);
   **q3**'s section weights read 5+20+25+20+35 = **105%**; **q3.ב**, **q4.ד** (39% declared over
   steps summing 34%) and **q5.ג** likewise. Each gets a `rubric_mismatch` WARNING quoting both
   the exam-scale numbers and her written ones, and INV-1/2/3 block the Contract until she acts.
3. **Her fix compiles.** `teacher_fix.py` plays the one move the rubric gate exists for —
   resolving those five nodes, keeping every other number — and the Contract compiles at
   **total 100.00** with question totals 33.5 / 33.25 × 4 and the selection group intact.

## Warnings for whoever reads this next

* **The model pin is not automatic outside the runner.** `extract_rubric_from_docx` resolves its
  model from `os.environ` and otherwise falls through to the pipeline's own **`gpt-4o`** default —
  the model `CLAUDE.md` records as never evaluated against any current prompt. An earlier attempt
  ran that way and extracted 1 question of 5. Export
  `EXTRACTION_LLM_PROVIDER/MODEL/REASONING_EFFORT/MAX_TOKENS` in any one-off script, as
  `run_math4_cached.py` does.
* **Page 8 rendered blank** — a grid page with almost no ink. The reader returned nothing rather
  than inventing content, which is the intended behaviour and is why the page count (16) and the
  content pages (15) differ.
* **`draft.json` is post-`rescale_to_exam`.** The weights the teacher actually wrote are the ones
  quoted inside each criterion description (`10%`, `15% נגזרת`, …) and in the mismatch messages;
  the `points` fields are already on the exam scale.
