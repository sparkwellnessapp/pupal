"""
GradableTest compiler unit tests — S6.

Pure function tests: zero mocks, zero DB. All Pydantic instances are constructed
directly. The compiler is deterministic, so the golden-path assertions are exact.

Test index (matches S6 PR spec §7):
  1.  Pass 1 — q{N} format matches by integer suffix
  2.  Pass 2 — q_{uid} format matches by positional index
  3.  Mixed formats — teacher-edited rubric resolves all questions
  4.  Sub-question separation — each sub-question gets its OWN answer (defect-fix)
  5.  Non-Hebrew sub_question_id — Latin letters match directly
  6.  answer_missing alignment — scope has criteria, no answer transcribed
  7.  Orphan answer — question_number beyond contract
  8.  Orphan sub-question — sub_question_id not in contract
  9.  Closed-world — direct-criteria scope carries only its own criteria
  10. Sub-question scopes — one per sub-question, answer_missing for unanswered
  11. sub_criteria carried to GradableCriterion
  12. Grading context carried (example_solution, trace_tables, context_tables,
      evaluation_guidance, notes)
  13. Decimal discipline preserved
  14. Determinism — same inputs → equal outputs
  15. Pinned versions in output
  16. Sub-question scopes carry parent question-level trace_tables/context_tables
  17. Compiler never raises on empty transcription
"""
from decimal import Decimal

import pytest

from app.schemas.ontology_types import (
    Criterion,
    GradingRubricContract,
    NumericPolicy,
    Question,
    QuestionType,
    SubCriterion,
    SubQuestion,
)
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer
from app.services import gradable_compiler


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _sub_criterion(scid: str, points: str = "5") -> SubCriterion:
    return SubCriterion(
        sub_criterion_id=scid, index=0, description="sc desc", points=Decimal(points)
    )


def _criterion(
    cid: str,
    points: str = "10",
    desc: str = "test criterion",
    guidance: str = None,
    notes: str = None,
    sub_criteria=None,
) -> Criterion:
    return Criterion(
        criterion_id=cid,
        index=0,
        description=desc,
        points=Decimal(points),
        evaluation_guidance=guidance,
        notes=notes,
        sub_criteria=sub_criteria,
    )


def _sub_question(
    sqid: str,
    points,
    criteria,
    index: int = 0,
    text: str = None,
    example_solution: str = None,
) -> SubQuestion:
    return SubQuestion(
        sub_question_id=sqid,
        index=index,
        points=Decimal(str(points)),
        criteria=criteria,
        text=text,
        example_solution=example_solution,
    )


def _question(
    qid: str,
    total,
    criteria=None,
    sub_questions=None,
    example_solution: str = None,
    trace_tables=None,
    context_tables=None,
) -> Question:
    return Question(
        question_id=qid,
        question_type=QuestionType.SHORT_ANSWER,
        total_points=Decimal(str(total)),
        criteria=criteria or [],
        sub_questions=sub_questions or [],
        example_solution=example_solution,
        trace_tables=trace_tables,
        context_tables=context_tables,
    )


def _contract(
    questions,
    rubric_id: str = "r1",
    subject: str = "cs",
    contract_version: str = "v-rubric",
) -> GradingRubricContract:
    return GradingRubricContract(
        contract_version=contract_version,
        rubric_id=rubric_id,
        subject=subject,
        numeric_policy=NumericPolicy(),
        total_points=sum(q.total_points for q in questions),
        questions=questions,
    )


def _transcription(answers, contract_version: str = "v-trans") -> TranscriptionContract:
    return TranscriptionContract(
        contract_version=contract_version,
        answers=[
            TranscriptionContractAnswer(
                question_number=qn, sub_question_id=sub, answer_text=text
            )
            for qn, sub, text in answers
        ],
    )


# ---------------------------------------------------------------------------
# Test 1 — Pass 1: q{N} format matches by integer suffix
# ---------------------------------------------------------------------------

def test_1_pass1_qN_format_matches_by_integer():
    r = _contract([
        _question("q1", 10, [_criterion("q1.c0")]),
        _question("q2", 10, [_criterion("q2.c0")]),
    ])
    t = _transcription([(1, None, "answer1"), (2, None, "answer2")])
    gt = gradable_compiler.compile(r, t)
    scopes = {s.question_id: s for s in gt.scopes}
    assert scopes["q1"].student_answer_text == "answer1"
    assert scopes["q2"].student_answer_text == "answer2"
    assert gt.unmatched_transcription_answers == []


# ---------------------------------------------------------------------------
# Test 2 — Pass 2: q_{uid} format matches by positional index
# ---------------------------------------------------------------------------

def test_2_pass2_uid_format_matches_by_position():
    r = _contract([
        _question("q_abc", 10, [_criterion("c1")]),
        _question("q_def", 10, [_criterion("c2")]),
    ])
    t = _transcription([(1, None, "first"), (2, None, "second")])
    gt = gradable_compiler.compile(r, t)
    scopes = {s.question_id: s for s in gt.scopes}
    assert scopes["q_abc"].student_answer_text == "first"
    assert scopes["q_def"].student_answer_text == "second"
    assert gt.unmatched_transcription_answers == []


# ---------------------------------------------------------------------------
# Test 3 — Mixed formats: teacher-edited rubric (q{N} + q_{uid} + q{N})
# ---------------------------------------------------------------------------

def test_3_mixed_formats_all_resolve():
    # q1 → regex (N=1), q_abc → positional (index=1 → N=2), q3 → regex (N=3)
    r = _contract([
        _question("q1",    10, [_criterion("c1")]),
        _question("q_abc", 10, [_criterion("c2")]),
        _question("q3",    10, [_criterion("c3")]),
    ])
    t = _transcription([(1, None, "a1"), (2, None, "a2"), (3, None, "a3")])
    gt = gradable_compiler.compile(r, t)
    scopes = {s.question_id: s for s in gt.scopes}
    assert scopes["q1"].student_answer_text == "a1"
    assert scopes["q_abc"].student_answer_text == "a2"
    assert scopes["q3"].student_answer_text == "a3"
    assert gt.unmatched_transcription_answers == []


# ---------------------------------------------------------------------------
# Test 4 — Sub-question separation (the defect-fix test)
# ---------------------------------------------------------------------------

def test_4_sub_question_each_gets_own_answer():
    """
    The central defect S6 fixes: sub-question answers must NOT collapse into one blob.
    Each sub-question scope must receive exactly its own answer.
    """
    sqs = [
        _sub_question("א", 20, [_criterion("q1.א.c0")]),
        _sub_question("ב", 20, [_criterion("q1.ב.c0")]),
    ]
    r = _contract([_question("q1", 40, sub_questions=sqs)])
    t = _transcription([(1, "א", "answer for alef"), (1, "ב", "answer for bet")])
    gt = gradable_compiler.compile(r, t)

    alef = next(s for s in gt.scopes if s.sub_question_id == "א")
    bet  = next(s for s in gt.scopes if s.sub_question_id == "ב")

    assert alef.student_answer_text == "answer for alef"
    assert bet.student_answer_text  == "answer for bet"
    # Core defect assertion: answers must not be collapsed / swapped
    assert alef.student_answer_text != bet.student_answer_text


# ---------------------------------------------------------------------------
# Test 5 — Non-Hebrew sub_question_id: Latin letters match directly
# ---------------------------------------------------------------------------

def test_5_latin_sub_question_id_matches_directly():
    sqs = [
        _sub_question("a", 10, [_criterion("c1")]),
        _sub_question("b", 10, [_criterion("c2")]),
    ]
    r = _contract([_question("q1", 20, sub_questions=sqs)])
    t = _transcription([(1, "a", "answer-a"), (1, "b", "answer-b")])
    gt = gradable_compiler.compile(r, t)

    a_scope = next(s for s in gt.scopes if s.sub_question_id == "a")
    b_scope = next(s for s in gt.scopes if s.sub_question_id == "b")
    assert a_scope.student_answer_text == "answer-a"
    assert b_scope.student_answer_text == "answer-b"


# ---------------------------------------------------------------------------
# Test 6 — alignment="answer_missing" when no transcription answer exists
# ---------------------------------------------------------------------------

def test_6_alignment_answer_missing():
    r = _contract([_question("q1", 10, [_criterion("c1")])])
    t = _transcription([])  # no answers at all
    gt = gradable_compiler.compile(r, t)

    assert len(gt.scopes) == 1
    assert gt.scopes[0].alignment == "answer_missing"
    assert gt.scopes[0].student_answer_text is None
    assert gt.unmatched_transcription_answers == []


# ---------------------------------------------------------------------------
# Test 7 — Orphan answer: question_number beyond contract
# ---------------------------------------------------------------------------

def test_7_orphan_answer_unknown_question_number():
    r = _contract([
        _question("q1", 10, [_criterion("c1")]),
        _question("q2", 10, [_criterion("c2")]),
    ])
    t = _transcription([(1, None, "a1"), (5, None, "a5")])  # q5 doesn't exist
    gt = gradable_compiler.compile(r, t)

    assert len(gt.unmatched_transcription_answers) == 1
    orphan = gt.unmatched_transcription_answers[0]
    assert orphan.question_number == 5
    assert orphan.answer_text == "a5"
    assert "position 5" in orphan.reason


# ---------------------------------------------------------------------------
# Test 8 — Orphan sub-question: sub_question_id not in contract
# ---------------------------------------------------------------------------

def test_8_orphan_sub_question_not_in_contract():
    sqs = [
        _sub_question("א", 20, [_criterion("c1")]),
        _sub_question("ב", 20, [_criterion("c2")]),
    ]
    r = _contract([_question("q1", 40, sub_questions=sqs)])
    t = _transcription([(1, "א", "ok"), (1, "ג", "orphan")])  # ג not in contract
    gt = gradable_compiler.compile(r, t)

    assert len(gt.unmatched_transcription_answers) == 1
    orphan = gt.unmatched_transcription_answers[0]
    assert orphan.sub_question_id == "ג"
    assert "ג" in orphan.reason
    assert "q1" in orphan.reason


# ---------------------------------------------------------------------------
# Test 9 — Closed-world: scope carries ONLY its own criteria, disjoint from others
# ---------------------------------------------------------------------------

def test_9_direct_criteria_scope_is_closed_world():
    r = _contract([
        _question("q1", 10, [_criterion("q1.c0"), _criterion("q1.c1")]),
        _question("q2", 10, [_criterion("q2.c0")]),
    ])
    t = _transcription([(1, None, "a1"), (2, None, "a2")])
    gt = gradable_compiler.compile(r, t)

    q1_scope = next(s for s in gt.scopes if s.question_id == "q1")
    q2_scope = next(s for s in gt.scopes if s.question_id == "q2")
    q1_ids = {c.criterion_id for c in q1_scope.criteria}
    q2_ids = {c.criterion_id for c in q2_scope.criteria}

    assert q1_ids == {"q1.c0", "q1.c1"}
    assert q2_ids == {"q2.c0"}
    assert q1_ids.isdisjoint(q2_ids), "closed-world violated: criteria leaked between questions"


# ---------------------------------------------------------------------------
# Test 10 — Sub-question scopes: one per sub-question, answer_missing for unanswered
# ---------------------------------------------------------------------------

def test_10_sub_question_bearing_produces_one_scope_per_sq():
    sqs = [
        _sub_question("א", 15, [_criterion("q1.א.c0")], index=0),
        _sub_question("ב", 15, [_criterion("q1.ב.c0")], index=1),
        _sub_question("ג", 20, [_criterion("q1.ג.c0")], index=2),
    ]
    r = _contract([_question("q1", 50, sub_questions=sqs)])
    t = _transcription([(1, "א", "a"), (1, "ב", "b")])  # ג has no answer

    gt = gradable_compiler.compile(r, t)

    assert len(gt.scopes) == 3
    sq_ids = {s.sub_question_id for s in gt.scopes}
    assert sq_ids == {"א", "ב", "ג"}

    gimel = next(s for s in gt.scopes if s.sub_question_id == "ג")
    assert gimel.alignment == "answer_missing"
    assert gimel.student_answer_text is None

    alef = next(s for s in gt.scopes if s.sub_question_id == "א")
    assert alef.alignment == "matched"


# ---------------------------------------------------------------------------
# Test 11 — sub_criteria carried correctly to GradableCriterion
# ---------------------------------------------------------------------------

def test_11_sub_criteria_carried_to_gradable_criterion():
    sc1 = _sub_criterion("q1.c0.sc0", "3")
    sc2 = _sub_criterion("q1.c0.sc1", "7")
    crit = _criterion("q1.c0", "10", sub_criteria=[sc1, sc2])
    r = _contract([_question("q1", 10, [crit])])
    t = _transcription([(1, None, "answer")])

    gt = gradable_compiler.compile(r, t)
    gc = gt.scopes[0].criteria[0]

    assert gc.sub_criteria is not None
    assert len(gc.sub_criteria) == 2
    sc_ids = {sc.sub_criterion_id for sc in gc.sub_criteria}
    assert sc_ids == {"q1.c0.sc0", "q1.c0.sc1"}
    sc_by_id = {sc.sub_criterion_id: sc for sc in gc.sub_criteria}
    assert sc_by_id["q1.c0.sc0"].points == Decimal("3")
    assert sc_by_id["q1.c0.sc1"].points == Decimal("7")


# ---------------------------------------------------------------------------
# Test 12 — Grading context carried to scope
# ---------------------------------------------------------------------------

def test_12_grading_context_carried_to_scope():
    tables = [{"headers": ["a", "b"], "rows": [{"a": 1, "b": 2}], "row_count": 1}]
    crit = _criterion("c1", "10", guidance="look at line 3", notes="deduct 2 if wrong indent")
    q = _question(
        "q1", 10, [crit],
        example_solution="x = 5",
        trace_tables=tables,
        context_tables=tables,
    )
    r = _contract([q])
    t = _transcription([(1, None, "answer")])

    gt = gradable_compiler.compile(r, t)
    scope = gt.scopes[0]

    assert scope.example_solution == "x = 5"
    assert scope.trace_tables == tables
    assert scope.context_tables == tables
    assert scope.criteria[0].evaluation_guidance == "look at line 3"
    assert scope.criteria[0].notes == "deduct 2 if wrong indent"


# ---------------------------------------------------------------------------
# Test 13 — Decimal discipline preserved throughout
# ---------------------------------------------------------------------------

def test_13_decimal_discipline_preserved():
    r = _contract([
        _question("q1", "30.5", [_criterion("c1", "15.25"), _criterion("c2", "15.25")]),
    ])
    t = _transcription([(1, None, "answer")])

    gt = gradable_compiler.compile(r, t)

    assert isinstance(gt.total_points, Decimal)
    assert gt.total_points == Decimal("30.5")

    scope = gt.scopes[0]
    assert isinstance(scope.points, Decimal)
    for c in scope.criteria:
        assert isinstance(c.points, Decimal)


# ---------------------------------------------------------------------------
# Test 14 — Determinism: same inputs → equal GradableTests
# ---------------------------------------------------------------------------

def test_14_compiler_is_deterministic():
    r = _contract([_question("q1", 10, [_criterion("c1")])])
    t = _transcription([(1, None, "answer")])

    gt1 = gradable_compiler.compile(r, t)
    gt2 = gradable_compiler.compile(r, t)
    assert gt1 == gt2


# ---------------------------------------------------------------------------
# Test 15 — Pinned contract versions appear in output
# ---------------------------------------------------------------------------

def test_15_contract_versions_pinned_in_output():
    r = _contract(
        [_question("q1", 10, [_criterion("c1")])],
        contract_version="rubric-v-abc",
    )
    t = _transcription([(1, None, "a")], contract_version="trans-v-xyz")

    gt = gradable_compiler.compile(r, t)
    assert gt.rubric_contract_version == "rubric-v-abc"
    assert gt.transcription_contract_version == "trans-v-xyz"


# ---------------------------------------------------------------------------
# Test 16 — Sub-question scopes carry parent question-level trace/context tables
# ---------------------------------------------------------------------------

def test_16_sub_question_scopes_carry_question_level_tables():
    tables = [{"headers": ["x"], "rows": [], "row_count": 0}]
    sqs = [
        _sub_question("א", 20, [_criterion("c1")]),
        _sub_question("ב", 20, [_criterion("c2")]),
    ]
    q = _question("q1", 40, sub_questions=sqs, trace_tables=tables, context_tables=tables)
    r = _contract([q])
    t = _transcription([(1, "א", "aa"), (1, "ב", "bb")])

    gt = gradable_compiler.compile(r, t)
    for scope in gt.scopes:
        assert scope.trace_tables == tables, f"trace_tables missing on scope {scope.sub_question_id}"
        assert scope.context_tables == tables, f"context_tables missing on scope {scope.sub_question_id}"


# ---------------------------------------------------------------------------
# Test 17 — Compiler never raises on empty transcription
# ---------------------------------------------------------------------------

def test_17_compiler_never_raises_on_empty_transcription():
    sqs = [_sub_question("א", 20, [_criterion("c1")])]
    r = _contract([_question("q1", 20, sub_questions=sqs)])
    t = _transcription([])

    gt = gradable_compiler.compile(r, t)  # must not raise

    assert len(gt.scopes) == 1
    assert all(s.alignment == "answer_missing" for s in gt.scopes)
    assert gt.unmatched_transcription_answers == []
