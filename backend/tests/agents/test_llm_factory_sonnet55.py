"""[AM-G18] Sonnet 5.5 in the grader's model factory, and served-model provenance.
Offline: the request payload is built, never sent."""
from __future__ import annotations

import pytest

from app.agents.grader.llm_factory import build_chat_model, serves_requested
from app.agents.grader.plan_schemas import ScopeVerificationResponse


def _payload(llm):
    raw = llm.with_structured_output(ScopeVerificationResponse, include_raw=True).first.steps__["raw"]
    return raw.bound._get_request_payload([("system", "s"), ("human", "u")], **raw.kwargs)


def test_sonnet_55_requires_effort_and_thinking_on_every_call():
    with pytest.raises(ValueError, match="AM-G18"):
        build_chat_model("anthropic", "claude-sonnet-5-5")
    with pytest.raises(ValueError, match="AM-G18"):
        build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="high")
    with pytest.raises(ValueError, match="AM-G18"):
        build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="high", thinking="disabled")


def test_sonnet_55_verifier_request_is_native_json_schema_with_explicit_effort_and_thinking():
    """5.5 refuses forced tool_choice (400): the grader's unchanged
    `with_structured_output(schema, include_raw=True)` rides json_schema instead."""
    p = _payload(build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="high",
                                  thinking="between_tools"))
    oc = p.get("output_config") or {}
    assert p["model"] == "claude-sonnet-5-5" and p["thinking"] == {"type": "between_tools"}
    assert oc.get("effort") == "high" and (oc.get("format") or {}).get("type") == "json_schema"
    assert not p.get("tools") and not p.get("tool_choice") and "temperature" not in p


def test_the_sonnet_5_production_request_is_unchanged():
    """The production pin (grader-v5.4 + Sonnet 5) keeps its forced-tool structured
    output and sends no thinking and no effort — AM-G18 changes nothing there."""
    p = _payload(build_chat_model("anthropic", "claude-sonnet-5"))
    assert p["model"] == "claude-sonnet-5" and p.get("tools") and p.get("tool_choice")
    assert "thinking" not in p and "temperature" not in p
    assert "effort" not in (p.get("output_config") or {})


def test_thinking_is_a_claude_5_knob_only():
    with pytest.raises(ValueError, match="Claude 5"):
        build_chat_model("openai", "gpt-4o", thinking="adaptive")


@pytest.mark.parametrize("requested,served,ok", [
    ("claude-sonnet-5", "claude-sonnet-5", True),
    ("claude-sonnet-5", "claude-sonnet-5-20260801", True),
    ("gpt-4o", "gpt-4o-2024-08-06", True),
    ("claude-sonnet-5-5", "claude-sonnet-5", False),       # the fallback AM-G18 flags
    ("claude-sonnet-5", "claude-sonnet-5-5", False),       # a prefix is not the model
    ("claude-sonnet-5", "claude-sonnet-5-x", False),
])
def test_serves_requested(requested, served, ok):
    assert serves_requested(requested, served) is ok


def test_the_eval_runner_excludes_a_fallback_served_trial_and_never_halts_on_it():
    from tests.eval_common.models_registry import spec
    from tests.grading_eval_suite import synth
    from tests.grading_eval_suite.runner import _assert_draft_stamp, model_fallbacks
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s55 = spec("claude-sonnet-5.5")
    draft = synth.draft_from_gt(bundle, gt).model_copy(update={
        "model_version": s55.model_id, "served_models": ["claude-sonnet-5"]})
    assert model_fallbacks(draft, s55) == ["claude-sonnet-5"]
    _assert_draft_stamp(draft, s55)                          # excluded by the caller, not a halt
    clean = draft.model_copy(update={"served_models": ["claude-sonnet-5-5"]})
    assert model_fallbacks(clean, s55) == []
    with pytest.raises(SystemExit, match="COST_TRUTH"):     # a model outside the registry still halts
        _assert_draft_stamp(draft.model_copy(update={"served_models": ["mystery-model"]}), s55)
