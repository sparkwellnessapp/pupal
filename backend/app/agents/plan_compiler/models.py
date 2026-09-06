"""
The two models the plan compiler spends on, with their price cards — the
production-side copy of the eval registry's entries (the Dockerfile ships
`app/` only, so `tests/eval_common/models_registry.py` does not exist in the
image). `tests/agents/test_plan_compiler_stage2.py` pins these cards EQUAL to
the registry's, so the two cannot drift.

Prices: USD per million tokens, verified 2026-08-28 (platform.claude.com).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from app.services.transcription.two_phase.instrument import PriceCard, cost_usd
from app.services.transcription.vlm_provider import Usage


@dataclass(frozen=True)
class ModelCard:
    key: str            # registry key
    model_id: str       # the id passed to the SDK
    provider: str
    price: PriceCard


SEGMENTER_MODEL_KEY = "claude-haiku-4.5"
ROUTER_MODEL_KEY = "claude-sonnet-5"

MODEL_CARDS: Dict[str, ModelCard] = {
    SEGMENTER_MODEL_KEY: ModelCard(
        key=SEGMENTER_MODEL_KEY, model_id="claude-haiku-4-5", provider="anthropic",
        price=PriceCard(in_per_mtok=1.00, out_per_mtok=5.00, cached_in_per_mtok=0.10)),
    ROUTER_MODEL_KEY: ModelCard(
        key=ROUTER_MODEL_KEY, model_id="claude-sonnet-5", provider="anthropic",
        price=PriceCard(in_per_mtok=2.00, out_per_mtok=10.00, cached_in_per_mtok=0.20)),
}

CostFn = Callable[[int, int, Optional[int]], float]


def cost_fn(model_key: str) -> CostFn:
    card = MODEL_CARDS[model_key].price

    def fn(in_tok: int, out_tok: int, cached: Optional[int]) -> float:
        return cost_usd(Usage(input_tokens=in_tok, output_tokens=out_tok,
                              cached_input_tokens=cached), card)
    return fn
