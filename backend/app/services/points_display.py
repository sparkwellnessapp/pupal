"""
Points, as a teacher reads them — the backend half of a cross-language rule.

The pricer speaks in exact `Decimal` strings (`"4.00"`, `"7.50"`, `"0"`) because
that is what the server computes and FREEZES, and the parity vectors are
byte-exact on it. None of that belongs on a page: nobody writes `4.00` on a
test, and `1.00 / 1` reads like a spreadsheet rather than a mark.

So the exact value travels and the DISPLAY is trimmed — **trailing zeros only,
never rounding**. `0.75` stays `0.75`, because a quarter point is a real thing
she awards; `7.50` becomes `7.5`; `4.00` becomes `4`.

⚠ THIS IS A MIRROR of `frontend/src/utils/points-display.ts::formatPoints`, and
it has to stay one: the returned exam is rendered here and PREVIEWED there, and
the whole point of the preview is that what she signs is what the student
receives. A number that reads `7.5` in the preview and `7.50` in the PDF makes
a liar of the preview. `tests/services/test_points_display.py` drives both
halves from one table.

Pure string work, no float round-trip: parsing to float to re-format is how
`0.1 + 0.2` gets onto a page.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional, Union

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")

Pointish = Union[str, Decimal, int, None]


def format_points(value: Pointish) -> str:
    """`"7.50"` -> `"7.5"`, `"4.00"` -> `"4"`, `"0.75"` -> `"0.75"`."""
    if value is None:
        return ""
    text = str(value).strip()
    if text == "":
        return ""
    # Anything unexpected (a scientific form, a stray label) passes through
    # untouched rather than mangled — showing the raw value is honest, and
    # silently reformatting something this function does not understand is not.
    if not _NUMERIC.match(text):
        return text
    if "." not in text:
        return text

    trimmed = text.rstrip("0").rstrip(".")
    # `-0.00` trims to `-0`, and a teacher reading «-0» would think something
    # was subtracted. Any all-zero result is plain zero.
    if re.match(r"^-?0*$", trimmed.replace(".", "")):
        return "0"
    return trimmed


def format_points_pair(awarded: Pointish, possible: Pointish) -> str:
    """«7.5 / 10» — the pair, both trimmed, in one place."""
    return f"{format_points(awarded)} / {format_points(possible)}"
