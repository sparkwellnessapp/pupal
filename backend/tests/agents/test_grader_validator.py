"""
Validator unit tests — pure, zero mocks, zero LLM calls.
Tests 1–10 from S7 spec §9.

These tests exercise validate_scope_grading() directly against hand-crafted
fixtures. The validator is the deterministic correctness core of the grading
pipeline; these tests protect it against regression.
"""
from decimal import Decimal
from typing import List, Optional

import pytest

from app.schemas.gradable import (
    GradableCriterion,
    GradableScope,
    GradableSubCriterion,
)
from app.schemas.ontology_types import (
    FlagReason,
    NumericPolicy,
    QuoteValidationStatus,
)
from app.agents.grader.schemas import QuestionGradingResponse, TerminalGrade
from app.agents.grader.validator import validate_scope_grading


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _make_policy(precision: str = "0.25") -> NumericPolicy:
    return NumericPolicy(precision=Decimal(precision))


def _make_scope(
    criterion_id: str = "c1",
    max_pts: float = 5.0,
    answer_text: str = "the student answer text",
    sub_criteria: Optional[List[GradableSubCriterion]] = None,
    extra_criteria: Optional[List[GradableCriterion]] = None,
) -> GradableScope:
    criteria = [
        GradableCriterion(
            criterion_id=criterion_id,
            description="Test criterion",
            points=Decimal(str(max_pts)),
            sub_criteria=sub_criteria,
        )
    ]
    if extra_criteria:
        criteria.extend(extra_criteria)
    return GradableScope(
        scope_kind="direct",
        question_id="q1",
        criteria=criteria,
        points=Decimal(str(max_pts)),
        student_answer_text=answer_text,
        alignment="matched",
    )


def _make_response(
    terminal_id: str = "c1",
    points_awarded: float = 3.0,
    quote_text: str = "",
    confidence: float = 0.9,
) -> QuestionGradingResponse:
    return QuestionGradingResponse(grades=[
        TerminalGrade(
            terminal_criterion_id=terminal_id,
            points_awarded=points_awarded,
            reasoning="reasoning text",
            quote_text=quote_text,
            confidence=confidence,
        )
    ])


# ---------------------------------------------------------------------------
# Test 1 — Closed-world: extra ID dropped + CLOSED_WORLD_VIOLATION + error annotation
# ---------------------------------------------------------------------------

def test_closed_world_extra_id_dropped():
    scope = _make_scope("c1", 5.0)
    response = QuestionGradingResponse(grades=[
        TerminalGrade(
            terminal_criterion_id="c1",
            points_awarded=3.0,
            reasoning="ok",
            quote_text="",
            confidence=0.9,
        ),
        TerminalGrade(
            terminal_criterion_id="EXTRA_UNKNOWN_ID",
            points_awarded=5.0,
            reasoning="sneaky",
            quote_text="",
            confidence=0.9,
        ),
    ])
    result = validate_scope_grading(response, scope, _make_policy())

    # Extra ID grade is dropped — only c1 in validated_grades
    ids = [vg.terminal_id for vg in result.validated_grades]
    assert "EXTRA_UNKNOWN_ID" not in ids
    assert "c1" in ids

    # Error annotation produced for the violation
    error_anns = [a for a in result.annotations if a.annotation_type == "closed_world_violation"]
    assert len(error_anns) == 1
    assert error_anns[0].severity.value == "error"


# ---------------------------------------------------------------------------
# Test 2 — Closed-world: missing ID → 0 points + UNGRADED_CRITERION + warning
# ---------------------------------------------------------------------------

def test_closed_world_missing_id_zero_points():
    scope = _make_scope(
        criterion_id="c1",
        max_pts=5.0,
        extra_criteria=[
            GradableCriterion(
                criterion_id="c2",
                description="Second criterion",
                points=Decimal("3.0"),
            )
        ],
    )
    # Response only grades c1, c2 is missing
    response = _make_response("c1", 3.0)
    result = validate_scope_grading(response, scope, _make_policy())

    c2_grade = next(vg for vg in result.validated_grades if vg.terminal_id == "c2")
    assert c2_grade.points_awarded == Decimal("0")

    c2_flags = [f for f in c2_grade.flags if f.reason == FlagReason.UNGRADED_CRITERION]
    assert len(c2_flags) == 1

    warn_anns = [a for a in result.annotations if a.annotation_type == "ungraded_criterion"]
    assert len(warn_anns) == 1
    assert warn_anns[0].severity.value == "warning"


# ---------------------------------------------------------------------------
# Test 3 — Bounds: over max clamped + BOUNDS_CLAMPED
# ---------------------------------------------------------------------------

def test_bounds_over_max_clamped():
    scope = _make_scope("c1", 5.0)
    response = _make_response("c1", 99.0)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.points_awarded == Decimal("5.0")

    clamped_flags = [f for f in vg.flags if f.reason == FlagReason.BOUNDS_CLAMPED]
    assert len(clamped_flags) == 1


# ---------------------------------------------------------------------------
# Test 4 — Bounds: negative clamped to 0 + BOUNDS_CLAMPED
# ---------------------------------------------------------------------------

def test_bounds_negative_clamped_to_zero():
    scope = _make_scope("c1", 5.0)
    response = _make_response("c1", -1.0)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.points_awarded == Decimal("0")

    clamped_flags = [f for f in vg.flags if f.reason == FlagReason.BOUNDS_CLAMPED]
    assert len(clamped_flags) == 1


# ---------------------------------------------------------------------------
# Test 5 — Precision: 0.3 rounds to 0.25 with precision=0.25; result is Decimal
# ---------------------------------------------------------------------------

def test_precision_rounding():
    scope = _make_scope("c1", 5.0)
    response = _make_response("c1", 0.3)
    result = validate_scope_grading(response, scope, _make_policy("0.25"))

    vg = result.validated_grades[0]
    assert vg.points_awarded == Decimal("0.25")
    assert isinstance(vg.points_awarded, Decimal)


# ---------------------------------------------------------------------------
# Test 6 — Quote: exact substring → EXACT, no flags
# ---------------------------------------------------------------------------

def test_quote_exact_substring():
    answer = "התלמיד כתב שהלולאה רצה עד סוף המערך ואז עצרה"
    quote = "הלולאה רצה עד סוף המערך"
    scope = _make_scope("c1", 5.0, answer_text=answer)
    response = _make_response("c1", 3.0, quote_text=quote)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.evidence_quote is not None
    assert vg.evidence_quote.validation_status == QuoteValidationStatus.EXACT

    quote_flags = [f for f in vg.flags if f.reason in (FlagReason.QUOTE_NOT_FOUND, FlagReason.FUZZY_MATCH)]
    assert len(quote_flags) == 0


# ---------------------------------------------------------------------------
# Test 7 — Quote: short exact quote in 200-word answer → EXACT (sliding-window critical test)
# ---------------------------------------------------------------------------

def test_quote_short_in_long_answer_exact():
    # Build a 200-word answer with the exact quote embedded near the middle
    preamble = " ".join(["מילה"] * 80)    # 80 filler Hebrew words before
    the_quote = "הפונקציה מחזירה את הערך המקסימלי"
    postamble = " ".join(["תוצאה"] * 80)  # 80 filler Hebrew words after
    long_answer = f"{preamble} {the_quote} {postamble}"

    scope = _make_scope("c1", 5.0, answer_text=long_answer)
    response = _make_response("c1", 4.0, quote_text=the_quote)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.evidence_quote is not None
    # Must be EXACT — the sliding-window must find it, not produce NOT_FOUND
    assert vg.evidence_quote.validation_status == QuoteValidationStatus.EXACT


# ---------------------------------------------------------------------------
# Test 8 — Quote: fuzzy match (≥0.85) → FUZZY + FUZZY_MATCH flag + info annotation
# ---------------------------------------------------------------------------

def test_quote_fuzzy_match():
    answer = "הלולאה רצה עד סוף המערך ואז עצרה"
    # One character different: "רץ" instead of "רצה"
    quote = "הלולאה רץ עד סוף המערך"
    scope = _make_scope("c1", 5.0, answer_text=answer)
    response = _make_response("c1", 3.0, quote_text=quote)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.evidence_quote is not None
    assert vg.evidence_quote.validation_status == QuoteValidationStatus.FUZZY

    fuzzy_flags = [f for f in vg.flags if f.reason == FlagReason.FUZZY_MATCH]
    assert len(fuzzy_flags) == 1

    info_anns = [a for a in result.annotations if a.annotation_type == "fuzzy_match"]
    assert len(info_anns) == 1
    assert info_anns[0].severity.value == "info"


# ---------------------------------------------------------------------------
# Test 9 — Quote: not found → NOT_FOUND + QUOTE_NOT_FOUND flag; grade stands (not zeroed)
# ---------------------------------------------------------------------------

def test_quote_not_found():
    answer = "התלמיד כתב תשובה על לולאות ותנאים"
    quote = "this text has nothing to do with the answer xyz123"
    scope = _make_scope("c1", 5.0, answer_text=answer)
    response = _make_response("c1", 3.0, quote_text=quote)
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    # Grade stands — not zeroed
    assert vg.points_awarded == Decimal("3.0")
    assert vg.evidence_quote is not None
    assert vg.evidence_quote.validation_status == QuoteValidationStatus.NOT_FOUND

    not_found_flags = [f for f in vg.flags if f.reason == FlagReason.QUOTE_NOT_FOUND]
    assert len(not_found_flags) == 1

    warn_anns = [a for a in result.annotations if a.annotation_type == "quote_not_found"]
    assert len(warn_anns) == 1
    assert warn_anns[0].severity.value == "warning"


# ---------------------------------------------------------------------------
# Test 10 — Quote: empty on non-zero award → QUOTE_NOT_FOUND flag, no evidence_quote
# ---------------------------------------------------------------------------

def test_empty_quote_on_nonzero_award():
    scope = _make_scope("c1", 5.0)
    response = _make_response("c1", 3.0, quote_text="")  # empty quote, non-zero award
    result = validate_scope_grading(response, scope, _make_policy())

    vg = result.validated_grades[0]
    assert vg.evidence_quote is None  # no quote object created

    not_found_flags = [f for f in vg.flags if f.reason == FlagReason.QUOTE_NOT_FOUND]
    assert len(not_found_flags) == 1
