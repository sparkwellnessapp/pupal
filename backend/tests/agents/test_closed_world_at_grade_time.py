"""CWV-1 ClosedWorldAtGradeTime / CWV-2 ConsequenceNotCause — the grade-time half.

A model verdict addressed to an id outside the grade's closed world is dropped
BEFORE the draft is written, recorded as a structured scope-level `flag` (the
eval signal, §6) plus a non-blocking INFO annotation — never an ERROR, because
nothing the teacher can do on the review screen could ever resolve it.

The production case these reproduce (graded_test 271813b4, 2026-09-24): the plan
said `q1.א.1.c0.k1`, the verifier answered `q1.a.1.c0.k1` — a transliteration.
The stray verdict was dropped (correctly), the REAL check therefore priced as
"no verdict" (0 of 12), and an ERROR annotation made the draft unapprovable.

The ONE function is `validator.strip_out_of_world`; both graders call it.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import (
    PlanCheck, ScopeVerificationResponse, TerminalPlan,
)
from app.agents.grader.schemas import QuestionGradingResponse, TerminalGrade
from app.agents.grader.validator import validate_scope_grading
from app.schemas.gradable import GradableCriterion, GradableScope
from app.schemas.ontology_types import AnnotationSeverity, FlagReason, NumericPolicy

from .test_grader_v5_agent import _agent, _gradable, _plan, _verdict

ANSWER = "the student wrote a loop here\nand a null check there"


def _hebrew_scope():
    return GradableScope(
        scope_kind="sub_question", question_id="q1", sub_question_id="א.1",
        criteria=[GradableCriterion(criterion_id="q1.א.1.c0",
                                    description="טבלת מעקב", points=Decimal("12"))],
        points=Decimal("12"), student_answer_text=ANSWER, alignment="matched")


def _hebrew_plan():
    return _plan([TerminalPlan(terminal_id="q1.א.1.c0", points_possible=Decimal("12"),
                               checks=[PlanCheck(check_id="q1.א.1.c0.k1",
                                                 description_he="כל התאים בטבלה נכונים",
                                                 kind="required", points=Decimal("12"))])])


# ── the ONE function, pure ────────────────────────────────────────────────────

def test_strip_keeps_known_drops_unknown_in_order():
    from app.agents.grader.validator import strip_out_of_world
    items = ["c1.k1", "ghost.k9", "c1.k2"]
    kept, flags, annotations = strip_out_of_world(
        items, key=lambda i: i, known={"c1.k1", "c1.k2"}, scope_id="q1")
    assert kept == ["c1.k1", "c1.k2"]
    assert [f.reason for f in flags] == [FlagReason.CLOSED_WORLD_VIOLATION]
    assert "ghost.k9" in flags[0].message          # the eval signal keeps the id
    assert all(a.severity == AnnotationSeverity.INFO for a in annotations)
    assert all(a.annotation_type == "closed_world_violation" for a in annotations)


def test_strip_is_a_noop_on_a_clean_answer():
    from app.agents.grader.validator import strip_out_of_world
    kept, flags, annotations = strip_out_of_world(
        ["a", "b"], key=lambda i: i, known={"a", "b"}, scope_id="q1")
    assert kept == ["a", "b"] and flags == [] and annotations == []


# ── v5: the production shape ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_v5_stray_verdict_is_dropped_flagged_and_never_an_error():
    """H1: a pure stray alongside a complete answer — nothing is missing."""
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("q1.א.1.c0.k1", "met"),
        _verdict("q1.a.1.c0.k1", "met")])            # stray (transliterated)
    draft = await _agent(_hebrew_plan(), [resp]).grade(_gradable([_hebrew_scope()]))

    assert not [a for a in draft.annotations if a.severity == AnnotationSeverity.ERROR]
    scope = draft.scope_outcomes[0]
    assert any(f.reason == FlagReason.CLOSED_WORLD_VIOLATION for f in scope.flags)
    assert scope.points_awarded == Decimal("12")    # the real verdict priced


@pytest.mark.asyncio
async def test_v5_misaddressed_verdict_leaves_the_real_check_undecided():
    """H4 — the production row: the ONLY verdict was misaddressed, so the real
    check has none. It must reach her as a no-verdict check (the pricer's
    `unverified_check`, keyed by check id), priced 0 until she decides it —
    and the draft must carry no ERROR that she could never clear."""
    resp = ScopeVerificationResponse(verdicts=[_verdict("q1.a.1.c0.k1", "met")])
    draft = await _agent(_hebrew_plan(), [resp]).grade(_gradable([_hebrew_scope()]))

    assert not [a for a in draft.annotations if a.severity == AnnotationSeverity.ERROR]
    no_verdict = [a for a in draft.annotations if a.annotation_type == "unverified_check"]
    assert [a.metadata["check_id"] for a in no_verdict] == ["q1.א.1.c0.k1"]
    scope = draft.scope_outcomes[0]
    assert any(f.reason == FlagReason.CLOSED_WORLD_VIOLATION for f in scope.flags)
    check = scope.criterion_outcomes[0].checks[0]
    assert check.check_id == "q1.א.1.c0.k1" and check.verdict == "not_met"
    assert scope.points_awarded == Decimal("0")


# ── v3 (the rollback grader) goes through the same function ───────────────────

def test_v3_extra_terminal_id_is_dropped_flagged_and_never_an_error():
    scope = GradableScope(
        scope_kind="direct", question_id="q1",
        criteria=[GradableCriterion(criterion_id="c1", description="c",
                                    points=Decimal("5"))],
        points=Decimal("5"), student_answer_text="the student answer text",
        alignment="matched")
    response = QuestionGradingResponse(grades=[
        TerminalGrade(terminal_criterion_id="c1", points_awarded=3.0, reasoning="ok",
                      quote_text="", confidence=0.9),
        TerminalGrade(terminal_criterion_id="EXTRA", points_awarded=5.0,
                      reasoning="x", quote_text="", confidence=0.9)])
    result = validate_scope_grading(response, scope, NumericPolicy(precision=Decimal("0.25")))

    assert "EXTRA" not in [g.terminal_id for g in result.validated_grades]
    assert not [a for a in result.annotations if a.severity == AnnotationSeverity.ERROR]
    assert any(f.reason == FlagReason.CLOSED_WORLD_VIOLATION for f in result.scope_flags)
