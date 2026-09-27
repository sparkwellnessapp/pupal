"""
The deterministic fallback reasoning line (PR_grader_v6_options.md §7.5).

    compose_reasoning_he(priced, view, terminal_id) -> str

Used when the explainer fails, is late, or produces a line that fails E-1..E-5,
for that terminal only; also what approval freezes when no model line exists
for the effective selections (§7.7). Python only — the frontend always
receives lines from the backend.

  fully earned, no applied/floored charge  «כל הדרישות בקריטריון מולאו.»
  otherwise, in plan order, joined « · »:
    credit at zero                         «חסר: {description}»
    credit between zero and max            «{description}: {selected label}»
    applied or floored fault               «נוכה: {selected label}»
  past 200 chars: truncate at the last « · » and append « …»

A terminal SHE decided (a terminal override, or a typed amount on any check —
AM-G3) is not explained by anyone: the line is «הציון נקבע ידנית».
Pure and deterministic: the same prices give the same line, whatever the
order of the view's check list.
"""
from __future__ import annotations

from typing import List

from app.agents.explainer.copy import (
    DEDUCTED_PREFIX_HE,
    ELLIPSIS,
    FULLY_EARNED_HE,
    MACHINE_VOCABULARY,
    MANUAL_HE,
    MAX_LINE,
    MISSING_PREFIX_HE,
    SEPARATOR,
)
from app.services.pricing_v6 import DraftV6View, PricedTest

__all__ = ["compose_reasoning_he", "FULLY_EARNED_HE", "MACHINE_VOCABULARY", "MANUAL_HE"]


def compose_reasoning_he(priced: PricedTest, view: DraftV6View, terminal_id: str) -> str:
    terminal = next(t for t in priced.terminals if t.terminal_id == terminal_id)
    if terminal.overridden or terminal.typed:
        return MANUAL_HE
    possible = next(t.points_possible for t in view.terminals if t.terminal_id == terminal_id)
    resolved = {r.check_id: r for r in priced.checks}
    charges = {c.check_id: c for c in terminal.charges}

    if terminal.awarded == possible and not any(
            c.status in ("applied", "floored") for c in terminal.charges):
        return FULLY_EARNED_HE

    parts: List[str] = []
    for vc in sorted(view.checks, key=lambda c: c.plan_index):
        plan = vc.plan
        if plan.priced_terminal_id != terminal_id:
            continue
        r = resolved[plan.check_id]
        if plan.role == "credit":
            if r.value == 0:
                parts.append(f"{MISSING_PREFIX_HE}{plan.description_he}")
            elif r.value < plan.options[0].value:
                option = plan.option(r.option_id)
                parts.append(f"{plan.description_he}: {option.label_he}")
        elif plan.role == "fault":
            ch = charges.get(plan.check_id)
            if ch is not None and ch.status in ("applied", "floored"):
                parts.append(f"{DEDUCTED_PREFIX_HE}{plan.option(ch.option_id).label_he}")

    if not parts:
        return FULLY_EARNED_HE
    return _fit(parts)


def _fit(parts: List[str]) -> str:
    line = SEPARATOR.join(parts)
    if len(line) <= MAX_LINE:
        return line
    while len(parts) > 1 and len(SEPARATOR.join(parts)) + len(ELLIPSIS) > MAX_LINE:
        parts = parts[:-1]
    line = SEPARATOR.join(parts)
    if len(line) + len(ELLIPSIS) > MAX_LINE:
        line = line[: MAX_LINE - len(ELLIPSIS)].rstrip()
    return line + ELLIPSIS
