"""
S8 — Grading runner service tests.

Tests the _do_grade() flow with a mocked DB session and a mocked GraderAgent.
No real OpenAI calls, no real database.

Critical tests:
  Test 3 (failed path)  — row never stranded in 'grading'
  Test 6 (Decimal JSONB) — model_dump(mode="json") round-trip
"""
from decimal import Decimal
from typing import List
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from contextlib import asynccontextmanager

from app.schemas.gradable import GradableCriterion, GradableScope, GradableTest, UnmatchedAnswer
from app.schemas.graded_test_draft import GradedTestDraft, ScopeOutcome
from app.services.grading_runner import _claim_grading, _compute_cost, _do_grade, run_grading


# ---------------------------------------------------------------------------
# Minimal fixture helpers
# ---------------------------------------------------------------------------

def _make_scope_outcome(question_id: str, possible: str, awarded: str) -> ScopeOutcome:
    return ScopeOutcome(
        scope_kind="direct",
        question_id=question_id,
        points_possible=Decimal(possible),
        points_awarded=Decimal(awarded),
        min_confidence=0.8,
        criterion_outcomes=[],
        graded_by="llm",
        input_tokens=100,
        output_tokens=50,
    )


def _make_draft(scopes: List[tuple]) -> GradedTestDraft:
    """Build a minimal GradedTestDraft. scopes = [(qid, possible, awarded), ...]"""
    scope_outcomes = [_make_scope_outcome(*s) for s in scopes]
    return GradedTestDraft(
        rubric_contract_version="test-rubric-v1",
        transcription_contract_version="test-trans-v1",
        model_version="gpt-4o",
        prompt_version="grader-v1",
        scope_outcomes=scope_outcomes,
        llm_calls_count=len(scope_outcomes),
        grading_duration_ms=500,
        total_input_tokens=sum(so.input_tokens for so in scope_outcomes),
        total_output_tokens=sum(so.output_tokens for so in scope_outcomes),
    )


def _make_graded_test_obj(graded_test_id, status="pending"):
    """Build a minimal mock GradedTest ORM row."""
    obj = MagicMock()
    obj.id = graded_test_id
    obj.status = status
    obj.transcription_id = uuid4()
    obj.rubric_id = uuid4()
    obj.draft_json = None
    obj.error_message = None
    return obj


def _make_db_mock(graded_test_obj, transcription_contract_json, rubric_contract_json):
    """Build an AsyncMock db session that yields the right objects on get()."""
    from app.models.grading import GradedTest, Rubric
    from app.models.transcription import Transcription

    transcription_obj = MagicMock()
    transcription_obj.contract_json = transcription_contract_json

    rubric_obj = MagicMock()
    rubric_obj.contract_json = rubric_contract_json

    async def _db_get(model, pk):
        if model is GradedTest:
            return graded_test_obj
        if model is Transcription:
            return transcription_obj
        if model is Rubric:
            return rubric_obj
        return None

    db = AsyncMock()
    db.get = AsyncMock(side_effect=_db_get)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Minimal valid contract JSON for compile()
# ---------------------------------------------------------------------------

MINIMAL_RUBRIC_CONTRACT_JSON = {
    "schema_version": "2.0",
    "rubric_id": str(uuid4()),
    "rubric_name": "Test Rubric",
    "subject": "computer_science",
    "programming_language": None,
    "numeric_policy": {"precision": "0.25"},
    "total_points": "15",
    "contract_version": str(uuid4()),
    "questions": [
        {
            "question_id": "q1",
            "question_text": "What is a variable?",
            "total_points": "10",
            "sub_questions": [],
            "criteria": [
                {
                    "criterion_id": "q1.c0",
                    "index": 0,
                    "description": "Correct definition",
                    "points": "10",
                    "sub_criteria": None,
                    "evaluation_guidance": None,
                    "notes": None,
                    "example_solution": None,
                    "trace_tables": None,
                    "context_tables": None,
                }
            ],
        },
        {
            "question_id": "q2",
            "question_text": "What is a loop?",
            "total_points": "5",
            "sub_questions": [],
            "criteria": [
                {
                    "criterion_id": "q2.c0",
                    "index": 0,
                    "description": "Correct definition",
                    "points": "5",
                    "sub_criteria": None,
                    "evaluation_guidance": None,
                    "notes": None,
                    "example_solution": None,
                    "trace_tables": None,
                    "context_tables": None,
                }
            ],
        },
    ],
}

MINIMAL_TRANSCRIPTION_CONTRACT_JSON = {
    "schema_version": "1.0",
    "contract_version": str(uuid4()),
    "answers": [
        {
            "question_number": 1,
            "sub_question_id": None,
            "answer_text": "A variable stores data",
        }
    ],
}


# ---------------------------------------------------------------------------
# Test 1 — Happy path: pending → grading → draft, aggregates correct
# ---------------------------------------------------------------------------

async def test_happy_path_pending_to_draft():
    """_do_grade owns ONLY grading→draft since the Cloud-Tasks CAS migration:
    the claim (pending→grading + grading_started_at) is commit 1 in
    _claim_grading; _do_grade fires exactly one commit. (Expectation updated
    2026-08-17, P1 harness chore — the old '2 commits' asserted the pre-CAS
    choreography.)"""
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "grading")   # post-claim state
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    draft = _make_draft([("q1", "10", "7")])

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = mock_agent_instance

        await _do_grade(db, graded_test_id)

    # Exactly ONE commit: grading → draft.
    assert db.commit.call_count == 1

    # Row advanced to 'draft' with draft_json set
    assert gt_obj.status == "draft"
    assert gt_obj.draft_json is not None
    assert gt_obj.draft_created_at is not None


# ---------------------------------------------------------------------------
# Test 2 — The CAS claim IS commit 1 (rewritten 2026-08-17, P1 harness chore:
# pending→grading + grading_started_at moved from _do_grade into
# _claim_grading with the Cloud-Tasks migration; the real UPDATE's values are
# integration-covered by the accept→pending→CAS seam tests).
# ---------------------------------------------------------------------------

async def test_claim_commits_once_and_reports_outcome():
    db = AsyncMock()
    won = MagicMock()
    won.rowcount = 1
    db.execute = AsyncMock(return_value=won)
    db.commit = AsyncMock()
    assert await _claim_grading(db, uuid4()) is True
    assert db.commit.call_count == 1                  # the claim IS a commit

    lost = MagicMock()
    lost.rowcount = 0
    db.execute = AsyncMock(return_value=lost)
    db.commit.reset_mock()
    assert await _claim_grading(db, uuid4()) is False  # duplicate delivery
    assert db.commit.call_count == 1                  # idempotent no-op commit


# ---------------------------------------------------------------------------
# Test 3 — Failed path (CRITICAL): exception → row='failed' + error_message,
# never left in 'grading'
# ---------------------------------------------------------------------------

async def test_failed_path_sets_error_message():
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "pending")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.grade = AsyncMock(side_effect=RuntimeError("agent exploded"))
        MockAgent.return_value = mock_agent_instance

        await _do_grade(db, graded_test_id)

    assert gt_obj.status == "failed"
    assert gt_obj.error_message is not None
    assert "RuntimeError" in gt_obj.error_message
    assert gt_obj.draft_json is None


# ---------------------------------------------------------------------------
# Test 4 — Idempotency (rewritten 2026-08-17, P1 harness chore): the guard
# moved from a _do_grade status check to run_grading's CAS — a duplicate
# delivery loses the claim (rowcount 0) and never constructs the agent.
# ---------------------------------------------------------------------------

async def test_idempotency_duplicate_delivery_noop():
    db = AsyncMock()
    lost = MagicMock()
    lost.rowcount = 0
    db.execute = AsyncMock(return_value=lost)
    db.commit = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield db

    with patch("app.services.grading_runner.get_db_context", _ctx), \
         patch("app.services.grading_runner.GraderAgent") as MockAgent:
        ran = await run_grading(uuid4())

    assert ran is False
    MockAgent.assert_not_called()
    assert db.commit.call_count == 1                  # the CAS's no-op commit only


# ---------------------------------------------------------------------------
# Test 5 — Aggregates correct: Σ points, percentage, divide-by-zero guard
# ---------------------------------------------------------------------------

async def test_aggregates_computed_correctly():
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "pending")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    # Two scopes: 7/10 + 4/5 = 11/15
    draft = _make_draft([("q1", "10", "7"), ("q2", "5", "4")])

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = mock_agent_instance

        await _do_grade(db, graded_test_id)

    assert gt_obj.total_score    == Decimal("11")
    assert gt_obj.total_possible == Decimal("15")
    assert gt_obj.percentage     == (Decimal("11") / Decimal("15") * 100).quantize(Decimal("0.01"))


async def test_divide_by_zero_guarded():
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "pending")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    draft = _make_draft([("q1", "0", "0")])

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = mock_agent_instance

        await _do_grade(db, graded_test_id)

    assert gt_obj.percentage == Decimal("0")


# ---------------------------------------------------------------------------
# Test 6 — Decimal JSONB round-trip (CRITICAL): model_dump(mode="json") used
# ---------------------------------------------------------------------------

async def test_decimal_jsonb_roundtrip():
    """
    The persisted draft_json must round-trip through GradedTestDraft.model_validate().
    This fails if model_dump() (without mode="json") was used — Decimal objects
    can't be JSON-serialised by the PostgreSQL JSONB driver.
    """
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "pending")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    draft = _make_draft([("q1", "10", "7.25")])

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        mock_agent_instance = AsyncMock()
        mock_agent_instance.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = mock_agent_instance

        await _do_grade(db, graded_test_id)

    # draft_json must be a plain dict (JSON-serialisable, no Decimal objects)
    assert isinstance(gt_obj.draft_json, dict)

    # Re-hydrate: proves all Decimal fields survived the mode="json" round-trip
    rehydrated = GradedTestDraft.model_validate(gt_obj.draft_json)
    assert rehydrated.scope_outcomes[0].points_awarded == Decimal("7.25")


# ---------------------------------------------------------------------------
# Test 7 — _compute_cost correctness
# ---------------------------------------------------------------------------

def test_compute_cost():
    from app.services.grading_runner import _compute_cost

    # 1000 input + 500 output
    cost = _compute_cost(1000, 500)
    # 1000/1000 * 0.005 + 500/1000 * 0.015 = 0.005 + 0.0075 = 0.0125
    assert cost == Decimal("0.0125")

    # Zero tokens → zero cost
    assert _compute_cost(0, 0) == Decimal("0")


# ---------------------------------------------------------------------------
# PR-G2 — the row-level exit (spec §2 PR-G2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_scopes_failed_marks_row_failed():
    """A draft in which EVERY scope failed is not a grade — it is a failed run
    wearing a draft's clothes. The row must land `failed` (terminal for the row;
    the chain continues via `retry`), never `draft`, or the teacher is offered a
    review screen of all-zeros with no way to tell it apart from a real zero."""
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "grading")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    draft = _make_draft([("q1", "10", "0"), ("q2", "10", "0")])
    for so in draft.scope_outcomes:
        object.__setattr__(so, "graded_by", "failed")

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        inst = AsyncMock()
        inst.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = inst
        await _do_grade(db, graded_test_id)

    assert gt_obj.status == "failed"
    assert gt_obj.error_message                      # the CHECK requires it


@pytest.mark.asyncio
async def test_partial_scope_failure_still_lands_a_draft():
    """The converse, so the rule above cannot be over-applied: per-scope
    isolation (CLAUDE.md §3.6) means SOME failures are a reviewable grade."""
    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "grading")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    draft = _make_draft([("q1", "10", "7"), ("q2", "10", "0")])
    object.__setattr__(draft.scope_outcomes[1], "graded_by", "failed")

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        inst = AsyncMock()
        inst.grade = AsyncMock(return_value=draft)
        MockAgent.return_value = inst
        await _do_grade(db, graded_test_id)

    assert gt_obj.status == "draft"


@pytest.mark.asyncio
async def test_row_budget_bounds_a_hung_grade(monkeypatch):
    """A grade that hangs anywhere — not only in the LLM call — must still give
    the row an exit. Without this a `grading` row waits for the liveness reaper
    (30 min) instead of failing at its own budget."""
    import app.services.grading_runner as runner_mod
    monkeypatch.setattr(runner_mod, "GRADING_ROW_BUDGET_S", 0.3, raising=True)

    graded_test_id = uuid4()
    gt_obj = _make_graded_test_obj(graded_test_id, "grading")
    db = _make_db_mock(gt_obj, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)

    async def _hang(*_a, **_kw):
        await asyncio.sleep(30)

    with patch("app.services.grading_runner.GraderAgent") as MockAgent:
        inst = AsyncMock()
        inst.grade = _hang
        MockAgent.return_value = inst
        await asyncio.wait_for(_do_grade(db, graded_test_id), timeout=6.0)

    assert gt_obj.status == "failed"
    assert "budget" in (gt_obj.error_message or "").lower()
