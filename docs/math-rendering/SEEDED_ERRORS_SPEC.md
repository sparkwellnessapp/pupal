# The seeded-error set — what to write by hand

**Why it exists (MATH_RENDERING_PLAN §6).** Vision models silently "fix" students' mistakes: a
2026 study of 15 models on handwritten student solutions found 42–66% of samples contained at
least one silently corrected error, stronger models did it more, and telling the model to keep
errors helped by about 4 points. If the student writes `2 × 3 = 5` and the transcription says
`6`, the grader awards a point he did not earn, and nothing on the screen shows it. Our real
fixtures contain no known errors, so today we cannot measure our rate. This set measures it.

**The gate:** every seeded error must survive transcription — 100% on the typed fixtures, and
reported per error type for handwriting. One silently corrected error fails the gate.

---

## What to produce

* **At least 10 pages, at least 30 errors**, written by hand, in ordinary pen, the way a student
  in a 3- or 4-unit class would write. Natural solutions — an error sits inside working that is
  otherwise sensible, not on a page of errors.
* Two or more writers if possible: one hand is one style.
* **A key** (a spreadsheet or a text file): for each error — page, question, the line as WRITTEN,
  the value a correct student would have written, and the error type below. The key is never
  shown to the model.
* Scan at the resolution the school's scanner uses (the pipeline renders at 200 dpi).

Do not write the student's real name on the page.

## The error types (at least 3 of each)

| # | type | example as written |
|---|---|---|
| 1 | arithmetic | `2 · 3 = 5`, `17 + 8 = 24` |
| 2 | sign | `-(x - 2) = -x - 2` |
| 3 | exponent | `(x²)³ = x⁵`, `e^{2x}` differentiated as `e^{2x}` |
| 4 | derivative rule | `(ln x)' = x`, `(x·eˣ)' = eˣ` |
| 5 | fraction | `1/2 + 1/3 = 2/5` |
| 6 | decimal point | `0.25 · 4 = 10`, `23.259` copied as `23.295` on the next line |
| 7 | inconsistent with the givens | the question gives `a = 4.8`, the sketch says `a = 3.6` |
| 8 | carried copying error | line 1 ends `x = 7`, line 2 begins `x = 1 ⇒ …` |
| 9 | interval / inequality | `x > 3` written as the solution of `x < 3`, `[3, ∞)` for `(3, ∞)` |
| 10 | wrong final answer, boxed | the boxed value disagrees with the line above it |

Types 6 and 8 matter most: a model that reads `23.295` and "knows" the earlier line said `23.259`
is exactly the failure we are looking for.

## Mix in, deliberately

* **Two or three pages with a cancellation** (the same term struck on both sides) — it must be
  transcribed as `\cancel{…}`, not deleted as crossed-out work.
* **One or two pages with genuinely crossed-out work** next to a seeded error — the crossed-out
  step must disappear and the error must stay.
* **One or two sketches** whose label disagrees with the computation beside it (√e on the graph,
  e^½ in the working).
