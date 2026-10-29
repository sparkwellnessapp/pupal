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

from typing import List, Sequence, Tuple

Token = Tuple[str, str]
# A token that remembers where it came from: (kind, value, start, end) — the source
# offsets [start, end) of the characters it was read from. The quote matcher needs them
# to say WHERE in the answer a quote sits (`quote_match.match_form_at`); everything else
# reads the first two fields only.
PToken = Tuple[str, str, int, int]


def tokenize_at(body: str) -> List[PToken]:
    out: List[PToken] = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            j = i + 1
            if body[j].isascii() and body[j].isalpha():
                while j < n and body[j].isascii() and body[j].isalpha():
                    j += 1
                out.append(("cw", body[i:j], i, j))
                i = j
            else:
                out.append(("cs", body[i:i + 2], i, i + 2))
                i += 2
            continue
        out.append(("ch", c, i, i + 1))
        i += 1
    return out


def tokenize(body: str) -> List[Token]:
    return [(k, v) for k, v, _, _ in tokenize_at(body)]


def untokenize(tokens: Sequence[tuple]) -> str:
    """Join tokens back, inserting one space where a control word would otherwise
    swallow the letter after it (`\\cdot` + `x` must not become `\\cdotx`)."""
    return untokenize_at(tokens)[0]


def untokenize_at(tokens: Sequence[tuple]) -> Tuple[str, List[int], List[int]]:
    """`untokenize`, plus where every output character came from: `starts[i]` /
    `ends[i]` are the source offsets of the token that produced character i (an
    inserted separator borrows the next token's). Tokens without offsets map to -1."""
    parts: List[str] = []
    starts: List[int] = []
    ends: List[int] = []
    prev_cw = False
    for tok in tokens:
        kind, val = tok[0], tok[1]
        s, e = (tok[2], tok[3]) if len(tok) == 4 else (-1, -1)
        if prev_cw and kind == "ch" and val.isascii() and val.isalpha():
            parts.append(" ")
            starts.append(s)
            ends.append(s)
        parts.append(val)
        starts.extend([s] * len(val))
        ends.extend([e] * len(val))
        prev_cw = kind == "cw"
    return "".join(parts), starts, ends
