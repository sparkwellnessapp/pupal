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
                           max_output_tokens=pl.PLANNER_MAX_OUTPUT_TOKENS, timeout_s=10)
    llm = llm.model_copy(update={"thinking": dict(pl.PLANNER_THINKING)})
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
