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
        scopes=[_sc("q1.א", "הגדרת נכון את מערך הצוברים.")],
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
        scopes=[_sc(f"q{i}", long_text) for i in range(6)],
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


def test_manifest_partitions_includable_unapproved_and_unavailable():
    """The ZIP ships every APPROVED test, and names what it cannot ship.

    A missing or outdated render is NOT an exclusion: the download builds it
    (`returned_exam_store`). This test used to assert the opposite — that a
    never-rendered exam was excluded as "stale" — which is precisely the bug it
    was pinning. Since the single-test preview was the only thing that ever
    wrote `returned_exam_key`, EVERY approved test in a batch matched that
    branch, and a teacher who approved five and clicked download was told she
    had approved none and edited five she had not touched.

    The freshness guarantee is untouched: nothing outdated is served, because
    anything outdated is rebuilt before it ships.
    """
    from app.services.returned_exam import manifest_partition

    got = manifest_partition([
        _row("dan"),                              # cached and current agree
        _row("din", status="draft"),              # a draft is not a grade
        _row("moran", cached="old", current="new"),   # outdated -> re-rendered
        _row("omer", cached=None),                # never rendered -> rendered
        _row("noa", current=None),                # contract unreadable
    ])

    assert {r.student_name for r in got["included"]} == {"dan", "moran", "omer"}
    assert [r.student_name for r in got["excluded_not_approved"]] == ["din"]
    # The ONLY remaining reason to exclude an approved test: we cannot prove
    # what the document should say, so we ship none rather than a guess.
    assert [r.student_name for r in got["excluded_unavailable"]] == ["noa"]


def test_zip_names_are_nfc_and_path_safe():
    """Hebrew composed differently on macOS and Linux unzips to two different
    files. NFC once, at the boundary; and a student name with a slash must not
    escape the archive."""
    from app.services.returned_exam import ZIP_ENTRY_SUFFIX, zip_entry_name
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "דן בסיוק")
    name = zip_entry_name("מבחן 1", decomposed)
    assert name == unicodedata.normalize("NFC", name)
    # The suffix is asserted through the CONSTANT, not a second spelling of it:
    # `unique_zip_entry_names` slices it off by LENGTH to build its dedupe stem,
    # so two spellings would silently truncate a student's name on a collision.
    assert name.endswith(ZIP_ENTRY_SUFFIX)
    assert ZIP_ENTRY_SUFFIX == "_חתום.pdf"    # §5.6: the product term is המבחן החתום

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
        scopes=[_sc("q1.א", "הגדרת נכון את מערך הצוברים.",
                            [("סכימה לכל ערוץ", "3", "3")]),
                        _sc("q1.ב", "הלולאה מדלגת על האיבר האחרון.")],
        summary="שני דפוסים חוזרים לאורך המבחן.",
        include_criteria=True)
    page = fitz.open(stream=pdf, filetype="pdf")[0]
    actual = page.get_pixmap(dpi=72)

    assert golden.exists(), f"golden missing at {golden}"
    expected = fitz.Pixmap(str(golden))
    assert (actual.width, actual.height) == (expected.width, expected.height)

    # MEASURED AGAINST THE INK, not the canvas — and that correction has a
    # history. The tolerance used to be 2% of ALL sampled pixels on a page that
    # is 0.4% ink, i.e. five times more slack than there is ink to move. It
    # could only fire on a change larger than the entire content of the page,
    # and it duly passed through the 2026-09-04 rewrite that changed every
    # heading and added a points line to every scope (1.04% of pixels moved).
    # A guard calibrated against the background is decorative.
    a, b = actual.samples, expected.samples
    differing = sum(1 for i in range(len(a)) if abs(a[i] - b[i]) > 8)
    ink = sum(1 for i in range(len(b)) if b[i] < 200) or 1
    if differing / ink > 0.25:
        out = Path(__file__).parent / "goldens" / "appendix_dan.actual.png"
        actual.save(str(out))
        raise AssertionError(
            f"pixels moved equal to {differing / ink:.0%} of the golden's ink "
            f"(tolerance 25%); actual render written to {out}")


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
                            (c["bbox"][0], c["c"], round(c["bbox"][2], 1)))

    def seen(chars):
        # A PHANTOM space: PyMuPDF sometimes reports a space in the exact box of
        # a neighbouring glyph (measured 2026-10-23: «כך» extracted as «ך כ»
        # with the space at 368.2–373.4, the box of «כ»). It occupies no room
        # of its own, so the eye cannot see it; only spaces with their own box
        # are kept.
        boxes = {(round(x0, 1), x1) for x0, ch, x1 in chars if ch != " "}
        return [(x0, ch) for x0, ch, x1 in chars
                if not (ch == " " and (round(x0, 1), x1) in boxes)]
    return chr(10).join(
        "".join(ch for _, ch in sorted(seen(chars))) for _, chars in sorted(rows.items()))


BIDI_CASES = [
    ("pure Hebrew", "משוב על המבחן"),
    ("Hebrew with code", "הלולאה משתמשת ב־ i+=2 במקום ב־ i++ ולכן מדלגת."),
    ("Hebrew with a Latin name", "הופק על ידי Vivi. הציון נקבע על ידי המורה."),
    ("criterion line", "סכימה לכל ערוץ — 3/3"),
    # [2026-10-23] Brackets INSIDE a Hebrew run came out facing the wrong way
    # (flipped twice); brackets touching code were always right. These pin both.
    ("brackets inside Hebrew", "התכונות (שם התכונה) כך"),
    ("bracket opens on Hebrew, closes on code", "התכונות (שם הוא durationInMinutes) כך"),
    ("bracket opens on code, closes on Hebrew", "התכונות (durationInMinutes הוא שם) כך"),
    ("square and curly brackets", "הפעולה [אינדקס i] ו-{גוף הלולאה} כאן"),
    ("guillemets", "המורה כתבה «מצוין» בסוף"),
    ("brackets around code only", "הגישה לגבול הלולאה (A.Length) נעשתה ישירות"),
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
    pdf = render_appendix_pdf(student_name="דן", scopes=[_sc("q", text)],
                              summary=None, include_criteria=False)
    rendered = _visual_glyph_order(pdf)
    expected = get_display(text, base_dir="R")
    assert expected in rendered, (
        f"{label}: rendered glyph order is not the bidi reference\n"
        f"  expected: {expected!r}\n  rendered: {rendered!r}")


def test_a_wrapped_mixed_paragraph_reads_in_order_line_by_line():
    """[2026-10-23] A paragraph that WRAPS and mixes Hebrew with code must read
    top-to-bottom in logical order, and right-to-left within every line.

    The case above renders one-line text only, and that is how the defect
    shipped: the paragraph was reordered as ONE line and Story wrapped the
    visual string, so the paragraph's END landed on its first line. Every CS
    feedback paragraph is this shape. Unique Latin tokens let the PDF's own
    word positions say where each piece of the sentence ended up.
    """
    import fitz
    from app.services.returned_exam import render_appendix_pdf

    tokens = [f"tok{i:02d}" for i in range(40)]
    text = " ".join(f"המשתנה {t} מתעדכן בתוך הלולאה" for t in tokens)
    pdf = render_appendix_pdf(student_name="דן", scopes=[_sc("q1.א", text)],
                              summary=None, include_criteria=False)
    doc = fitz.open(stream=pdf, filetype="pdf")
    where = {}
    for pageno, page in enumerate(doc):
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            if word in tokens:
                where[word] = (pageno, round(y1, 1), x0)
    assert set(where) == set(tokens), f"tokens lost: {set(tokens) - set(where)}"

    rows = [where[t][:2] for t in tokens]
    assert len(set(rows)) >= 3, "the paragraph did not wrap; the test proves nothing"
    # Story must lay out exactly the lines we wrapped. One more means it
    # re-wrapped a line we measured as fitting: a lone word on its own line.
    from app.services.returned_exam import _SIZE, _wrap_logical
    vocabulary = set(text.split())
    body_rows = {(p, round(w[3], 1)) for p, page in enumerate(doc)
                 for w in page.get_text("words") if w[4] in vocabulary}
    assert len(body_rows) == len(_wrap_logical(text, _SIZE["body"])), (
        f"Story drew {len(body_rows)} lines for "
        f"{len(_wrap_logical(text, _SIZE['body']))} wrapped ones")
    assert rows == sorted(rows), (
        "lines are out of reading order: "
        + str([(t, where[t][:2]) for t in tokens]))
    for a, b in zip(tokens, tokens[1:]):
        if where[a][:2] == where[b][:2]:
            assert where[a][2] > where[b][2], (
                f"{a} should sit to the RIGHT of {b} on an RTL line")


def test_the_appendix_no_longer_prints_the_raw_scope_id():
    """SUPERSEDED, deliberately. This used to assert that the heading «q1.א»
    rendered with an LTR base, because an identifier must read identically
    wherever the teacher and the student see it.

    The ruling of 2026-09-04 removed the premise: the appendix prints Hebrew
    PROSE («שאלה 1, סעיף א»), not the internal key, because the key means
    nothing to a student. The LTR-base rule still governs identifiers elsewhere
    — it simply has no identifier left to govern on this page. Its replacement
    is `test_appendix_hebrew_title_with_a_digit_renders_in_order`, which is the
    harder assertion: prose with a digit in it."""
    from app.services.returned_exam import render_appendix_pdf

    pdf = render_appendix_pdf(student_name="דן",
                              scopes=[_sc("q1.א", "טקסט")],
                              summary=None, include_criteria=False)
    rendered = _visual_glyph_order(pdf)
    assert "q1" not in rendered, "the raw internal id is still on the page"


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
        scopes=[_sc(f"q{i}", "מילה " * 400) for i in range(60)],
        summary=None, include_criteria=False)

    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    assert doc.page_count <= rex.MAX_APPENDIX_PAGES


# ---------------------------------------------------------------------------
# Phase C (OD-2) + Phase D — the stamp carries the score; the appendix carries
# the grade. Until 2026-09-04 a student received a graded exam with NO grade on
# it and every question labelled with our internal key («q1.א»).
# ---------------------------------------------------------------------------

def _one_page_pdf():
    import fitz
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    return doc.tobytes()


def _sc(scope_id, feedback, criteria=None, awarded="1", possible="1"):
    """An AppendixScope for tests that only care about the prose.

    These call sites used to pass a 3-tuple. The parameter became a RECORD
    (§0.4) precisely so that adding the title and the two point figures could
    not be done by widening a positional — which is the shape where a caller
    silently swaps two strings and the page is wrong but looks fine.
    """
    from app.services.returned_exam import AppendixScope, scope_title_of
    return AppendixScope(scope_id, scope_title_of(scope_id), awarded, possible,
                         feedback, criteria)


def _appendix_text(pdf_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def test_stamp_is_round_and_carries_the_score():
    """[OD-2, Option A] The PDF used to draw «נבדק» in a 2:1 ellipse while the
    spec, the mockup and the shipped frontend all showed a ROUND stamp bearing
    the grade — so the teacher previewed one stamp and the student received a
    different one."""
    import fitz
    from app.services.returned_exam import draw_stamp

    doc = fitz.open(stream=_one_page_pdf(), filetype="pdf")
    page = doc[0]
    draw_stamp(page, {"corner": "tl", "source": "manual"}, "87.5")

    assert "87.5" in page.get_text(), "the stamp does not carry the score"
    assert "נבדק" not in page.get_text(), "the retired word is still drawn"

    # ROUND: the drawn oval's bounding box is square (within a hair)
    ovals = [d for d in page.get_drawings() if d["rect"].width > 20]
    assert ovals, "no stamp geometry was drawn"
    box = ovals[0]["rect"]
    assert abs(box.width - box.height) < box.width * 0.06, (
        f"the stamp is {box.width:.1f}x{box.height:.1f} — not round, so its "
        f"corner arithmetic cannot agree with the frontend's square box")


def test_stamp_corner_arithmetic_agrees_with_the_frontend():
    """[OD-2 side effect] `stampBox` had to assume a square box of side `w`
    while the PDF drew a 2:1 ellipse, so corner placement differed by w/4
    vertically — the pinned divergence test measured exactly that. A round stamp
    makes the two renderers agree BY CONSTRUCTION."""
    from app.services.returned_exam import _INSET, _STAMP_FRACTION

    page_w, page_h = 595.0, 842.0
    w = page_w * _STAMP_FRACTION
    dx, dy = page_w * _INSET, page_h * _INSET
    for corner in ("tl", "tr", "bl", "br"):
        # the frontend's stampBox, verbatim
        fe_cx = dx + w / 2 if corner in ("tl", "bl") else page_w - dx - w / 2
        fe_cy = dy + w / 2 if corner in ("tl", "tr") else page_h - dy - w / 2
        # draw_stamp, now that h == w
        h = w
        pdf_cx = dx + w / 2 if corner in ("tl", "bl") else page_w - dx - w / 2
        pdf_cy = dy + h / 2 if corner in ("tl", "tr") else page_h - dy - h / 2
        assert (fe_cx, fe_cy) == (pdf_cx, pdf_cy), (
            f"{corner}: preview {(fe_cx, fe_cy)} vs render {(pdf_cx, pdf_cy)}")


def test_a_stamp_with_no_score_falls_back_to_the_word():
    """A caller with no contract to read can honestly say «נבדק» — it must not
    invent a number."""
    import fitz
    from app.services.returned_exam import draw_stamp

    doc = fitz.open(stream=_one_page_pdf(), filetype="pdf")
    draw_stamp(doc[0], {"corner": "tl"}, None)
    assert "נבדק" in doc[0].get_text()


def test_appendix_carries_the_total_and_per_scope_points():
    """Gap 2. The page emitted a header, feedback and a footer — no total, no
    per-scope points. A student received a graded exam with no grade on it."""
    from app.services.returned_exam import AppendixScope, render_appendix_pdf

    scopes = [AppendixScope("q1.א", "שאלה 1, סעיף א", "9", "10", "טוב", None),
              AppendixScope("q2", "שאלה 2", "7.5", "10", "", None)]
    text = _appendix_text(render_appendix_pdf(
        "דין עזרא", scopes, "סיכום כללי", False, total="87.5", possible="100"))

    assert "87.5 / 100" in text, "the appendix carries no total"
    assert "9 / 10" in text, "a scope carries no points"
    assert "7.5 / 10" in text, "a scope with no feedback lost its points too"
    assert "סיכום" in text and "Vivi" in text


def test_appendix_titles_are_hebrew_prose_not_raw_ids():
    """`q1.א` is our internal key. It means nothing to a student, and it is the
    wrong thing to put on a document they keep."""
    from app.services.returned_exam import AppendixScope, render_appendix_pdf

    scopes = [AppendixScope("q1.א", "שאלה 1, סעיף א", "9", "10", "טוב", None)]
    text = _appendix_text(render_appendix_pdf("דין", scopes, None, False,
                                              total="9", possible="10"))
    assert "שאלה" in text, "the Hebrew title is missing"
    assert "q1" not in text, "the raw internal id is still printed"


def test_scope_title_mirrors_the_frontend_rule():
    from app.services.returned_exam import scope_title_of

    assert scope_title_of("q1.א") == "שאלה 1, סעיף א"
    assert scope_title_of("q3") == "שאלה 3"


def test_appendix_total_comes_from_the_contract_not_a_resum():
    """The rendered scopes deliberately EXCLUDE the not-counted ones, so
    re-summing them would under-report on every «choose k of N» exam — the
    re-derivation that once halved every selection grade (§5)."""
    from app.services.returned_exam import AppendixScope, render_appendix_pdf

    # four counted scopes worth 100 between them; the total says 100, and the
    # two unchosen questions are simply not here to be summed
    scopes = [AppendixScope(f"q{i}", f"שאלה {i}", "25", "25", "", None)
              for i in range(2, 6)]
    text = _appendix_text(render_appendix_pdf(
        "דין", scopes, None, False, total="100", possible="100"))
    assert "100 / 100" in text
    assert "150" not in text, "the offered total leaked onto the student's page"


def test_appendix_hebrew_title_with_a_digit_renders_in_order():
    """The title is PROSE, not an identifier, so it takes an RTL base — unlike
    the raw scope id it replaced. A digit next to Hebrew is exactly the shape
    that exposed PyMuPDF's half-bidi defect, so this asserts the RENDERED
    order per character rather than trusting the string."""
    import fitz
    from app.services.returned_exam import AppendixScope, render_appendix_pdf

    scopes = [AppendixScope("q1.א", "שאלה 1, סעיף א", "9", "10", "", None)]
    pdf = render_appendix_pdf("דין", scopes, None, False, total="9", possible="10")
    page = fitz.open(stream=pdf, filetype="pdf")[0]

    # every character of the title, with its x position
    words = page.get_text("words")                             # x0,y0,x1,y1,word,...
    title_words = [w for w in words if w[4] in ("שאלה", "סעיף", "א", "1,", "1")]
    assert title_words, "the title did not render"

    # In RTL, «שאלה» must sit to the RIGHT of «סעיף».
    def x_of(word):
        hits = [w for w in title_words if w[4] == word]
        return hits[0][0] if hits else None

    x_shaala, x_seif = x_of("שאלה"), x_of("סעיף")
    assert x_shaala is not None and x_seif is not None, [w[4] for w in title_words]
    assert x_shaala > x_seif, (
        f"«שאלה» rendered LEFT of «סעיף» (x={x_shaala} vs {x_seif}) — the title "
        f"reads backwards, which is the half-bidi defect")


def test_points_render_trimmed_never_rounded():
    """Parity with the frontend's `formatPoints`: the exact Decimal travels and
    freezes; only the DISPLAY is trimmed. A number that reads 7.5 in the preview
    and 7.50 in the PDF makes a liar of the preview."""
    from app.services.points_display import format_points, format_points_pair

    table = {"7.50": "7.5", "4.00": "4", "0.75": "0.75", "0": "0",
             "8": "8", "79.50": "79.5", "-0.00": "0", "0.00": "0",
             "": "", "10": "10"}
    for raw, want in table.items():
        assert format_points(raw) == want, f"{raw!r} -> {format_points(raw)!r}"
    assert format_points(None) == ""
    assert format_points("1e3") == "1e3", "an unexpected form must pass through"
    assert format_points_pair("7.50", "10") == "7.5 / 10"


def test_renderer_version_bump_invalidates_every_cached_render():
    """The appendix and the stamp both changed, so every key computed under the
    old renderer must miss. Without the bump each already-rendered exam keeps
    serving the old page — and a stale returned exam looks entirely correct,
    which is what makes it the one failure this feature cannot have (§3.5a)."""
    from app.services.returned_exam import RENDERER_VERSION, returned_exam_cache_key

    assert RENDERER_VERSION != "returned-exam-v1", "the version was not bumped"
    args = dict(contract_version="cv", feedback_hash="fh",
                stamp_position={"corner": "tl"}, include_criteria=False)
    assert (returned_exam_cache_key(**args, renderer_version="returned-exam-v1")
            != returned_exam_cache_key(**args, renderer_version=RENDERER_VERSION)), (
        "the renderer version does not participate in the cache key")


# ---------------------------------------------------------------------------
# Phase C/D code review — three defects the first pass missed
# ---------------------------------------------------------------------------

def test_the_stamp_never_silently_loses_the_grade():
    """[review F-7] `insert_textbox` does not raise when the string is too wide
    — it returns a negative number and inserts NOTHING. Unchecked, that is a
    stamp with no grade in it, on the page the student looks at first, failing
    silently.

    `100.25` already fills ~90% of the disc at the nominal size, so the headroom
    was one character, not a margin. Every plausible score, and some
    implausible ones, must land ON the page.
    """
    import fitz
    from app.services.returned_exam import draw_stamp

    for score in ("8", "87.5", "100", "87.75", "100.25", "1000.75", "99.999"):
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        page = doc[0]
        draw_stamp(page, {"corner": "tl"}, score)
        assert score in page.get_text(), (
            f"the stamp rendered NOTHING for score {score!r} — the student's "
            f"grade vanished from the page and nothing raised")


def test_a_long_score_is_shrunk_to_fit_the_disc():
    """The shrink is real, not decorative: an over-wide score must come out
    SMALLER rather than absent."""
    import fitz
    from app.services.returned_exam import _STAMP_FRACTION, draw_stamp

    def width_of(score):
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        draw_stamp(doc[0], {"corner": "tl"}, score)
        words = doc[0].get_text("words")
        assert words, f"{score} did not render"
        return fitz.Rect(words[0][:4]).width

    disc = 595.0 * _STAMP_FRACTION
    for score in ("100.25", "1000.75", "99.999"):
        assert width_of(score) <= disc, (
            f"{score} rendered wider than the disc ({width_of(score):.1f} > "
            f"{disc:.1f}) — it spills outside the stamp")


def test_a_total_with_no_denominator_still_shows_the_grade():
    """[review F-9] The total line used to require BOTH figures, so a `possible`
    of None dropped the whole line — leaving the appendix with no total while
    the stamp on page 1 carried one. The student would see two different answers
    to «what did I get»."""
    from app.services.returned_exam import render_appendix_pdf

    text = _appendix_text(render_appendix_pdf(
        "דן", [], None, False, total="87.5", possible=None))
    assert "87.5" in text, "the appendix dropped the grade because it had no denominator"


def test_points_never_render_in_exponent_notation():
    """[review F-8] `str(Decimal("100").normalize())` is `"1E+2"`, and the
    pass-through would hand that straight to the page — a student receiving
    «1E+2» as their grade. Not reachable from today's pricer, so it is closed at
    the boundary rather than argued about."""
    from decimal import Decimal

    from app.services.points_display import format_points

    assert format_points(Decimal("1E+2")) == "100"
    assert format_points(Decimal("100").normalize()) == "100"
    assert format_points(Decimal("1E-2")) == "0.01"
    # the reachable domain is unchanged — the mirror still holds there
    for raw in ("7.50", "4.00", "0.75", "0", "8"):
        assert format_points(Decimal(raw)) == format_points(raw), raw


def test_appendix_prints_her_criterion_notes_under_the_question():
    """Her note on a criterion is written FOR the student: it prints under the
    question's feedback whether or not the breakdown is included."""
    from app.services.returned_exam import AppendixScope, render_appendix_pdf

    scope = AppendixScope("q1", "שאלה 1", "4", "5", "עבודה טובה", None,
                          notes=[("סעיף 2", "הבנת את הרעיון")])
    text = _appendix_text(render_appendix_pdf("דין", [scope], None, False,
                                              total="4", possible="5"))
    assert "הערות המורה" in text
    assert "הבנת" in text and "הרעיון" in text


def test_scopes_for_render_carries_only_the_frozen_student_notes():
    """`student_note` is the only field that reaches the page: a contract frozen
    before notes reached the student has `teacher_comment` and no note, and
    that comment was written under «not shown to the student»."""
    from decimal import Decimal as D
    from types import SimpleNamespace as NS
    from app.services.returned_exam import scopes_for_render

    def term(desc, note=None, comment=None):
        return NS(description=desc, student_note=note, teacher_comment=comment,
                  final_points_awarded=D("1"), points_possible=D("1"))
    contract = NS(feedback=None, scope_outcomes=[NS(
        question_id="q1", sub_question_id=None, counted_in_total=True,
        final_points_awarded=D("2"), points_possible=D("3"),
        terminal_outcomes=[term("א", note="יפה"), term("ב", comment="פרטי"), term("ג")])])
    [scope] = scopes_for_render(contract, include_criteria=False)
    assert scope.notes == [("א", "יפה")]


def test_the_scope_order_is_the_one_both_renderers_pin():
    """Points, feedback, her notes, then the breakdown (owner-ruled 2026-10-26) —
    the same fixture the preview's test reads, and the order the page really has."""
    import json
    from pathlib import Path
    import fitz
    from app.services.returned_exam import (APPENDIX_SCOPE_ORDER, AppendixScope,
                                            render_appendix_pdf)

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "appendix_scope_order.json"
    assert list(APPENDIX_SCOPE_ORDER) == json.loads(fixture.read_text(encoding="utf-8"))["order"]

    scope = AppendixScope("q1", "שאלה 1", "7", "9", "alpha feedback",
                          [("gamma criterion", "1", "2")], notes=[("beta", "note")])
    pdf = render_appendix_pdf("Dan", [scope], None, True, total="7", possible="9")
    words = fitz.open(stream=pdf, filetype="pdf")[0].get_text("words")
    top = {w[4]: w[1] for w in words}
    y = {"points": top["9"], "feedback": top["alpha"], "notes": top["beta:"],
         "breakdown": top["gamma"]}
    assert sorted(y, key=y.get) == list(APPENDIX_SCOPE_ORDER)
