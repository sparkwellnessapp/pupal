"""
THE pricing composition point (PR-G5).

Grading, `PATCH /draft`, `/approve`, the batch feed's `total_awarded` and the
fixture generator all price through this module. That is not tidiness: the
selection-scoring incident (§5) happened because two places derived the same
number and drifted, so a teacher reviewed one percentage and a different one
froze into the immutable contract. One arithmetic, one direction of derivation.

Points are DERIVED from verdicts, never stored as an input. An override is a
verdict on a check (R-2 branch B — the production count of legacy overlays was
0, so there is no `points_awarded` path and no dual-path pricer).

Two rules in here are policy, not arithmetic, and both are deliberate:

* **Evidence gating applies to the MODEL, not to the teacher.** A `met` whose
  cited span is not in the answer earns nothing — that is the invented-credit
  guard. But a check the TEACHER overrode is priced on her verdict alone: she
  has the paper in front of her, and refusing her credit because the model's
  citation failed would make her argue with the machine about a fact she can
  see. The teacher is the authority (CLAUDE.md §2).
* **Charge groups dedup across the whole SCOPE**, not per terminal: the same
  defect is charged once, by the first firing member in document order, at the
  maximum amount fired in the group.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.schemas.graded_test_draft import Check

# (terminal_id, points_possible, checks)
ScopeTerminals = Sequence[Tuple[str, Decimal, Sequence[Check]]]

_VERIFIED = ("exact", "fuzzy")


@dataclass(frozen=True)
class TerminalPrice:
    awarded: Decimal        # clamped to [0, possible] and snapped to the grid
    raw: Decimal            # earned − deducted, before clamp/snap


def _snap(value: Decimal, lo: Decimal, hi: Decimal, precision: Decimal) -> Decimal:
    clamped = max(lo, min(value, hi))
    return (clamped / precision).to_integral_value(rounding=ROUND_HALF_UP) * precision


def _fired(check: Check) -> bool:
    """Tariffs are binary: partially_met is coerced to fired."""
    return check.verdict in ("not_met", "partially_met")


def counted_units(check: Check) -> Optional[int]:
    """The units a counted check earns, or None when the record cannot say.

    `met` ⇒ every unit; `not_met` ⇒ none; `partially_met` ⇒ the reported count,
    clamped into [0, unit_count]. A partially_met with NO count is None — the
    caller prices nothing and flags, because inventing a count would be a
    number the model never emitted."""
    n = check.unit_count or 0
    if check.verdict == "met":
        return n
    if check.verdict == "not_met":
        return 0
    if check.units_correct is None:
        return None
    return max(0, min(n, int(check.units_correct)))


def _credited(check: Check, overridden: bool) -> bool:
    """Whether a `required` check may earn its points at all."""
    if check.verdict not in ("met", "partially_met"):
        return False
    if overridden:
        return True                       # the teacher decided; see module doc
    return check.quote_status in _VERIFIED


def price_scope_checks_detailed(
    terminals: ScopeTerminals,
    precision: Decimal,
    overridden_check_ids: Optional[Set[str]] = None,
) -> Dict[str, TerminalPrice]:
    """Price every terminal in ONE scope from its checks. Pure."""
    overridden = overridden_check_ids or frozenset()

    # charge-once pre-pass, scope-wide: per group, the first firing check in
    # document order pays the MAX amount fired anywhere in that group.
    first_firing: Dict[str, str] = {}
    group_amount: Dict[str, Decimal] = {}
    for _tid, _possible, checks in terminals:
        for check in checks:
            if check.kind != "tariff" or not _fired(check):
                continue
            group = check.charge_group or f"__solo__{check.check_id}"
            first_firing.setdefault(group, check.check_id)
            amount = check.tariff or Decimal("0")
            if amount > group_amount.get(group, Decimal("0")):
                group_amount[group] = amount

    out: Dict[str, TerminalPrice] = {}
    for tid, possible, checks in terminals:
        earned = Decimal("0")
        deducted = Decimal("0")
        for check in checks:
            if check.kind == "required":
                if not _credited(check, check.check_id in overridden):
                    continue
                if check.verdict == "met":
                    earned += check.points
                else:                                     # partially_met
                    earned += check.points * check.partial_fraction
            elif check.kind == "counted":
                # R-E Case 1: points × units_correct / unit_count, snapped with the
                # terminal below (12 × 15/17 = 10.588 → 10.5 on a 0.25 grid). The
                # count is the partial credit; partial_fraction is not consulted.
                if not _credited(check, check.check_id in overridden):
                    continue
                units = counted_units(check)
                if units is None:
                    continue                          # pricer flags COUNT_MISSING
                earned += check.points * Decimal(units) / Decimal(check.unit_count or 1)
            elif check.kind == "tariff":
                if not _fired(check):
                    continue
                group = check.charge_group or f"__solo__{check.check_id}"
                if first_firing.get(group) == check.check_id:
                    deducted += group_amount[group]
            # note_only never moves points — the rubric's «לציין, לא להוריד»
        raw = earned - deducted
        out[tid] = TerminalPrice(
            awarded=_snap(raw, Decimal("0"), possible, precision), raw=raw)
    return out


def price_scope_checks(
    terminals: ScopeTerminals,
    precision: Decimal,
    overridden_check_ids: Optional[Set[str]] = None,
) -> Dict[str, Decimal]:
    """The awards only — the common case."""
    return {tid: p.awarded for tid, p in
            price_scope_checks_detailed(terminals, precision, overridden_check_ids).items()}


def apply_overlay(checks: Sequence[Check],
                  overrides: Iterable) -> Tuple[List[Check], Set[str]]:
    """Return (effective checks, ids the teacher decided).

    Sparse by construction: a check with no override passes through untouched,
    so the AI's verdict remains the record for everything she did not look at.
    """
    by_id = {o.check_id: o for o in (overrides or [])}
    effective, touched = [], set()
    for check in checks:
        override = by_id.get(check.check_id)
        if override is None:
            effective.append(check)
            continue
        touched.add(check.check_id)
        effective.append(check.model_copy(update={"verdict": override.verdict}))
    return effective, touched
