"""
OpenAI adapter. Thin translation; no policy.

- SDK retries disabled (max_retries=0): retry lives in the scheduler only.
- The only adapter wired for logprobs (approved decision #3).
- json_schema -> response_format json_schema (strict).
- Errors classified at this boundary into VLMCallError; no SDK exception
  type escapes this module.
"""
from __future__ import annotations

import os
import time

import openai

from ..vlm_provider import ErrorKind, Usage, VLMCallError, VLMResponse


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, *, api_key: str | None = None):
        self.model = model
        self._client = openai.AsyncOpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            max_retries=0,
        )

    def _classify(self, exc: Exception) -> VLMCallError:
        if isinstance(exc, openai.RateLimitError):
            kind = ErrorKind.RATE_LIMIT
        elif isinstance(exc, openai.APITimeoutError):
            kind = ErrorKind.TIMEOUT
        elif isinstance(exc, (openai.APIConnectionError, openai.InternalServerError)):
            kind = ErrorKind.TRANSIENT
        elif isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
            kind = ErrorKind.AUTH
        elif isinstance(exc, openai.BadRequestError):
            kind = ErrorKind.BAD_REQUEST
        else:
            kind = ErrorKind.TRANSIENT  # unknown -> retryable once, not fatal
        return VLMCallError(kind, str(exc), provider=self.name)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        images_b64: list[str] | None = None,
        max_tokens: int,
        temperature: float = 0.0,
        want_logprobs: bool = False,
        json_schema: dict | None = None,
        timeout_s: float = 90.0,
    ) -> VLMResponse:
        content: list[dict] | str
        if images_b64:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}",
                                  "detail": "high"},
                }
                for b64 in images_b64
            ] + [{"type": "text", "text": user}]
        else:
            content = user

        kwargs: dict = {}
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "out", "schema": json_schema, "strict": True},
            }
        if want_logprobs:
            kwargs["logprobs"] = True

        t0 = time.monotonic()
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                max_completion_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout_s,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001 — classified, never re-raised raw
            raise self._classify(exc) from exc
        total_ms = (time.monotonic() - t0) * 1000.0

        choice = resp.choices[0]
        logprobs = None
        if want_logprobs and choice.logprobs and choice.logprobs.content:
            logprobs = tuple(t.logprob for t in choice.logprobs.content)

        u = resp.usage
        cached = None
        if u and u.prompt_tokens_details:
            cached = u.prompt_tokens_details.cached_tokens

        return VLMResponse(
            text=choice.message.content or "",
            usage=Usage(
                input_tokens=u.prompt_tokens if u else 0,
                output_tokens=u.completion_tokens if u else 0,
                cached_input_tokens=cached,
            ),
            total_ms=total_ms,
            model_id=resp.model,
            token_logprobs=logprobs,
            raw_finish_reason=choice.finish_reason,
        )
