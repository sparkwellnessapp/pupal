r"""Mathematics a MODEL wrote (feedback, an explanation line), brought to the one notation.

Every surface draws math from `\( … \)` spans: KaTeX on the review screens, `linearize` in
the student's PDF. A language model asked for Hebrew prose with formulas reaches for its
habits — `$…$`, `$$…$$`, `\[…\]` — and none of those is a span here: the preview shows them
as raw source and the PDF prints `$f'(x)=2x$` to the student. This rewrites those three
delimiters, and only them, into `\( … \)`. The mathematics inside is untouched.

Applied to model output only, never to the student's answer (that is faithful capture, and
its notation is the transcription's) and never to text the teacher typed.
"""
from __future__ import annotations

import re

_HEBREW = re.compile(r"[֐-׿]")
_DISPLAY_DOLLARS = re.compile(r"\$\$(.+?)\$\$", re.S)
_BRACKETS = re.compile(r"\\\[(.+?)\\\]", re.S)
# `$…$` on one line, no padding inside (TeX's own rule for an inline formula), no Hebrew:
# a currency amount in a sentence is not a formula.
_DOLLARS = re.compile(r"(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\$)")


def _span(body: str) -> str:
    return r"\(" + " ".join(body.split()) + r"\)"


_BARE = re.compile(r"[^֐-׿\n\[\];]*?(?:\\[A-Za-z]+|\^|_\{)[^֐-׿\n\[\];]*")


def _wrap_outside(segment: str) -> str:
    def wrap(m: "re.Match[str]") -> str:
        run = m.group(0)
        core = run.strip(" ,.:")
        if not core:
            return run
        lead = run[: run.index(core)]
        tail = run[run.index(core) + len(core):]
        return f"{lead}\\({core}\\){tail}"
    return _BARE.sub(wrap, segment)


def wrap_bare_latex(text: str) -> str:
    """LaTeX a READER wrote outside any span (a whole formula line, a `50^\\circ` inside a
    drawing's description) wrapped in `\\( … \\)`: each maximal run of non-Hebrew text that
    carries a command, `^` or `_{`, outside the spans already there. Markup, never content."""
    from .spans import split_math
    if not text or ("\\" not in text and "^" not in text):
        return text
    out = []
    for seg in split_math(text).segments:
        piece = text[seg.start:seg.end]
        out.append(piece if seg.kind == "math" else _wrap_outside(piece))
    return "".join(out)


def normalize_written_math(text: str) -> str:
    if not text or ("$" not in text and "\\[" not in text):
        return text
    text = _DISPLAY_DOLLARS.sub(lambda m: _span(m.group(1)), text)
    text = _BRACKETS.sub(lambda m: _span(m.group(1)), text)
    return _DOLLARS.sub(
        lambda m: m.group(0) if _HEBREW.search(m.group(1)) else _span(m.group(1)), text)
