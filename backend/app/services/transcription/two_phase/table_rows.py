"""
table_rows.py — re-join a table row the model broke across lines (MISSION Bet 2,
follow-up; behind `PipelineConfig.p1_join_split_table_rows`, default OFF).

WHY. The table convention is one row per line (prompts.py t1.4). The gemini-flash
P1 models break a line INSIDE a header cell whose ink wraps — `| x | i | if:` ↵
`(arr[i] != 1 && x % arr[i] == 0) |` — and a prompt sentence saying "never break a
line inside a row" did not stop it (Bet 2, k=3: 0/3 on itay_katav). A split row
reads as a 5-cell row plus a stray line, which the review surface cannot render as
the grid the student drew, and the scorer counts every later row as misplaced.

WHAT IT MAY DO. Only FORMAT, never ink: it joins lines with a single space and
touches nothing else — no character is added, dropped or moved in reading order.
It fires on exactly one shape: a line that OPENS a row (`| `) but does not close
it, followed within 3 lines by non-row text whose last line CLOSES the row (` |`,
never `||`, which is the logical-OR a code line can end with). Anything else is
left alone — measured as a no-op on the incumbent's (well-formed) output.
"""
from __future__ import annotations

MAX_CONTINUATION = 3


def _opens(s: str) -> bool:
    return s.startswith("| ") and not s.endswith("|")


def _closes(s: str) -> bool:
    return s.endswith(" |") and not s.endswith("||")


def _rejoin(lines: list[str], i: int) -> int | None:
    """If lines[i] opens a row that a later line (within MAX_CONTINUATION) closes,
    with only non-row text between them, return the closing line's index."""
    if not _opens(lines[i].strip()):
        return None
    for j in range(i + 1, min(len(lines), i + 1 + MAX_CONTINUATION)):
        t = lines[j].strip()
        if not t or t.startswith("|"):
            return None
        if _closes(t):
            return j
    return None


def join_split_rows(text: str) -> str:
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        j = _rejoin(lines, i)
        if j is None:
            out.append(lines[i])
            i += 1
        else:
            out.append(" ".join(ln.strip() for ln in lines[i:j + 1]))
            i = j + 1
    return "\n".join(out)


# --- the table RE-READ splice (recommendation #1, 2026-09-28) -----------------------
# The gemini-flash P1 reads Hebrew better than the incumbent but draws table GRIDS
# worse (row splits, a nearby marker absorbed as a column); the incumbent's tables
# were shape-perfect. So a page whose P1 text holds a table is re-read by the table
# model, and ONLY its table blocks are swapped in — everything else on the page
# stays the P1 model's. Refusal is the default: no table, or a different number of
# tables in the two readings, and the page is left exactly as P1 wrote it.

def table_blocks(text: str) -> list[tuple[int, int]]:
    """(first, last) line indexes of each table: a run of row lines (stripped text
    starts with `|`) spanning >= 2 lines — INCLUDING the continuation of a row the
    model broke across lines (the `_rejoin` shape), because those split tables are
    exactly the ones the re-read exists to replace."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        j = i
        while True:
            k = _rejoin(lines, j)
            if k is not None:
                j = k
            if j + 1 < len(lines) and lines[j + 1].strip().startswith("|"):
                j += 1
                continue
            break
        if j > i:
            out.append((i, j))
        i = j + 1
    return out


def replace_tables(text: str, donor: str) -> tuple[str, str]:
    """Swap each table block of `text` for the donor's block at the same index.
    Returns (new_text, reason): "applied" | "no_table" | "count_mismatch"."""
    mine, theirs = table_blocks(text), table_blocks(donor)
    if not mine:
        return text, "no_table"
    if len(mine) != len(theirs):
        return text, "count_mismatch"
    lines, dl = text.split("\n"), donor.split("\n")
    for (a, b), (c, d) in reversed(list(zip(mine, theirs))):
        lines[a:b + 1] = dl[c:d + 1]
    return "\n".join(lines), "applied"
