"""§5.5 / Q-14 — the planner's request, built OFFLINE (nothing is sent): Sonnet 5,
adaptive thinking at effort high, native json_schema output, no forced tool use."""
from __future__ import annotations

from app.agents.grader.llm_factory import build_chat_model
from app.agents.plan_compiler.models import MODEL_CARDS
from app.agents.planner import planner_llm as pl
from app.agents.planner.schemas import ScopePlanOutput


def test_planner_request_is_sonnet5_adaptive_high_native_json_schema():
    card = MODEL_CARDS[pl.PLANNER_MODEL_KEY]
    llm = build_chat_model(card.provider, card.model_id, reasoning_effort=pl.PLANNER_EFFORT,
                           max_output_tokens=pl.PLANNER_MAX_OUTPUT_TOKENS, timeout_s=10,
                           thinking="adaptive")
    bound = llm.with_structured_output(ScopePlanOutput, method="json_schema", include_raw=True)
    raw = bound.first.steps__["raw"]
    payload = raw.bound._get_request_payload([("system", "s"), ("human", "u")], **raw.kwargs)
    output_config = payload.get("output_config") or {}
    assert payload["model"] == "claude-sonnet-5"
    assert payload["thinking"] == {"type": "adaptive"}          # never budget_tokens (400 on Sonnet 5)
    assert output_config.get("effort") == "high"
    assert (output_config.get("format") or {}).get("type") == "json_schema"
    assert not payload.get("tools") and not payload.get("tool_choice")
    assert "temperature" not in payload


def test_sonnet_55_planner_request_sets_effort_explicitly_and_never_forces_a_tool():
    """[AM-G18] Sonnet 5.5 rejects forced tool_choice and `thinking: disabled`, and
    its default effort is recalibrated: the request is adaptive, effort EXPLICIT,
    native json_schema, no tools, no temperature."""
    from app.agents.plan_compiler.models import SONNET_55_MODEL_KEY
    card = MODEL_CARDS[SONNET_55_MODEL_KEY]
    llm = build_chat_model(card.provider, card.model_id, reasoning_effort="high",
                           max_output_tokens=pl.PLANNER_MAX_OUTPUT_TOKENS, timeout_s=10,
                           thinking="adaptive")
    raw = llm.with_structured_output(ScopePlanOutput, method="json_schema",
                                     include_raw=True).first.steps__["raw"]
    payload = raw.bound._get_request_payload([("system", "s"), ("human", "u")], **raw.kwargs)
    oc = payload.get("output_config") or {}
    assert payload["model"] == "claude-sonnet-5-5" and payload["thinking"] == {"type": "adaptive"}
    assert oc.get("effort") == "high" and (oc.get("format") or {}).get("type") == "json_schema"
    assert not payload.get("tools") and not payload.get("tool_choice") and "temperature" not in payload


def test_the_app_price_cards_equal_the_eval_registry():
    from tests.eval_common.models_registry import spec
    for key, card in MODEL_CARDS.items():
        reg = spec(key)
        assert (card.model_id, card.price) == (reg.model_id, reg.price), key


def test_a_call_served_by_another_model_is_flagged_model_fallback():
    from app.agents.planner.planner import ScopePlanResult
    ok = ScopePlanResult("q1", "planner", [], [], [], usage=[{"model_fallback": False}])
    fb = ScopePlanResult("q1", "planner", [], [], [], usage=[{"model_fallback": True}])
    assert (ok.model_fallback, fb.model_fallback) == (False, True)
