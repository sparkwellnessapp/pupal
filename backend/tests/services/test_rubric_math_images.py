r"""A typed math rubric's pictures are READ, not dropped (2026-10-29). Zero network: the reader
is faked; what is pinned is where each reading lands and what happens when counts disagree."""
from __future__ import annotations

import pytest

from app.services.docx_v3 import image_render as ir


@pytest.fixture
def fake_reader(monkeypatch):
    calls = {}

    async def read_pages(images, *, deadline_s=None, report=None, max_parallel=4, math=False,
                         embedded=False):
        calls.update(n=len(images), math=math, embedded=embedded)
        return "\n\n".join(f"=== PAGE {i + 1} ===\n[איור: גרף {i + 1}; \\(x=2\\)]"
                           for i in range(len(images))) + "\n", report

    monkeypatch.setattr(ir, "read_pages", read_pages)
    monkeypatch.setattr(ir, "_to_pil", lambda b: b)
    return calls


async def test_each_reading_takes_its_markers_place(fake_reader, monkeypatch):
    monkeypatch.setattr(ir, "docx_page_images", lambda _b: [b"1", b"2"])
    rendered = "שאלה 1\n[IMAGE: Picture 1]\nהסבר\n[IMAGE: equation]\nשאלה 2\n[IMAGE: Picture 2]"
    out = await ir._read_embedded_images(b"", rendered, ir.RenderReport(stage="docx_text", source="docx"), None)
    assert out == ("שאלה 1\n[איור: גרף 1; \\(x=2\\)]\nהסבר\n[IMAGE: equation]\n"
                   "שאלה 2\n[איור: גרף 2; \\(x=2\\)]")
    assert fake_reader == {"n": 2, "math": True, "embedded": True}


async def test_a_count_mismatch_appends_never_guesses(fake_reader, monkeypatch):
    monkeypatch.setattr(ir, "docx_page_images", lambda _b: [b"1", b"2", b"3"])
    rendered = "שאלה 1\n[IMAGE: Picture 1]"
    out = await ir._read_embedded_images(b"", rendered, ir.RenderReport(stage="docx_text", source="docx"), None)
    assert out.startswith(rendered)                       # the marker is left where it was
    assert out.count("[תמונה ") == 3 and "[איור: גרף 3" in out


def test_the_math_reader_is_math_only():
    assert ir._has_math_notation("mathematics") is True
    assert ir._has_math_notation("computer_science") is False
    assert ir._has_math_notation(None) is False
    lines = [l for l in ir.RUBRIC_READ_SYSTEM_MATH.splitlines() if l.strip()]
    assert len(lines) <= 12                                  # execution plan §4.1
    assert "\\(" in ir.RUBRIC_READ_SYSTEM_MATH and "[איור:" in ir.RUBRIC_READ_SYSTEM_MATH
