"""Where the mathematics is in an answer string (MATH_RENDERING_PLAN §4).

Under a profile with the `math_notation` modality, P1 writes every piece of mathematics
between `\\(` and `\\)` and everything else — Hebrew words, units, section markers — outside.
This module finds those spans. It is the ONE definition of a span in the backend; the
frontend's `utils/math-spans.ts` is its mirror, pinned to the same vectors
(`tests/fixtures/math_spans_vectors.json`).

THE ANSWER STRING STAYS THE ONLY TRUTH. A span is a pair of offsets into it, never a
second copy, so every consumer (validator, canonicaliser, linearisation, the review
surface's span editor) reads and writes the same bytes.

Rules, chosen to be unambiguous rather than clever:
  * `\\(` opens and the next `\\)` closes. Spans do not nest.
  * A `\\)` with no open span is stray; a `\\(` with no close runs to the end of the
    string and is UNCLOSED. Both are reported, and the text in them is kept as text —
    a span that cannot be delimited is never guessed into one.
  * An escaped backslash is not a delimiter: `\\\\(` is a line break followed by `(`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple

OPEN = "\\("
CLOSE = "\\)"


@dataclass(frozen=True)
class Segment:
    """One run of the answer. `start`/`end` cover the delimiters of a math segment;
    `body_start`/`body_end` cover what is between them. For text they coincide."""
    kind: Literal["text", "math"]
    start: int
    end: int
    body_start: int
    body_end: int

    def body(self, text: str) -> str:
        return text[self.body_start:self.body_end]


@dataclass(frozen=True)
class SplitResult:
    segments: Tuple[Segment, ...]
    unclosed_at: Tuple[int, ...]     # offsets of a `\(` that never closed
    stray_close_at: Tuple[int, ...]  # offsets of a `\)` with no open span


def _delimiters(text: str) -> List[Tuple[int, str]]:
    """Every `\\(` / `\\)` in the text, skipping an escaped backslash pair."""
    out: List[Tuple[int, str]] = []
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] != "\\":
            i += 1
            continue
        nxt = text[i + 1]
        if nxt == "\\":          # `\\` is one escaped backslash — never a delimiter
            i += 2
            continue
        if nxt == "(":
            out.append((i, OPEN))
        elif nxt == ")":
            out.append((i, CLOSE))
        i += 2
    return out


def split_math(text: str) -> SplitResult:
    segments: List[Segment] = []
    unclosed: List[int] = []
    stray: List[int] = []
    cursor = 0
    open_at = -1
    for at, kind in _delimiters(text):
        if kind == OPEN:
            if open_at != -1:
                # `\(` inside an open span: the first open never closed where it should.
                # Keep it as text up to here and restart — the validator reports it.
                unclosed.append(open_at)
                open_at = at
                continue
            open_at = at
        else:
            if open_at == -1:
                stray.append(at)
                continue
            if open_at > cursor:
                segments.append(Segment("text", cursor, open_at, cursor, open_at))
            segments.append(Segment("math", open_at, at + 2, open_at + 2, at))
            cursor = at + 2
            open_at = -1
    if open_at != -1:
        unclosed.append(open_at)
    if cursor < len(text):
        segments.append(Segment("text", cursor, len(text), cursor, len(text)))
    return SplitResult(tuple(segments), tuple(unclosed), tuple(stray))


def has_math(text: str) -> bool:
    return any(s.kind == "math" for s in split_math(text or "").segments)


def map_math_bodies(text: str, fn) -> str:
    """Rebuild `text` with `fn(body)` applied to every math span's body, the
    delimiters and all text kept byte-for-byte."""
    parts: List[str] = []
    for seg in split_math(text).segments:
        if seg.kind == "math":
            parts.append(OPEN + fn(seg.body(text)) + CLOSE)
        else:
            parts.append(text[seg.start:seg.end])
    return "".join(parts)
