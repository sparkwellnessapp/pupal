"""LaTeX → readable Unicode, for surfaces that cannot run KaTeX (OD-M10).

The student's returned exam is drawn by PyMuPDF, which has no math engine. Any math in
the text it prints — feedback that quotes the answer, a teacher's note — is linearised
here: `\\frac{1}{e}` → `1/e`, `\\sqrt{e}` → `√e`, `x^{2}` → `x²`, `\\leq` → `≤`.

Deterministic and FORM-PRESERVING: it changes how a mark is spelled, never which mark
it is. `\\sqrt{e}` becomes `√e`, never `e^½`; a fraction stays a fraction. A command it
does not know is printed by name rather than dropped — a missing symbol is a silent
change, a visible name is not.

Each linearised span is wrapped in LEFT-TO-RIGHT EMBEDDING … POP (U+202A … U+202C).
MEASURED in the render test: in a right-to-left paragraph the bidi algorithm reorders
the neutrals between two numbers, so a bare `(2, 3)` displays as `(3 ,2)` — a different
point. The embedding keeps the span's internal order; `_bidi_for_pymupdf` treats LRE as
strong LTR and the algorithm removes the controls (X9), so nothing extra is drawn.
"""
from __future__ import annotations

from typing import List

from .spans import split_math
from .tokens import Token, tokenize

LRE, PDF, NBSP = "‪", "‬", " "

_SYMBOLS = {
    "\\cdot": "·", "\\times": "×", "\\div": "÷", "\\pm": "±", "\\mp": "∓",
    "\\leq": "≤", "\\le": "≤", "\\geq": "≥", "\\ge": "≥", "\\neq": "≠", "\\ne": "≠",
    "\\approx": "≈", "\\equiv": "≡", "\\sim": "~", "\\propto": "∝",
    "\\infty": "∞", "\\to": "→", "\\rightarrow": "→", "\\leftarrow": "←", "\\gets": "←",
    "\\Rightarrow": "⇒", "\\Leftarrow": "⇐", "\\Leftrightarrow": "⇔", "\\iff": "⇔",
    "\\implies": "⇒", "\\nearrow": "↗", "\\searrow": "↘", "\\nwarrow": "↖", "\\swarrow": "↙",
    "\\in": "∈", "\\notin": "∉", "\\subset": "⊂", "\\subseteq": "⊆", "\\cup": "∪",
    "\\cap": "∩", "\\emptyset": "∅", "\\varnothing": "∅", "\\forall": "∀", "\\exists": "∃",
    "\\angle": "∠", "\\triangle": "△", "\\perp": "⊥", "\\parallel": "∥", "\\circ": "°",
    "\\degree": "°", "\\int": "∫", "\\sum": "∑", "\\prod": "∏", "\\partial": "∂",
    "\\ldots": "…", "\\dots": "…", "\\cdots": "⋯", "\\prime": "′", "\\wedge": "∧", "\\vee": "∨",
    "\\neg": "¬", "\\lvert": "|", "\\rvert": "|", "\\vert": "|", "\\mid": "|",
    "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\delta": "δ", "\\epsilon": "ε",
    "\\varepsilon": "ε", "\\theta": "θ", "\\lambda": "λ", "\\mu": "μ", "\\pi": "π",
    "\\rho": "ρ", "\\sigma": "σ", "\\tau": "τ", "\\phi": "φ", "\\varphi": "φ", "\\omega": "ω",
    "\\Delta": "Δ", "\\Sigma": "Σ", "\\Omega": "Ω", "\\Pi": "Π", "\\Gamma": "Γ",
}
_SYMBOL_CS = {"\\{": "{", "\\}": "}", "\\|": "‖", "\\%": "%", "\\$": "$", "\\&": "&",
              "\\#": "#", "\\_": "_"}
_SILENT_CS = frozenset({"\\,", "\\;", "\\:", "\\!", "\\>"})
_SILENT_CW = frozenset({
    "\\left", "\\right", "\\middle", "\\displaystyle", "\\textstyle", "\\quad", "\\qquad",
    "\\big", "\\Big", "\\bigg", "\\Bigg", "\\bigl", "\\bigr", "\\Bigl", "\\Bigr",
    "\\limits", "\\nolimits",
})
_NAMED_FUNCTIONS = frozenset({
    "\\sin", "\\cos", "\\tan", "\\cot", "\\sec", "\\csc", "\\arcsin", "\\arccos", "\\arctan",
    "\\ln", "\\log", "\\exp", "\\lim", "\\max", "\\min", "\\sup", "\\inf", "\\det", "\\deg",
})
_PASSTHROUGH = frozenset({"\\mathrm", "\\mathbf", "\\mathit", "\\operatorname", "\\boxed"})
# Text-mode arguments: their spaces are words, so they are copied, not linearised.
_TEXT_MODE = frozenset({"\\text", "\\textrm", "\\textbf", "\\textit", "\\mbox"})
# Relations and arrows read with a space either side, as a typeset formula shows them.
_RELATIONS = frozenset("=<>≤≥≠≈≡→←⇒⇐⇔∈∉⊂⊆")
_SUP = str.maketrans("0123456789+-=()nix", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱˣ")
_SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_SUP_OK = set("0123456789+-=()nix")
_SUB_OK = set("0123456789+-=()")
_COMBINING = {"\\overline": "̅", "\\bar": "̄", "\\vec": "⃗",
              "\\overrightarrow": "⃗", "\\hat": "̂", "\\cancel": "̶",
              "\\underline": "̲"}


class _Reader:
    def __init__(self, toks: List[Token]):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def skip_ws(self):
        while self.peek() and self.peek()[0] == "ch" and self.peek()[1] == " ":
            self.i += 1

    def group(self) -> List[Token]:
        """One argument: a brace group's contents, or a single token."""
        self.skip_ws()
        tok = self.take()
        if tok is None:
            return []
        if tok != ("ch", "{"):
            return [tok]
        depth, out = 1, []
        while self.peek() is not None:
            tok = self.take()
            if tok == ("ch", "{"):
                depth += 1
            elif tok == ("ch", "}"):
                depth -= 1
                if depth == 0:
                    break
            out.append(tok)
        return out


def _atomic(s: str) -> bool:
    """Does `s` read as one unit without parentheses (`12`, `e`, `√e`, `2x`)?"""
    return bool(s) and all(c.isalnum() or c in "√.′" for c in s)


def _wrap(s: str) -> str:
    return s if _atomic(s) else f"({s})"


def _script(s: str, table, ok, caret: str) -> str:
    if s and all(c in ok for c in s):
        return s.translate(table)
    return f"{caret}{_wrap(s)}"


def _lin(toks: List[Token]) -> str:
    r = _Reader(toks)
    out: List[str] = []
    while r.peek() is not None:
        kind, val = r.take()
        if kind == "ch":
            if val == "^":
                out.append(_script(_lin(r.group()), _SUP, _SUP_OK, "^"))
            elif val == "_":
                out.append(_script(_lin(r.group()), _SUB, _SUB_OK, "_"))
            elif val in "{}":
                continue
            elif val == "&":
                out.append(", ")
            elif val == "~":
                out.append(" ")
            elif val.isspace():
                continue                  # math mode: whitespace is not a mark
            elif val == ",":
                out.append(", ")
            elif val in _RELATIONS:
                out.append(f" {val} ")
            else:
                out.append(val)
            continue
        if kind == "cs":
            if val == "\\\\":
                out.append("; ")
            elif val in _SILENT_CS:
                continue
            elif val == "\\ ":
                out.append(" ")
            else:
                out.append(_SYMBOL_CS.get(val, val[1:]))
            continue
        # control word
        if val in _SILENT_CW:
            if val in ("\\left", "\\right", "\\middle") and r.peek() == ("ch", "."):
                r.take()
            continue
        if val in ("\\frac", "\\dfrac", "\\tfrac", "\\cfrac"):
            num, den = _lin(r.group()), _lin(r.group())
            out.append(f"{_wrap(num)}/{_wrap(den)}")
        elif val == "\\sqrt":
            r.skip_ws()
            index = ""
            if r.peek() == ("ch", "["):
                r.take()
                idx: List[Token] = []
                while r.peek() is not None and r.peek() != ("ch", "]"):
                    idx.append(r.take())
                r.take()
                index = _lin(idx)
            body = _lin(r.group())
            root = "√" if not index else (index.translate(_SUP) if all(c in _SUP_OK for c in index)
                                         else f"{index}") + "√"
            out.append(root + _wrap(body))
        elif val in _COMBINING:
            mark = _COMBINING[val]
            out.append("".join(c + mark for c in _lin(r.group())))
        elif val in _PASSTHROUGH:
            out.append(_lin(r.group()))
        elif val in _TEXT_MODE:
            out.append("".join(v for _, v in r.group()))
        elif val == "\\binom":
            a, b = _lin(r.group()), _lin(r.group())
            out.append(f"C({a}, {b})")
        elif val in ("\\begin", "\\end"):
            name = "".join(v for _, v in r.group())
            if name == "cases":
                out.append("{ " if val == "\\begin" else " }")
        elif val in _NAMED_FUNCTIONS:
            out.append(val[1:])
            r.skip_ws()
            nxt = r.peek()
            if nxt and nxt[0] in ("ch", "cw") and nxt[1] not in ("(", "^", "_", " "):
                out.append(" ")
        elif val in _SYMBOLS:
            sym = _SYMBOLS[val]
            out.append(f" {sym} " if sym in _RELATIONS else sym)
        else:
            out.append(val[1:])           # unknown: its name, never nothing
    return "".join(out)


def linearize_math_body(body: str) -> str:
    text = _lin(tokenize(body.replace("\n", " ")))
    return " ".join(text.split())


def linearize(text: str) -> str:
    """The text with every math span linearised and isolated LTR; prose untouched."""
    if not text or "\\(" not in text:
        return text
    res = split_math(text)
    parts: List[str] = []
    for seg in res.segments:
        if seg.kind == "math":
            # No-break spaces: a formula is one unit, and a line break inside it
            # would also split its LTR embedding across two lines.
            parts.append(LRE + linearize_math_body(seg.body(text)).replace(" ", NBSP) + PDF)
        else:
            parts.append(text[seg.start:seg.end])
    return "".join(parts)
