r"""Mathematics as the student wrote it: LaTeX spans inside the answer string
(docs/MATH_RENDERING_PLAN.md §4). Pure, deterministic, no I/O.

    spans      where the math is (`\(` … `\)`), as offsets into the answer
    validate   the structural check P1's output gets (an INFO annotation, never a repair)
    canonical  typographic sameness, for the quote check — never mathematical equivalence
    linearize  LaTeX → Unicode for the PDF the student receives
"""
from .canonical import canonicalize
from .linearize import linearize
from .spans import has_math, split_math
from .validate import Issue, check_math_answer

__all__ = ["canonicalize", "linearize", "has_math", "split_math", "Issue", "check_math_answer"]
