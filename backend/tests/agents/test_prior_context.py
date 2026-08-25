# -*- coding: utf-8 -*-
"""
PR-G1 v2 pin tests (RATIFIED 2026-08-25) — the prefix-context seam.

(i)   compiler prefix logic: order, prefix-only, direct/first-sub empty
(ii)  off-path byte-equality: flag off => rendered prompt byte-identical to
      the pre-change renderer (sha256 pinned from the live dan_basiuk q1.ב
      scope, captured 2026-08-25 BEFORE the seam landed)
(iii) on-path render: all four ruled fields, ruled order, the Hebrew header
(iv)  version-suffix mapping: grader-v2 off / grader-v2+priorctx on
(v)   OV-1 overlap-legality pin (owner ruling recorded in the test body)

Zero API calls.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from app.schemas.ontology_types import (
    Criterion,
    GradingRubricContract,
    NumericPolicy,
    Question,
    SubQuestion,
)
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer
from app.services.gradable_compiler import compile as compile_gradable

FLAG = "GRADER_PRIOR_CONTEXT_ENABLED"

# Captured 2026-08-25 from build_user_message(dan_basiuk q1.ב) BEFORE the seam
# landed — the off-path byte-identity pin [PR-G1 item 3].
PRE_CHANGE_SHA256 = "c575112f6d85237e5946cff8b5cbee601b6d37f8f3c331dbb4502648d1a9b95a"

HEADER = "חלקים קודמים — להקשר בלבד: אין לנקד אותם ואין לצטט מתוכם"


def _contract() -> GradingRubricContract:
    """q1 with parts א/ב/ג (א has an example solution) + direct-criteria q2."""
    def crit(cid: str, pts: str) -> Criterion:
        return Criterion(criterion_id=cid, index=0,
                         description=f"criterion {cid}", points=Decimal(pts))
    q1 = Question(
        question_id="q1", total_points=Decimal("9"),
        question_text="the parent stem shared by all parts",
        sub_questions=[
            SubQuestion(sub_question_id="א", index=0, points=Decimal("3"),
                        text="part alef task", example_solution="alef model answer",
                        criteria=[crit("q1.א.c0", "3")]),
            SubQuestion(sub_question_id="ב", index=1, points=Decimal("3"),
                        text="part bet task", criteria=[crit("q1.ב.c0", "3")]),
            SubQuestion(sub_question_id="ג", index=2, points=Decimal("3"),
                        text="part gimel task", criteria=[crit("q1.ג.c0", "3")]),
        ],
    )
    q2 = Question(question_id="q2", total_points=Decimal("4"),
                  criteria=[crit("q2.c0", "4")])
    return GradingRubricContract(
        contract_version="prior-ctx-test", rubric_id="prior-ctx",
        subject="computer_science", numeric_policy=NumericPolicy(),
        total_points=Decimal("13"), questions=[q1, q2],
    )


def _transcription() -> TranscriptionContract:
    """Answers for א and ג; ב deliberately missing (answer_missing prior)."""
    return TranscriptionContract(
        contract_version="prior-ctx-tr",
        answers=[
            TranscriptionContractAnswer(question_number=1, sub_question_id="א",
                                        answer_text="student wrote alef"),
            TranscriptionContractAnswer(question_number=1, sub_question_id="ג",
                                        answer_text="student wrote gimel"),
            TranscriptionContractAnswer(question_number=2, sub_question_id=None,
                                        answer_text="student wrote q2"),
        ],
    )


def _scopes():
    gradable = compile_gradable(_contract(), _transcription())
    return {(s.question_id, s.sub_question_id): s for s in gradable.scopes}


# ---------------------------------------------------------------------------
# (i) compiler prefix logic [PR-G1 item 2]
# ---------------------------------------------------------------------------

def test_compiler_prefix_only_document_order():
    s = _scopes()
    # first sub-question and direct-criteria question: empty
    assert s[("q1", "א")].prior_parts == []
    assert s[("q2", None)].prior_parts == []
    # ב sees exactly [א], with the ruled 4-field payload
    (pa,) = s[("q1", "ב")].prior_parts
    assert pa.sub_question_id == "א"
    assert pa.sub_question_text == "part alef task"
    assert pa.example_solution == "alef model answer"
    assert pa.student_answer_text == "student wrote alef"
    assert pa.answer_missing is False
    # ג sees [א, ב] in document order; ב is answer-missing — prefix-only,
    # never current, never subsequent
    priors = s[("q1", "ג")].prior_parts
    assert [p.sub_question_id for p in priors] == ["א", "ב"]
    assert priors[1].answer_missing is True
    assert priors[1].student_answer_text is None
    # ruled exclusions: no criteria, no awarded points on the context object
    assert not hasattr(priors[0], "criteria")
    assert not hasattr(priors[0], "points_awarded")


# ---------------------------------------------------------------------------
# (ii) off-path byte-equality [PR-G1 item 3]
# ---------------------------------------------------------------------------

def test_flag_off_prompt_byte_identical_to_prechange(monkeypatch):
    from app.agents.grader.prompt import build_user_message
    from tests.grading_eval_suite.fixtures import load_bundle
    monkeypatch.delenv(FLAG, raising=False)
    b = load_bundle("dan_basiuk", require_gt=False)
    scope = next(x for x in b.gradable_test.scopes
                 if x.question_id == "q1" and x.sub_question_id == "ב")
    msg = build_user_message(scope)
    assert hashlib.sha256(msg.encode("utf-8")).hexdigest() == PRE_CHANGE_SHA256, (
        "flag-off render drifted from the pre-change renderer — the off path "
        "must be byte-identical to grader-v2 without the seam")


# ---------------------------------------------------------------------------
# (iii) on-path render [PR-G1 item 3]
# ---------------------------------------------------------------------------

def test_flag_on_renders_priors_in_ruled_order(monkeypatch):
    from app.agents.grader.prompt import build_user_message
    monkeypatch.setenv(FLAG, "1")
    s = _scopes()
    msg = build_user_message(s[("q1", "ג")])
    assert HEADER in msg
    # exam reading order: parent stem -> priors -> current part -> GRADE THESE
    i_stem = msg.index("the parent stem shared by all parts")
    i_hdr = msg.index(HEADER)
    i_alef_text = msg.index("part alef task")
    i_alef_sol = msg.index("alef model answer")
    i_alef_ans = msg.index("student wrote alef")
    i_bet_text = msg.index("part bet task")
    i_missing = msg.index("«לא נענה»")             # ב has no answer
    i_current = msg.index("part gimel task")
    i_grade = msg.index("GRADE THESE")
    assert (i_stem < i_hdr < i_alef_text < i_alef_sol < i_alef_ans
            < i_bet_text < i_missing < i_current < i_grade)
    # and the flag-on/empty-priors case renders exactly like flag-off
    msg_alef_on = build_user_message(s[("q1", "א")])
    monkeypatch.delenv(FLAG, raising=False)
    msg_alef_off = build_user_message(s[("q1", "א")])
    assert msg_alef_on == msg_alef_off


# ---------------------------------------------------------------------------
# (iv) version-suffix mapping [PR-G1 item 4]
# ---------------------------------------------------------------------------

def test_version_is_pure_function_of_code_and_flag(monkeypatch):
    from app.agents.grader.prompt import GRADING_PROMPT_VERSION, effective_prompt_version
    assert GRADING_PROMPT_VERSION == "grader-v2"
    monkeypatch.delenv(FLAG, raising=False)
    assert effective_prompt_version() == "grader-v2"
    monkeypatch.setenv(FLAG, "1")
    assert effective_prompt_version() == "grader-v2+priorctx"


# ---------------------------------------------------------------------------
# (v) OV-1 overlap-legality pin
# ---------------------------------------------------------------------------

def test_ov1_identical_span_quoted_by_two_terminals_is_legal():
    """OV-1 (owner ruling, 2026-08-25): quote validation is an EXISTENCE check,
    never an exclusivity check. Cross-sub-question overlap is unconditionally
    legal by construction (each scope validates against its own answer text);
    within-scope overlap is affirmed legal for v0 — two terminals may cite the
    identical answer span and both validate exact with zero flags. Any future
    within-scope constraint requires an owner ruling, changes this pin
    deliberately, and starts as a Tier-3 diagnostic counter, never a validity
    gate."""
    from app.agents.grader.schemas import QuestionGradingResponse, TerminalGrade
    from app.agents.grader.validator import validate_scope_grading
    from app.schemas.ontology_types import QuoteValidationStatus
    s = _scopes()
    scope = s[("q2", None)]
    span = "student wrote q2"
    resp = QuestionGradingResponse(grades=[
        TerminalGrade(terminal_criterion_id="q2.c0", quote_text=span,
                      reasoning="נימוק", points_awarded=4.0, confidence=0.9),
    ])
    # single-terminal scope: validate the same span twice via two scopes'
    # criteria is impossible here, so pin the two-terminal case on q1.א+shared
    # span with a two-criterion synthetic scope:
    from app.schemas.gradable import GradableCriterion, GradableScope
    two = GradableScope(
        scope_kind="direct", question_id="q9", sub_question_id=None,
        criteria=[
            GradableCriterion(criterion_id="q9.c0", description="first facet",
                              points=Decimal("2")),
            GradableCriterion(criterion_id="q9.c1", description="second facet",
                              points=Decimal("2")),
        ],
        points=Decimal("4"), student_answer_text="the one shared span of text",
        alignment="matched",
    )
    resp2 = QuestionGradingResponse(grades=[
        TerminalGrade(terminal_criterion_id="q9.c0",
                      quote_text="the one shared span of text",
                      reasoning="נימוק", points_awarded=2.0, confidence=0.9),
        TerminalGrade(terminal_criterion_id="q9.c1",
                      quote_text="the one shared span of text",
                      reasoning="נימוק", points_awarded=2.0, confidence=0.9),
    ])
    result = validate_scope_grading(resp2, two, NumericPolicy())
    grades = {g.terminal_id: g for g in result.validated_grades}
    for tid in ("q9.c0", "q9.c1"):
        g = grades[tid]
        assert g.evidence_quote is not None
        assert g.evidence_quote.validation_status == QuoteValidationStatus.EXACT
        assert g.flags == []
    assert result.annotations == []
