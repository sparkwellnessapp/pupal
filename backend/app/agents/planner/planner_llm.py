"""The LIVE planner call (PR_grader_v6_options.md §5.5) — built here, injected into
`planner.plan_scope`, and never constructed in a test.

  * model: Sonnet 5 (`claude-sonnet-5`), from the plan compiler's price-card
    registry (`plan_compiler.models`, pinned equal to the eval registry);
  * thinking: ADAPTIVE, depth `effort="high"` [Q-14] — Sonnet 5 rejects
    `budget_tokens` (HTTP 400); `effort` rides `output_config.effort`
    (langchain-anthropic 1.4.0's native field), `thinking={"type": "adaptive"}`;
  * structured output: the provider's NATIVE json_schema mode
    (`output_config.format`), never forced tool_choice — forced tool use is
    incompatible with thinking, and the comparison model (Opus 5.5) rejects it;
  * transport: the SDK's hidden retries off (`max_retries=0`, the factory's
    policy) and exactly ONE app-level retry on transient transport errors only,
    through the shared layer `docx_v3.pipeline._transport_retry_async` — quota
    and 4xx are terminal, content/parse errors are re-raised (CLAUDE.md §7:
    never stack a second retry layer).

Everything is verified against docs.claude.com / platform.claude.com, never
from memory (§5.5).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.agents.grader.llm_factory import build_chat_model
from app.agents.plan_compiler.models import MODEL_CARDS, ROUTER_MODEL_KEY, cost_fn
from app.services.docx_v3.pipeline import _Deadline, _transport_retry_async

from .planner import LLMCall
from .schemas import ScopePlanOutput

PLANNER_MODEL_KEY = ROUTER_MODEL_KEY            # "claude-sonnet-5"
PLANNER_EFFORT = "high"                         # [Q-14], pre-registered in PREDICTIONS.md
PLANNER_THINKING: Dict[str, Any] = {"type": "adaptive"}
PLANNER_MAX_OUTPUT_TOKENS = 32000
PLANNER_TIMEOUT_S = 300.0
PLANNER_TRANSPORT_ATTEMPTS = 2                  # one app-level retry, transient only


class PlannerParseError(RuntimeError):
    """The provider answered but the structured output did not parse."""


def build_planner_call(*, model_key: str = PLANNER_MODEL_KEY, effort: str = PLANNER_EFFORT,
                       timeout_s: float = PLANNER_TIMEOUT_S,
                       deadline_s: Optional[float] = None) -> LLMCall:
    card = MODEL_CARDS[model_key]
    llm = build_chat_model(card.provider, card.model_id, reasoning_effort=effort,
                           max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS, timeout_s=timeout_s)
    llm = llm.model_copy(update={"thinking": dict(PLANNER_THINKING)})
    runner = llm.with_structured_output(ScopePlanOutput, method="json_schema", include_raw=True)
    cost = cost_fn(model_key)

    async def call(system: str, user: str) -> Tuple[ScopePlanOutput, Dict[str, Any]]:
        res = await _transport_retry_async(
            lambda: runner.ainvoke([("system", system), ("human", user)]),
            attempts=PLANNER_TRANSPORT_ATTEMPTS, timeout_s=timeout_s,
            deadline=_Deadline(deadline_s), label=f"planner ({card.model_id})")
        raw = res.get("raw")
        meta = dict(getattr(raw, "usage_metadata", None) or {})
        in_tok = int(meta.get("input_tokens") or 0)
        out_tok = int(meta.get("output_tokens") or 0)
        cached = int((meta.get("input_token_details") or {}).get("cache_read") or 0)
        usage = {"model": card.model_id, "input_tokens": in_tok, "output_tokens": out_tok,
                 "cached_input_tokens": cached, "cost_usd": round(cost(in_tok, out_tok, cached), 6)}
        if res.get("parsed") is None:
            raise PlannerParseError(f"{card.model_id}: {res.get('parsing_error')!r}"[:400])
        return res["parsed"], usage

    return call
