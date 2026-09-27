"""
The grader-v6 pricer — selections in, points out (PR_grader_v6_options.md §4).

    price(view: DraftV6View, overlay: PricingOverlay | None) -> PricedTest

PURE (PRC-8): no I/O, DB, LLM, clock, logging or randomness — pinned by an
import scan. Everything it needs is in the view, so the TypeScript mirror
computes the same result from the same JSON (PRC-7). A logic-bug signal (an
upper clamp V13 should make impossible) is RETURNED in `PricedTest.flags` for
the caller to log, rather than logged here.

The algorithm, in order (§4.2, as amended at STOP-1 and by AM-G13):
  1 Resolve   her typed amount (credit only, AM-G3) › her option › the model's
              option — evidence-gated (AM-G2): a MODEL selection of a
              non-default option on an `evidence_required` check whose quote is
              not exact/fuzzy resolves to the default; hers never is ›
              the default (zero / `none`) with UNVERIFIED_CHECK (PRC-1).
  2 Activity  a fault that `requires` T is active iff T resolved > 0 (PRC-2);
              an active fault with a fault option is a CANDIDATE charge.
  3 BehaviorCap  [AM-G13, PRC-3] the charges of all charged faults requiring
              one credit check T sum to ≥ −value(T); an excess is removed
              LATEST plan order first, and a reduced charge is `capped`.
  4 ChargedOnce  [AM-G13, PRC-4] every charge group with a candidate charges
              EXACTLY one member. The members are chosen JOINTLY across the
              scope's groups: the assignment giving the LOWEST scope total, the
              total taken with steps 3, 5 and her terminal overrides (6)
              applied (census Q-23). Assignments are enumerated
              lexicographically — groups in plan order (a group's place is its
              first member's), members in plan order — and the FIRST that
              attains the minimum is kept. The rest are `superseded`.
  5 Terminal  raw = credit + charges; below 0, charges are reduced in REVERSE
              plan order until the terminal reaches 0 (`floored`,
              BOUNDS_CLAMPED); awarded = clamp(raw, 0, P) (PRC-5).
  6 Override  her terminal award replaces it; charge statuses stay for display.
  7 Notes     never priced (Q-10); observed ones are reported.
  8 Totals    `score_with_selection`, unchanged.

Statuses: inactive · no_fault · applied · capped · superseded · floored.
Why 3 and 4 changed (census Q-22): S-3's per-fault cap let two faults on one
behavior cost twice what it earned, and a group charge chosen before the floor
could hide in a floored terminal, then MOVE to one where it bites when another
fault was cleared — both lowered a total when an answer got better (PRC-6).

[AM-G1] There are no reduction terminals and no home statuses.

Named `pricing_v6` while the v5 pricer (`pricing.py`) still prices legacy
drafts; §9.4 deletes that one once legacy parity is green, and this module
becomes the one pricer.
"""
from __future__ import annotations

import itertools
from decimal import Decimal
from types import SimpleNamespace
from typing import Dict, List, Literal, NamedTuple, Optional, Set, Tuple

from pydantic import BaseModel, Field

from app.agents.grader.plan_schemas import PlanCheckV6
from app.schemas.ontology_types import FlagReason
from app.services.selection_scoring import ScopeScore, score_with_selection

ZERO = Decimal("0")
_VERIFIED = ("exact", "fuzzy")

UNVERIFIED_CHECK = FlagReason.UNVERIFIED_CHECK.value
EVIDENCE_UNVERIFIED = FlagReason.EVIDENCE_UNVERIFIED.value
BOUNDS_CLAMPED = FlagReason.BOUNDS_CLAMPED.value
UPPER_CLAMP_LOGIC_BUG = "upper_clamp_logic_bug"


# ═══════════════════════════════════════════════════════════════════════════
# inputs — the view of one draft (§9.1) and of her overlay (§9.2)
# ═══════════════════════════════════════════════════════════════════════════

class ViewTerminal(BaseModel):
    model_config = {"frozen": True}
    terminal_id: str
    question_id: str
    sub_question_id: Optional[str] = None
    points_possible: Decimal


class ViewCheck(BaseModel):
    """One plan check, copied into the draft, with the model's selection."""
    model_config = {"frozen": True}
    plan: PlanCheckV6
    plan_index: int                                   # position in the plan: THE order
    model_option_id: Optional[str] = None
    quote_status: Optional[Literal["exact", "fuzzy", "not_found"]] = None


class SelectionGroupView(BaseModel):
    model_config = {"frozen": True}
    of_question_ids: List[str]
    choose_k: int


class SelectionView(BaseModel):
    """What `score_with_selection` reads from the contract: the ACHIEVABLE
    total, the question order (its tie-break), and the groups."""
    model_config = {"frozen": True}
    total_points: Decimal
    question_order: List[str]
    groups: List[SelectionGroupView] = Field(default_factory=list)


class DraftV6View(BaseModel):
    model_config = {"frozen": True}
    precision: Decimal
    terminals: List[ViewTerminal]
    checks: List[ViewCheck]
    selection: SelectionView


class CheckDecision(BaseModel):
    """Her decision on one check (AM-G3). `amount` is valid on credit checks
    only — CW-3 refuses it elsewhere; the pricer ignores it elsewhere."""
    model_config = {"frozen": True}
    option_id: Optional[str] = None
    amount: Optional[Decimal] = None
    comment: Optional[str] = None
    evidence_disputed: bool = False


class PricingOverlay(BaseModel):
    model_config = {"frozen": True}
    checks: Dict[str, CheckDecision] = Field(default_factory=dict)
    terminal_points: Dict[str, Decimal] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# outputs (§4.3)
# ═══════════════════════════════════════════════════════════════════════════

ResolutionSource = Literal["amount", "overlay", "model", "gated", "default"]
FaultStatus = Literal["inactive", "no_fault", "applied", "capped", "superseded", "floored"]
Chip = Literal["full", "partial", "zero"]


class ResolvedCheck(BaseModel):
    model_config = {"frozen": True}
    check_id: str
    option_id: Optional[str]                          # None only for a typed amount
    value: Decimal
    source: ResolutionSource
    missing: bool = False                             # no valid selection at all
    claimed_option_id: Optional[str] = None           # the model's own (valid) pick


class PricedCharge(BaseModel):
    model_config = {"frozen": True}
    check_id: str
    option_id: str
    amount: Decimal                                   # the resolved option's value (≤ 0)
    charged: Decimal                                  # what was actually deducted (≤ 0)
    status: FaultStatus


class PricedTerminal(BaseModel):
    model_config = {"frozen": True}
    terminal_id: str
    awarded: Decimal
    credit_points: Decimal
    chip: Chip
    primary_check_id: Optional[str]
    charges: List[PricedCharge]
    notes_observed: List[str]
    flags: List[str]
    overridden: bool
    typed: bool                                       # [AM-G3] an amount on any of its checks


class PricedScope(BaseModel):
    model_config = {"frozen": True}
    question_id: str
    sub_question_id: Optional[str]
    points_possible: Decimal
    awarded: Decimal
    counted: bool


class PricedTest(BaseModel):
    model_config = {"frozen": True}
    terminals: List[PricedTerminal]
    checks: List[ResolvedCheck]
    scopes: List[PricedScope]
    total_score: Decimal
    total_possible: Decimal
    flags: List[str]


# ═══════════════════════════════════════════════════════════════════════════
# the algorithm
# ═══════════════════════════════════════════════════════════════════════════

def _resolve(vc: ViewCheck, decision: Optional[CheckDecision]) -> ResolvedCheck:
    """Step 1 — PRC-1 as amended (AM-G2, AM-G3)."""
    plan = vc.plan
    default = plan.default_option
    claimed = plan.option(vc.model_option_id)
    claimed_id = claimed.option_id if claimed is not None else None

    if decision is not None:
        if plan.role == "credit" and decision.amount is not None:
            return ResolvedCheck(check_id=plan.check_id, option_id=None, value=decision.amount,
                                 source="amount", claimed_option_id=claimed_id)
        mine = plan.option(decision.option_id)
        if mine is not None:
            return ResolvedCheck(check_id=plan.check_id, option_id=mine.option_id,
                                 value=mine.value, source="overlay", claimed_option_id=claimed_id)

    if claimed is None:
        return ResolvedCheck(check_id=plan.check_id, option_id=default.option_id,
                             value=default.value, source="default", missing=True)
    if (plan.evidence_required and claimed.option_id != default.option_id
            and vc.quote_status not in _VERIFIED):
        return ResolvedCheck(check_id=plan.check_id, option_id=default.option_id,
                             value=default.value, source="gated", claimed_option_id=claimed_id)
    return ResolvedCheck(check_id=plan.check_id, option_id=claimed.option_id,
                         value=claimed.value, source="model", claimed_option_id=claimed_id)


def _chip(awarded: Decimal, possible: Decimal) -> Chip:
    if awarded == possible:
        return "full"
    return "zero" if awarded == 0 else "partial"


class _Settled(NamedTuple):
    """One terminal under one choice of charged faults (steps 3, 5, 6)."""
    charged: Dict[str, Decimal]
    status: Dict[str, FaultStatus]
    credit: Decimal
    final: Decimal
    floored: bool
    upper_bug: bool
    pin_clamped: bool


def _settle(t: ViewTerminal, tchecks: List[ViewCheck], chosen: Set[str],
            candidate: Dict[str, Decimal], resolved: Dict[str, ResolvedCheck],
            order: Dict[str, int], pin: Optional[Decimal]) -> _Settled:
    charged: Dict[str, Decimal] = {c.plan.check_id: candidate[c.plan.check_id]
                                   for c in tchecks if c.plan.check_id in chosen}
    status: Dict[str, FaultStatus] = {cid: "applied" for cid in charged}

    # 3 — BehaviorCap: a behavior's faults together never cost more than it earned
    by_behavior: Dict[str, List[str]] = {}
    for c in tchecks:
        if c.plan.check_id in charged and c.plan.requires is not None:
            by_behavior.setdefault(c.plan.requires, []).append(c.plan.check_id)
    for behavior, members in by_behavior.items():
        room = resolved[behavior].value + sum((charged[m] for m in members), ZERO)
        for m in sorted(members, key=lambda x: order[x], reverse=True):
            if room >= 0:
                break
            relief = min(-room, -charged[m])
            charged[m] += relief
            room += relief
            status[m] = "capped"

    # 5 — the terminal floor, reverse plan order
    credit = sum((resolved[c.plan.check_id].value for c in tchecks
                  if c.plan.role == "credit"), ZERO)
    raw = credit + sum(charged.values(), ZERO)
    floored = raw < 0
    if floored:
        deficit = -raw
        for cid in sorted(charged, key=lambda x: order[x], reverse=True):
            if deficit <= 0:
                break
            relief = min(deficit, -charged[cid])
            charged[cid] += relief
            deficit -= relief
            status[cid] = "floored"
        raw = credit + sum(charged.values(), ZERO)
    upper_bug = raw > t.points_possible
    if upper_bug:
        raw = t.points_possible

    # 6 — her terminal override
    final, pin_clamped = raw, False
    if pin is not None:
        final = min(max(pin, ZERO), t.points_possible)
        pin_clamped = final != pin
    return _Settled(charged, status, credit, final, floored, upper_bug, pin_clamped)


def _require_scope_local_groups(checks: List[ViewCheck],
                                scope_of: Dict[str, Tuple[str, Optional[str]]]) -> None:
    """V7 is a PRECONDITION of step 4: a scope's groups are assigned jointly, so a
    group whose members sat in two scopes would be charged once in EACH. Plans
    are validated at assembly (V7), so this never fires on a real plan; if it
    does, the input is wrong and pricing it would be a silent repair (§3.5a:
    a consuming path refuses)."""
    seen: Dict[str, Tuple[str, Optional[str]]] = {}
    for c in checks:
        group = c.plan.charge_group
        if group is None:
            continue
        scope = scope_of.get(c.plan.priced_terminal_id)
        if seen.setdefault(group, scope) != scope:
            raise ValueError(f"charge group {group!r} spans scopes {seen[group]} and {scope} "
                             f"(V7): the pricer assigns a scope's groups jointly (AM-G13)")


def price(view: DraftV6View, overlay: Optional[PricingOverlay] = None) -> PricedTest:
    overlay = overlay or PricingOverlay()
    checks = sorted(view.checks, key=lambda c: c.plan_index)          # plan order, always
    order = {c.plan.check_id: i for i, c in enumerate(checks)}

    # 1 — resolve
    resolved: Dict[str, ResolvedCheck] = {
        c.plan.check_id: _resolve(c, overlay.checks.get(c.plan.check_id)) for c in checks}

    # 2 — activity: the candidate charges
    candidate: Dict[str, Decimal] = {}
    base_status: Dict[str, FaultStatus] = {}
    for c in checks:
        plan = c.plan
        if plan.role != "fault":
            continue
        r = resolved[plan.check_id]
        active = plan.requires is None or (
            plan.requires in resolved and resolved[plan.requires].value > 0)
        if not active:
            base_status[plan.check_id] = "inactive"
        elif r.value >= 0:
            base_status[plan.check_id] = "no_fault"
        else:
            candidate[plan.check_id] = r.value

    by_terminal: Dict[str, List[ViewCheck]] = {}
    for c in checks:
        by_terminal.setdefault(c.plan.priced_terminal_id, []).append(c)
    by_scope: Dict[Tuple[str, Optional[str]], List[ViewTerminal]] = {}
    scope_of: Dict[str, Tuple[str, Optional[str]]] = {}
    for t in view.terminals:
        by_scope.setdefault((t.question_id, t.sub_question_id), []).append(t)
        scope_of[t.terminal_id] = (t.question_id, t.sub_question_id)
    _require_scope_local_groups(checks, scope_of)

    # 3–6 — one scope at a time; its charge groups are assigned jointly (4)
    settled: Dict[str, _Settled] = {}
    superseded: Set[str] = set()
    for terms in by_scope.values():
        tids = {t.terminal_id for t in terms}
        in_scope = [c for c in checks if c.plan.priced_terminal_id in tids]
        ungrouped = {c.plan.check_id for c in in_scope
                     if c.plan.check_id in candidate and c.plan.charge_group is None}
        first_member: Dict[str, int] = {}
        members: Dict[str, List[str]] = {}
        for c in in_scope:
            group = c.plan.charge_group
            if group is None:
                continue
            first_member.setdefault(group, order[c.plan.check_id])
            if c.plan.check_id in candidate:
                members.setdefault(group, []).append(c.plan.check_id)
        groups = sorted(members, key=lambda g: first_member[g])

        best: Optional[Tuple[Decimal, Set[str], Dict[str, _Settled]]] = None
        for assignment in itertools.product(*(members[g] for g in groups)):
            chosen = ungrouped | set(assignment)
            trial = {t.terminal_id: _settle(t, by_terminal.get(t.terminal_id, []), chosen,
                                            candidate, resolved, order,
                                            overlay.terminal_points.get(t.terminal_id))
                     for t in terms}
            total = sum((st.final for st in trial.values()), ZERO)
            if best is None or total < best[0]:                   # the FIRST minimum
                best = (total, chosen, trial)
        _total, chosen, trial = best
        settled.update(trial)
        superseded.update(cid for g in groups for cid in members[g] if cid not in chosen)

    # 7 — terminals, as priced
    test_flags: List[str] = []
    priced_terminals: List[PricedTerminal] = []
    for t in view.terminals:
        tchecks = by_terminal.get(t.terminal_id, [])
        st = settled[t.terminal_id]
        flags: List[str] = []
        if any(resolved[c.plan.check_id].missing for c in tchecks):
            flags.append(UNVERIFIED_CHECK)
        if any(resolved[c.plan.check_id].source == "gated" for c in tchecks):
            flags.append(EVIDENCE_UNVERIFIED)
        if st.floored:
            flags.append(BOUNDS_CLAMPED)
        if st.upper_bug:
            flags.append(BOUNDS_CLAMPED)
            test_flags.append(f"{UPPER_CLAMP_LOGIC_BUG}:{t.terminal_id}")
        if st.pin_clamped:
            flags.append(BOUNDS_CLAMPED)

        charges = []
        for c in tchecks:
            if c.plan.role != "fault":
                continue
            cid = c.plan.check_id
            r = resolved[cid]
            status: FaultStatus = st.status.get(cid) or (
                "superseded" if cid in superseded else base_status[cid])
            charges.append(PricedCharge(
                check_id=cid, option_id=r.option_id or c.plan.default_option.option_id,
                amount=r.value, charged=st.charged.get(cid, ZERO), status=status))

        primary: Optional[str] = None
        top = ZERO
        for c in tchecks:
            if c.plan.role != "credit":
                continue
            v = resolved[c.plan.check_id].value
            if v > top:
                primary, top = c.plan.check_id, v

        priced_terminals.append(PricedTerminal(
            terminal_id=t.terminal_id, awarded=st.final, credit_points=st.credit,
            chip=_chip(st.final, t.points_possible), primary_check_id=primary,
            charges=charges,
            notes_observed=[c.plan.check_id for c in tchecks
                            if c.plan.role == "note"
                            and resolved[c.plan.check_id].option_id == "observed"],
            flags=_dedup(flags), overridden=t.terminal_id in overlay.terminal_points,
            typed=any(resolved[c.plan.check_id].source == "amount" for c in tchecks)))

    # 8 — scopes and totals, unchanged (score_with_selection)
    scopes, scoring = _aggregate(view, priced_terminals)
    return PricedTest(
        terminals=priced_terminals,
        checks=[resolved[c.plan.check_id] for c in checks],
        scopes=scopes,
        total_score=scoring.total_score,
        total_possible=scoring.total_possible,
        flags=test_flags)


def _aggregate(view: DraftV6View, terminals: List[PricedTerminal]):
    awarded = {t.terminal_id: t.awarded for t in terminals}
    keys: List[Tuple[str, Optional[str]]] = []
    possible: Dict[Tuple[str, Optional[str]], Decimal] = {}
    got: Dict[Tuple[str, Optional[str]], Decimal] = {}
    for t in view.terminals:
        key = (t.question_id, t.sub_question_id)
        if key not in possible:
            keys.append(key)
            possible[key] = ZERO
            got[key] = ZERO
        possible[key] += t.points_possible
        got[key] += awarded[t.terminal_id]
    # `score_with_selection` reads exactly these three contract attributes;
    # the view carries them so the pricer stays a function of one document.
    contract = SimpleNamespace(
        total_points=view.selection.total_points,
        questions=[SimpleNamespace(question_id=q) for q in view.selection.question_order],
        selection_groups=[SimpleNamespace(of_question_ids=list(g.of_question_ids),
                                          choose_k=g.choose_k)
                          for g in view.selection.groups])
    scoring = score_with_selection(
        [ScopeScore(question_id=q, sub_question_id=s, awarded=got[(q, s)]) for q, s in keys],
        contract)
    scopes = [PricedScope(question_id=q, sub_question_id=s, points_possible=possible[(q, s)],
                          awarded=got[(q, s)], counted=scoring.is_counted((q, s)))
              for q, s in keys]
    return scopes, scoring


def _dedup(xs: List[str]) -> List[str]:
    out: List[str] = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out
