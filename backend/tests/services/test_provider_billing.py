"""
A-8 — Billing visibility (owner ruling).

«A provider error meaning "out of credits" is logged at CRITICAL with the
structured tag PROVIDER_BILLING_EXHAUSTED, in the grading runner, the plan
builder and the feedback call. The teacher-facing failure copy is unchanged.»

Three things are pinned here, and each is a way the alert could silently die:

  * RECOGNITION — the real SDK exception shapes (constructed from the real
    classes) are recognised, including under a wrapper; a plain 429, a
    timeout, a 5xx and a parse failure are NOT (a false positive pages a human
    for traffic that heals itself).
  * THE LINE — CRITICAL, the tag at the START of the message string (the alert
    can only key on the message: `extra=` is never rendered here, §8), ids in
    the message, and never the provider's error body.
  * THE SITES — each hook fires on a billing error and changes NOTHING else:
    the grader still lands a flagged zero-outcome, the runner still fails the
    row with the same message, the plan still degrades to placeholder, the
    feedback still degrades to None with the same annotation. And the grader
    reports ONE fact per graded test, however many scopes failed.

Pure: no provider is ever called and no database is needed.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anthropic
import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from app.services.provider_billing import (
    PROVIDER_BILLING_EXHAUSTED,
    first_billing_exhausted,
    is_billing_exhausted,
    log_billing_exhausted,
)

_LOGGER = "app.services.provider_billing"


# ---------------------------------------------------------------------------
# Real provider error shapes
# ---------------------------------------------------------------------------

def _anthropic_status(cls, status: int, err_type: str, message: str):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    body = {"type": "error", "error": {"type": err_type, "message": message}}
    return cls(f"Error code: {status} - {body}",
               response=httpx.Response(status, request=req), body=body)


def anthropic_credit_too_low():
    """The exact error of the 2026-09-27 incident."""
    return _anthropic_status(
        anthropic.BadRequestError, 400, "invalid_request_error",
        "Your credit balance is too low to access the Anthropic API. Please go to "
        "Plans & Billing to upgrade or purchase credits.")


def _openai_status(cls, status: int, err: dict):
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return cls(f"Error code: {status} - {{'error': {err}}}",
               response=httpx.Response(status, request=req), body=err)


def openai_insufficient_quota():
    return _openai_status(openai.RateLimitError, 429, {
        "message": "You exceeded your current quota, please check your plan and "
                   "billing details. For more information on this error, read the "
                   "docs: https://platform.openai.com/docs/guides/error-codes/api-errors.",
        "type": "insufficient_quota", "param": None, "code": "insufficient_quota"})


def openai_plain_rate_limit():
    return _openai_status(openai.RateLimitError, 429, {
        "message": "Rate limit reached for gpt-4o in organization org-x on tokens per "
                   "min (TPM): Limit 30000, Used 29000, Requested 2000. Please try "
                   "again in 2s. Visit https://platform.openai.com/account/rate-limits "
                   "to learn more.",
        "type": "tokens", "param": None, "code": "rate_limit_exceeded"})


def gemini_billing_disabled():
    return genai_errors.ClientError(403, {"error": {
        "code": 403,
        "message": "This API method requires billing to be enabled. Please enable "
                   "billing on project #123 by visiting https://console.developers."
                   "google.com/billing/enable?project=123 then retry.",
        "status": "PERMISSION_DENIED",
        "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                     "reason": "BILLING_DISABLED", "domain": "googleapis.com"}]}})


def gemini_resource_exhausted(message="Resource exhausted. Please try again later. "
                                      "Please refer to https://cloud.google.com/vertex-ai/"
                                      "generative-ai/docs/error-code-429 for more details."):
    return genai_errors.ClientError(429, {"error": {
        "code": 429, "message": message, "status": "RESOURCE_EXHAUSTED"}})


# ---------------------------------------------------------------------------
# Recognition — the positives
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    anthropic_credit_too_low,
    lambda: _anthropic_status(anthropic.APIStatusError, 402, "billing_error",
                              "There is an issue with your billing."),
    openai_insufficient_quota,
    # the message alone, on an OpenAI exception whose body carried no code
    lambda: openai.RateLimitError(
        "Error code: 429 - You exceeded your current quota, please check your plan",
        response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
        body=None),
    lambda: _openai_status(openai.PermissionDeniedError, 403, {
        "message": "Your account is not active, please check your billing details.",
        "type": "billing_not_active", "param": None, "code": "billing_not_active"}),
    gemini_billing_disabled,
    lambda: genai_errors.ClientError(403, {"error": {
        "code": 403, "message": "Billing is not enabled for this project.",
        "status": "PERMISSION_DENIED"}}),
    # the shape the grader's own tests already use for a billing 429
    lambda: RuntimeError("Error code: 429 - insufficient_quota"),
], ids=["anthropic-credit-too-low", "anthropic-402-billing_error",
        "openai-insufficient_quota", "openai-exceeded-quota-wording",
        "openai-billing_not_active", "gemini-BILLING_DISABLED",
        "gemini-billing-not-enabled", "grader-test-shape"])
def test_each_providers_out_of_credit_error_is_recognised(make):
    assert is_billing_exhausted(make()) is True


def test_recognised_under_a_wrapper_through_cause_context_and_groups():
    """LangChain and our own code re-raise provider errors under their own
    types; the fact must survive the wrapping."""
    try:
        try:
            raise anthropic_credit_too_low()
        except Exception as inner:
            raise RuntimeError("plan build failed") from inner        # __cause__
    except RuntimeError as wrapped:
        assert is_billing_exhausted(wrapped)

    try:
        try:
            raise openai_insufficient_quota()
        except Exception:
            raise ValueError("while handling")                        # __context__
    except ValueError as implicit:
        assert is_billing_exhausted(implicit)

    group = ExceptionGroup("scopes", [ValueError("parse"), gemini_billing_disabled()])
    assert is_billing_exhausted(group)

    # a bare httpx wrapper: the provider's words are only in the response body
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(429, request=req,
                          text='{"error": {"code": "insufficient_quota"}}')
    assert is_billing_exhausted(httpx.HTTPStatusError("429", request=req, response=resp))


# ---------------------------------------------------------------------------
# Recognition — the negatives (a false positive pages a human at night)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    openai_plain_rate_limit,
    lambda: _anthropic_status(anthropic.RateLimitError, 429, "rate_limit_error",
                              "Number of request tokens has exceeded your per-minute "
                              "rate limit"),
    lambda: _anthropic_status(anthropic.InternalServerError, 500, "api_error",
                              "Internal server error"),
    lambda: _anthropic_status(anthropic.APIStatusError, 529, "overloaded_error",
                              "Overloaded"),
    lambda: _anthropic_status(anthropic.BadRequestError, 400, "invalid_request_error",
                              "prompt is too long: 250000 tokens > 200000 maximum"),
    lambda: _openai_status(openai.InternalServerError, 500, {
        "message": "The server had an error while processing your request.",
        "type": "server_error", "param": None, "code": None}),
    lambda: openai.APITimeoutError(request=httpx.Request("POST", "https://x")),
    lambda: anthropic.APITimeoutError(request=httpx.Request("POST", "https://x")),
    lambda: asyncio.TimeoutError(),
    lambda: ValueError("LLM parse failure: Invalid json output: {'verdicts': ["),
    gemini_resource_exhausted,
    # Gemini AI-Studio's per-minute 429 borrows OpenAI's sentence verbatim — it
    # is quota PRESSURE, not an empty account, which is why that sentence only
    # counts on an openai.* exception.
    lambda: gemini_resource_exhausted(
        "You exceeded your current quota, please check your plan and billing "
        "details. For more information on this error, head to: "
        "https://ai.google.dev/gemini-api/docs/rate-limits."),
    lambda: genai_errors.ServerError(503, {"error": {
        "code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}),
], ids=["openai-plain-429", "anthropic-plain-429", "anthropic-500", "anthropic-529",
        "anthropic-400-not-billing", "openai-500", "openai-timeout", "anthropic-timeout",
        "asyncio-timeout", "parse-failure", "gemini-429", "gemini-aistudio-429",
        "gemini-503"])
def test_rate_limits_timeouts_5xx_and_parse_failures_are_not_billing(make):
    assert is_billing_exhausted(make()) is False


def test_non_exceptions_and_cycles_are_simply_false():
    assert is_billing_exhausted(None) is False
    assert is_billing_exhausted(MagicMock()) is False          # a test double
    assert is_billing_exhausted("credit balance is too low") is False
    a, b = ValueError("a"), ValueError("b")
    a.__context__, b.__context__ = b, a                         # a cycle terminates
    assert is_billing_exhausted(a) is False


def test_first_billing_exhausted_keeps_the_first_fact():
    first, second = anthropic_credit_too_low(), anthropic_credit_too_low()
    seen = first_billing_exhausted(None, ValueError("parse"))
    assert seen is None
    seen = first_billing_exhausted(seen, first)
    seen = first_billing_exhausted(seen, second)
    seen = first_billing_exhausted(seen, ValueError("parse"))
    assert seen is first


# ---------------------------------------------------------------------------
# The line
# ---------------------------------------------------------------------------

def _billing_records(caplog) -> List[logging.LogRecord]:
    return [r for r in caplog.records
            if r.getMessage().startswith(PROVIDER_BILLING_EXHAUSTED)]


def test_the_line_is_critical_starts_with_the_tag_and_carries_the_ids(caplog):
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    gt = uuid4()
    logged = log_billing_exhausted(anthropic_credit_too_low(), site="grading",
                                   model="claude-sonnet-5", graded_test_id=gt)
    assert logged is True
    [rec] = _billing_records(caplog)
    assert rec.levelno == logging.CRITICAL
    msg = rec.getMessage()
    assert msg == (f"PROVIDER_BILLING_EXHAUSTED site=grading graded_test_id={gt} "
                   f"provider=anthropic model=claude-sonnet-5: BadRequestError")
    # the provider's body is NOT dumped: the class is enough to find the row
    assert "credit balance" not in msg and "Plans & Billing" not in msg


def test_the_line_names_the_provider_from_the_exception(caplog):
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    log_billing_exhausted(openai_insufficient_quota(), site="feedback", model="m",
                          graded_test_id="g")
    log_billing_exhausted(gemini_billing_disabled(), site="plan_build", model="m",
                          plan_id="p", rubric_id="r", stage="segmenter")
    msgs = [r.getMessage() for r in _billing_records(caplog)]
    assert msgs == [
        "PROVIDER_BILLING_EXHAUSTED site=feedback graded_test_id=g provider=openai "
        "model=m: RateLimitError",
        "PROVIDER_BILLING_EXHAUSTED site=plan_build plan_id=p rubric_id=r "
        "stage=segmenter provider=gemini model=m: ClientError",
    ]


def test_a_non_billing_error_logs_nothing(caplog):
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    assert log_billing_exhausted(openai_plain_rate_limit(), site="grading",
                                 graded_test_id="g") is False
    assert log_billing_exhausted(None, site="grading", graded_test_id="g") is False
    assert _billing_records(caplog) == []


# ---------------------------------------------------------------------------
# Site: the grader (v5 — production; v3 — the rollback) reports ONE fact up
# ---------------------------------------------------------------------------

def _v5_plan(terminals):
    from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
    return GradingPlan(
        plan_version="a8/v1", exam_id="ex", rubric_contract_sha256="0" * 64,
        terminals=[TerminalPlan(terminal_id=tid, points_possible=Decimal(pts), checks=[
            PlanCheck(check_id=f"{tid}.k1", description_he="בדיקה", kind="required",
                      points=Decimal(pts))]) for tid, pts in terminals])


class _RaisingLLM:
    """A chat-model stand-in whose every call raises `exc` (and counts)."""

    def __init__(self, exc):
        self.exc, self.calls = exc, 0

    def with_structured_output(self, schema, include_raw=False):
        outer = self

        class _Runner:
            async def ainvoke(self, messages):
                outer.calls += 1
                raise outer.exc
        return _Runner()


def _scope(qid, cid, pts="3", answer="the student wrote a loop here"):
    from app.schemas.gradable import GradableCriterion, GradableScope
    return GradableScope(scope_kind="direct", question_id=qid,
                         criteria=[GradableCriterion(criterion_id=cid, description="c",
                                                     points=Decimal(pts))],
                         points=Decimal(pts), student_answer_text=answer,
                         alignment="matched")


def _gradable(scopes):
    from app.schemas.gradable import GradableTest
    return GradableTest(rubric_contract_version="rc", transcription_contract_version="tc",
                        scopes=scopes, unmatched_transcription_answers=[],
                        total_points=sum(s.points for s in scopes))


@pytest.fixture
def no_backoff(monkeypatch):
    import app.agents.grader.grader as v3
    import app.agents.grader.grader_v5 as v5
    for mod in (v3, v5):
        monkeypatch.setattr(mod, "RETRY_BACKOFF_MIN", 0.0)
        monkeypatch.setattr(mod, "RETRY_BACKOFF_MAX", 0.0)


async def test_v5_grader_reports_one_fact_for_a_test_whose_every_scope_ran_dry(caplog):
    """Three scopes, three identical billing failures: the grader records the
    FIRST and logs nothing itself (it does not know the graded_test id). What
    it returns is exactly what it returned before A-8."""
    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.schemas.ontology_types import NumericPolicy
    caplog.set_level(logging.DEBUG, logger=_LOGGER)

    llm = _RaisingLLM(anthropic_credit_too_low())
    agent = PlanVerifyGrader(_v5_plan([("c1", "3"), ("c2", "3"), ("c3", "3")]),
                             NumericPolicy(), llm=llm, model_version="claude-sonnet-5")
    draft = await agent.grade(_gradable([_scope("q1", "c1"), _scope("q2", "c2"),
                                         _scope("q3", "c3")]))

    assert agent.billing_exhausted is llm.exc
    assert _billing_records(caplog) == []                  # the runner logs, once
    # unchanged: permanent ⇒ asked once per scope, flagged zero-outcomes, and
    # the failed scope still carries its checks for her to decide (OD-R1)
    assert llm.calls == 3
    assert [so.graded_by for so in draft.scope_outcomes] == ["failed"] * 3
    assert all(so.retry_count == 0 for so in draft.scope_outcomes)
    assert [a.annotation_type for a in draft.annotations].count("llm_failure") == 3
    assert all(co.checks for so in draft.scope_outcomes for co in so.criterion_outcomes)


async def test_v5_grader_records_billing_on_the_retried_path_too(no_backoff):
    """Gemini's BILLING_DISABLED is not in the grader's permanent set, so it is
    retried once and fails in the OTHER branch — which must record it too."""
    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.schemas.ontology_types import NumericPolicy

    llm = _RaisingLLM(gemini_billing_disabled())
    agent = PlanVerifyGrader(_v5_plan([("c1", "3")]), NumericPolicy(), llm=llm,
                             model_version="gemini-x")
    draft = await agent.grade(_gradable([_scope("q1", "c1")]))
    assert agent.billing_exhausted is llm.exc
    assert llm.calls == 2 and draft.scope_outcomes[0].retry_count == 1   # unchanged


async def test_v5_grader_records_nothing_for_an_ordinary_failure(no_backoff):
    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.schemas.ontology_types import NumericPolicy

    agent = PlanVerifyGrader(_v5_plan([("c1", "3")]), NumericPolicy(),
                             llm=_RaisingLLM(openai_plain_rate_limit()),
                             model_version="m")
    draft = await agent.grade(_gradable([_scope("q1", "c1")]))
    assert agent.billing_exhausted is None
    assert draft.scope_outcomes[0].graded_by == "failed"


async def test_v3_grader_reports_the_fact_up_too():
    """v3 is the LIVE rollback (`GRADER_ARCHITECTURE=v3`); a rollback must not
    silently drop the alert."""
    from app.agents.grader.grader import GraderAgent
    from app.schemas.ontology_types import NumericPolicy

    agent = GraderAgent(numeric_policy=NumericPolicy(), llm=MagicMock())
    billing = openai_insufficient_quota()
    agent._structured_llm = MagicMock()
    agent._structured_llm.ainvoke = AsyncMock(side_effect=billing)
    draft = await agent.grade(_gradable([_scope("q1", "c1"), _scope("q2", "c2")]))

    assert agent.billing_exhausted is billing
    assert [so.graded_by for so in draft.scope_outcomes] == ["failed", "failed"]
    assert agent._structured_llm.ainvoke.await_count == 2      # never retried (unchanged)


# ---------------------------------------------------------------------------
# Site: the grading runner — ONE line per graded test, row unchanged
# ---------------------------------------------------------------------------

class _FakeAgent:
    def __init__(self, draft, billing=None):
        self._draft, self.billing_exhausted = draft, billing

    async def grade(self, _gradable_test):
        return self._draft


def _runner_fixture():
    from tests.services.test_grading_runner import (
        MINIMAL_RUBRIC_CONTRACT_JSON, MINIMAL_TRANSCRIPTION_CONTRACT_JSON,
        _make_db_mock, _make_draft, _make_graded_test_obj, _stub_resolve)
    gid = uuid4()
    gt = _make_graded_test_obj(gid, "grading")
    db = _make_db_mock(gt, MINIMAL_TRANSCRIPTION_CONTRACT_JSON, MINIMAL_RUBRIC_CONTRACT_JSON)
    return SimpleNamespace(gid=gid, gt=gt, db=db, make_draft=_make_draft,
                           stub_resolve=_stub_resolve)


@pytest.fixture
def no_feedback_call(monkeypatch):
    """The runner calls attach_feedback on a landed draft; no provider here."""
    from app.config import settings
    monkeypatch.setattr(settings, "feedback_model_key", None, raising=False)


@pytest.mark.parametrize("billing", [True, False], ids=["billing", "ordinary"])
async def test_runner_logs_once_when_every_scope_ran_dry_and_the_row_is_unchanged(
        caplog, no_feedback_call, billing):
    from app.services.grading_runner import _do_grade
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    fx = _runner_fixture()
    draft = fx.make_draft([("q1", "10", "0"), ("q2", "5", "0")])
    for so in draft.scope_outcomes:
        object.__setattr__(so, "graded_by", "failed")
    agent = _FakeAgent(draft, anthropic_credit_too_low() if billing else None)

    with patch("app.services.grading_runner.resolve_plan_for_grade", new=fx.stub_resolve), \
         patch("app.services.grading_runner.build_grader", return_value=agent):
        await _do_grade(fx.db, fx.gid)

    # the teacher-facing outcome is exactly the pre-A-8 one
    assert fx.gt.status == "failed"
    assert fx.gt.error_message.startswith("AllScopesFailed: all 2 scope(s) failed")
    records = _billing_records(caplog)
    if not billing:
        assert records == []
        return
    [rec] = records
    assert rec.levelno == logging.CRITICAL
    assert rec.getMessage() == (
        f"PROVIDER_BILLING_EXHAUSTED site=grading graded_test_id={fx.gid} "
        f"provider=anthropic model=claude-sonnet-5: BadRequestError")


async def test_runner_logs_when_credit_ran_out_mid_grade_and_the_draft_still_lands(
        caplog, no_feedback_call):
    """Some scopes graded, then the account emptied: the draft lands as it
    always did — and the owner still hears about it."""
    from app.services.grading_runner import _do_grade
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    fx = _runner_fixture()
    draft = fx.make_draft([("q1", "10", "7"), ("q2", "5", "0")])
    object.__setattr__(draft.scope_outcomes[1], "graded_by", "failed")

    with patch("app.services.grading_runner.resolve_plan_for_grade", new=fx.stub_resolve), \
         patch("app.services.grading_runner.build_grader",
               return_value=_FakeAgent(draft, anthropic_credit_too_low())):
        await _do_grade(fx.db, fx.gid)

    assert fx.gt.status == "draft"
    assert len(_billing_records(caplog)) == 1


async def test_runner_top_level_catch_is_the_belt_and_still_logs_once(caplog):
    """A billing error that escaped every inner catch (here: raised straight out
    of `grade`) is caught by the runner's own failure handling — logged once,
    and the row fails with the same message it always did."""
    from app.services.grading_runner import _do_grade
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    fx = _runner_fixture()

    class _Raises:
        billing_exhausted = None

        async def grade(self, _t):
            raise anthropic_credit_too_low()

    with patch("app.services.grading_runner.resolve_plan_for_grade", new=fx.stub_resolve), \
         patch("app.services.grading_runner.build_grader", return_value=_Raises()):
        await _do_grade(fx.db, fx.gid)

    assert fx.gt.status == "failed"
    assert fx.gt.error_message.startswith("BadRequestError: Error code: 400")
    [rec] = _billing_records(caplog)
    assert rec.getMessage().startswith(
        f"PROVIDER_BILLING_EXHAUSTED site=grading graded_test_id={fx.gid} ")


async def test_runner_end_to_end_with_the_real_v5_grader_logs_exactly_once(
        caplog, no_feedback_call):
    """The whole chain, no fake agent: the real PlanVerifyGrader against a
    model that is out of credit on BOTH scopes → one line, not two."""
    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.services.grading_runner import _do_grade
    from tests.services.test_grading_runner import (
        MINIMAL_RUBRIC_CONTRACT_JSON, _make_db_mock, _make_graded_test_obj, _stub_resolve)
    caplog.set_level(logging.DEBUG, logger=_LOGGER)

    transcription = {"schema_version": "1.0", "contract_version": str(uuid4()),
                     "answers": [{"question_number": 1, "sub_question_id": None,
                                  "answer_text": "A variable stores data"},
                                 {"question_number": 2, "sub_question_id": None,
                                  "answer_text": "A loop repeats"}]}
    gid = uuid4()
    gt = _make_graded_test_obj(gid, "grading")
    db = _make_db_mock(gt, transcription, MINIMAL_RUBRIC_CONTRACT_JSON)
    llm = _RaisingLLM(anthropic_credit_too_low())

    def _build(*_a, numeric_policy=None, **_kw):
        return PlanVerifyGrader(_v5_plan([("q1.c0", "10"), ("q2.c0", "5")]),
                                numeric_policy, llm=llm, model_version="claude-sonnet-5")

    with patch("app.services.grading_runner.resolve_plan_for_grade", new=_stub_resolve), \
         patch("app.services.grading_runner.build_grader",
               side_effect=lambda rid, policy, **kw: _build(numeric_policy=policy)):
        await _do_grade(db, gid)

    assert llm.calls == 2                                  # both scopes asked
    assert gt.status == "failed" and gt.error_message.startswith("AllScopesFailed")
    [rec] = _billing_records(caplog)
    assert f"graded_test_id={gid}" in rec.getMessage()


# ---------------------------------------------------------------------------
# Site: the plan builder — placeholder exactly as before, plus ONE line
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def hobby_contract():
    from tests.grading_eval_suite.fixtures import load_bundle
    return load_bundle("dan_basiuk").rubric_contract


def _plan_factory(exc):
    class _LLM:
        def with_structured_output(self, schema, include_raw=True):
            class _R:
                async def ainvoke(self, messages):
                    raise exc
            return _R()
    return lambda model_key: _LLM()


async def test_plan_builder_logs_once_and_still_degrades_to_placeholder(
        caplog, hobby_contract):
    from app.services import plan_build_runner as pbr
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    plan_id = uuid4()
    res = await pbr.build_plan_for_contract(
        hobby_contract, plan_exam_id="rubric-x", plan_id=plan_id,
        llm_factory=_plan_factory(anthropic_credit_too_low()))

    # unchanged: W-2 — the wording degrades, the build still yields a plan
    assert res.wording_source == "placeholder"
    assert "router" in res.error_message and "segmenter" in res.error_message
    assert res.router_model is None and res.segmenter_model is None
    # the router AND the segmenter hit the empty account: one line, not two
    [rec] = _billing_records(caplog)
    assert rec.levelno == logging.CRITICAL
    assert rec.getMessage() == (
        f"PROVIDER_BILLING_EXHAUSTED site=plan_build plan_id={plan_id} "
        f"rubric_id=rubric-x stage=router provider=anthropic "
        f"model=claude-sonnet-5: BadRequestError")


async def test_plan_builder_outage_that_is_not_billing_logs_nothing(caplog, hobby_contract):
    from app.services import plan_build_runner as pbr
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    res = await pbr.build_plan_for_contract(
        hobby_contract, plan_exam_id="rubric-x",
        llm_factory=_plan_factory(ConnectionError("provider down")))
    assert res.wording_source == "placeholder"
    assert _billing_records(caplog) == []


# ---------------------------------------------------------------------------
# Site: the feedback call — None + the same INFO annotation, plus ONE line
# ---------------------------------------------------------------------------

class _BoomRunner:
    def __init__(self, exc):
        self.exc = exc

    async def ainvoke(self, *_a, **_kw):
        raise self.exc


async def test_feedback_agent_logs_billing_and_degrades_exactly_as_before(caplog):
    from app.agents.feedback.agent import FeedbackAgent
    caplog.set_level(logging.DEBUG, logger=_LOGGER)

    agent = FeedbackAgent(llm=_BoomRunner(anthropic_credit_too_low()),
                          model_version="claude-sonnet-5", graded_test_id="gt-1")
    block, annotations = await agent.generate(scopes=[("q1", "prompt text")])

    assert block is None
    [ann] = annotations
    assert ann.annotation_type == "feedback_unavailable"
    assert ann.message == ("לא נוצר משוב לתלמיד/ה עבור מבחן זה. "
                           "הציון והנימוקים אינם מושפעים.")          # copy unchanged
    [rec] = _billing_records(caplog)
    assert rec.getMessage() == ("PROVIDER_BILLING_EXHAUSTED site=feedback "
                                "graded_test_id=gt-1 provider=anthropic "
                                "model=claude-sonnet-5: BadRequestError")


async def test_feedback_ordinary_failure_logs_nothing(caplog):
    from app.agents.feedback.agent import FeedbackAgent
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    agent = FeedbackAgent(llm=_BoomRunner(RuntimeError("provider down")),
                          model_version="m")
    block, _ = await agent.generate(scopes=[("q1", "prompt text")])
    assert block is None and _billing_records(caplog) == []


async def test_attach_feedback_threads_the_graded_test_id_to_the_line(caplog, monkeypatch):
    import app.agents.feedback.runner as runner_mod
    from app.schemas.graded_test_draft import GradedTestDraft, ScopeOutcome
    caplog.set_level(logging.DEBUG, logger=_LOGGER)

    class _LLM:
        def with_structured_output(self, _schema, include_raw=False):
            return _BoomRunner(openai_insufficient_quota())

    monkeypatch.setattr(runner_mod.settings, "feedback_model_key", "fake-model",
                        raising=False)
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model",
                        lambda *a, **kw: _LLM())
    draft = GradedTestDraft(
        rubric_contract_version="rc", transcription_contract_version="tc",
        model_version="m", prompt_version="p",
        scope_outcomes=[ScopeOutcome(
            scope_kind="direct", question_id="q1", points_possible=Decimal("3"),
            points_awarded=Decimal("3"), min_confidence=0.9, criterion_outcomes=[],
            graded_by="llm", input_tokens=1, output_tokens=1)],
        llm_calls_count=1, grading_duration_ms=1, total_input_tokens=1,
        total_output_tokens=1)
    gid = uuid4()

    out = await runner_mod.attach_feedback(draft, graded_test_id=gid)

    assert out.feedback is None
    assert [a.annotation_type for a in out.annotations] == ["feedback_unavailable"]
    [rec] = _billing_records(caplog)
    assert rec.getMessage().startswith(
        f"PROVIDER_BILLING_EXHAUSTED site=feedback graded_test_id={gid} provider=openai")
