"""A LaTeX math-mode tokenizer — just enough for the validator and the canonicaliser.

It is not a parser. KaTeX on the client is the authority on whether a span renders; this
module answers the structural questions a backend needs answered without a TeX engine:
are the braces balanced, which environments are used, which commands appear.

Tokens:
  ("cw", "\\frac")   a control word: backslash + letters
  ("cs", "\\,")      a control symbol: backslash + one non-letter
  ("ch", "x")        any other single character, whitespace included
"""
from __future__ import annotations

from typing import List, Tuple

Token = Tuple[str, str]


def tokenize(body: str) -> List[Token]:
    out: List[Token] = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            j = i + 1
            if body[j].isascii() and body[j].isalpha():
                while j < n and body[j].isascii() and body[j].isalpha():
                    j += 1
                out.append(("cw", body[i:j]))
                i = j
            else:
                out.append(("cs", body[i:i + 2]))
                i += 2
            continue
        out.append(("ch", c))
        i += 1
    return out


def untokenize(tokens: List[Token]) -> str:
    """Join tokens back, inserting one space where a control word would otherwise
    swallow the letter after it (`\\cdot` + `x` must not become `\\cdotx`)."""
    parts: List[str] = []
    prev_cw = False
    for kind, val in tokens:
        if prev_cw and kind == "ch" and val.isascii() and val.isalpha():
            parts.append(" ")
        parts.append(val)
        prev_cw = kind == "cw"
    return "".join(parts)
