"""
The roster-aware name reader (OD-7) — pure, and the prompt it must not disturb.
"""
import asyncio
import hashlib
from types import SimpleNamespace

from PIL import Image

from app.services.transcription import identity


def test_the_identity_pass_prompt_is_byte_identical_after_the_split():
    """`IDENTITY_SYSTEM` is now built from parts shared with the roster reader;
    the transcription pipeline must send exactly what it sent before."""
    assert hashlib.sha256(identity.IDENTITY_SYSTEM.encode()).hexdigest() == \
        "b8e7259399496ed5e5da8df93518a5a6c16c0bd480f7b390dba0af1b1ccd4712"


def test_the_roster_reader_shares_the_name_field_rules():
    assert identity._NAME_FIELD_RULES in identity.ROSTER_SYSTEM
    assert identity._NAME_FIELD_RULES in identity.IDENTITY_SYSTEM


ALIASES = {"s1": "11111111-0000-0000-0000-000000000001",
           "s2": "11111111-0000-0000-0000-000000000002"}


def test_an_alias_from_the_list_maps_back_to_the_real_id():
    r = identity.closed_world({"read_name": "דני כהן", "roster_match_id": "s2",
                               "confidence": "high"}, ALIASES)
    assert r == identity.RosterSuggestion("דני כהן", ALIASES["s2"], "high")


def test_an_id_the_model_invented_is_a_no_match_scn12():
    for bad in ("s9", ALIASES["s1"], "", None, 7):
        r = identity.closed_world({"read_name": "x", "roster_match_id": bad,
                                   "confidence": "high"}, ALIASES)
        assert r.student_id is None


def test_nothing_read_and_nothing_matched_is_always_low_confidence():
    r = identity.closed_world({"read_name": None, "roster_match_id": None,
                               "confidence": "high"}, ALIASES)
    assert r == identity.NO_SUGGESTION


class _Provider:
    def __init__(self, text=None, delay=0.0):
        self.text, self.delay, self.seen = text, delay, None

    async def complete(self, **kw):
        self.seen = kw
        await asyncio.sleep(self.delay)
        return SimpleNamespace(text=self.text)


def _page():
    return Image.new("RGB", (800, 1100), "white")


def test_the_model_sees_aliases_and_names_never_the_ids():
    p = _Provider('{"read_name": "רות", "roster_match_id": "s1", "confidence": "low"}')
    r = asyncio.run(identity.suggest_from_roster(
        _page(), [(ALIASES["s1"], "רות לוי")], p, doc_id="d", timeout_s=5))
    assert r.student_id == ALIASES["s1"]
    assert ALIASES["s1"] not in p.seen["user"] and '"s1"' in p.seen["user"]


def test_a_slow_or_garbled_model_is_no_suggestion_never_an_error():
    slow = _Provider('{"read_name": "x", "roster_match_id": "s1", "confidence": "high"}', delay=2)
    assert asyncio.run(identity.suggest_from_roster(
        _page(), [(ALIASES["s1"], "x")], slow, doc_id="d", timeout_s=0.2)) == identity.NO_SUGGESTION
    junk = _Provider("not json at all")
    assert asyncio.run(identity.suggest_from_roster(
        _page(), [], junk, doc_id="d", timeout_s=5)) == identity.NO_SUGGESTION
