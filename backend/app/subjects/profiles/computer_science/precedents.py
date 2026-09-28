"""computer_science pack — the PRECEDENTS ([AM-G5], owner 2026-09-27).

The eleven general clauses AM-G5 names, REFERENCED from the constitution
(`app/agents/plan_gen/constitution.py`), never copied: `select` returns the
constitution's own frozen `Clause` objects, in the ruling's order, and refuses a
class-4 exam-specific ruling by id. They feed the v6 PLANNER and EXPLAINER only,
never the verifier. No PB-* ruling is a clause here, or anywhere a prompt reads.
"""
from __future__ import annotations

from app.agents.plan_gen.constitution import select

# AM-G5's list, in its order. The constitution spells R-α / R-β as R-alpha / R-beta.
PRECEDENT_IDS = ("PL-1", "PL-2", "PL-3", "PL-9", "PL-10", "R-alpha", "R-beta",
                 "A-6", "charge-once", "credit-once", "P-A")

PRECEDENTS = select(*PRECEDENT_IDS)
