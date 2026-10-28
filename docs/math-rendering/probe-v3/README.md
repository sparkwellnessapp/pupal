# Probe v3 — the `latex1` P1 variant through production's own perception path

Measured 2026-10-28, after the owner approved the plan (OD-M2/M8/M9/M11). Spend ≈ $2.29.
No ground truth exists yet (OD-M11: a math teacher ratifies it), so nothing here is an accuracy
number. Every measure is deterministic over the raw output, plus three readings of the ink made
by eye and named below.

`probe3.py` calls `Pipeline._transcribe_pages` (P1) and `_strike_check_pages` exactly as
production does, with `subject_key="mathematics"`. Pages: the student pages of both papers
(4-unit p07–p12, 3-unit p07–p10), k = 5. `analyze3.py` scores; every run's `raw.json` and
`scores.txt` sit in its `out_*` directory.

## Runs, one variable each

| run | fragment | pages/call | what it answered |
|---|---|---|---|
| `out` | latex1 v0 | 3 (production) | first look |
| `out_A_latex1_1ppc` | latex1 v0 | **1** | is the fragment or the packing to blame? |
| `out_B_linear_3ppc` | **linear (today's prod)** | 3 | what does production do today? |
| `out_it1_p07` | + delimiters on all-math lines | 1 | iteration 1, p07 only |
| `out_it2_figs` | + caption labels as spans | 1 | iteration 2, p10–p12 only |
| `out_final` | it1 + it2 | 1 | whole partition, strike check on |
| `out_final_it1` | **it1 (shipped)** | 1 | whole partition after reverting it2 |

## What it found

**1. Rendering is solved.** Every run: 100% of spans parse in the frontend's pinned KaTeX
(1,045, 590, 95, 356, 1,321, 1,048 spans). Hebrew inside a span: 0, except one convention
conflict (5 below).

**2. The student's notation is kept.** On p11, which writes both forms of two values (√e and
e^½, 1/e and e^-1), every LaTeX run kept every form, 5/5.

**3. Production's 3-pages-per-call packing misreads the student's Hebrew.** The ink beside
`d = −10` on p07 says «התשלום החודשי קטן ב-10 ש"ח» (read by eye from the scan). Today's
production configuration (linear, 3/call) wrote «ההפרש החודשי» in **5/5** draws — stable and
wrong. At 1/call the same model read it right 15/15 (probe v2's 10, arm A's 5). The LaTeX
fragment at 3/call paraphrased it 4/5. **Attribution: packing, not fragment.** So `latex1` is a
package — fragment + 1 page per call (`P1_VARIANT_PAGES_PER_CALL`). Cost: ≈ $0.010 vs $0.007
per page. Note for CS: the same packing serves CS today; the CS eval gate passes at 3/call, so
this is a finding about dense Hebrew-with-math pages, not a measured CS defect.

**4. Iteration 1 fixed what it targeted.** Arm A left `cases`/`\cancel`/`\boxed` lines without
`\( \)` (3 lines per draw on p07, all caught by the validator). Saying so in the fragment took
p07 to zero findings, 5/5, with the Hebrew still faithful and every cancellation kept.

**5. Iteration 2 redistributed failure — the prompt surface is exhausted for these pages.**
Writing caption labels as spans fixed the captions and math3 p07's drawing lines (5/5), but
p07's Hebrew became «התשלום פוחת ב-10 ש"ח» in 5/5 draws. Reverted (CLAUDE.md §17.8: a new
failure on a working page ends prompt iteration). With it reverted, math3 p07 omits its two
drawing lines in 4/5 draws and one math3 p09 draw came out malformed (12 validator findings).
Each wording fixes one page and breaks another; this is a model-level limit on dense pages, to
be measured against ratified ground truth, not prompted around.

**6. A convention conflict, surfaced by the validator.** math3 p07 frames a phrase that mixes
Hebrew and a number («השטח גדל ב- 56.25%»). Convention 4 (frame → `\boxed{}`) and convention 2
(no Hebrew in a span) cannot both hold. The model wrote `\boxed{\text{השטח גדל ב-} 56.25\%}`,
the validator flagged it (INFO), and the screen shows it raw with a marker. Open decision.

**7. Cancellations survive the strike check; a student's error did not, once.** In-pipeline
the strike check (gemini-3.5-flash, 60 s) timed out on p07 in 10/10 draws from this machine,
so `strike_cancel.py` ran it directly, sequentially, k = 5: **0/5** deleted a `\cancel` line.
But draw 3 deleted two lines that are NOT struck in the ink (checked by eye): the student's
wrong sum formula `S_n = a_1·q^n/(q−1)` and its substitution, which he corrects on the next line.
A 1-in-5 silent deletion of a student's error is the plan's top risk (§6) in a new form, and it
comes from a pass CS also runs. Open decision.

## Files

`probe3.py` (one-variable env switches: `PROBE_VARIANT`, `PROBE_PAGES_PER_CALL`, `PROBE_STRIKE`,
`PROBE_DOCS`, `PROBE_PAGES`), `analyze3.py`, `strike_cancel.py`, and one `out_*` directory per
run.
