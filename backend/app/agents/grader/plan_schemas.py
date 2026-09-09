"""
grader-v5 Plan/Verify/Price — the PLAN side (MISSION_grader_v5_closed_loop §3/§5).

A GradingPlan decomposes every terminal of ONE rubric contract into discrete,
requirement-phrased checks. The verifier model emits VERDICTS over these checks
(never a number); the deterministic pricer (pricer.py) converts verdicts to
points. The plan is authored per exam, validated by plan_validator.py, and
ratified by the owner (H-4) — plan_version is pinned at ratification.

Check semantics (all checks are REQUIREMENT-phrased — "met" means the
requirement is satisfied, i.e. NO defect):
  required   carries points; met→100%, partially_met→partial_fraction (default
             50%), not_met→0. Per terminal, Σ required.points == points_possible
             EXACTLY (validator rule V1) — so a fully-met terminal earns full.
  tariff     carries a NAMED deduction (rubric tariff, verbatim). not_met (the
             defect is present) deducts tariff_amount, once per charge_group
             (the charge-once precedent). Carries no earn-points.
  note_only  the rubric says "לציין, לא להוריד": not_met produces an annotation,
             never a deduction. Carries no points ever.

Two fields beyond the ratified mission schema, both flagged for owner review in
the V5-B render:
  partial_fraction  the mission's "50% default, plan-overridable" — the override
                    has to live somewhere; it lives on the check.
  rubric_quote      the rubric span this check derives from — traceability for
                    the owner's H-4 review (and the anti-GT-leak audit trail:
                    every check must trace to rubric text, never to a GT note).
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_serializer

# ALPHA-GAP A-1 (D-3): no `level_select` kind — a band ladder grades as ONE `required` check at the
# top band (C8-lite in plan_compiler/compile.py). Alpha adds the kind here first; every
# dispatch below and in pricer.py / plan_validator.py / pricing.ts follows from it.
CheckKind = Literal["required", "tariff", "note_only", "counted"]

# `counted` — R-E Case 1 (owner-ruled), made a kind by PLAN COMPILER v2 (C3).
# The rubric prices N UNIFORM UNITS («17 תאים 0.7 כל תא»): the award is
#   snap_to_grid(points × units_correct / unit_count)
# and the per-unit figure the teacher wrote is her rounding, not an input. A
# counted check is the ONLY check on its terminal (V12) and carries the terminal's
# full points (so V1 holds). The verifier reports a COUNT (`units_correct`),
# never points — the point-blind contract is intact.


class PlanCheck(BaseModel):
    """One discrete verifiable requirement inside a terminal."""

    model_config = {"frozen": True}

    check_id: str                       # globally unique; convention "<terminal_id>.k<N>"
    description_he: str                 # requirement-phrased, faithful to the rubric wording
    # [plan-gen] WHERE this check came from, and therefore whether V9 binds.
    # "generated" — decomposed from rubric text; its rubric_quote MUST ground in
    #   the contract (V9). This is the volatile layer, re-rollable on edit.
    # "ruling"    — an owner/teacher ruling. It cites a RULING, not rubric text,
    #   so V9 cannot apply; measured against the ratified plan, exactly the two
    #   checks carrying "Owner-ruled …" and "[A-2 owner tariff]" fall here.
    #   This is the durable layer and regeneration must never touch it.
    # Default "generated" so every existing plan re-parses unchanged.
    source: Literal["generated", "ruling"] = "generated"
    kind: CheckKind
    points: Decimal = Decimal("0")      # required: > 0; tariff/note_only: 0
    tariff_amount: Optional[Decimal] = None   # tariff only; > 0, on the precision grid
    partial_fraction: Decimal = Decimal("0.5")  # required only; points*fraction must sit on the grid
    equivalence_note: Optional[str] = None      # acceptable alternative forms (verdict guidance)
    charge_group: Optional[str] = None  # tariff only; same-defect-once across ONE scope
    rubric_quote: Optional[str] = None  # the rubric span this check derives from (H-4 traceability)
    unit_count: Optional[int] = None    # counted only; >= 2 (V12)

    @field_serializer("points", "tariff_amount", "partial_fraction")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return None if v is None else str(v)


class TerminalPlan(BaseModel):
    """The check decomposition of one terminal (leaf criterion / sub-criterion)."""

    model_config = {"frozen": True}

    terminal_id: str
    points_possible: Decimal            # must equal the contract terminal's points (V6)
    checks: List[PlanCheck]

    @field_serializer("points_possible")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class GradingPlan(BaseModel):
    """The full per-exam plan. Frozen: a ratified plan is a contract-like artifact."""

    model_config = {"frozen": True}

    plan_version: str                   # e.g. "hobby_tvshow/v1" — pinned at H-4 ratification
    exam_id: str
    rubric_contract_sha256: str         # pins the plan to the exact contract file bytes
    terminals: List[TerminalPlan]
    # [PLAN COMPILER v2 §6] provenance. All optional so every ratified hand plan
    # re-parses unchanged; a compiled plan stamps all four.
    compiler_version: Optional[str] = None
    segmenter_prompt_version: Optional[str] = None
    segmenter_model: Optional[str] = None
    router_model: Optional[str] = None

    def terminal(self, terminal_id: str) -> TerminalPlan:
        for t in self.terminals:
            if t.terminal_id == terminal_id:
                return t
        raise KeyError(f"plan {self.plan_version!r} has no terminal {terminal_id!r}")


class CheckVerdict(BaseModel):
    """LLM structured output for ONE check.

    FIELD ORDER IS LOAD-BEARING (the grader-v2 lever carried into v5): pydantic
    definition order -> JSON-schema property order -> structured-output DECODE
    order. The verdict is decoded AFTER the evidence span and the basis text —
    evidence-before-verdict, mechanically enforced. Do not reorder.

    evidence_quote: verbatim span from the student's answer supporting the
    verdict. May be "" ONLY when verdict == not_met (an absence cannot be
    quoted); then basis_he states what was searched for and where.
    """

    check_id: str
    evidence_quote: str                 # 1st content field: verbatim span; "" only for not_met
    basis_he: str                       # v5.1 basis-lean: "" for met; for not_met: what was searched
    verdict: Literal["met", "partially_met", "not_met"]
    confidence: float                   # 0.0–1.0 for THIS check's verdict
    # [compiler v2, C3] counted checks only: how many of the unit_count units
    # are correct. A COUNT, never points. Appended LAST so the pinned
    # evidence→basis→verdict→confidence decode prefix is untouched; the
    # verdict is committed before the number that refines it.
    units_correct: Optional[int] = None


class ScopeVerificationResponse(BaseModel):
    """LLM structured output for one GradableScope — one verdict per check."""

    verdicts: List[CheckVerdict]
