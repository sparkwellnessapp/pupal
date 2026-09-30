"""The planner's per-scope input (PR_grader_v6_options.md §5.2). Pure data, frozen.

What the planner sees for ONE scope, and nothing else:

  scope      question text · example solution (verbatim) · the scope's compiled
             `note` checks, read-only (Q-10)
  terminal   terminal_id · points_possible (context only) · the teacher's text ·
             the compiler skeleton (components, each `fixed` or `monolith`) or a
             compiled shape (`levels` / `count`), read-only
  marker     marker_id · text_span · polarity · home_terminal_id · candidate_anchors

IDS (AM-G17): every id here is a call-scoped ASCII alias (t1, k1, m1; split refs n1…n6),
never a real id: `stage1_input.scope_planner_input` is the one place real ids become
aliases, and `ScopePlannerInput` refuses anything else.

NEVER INPUT (§5.2): student work, ground truth, other scopes — and NO AMOUNT. There
is no field for any of them, so a caller cannot pass one by accident; the test
`test_planner_payload_has_no_amounts_and_no_student_work` walks these types to keep
it so. Nothing here names a subject (§3.3): the pack reaches the planner through the
SYSTEM prompt, never through this input.

AMOUNTS. A marker's amount is copied by code (§3.3) and never shown to the planner
(D-LAW-2): the planner phrases conditions, and a label that carried an amount would
reach the verifier, whose payload holds no value (§6.1). But the teacher's own text
states the amount («יורדו 2 נק'»), so it must be MASKED where it enters this input:
`marker_input` and `mask_marker_amounts` replace the amount inside each marker's span
with `AMOUNT_MASK`. They are the one way Stage-1 text becomes planner text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Literal, Optional, Tuple

from app.agents.grader.payload_aliases import ALIAS_PATTERN
from app.agents.grader.plan_schemas import DeductionMarker

__all__ = ["AMOUNT_MASK", "SPLIT_REFS", "SkeletonComponent", "CompiledShape", "TerminalInput",
           "NoteInput", "MarkerInput", "ScopePlannerInput", "mask_amount",
           "mask_marker_amounts", "marker_input"]

AMOUNT_MASK = "[סכום]"
SPLIT_REFS: Tuple[str, ...] = tuple(f"n{i}" for i in range(1, 7))   # §5.3: a split has 2..6 credits (AM-G17: aliases)

ComponentStatus = Literal["fixed", "monolith"]
CompiledShapeKind = Literal["levels", "count"]
Polarity = Literal["deduct", "no_deduct"]


class PlannerInputError(ValueError):
    """An input that would put an id outside the closed world in front of the model."""


@dataclass(frozen=True)
class SkeletonComponent:
    """One compiler component (C4). `fixed`: enumerated by her text — phrased, never
    split, merged or reordered (V20). `monolith`: one undivided requirement — the
    planner chooses binary, ladder or split (C7)."""
    component_id: str
    source_span: str
    status: ComponentStatus


@dataclass(frozen=True)
class CompiledShape:
    """A terminal the compiler built alone (`levels`, `count`): shown, never planned."""
    shape: CompiledShapeKind
    source_span: str


@dataclass(frozen=True)
class TerminalInput:
    terminal_id: str
    points_possible: Decimal              # context only — never a value the planner assigns
    teacher_text: str                     # verbatim, marker amounts masked (mask_marker_amounts)
    components: Tuple[SkeletonComponent, ...] = ()
    compiled: Optional[CompiledShape] = None

    def __post_init__(self) -> None:
        if bool(self.components) == (self.compiled is not None):
            raise PlannerInputError(
                f"{self.terminal_id}: exactly one of components / compiled is required")
        if self.components:
            statuses = [c.status for c in self.components]
            if "monolith" in statuses and statuses != ["monolith"]:
                raise PlannerInputError(
                    f"{self.terminal_id}: a monolith is the terminal's only component")

    @property
    def planned(self) -> bool:
        return self.compiled is None

    @property
    def is_monolith(self) -> bool:
        return len(self.components) == 1 and self.components[0].status == "monolith"

    @property
    def component_refs(self) -> Tuple[str, ...]:
        """Every `component_ref` a credit or a `requires` on this terminal may name."""
        ids = tuple(c.component_id for c in self.components)
        return ids + SPLIT_REFS if self.is_monolith else ids


@dataclass(frozen=True)
class NoteInput:
    """A compiled `note` check (Q-10) — «לא להוריד, לכתוב הערה». Read-only."""
    terminal_id: str
    text_span: str


@dataclass(frozen=True)
class MarkerInput:
    """A Stage-1 deduction marker as the planner sees it: no amount field, and the
    amount masked inside `text_span` (`marker_input`)."""
    marker_id: str
    text_span: str
    polarity: Polarity
    home_terminal_id: str
    candidate_anchors: Tuple[str, ...]


@dataclass(frozen=True)
class ScopePlannerInput:
    scope_id: str
    question_text: str
    example_solution: Optional[str]
    terminals: Tuple[TerminalInput, ...]
    notes: Tuple[NoteInput, ...] = ()
    markers: Tuple[MarkerInput, ...] = ()

    def __post_init__(self) -> None:
        if not self.terminals:
            raise PlannerInputError(f"scope {self.scope_id}: no terminals")
        # [AM-G17] the model reads aliases only: a real id here is refused, never rendered
        ids = ([t.terminal_id for t in self.terminals]
               + [c.component_id for t in self.terminals for c in t.components]
               + [n.terminal_id for n in self.notes]
               + [x for m in self.markers for x in (m.marker_id, m.home_terminal_id,
                                                    *m.candidate_anchors)])
        not_aliases = sorted({i for i in ids if not ALIAS_PATTERN.fullmatch(i)})
        if not_aliases:
            raise PlannerInputError(f"scope {self.scope_id}: ids that are not AM-G17 aliases "
                                    f"{not_aliases}")
        tids = [t.terminal_id for t in self.terminals]
        _unique(tids, f"scope {self.scope_id}: terminal ids")
        _unique([c.component_id for t in self.terminals for c in t.components],
                f"scope {self.scope_id}: component ids")
        _unique([m.marker_id for m in self.markers], f"scope {self.scope_id}: marker ids")
        in_scope = set(tids)
        for n in self.notes:
            if n.terminal_id not in in_scope:
                raise PlannerInputError(f"note on {n.terminal_id!r}: not a terminal of this scope")
        for m in self.markers:
            # V18's precondition: every candidate anchor is a terminal of THIS scope.
            if not m.candidate_anchors:
                raise PlannerInputError(f"marker {m.marker_id}: no candidate anchors")
            _unique(list(m.candidate_anchors), f"marker {m.marker_id}: candidate anchors")
            outside = [a for a in m.candidate_anchors if a not in in_scope]
            if outside:
                raise PlannerInputError(
                    f"marker {m.marker_id}: candidate anchors outside the scope {outside}")

    @property
    def planned_terminals(self) -> Tuple[TerminalInput, ...]:
        return tuple(t for t in self.terminals if t.planned)

    @property
    def compiled_terminals(self) -> Tuple[TerminalInput, ...]:
        return tuple(t for t in self.terminals if not t.planned)

    def terminal(self, terminal_id: str) -> Optional[TerminalInput]:
        for t in self.terminals:
            if t.terminal_id == terminal_id:
                return t
        return None


def _unique(values: list, what: str) -> None:
    seen, dup = set(), set()
    for v in values:
        (dup if v in seen else seen).add(v)
    if dup:
        raise PlannerInputError(f"{what} repeat: {sorted(dup)}")


# ═══════════════════════════════════════════════════════════════════════════
# masking — the one way Stage-1 text becomes planner text
# ═══════════════════════════════════════════════════════════════════════════

# A figure, with a minus sign only when attached to it («−2», «-0.5», «2», «.5», «½»).
# Digit boundaries on both sides, so «12» never yields a «2».
_FIGURE = re.compile(r"(?<![0-9.,])[-−–]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?![0-9])|½")


def _figure_value(token: str) -> Optional[Decimal]:
    if token == "½":
        return Decimal("0.5")
    try:
        return abs(Decimal(token.lstrip("-−–").replace(",", ".")))
    except InvalidOperation:        # pragma: no cover - the pattern admits only numerals
        return None


def mask_amount(text: str, amount: Optional[Decimal]) -> str:
    """`text` with every figure whose magnitude equals `amount` replaced by AMOUNT_MASK.
    `None` (a marker with no stated amount) masks nothing. Worded amounts («שתי
    נקודות») are NOT masked here: they are Stage 1's vocabulary (AM-G1) — see the
    Phase-2 report."""
    if amount is None:
        return text
    target = abs(Decimal(amount))
    return _FIGURE.sub(lambda m: AMOUNT_MASK if _figure_value(m.group(0)) == target
                       else m.group(0), text)


def mask_marker_amounts(text: str, markers: Iterable[DeductionMarker]) -> str:
    """`text` with each marker's amount masked inside every occurrence of that marker's
    span — and nowhere else, so her points («(4 נק')») and the solution's figures stay.
    Longest span first, so a span nested inside another is masked once."""
    for m in sorted(markers, key=lambda d: len(d.text_span), reverse=True):
        if m.amount is not None and m.text_span and m.text_span in text:
            text = text.replace(m.text_span, mask_amount(m.text_span, m.amount))
    return text


def marker_input(m: DeductionMarker) -> MarkerInput:
    """A Stage-1 marker, projected onto what the planner may see."""
    return MarkerInput(marker_id=m.marker_id,
                       text_span=mask_amount(m.text_span, m.amount),
                       polarity=m.polarity,
                       home_terminal_id=m.home_terminal_id,
                       candidate_anchors=tuple(m.candidate_anchors))
