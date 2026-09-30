"""plan/v6 expressibility (PR_grader_v6_options.md §13.1): for every GT terminal award,
does SOME option assignment price to it?

Priced by THE pricer (`pricing_v6.price`), never a re-derivation: each terminal is
priced alone, over every combination of the options of the checks priced at it
(credits and faults; a note never moves points), with every evidence citation taken
as verified — the question is what the plan CAN express, not what a verifier will
find. Per terminal, and existential across terminals exactly as the v5 guard is
(`plan_expressibility.py`): a charge group shared with another terminal is taken as
charged here, which some assignment of the other members makes true.

Enumeration is exact and capped at 10⁶ assignments per terminal (§13.1). A terminal
over the cap is reported as `capped`, never guessed.

[A-5] A miss on a cell whose GT rests on an owner ruling written nowhere in the
rubric is labelled `unwritten_ruling`, apart from `planner_miss`.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Set, Tuple

from app.agents.grader.plan_schemas import GradingPlanV6, PlanCheckV6
from app.services.pricing_v6 import (DraftV6View, SelectionView, ViewCheck, ViewTerminal,
                                     price)

from .plan_expressibility import PLANNER_MISS, UNWRITTEN_RULING, UNWRITTEN_RULINGS

ENUMERATION_CAP = 10 ** 6


def reachable_awards_v6(plan: GradingPlanV6, terminal_id: str, precision: Decimal
                        ) -> Optional[Set[Decimal]]:
    """Every award the plan can price at `terminal_id`, or None over the cap."""
    term = next(t for t in plan.terminals if t.terminal_id == terminal_id)
    indexed = [(i, c) for i, c in enumerate(plan.checks)
               if c.priced_terminal_id == terminal_id and c.role in ("credit", "fault")]
    size = 1
    for _, c in indexed:
        size *= len(c.options)
    if size > ENUMERATION_CAP:
        return None
    vt = ViewTerminal(terminal_id=terminal_id, question_id="q",
                      points_possible=term.points_possible)
    selection = SelectionView(total_points=term.points_possible, question_order=["q"])
    out: Set[Decimal] = set()
    for choice in itertools.product(*(c.options for _, c in indexed)):
        view = DraftV6View(
            precision=precision, terminals=[vt], selection=selection,
            checks=[ViewCheck(plan=c, plan_index=i, model_option_id=o.option_id, quote_status="exact")
                    for (i, c), o in zip(indexed, choice)])
        out.add(price(view).terminals[0].awarded)
    return out


@dataclass(frozen=True)
class MissV6:
    fixture: str
    terminal_id: str
    award: Decimal
    reachable: Tuple[str, ...]                 # empty when capped
    capped: bool = False

    @property
    def label(self) -> str:
        return (UNWRITTEN_RULING if (self.fixture, self.terminal_id) in UNWRITTEN_RULINGS
                else PLANNER_MISS)

    def as_dict(self) -> dict:
        return {"fixture": self.fixture, "terminal_id": self.terminal_id, "award": str(self.award),
                "reachable": list(self.reachable), "capped": self.capped, "label": self.label}


def expressibility_v6(plan: GradingPlanV6, judgments: Dict[str, Sequence[Tuple[str, Decimal]]],
                      precision: Decimal) -> Tuple[int, List[MissV6]]:
    """(cells judged, misses) over `judgments` = {fixture: [(terminal_id, award)]}."""
    cache: Dict[str, Optional[Set[Decimal]]] = {}
    total, misses = 0, []
    for fixture, cells in judgments.items():
        for tid, award in cells:
            total += 1
            if tid not in cache:
                cache[tid] = reachable_awards_v6(plan, tid, precision)
            reach = cache[tid]
            if reach is None:
                misses.append(MissV6(fixture, tid, award, (), capped=True))
            elif award not in reach:
                misses.append(MissV6(fixture, tid, award, tuple(format(v.normalize(), "f") for v in sorted(reach))))
    return total, misses


def plan_decision(plan: GradingPlanV6, terminal_id: str) -> str:
    """The plan's shape at a terminal, in one line — «the plan decision that excludes
    it» (§13.1): each check's role, shape and option values."""
    parts = []
    for c in plan.checks:
        if c.priced_terminal_id != terminal_id or c.role == "note":
            continue
        vals = "/".join(format(o.value.normalize(), "f") for o in c.options)
        req = f" req {c.requires.rsplit('.', 1)[1]}" if c.requires else ""
        grp = f" grp {c.charge_group}" if c.charge_group else ""
        parts.append(f"{c.check_id.rsplit('.', 1)[1]} {c.shape}[{vals}]{req}{grp}")
    return "; ".join(parts)
