"""
Gemini adapter (google-genai SDK). Thin translation; no policy.

- No SDK retry option to disable in the same sense; we pass no retry config
  and rely on the scheduler as the single retry site.
- No logprobs wired (approved decision #3) -> token_logprobs is always None.
- json_schema -> response_mime_type="application/json" + response_schema.
- google-genai raises APIError carrying an HTTP code; classification maps
  codes -> ErrorKind.
"""
from __future__ import annotations

import base64
import os
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from ..vlm_provider import ErrorKind, Usage, VLMCallError, VLMResponse


def _to_gemini_schema(node):
    """Translate a neutral JSON Schema (OpenAI-strict dialect) into the subset
    Gemini's ``response_schema`` accepts (a restricted OpenAPI 3.0 dialect):

    - drop ``additionalProperties`` (OpenAI strict requires it; Gemini rejects it),
    - rewrite ``type: [T, "null"]`` unions into ``type: T`` + ``nullable: True``.

    Recurses through ``properties``/``items``. Other providers adapt the same
    neutral schema to their own API; this is Gemini's adapter step.
    """
    if isinstance(node, dict):
        out: dict = {}
        for k, v in node.items():
            if k == "additionalProperties":
                continue
            if k == "type" and isinstance(v, list):
                non_null = [t for t in v if t != "null"]
                out["type"] = non_null[0] if non_null else "string"
                if "null" in v:
                    out["nullable"] = True
                continue
            out[k] = _to_gemini_schema(v)
        return out
    if isinstance(node, list):
        return [_to_gemini_schema(x) for x in node]
    return node


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        thinking_level: str | None = "low",
    ):
        self.model = model
        # Gemini-3 "thinking" tokens are emitted into max_output_tokens BEFORE the
        # visible answer; on reasoning models (e.g. pro) that can exhaust the budget
        # and truncate the JSON (finish_reason=MAX_TOKENS). Constrain it for this
        # perception task. None omits the field entirely (model default).
        self._thinking_level = (
            genai_types.ThinkingLevel(thinking_level.upper())
            if thinking_level
            else None
        )
        self._client = genai.Client(
            api_key=api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY"),
        )

    def _classify(self, exc: Exception) -> VLMCallError:
        if isinstance(exc, genai_errors.APIError):
            code = getattr(exc, "code", None)
            if code == 429:
                kind = ErrorKind.RATE_LIMIT
            elif code in (401, 403):
                kind = ErrorKind.AUTH
            elif code == 400:
                kind = ErrorKind.BAD_REQUEST
            elif code is not None and 500 <= code < 600:
                kind = ErrorKind.TRANSIENT
            else:
                kind = ErrorKind.TRANSIENT
        elif isinstance(exc, TimeoutError):
            kind = ErrorKind.TIMEOUT
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
        want_logprobs: bool = False,  # unsupported here; always returns None
        json_schema: dict | None = None,
        timeout_s: float = 90.0,
    ) -> VLMResponse:
        parts: list = [
            genai_types.Part.from_bytes(
                data=base64.b64decode(b64), mime_type="image/png"
            )
            for b64 in (images_b64 or [])
        ]
        parts.append(genai_types.Part.from_text(text=user))

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            http_options=genai_types.HttpOptions(timeout=int(timeout_s * 1000)),
            **(
                {"thinking_config": genai_types.ThinkingConfig(
                    thinking_level=self._thinking_level)}
                if self._thinking_level is not None
                else {}
            ),
            **(
                {"response_mime_type": "application/json",
                 "response_schema": _to_gemini_schema(json_schema)}
                if json_schema is not None
                else {}
            ),
        )

        t0 = time.monotonic()
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model,
                contents=parts,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            raise self._classify(exc) from exc
        total_ms = (time.monotonic() - t0) * 1000.0

        um = resp.usage_metadata
        cached = getattr(um, "cached_content_token_count", None) if um else None
        finish = None
        if resp.candidates:
            fr = resp.candidates[0].finish_reason
            finish = fr.name if fr is not None else None

        return VLMResponse(
            text=resp.text or "",
            usage=Usage(
                input_tokens=(um.prompt_token_count or 0) if um else 0,
                output_tokens=(um.candidates_token_count or 0) if um else 0,
                cached_input_tokens=cached,
            ),
            total_ms=total_ms,
            model_id=self.model,
            token_logprobs=None,
            raw_finish_reason=finish,
        )
