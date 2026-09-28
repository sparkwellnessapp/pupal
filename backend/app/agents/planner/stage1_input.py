"""Stage 1 → the planner's input (§5.2): the ONE place a `V6Scope` becomes a
`ScopePlannerInput`. Marker amounts are masked on the way in (`inputs.mask_*`),
and `unmask_span` is the exact inverse on the way out, for `source_span` only."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from app.agents.grader.plan_validator_v6 import normalize_span
from app.agents.plan_compiler.stage1_v6 import V6Scope

from .inputs import (AMOUNT_MASK, CompiledShape, NoteInput, ScopePlannerInput, SkeletonComponent,
                     TerminalInput, marker_input, mask_marker_amounts)

_FIGURE = r"\d+(?:[.,]\d+)?"


def scope_planner_input(scope: V6Scope) -> ScopePlannerInput:
    markers = list(scope.markers)

    def mask(text: str) -> str:
        return mask_marker_amounts(text or "", markers)

    terminals = []
    for t in scope.terminals:
        if t.shape == "components":
            status = "fixed" if t.fixed else "monolith"
            terminals.append(TerminalInput(
                terminal_id=t.terminal_id, points_possible=t.points_possible,
                teacher_text=mask(t.text),
                components=tuple(SkeletonComponent(c.component_id, mask(c.source_span), status)
                                 for c in t.components)))
        else:
            terminals.append(TerminalInput(
                terminal_id=t.terminal_id, points_possible=t.points_possible,
                teacher_text=mask(t.text),
                compiled=CompiledShape(shape=t.shape, source_span=mask(t.text))))
    notes = tuple(NoteInput(t.terminal_id, n.source_span) for t in scope.terminals for n in t.notes)
    return ScopePlannerInput(scope_id=scope.scope, question_text=scope.question_text,
                             example_solution=scope.example_solution or None,
                             terminals=tuple(terminals), notes=notes,
                             markers=tuple(marker_input(m) for m in markers))


def unmask_span(span: str, sources: Iterable[str]) -> Optional[str]:
    """The verbatim source text the planner quoted through our mask: each
    AMOUNT_MASK stands for exactly one figure. Returns the normalized match when it
    is UNIQUE across `sources`, the span unchanged when it carries no mask, and
    None when the masked quote cannot be resolved (V16 then refuses it — repair)."""
    if AMOUNT_MASK not in (span or ""):
        return span
    parts = normalize_span(span).split(AMOUNT_MASK)
    rx = re.compile(f"({_FIGURE})".join(re.escape(p) for p in parts))
    found = {m.group(0) for s in sources for m in rx.finditer(normalize_span(s or ""))}
    return found.pop() if len(found) == 1 else None
