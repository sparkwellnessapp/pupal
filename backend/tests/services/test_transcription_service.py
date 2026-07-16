"""
S4 — Service modification tests.

Tests that the two new fields on TranscribedAnswer (page_numbers,
needed_grounding_retry) are correctly populated through the grounded path.
These tests call _merge_grounded_results and _transcribe_page_grounded
directly — no PDF or real VLM needed.
"""
import json
from unittest.mock import patch

import pytest

from app.services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    TranscribedAnswer,
    TranscriptionResult,
    VLMProvider,
)


# ---------------------------------------------------------------------------
# Fake VLM provider
# ---------------------------------------------------------------------------

class FakeVLMProvider(VLMProvider):
    """Returns a canned JSON string on every call."""

    def __init__(self, responses):
        # responses: list of dicts, one per call in order
        self._responses = iter(responses)
        self._call_count = 0

    @property
    def name(self) -> str:
        return "fake"

    def transcribe_images(self, images_b64, system_prompt, user_prompt, **kwargs) -> str:
        self._call_count += 1
        try:
            return json.dumps(next(self._responses))
        except StopIteration:
            return "{}"


def _make_service(responses):
    return HandwritingTranscriptionService(vlm_provider=FakeVLMProvider(responses))


# ---------------------------------------------------------------------------
# Test 1 — page_numbers populated correctly
# ---------------------------------------------------------------------------

def test_1_page_numbers_from_two_pages():
    """Q1 appears on both page 1 and page 2 — page_numbers should be [1, 2]."""
    page_results = [
        {
            "visual_grounding": {"class_name": "MyClass", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": "דני",
                "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "part one", "confidence": 0.9},
                ],
            },
        },
        {
            "visual_grounding": {"class_name": "MyClass", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": None,
                "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "part two", "confidence": 0.8},
                ],
            },
        },
    ]
    service = _make_service([])
    result = service._merge_grounded_results(page_results, "test.pdf", "דני")

    assert len(result.answers) == 1
    ans = result.answers[0]
    assert ans.page_numbers == [1, 2], f"Expected [1, 2], got {ans.page_numbers}"
    assert ans.answer_text == "part one\npart two"
    assert ans.confidence == 0.8  # min of 0.9, 0.8


# ---------------------------------------------------------------------------
# Test 2 — needed_grounding_retry propagated from retry tag
# ---------------------------------------------------------------------------

def test_2_needed_grounding_retry_tagged():
    """
    Page result carrying _needed_grounding_retry=True must propagate to
    the answer's needed_grounding_retry field.  A second page without the
    flag must remain False.
    """
    page_results = [
        {
            "_needed_grounding_retry": True,
            "visual_grounding": {"class_name": "X", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": "שרה",
                "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "ans1", "confidence": 0.85},
                ],
            },
        },
        {
            "visual_grounding": {"class_name": "X", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": None,
                "answers": [
                    {"question_number": 2, "sub_question_id": None, "answer_text": "ans2", "confidence": 0.95},
                ],
            },
        },
    ]
    service = _make_service([])
    result = service._merge_grounded_results(page_results, "test.pdf", "שרה")

    by_q = {a.question_number: a for a in result.answers}
    assert by_q[1].needed_grounding_retry is True
    assert by_q[2].needed_grounding_retry is False


# ---------------------------------------------------------------------------
# Test 3 — existing merge behavior unchanged (text join + min confidence)
# ---------------------------------------------------------------------------

def test_3_merge_behavior_unchanged():
    """Multi-page answer: text joined with newline, confidence is min."""
    page_results = [
        {
            "visual_grounding": {"class_name": "", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": "אבי",
                "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "line A", "confidence": 0.75},
                    {"question_number": 2, "sub_question_id": "א", "answer_text": "sub A", "confidence": 0.88},
                ],
            },
        },
        {
            "visual_grounding": {"class_name": "", "method_names": [], "field_names": []},
            "transcription": {
                "student_name": None,
                "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "line B", "confidence": 0.60},
                ],
            },
        },
    ]
    service = _make_service([])
    result = service._merge_grounded_results(page_results, "test.pdf", "אבי")

    by_key = {(a.question_number, a.sub_question_id): a for a in result.answers}

    q1 = by_key[(1, None)]
    assert q1.answer_text == "line A\nline B"
    assert q1.confidence == 0.60  # min(0.75, 0.60)
    assert q1.page_numbers == [1, 2]

    q2_sub = by_key[(2, "א")]
    assert q2_sub.answer_text == "sub A"
    assert q2_sub.confidence == 0.88
    assert q2_sub.page_numbers == [1]
    assert q2_sub.needed_grounding_retry is False
