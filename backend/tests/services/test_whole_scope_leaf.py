"""WHOLE-SCOPE (owner-ruled 2026-10-25): a scored leaf with NO criteria is one unit.

"No criteria" must never mean "the criteria sum to 0". INV-1/INV-2 are vacuous at such
a leaf, the Draft stays faithful (empty `criteria`), and the CONTRACT carries one
whole-scope criterion worth the leaf's declared points — because every downstream
stage grades and overrides TERMINALS, and a scope with none would be unearnable.
"""
from decimal import Decimal

import pytest

from app.schemas.ontology_types import (
    CompilationError,
    Criterion,
    ExtractRubricResponse,
    Question,
    QuestionType,
    SubQuestion,
)
from app.services.contract_compiler import ContractCompiler
from app.services.docx_v3.pedagogical_mistakes import _check_point_sums


def _crit(cid: str, pts: str) -> Criterion:
    return Criterion(criterion_id=cid, index=0, description="רכיב", points=Decimal(pts),
                     skill_targets=["s"])


def _draft() -> ExtractRubricResponse:
    """q1: א has a table (5), ב has NONE (5), ג is a parent whose child 1 has none (10).
    q2: a direct question with no criteria at all (20). Total 40."""
    q1 = Question(
        question_id="q1", question_type=QuestionType.SHORT_ANSWER, total_points=Decimal("20"),
        criteria=[],
        sub_questions=[
            SubQuestion(sub_question_id="א", index=0, text="a", points=Decimal("5"),
                        criteria=[_crit("q1.א.c0", "5")]),
            SubQuestion(sub_question_id="ב", index=1, text="b", points=Decimal("5"), criteria=[]),
            SubQuestion(sub_question_id="ג", index=2, text="", points=Decimal("10"), criteria=[],
                        sub_questions=[SubQuestion(sub_question_id="1", index=0, text="c1",
                                                   points=Decimal("10"), criteria=[])]),
        ],
    )
    q2 = Question(question_id="q2", question_type=QuestionType.SHORT_ANSWER,
                  total_points=Decimal("20"), criteria=[], sub_questions=[])
    return ExtractRubricResponse(rubric_id="r-whole", rubric_name="t", subject="computer_science",
                                 total_points=Decimal("40"), questions=[q1, q2])


def test_criteria_less_leaves_compile_and_the_contract_gets_one_whole_scope_criterion():
    draft = _draft()
    contract = ContractCompiler().compile(draft, acknowledged_warnings=[])

    q1, q2 = contract.questions
    b = q1.sub_questions[1]
    assert [(c.criterion_id, c.points) for c in b.criteria] == [("q1.ב.c0", Decimal("5"))]
    nested = q1.sub_questions[2].sub_questions[0]
    assert [(c.criterion_id, c.points) for c in nested.criteria] == [("q1.ג.1.c0", Decimal("10"))]
    assert q1.sub_questions[2].criteria == []          # a parent never gets one
    assert [(c.criterion_id, c.points) for c in q2.criteria] == [("q2.c0", Decimal("20"))]
    assert q1.sub_questions[0].criteria[0].criterion_id == "q1.א.c0"   # untouched
    assert contract.total_points == Decimal("40")

    # The Draft is faithful and NOT mutated (nested nodes are shared with the input).
    assert draft.questions[0].sub_questions[1].criteria == []
    assert draft.questions[0].sub_questions[2].sub_questions[0].criteria == []
    assert draft.questions[1].criteria == []


def test_whole_scope_uid_is_deterministic_so_a_resave_does_not_rebuild_the_plan():
    a = ContractCompiler().compile(_draft(), acknowledged_warnings=[])
    b = ContractCompiler().compile(_draft(), acknowledged_warnings=[])
    assert a.questions[1].criteria[0].uid == b.questions[1].criteria[0].uid
    assert a.questions[0].sub_questions[1].criteria[0].uid != a.questions[1].criteria[0].uid


def test_unscored_leaf_without_criteria_stays_empty():
    draft = _draft()
    draft.questions[0].sub_questions[1].points = Decimal("0")
    draft.questions[0].total_points = Decimal("15")
    draft.total_points = Decimal("35")
    contract = ContractCompiler().compile(draft, acknowledged_warnings=[])
    assert contract.questions[0].sub_questions[1].criteria == []


def test_a_leaf_WITH_criteria_still_fires_inv2():
    draft = _draft()
    draft.questions[0].sub_questions[0].points = Decimal("6")
    draft.questions[0].total_points = Decimal("21")
    draft.total_points = Decimal("41")
    with pytest.raises(CompilationError) as e:
        ContractCompiler().compile(draft, acknowledged_warnings=[])
    assert [a.invariant for a in e.value.errors] == ["INV-2"]


def test_no_point_sum_advisory_proposes_zero_for_a_criteria_less_leaf():
    assert _check_point_sums(_draft()) == []
