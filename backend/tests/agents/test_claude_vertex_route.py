"""[Owner ruling 2026-10-17 §5a/§5c] The Claude-on-Vertex provider route.

  * the factory resolves the route by CONFIG (`settings.claude_route`), for every Claude call;
  * the Vertex variant is ChatAnthropic with only its SDK client swapped (`AnthropicVertex`),
    in the configured region and project, with the factory's retry policy and NO Anthropic key;
  * logical ids map through the closed VERTEX_MODEL_IDS table — an unmapped id is refused;
  * the provider guard blocks every Vertex host form a test could reach (global, regional,
    multi-region `aiplatform.<eu|us>.rep.googleapis.com`);
  * provenance carries the provider (`provider_of`, `GradedTestDraft.llm_provider`).
No provider is ever called here (tests/guards.py).
"""
from __future__ import annotations

import pytest

from app.agents.grader import llm_factory as lf
from app.agents.grader.prompt_cache import supports_cache
from tests.guards import is_provider_host


@pytest.fixture
def route(monkeypatch):
    from app.config import settings

    def set_route(value, region="eu", project="proj-x"):
        monkeypatch.setattr(settings, "claude_route", value)
        monkeypatch.setattr(settings, "claude_vertex_region", region)
        monkeypatch.setattr(settings, "claude_vertex_project", project)
    return set_route


def test_direct_route_is_the_historical_chat_anthropic(route):
    route("direct")
    m = lf.build_chat_model("anthropic", "claude-sonnet-5", max_output_tokens=2000, timeout_s=120)
    assert type(m).__name__ == "ChatAnthropic" and m.model == "claude-sonnet-5"
    assert lf.provider_of(m) == "anthropic"
    assert "api.anthropic.com" in str(m._client.base_url)


def test_vertex_route_swaps_only_the_client(route):
    route("vertex", region="eu", project="proj-x")
    m = lf.build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="low", thinking="adaptive")
    assert lf.provider_of(m) == "vertex:eu"
    assert supports_cache(m)                                  # CL-2 still applies: it IS a ChatAnthropic
    assert m.thinking == {"type": "adaptive"} and m.model == "claude-sonnet-5-5"
    for client in (m._client, m._async_client):
        assert type(client).__name__ in ("AnthropicVertex", "AsyncAnthropicVertex")
        assert (client.region, client.project_id, client.max_retries) == ("eu", "proj-x", 0)
        assert str(client.base_url).startswith("https://aiplatform.eu.rep.googleapis.com/")
    assert m.anthropic_api_key.get_secret_value() == ""      # no Anthropic key can leave on Vertex


def test_vertex_native_schema_models_keep_json_schema_structured_output(route):
    route("vertex")
    m = lf.build_chat_model("anthropic", "claude-sonnet-5-5", reasoning_effort="low", thinking="adaptive")
    assert type(m).__name__ == "NativeSchemaChatAnthropic"
    assert isinstance(m, lf._vertex_chat_anthropic())


@pytest.mark.parametrize("logical,vertex", sorted(lf.VERTEX_MODEL_IDS.items()))
def test_every_production_model_has_a_confirmed_vertex_id(route, logical, vertex):
    route("vertex")
    kwargs = {"reasoning_effort": "low", "thinking": "adaptive"} if logical in lf.NATIVE_SCHEMA_MODELS else {}
    m = lf.build_chat_model("anthropic", logical, max_output_tokens=2000, **kwargs)
    assert m.model == vertex


def test_production_claude_models_are_all_mapped():
    from app.agents.plan_compiler.models import MODEL_CARDS
    from app.config import settings
    used = {c.model_id for c in MODEL_CARDS.values() if c.provider == "anthropic"}
    used |= {m for m in (settings.grader_model_key, settings.feedback_model_key) if m}
    assert used <= set(lf.VERTEX_MODEL_IDS), used - set(lf.VERTEX_MODEL_IDS)


def test_an_unmapped_model_is_refused_never_guessed(route):
    route("vertex")
    with pytest.raises(ValueError, match="refused rather than guessed"):
        lf.build_chat_model("anthropic", "claude-opus-4-8", max_output_tokens=100)


def test_an_unknown_route_is_refused(route):
    route("bedrock")
    with pytest.raises(ValueError, match="CLAUDE_ROUTE"):
        lf.build_chat_model("anthropic", "claude-sonnet-5", max_output_tokens=100)


def test_served_model_provenance_accepts_the_vertex_snapshot_form():
    assert lf.serves_requested("claude-haiku-4-5", "claude-haiku-4-5@20251001")
    assert lf.serves_requested("claude-haiku-4-5", "claude-haiku-4-5-20251001")
    assert lf.serves_requested("claude-opus-5-5", "claude-opus-5-5")
    assert not lf.serves_requested("claude-sonnet-5-5", "claude-sonnet-5")      # AM-G18 unchanged


@pytest.mark.parametrize("host", ["aiplatform.googleapis.com", "europe-west1-aiplatform.googleapis.com",
                                  "aiplatform.eu.rep.googleapis.com", "aiplatform.us.rep.googleapis.com",
                                  "api.anthropic.com"])
def test_the_provider_guard_blocks_every_claude_host(host):
    assert is_provider_host(host)


def test_the_guard_blocks_the_host_the_vertex_client_would_call(route):
    route("vertex", region="eu")
    # Opus 5.5 is a native-schema model (2026-10-29): effort and thinking are required (AM-G18)
    m = lf.build_chat_model("anthropic", "claude-opus-5-5", max_output_tokens=100,
                            reasoning_effort="low", thinking="adaptive")
    host = m._client.base_url.host
    assert is_provider_host(host), host


def test_the_route_reaches_draft_provenance():
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.schemas.graded_test_draft_v6 import UsageV6
    assert "llm_provider" in GradedTestDraft.model_fields
    assert UsageV6(model="m", provider="vertex:eu").provider == "vertex:eu"
