"""
The factory must take its credentials from `settings`, not from the ambient
environment — for every provider, not just OpenAI.

Found while pinning the feedback model to Sonnet 5 (OD-B3): the anthropic
branch built `ChatAnthropic` with no `api_key`, so the SDK fell back to
`os.environ["ANTHROPIC_API_KEY"]`. The key lives in `.env` and is loaded into
`settings`, NOT into the process environment, so the client raised
"Could not resolve authentication method" on every call.

Why this matters beyond a broken script: `attach_feedback` catches everything
and degrades to `feedback_unavailable`. A missing env var in production would
therefore produce silently feedback-less exams for every student, with nothing
but a WARNING in the logs to say why — a config error wearing the costume of a
product state.
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("provider,model", [
    ("anthropic", "claude-sonnet-5"),
    ("openai", "gpt-4o"),
])
def test_factory_takes_the_api_key_from_settings_not_the_environment(
        provider, model, monkeypatch):
    from app.agents.grader.llm_factory import build_chat_model

    # the ambient environment is empty — settings must be sufficient on its own
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = build_chat_model(provider, model)

    key = None
    for attr in ("anthropic_api_key", "openai_api_key", "api_key"):
        value = getattr(client, attr, None)
        if value is not None:
            key = value.get_secret_value() if hasattr(value, "get_secret_value") else value
            break

    assert key, f"{provider}: the client carries no API key from settings"
