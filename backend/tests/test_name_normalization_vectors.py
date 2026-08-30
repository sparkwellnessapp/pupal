"""
Cross-pinned name-normalization vectors (P2/D4) — TS ⇄ PY.

The client's identity-pill dedupe (frontend/src/utils/batch-partition.ts::
normalizeName) must judge names EXACTLY like the server's auto-match
(batch_triage._normalize_name): a pill the client merges must merge on the
server too, or the identity wave's bulk-create produces surprise 409s.

Twin table: frontend/src/utils/batch-partition.test.ts (VECTORS) —
change one side, change the other (the segmentation-grammar precedent).
"""
import pytest

from app.services.batch_triage import _normalize_name

VECTORS = [
    ("  דנה לוי ", "דנה לוי"),
    ("דָּנָה לֵוִי", "דנה לוי"),          # niqqud stripped
    ("Dana Levi", "dana levi"),           # casefold
    ("נועהְ שריד", "נועה שריד"),     # combining sheva stripped
    ("אִיתַי כֹּהֵן", "איתי כהן"),
]


@pytest.mark.parametrize("raw,expected", VECTORS)
def test_vector(raw, expected):
    assert _normalize_name(raw) == expected


def test_two_spellings_collide():
    assert _normalize_name("דָּנָה לֵוִי") == _normalize_name("דנה לוי ")
