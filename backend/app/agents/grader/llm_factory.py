"""
Multi-provider chat-model factory for the grader path (mission V5-A, the D6 seam).

build_chat_model(provider, model_id, ...) -> a LangChain chat model whose
with_structured_output / ainvoke surface both grader agents consume unchanged.

Parameter policy is NOT re-implemented here: it is docx_v3.pipeline._llm_params
— the one per-family kwargs policy in this codebase (§0.4: one concept, one
place). That gives every seam-constructed call the PR-2 discipline for free:
bounded timeout, SDK hidden-retry layer disabled (max_retries=0), reasoning
family handled (no temperature, reasoning_effort passthrough, completion budget
that reasoning tokens bill against), anthropic max_tokens requirement.

The DEFAULT grader path (GraderAgent constructed with no llm argument) does NOT
go through this factory — it keeps its historical construction byte-for-byte
(no timeout, SDK retries), because comparability with C2/E7 and production
behavior must not shift as a side effect of the seam landing. Bounding the
default path is PR-7's decision, not this mission's side effect.

Providers:
  openai     ChatOpenAI; key from settings.
  anthropic  ChatAnthropic; ANTHROPIC_API_KEY read from the environment by the
             SDK. Structured output rides Anthropic tool-use — same LangChain
             surface, include_raw works, usage_metadata is normalized.
  gemini     REFUSED. Mission §1.7: the only Google path on this machine rides
             Vertex on GOOGLE_CLOUD_PROJECT — the PRODUCTION transcription
             project. Isolation from the launch quota cannot be positively
             established, so every Google entrant is skipped, loudly.
  xai        REFUSED. Excluded by default per the mission roster (owner
             skepticism); a one-line owner flip reintroduces it deliberately.
"""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.services.docx_v3.pipeline import _llm_params, _is_openai_reasoning

# Per-call bound for seam-constructed grader calls. Deliberately BELOW the eval
# runner's 300 s trial wall so the in-call timeout fires first and the runner's
# single re-run (D7) sees a classified transport error instead of a wall hit.
GRADER_LLM_TIMEOUT_S = 240.0

# The grader's historical completion budget for non-reasoning OpenAI models —
# kept so a seam-constructed gpt-4o call generates under the same cap as the
# default path. Reasoning-family models take _llm_params' 32k completion budget
# (reasoning tokens bill against it).
GRADER_MAX_TOKENS_NON_REASONING = 8192


def build_chat_model(provider: str, model_id: str, *,
                     reasoning_effort: Optional[str] = None,
                     max_output_tokens: Optional[int] = None,
                     timeout_s: Optional[float] = None):
    timeout = GRADER_LLM_TIMEOUT_S if timeout_s is None else timeout_s

    if provider == "gemini":
        raise RuntimeError(
            "Google entrants are SKIPPED (mission §1.7): the google-genai path on "
            "this machine rides Vertex on GOOGLE_CLOUD_PROJECT — the production "
            "transcription project — and quota isolation cannot be positively "
            "established. The launch resource is never put at risk for an eval.")
    if provider == "xai":
        raise RuntimeError(
            "xAI is excluded by default (mission §3 roster — owner skepticism). "
            "Reintroducing it is a one-line owner flip, not a factory default.")
    if provider not in ("openai", "anthropic"):
        raise ValueError(f"unknown provider {provider!r}")

    if max_output_tokens is None and provider == "openai" \
            and not _is_openai_reasoning(model_id):
        max_output_tokens = GRADER_MAX_TOKENS_NON_REASONING

    params = _llm_params(provider, model_id, max_output_tokens,
                         reasoning_effort, timeout_s=timeout)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id, **params)

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model_id, api_key=settings.openai_api_key, **params)
