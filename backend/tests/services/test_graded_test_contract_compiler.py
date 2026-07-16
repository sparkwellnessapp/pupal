"""
GradedTestContract compiler — pure unit tests (zero DB, zero mocks).

Tests 1–10 from S9 spec §9 "Compiler + gate (pure — zero mocks)".
Tests marked [CORE] protect the three critical invariants:
  [CORE-9]  error annotation blocks approval
  [CORE-13] arithmetic / aggregate correctness (pure function)
  [CORE-17] AI-outcome immutability (provenance preservation)
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

import pytest

from app.schemas.graded_test_draft import (
    CriterionOutcome,
    GradedTestDraft,
    GradedTestOverrides,
    GradingAnnotation,
    ScopeOutcome,
    SubCriterionOutcome,
    TeacherOverride,
)
from app.schemas.ontology_types import AnnotationSeverity
from app.services.graded_test_contract_compiler import (
    GateError,
    compile_graded_test,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _rubric_contract(
    precision: str = "0.25",
    total_points: str = "0",
    selection_groups=None,
    questions=None,
):
    """Stub for GradingRubricContract.

    PR-3 WIDENED what the approval gate needs. It used to read only
    `numeric_policy.precision` (hence the old one-field stub). It now also reads
    `total_points` — the ACHIEVABLE denominator, which it must NOT re-derive by
    re-summing scopes — plus `selection_groups` (and `questions`, only when groups
    exist, for the deterministic best-k tie-break).

    Callers that assert on totals MUST pass a `total_points` consistent with their
    scopes, exactly as a real compiled contract guarantees via INV-1/INV-4. The old
    stub let tests pair a contract with scopes it could never have produced.
    """
    return SimpleNamespace(
        numeric_policy=SimpleNamespace(precision=Decimal(precision)),
        total_points=Decimal(total_points),
        selection_groups=selection_groups or [],
        questions=questions or [],
    )


def _leaf_criterion(
    criterion_id: str = "q1.c0",
    description: str = "Leaf criterion",
    points_possible: str = "5",
    points_awarded: str = "4",
    reasoning: str = "Looks good",
) -> CriterionOutcome:
    return CriterionOutcome(
        criterion_id=criterion_id,
        description=description,
        points_possible=Decimal(points_possible),
        points_awarded=Decimal(points_awarded),
        reasoning=reasoning,
        confidence=0.9,
        sub_criterion_outcomes=None,
    )


def _branch_criterion(
    criterion_id: str = "q1.c1",
    sub_ids: Optional[list] = None,
) -> CriterionOutcome:
    if sub_ids is None:
        sub_ids = [("q1.c1.s0", "3", "2"), ("q1.c1.s1", "4", "3")]
    sub_outcomes = [
        SubCriterionOutcome(
            sub_criterion_id=sid,
            description=f"Sub {sid}",
            points_possible=Decimal(pp),
            points_awarded=Decimal(pa),
            reasoning="Reasonable",
            confidence=0.8,
        )
        for sid, pp, pa in sub_ids
    ]
    total_possible = sum(Decimal(pp) for _, pp, _ in sub_ids)
    total_awarded = sum(Decimal(pa) for _, _, pa in sub_ids)
    return CriterionOutcome(
        criterion_id=criterion_id,
        description="Branch criterion",
        points_possible=total_possible,
        points_awarded=total_awarded,
        reasoning="",
        confidence=0.8,
        sub_criterion_outcomes=sub_outcomes,
    )


def _scope(
    question_id: str = "q1",
    sub_question_id: Optional[str] = None,
    criterion_outcomes: Optional[list] = None,
) -> ScopeOutcome:
    if criterion_outcomes is None:
        criterion_outcomes = [_leaf_criterion()]
    scope_kind = "sub_question" if sub_question_id else "direct"
    total_possible = sum(c.points_possible for c in criterion_outcomes)
    total_awarded = sum(c.points_awarded for c in criterion_outcomes)
    return ScopeOutcome(
        scope_kind=scope_kind,
        question_id=question_id,
        sub_question_id=sub_question_id,
        points_possible=total_possible,
        points_awarded=total_awarded,
        min_confidence=0.8,
        criterion_outcomes=criterion_outcomes,
        graded_by="llm",
    )


def _annotation(
    severity: AnnotationSeverity,
    target_id: str = "q1.c0",
    annotation_type: str = "closed_world_violation",
    message: str = "Test annotation",
) -> GradingAnnotation:
    return GradingAnnotation(
        severity=severity,
        target_id=target_id,
        annotation_type=annotation_type,
        message=message,
    )


def _draft(
    scope_outcomes=None,
    teacher_overrides: Optional[GradedTestOverrides] = None,
    annotations=None,
) -> GradedTestDraft:
    return GradedTestDraft(
        rubric_contract_version="v-test",
        transcription_contract_version="tv-test",
        model_version="gpt-4o",
        prompt_version="v1",
        scope_outcomes=scope_outcomes or [_scope()],
        teacher_overrides=teacher_overrides or {},
        annotations=annotations or [],
        llm_calls_count=1,
        grading_duration_ms=500,
    )


# ---------------------------------------------------------------------------
# Test 1: No overrides → contract finals == AI awards; was_overridden == False
# ---------------------------------------------------------------------------

def test_no_overrides_finals_equal_ai():
    draft = _draft()
    contract = compile_graded_test(draft, {}, _rubric_contract())

    assert len(contract.scope_outcomes) == 1
    scope = contract.scope_outcomes[0]
    assert len(scope.terminal_outcomes) == 1
    t = scope.terminal_outcomes[0]

    assert t.final_points_awarded == Decimal("4")
    assert t.ai_points_awarded == Decimal("4")
    assert t.was_overridden is False
    assert t.teacher_comment is None


# ---------------------------------------------------------------------------
# Test 2: Leaf override → final == teacher value; was_overridden == True; AI preserved
# [CORE-17] AI-outcome immutability
# ---------------------------------------------------------------------------

def test_leaf_override_updates_final_preserves_ai():
    draft = _draft()
    overrides = {"q1.c0": TeacherOverride(points_awarded=Decimal("3"), teacher_comment="Good try")}
    contract = compile_graded_test(draft, overrides, _rubric_contract())

    t = contract.scope_outcomes[0].terminal_outcomes[0]
    assert t.final_points_awarded == Decimal("3")
    assert t.ai_points_awarded == Decimal("4")   # AI value preserved
    assert t.was_overridden is True
    assert t.teacher_comment == "Good try"
    assert t.ai_reasoning == "Looks good"


# ---------------------------------------------------------------------------
# Test 3: Branch recompute → overriding a sub-criterion updates scope total
# ---------------------------------------------------------------------------

def test_branch_sub_criterion_override_updates_scope_total():
    branch = _branch_criterion(sub_ids=[("q1.c1.s0", "3", "2"), ("q1.c1.s1", "4", "3")])
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[branch])])

    # Override first sub-criterion: 2 → 1
    overrides = {"q1.c1.s0": TeacherOverride(points_awarded=Decimal("1"))}
    contract = compile_graded_test(draft, overrides, _rubric_contract())

    scope = contract.scope_outcomes[0]
    # Scope final = 1 (overridden s0) + 3 (AI s1) = 4
    assert scope.final_points_awarded == Decimal("4")

    finals = {t.terminal_id: t.final_points_awarded for t in scope.terminal_outcomes}
    assert finals["q1.c1.s0"] == Decimal("1")
    assert finals["q1.c1.s1"] == Decimal("3")


# ---------------------------------------------------------------------------
# Test 4: Provenance preserved
# [CORE-17] All four provenance fields present and correct
# ---------------------------------------------------------------------------

def test_provenance_all_four_fields():
    crit = _leaf_criterion(points_awarded="3", reasoning="Solid reasoning")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])
    overrides = {"q1.c0": TeacherOverride(points_awarded=Decimal("4"), teacher_comment="Adjusted")}
    contract = compile_graded_test(draft, overrides, _rubric_contract())

    t = contract.scope_outcomes[0].terminal_outcomes[0]
    assert t.ai_points_awarded == Decimal("3")
    assert t.ai_reasoning == "Solid reasoning"
    assert t.teacher_comment == "Adjusted"
    assert t.final_points_awarded == Decimal("4")


# ---------------------------------------------------------------------------
# Test 5: Gate — out of bounds → GateError with out_of_bounds violation
# ---------------------------------------------------------------------------

def test_gate_out_of_bounds():
    draft = _draft()
    overrides = {"q1.c0": TeacherOverride(points_awarded=Decimal("99"))}  # max is 5
    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, overrides, _rubric_contract())

    kinds = [v.violation_kind for v in exc_info.value.violations]
    assert "out_of_bounds" in kinds


# ---------------------------------------------------------------------------
# Test 6: Gate — precision → off-grid override is ROUNDED (not rejected)
# ---------------------------------------------------------------------------

def test_gate_precision_rounds_not_rejects():
    # precision = 0.25; teacher enters 4.3 → should be rounded to 4.25
    crit = _leaf_criterion(points_possible="5", points_awarded="4")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])
    overrides = {"q1.c0": TeacherOverride(points_awarded=Decimal("4.3"))}

    # Should NOT raise
    contract = compile_graded_test(draft, overrides, _rubric_contract("0.25"))
    t = contract.scope_outcomes[0].terminal_outcomes[0]
    # 4.3 rounded to nearest 0.25 = 4.25
    assert t.final_points_awarded == Decimal("4.25")


# ---------------------------------------------------------------------------
# Test 7: Gate — closed-world → unknown terminal_id → GateError
# ---------------------------------------------------------------------------

def test_gate_closed_world_unknown_terminal():
    draft = _draft()
    overrides = {"nonexistent.criterion": TeacherOverride(points_awarded=Decimal("1"))}
    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, overrides, _rubric_contract())

    kinds = [v.violation_kind for v in exc_info.value.violations]
    assert "closed_world" in kinds


# ---------------------------------------------------------------------------
# Test 8: Gate — override on branch criterion_id → GateError with branch_criterion
# ---------------------------------------------------------------------------

def test_gate_branch_criterion_not_overridable():
    branch = _branch_criterion()  # criterion_id = "q1.c1"
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[branch])])

    overrides = {"q1.c1": TeacherOverride(points_awarded=Decimal("5"))}  # branch ID
    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, overrides, _rubric_contract())

    kinds = [v.violation_kind for v in exc_info.value.violations]
    assert "branch_criterion" in kinds


# ---------------------------------------------------------------------------
# Test 9: Gate — error annotation blocks; warning/info do NOT block
# [CORE-9]
# ---------------------------------------------------------------------------

def test_gate_error_annotation_blocks():
    error_ann = _annotation(AnnotationSeverity.ERROR, annotation_type="no_answer")
    draft = _draft(annotations=[error_ann])
    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, {}, _rubric_contract())

    kinds = [v.violation_kind for v in exc_info.value.violations]
    assert "error_annotation" in kinds


def test_gate_warning_and_info_do_not_block():
    warning_ann = _annotation(AnnotationSeverity.WARNING, annotation_type="fuzzy_match")
    info_ann = _annotation(AnnotationSeverity.INFO, annotation_type="no_answer")
    draft = _draft(annotations=[warning_ann, info_ann])
    # Should compile without raising
    contract = compile_graded_test(draft, {}, _rubric_contract())
    assert contract is not None


# ---------------------------------------------------------------------------
# Test 10: Aggregates → total_score/possible/percentage correct; /0 guarded
# [CORE-13]
# ---------------------------------------------------------------------------

def test_aggregates_correct_post_override():
    crit_a = _leaf_criterion("q1.c0", points_possible="5", points_awarded="4")
    crit_b = _leaf_criterion("q1.c1", points_possible="10", points_awarded="8")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit_a, crit_b])])
    overrides = {"q1.c0": TeacherOverride(points_awarded=Decimal("3"))}

    # PR-3: the denominator now comes from the CONTRACT (achievable), never from
    # re-summing scopes. A real contract whose scopes are 5+10 declares total 15 —
    # INV-1/INV-4 guarantee it — so the expected values below are UNCHANGED. That
    # equality is the point: for a flat, selection-free contract the new math is
    # bit-for-bit the old math.
    contract = compile_graded_test(draft, overrides, _rubric_contract(total_points="15"))

    assert contract.total_score == Decimal("11")    # 3 + 8
    assert contract.total_possible == Decimal("15") # achievable == offered here
    # 11 / 15 * 100 = 73.33...
    assert contract.percentage == Decimal("73.33")
    # nothing excluded on a non-selection contract
    assert all(s.counted_in_total for s in contract.scope_outcomes)


def test_aggregates_zero_possible_no_division_error():
    # Degenerate: all criteria have 0 points_possible
    crit = _leaf_criterion(points_possible="0", points_awarded="0")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])
    contract = compile_graded_test(draft, {}, _rubric_contract())
    assert contract.percentage == Decimal("0")


def test_gate_collect_all_violations():
    """Gate should report all violations in one raise, not fail-fast."""
    draft = _draft()
    overrides = {
        "nonexistent_1": TeacherOverride(points_awarded=Decimal("1")),
        "nonexistent_2": TeacherOverride(points_awarded=Decimal("2")),
    }
    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, overrides, _rubric_contract())

    assert len(exc_info.value.violations) == 2
