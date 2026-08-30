"""
PR-G2 — bounded grading (spec §2 PR-G2, the promoted PR-7).

The defect this pins: the production GraderAgent constructs `ChatOpenAI` with
neither `timeout` nor `max_retries` (grader.py). LangChain then passes
`timeout=None` EXPLICITLY, which overrides the SDK default and yields
httpx Timeout(None) — no timeout at all — while the SDK's hidden `max_retries=2`
adds 3 transport attempts. Wrapped in GA-3's own retry that is 6 unbounded calls
per scope, and a `grading` row with no exit.

Two bounds are required and they are NOT the same mechanism:
  * a per-call client timeout (production construction), and
  * a per-scope wall INSIDE the agent, which is what makes a hung provider
    become a flagged `failed` outcome instead of a hung task. Only the second
    is observable with an injected fake, which is why both are pinned here.

No provider is ever called (CLAUDE.md §8): the LLM seam is an AsyncMock.
"""
import asyncio
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.agents.grader.grader import GraderAgent
from app.schemas.gradable import GradableCriterion, GradableScope, GradableTest


def _scope(question_id: str = "q1", criterion_id: str = "c1") -> GradableScope:
    return GradableScope(
        scope_kind="direct",
        question_id=question_id,
        sub_question_id=None,
        criteria=[GradableCriterion(
            criterion_id=criterion_id,
            description="Test criterion",
            points=Decimal("5"),
            sub_criteria=None,
        )],
        points=Decimal("5"),
        student_answer_text="student answer",
        alignment="matched",
    )


def _gradable(scopes) -> GradableTest:
    return GradableTest(
        rubric_contract_version="rc-1",
        transcription_contract_version="tc-1",
        scopes=scopes,
        unmatched_transcription_answers=[],
        total_points=sum((sc.points for sc in scopes), Decimal("0")),
    )


# ---------------------------------------------------------------------------
# grading-card-has-bounded-exit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grading_card_has_bounded_exit(monkeypatch):
    """A provider that never answers must become a flagged `failed` outcome
    within the scope bound — never a hung grade. Red today: the agent has no
    wall, so `grade()` waits on the hang forever."""
    import app.agents.grader.grader as grader_mod

    # raising=True: if the knob does not exist the test fails LOUDLY here
    # rather than silently passing with no bound in place.
    monkeypatch.setattr(grader_mod, "GRADER_SCOPE_TIMEOUT_S", 0.2, raising=True)

    agent = GraderAgent()

    async def _hang(*_a, **_kw):
        await asyncio.sleep(30)

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = _hang

    # The outer wall is the test's own safety net, deliberately far above the
    # agent's: if the agent bounds correctly this never fires.
    draft = await asyncio.wait_for(agent.grade(_gradable([_scope()])), timeout=5.0)

    assert len(draft.scope_outcomes) == 1
    assert draft.scope_outcomes[0].graded_by == "failed"
    assert draft.scope_outcomes[0].points_awarded == Decimal("0")


@pytest.mark.asyncio
async def test_bounded_exit_isolates_per_scope(monkeypatch):
    """Per-scope isolation (CLAUDE.md §3.6) survives the bound: one hung scope
    does not take the other down, and the draft still lands."""
    import app.agents.grader.grader as grader_mod
    monkeypatch.setattr(grader_mod, "GRADER_SCOPE_TIMEOUT_S", 0.2, raising=True)

    agent = GraderAgent()
    calls = {"n": 0}

    async def _hang_first(*_a, **_kw):
        calls["n"] += 1
        await asyncio.sleep(30)

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = _hang_first

    draft = await asyncio.wait_for(
        agent.grade(_gradable([_scope("q1", "c1"), _scope("q2", "c2")])), timeout=8.0)

    assert len(draft.scope_outcomes) == 2                      # output totality
    assert all(so.graded_by == "failed" for so in draft.scope_outcomes)


# ---------------------------------------------------------------------------
# transient-retry-once-never-on-content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_is_retried_exactly_once(monkeypatch):
    """A wall expiry is a TRANSIENT transport condition: GA-3 grants it exactly
    one retry, never two. Pins the retry budget the unbounded client hid."""
    import app.agents.grader.grader as grader_mod
    monkeypatch.setattr(grader_mod, "GRADER_SCOPE_TIMEOUT_S", 0.2, raising=True)

    agent = GraderAgent()
    calls = {"n": 0}

    async def _hang(*_a, **_kw):
        calls["n"] += 1
        await asyncio.sleep(30)

    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = _hang

    await asyncio.wait_for(agent.grade(_gradable([_scope()])), timeout=5.0)

    # one attempt + one GA-3 retry, and no more
    assert calls["n"] == 2, f"expected exactly 2 attempts, got {calls['n']}"


# ---------------------------------------------------------------------------
# the production construction itself
# ---------------------------------------------------------------------------

def test_default_construction_is_bounded():
    """The DEFAULT path — what production runs — must carry a real timeout and
    must disable the SDK's hidden retry layer. Construction only; no call."""
    agent = GraderAgent()
    llm = agent._llm

    timeout = getattr(llm, "request_timeout", None) or getattr(llm, "timeout", None)
    assert timeout is not None, (
        "production ChatOpenAI has no timeout: LangChain passes timeout=None "
        "explicitly, which is httpx Timeout(None) — no bound at all")
    assert float(timeout) > 0

    assert getattr(llm, "max_retries", None) == 0, (
        "the SDK's hidden 2-retry layer is still live: it is unbounded and "
        "cannot tell insufficient_quota from real rate pressure")
