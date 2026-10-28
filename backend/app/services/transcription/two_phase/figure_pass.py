"""The figure pass — what Vivi reads FROM a drawing (MATH_RENDERING_PLAN §5).

An OPTIONAL post-P1 pass, the strike check's sibling: one call per page whose P1 text holds a
`[איור N: …]` line, returning for each drawing its box on the page and a FLAT list of
features (`kind`, `as_written`, `[y, x]` point, ink colour, uncertain). Its cost follows the
figures; a page with none costs nothing. Any failure — transport, parse, budget — returns no
figures for that page and the caption line stands alone, as it did before this pass existed.

It never touches the transcription text. Its output is attached to the answer that holds the
caption line (two_phase_engine) and tied to that line by FIG-1 (services/figures.py).

THE RULE THAT FIXED DRIFT (probe v2, 10/10 on the trap page): copy each label from the
DRAWING, never from the computation beside it, even when it is the same number in another
form (`\\sqrt{e}` on the graph, `e^{1/2}` in the working). Measured cost: $0.008–0.009 per
figure page. Measured limit: the model misses an UNLABELLED drawn line while calling the
figure complete (10/10), which is why no completeness flag is kept and why a deduction in a
scope with a figure raises a review marker (plan §5, "Absence is not evidence").
"""
from __future__ import annotations

import logging
from typing import Any, List

from pydantic import ValidationError

from app.schemas.transcription import Figure, FigureFeature

log = logging.getLogger("transcription.two_phase")

FIGURE_PASS_VERSION = "fig1"

FEATURE_KINDS = [
    "vertical_asymptote", "horizontal_asymptote", "minimum", "maximum",
    "x_intercept", "y_intercept", "point", "shaded_region",
    "vertex", "side_label", "angle_label", "segment_label", "right_angle_mark",
    "axis_label", "other_label",
]

FIGURE_SCHEMA: dict = {
    "type": "object",
    "properties": {"figures": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "figure_no": {"type": "integer"},
            "kind": {"type": "string", "enum": ["function_sketch", "geometry", "other"]},
            "box_2d": {"type": "array", "items": {"type": "number"}},
            "features": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": FEATURE_KINDS},
                    "as_written": {"type": "string"},
                    "point": {"type": "array", "items": {"type": "number"}},
                    "ink": {"type": "string", "enum": ["primary", "other"]},
                    "uncertain": {"type": "boolean"},
                },
                "required": ["kind", "as_written", "point", "ink", "uncertain"],
            }},
        },
        "required": ["figure_no", "kind", "box_2d", "features"],
    }}},
    "required": ["figures"],
}

FIGURE_SYSTEM = """\
You read ONE page of a student's handwritten mathematics exam and list the marks on every \
DRAWING the transcription names (a graph, a sketch, a geometric figure). Equations, text and \
tables are not drawings.

For each named drawing, return its `figure_no` (the N of its `[איור N: …]` line) and list \
what is drawn and labelled ON it:
- `as_written`: copy each label EXACTLY as it is written ON OR BESIDE THE DRAWING, in LaTeX \
(no \\( \\) delimiters). Never take a value from the surrounding computation, even when it is \
the same number written another way: \\sqrt{e} and e^{1/2} are different, \\frac{1}{e} and \
e^{-1} are different. Never correct a label.
- Report a feature only if it is DRAWN: an asymptote only if a line is drawn, an extremum or \
intercept only if it is marked or labelled. A drawn line with no label is still a feature: \
give it `as_written` "" and its point.
- `point`: [y, x] on a 0-1000 grid of the WHOLE page, at the mark the label belongs to.
- `ink`: "other" when the mark or its label is in a different colour from the student's main \
pen (for example pink or red); otherwise "primary".
- `uncertain`: true when you cannot read the label with confidence.
- `box_2d`: [ymin, xmin, ymax, xmax] of the drawing on the same 0-1000 grid.
Output JSON only."""


def figure_user_prompt(page_number: int, caption_lines: List[str]) -> str:
    listed = "\n".join(caption_lines)
    return (f"This image is page {page_number}. Its transcription names these drawings:\n"
            f"{listed}\n"
            "Return one entry per named drawing, with its figure_no.")


def _grid(values: Any, n: int) -> List[int] | None:
    if not isinstance(values, list) or len(values) != n:
        return None
    try:
        return [max(0, min(1000, int(round(float(v))))) for v in values]
    except (TypeError, ValueError):
        return None


def parse_figures(data: dict, page_number: int, wanted: set[int]) -> List[Figure]:
    """Model JSON → validated Figures for the numbers the page actually names.

    Defensive by design: a figure numbered outside `wanted`, a duplicate number, or a malformed
    feature is DROPPED (logged), never coerced — a reading that cannot be tied to a line
    cannot be shown to the teacher next to its ink."""
    out: List[Figure] = []
    seen: set[int] = set()
    for raw in data.get("figures") or []:
        if not isinstance(raw, dict):
            continue
        try:
            no = int(raw.get("figure_no"))
        except (TypeError, ValueError):
            continue
        if no not in wanted or no in seen:
            log.info("figure_pass page %d: dropped figure_no=%s (named: %s)",
                     page_number, raw.get("figure_no"), sorted(wanted))
            continue
        feats: List[FigureFeature] = []
        for f in raw.get("features") or []:
            try:
                feats.append(FigureFeature(
                    kind=f.get("kind"), as_written=str(f.get("as_written") or "").strip(),
                    point=_grid(f.get("point"), 2), ink=f.get("ink") or "primary",
                    uncertain=bool(f.get("uncertain")), source="vivi"))
            except (ValidationError, AttributeError):
                log.info("figure_pass page %d figure %d: dropped a malformed feature", page_number, no)
        try:
            out.append(Figure(figure_no=no, page_number=page_number,
                              kind=raw.get("kind") or "other",
                              box_2d=_grid(raw.get("box_2d"), 4), features=feats))
            seen.add(no)
        except ValidationError:
            log.info("figure_pass page %d: dropped malformed figure %d", page_number, no)
    return out
