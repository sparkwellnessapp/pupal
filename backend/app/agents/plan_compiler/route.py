"""
PLAN COMPILER v2 — Stage 2b: the MONOLITH DECOMPOSER / router (PR §5).

For C7-routed terminals only: one call with the criterion text and the scope's
example solution. Output: 2..5 component NAMES, each with a verbatim evidence
span from the solution or the criterion. No points — the compiler even-splits
P over N (C5, on the ½-lattice per OD-22) and Stage 2 phrases them.

A component whose evidence span does not ground in the scope corpus is an
error; the call retries ONCE with the errors verbatim, then the terminal KEEPS
its single check and is flagged `router_failed` — routing can only refine a
plan, never block it. Cost is accounted per call; the envelope (A2 ≤ $1) aborts
the run before it can be exceeded.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.grader.plan_validator import _tight, quote_is_grounded

from .compile import _canon, even_split
from .segment import EnvelopeExceeded, _usage
from .skeleton import Flag, PlanSkeleton, Slot, TerminalSkeleton

ROUTER_PROMPT_VERSION = "router/v1"
ROUTER_MODEL_KEY = "claude-sonnet-5"
MAX_COMPONENTS = 5


class RoutedComponent(BaseModel):
    evidence_span: str       # decoded first: verbatim, from the solution or the criterion
    name_he: str             # a short name for the component


class RouterResponse(BaseModel):
    components: List[RoutedComponent]


assert not any(f in RoutedComponent.model_fields for f in ("points", "kind", "tariff_amount")), \
    "the router's output type must not be able to carry a number or a kind"


ROUTER_SYSTEM_PROMPT = """\
A teacher wrote ONE grading criterion as a single undifferentiated requirement, and her
example solution shows what a full answer contains. Name the 2 to 5 COMPONENTS a grader
would check separately — the parts a partially-correct answer could have or lack
independently. You are NOT grading and you assign NO points: the points are split later.

For each component, quote first: `evidence_span` is a VERBATIM span of the solution or the
criterion text that evidences the component (copy exactly; never paraphrase; never quote
text you were not shown). Then `name_he`, a short name in the teacher's language.

Keep the components at the grain of the teacher's own text and her solution — the way she
would tick parts off. Do not invent sub-steps she would not separate, and do not return one
component: if the criterion truly has no separable parts, return the two most natural halves.

OUTPUT: {"components": [{"evidence_span": "...", "name_he": "..."}, ...]} in the order the
parts appear in a full answer.
"""


def build_router_message(t: TerminalSkeleton, question_text: str, solution: str) -> str:
    lines = [f"TERMINAL: {t.terminal_id}", "",
             "=== THE CRITERION (one undifferentiated requirement) ===", t.text.strip()]
    if question_text:
        lines += ["", "=== THE QUESTION ===", question_text.strip()]
    lines += ["", "=== THE TEACHER'S EXAMPLE SOLUTION ===", solution.strip(), "",
              f"Return 2 to {MAX_COMPONENTS} components, evidence first."]
    return "\n".join(lines)


def validate_components(comps: Sequence[RoutedComponent], *, corpus: str) -> List[str]:
    errs: List[str] = []
    if not 2 <= len(comps) <= MAX_COMPONENTS:
        errs.append(f"return between 2 and {MAX_COMPONENTS} components; got {len(comps)}")
    tight = _tight(corpus)
    lines = frozenset(_tight(l) for l in corpus.split("\n") if l.strip())
    for i, c in enumerate(comps, 1):
        if not c.name_he.strip():
            errs.append(f"component {i}: name_he is empty")
        if not quote_is_grounded(c.evidence_span, tight, lines):
            errs.append(f"component {i}: evidence_span is not a verbatim span of the text you were shown")
    return errs


def apply_routing(t: TerminalSkeleton, comps: Sequence[RoutedComponent], grid) -> TerminalSkeleton:
    """Replace the single earn slot with N even-split slots (OD-9 on the ½-lattice,
    OD-22). Tariffs and notes are untouched. N is capped at what P can carry."""
    earn = [s for s in t.slots if s.kind == "required"]
    assert len(earn) == 1, "apply_routing expects a monolith"
    n = len(comps)
    split = even_split(t.points_possible, n, grid)
    while split is None and n > 1:
        n -= 1
        split = even_split(t.points_possible, n, grid)
    vals, resid = split if split else ([t.points_possible], False)
    new_slots: List[Slot] = []
    for i, (c, v) in enumerate(zip(comps[:n], vals)):
        new_slots.append(Slot(f"{t.terminal_id}.k{i + 1}", "required", points=_canon(v),
                              source_span=c.evidence_span.strip(), summary=c.name_he.strip(),
                              flags=("routed_component",)))
    new_slots += [s for s in t.slots if s.kind != "required"]
    flags = list(t.flags) + [Flag("routed_split", t.terminal_id,
                                  f"{len(comps)} components → {[str(v) for v in vals]}"
                                  + (f" (capped to {n})" if n < len(comps) else "")
                                  + (" residual" if resid else ""))]
    return replace(t, slots=tuple(new_slots), routed=False, case="routed", flags=tuple(flags))


@dataclass
class RouteCall:
    terminal_id: str
    attempt: int
    input_tokens: int
    output_tokens: int
    cached_tokens: Optional[int]
    cost_usd: float
    latency_s: float
    errors: Tuple[str, ...] = ()
    components: Tuple[str, ...] = ()


@dataclass
class RouteRun:
    skeleton: PlanSkeleton
    calls: List[RouteCall] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    flags: List[Flag] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)


CostFn = Callable[[int, int, Optional[int]], float]


async def route_monoliths(skeleton: PlanSkeleton, llm, *, corpora: Dict[str, str],
                          solutions: Dict[str, str], questions: Dict[str, str],
                          cost_fn: CostFn, envelope_usd: float,
                          timeout_s: float = 180.0) -> RouteRun:
    runner = llm.with_structured_output(RouterResponse, include_raw=True)
    run = RouteRun(skeleton=skeleton)
    new_terminals: List[TerminalSkeleton] = []
    for t in skeleton.terminals:
        if not t.routed:
            new_terminals.append(t)
            continue
        solution = solutions.get(t.scope, "")
        if not solution:
            run.flags.append(Flag("router_failed", t.terminal_id, "no solution on the scope"))
            new_terminals.append(t)
            continue
        message = build_router_message(t, questions.get(t.scope, ""), solution)
        corpus = corpora[t.scope]
        errors: List[str] = []
        comps: List[RoutedComponent] = []
        for attempt in (1, 2):
            if run.cost_usd >= envelope_usd:
                raise EnvelopeExceeded(f"spent ${run.cost_usd:.4f} ≥ envelope ${envelope_usd:.2f} "
                                       f"before {t.terminal_id}")
            payload = message
            if errors:
                payload += ("\n\n=== YOUR PREVIOUS ANSWER FAILED VALIDATION — fix EXACTLY these ===\n"
                            + "\n".join(f"  · {e}" for e in errors))
            t0 = time.monotonic()
            result = await asyncio.wait_for(runner.ainvoke([
                SystemMessage(content=ROUTER_SYSTEM_PROMPT), HumanMessage(content=payload)]),
                timeout=timeout_s)
            latency = time.monotonic() - t0
            in_tok, out_tok, cached = _usage(result)
            if result.get("parsing_error") or result.get("parsed") is None:
                errors, comps = [f"unparseable response: {result.get('parsing_error')}"], []
            else:
                comps = list(result["parsed"].components)
                errors = validate_components(comps, corpus=corpus)
            run.calls.append(RouteCall(t.terminal_id, attempt, in_tok, out_tok, cached,
                                       cost_fn(in_tok, out_tok, cached), latency, tuple(errors),
                                       tuple(c.name_he for c in comps)))
            if not errors:
                break
        if errors:
            run.failed.append(t.terminal_id)
            run.flags.append(Flag("router_failed", t.terminal_id, "; ".join(errors)[:160]))
            new_terminals.append(t)
        else:
            new_terminals.append(apply_routing(t, comps, skeleton.precision))
    run.skeleton = replace(skeleton, terminals=tuple(new_terminals))
    return run
