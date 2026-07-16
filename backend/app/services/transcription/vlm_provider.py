"""
The single VLM provider interface — shared by production and the eval harness.

One async method serves BOTH pipeline phases:
    Phase 1 (perception):     images_b64 set   -> verbatim per-page transcription
    Phase 2 (interpretation): images_b64 None  -> text-only segmentation call

Design commitments (locked in the instrument/provider design review):
- Provider-REPORTED usage is the source of truth for tokens (and therefore
  cost). We never model image tokenization ourselves — each vendor counts
  differently and all report actual counts; a parallel model would drift.
- No streaming in v0; time-to-first-DRAFT is a scheduler-level metric.
- SDK-internal retries are disabled in every adapter (max_retries=0).
  Retry policy lives in exactly one place: the scheduler.
- Errors are classified AT THE ADAPTER BOUNDARY into VLMCallError.kind.
  Nothing outside an adapter ever touches an SDK exception class.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class ErrorKind(str, Enum):
    RATE_LIMIT = "rate_limit"          # 429 / quota — retryable + informs limiter
    TRANSIENT = "transient"            # 5xx / connection drop — retryable
    TIMEOUT = "timeout"                # client-side deadline — retryable
    CONTENT_FILTER = "content_filter"  # provider refused content — NOT retryable
    BAD_REQUEST = "bad_request"        # our bug (schema, args) — NOT retryable
    AUTH = "auth"                      # key/permission — NOT retryable

RETRYABLE_KINDS = frozenset({ErrorKind.RATE_LIMIT, ErrorKind.TRANSIENT, ErrorKind.TIMEOUT})


class VLMCallError(Exception):
    """The only exception type that crosses the provider boundary."""

    def __init__(self, kind: ErrorKind, message: str, *, provider: str):
        super().__init__(f"[{provider}/{kind.value}] {message}")
        self.kind = kind
        self.provider = provider

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS


@dataclass(frozen=True)
class Usage:
    """Provider-reported token usage. The cost primitive."""
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None  # None when the API doesn't break it out


@dataclass(frozen=True)
class VLMResponse:
    text: str
    usage: Usage
    total_ms: float
    model_id: str                          # provider-reported, for version stamping
    token_logprobs: tuple[float, ...] | None = None  # None: unsupported/not requested
    raw_finish_reason: str | None = None   # truncation diagnosis ("length" vs "stop")


@runtime_checkable
class VLMProvider(Protocol):
    """One method, both phases. Adapters are thin translations to vendor SDKs."""

    name: str

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
    ) -> VLMResponse: ...
