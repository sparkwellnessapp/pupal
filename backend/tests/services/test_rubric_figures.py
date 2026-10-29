"""A rubric's drawings are kept, located and cropped — never dropped (2026-10-29). Pure."""
from __future__ import annotations

import io

from PIL import Image

from app.services.docx_v3.rubric_figures import (FIGURE_MARKER, attach_orphan_figures,
                                                 canonical_figure_lines, crop_figure)
from app.schemas.ontology_types import Criterion, ExtractRubricResponse, Question, SubQuestion


def test_the_readers_box_becomes_the_marker_with_its_page():
    text = "נתון משולש:\n[איור: משולש ישר זווית; \\(c=30\\) @ 120, 80, 560,400]\nחשבו"
    out = canonical_figure_lines(text, 3)
    assert "[איור p3 120,80,560,400: משולש ישר זווית; \\(c=30\\)]" in out
    assert FIGURE_MARKER.search(out).group(1) == "3"


def test_a_line_without_a_box_or_with_a_broken_one_stays_described():
    assert canonical_figure_lines("[איור: גרף]", 1) == "[איור: גרף]"
    assert canonical_figure_lines("[איור: גרף @ 500,10,400,90]", 1) == "[איור: גרף]"   # ymax < ymin


def _crit(cid):
    return Criterion(criterion_id=cid, index=0, description="d", points=10)


def test_a_dropped_drawing_is_put_back_on_the_part_it_stood_in():
    rendered = ("שאלה 1 נתון ארגז חול מלבני שמידותיו\n[איור p2 100,100,500,600: מלבן; 4.8, 3.6]\n"
                "שאלה 2 נתונה מפית בצורת משולש\nא. חשבו את גובה המפית בסנטימטרים\n"
                "[איור p4 50,50,400,500: משולש ABC]\n")
    resp = ExtractRubricResponse(rubric_name="r", total_points=20, questions=[
        Question(question_id="q1", question_type="computation", total_points=10,
                 question_text="נתון ארגז חול מלבני שמידותיו", criteria=[_crit("q1.c0")]),
        Question(question_id="q2", question_type="computation", total_points=10,
                 question_text="נתונה מפית בצורת משולש", sub_questions=[
                     SubQuestion(sub_question_id="א", index=0, points=10,
                                 text="חשבו את גובה המפית בסנטימטרים",
                                 criteria=[_crit("q2.א.c0")])]),
    ])
    out, n = attach_orphan_figures(resp, rendered)
    assert n == 2
    assert out.questions[0].question_text.endswith("[איור p2 100,100,500,600: מלבן; 4.8, 3.6]")
    assert out.questions[1].sub_questions[0].text.endswith("[איור p4 50,50,400,500: משולש ABC]")
    # a second pass finds nothing missing
    assert attach_orphan_figures(out, rendered)[1] == 0


def test_a_kept_drawing_is_not_duplicated():
    marker = "[איור p1 10,10,500,500: גרף]"
    resp = ExtractRubricResponse(rubric_name="r", total_points=10, questions=[
        Question(question_id="q1", question_type="computation", total_points=10,
                 question_text=f"נתון הגרף\n{marker}", criteria=[_crit("q1.c0")])])
    assert attach_orphan_figures(resp, f"נתון הגרף\n{marker}")[1] == 0


def test_the_crop_is_the_box_with_a_margin():
    img = Image.new("RGB", (1000, 2000), "white")
    png = crop_figure([img], 1, (100, 200, 300, 600))
    w, h = Image.open(io.BytesIO(png)).size
    assert 400 <= w <= 470 and 400 <= h <= 540          # (600-200)·1 + margin, (300-100)·2 + margin
    assert crop_figure([img], 2, (100, 200, 300, 600)) is None
