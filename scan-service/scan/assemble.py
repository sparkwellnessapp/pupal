"""
PDF assembly (§7.3) — pure: JPEG pages in, PDF bytes out.

img2pdf EMBEDS each JPEG as-is (no re-encode), and the page size is derived
from the pixel size at 200 DPI, so an A4-normalized page (1654×2339) is A4.
`nodate=True` and fixed metadata make the bytes a function of the pages alone
(SCN-4: compiling the same version twice writes the same object), and the
metadata carries no student name: the title is generic.
"""
from __future__ import annotations

from typing import Sequence

import img2pdf

from .pipeline import COMPILE_DPI

PDF_TITLE = "exam"
PDF_PRODUCER = "Vivi"


def assemble_pdf(jpegs: Sequence[bytes]) -> bytes:
    if not jpegs:
        raise ValueError("a PDF needs at least one page")
    layout = img2pdf.get_fixed_dpi_layout_fun((COMPILE_DPI, COMPILE_DPI))
    # Engine.internal, ALWAYS: img2pdf prefers pikepdf when it is importable
    # (it is — img2pdf requires it), and pikepdf writes a trailer /ID derived
    # from the clock, so two compiles a second apart differ (measured: byte 424).
    return img2pdf.convert(list(jpegs), layout_fun=layout, title=PDF_TITLE,
                           producer=PDF_PRODUCER, creator=PDF_PRODUCER, nodate=True,
                           engine=img2pdf.Engine.internal)
