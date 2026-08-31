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
  gemini     APPROVED (owner RULING REVERSAL, 2026-08-28 — §1.7's isolation
             condition withdrawn: DSQ headroom dwarfs three months of launch
             volume, so eval traffic on the production project is immaterial).
             Served by _GenAIChat below: the google-genai/Vertex SDK path
             (same auth env as production), native response_schema structured
             output, temperature 0, and — MANDATORY for the COST_TRUTH
             reconciliation — every request carries the eval attribution
             labels, since Vertex has no per-key billing split.
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
                     thinking_budget: Optional[int] = None,
                     timeout_s: Optional[float] = None):
    timeout = GRADER_LLM_TIMEOUT_S if timeout_s is None else timeout_s

    if provider == "gemini":
        return _GenAIChat(model_id, reasoning_effort=reasoning_effort,
                          max_output_tokens=max_output_tokens or 16000,
                          thinking_budget=thinking_budget,
                          timeout_s=timeout)
    if thinking_budget is not None:
        raise ValueError("thinking_budget is a gemini-only knob")
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
        # The key comes from SETTINGS, like the openai branch below. Relying on
        # the SDK's os.environ fallback made this branch depend on a variable
        # that `.env` never exports, and `attach_feedback` swallows the failure
        # into `feedback_unavailable` — so the symptom was silently feedbackless
        # exams, not an error anyone would see (OD-B3, 2026-08-31).
        return ChatAnthropic(model=model_id,
                             api_key=settings.anthropic_api_key.get_secret_value()
                             if settings.anthropic_api_key else None, **params)

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model_id, api_key=settings.openai_api_key.get_secret_value(), **params)


# ---------------------------------------------------------------------------
# Google adapter — google-genai over Vertex (owner ruling reversal 2026-08-28)
# ---------------------------------------------------------------------------

# [COST_TRUTH] Vertex has no per-key split; these request labels are how the
# GCP billing view separates eval spend from production transcription. Without
# them the owner-mandated reconciliation is blind on one of three providers.
EVAL_REQUEST_LABELS = {"vivi-workload": "grading-eval"}

_THINKING_LEVELS = ("minimal", "low", "medium", "high")


class _GenAIChat:
    """Minimal chat-model stand-in exposing exactly the surface both grader
    agents consume: with_structured_output(schema, include_raw=True) ->
    .ainvoke([...]) -> {"raw", "parsed", "parsing_error"}, with raw carrying
    LangChain-shaped usage_metadata and response_metadata.

    Auth rides the same env as production transcription (GOOGLE_GENAI_USE_
    VERTEXAI + GOOGLE_CLOUD_PROJECT/LOCATION) — deliberate, per the reversal.
    Token accounting: thoughts bill as OUTPUT on Gemini, so output_tokens =
    candidates + thoughts (the number the dashboard will show; anything else
    breaks the reconciliation). reasoning_effort maps to ThinkingLevel; unset
    leaves the provider default. 429s are NOT retried in-adapter — the
    runner's D7 re-run owns that; ServerError (5xx) is in the v5 transient
    tuple."""

    def __init__(self, model_id: str, *, reasoning_effort: Optional[str],
                 max_output_tokens: int, timeout_s: float,
                 thinking_budget: Optional[int] = None) -> None:
        from google import genai
        from google.genai import types as genai_types
        if "labels" not in genai_types.GenerateContentConfig.model_fields:
            raise RuntimeError(
                "google-genai SDK lacks GenerateContentConfig.labels — the "
                "COST_TRUTH attribution labels cannot be attached; upgrade the "
                "SDK before running Google entrants (owner-mandated bookkeeping).")
        if reasoning_effort is not None and reasoning_effort not in _THINKING_LEVELS:
            raise ValueError(f"gemini reasoning_effort must be one of "
                             f"{_THINKING_LEVELS}, got {reasoning_effort!r}")
        if reasoning_effort is not None and thinking_budget is not None:
            raise ValueError("set reasoning_effort OR thinking_budget, not both")
        # [FP2, probe-verified 2026-08-29] explicit per-call thinking-token cap
        # — the knob that charts the empty $0.15-0.36 band on gemini-3.1-pro
        self._thinking_budget = thinking_budget
        self._genai = genai
        self._types = genai_types
        self.model = model_id
        self._effort = reasoning_effort
        self._max_tokens = max_output_tokens
        self._client = genai.Client(
            http_options=genai_types.HttpOptions(timeout=int(timeout_s * 1000)))

    def with_structured_output(self, schema, include_raw: bool = False):
        assert include_raw, "grader agents always use include_raw=True"
        return _GenAIStructuredRunner(self, schema)


class _GenAIStructuredRunner:
    def __init__(self, chat: _GenAIChat, schema) -> None:
        self._chat = chat
        self._schema = schema

    async def ainvoke(self, messages):
        from types import SimpleNamespace
        t = self._chat._types
        system = "\n".join(m.content for m in messages
                            if getattr(m, "type", "") == "system")
        user = "\n".join(m.content for m in messages
                          if getattr(m, "type", "") != "system")
        cfg_kwargs = dict(
            temperature=0.0,
            max_output_tokens=self._chat._max_tokens,
            response_mime_type="application/json",
            response_schema=self._schema,
            system_instruction=system or None,
            labels=dict(EVAL_REQUEST_LABELS),        # [COST_TRUTH] every call
        )
        if self._chat._effort is not None:
            cfg_kwargs["thinking_config"] = t.ThinkingConfig(
                thinking_level=t.ThinkingLevel(self._chat._effort.upper()))
        elif self._chat._thinking_budget is not None:
            cfg_kwargs["thinking_config"] = t.ThinkingConfig(
                thinking_budget=self._chat._thinking_budget)
        response = await self._chat._client.aio.models.generate_content(
            model=self._chat.model, contents=user,
            config=t.GenerateContentConfig(**cfg_kwargs))

        parsed = response.parsed
        parsing_error = None
        if parsed is None:
            parsing_error = (f"gemini returned no parseable {self._schema.__name__}: "
                             f"{(response.text or '')[:300]!r}")
        um = response.usage_metadata
        in_tok = (um.prompt_token_count or 0) if um else 0
        out_tok = (((um.candidates_token_count or 0) + (um.thoughts_token_count or 0))
                   if um else 0)
        cached = um.cached_content_token_count if um else None
        raw = SimpleNamespace(
            usage_metadata={
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "input_token_details": ({"cache_read": cached}
                                        if cached is not None else {}),
            },
            response_metadata={"model_name": getattr(response, "model_version", None)
                               or self._chat.model},
        )
        return {"raw": raw, "parsed": parsed, "parsing_error": parsing_error}
