"""Typographic canonicalisation of math spans (MATH_RENDERING_PLAN §4, OD-M3).

TWO SPANS ARE "THE SAME" ONLY IF THEY DRAW THE SAME MARKS. Never mathematical equivalence:
`\\sqrt{e}` and `e^{1/2}` are different answers (form is answer content, convention 1),
and `\\cdot` and `\\times` are different symbols the student chose. What collapses here is
only what the reader of a rendered page could not tell apart:

  * whitespace (insignificant in math mode; kept inside `\\text{…}`)
  * spacing commands: `\\,` `\\;` `\\:` `\\!` `\\ ` `\\quad` `\\qquad`
  * size and style wrappers: `\\left` `\\right` `\\big…` `\\displaystyle` `\\textstyle`
  * synonyms that draw one glyph: `\\dfrac`/`\\tfrac`→`\\frac`, `\\le`→`\\leq`,
    `\\ge`→`\\geq`, `\\ne`→`\\neq`, `\\to`→`\\rightarrow`, `\\lvert`/`\\rvert`→`|`
  * redundant braces around a single-token argument: `x^2` ≡ `x^{2}`, `\\frac12` ≡
    `\\frac{1}{2}`, `\\sqrt e` ≡ `\\sqrt{e}` — the canonical form is always braced

ONE canonicaliser. The grader's quote check (`agents/grader/validator.py`) and the
transcription eval read this module; nothing re-implements it. Text outside spans is
returned byte-for-byte, so a CS answer (no spans) is the identity.
"""
from __future__ import annotations

from typing import List, Tuple

from .spans import map_math_bodies
from .tokens import Token, tokenize, untokenize

_SPACING_CS = frozenset({"\\,", "\\;", "\\:", "\\!", "\\ ", "\\>"})
_DROP_CW = frozenset({
    "\\quad", "\\qquad", "\\thinspace", "\\medspace", "\\thickspace", "\\enspace",
    "\\negthinspace", "\\displaystyle", "\\textstyle", "\\scriptstyle",
    "\\left", "\\right", "\\middle",
    "\\big", "\\Big", "\\bigg", "\\Bigg",
    "\\bigl", "\\bigr", "\\Bigl", "\\Bigr", "\\biggl", "\\biggr", "\\Biggl", "\\Biggr",
})
_SIZERS_WITH_INVISIBLE_DOT = frozenset({"\\left", "\\right", "\\middle"})
_SYNONYMS = {
    "\\dfrac": "\\frac", "\\tfrac": "\\frac", "\\cfrac": "\\frac",
    "\\le": "\\leq", "\\ge": "\\geq", "\\ne": "\\neq", "\\leqslant": "\\leq",
    "\\geqslant": "\\geq", "\\to": "\\rightarrow", "\\gets": "\\leftarrow",
    "\\lvert": "|", "\\rvert": "|", "\\vert": "|", "\\lVert": "\\|", "\\rVert": "\\|",
    "\\lbrace": "\\{", "\\rbrace": "\\}", "\\land": "\\wedge", "\\lor": "\\vee",
}
_TEXT_CMDS = frozenset({"\\text", "\\textrm", "\\mathrm", "\\textit", "\\operatorname", "\\mbox"})
_ARITY = {"\\frac": 2, "\\binom": 2, "\\sqrt": 1, "\\overline": 1, "\\underline": 1,
          "\\vec": 1, "\\hat": 1, "\\bar": 1, "\\cancel": 1, "\\boxed": 1, "\\overrightarrow": 1}


def _group_end(toks: List[Token], i: int) -> Tuple[int, bool]:
    """(index just past the brace group opening at `toks[i] == ("ch","{")`, closed?)."""
    depth = 0
    j = i
    while j < len(toks):
        if toks[j] == ("ch", "{"):
            depth += 1
        elif toks[j] == ("ch", "}"):
            depth -= 1
            if depth == 0:
                return j + 1, True
        j += 1
    return len(toks), False              # unbalanced: take the rest, never invent a brace


def _canon(toks: List[Token]) -> List[Token]:
    out: List[Token] = []
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        if kind == "cw" and val in _TEXT_CMDS and i + 1 < len(toks) and toks[i + 1] == ("ch", "{"):
            end, _ = _group_end(toks, i + 1)
            out.extend(toks[i:end])      # text is verbatim, its spaces included
            i = end
            continue
        if kind == "ch" and val.isspace():
            i += 1
            continue
        if kind == "cs" and val in _SPACING_CS:
            i += 1
            continue
        if kind == "cw" and val in _DROP_CW:
            i += 1
            if val in _SIZERS_WITH_INVISIBLE_DOT and i < len(toks) and toks[i] == ("ch", "."):
                i += 1                   # `\left.` is an invisible delimiter
            continue
        if kind == "cw":
            val = _SYNONYMS.get(val, val)
            kind = "ch" if len(val) == 1 else ("cs" if len(val) == 2 and not val[1].isalpha() else "cw")
        if kind == "ch" and val in ("^", "_"):
            out.append((kind, val))
            i = _canon_arg(toks, i + 1, out)
            continue
        if kind == "cw" and val in _ARITY:
            out.append((kind, val))
            i += 1
            if val == "\\sqrt":
                i = _skip_ws(toks, i)
                if i < len(toks) and toks[i] == ("ch", "["):   # optional index, verbatim
                    j = i
                    while j < len(toks) and toks[j] != ("ch", "]"):
                        j += 1
                    out.extend(_canon(toks[i:j + 1]))
                    i = j + 1
            for _ in range(_ARITY[val]):
                i = _canon_arg(toks, i, out)
            continue
        out.append((kind, val))
        i += 1
    return out


def _skip_ws(toks: List[Token], i: int) -> int:
    while i < len(toks) and toks[i][0] == "ch" and toks[i][1].isspace():
        i += 1
    return i


def _canon_arg(toks: List[Token], i: int, out: List[Token]) -> int:
    """Emit one argument as a brace group, whatever form it came in."""
    i = _skip_ws(toks, i)
    if i >= len(toks):
        return i
    if toks[i] == ("ch", "{"):
        end, closed = _group_end(toks, i)
        out.append(("ch", "{"))
        out.extend(_canon(toks[i + 1:end - 1] if closed else toks[i + 1:end]))
        if closed:                       # an unclosed group stays unclosed
            out.append(("ch", "}"))
        return end
    # a single token argument: one character or one command
    out.append(("ch", "{"))
    out.extend(_canon([toks[i]]))
    out.append(("ch", "}"))
    return i + 1


def canonical_math_body(body: str) -> str:
    return untokenize(_canon(tokenize(body)))


def canonicalize(text: str) -> str:
    """The answer with every math span canonicalised; prose untouched."""
    if not text or "\\(" not in text:
        return text
    return map_math_bodies(text, canonical_math_body)
