"""
plan/v6 validators — pure, loud, total (PR_grader_v6_options.md §3.4).

validate_plan_v6(terminals, checks, ctx) -> [errors]   empty list == pass

Every error starts with its rule id, so tests and the plan render name the
exact violation. Run at assembly; on failure the assembler makes ONE repair
call and then falls back deterministically (§5.6) — a plan always assembles,
so nothing here raises.

Rules (as amended at STOP-1, docs/GRADER_V6_CENSUS.md §1a):
  V12 OptionShape       per shape; count exempt from uniqueness (AM-G4);
                        note = none/observed at 0 (Q-10); no home terminals (AM-G1)
  V13 CreditSum         Σ max credit value per terminal == points_possible
  V14 MarkerDisposition every marker disposed exactly once; OD-20/OD-21 folds
                        never reach here (Q-11)
  V15 RequiresShape     fault → credit on the same terminal; no chains
  V16 SourceSpan        normalized (NFC, whitespace-collapsed) substring
  V17 Grid              every value on the precision grid
  V18 Placement         the anchor is a candidate of every member marker
  V19 FaultLeakCandidate telemetry only — see v19_fault_leak_candidates
  V20 SkeletonConformity enumerated components kept exactly, in order
Kept from v5 (census Appendix C): V5 unique ids, V6 totality vs the contract,
V7 a charge group stays inside one scope, V10 no point text in anything the
point-blind verifier reads (descriptions AND option labels).

The v5 validator's own `V12` (counted shape, plan_validator.py) retires into
this V12's count arm when the v5 path is deleted.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Sequence, Set, Tuple

from app.agents.grader.plan_schemas import (
    DeductionMarker,
    MarkerDisposition,
    PlanCheckV6,
    TerminalPlanV6,
)
from app.agents.grader.plan_validator import _POINT_TEXT

_CREDIT_SHAPES = {"binary", "ladder", "levels", "count"}
_OPTION_COUNT = {"binary": (2, 2), "ladder": (3, 4), "levels": (2, 8), "fault": (2, 8),
                 "note": (2, 2)}
_MAX_COUNT_OPTIONS = 41
_LABEL_MAX = 140
_LATIN_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class SkeletonComponent:
    """One compiler-enumerated component: fixed input to the planner (C4)."""
    source_span: str
    points: Decimal


@dataclass(frozen=True)
class PlanContext:
    precision: Decimal
    contract_terminal_points: Dict[str, Decimal]
    terminal_scopes: Dict[str, str]                 # terminal_id -> scope label
    terminal_texts: Dict[str, str]                  # description + guidance + sub-criteria text
    scope_question_text: Dict[str, str]
    scope_example_solution: Dict[str, str]
    markers: List[DeductionMarker] = field(default_factory=list)
    dispositions: List[MarkerDisposition] = field(default_factory=list)
    skeleton: Dict[str, List[SkeletonComponent]] = field(default_factory=dict)


def normalize_span(s: str) -> str:
    """V16's normalization: NFC, whitespace runs collapsed, trimmed."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def _on_grid(v: Decimal, precision: Decimal) -> bool:
    return (v % precision) == 0


# ═══════════════════════════════════════════════════════════════════════════

def validate_plan_v6(terminals: Sequence[TerminalPlanV6], checks: Sequence[PlanCheckV6],
                     ctx: PlanContext) -> List[str]:
    errs: List[str] = []
    errs += _v5_v6_ids_and_totality(terminals, checks, ctx)
    for c in checks:
        errs += _v12_option_shape(c)
        errs += _v10_point_text(c)
        errs += _v17_grid(c, ctx.precision)
    errs += _v13_credit_sum(terminals, checks)
    errs += _v14_marker_disposition(checks, ctx)
    errs += _v15_requires(checks)
    errs += _v16_source_span(checks, ctx)
    errs += _v18_placement(terminals, checks, ctx)
    errs += _v7_group_scope(checks, ctx)
    errs += _v20_skeleton(checks, ctx)
    return errs


# ── V5 / V6 (kept) ───────────────────────────────────────────────────────────

def _v5_v6_ids_and_totality(terminals, checks, ctx) -> List[str]:
    errs: List[str] = []
    seen_t: Set[str] = set()
    for t in terminals:
        if t.terminal_id in seen_t:
            errs.append(f"V5: duplicate terminal {t.terminal_id!r}")
        seen_t.add(t.terminal_id)
    seen_c: Set[str] = set()
    for c in checks:
        if c.check_id in seen_c:
            errs.append(f"V5: duplicate check_id {c.check_id!r}")
        seen_c.add(c.check_id)
    for tid in sorted(set(ctx.contract_terminal_points) - seen_t):
        errs.append(f"V6: contract terminal {tid!r} has no plan")
    for tid in sorted(seen_t - set(ctx.contract_terminal_points)):
        errs.append(f"V6: plan terminal {tid!r} is not in the contract")
    for t in terminals:
        want = ctx.contract_terminal_points.get(t.terminal_id)
        if want is not None and t.points_possible != want:
            errs.append(f"V6: {t.terminal_id} points_possible {t.points_possible} != contract {want}")
    return errs


# ── V12 ──────────────────────────────────────────────────────────────────────

def _v12_option_shape(c: PlanCheckV6) -> List[str]:
    tag = f"V12: {c.check_id}"
    errs: List[str] = []
    role_ok = ((c.role == "credit" and c.shape in _CREDIT_SHAPES)
               or (c.role == "fault" and c.shape == "fault")
               or (c.role == "note" and c.shape == "note"))
    if not role_ok:
        return [f"{tag} role {c.role!r} does not admit shape {c.shape!r}"]
    ids = [o.option_id for o in c.options]
    if len(set(ids)) != len(ids):
        errs.append(f"{tag} duplicate option ids {ids}")
    for o in c.options:
        if not o.label_he or not o.label_he.strip() or len(o.label_he) > _LABEL_MAX:
            errs.append(f"{tag} option {o.option_id!r} label must be 1..{_LABEL_MAX} chars")
    n = len(c.options)
    if c.shape == "count":
        if not 2 <= n <= _MAX_COUNT_OPTIONS:
            errs.append(f"{tag} count has {n} options (2..{_MAX_COUNT_OPTIONS})")
    else:
        lo, hi = _OPTION_COUNT[c.shape]
        if not lo <= n <= hi:
            errs.append(f"{tag} {c.shape} has {n} options ({lo}..{hi})")
    if n < 2:
        return errs
    values = [o.value for o in c.options]

    if c.role == "credit":
        if values[0] <= 0:
            errs.append(f"{tag} top option must carry the check max > 0 (got {values[0]})")
        if values[-1] != 0:
            errs.append(f"{tag} the last option must be the zero option (got {values[-1]})")
        if c.shape == "count":                                         # AM-G4
            if any(b > a for a, b in zip(values, values[1:])):
                errs.append(f"{tag} count values must not increase {values}")
        else:
            if any(b >= a for a, b in zip(values, values[1:])):
                errs.append(f"{tag} values must be unique and strictly decreasing {values}")
        if any(o.marker_id is not None for o in c.options):
            errs.append(f"{tag} credit options carry no marker")
        if c.charge_group is not None:
            errs.append(f"{tag} charge_group is for fault checks only")
    elif c.role == "fault":
        first = c.options[0]
        if first.option_id != "none" or first.value != 0:
            errs.append(f"{tag} the first option must be `none` with value 0")
        for o in c.options[1:]:
            if o.value >= 0:
                errs.append(f"{tag} fault option {o.option_id!r} must be < 0 (got {o.value})")
            if not o.marker_id:
                errs.append(f"{tag} fault option {o.option_id!r} carries no marker_id")
    else:                                                               # note (Q-10)
        if ids != ["none", "observed"] or any(v != 0 for v in values):
            errs.append(f"{tag} a note is exactly none/observed at 0")
        if c.charge_group is not None:
            errs.append(f"{tag} charge_group is for fault checks only")
    return errs


def _v10_point_text(c: PlanCheckV6) -> List[str]:
    texts = [("description_he", c.description_he)]
    texts += [(f"option {o.option_id!r} label", o.label_he) for o in c.options]
    return [f"V10: {c.check_id} {where} states a point value; the verifier is point-blind"
            for where, text in texts if _POINT_TEXT.search(text or "")]


def _v17_grid(c: PlanCheckV6, precision: Decimal) -> List[str]:
    return [f"V17: {c.check_id} option {o.option_id!r} value {o.value} off the {precision} grid"
            for o in c.options if not _on_grid(o.value, precision)]


# ── V13 ──────────────────────────────────────────────────────────────────────

def _v13_credit_sum(terminals, checks) -> List[str]:
    errs: List[str] = []
    for t in terminals:
        credit_max = sum((c.options[0].value for c in checks
                          if c.priced_terminal_id == t.terminal_id and c.role == "credit"
                          and c.options), Decimal("0"))
        if credit_max != t.points_possible:
            errs.append(f"V13: {t.terminal_id} Σ credit max {credit_max} != "
                        f"points_possible {t.points_possible}")
    return errs


# ── V14 ──────────────────────────────────────────────────────────────────────

def _v14_marker_disposition(checks, ctx: PlanContext) -> List[str]:
    errs: List[str] = []
    markers = {m.marker_id: m for m in ctx.markers}
    disp_count: Dict[str, int] = {}
    disp: Dict[str, MarkerDisposition] = {}
    for d in ctx.dispositions:
        disp_count[d.marker_id] = disp_count.get(d.marker_id, 0) + 1
        disp[d.marker_id] = d
        if d.marker_id not in markers:
            errs.append(f"V14: disposition for unknown marker {d.marker_id!r}")
    for mid in markers:
        if disp_count.get(mid, 0) != 1:
            errs.append(f"V14: marker {mid!r} has {disp_count.get(mid, 0)} dispositions (need exactly 1)")

    as_option: Dict[str, List[Tuple[PlanCheckV6, Decimal]]] = {}
    for c in checks:
        for o in c.options:
            if o.marker_id is not None:
                as_option.setdefault(o.marker_id, []).append((c, o.value))
                if o.marker_id not in markers:
                    errs.append(f"V14: {c.check_id} option {o.option_id!r} cites unknown "
                                f"marker {o.marker_id!r}")

    merged_into: Dict[str, List[str]] = {}
    for mid, d in disp.items():
        m = markers.get(mid)
        if m is None:
            continue
        uses = as_option.get(mid, [])
        if d.disposition == "fault":
            if len(uses) != 1:
                errs.append(f"V14: marker {mid!r} disposed `fault` appears as {len(uses)} "
                            f"fault options (need exactly 1)")
            if m.polarity == "no_deduct":
                errs.append(f"V14: no_deduct marker {mid!r} can never be a fault option")
        elif d.disposition == "merged":
            if uses:
                errs.append(f"V14: merged marker {mid!r} must not be an option itself")
            target = d.merged_into_marker_id
            if not target or disp.get(target) is None or disp[target].disposition != "fault":
                errs.append(f"V14: merged marker {mid!r} must merge into a marker disposed `fault`")
            else:
                merged_into.setdefault(target, []).append(mid)
            if not (d.reason_he or "").strip():
                errs.append(f"V14: merged marker {mid!r} needs a reason_he")
        else:                                                           # not_a_deduction
            if uses:
                errs.append(f"V14: marker {mid!r} disposed not_a_deduction is a fault option")
            if not (d.reason_he or "").strip():
                errs.append(f"V14: marker {mid!r} disposed not_a_deduction needs a reason_he")

    # values: −amount, or −min over a merged set
    for mid, uses in as_option.items():
        m = markers.get(mid)
        if m is None or not uses:
            continue
        amounts = [m.amount] + [markers[x].amount for x in merged_into.get(mid, [])]
        if any(a is None for a in amounts):
            errs.append(f"V14: marker {mid!r} (or a marker merged into it) has no amount")
            continue
        want = -min(amounts)
        for c, value in uses:
            if value != want:
                errs.append(f"V14: {c.check_id} option for marker {mid!r} is {value}, "
                            f"want {want} (−amount, lenient min over a merged set)")

    # one charge group per fault check
    for c in checks:
        if c.role != "fault":
            continue
        members = [o.marker_id for o in c.options if o.marker_id]
        members += [x for mid in list(members) for x in merged_into.get(mid, [])]
        groups = {markers[x].charge_group for x in members if x in markers}
        if len(groups) > 1:
            errs.append(f"V14: {c.check_id} members span charge groups {sorted(map(str, groups))}")
        elif groups and next(iter(groups)) != c.charge_group:
            errs.append(f"V14: {c.check_id} charge_group {c.charge_group!r} != its markers' "
                        f"{next(iter(groups))!r}")
    return errs


# ── V15 ──────────────────────────────────────────────────────────────────────

def _v15_requires(checks) -> List[str]:
    errs: List[str] = []
    by_id = {c.check_id: c for c in checks}
    for c in checks:
        if c.requires is None:
            continue
        if c.role != "fault":
            errs.append(f"V15: {c.check_id} `requires` is for fault checks only")
            continue
        target = by_id.get(c.requires)
        if target is None:
            errs.append(f"V15: {c.check_id} requires unknown check {c.requires!r}")
        elif target.role != "credit":
            errs.append(f"V15: {c.check_id} requires {c.requires!r}, which is not a credit check")
        elif target.priced_terminal_id != c.priced_terminal_id:
            errs.append(f"V15: {c.check_id} requires {c.requires!r} on another terminal")
        elif target.requires is not None:
            errs.append(f"V15: {c.check_id} requires {c.requires!r}, which itself requires — no chains")
    return errs


# ── V16 ──────────────────────────────────────────────────────────────────────

def _v16_source_span(checks, ctx: PlanContext) -> List[str]:
    errs: List[str] = []
    markers = {m.marker_id: m for m in ctx.markers}
    for c in checks:
        span = normalize_span(c.source_span)
        if not span:
            errs.append(f"V16: {c.check_id} has an empty source_span")
            continue
        scope = ctx.terminal_scopes.get(c.priced_terminal_id, "")
        sources = [ctx.terminal_texts.get(c.priced_terminal_id, ""),
                   ctx.scope_question_text.get(scope, ""),
                   ctx.scope_example_solution.get(scope, "")]
        sources += [markers[o.marker_id].text_span for o in c.options
                    if o.marker_id and o.marker_id in markers]
        if not any(span in normalize_span(s) for s in sources if s):
            errs.append(f"V16: {c.check_id} source_span is not verbatim in any allowed source")
    return errs


# ── V18 / V7 ─────────────────────────────────────────────────────────────────

def _v18_placement(terminals, checks, ctx: PlanContext) -> List[str]:
    errs: List[str] = []
    tids = {t.terminal_id for t in terminals}
    markers = {m.marker_id: m for m in ctx.markers}
    merged_into: Dict[str, List[str]] = {}
    for d in ctx.dispositions:
        if d.disposition == "merged" and d.merged_into_marker_id:
            merged_into.setdefault(d.merged_into_marker_id, []).append(d.marker_id)
    for c in checks:
        if c.priced_terminal_id not in tids:
            errs.append(f"V18: {c.check_id} is priced on unknown terminal {c.priced_terminal_id!r}")
            continue
        if c.role != "fault":
            continue
        members = [o.marker_id for o in c.options if o.marker_id]
        members += [x for mid in list(members) for x in merged_into.get(mid, [])]
        anchor_scope = ctx.terminal_scopes.get(c.priced_terminal_id)
        for mid in members:
            m = markers.get(mid)
            if m is None:
                continue
            if c.priced_terminal_id not in m.candidate_anchors:
                errs.append(f"V18: {c.check_id} anchor {c.priced_terminal_id!r} is not a "
                            f"candidate of marker {mid!r}")
            if ctx.terminal_scopes.get(m.home_terminal_id) != anchor_scope:
                errs.append(f"V18: {c.check_id} is priced outside marker {mid!r}'s scope")
    return errs


def _v7_group_scope(checks, ctx: PlanContext) -> List[str]:
    scopes: Dict[str, Set[str]] = {}
    for c in checks:
        if c.charge_group is not None:
            scopes.setdefault(c.charge_group, set()).add(
                ctx.terminal_scopes.get(c.priced_terminal_id, "?"))
    return [f"V7: charge_group {g!r} spans scopes {sorted(s)}"
            for g, s in sorted(scopes.items()) if len(s) > 1]


# ── V20 ──────────────────────────────────────────────────────────────────────

def _v20_skeleton(checks, ctx: PlanContext) -> List[str]:
    errs: List[str] = []
    for tid, components in ctx.skeleton.items():
        credits = [c for c in checks if c.priced_terminal_id == tid and c.role == "credit"]
        if len(credits) != len(components):
            errs.append(f"V20: {tid} has {len(credits)} credit checks for "
                        f"{len(components)} compiled components")
            continue
        for i, (c, comp) in enumerate(zip(credits, components)):
            if normalize_span(c.source_span) != normalize_span(comp.source_span):
                errs.append(f"V20: {tid} component {i + 1} span differs from the compiled one")
            if c.options and c.options[0].value != comp.points:
                errs.append(f"V20: {tid} component {i + 1} max {c.options[0].value} != "
                            f"compiled {comp.points}")
    return errs


# ── V19 — telemetry only ─────────────────────────────────────────────────────

def v19_fault_leak_candidates(checks: Sequence[PlanCheckV6],
                              markers: Sequence[DeductionMarker]
                              ) -> List[Tuple[str, str, List[str]]]:
    """Latin identifier tokens (≥ 3 chars) that appear both in a fault's marker
    text and in the description of the credit check it requires — a possible
    breach of P-3 (the credit check should describe the behavior WITHOUT the
    fault). Listed in the plan report for a human; NEVER an error."""
    by_id = {c.check_id: c for c in checks}
    mk = {m.marker_id: m for m in markers}
    out: List[Tuple[str, str, List[str]]] = []
    for c in checks:
        if c.role != "fault" or c.requires not in by_id:
            continue
        credit_tokens = set(_LATIN_IDENT.findall(by_id[c.requires].description_he))
        fault_tokens: Set[str] = set()
        for o in c.options:
            if o.marker_id in mk:
                fault_tokens |= set(_LATIN_IDENT.findall(mk[o.marker_id].text_span))
        common = sorted(credit_tokens & fault_tokens)
        if common:
            out.append((c.check_id, c.requires, common))
    return out
