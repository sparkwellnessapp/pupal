"""Self-tests for the table diagnostic. Instrument bugs have silently corrupted
conclusions in this suite four times (MISSION §4.3), so: GT against itself must
score exactly 1.0, known perturbations must score exactly as predicted, and the
parser must read every table exactly as the review UI does."""
import json
from pathlib import Path

import pytest

from .diag_tables import parse_tables, score_tables, table_looking_rows_refused
from .ground_truth import load_ground_truth, load_page_ground_truth

SUITE = Path(__file__).parent
PARITY = SUITE / "table_parser_parity.json"

TABLE = ("| x | i | arr[i] | ret |\n"
         "| 6 | 0 | 8 |  |\n"
         "|  | 1 | 5 |  |\n"
         "|  | 2 | 3 | T |")


# --- parity with the review UI's detector (the TS side asserts the same file) ---------

def _parity_cases():
    return json.loads(PARITY.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _parity_cases(), ids=lambda c: c["id"])
def test_reads_every_table_exactly_as_the_review_ui_does(case):
    got = [{"rows": [list(r) for r in t.rows], "hasHeader": t.has_header}
           for t in parse_tables(case["text"])]
    assert got == case["expected"]


# --- GT against itself ------------------------------------------------------------------

def test_every_gt_table_scores_one_against_itself():
    n = 0
    for p in sorted((SUITE / "raw_benchmarks").glob("*.md")):
        for text in load_page_ground_truth(p).as_dict().values():
            s = score_tables(text, text)
            assert s.shape_rate == 1.0 and s.cell_rate == 1.0
            n += s.expected
    assert n == 6          # the three Q1-answering bagrut fixtures, two tables each


def test_raw_and_draft_gt_tables_agree_cell_for_cell():
    """The same ink at two scopes: every draft table equals its raw table."""
    for p in sorted((SUITE / "raw_benchmarks").glob("bagrut*.md")):
        raw_tables = [t for text in load_page_ground_truth(p).as_dict().values()
                      for t in parse_tables(text)]
        draft_tables = [t for a in load_ground_truth(SUITE / "draft_benchmarks" / p.name).answers
                        for t in parse_tables(a.answer_text)]
        assert [t.rows for t in raw_tables] == [t.rows for t in draft_tables], p.stem


# --- known perturbations score exactly as predicted --------------------------------------

def test_one_wrong_cell_costs_exactly_one_cell():
    pred = TABLE.replace("| 5 |", "| 6 |")
    s = score_tables(TABLE, pred)
    assert s.shape_rate == 1.0
    assert (s.cells_exact, s.cells_total) == (15, 16)


def test_a_skipped_blank_cell_is_a_shape_miss_and_shifts_the_row():
    """The failure the P1 rule exists to prevent: the row is short at the FRONT,
    the UI pads at the END, and every value in it lands under the wrong header."""
    pred = TABLE.replace("|  | 1 | 5 |  |", "| 1 | 5 |")
    s = score_tables(TABLE, pred)
    assert s.shape_rate == 1.0                     # padded to 4 cols: shape survives…
    assert s.ragged_rows_pred == 1
    assert s.cells_exact == 16 - 3                 # …but x, i, arr[i] of that row are wrong


def test_a_missing_table_costs_every_cell():
    s = score_tables(TABLE, "no table here")
    assert (s.expected, s.found, s.shape_exact, s.cells_exact) == (1, 0, 0, 0)


def test_whitespace_and_case_inside_a_cell_are_free():
    pred = TABLE.replace("| T |", "|   t   |")
    assert score_tables(TABLE, pred).cell_rate == 1.0


def test_a_literal_or_in_a_cell_breaks_the_row_and_is_counted():
    pred = TABLE.replace("|  | 1 | 5 |  |", "|  | 1 | a || b |  |")
    s = score_tables(TABLE, pred)
    assert s.refused_rows_pred == 1


def test_code_containing_or_is_not_a_refused_table_row():
    assert table_looking_rows_refused('if (a == "n" || a == "N")') == []
