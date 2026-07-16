"""
GradedTest contract compiler — pure function, no DB, no I/O.

compile_graded_test(draft, overrides, rubric_contract) -> GradedTestContract

The approval gate (§4.2 of S9 spec) runs first. On any violation the function
raises GateError with a list of all violations found (collect-all, not fail-fast).
Gate does NOT re-fire rubric point-sum invariants on awarded points — those
constrain possible points, not awarded points, and were validated at rubric-compile
time (S6). Re-firing them here would wrongly reject legitimate partial credit.

Five gate checks (in order):
  1. CW — no override keys referencing branch criterion IDs (only leaves are overridable)
  2. CW — no override keys referencing unknown terminal IDs (closed-world)
  3. Bounds — every effective points_awarded ∈ [0, terminal.points_possible]
  4. Precision — every overridden award rounded to numeric_policy.precision (not rejected)
  5. Annotations — no error-severity annotations in draft.annotations
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Literal, NamedTuple, Optional, Set, Tuple
from uuid import uuid4

from app.schemas.graded_test_contract import (
    ContractScopeOutcome,
    ContractTerminalOutcome,
    GradedTestContract,
)
from app.schemas.graded_test_draft import GradedTestDraft, GradedTestOverrides
from app.schemas.ontology_types import AnnotationSeverity, GradingRubricContract
from app.services.selection_scoring import ScopeScore, score_with_selection


# ---------------------------------------------------------------------------
# Gate error types
# ---------------------------------------------------------------------------

@dataclass
class GateViolation:
    terminal_id: str
    violation_kind: Literal[
        "branch_criterion",
        "closed_world",
        "out_of_bounds",
        "error_annotation",
    ]
    message: str


class GateError(Exception):
    """Raised when the approval gate finds one or more violations."""

    def __init__(self, violations: List[GateViolation]) -> None:
        self.violations = violations
        super().__init__(f"{len(violations)} gate violation(s)")


# ---------------------------------------------------------------------------
# Internal: per-terminal metadata extracted from the draft
# ---------------------------------------------------------------------------

class _TerminalInfo(NamedTuple):
    terminal_id: str
    terminal_kind: Literal["criterion", "sub_criterion"]
    description: str
    points_possible: Decimal
    ai_points_awarded: Decimal
    ai_reasoning: str
    ai_evidence_quote: object          # Optional[AnswerQuotation]
    scope_key: Tuple[str, Optional[str]]  # (question_id, sub_question_id)


def _build_terminal_index(
    draft: GradedTestDraft,
) -> Tuple[Dict[str, _TerminalInfo], Set[str]]:
    """
    Walk draft.scope_outcomes and build:
      terminal_index: terminal_id → _TerminalInfo
      branch_criterion_ids: set of criterion_ids that have sub_criterion_outcomes
                            (these are NOT terminals — overrides on them are rejected)
    """
    terminal_index: Dict[str, _TerminalInfo] = {}
    branch_criterion_ids: Set[str] = set()

    for scope in draft.scope_outcomes:
        scope_key = (scope.question_id, scope.sub_question_id)

        for crit in scope.criterion_outcomes:
            if crit.sub_criterion_outcomes:
                # Branch criterion — not a terminal; its sub-criteria are
                branch_criterion_ids.add(crit.criterion_id)

                for sub in crit.sub_criterion_outcomes:
                    terminal_index[sub.sub_criterion_id] = _TerminalInfo(
                        terminal_id=sub.sub_criterion_id,
                        terminal_kind="sub_criterion",
                        description=sub.description,
                        points_possible=sub.points_possible,
                        ai_points_awarded=sub.points_awarded,
                        ai_reasoning=sub.reasoning,
                        ai_evidence_quote=sub.evidence_quote,
                        scope_key=scope_key,
                    )
            else:
                # Leaf criterion — directly a terminal
                terminal_index[crit.criterion_id] = _TerminalInfo(
                    terminal_id=crit.criterion_id,
                    terminal_kind="criterion",
                    description=crit.description,
                    points_possible=crit.points_possible,
                    ai_points_awarded=crit.points_awarded,
                    ai_reasoning=crit.reasoning,
                    ai_evidence_quote=crit.evidence_quote,
                    scope_key=scope_key,
                )

    return terminal_index, branch_criterion_ids


# ---------------------------------------------------------------------------
# Public: compile_graded_test
# ---------------------------------------------------------------------------

def compile_graded_test(
    draft: GradedTestDraft,
    overrides: GradedTestOverrides,
    rubric_contract: GradingRubricContract,
) -> GradedTestContract:
    """
    Gate + compile the teacher's overrides against the draft, producing a
    frozen GradedTestContract.

    Args:
        draft: The GradedTestDraft (agent's output + teacher overrides).
        overrides: The teacher's final override map (terminal_id → TeacherOverride).
                   This is authoritative; the draft's existing teacher_overrides
                   is NOT used here — the caller passes the current set.
        rubric_contract: The frozen rubric contract (for numeric_policy.precision).

    Returns:
        A frozen GradedTestContract.

    Raises:
        GateError: if any approval gate check fails (collect-all violations).
    """
    terminal_index, branch_criterion_ids = _build_terminal_index(draft)
    precision = rubric_contract.numeric_policy.precision

    # ------------------------------------------------------------------
    # Gate: collect all violations before raising
    # ------------------------------------------------------------------
    violations: List[GateViolation] = []

    # Round overrides to precision in-place (mutate a working copy)
    rounded_overrides = {}
    for tid, override in overrides.items():
        # Round to the nearest multiple of precision (e.g. 4.3 → 4.25 when precision=0.25).
        # Decimal.quantize(precision) controls only decimal places; to snap to a grid
        # we divide, round to nearest integer, then multiply back.
        rounded = (override.points_awarded / precision).to_integral_value(
            rounding=ROUND_HALF_UP
        ) * precision
        # Rebuild with rounded value (TeacherOverride is a Pydantic model)
        rounded_overrides[tid] = override.model_copy(update={"points_awarded": rounded})

    for tid in rounded_overrides:
        # Check 1: branch criterion ID (not overridable)
        if tid in branch_criterion_ids:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="branch_criterion",
                message=(
                    f"'{tid}' is a branch criterion (has sub-criteria) and cannot be "
                    "overridden directly — override its individual sub-criteria instead."
                ),
            ))
            continue  # skip further checks for this key

        # Check 2: unknown terminal ID (closed-world)
        if tid not in terminal_index:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="closed_world",
                message=(
                    f"Override key '{tid}' does not reference any known terminal "
                    "criterion in this graded test."
                ),
            ))
            continue

        # Check 3: bounds
        info = terminal_index[tid]
        awarded = rounded_overrides[tid].points_awarded
        if awarded < Decimal("0") or awarded > info.points_possible:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="out_of_bounds",
                message=(
                    f"Override for '{tid}': points_awarded={awarded} is outside "
                    f"[0, {info.points_possible}]."
                ),
            ))

    # Check 5: no error-severity annotations in draft
    for ann in draft.annotations:
        if ann.severity == AnnotationSeverity.ERROR:
            violations.append(GateViolation(
                terminal_id=ann.target_id,
                violation_kind="error_annotation",
                message=(
                    f"Annotation '{ann.annotation_type}' (ERROR) on target "
                    f"'{ann.target_id}' must be resolved before approval: {ann.message}"
                ),
            ))

    if violations:
        raise GateError(violations)

    # ------------------------------------------------------------------
    # Resolve effective values + build ContractTerminalOutcomes
    # ------------------------------------------------------------------

    # Group terminals by scope_key so we can reconstruct ContractScopeOutcomes
    # in the same order as draft.scope_outcomes.
    scope_terminals: Dict[Tuple[str, Optional[str]], List[ContractTerminalOutcome]] = {
        (s.question_id, s.sub_question_id): [] for s in draft.scope_outcomes
    }

    for info in terminal_index.values():
        override = rounded_overrides.get(info.terminal_id)
        final = override.points_awarded if override is not None else info.ai_points_awarded
        was_overridden = (
            override is not None
            and override.points_awarded != info.ai_points_awarded
        )
        teacher_comment = override.teacher_comment if override is not None else None

        terminal = ContractTerminalOutcome(
            terminal_id=info.terminal_id,
            terminal_kind=info.terminal_kind,
            description=info.description,
            points_possible=info.points_possible,
            ai_points_awarded=info.ai_points_awarded,
            ai_reasoning=info.ai_reasoning,
            ai_evidence_quote=info.ai_evidence_quote,
            was_overridden=was_overridden,
            teacher_comment=teacher_comment,
            final_points_awarded=final,
        )
        scope_terminals[info.scope_key].append(terminal)

    # ------------------------------------------------------------------
    # Build ContractScopeOutcomes, preserving draft scope order
    # ------------------------------------------------------------------
    scope_outcomes: List[ContractScopeOutcome] = []
    for scope in draft.scope_outcomes:
        key = (scope.question_id, scope.sub_question_id)
        terminals = scope_terminals[key]
        scope_final = sum(
            (t.final_points_awarded for t in terminals), Decimal("0")
        )
        scope_outcomes.append(ContractScopeOutcome(
            scope_kind=scope.scope_kind,
            question_id=scope.question_id,
            sub_question_id=scope.sub_question_id,
            points_possible=scope.points_possible,
            final_points_awarded=scope_final,
            terminal_outcomes=terminals,
        ))

    # ------------------------------------------------------------------
    # Compute totals — SELECTION-AWARE, and AUTHORITATIVE (PR-3)
    # ------------------------------------------------------------------
    # This gate used to re-sum `Σ scope.points_possible` for the denominator, which
    # is the same re-derivation bug the grading runner had. Fixing only the runner
    # would have been WORSE than leaving both broken: the teacher would have reviewed
    # one percentage and had a different one frozen into the immutable contract — a
    # silent disagreement at the exact trust boundary the product is built on.
    #
    # Both sites now call the SAME helper. The split is recomputed here from
    # POST-OVERRIDE scores, because a teacher override can change which member wins
    # the best-k slot (she bumps the 15-pointer above the 50-pointer's awarded
    # points and membership flips). The grading-time marks were provisional; THIS
    # recomputation is authoritative and is what freezes.
    scoring = score_with_selection(
        [
            ScopeScore(
                question_id=s.question_id,
                sub_question_id=s.sub_question_id,
                awarded=s.final_points_awarded,
            )
            for s in scope_outcomes
        ],
        rubric_contract,
    )
    scope_outcomes = [
        s.model_copy(update={
            "counted_in_total": scoring.is_counted((s.question_id, s.sub_question_id))
        })
        for s in scope_outcomes
    ]

    total_score = scoring.total_score
    total_possible = scoring.total_possible          # contract ACHIEVABLE — never re-summed
    if total_possible == Decimal("0"):
        percentage = Decimal("0")
    else:
        percentage = (total_score / total_possible * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return GradedTestContract(
        contract_version=str(uuid4()),
        rubric_contract_version=draft.rubric_contract_version,
        transcription_contract_version=draft.transcription_contract_version,
        model_version=draft.model_version,
        prompt_version=draft.prompt_version,
        scope_outcomes=scope_outcomes,
        total_score=total_score,
        total_possible=total_possible,
        percentage=percentage,
        approved_at=datetime.now(timezone.utc).isoformat(),
    )
