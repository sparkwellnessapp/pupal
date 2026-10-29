"""
Anthropic adapter. Thin translation; no policy.

- SDK retries disabled: retry lives in the scheduler only.
- No logprobs (API doesn't expose them) -> token_logprobs is always None.
- json_schema is honored via FORCED TOOL USE (the API's structured-output
  mechanism): a single tool whose input_schema is the requested schema, with
  tool_choice pinned to it. The tool input is returned as the response text
  (JSON), so callers parse uniformly across providers.
"""
from __future__ import annotations

import json
import os
import time

import anthropic

from ..vlm_provider import ErrorKind, Usage, VLMCallError, VLMResponse, image_mime_for


#: Model-id prefixes of the CURRENT Claude family: no sampling parameters, no
#: forced tool choice (Opus 5.5), structured output via `output_config.format`,
#: depth via `output_config.effort`. Their output_tokens INCLUDE thinking tokens
#: (billed as output), so the cost ledger needs no correction here.
_CURRENT_FAMILY_PREFIXES = ("claude-opus-5", "claude-sonnet-5", "claude-fable",
                            "claude-mythos", "claude-opus-4-7", "claude-opus-4-8")


def _current_family(model: str) -> bool:
    return model.startswith(_CURRENT_FAMILY_PREFIXES)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, *, api_key: str | None = None):
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            max_retries=0,
        )

    def _classify(self, exc: Exception) -> VLMCallError:
        if isinstance(exc, anthropic.RateLimitError):
            kind = ErrorKind.RATE_LIMIT
        elif isinstance(exc, anthropic.APITimeoutError):
            kind = ErrorKind.TIMEOUT
        elif isinstance(exc, (anthropic.APIConnectionError, anthropic.InternalServerError)):
            kind = ErrorKind.TRANSIENT
        elif isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
            kind = ErrorKind.AUTH
        elif isinstance(exc, anthropic.BadRequestError):
            kind = ErrorKind.BAD_REQUEST
        else:
            kind = ErrorKind.TRANSIENT
        return VLMCallError(kind, str(exc), provider=self.name)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        images_b64: list[str] | None = None,
        max_tokens: int,
        temperature: float = 0.0,
        want_logprobs: bool = False,  # unsupported; always returns None
        json_schema: dict | None = None,
        timeout_s: float = 90.0,
        reasoning_effort: str | None = None,  # OpenAI-only knob; accepted, ignored
    ) -> VLMResponse:
        blocks: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": image_mime_for(b64), "data": b64},
            }
            for b64 in (images_b64 or [])
        ]
        blocks.append({"type": "text", "text": user})

        kwargs: dict = {}
        if _current_family(self.model):
            # The current Claude family (Opus 5.x, Sonnet 5, Fable, Opus 4.7/4.8)
            # 400s on ANY sampling parameter, and Opus 5.5 also 400s on a forced
            # `tool_choice` — so the historical shape (temperature + forced
            # `emit` tool) cannot reach them at all. Structured output rides
            # `output_config.format`, which guarantees the first text block is
            # schema-valid JSON; depth is `output_config.effort` (Opus 5.5
            # defaults to `medium`, so an eval that omits it is not testing
            # "the default of the family" — it is testing medium).
            output_config: dict = {}
            if json_schema is not None:
                output_config["format"] = {"type": "json_schema", "schema": json_schema}
            if reasoning_effort:
                output_config["effort"] = reasoning_effort
            if output_config:
                kwargs["output_config"] = output_config
        else:
            # Older models (haiku-4.5, sonnet-4.6 — the retired trust readers):
            # the proven shape, byte-identical.
            kwargs["temperature"] = temperature
            if json_schema is not None:
                kwargs["tools"] = [{
                    "name": "emit",
                    "description": "Emit the structured result.",
                    "input_schema": json_schema,
                }]
                kwargs["tool_choice"] = {"type": "tool", "name": "emit"}

        t0 = time.monotonic()
        try:
            resp = await self._client.messages.create(
                model=self.model,
                system=system,
                messages=[{"role": "user", "content": blocks}],
                max_tokens=max_tokens,
                timeout=timeout_s,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise self._classify(exc) from exc
        total_ms = (time.monotonic() - t0) * 1000.0

        text = ""
        for block in resp.content:
            if block.type == "tool_use" and json_schema is not None:
                text = json.dumps(block.input, ensure_ascii=False)
                break
            if block.type == "text":
                text += block.text

        return VLMResponse(
            text=text,
            usage=Usage(
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                cached_input_tokens=getattr(
                    resp.usage, "cache_read_input_tokens", None
                ),
            ),
            total_ms=total_ms,
            model_id=resp.model,
            token_logprobs=None,
            raw_finish_reason=resp.stop_reason,
        )
