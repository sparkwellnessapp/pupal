"""
Model registry — the ONLY file that rots when providers change prices/models.

Seed set (approved): one cheap + one frontier per provider. The cheap tier is
the v0 default conjecture (the cost gate: $0.05–$0.08/doc average); the
frontier tier exists as the ACCURACY CEILING REFERENCE in sweeps — it may fail
the cost gate and still be informative (the gap to it is what L6 escalation
must recover).

Prices in USD per million tokens, standard interactive tier, verified
AS_OF the date below from provider pricing pages/aggregators. cached_in uses
each provider's cached-input rate (~90% discount where offered).

NOTE: `model_id` strings should be confirmed against each provider console on
first real run — marketing names and API ids drift (e.g. "-preview" suffixes).
The harness fails loudly on an unknown model id, which is the desired behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .instrument import PriceCard

AS_OF = "2026-06-11"


@dataclass(frozen=True)
class ModelSpec:
    key: str                   # registry key used in configs and CallRecords
    provider: str              # scheduler/adapter name: openai | anthropic | gemini
    model_id: str              # the id passed to the SDK
    price: PriceCard
    supports_logprobs: bool
    supports_json_schema: bool
    tier: str                  # "cheap" | "frontier"


MODELS: dict[str, ModelSpec] = {
    # --- OpenAI ---
    "gpt-5.4-nano-2026-03-17": ModelSpec(
        key="gpt-5.4-nano-2026-03-17", provider="openai", model_id="gpt-5.4-nano-2026-03-17",
        price=PriceCard(in_per_mtok=0.20, out_per_mtok=1.25),
        supports_logprobs=True, supports_json_schema=True, tier="cheap",
    ),
    "gpt-5.5": ModelSpec(
        key="gpt-5.5", provider="openai", model_id="gpt-5.5",
        price=PriceCard(in_per_mtok=5.00, out_per_mtok=30.00,
                        cached_in_per_mtok=0.50),
        supports_logprobs=True, supports_json_schema=True, tier="frontier",
    ),
    # --- Anthropic ---
    "claude-haiku-4.5": ModelSpec(
        key="claude-haiku-4.5", provider="anthropic", model_id="claude-haiku-4-5",
        price=PriceCard(in_per_mtok=1.00, out_per_mtok=5.00,
                        cached_in_per_mtok=0.10),
        supports_logprobs=False, supports_json_schema=True, tier="cheap",
    ),
    "claude-opus-4.8": ModelSpec(
        key="claude-opus-4.8", provider="anthropic", model_id="claude-opus-4-8",
        price=PriceCard(in_per_mtok=5.00, out_per_mtok=25.00,
                        cached_in_per_mtok=0.50),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
    # --- Gemini ---
    "gemini-3.1-flash-lite": ModelSpec(
        key="gemini-3.1-flash-lite", provider="gemini",
        model_id="gemini-3.1-flash-lite",
        price=PriceCard(in_per_mtok=0.25, out_per_mtok=1.50,
                        cached_in_per_mtok=0.025),
        supports_logprobs=False, supports_json_schema=True, tier="cheap",
    ),
    "gemini-3.1-pro-preview": ModelSpec(
        key="gemini-3.1-pro-preview", provider="gemini", model_id="gemini-3.1-pro-preview",
        price=PriceCard(in_per_mtok=2.00, out_per_mtok=12.00,
                        cached_in_per_mtok=0.20),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
    "chatgpt-4o-mini": ModelSpec(
        key="chatgpt-4o-mini", provider="openai", model_id="gpt-4o-mini",
        price=PriceCard(in_per_mtok=0.15, out_per_mtok=0.60,
                        cached_in_per_mtok=0.075),
        supports_logprobs=True, supports_json_schema=True, tier="cheap",
    ),
    # Trust-layer reader candidate (2026-07-09): a stronger OpenAI eye than
    # 4o-mini — reader NOISE (false disagreements) is the burden bottleneck,
    # so reader fidelity buys warning-tier precision directly.
    "gpt-4o": ModelSpec(
        key="gpt-4o", provider="openai", model_id="gpt-4o",
        price=PriceCard(in_per_mtok=2.50, out_per_mtok=10.00,
                        cached_in_per_mtok=1.25),
        supports_logprobs=True, supports_json_schema=True, tier="frontier",
    ),
    "claude-sonnet-4-6": ModelSpec(
        key="claude-sonnet-4-6", provider="anthropic", model_id="claude-sonnet-4-6",
        price=PriceCard(in_per_mtok=3.00, out_per_mtok=15.00,
                        cached_in_per_mtok=3.75),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
}


def spec(key: str) -> ModelSpec:
    if key not in MODELS:
        raise KeyError(
            f"Unknown model key {key!r}. Known: {sorted(MODELS)}. "
            f"Registry as of {AS_OF} — update models_registry.py."
        )
    return MODELS[key]
