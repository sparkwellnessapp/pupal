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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import fitz
from bidi.algorithm import get_display

# Re-exported so the render path and the API layer name the overlay the same
# way; DEFINED in the schema that declares the field (§0.4).
from ..schemas.graded_test_draft import OVERLAY_KEY  # noqa: F401
from .math_notation import linearize as linearize_math
from .points_display import format_points, format_points_pair

logger = logging.getLogger(__name__)

# Bump when a change alters the rendered PIXELS. It is part of the cache key, so
# a bump re-renders every exam rather than serving one drawn by older code.
# [OD-2 + gap 2, 2026-09-04] BUMPED. The stamp became round and score-bearing
# and the appendix gained the total, per-scope points and Hebrew titles. Without
# this bump every already-rendered exam keeps serving the old page — the
# staleness failure the cache key exists to prevent, and the one that looks
# entirely correct to everyone who receives it (§3.5a).
# [2026-10-23] BUMPED again: multi-line paragraphs that mix Hebrew and code
# rendered with their LINES SCRAMBLED (see `_escape`). Every exam drawn by v2
# carries that defect, so every one of them must be redrawn on next request.
# [2026-10-23, later] v4: brackets inside Hebrew rendered facing the wrong way.
RENDERER_VERSION = "returned-exam-v4"

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

# [OD-2, owner-ruled 2026-09-04 — Option A] The stamp carries the SCORE, not a
# word. It used to draw «נבדק» in a 2:1 ellipse while the spec, the mockup and
# the shipped frontend all showed a ROUND stamp bearing the grade — so the
# teacher previewed one stamp and the student received a different one, which
# is the exact property the preview exists to guarantee.
#
# The geometry consequence is the point: a round stamp makes `draw_stamp`'s
# corner arithmetic identical to the frontend's `stampBox`, which had to assume
# a square box of side `w`. The two renderers now agree by construction rather
# than by a pinned divergence test.
_STAMP_ROTATION_DEG = 7
CORNERS = ("tl", "tr", "bl", "br")
_STAMP_FALLBACK_WORD = "נבדק"   # only when no score is available
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

# The type size of every appendix element, in ONE place: the CSS sets them and
# `_wrap_logical` measures with them. Two copies would drift, and a wrap
# measured at the wrong size lets Story re-wrap a line — reintroducing the
# scrambled order `_escape` exists to prevent. Story's px is the PDF point
# (measured: 232.36 rendered vs 232.50 from `Font.text_length`, same string).
_SIZE = {"body": 11, "h1": 17, "h2": 13, "meta": 10, "total": 30, "pts": 11,
         "crit": 10, "foot": 9}


def _css() -> str:
    return f"""
@font-face {{ font-family: {FONT_FAMILY}; src: url({FONT_FILE}); }}
* {{ font-family: {FONT_FAMILY}; }}
body {{ direction: rtl; text-align: right; font-size: {_SIZE["body"]}px; color: #16181d; }}
h1 {{ font-size: {_SIZE["h1"]}px; margin: 0 0 4px; }}
h2 {{ font-size: {_SIZE["h2"]}px; margin: 14px 0 4px; }}
p  {{ margin: 0 0 6px; line-height: 1.6; }}
.meta {{ color: #5a6068; font-size: {_SIZE["meta"]}px; margin-bottom: 12px; }}
.total {{ color: #C8102E; font-size: {_SIZE["total"]}px; margin: 2px 0 14px; }}
.pts {{ color: #16181d; font-size: {_SIZE["pts"]}px; margin: 0 0 4px; }}
.crit {{ color: #5a6068; font-size: {_SIZE["crit"]}px; margin: 2px 0 0 0; }}
.foot {{ color: #5a6068; font-size: {_SIZE["foot"]}px; margin-top: 18px; }}
"""


# Paired punctuation that a right-to-left run displays MIRRORED (Unicode's
# Bidi_Mirrored pairs that occur in prose). See `_bidi_for_pymupdf`.
_MIRROR = str.maketrans("()[]{}<>«»‹›", ")(][}{><»«›‹")


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

    BRACKETS INSIDE A RUN ARE UN-MIRRORED TOO (2026-10-23, renderer v4).
    `get_display` already gives every bracket its displayed (mirrored) shape,
    and PyMuPDF flips the shape of a bracket inside an RTL run again when it
    re-reverses the run, so «(שם התכונה)» came out «)שם התכונה(». A bracket
    touching code sits OUTSIDE the run and is flipped once, which is why
    «(A.Length)» was always right. Cancelling the second flip in advance is
    the same move this function already makes for character order. Measured
    against a render, pinned by the bracket cases in the glyph-order test.
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
        # reversed AND un-mirrored: PyMuPDF will redo both (see the docstring)
        out.extend("".join(reversed(chars[i:last_rtl + 1])).translate(_MIRROR))
        # trailing neutrals stay put
        out.extend(chars[last_rtl + 1:j])
        i = j
    return "".join(out)


# The text column the Story actually fills: `render_appendix_pdf`'s `where`
# less MuPDF's default 1em body margin on each side (MEASURED: in the 50–545 box
# at 11px, text spans x 61–534), less a 2% belt for shaping. A line measured as
# fitting must never be re-wrapped by Story — that would put one word on a line
# of its own, and a test pins that the engine's line count equals ours.
_COLUMN_PT = (_A4.width - 2 * _MARGIN - 2 * _SIZE["body"]) * 0.98
_font_cache: List[fitz.Font] = []


def _measure(text: str, size: float) -> float:
    if not _font_cache:
        _font_cache.append(fitz.Font(fontfile=str(FONT_DIR / FONT_FILE)))
    return _font_cache[0].text_length(text, fontsize=size)


def _wrap_logical(text: str, size: float, width: float = _COLUMN_PT) -> List[str]:
    """Break `text` into lines in LOGICAL (reading) order, each fitting `width`.

    Greedy on spaces, as HTML would; whitespace collapses exactly as the HTML
    did before. A single token wider than the column (a long code expression)
    is cut by characters rather than allowed to overflow, because an
    overflowing line is one Story would wrap itself — out of order.
    """
    lines: List[str] = []
    current = ""
    for word in str(text or "").split():
        candidate = f"{current} {word}" if current else word
        if current and _measure(candidate, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
        while _measure(current, size) > width and len(current) > 1:
            cut = len(current) - 1
            while cut > 1 and _measure(current[:cut], size) > width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    lines.append(current)
    return lines


def _escape(text: str, size: float, base_dir: str = "R") -> str:
    """The ONE text boundary into the appendix HTML: wrap, reorder, escape.

    WRAP FIRST, IN LOGICAL ORDER, THEN REORDER EACH LINE (2026-10-23). The
    Bidirectional Algorithm reorders per LINE, after line breaking (UAX #9,
    L1-L4). This used to reorder the whole paragraph as one line and let Story
    wrap the visual string — so in any paragraph that wrapped AND mixed Hebrew
    with code, the end of the paragraph landed on the first line and the lines
    came out scrambled. A pure-Hebrew paragraph hid it (its transform is the
    identity), and the glyph-order guard only ever rendered one-line text.
    Every CS feedback paragraph mixes the two. Each line is now reordered on
    its own and the lines are joined with explicit breaks, in reading order.

    Escaping last: escaping first would turn `i < n` into `i &lt; n` and hand
    the bidi pass four Latin letters of markup to reason about; this way the
    algorithm sees the text the reader sees, and the entity is re-decoded by
    the HTML parser afterwards.
    """
    # Mathematics first (OD-M10): PyMuPDF cannot run KaTeX, so a LaTeX span in
    # feedback or a note is linearised to Unicode (`1/e`, `√e`, `x²`) and wrapped
    # LTR so a coordinate pair cannot reverse. Identity on text with no span.
    text = linearize_math(str(text or ""))
    return "<br/>".join(
        _bidi_for_pymupdf(line, base_dir).replace("&", "&amp;")
        .replace("<", "&lt;").replace(">", "&gt;")
        for line in _wrap_logical(text, size))


def render_appendix_pdf(student_name: str,
                        scopes: Sequence["AppendixScope"],
                        summary: Optional[str],
                        include_criteria: bool,
                        total: Optional[str] = None,
                        possible: Optional[str] = None) -> bytes:
    """The feedback pages, paginated.

    CONTENT AND ORDER mirror `AppendixPage.tsx` — header, red total, then per
    scope its Hebrew title, its points, the optional breakdown and the feedback,
    then «סיכום» and the footer. Until 2026-09-04 this page carried NO total and
    NO per-scope points and titled every question with the raw internal id
    («q1.א»): a student received a graded exam with no grade on it.

    `total`/`possible` come from the CONTRACT and are never re-summed from
    `scopes` — the rendered scopes deliberately EXCLUDE the not-counted ones, so
    re-summing them would under-report on every «choose k of N» exam.

    Uses Story + DocumentWriter rather than a single insert_htmlbox: feedback is
    unbounded prose, and a fixed box silently TRUNCATES — dropping the pointer
    at the end, which is the part the student most needs.
    """
    parts = [f"<h1>{_escape(student_name, _SIZE['h1'])}</h1>",
             '<p class="meta">' + _escape("משוב על המבחן", _SIZE["meta"]) + '</p>']
    if total is not None:
        # The grade, in the red a teacher's pen would use. Digits are LTR, so
        # the pair is assembled and escaped as ONE line — reordering «87.5» and
        # «100» separately would place two correct numbers the wrong way round.
        # A grade with no denominator still shows the grade. Dropping the whole
        # line because `possible` is missing would leave the appendix with no
        # total while the stamp on page 1 carries one — the student would see
        # two different answers to "what did I get".
        shown = (format_points_pair(total, possible) if possible is not None
                 else format_points(total))
        parts.append('<p class="total">' + _escape(shown, _SIZE["total"], base_dir="L") + '</p>')
    for scope in scopes:
        # The TITLE is prose — «שאלה 1, סעיף א» — so it takes an RTL base, unlike
        # the raw scope id it replaced. An id is an identifier and had to read
        # identically everywhere; a sentence must read as a sentence. The digit
        # next to Hebrew is exactly the shape that exposed the half-bidi defect,
        # so this is pinned by a per-character render assertion, not an eyeball.
        parts.append('<h2>' + _escape(scope.title, _SIZE["h2"], base_dir="R") + '</h2>')
        parts.append('<p class="pts">'
                     + _escape(format_points_pair(scope.awarded, scope.possible),
                               _SIZE["pts"], base_dir="L")
                     + '</p>')
        if scope.feedback:
            parts.append(f"<p>{_escape(scope.feedback, _SIZE['body'])}</p>")
        if scope.notes:
            parts.append('<p class="crit">' + _escape("הערות המורה:", _SIZE["crit"]) + '</p>')
            for description, note in scope.notes:
                parts.append(f"<p>{_escape(f'{description}: {note}', _SIZE['body'])}</p>")
        criteria = scope.criteria
        if include_criteria and criteria:
            for description, awarded, possible in criteria:
                # one _escape over the ASSEMBLED line: reordering the parts
                # separately would place three correct fragments in the wrong
                # order, which is the defect this function exists to prevent.
                parts.append('<p class="crit">'
                             + _escape(f"{description} — {awarded}/{possible}", _SIZE["crit"])
                             + '</p>')
    if summary:
        parts.append('<h2>' + _escape("סיכום", _SIZE["h2"]) + '</h2>')
        parts.append(f"<p>{_escape(summary, _SIZE['body'])}</p>")
    parts.append('<p class="foot">' + _escape(
        "הופק על ידי Vivi. הציון נקבע על ידי המורה.", _SIZE["foot"]) + '</p>')

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
        # Truncated. Say so in the log with the page count — a silently short
        # appendix looks complete to everyone who receives it. [OD-B4] Never
        # the student's name; the caller's graded-test id is what joins it.
        logger.warning("appendix_truncated_at_page_cap pages=%d", pages)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# the whole artefact
# ---------------------------------------------------------------------------

def draw_stamp(page, corner_or_point, score: Optional[str] = None) -> None:
    """A vector stamp on page 1 — drawn, never rasterised, so it stays crisp.

    [OD-2] ROUND, and it carries the SCORE. Vector because the original page is
    the student's own scan: a raster overlay would soften their handwriting
    underneath it.

    `score` is already display-formatted (`format_points`) — trimmed, never
    rounded. `None` falls back to the historical «נבדק» word, which is what a
    caller with no contract to read can honestly say.
    """
    rect = page.rect
    w = rect.width * _STAMP_FRACTION
    # ROUND: h == w. The old 2:1 ellipse is what made the corner arithmetic
    # differ from the frontend's by w/4 vertically.
    h = w
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
    # glyphs and rendered «נבדק» as «????» — measured, on every exam, as the
    # first thing the student sees. The face stays even now the stamp usually
    # carries digits, because the fallback word is still Hebrew and because one
    # face for one stamp is one thing to get right.
    #
    # `insert_textbox` does NO bidi of its own (unlike Story), so it takes the
    # VISUAL string. A SCORE is digits — LTR — so it needs no reordering at all;
    # running it through get_display with an RTL base would be the bug this
    # comment exists to prevent.
    if score:
        text = score
        size = h * 0.34          # digits fill more of the disc than a word
    else:
        text = get_display(_STAMP_FALLBACK_WORD, base_dir="R")
        size = h * 0.30

    # SHRINK TO FIT, because `insert_textbox` does not raise when the string is
    # too wide — it returns a negative number and inserts NOTHING. Unchecked,
    # that is a stamp with no grade in it, on the one page the student looks at
    # first, failing silently. `100.25` already fills 90% of the disc at the
    # nominal size, so the headroom is one character, not a comfortable margin.
    font = fitz.Font(fontfile=str(FONT_DIR / FONT_FILE))
    usable = w * 0.82            # a chord across the disc, not its diameter
    width = font.text_length(text, fontsize=size)
    if width > usable:
        size *= usable / width

    # vertically centred in the disc: insert_textbox anchors at the box top, so
    # a full-height box would sit the glyphs against the upper rim.
    band = fitz.Rect(oval.x0, cy - size * 0.72, oval.x1, cy + size * 0.9)
    written = page.insert_textbox(
        band, text, fontname=FONT_FAMILY, fontfile=str(FONT_DIR / FONT_FILE),
        fontsize=size, color=red,
        align=fitz.TEXT_ALIGN_CENTER, morph=morph)
    if written < 0:
        # Should be unreachable after the shrink. If it ever happens the stamp
        # is blank, so say so loudly rather than hand back a page that looks
        # finished and carries no grade.
        logger.error("stamp_text_did_not_fit",
                     extra={"text": text, "fontsize": size, "shortfall": written})


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
                         include_criteria: bool,
                         score: Optional[str] = None,
                         possible: Optional[str] = None) -> bytes:
    """Original pages + stamp on page 1 + appendix pages, as ONE PDF."""
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    if doc.page_count:
        position = stamp_position or auto_stamp_position(doc[0])
        draw_stamp(doc[0], position, score)

    appendix = fitz.open(stream=render_appendix_pdf(
        student_name, scopes, summary, include_criteria,
        total=score, possible=possible), filetype="pdf")
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
    """What the ZIP will contain, and why each exclusion happened.

    TWO exclusion classes, both stated rather than silently dropped:

    - NOT APPROVED — a draft is not a grade. The teacher has not decided yet.
    - UNAVAILABLE — approved, but no document can be produced from it: the
      frozen contract will not parse, so there is nothing trustworthy to
      render. Omitted and named, never substituted with a draft render or an
      older PDF (§3.5a).

    A MISSING OR OUTDATED RENDER IS NOT AN EXCLUSION ANY MORE, and that is the
    fix. This used to read `cached_key and cached_key == current_key`, so an
    approved test that had simply never been rendered fell into the `else` and
    was reported as STALE — "edited after signing, re-approve it". Since the
    only writer of `returned_exam_key` was the single-test preview endpoint, a
    teacher who approved a batch and clicked download hit that on EVERY row:
    nothing included, and a modal telling her she had approved nothing and
    edited five tests she had not touched. Both statements false, and both
    pointing at a fix that would not have helped.

    The ZIP now renders what is missing or outdated (`returned_exam_store`), so
    a cache miss is a reason to BUILD the exam rather than to withhold it. The
    freshness guarantee is untouched: nothing outdated is ever served, because
    anything outdated is rebuilt before it ships.
    """
    included: List[ExamRow] = []
    not_approved: List[ExamRow] = []
    unavailable: List[ExamRow] = []
    for row in rows:
        if row.status != "approved":
            not_approved.append(row)
        elif row.current_key is None:
            # The key could not be computed at all — an unreadable contract.
            # We cannot prove what this document should say, so we do not ship
            # one. This is the ONLY remaining reason to exclude an approved test.
            unavailable.append(row)
        else:
            included.append(row)
    return {"included": included,
            "excluded_not_approved": not_approved,
            "excluded_unavailable": unavailable}


#: The product term, ONCE. «המבחן המוחזר» became «המבחן החתום» (ruled
#: 2026-09-14): the name has to say what makes the document trustworthy, which
#: is her signature and not the direction it travels. The suffix is a constant
#: because `unique_zip_entry_names` below slices it off by LENGTH to build a
#: dedupe stem — two spellings of it, and a collision would silently produce
#: `…_חתום_2_מוחזר.pdf` or worse, truncate a student's name.
ZIP_ENTRY_SUFFIX = "_חתום.pdf"


def zip_entry_name(batch_name: Optional[str], student_name: Optional[str]) -> str:
    """`{exam}_{student}_חתום.pdf`, NFC.

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

    return (f"{clean(batch_name, 'מבחן')}_{clean(student_name, 'ללא שם')}"
            f"{ZIP_ENTRY_SUFFIX}")




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


@dataclass(frozen=True)
class AppendixScope:
    """One question on the student's feedback page.

    A RECORD rather than a widening tuple (§0.4). The parameter used to be
    `[(scope_id, feedback, criteria)]`; adding the title and the two point
    figures would have made it a five-slot positional in which a caller can
    silently swap two strings and produce a page that is wrong and looks fine.

    Mirrors `frontend/src/utils/returned-exam.ts::AppendixScope` field for
    field — the preview and the render are two views of ONE content model, and
    that is the property the preview exists to guarantee.
    """
    scope_id: str
    title: str                    # «שאלה 1, סעיף א» — prose, not an identifier
    awarded: str                  # display-formatted (trimmed, never rounded)
    possible: str
    feedback: str
    criteria: Optional[List[tuple]] = None
    # [(criterion description, her note)] — her notes for the student, always
    # printed (they are not part of the optional breakdown).
    notes: List[tuple] = field(default_factory=list)


def scope_title_of(scope_id: str) -> str:
    """`q1.א` -> «שאלה 1, סעיף א». Mirrors the frontend's `scopeTitleOf`.

    The appendix used to print the RAW id. `q1.א` is our internal key: it means
    nothing to a student, and it is the wrong thing to put on a document they
    keep. This is the same string the teacher sees on her own screen.
    """
    question, _, sub = scope_id.partition(".")
    number = question[1:] if question[:1].lower() == "q" else question
    return f"שאלה {number}, סעיף {sub}" if sub else f"שאלה {number}"


def scopes_for_render(contract, include_criteria: bool) -> List[AppendixScope]:
    """[(scope_id, feedback_text, criteria_or_None)] from the CONTRACT.

    Excluded-by-selection scopes are omitted entirely: on a «choose k of N» the
    unchosen questions were never owed, and printing them at 0 would tell the
    student they failed something the exam told them to skip.

    A scope with no feedback still appears — with its points — because silence
    about a question she graded reads as an omission, not as «nothing to say».
    (That sentence was in this docstring while the function returned no points
    at all. The behaviour was changed to match the promise, not the other way
    round.)
    """
    block = getattr(contract, "feedback", None)
    texts = {k: v.text for k, v in ((block.scopes if block else {}) or {}).items()}

    out: List[AppendixScope] = []
    for scope in contract.scope_outcomes:
        if not getattr(scope, "counted_in_total", True):
            continue
        sid = scope_id_of(scope)
        criteria = None
        if include_criteria:
            criteria = [(t.description, format_points(t.final_points_awarded),
                         format_points(t.points_possible))
                        for t in scope.terminal_outcomes]
        out.append(AppendixScope(
            scope_id=sid,
            title=scope_title_of(sid),
            awarded=format_points(scope.final_points_awarded),
            possible=format_points(scope.points_possible),
            feedback=texts.get(sid, ""),
            criteria=criteria,
            notes=[(t.description, t.student_note) for t in scope.terminal_outcomes
                   if t.student_note]))
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
            stem = name[:-len(ZIP_ENTRY_SUFFIX)]
            name = f"{stem}_{count + 1}{ZIP_ENTRY_SUFFIX}"
        out.append(name)
    return out
