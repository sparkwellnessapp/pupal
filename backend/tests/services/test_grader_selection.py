"""
The production grader seam under PLAN COMPILER v2's wiring (W-4).

The decision is a PURE function of config, tested with zero mocks and no
client construction. The plan is an ARGUMENT now (the runner resolves it from
grading_plans); the fit guard is retained as the second, independent check.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.grader_selection import build_grader, grader_kind_for


def _cfg(monkeypatch, **kw):
    import app.services.grader_selection as mod
    for k, v in kw.items():
        monkeypatch.setattr(mod.settings, k, v, raising=False)


def test_v5_for_every_rubric_by_default(monkeypatch):
    _cfg(monkeypatch, grader_architecture="v5")
    assert grader_kind_for(str(uuid4())) == "v5"
    assert grader_kind_for(None) == "v5"


def test_v3_only_under_the_rollback_knob(monkeypatch):
    """GRADER_ARCHITECTURE=v3 is the emergency rollback: every grade, the
    historical path, no data change."""
    _cfg(monkeypatch, grader_architecture="v3")
    assert grader_kind_for(str(uuid4())) == "v3"
    _cfg(monkeypatch, grader_architecture="V3")
    assert grader_kind_for(str(uuid4())) == "v3"


def test_v5_without_a_plan_is_a_loud_error_not_a_fallback(monkeypatch):
    """W-4 forbids the quiet lie: a v5 grade with no plan must fail naming the
    cause, never slide to v3 and look like a working system."""
    from app.schemas.ontology_types import NumericPolicy
    _cfg(monkeypatch, grader_architecture="v5", grader_model_key="claude-sonnet-5")
    with pytest.raises(ValueError) as ei:
        build_grader(str(uuid4()), NumericPolicy())
    assert "needs a GradingPlan" in str(ei.value)


def test_v5_without_a_model_key_is_a_loud_error(monkeypatch):
    from app.agents.grader.plan_schemas import GradingPlan
    from app.schemas.ontology_types import NumericPolicy
    _cfg(monkeypatch, grader_architecture="v5", grader_model_key=None)
    plan = GradingPlan(exam_id="x", plan_version="x/v1", rubric_contract_sha256="0" * 64, terminals=[])
    with pytest.raises(ValueError) as ei:
        build_grader(str(uuid4()), NumericPolicy(), plan=plan)
    assert "GRADER_MODEL_KEY" in str(ei.value)


def test_a_plan_that_does_not_fit_the_test_is_refused_before_any_spend(monkeypatch):
    """A ready plan is keyed by the contract's content hash, so it fits by
    construction — this is the SECOND, independent guard (OD-G1.4's lesson).
    Without it a mismatched plan surfaces as a KeyError inside every scope,
    after paying for all of them, reported as a grading failure rather than
    the wiring bug it is."""
    from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
    from app.schemas.gradable import GradableCriterion, GradableScope, GradableTest
    from app.schemas.ontology_types import NumericPolicy

    _cfg(monkeypatch, grader_architecture="v5", grader_model_key="claude-sonnet-5",
         grader_model_provider="anthropic")
    plan = GradingPlan(
        exam_id="wrong-exam", plan_version="wrong/v1", rubric_contract_sha256="0" * 64,
        terminals=[TerminalPlan(
            terminal_id="NOT_IN_THIS_TEST", points_possible=Decimal("5"),
            checks=[PlanCheck(check_id="NOT_IN_THIS_TEST.k1", description_he="x",
                              kind="required", points=Decimal("5"))])])
    scope = GradableScope(
        scope_kind="direct", question_id="q1", sub_question_id=None,
        criteria=[GradableCriterion(criterion_id="q1.c0", description="d",
                                    points=Decimal("5"), sub_criteria=None)],
        points=Decimal("5"), student_answer_text="answer", alignment="matched")
    test = GradableTest(rubric_contract_version="rc", transcription_contract_version="tc",
                        scopes=[scope], unmatched_transcription_answers=[],
                        total_points=Decimal("5"))
    with pytest.raises(ValueError) as ei:
        build_grader(str(uuid4()), NumericPolicy(), gradable_test=test, plan=plan)
    assert "does not fit" in str(ei.value)


def test_the_v3_branch_never_needs_a_plan(monkeypatch):
    from app.schemas.ontology_types import NumericPolicy
    _cfg(monkeypatch, grader_architecture="v3")
    agent = build_grader(str(uuid4()), NumericPolicy())
    assert type(agent).__name__ == "GraderAgent"
