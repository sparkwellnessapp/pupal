"""
Anthropic prompt caching for the grader-v6 calls (AM-G12 CL-2; §6.4, §7.3) — one place.

The v6 verifier and explainer resend identical prefixes on every call: the system prompt
(core rules + pack + examples) for every scope of every test, and the verifier's per-scope
rubric part (question, solution, checks) for every student of an exam. A cache breakpoint
after each makes repeats bill at the cache-read rate. Outputs are unchanged: caching is a
transport property, not a prompt change.

Anthropic only. The factory's other providers take plain strings (the Gemini adapter joins
`m.content` as text), so for them the messages are exactly what they were.
"""
from __future__ import annotations

from typing import Any, Mapping

from langchain_core.messages import HumanMessage, SystemMessage

_EPHEMERAL = {"type": "ephemeral"}


def supports_cache(llm: Any) -> bool:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:                                   # pragma: no cover
        return False
    return isinstance(llm, ChatAnthropic)


def system_message(text: str, cache: bool) -> SystemMessage:
    if not cache:
        return SystemMessage(content=text)
    return SystemMessage(content=[{"type": "text", "text": text, "cache_control": dict(_EPHEMERAL)}])


def human_message(prefix: str, rest: str, cache: bool) -> HumanMessage:
    """`prefix` is the cacheable part; without caching the text is `prefix + "\\n" + rest`."""
    if not cache:
        return HumanMessage(content=prefix + "\n" + rest)
    return HumanMessage(content=[{"type": "text", "text": prefix, "cache_control": dict(_EPHEMERAL)},
                                 {"type": "text", "text": rest}])


def cache_write_tokens(usage_metadata: Mapping[str, Any]) -> int:
    return int((usage_metadata.get("input_token_details") or {}).get("cache_creation") or 0)
