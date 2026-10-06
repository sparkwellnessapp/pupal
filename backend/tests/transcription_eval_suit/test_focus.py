"""The focus pass's pure half (focus.py), zero mocks. The splice guard is the
safety story, so it gets the most cases: a reader may add or fix HEBREW and its
comment punctuation, never code."""
import pytest
from PIL import Image

from app.services.transcription.two_phase import focus as F


# --- the guard ---------------------------------------------------------------------

@pytest.mark.parametrize("before,after", [
    ("private string hobbyName;", "private string hobbyName; // הגדרת תכונות"),   # dropped comment restored
    ("return false; // יכול גם מלא //", "return false; // בדיקה אם מלא"),          # misread fixed
    ("int x = 0; // מונה", "int x = 0;   // מונה חדש"),
])
def test_hebrew_and_comment_punctuation_may_change(before, after):
    assert F.check(before, after) == "applied"


@pytest.mark.parametrize("before,after,why", [
    ("i+2; // קידום", "i+=2; // קידום", "skeleton"),        # the flagging.py normalization: refused
    ("int x = 0; // מונה", "int y = 0; // מונה", "skeleton"),
    ("foo(x); // קריאה", "foo(x) // קריאה", "skeleton"),     # a code `;` is NOT comment punctuation
    ("foo(x);", "foo(x) // קריאה", "skeleton"),              # ...nor when restoring a dropped comment
    ("int c=0; // (אם לא עדכן נחזיר fake)", "int c=0; // (אם לא עדכן נחזיר false)", "skeleton"),
    ("int x = 0; // מונה", "int x = 0;", "no_hebrew"),
    ("int x = 0; // מונה", "int x = 0; // מונה", "unchanged"),
    ("int x = 0; // מונה", "", "empty"),
    ("int x = 0; // מונה", "int x = 0;\n// מונה", "multi_line"),
])
def test_everything_else_is_refused(before, after, why):
    assert F.check(before, after) == why


def test_splice_replaces_only_named_lines_and_keeps_indentation():
    text = "class A\n{\n    int n;\n    return n; // מחזיר\n}"
    out, rec = F.splice(text, {3: "int n; // מספר", 4: "return m; // מחזיר"})
    assert out == "class A\n{\n    int n; // מספר\n    return n; // מחזיר\n}"
    assert [(r.line_id, r.accepted, r.reason) for r in rec] == [(3, True, "applied"),
                                                                  (4, False, "skeleton")]


def test_splice_ignores_out_of_range_ids_and_is_pure():
    text = "a // א"
    out, rec = F.splice(text, {9: "a // ב"})
    assert out == text and rec == []


# --- localizer output ----------------------------------------------------------------

def test_parse_targets_drops_the_malformed_and_keeps_page_order():
    raw = [
        {"line_id": 4, "box_2d": [100, 50, 130, 900]},
        {"line_id": 2, "box_2d": [40, 50, 70, 900]},
        {"line_id": 4, "box_2d": [0, 0, 500, 500]},         # duplicate id
        {"line_id": 99, "box_2d": [0, 0, 10, 10]},          # out of range
        {"line_id": 3, "box_2d": [10, 10, 11, 900]},        # degenerate height
        {"line_id": "x", "box_2d": [1, 2, 3]},              # garbage
        "nonsense",
    ]
    t = F.parse_targets(raw, n_lines=5, max_targets=10)
    assert [x.line_id for x in t] == [2, 4]
    assert F.parse_targets(raw, n_lines=5, max_targets=1)[0].line_id == 2


def test_parse_targets_clamps_and_orders_the_box():
    t = F.parse_targets([{"line_id": 1, "box_2d": [300, 1200, 200, -5]}], 1, 5)
    assert t[0].box == (200.0, 0.0, 300.0, 1000.0)


# --- geometry -----------------------------------------------------------------------

def test_crop_maps_the_0_1000_grid_with_padding():
    img = Image.new("RGB", (1000, 2000), "white")
    c = F.crop(img, (100, 200, 150, 800), pad_y=0.0, pad_x=0.0)
    assert c.size == (600, 100)
    c = F.crop(img, (100, 200, 150, 800), pad_y=1.0, pad_x=0.05)
    assert c.size == (700, 300)
    c = F.crop(img, (0, 0, 1000, 1000), pad_y=1.0, pad_x=0.5)   # clamped to the page
    assert c.size == (1000, 2000)


def test_number_lines_is_one_based_and_complete():
    assert F.number_lines("a\n\nb") == "001| a\n002| \n003| b"


# --- wiring on fakes (pipeline._focus_pages) -----------------------------------------

import asyncio
import json

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler

from .pipelines import PipelineConfig, build_pipeline

PAGE = "class A\n{\nprivate string name;\n}"


def _perceive(script, **kw):
    fake = FakeProvider(script=script)
    cfg = PipelineConfig(p1_model_key="gemini-3.1-flash-lite", p1_pages_per_call=1, **kw)
    pipe = build_pipeline(
        cfg, {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=lambda b, d: [Image.new("RGB", (400, 600), "white")],
    )
    pages, trace = asyncio.new_event_loop().run_until_complete(
        pipe.run_phase1(b"pdf", "doc"))
    return pages, trace, fake


P1 = FakeProvider.ok(json.dumps({"pages": [{"page_number": 1, "text": PAGE}]}))
LOC = FakeProvider.ok(json.dumps({"hebrew_lines": [{"line_id": 3, "box_2d": [300, 50, 340, 950]}]}))
ON = dict(p1_focus_localizer_model_key="gemini-3.1-flash-lite")


def test_off_makes_no_extra_call():
    pages, trace, fake = _perceive([P1])
    assert len(fake.calls) == 1 and pages[1] == PAGE and trace.focus == []


def test_on_restores_a_dropped_hebrew_comment_from_a_crop():
    read = FakeProvider.ok(json.dumps({"line": "private string name; // הגדרת תכונות"}))
    pages, trace, fake = _perceive([P1, LOC, read], **ON)
    assert pages[1] == "class A\n{\nprivate string name; // הגדרת תכונות\n}"
    assert [c.n_images for c in fake.calls] == [1, 1, 1]
    assert fake.calls[2].images_b64[0] != fake.calls[1].images_b64[0]      # a crop, not the page
    assert "003| private string name;" in fake.calls[1].user
    assert trace.focus == [{"page": 1, "line_id": 3, "before": "private string name;",
                            "after": "private string name; // הגדרת תכונות",
                            "accepted": True, "reason": "applied"}]


def test_a_reading_that_touches_code_is_refused_and_p1_stands():
    read = FakeProvider.ok(json.dumps({"line": "private String name; // שם"}))
    pages, trace, _ = _perceive([P1, LOC, read], **ON)
    assert pages[1] == PAGE and trace.focus[0]["reason"] == "skeleton"


def test_an_unparseable_reading_keeps_the_line():
    pages, trace, _ = _perceive([P1, LOC, FakeProvider.ok("not json")], **ON)
    assert pages[1] == PAGE and trace.focus == []


def test_an_unparseable_localization_keeps_the_page():
    pages, trace, fake = _perceive([P1, FakeProvider.ok("not json")], **ON)
    assert pages[1] == PAGE and len(fake.calls) == 3      # P1 + localize + its one re-request


def test_only_missing_rereads_lines_without_hebrew_and_skips_the_rest():
    """Recommendation #5: a line P1 already wrote Hebrew on is never re-read."""
    page = "class A\n{\nprivate string name;\nint n; // מונה\n}"
    p1 = FakeProvider.ok(json.dumps({"pages": [{"page_number": 1, "text": page}]}))
    loc = FakeProvider.ok(json.dumps({"hebrew_lines": [
        {"line_id": 3, "box_2d": [300, 50, 340, 950]},       # no Hebrew in P1 → read
        {"line_id": 4, "box_2d": [400, 50, 440, 950]}]}))    # has Hebrew → skipped
    read = FakeProvider.ok(json.dumps({"line": "private string name; // שם"}))
    pages, trace, fake = _perceive([p1, loc, read], p1_focus_only_missing=True, **ON)
    assert len(fake.calls) == 3                                # P1, localize, ONE read
    assert pages[1] == "class A\n{\nprivate string name; // שם\nint n; // מונה\n}"
    assert [r["line_id"] for r in trace.focus] == [3]
