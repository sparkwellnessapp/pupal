"""
focus.py — the FOCUS PASS (MISSION_transcription_accuracy Bet 4): the pure half.

WHY. A code-heavy page is read in one pass at one resolution, and the small
Hebrew lines — a margin comment, a one-line explanation — lose. The baseline
taxonomy (2026-09-27) says HOW they lose: mostly DROPPED (a right-margin
`// הגדרת תכונות` simply absent from P1's line), then misread, then invented. A
crop gives effective resolution without paying it on the whole page, and a
reader that emits one line costs one line of output.

THE MECHANISM, three steps, one of them a model call each:
  1. LOCALIZE — the localizer sees the page and P1's text with numbered lines,
     and returns a box for every line that carries Hebrew-script handwriting,
     INCLUDING lines where P1 dropped the Hebrew (it names the line the ink
     belongs to). Boxes are Gemini-native `box_2d` [ymin, xmin, ymax, xmax] on a
     0–1000 grid.
  2. READ — the crop (from the full render, padded) plus P1's reading of that
     line go to the reader, which returns the line verbatim, errors included.
  3. SPLICE — deterministic, by line id, and it may replace only the text of the
     line it names. THE GUARD is the whole safety story: the new line must keep
     P1's skeleton (every non-whitespace character OUTSIDE the Hebrew span —
     `skeleton`) EXACTLY. A reader can therefore add or fix
     Hebrew and the `//` around it — never touch code. That is precisely the
     failure that retired the reader-flag layer (`i+2` → `i+=2`, flagging.py):
     here it is not flagged afterwards, it is unrepresentable.

OPTIONAL PASS (OD-H1, ruled): any failure, timeout or refused splice leaves P1's
line standing and the document completes. The orchestration lives in
pipeline.py beside the strike check, under the same budget belt.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

HEB_LO, HEB_HI = 0x0590, 0x05FF

# The HEBREW SPAN of a line runs from its first Hebrew character to its last,
# widened back over the comment opener (`//`, whitespace) and forward over sentence
# punctuation. Inside it a reader may change anything; OUTSIDE it — the code — not
# one non-whitespace character. (A first draft exempted comment punctuation
# anywhere in the line, which would have let a reader drop a code `;`.)
_BACK = set("/ 	")
_FWD = set("/.,:;!?- 	")    # a `/` after Hebrew is never code


def _is_heb(ch: str) -> bool:
    return HEB_LO <= ord(ch) <= HEB_HI


def has_hebrew(s: str) -> bool:
    return any(_is_heb(c) for c in s)


def skeleton(line: str) -> str:
    """What the focus pass may never change: the line's non-whitespace characters
    OUTSIDE its Hebrew span (the whole line when it has no Hebrew)."""
    idx = [i for i, c in enumerate(line) if _is_heb(c)]
    if idx:
        a, b = idx[0], idx[-1] + 1
        while a > 0 and line[a - 1] in _BACK:
            a -= 1
        while b < len(line) and line[b] in _FWD:
            b += 1
        line = line[:a] + line[b:]
    return "".join(c for c in line if not c.isspace())


def number_lines(text: str) -> str:
    """P1's page text with 1-based line ids, the key every later step uses."""
    return "\n".join(f"{i:03d}| {ln}" for i, ln in enumerate(text.split("\n"), 1))


@dataclass(frozen=True)
class Target:
    line_id: int          # 1-based, into P1's page text split on "\n"
    box: tuple[float, float, float, float]   # ymin, xmin, ymax, xmax on 0..1000


def parse_targets(raw, n_lines: int, max_targets: int) -> list[Target]:
    """Localizer output → targets. Malformed items, out-of-range ids, degenerate
    boxes and duplicate ids are DROPPED (never guessed); the first `max_targets`
    survive, in page order."""
    seen, out = set(), []
    for it in raw or []:
        if not isinstance(it, dict):
            continue
        try:
            lid = int(it.get("line_id"))
            y0, x0, y1, x1 = (float(v) for v in it.get("box_2d"))
        except (TypeError, ValueError):
            continue
        if not (1 <= lid <= n_lines) or lid in seen:
            continue
        y0, y1 = sorted((max(0.0, min(1000.0, y0)), max(0.0, min(1000.0, y1))))
        x0, x1 = sorted((max(0.0, min(1000.0, x0)), max(0.0, min(1000.0, x1))))
        if y1 - y0 < 5 or x1 - x0 < 5:
            continue
        seen.add(lid)
        out.append(Target(lid, (y0, x0, y1, x1)))
    out.sort(key=lambda t: t.line_id)
    return out[:max_targets]


def crop(image: Image.Image, box: tuple[float, float, float, float], *,
         pad_y: float = 0.6, pad_x: float = 0.04) -> Image.Image:
    """Crop a 0..1000 box from the full render. Vertical padding is RELATIVE to
    the box height (a line's ascenders and a comment written slightly above it),
    horizontal padding relative to the page width (margin notes sit off the box
    edge more often than inside it)."""
    W, H = image.size
    y0, x0, y1, x1 = box
    h = y1 - y0
    y0, y1 = y0 - pad_y * h, y1 + pad_y * h
    x0, x1 = x0 - pad_x * 1000, x1 + pad_x * 1000
    px = lambda v, n: int(round(max(0.0, min(1000.0, v)) / 1000.0 * n))  # noqa: E731
    return image.crop((px(x0, W), px(y0, H), px(x1, W), px(y1, H)))


@dataclass(frozen=True)
class Splice:
    line_id: int
    before: str
    after: str
    accepted: bool
    reason: str           # "applied" | "unchanged" | "skeleton" | "no_hebrew" | "multi_line" | "empty"


def check(before: str, after: str) -> str:
    """The splice guard. Returns "applied" or the reason it is refused."""
    after = after.rstrip("\n")
    if not after.strip():
        return "empty"
    if "\n" in after:
        return "multi_line"
    if after.strip() == before.strip():
        return "unchanged"
    if not has_hebrew(after):
        return "no_hebrew"
    if skeleton(after) != skeleton(before):
        return "skeleton"
    return "applied"


def splice(text: str, readings: dict[int, str]) -> tuple[str, list[Splice]]:
    """Replace each named line with its reading when the guard allows. Pure; line
    ids refer to `text` as given, and a splice never changes the line count, so
    ids stay valid for every other reading."""
    lines = text.split("\n")
    record = []
    for lid in sorted(readings):
        if not (1 <= lid <= len(lines)):
            continue
        before, after = lines[lid - 1], readings[lid].rstrip("\n")
        why = check(before, after)
        if why == "applied":
            # keep P1's leading indentation: layout is P1's, content is the reader's
            indent = before[: len(before) - len(before.lstrip())]
            lines[lid - 1] = indent + after.strip()
        record.append(Splice(lid, before, after, why == "applied", why))
    return "\n".join(lines), record


# --- prompts ---------------------------------------------------------------------

LOCALIZE_SYSTEM = """\
You locate handwriting on a scanned exam page.

You are given the page image and a transcription of it with numbered lines \
(`NNN| text`). Return a bounding box for EVERY line of handwriting that contains \
Hebrew-script characters: a Hebrew comment after code, a Hebrew sentence, a \
Hebrew margin note. Include Hebrew ink that the transcription MISSED: box the \
ink, and give the number of the transcribed line it belongs to (the line it is \
written beside, or the line it comments on).

For each: `line_id` = the line number; `box_2d` = [ymin, xmin, ymax, xmax] on a \
0-1000 grid over the whole page, tightly covering that whole line of handwriting \
(the code part too, when the Hebrew sits on a code line) and any Hebrew ink \
written beside it in the margin.

Skip printed text (headers, the form, a scanner watermark such as \
`נסרק עם CamScanner`), crossed-out ink, and lines with no Hebrew. \
Output JSON only."""

LOCALIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "hebrew_lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "integer"},
                    "box_2d": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["line_id", "box_2d"],
            },
        },
    },
    "required": ["hebrew_lines"],
}

READ_SYSTEM = """\
You transcribe ONE line of a student's handwritten exam, from a cropped image.

The crop is centered on the line; parts of neighbouring lines may show at its \
edges — ignore them. You are also given a first reading of the line, which may \
have dropped or misread its Hebrew.

Return the line exactly as the student wrote it: every character, errors and \
misspellings included, in logical reading order (Hebrew right-to-left as a \
Hebrew reader reads it; code left-to-right). Keep the code part exactly as in \
the first reading unless the image clearly shows otherwise. Never correct, \
complete or improve the student's words. Crossed-out ink is omitted. If the crop \
is unreadable, return the first reading unchanged. Output JSON only: \
{"line": "..."}"""

READ_SCHEMA = {
    "type": "object",
    "properties": {"line": {"type": "string"}},
    "required": ["line"],
}


def localize_user_prompt(page: int, text: str) -> str:
    return (f"Page {page}. Transcription with line numbers:\n\n"
            f"{number_lines(text)}\n\nReturn the Hebrew-bearing lines.")


def read_user_prompt(line: str) -> str:
    return f"First reading of this line:\n{line}\n\nReturn the line as written."
