"""
grader-v5 plan validator — pure, loud, total (MISSION_grader_v5_closed_loop §5 V5-A).

validate_plan(plan, contract_terminal_points, terminal_scopes, precision) -> [errors]

Every rule carries a stable tag so tests and the H-4 render can name the exact
violation. An empty list is the ONLY pass. No I/O, no LLM, no floats.

Rules:
  V1  per terminal: Σ required.points == points_possible EXACTLY.
  V2  every points / tariff_amount value sits on the precision grid.
  V3  kind shape: required ⇒ points>0, no tariff_amount, no charge_group;
      tariff ⇒ points==0, 0 < tariff_amount <= points_possible;
      note_only ⇒ points==0, no tariff_amount, no charge_group.
  V4  required: points * partial_fraction sits on the grid (the partial award
      must be representable — no snapping ambiguity on the honest path).
  V5  check_id globally unique; terminal_id unique.
  V6  totality vs the contract: plan terminals == contract terminals exactly,
      and points_possible matches per terminal.
  V7  a charge_group never spans scopes (verdicts arrive per scope; a cross-
      scope group could not be deduped deterministically).
  V8  partial_fraction strictly inside (0, 1).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from app.agents.grader.plan_schemas import GradingPlan


def _on_grid(v: Decimal, precision: Decimal) -> bool:
    return (v % precision) == 0


def validate_plan(plan: GradingPlan,
                  *,
                  contract_terminal_points: Dict[str, Decimal],
                  terminal_scopes: Dict[str, str],
                  precision: Decimal) -> List[str]:
    errs: List[str] = []

    # V5 — uniqueness first (later rules assume addressability)
    seen_terminals: set = set()
    seen_checks: set = set()
    for tp in plan.terminals:
        if tp.terminal_id in seen_terminals:
            errs.append(f"V5: duplicate terminal {tp.terminal_id!r} in plan")
        seen_terminals.add(tp.terminal_id)
        for c in tp.checks:
            if c.check_id in seen_checks:
                errs.append(f"V5: duplicate check_id {c.check_id!r}")
            seen_checks.add(c.check_id)

    # V6 — totality vs contract
    missing = set(contract_terminal_points) - seen_terminals
    extra = seen_terminals - set(contract_terminal_points)
    for t in sorted(missing):
        errs.append(f"V6: contract terminal {t!r} has no plan")
    for t in sorted(extra):
        errs.append(f"V6: plan terminal {t!r} is not in the contract")

    group_scopes: Dict[str, set] = {}

    for tp in plan.terminals:
        tid = tp.terminal_id
        if tid in contract_terminal_points and \
                tp.points_possible != contract_terminal_points[tid]:
            errs.append(f"V6: {tid} points_possible {tp.points_possible} != "
                        f"contract {contract_terminal_points[tid]}")

        required_sum = Decimal("0")
        for c in tp.checks:
            # V2 — grid
            if not _on_grid(c.points, precision):
                errs.append(f"V2: {c.check_id} points {c.points} off the "
                            f"{precision} grid")
            if c.tariff_amount is not None and not _on_grid(c.tariff_amount, precision):
                errs.append(f"V2: {c.check_id} tariff_amount {c.tariff_amount} "
                            f"off the {precision} grid")

            # V3 — kind shape
            if c.kind == "required":
                required_sum += c.points
                if c.points <= 0:
                    errs.append(f"V3: required {c.check_id} must carry points > 0")
                if c.tariff_amount is not None:
                    errs.append(f"V3: required {c.check_id} carries a tariff_amount")
                if c.charge_group is not None:
                    errs.append(f"V3: required {c.check_id} carries a charge_group")
                # V8 + V4 — partial credit representability
                if not (Decimal("0") < c.partial_fraction < Decimal("1")):
                    errs.append(f"V8: {c.check_id} partial_fraction "
                                f"{c.partial_fraction} outside (0, 1)")
                elif not _on_grid(c.points * c.partial_fraction, precision):
                    errs.append(f"V4: {c.check_id} partial award "
                                f"{c.points * c.partial_fraction} off the grid — "
                                f"adjust points or partial_fraction")
            elif c.kind == "tariff":
                if c.points != 0:
                    errs.append(f"V3: tariff {c.check_id} must carry points == 0")
                if c.tariff_amount is None or c.tariff_amount <= 0:
                    errs.append(f"V3: tariff {c.check_id} needs tariff_amount > 0")
                elif c.tariff_amount > tp.points_possible:
                    errs.append(f"V3: {c.check_id} tariff_amount {c.tariff_amount} "
                                f"exceeds the terminal's points_possible "
                                f"{tp.points_possible} — a defect never costs more "
                                f"than the component it belongs to")
                if c.charge_group is not None and tid in terminal_scopes:
                    group_scopes.setdefault(c.charge_group, set()).add(
                        terminal_scopes[tid])
            else:  # note_only
                if c.points != 0:
                    errs.append(f"V3: note_only {c.check_id} must carry points == 0")
                if c.tariff_amount is not None:
                    errs.append(f"V3: note_only {c.check_id} carries a tariff_amount")
                if c.charge_group is not None:
                    errs.append(f"V3: note_only {c.check_id} carries a charge_group")

        # V1 — the sum law
        if required_sum != tp.points_possible:
            errs.append(f"V1: {tid} Σ required.points = {required_sum} != "
                        f"points_possible {tp.points_possible}")

    # V7 — charge groups stay inside one scope
    for group, scopes in sorted(group_scopes.items()):
        if len(scopes) > 1:
            errs.append(f"V7: charge_group {group!r} spans scopes "
                        f"{sorted(scopes)} — groups must stay inside one scope")

    return errs
