"""The planner's structured output (PR_grader_v6_options.md §5.3).

D-LAW-2 / P-10: the model never emits a number. There is NO numeric field in any
model here — `PartialFraction` is a closed enum, ids and enums come from closed
lists given in the input, and code derives every value (§3.3, `plan_values`).
`test_planner_schema_has_no_numeric_fields` walks the JSON schema to keep it so.

List-length limits (partials 0..2, notes 0..3, fault options 1..7) are checked in
code, never in the schema: a provider's native JSON-schema mode may reject or
ignore `minItems`/`maxItems`, and a violation must reach the ONE repair call with a
validator message (§5.6) rather than fail the parse.

`MarkerDisposition` is the Phase-1 type in `grader/plan_schemas.py` — one
concept, one place — re-exported here for the planner's output.

[AM-G19, planner-v6.2] Each credit carries `element` (binary | non_binary), decoded
after its span and BEFORE its labels and partials, so the call precedes the options it
governs. It is required-and-nullable in the schema: a live call must state it, and a
planner-v6.1 recording (which has no such key) still parses — as null, which only the
legacy replay path accepts (`assemble.map_scope(am_g19=False)`). A partial may carry
`teacher_span`: her own words stating a partial value, the one way a binary or small
credit keeps a partial.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.agents.grader.plan_schemas import CreditElement, MarkerDisposition, PartialFraction

__all__ = ["PlannedPartial", "PlannedCredit", "PlannedTerminal", "PlannedFaultOption",
           "PlannedFault", "MarkerDisposition", "ScopePlanOutput", "Decomposition"]

Decomposition = Literal["as_compiled", "binary", "ladder", "split"]


class PlannedPartial(BaseModel):
    label_he: str
    fraction: PartialFraction
    teacher_span: Optional[str] = None    # [AM-G19 c] verbatim, when SHE states this partial's value


class PlannedCredit(BaseModel):
    component_ref: str                    # an AM-G17 alias: a component (k1…); for split: "n1".."n6"
    description_he: str
    source_span: str
    element: Optional[CreditElement]      # [AM-G19 a] required key; null only in v6.1 recordings
    full_label_he: str
    absent_label_he: str
    partials: List[PlannedPartial] = Field(default_factory=list)          # 0..2 (checked in code)
    equivalence_note_he: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _v61_recordings_have_no_element(cls, data: Any) -> Any:
        if isinstance(data, dict) and "element" not in data:
            return {**data, "element": None}
        return data


class PlannedTerminal(BaseModel):
    terminal_id: str                      # an AM-G17 alias (t1…)
    decomposition: Decomposition
    credits: List[PlannedCredit]
    interpretation_notes_he: List[str] = Field(default_factory=list)     # 0..3 (checked in code)


class PlannedFaultOption(BaseModel):
    marker_id: str
    label_he: str                         # a disjoint condition, rewritten if needed (P-5)


class PlannedFault(BaseModel):
    anchor_terminal_id: str               # in every member marker's candidate_anchors (V18)
    requires_component_ref: Optional[str] = None   # a credit component of the anchor
    description_he: str
    options: List[PlannedFaultOption]                                    # 1..7 (checked in code)


class ScopePlanOutput(BaseModel):
    terminals: List[PlannedTerminal]
    faults: List[PlannedFault] = Field(default_factory=list)
    dispositions: List[MarkerDisposition] = Field(default_factory=list)
