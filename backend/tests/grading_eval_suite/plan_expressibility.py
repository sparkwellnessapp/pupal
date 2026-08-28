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
amendment) and the runner's `_load_plan` (pre-spend refusal).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from typing import Dict, List, Set

from app.agents.grader.plan_schemas import GradingPlan, TerminalPlan

from .fixtures import TerminalInfo
from .schemas import FixtureGT


def reachable_awards(tp: TerminalPlan, precision: Decimal) -> Set[Decimal]:
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


def expressibility_errors(plan: GradingPlan,
                          gt: FixtureGT,
                          terminal_infos: Dict[str, TerminalInfo],
                          precision: Decimal) -> List[str]:
    """Every GT award must be reachable. Errors name fixture, terminal, award,
    and the reachable set — enough to fix the plan without re-deriving."""
    plan_by_tid = {t.terminal_id: t for t in plan.terminals}
    errs: List[str] = []
    for t in gt.terminals:
        tp = plan_by_tid.get(t.terminal_id)
        if tp is None:
            continue        # totality is validator rule V6's job, not ours
        reach = reachable_awards(tp, precision)
        if t.awarded not in reach:
            errs.append(
                f"EXPR: {gt.fixture}/{t.terminal_id} GT award {t.awarded} is "
                f"UNREACHABLE under plan {plan.plan_version!r} — reachable: "
                f"{sorted(str(v) for v in reach)}")
    return errs
