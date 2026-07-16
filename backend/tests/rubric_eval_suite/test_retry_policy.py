"""PR B self-tests: point-mismatches are NON-RETRYABLE (PIPELINE 3.1.0).

Design under test: with both never-reconcile tripwires live (annotation_match +
pedagogical_match), a retry on a faithful teacher point-error can only "succeed"
by falsifying the numbers — so POINT_MISMATCH_* issues no longer TRIGGER a retry.
They downgrade IMMEDIATELY through the same _downgrade_persistent_mismatches path
the post-retry flow uses, producing an IDENTICAL RUBRIC_MISMATCH_WARNING →
rubric_mismatch annotation (type + anchor). Other retryable classes still retry,
and mismatches are re-evaluated after such a retry exactly as before.

No OpenAI: _call_llm (the pipeline's single LLM seam) is monkeypatched.

Run: PYTHONPATH=. python tests/rubric_eval_suite/test_retry_policy.py
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.services.docx_v3 import pipeline as pl
from app.services.docx_v3.pipeline import (
    RubricExtraction, QuestionExtraction, SubQuestionExtraction,
    CriterionExtraction, _extract_with_retry, _build_response,
)

_META = {"input_tokens": 10, "output_tokens": 5, "finish_reason": "stop", "model": "fake"}


def _mismatch_only_extraction() -> RubricExtraction:
    """One question, criteria sum 98 under a declared 100 — the bagrut shape:
    a faithful teacher point-error, and NOTHING else wrong."""
    return RubricExtraction(total_points=100, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=100,
        criteria=[CriterionExtraction(description="crit", points=98)])])


def _run(fake_llm):
    with patch.object(pl, "_call_llm", side_effect=fake_llm):
        return asyncio.run(_extract_with_retry("rendered"))


def test_mismatch_only_no_retry_downgrades_and_annotates():
    calls = []

    async def fake(rendered, feedback=None, **_):
        calls.append(feedback)
        return _mismatch_only_extraction(), dict(_META)

    ext, issues, retry_count, meta = _run(fake)
    assert len(calls) == 1, f"LLM must be called EXACTLY once, got {len(calls)}"
    assert calls[0] is None, "no retry feedback may be built for a mismatch-only draft"
    assert retry_count == 0
    warns = [i for i in issues if i.code == "RUBRIC_MISMATCH_WARNING"]
    assert len(warns) == 1 and not warns[0].retryable, issues
    # end-to-end: the downgraded issue becomes the SAME teacher-facing annotation
    resp, _w = _build_response(ext, "t", issues)
    anns = [(a.annotation_type, a.target_id) for a in resp.annotations]
    assert ("rubric_mismatch", "q1") in anns, anns
    print("  [ok] mismatch-only: 1 LLM call, 0 retries, immediate downgrade -> rubric_mismatch@q1")


def test_other_retryable_still_retries():
    calls = []
    broken = RubricExtraction(total_points=100, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=100,
        sub_questions=[SubQuestionExtraction(
            sub_question_id="א", text="", points=100,   # EMPTY_SQ_TEXT -> retryable
            criteria=[CriterionExtraction(description="crit", points=100)])])])
    fixed = RubricExtraction(total_points=100, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=100,
        sub_questions=[SubQuestionExtraction(
            sub_question_id="א", text="task text", points=100,
            criteria=[CriterionExtraction(description="crit", points=100)])])])

    async def fake(rendered, feedback=None, **_):
        calls.append(feedback)
        return (broken if len(calls) == 1 else fixed), dict(_META)

    ext, issues, retry_count, meta = _run(fake)
    assert len(calls) == 2 and retry_count == 1, (len(calls), retry_count)
    assert calls[1] and "has no task text" in calls[1], "retry feedback must carry the structural issue"
    assert not [i for i in issues if i.retryable]
    print("  [ok] non-mismatch retryable (EMPTY_SQ_TEXT): still retries exactly as before")


def test_mixed_retries_once_and_mismatch_downgrades():
    calls = []
    both = RubricExtraction(total_points=100, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=100,
        sub_questions=[SubQuestionExtraction(
            sub_question_id="א", text="", points=100,   # retryable trigger
            criteria=[CriterionExtraction(description="crit", points=98)])])])  # SQ mismatch
    text_fixed_mismatch_persists = RubricExtraction(total_points=100, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=100,
        sub_questions=[SubQuestionExtraction(
            sub_question_id="א", text="task text", points=100,
            criteria=[CriterionExtraction(description="crit", points=98)])])])

    async def fake(rendered, feedback=None, **_):
        calls.append(feedback)
        return (both if len(calls) == 1 else text_fixed_mismatch_persists), dict(_META)

    ext, issues, retry_count, meta = _run(fake)
    assert len(calls) == 2 and retry_count == 1, (len(calls), retry_count)
    # feedback of the (structural) retry still carries the mismatch guidance, as before
    assert "POINT_MISMATCH" in calls[1], calls[1]
    warns = [i for i in issues if i.code == "RUBRIC_MISMATCH_WARNING"]
    assert len(warns) == 1 and not warns[0].retryable, issues
    resp, _w = _build_response(ext, "t", issues)
    anns = [(a.annotation_type, a.target_id) for a in resp.annotations]
    assert ("rubric_mismatch", "q1.א") in anns, anns
    print("  [ok] mixed: ONE retry (for the structural issue), mismatch downgrades -> rubric_mismatch@q1.א")


if __name__ == "__main__":
    print("RETRY-POLICY (PIPELINE 3.1.0) SELF-TESTS")
    test_mismatch_only_no_retry_downgrades_and_annotates()
    test_other_retryable_still_retries()
    test_mixed_retries_once_and_mismatch_downgrades()
    print("ALL RETRY-POLICY SELF-TESTS PASSED")
