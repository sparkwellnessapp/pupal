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
from enum import Enum
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


# ═══════════════════════════════════════════════════════════════════════════
# plan/v6 — one building block for every check (PR_grader_v6_options.md §3.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# Every check is a small multiple-choice question: options carry a Hebrew
# label and a VALUE; the verifier picks an option id, never a number (D-LAW-2);
# code prices (services/pricing_v6.py). Extended IN PLACE here, beside the v5
# types, because both stacks live until the v5 path is deleted
# (GRADER_ARCHITECTURE ∈ {v3, v5, v6}, Q-13). The v6 classes carry a `V6`
# suffix only because the spec's names collide with the v5 classes above,
# which must keep parsing the v5 plans in `grading_plans` until then; the
# suffix goes when v5 does.
#
# Amendments (STOP-1, 2026-09-27; docs/GRADER_V6_CENSUS.md §1a):
#   AM-G1  no reduction terminals: no `TerminalPlan.kind`, no
#          `CheckOption.home_terminal_id` (markers keep their home, below).
#   AM-G2  `evidence_required` — false only for legacy fault checks.
#   Q-10   the `note` role: a «לא להוריד, לכתוב הערה» line, options
#          `none`/`observed`, both 0, never priced. `notes_he` is gone.


class PartialFraction(str, Enum):
    """The closed fraction list the planner chooses from (D-LAW-2): never a
    free number. Values in `plan_values.FRACTION_VALUE`."""
    QUARTER = "QUARTER"
    HALF = "HALF"
    THREE_QUARTERS = "THREE_QUARTERS"


CheckRole = Literal["credit", "fault", "note"]
CheckShape = Literal["binary", "ladder", "levels", "count", "fault", "note"]
CheckOrigin = Literal["compiler", "planner", "fallback", "legacy"]


class CheckOption(BaseModel):
    """One possible answer to a check. Values are exact Decimals on the grid:
    credit 0..max, fault <= 0, note 0 (V12, V17)."""
    model_config = {"frozen": True}

    option_id: str                       # assigned by code (§3.2)
    label_he: str                        # what the answer looks like when this option applies
    value: Decimal
    marker_id: Optional[str] = None      # fault options only

    @field_serializer("value")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class PlanCheckV6(BaseModel):
    """One check. Display order of `options`: credit highest-first; fault and
    note `none` first."""
    model_config = {"frozen": True}

    check_id: str                        # assigned by code (§3.2)
    role: CheckRole
    shape: CheckShape
    description_he: str                  # the thing checked, in the teacher's words
    source_span: str                     # verbatim from an allowed source (V16)
    options: List[CheckOption]
    requires: Optional[str] = None       # fault only: a credit check on the same priced terminal
    charge_group: Optional[str] = None   # fault only
    priced_terminal_id: str
    equivalence_note_he: Optional[str] = None
    evidence_required: bool = True       # [AM-G2]
    origin: CheckOrigin

    def option(self, option_id: Optional[str]) -> Optional[CheckOption]:
        for o in self.options:
            if o.option_id == option_id:
                return o
        return None

    @property
    def default_option(self) -> CheckOption:
        """The option a check resolves to with no valid selection (PRC-1):
        the zero option for credit (the LAST option in display order — V12),
        `none` for fault and note (the FIRST)."""
        return self.options[-1] if self.role == "credit" else self.options[0]


class TerminalPlanV6(BaseModel):
    model_config = {"frozen": True}

    terminal_id: str
    points_possible: Decimal
    interpretation_notes_he: List[str] = Field(default_factory=list)   # OD-G4; <= 3

    @field_serializer("points_possible")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class PackRef(BaseModel):
    model_config = {"frozen": True}
    pack_id: str
    pack_version: str


class GradingPlanV6(BaseModel):
    """The frozen, hashed plan (§3.1). A compiled artefact of the contract —
    never teacher-edited, never shown to her (W-3)."""
    model_config = {"frozen": True}

    plan_schema: Literal["plan/v6"]
    plan_hash: str                       # plan_values.plan_hash(terminals, checks)
    config_hash: str                     # plan_values.config_hash(...)
    rubric_contract_version: str
    subject_pack: PackRef
    terminals: List[TerminalPlanV6]
    checks: List[PlanCheckV6]            # plan order: rubric order; within a terminal credit, fault, note


# ── plan-building vocabulary (Stage 1 → planner → assembly) ─────────────────

class DeductionMarker(BaseModel):
    """A deduction phrase Stage 1 detected in the teacher's text (§5.1 C1).
    `home_terminal_id` is where she wrote it; the planner anchors the fault on
    one of `candidate_anchors` (S-4, V18). The amount is copied verbatim and
    NEVER shown to the planner."""
    model_config = {"frozen": True}

    marker_id: str
    home_terminal_id: str
    amount: Optional[Decimal]
    polarity: Literal["deduct", "no_deduct"]
    text_span: str
    charge_group: Optional[str] = None
    candidate_anchors: List[str]

    @field_serializer("amount")
    def _sd(self, v: Optional[Decimal]) -> Optional[str]:
        return None if v is None else str(v)


class MarkerDisposition(BaseModel):
    """What the planner did with one marker (V14)."""
    model_config = {"frozen": True}

    marker_id: str
    disposition: Literal["fault", "merged", "not_a_deduction"]
    merged_into_marker_id: Optional[str] = None
    reason_he: Optional[str] = None      # required for merged and not_a_deduction


class PlanDraft(BaseModel):
    """Mutable build-time companion of a GradingPlanV6 — never on the plan.
    Carries what the plan must not: dispositions and telemetry."""
    marker_dispositions: List[MarkerDisposition] = Field(default_factory=list)
    telemetry: dict = Field(default_factory=dict)


# ── the v6 verifier's output (§6.2) ──────────────────────────────────────────

class CheckVerdictV6(BaseModel):
    """One check's verdict. FIELD ORDER IS LOAD-BEARING: the evidence is decoded
    before the decision (`test_check_verdict_v6_decode_order_is_evidence_first`).
    Ids are the call's AM-G17 aliases (`c1`, `o2`); code maps them back."""
    check_id: str
    evidence_quote: str                  # "" only for a default option
    absence_pointer_he: str              # "" unless the credit zero option
    option_id: str


class ScopeVerdictsV6(BaseModel):
    verdicts: List[CheckVerdictV6]
