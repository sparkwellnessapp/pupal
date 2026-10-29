"""
Settled point claims (owner-ruled 2026-10-29) — the compiler stops demanding an ack
for a `rubric_mismatch` WARNING that the current numbers falsify.

Prod incident: extraction annotated q3 «Σ criteria = 30, declared 40». The teacher
fixed the points and saved; the annotation stays in the draft (the faithful record),
and every later save of that rubric re-popped the warnings modal with the long-fixed
claim, because Step 5 acked every stored WARNING by id regardless of its truth.

Zero mocks — the compiler is pure.
"""
from decimal import Decimal

import pytest

from app.schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    CompilationError,
    Criterion,
    ExtractRubricResponse,
    Question,
    QuestionType,
    SelectionGroup,
    SubCriterion,
    SubQuestion,
    WarningsRequireAcknowledgment,
)
from app.services.contract_compiler import ContractCompiler


def _crit(cid: str, pts: str, subs=None) -> Criterion:
    return Criterion(criterion_id=cid, index=0, description="c", points=Decimal(pts),
                     sub_criteria=subs, skill_targets=["s"])


def _mismatch(target_id, message="אזהרה: סכום הנקודות אינו תואם") -> Annotation:
    return Annotation(annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
                      message=message, target_id=target_id)


def _rubric(q3_criteria, annotations, *, q1_total="60", selection_groups=()) -> ExtractRubricResponse:
    """q1 (nested: q1.א → q1.א.1), q3 (direct criteria). Totals: 60 + 40 = 100."""
    q1 = Question(
        question_id="q1", question_type=QuestionType.SHORT_ANSWER, total_points=Decimal(q1_total),
        criteria=[],
        sub_questions=[SubQuestion(
            sub_question_id="א", index=0, text="t", points=Decimal(q1_total), criteria=[],
            sub_questions=[SubQuestion(
                sub_question_id="1", index=0, text="t", points=Decimal(q1_total),
                criteria=[_crit("q1.א.1.c0", q1_total, subs=[
                    SubCriterion(sub_criterion_id="q1.א.1.c0.s0", index=0, description="s",
                                 points=Decimal(q1_total)),
                ])],
            )],
        )],
    )
    q3 = Question(question_id="q3", question_type=QuestionType.SHORT_ANSWER,
                  total_points=Decimal("40"), criteria=q3_criteria, sub_questions=[])
    total = Decimal(q1_total) + Decimal("40")
    return ExtractRubricResponse(
        rubric_id="r", rubric_name="R", subject="computer_science", total_points=total,
        questions=[q1, q3], annotations=list(annotations), selection_groups=list(selection_groups),
    )


FIXED_Q3 = [_crit("q3.c0", "18"), _crit("q3.c1", "22")]          # Σ 40 — she fixed it
BROKEN_Q3 = [_crit("q3.c0", "8"), _crit("q3.c1", "22")]          # Σ 30 — as extracted


def test_the_incident_a_fixed_question_mismatch_no_longer_gates_the_save():
    contract = ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch("q3")]), acknowledged_warnings=[])
    assert contract.total_points == Decimal("100")


def test_the_draft_keeps_the_annotation_the_compiler_only_stops_gating_on_it():
    draft = _rubric(FIXED_Q3, [_mismatch("q3")])
    ContractCompiler().compile(draft, acknowledged_warnings=[])
    assert [a.id for a in draft.annotations] == ["rubric_mismatch:q3"]


def test_a_still_broken_question_is_refused_by_the_invariant_not_waved_through():
    with pytest.raises(CompilationError) as e:
        ContractCompiler().compile(_rubric(BROKEN_Q3, [_mismatch("q3")]), acknowledged_warnings=[])
    assert any(a.invariant == "INV-1" for a in e.value.errors)


@pytest.mark.parametrize("target", ["q1", "q1.א", "q1.א.1", "q1.א.1.c0"])
def test_settles_at_every_node_shape_the_extractor_and_rescale_pass_anchor_to(target):
    ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch(target)]), acknowledged_warnings=[])


def test_a_claim_about_a_node_she_deleted_still_needs_her_ack():
    with pytest.raises(WarningsRequireAcknowledgment) as e:
        ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch("q9")]), acknowledged_warnings=[])
    assert [w.id for w in e.value.warnings] == ["rubric_mismatch:q9"]


def test_other_warning_types_still_need_her_ack():
    other = Annotation(annotation_type="review_flag", severity=AnnotationSeverity.WARNING,
                       message="m", target_id="q3")
    with pytest.raises(WarningsRequireAcknowledgment) as e:
        ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch("q3"), other]), acknowledged_warnings=[])
    assert [w.id for w in e.value.warnings] == [other.id]


def test_rubric_level_claim_settles_only_when_the_questions_now_sum_to_100():
    ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch(None)]), acknowledged_warnings=[])
    with pytest.raises(WarningsRequireAcknowledgment):
        # 50 + 40 = 90: the «not 100» claim is still true — a choice only she can confirm.
        ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch(None)], q1_total="50"),
                                   acknowledged_warnings=[])


def test_rubric_level_claim_is_never_settled_on_a_selection_exam():
    groups = [SelectionGroup(group_id="g1", choose_k=2, of_question_ids=["q1", "q3"])]
    with pytest.raises(WarningsRequireAcknowledgment):
        ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch(None)], selection_groups=groups),
                                   acknowledged_warnings=[])


def test_an_explicit_ack_still_works_for_an_unsettled_claim():
    ContractCompiler().compile(_rubric(FIXED_Q3, [_mismatch("q9")]),
                               acknowledged_warnings=["rubric_mismatch:q9"])
