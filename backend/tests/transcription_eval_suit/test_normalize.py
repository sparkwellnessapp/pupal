"""Pure unit tests for the shared normalizer. Zero mocks; runs in `pytest -q`."""
import unicodedata

from app.services.transcription.normalize import normalize


def test_strips_all_whitespace():
    assert normalize("a b\n\tc  d", strip_illegible=False) == "abcd"


def test_lowercases():
    # Case-insensitive by design: a "While"->"while" correction must NOT be
    # rewarded/punished here (the critical-token metric catches case fidelity).
    assert normalize("While(True)", strip_illegible=False) == "while(true)"


def test_nfc_makes_canonically_equivalent_strings_equal():
    composed = "\u00e9"            # é
    decomposed = "e\u0301"         # e + combining acute
    assert composed != decomposed  # different code points...
    assert normalize(composed, strip_illegible=False) == normalize(
        decomposed, strip_illegible=False
    )  # ...but canonically equal after NFC


def test_hebrew_is_preserved_not_stripped():
    # lower() is a no-op on Hebrew; NFC composes; no whitespace -> unchanged.
    s = "שלום"
    assert normalize(s, strip_illegible=False) == unicodedata.normalize("NFC", s)


def test_illegible_strict_keeps_marker():
    assert normalize("a[?]b", strip_illegible=False) == "a[?]b"


def test_illegible_lenient_drops_marker():
    assert normalize("a[?]b", strip_illegible=True) == "ab"


def test_spaced_illegible_marker_handled_in_lenient():
    # Whitespace is stripped before the marker is removed, so "[ ? ]" collapses.
    assert normalize("a [ ? ] b", strip_illegible=True) == "ab"


def test_none_and_empty():
    assert normalize(None, strip_illegible=False) == ""
    assert normalize("", strip_illegible=True) == ""


def test_idempotent():
    s = "  If (X == 5) [?]  "
    once = normalize(s, strip_illegible=False)
    assert normalize(once, strip_illegible=False) == once
