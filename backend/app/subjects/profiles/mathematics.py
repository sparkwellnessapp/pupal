"""mathematics - math_notation + prose + figure modalities. Fragments per the execution
plan section 5 Phase 1 (F-1/F-2/F-3). Written blind; <= 12 lines each; replace CS rules, add none.
"""
from __future__ import annotations

KEY = "mathematics"
MODALITIES = ("math_notation", "prose", "figure")

# F-1 (extraction). The arithmetic is Phase 2b's post-pass (rescale_to_exam), never the model's.
# ALPHA-GAP A-3 (D-13): weights recorded verbatim on a per-question 100 scale; alpha normalizes per-question scale vs exam share.
EXTRACTION_FRAGMENT = """\
═══════════════════════════════════════════
SUBJECT: MATHEMATICS
═══════════════════════════════════════════
The handwritten solution pages are the marking scheme. A percentage or point weight written beside a step or sub-question is one criterion; record the number exactly as the teacher wrote it, on a per-question scale of 100, and keep her written weight (e.g. `10%`) in the criterion description. Do no arithmetic.
'Answer k of n' → a selection group choosing k; 'answer any, total capped at 100' → a selection group choosing ⌊100 / question points⌋ of n.
"""

# F-3 (P1 perception). Replaces the CS ink rules.
# ALPHA-GAP A-2 (D-1): linear notation only (`^`, `(a)/(b)`, `sqrt`); alpha adds the LaTeX grammar + KaTeX.
# ALPHA-GAP A-4 (D-2): a one-line `[איור: …]` description at a figure; alpha adds the page reference + crop.
P1_FRAGMENT = """\
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
wrong values, wrong signs, wrong steps.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind.
- Write mathematics as written, linearly: powers with `^`, fractions as \
`(numerator)/(denominator)`, roots as `sqrt(...)`, absolute value `|x|`. \
Never solve, simplify, or correct.
- At a drawing or graph, write one line `[איור: <what is drawn, labels verbatim>]` at its position.
- Include the student's handwritten answer content and substantive margin notes or messages.
"""

# F-2 (verifier). Replaces rules 3-5 of grader-v5.3. Lines 3 and 5 are D-4 by instruction.
# ALPHA-GAP A-9 (D-4b): deductions / follow-through by instruction only; alpha models them.
VERIFY_FRAGMENT = """\
3. VERIFY WHAT THE STUDENT WROTE against the check. Judge each step as written,
   consistent with the student's own prior values; never re-solve, simplify, or correct.

4. THE ABSENCE AUDIT. Before returning not_met for a missing element, search the
   ENTIRE answer for it; basis_he states, in Hebrew, what you searched for and where.

5. A correct method applied to a carried error is met for the method step; a wrong
   value is judged only by the check that names that value.
"""

P2_KEYWORDS = frozenset()

# D-13 (ruled 2026-09-08): weights recorded on a per-question 100 scale are mapped onto the exam by the grid-snap post-pass.
RESCALE_TO_EXAM = True
