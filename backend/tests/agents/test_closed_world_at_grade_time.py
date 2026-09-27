"""CWV-1 ClosedWorldAtGradeTime · CWV-2 ConsequenceNotCause · CWV-6 TransliterationRecovery.

A model verdict addressed to an id outside the grade's closed world is handled
BEFORE the draft is written: RECOVERED onto its one real id when it is provably
a romanisation of it (CWV-6, owner-ruled 2026-09-27), dropped otherwise. Either
way it is recorded as a structured scope-level `flag` (the eval signal, §6) and
never becomes an ERROR — nothing on the review screen could resolve one.

The production case (graded_test 271813b4, 2026-09-24): the plan said
`q1.א.1.c0.k1`, the verifier answered `q1.a.1.c0.k1`. The stray was dropped, the
real 12-point check priced as "no verdict", and an ERROR made the draft
unapprovable. Under CWV-6 that answer is simply graded.

The ONE function is `validator.strip_out_of_world`; both graders call it.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import (
    PlanCheck, ScopeVerificationResponse, TerminalPlan,
)
from app.agents.grader.schemas import QuestionGradingResponse, TerminalGrade
from app.agents.grader.validator import (
    recover_transliterated_id, strip_out_of_world, validate_scope_grading,
)
from app.schemas.gradable import GradableCriterion, GradableScope
from app.schemas.ontology_types import AnnotationSeverity, FlagReason, NumericPolicy

from .test_grader_v5_agent import _agent, _gradable, _plan, _verdict

ANSWER = "the student wrote a loop here\nand a null check there"
REAL = "q1.א.1.c0.k1"
ROMANISED = "q1.a.1.c0.k1"


def _hebrew_scope():
    return GradableScope(
        scope_kind="sub_question", question_id="q1", sub_question_id="א.1",
        criteria=[GradableCriterion(criterion_id="q1.א.1.c0",
                                    description="טבלת מעקב", points=Decimal("12"))],
        points=Decimal("12"), student_answer_text=ANSWER, alignment="matched")


def _hebrew_plan():
    return _plan([TerminalPlan(terminal_id="q1.א.1.c0", points_possible=Decimal("12"),
                               checks=[PlanCheck(check_id=REAL,
                                                 description_he="כל התאים בטבלה נכונים",
                                                 kind="required", points=Decimal("12"))])])


def _reasons(flags):
    return [f.reason for f in flags]


# ── CWV-6: the interpreter, pure ─────────────────────────────────────────────

def test_recovers_the_production_case():
    assert recover_transliterated_id(ROMANISED, {REAL}) == REAL


@pytest.mark.parametrize("latin,hebrew", [
    ("a", "א"), ("b", "ב"), ("v", "ב"), ("c", "ג"), ("g", "ג"), ("d", "ד"),
    ("e", "ה"), ("h", "ה"), ("z", "ז"), ("ch", "ח"), ("t", "ט"), ("y", "י"),
    ("B", "ב"),
])
def test_accepts_position_and_sound_spellings_of_the_right_letter(latin, hebrew):
    assert recover_transliterated_id(f"q1.{latin}.c0.k1", {f"q1.{hebrew}.c0.k1"}) \
        == f"q1.{hebrew}.c0.k1"


def test_refuses_a_letter_that_does_not_spell_the_real_label():
    assert recover_transliterated_id("q1.b.c0.k1", {"q1.א.c0.k1"}) is None


def test_refuses_when_any_ascii_segment_differs():
    """The model copies c0/k1 faithfully; if those differ it is not a
    transliteration, it is a different check."""
    assert recover_transliterated_id("q1.a.c0.k2", {"q1.א.c0.k1"}) is None
    assert recover_transliterated_id("q2.a.c0.k1", {"q1.א.c0.k1"}) is None


def test_refuses_when_two_real_ids_fit():
    """`h` spells both ה (by sound) and ח (by position): ambiguous, so no guess."""
    assert recover_transliterated_id("q1.h.c0.k1", {"q1.ה.c0.k1", "q1.ח.c0.k1"}) is None


def test_refuses_a_segment_that_is_not_a_single_hebrew_letter():
    assert recover_transliterated_id("q1.ab.c0.k1", {"q1.אב.c0.k1"}) is None
    assert recover_transliterated_id("q1.x.c0.k1", {"q1.1.c0.k1"}) is None


def test_an_exact_id_is_not_a_recovery():
    assert recover_transliterated_id(REAL, {REAL}) is None


# ── CWV-1: the ONE function, pure ────────────────────────────────────────────

def test_strip_keeps_known_drops_unknown_in_order():
    kept, flags, annotations = strip_out_of_world(
        ["c1.k1", "ghost.k9", "c1.k2"], key=lambda i: i,
        known={"c1.k1", "c1.k2"}, scope_id="q1")
    assert kept == ["c1.k1", "c1.k2"]
    assert _reasons(flags) == [FlagReason.CLOSED_WORLD_VIOLATION]
    assert "ghost.k9" in flags[0].message          # the eval signal keeps the id
    assert [a.severity for a in annotations] == [AnnotationSeverity.INFO]
    assert annotations[0].annotation_type == "closed_world_violation"
    assert annotations[0].target_id == "q1"       # anchored to a REAL scope


def test_strip_is_a_noop_on_a_clean_answer():
    kept, flags, annotations = strip_out_of_world(
        ["a", "b"], key=lambda i: i, known={"a", "b"}, scope_id="q1")
    assert kept == ["a", "b"] and flags == [] and annotations == []


def test_strip_recovers_silently_when_given_a_rekey():
    kept, flags, annotations = strip_out_of_world(
        [ROMANISED], key=lambda i: i, known={REAL}, scope_id="q1.א.1",
        rekey=lambda _i, real: real)
    assert kept == [REAL]
    assert _reasons(flags) == [FlagReason.CHECK_ID_RECOVERED]
    assert annotations == []                       # she is not told (ruling)


def test_strip_never_recovers_onto_a_check_that_answered_for_itself():
    """Condition 4: the real id already has its own verdict — the romanised one
    is a duplicate, never a second opinion that could overwrite it."""
    kept, flags, _ = strip_out_of_world(
        [ROMANISED, REAL], key=lambda i: i, known={REAL}, scope_id="q1.א.1",
        rekey=lambda _i, real: real)
    assert kept == [REAL]
    assert _reasons(flags) == [FlagReason.CLOSED_WORLD_VIOLATION]


# ── v5: the production shape ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_v5_the_production_case_is_graded_normally():
    """CWV-6 end to end: the romanised verdict is priced on the real check, and
    nothing about it reaches the teacher."""
    resp = ScopeVerificationResponse(verdicts=[_verdict(ROMANISED, "met")])
    draft = await _agent(_hebrew_plan(), [resp]).grade(_gradable([_hebrew_scope()]))

    scope = draft.scope_outcomes[0]
    assert scope.points_awarded == Decimal("12")
    check = scope.criterion_outcomes[0].checks[0]
    assert check.check_id == REAL and check.verdict == "met"
    assert _reasons(scope.flags) == [FlagReason.CHECK_ID_RECOVERED]
    assert not [a for a in draft.annotations
                if a.annotation_type in ("closed_world_violation", "unverified_check")]


@pytest.mark.asyncio
async def test_v5_a_stray_beside_a_complete_answer_is_dropped_not_an_error():
    """H1: a duplicate stray beside the real verdict — nothing is missing."""
    resp = ScopeVerificationResponse(verdicts=[
        _verdict(REAL, "met"), _verdict(ROMANISED, "not_met")])
    draft = await _agent(_hebrew_plan(), [resp]).grade(_gradable([_hebrew_scope()]))

    assert not [a for a in draft.annotations if a.severity == AnnotationSeverity.ERROR]
    scope = draft.scope_outcomes[0]
    assert _reasons(scope.flags) == [FlagReason.CLOSED_WORLD_VIOLATION]
    assert scope.points_awarded == Decimal("12")    # the REAL verdict priced


@pytest.mark.asyncio
async def test_v5_an_unrecoverable_misaddress_leaves_the_real_check_undecided():
    """H4 without a provable repair: the real check has no verdict. It reaches
    her as a no-verdict check (the pricer's `unverified_check`, keyed by check
    id), priced 0 until she decides it — never an ERROR she could not clear."""
    resp = ScopeVerificationResponse(verdicts=[_verdict("q1.א.1.c9.k1", "met")])
    draft = await _agent(_hebrew_plan(), [resp]).grade(_gradable([_hebrew_scope()]))

    assert not [a for a in draft.annotations if a.severity == AnnotationSeverity.ERROR]
    no_verdict = [a for a in draft.annotations if a.annotation_type == "unverified_check"]
    assert [a.metadata["check_id"] for a in no_verdict] == [REAL]
    scope = draft.scope_outcomes[0]
    assert _reasons(scope.flags) == [FlagReason.CLOSED_WORLD_VIOLATION]
    check = scope.criterion_outcomes[0].checks[0]
    assert check.check_id == REAL and check.verdict == "not_met"
    assert scope.points_awarded == Decimal("0")


# ── v3 (the rollback grader) goes through the same function ──────────────────

def _v3_scope(criterion_id="c1"):
    return GradableScope(
        scope_kind="direct", question_id="q1",
        criteria=[GradableCriterion(criterion_id=criterion_id, description="c",
                                    points=Decimal("5"))],
        points=Decimal("5"), student_answer_text="the student answer text",
        alignment="matched")


def _grade(tid, pts):
    return TerminalGrade(terminal_criterion_id=tid, points_awarded=pts,
                         reasoning="ok", quote_text="", confidence=0.9)


def test_v3_extra_terminal_id_is_dropped_flagged_and_never_an_error():
    result = validate_scope_grading(
        QuestionGradingResponse(grades=[_grade("c1", 3.0), _grade("EXTRA", 5.0)]),
        _v3_scope(), NumericPolicy(precision=Decimal("0.25")))

    assert "EXTRA" not in [g.terminal_id for g in result.validated_grades]
    assert not [a for a in result.annotations if a.severity == AnnotationSeverity.ERROR]
    assert _reasons(result.scope_flags) == [FlagReason.CLOSED_WORLD_VIOLATION]


def test_v3_a_romanised_terminal_id_is_recovered_and_graded():
    result = validate_scope_grading(
        QuestionGradingResponse(grades=[_grade("q1.a.c0", 3.0)]),
        _v3_scope("q1.א.c0"), NumericPolicy(precision=Decimal("0.25")))

    graded = {g.terminal_id: g.points_awarded for g in result.validated_grades}
    assert graded == {"q1.א.c0": Decimal("3")}
    assert _reasons(result.scope_flags) == [FlagReason.CHECK_ID_RECOVERED]
    assert not [a for a in result.annotations
                if a.annotation_type in ("closed_world_violation", "ungraded_criterion")]
