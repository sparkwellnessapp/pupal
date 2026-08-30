"""
Closeout live-E2E finding (2026-08-22): 7/10 identity passes failed under
batch load — the gemini lane (cap 5) was saturated by ~26 P1 chunks running
57-195s each, identity's 150s TOTAL timeout expired while its call was still
QUEUED (`lim.acquire`), and `extract_student_name` returned None…

…even though every fixture's filename WAS the student's name (רז כהן.pdf).

Root cause: B-25's "filename as name-plausibility fallback" was implemented
ONLY as a clause in the model prompt. When the model call never happens,
the fallback silently dies with it. These tests pin the CODE-level fallback:
the VLM path failing (timeout/transport/parse) must still yield a plausible
filename-derived suggestion — and must still yield None for scanner junk,
because a wrong suggestion is worse than none (the conservative exact-match
downstream would silently pre-seed the wrong student).
"""
import asyncio

import pytest

from app.services.transcription.identity import (
    extract_student_name,
    plausible_name_from_filename,
)


# ---------------------------------------------------------------------------
# The pure plausibility rule (zero mocks)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("רז כהן.pdf", "רז כהן"),
    ("יעל_קוגן.pdf", "יעל קוגן"),                    # underscores → spaces
    ("נועם ברינשטיין.pdf", "נועם ברינשטיין"),
    ("רוני בן עזרא.pdf", "רוני בן עזרא"),            # 3 tokens
    ("  דנה   לוי .pdf", "דנה לוי"),                 # whitespace normalized
])
def test_plausible_hebrew_names_pass(filename, expected):
    assert plausible_name_from_filename(filename) == expected


@pytest.mark.parametrize("filename", [
    None, "", "scan_007.pdf", "IMG_20260822_1544.pdf", "מסמך.pdf",
    "Scan2026-08-22.pdf", "עמוד 3.pdf", "בגרות קיץ.pdf",
    "א.pdf",                                          # single letter
    "אבגד הוזחט יכלמנ סעפצק רשתאב.pdf",              # 5 tokens — too many
    "דוח ציונים.pdf",                                 # generic words
    "test.pdf", "final_v2.pdf",
])
def test_junk_and_generic_filenames_yield_none(filename):
    assert plausible_name_from_filename(filename) is None


# ---------------------------------------------------------------------------
# The fallback FIRES when the VLM path dies (the live-E2E defect)
# ---------------------------------------------------------------------------

class _HangingProvider:
    """Simulates the starved lane: the call never returns in time."""
    async def complete(self, **kw):
        await asyncio.sleep(3600)


class _JunkProvider:
    """Provider returns unparseable output."""
    class _R:
        text = "not json at all"
    async def complete(self, **kw):
        return self._R()


@pytest.mark.asyncio
async def test_timeout_falls_back_to_plausible_filename(monkeypatch):
    monkeypatch.setattr("app.services.transcription.identity.TOTAL_TIMEOUT_S", 0.2)
    # Render never runs before the provider path — patch it cheap anyway.
    monkeypatch.setattr(
        "app.services.transcription.identity._header_b64", lambda _b: "AA==")
    name = await extract_student_name(b"%PDF-1.4", "רז כהן.pdf", _HangingProvider())
    assert name == "רז כהן"


@pytest.mark.asyncio
async def test_timeout_with_junk_filename_still_none(monkeypatch):
    monkeypatch.setattr("app.services.transcription.identity.TOTAL_TIMEOUT_S", 0.2)
    monkeypatch.setattr(
        "app.services.transcription.identity._header_b64", lambda _b: "AA==")
    name = await extract_student_name(b"%PDF-1.4", "scan_007.pdf", _HangingProvider())
    assert name is None


@pytest.mark.asyncio
async def test_parse_failure_falls_back_too(monkeypatch):
    monkeypatch.setattr(
        "app.services.transcription.identity._header_b64", lambda _b: "AA==")
    name = await extract_student_name(b"%PDF-1.4", "יעל_קוגן.pdf", _JunkProvider())
    assert name == "יעל קוגן"
