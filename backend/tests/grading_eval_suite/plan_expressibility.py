"""
Plan-expressibility guard [owner H-4 item 3, 2026-08-28 — permanent].

For every fixture GT, every ratified award must be REACHABLE under the plan
algebra: each required check contributes {0, points×partial_fraction, points},
each tariff anchored at the terminal either fires (its amount) or not, the
result clamps to [0, points_possible] and snaps to the precision grid. A GT
award no verdict assignment can produce means the plan cannot express the
teacher's judgment — a plan defect, caught mechanically before any spend.

Reachability is per-terminal and EXISTENTIAL: a cross-terminal charge_group's
tariff is treated as fireable at every member terminal (some assignment of the
other members makes it so). Exhaustive enumeration — the worst terminal is
3^4 required-states; nothing here approaches combinatorial cost.

Two call sites, one function (§0.4): the standing pytest
(test_plan_expressibility.py — re-runs automatically on any plan or GT
amendment) and the runner's `_load_plan` (pre-spend refusal — or, under
`expressibility_guard: "report"` [Track B 1e], a provenance record).

[A-5, owner ruling 2026-09-27] A miss is labelled. Two hobby GT awards rest on
tariffs the OWNER ruled into the hand plan (`source="ruling"`) that the rubric
text never states — no planner reading the rubric can reach them. They are
"unwritten_ruling", reported apart from every other miss ("planner_miss").
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from typing import Any, Dict, List, Set, Tuple

from app.agents.grader.plan_schemas import GradingPlan, TerminalPlan

from .fixtures import TerminalInfo
from .schemas import FixtureGT


def reachable_awards(tp: TerminalPlan, precision: Decimal) -> Set[Decimal]:
    counted = [c for c in tp.checks if c.kind == "counted"]
    if counted:
        # V12: alone on its terminal. Reachable = every snapped k/N fraction.
        c = counted[0]
        n = int(c.unit_count or 0)
        return {
            (max(Decimal("0"), min(c.points * Decimal(k) / Decimal(n), tp.points_possible))
             / precision).to_integral_value(rounding=ROUND_HALF_UP) * precision
            for k in range(n + 1)
        }
    required = [c for c in tp.checks if c.kind == "required"]
    tariffs = [c for c in tp.checks if c.kind == "tariff"]
    req_options = [(Decimal("0"), c.points * c.partial_fraction, c.points)
                   for c in required]
    tariff_options = [(Decimal("0"), c.tariff_amount or Decimal("0"))
                      for c in tariffs]
    out: Set[Decimal] = set()
    for earns in product(*req_options) if req_options else [()]:
        earned = sum(earns, Decimal("0"))
        for deds in product(*tariff_options) if tariff_options else [()]:
            raw = earned - sum(deds, Decimal("0"))
            clamped = max(Decimal("0"), min(raw, tp.points_possible))
            out.add((clamped / precision).to_integral_value(
                rounding=ROUND_HALF_UP) * precision)
    return out


# [A-5] (fixture, terminal) -> the owner ruling the award rests on. Keyed by
# CELL, not terminal: the same terminal on another student is an ordinary miss.
UNWRITTEN_RULINGS: Dict[Tuple[str, str], str] = {
    ("dan_basiuk", "q2.א.c1"): "owner-ruled −1 (hand plan q2.א.c1.t1, source=ruling)",
    ("yonatan_basiuk", "q2.ב.c4.s2"): "owner-ruled −0.5 (hand plan q2.ב.c4.s2.k2, source=ruling)",
}
UNWRITTEN_RULING, PLANNER_MISS = "unwritten_ruling", "planner_miss"


@dataclass(frozen=True)
class ExpressibilityMiss:
    fixture: str
    terminal_id: str
    award: Decimal
    reachable: Tuple[str, ...]
    plan_version: str

    @property
    def label(self) -> str:
        return (UNWRITTEN_RULING if (self.fixture, self.terminal_id) in UNWRITTEN_RULINGS
                else PLANNER_MISS)

    def message(self) -> str:
        return (f"EXPR: {self.fixture}/{self.terminal_id} GT award {self.award} is "
                f"UNREACHABLE under plan {self.plan_version!r} — reachable: "
                f"{list(self.reachable)}")

    def as_dict(self) -> Dict[str, Any]:
        return {"fixture": self.fixture, "terminal_id": self.terminal_id,
                "award": str(self.award), "reachable": list(self.reachable),
                "label": self.label}


def expressibility_misses(plan: GradingPlan,
                          gt: FixtureGT,
                          terminal_infos: Dict[str, TerminalInfo],
                          precision: Decimal) -> List[ExpressibilityMiss]:
    """Every GT award must be reachable; one record per award that is not."""
    plan_by_tid = {t.terminal_id: t for t in plan.terminals}
    out: List[ExpressibilityMiss] = []
    for t in gt.terminals:
        if t.awarded is None:
            continue        # [Track B 1b] unselected question: nothing to express
        tp = plan_by_tid.get(t.terminal_id)
        if tp is None:
            continue        # totality is validator rule V6's job, not ours
        reach = reachable_awards(tp, precision)
        if t.awarded not in reach:
            out.append(ExpressibilityMiss(
                fixture=gt.fixture, terminal_id=t.terminal_id, award=t.awarded,
                reachable=tuple(sorted(str(v) for v in reach)),
                plan_version=plan.plan_version))
    return out


def expressibility_errors(plan: GradingPlan,
                          gt: FixtureGT,
                          terminal_infos: Dict[str, TerminalInfo],
                          precision: Decimal) -> List[str]:
    """Every GT award must be reachable. Errors name fixture, terminal, award,
    and the reachable set — enough to fix the plan without re-deriving."""
    return [m.message()
            for m in expressibility_misses(plan, gt, terminal_infos, precision)]
