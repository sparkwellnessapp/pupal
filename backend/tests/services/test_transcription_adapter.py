"""
S4 — Adapter annotation tests.

Constructs TranscriptionResult objects directly (no VLM, no PDF) and
calls build_transcription_draft.  Verifies the four annotation paths.
"""
import pytest

from app.services.handwriting_transcription_service import (
    TranscribedAnswer,
    TranscriptionResult,
)
from app.services.transcription_adapter import (
    LOW_CONFIDENCE_THRESHOLD,
    build_transcription_draft,
)


def _result(answers, student_name="דני"):
    return TranscriptionResult(student_name=student_name, filename="test.pdf", answers=answers)


def _answer(q=1, sub=None, text="hello", confidence=0.9, retry=False):
    return TranscribedAnswer(
        question_number=q,
        sub_question_id=sub,
        answer_text=text,
        confidence=confidence,
        needed_grounding_retry=retry,
        page_numbers=[1],
    )


# ---------------------------------------------------------------------------
# Test 4 — [?] in answer_text → vlm_unparseable WARNING
# ---------------------------------------------------------------------------

def test_4_unparseable_annotation():
    ans = _answer(text="public int foo() [?]")
    draft = build_transcription_draft(_result([ans]), page_count=1, model_version="fake", duration_ms=0)

    unparseable = [a for a in draft.annotations if a.annotation_type == "vlm_unparseable"]
    assert len(unparseable) == 1
    a = unparseable[0]
    assert a.severity == "warning"
    assert a.target_id == "q1"


# ---------------------------------------------------------------------------
# Test 5 — needed_grounding_retry=True → vlm_uncertainty WARNING
# ---------------------------------------------------------------------------

def test_5_retry_flag_annotation():
    ans = _answer(retry=True, confidence=0.95)
    draft = build_transcription_draft(_result([ans]), page_count=1, model_version="fake", duration_ms=0)

    uncertainty = [a for a in draft.annotations if a.annotation_type == "vlm_uncertainty"]
    assert len(uncertainty) == 1
    a = uncertainty[0]
    assert a.severity == "warning"
    assert a.target_id == "q1"


# ---------------------------------------------------------------------------
# Test 6 — confidence < 0.7 (no retry) → vlm_uncertainty INFO
# ---------------------------------------------------------------------------

def test_6_low_confidence_annotation():
    low_conf = LOW_CONFIDENCE_THRESHOLD - 0.1
    ans = _answer(confidence=low_conf, retry=False)
    draft = build_transcription_draft(_result([ans]), page_count=1, model_version="fake", duration_ms=0)

    uncertainty = [a for a in draft.annotations if a.annotation_type == "vlm_uncertainty"]
    assert len(uncertainty) == 1
    a = uncertainty[0]
    assert a.severity == "info"
    assert a.target_id == "q1"


def test_6_retry_takes_precedence_over_low_confidence():
    """When retry flag is set AND confidence is low, only one WARNING annotation emitted."""
    low_conf = LOW_CONFIDENCE_THRESHOLD - 0.1
    ans = _answer(confidence=low_conf, retry=True)
    draft = build_transcription_draft(_result([ans]), page_count=1, model_version="fake", duration_ms=0)

    uncertainty = [a for a in draft.annotations if a.annotation_type == "vlm_uncertainty"]
    assert len(uncertainty) == 1
    assert uncertainty[0].severity == "warning"  # not duplicated with info


# ---------------------------------------------------------------------------
# Test 7 — missing student name → student_name_missing INFO at "transcription"
# ---------------------------------------------------------------------------

def test_7_missing_student_name_none():
    ans = _answer()
    draft = build_transcription_draft(_result([ans], student_name=None), page_count=1, model_version="fake", duration_ms=0)

    missing = [a for a in draft.annotations if a.annotation_type == "student_name_missing"]
    assert len(missing) == 1
    a = missing[0]
    assert a.severity == "info"
    assert a.target_id == "transcription"


def test_7_missing_student_name_empty_string():
    ans = _answer()
    draft = build_transcription_draft(_result([ans], student_name=""), page_count=1, model_version="fake", duration_ms=0)

    missing = [a for a in draft.annotations if a.annotation_type == "student_name_missing"]
    assert len(missing) == 1


def test_7_present_student_name_no_annotation():
    ans = _answer()
    draft = build_transcription_draft(_result([ans], student_name="שרה לוי"), page_count=1, model_version="fake", duration_ms=0)

    missing = [a for a in draft.annotations if a.annotation_type == "student_name_missing"]
    assert len(missing) == 0
