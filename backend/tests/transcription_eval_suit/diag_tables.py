"""
diag_tables.py — the TABLE diagnostic (MISSION §4.3). Additive: nothing in the
gate path reads it.

ONE PARSER, AND IT IS THE REVIEW UI'S. The convention a transcribed table must
follow is the one the teacher's review surface renders (OD-T1: use the
convention already implemented). That implementation is TypeScript —
`frontend/src/utils/detect-pipe-tables.ts`, the pipe pass of
`segmentAnswerSpans` — and the backend has no parser of its own. So this is a
line-for-line MIRROR of that pipe pass, not a second opinion about what a table
is. Agreement is not asserted by reading: `table_parser_parity.json` holds the
TS implementation's own output on every real table in the corpus plus the edge
cases, and BOTH sides are tested against it (the segmentation_check.py ↔
segmentation-check.ts precedent). If the UI's detector changes, one of the two
tests goes red.

The mirrored rules, cited to their source:
  * a candidate row contains `|` and NONE of `||` `;` `{` `}`   (CODE_TOKENS)
  * a run needs >= 2 non-separator rows, each of >= 2 cells
  * edge pipes are stripped only when EVERY row is bounded on both sides
  * short rows are padded at the END with VIRTUAL cells (they own no bytes)
  * >= 70% of cells must be <= 12 chars                         (SHORT_CELL_*)
  * a first row with no numeric cell is a header; a `|---|` settles it
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.transcription.normalize import normalize

NUMERIC_ISH = re.compile(r"^-?\d+(\.\d+)?$")
SEPARATOR_RE = re.compile(r"^\s*\|?[-\s|]+\|?\s*$")
CODE_TOKENS = ("||", ";", "{", "}")
SHORT_CELL_MAX = 12
SHORT_CELL_RATIO = 0.7


@dataclass(frozen=True)
class Table:
    rows: tuple[tuple[str, ...], ...]       # padded to the widest row
    virtual: tuple[tuple[bool, ...], ...]   # True = end-padding, owns no bytes
    has_header: bool
    first_line: int
    last_line: int

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.rows), len(self.rows[0]) if self.rows else 0)

    def as_json(self) -> dict:
        return {"rows": [list(r) for r in self.rows],
                "virtual": [list(v) for v in self.virtual],
                "hasHeader": self.has_header}


# --- the mirror of detect-pipe-tables.ts's pipe pass ------------------------------

def is_separator(line: str) -> bool:
    return "|" in line and "-" in line and SEPARATOR_RE.match(line) is not None


def is_candidate(line: str) -> bool:
    if "|" not in line:
        return False
    return not any(t in line for t in CODE_TOKENS)


def _js_trim_start_len(line: str) -> int:
    return len(line) - len(line.lstrip())


def split_cells(line: str, strip_edges: bool) -> list[str]:
    a = _js_trim_start_len(line)
    b = max(a, len(line.rstrip()))
    if strip_edges:
        if a < len(line) and line[a] == "|" and a < b:
            a += 1
        if b > a and line[b - 1] == "|":
            b -= 1
    cells, frm = [], a
    for q in range(a, b + 1):
        if q == b or line[q] == "|":
            cells.append(line[frm:q].strip())
            frm = q + 1
    return cells


def _short_ratio(rows: list[list[str]]) -> float:
    cells = [c for r in rows for c in r]
    return 0.0 if not cells else sum(len(c) <= SHORT_CELL_MAX for c in cells) / len(cells)


def _has_header(rows: list[list[str]], saw_sep: bool) -> bool:
    if len(rows) < 2:
        return False
    if saw_sep:
        return True
    first = rows[0]
    if not any(c != "" for c in first):
        return False
    return all(not NUMERIC_ISH.match(c) for c in first)


def _build(lines: list[str], frm: int, to: int) -> Table | None:
    idx = list(range(frm, to))
    saw_sep = any(is_separator(lines[i]) for i in idx)
    data = [i for i in idx if not is_separator(lines[i])]
    if len(data) < 2:
        return None
    strip = all(lines[i].strip().startswith("|") and lines[i].strip().endswith("|")
                for i in data)
    raw = [split_cells(lines[i], strip) for i in data]
    if any(len(c) < 2 for c in raw):
        return None
    cols = max(len(c) for c in raw)
    if cols < 2:
        return None
    rows = [c + [""] * (cols - len(c)) for c in raw]
    virtual = [[False] * len(c) + [True] * (cols - len(c)) for c in raw]
    if _short_ratio(rows) < SHORT_CELL_RATIO:
        return None
    return Table(tuple(tuple(r) for r in rows), tuple(tuple(v) for v in virtual),
                 _has_header(rows, saw_sep), frm, to - 1)


def parse_tables(text: str) -> list[Table]:
    """Every pipe table the review UI would render in `text`, in order."""
    lines = (text or "").split("\n")
    out, i = [], 0
    while i < len(lines):
        if is_candidate(lines[i]):
            j = i
            while j < len(lines) and is_candidate(lines[j]):
                j += 1
            if j - i >= 2:
                t = _build(lines, i, j)
                if t is not None:
                    out.append(t)
            i = j
            continue
        i += 1
    return out


def table_looking_rows_refused(text: str) -> list[str]:
    """Rows written AS table rows — they open with `|` and carry >= 2 pipes — that
    the UI refuses because they contain a CODE_TOKEN. That is the structure
    breaker a literal `||` (or a `;`, or a brace) inside a cell produces: the
    whole row stops being a table row and the grid breaks around it.

    Code that merely contains `||` (`if (a || b)`) does not open with a pipe
    and is not counted — it was never a table row."""
    return [ln for ln in (text or "").split("\n")
            if ln.lstrip().startswith("|") and ln.count("|") >= 2
            and not is_candidate(ln)]


# --- the metric ------------------------------------------------------------------

def _n(cell: str) -> str:
    return normalize(cell, strip_illegible=False)


@dataclass
class TableScore:
    expected: int = 0
    found: int = 0
    shape_exact: int = 0                   # among expected tables
    cells_total: int = 0                   # GT cells (non-virtual)
    cells_exact: int = 0
    empty_cells_gt: int = 0
    ragged_rows_pred: int = 0              # pred rows that needed end-padding
    refused_rows_pred: int = 0             # table-looking rows the UI refuses
    shape_misses: list[dict] = field(default_factory=list)
    cell_misses: list[dict] = field(default_factory=list)

    def add(self, other: "TableScore") -> None:
        for k in ("expected", "found", "shape_exact", "cells_total", "cells_exact",
                  "empty_cells_gt", "ragged_rows_pred", "refused_rows_pred"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.shape_misses += other.shape_misses
        self.cell_misses += other.cell_misses

    @property
    def shape_rate(self) -> float:
        return self.shape_exact / self.expected if self.expected else 1.0

    @property
    def cell_rate(self) -> float:
        return self.cells_exact / self.cells_total if self.cells_total else 1.0

    def as_dict(self) -> dict:
        return {
            "expected": self.expected, "found": self.found,
            "shape_exact": self.shape_exact, "shape_rate": self.shape_rate,
            "cells_total": self.cells_total, "cells_exact": self.cells_exact,
            "cell_rate": self.cell_rate, "empty_cells_gt": self.empty_cells_gt,
            "ragged_rows_pred": self.ragged_rows_pred,
            "refused_rows_pred": self.refused_rows_pred,
            "shape_misses": self.shape_misses[:20],
            "cell_misses": self.cell_misses[:40],
        }


def score_tables(gold_text: str, pred_text: str, *, where: str = "") -> TableScore:
    """Tables are matched IN ORDER (the i-th gold table with the i-th predicted
    one). A GT cell counts as exact only if the predicted table has the same
    cell at the same (row, col) and it normalizes equal — so a shape error costs
    every cell it displaces, which is the teacher's experience of it."""
    g, p = parse_tables(gold_text), parse_tables(pred_text)
    s = TableScore(expected=len(g), found=len(p))
    s.refused_rows_pred = len(table_looking_rows_refused(pred_text))
    for t in p:
        s.ragged_rows_pred += sum(1 for v in t.virtual if any(v))
    for k, gt in enumerate(g):
        pt = p[k] if k < len(p) else None
        if pt is not None and pt.shape == gt.shape:
            s.shape_exact += 1
        elif True:
            s.shape_misses.append({"where": where, "table": k, "gold": gt.shape,
                                   "pred": pt.shape if pt else None})
        for r, row in enumerate(gt.rows):
            for c, cell in enumerate(row):
                if gt.virtual[r][c]:
                    continue
                s.cells_total += 1
                if cell == "":
                    s.empty_cells_gt += 1
                got = None
                if pt is not None and r < len(pt.rows) and c < len(pt.rows[r]):
                    got = pt.rows[r][c]
                if got is not None and _n(got) == _n(cell):
                    s.cells_exact += 1
                elif len(s.cell_misses) < 40:
                    s.cell_misses.append({"where": where, "table": k, "cell": [r, c],
                                          "gold": cell, "pred": got})
    return s
