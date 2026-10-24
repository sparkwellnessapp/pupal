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
    # [036, OD-6 / D16]
    ("כהן דני", "דני כהן"),                # token order: surname-first is the same name
    ("דני   כהן", "דני כהן"),              # internal whitespace collapsed
    ("ג׳ורג׳ חביב", "ג'ורג' חביב"),          # geresh U+05F3 → apostrophe
    ("ג’ורג’ חביב", "ג'ורג' חביב"),          # typographic apostrophe → apostrophe
    ("שלום בן״ק", 'בן"ק שלום'),            # gershayim → quote (and token order)
    ("Dana LEVI", "dana levi"),
]


def test_a_geresh_is_unified_never_deleted():
    """«ג'ורג'» and «גורג» are different names; only the KEYBOARD varies."""
    assert _normalize_name("ג׳ורג׳") != _normalize_name("גורג")


def test_a_roster_collision_is_no_match():
    """Token-order independence can make two roster names one key — that is
    doubt, and the match refuses rather than picking the first (§6.3)."""
    from types import SimpleNamespace

    from app.services.batch_triage import match_student

    roster = [SimpleNamespace(id="a", full_name="דני כהן"),
              SimpleNamespace(id="b", full_name="כהן דני")]
    assert match_student("דני כהן", roster).match_confidence == "none"
    assert match_student("דני כהן", roster[:1]).student_id == "a"


@pytest.mark.parametrize("raw,expected", VECTORS)
def test_vector(raw, expected):
    assert _normalize_name(raw) == expected


def test_two_spellings_collide():
    assert _normalize_name("דָּנָה לֵוִי") == _normalize_name("דנה לוי ")
