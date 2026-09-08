"""The rubric-read render stage (docx_v3/image_render.py) — pure parts + stage
selection with the reader mocked. No provider is ever constructed here.

Fixtures: the real Math 4-unit DOCX (16 page images, zero text) and a CS DOCX
with text (`hobby_tvshow.docx`) from tests/rubric_eval_suite/fixtures/.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.docx_v3 import image_render as ir
from app.services.docx_v3.parser_render import render_docx_to_markdown

FIX = Path(__file__).resolve().parents[1] / "rubric_eval_suite" / "fixtures"
MATH4 = FIX / "Math_rubrics" / "4 יחל מבחן ומחוון.docx"
MATH4_PDF = FIX / "Math_rubrics" / "4 יחל מבחן ומחוון.pdf"
HOBBY = FIX / "hobby_tvshow.docx"


def _need(p: Path):
    if not p.exists():
        pytest.skip(f"fixture missing: {p.name}")
    return p.read_bytes()


def test_docx_page_images_returns_every_page_in_document_order():
    blobs = ir.docx_page_images(_need(MATH4))
    assert len(blobs) == 16
    assert all(b[:3] == b"\xff\xd8\xff" or b[:8] == b"\x89PNG\r\n\x1a\n" for b in blobs)


def test_text_chars_ignores_placeholders():
    md = "[IMAGE: Image 1]\n\n[IMAGE: Image 2]\n\n[TEXTBOX]\nab\n[/TEXTBOX]\n"
    assert ir._text_chars(md) == 2


def test_is_pdf_by_name_or_magic():
    assert ir.is_pdf("x.PDF", b"PK\x03\x04")
    assert ir.is_pdf("x.docx", b"%PDF-1.7")
    assert not ir.is_pdf("x.docx", b"PK\x03\x04")


def test_docx_with_text_takes_the_deterministic_render_byte_identically():
    """CS byte-identity: the stage returns exactly render_docx_to_markdown's output."""
    data = _need(HOBBY)

    async def boom(*a, **k):  # the reader must NOT be called
        raise AssertionError("read_pages called on a text DOCX")

    with patch.object(ir, "read_pages", boom):
        md, rep = asyncio.run(ir.render_source(data, "hobby_tvshow.docx"))
    assert md == render_docx_to_markdown(data)
    assert rep.stage == "docx_text" and rep.source == "docx"
    assert rep.text_chars > ir.IMAGE_STAGE_TEXT_CHARS
    assert rep.omml_seen == rep.omml_rendered == 0


def test_pages_as_images_docx_triggers_the_reader():
    data = _need(MATH4)
    seen = {}

    async def fake_read(images, *, deadline_s=None, report=None, max_parallel=4):
        seen["n"] = len(images)
        report.stage = "image_read"
        report.pages_read = len(images)
        report.prompt_version = ir.RUBRIC_READ_PROMPT_VERSION
        return "=== PAGE 1 ===\nשאלה 1\n", report

    with patch.object(ir, "read_pages", fake_read):
        md, rep = asyncio.run(ir.render_source(data, "4 יחל מבחן ומחוון.docx", deadline_s=100))
    assert seen["n"] == 16
    assert md.startswith("=== PAGE 1 ===") and "שאלה 1" in md
    assert rep.stage == "image_read" and rep.image_count == 16 and rep.pages_read == 16
    assert rep.prompt_version == "rubric-read/rr1.0"


def test_pdf_always_goes_through_the_reader():
    data = _need(MATH4_PDF)
    seen = {}

    async def fake_read(images, *, deadline_s=None, report=None, max_parallel=4):
        seen["n"] = len(images)
        report.stage = "image_read"
        return "=== PAGE 1 ===\nשאלה 1\n", report

    with patch.object(ir, "read_pages", fake_read):
        md, rep = asyncio.run(ir.render_source(data, "rubric.pdf"))
    assert seen["n"] == 16
    assert rep.source == "pdf" and rep.stage == "image_read" and rep.image_count == 16


def test_render_report_logs_a_queryable_message_line(caplog):
    rep = ir.RenderReport(stage="image_read", source="pdf", pages_read=3, image_count=3)
    with caplog.at_level("INFO"):
        rep.log("job=x")
    line = next(r.message for r in caplog.records if "rubric_render" in r.message)
    assert "stage=image_read" in line and "pages_read=3" in line and "job=x" in line
