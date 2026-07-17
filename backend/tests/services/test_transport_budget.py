"""
PR-2 — transport budget + the ONE retry layer.

Pure tests: fake exceptions, a fake clock, a mocked LLM. No network, no OpenAI,
no sleeping (the clock is injected; backoff sleeps are captured, not awaited).

What must hold:
  1. Predicate table — every exception class routes to retry | terminal | passthrough.
  2. insufficient_quota fails FAST with the billing message (all 3 observed 429s
     were this; the SDK used to retry it twice per call for nothing).
  3. THE F1 ARITHMETIC (fake clock): admit at T+60 remaining -> attempt 1 fails
     transient -> attempt 2 is REFUSED because it cannot fit -> clean raise naming
     BOTH facts, elapsed never exceeds the budget. This is the exact scenario the
     original spec's single-layer guard would have blown (2xT past the deadline).
  4. deadline=None => unbounded => byte-identical behavior (the eval path).
  5. Tier-B is SKIPPED (distinct greppable warning) when the budget cannot hold it,
     and the extraction still SUCCEEDS with Tier A results.
"""
import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from app.services.docx_v3.pipeline import (
    _DEADLINE_ATTEMPT_RESERVE_S,
    _DEADLINE_ENTRY_RESERVE_S,
    _Deadline,
    _classify_transport,
    _is_quota_exhausted,
    _transport_retry_async,
    _transport_retry_sync,
    CriterionExtraction,
    ExtractionConfig,
    ExtractionError,
    QuestionExtraction,
    RubricExtraction,
    extract_rubric_from_docx,
)

T = 360.0  # the ruled per-attempt bound


# ---------------------------------------------------------------------------
# Fake clock + exception builders
# ---------------------------------------------------------------------------

class FakeClock:
    """Monotonic clock we drive by hand — no sleeping, exact arithmetic."""
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status_code=status, request=httpx.Request("POST", "https://api.openai.com/v1/x"))


def rate_limit(code: str = "rate_limit_exceeded") -> openai.RateLimitError:
    return openai.RateLimitError(
        f"Error code: 429 - {{'error': {{'code': '{code}'}}}}",
        response=_resp(429), body={"error": {"code": code}},
    )


def quota_error() -> openai.RateLimitError:
    return rate_limit("insufficient_quota")


def conn_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/x"))


def timeout_error() -> openai.APITimeoutError:
    # REACHABLE for the first time in PR-2 — before the timeout existed this was a dead branch.
    return openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/x"))


def server_error() -> openai.InternalServerError:
    return openai.InternalServerError("boom", response=_resp(500), body=None)


def auth_error() -> openai.AuthenticationError:
    return openai.AuthenticationError("bad key", response=_resp(401), body=None)


def bad_request() -> openai.BadRequestError:
    return openai.BadRequestError("nope", response=_resp(400), body=None)


# ===========================================================================
# 1. Predicate table
# ===========================================================================

@pytest.mark.parametrize("exc, expected", [
    (conn_error(),    "transient"),
    (timeout_error(), "transient"),
    (server_error(),  "transient"),
    (rate_limit(),    "transient"),   # REAL rate pressure -> retry
    (quota_error(),   "quota"),       # billing exhaustion  -> NEVER retry
    (auth_error(),    "terminal"),
    (bad_request(),   "terminal"),
    (ValueError("parse failed"), "other"),   # content failure -> not our business
])
def test_predicate_table(exc, expected):
    assert _classify_transport(exc) == expected


def test_quota_detected_three_ways():
    assert _is_quota_exhausted(quota_error())                       # via .body/.code
    assert _is_quota_exhausted(Exception("... insufficient_quota")) # via message only
    assert not _is_quota_exhausted(rate_limit())                    # real pressure is NOT quota


# ===========================================================================
# 2. Quota fails fast with the billing message
# ===========================================================================

@pytest.mark.asyncio
async def test_quota_fails_fast_no_retry():
    calls = {"n": 0}

    async def invoke():
        calls["n"] += 1
        raise quota_error()

    with pytest.raises(ExtractionError) as ei:
        await _transport_retry_async(
            invoke, attempts=2, timeout_s=T, deadline=_Deadline(None), label="x")

    assert calls["n"] == 1, "quota must NOT be retried — it cannot succeed"
    msg = str(ei.value)
    assert "quota exhausted" in msg and "billing" in msg and "not retryable" in msg
    assert "RateLimitError" in msg, "underlying type must be carried in the string (B5)"
    assert isinstance(ei.value.__cause__, openai.RateLimitError)


@pytest.mark.asyncio
async def test_terminal_auth_fails_fast():
    calls = {"n": 0}

    async def invoke():
        calls["n"] += 1
        raise auth_error()

    with pytest.raises(ExtractionError, match="not retryable"):
        await _transport_retry_async(
            invoke, attempts=2, timeout_s=T, deadline=_Deadline(None), label="x")
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_content_failure_passes_through_untouched():
    """'other' must re-raise AS-IS — transport policy never touches content failures."""
    async def invoke():
        raise ValueError("structured output parse failed")

    with pytest.raises(ValueError):     # NOT wrapped in ExtractionError
        await _transport_retry_async(
            invoke, attempts=2, timeout_s=T, deadline=_Deadline(None), label="x")


# ===========================================================================
# 3. THE F1 ARITHMETIC — the scenario the single-layer guard would have blown
# ===========================================================================

@pytest.mark.asyncio
async def test_f1_transport_layer_refuses_unaffordable_retry():
    """Admit a logical call at exactly the entry guard (T + entry-reserve remaining),
    attempt 1 burns its full timeout and fails transient, then attempt 2 is REFUSED
    because the remainder (< T + 10) cannot fit another full attempt.

    Under the spec's ORIGINAL single-guard design this call would have proceeded to
    a 2nd full attempt and overrun the budget by ~2xT — blowing straight through the
    Cloud Run kill it was meant to prevent. The refusal is what makes the entry guard
    sound.
    """
    clock = FakeClock()
    budget = T + _DEADLINE_ENTRY_RESERVE_S            # 420 — exactly the entry guard
    deadline = _Deadline(budget, clock=clock)
    slept: List[float] = []

    async def fake_sleep(d: float) -> None:
        slept.append(d)
        clock.advance(d)

    attempts_made = {"n": 0}

    async def invoke():
        attempts_made["n"] += 1
        clock.advance(T)            # attempt burns its full per-attempt bound
        raise conn_error()          # ...and then fails transient

    with pytest.raises(ExtractionError) as ei:
        await _transport_retry_async(
            invoke, attempts=2, timeout_s=T, deadline=deadline,
            label="extraction LLM call", sleep=fake_sleep,
        )

    assert attempts_made["n"] == 1, "the 2nd attempt must be REFUSED, never started"

    msg = str(ei.value)
    # F1 ruling: TWO facts, ONE message — the transient cause AND the budget refusal
    assert "refused" in msg and "time budget exhausted" in msg
    assert "after transient failure" in msg
    assert "APIConnectionError" in msg
    assert isinstance(ei.value.__cause__, openai.APIConnectionError)

    # The budget was never exceeded: elapsed <= budget
    elapsed = clock.t
    assert elapsed <= budget, f"overran the budget: {elapsed} > {budget}"
    assert deadline.remaining() >= 0


@pytest.mark.asyncio
async def test_transient_retry_succeeds_within_budget():
    """The happy retry: attempt 1 fails transient, budget affords attempt 2, it wins."""
    clock = FakeClock()
    deadline = _Deadline(1000.0, clock=clock)         # plenty
    calls = {"n": 0}

    async def fake_sleep(d: float) -> None:
        clock.advance(d)

    async def invoke():
        calls["n"] += 1
        if calls["n"] == 1:
            clock.advance(5)
            raise conn_error()
        return "ok"

    out = await _transport_retry_async(
        invoke, attempts=2, timeout_s=T, deadline=deadline, label="x", sleep=fake_sleep)
    assert out == "ok" and calls["n"] == 2


@pytest.mark.asyncio
async def test_exhausted_attempts_names_the_cause():
    clock = FakeClock()
    deadline = _Deadline(10_000.0, clock=clock)

    async def fake_sleep(d: float) -> None:
        clock.advance(d)

    async def invoke():
        raise conn_error()

    with pytest.raises(ExtractionError) as ei:
        await _transport_retry_async(
            invoke, attempts=2, timeout_s=T, deadline=deadline, label="x", sleep=fake_sleep)
    assert "after 2 transport attempt(s)" in str(ei.value)
    assert "APIConnectionError" in str(ei.value)


def test_sync_twin_matches_async_policy():
    """Tier-B's sync path must enforce the identical policy."""
    clock = FakeClock()
    deadline = _Deadline(T + _DEADLINE_ENTRY_RESERVE_S, clock=clock)
    made = {"n": 0}

    def invoke():
        made["n"] += 1
        clock.advance(T)
        raise conn_error()

    with pytest.raises(ExtractionError) as ei:
        _transport_retry_sync(
            invoke, attempts=2, timeout_s=T, deadline=deadline,
            label="Tier-B call", sleep=lambda d: clock.advance(d))

    assert made["n"] == 1
    assert "refused" in str(ei.value) and "after transient failure" in str(ei.value)

    # and quota fails fast on the sync path too
    def quota_invoke():
        raise quota_error()

    with pytest.raises(ExtractionError, match="billing"):
        _transport_retry_sync(quota_invoke, attempts=2, timeout_s=T,
                              deadline=_Deadline(None), label="Tier-B call")


# ===========================================================================
# 4/5. Pipeline-level: unbounded default, and the Tier-B skip
# ===========================================================================

def _extraction() -> RubricExtraction:
    return RubricExtraction(
        document_title="t", total_points=100,
        questions=[QuestionExtraction(
            question_number=1, question_text="q", total_points=100,
            criteria=[CriterionExtraction(description="c", points=100)],
            sub_questions=[],
        )],
    )


def _meta() -> Dict[str, Any]:
    return {"input_tokens": 1, "output_tokens": 1, "finish_reason": "stop", "model": "m"}


async def _run(deadline_seconds, detect=True, tier_b_spy=None, llm_burns_s: float = 0.0):
    """Drive the real pipeline with a mocked LLM. `llm_burns_s` makes the mocked
    call consume real budget, which is the only way to reach a state where the
    validation loop was affordable but Tier-B is not."""
    def _detect(response, rendered, llm=None, warnings_sink=None):
        if tier_b_spy is not None:
            tier_b_spy["llm"] = llm          # None => Tier B was skipped/disabled
        return []

    async def _slow_call(*a, **kw):
        if llm_burns_s:
            await asyncio.sleep(llm_burns_s)
        return _extraction(), _meta()

    with patch("app.services.docx_v3.parser_render.render_docx_to_markdown", return_value="DOC"), \
         patch("app.services.docx_v3.pipeline._call_llm", side_effect=_slow_call), \
         patch("app.services.docx_v3.pipeline.detect_pedagogical_mistakes", side_effect=_detect):
        return await extract_rubric_from_docx(
            file_bytes=b"PK\x03\x04",
            extraction_config=ExtractionConfig(detect_pedagogical_mistakes=detect),
            name="t", deadline_seconds=deadline_seconds,
        )


@pytest.mark.asyncio
async def test_deadline_none_is_the_unbounded_eval_path():
    """deadline_seconds=None (what the eval runner passes) => no budget, no skip.
    This is why the eval battery and the gate are untouched BY CONSTRUCTION."""
    spy: Dict[str, Any] = {}
    result = await _run(None, tier_b_spy=spy)
    assert result.response is not None
    assert spy["llm"] is not None, "Tier B must run when the budget is unbounded"
    assert not any("Tier B skipped" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_tier_b_skipped_when_budget_cannot_hold_it(monkeypatch):
    """The state that matters: the validation loop WAS affordable and succeeded, but
    it consumed enough budget that Tier-B can no longer fit => SKIP with a DISTINCT
    warning, and the extraction still SUCCEEDS on Tier A results.

    Scaled down (tiny T + tiny reserves) so it runs in ~0.6s of real time while
    exercising the real production guards.
    """
    monkeypatch.setenv("EXTRACTION_LLM_TIMEOUT_S", "0.1")          # T = 0.1
    monkeypatch.setattr("app.services.docx_v3.pipeline._DEADLINE_ENTRY_RESERVE_S", 0.1)
    monkeypatch.setattr("app.services.docx_v3.pipeline._DEADLINE_ATTEMPT_RESERVE_S", 0.5)
    # entry need = T + 0.1 = 0.2   |   Tier-B need = T + 0.5 = 0.6

    spy: Dict[str, Any] = {}
    # budget 1.0 clears entry (>= 0.2); the call burns 0.6 => ~0.4 left < 0.6 needed
    result = await _run(1.0, tier_b_spy=spy, llm_burns_s=0.6)

    assert result.response is not None, "extraction must still SUCCEED on Tier A"
    assert spy["llm"] is None, "Tier B adjudicator must NOT be constructed"
    skips = [w for w in result.warnings if "Tier B skipped: time budget" in w]
    assert len(skips) == 1, f"expected exactly one distinct skip warning, got {result.warnings}"
    # Must never be confusable with a Tier-B TRANSPORT failure in artifacts
    assert "adjudication failed" not in skips[0]


@pytest.mark.asyncio
async def test_validation_entry_guard_refuses_and_names_the_budget():
    """A budget below the entry guard (T + entry-reserve) => refuse to start any
    logical call, with the budget message — a durable `failed` row, not a kill."""
    with pytest.raises(ExtractionError) as ei:
        await _run(10.0)
    assert "time budget exhausted" in str(ei.value)


def test_entry_guard_reserves_only_one_attempt_not_a_full_extra_timeout():
    """Regression — prod incident (2026-07-17): the validation-loop ENTRY guard
    over-reserved at T + 60. With a slow model (~213s/call) only 2 attempts fit the
    ~840s budget, so a COMPLETABLE extraction HARD-FAILED: the loop refused its final
    attempt (needing 420s) with 414s still free, instead of running it and returning
    gracefully at _MAX_RETRIES.

    The entry guard must reserve only what it takes to START a logical call — one
    transport attempt (T + attempt-reserve) plus a few seconds of per-iteration work
    (clean/validate/emit) — NEVER a second ~timeout. Check (2), the per-attempt guard,
    is what keeps a started call in budget, so the entry guard has no reason to hold
    the extra headroom. Both reserves are the slack ON TOP OF T."""
    assert _DEADLINE_ENTRY_RESERVE_S <= _DEADLINE_ATTEMPT_RESERVE_S + 15, (
        f"entry guard over-reserves ({_DEADLINE_ENTRY_RESERVE_S}s on top of T) — it will "
        f"refuse attempts a single call could still fit (the 2026-07-17 hard-fail-with-budget-free bug)"
    )
