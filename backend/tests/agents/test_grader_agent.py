"""
GraderAgent integration tests — LLM mocked via unittest.mock.AsyncMock.
Tests 11–21 from S7 spec §9 (updated for S8 include_raw=True call-site change).

No real OpenAI calls. The mock target is agent._structured_llm.ainvoke.

After S8's include_raw=True change, ainvoke returns:
    {"raw": AIMessage(usage_metadata=...), "parsed": QuestionGradingResponse|None, "parsing_error": ...}
All success-path mocks use _make_raw_response(); transient exceptions still raise.
"""
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.schemas.gradable import (
    GradableCriterion,
    GradableScope,
    GradableSubCriterion,
    GradableTest,
    UnmatchedAnswer,
)
from app.schemas.ontology_types import AnnotationSeverity, FlagReason
from app.agents.grader.grader import GraderAgent
from app.agents.grader.prompt import GRADING_PROMPT_VERSION
from app.agents.grader.schemas import QuestionGradingResponse, TerminalGrade


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _make_scope_answered(
    question_id: str = "q1",
    criterion_id: str = "c1",
    max_pts: float = 5.0,
    answer_text: str = "student answer",
    sub_question_id: str | None = None,
    sub_criteria: list | None = None,
) -> GradableScope:
    criteria = [GradableCriterion(
        criterion_id=criterion_id,
        description="Test criterion",
        points=Decimal(str(max_pts)),
        sub_criteria=sub_criteria,
    )]
    return GradableScope(
        scope_kind="sub_question" if sub_question_id else "direct",
        question_id=question_id,
        sub_question_id=sub_question_id,
        criteria=criteria,
        points=Decimal(str(max_pts)),
        student_answer_text=answer_text,
        alignment="matched",
    )


def _make_scope_missing(
    question_id: str = "q1",
    criterion_id: str = "c1",
    max_pts: float = 5.0,
) -> GradableScope:
    return GradableScope(
        scope_kind="direct",
        question_id=question_id,
        criteria=[GradableCriterion(
            criterion_id=criterion_id,
            description="Test criterion",
            points=Decimal(str(max_pts)),
        )],
        points=Decimal(str(max_pts)),
        student_answer_text=None,
        alignment="answer_missing",
    )


def _make_gradable_test(scopes: List[GradableScope]) -> GradableTest:
    total = sum(s.points for s in scopes)
    return GradableTest(
        rubric_contract_version="test-rubric-v1",
        transcription_contract_version="test-trans-v1",
        scopes=scopes,
        unmatched_transcription_answers=[],
        total_points=total,
    )


def _make_llm_response(terminal_id: str, points: float, confidence: float = 0.9) -> QuestionGradingResponse:
    return QuestionGradingResponse(grades=[
        TerminalGrade(
            terminal_criterion_id=terminal_id,
            points_awarded=points,
            reasoning="reasoning",
            quote_text="student answer",
            confidence=confidence,
        )
    ])


def _make_raw_response(
    parsed: QuestionGradingResponse,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> dict:
    """Wrap a QuestionGradingResponse in the include_raw=True dict shape."""
    raw_msg = MagicMock()
    raw_msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return {"raw": raw_msg, "parsed": parsed, "parsing_error": None}


def _make_agent() -> GraderAgent:
    return GraderAgent()


# ---------------------------------------------------------------------------
# Test 11 — Skip path: no LLM call, NO_ANSWER flag, graded_by="skipped_no_answer"
# ---------------------------------------------------------------------------

async def test_skip_path_no_llm_call():
    agent = _make_agent()
    mock_ainvoke = AsyncMock()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = mock_ainvoke

    scope = _make_scope_missing("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    draft = await agent.grade(gt)

    # LLM was NOT called
    mock_ainvoke.assert_not_called()

    assert len(draft.scope_outcomes) == 1
    so = draft.scope_outcomes[0]
    assert so.graded_by == "skipped_no_answer"
    assert so.points_awarded == Decimal("0")
    assert so.input_tokens == 0
    assert so.output_tokens == 0
    assert draft.llm_calls_count == 0
    assert draft.total_input_tokens == 0
    assert draft.total_output_tokens == 0

    no_answer_flags = [f for f in so.flags if f.reason == FlagReason.NO_ANSWER]
    assert len(no_answer_flags) == 1


# ---------------------------------------------------------------------------
# Test 12 — Grade path: correct outcomes, graded_by="llm", tokens captured
# ---------------------------------------------------------------------------

async def test_grade_path_correct_outcomes():
    agent = _make_agent()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(
        return_value=_make_raw_response(_make_llm_response("c1", 4.0), input_tokens=120, output_tokens=60)
    )

    scope = _make_scope_answered("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    draft = await agent.grade(gt)

    so = draft.scope_outcomes[0]
    assert so.graded_by == "llm"
    assert so.points_awarded == Decimal("4.0")
    assert so.criterion_outcomes[0].points_awarded == Decimal("4.0")
    assert draft.llm_calls_count == 1
    assert so.input_tokens == 120
    assert so.output_tokens == 60
    assert draft.total_input_tokens == 120
    assert draft.total_output_tokens == 60


# ---------------------------------------------------------------------------
# Test 13 — Branch criterion aggregation
# ---------------------------------------------------------------------------

async def test_branch_criterion_aggregation():
    sub_criteria = [
        GradableSubCriterion(sub_criterion_id="sc1", description="sub 1", points=Decimal("3.0")),
        GradableSubCriterion(sub_criterion_id="sc2", description="sub 2", points=Decimal("2.0")),
    ]
    scope = _make_scope_answered("q1", "c1", 5.0, sub_criteria=sub_criteria)

    agent = _make_agent()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(
        return_value=_make_raw_response(QuestionGradingResponse(grades=[
            TerminalGrade(terminal_criterion_id="sc1", points_awarded=2.0, reasoning="r", quote_text="", confidence=0.8),
            TerminalGrade(terminal_criterion_id="sc2", points_awarded=1.5, reasoning="r", quote_text="", confidence=0.9),
        ]))
    )

    gt = _make_gradable_test([scope])
    draft = await agent.grade(gt)

    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.sub_criterion_outcomes is not None
    total_sub = sum(so.points_awarded for so in co.sub_criterion_outcomes)
    assert co.points_awarded == total_sub
    assert co.points_awarded == Decimal("3.5")


# ---------------------------------------------------------------------------
# Test 14 — Failure isolation (CRITICAL): persistent failure on one scope doesn't
# prevent others from succeeding.
# ---------------------------------------------------------------------------

async def test_failure_isolation_persistent():
    scopes = [
        _make_scope_answered("q1", "c1", 5.0),
        _make_scope_answered("q2", "c2", 3.0),
        _make_scope_answered("q3", "c3", 4.0),
    ]
    gt = _make_gradable_test(scopes)

    agent = _make_agent()

    call_count = {"q2": 0}

    async def selective_fail(*args, **kwargs):
        # Detect which scope is being graded by inspecting the messages
        msg_content = args[0][1].content if args else ""
        if "q2" in msg_content or "c2" in msg_content:
            call_count["q2"] += 1
            raise openai.RateLimitError("rate limited", response=MagicMock(), body=None)
        if "c1" in msg_content:
            return _make_raw_response(_make_llm_response("c1", 4.0))
        return _make_raw_response(_make_llm_response("c3", 3.0))

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=selective_fail)

    draft = await agent.grade(gt)

    # grade() must return, not raise
    assert len(draft.scope_outcomes) == 3

    # The failed scope is graded_by="failed" with retry_count=1
    failed_scope = next(so for so in draft.scope_outcomes if so.question_id == "q2")
    assert failed_scope.graded_by == "failed"
    assert failed_scope.retry_count == 1
    assert failed_scope.points_awarded == Decimal("0")

    # Error annotation exists for the failed scope
    error_anns = [a for a in draft.annotations if a.severity == AnnotationSeverity.ERROR]
    assert len(error_anns) >= 1

    # Other scopes are not affected
    other_scopes = [so for so in draft.scope_outcomes if so.question_id != "q2"]
    for so in other_scopes:
        assert so.graded_by == "llm"


# ---------------------------------------------------------------------------
# Test 15 — Output totality: len(scope_outcomes) == len(scopes) always
# ---------------------------------------------------------------------------

async def test_output_totality():
    scopes = [
        _make_scope_answered("q1", "c1", 5.0),
        _make_scope_missing("q2", "c2", 3.0),
        _make_scope_answered("q3", "c3", 4.0),
        _make_scope_missing("q4", "c4", 2.0),
        _make_scope_answered("q5", "c5", 1.0),
    ]
    gt = _make_gradable_test(scopes)

    agent = _make_agent()

    async def respond(*args, **kwargs):
        msg_content = args[0][1].content if args else ""
        for qid in ("q1", "q3", "q5"):
            if qid in msg_content:
                cid = qid.replace("q", "c")
                return _make_raw_response(_make_llm_response(cid, 2.0))
        return _make_raw_response(_make_llm_response("c1", 2.0))

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=respond)

    draft = await agent.grade(gt)
    assert len(draft.scope_outcomes) == len(scopes)


# ---------------------------------------------------------------------------
# Test 16 — Counters: llm_calls_count and grading_duration_ms
# ---------------------------------------------------------------------------

async def test_counters():
    scopes = [
        _make_scope_answered("q1", "c1", 5.0),
        _make_scope_answered("q2", "c2", 3.0),
        _make_scope_missing("q3", "c3", 4.0),
    ]
    gt = _make_gradable_test(scopes)
    agent = _make_agent()

    async def respond(*args, **kwargs):
        msg_content = args[0][1].content if args else ""
        cid = "c1" if "q1" in msg_content else "c2"
        return _make_raw_response(_make_llm_response(cid, 2.0), input_tokens=80, output_tokens=40)

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=respond)

    draft = await agent.grade(gt)
    assert draft.llm_calls_count == 2  # q1 + q2; q3 was skipped
    assert draft.grading_duration_ms >= 0
    # Two LLM-graded scopes × 80 input tokens each
    assert draft.total_input_tokens == 160
    assert draft.total_output_tokens == 80


# ---------------------------------------------------------------------------
# Test 17 — Empty teacher_overrides
# ---------------------------------------------------------------------------

async def test_empty_teacher_overrides():
    scope = _make_scope_missing("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    agent = _make_agent()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock()

    draft = await agent.grade(gt)
    assert draft.teacher_overrides == {}


# ---------------------------------------------------------------------------
# Test 18 — Transient retry success (CRITICAL): first call raises timeout,
# second succeeds; scope graded_by="llm" with retry_count=1, no failure annotation.
# ---------------------------------------------------------------------------

async def test_transient_retry_success():
    scope = _make_scope_answered("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    agent = _make_agent()

    call_count = [0]

    async def first_fails_second_succeeds(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise openai.APITimeoutError(request=MagicMock())
        return _make_raw_response(_make_llm_response("c1", 4.0), input_tokens=110, output_tokens=55)

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=first_fails_second_succeeds)

    draft = await agent.grade(gt)

    so = draft.scope_outcomes[0]
    assert so.graded_by == "llm"
    assert so.points_awarded == Decimal("4.0")
    assert so.retry_count == 1

    # No failure annotation
    failure_anns = [a for a in draft.annotations if a.annotation_type == "llm_failure"]
    assert len(failure_anns) == 0

    # LLM was called exactly twice
    assert call_count[0] == 2

    # Tokens from the successful second call are captured
    assert so.output_tokens == 55


# ---------------------------------------------------------------------------
# Test 19 — No retry on content failure (CRITICAL GA-3 boundary):
# LLM returns successfully but with a wrong criterion ID (closed-world content failure).
# Mock called exactly once; scope has CLOSED_WORLD_VIOLATION flag; graded_by="llm".
# ---------------------------------------------------------------------------

async def test_no_retry_on_content_failure():
    scope = _make_scope_answered("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    agent = _make_agent()

    call_count = [0]

    async def returns_wrong_id(*args, **kwargs):
        call_count[0] += 1
        # Returns a grade for a criterion ID not in the scope — a content failure
        return _make_raw_response(QuestionGradingResponse(grades=[
            TerminalGrade(
                terminal_criterion_id="WRONG_ID_NOT_IN_SCOPE",
                points_awarded=5.0,
                reasoning="wrong",
                quote_text="",
                confidence=0.99,
            )
        ]))

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=returns_wrong_id)

    draft = await agent.grade(gt)

    # LLM called exactly once — no retry on content failures (GA-3)
    assert call_count[0] == 1

    # Scope has closed-world violation annotation (error), NOT graded_by="failed"
    so = draft.scope_outcomes[0]
    assert so.graded_by == "llm"  # the call succeeded; validator flagged the content

    cw_anns = [a for a in draft.annotations if a.annotation_type == "closed_world_violation"]
    assert len(cw_anns) >= 1


# ---------------------------------------------------------------------------
# Test 20 — Confidence propagation + prompt_version
# ---------------------------------------------------------------------------

async def test_confidence_propagation_and_prompt_version():
    sub_criteria = [
        GradableSubCriterion(sub_criterion_id="sc1", description="sub 1", points=Decimal("3.0")),
        GradableSubCriterion(sub_criterion_id="sc2", description="sub 2", points=Decimal("2.0")),
    ]
    scope_with_branch = _make_scope_answered("q1", "c1", 5.0, sub_criteria=sub_criteria)
    scope_missing = _make_scope_missing("q2", "c2", 3.0)
    gt = _make_gradable_test([scope_with_branch, scope_missing])

    agent = _make_agent()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(
        return_value=_make_raw_response(QuestionGradingResponse(grades=[
            TerminalGrade(terminal_criterion_id="sc1", points_awarded=2.0, reasoning="r", quote_text="", confidence=0.9),
            TerminalGrade(terminal_criterion_id="sc2", points_awarded=1.5, reasoning="r", quote_text="", confidence=0.7),
        ]))
    )

    draft = await agent.grade(gt)

    # Branch criterion confidence = min of leaf confidences
    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.confidence == pytest.approx(0.7)

    # Scope min_confidence = min across all terminals
    assert draft.scope_outcomes[0].min_confidence == pytest.approx(0.7)

    # Skipped scope: min_confidence = 0.0
    assert draft.scope_outcomes[1].min_confidence == 0.0

    # prompt_version stamped correctly
    assert draft.prompt_version == GRADING_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Test 21 — Parse-error path (S8 addition): parsing_error non-None is treated as
# non-transient failure; LLM called exactly once (GA-3: no retry);
# scope graded_by="failed"; grade() returns without raising.
# ---------------------------------------------------------------------------

async def test_no_retry_on_parsing_error():
    scope = _make_scope_answered("q1", "c1", 5.0)
    gt = _make_gradable_test([scope])
    agent = _make_agent()

    call_count = [0]

    async def returns_parse_error(*args, **kwargs):
        call_count[0] += 1
        raw_msg = MagicMock()
        raw_msg.usage_metadata = {"input_tokens": 50, "output_tokens": 0}
        return {"raw": raw_msg, "parsed": None, "parsing_error": "JSON schema mismatch: missing 'grades'"}

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=returns_parse_error)

    draft = await agent.grade(gt)

    # grade() returns normally — scope failure is isolated
    assert len(draft.scope_outcomes) == 1

    so = draft.scope_outcomes[0]
    assert so.graded_by == "failed"
    assert so.points_awarded == Decimal("0")
    assert so.retry_count == 0  # ValueError (non-transient) — no retry per GA-3

    # LLM was called exactly once
    assert call_count[0] == 1

    # Error annotation produced
    failure_anns = [a for a in draft.annotations if a.annotation_type == "llm_failure"]
    assert len(failure_anns) == 1
    assert failure_anns[0].severity == AnnotationSeverity.ERROR
