"""table_rows.join_split_rows — format only, one shape only. Zero mocks."""
from app.services.transcription.two_phase.table_rows import join_split_rows as J

SPLIT = ("| returned | x | i | arr[i] | if:\n"
         "(arr[i] != 1 && arr[i] != x && x % arr[i] == 0) |\n"
         "|  | 6 | 0 | 8 | F |")


def test_the_flash_header_split_is_rejoined_with_one_space():
    assert J(SPLIT) == ("| returned | x | i | arr[i] | if: "
                        "(arr[i] != 1 && arr[i] != x && x % arr[i] == 0) |\n"
                        "|  | 6 | 0 | 8 | F |")


def test_no_character_is_added_or_lost_beyond_the_joining_space():
    strip = lambda s: "".join(s.split())       # noqa: E731
    assert strip(J(SPLIT)) == strip(SPLIT)


def test_well_formed_tables_and_prose_are_untouched():
    ok = "| a | b |\n|  | 1 |\nplain line\nint x = 0;"
    assert J(ok) == ok


def test_a_code_line_ending_in_logical_or_is_never_swallowed():
    t = "| a | b\nif (x == 1 ||\n    y == 2)"
    assert J(t) == t


def test_a_row_that_never_closes_is_left_alone():
    t = "| a | b\none\ntwo\nthree\nfour |"      # closes on the 4th line: past the window
    assert J(t) == t
    assert J("| a | b\n\n(c) |") == "| a | b\n\n(c) |"          # a blank line ends the search
    assert J("| a | b\n| c | d |") == "| a | b\n| c | d |"       # the next line is a row


def test_two_split_rows_in_one_table():
    t = "| h1 | long\nheader |\n| v1 | wrapped\nvalue |"
    assert J(t) == "| h1 | long header |\n| v1 | wrapped value |"


# --- the table re-read splice --------------------------------------------------------
from app.services.transcription.two_phase.table_rows import replace_tables, table_blocks

P1 = "שאלה 1\nא.\n| x | i\n(cond) |\n| 6 | 0 |\n\n2) הסבר בעברית\n| a | b |\n| 1 | 2 |"
DONOR = "שאלה 1\nא.\n| x | i | cond |\n| 6 | 0 | T |\n\n2) הסבר גרוע\n| a | b |\n| 1 | 3 |"


def test_table_blocks_are_runs_of_two_or_more_rows():
    assert table_blocks("| a |\ntext\n| b |\n| c |") == [(2, 3)]


def test_only_the_tables_are_swapped_the_prose_stays_p1s():
    out, why = replace_tables(P1, DONOR)
    assert why == "applied"
    assert "2) הסבר בעברית" in out and "הסבר גרוע" not in out       # P1's Hebrew kept
    assert "| x | i | cond |" in out and "| 1 | 3 |" in out           # donor's grids
    assert "(cond) |" not in out


def test_refuses_when_the_readings_disagree_on_how_many_tables():
    out, why = replace_tables(P1, "| only | one |\n| 1 | 2 |")
    assert (out, why) == (P1, "count_mismatch")
    assert replace_tables("no table here", DONOR) == ("no table here", "no_table")


def test_a_split_row_stays_inside_its_table_block():
    assert table_blocks(P1) == [(2, 4), (7, 8)]
