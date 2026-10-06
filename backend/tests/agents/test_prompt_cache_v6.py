"""[CL-2] prompt caching on the v6 calls: Anthropic only, prefixes unchanged; and the
v6 cost function prices cache writes at their premium. Offline: payloads are built, not sent."""
from __future__ import annotations

from app.agents.grader.llm_factory import build_chat_model
from app.agents.grader.plan_schemas import ScopeVerdictsV6
from app.agents.grader.prompt_cache import human_message, supports_cache, system_message
from tests.grading_eval_suite.v6_cost import usage_cost


def test_cache_breakpoints_reach_the_anthropic_request():
    llm = build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="low", thinking="adaptive")
    assert supports_cache(llm)
    raw = llm.with_structured_output(ScopeVerdictsV6, include_raw=True).first.steps__["raw"]
    msgs = [system_message("SYS", True), human_message("RUBRIC", "STUDENT", True)]
    p = raw.bound._get_request_payload(msgs, **raw.kwargs)
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    user = p["messages"][0]["content"]
    assert user[0]["text"] == "RUBRIC" and user[0]["cache_control"] == {"type": "ephemeral"}
    assert user[1]["text"] == "STUDENT" and "cache_control" not in user[1]


def test_without_caching_the_text_is_unchanged():
    assert system_message("SYS", False).content == "SYS"
    assert human_message("RUBRIC", "STUDENT", False).content == "RUBRIC\nSTUDENT"
    assert not supports_cache(object())


def test_the_v6_cost_prices_cache_writes_at_their_premium():
    base = {"model": "claude-sonnet-5-5", "calls": 1, "input_tokens": 1_000_000,
            "output_tokens": 0, "cached_input_tokens": 0, "cache_write_input_tokens": 0}
    assert round(usage_cost(base), 6) == 2.0
    assert round(usage_cost({**base, "cache_write_input_tokens": 1_000_000}), 6) == 2.5
    assert round(usage_cost({**base, "cached_input_tokens": 1_000_000}), 6) == 0.2
    assert usage_cost({**base, "calls": 0}) == 0.0
