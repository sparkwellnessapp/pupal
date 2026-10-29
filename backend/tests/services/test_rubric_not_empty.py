"""
INV-7 RubricNotEmpty — zero mocks, pure.

Every point-sum invariant is vacuous on an empty rubric (0 questions, declared 0
⇒ INV-4 reads 0 == 0), so before INV-7 an empty draft compiled into a "valid"
contract — which is exactly what production saved for three teachers,
2026-10-25..29. The API-level half lives in tests/api/test_empty_rubric.py.
"""
from decimal import Decimal

import pytest

from app.models.grading import Rubric
from app.schemas.ontology_types import (
    CompilationError,
    Criterion,
    ExtractRubricResponse,
    Question,
    QuestionType,
)
from app.services.contract_compiler import ContractCompiler
from app.services.transcription.two_phase.parsing import spec_from_rubric_draft_data


def _rubric(questions, total):
    return ExtractRubricResponse(
        rubric_id="r", rubric_name="מחוון", subject="computer_science",
        total_points=Decimal(total), questions=questions,
    )


def _question(points: str) -> Question:
    return Question(
        question_id="q1", question_type=QuestionType.SHORT_ANSWER,
        total_points=Decimal(points), sub_questions=[],
        criteria=[Criterion(criterion_id="q1.c0", index=0, description="c",
                            points=Decimal(points), skill_targets=["s"])],
    )


def _inv7(exc: CompilationError):
    return [a for a in exc.errors if a.invariant == "INV-7"]


def test_an_empty_rubric_does_not_compile():
    with pytest.raises(CompilationError) as exc:
        ContractCompiler().compile(_rubric([], "0"), acknowledged_warnings=[])
    [err] = _inv7(exc.value)
    assert (err.expected, err.actual, err.target_id) == ("≥1", "0", None)
    assert err.message_he  # the teacher reads Hebrew on the rejection surface


def test_an_empty_rubric_with_a_declared_total_still_names_INV_7():
    # INV-4 also fires here (0 ≠ 100); INV-7 must be among the reasons, because
    # «achievable differs from declared» sends her hunting for a points error.
    with pytest.raises(CompilationError) as exc:
        ContractCompiler().compile(_rubric([], "100"), acknowledged_warnings=[])
    assert _inv7(exc.value)


def test_a_question_cannot_be_worth_zero_so_one_question_is_enough():
    # Why INV-7 checks only the count: the type already refuses a 0-point
    # question, so a non-empty rubric always has a positive denominator.
    with pytest.raises(ValueError):
        Question(question_id="q1", question_type=QuestionType.SHORT_ANSWER,
                 total_points=Decimal("0"), sub_questions=[], criteria=[])


def test_a_real_rubric_is_untouched_by_INV_7():
    contract = ContractCompiler().compile(_rubric([_question("10")], "10"),
                                          acknowledged_warnings=[])
    assert len(contract.questions) == 1


@pytest.mark.parametrize("contract_json, expected", [
    (None, False),
    ({}, False),
    ({"questions": []}, False),
    ({"questions": [{"question_id": "q1"}]}, True),
])
def test_rubric_has_questions_reads_the_contract(contract_json, expected):
    r = Rubric(contract_json=contract_json, needs_recompilation=False)
    assert r.has_questions is expected
    assert r.can_grade is (expected and contract_json is not None)


def test_the_spec_parser_says_EMPTY_rather_than_missing():
    # 2026-10-29: the old message claimed the 'questions' list was missing while
    # listing 'questions' among the keys it found.
    with pytest.raises(ValueError, match="EMPTY"):
        spec_from_rubric_draft_data({"questions": [], "name": "x"}, name="rubric")
    with pytest.raises(ValueError, match="expected a top-level 'questions' list"):
        spec_from_rubric_draft_data({"name": "x"}, name="rubric")
