"""
Canonical key normalization for (question_number, sub_question_id) joining.

PROBLEM: scoring joins prediction to ground truth on (q_num, sub_id). Ground
truth uses Hebrew letters ("א"); nothing guarantees a VLM echoes "א" rather
than "a", "1", "אleph", "א.", or "A". Every formatting mismatch would count as
missed+extra — i.e. *label-format* noise polluting the *segmentation* metric
(coverage). Both sides of the join therefore pass through this one function.

Mapping: Hebrew ordinal letters, Latin letters, and numerals all collapse to a
canonical ordinal index rendered as the Hebrew letter (the GT convention):
    "א" / "a" / "A" / "1"  ->  "א"
    "ב" / "b" / "B" / "2"  ->  "ב"
    ...
Trailing/leading punctuation and whitespace are stripped first ("א." -> "א").

Out-of-vocabulary sub-ids (e.g. "ii", "3a") are returned stripped-but-unmapped,
so exotic labels still join when both sides agree, and surface as missed/extra
when they don't — which at that point is a real segmentation signal, not noise.

Scope: the first 10 ordinals, which covers Bagrut exam structure. Extend the
table if a fixture exceeds it. Pure; no I/O.
"""
from __future__ import annotations

# Hebrew ordinal alphabet as used in exam sub-question labels.
_HEBREW_ORDINALS = ("א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט", "י")

_PUNCT_STRIP = " \t.()[]{}:;,-—'\"׳"


def _build_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for idx, heb in enumerate(_HEBREW_ORDINALS):
        latin = chr(ord("a") + idx)
        table[heb] = heb
        table[latin] = heb            # "a" -> "א"
        table[latin.upper()] = heb    # "A" -> "א"
        table[str(idx + 1)] = heb     # "1" -> "א"
    return table


_TABLE = _build_table()

Key = tuple[int, str | None]


def normalize_sub_id(sub_id: str | None) -> str | None:
    """Collapse a sub-question label to canonical form. Pure."""
    if sub_id is None:
        return None
    stripped = sub_id.strip(_PUNCT_STRIP)
    if not stripped:
        return None
    return _TABLE.get(stripped, stripped)


def normalize_key(key: Key) -> Key:
    return (key[0], normalize_sub_id(key[1]))
