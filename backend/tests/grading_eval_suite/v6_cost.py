"""The ONE cost function for grader-v6 components (AM-G12 accounting): verifier and
explainer usage priced on their OWN registry cards, cache reads at the cached rate and
cache WRITES at 1.25× input (Anthropic's 5-minute cache) — `cost_usd` alone prices a
write as an ordinary input token, which would flatter a cached run."""
from __future__ import annotations

from typing import Optional

from app.services.transcription.two_phase.instrument import cost_usd
from app.services.transcription.vlm_provider import Usage
from tests.eval_common.models_registry import MODELS

CACHE_WRITE_PREMIUM = 0.25


def card_for(model_id: str):
    for m in MODELS.values():
        if m.model_id == model_id:
            return m.price
    raise SystemExit(f"no registry card for {model_id!r}")


def usage_cost(u: Optional[dict]) -> float:
    if not u or not u.get("calls"):
        return 0.0
    card = card_for(u["model"])
    base = cost_usd(Usage(input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                          cached_input_tokens=u.get("cached_input_tokens") or None), card)
    return base + CACHE_WRITE_PREMIUM * (u.get("cache_write_input_tokens") or 0) * card.in_per_mtok / 1e6
