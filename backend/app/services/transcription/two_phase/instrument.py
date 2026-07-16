"""
Harness instrumentation: stage timing, per-call records, and cost.

Stage vocabulary (phase-aware, keep consistent so traces are comparable):
    pdf_render | image_encode | p1_call | p1_parse | p2_call | p2_parse
    | merge | score

Cost: raw provider-reported Usage is the primitive; PriceCard converts to USD.
The registry of cards (models_registry.py) is the ONLY file that rots when
prices change.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

from ..vlm_provider import Usage


@dataclass(frozen=True)
class Span:
    stage: str
    ms: float


@dataclass(frozen=True)
class CallRecord:
    """One VLM call, fully accounted: phase, identity, usage, timing, outcome."""
    phase: str                 # "p1" | "p2"
    provider: str
    model_key: str             # registry key (not the provider-reported id)
    usage: Usage
    total_ms: float
    queue_wait_ms: float
    attempts: int
    parse_ok: bool             # D2: parse failures are a v0 metric
    cost_usd: float
    finish_reason: str | None = None   # truncation diagnosis: 'length'/'MAX_TOKENS'
                                       # on a parse failure means the output was cut


@dataclass
class Trace:
    """Per-document trace: ordered stage spans + call records."""
    doc_id: str
    spans: list[Span] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)

    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def stage_ms(self, stage: str) -> float:
        return sum(s.ms for s in self.spans if s.stage == stage)

    def parse_failure_rate(self) -> float:
        if not self.calls:
            return 0.0
        return sum(1 for c in self.calls if not c.parse_ok) / len(self.calls)


class StageTimer:
    """Context-manager timer appending Spans to a Trace. Injectable clock."""

    def __init__(self, trace: Trace, *, time_fn: Callable[[], float] = time.monotonic):
        self._trace = trace
        self._time = time_fn

    @contextmanager
    def span(self, stage: str) -> Iterator[None]:
        t0 = self._time()
        try:
            yield
        finally:
            self._trace.spans.append(Span(stage, (self._time() - t0) * 1000.0))


@dataclass(frozen=True)
class PriceCard:
    """USD per million tokens. cached_in falls back to in_per_mtok when None."""
    in_per_mtok: float
    out_per_mtok: float
    cached_in_per_mtok: float | None = None


def cost_usd(usage: Usage, card: PriceCard) -> float:
    cached = usage.cached_input_tokens or 0
    uncached = usage.input_tokens - cached
    cached_rate = (card.cached_in_per_mtok
                   if card.cached_in_per_mtok is not None else card.in_per_mtok)
    return (
        uncached * card.in_per_mtok
        + cached * cached_rate
        + usage.output_tokens * card.out_per_mtok
    ) / 1_000_000.0