"""
PLAN COMPILER v2 — the Stage-1 output types (PR_plan_compiler_v2.md §3, "Output").

A `PlanSkeleton` is the ALGEBRA of a GradingPlan with no wording: per terminal,
ordered slots carrying kind, points / tariff_amount / unit_count, charge_group,
and the verbatim `source_span` each slot was compiled from. Stage 2 (the
segmenter) adds `description_he` / `rubric_quote` / `equivalence_note`; Stage 3
assembles the frozen `GradingPlan`.

Design law (PR §1): the model never emits a number, a kind, an amount, an
anchor, or a count. Everything here is a pure function of contract text, and
two compilations of one contract are byte-identical.

Everything is frozen and hashable so a skeleton can be compared, diffed and
pinned in a test without a serializer in the way.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Tuple

SlotKind = str          # "required" | "tariff" | "note_only" | "counted"


class CompilerBug(AssertionError):
    """A by-construction invariant (V1: Σ earn-side points == points_possible)
    failed inside the compiler. Never a rubric problem — a compiler defect."""


@dataclass(frozen=True)
class Flag:
    """One thing the owner should see. `code` is a closed vocabulary (see
    `compile.FLAG_CODES`); `detail` is free text; `terminal_id` anchors it."""
    code: str
    terminal_id: str
    detail: str = ""


@dataclass(frozen=True)
class Slot:
    slot_id: str                         # "<terminal>.k1" | ".t1" | ".n1"
    kind: SlotKind
    points: Decimal = Decimal("0")       # required/counted only
    tariff_amount: Optional[Decimal] = None
    unit_count: Optional[int] = None     # counted only
    partial_fraction: Decimal = Decimal("0.5")
    charge_group: Optional[str] = None   # tariff only
    source_span: str = ""                # VERBATIM slice of the terminal text (rubric_quote, V9)
    summary: str = ""                    # the same, whitespace-normalised and marker-free (V10-safe)
    anchor_span: str = ""                # tariff only: the requirement whose absence fires it
    # per-slot notes the segmenter/owner may want; algebra-free
    flags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TerminalSkeleton:
    terminal_id: str
    scope: str                           # "q1.א" | "q6"
    points_possible: Decimal
    text: str                            # the terminal's own criterion text (input)
    slots: Tuple[Slot, ...]
    routed: bool = False                 # C7: monolith → Stage 2b
    case: str = "single"                 # which C4/C5 path produced the earn side
    flags: Tuple[Flag, ...] = ()

    @property
    def earn_slots(self) -> Tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind in ("required", "counted"))

    @property
    def tariff_slots(self) -> Tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind == "tariff")

    @property
    def note_slots(self) -> Tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.kind == "note_only")


@dataclass(frozen=True)
class PlanSkeleton:
    exam_id: str
    rubric_contract_sha256: str
    precision: Decimal
    compiler_version: str
    terminals: Tuple[TerminalSkeleton, ...]
    flags: Tuple[Flag, ...] = field(default_factory=tuple)   # scope-level flags

    def terminal(self, terminal_id: str) -> TerminalSkeleton:
        for t in self.terminals:
            if t.terminal_id == terminal_id:
                return t
        raise KeyError(terminal_id)

    @property
    def all_flags(self) -> Tuple[Flag, ...]:
        out = list(self.flags)
        for t in self.terminals:
            out.extend(t.flags)
        return tuple(out)
