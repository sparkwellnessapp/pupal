"""
pdf_render.py — THE PDF rasterization implementation. One concept, one place.

WHY THIS EXISTS (2026-08-19): `pdf_render` was the largest stage in a
transcription — median 30.8s/doc across 76 eval records, more than the P1 model
call, the strike-check pass and P2 combined. The cost was never the pixels: it
was `pdf2image`'s architecture, which spawns a Poppler SUBPROCESS per call and
serialises every page through PPM/PNG pipes for Python to re-decode. Measured on
the eval fixtures (27 pages): Poppler 82.8s vs PyMuPDF 4.6s — 18x, with a
library already pinned in requirements.txt.

Three independent copies of `pdf_to_images` existed in live code
(`document_parser`, `handwriting_transcription_service`, plus a single-page
`render_pdf_page`). They now all delegate here, so there is exactly one
rasterizer and the page-proxy's byte-equality guarantee against the full render
(tests/api/test_transcription_page_render.py) holds by construction rather than
by coincidence.

BACKEND SELECTION is a kill switch, not a preference: `settings.pdf_renderer`
("pymupdf" | "poppler"). Poppler stays installed in the Docker image and stays
reachable by config so a production revert is one env var and no redeploy. The
backends are NOT pixel-identical (measured: mean delta 1.3-4.3 of 255, 2-7% of
pixels differing by >16 on stroke edges), which is why the switch to pymupdf was
gated on a k=5 transcription-eval non-inferiority run rather than on the latency
argument alone.
"""
from __future__ import annotations

import logging
from typing import List

from PIL import Image

from ..config import settings

logger = logging.getLogger(__name__)

POPPLER = "poppler"
PYMUPDF = "pymupdf"


def _backend() -> str:
    """Resolved once per call so the flag can be flipped without a restart."""
    choice = (getattr(settings, "pdf_renderer", PYMUPDF) or PYMUPDF).strip().lower()
    if choice not in (POPPLER, PYMUPDF):
        logger.warning("Unknown PDF_RENDERER=%r; falling back to %s", choice, PYMUPDF)
        return PYMUPDF
    return choice


# --- page count -------------------------------------------------------------

def page_count(pdf_bytes: bytes) -> int:
    """Number of pages WITHOUT rasterizing anything.

    Callers previously rendered the whole document at a low DPI just to take
    `len()` of the result (transcribe_one), which paid seconds for a number the
    PDF header already carries.
    """
    import fitz

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


# --- rasterization ----------------------------------------------------------

def _render_pymupdf(
    pdf_bytes: bytes, dpi: int, first_page: int | None, last_page: int | None
) -> List[Image.Image]:
    import fitz

    out: List[Image.Image] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        n = doc.page_count
        lo = 1 if first_page is None else first_page
        hi = n if last_page is None else min(last_page, n)
        if lo < 1 or lo > n:
            return []                      # matches poppler: empty, caller decides
        for idx in range(lo - 1, hi):
            # csRGB + alpha=False pins the sample layout at 3 channels, so the
            # PIL mode is never inferred from a variable `pm.n` (a page with
            # transparency or a CMYK colorspace would otherwise change it).
            pix = doc[idx].get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            out.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            del pix                        # release the buffer promptly under batch fan-out
    return out


def _render_poppler(
    pdf_bytes: bytes, dpi: int, first_page: int | None, last_page: int | None
) -> List[Image.Image]:
    from pdf2image import convert_from_bytes

    kwargs = {}
    if first_page is not None:
        kwargs["first_page"] = first_page
    if last_page is not None:
        kwargs["last_page"] = last_page
    return convert_from_bytes(pdf_bytes, dpi=dpi, fmt="PNG", **kwargs)


def render_pages(
    pdf_bytes: bytes,
    dpi: int = 150,
    *,
    first_page: int | None = None,
    last_page: int | None = None,
) -> List[Image.Image]:
    """Rasterize a PDF (or a 1-based inclusive page range) to RGB PIL images.

    Raises on an unreadable/corrupt document — the backends raise different
    types (fitz `FileDataError`/`EmptyFileError`, poppler `PDFPageCountError`),
    all Exception subclasses, and no call-site catches either specifically
    (verified). An out-of-range `first_page` yields an EMPTY list under both
    backends; `render_page` is what turns that into the ValueError its callers
    expect.
    """
    backend = _backend()
    fn = _render_pymupdf if backend == PYMUPDF else _render_poppler
    images = fn(pdf_bytes, dpi, first_page, last_page)
    logger.info(
        "Converted PDF to %d images at %d DPI (backend=%s%s)",
        len(images), dpi, backend,
        "" if first_page is None and last_page is None
        else f", pages {first_page}-{last_page}",
    )
    return images


def render_page(pdf_bytes: bytes, page_number: int, dpi: int = 200) -> Image.Image:
    """Rasterize ONE page (1-based). Raises ValueError when out of range.

    Rendering the whole PDF per page request made a full review of an N-page
    test cost N^2 page renders (batch-review Phase 1.5); this stays bounded to
    the requested page under both backends.
    """
    images = render_pages(pdf_bytes, dpi, first_page=page_number, last_page=page_number)
    if not images:
        raise ValueError(f"Page {page_number} out of range")
    return images[0]
