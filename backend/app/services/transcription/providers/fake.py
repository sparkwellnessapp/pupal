"""
FakeProvider — deterministic, zero-network provider for tests and dry runs.

Scripted per-call behavior: each call pops the next item from `script`.
An item is either a VLMResponse-shaping dict or a VLMCallError to raise.
When the script is exhausted, the last item repeats (steady-state behavior).

`gate` (optional asyncio.Event) lets scheduler tests hold calls in-flight to
assert concurrency limits deterministically — no sleeps, no flaky timing.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..vlm_provider import Usage, VLMCallError, VLMResponse


@dataclass
class FakeCall:
    """A record of one received call, for assertions."""
    system: str
    user: str
    n_images: int
    max_tokens: int
    temperature: float
    want_logprobs: bool
    json_schema: dict | None


@dataclass
class FakeProvider:
    name: str = "fake"
    script: list[VLMResponse | VLMCallError] = field(default_factory=list)
    gate: asyncio.Event | None = None
    calls: list[FakeCall] = field(default_factory=list)
    _i: int = 0

    @staticmethod
    def ok(text: str = "ok", *, in_tok: int = 100, out_tok: int = 50,
           model_id: str = "fake-1", total_ms: float = 5.0) -> VLMResponse:
        return VLMResponse(
            text=text,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok),
            total_ms=total_ms,
            model_id=model_id,
        )

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
        self.calls.append(FakeCall(
            system=system, user=user, n_images=len(images_b64 or []),
            max_tokens=max_tokens, temperature=temperature,
            want_logprobs=want_logprobs, json_schema=json_schema,
        ))
        if self.gate is not None:
            await self.gate.wait()
        if not self.script:
            return self.ok()
        item = self.script[min(self._i, len(self.script) - 1)]
        self._i += 1
        if isinstance(item, VLMCallError):
            raise item
        return item
