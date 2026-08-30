"""
segmentation_check — the marker↔key mismatch detector (pure, zero mocks).

CROSS-PINNED with frontend/src/utils/segmentation-check.test.ts: the grammar
fixtures below are the SAME strings — a rule change must keep both suites
green or the two implementations have drifted.

The end-to-end case is the real incident document (49f9a2e1, 2026-08-07):
the student skipped Q2 and P2 renumbered every later block one question
early, against the student's own markers.
"""
from app.services.transcription.segmentation_check import (
    DeclaredMarker,
    detect_mismatches,
    parse_leading_marker,
)


# ---------------------------------------------------------------------------
# Grammar (shared fixture strings — keep in sync with the TS suite)
# ---------------------------------------------------------------------------

def test_letter_paren_digit():
    assert parse_leading_marker("א) 3\npublic static int[] DiceStatistics(int[] arr)") \
        == DeclaredMarker(question=3, sub="א")


def test_digit_paren_letter():
    assert parse_leading_marker("3 (א\npublic static ...") \
        == DeclaredMarker(question=3, sub="א")


def test_question_word_then_sub_letter_composes():
    assert parse_leading_marker("שאלה 5\nא.\npublic bool IsSimilar(...)") \
        == DeclaredMarker(question=5, sub="א")


def test_sub_only_marker_claims_no_question():
    assert parse_leading_marker("ב)\npublic static void PrintStatistics(int[] arr)") \
        == DeclaredMarker(question=None, sub="ב")


def test_content_first_line_claims_nothing():
    # A trace-table answer — no marker, no claim.
    assert parse_leading_marker("if:\nreturned | x | i | arr[i]") \
        == DeclaredMarker()


def test_digits_inside_code_never_match():
    assert parse_leading_marker("int[] counters = new int[21];") == DeclaredMarker()


def test_marker_with_trailing_content_is_not_a_marker():
    # Full-match only: a digit-ish prefix glued to code claims nothing.
    assert parse_leading_marker("3 (א public static void F()") == DeclaredMarker()


def test_scan_stops_at_first_non_marker_line():
    # A marker BURIED below content does not count (mid-text markers are a
    # merge symptom, out of scope for v1 — leading lines only).
    assert parse_leading_marker("public int F()\nשאלה 4") == DeclaredMarker()


def test_two_digit_question():
    assert parse_leading_marker("שאלה 12") == DeclaredMarker(question=12)


# ---------------------------------------------------------------------------
# Detection + proposal resolution — the real incident document
# ---------------------------------------------------------------------------

INCIDENT_DOC = [
    (1, "א", "if:\nreturned | x | i | arr[i]"),
    (1, "ב", "if:\narr[i] | sum | i"),
    (2, "א", "א) 3\npublic static int[] DiceStatistics(int[] arr)"),
    (2, "ב", "ב)\npublic static void PrintStatistics(int[] arr)"),
    (3, "א", "א) 4\npublic int TotalEarnings()"),
    (3, "ב", "ב)\nבהנחה שהמערך מונים ממולא ב- null."),
    (4, "א", "שאלה 5\nא."),
    (4, "ב", "ב.\npublic bool HandleNewWorkshop (Workshop ws)"),
    (5, None, ""),
    (6, None, ""),
]


def test_incident_document_detection_and_proposals():
    mismatches = detect_mismatches(INCIDENT_DOC)
    by_key = {(m.question_number, m.sub_question_id): m for m in mismatches}

    # Exactly the three digit-bearing misassigned blocks fire.
    assert set(by_key) == {(2, "א"), (3, "א"), (4, "א")}

    # q2.א declares 3 → exact target (3, א) exists.
    assert by_key[(2, "א")].declared_question == 3
    assert by_key[(2, "א")].proposed_target == (3, "א")

    # q3.א declares 4 → (4, א) exists.
    assert by_key[(3, "א")].proposed_target == (4, "א")

    # q4.א declares 5 → (5, א) does NOT exist; bare (5, None) does (the
    # skipped-question shape P2 emits) — ruled fallback.
    assert by_key[(4, "א")].proposed_target == (5, None)


def test_sub_only_and_unmarked_blocks_never_fire():
    mismatches = detect_mismatches(INCIDENT_DOC)
    keys = {(m.question_number, m.sub_question_id) for m in mismatches}
    assert (2, "ב") not in keys      # "ב)" — no digit, no claim
    assert (1, "א") not in keys      # trace table — no marker


def test_matching_marker_is_silent():
    answers = [(3, "א", "א) 3\npublic static int[] DiceStatistics(int[] arr)")]
    assert detect_mismatches(answers) == []


def test_declared_target_missing_entirely_yields_no_proposal():
    # Declares question 9; no q9 container exists in any shape.
    answers = [
        (2, "א", "א) 9\nsome code"),
        (3, "א", "other"),
    ]
    (m,) = detect_mismatches(answers)
    assert m.declared_question == 9
    assert m.proposed_target is None
