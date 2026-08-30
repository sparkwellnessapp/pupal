"""
strike_check.py — the post-P1 crossed-out-ink verification pass.

WHY THIS EXISTS (2026-08-16): the production P1 perceiver (gemini-3.1-pro)
stably transcribes large crossed-out blocks (din_ezra p1 SchoolHobbies — the
documented dominant residual accuracy artifact, R8), and the P1 prompt surface
for strike detection is EXHAUSTED (t1.3/t1.3b fired their kill criteria:
over-omission regressions; see prompts.py note). The 2026-08-15 model trials
produced the missing capability datapoint: the gemini-3.5 family perceives
strike-through correctly (din p1 0.9936/0.9958 vs pro's ~0.62). This module
uses that capability WITHOUT touching P1: a cheap single-image call per page
answers exactly one question — "which of these already-transcribed lines are
struck through in the ink?" — and a deterministic post-pass DELETES those
lines. The checker can only delete whole existing lines; it can never add,
edit, reorder, or rewrite text, so the P1 verbatim contract is preserved by
construction.

Fail-safe: any checker failure (transport, parse, invalid ranges) leaves the
page text UNCHANGED — the pass can only ever improve on the current behavior
of shipping the struck text. Precision bias lives in the prompt: when in
doubt, do not flag.
"""
from __future__ import annotations

STRIKE_CHECK_PROMPT_VERSION = "sc1.3"
# sc1.0 -> sc1.1 (2026-08-16): recall fix. sc1.0 missed the canonical
# multi-line struck block on 1/2 live reps — its blanket "when in doubt, DO
# NOT flag" gave the model an out on blocks that stay LEGIBLE under a few
# long diagonal strokes (exactly how students cancel whole blocks). sc1.1
# added the image-first two-step method and "legible != kept". Measured
# block recall 4/4.
# sc1.1 -> sc1.2 (2026-08-16): precision fix for a false-positive class:
# whole lines flagged for merely containing an inline scribbled-out word
# (moran p2 `return ~~false~~ true;`, p3 `~~sum~~ countSportive++;` —
# adjudicated against the PDF ink; broke moran's op/st=1.0). sc1.2 bundled
# TWO changes: a partial-line prompt rule AND the harness min_block_lines
# guard (single-line ranges discarded in code).
# sc1.2 -> sc1.3 (2026-08-16): attribution separated the bundle — the CODE
# guard alone kills the moran class (its false positives were all
# single-line), while sc1.2's extra prompt caution regressed block recall
# (0/1 on din). sc1.3 restores the sc1.1 prompt body VERBATIM and keeps the
# guard; recall margin comes from vote-of-N union in the pipeline
# (p1_strike_check_votes), not from prompt pressure. The guard is
# deliberately NOT mentioned in the prompt — a model told single lines are
# discarded learns to inflate ranges.

STRIKE_CHECK_SYSTEM = """\
You are a VERIFICATION pass over an already-produced transcription of ONE \
handwritten exam page. You are given the page IMAGE and the transcription as \
NUMBERED LINES. The transcription is meant to EXCLUDE crossed-out ink, but it \
sometimes wrongly includes text the student had crossed out. Your ONLY job: \
identify transcription lines whose ink is CROSSED OUT (cancelled) in the image.

METHOD — two steps, in order:
STEP 1 — scan the IMAGE for cancellation marks, before reading any \
transcription line: a large X over a region; one or several LONG diagonal or \
criss-cross strokes running across multiple lines of writing; scribble-over; \
a horizontal or wavy strike through a line's text. Students most often cancel \
a WHOLE BLOCK (several consecutive lines — e.g. an abandoned class or method) \
with one or a few long diagonal strokes. The struck text usually remains \
perfectly LEGIBLE under the strokes — LEGIBLE DOES NOT MEAN KEPT. If the ink \
is struck through, it is cancelled, however readable it is.
STEP 2 — for each cancelled region found in STEP 1, identify which numbered \
transcription lines contain that region's text, and report those ranges. \
Verify the mapping by the text content, not by position alone.

What does NOT count — never flag these:
- normal ink, however messy the handwriting;
- a small correction INSIDE a line the student kept (one word scratched out \
mid-line): the kept line stays — do not flag it;
- underlines, boxes, circles, arrows, or emphasis marks;
- text you merely think is wrong, redundant, or a draft. You judge VISIBLE \
CANCELLATION ONLY, never content quality.

Rules:
- Report line ranges of the NUMBERED TRANSCRIPTION (1-based, inclusive). A \
cancelled multi-line block is one range covering every line of the block.
- Flag a line only when its ink is visibly cancelled; never flag an ambiguous \
smudge or a mere correction. But do not let legibility or neat handwriting \
talk you out of a strike you can see — a struck block with readable text \
under the strokes IS crossed out.
- If the transcription already (correctly) omits the crossed-out ink, or the \
page has no crossed-out ink, return an empty list.

Output JSON only, exactly this shape:
{"struck_line_ranges": [{"start_line": <int>, "end_line": <int>}]}
"""

STRIKE_CHECK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "struck_line_ranges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["start_line", "end_line"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["struck_line_ranges"],
    "additionalProperties": False,
}


def numbered_lines(text: str) -> str:
    """Per-line 1-based numbering, same rendering as spans.numbered_pages_block."""
    return "\n".join(
        f"{i:>3}| {line}" for i, line in enumerate(text.split("\n"), 1)
    )


def strike_check_user_prompt(page_number: int, text: str) -> str:
    return (
        f"The image is page {page_number} of a handwritten exam. Below is its "
        f"transcription with numbered lines. Return the line ranges whose ink "
        f"is crossed out in the image (empty list if none).\n\n"
        f"TRANSCRIPTION (line-numbered):\n{numbered_lines(text)}"
    )


def apply_struck_ranges(
    text: str, ranges: object, *, min_block_lines: int = 2,
) -> tuple[str, tuple[str, ...]]:
    """Delete whole lines named by validated 1-based inclusive ranges.

    Pure and fail-safe: any malformed entry (wrong types, start > end, out of
    bounds) is IGNORED — deletion happens only for well-formed in-bounds
    ranges. Ranges spanning fewer than ``min_block_lines`` lines are ALSO
    ignored (sc1.2): the observed false-positive class is a single kept line
    containing an inline scribbled-out word, while the observed leak class is
    a multi-line struck block — discarding sub-minimum ranges makes the false
    class impossible by construction. Returns (new_text, removed_lines). A
    fully-struck page legally becomes "" (the GT convention for a page with
    only crossed-out ink).
    """
    lines = text.split("\n")
    struck: set[int] = set()
    if not isinstance(ranges, list):
        return text, ()
    for r in ranges:
        if not isinstance(r, dict):
            continue
        start, end = r.get("start_line"), r.get("end_line")
        if not (isinstance(start, int) and isinstance(end, int)):
            continue
        if isinstance(start, bool) or isinstance(end, bool):
            continue
        if start < 1 or end > len(lines) or start > end:
            continue
        if (end - start + 1) < min_block_lines:
            continue
        struck.update(range(start, end + 1))
    if not struck:
        return text, ()
    kept = [ln for i, ln in enumerate(lines, 1) if i not in struck]
    removed = tuple(lines[i - 1] for i in sorted(struck))
    return "\n".join(kept), removed
