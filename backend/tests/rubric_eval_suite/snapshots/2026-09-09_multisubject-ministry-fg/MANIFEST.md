# REAL-PROVIDER SNAPSHOT — Ministry F/G writing rubric, multi-subject beta Phase 4a

**This is a SNAPSHOT, not ground truth.** One recorded run of the real pipeline, kept so the
numbers in `docs/MULTISUBJECT_PHASE_GATE.md` can be checked without paying for it again. Nothing
here is hand-ratified; the ratified goldens live in `../../benchmarks/`.

## The fixture is PUBLIC-MINISTRY

`tests/rubric_eval_suite/fixtures/English_rubircs-solutions/public/ministry_FG_writing_rubric_2020.docx`

* **Source** Israeli Ministry of Education — MODULE G (16582) and F (external 16584) WRITING
  RUBRIC, as of Winter 2020.
* **URL** https://meyda.education.gov.il/files/Pop/0files/english/Chativa-Elyona/Bagrut/FGExternalInternal2020.pdf
* **Fetched** 2026-09-05. **Built** 2026-09-09 by `make_ministry_docx.py` (kept here), which
  transcribes the PDF's own text layer into the DOCX shape a teacher's file has: a band table,
  one row per criterion, four band columns, points on the row beneath. **No wording is invented.**
* It is a public document, not a teacher's private file, which is why it can live in the repo.

## The run

`gpt-5.6-terra` / reasoning `high` / max_tokens 32000, prompt **`3.10.0-fixsource+english`**
(the D-16 stamp). Render stage `docx_text` — the DOCX has a real text layer, so the deterministic
renderer handled it and the image stage never fired. 26.6 s · 9,106 in / 1,654 out tokens ·
**0 retries** · no warnings.

## What it establishes (P-12, the D-3 beta path)

| claim | result |
|---|---|
| the ladder flattens to ONE criterion per row | 4 criteria, not 16 |
| each takes the TOP band's points | **8 / 10 / 16 / 6** |
| the total is the document's own | **40**, and `compile` **OK total=40.0** |
| every band survives verbatim for the teacher | all four band names present in all four descriptions, each with its own points |
| English never enters the Math post-pass | `rescale_to_exam` absent from the metadata |
| the question type is not CS | `short_answer` — the profile default, never model output (D-10) |

Example, the MECHANICS criterion as extracted (points 6, the CORRECT band):

```
MECHANICS
CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on sentences
PARTIALLY CORRECT (4): • partially correct use of: … • some run-on sentences
MINIMALLY CORRECT (2): • minimally correct use of: … • frequent run-on sentences
INCORRECT (0): • Incorrect use of: … • consistent use of run-on sentences
```

## What it does NOT establish

The grader does not SELECT a band — it awards against a 6-point criterion whose description
happens to describe four. A teacher who wants "this essay is PARTIALLY CORRECT on mechanics,
so 4" must set 4 herself. That is **ALPHA-GAP A-1** (discrete levels: ontology, compiler, editor,
pricer and a `level_select` verifier rule), and the ministry's own note — *"Markers can give
in-between grades e.g. 7 pts"* — is the reason the flattened path is defensible for beta rather
than merely convenient: the ministry already expects marks between the bands.
