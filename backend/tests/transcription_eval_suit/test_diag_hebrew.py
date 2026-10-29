"""Self-tests for the Hebrew diagnostic: GT against itself is exactly 1.0 / WER 0,
and hand-perturbed predictions score exactly as predicted."""
from pathlib import Path

from .diag_hebrew import hebrew_words, project, score_hebrew, score_units
from .ground_truth import load_ground_truth, load_page_ground_truth

SUITE = Path(__file__).parent
LINE = "int x = 0; // אם ספורטיבי מוסיפים עוד שעה"


def test_projection_keeps_only_hebrew_script():
    assert project(LINE) == "אםספורטיבימוסיפיםעודשעה"
    assert project("return x; // abc") == ""


def test_every_gt_page_and_answer_scores_one_against_itself():
    for p in sorted((SUITE / "raw_benchmarks").glob("*.md")):
        pages = load_page_ground_truth(p).as_dict()
        r = score_units(pages, pages)
        assert r["doc"]["ratio"] in (None, 1.0) and r["doc"]["word_errors"] == 0
        answers = {a.key: a.answer_text
                   for a in load_ground_truth(SUITE / "draft_benchmarks" / p.name).answers}
        r = score_units(answers, answers)
        assert r["doc"]["ratio"] in (None, 1.0) and r["doc"]["word_errors"] == 0


def test_letter_confusion_costs_one_char_and_one_word():
    pred = LINE.replace("ספורטיבי", "ספורטיבו")          # class (a): ו for י
    s = score_hebrew(LINE, pred)
    assert s.ratio < 1.0 and s.word_errors == 1 and s.gold_words == 5


def test_dropped_word_is_one_word_error():
    s = score_hebrew(LINE, LINE.replace(" עוד", ""))       # class (b)
    assert s.word_errors == 1


def test_reversed_word_order_is_caught_even_with_the_same_letters():
    """Class (c), the classic bidi failure: same letters, wrong order."""
    pred = "int x = 0; // שעה עוד מוסיפים ספורטיבי אם"
    s = score_hebrew(LINE, pred)
    assert s.ratio < 0.9 and s.word_errors >= 4


def test_code_errors_are_invisible_to_it_by_design():
    s = score_hebrew(LINE, LINE.replace("int x = 0;", "in x == 1"))
    assert s.ratio == 1.0 and s.word_errors == 0


def test_invented_hebrew_scores_zero():
    s = score_hebrew("return x;", "return x; // שלום")
    assert s.ratio == 0.0


def test_no_hebrew_either_side_is_not_a_measurement():
    assert score_hebrew("x = 1;", "x = 2;").ratio is None


def test_words_are_projected_to_their_letters():
    assert hebrew_words("//אם x ב-null") == ["אם", "ב"]


# --- the PROSE view: whole marker lines out, on both sides -----------------------

import pytest

from .diag_hebrew import strip_marker_lines


@pytest.mark.parametrize("line", ["שאלה 1", "שאלה 7 ", "שאלה א", "שאלה ב.", "א.", "(1)", "א) (1)", "(ב) (1)", "ג. 2"])
def test_whole_marker_lines_are_dropped(line):
    assert strip_marker_lines(line) == ""


@pytest.mark.parametrize("line", ["(2) לבדוק אם יש", "x = 1; // הערה", "המשך בעמ 33",
                                  "לא", "בב", "}", "a) b", "שאלה טובה"])
def test_prose_and_code_lines_stay(line):
    assert strip_marker_lines(line) == line


def test_a_marker_misread_moves_the_all_view_but_not_the_prose_view():
    gold = {1: "שאלה 1\nא.\nint x; // מונה"}
    pred = {1: "שאלה 1\nב.\nint x; // מונה"}     # the letter misread (digits are not Hebrew)
    assert score_units(gold, pred)["doc"]["ratio"] < 1.0
    assert score_units(gold, pred, markers=False)["doc"]["ratio"] == 1.0


def test_a_line_read_backwards_is_caught_at_line_level():
    from .hebrew_taxonomy import reversed_lines
    gold = "// מערך של מספרים אז כדאי להחזיר גם את המכינה"
    assert reversed_lines(gold, "// להחזיר כדאי אז מספרים של מערך") == ["// להחזיר כדאי אז מספרים של מערך"]
    assert reversed_lines(gold, "// מערך של מספרים אז כדאי") == []      # forward = not reversed
    assert reversed_lines(gold, "// של מערך") == []                     # too short to call
    # one misread word inside the reversal (noam p7's shape) is still caught
    assert reversed_lines(gold, "// המכינה את גם להחזיר כדאי על מספרים של מערך")
