"""C8-lite — a band ladder is ONE criterion, never a sum (multisubject Phase 4b).

Why this exists, from the ruled 10-minute probe: the Ministry F/G writing rubric compiled to
THREE `required` slots per criterion. C5 read the band values as components, saw
8 + 5 + 2 + 0 = 15 > 8, and reconciled them down to 5 / 2 / 1 — so a student would have needed
CORRECT *and* PARTIALLY CORRECT *and* MINIMALLY CORRECT to earn full marks, and the bottom band
(INCORRECT, 0) was named as something to earn. Bands are ALTERNATIVES, not parts.

The detector is deliberately narrow: a false positive would silently collapse a real component
list into one slot, which is the same class of error in the other direction. Three or more
labelled bands, values strictly descending, top band == the terminal's points, bottom band 0.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.plan_compiler.compile import _band_ladder, compile_terminal

D = Decimal
GRID = D("0.25")

MINISTRY_MECHANICS = """MECHANICS
CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on sentences
PARTIALLY CORRECT (4): • partially correct use of: spelling • punctuation • some run-on sentences
MINIMALLY CORRECT (2): • minimally correct use of: spelling • punctuation • frequent run-on sentences
INCORRECT (0): • Incorrect use of: spelling • punctuation • consistent use of run-on sentences"""


def _compile(text: str, points: str):
    return compile_terminal(terminal_id="q1.c0", scope="q1", text=text, points=D(points),
                            grid=GRID, has_solution=False)


def test_a_ministry_ladder_stays_one_required_slot_at_the_top_band():
    t = _compile(MINISTRY_MECHANICS, "6")
    assert t.case == "band_ladder"
    assert len(t.earn_slots) == 1
    slot = t.earn_slots[0]
    assert slot.kind == "required"
    assert slot.points == D("6")
    assert t.routed is False
    # the ladder the teacher wrote travels with the slot, so the grader reads all four bands
    for band in ("CORRECT", "PARTIALLY CORRECT", "MINIMALLY CORRECT", "INCORRECT"):
        assert band in slot.source_span
    codes = [f.code for f in t.flags]
    assert "band_ladder_kept_whole" in codes
    # and none of the reconciliation that fired before C8-lite
    assert "case3_over_allocation" not in codes
    assert "unvalued_component_dropped" not in codes


@pytest.mark.parametrize("points,expected_top", [("8", "8"), ("10", "10"), ("16", "16")])
def test_every_ministry_criterion_holds_its_own_top_band(points, expected_top):
    text = (f"CONTENT\nCORRECT ({points}): • fully on topic\n"
            f"PARTIALLY CORRECT (5): • partially on topic\n"
            f"MINIMALLY CORRECT (2): • minimally on topic\n"
            f"INCORRECT (0): • not on topic")
    t = _compile(text, points)
    assert t.case == "band_ladder"
    assert str(t.earn_slots[0].points) == expected_top


def test_a_real_component_list_is_NOT_a_ladder():
    """The guard against the opposite error: components that SUM to the total keep splitting."""
    text = ("כותרת הפעולה, חתימה נכונה (1.5): …\n"
            "מעבר תקין על המערך (3): …\n"
            "בדיקת סכום איברי המערך (1.5): …")
    assert _band_ladder(text, D("6")) is None
    t = _compile(text, "6")
    assert t.case != "band_ladder"
    assert len(t.earn_slots) > 1


@pytest.mark.parametrize("why,text,points", [
    ("only two bands", "CORRECT (6): a\nINCORRECT (0): b", "6"),
    ("top band is not the terminal's points",
     "CORRECT (5): a\nPARTIAL (3): b\nINCORRECT (0): c", "6"),
    ("bottom band is not zero",
     "CORRECT (6): a\nPARTIAL (3): b\nWEAK (1): c", "6"),
    ("values do not descend",
     "CORRECT (6): a\nPARTIAL (6): b\nINCORRECT (0): c", "6"),
])
def test_near_misses_are_not_ladders(why, text, points):
    assert _band_ladder(text, D(points)) is None, why


def test_the_detector_is_pure_and_reports_the_ladder_it_found():
    bands = _band_ladder(MINISTRY_MECHANICS, D("6"))
    assert bands == [("CORRECT", D("6")), ("PARTIALLY CORRECT", D("4")),
                     ("MINIMALLY CORRECT", D("2")), ("INCORRECT", D("0"))]
