"""
ContractCompiler regression tests — S6 §4 upstream fix.

Asserts that example_solution, trace_tables, and context_tables on Question
are NOT stripped during compilation. These fields must survive into the frozen
GradingRubricContract so the GraderAgent can use them for grading.

Background: before the S6 fix, the compiler explicitly zeroed out these three
fields on every Question. SubQuestion.example_solution was already kept; the fix
makes Question-level fields symmetric.
"""
from decimal import Decimal

from app.schemas.ontology_types import (
    Criterion,
    ExtractRubricResponse,
    Question,
    QuestionType,
)
from app.services.contract_compiler import ContractCompiler


def _response_with_context(
    example_solution="x = 42",
    trace_tables=None,
    context_tables=None,
):
    """
    Minimal valid ExtractRubricResponse with grading-context fields populated.
    Criterion is aligned (skill_targets non-empty) so no alignment warnings fire,
    keeping acknowledged_warnings=[] valid.
    """
    tables = trace_tables or [{"headers": ["a"], "rows": [{"a": 1}], "row_count": 1}]
    ctx_tables = context_tables or [{"headers": ["x"], "rows": [], "row_count": 0}]

    crit = Criterion(
        criterion_id="q1.c0",
        index=0,
        description="test criterion",
        points=Decimal("100"),
        skill_targets=["some.skill"],  # is_aligned=True → no narrowness_issue warning
    )
    q = Question(
        question_id="q1",
        question_type=QuestionType.SHORT_ANSWER,
        total_points=Decimal("100"),
        criteria=[crit],
        sub_questions=[],
        example_solution=example_solution,
        trace_tables=tables,
        context_tables=ctx_tables,
    )
    return ExtractRubricResponse(
        rubric_id="test-rubric",
        rubric_name="Test Rubric",
        subject="computer_science",
        total_points=Decimal("100"),
        questions=[q],
    )


def test_compiled_question_retains_example_solution():
    """example_solution must survive into the contract after the S6 fix."""
    contract = ContractCompiler().compile(
        _response_with_context(), acknowledged_warnings=[]
    )
    assert contract.questions[0].example_solution == "x = 42", (
        "example_solution was stripped — the S6 fix to contract_compiler.py was not applied"
    )


def test_compiled_question_retains_trace_tables():
    """trace_tables must survive into the contract after the S6 fix."""
    tables = [{"headers": ["step", "val"], "rows": [{"step": 1, "val": 0}], "row_count": 1}]
    contract = ContractCompiler().compile(
        _response_with_context(trace_tables=tables), acknowledged_warnings=[]
    )
    assert contract.questions[0].trace_tables == tables, (
        "trace_tables was stripped — the S6 fix to contract_compiler.py was not applied"
    )


def test_compiled_question_retains_context_tables():
    """context_tables must survive into the contract after the S6 fix."""
    tables = [{"headers": ["col"], "rows": [{"col": "v"}], "row_count": 1}]
    contract = ContractCompiler().compile(
        _response_with_context(context_tables=tables), acknowledged_warnings=[]
    )
    assert contract.questions[0].context_tables == tables, (
        "context_tables was stripped — the S6 fix to contract_compiler.py was not applied"
    )


def test_proposals_still_stripped():
    """proposals must still be stripped (editor-only, never reaches the contract)."""
    from app.schemas.ontology_types import Criterion, Question, QuestionType

    crit = Criterion(
        criterion_id="q1.c0",
        index=0,
        description="crit",
        points=Decimal("100"),
        skill_targets=["s"],
    )
    q = Question(
        question_id="q1",
        question_type=QuestionType.SHORT_ANSWER,
        total_points=Decimal("100"),
        criteria=[crit],
        sub_questions=[],
        proposals={"some": "data"},
    )
    response = ExtractRubricResponse(
        rubric_id="r",
        total_points=Decimal("100"),
        questions=[q],
    )
    contract = ContractCompiler().compile(response, acknowledged_warnings=[])
    assert contract.questions[0].proposals is None, (
        "proposals must be stripped at compilation — it is editor-only metadata"
    )
