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

from ..vlm_provider import ErrorKind, Usage, VLMCallError, VLMResponse


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
    ) -> VLMResponse:
        blocks: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            }
            for b64 in (images_b64 or [])
        ]
        blocks.append({"type": "text", "text": user})

        kwargs: dict = {}
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
                temperature=temperature,
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
