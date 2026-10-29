r"""Drawings in a teacher's rubric — kept, located, and shown as HER drawing (2026-10-29).

A math rubric's questions are full of drawings: the triangle a Pythagoras question is about,
the two graphs a comparison question names «I» and «II». The math rubric reader describes
each one, but the extraction step dropped those lines, so the review surface showed the
question without the figure it is ABOUT — and the grader planned it blind.

THE MARKER (one grammar, mirrored by `frontend/src/utils/rubric-figures.ts`):

    [איור p<page> <ymin>,<xmin>,<ymax>,<xmax>: <description>]

`page` is 1-based into the SOURCE's figure images (`figure_source_images`: a PDF's pages, a
DOCX's embedded pictures — the same list the reader read); the box is Gemini's native
`box_2d` convention, each coordinate 0–1000 of that image. The description is the reader's
text (labels, values, LaTeX spans). The crop endpoint redraws the drawing from the stored
source document on demand — no second copy of her document is stored anywhere.

Three steps, each pure except the crop's decode:
  1. `canonical_figure_lines` — the reader's `[איור: … @ y0,x0,y1,x1]` → the marker (page added);
  2. the extraction keeps the lines (math extraction fragment), and `attach_orphan_figures`
     puts back any it dropped, onto the question or part it stood in (never a guess elsewhere);
  3. `crop_figure` — the PNG of that box.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional, Sequence, Tuple

FIGURE_MARKER = re.compile(r"\[איור p(\d+) (\d+),(\d+),(\d+),(\d+): ([^\n]*)\]")
_READER_LINE = re.compile(r"\[איור:\s*([^\n]*?)\s*@\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]")


def canonical_figure_lines(text: str, page: int) -> str:
    """The reader's figure lines on image `page` → the marker. A line with no box stays as
    the reader wrote it (`[איור: …]`): described, never invented a place."""
    def sub(m: "re.Match[str]") -> str:
        y0, x0, y1, x1 = (min(1000, max(0, int(v))) for v in m.groups()[1:])
        if y1 <= y0 or x1 <= x0:
            return f"[איור: {m.group(1)}]"
        return f"[איור p{page} {y0},{x0},{y1},{x1}: {m.group(1)}]"
    return _READER_LINE.sub(sub, text)


def figure_markers(text: str) -> List[str]:
    return [m.group(0) for m in FIGURE_MARKER.finditer(text or "")]


def _key(marker: str) -> Tuple[int, ...]:
    m = FIGURE_MARKER.match(marker)
    return tuple(int(m.group(i)) for i in range(1, 6)) if m else ()


# ── 2. the safety net ─────────────────────────────────────────────────────────

def _anchor(text: Optional[str]) -> Optional[str]:
    """The first words of a node's text, as they appear in the render: where it starts."""
    if not text:
        return None
    t = FIGURE_MARKER.sub("", text).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:24] if len(t) >= 8 else None


def _text_field(node) -> str:
    """A Question's text is `question_text`; a SubQuestion's is `text` (ontology_types)."""
    return "question_text" if "question_text" in type(node).model_fields else "text"


def _find(rendered_flat: str, anchor: str) -> int:
    return rendered_flat.find(anchor)


def attach_orphan_figures(response, rendered: str) -> Tuple[object, int]:
    """Every marker of the render that no extracted text kept is appended to the question
    or part whose text starts closest BEFORE it in the render. Returns (response, n
    attached). A marker with no such node is left out rather than placed on a guess."""
    markers = figure_markers(rendered)
    if not markers:
        return response, 0
    kept = set()

    def collect(node):
        for field in (_text_field(node), "example_solution"):
            kept.update(_key(m) for m in figure_markers(getattr(node, field, None) or ""))
        for sq in getattr(node, "sub_questions", None) or []:
            collect(sq)
    for q in response.questions:
        collect(q)
    # A drawing IS its place (page + box): the extraction may retouch the description's
    # spacing or LaTeX, and that must neither hide a kept drawing nor duplicate it.
    orphans = [m for m in markers if _key(m) not in kept]
    if not orphans:
        return response, 0

    flat = re.sub(r"\s+", " ", rendered)
    nodes = []          # (start offset in the render, path)

    def index(node, path):
        a = _anchor(getattr(node, _text_field(node), None))
        if a is not None:
            at = _find(flat, a)
            if at >= 0:
                nodes.append((at, path))
        for i, sq in enumerate(getattr(node, "sub_questions", None) or []):
            index(sq, path + (i,))
    for qi, q in enumerate(response.questions):
        index(q, (qi,))
    nodes.sort()

    def node_at(path):
        node = response.questions[path[0]]
        for i in path[1:]:
            node = node.sub_questions[i]
        return node

    attached = 0
    for marker in orphans:
        at = flat.find(re.sub(r"\s+", " ", marker))
        before = [p for off, p in nodes if off <= at]
        if at < 0 or not before:
            continue
        node = node_at(before[-1])
        field = _text_field(node)
        setattr(node, field, ((getattr(node, field) or "").rstrip() + "\n" + marker).strip())
        attached += 1
    return response, attached


# ── 3. the crop ───────────────────────────────────────────────────────────────

def figure_source_images(file_bytes: bytes, filename: Optional[str]):
    """The images the reader read, in its order: a PDF's pages, else a DOCX's decodable
    embedded pictures (the reader skips an undecodable one the same way)."""
    from .image_render import _to_pil, docx_page_images, is_pdf, pdf_page_images
    if is_pdf(filename, file_bytes):
        return pdf_page_images(file_bytes)
    out = []
    for blob in docx_page_images(file_bytes):
        try:
            out.append(_to_pil(blob))
        except Exception:
            continue
    return out


def crop_figure(images: Sequence, page: int, box: Tuple[int, int, int, int],
                margin: float = 0.03, max_px: int = 1400) -> Optional[bytes]:
    """The PNG of `box` (0–1000, ymin,xmin,ymax,xmax) on image `page` (1-based), with a
    small margin so a label at the edge is not cut. None when the page does not exist."""
    if page < 1 or page > len(images):
        return None
    img = images[page - 1]
    w, h = img.size
    y0, x0, y1, x1 = box
    my, mx = int(margin * h), int(margin * w)
    left, top = max(0, int(x0 / 1000 * w) - mx), max(0, int(y0 / 1000 * h) - my)
    right, bottom = min(w, int(x1 / 1000 * w) + mx), min(h, int(y1 / 1000 * h) + my)
    if right - left < 4 or bottom - top < 4:
        return None
    crop = img.crop((left, top, right, bottom))
    if max(crop.size) > max_px:
        scale = max_px / max(crop.size)
        crop = crop.resize((int(crop.size[0] * scale), int(crop.size[1] * scale)))
    buf = io.BytesIO()
    crop.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── serving ───────────────────────────────────────────────────────────────────

_IMAGE_CACHE: "dict[str, list]" = {}
_IMAGE_CACHE_ORDER: "list[str]" = []
_IMAGE_CACHE_MAX = 6


def _images_for(object_path: str, filename: Optional[str]):
    """The source's figure images, decoded once per document (a rubric has many drawings)."""
    if object_path in _IMAGE_CACHE:
        return _IMAGE_CACHE[object_path]
    from app.services.gcs_service import get_gcs_service
    images = figure_source_images(get_gcs_service().download_bytes(object_path), filename)
    _IMAGE_CACHE[object_path] = images
    _IMAGE_CACHE_ORDER.append(object_path)
    while len(_IMAGE_CACHE_ORDER) > _IMAGE_CACHE_MAX:
        _IMAGE_CACHE.pop(_IMAGE_CACHE_ORDER.pop(0), None)
    return images


def figure_png_for_job(job, page: int, box: Tuple[int, int, int, int]) -> Optional[bytes]:
    """The crop for an extraction job's source document (sync; run it in a thread)."""
    from app.services.gcs_service import get_gcs_service
    uri = job.source_gcs_uri or ""
    path = uri.removeprefix(f"gs://{get_gcs_service().bucket_name}/")
    if not path:
        return None
    return crop_figure(_images_for(path, job.source_filename), page, box)
