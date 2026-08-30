"""
pdf_render — the ONE rasterizer. Backend-parity and contract tests.

These run against BOTH backends so the kill switch (settings.pdf_renderer) is
provably real: if poppler ever stops working, the revert path is not a revert
path. Pixel-level equality between backends is NOT asserted — it was measured
and is false (mean delta 1.3-4.3 of 255 on scanned pages); that difference is
what the k=5 transcription-eval gate covered. What IS asserted here is every
structural contract callers depend on.
"""
from __future__ import annotations

import fitz
import pytest
from PIL import Image

from app.services import pdf_render
from app.services.pdf_render import POPPLER, PYMUPDF, page_count, render_page, render_pages

BACKENDS = [PYMUPDF, POPPLER]


@pytest.fixture
def use(monkeypatch):
    def _use(backend: str):
        monkeypatch.setattr(pdf_render.settings, "pdf_renderer", backend, raising=False)
    return _use


def _pdf(n_pages: int = 3, rotation: int = 0) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100 + 60 * i), f"Page {i + 1} marker {'X' * (i + 1)}",
                         fontsize=28)
        if rotation:
            page.set_rotation(rotation)
    data = doc.tobytes()
    doc.close()
    return data


THREE_PAGE = _pdf(3)


# --- page_count: the R2 change ------------------------------------------------

def test_page_count_matches_render_count_without_rasterizing():
    for n in (1, 3, 7):
        assert page_count(_pdf(n)) == n


def test_page_count_agrees_with_rendering():
    assert page_count(THREE_PAGE) == len(render_pages(THREE_PAGE, 72))


# --- render_pages -------------------------------------------------------------

@pytest.mark.parametrize("backend", BACKENDS)
def test_render_pages_returns_one_rgb_image_per_page(backend, use):
    use(backend)
    imgs = render_pages(THREE_PAGE, 100)
    assert len(imgs) == 3
    assert all(isinstance(i, Image.Image) and i.mode == "RGB" for i in imgs)


@pytest.mark.parametrize("backend", BACKENDS)
def test_both_backends_agree_on_page_geometry(backend, use):
    """Dimensions must match across backends — the VLM's aspect ratio and the
    downstream _resize target both depend on it."""
    use(backend)
    sizes = [i.size for i in render_pages(THREE_PAGE, 100)]
    assert sizes == [(827, 1170)] * 3 or all(
        abs(w - 827) <= 2 and abs(h - 1170) <= 2 for w, h in sizes
    ), sizes


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotation_geometry_identical_across_backends(rotation, use):
    """A /Rotate page must not come out transposed under one backend only."""
    pdf = _pdf(2, rotation=rotation)
    use(PYMUPDF)
    a = [i.size for i in render_pages(pdf, 100)]
    use(POPPLER)
    b = [i.size for i in render_pages(pdf, 100)]
    assert a == b, f"rotation={rotation}: pymupdf {a} != poppler {b}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_dpi_scales_output(backend, use):
    use(backend)
    small = render_pages(THREE_PAGE, 72)[0]
    large = render_pages(THREE_PAGE, 144)[0]
    assert large.width > small.width * 1.8


# --- page ranges + render_page ------------------------------------------------

@pytest.mark.parametrize("backend", BACKENDS)
def test_render_page_matches_full_render_of_that_page(backend, use):
    """The page-proxy guarantee: single-page render == full render indexed.
    Same backend on both sides — this is what makes N page views cost N renders
    instead of N^2."""
    use(backend)
    full = render_pages(THREE_PAGE, 100)
    for n in (1, 2, 3):
        assert render_page(THREE_PAGE, n, 100).tobytes() == full[n - 1].tobytes()


@pytest.mark.parametrize("backend", BACKENDS)
def test_render_page_out_of_range_raises_value_error(backend, use):
    use(backend)
    with pytest.raises(ValueError):
        render_page(THREE_PAGE, 4, 100)


@pytest.mark.parametrize("backend", BACKENDS)
def test_page_range_is_bounded(backend, use):
    use(backend)
    assert len(render_pages(THREE_PAGE, 72, first_page=2, last_page=3)) == 2
    assert len(render_pages(THREE_PAGE, 72, first_page=2, last_page=99)) == 2


# --- failure contract ---------------------------------------------------------

@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("data", [b"", b"not a pdf at all"])
def test_corrupt_input_raises(backend, use, data):
    """Both backends must FAIL LOUDLY on unreadable input — callers wrap this in
    try/except and would otherwise silently transcribe nothing."""
    use(backend)
    with pytest.raises(Exception):
        render_pages(data, 72)


def test_unknown_backend_falls_back_to_pymupdf(use, caplog):
    use("wharrgarbl")
    assert len(render_pages(THREE_PAGE, 72)) == 3   # does not raise


# --- the delegates still work (import surfaces other code/tests patch) --------

def test_legacy_entry_points_delegate_here():
    from app.services.document_parser import pdf_to_images as a
    from app.services.handwriting_transcription_service import (
        pdf_to_images as b,
        render_pdf_page as b2,
    )
    assert len(a(THREE_PAGE, 72)) == 3
    assert len(b(THREE_PAGE, 72)) == 3
    assert b2(THREE_PAGE, 1, 72).tobytes() == a(THREE_PAGE, 72)[0].tobytes()
