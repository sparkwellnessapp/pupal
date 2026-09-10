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
    ContractCheck,
    ContractScopeAnswer,
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
    checks: object                     # Optional[List[Check]] (PR-G1)
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
                        checks=sub.checks,
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
                    checks=crit.checks,
                    scope_key=scope_key,
                )

    return terminal_index, branch_criterion_ids


def _scope_target_id(scope_key: Tuple[str, Optional[str]]) -> str:
    """Mirror of `agents/grader/grader.py::_scope_target_id`, which is what
    stamps an `llm_failure` annotation's `target_id`. The two must agree."""
    question_id, sub_question_id = scope_key
    return f"{question_id}.{sub_question_id}" if sub_question_id else question_id


def _llm_failure_resolved_by_teacher(
    ann,
    terminal_index: Dict[str, _TerminalInfo],
    overrides: GradedTestOverrides,
) -> bool:
    """[OD-R1] Her own verdicts resolve the ONE scope the grader could not grade.

    `llm_failure` is the only ERROR class a teacher can answer directly, and the
    reason is §2: it asserts nothing about the student's work — it says the
    machine has no opinion — so the authority who decides grades can simply
    decide this one. Every other ERROR class stays blocking.

    Without this the row is a DEAD END, which is what production showed: `/retry`
    demands `status == 'failed'` and this row is `draft`; `/manual_edit` demands
    `approved`. Nothing could ever clear the gate, so a student's returned exam
    could never be produced (graded_test e372e6f1, 2026-09-09).

    THE BAR IS EVERY CHECK IN THE SCOPE, not some of them. A crashed scope was
    zeroed wholesale, so a check she has not decided still carries a machine zero
    that no one has read — freezing that into an immutable contract is precisely
    the §5 catastrophe the gate exists to prevent. And a scope carrying NO checks
    can never be resolved this way: there is nothing she could have decided, so
    "all of them are decided" must not be vacuously true (`bool(required)`).
    """
    if getattr(ann, "annotation_type", None) != "llm_failure" or not ann.target_id:
        return False
    decided = {
        (terminal_id, decision.check_id)
        for terminal_id, decisions in overrides.terminals.items()
        for decision in decisions
    }
    required = [
        (info.terminal_id, check.check_id)
        for info in terminal_index.values()
        if _scope_target_id(info.scope_key) == ann.target_id
        for check in (info.checks or [])
    ]
    return bool(required) and all(key in decided for key in required)


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

    # [PR-G5] An override is a VERDICT on a CHECK, so there is nothing to
    # round and no teacher-typed number to bound: points are derived by the one
    # pricer, which clamps and snaps. The bounds check survives on the DERIVED
    # value further down — a firing guard there would mean the pricer is wrong,
    # which is exactly what we want to hear about (§0.5).
    for tid, decisions in overrides.terminals.items():
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

        # Check 3 [CW-3, extended to checks]: every overridden check_id must be
        # a real check in THIS terminal's draft. The closed world is now the
        # check set, because the check is what she decides.
        known = {c.check_id for c in (terminal_index[tid].checks or [])}
        for decision in decisions:
            if decision.check_id not in known:
                violations.append(GateViolation(
                    terminal_id=tid,
                    violation_kind="closed_world",
                    message=(
                        f"Override on '{tid}' references check "
                        f"'{decision.check_id}', which is not a check of that "
                        f"terminal in this draft."
                    ),
                ))

    # Check 5: no UNRESOLVED error-severity annotations in draft
    for ann in draft.annotations:
        if ann.severity != AnnotationSeverity.ERROR:
            continue
        if _llm_failure_resolved_by_teacher(ann, terminal_index, overrides):
            continue
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

    # [PR-G5, R-9 condition i] BOTH numbers are derived by the one pricer:
    # ai_points_awarded from the AI verdicts, final_points_awarded from the
    # effective ones. Copying the draft's stored points for the AI side would
    # reintroduce a second source of truth for a number the pricer owns.
    ai_prices, final_prices, effective_checks, touched_ids = _price_by_scope(
        draft, terminal_index, overrides, precision)

    for info in terminal_index.values():
        decisions = overrides.overrides_for(info.terminal_id)
        by_check = {d.check_id: d for d in decisions}
        final = final_prices.get(info.terminal_id, info.ai_points_awarded)
        ai_award = ai_prices.get(info.terminal_id, info.ai_points_awarded)
        was_overridden = final != ai_award
        # the terminal-level note keeps the v3 wire: the first comment she wrote
        teacher_comment = next((d.teacher_comment for d in decisions
                                if d.teacher_comment), None)

        # Belt and braces on the DERIVED value (§0.5): the pricer clamps and
        # snaps, so this can only fire if the pricer is wrong.
        if final < Decimal("0") or final > info.points_possible:
            raise GateError([GateViolation(
                terminal_id=info.terminal_id, violation_kind="out_of_bounds",
                message=(f"derived award {final} for '{info.terminal_id}' is "
                         f"outside [0, {info.points_possible}] — the pricer is wrong"))])

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
            # [PR-G1] mirror the checks. No verdict overlay exists until PR-G5,
            # so final == ai here; the provenance SHAPE is what freezes.
            checks=([ContractCheck(
                check_id=c.check_id, text=c.text, tariff=c.tariff,
                ai_verdict=c.verdict,
                final_verdict=(by_check[c.check_id].verdict
                               if c.check_id in by_check else c.verdict),
                was_overridden=c.check_id in by_check,
                evidence_disputed=(by_check[c.check_id].evidence_disputed
                                   if c.check_id in by_check else False),
                teacher_comment=(by_check[c.check_id].teacher_comment
                                 if c.check_id in by_check else None),
            ) for c in info.checks] if info.checks else None),
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
            # [EVD-1] carried verbatim from the draft — the approval gate does
            # not re-resolve the answer, because the answer is not a judgement
            # the gate makes. Re-deriving it here would be a second opinion
            # about what the grader saw.
            student_answer=(
                ContractScopeAnswer(**scope.student_answer.model_dump())
                if scope.student_answer is not None else None
            ),
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
        feedback=_freeze_feedback(draft, overrides),   # [PR-G4] effective text
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


def _price_by_scope(draft, terminal_index, overrides, precision):
    """Price every terminal twice — AI verdicts and effective verdicts — through
    the ONE composer. Charge groups dedup scope-wide, which is why this is done
    per scope rather than per terminal.

    v3 drafts carry no checks; those terminals keep their stored award and
    cannot be verdict-overridden, so both sides fall back to the draft.
    """
    from app.services.pricing import apply_overlay, price_scope_checks

    ai_prices, final_prices, effective, touched = {}, {}, {}, set()
    by_scope = {}
    for info in terminal_index.values():
        by_scope.setdefault(info.scope_key, []).append(info)

    for _key, infos in by_scope.items():
        ai_terms, final_terms = [], []
        for info in infos:
            if not info.checks:
                continue
            eff, ids = apply_overlay(info.checks,
                                     overrides.overrides_for(info.terminal_id))
            effective[info.terminal_id] = eff
            touched |= ids
            ai_terms.append((info.terminal_id, info.points_possible, info.checks))
            final_terms.append((info.terminal_id, info.points_possible, eff))
        if not ai_terms:
            continue
        ai_prices.update(price_scope_checks(ai_terms, precision))
        final_prices.update(price_scope_checks(final_terms, precision,
                                               overridden_check_ids=touched))
    return ai_prices, final_prices, effective, touched


def _freeze_feedback(draft, overrides):
    """The EFFECTIVE feedback at approval: her edit wins, and was_edited says so.

    Her words are never overwritten by a regeneration (OD-G4.2) and never
    silently attributed to the model.
    """
    from app.schemas.graded_test_contract import ContractFeedback, ContractFeedbackText

    edits = dict(getattr(overrides, "feedback", {}) or {})
    block = getattr(draft, "feedback", None)
    if block is None and not edits:
        return None

    scopes = {}
    for scope_id, text in ((block.scopes if block else {}) or {}).items():
        scopes[scope_id] = ContractFeedbackText(
            text=edits.get(scope_id, text.text),
            was_edited=scope_id in edits)
    for scope_id, edited in edits.items():          # she wrote where the model did not
        if scope_id not in scopes and scope_id != "summary":
            scopes[scope_id] = ContractFeedbackText(text=edited, was_edited=True)

    summary_src = block.summary.text if block and block.summary else None
    summary = None
    if "summary" in edits or summary_src is not None:
        summary = ContractFeedbackText(
            text=edits.get("summary", summary_src or ""),
            was_edited="summary" in edits)
    return ContractFeedback(scopes=scopes, summary=summary)
