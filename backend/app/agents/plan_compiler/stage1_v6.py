"""
grader-v6 Stage 1 (PR_grader_v6_options.md §5.1): the pure compiler, re-read for
OPTIONS. Zero I/O, zero spend, byte-identical across runs.

It is an adapter over PLAN COMPILER v2 (`compile_contract`), not a second
compiler: the algebra — components and their points (C4/C5), counted units
(C3), band ladders (C8-lite), charge-once groups (C6), the OD-20 value and OD-21
fold rules (Q-11: they run first, and what they consume never becomes a
marker) — is v2's, unchanged. What v6 changes is what a deduction BECOMES:

  * C1 [changed]   a detected deduction is a `DeductionMarker`, never a tariff
                   slot, found with the AM-G1 phrase set (`patterns_v6`):
                     - written in a criterion   → candidate_anchors = [itself];
                     - a parent-level phrase     → its sibling sub-criteria (S-4,
                       superseding OD-10(a)); the OD-10 sibling group stays;
                     - a scope-level phrase      → the scope's terminals.
                   The amount is copied verbatim and never shown to the planner.
  * C2 [changed]   a no-deduction clause is a `note` (Q-10), not a note slot.
  * C4             two or more enumerated components are FIXED planner input;
                   a single component is a monolith the planner decomposes.
  * C7 [changed]   no threshold: a scope goes to the planner unless every one
                   of its terminals is fully compiled (`levels` / `count`).
  * C8             removed (AM-G1): standalone lines are Track C.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Tuple

from app.agents.grader.plan_schemas import DeductionMarker

from .compile import COMPILER_VERSION, _band_ladder, _scope_label, _split_code_tail, compile_contract
from .patterns_v6 import V6_PATTERNS
from .skeleton import Flag, TerminalSkeleton
from .stage0 import contract_scopes, terminals_of

STAGE1_V6_VERSION = f"{COMPILER_VERSION}+stage1-v6.0"
_NEVER_ROUTE = Decimal("Infinity")          # C7 has no threshold in v6; v2's routing is unused

Shape = Literal["components", "levels", "count"]


@dataclass(frozen=True)
class V6Component:
    component_id: str                     # the v2 slot id, e.g. "q1.א.c0.k1"
    source_span: str                      # verbatim slice of the teacher's text
    points: Decimal


@dataclass(frozen=True)
class V6Note:
    note_id: str
    source_span: str
    label_he: str                         # the clause, whitespace-normalised


@dataclass(frozen=True)
class V6Terminal:
    terminal_id: str
    scope: str
    points_possible: Decimal
    text: str
    shape: Shape
    components: Tuple[V6Component, ...] = ()       # shape "components"
    fixed: bool = False                             # C4: enumerated → fixed; one → monolith
    bands: Tuple[Tuple[str, Decimal], ...] = ()     # shape "levels" (Q-7: C8-lite band ladder)
    unit_count: Optional[int] = None                # shape "count"
    notes: Tuple[V6Note, ...] = ()
    flags: Tuple[Flag, ...] = ()

    @property
    def fully_compiled(self) -> bool:
        return self.shape in ("levels", "count")


@dataclass(frozen=True)
class V6Scope:
    scope: str
    terminals: Tuple[V6Terminal, ...]
    markers: Tuple[DeductionMarker, ...]

    @property
    def needs_planner(self) -> bool:
        """C7: every scope goes to the planner unless all its terminals are
        fully compiled (a scope of levels/count/notes needs no language)."""
        return not all(t.fully_compiled for t in self.terminals)


@dataclass(frozen=True)
class Stage1V6:
    exam_id: str
    rubric_contract_sha256: str
    precision: Decimal
    version: str
    scopes: Tuple[V6Scope, ...]
    flags: Tuple[Flag, ...] = ()

    def scope(self, label: str) -> V6Scope:
        for s in self.scopes:
            if s.scope == label:
                return s
        raise KeyError(label)


def _anchor_map(contract) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """(criterion id → its sub-criterion ids, scope label → its terminal ids),
    walked exactly as `compile_contract` walks the contract."""
    kids: Dict[str, List[str]] = {}
    scope_terms: Dict[str, List[str]] = {}
    for key, question, sub in contract_scopes(contract):
        node = sub or question
        scope_terms[_scope_label(key)] = [t for t, _ in terminals_of(node)]
        for criterion in getattr(node, "criteria", []) or []:
            subs = getattr(criterion, "sub_criteria", None) or []
            if subs:
                kids[criterion.criterion_id] = [s.sub_criterion_id for s in subs]
    return kids, scope_terms


def _candidates(slot, home: str, scope: str, kids: Dict[str, List[str]],
                scope_terms: Dict[str, List[str]]) -> List[str]:
    if "parent_level" in slot.flags:
        # compile_contract names a parent-level group f"{scope}:{criterion_id}:d{i}"
        criterion_id = (slot.charge_group or "").split(":")[1]
        return list(kids[criterion_id])
    if "scope_level" in slot.flags:
        return list(scope_terms[scope])
    return [home]


def _terminal(t: TerminalSkeleton) -> V6Terminal:
    notes = tuple(V6Note(s.slot_id, s.source_span, s.summary) for s in t.note_slots)
    if t.case == "band_ladder":
        prose, _ = _split_code_tail(t.text or "")
        bands = tuple((label, Decimal(str(v))) for label, v in _band_ladder(prose, t.points_possible))
        return V6Terminal(t.terminal_id, t.scope, t.points_possible, t.text, "levels",
                          bands=bands, notes=notes, flags=t.flags)
    if t.case == "counted":
        (slot,) = [s for s in t.slots if s.kind == "counted"]
        return V6Terminal(t.terminal_id, t.scope, t.points_possible, t.text, "count",
                          unit_count=slot.unit_count, notes=notes, flags=t.flags)
    comps = tuple(V6Component(s.slot_id, s.source_span, s.points)
                  for s in t.slots if s.kind == "required")
    return V6Terminal(t.terminal_id, t.scope, t.points_possible, t.text, "components",
                      components=comps, fixed=len(comps) >= 2, notes=notes, flags=t.flags)


def compile_stage1_v6(contract, *, exam_id: str, rubric_contract_sha256: str) -> Stage1V6:
    skeleton = compile_contract(contract, exam_id=exam_id,
                                rubric_contract_sha256=rubric_contract_sha256,
                                route_min_points=_NEVER_ROUTE, patterns=V6_PATTERNS)
    kids, scope_terms = _anchor_map(contract)
    by_scope: Dict[str, List[TerminalSkeleton]] = {}
    for t in skeleton.terminals:
        by_scope.setdefault(t.scope, []).append(t)

    scopes: List[V6Scope] = []
    for label, terms in by_scope.items():
        markers: List[DeductionMarker] = []
        for t in terms:
            for n, slot in enumerate(t.tariff_slots, start=1):
                markers.append(DeductionMarker(
                    marker_id=f"{t.terminal_id}.m{n}", home_terminal_id=t.terminal_id,
                    amount=slot.tariff_amount, polarity="deduct", text_span=slot.source_span,
                    charge_group=slot.charge_group,
                    candidate_anchors=_candidates(slot, t.terminal_id, label, kids, scope_terms)))
        scopes.append(V6Scope(label, tuple(_terminal(t) for t in terms), tuple(markers)))
    return Stage1V6(exam_id=exam_id, rubric_contract_sha256=rubric_contract_sha256,
                    precision=skeleton.precision, version=STAGE1_V6_VERSION,
                    scopes=tuple(scopes), flags=skeleton.flags)
