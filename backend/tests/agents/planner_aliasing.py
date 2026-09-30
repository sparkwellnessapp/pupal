"""Test helper: a planner output written against a scope's REAL ids, re-addressed
by the AM-G17 aliases that scope's input carries — i.e. the output a model that
copied its closed lists correctly would return. Split refs (n1…) are unchanged."""
from __future__ import annotations

from app.agents.planner.inputs import SPLIT_REFS
from app.agents.planner.schemas import ScopePlanOutput
from app.agents.planner.stage1_input import planner_aliases


def to_aliases(scope, out: ScopePlanOutput) -> ScopePlanOutput:
    table = planner_aliases(scope)

    def a(x):
        return x if x is None or x in SPLIT_REFS else table.alias(x)

    return out.model_copy(update={
        "terminals": [pt.model_copy(update={
            "terminal_id": a(pt.terminal_id),
            "credits": [c.model_copy(update={"component_ref": a(c.component_ref)}) for c in pt.credits]})
            for pt in out.terminals],
        "faults": [f.model_copy(update={
            "anchor_terminal_id": a(f.anchor_terminal_id),
            "requires_component_ref": a(f.requires_component_ref),
            "options": [o.model_copy(update={"marker_id": a(o.marker_id)}) for o in f.options]})
            for f in out.faults],
        "dispositions": [d.model_copy(update={"marker_id": a(d.marker_id),
                                              "merged_into_marker_id": a(d.merged_into_marker_id)})
                         for d in out.dispositions]})
