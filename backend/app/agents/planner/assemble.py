"""
grader-v6 Stage 3 — ASSEMBLE (PR_grader_v6_options.md §5.1 [3], §5.3, §5.6).

Pure. Three ways a scope becomes plan/v6 checks, all ending in the same
validator (V12–V20):

  * `map_scope`       the planner's `ScopePlanOutput` → checks. Code assigns every
                      id (§3.2) and every value (§3.3); the planner chose only
                      words, shapes and dispositions (D-LAW-2). A structural
                      mistake raises `MappingError` with messages written for the
                      ONE repair call (§5.6).
  * `fallback_scope`  the deterministic fallback (§5.6), `origin="fallback"`:
                      valid BY CONSTRUCTION.
  * compiled terminals (`levels`, `count`) and notes are built by code on both
                      paths; the planner only ever sees them read-only.

Two decisions this module makes (recorded as "decided — pending owner veto"):
  1. V10 forbids point text in descriptions and labels, and a teacher's verbatim
     span usually carries it («(1 נקודה)», «להוריד 1»). The fallback therefore
     keeps the span VERBATIM in `source_span` (V16) and uses a point-free copy of
     it for `description_he` and labels.
  2. The fallback's «one fault check per anchor» is one per (anchor,
     charge_group): V14 requires every member of a fault check to share one
     group, and markers of different groups are different faults.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from app.agents.grader import plan_values as pv
from app.agents.grader.plan_schemas import (CheckOption, DeductionMarker, MarkerDisposition,
                                            PlanCheckV6, TerminalPlanV6)
from app.agents.grader.plan_validator import _POINT_TEXT
from app.agents.grader.plan_validator_v6 import PlanContext, SkeletonComponent, validate_plan_v6
from app.agents.plan_compiler.compile import scan_deductions
from app.agents.plan_compiler.patterns_v6 import V6_PATTERNS
from app.agents.plan_compiler.stage1_v6 import V6Scope, V6Terminal

from .inputs import AMOUNT_MASK
from .schemas import PlannedCredit, ScopePlanOutput
from .stage1_input import unmask_span

FALLBACK_FAULT_DESCRIPTION = "טעות שהמחוון מפרט"      # the fault check's own line, point-free
FALLBACK_NOTE_DESCRIPTION = "הערה מהמחוון"
_VALUE_MARK = re.compile(r"\(\s*\d+(?:[.,]\d+)?\s*(?:נקודות|נקודה|נק['׳]?)?\s*\)")
_LATIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


class MappingError(ValueError):
    """The planner's output cannot be mapped. `errors` go to the repair call."""

    def __init__(self, errors: Sequence[str]):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


# ═══════════════════════════════════════════════════════════════════════════
# shared
# ═══════════════════════════════════════════════════════════════════════════

def point_free(text: str, fallback: str = "") -> str:
    """The span with its deduction phrases and point values removed — V10-safe
    words for a description or label. Never used as a source_span."""
    s = text or ""
    spans = sorted(((d.phrase_start, d.phrase_end) for d in scan_deductions(s, V6_PATTERNS)
                    if d.polarity != "value"), reverse=True)
    for a, b in spans:                               # from the end: offsets stay valid
        s = s[:a] + " " + s[b:]
    s = _VALUE_MARK.sub(" ", s)
    s = _POINT_TEXT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:-–()")
    if len(s) > 140:
        s = s[:139].rstrip() + "…"
    return s or fallback


def scope_context(scope: V6Scope, precision: Decimal,
                  dispositions: Sequence[MarkerDisposition] = ()) -> PlanContext:
    terms = scope.terminals
    return PlanContext(
        precision=precision,
        contract_terminal_points={t.terminal_id: t.points_possible for t in terms},
        terminal_scopes={t.terminal_id: scope.scope for t in terms},
        terminal_texts={t.terminal_id: t.text for t in terms},
        scope_question_text={scope.scope: scope.question_text},
        scope_example_solution={scope.scope: scope.example_solution},
        markers=list(scope.markers), dispositions=list(dispositions),
        skeleton={t.terminal_id: [SkeletonComponent(c.source_span, c.points) for c in t.components]
                  for t in terms if t.shape == "components" and t.fixed})


def _compiled_credit(t: V6Terminal, grid: Decimal) -> PlanCheckV6:
    description = point_free(t.text, fallback=t.terminal_id)
    if t.shape == "levels":
        options, shape = pv.levels_options(t.bands), "levels"
    else:
        options, shape = pv.count_options(t.points_possible, t.unit_count, grid), "count"
    return PlanCheckV6(check_id=pv.check_id(t.terminal_id, "credit", 1), role="credit", shape=shape,
                       description_he=description, source_span=t.text or description,
                       options=options, priced_terminal_id=t.terminal_id, origin="compiler")


def _note_checks(t: V6Terminal) -> List[PlanCheckV6]:
    out = []
    for n, note in enumerate(t.notes, start=1):
        label = point_free(note.label_he or note.source_span, fallback=FALLBACK_NOTE_DESCRIPTION)
        out.append(PlanCheckV6(check_id=pv.check_id(t.terminal_id, "note", n), role="note",
                               shape="note", description_he=label, source_span=note.source_span,
                               options=pv.note_options(label), priced_terminal_id=t.terminal_id,
                               evidence_required=False, origin="compiler"))
    return out


def _credit_check(tid: str, n: int, value: Decimal, credit: PlannedCredit, grid: Decimal,
                  origin: str) -> Tuple[PlanCheckV6, List[str]]:
    partials = [(p.label_he, p.fraction) for p in credit.partials]
    if partials:
        options, collapsed = pv.credit_ladder_options(value, credit.full_label_he, partials,
                                                      credit.absent_label_he, grid)
    else:
        options, collapsed = pv.credit_binary_options(value, credit.full_label_he,
                                                      credit.absent_label_he), []
    shape = "ladder" if len(options) > 2 else "binary"
    return PlanCheckV6(check_id=pv.check_id(tid, "credit", n), role="credit", shape=shape,
                       description_he=credit.description_he, source_span=credit.source_span,
                       options=options, equivalence_note_he=credit.equivalence_note_he,
                       priced_terminal_id=tid, origin=origin), collapsed


def _ordered(scope: V6Scope, checks: Sequence[PlanCheckV6]) -> List[PlanCheckV6]:
    """Plan order (§3.1): rubric order; within a terminal credit, fault, note."""
    rank = {"credit": 0, "fault": 1, "note": 2}
    pos = {t.terminal_id: i for i, t in enumerate(scope.terminals)}
    return sorted(checks, key=lambda c: (pos[c.priced_terminal_id], rank[c.role],
                                         int(c.check_id.rsplit(".", 1)[1][1:])))


# ═══════════════════════════════════════════════════════════════════════════
# the planner's output → checks (§5.3)
# ═══════════════════════════════════════════════════════════════════════════

def _wording_errors(out: ScopePlanOutput) -> List[str]:
    """The amount mask is OUR marker in the planner's input; it must never come
    back in words a teacher reads (descriptions, labels, notes)."""
    texts = []
    for pt in out.terminals:
        texts += [(pt.terminal_id, n) for n in pt.interpretation_notes_he]
        for c in pt.credits:
            texts += [(pt.terminal_id, c.description_he), (pt.terminal_id, c.full_label_he),
                      (pt.terminal_id, c.absent_label_he), (pt.terminal_id, c.equivalence_note_he or "")]
            texts += [(pt.terminal_id, x.label_he) for x in c.partials]
    for f in out.faults:
        texts += [(f.anchor_terminal_id, f.description_he)] + [(f.anchor_terminal_id, o.label_he)
                                                               for o in f.options]
    return [f"{tid}: remove {AMOUNT_MASK} from the wording «{t[:60]}» — describe the condition, "
            f"never the amount" for tid, t in texts if AMOUNT_MASK in (t or "")]


def map_scope(scope: V6Scope, out: ScopePlanOutput, grid: Decimal
              ) -> Tuple[List[TerminalPlanV6], List[PlanCheckV6], List[MarkerDisposition], List[str]]:
    """(terminals, checks, dispositions, telemetry). Raises MappingError."""
    errors: List[str] = _wording_errors(out)
    telemetry: List[str] = []
    by_tid = {t.terminal_id: t for t in scope.terminals}
    planned = {}
    for pt in out.terminals:
        if pt.terminal_id not in by_tid:
            errors.append(f"unknown terminal_id {pt.terminal_id!r}")
        elif pt.terminal_id in planned:
            errors.append(f"terminal {pt.terminal_id!r} planned twice")
        elif by_tid[pt.terminal_id].shape == "components":
            planned[pt.terminal_id] = pt           # compiled terminals are read-only: ignored

    notes: Dict[str, List[str]] = {t.terminal_id: [] for t in scope.terminals}
    checks: List[PlanCheckV6] = []
    credit_ref: Dict[Tuple[str, str], str] = {}     # (terminal, component_ref) → credit check id
    for t in scope.terminals:
        if t.shape != "components":
            checks.append(_compiled_credit(t, grid))
            continue
        pt = planned.get(t.terminal_id)
        if pt is None:
            errors.append(f"terminal {t.terminal_id!r} was not planned")
            continue
        if len(pt.interpretation_notes_he) > 3:
            errors.append(f"{t.terminal_id}: at most 3 interpretation notes, got "
                          f"{len(pt.interpretation_notes_he)}")
        notes[t.terminal_id] = list(pt.interpretation_notes_he[:3])
        refs = [c.component_ref for c in pt.credits]
        comp_ids = [c.component_id for c in t.components]
        if t.fixed or pt.decomposition == "as_compiled":
            if pt.decomposition != "as_compiled":
                errors.append(f"{t.terminal_id}: enumerated components are fixed input — "
                              f"decomposition must be 'as_compiled', got {pt.decomposition!r}")
                continue
            if refs != comp_ids:
                errors.append(f"{t.terminal_id}: credits must be exactly the components "
                              f"{comp_ids}, in order; got {refs}")
                continue
            values = [c.points for c in t.components]
        else:
            k = len(pt.credits)
            want = {"binary": (1, 1), "ladder": (1, 1), "split": (2, 6)}[pt.decomposition]
            if not want[0] <= k <= want[1]:
                errors.append(f"{t.terminal_id}: {pt.decomposition!r} takes {want[0]}–{want[1]} "
                              f"credits, got {k}")
                continue
            if pt.decomposition == "split":
                expected = [f"new:{i}" for i in range(1, k + 1)]
                if refs != expected:
                    errors.append(f"{t.terminal_id}: split credits are {expected}, got {refs}")
                    continue
                values = pv.even_split(t.points_possible, k, grid)
            else:
                if refs != comp_ids:
                    errors.append(f"{t.terminal_id}: the monolith's credit is {comp_ids[0]!r}, got {refs}")
                    continue
                n_partials = len(pt.credits[0].partials)
                if pt.decomposition == "binary" and n_partials:
                    errors.append(f"{t.terminal_id}: 'binary' takes no partials, got {n_partials}")
                    continue
                if pt.decomposition == "ladder" and not 1 <= n_partials <= 2:
                    errors.append(f"{t.terminal_id}: 'ladder' takes 1–2 partials, got {n_partials}")
                    continue
                values = [t.points_possible]
        sources = (t.text, scope.question_text, scope.example_solution)
        for n, (credit, value) in enumerate(zip(pt.credits, values), start=1):
            if AMOUNT_MASK in credit.source_span:           # the exact inverse of our input mask
                verbatim = unmask_span(credit.source_span, sources)
                if verbatim is None:
                    errors.append(f"{t.terminal_id}: source_span «{credit.source_span[:60]}» quotes "
                                  f"the masked text; quote the teacher's words without {AMOUNT_MASK}")
                    continue
                credit = credit.model_copy(update={"source_span": verbatim})
            if len(credit.partials) > 2:
                errors.append(f"{t.terminal_id}: credit {credit.component_ref!r} has "
                              f"{len(credit.partials)} partials (at most 2)")
                continue
            check, collapsed = _credit_check(t.terminal_id, n, value, credit, grid, "planner")
            checks.append(check)
            credit_ref[(t.terminal_id, credit.component_ref)] = check.check_id
            telemetry += [f"partial_collapsed {check.check_id}: {lab}" for lab in collapsed]

    markers = {m.marker_id: m for m in scope.markers}
    disp = {d.marker_id: d for d in out.dispositions}
    merged_into: Dict[str, List[str]] = {}
    for d in out.dispositions:
        if d.disposition == "merged" and d.merged_into_marker_id:
            merged_into.setdefault(d.merged_into_marker_id, []).append(d.marker_id)

    fault_n: Dict[str, int] = {}
    for f in out.faults:
        anchor = f.anchor_terminal_id
        if anchor not in by_tid:
            errors.append(f"fault anchored on unknown terminal {anchor!r}")
            continue
        if not 1 <= len(f.options) <= 7:
            errors.append(f"fault on {anchor}: 1–7 options, got {len(f.options)}")
            continue
        unknown = [o.marker_id for o in f.options if o.marker_id not in markers]
        if unknown:
            errors.append(f"fault on {anchor}: unknown marker ids {unknown}")
            continue
        requires = None
        if f.requires_component_ref is not None:
            requires = credit_ref.get((anchor, f.requires_component_ref))
            if requires is None:
                errors.append(f"fault on {anchor}: requires_component_ref "
                              f"{f.requires_component_ref!r} is not a credit component of {anchor}")
                continue
        specs = []
        for o in f.options:
            amounts = [markers[o.marker_id].amount] + [markers[m].amount
                                                       for m in merged_into.get(o.marker_id, [])]
            specs.append((o.marker_id, amounts if len(amounts) > 1 else amounts[0], o.label_he))
        members = [markers[o.marker_id] for o in f.options]
        fault_n[anchor] = fault_n.get(anchor, 0) + 1
        checks.append(PlanCheckV6(
            check_id=pv.check_id(anchor, "fault", fault_n[anchor]), role="fault", shape="fault",
            description_he=f.description_he, source_span=members[0].text_span,
            options=pv.fault_options(specs), requires=requires,
            charge_group=members[0].charge_group, priced_terminal_id=anchor, origin="planner"))
        for o in f.options:                          # §5.3: a merge's reason is a note, by code
            for m in merged_into.get(o.marker_id, []):
                reason = disp[m].reason_he
                if reason:
                    notes[anchor].append(reason)

    if errors:
        raise MappingError(errors)
    for t in scope.terminals:
        checks += _note_checks(t)
    terminals = [TerminalPlanV6(terminal_id=t.terminal_id, points_possible=t.points_possible,
                                interpretation_notes_he=notes[t.terminal_id]) for t in scope.terminals]
    return terminals, _ordered(scope, checks), list(out.dispositions), telemetry


# ═══════════════════════════════════════════════════════════════════════════
# the deterministic fallback (§5.6)
# ═══════════════════════════════════════════════════════════════════════════

def _tokens(s: str) -> set:
    return set(_LATIN.findall(s or ""))


def _fallback_anchor(m: DeductionMarker, by_tid: Dict[str, V6Terminal]) -> str:
    """The candidate sharing the most identifier tokens with the marker text;
    ties to the first candidate (§5.6)."""
    toks = _tokens(m.text_span)
    best, best_n = m.candidate_anchors[0], -1
    for c in m.candidate_anchors:
        t = by_tid.get(c)
        n = len(toks & _tokens(t.text if t else ""))
        if n > best_n:
            best, best_n = c, n
    return best


def fallback_scope(scope: V6Scope, grid: Decimal
                   ) -> Tuple[List[TerminalPlanV6], List[PlanCheckV6], List[MarkerDisposition]]:
    by_tid = {t.terminal_id: t for t in scope.terminals}
    checks: List[PlanCheckV6] = []
    for t in scope.terminals:
        if t.shape != "components":
            checks.append(_compiled_credit(t, grid))
            continue
        for n, comp in enumerate(t.components, start=1):
            desc = point_free(comp.source_span, fallback=t.terminal_id)
            checks.append(PlanCheckV6(
                check_id=pv.check_id(t.terminal_id, "credit", n), role="credit", shape="binary",
                description_he=desc, source_span=comp.source_span,
                options=pv.credit_binary_options(comp.points, pv.FALLBACK_FULL_LABEL,
                                                 pv.FALLBACK_ABSENT_LABEL),
                priced_terminal_id=t.terminal_id, origin="fallback"))

    groups: Dict[Tuple[str, Optional[str]], List[DeductionMarker]] = {}
    for m in scope.markers:
        groups.setdefault((_fallback_anchor(m, by_tid), m.charge_group), []).append(m)
    fault_n: Dict[str, int] = {}
    for (anchor, group), members in groups.items():
        anchor_credits = [c for c in checks if c.priced_terminal_id == anchor and c.role == "credit"
                          and c.shape in ("binary", "ladder")]
        toks = set().union(*(_tokens(m.text_span) for m in members))
        best, best_key = None, (0, Decimal("-1"))
        for c in anchor_credits:
            key = (len(toks & _tokens(c.source_span)), c.options[0].value)
            if key[0] >= 1 and key > best_key:
                best, best_key = c.check_id, key
        fault_n[anchor] = fault_n.get(anchor, 0) + 1
        specs = [(m.marker_id, m.amount, point_free(m.text_span, fallback=FALLBACK_FAULT_DESCRIPTION))
                 for m in members]
        checks.append(PlanCheckV6(
            check_id=pv.check_id(anchor, "fault", fault_n[anchor]), role="fault", shape="fault",
            description_he=FALLBACK_FAULT_DESCRIPTION, source_span=members[0].text_span,
            options=pv.fault_options(specs), requires=best, charge_group=group,
            priced_terminal_id=anchor, origin="fallback"))

    for t in scope.terminals:
        checks += _note_checks(t)
    dispositions = [MarkerDisposition(marker_id=m.marker_id, disposition="fault") for m in scope.markers]
    terminals = [TerminalPlanV6(terminal_id=t.terminal_id, points_possible=t.points_possible)
                 for t in scope.terminals]
    return terminals, _ordered(scope, checks), dispositions


def validate_scope(scope: V6Scope, terminals, checks, dispositions, precision: Decimal) -> List[str]:
    return validate_plan_v6(terminals, checks, scope_context(scope, precision, dispositions))
