# Transcription conventions — Mathematics (v2, LaTeX)

**Status: written 2026-10-28, BEFORE any Math ground truth exists** (MATH_RENDERING_PLAN §4, §7
Phase 0). A convention decided after the first measurement is a ruler bent to fit it. These rules
bind three things at once, so they cannot drift apart:

1. the `latex1` P1 fragment (`backend/app/subjects/profiles/mathematics/__init__.py`);
2. the ground truth a math teacher ratifies (OD-M11: the agent pre-fills, the teacher decides);
3. the deterministic checks (`backend/app/services/math_notation/`).

Everything not stated here follows the CS conventions
(`backend/tests/transcription_eval_suit/TRANSCRIPTION_GT_CONVENTIONS.md`): page-by-page raw files,
`שאלה {n}` and `א.` section markers, `[?]` for what cannot be read, crossed-out work omitted, the
student's identity excluded, the hand-drawn table grid.

---

## The rules

**1. The student's form is the answer.** Write what he wrote, in the form he wrote it:

| he wrote | write | never |
|---|---|---|
| √e | `\(\sqrt{e}\)` | `e^{1/2}` |
| e^½ | `\(e^{1/2}\)` | `\sqrt{e}` |
| 1/e as a fraction bar | `\(\frac{1}{e}\)` | `e^{-1}` |
| e⁻¹ | `\(e^{-1}\)` | `\frac{1}{e}` |
| 0.5 | `\(0.5\)` | `\frac{1}{2}` |
| 23.259 | `\(23.259\)` | `23.26` |

Equal values in different forms are different answers. A teacher grades the form ("השאירו
בשורש"), so the transcription keeps it.

**2. Mathematics inside `\( … \)`, Hebrew outside.** Every formula, number-with-operator, variable
and coordinate is inside a span. Hebrew words and units are outside, always: Hebrew inside a span
reverses on every renderer we tested (`מ"ר` → `ר"מ`). A unit after a number:
`\(30\)` ש"ח, not `\(30 \text{ ש"ח}\)`. A lone number in a Hebrew sentence may be written either
way — the delimiters draw nothing, so `30` and `\(30\)` are the same marks (see "What counts as the
same transcription").

**3. One written line is one transcribed line.** Do not merge his lines into one block and do not
split one of his lines into two. A system drawn with a brace is one span with
`\begin{cases} … \\ … \end{cases}`. The environments `aligned`, `align`, `gather` (and their
starred forms), `\[ … \]` and `$ … $` are forbidden: they merge lines, which breaks segmentation and
hides where each line came from.

**4. A framed or circled final answer is `\boxed{…}` inside its span.** `\(\boxed{x = 2}\)`. Square
brackets are mathematics here (`[3, \infty)`), so the CS `[74]` box convention does not apply.

**5. A cancellation is `\cancel{…}`, and it is kept.** A slash through the same term on both sides
of an equation, or a factor struck in a fraction, is mathematics: `\(\cancel{a_1} q^{4} = \cancel{a_1}
\cdot 16\)`. It is NOT crossed-out work. Crossed-out work — a step he struck and abandoned — is
still omitted entirely.

**6. A digit written over another is the final digit written.** When the final digit cannot be
decided from the ink, write `[?]`. The ratifying teacher may use the student's OWN later arithmetic
as evidence of what he wrote (his perimeter 66.518 = 2 × 23.259 + 20 shows he used 23.259) — that is
evidence about the ink, never a correction of it. The model is not told this; it is a rule for the
humans who author the truth.

**7. Sign and variation tables use the grid, with math cells.** One table row per line (the CS grid
rule). Arrows are `\(\nearrow\)` and `\(\searrow\)`; convexity marks are `\(\cup\)` and `\(\cap\)`;
signs are `+`, `-`, `0`. A cell he left blank is an empty cell.

**8. A drawing is one numbered line at its position.** `[איור 1: <what is drawn, labels verbatim>]`,
numbered 1, 2, … per page in reading order. The number is what ties the line to the structured
reading of the drawing (FIG-1, plan §5). Labels inside the description are copied from the
drawing, never from the computation beside it, even when they are the same number in another form.

**9. Never solve, simplify, complete, or correct.** `2 \cdot 3 = 5` stays `2 \cdot 3 = 5`. A missing
bracket stays missing. A wrong sign stays wrong. This is the rule the literature says models break
most (plan §6); the seeded-error set measures it.

---

## What counts as the same transcription (OD-M3)

**Typographic sameness only** — what draws the same marks. `\dfrac` = `\frac`; `\left(` = `(`;
spacing commands and whitespace inside a span are nothing; `x^2` = `x^{2}`; `\le` = `\leq`. That is
the entire list, implemented once in `math_notation/canonical.py` and used by the grader's quote
check and the eval scorer. A scorer additionally ignores the `\(` `\)` delimiters themselves, which
draw no mark; the renderer does not, because they decide which side of the page a mark lands on. **Mathematical** equivalence (`\sqrt{e}` vs `e^{1/2}`, `0.5` vs
`\frac{1}{2}`, `2x` vs `x \cdot 2`) is a DIFFERENCE, always.

## What the ratifying teacher checks, line by line

For each pre-filled line, against the scan:

1. Every number, sign, operator, exponent, index, fraction bar and root — exactly his.
2. The form (rule 1) — not just the value.
3. The scope: what is in the exponent, under the root, in the numerator.
4. Lines: none merged, none split, none missing, none invented.
5. Cancellations kept as `\cancel`; crossed-out work omitted.
6. Each drawing has its numbered line and its labels are the drawing's own.

A correction is written into the file; an uncertainty is written as `[?]` and noted. The ratified
file is the ground truth. The pre-fill is never the ground truth, however clean it looks — the
agent's own count on one page was wrong in probe v2, and the models were right.
