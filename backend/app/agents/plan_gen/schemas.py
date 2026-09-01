"""
What the generator is allowed to emit (plan generation, Phase 0).

RULING 1 (2026-09-01): **the generator may only produce `source="generated"`.**
That is enforced STRUCTURALLY here — `GeneratedCheck` has no `source` field at
all, so the model cannot label its own output as a ruling even if it tries. Only
`plan_compiler` sets `ruling`, when merging a layer-1 entry.

Without that, V9 is voluntary: any check the model could not ground it would
simply relabel, and the grounding rule would quietly stop binding. With it, V9
is inescapable.

`reject_self_labelled` covers the other door — a draft assembled from raw JSON
rather than from the structured-output type.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class GeneratedCheck(BaseModel):
    """One proposed check. Deliberately NOT a `PlanCheck`: no `source`, and no
    `check_id` — ids are minted deterministically by the assembler so the model
    cannot collide them or encode meaning in them.

    FIELD ORDER IS LOAD-BEARING, the same lever as the verifier's: pydantic
    definition order becomes JSON-schema property order becomes decode order.
    `rubric_quote` is decoded FIRST, so the span the check derives from is
    committed before the requirement is phrased and before any number is
    chosen. Cite, then claim.
    """

    rubric_quote: str = Field(
        description="Verbatim span from THIS scope's text that this check "
                    "derives from. Copy exactly, including any typo. Elide the "
                    "middle of a long span with … but never paraphrase.")
    description_he: str = Field(
        description="The requirement in Hebrew, phrased so that 'met' means "
                    "satisfied. Never state points.")
    kind: Literal["required", "tariff", "note_only"]
    points: Decimal = Field(
        default=Decimal("0"),
        description="required: the points this check earns. tariff/note_only: 0.")
    tariff_amount: Optional[Decimal] = Field(
        default=None, description="tariff only: the deduction the rubric names.")
    partial_fraction: Decimal = Field(
        default=Decimal("0.5"),
        description="required only: fraction earned on partially_met.")
    equivalence_note: Optional[str] = Field(
        default=None,
        description="Acceptable alternative forms, when the scope's text or "
                    "example solution licenses them.")
    charge_group: Optional[str] = Field(
        default=None,
        description="tariff only: a name shared by tariffs the rubric says to "
                    "charge only once within this scope.")


class GeneratedTerminal(BaseModel):
    """The decomposition of ONE terminal. `terminal_id` and `points_possible`
    are echoed back so a misaligned response is caught at assembly rather than
    silently mapped onto the wrong criterion."""

    terminal_id: str
    points_possible: Decimal
    checks: List[GeneratedCheck]


class ScopeDecomposition(BaseModel):
    """The LLM's structured output for one scope."""

    terminals: List[GeneratedTerminal]


class SelfLabelledCheckError(ValueError):
    """A draft tried to declare its own check a ruling."""


def reject_self_labelled(raw: object) -> None:
    """RULING 1's second door: raw JSON assembled into a draft.

    A generated draft carrying `source: "ruling"` anywhere is a schema
    violation, not something to normalise away — silently rewriting it to
    "generated" would hide a model that is trying to exempt itself from V9.
    """
    def walk(node):
        if isinstance(node, dict):
            if node.get("source") == "ruling":
                raise SelfLabelledCheckError(
                    f"generated draft declares check "
                    f"{node.get('check_id') or '<unnamed>'!r} as source='ruling'; "
                    f"only the plan compiler may set that, when merging a "
                    f"layer-1 ruling (RULING 1)")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(raw)
