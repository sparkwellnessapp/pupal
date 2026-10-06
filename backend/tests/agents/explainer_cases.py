"""Shared builders for the explainer tests: a `DraftV6Content` from the pricer's case
vocabulary (`tests/services/pricing_v6_cases.py` — one vocabulary, never forked), and a
fake chat model that never touches a provider."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from langchain_core.messages import AIMessage

from app.agents.explainer.payload import ScopeMaterials
from app.agents.explainer.prompt import ExplanationLine, ScopeExplanations
from app.agents.grader.plan_schemas import PackRef, PlanCheckV6, TerminalPlanV6
from app.schemas.graded_test_draft_v6 import CheckRecordV6, DraftV6Content, ScopeRecordV6
from app.services.pricing_v6 import PricingOverlay, PricedTest, ViewTerminal, price
from tests.services.pricing_v6_cases import GRID, Sel, view

D = Decimal
MODEL_ID = "claude-sonnet-5-5"


@dataclass(frozen=True)
class XSel:
    """A pricer `Sel` plus the verifier's evidence for it."""
    check: PlanCheckV6
    option_id: Optional[str]
    quote: Optional[str] = "exact"
    evidence: str = ""
    pointer: str = ""


def make_content(terminals: Sequence[ViewTerminal], sels: Sequence[XSel], *,
                 graded_by: Optional[Mapping[Tuple[str, Optional[str]], str]] = None,
                 notes: Optional[Mapping[str, List[str]]] = None,
                 groups: Sequence[Tuple[Sequence[str], int]] = (),
                 grid: Decimal = GRID) -> DraftV6Content:
    v = view(terminals, [Sel(s.check, s.option_id, s.quote) for s in sels], grid=grid,
             groups=groups)
    checks = [CheckRecordV6(plan=vc.plan, plan_index=vc.plan_index,
                            model_option_id=vc.model_option_id, quote_status=vc.quote_status,
                            evidence_quote=s.evidence, absence_pointer_he=s.pointer)
              for vc, s in zip(v.checks, sels)]
    keys: List[Tuple[str, Optional[str]]] = []
    for t in terminals:
        k = (t.question_id, t.sub_question_id)
        if k not in keys:
            keys.append(k)
    graded_by = graded_by or {}
    return DraftV6Content(
        plan_hash="plan-sha", config_hash="config-sha",
        pack=PackRef(pack_id="computer_science", pack_version="v1"),
        verifier_prompt_version="grader-v6.0", precision=v.precision,
        terminals=[TerminalPlanV6(terminal_id=t.terminal_id, points_possible=t.points_possible,
                                  interpretation_notes_he=list((notes or {}).get(t.terminal_id, [])))
                   for t in terminals],
        view_terminals=list(v.terminals), selection=v.selection, checks=checks,
        scopes=[ScopeRecordV6(question_id=q, sub_question_id=s,
                              graded_by=graded_by.get((q, s), "llm")) for q, s in keys])


def priced_of(content: DraftV6Content, overlay: Optional[PricingOverlay] = None) -> PricedTest:
    return price(content.to_view(), overlay)


def materials(texts: Mapping[Tuple[str, Optional[str]], Mapping[str, str]], *,
              question: str = "שאלה", solution: str = "") -> Dict:
    """One ScopeMaterials per scope; the question text names no id (an id in it would
    defeat the alias tests), so scopes are told apart by an ordinal word."""
    ordinals = ("ראשונה", "שנייה", "שלישית", "רביעית", "חמישית", "שישית")
    return {k: ScopeMaterials(question_text=f"{question} {ordinals[n % len(ordinals)]}",
                              example_solution=solution, teacher_texts=dict(v))
            for n, (k, v) in enumerate(texts.items())}


# ── the fake chat model ─────────────────────────────────────────────────────

_ALIASES = re.compile(r"Write one line for each of: (.*)\.$", re.M)


def aliases_of(message: str) -> List[str]:
    return [a.strip() for a in _ALIASES.search(message).group(1).split(",")]


def raw(model: str = MODEL_ID, in_tok: int = 100, out_tok: int = 20, cached: int = 60) -> AIMessage:
    return AIMessage(content="", response_metadata={"model": model},
                     usage_metadata={"input_tokens": in_tok, "output_tokens": out_tok,
                                     "total_tokens": in_tok + out_tok,
                                     "input_token_details": {"cache_read": cached}})


def ok(lines: Sequence[Tuple[str, str]], **raw_kw) -> dict:
    return {"raw": raw(**raw_kw), "parsed": ScopeExplanations(
        lines=[ExplanationLine(terminal_id=a, text_he=t) for a, t in lines]),
        "parsing_error": None}


Responder = Callable[[str, int], object]          # (user message, call number) -> result | raise


class FakeLLM:
    """`with_structured_output(schema, include_raw=True).ainvoke(messages)`, scripted.
    `respond(user_message, n)` returns a result dict, an awaitable of one, or raises."""

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls: List[str] = []
        self.systems: List[str] = []

    def with_structured_output(self, schema, include_raw: bool = False):
        assert schema is ScopeExplanations and include_raw is True
        return self

    async def ainvoke(self, messages):
        system, user = messages[0].content, messages[1].content
        self.systems.append(system)
        self.calls.append(user)
        out = self.respond(user, len(self.calls))
        if asyncio.iscoroutine(out):
            out = await out
        return out


def echo(text_for: Callable[[str, str], str], **raw_kw) -> FakeLLM:
    """A model that answers every listed alias with `text_for(alias, message)`."""
    return FakeLLM(lambda msg, n: ok([(a, text_for(a, msg)) for a in aliases_of(msg)], **raw_kw))
