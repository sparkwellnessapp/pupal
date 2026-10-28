"""Figure lines ↔ figure readings (MATH_RENDERING_PLAN §5). Pure, deterministic.

THE ANSWER STRING STAYS THE ONLY TRUTH. P1 writes one line per drawing,
`[איור N: <what is drawn>]`, numbered per page in reading order; the optional figure pass
returns one `Figure` per drawing with its `(page_number, figure_no)`. This module ties the
two together, and it is the ONE place that does.

**FIG-1 (FigureLineIntegrity).** In a frozen answer, every figure is attached to exactly one
figure line of that answer's text, and no line carries two figures. Enforced by the
`TranscriptionContractAnswer` type itself (a validator that calls `match_figures`), and kept
true by construction in `build_transcription_contract`, which freezes only the figures whose
line is still in the text she approved.

Deliberately ONE-directional — a refinement of the plan's wording ("every line maps to one
figure"), forced by §5's own rule that the figure pass is OPTIONAL: when it fails or times
out the line stands alone, exactly as it did before figures existed, and that must never
block approval. A line with no figure is an UNREAD drawing, recorded and surfaced; a figure
with no line is a reading of nothing, and is refused.

Matching: lines in text order; for each `[איור N:` the first unused figure numbered N, in
page order. Numbering restarts on each page, so an answer that spans two pages can hold two
«איור 1» lines — page order is what tells them apart.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

FIGURE_LINE = re.compile(r"\[איור\s*(\d+)\s*:")


@dataclass(frozen=True)
class FigureMatch:
    pairs: Tuple[Tuple[int, object], ...]      # (line index, Figure)
    unread_lines: Tuple[int, ...]              # figure lines with no reading
    orphans: Tuple[object, ...]                # figures whose line is not in the text


def figure_lines(text: str) -> List[Tuple[int, int]]:
    """(line index, N) for every figure line, in order."""
    out = []
    for i, line in enumerate((text or "").split("\n")):
        m = FIGURE_LINE.search(line)
        if m:
            out.append((i, int(m.group(1))))
    return out


def match_figures(text: str, figures: Sequence) -> FigureMatch:
    pool = sorted(figures, key=lambda f: (f.page_number, f.figure_no))
    used = [False] * len(pool)
    pairs, unread = [], []
    for idx, n in figure_lines(text):
        for j, fig in enumerate(pool):
            if not used[j] and fig.figure_no == n:
                used[j] = True
                pairs.append((idx, fig))
                break
        else:
            unread.append(idx)
    orphans = tuple(fig for j, fig in enumerate(pool) if not used[j])
    return FigureMatch(tuple(pairs), tuple(unread), orphans)


# ── what the grader reads ────────────────────────────────────────────────────

KIND_HE = {
    "vertical_asymptote": "אסימפטוטה אנכית",
    "horizontal_asymptote": "אסימפטוטה אופקית",
    "minimum": "נקודת מינימום",
    "maximum": "נקודת מקסימום",
    "x_intercept": "חיתוך עם ציר x",
    "y_intercept": "חיתוך עם ציר y",
    "point": "נקודה",
    "shaded_region": "שטח מסומן",
    "vertex": "קודקוד",
    "side_label": "צלע",
    "angle_label": "זווית",
    "segment_label": "קטע",
    "right_angle_mark": "סימון זווית ישרה",
    "axis_label": "ציר",
    "other_label": "סימון",
}


def feature_line(figure_no: int, feature) -> str:
    """One reviewed reading as one quotable line: `איור 1 · אסימפטוטה אנכית: \\(x=2\\)`."""
    label = KIND_HE.get(feature.kind, feature.kind)
    value = f" \\({feature.as_written}\\)" if feature.as_written.strip() else ""
    notes = []
    if feature.uncertain:
        notes.append("לא ודאי")
    if feature.ink == "other":
        notes.append("בצבע אחר")
    tail = f" ({', '.join(notes)})" if notes else ""
    return f"איור {figure_no} · {label}:{value}{tail}"


def expand_figure_lines(text: str, figures: Sequence) -> str:
    """The answer as the grader reads it: each figure line followed by one line per reading.

    Deterministic, so EVD-1 records exactly this text as what was graded, and the grader's
    quote of a reading is found by the ordinary quote check — "show your work" for a drawing,
    with no change to the grader (plan §5). Identity when there are no figures.
    """
    if not figures:
        return text
    by_line = {idx: fig for idx, fig in match_figures(text, figures).pairs}
    out: List[str] = []
    for i, line in enumerate(text.split("\n")):
        out.append(line)
        fig = by_line.get(i)
        if fig is not None:
            out.extend(feature_line(fig.figure_no, f) for f in fig.features)
    return "\n".join(out)
