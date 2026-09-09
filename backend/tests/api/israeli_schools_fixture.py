"""Read the REAL Ministry school export in place, from the frontend data module.

Read IN PLACE rather than copied, following this repo's existing precedent for
cross-tree fixtures (the frontend vitest suite reads the golden rubrics straight
out of `backend/tests/rubric_eval_suite/benchmarks`). A copy would drift, and a
test that pins a stale copy of the dataset proves nothing about the dataset the
teacher actually uses.

The module is TypeScript, but the payload is a flat array of object literals with
a fixed field order, so a regex over it is honest and cheap. If the generator's
output shape ever changes, `load_schools()` returns fewer rows than expected and
`test_fixture_parses_the_whole_export` fails loudly — it does not silently test
a subset.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

DATA_FILE = (
    Path(__file__).resolve().parents[3]
    / "frontend" / "src" / "data" / "israeli-schools.ts"
)

# {id:"268029",name:"טכנולוגי הארמון חנ\"מ",city:"אבו גוש",label:"...",gradeLow:1,gradeHigh:12}
# Names contain BACKSLASH-ESCAPED quotes (500 of 2,194 rows carry a gershayim),
# so each string body is "any run of (escaped-anything | non-quote)".
_STR = r'"((?:\\.|[^"\\])*)"'
_ROW = re.compile(
    r"\{\s*id:\s*" + _STR
    + r"\s*,\s*name:\s*" + _STR
    + r"\s*,\s*city:\s*" + _STR
    + r"\s*,\s*label:\s*" + _STR
)


@dataclass(frozen=True)
class SchoolRow:
    symbol: str          # the dataset's `id` IS the Ministry symbol (סמל מוסד)
    name: str
    city: str
    label: str


def _unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\")


@lru_cache(maxsize=1)
def load_schools() -> List[SchoolRow]:
    text = DATA_FILE.read_text(encoding="utf-8")
    return [
        SchoolRow(symbol=m.group(1), name=_unescape(m.group(2)),
                  city=_unescape(m.group(3)), label=_unescape(m.group(4)))
        for m in _ROW.finditer(text)
    ]
