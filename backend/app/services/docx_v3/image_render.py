"""rubric-read/rr1.0 — the image-render stage for RUBRIC pages (execution plan Phase 2a).

Two readers, two purposes (execution plan §4.6):
  * THIS module reads a TEACHER'S RUBRIC pages and may read everything on them —
    printed text, handwriting, point weights. It runs when a rubric arrives as
    page images (a scanned DOCX, any PDF).
  * P1 (`transcription/two_phase/prompts.py`) reads STUDENT pages and stays
    spec-blind. It never sees a rubric, and the student path never imports this
    module (pinned by tests/subjects/test_reader_separation.py).
They share the provider adapters, the scheduler and the page encode machinery only.

Stage selection (`render_source`):
  * `.pdf`  → rasterize with PyMuPDF (≈150 dpi) → rr1.0, always.
    # ALPHA-GAP A-6 (D-8): every PDF is rasterized; alpha adds the text-layer fast path (PyMuPDF text → the V3 chain).
  * `.docx` → `parser_render` (deterministic). If the rendered TEXT is under
    `IMAGE_STAGE_TEXT_CHARS` and the document carries ≥ 1 image, the pages are
    read with rr1.0 instead; otherwise the text render is the render, byte-for-byte
    what it was before this module existed.

Every provider call is bounded by the extraction deadline the runner passes down;
a page that fails to read becomes an empty page + a log line, never a thrown job
(§3.6 per-unit isolation) — the teacher reviews what was read.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

RUBRIC_READ_PROMPT_VERSION = "rubric-read/rr1.0"

# ≤ 12 lines (execution plan §4.1). Reads rubric pages VERBATIM; never solves.
RUBRIC_READ_SYSTEM = """\
You transcribe the pages of a TEACHER'S RUBRIC (a test and its marking scheme) VERBATIM.
Read everything on the page — printed text and handwriting — in reading order.
Keep every percentage or point weight on the SAME LINE as the step or sub-question it annotates; never move, sum, or rescale a number.
Keep question and sub-question markers exactly as written (שאלה 1, א., (1), 1.).
Write mathematics as written, linearly: powers with `^`, fractions as `(numerator)/(denominator)`, roots as `sqrt(...)`, absolute value `|x|`.
Never solve, simplify, correct, or complete anything. Do not add text that is not on the page.
At a drawing or graph, write one line `[איור: <what is drawn, labels verbatim>]` at its position.
Crossed-out text is omitted entirely.
Start the output with `=== PAGE {n} ===` on its own line, then the page text as PLAIN TEXT — no markdown, no JSON.
"""

# [math, 2026-10-29] The SAME reader for a subject with math notation, in the notation the
# student side and the OMML walker use: LaTeX in `\( … \)` spans (typeset on the rubric mirror),
# and every drawing described in full — a math rubric's graphs, functions and figures carry the
# answer key (an asymptote, an intercept, a side length). ≤ 12 lines (execution plan §4.1).
# rr2.1 (2026-10-29): each drawing line also carries its BOX on the image (`@ ymin,xmin,ymax,
# xmax`, 0–1000 — Gemini's native box_2d), so the review surface can show HER drawing, cropped
# from the source (`rubric_figures.py`), with the description beneath it.
RUBRIC_READ_MATH_PROMPT_VERSION = "rubric-read/rr2.1-math"
RUBRIC_READ_SYSTEM_MATH = r"""
You transcribe the pages of a TEACHER'S MATHEMATICS RUBRIC (a test and its marking scheme) VERBATIM.
Read everything — printed text and handwriting — in reading order. Never solve, simplify, correct or complete.
Keep every percentage or point weight on the SAME LINE as the step it annotates; never move, sum or rescale a number.
Keep question and sub-question markers exactly as written (שאלה 1, א., (1), 1.).
Write every piece of mathematics in LaTeX between \( and \), exactly in the form written: \frac{1}{e}, \sqrt{x}, x^{2},
\begin{cases} ... \end{cases} for a brace system, \boxed{...} for a framed answer. Hebrew words stay OUTSIDE the spans.
At a graph, function sketch, geometric figure or table drawn as a picture, write one line, at its position:
`[איור: <what is drawn>; <every label, value, point, intercept, asymptote, extremum, side and angle on it> @ ymin,xmin,ymax,xmax]` — the drawing's box on this image, each coordinate 0–1000.
Crossed-out text is omitted entirely. Do not add text that is not on the page.
Start the output with `=== PAGE {n} ===` on its own line, then the page text as PLAIN TEXT — no markdown, no JSON.
""".lstrip("\n")

IMAGE_STAGE_TEXT_CHARS = 200      # trigger: rendered text shorter than this AND ≥ 1 image
PDF_RASTER_DPI = 150
MAX_PARALLEL_PAGES = 4
PER_PAGE_MAX_TOKENS = 4000
PER_PAGE_TIMEOUT_S = 180.0


@dataclass
class RenderReport:
    """What the render stage did, logged per job (message string — `extra=` is never rendered)."""
    stage: str                       # "docx_text" | "image_read"
    source: str                      # "docx" | "pdf"
    text_chars: int = 0              # chars of TEXT in the deterministic render (placeholders excluded)
    image_count: int = 0
    omml_seen: int = 0
    omml_rendered: int = 0
    ole_equations: int = 0         # MathType / Equation 3 objects: unreadable, the teacher is told
    pages_read: int = 0
    pages_failed: int = 0
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None
    cost_usd: float = 0.0
    read_seconds: float = 0.0
    failed_pages: List[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def log(self, job_label: str = "") -> None:
        logger.info(
            "rubric_render stage=%s source=%s text_chars=%d images=%d omml_seen=%d omml_rendered=%d "
            "pages_read=%d pages_failed=%d prompt=%s model=%s cost_usd=%.4f read_s=%.1f %s",
            self.stage, self.source, self.text_chars, self.image_count, self.omml_seen,
            self.omml_rendered, self.pages_read, self.pages_failed, self.prompt_version,
            self.model_id, self.cost_usd, self.read_seconds, job_label,
        )


# ---------------------------------------------------------------------------
# Page images from the source document
# ---------------------------------------------------------------------------

def docx_page_images(file_bytes: bytes) -> List[bytes]:
    """Every embedded raster image of a DOCX, in DOCUMENT order (the order the
    blips are referenced from the body), as raw bytes. A scanned-pages DOCX is
    one image per page; the order IS the page order."""
    from docx import Document  # python-docx (already a dependency of parser_render)

    doc = Document(io.BytesIO(file_bytes))
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    blobs: List[bytes] = []
    seen_rids: set = set()
    for blip in doc.element.body.iter(f"{{{a_ns}}}blip"):
        rid = blip.get(f"{{{r_ns}}}embed")
        if not rid or rid in seen_rids:
            continue
        seen_rids.add(rid)
        try:
            blobs.append(doc.part.related_parts[rid].blob)
        except KeyError:
            logger.warning("rubric_render docx image rId=%s has no part; skipped", rid)
    return blobs


def pdf_page_images(pdf_bytes: bytes, dpi: int = PDF_RASTER_DPI) -> List[Image.Image]:
    """Rasterize every page of a PDF (the ONE rasterizer, `document_parser.pdf_to_images`)."""
    from ..document_parser import pdf_to_images

    return pdf_to_images(pdf_bytes, dpi)


def _to_pil(blob: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(blob))
    img.load()
    return img.convert("RGB") if img.mode not in ("RGB", "L") else img


def _text_chars(rendered: str) -> int:
    """Characters of real text in a deterministic render: placeholder lines
    (`[IMAGE: …]`, `[TEXTBOX]` wrappers) do not count."""
    kept = [
        line for line in rendered.splitlines()
        if line.strip() and not line.startswith("[IMAGE:")
        and line.strip() not in ("[TEXTBOX]", "[/TEXTBOX]")
    ]
    return len("".join(kept).strip())


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def _page_user_prompt(page_number: int, page_count: int) -> str:
    return (f"This image is page {page_number} of {page_count} of a teacher's rubric "
            f"(test + marking scheme). Transcribe it per the rules; begin with "
            f"`=== PAGE {page_number} ===`.")


def _embedded_user_prompt(index: int, count: int) -> str:
    return (f"This image ({index} of {count}) is EMBEDDED in a typed mathematics rubric — a picture of "
            f"a formula, a graph, a function sketch or a geometric figure. Transcribe it per the rules; "
            f"begin with `=== PAGE {index} ===`.")


async def read_pages(
    images: Sequence[Image.Image],
    *,
    deadline_s: Optional[float] = None,
    report: Optional[RenderReport] = None,
    max_parallel: int = MAX_PARALLEL_PAGES,
    math: bool = False,
    embedded: bool = False,
) -> Tuple[str, RenderReport]:
    """Read rubric page images with rr1.0 through the SHARED provider + scheduler
    (the same adapter instance P1 uses — one concept, one place — at doc_priority 0).

    One call per page, bounded parallel, page order preserved. A page whose call
    fails (or whose deadline is gone) is emitted as an empty page and counted in
    `pages_failed`; the job continues.
    """
    # Lazy imports keep this module import-light and keep the coupling to the
    # transcription package one-directional (the guard test checks the reverse).
    from ..transcription.two_phase.instrument import cost_usd
    from ..transcription.two_phase.pipeline import _ENCODE_POOL, _encode_pages_sync
    from ..transcription.two_phase_engine import PROD_CONFIG, _shared_infra

    rep = report or RenderReport(stage="image_read", source="unknown")
    if not embedded:
        rep.stage = "image_read"
    rep.prompt_version = RUBRIC_READ_MATH_PROMPT_VERSION if math else RUBRIC_READ_PROMPT_VERSION
    system = RUBRIC_READ_SYSTEM_MATH if math else RUBRIC_READ_SYSTEM
    user_prompt = _embedded_user_prompt if embedded else _page_user_prompt

    providers, aliased, scheduler = _shared_infra()
    key = PROD_CONFIG.p1_model_key
    provider = providers[key]
    ms = aliased[key]
    rep.model_id = ms.model_id

    t0 = time.monotonic()
    end = None if deadline_s is None else t0 + deadline_s
    loop = asyncio.get_running_loop()
    # Encode every page once (resize + JPEG/PNG + base64) off the event loop.
    b64_pages: List[str] = await loop.run_in_executor(
        _ENCODE_POOL, _encode_pages_sync, list(images), PROD_CONFIG.image_max_px,
        PROD_CONFIG.image_format, PROD_CONFIG.image_jpeg_quality, False,
    )
    sem = asyncio.Semaphore(max(1, max_parallel))
    n = len(b64_pages)
    cost = 0.0

    async def one(idx: int, b64: str) -> str:
        nonlocal cost
        page = idx + 1
        async with sem:
            remaining = float("inf") if end is None else end - time.monotonic()
            if remaining <= 5.0:
                logger.warning("rubric_render page=%d skipped: deadline exhausted", page)
                rep.pages_failed += 1
                rep.failed_pages.append(page)
                return f"=== PAGE {page} ===\n"
            timeout = min(PER_PAGE_TIMEOUT_S, remaining)

            def call():
                return provider.complete(
                    system=system,
                    user=user_prompt(page, n),
                    images_b64=[b64],
                    max_tokens=PER_PAGE_MAX_TOKENS,
                    temperature=0.0,
                    json_schema=None,
                    timeout_s=timeout,
                )

            try:
                result = await scheduler.submit(ms.provider, 0, call)
            except Exception as e:  # per-page isolation: never a thrown job
                logger.warning("rubric_render page=%d failed: %s: %s", page, type(e).__name__, e)
                rep.pages_failed += 1
                rep.failed_pages.append(page)
                return f"=== PAGE {page} ===\n"
            resp = result.response
            try:
                cost += cost_usd(resp.usage, ms.price)
            except Exception:  # pricing is bookkeeping, never a failure
                pass
            text = (resp.text or "").strip()
            if math:                       # a formula the reader left bare gets its span
                from ..math_notation.written import wrap_bare_latex
                from .rubric_figures import canonical_figure_lines
                # each drawing's box becomes the marker the surface crops from (page = image index)
                text = wrap_bare_latex(canonical_figure_lines(text, page))
            if not text.startswith("=== PAGE"):
                text = f"=== PAGE {page} ===\n{text}"
            rep.pages_read += 1
            return text

    pages_text = await asyncio.gather(*(one(i, b) for i, b in enumerate(b64_pages)))
    rep.cost_usd = round(cost, 4)
    rep.read_seconds = round(time.monotonic() - t0, 1)
    return "\n\n".join(pages_text) + "\n", rep


# ---------------------------------------------------------------------------
# Stage selection
# ---------------------------------------------------------------------------

def is_pdf(filename: Optional[str], file_bytes: bytes) -> bool:
    name = (filename or "").lower()
    return name.endswith(".pdf") or file_bytes[:5] == b"%PDF-"


async def render_source(
    file_bytes: bytes,
    filename: Optional[str] = None,
    *,
    deadline_s: Optional[float] = None,
    subject: Optional[str] = None,
) -> Tuple[str, RenderReport]:
    """The render step of rubric extraction for ANY accepted source.

    `subject` with the `math_notation` modality (2026-10-29): pages are read with the math
    reader (LaTeX spans, drawings described), and a TYPED rubric's embedded pictures — the
    graphs, sketches, figures and pasted formulas a math teacher's DOCX is mostly made of —
    are read one by one and put back where their `[IMAGE]` markers stood.

    DOCX with text → the deterministic markdown (unchanged path). DOCX that is
    pages-as-images, or any PDF → rr1.0 over the page images.
    """
    from .parser_render import render_docx_to_markdown_with_stats

    math = _has_math_notation(subject)
    if is_pdf(filename, file_bytes):
        images = pdf_page_images(file_bytes)
        rep = RenderReport(stage="image_read", source="pdf", image_count=len(images))
        return await read_pages(images, deadline_s=deadline_s, report=rep, math=math)

    rendered, stats = render_docx_to_markdown_with_stats(file_bytes)
    rep = RenderReport(
        stage="docx_text", source="docx",
        text_chars=_text_chars(rendered), image_count=stats.images_found,
        omml_seen=stats.omml_seen, omml_rendered=stats.omml_rendered,
        ole_equations=stats.ole_equations,
    )
    if rep.text_chars < IMAGE_STAGE_TEXT_CHARS and rep.image_count >= 1:
        blobs = docx_page_images(file_bytes)
        if blobs:
            images = [_to_pil(b) for b in blobs]
            rep.image_count = len(images)
            return await read_pages(images, deadline_s=deadline_s, report=rep, math=math)
        logger.warning("rubric_render docx has %d image refs but no readable image parts; "
                       "falling back to the text render", stats.images_found)
    if math and rep.image_count >= 1:
        rendered = await _read_embedded_images(file_bytes, rendered, rep, deadline_s)
    return rendered, rep


def _has_math_notation(subject: Optional[str]) -> bool:
    if not subject:
        return False
    from app.subjects import UnknownSubject, get_profile
    try:
        return "math_notation" in get_profile(subject).modalities
    except UnknownSubject:
        return False


_IMAGE_MARKER = re.compile(r"\[IMAGE: (?!equation\])[^\]]*\]")
_PAGE_HEADER = re.compile(r"^=== PAGE \d+ ===\s*", re.M)


async def _read_embedded_images(file_bytes: bytes, rendered: str, rep: RenderReport,
                                deadline_s: Optional[float]) -> str:
    """Each picture of a typed math rubric, read and put back at its `[IMAGE: …]` marker
    (document order — the order both the renderer and `docx_page_images` walk). When the
    counts disagree the readings are APPENDED, numbered, rather than guessed into place:
    nothing the teacher pasted is dropped, and nothing is moved to a wrong question."""
    blobs = docx_page_images(file_bytes)
    if not blobs:
        return rendered
    images = []
    for b in blobs:
        try:
            images.append(_to_pil(b))
        except Exception:                              # an unreadable part: skip, never fail
            logger.warning("rubric_render embedded image could not be decoded; skipped")
    if not images:
        return rendered
    text, _ = await read_pages(images, deadline_s=deadline_s, report=rep, math=True, embedded=True)
    readings = [_PAGE_HEADER.sub("", chunk).strip()
                for chunk in re.split(r"(?=^=== PAGE \d+ ===)", text, flags=re.M) if chunk.strip()]
    markers = _IMAGE_MARKER.findall(rendered)
    logger.info("rubric_render embedded images read=%d markers=%d", len(readings), len(markers))
    if readings and len(readings) == len(markers):
        it = iter(readings)
        return _IMAGE_MARKER.sub(lambda _m: next(it) or _m.group(0), rendered)
    block = "\n\n".join(f"[תמונה {i + 1} מהמסמך]\n{r}" for i, r in enumerate(readings) if r)
    return rendered + ("\n\n" + block + "\n" if block else "")
