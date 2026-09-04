"""
The returned exam — what the STUDENT receives (PR-G9).

Rendered from the CONTRACT only. A render that consulted the draft could hand
back something the teacher never froze, and she would have no way to know.

THE FONT IS VENDORED, and that is not incidental. `pymupdf-fonts` carries no
Hebrew face at all (verified: Cascadia, FiraGO, FiraMono, Noto Music/Math/
Symbols, Noto Sans *Latin*, Space Mono, Ubuntu), and without an embedded face
PyMuPDF falls back to whatever the MACHINE happens to have. On a developer
laptop that silently produces a perfect-looking page in Noto Serif Hebrew; the
Cloud Run image has no Hebrew font, so the identical code would hand every
student a page of empty boxes. `Assistant-Regular.ttf` (OFL, licence beside it)
is instanced to weight 400 and shipped in the repo — PyMuPDF ignores CSS
font-weight on a variable font and would otherwise embed ExtraLight.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import fitz
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

# Bump when a change alters the rendered PIXELS. It is part of the cache key, so
# a bump re-renders every exam rather than serving one drawn by older code.
RENDERER_VERSION = "returned-exam-v1"

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_FILE = "Assistant-Regular.ttf"
FONT_FAMILY = "assistant"

_A4 = fitz.paper_rect("a4")
_MARGIN = 50

# An unbounded `while more:` is an infinite loop inside a request handler.
# MEASURED: when the box cannot fit even one line, PyMuPDF's `place` keeps
# returning "more" forever, and the PDF grows until memory runs out. The
# real box is comfortably large, so this cap should never bind — which is
# exactly why it must exist rather than be argued away.
MAX_APPENDIX_PAGES = 40


# ---------------------------------------------------------------------------
# stamp placement
# ---------------------------------------------------------------------------

_STAMP_WORD = "נבדק"
_STAMP_ROTATION_DEG = 7
CORNERS = ("tl", "tr", "bl", "br")
_STAMP_FRACTION = 0.16      # stamp ≈ 16% of page width (spec §2 PR-G9(a))
_INSET = 0.03               # inset 3%


def stamp_corner_picker(page1_gray) -> str:
    """Which corner covers the least of the student's work.

    Takes a PIL grayscale image — Pillow is already in the image and numpy is
    not, so this uses the type we already ship (deviation from the spec's
    ndarray, deliberate and recorded).

    Ties resolve to top-left, deterministically: the same page must always
    stamp the same way, or a re-render would differ from the cached PDF.
    """
    w, h = page1_gray.size
    box_w, box_h = int(w * _STAMP_FRACTION), int(w * _STAMP_FRACTION)
    dx, dy = int(w * _INSET), int(h * _INSET)

    boxes: Dict[str, Tuple[int, int, int, int]] = {
        "tl": (dx, dy, dx + box_w, dy + box_h),
        "tr": (w - dx - box_w, dy, w - dx, dy + box_h),
        "bl": (dx, h - dy - box_h, dx + box_w, h - dy),
        "br": (w - dx - box_w, h - dy - box_h, w - dx, h - dy),
    }

    best, best_ink = "tl", None
    for corner in CORNERS:                     # fixed order ⇒ ties go to tl
        crop = page1_gray.crop(boxes[corner]).convert("L")
        # mean luminance: higher = emptier. Ink is dark.
        pixels = crop.tobytes()
        ink = 255 - (sum(pixels) / max(len(pixels), 1))
        if best_ink is None or ink < best_ink - 1e-9:
            best, best_ink = corner, ink
    return best


# ---------------------------------------------------------------------------
# cache key
# ---------------------------------------------------------------------------

def returned_exam_cache_key(contract_version: str,
                            stamp_position: Optional[dict],
                            include_criteria: bool,
                            feedback_hash: str,
                            renderer_version: str = RENDERER_VERSION) -> str:
    """Every input that can change a pixel.

    A key that misses one serves a STALE exam to a student — the worst failure
    this feature has, because the stale PDF looks entirely fine. `sort_keys`
    makes the stamp dict order-independent: two equal positions are one render.
    """
    payload = json.dumps({
        "contract_version": contract_version,
        "stamp_position": stamp_position,
        "include_criteria": bool(include_criteria),
        "feedback_hash": feedback_hash,
        "renderer_version": renderer_version,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# the appendix
# ---------------------------------------------------------------------------

def _css() -> str:
    return f"""
@font-face {{ font-family: {FONT_FAMILY}; src: url({FONT_FILE}); }}
* {{ font-family: {FONT_FAMILY}; }}
body {{ direction: rtl; text-align: right; font-size: 11px; color: #16181d; }}
h1 {{ font-size: 17px; margin: 0 0 4px; }}
h2 {{ font-size: 13px; margin: 14px 0 4px; }}
p  {{ margin: 0 0 6px; line-height: 1.6; }}
.meta {{ color: #5a6068; font-size: 10px; margin-bottom: 12px; }}
.crit {{ color: #5a6068; font-size: 10px; margin: 2px 0 0 0; }}
.foot {{ color: #5a6068; font-size: 9px; margin-top: 18px; }}
"""


def _bidi_for_pymupdf(text: str, base_dir: str = "R") -> str:
    """Make one line of mixed Hebrew/Latin read right-to-left. MEASURED, not
    assumed (2026-08-31, per-character bbox probe).

    PyMuPDF's Story does HALF the bidi algorithm: it reverses the characters
    INSIDE a directional run, but lays the runs out left-to-right in logical
    order. So a pure-Hebrew paragraph — one run — renders perfectly, which is
    exactly why this is easy to miss; add a single code token and the sentence
    reads backwards. Probe: `"AAA " + shalom` rendered `AAA <shalom-reversed>`
    where RTL demands the Hebrew on the right.

    So we run the real algorithm (`python-bidi`, already a dependency —
    requirements.txt:27) to get visual order, then flip each RTL run back,
    because PyMuPDF is about to flip it again. The two passes compose to a
    correct render, and for pure Hebrew the transform is the IDENTITY.

    Falsified alternatives, both against a render — do not retry from first
    principles: U+2066/U+2069 isolates scrambled the following Hebrew run, and
    plain `get_display()` with no flip-back came out backwards (PyMuPDF
    reversed it a second time). Known limitation: niqqud (`NSM`) travels inside
    the reversed run and would be misplaced; this content carries none.
    """
    visual = get_display(str(text or ""), base_dir=base_dir)
    chars = list(visual)
    strong_rtl = [unicodedata.bidirectional(c) in ("R", "AL", "NSM") for c in chars]
    strong_ltr = [unicodedata.bidirectional(c) in ("L", "LRE", "LRO", "LRI")
                  for c in chars]

    # An RTL run is a maximal stretch of RTL characters plus any NEUTRALS that
    # sit BETWEEN two of them — the spaces inside a Hebrew phrase belong to the
    # phrase. Splitting on them instead reverses the WORD order of pure Hebrew
    # (observed: «משוב על המבחן» → «המבחן על משוב»), which is why the run rule
    # is spelled out here rather than left to a simple character class.
    out: List[str] = []
    i, n = 0, len(chars)
    while i < n:
        if not strong_rtl[i]:
            out.append(chars[i])
            i += 1
            continue
        j = i
        last_rtl = i
        while j < n and not strong_ltr[j]:
            if strong_rtl[j]:
                last_rtl = j
            j += 1
        out.extend(reversed(chars[i:last_rtl + 1]))     # trailing neutrals stay put
        out.extend(chars[last_rtl + 1:j])
        i = j
    return "".join(out)


def _escape(text: str, base_dir: str = "R") -> str:
    """The ONE text boundary into the appendix HTML: reorder, then escape.

    Order matters. Escaping first would turn `i < n` into `i &lt; n` and hand
    the bidi pass four Latin letters of markup to reason about; this way the
    algorithm sees the text the reader sees, and the entity is re-decoded by
    the HTML parser afterwards.
    """
    reordered = _bidi_for_pymupdf(text, base_dir)
    return (reordered.replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def render_appendix_pdf(student_name: str,
                        scopes: Sequence[Tuple[str, str, Optional[List[tuple]]]],
                        summary: Optional[str],
                        include_criteria: bool) -> bytes:
    """The feedback pages, paginated.

    `scopes` is [(scope_id, feedback_text, criteria)] where criteria is an
    optional [(description, awarded, possible)] breakdown, rendered only when
    the teacher turned it on for the batch.

    Uses Story + DocumentWriter rather than a single insert_htmlbox: feedback is
    unbounded prose, and a fixed box silently TRUNCATES — dropping the pointer
    at the end, which is the part the student most needs.
    """
    parts = [f"<h1>{_escape(student_name)}</h1>",
             '<p class="meta">' + _escape("משוב על המבחן") + '</p>']
    for scope_id, text, criteria in scopes:
        # A scope id is an IDENTIFIER, not prose. Under an RTL base `q1.א`
        # resolves to `א.q1` — correct by the algorithm, and different from how
        # the same id reads in the app. An identifier must be the same string
        # everywhere the teacher and the student see it, so it gets an LTR base.
        parts.append('<h2>' + _escape(scope_id, base_dir="L") + '</h2>')
        parts.append(f"<p>{_escape(text)}</p>")
        if include_criteria and criteria:
            for description, awarded, possible in criteria:
                # one _escape over the ASSEMBLED line: reordering the parts
                # separately would place three correct fragments in the wrong
                # order, which is the defect this function exists to prevent.
                parts.append('<p class="crit">'
                             + _escape(f"{description} — {awarded}/{possible}")
                             + '</p>')
    if summary:
        parts.append('<h2>' + _escape("סיכום") + '</h2>')
        parts.append(f"<p>{_escape(summary)}</p>")
    parts.append('<p class="foot">' + _escape(
        "הופק על ידי Vivi. הציון נקבע על ידי המורה.") + '</p>')

    story = fitz.Story(html=f"<body>{''.join(parts)}</body>",
                       user_css=_css(), archive=fitz.Archive(str(FONT_DIR)))
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    where = fitz.Rect(_MARGIN, _MARGIN, _A4.x1 - _MARGIN, _A4.y1 - _MARGIN)

    more, pages = 1, 0
    while more and pages < MAX_APPENDIX_PAGES:
        device = writer.begin_page(_A4)
        more, _filled = story.place(where)
        story.draw(device)
        writer.end_page()
        pages += 1
    writer.close()
    if more:
        # Truncated. Say so in the log with the student's own page count — a
        # silently short appendix looks complete to everyone who receives it.
        logger.warning("appendix_truncated_at_page_cap",
                       extra={"student_name": student_name, "pages": pages})
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# the whole artefact
# ---------------------------------------------------------------------------

def draw_stamp(page, corner_or_point) -> None:
    """A vector stamp on page 1 — drawn, never rasterised, so it stays crisp.

    Double-stroke ellipse at a slight rotation, in the red a teacher's pen
    would use. Vector because the original page is the student's own scan: a
    raster overlay would soften their handwriting underneath it.
    """
    rect = page.rect
    w = rect.width * _STAMP_FRACTION
    h = w * 0.5
    dx, dy = rect.width * _INSET, rect.height * _INSET

    if isinstance(corner_or_point, dict) and corner_or_point.get("corner") is None \
            and corner_or_point.get("x") is not None:
        cx = rect.width * float(corner_or_point["x"])
        cy = rect.height * float(corner_or_point["y"])
    else:
        corner = (corner_or_point.get("corner") if isinstance(corner_or_point, dict)
                  else corner_or_point) or "tl"
        cx = dx + w / 2 if corner in ("tl", "bl") else rect.width - dx - w / 2
        cy = dy + h / 2 if corner in ("tl", "tr") else rect.height - dy - h / 2

    oval = fitz.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    red = (0.78, 0.11, 0.13)
    # -7 degrees, from the mockup's SVG: a stamp pressed by hand is never square
    # to the page, and a perfectly level one reads as machine output on a
    # document whose whole point is that a person checked it.
    morph = (fitz.Point(cx, cy), fitz.Matrix(-_STAMP_ROTATION_DEG))
    shape = page.new_shape()
    shape.draw_oval(oval)
    shape.draw_oval(oval + (2, 2, -2, -2))          # double stroke
    shape.finish(color=red, width=1.4, morph=morph)
    shape.commit()

    # THE VENDORED FACE, not `helv`. PyMuPDF's built-in Helvetica has no Hebrew
    # glyphs and renders «נבדק» as «????» — measured, on every exam, as the
    # first thing the student sees. And `insert_textbox` does NO bidi of its
    # own (unlike Story), so it takes the VISUAL string.
    page.insert_textbox(oval, get_display(_STAMP_WORD, base_dir="R"),
                        fontname=FONT_FAMILY, fontfile=str(FONT_DIR / FONT_FILE),
                        fontsize=h * 0.42, color=red,
                        align=fitz.TEXT_ALIGN_CENTER, morph=morph)


def auto_stamp_position(page) -> dict:
    """Where to stamp when nobody has chosen — the picker, finally in the path.

    Without this the fallback was a hardcoded top-left, which put the stamp
    over the student's work on every page whose answer starts there, and left
    `stamp_corner_picker` as dead code.

    Deterministic, and that matters for the CACHE: the corner is a pure
    function of page 1, which never changes, so an auto-placed exam re-renders
    identically and the key computed WITHOUT this corner (the manifest cannot
    see the PDF) still fully identifies the output.
    """
    from PIL import Image

    pixmap = page.get_pixmap(dpi=50, colorspace=fitz.csGRAY)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    return {"corner": stamp_corner_picker(image), "source": "auto"}


def render_returned_exam(original_pdf: bytes,
                         student_name: str,
                         scopes: Sequence[Tuple[str, str, Optional[List[tuple]]]],
                         summary: Optional[str],
                         stamp_position: Optional[dict],
                         include_criteria: bool) -> bytes:
    """Original pages + stamp on page 1 + appendix pages, as ONE PDF."""
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    if doc.page_count:
        position = stamp_position or auto_stamp_position(doc[0])
        draw_stamp(doc[0], position)

    appendix = fitz.open(stream=render_appendix_pdf(
        student_name, scopes, summary, include_criteria), filetype="pdf")
    doc.insert_pdf(appendix)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# the batch: manifest, names, «apply to all»
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExamRow:
    """One test's standing in the download decision — the fields the partition
    needs and nothing else, so the rule stays testable without a database."""
    graded_test_id: str
    student_name: Optional[str]
    status: str
    cached_key: Optional[str]
    current_key: Optional[str]


def manifest_partition(rows: Sequence[ExamRow]) -> Dict[str, List[ExamRow]]:
    """What the ZIP may contain, and why each exclusion happened.

    Two exclusion classes, both stated rather than silently dropped:

    - NOT APPROVED — a draft is not a grade. The teacher has not decided yet.
    - STALE — a PDF exists but was rendered under a different contract, stamp,
      or feedback text. Shipping it would hand the student a document the
      teacher never froze, and NOTHING on the page would reveal that. We omit
      it and say so, rather than serving a plausible wrong artefact (§3.5a).
    """
    included: List[ExamRow] = []
    not_approved: List[ExamRow] = []
    stale: List[ExamRow] = []
    for row in rows:
        if row.status != "approved":
            not_approved.append(row)
        elif row.cached_key and row.cached_key == row.current_key:
            included.append(row)
        else:
            stale.append(row)
    return {"included": included,
            "excluded_not_approved": not_approved,
            "excluded_stale": stale}


def zip_entry_name(batch_name: Optional[str], student_name: Optional[str]) -> str:
    """`{batch}_{student}_מוחזר.pdf`, NFC.

    NFC once, at the boundary: Hebrew composed one way on macOS and another on
    Linux unzips to two files that look identical and are not. Path separators
    are stripped because a student name is teacher-typed text, and an archive
    entry is a path.
    """
    def clean(value: Optional[str], fallback: str) -> str:
        text = unicodedata.normalize("NFC", (value or "").strip()) or fallback
        for bad in '/\\:*?"<>|\n\r\t':
            text = text.replace(bad, "-")
        return text[:80]

    return f"{clean(batch_name, 'מקבץ')}_{clean(student_name, 'ללא שם')}_מוחזר.pdf"


#: The overlay's ONE key. `GradedTestOverrides` is persisted under
#: `draft_json["teacher_overrides"]` (grading.py's two writers, and
#: `override_attribution` reads it correctly). Every stamp READER used
#: `"overrides"` — a key nothing has ever written — so a dragged stamp could
#: never reach the student's PDF and «apply to all» could never clear anything.
#: Both failures were silent. Named once here so the writer and the four
#: readers cannot drift apart again.
OVERLAY_KEY = "teacher_overrides"


def apply_stamp_default_to_draft(draft_json: dict) -> Tuple[dict, bool]:
    """«Apply to all»: clear the picker's guesses, keep the teacher's decisions.

    A position she DRAGGED is a decision; one the corner picker chose is a
    guess. Clearing it lets the test inherit the new batch default; clearing
    hers would be the product undoing something she did deliberately and cannot
    see it did. A position written before `source` existed counts as auto —
    there was no manual affordance then, so every one of them is picker output.

    Returns the draft and whether anything actually changed, because the
    endpoint reports a COUNT and that count must be true.
    """
    overrides = (draft_json or {}).get(OVERLAY_KEY) or {}
    position = overrides.get("stamp_position")
    if not position or position.get("source") == "manual":
        return draft_json, False

    new_overrides = {**overrides, "stamp_position": None}
    return {**draft_json, OVERLAY_KEY: new_overrides}, True


# ---------------------------------------------------------------------------
# contract -> render inputs  (the ONE place that reads a contract for this)
# ---------------------------------------------------------------------------

def scope_id_of(scope) -> str:
    """The id the teacher and the student both see. Matches the review surface;
    a returned exam that numbered questions differently would be unusable next
    to the screen she graded on."""
    sub = getattr(scope, "sub_question_id", None)
    return f"{scope.question_id}.{sub}" if sub else str(scope.question_id)


def feedback_hash(contract) -> str:
    """Every EFFECTIVE feedback string, in a stable order.

    Part of the cache key, so an edited sentence re-renders. `was_edited` is
    deliberately NOT hashed: it is provenance about the same text, and hashing
    it would re-render an identical page.
    """
    block = getattr(contract, "feedback", None)
    if block is None:
        return "none"
    items = sorted((k, v.text) for k, v in (block.scopes or {}).items())
    if block.summary is not None:
        items.append(("__summary__", block.summary.text))
    payload = json.dumps(items, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def scopes_for_render(contract, include_criteria: bool):
    """[(scope_id, feedback_text, criteria_or_None)] from the CONTRACT.

    Excluded-by-selection scopes are omitted entirely: on a «choose k of N» the
    unchosen questions were never owed, and printing them at 0 would tell the
    student they failed something the exam told them to skip.

    A scope with no feedback still appears — with its points — because silence
    about a question she graded reads as an omission, not as «nothing to say».
    """
    block = getattr(contract, "feedback", None)
    texts = {k: v.text for k, v in ((block.scopes if block else {}) or {}).items()}

    out = []
    for scope in contract.scope_outcomes:
        if not getattr(scope, "counted_in_total", True):
            continue
        sid = scope_id_of(scope)
        criteria = None
        if include_criteria:
            criteria = [(t.description, str(t.final_points_awarded),
                         str(t.points_possible)) for t in scope.terminal_outcomes]
        out.append((sid, texts.get(sid, ""), criteria))
    return out


def summary_for_render(contract) -> Optional[str]:
    block = getattr(contract, "feedback", None)
    if block is None or block.summary is None:
        return None
    return block.summary.text


def effective_stamp_position(row_position: Optional[dict],
                             batch_default: Optional[dict]) -> Optional[dict]:
    """Per-test position wins; otherwise the batch default. `apply_stamp_default_to_draft`
    clears auto positions precisely so this falls through to the new default."""
    return row_position or batch_default


def current_cache_key(contract, stamp_position: Optional[dict],
                      include_criteria: bool) -> str:
    return returned_exam_cache_key(
        contract_version=str(getattr(contract, "contract_version", "")),
        stamp_position=stamp_position,
        include_criteria=include_criteria,
        feedback_hash=feedback_hash(contract))


def gcs_object_path(graded_test_id, key: str) -> str:
    """Content-addressed by the key, so a stale render is never overwritten in
    place — the old object simply stops being referenced."""
    return f"returned_exams/{graded_test_id}/{key}.pdf"


def unique_zip_entry_names(batch_name: Optional[str],
                           student_names: Sequence[Optional[str]]) -> List[str]:
    """`zip_entry_name` per student, disambiguated.

    Two students whose names truncate to the same 80 characters — or who simply
    share a name — produce the same entry. `zipfile` writes both without
    complaint and most unzip tools keep the LAST, so one student silently
    receives another's exam and the other receives nothing, with nothing on
    either page to reveal it. A numeric suffix is ugly; handing back the wrong
    exam is worse.
    """
    seen: Dict[str, int] = {}
    out: List[str] = []
    for student in student_names:
        name = zip_entry_name(batch_name, student)
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count:
            stem = name[:-len("_מוחזר.pdf")]
            name = f"{stem}_{count + 1}_מוחזר.pdf"
        out.append(name)
    return out
