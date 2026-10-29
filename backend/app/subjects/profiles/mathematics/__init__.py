"""mathematics - math_notation + prose + figure modalities. Fragments per the execution
plan section 5 Phase 1 (F-1/F-2/F-3). Written blind; <= 12 lines each; replace CS rules, add none.
"""
from __future__ import annotations

# [Q-18] The v6 PACK (PR_grader_v6_options.md §8) is the four sibling files, re-exported here;
# the seam data below is unchanged from when this package was a module.
from .explainer import EXPLAINER_FRAGMENT
from .planner import PLANNER_FRAGMENT
from .precedents import PRECEDENTS
from .verifier import VERIFIER_FRAGMENT

KEY = "mathematics"

# The v6 pack identity (config_hash input, §3.5). Bump PACK_VERSION with ANY change to the pack files.
PACK_ID = KEY
PACK_VERSION = "v4"   # v2 (Oct 18, Item A); v3 (Oct 18): R2; v4 (2026-10-29): the verifier traces each number to where she produced it, then recomputes (planner unchanged = v3)

MODALITIES = ("math_notation", "prose", "figure")

# F-1 (extraction). The arithmetic is Phase 2b's post-pass (rescale_to_exam), never the model's.
# ALPHA-GAP A-3 (D-13): weights recorded verbatim on a per-question 100 scale; alpha normalizes per-question scale vs exam share.
EXTRACTION_FRAGMENT = """\
═══════════════════════════════════════════
SUBJECT: MATHEMATICS
═══════════════════════════════════════════
The handwritten solution pages are the marking scheme. A percentage or point weight written beside a step or sub-question is one criterion; record the number exactly as the teacher wrote it, on a per-question scale of 100, and keep her written weight (e.g. `10%`) in the criterion description. Do no arithmetic.
That per-question 100 scale is for CRITERIA ONLY. A question's total_points is always its points as PRINTED on the exam paper (e.g. 33⅓ when five questions share 100 and three are answered) — never the 100 its criteria are written on — and the rubric total_points is the exam's printed total. The pipeline maps the criteria onto the printed points itself.
'Answer k of n' → a selection group choosing k; 'answer any, total capped at 100' → a selection group choosing ⌊100 / question points⌋ of n.
A question the solution pages do not score at all: keep the question's total as PRINTED on the exam paper, keep its printed parts, and give each part points 0 with no criteria — never invent a weight; the pipeline flags it for the teacher.
A weight beside a part that equals the SUM of the weights written beside its steps (40% beside «ג.» with 20% and 20% inside it) is that part's subtotal, not another criterion: record the step weights only.
A line `[איור …]` is a drawing on the exam or solution page: copy the WHOLE line verbatim, unchanged, into the question_text of the question or sub-question it stands in (into example_solution when it is part of the teacher's solution). Never summarize, merge or drop one.
"""

# F-3 (P1 perception). Replaces the CS ink rules.
# The DEFAULT fragment: linear notation (`^`, `(a)/(b)`, `sqrt`). The LaTeX grammar is the
# `latex1` variant below (A-2, MATH_RENDERING_PLAN §4), switched on by TRANSCRIPTION_P1_VARIANT.
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

# P1 VARIANTS (MATH_RENDERING_PLAN §4, 2026-10-28). A variant is a whole replacement of
# P1_FRAGMENT, selected by `PipelineConfig.p1_variant` (prod: TRANSCRIPTION_P1_VARIANT) and
# stamped into the prompt version as `+mathematics.<name>`, so a draft always says which
# notation it was written in. The DEFAULT stays the linear fragment above until the
# Phase 1 gate (plan §7) passes on teacher-ratified ground truth; flipping is env-only.
#
# `latex1` is probe v2's LaTeX fragment (docs/math-rendering/probe-v2: production pro kept the
# student's form 5/5 and wrote 588/588 spans KaTeX parses) plus the written conventions
# (docs/math-rendering/TRANSCRIPTION_GT_CONVENTIONS_MATH.md): one line per written line,
# `cases` only, `\boxed{}` for a framed answer, `\cancel{}` for a cancellation, sign-table
# arrows, and a numbered figure line (FIG-1 maps figure lines to figures by that number).
P1_FRAGMENT_LATEX = """\
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
wrong values, wrong signs, wrong steps, wrong arithmetic. Never solve, simplify, or correct.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind. A slash \
that CANCELS a term (the same term struck on both sides, a factor cancelled in a fraction) \
is not crossed-out work: write the term as \\cancel{...}.
- Write every piece of mathematics in LaTeX between \\( and \\), in the student's OWN form: \
√e is \\sqrt{e}, e^½ is e^{1/2}, 1/e is \\frac{1}{e}, e^-1 is e^{-1}, 0.5 stays 0.5. Never \
rewrite one form as another. A digit written over another is the final digit written.
- Hebrew words and units stay OUTSIDE the \\( \\) spans; never put Hebrew inside a span.
- One written line is one transcribed line. A line that is all mathematics is still \
wrapped in \\( \\) — including a system with a brace, written \
\\(\\begin{cases} ... \\end{cases}\\), and a line with \\cancel or \\boxed. Never use aligned, \
align, gather, \\[ \\] or $.
- A framed or circled final answer is \\boxed{...} inside its span.
- In a sign or variation table drawn as a grid, write arrows as \\nearrow and \\searrow and \
convex/concave marks as \\cup and \\cap, each in its own span inside its cell.
- At a drawing, graph or sketch, write one line `[איור N: <what is drawn, labels verbatim>]` \
at its position, numbering the drawings on each page 1, 2, … in reading order.
- Include the student's handwritten answer content and substantive margin notes or messages.
"""

# [owner 2026-10-29] Mathematics keeps the P1 its LaTeX work was MEASURED on (probe v3,
# OD-M8): gemini-3.1-pro with none of the accuracy mission's prompt rules — its `[74]`
# boxed-number rule would fight `\boxed{}`, and its table-row rule was measured on CS
# trace tables only. The mission's pin (gemini-3.5-flash) serves CS and English.
P1_CONFIG_OVERRIDES = {
    "p1_model_key": "gemini-3.1-pro-preview",
    "p1_reasoning_effort": "",
    "p1_table_rows": False,
    "p1_join_split_table_rows": False,
    "p1_instructions": False,
    "p1_boxed_values": False,
}

P1_VARIANTS = {"latex1": P1_FRAGMENT_LATEX}
# Measured at ONE page per call (probe v3, docs/math-rendering/probe-v3): at production's 3,
# both this fragment and the linear one misread the student's Hebrew on a dense page.
P1_VARIANT_PAGES_PER_CALL = {"latex1": 1}

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
