"""
Model registry — the ONLY file that rots when providers change prices/models.

SHARED by BOTH eval suites (transcription + rubric): one definition of a
model's identity, price card, capabilities and tier; suite configs name only
the registry key. Production deliberately keeps its own narrow settings-owned
map (app/services/transcription/two_phase/__init__.py's ruling: the registry
stays eval-side).

`tier` is VENDOR POSITIONING, not suite economics: "cheap" = the vendor's
small/economy line, "frontier" = the vendor's flagship line. Each suite's
economics live in its own cost ceiling (transcription: the $0.05–$0.08/doc
gate; rubric: per-config `cost_ceiling`) — never in `tier`.

Prices in USD per million tokens, standard interactive tier, verified
AS_OF the date below from provider pricing pages/aggregators. cached_in uses
each provider's cached-input rate (~90% discount where offered).

Conventions:
- `model_id` strings should be confirmed against each provider console on
  first real run — marketing names and API ids drift (e.g. "-preview"
  suffixes). The harness fails loudly on an unknown model id, which is the
  desired behavior.
- An UNVERIFIED capability or price detail is recorded in the direction that
  cannot cause a bad call (e.g. supports_logprobs=False; cached_in omitted so
  cost falls back to the uncached rate — a conservative upper bound).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.transcription.two_phase.instrument import PriceCard

AS_OF = "2026-08-15"


@dataclass(frozen=True)
class ModelSpec:
    key: str                   # registry key used in configs and CallRecords
    provider: str              # adapter/branch name: openai | anthropic | gemini | xai
    model_id: str              # the id passed to the SDK
    price: PriceCard
    supports_logprobs: bool
    supports_json_schema: bool
    tier: str                  # "cheap" | "frontier"


MODELS: dict[str, ModelSpec] = {
    # Transcription-suite v0 seed set (approved): one cheap + one frontier per
    # of openai/anthropic/gemini. The cheap tier was the v0 default conjecture
    # under the $0.05–$0.08/doc cost gate; the frontier tier is the ACCURACY
    # CEILING REFERENCE in sweeps — it may fail that gate and still be
    # informative (the gap to it is what L6 escalation must recover).
    # --- OpenAI ---
    "gpt-5.4-nano-2026-03-17": ModelSpec(
        key="gpt-5.4-nano-2026-03-17", provider="openai", model_id="gpt-5.4-nano-2026-03-17",
        price=PriceCard(in_per_mtok=0.20, out_per_mtok=1.25),
        supports_logprobs=True, supports_json_schema=True, tier="cheap",
    ),
    # P2 segmentor candidate (owner decision 2026-08-07, following the fired
    # §17.8 escalation trigger): nano's successor cost tier — "roughly
    # corresponds to the nano model tier used in earlier GPT-5 families"
    # (OpenAI model page). Text+image in, text out, reasoning tokens, 128k max
    # output. Prices verified 2026-08-07 from the model page.
    "gpt-5.6-luna": ModelSpec(
        key="gpt-5.6-luna", provider="openai", model_id="gpt-5.6-luna",
        price=PriceCard(in_per_mtok=0.20, out_per_mtok=1.20),
        supports_logprobs=True, supports_json_schema=True, tier="cheap",
    ),
    # --- gpt-5.6 family (rubric-extraction latency sweep, 2026-08-23) ---
    # Ordered luna < terra < sol by vendor positioning. Prices VERIFIED
    # 2026-08-23 from developers.openai.com/api/docs/pricing (standard tier,
    # SHORT-context column; every rubric render is far below the long-context
    # threshold, so the short rates are the ones that bill). All three share a
    # 1.05M context / 128k max-output envelope, so this suite's 32k completion
    # budget is never the binding constraint.
    "gpt-5.6-terra": ModelSpec(
        key="gpt-5.6-terra", provider="openai", model_id="gpt-5.6-terra",
        price=PriceCard(in_per_mtok=2.00, out_per_mtok=12.00,
                        cached_in_per_mtok=0.20),
        supports_logprobs=True, supports_json_schema=True, tier="frontier",
    ),
    # SOL PRICE CARD IS THE **LIST** RATE (5.00/30.00/0.50), NOT the rate we
    # are billed today. The pricing page shows 4.00 in / 20.00 out / 0.40
    # cached as PROMOTIONAL pricing "available at least through November 21,
    # 2026". The registry's standing convention is to record the direction
    # that cannot cause a bad call: an adoption decision outlives the promo,
    # so costing sol at the promo rate could buy a model that gets 25-50%
    # more expensive under us. Costed at list, sol's card is IDENTICAL to
    # gpt-5.5's — which makes the cost comparison a pure token-volume
    # question, and any sol win here is a floor, not a ceiling (at promo
    # rates sol is a further ~20% (in) / ~33% (out) cheaper).
    "gpt-5.6-sol": ModelSpec(
        key="gpt-5.6-sol", provider="openai", model_id="gpt-5.6-sol",
        price=PriceCard(in_per_mtok=5.00, out_per_mtok=30.00,
                        cached_in_per_mtok=0.50),
        supports_logprobs=True, supports_json_schema=True, tier="frontier",
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
    # --- Claude 5 family (grader-v5 mission roster, 2026-08-28) ---
    # Prices VERIFIED 2026-08-28 from platform.claude.com/docs/en/about-claude/
    # pricing. Sonnet 5's $2/$10 launched as introductory-through-Aug-31 and the
    # page now states the scheduled increase to $3/$15 "will not occur" — $2/$10
    # IS the standard rate, so no sol-style list-rate conservatism applies.
    # ⚠ TOKENIZER: Claude 4.7+ models tokenize ~30% MORE tokens for the same
    # text than older Claude models — cross-vendor cost comparisons must use
    # measured usage (which cost_usd does), never token-count intuitions.
    # model_id strings are the documented aliases; the harness fails loudly on
    # an unknown id at first real call (registry convention).
    "claude-sonnet-5": ModelSpec(
        key="claude-sonnet-5", provider="anthropic", model_id="claude-sonnet-5",
        price=PriceCard(in_per_mtok=2.00, out_per_mtok=10.00,
                        cached_in_per_mtok=0.20),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
    "claude-opus-5": ModelSpec(
        key="claude-opus-5", provider="anthropic", model_id="claude-opus-5",
        price=PriceCard(in_per_mtok=5.00, out_per_mtok=25.00,
                        cached_in_per_mtok=0.50),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
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
    # P1 perceiver candidate (2026-08-15): 3.1-flash-lite's successor tier
    # ("most cost-efficient GA model", Google model page). Prices verified
    # 2026-08-15 from the model page: $0.30 in (text/image/video/audio);
    # out is listed as 10.00 ILS (owner-confirmed the ש"ח cells are literal)
    # → $3.30 at ~3.03 ILS/USD (Aug 2026). Out INCLUDES thinking tokens —
    # budget p1_max_tokens accordingly. $0.03 cached-in ($-labeled = USD;
    # +$1.00/Mtok/hr storage, not modeled in PriceCard).
    "gemini-3.5-flash-lite": ModelSpec(
        key="gemini-3.5-flash-lite", provider="gemini",
        model_id="gemini-3.5-flash-lite",
        price=PriceCard(in_per_mtok=0.30, out_per_mtok=3.30,
                        cached_in_per_mtok=0.03),
        supports_logprobs=False, supports_json_schema=True, tier="cheap",
    ),
    # P1 perceiver candidate (2026-08-15): the 3.5 "smartest, fast" tier.
    # Model page lists 6.00/36.00 ILS in/out (owner-confirmed the ש"ח cells
    # are literal) → $1.98/$11.88 at ~3.03 ILS/USD (Aug 2026) — effectively
    # gemini-3.1-pro-preview's price card. Out INCLUDES thinking tokens.
    # $0.15 cached-in ($-labeled = USD; +$1.00/Mtok/hr storage, not modeled).
    # Frontier: pro-class pricing, ceiling-reference role.
    "gemini-3.5-flash": ModelSpec(
        key="gemini-3.5-flash", provider="gemini",
        model_id="gemini-3.5-flash",
        price=PriceCard(in_per_mtok=1.98, out_per_mtok=11.88,
                        cached_in_per_mtok=0.15),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
    # RE-VERIFIED 2026-08-28 for the grading roster (owner Google reversal):
    # $2 in / $12 out confirmed (short-context tier; grading renders never
    # approach the 200K threshold where in doubles). Thinking tokens BILL AS
    # OUTPUT — the grader adapter counts candidates+thoughts as output_tokens
    # so the ledger matches the dashboard. model_id string is production-proven
    # on this Vertex project (two_phase_engine P1 baseline).
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
    # cached_in CORRECTED 3.75 -> 0.30 (2026-08-28, caught by the COST_TRUTH
    # registry unit test on its first run): 3.75 is the 5-minute cache WRITE
    # rate (1.25x in), not the cache-READ rate. platform.claude.com pricing
    # table: Sonnet 4.6 = $3 in / $3.75 5m-write / $0.30 cache hits / $15 out.
    # The old value overcharged cached input 12.5x in every cost figure.
    "claude-sonnet-4-6": ModelSpec(
        key="claude-sonnet-4-6", provider="anthropic", model_id="claude-sonnet-4-6",
        price=PriceCard(in_per_mtok=3.00, out_per_mtok=15.00,
                        cached_in_per_mtok=0.30),
        supports_logprobs=False, supports_json_schema=True, tier="frontier",
    ),
    # --- xAI ---
    # Rubric-suite sweep model (2026-08-15; registry entry 2026-08-23, sourced
    # from configs/grok-4.6.json's own pricing note — xAI pricing page
    # 2026-08-15, <=200K-context tier; renders stay far below 200K).
    # cached_in deliberately OMITTED: xAI lists $0.50, but whether LangChain
    # populates input_token_details.cache_read on the streamed x.ai path is
    # unverified — omission bills cached input at the uncached rate, a
    # conservative upper bound (the unverified-capability convention above).
    # supports_json_schema verified live: 10/10 valid structured records
    # (rubric run 20260815-185359). supports_logprobs unverified -> False.
    "grok-4.6": ModelSpec(
        key="grok-4.6", provider="xai", model_id="grok-4.6",
        price=PriceCard(in_per_mtok=2.00, out_per_mtok=6.00),
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
