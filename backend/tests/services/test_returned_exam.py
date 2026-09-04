"""
PR-G9 — the returned exam: stamp, appendix, cache key.

The artefact the STUDENT receives. It renders from the CONTRACT only, so what
the teacher approved is exactly what is handed back — a render that consulted
the draft could show her something she never froze.
"""
import hashlib

import pytest
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# stamp-auto-corner-picks-min-ink
# ---------------------------------------------------------------------------

def _page(dark_corner=None, size=400):
    """A white page, optionally with one corner filled with ink.

    A PIL grayscale image, NOT a numpy array: Pillow is already in the Cloud Run
    image and numpy is not, so the picker takes the type we already ship rather
    than adding a heavy dependency for one function (deviation from spec §2
    PR-G9(a), recorded).
    """
    page = Image.new("L", (size, size), 255)
    if dark_corner:
        box = size // 4
        boxes = {
            "tl": (0, 0, box, box),
            "tr": (size - box, 0, size, box),
            "bl": (0, size - box, box, size),
            "br": (size - box, size - box, size, size),
        }
        ImageDraw.Draw(page).rectangle(boxes[dark_corner], fill=0)
    return page


@pytest.mark.parametrize("inked", ["tl", "tr", "bl", "br"])
def test_stamp_picks_the_emptiest_corner(inked):
    """The stamp goes where it covers the least of her student's work. Four
    candidate boxes, minimum ink wins — so a page whose top-left is full of
    writing never gets stamped over it."""
    from app.services.returned_exam import stamp_corner_picker

    chosen = stamp_corner_picker(_page(dark_corner=inked))
    assert chosen != inked, "the stamp was placed on the inkiest corner"


def test_stamp_ties_break_to_top_left():
    """A blank page has no emptiest corner. Ties resolve to top-left —
    deterministic, so the same page always stamps the same way and a re-render
    is byte-identical."""
    from app.services.returned_exam import stamp_corner_picker
    assert stamp_corner_picker(_page()) == "tl"


# ---------------------------------------------------------------------------
# returned-exam-cache-key-covers-all-inputs
# ---------------------------------------------------------------------------

def test_cache_key_changes_with_every_input_that_changes_the_pdf():
    """A cache key that misses an input serves a STALE exam to a student — the
    worst failure this feature has, because it looks fine. Every input that can
    change a pixel must move the key."""
    from app.services.returned_exam import returned_exam_cache_key

    base = dict(contract_version="c1", stamp_position={"corner": "tl"},
                include_criteria=False, feedback_hash="f1", renderer_version="r1")
    key = returned_exam_cache_key(**base)

    for field, other in (
        ("contract_version", "c2"),
        ("stamp_position", {"corner": "br"}),
        ("include_criteria", True),
        ("feedback_hash", "f2"),
        ("renderer_version", "r2"),
    ):
        assert returned_exam_cache_key(**{**base, field: other}) != key, (
            f"{field} does not move the cache key — a change to it would serve "
            f"a stale PDF")

    assert returned_exam_cache_key(**base) == key, "the key must be deterministic"


def test_cache_key_is_stable_across_dict_ordering():
    """The stamp position is a dict on the wire; two equal positions written in
    a different order are the same render and must not miss the cache."""
    from app.services.returned_exam import returned_exam_cache_key
    a = returned_exam_cache_key("c", {"x": 0.1, "y": 0.9}, False, "f", "r")
    b = returned_exam_cache_key("c", {"y": 0.9, "x": 0.1}, False, "f", "r")
    assert a == b


# ---------------------------------------------------------------------------
# appendix-has-no-notdef-glyphs
# ---------------------------------------------------------------------------

def test_appendix_embeds_a_hebrew_face_and_renders_no_notdef():
    """The tofu guard.

    `pymupdf-fonts` carries NO Hebrew face (verified: Cascadia, FiraGO,
    FiraMono, NotoMusic/Math/Symbols, NotoSans-Latin, SpaceMono, Ubuntu), and
    PyMuPDF otherwise falls back to whatever the MACHINE has. On this laptop
    that silently produced 'Noto Serif Hebrew' and looked perfect; the Cloud Run
    image has no Hebrew font, so the same code would hand every student a page
    of empty boxes.

    So the face is VENDORED and this asserts it is the one actually embedded.
    """
    from app.services.returned_exam import render_appendix_pdf

    pdf = render_appendix_pdf(
        student_name="דן",
        scopes=[("q1.א", "הגדרת נכון את מערך הצוברים.", None)],
        summary="שני דפוסים חוזרים לאורך המבחן.",
        include_criteria=False)

    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    fonts = [f[3] for page in doc for f in page.get_fonts(full=True)]
    assert any("assistant" in str(f).lower() for f in fonts), (
        f"the vendored Hebrew face is not embedded; got {fonts} — on a machine "
        f"with no Hebrew font this renders as tofu")

    # every Hebrew character survives the round trip (no .notdef substitution)
    text = "".join(page.get_text() for page in doc)
    for ch in "הגדרתנכוןמערךהצובריםשנידפוסים":
        assert ch in text, f"character {ch!r} did not render"


def test_appendix_paginates_long_feedback():
    """Feedback is unbounded prose. A single page that silently truncates would
    drop the part the student most needs — the pointer at the end."""
    from app.services.returned_exam import render_appendix_pdf

    long_text = "הגדרת נכון את מערך הצוברים וסכמת את הדירוגים לכל ערוץ. " * 60
    pdf = render_appendix_pdf(
        student_name="דן",
        scopes=[(f"q{i}", long_text, None) for i in range(6)],
        summary=long_text, include_criteria=False)

    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    assert doc.page_count > 1, "long feedback must paginate, never truncate"

    text = "".join(page.get_text() for page in doc)
    assert text.count("הגדרת") >= 60, "content was dropped instead of paginated"


# ---------------------------------------------------------------------------
# zip-approved-only-with-manifest  (the partition, pure)
# ---------------------------------------------------------------------------

def _row(name, status="approved", cached="k1", current="k1"):
    from app.services.returned_exam import ExamRow
    return ExamRow(graded_test_id=name, student_name=name, status=status,
                   cached_key=cached, current_key=current)


def test_manifest_partitions_approved_stale_and_unapproved():
    """The ZIP ships APPROVED work whose cached PDF still matches what the
    contract says today. A draft is not a grade, and a PDF rendered from a
    superseded contract is worse than a missing one — the student would receive
    a document the teacher never froze, and nothing on the page would say so."""
    from app.services.returned_exam import manifest_partition

    got = manifest_partition([
        _row("dan"),
        _row("din", status="draft"),
        _row("moran", cached="old", current="new"),
        _row("omer", cached=None),           # never rendered
    ])

    assert [r.student_name for r in got["included"]] == ["dan"]
    assert [r.student_name for r in got["excluded_not_approved"]] == ["din"]
    assert {r.student_name for r in got["excluded_stale"]} == {"moran", "omer"}


def test_zip_names_are_nfc_and_path_safe():
    """Hebrew composed differently on macOS and Linux unzips to two different
    files. NFC once, at the boundary; and a student name with a slash must not
    escape the archive."""
    from app.services.returned_exam import zip_entry_name
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "דן בסיוק")
    name = zip_entry_name("מבחן 1", decomposed)
    assert name == unicodedata.normalize("NFC", name)
    assert name.endswith("_מוחזר.pdf")

    assert "/" not in zip_entry_name("a/b", "c/d")
    assert "\\" not in zip_entry_name("a\b", "c\d")


# ---------------------------------------------------------------------------
# stamp-apply-to-batch-writes-default-not-manual-overrides
# ---------------------------------------------------------------------------

def _draft_with_stamp(position):
    """A draft overlay built the way PRODUCTION builds it.

    ⚠ These tests used to hand-write `{"overrides": {...}}`. That key is not
    what anything writes — the overlay persists under `teacher_overrides` — so
    the tests passed against a shape production never produces while every
    stamp reader in the codebase was reading a key that did not exist. A fixture
    the test constructs rather than the code under test validates nothing.
    Everything below now goes through `GradedTestOverrides` and `OVERLAY_KEY`.
    """
    import json as _json
    from app.schemas.graded_test_draft import GradedTestOverrides
    from app.services.returned_exam import OVERLAY_KEY

    overlay = GradedTestOverrides(stamp_position=position)
    return {OVERLAY_KEY: _json.loads(overlay.model_dump_json())}


def test_apply_batch_default_clears_auto_positions_but_never_manual():
    """«Apply to all» is a convenience, not an eraser. A position the teacher
    dragged herself is a decision; one the picker chose is a guess. Clearing her
    decision silently would be the product doing something she did not ask for
    and cannot see."""
    from app.schemas.graded_test_draft import StampPosition
    from app.services.returned_exam import OVERLAY_KEY, apply_stamp_default_to_draft

    after_auto, changed_auto = apply_stamp_default_to_draft(
        _draft_with_stamp(StampPosition(corner="tl", source="auto")))
    assert changed_auto is True
    assert after_auto[OVERLAY_KEY].get("stamp_position") is None

    after_manual, changed_manual = apply_stamp_default_to_draft(
        _draft_with_stamp(StampPosition(corner="br", source="manual")))
    assert changed_manual is False
    assert after_manual[OVERLAY_KEY]["stamp_position"]["corner"] == "br", (
        "the teacher's own placement was overwritten by «apply to all»")

    _, changed_none = apply_stamp_default_to_draft(_draft_with_stamp(None))
    assert changed_none is False, "nothing to clear must not count as a change"


def test_apply_batch_default_treats_a_sourceless_position_as_auto():
    """Positions written before `source` existed carry none. They were all
    picker output — there was no manual affordance yet — so they clear.

    Built by hand at the POSITION level only (the schema defaults `source` to
    "auto", so a sourceless payload cannot be produced through it) — the overlay
    envelope still goes through the real key."""
    from app.services.returned_exam import OVERLAY_KEY, apply_stamp_default_to_draft

    legacy = {OVERLAY_KEY: {"stamp_position": {"corner": "tl"}}}
    after, changed = apply_stamp_default_to_draft(legacy)
    assert changed is True and after[OVERLAY_KEY].get("stamp_position") is None


# ---------------------------------------------------------------------------
# render golden-image diff
# ---------------------------------------------------------------------------

def test_appendix_render_matches_the_golden_image():
    """A pixel guard on the one thing no unit test sees: layout.

    Tolerant by necessity — rasterisation differs slightly across platforms and
    PyMuPDF builds — but the vendored font makes glyph SHAPES stable, so a real
    layout regression moves far more than the tolerance. On failure the actual
    render is written beside the golden so the diff is inspectable.
    """
    import fitz
    from pathlib import Path
    from app.services.returned_exam import render_appendix_pdf

    golden = Path(__file__).parent / "goldens" / "appendix_dan.png"
    pdf = render_appendix_pdf(
        student_name="דן בסיוק",
        scopes=[("q1.א", "הגדרת נכון את מערך הצוברים.",
                 [("סכימה לכל ערוץ", "3", "3")]),
                ("q1.ב", "הלולאה מדלגת על האיבר האחרון.", None)],
        summary="שני דפוסים חוזרים לאורך המבחן.",
        include_criteria=True)
    page = fitz.open(stream=pdf, filetype="pdf")[0]
    actual = page.get_pixmap(dpi=72)

    assert golden.exists(), f"golden missing at {golden}"
    expected = fitz.Pixmap(str(golden))
    assert (actual.width, actual.height) == (expected.width, expected.height)

    a, b = actual.samples, expected.samples
    differing = sum(1 for i in range(0, len(a), 7) if abs(a[i] - b[i]) > 8)
    total = len(range(0, len(a), 7))
    if differing / total > 0.02:
        out = Path(__file__).parent / "goldens" / "appendix_dan.actual.png"
        actual.save(str(out))
        raise AssertionError(
            f"{differing / total:.1%} of sampled pixels moved (tolerance 2%); "
            f"actual render written to {out}")


# ---------------------------------------------------------------------------
# bidi: measured, not assumed
# ---------------------------------------------------------------------------

def _visual_glyph_order(pdf_bytes) -> str:
    """The glyphs of the whole PDF, left to right — what a reader's eye sees.

    Span text is NOT usable here: PyMuPDF reconstructs a span's text in logical
    order, so extraction reports a correct-looking string for a line that is
    laid out backwards. Only per-character x positions tell the truth.
    """
    import fitz
    from collections import defaultdict

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    rows = defaultdict(list)
    for pageno, page in enumerate(doc):
        for block in page.get_text("rawdict")["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    for c in span["chars"]:
                        # bucket by BASELINE, not by PyMuPDF's "line" objects:
                        # it emits one of those per direction run, so a single
                        # visual row arrives in three pieces.
                        rows[(pageno, round(c["bbox"][3], 1))].append(
                            (c["bbox"][0], c["c"]))
    return chr(10).join(
        "".join(ch for _, ch in sorted(chars)) for _, chars in sorted(rows.items()))


BIDI_CASES = [
    ("pure Hebrew", "משוב על המבחן"),
    ("Hebrew with code", "הלולאה משתמשת ב־ i+=2 במקום ב־ i++ ולכן מדלגת."),
    ("Hebrew with a Latin name", "הופק על ידי Vivi. הציון נקבע על ידי המורה."),
    ("criterion line", "סכימה לכל ערוץ — 3/3"),
]


@pytest.mark.parametrize("label,text", BIDI_CASES, ids=[c[0] for c in BIDI_CASES])
def test_appendix_glyph_order_matches_the_bidi_reference(label, text):
    """The rendered glyph order must equal what the Unicode Bidirectional
    Algorithm says it should be — `python-bidi`'s `get_display` is the
    reference, and this asserts the render reproduces it exactly.

    MEASURED, not assumed (2026-08-31, per-character bbox probe). PyMuPDF's
    Story does HALF the algorithm: it reverses characters INSIDE a directional
    run but lays the runs out left-to-right in logical order. A pure-Hebrew
    paragraph is one run and renders perfectly — which is exactly why this is
    easy to miss. Add one code token, as every CS feedback sentence does, and
    the sentence reads backwards.

    Two alternatives were tried and FALSIFIED against a render; do not
    reintroduce either from first principles:
      · U+2066/U+2069 isolates — scrambled the following Hebrew run.
      · plain `get_display()` with no flip-back — PyMuPDF reversed it a second
        time and pure Hebrew came out backwards.
    The third alternative, splitting runs on any neutral, reversed the WORD
    order of pure Hebrew («משוב על המבחן» → «המבחן על משוב»); the "pure Hebrew"
    case above is that regression's guard.
    """
    from bidi.algorithm import get_display
    from app.services.returned_exam import render_appendix_pdf

    # as body prose, not the 17px <h1>: a heading WRAPS these sentences, and
    # the reference is per-line, so a wrapped line would fail for a reason that
    # has nothing to do with direction.
    pdf = render_appendix_pdf(student_name="דן", scopes=[("q", text, None)],
                              summary=None, include_criteria=False)
    rendered = _visual_glyph_order(pdf)
    expected = get_display(text, base_dir="R")
    assert expected in rendered, (
        f"{label}: rendered glyph order is not the bidi reference\n"
        f"  expected: {expected!r}\n  rendered: {rendered!r}")


def test_scope_id_reads_the_same_as_it_does_in_the_app():
    """`q1.א` is an identifier, not prose. Under an RTL base the algorithm
    resolves it to `א.q1` — correct by the algorithm, and NOT what the teacher
    sees on her screen. A student comparing the PDF against the review screen
    must not have to work out that two different-looking strings are the same
    question, so identifiers get an LTR base and prose does not.
    """
    from bidi.algorithm import get_display
    from app.services.returned_exam import render_appendix_pdf

    pdf = render_appendix_pdf(student_name="דן",
                              scopes=[("q1.א", "טקסט", None)],
                              summary=None, include_criteria=False)
    rendered = _visual_glyph_order(pdf)
    assert get_display("q1.א", base_dir="L") in rendered, (
        "the scope heading does not read as the identifier it is")


# ---------------------------------------------------------------------------
# Code-review findings on G9 (2026-08-31)
# ---------------------------------------------------------------------------

def _blank_source_pdf(inked_corner=None, pages=1):
    """A source exam page, optionally with ink in one corner."""
    import fitz
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        if inked_corner:
            r = page.rect
            w = r.width * 0.30
            boxes = {
                "tl": fitz.Rect(0, 0, w, w),
                "tr": fitz.Rect(r.width - w, 0, r.width, w),
                "bl": fitz.Rect(0, r.height - w, w, r.height),
                "br": fitz.Rect(r.width - w, r.height - w, r.width, r.height),
            }
            page.draw_rect(boxes[inked_corner], color=(0, 0, 0), fill=(0, 0, 0))
    return doc.tobytes()


def test_stamp_word_renders_in_the_vendored_hebrew_face():
    """THE tofu bug, one layer down.

    `helv` — PyMuPDF's built-in Helvetica — has no Hebrew glyphs at all; it
    renders «נבדק» as four question marks. The appendix guards against this for
    its prose, and the stamp needs the same guard: it is the first thing the
    student sees on page 1, and it would be four question marks on every exam.
    """
    import fitz
    from app.services.returned_exam import render_returned_exam

    pdf = render_returned_exam(_blank_source_pdf(), "דן", [], None, None, False)
    page1 = fitz.open(stream=pdf, filetype="pdf")[0]
    text = page1.get_text()
    assert "?" not in text, f"the stamp rendered as tofu: {text!r}"
    assert "נבדק" in text, f"the stamp word is missing entirely: {text!r}"


def test_stamp_auto_picks_the_emptiest_corner_when_none_is_set():
    """`stamp_corner_picker` must actually run in production.

    With no position on the test and none on the batch, the renderer has to
    LOOK at the page — otherwise the picker is dead code and every unstamped
    exam gets a top-left stamp, including the ones whose top-left is full of
    the student's work.
    """
    import fitz
    from app.services.returned_exam import render_returned_exam

    pdf = render_returned_exam(_blank_source_pdf(inked_corner="tl"),
                               "דן", [], None, None, False)
    page1 = fitz.open(stream=pdf, filetype="pdf")[0]
    hits = page1.search_for("נבדק")
    assert hits, "the stamp was not drawn"
    r = page1.rect
    assert not (hits[0].x0 < r.width / 2 and hits[0].y0 < r.height / 2), (
        "the stamp was placed over the inkiest corner — the picker never ran")


def test_zip_entry_names_stay_unique_when_students_collide():
    """Two students whose names truncate the same must not become one file.

    `zipfile` accepts duplicate entry names without complaint and most unzip
    tools keep the last — so one student silently receives another's exam and
    the other receives nothing. Neither can tell.
    """
    from app.services.returned_exam import unique_zip_entry_names

    names = unique_zip_entry_names("מבחן", ["דן " + "א" * 200,
                                            "דן " + "א" * 200 + "ב",
                                            "דן " + "א" * 200])
    assert len(set(names)) == 3, f"entries collide: {names}"


def test_appendix_pagination_is_bounded():
    """An unbounded `while more:` is an infinite loop inside a request.

    Measured: when the box cannot fit even one line, PyMuPDF's `place` returns
    «more» forever. Today's box is comfortably large, but a font-metric change
    or one unbreakable token is all it takes, and the failure mode is a hung
    worker plus a PDF that grows until memory runs out.
    """
    from app.services import returned_exam as rex

    pdf = rex.render_appendix_pdf(
        student_name="דן",
        scopes=[(f"q{i}", "מילה " * 400, None) for i in range(60)],
        summary=None, include_criteria=False)

    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    assert doc.page_count <= rex.MAX_APPENDIX_PAGES
