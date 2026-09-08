"""rescale_to_exam — the D-13 grid-snap post-pass. Pure, no mocks.

Known answers from the execution plan §5 Phase 2b and the two Math fixtures' shapes:
  * 4-unit 35472: 5 questions, answer 3 → shares 33.5 / 33.25 / 33.25 / 33.25 / 33.25, total 100
  * 3-unit 35173: 5 questions, "answer any, capped at 100" → choose 4 → 25 × 5, total 100
  * Q5's weights 10/10/7/39/9/15/10 (= 100) on a 33.25 share → grid values summing to 33.25
INV-1..4 must hold EXACTLY on every output — by construction, never by tolerance.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.schemas.ontology_types import (
    Criterion, ExtractRubricResponse, NumericPolicy, Question, QuestionType,
    SelectionGroup, SubCriterion, SubQuestion,
)
from app.services.contract_compiler import ContractCompiler
from app.services.docx_v3 import rescale_to_exam as rx

D = Decimal


def _crit(cid, pts, desc="step"):
    return Criterion(criterion_id=cid, index=0, description=f"{desc} ({pts}%)", points=D(str(pts)))


def _q(qid, crits=None, subs=None, total="100"):
    return Question(question_id=qid, question_type=QuestionType.COMPUTATION, total_points=D(total),
                    criteria=crits or [], sub_questions=subs or [])


def _sq(sqid, pts, crits=None, subs=None, index=0):
    return SubQuestion(sub_question_id=sqid, index=index, points=D(str(pts)),
                       criteria=crits or [], sub_questions=subs or [])


def _draft(questions, groups=(), total="100", subject="mathematics"):
    return ExtractRubricResponse(rubric_id="r", rubric_name="t", subject=subject, total_points=D(total),
                                 questions=questions, selection_groups=list(groups))


# --- primitives ----------------------------------------------------------------

@pytest.mark.parametrize("k,expected", [
    (2, ["50", "50"]),
    (3, ["33.5", "33.25", "33.25"]),
    (4, ["25", "25", "25", "25"]),
    (5, ["20", "20", "20", "20", "20"]),
])
def test_snap_shares_pattern(k, expected):
    assert [str(s) for s in rx.snap_shares(D("100"), k)] == expected


def test_largest_remainder_q5_weights_on_a_33_25_share():
    weights = [D(w) for w in ("10", "10", "7", "39", "9", "15", "10")]
    out = rx.largest_remainder(weights, D("33.25"))
    assert sum(out) == D("33.25")
    assert all((v / D("0.25")) == (v / D("0.25")).to_integral_value() for v in out)
    # pinned deterministic result (Hamilton, ties → earlier index):
    # 133 units → raw 13.3/13.3/9.31/51.87/11.97/19.95/13.3 → floors sum 129 → the
    # four largest remainders (.97 .95 .87 .31) each get one unit.
    assert [str(v) for v in out] == ["3.25", "3.25", "2.5", "13", "3", "5", "3.25"]
    # drift bound P-11b: |snapped − exact| ≤ 0.25 everywhere
    exact = [D("33.25") * w / D("100") for w in weights]
    assert max(abs(o - e) for o, e in zip(out, exact)) <= D("0.25")


def test_largest_remainder_even_split_when_no_weights():
    assert [str(v) for v in rx.largest_remainder([D(0), D(0), D(0)], D("10"))] == ["3.5", "3.25", "3.25"]


def test_largest_remainder_refuses_off_grid_target():
    with pytest.raises(ValueError):
        rx.largest_remainder([D(1)], D("10.1"))


# --- the 4-unit shape: answer 3 of 5, weights per question on a 100 scale ---------

def _four_unit_draft():
    q5 = _q("q5", subs=[
        _sq("q5.א", 10, crits=[_crit("q5.א.c0", 10)], index=0),
        _sq("q5.ב", 10, crits=[_crit("q5.ב.c0", 5), _crit("q5.ב.c1", 5)], index=1),
        _sq("q5.ג", 7, crits=[_crit("q5.ג.c0", 7)], index=2),
        _sq("q5.ד", 39, crits=[_crit("q5.ד.c0", 15), _crit("q5.ד.c1", 24)], index=3),
        _sq("q5.ה", 9, crits=[_crit("q5.ה.c0", 9)], index=4),
        _sq("q5.ו", 15, crits=[_crit("q5.ו.c0", 15)], index=5),
        _sq("q5.ז", 10, crits=[_crit("q5.ז.c0", 10)], index=6),
    ])
    others = [_q(f"q{i}", crits=[_crit(f"q{i}.c0", 60), _crit(f"q{i}.c1", 40)]) for i in (1, 2, 3, 4)]
    group = SelectionGroup(group_id="sg0", choose_k=3, of_question_ids=["q1", "q2", "q3", "q4", "q5"])
    return _draft(others + [q5], groups=[group])


def test_four_unit_shares_total_and_compile():
    before = _four_unit_draft()
    after = rx.rescale_to_exam(before)
    shares = [str(q.total_points) for q in after.questions]
    assert shares == ["33.5", "33.25", "33.25", "33.25", "33.25"]
    assert after.total_points == D("100")
    # INV-2/INV-3 exact on every node
    for q in after.questions:
        if q.sub_questions:
            assert sum(s.points for s in q.sub_questions) == q.total_points
            for s in q.sub_questions:
                assert sum(c.points for c in s.criteria) == s.points
        else:
            assert sum(c.points for c in q.criteria) == q.total_points
    # the compiler agrees: INV-1..4 pass, achievable == 100 (k largest of the shares)
    contract = ContractCompiler().compile(after, policy=NumericPolicy())
    assert contract.total_points == D("100")
    # the teacher's written weight survives in every description
    assert all("%" in c.description for q in after.questions for c in q.all_criteria)
    # P-11b drift bound
    assert rx.max_criterion_drift(before, after) <= D("0.25")


def test_four_unit_q5_subquestions_snap_by_largest_remainder():
    after = rx.rescale_to_exam(_four_unit_draft())
    q5 = next(q for q in after.questions if q.question_id == "q5")
    assert [str(s.points) for s in q5.sub_questions] == ["3.25", "3.25", "2.5", "13", "3", "5", "3.25"]
    d = next(s for s in q5.sub_questions if s.sub_question_id == "q5.ד")
    assert [str(c.points) for c in d.criteria] == ["5", "8"]     # 15/24 of 13 on the grid


# --- the 3-unit shape: answer any, capped at 100 → choose 4 of 5 ---------------------

def test_three_unit_cap_as_choose_four_of_five():
    qs = [_q(f"q{i}", crits=[_crit(f"q{i}.c0", 40), _crit(f"q{i}.c1", 60)]) for i in range(1, 6)]
    group = SelectionGroup(group_id="sg0", choose_k=4, of_question_ids=[q.question_id for q in qs])
    after = rx.rescale_to_exam(_draft(qs, groups=[group]))
    assert [str(q.total_points) for q in after.questions] == ["25"] * 5
    assert [str(c.points) for c in after.questions[0].criteria] == ["10", "15"]
    contract = ContractCompiler().compile(after, policy=NumericPolicy())
    assert contract.total_points == D("100")


# --- no selection group: printed points stay, weights scale into them -------------

def test_no_group_keeps_printed_points_and_scales_weights():
    qs = [_q("q1", total="24", crits=[_crit("q1.c0", 10), _crit("q1.c1", 20), _crit("q1.c2", 40), _crit("q1.c3", 30)]),
          _q("q2", total="76", crits=[_crit("q2.c0", 100)])]
    after = rx.rescale_to_exam(_draft(qs))
    assert [str(q.total_points) for q in after.questions] == ["24", "76"]
    assert sum(c.points for c in after.questions[0].criteria) == D("24")
    assert [str(c.points) for c in after.questions[0].criteria] == ["2.5", "4.75", "9.5", "7.25"]
    ContractCompiler().compile(after, policy=NumericPolicy())


# --- invariants of the post-pass itself ---------------------------------------------

def test_idempotent():
    once = rx.rescale_to_exam(_four_unit_draft())
    twice = rx.rescale_to_exam(once)
    assert twice.model_dump(mode="json") == once.model_dump(mode="json")
    assert once.extraction_metadata[rx.STAMP_KEY]["shares"]["q1"] == "33.5"


def test_teacher_weights_that_do_not_sum_to_100_are_scaled_not_invented():
    """FC: the teacher wrote 90 % of steps; the node still fills its share (the
    per-node mismatch annotation from extraction stays for her to resolve)."""
    q = _q("q1", crits=[_crit("q1.c0", 50), _crit("q1.c1", 40)])
    after = rx.rescale_to_exam(_draft([q]))
    assert sum(c.points for c in after.questions[0].criteria) == D("100")
    assert [str(c.points) for c in after.questions[0].criteria] == ["55.5", "44.5"]


def test_global_rubric_mismatch_annotation_is_dropped_but_node_ones_stay():
    from app.schemas.ontology_types import Annotation, AnnotationSeverity
    d = _four_unit_draft().model_copy(update={"annotations": [
        Annotation(annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
                   message="Σ questions 500 ≠ 100", target_id=None),
        Annotation(annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
                   message="weights sum 90", target_id="q1"),
    ]})
    after = rx.rescale_to_exam(d)
    assert [a.target_id for a in after.annotations] == ["q1"]


def test_cs_and_english_never_enter_the_post_pass():
    """The profile flag decides — no subject branch anywhere in the pipeline."""
    from app.subjects import get_profile
    assert get_profile("mathematics").rescale_to_exam is True
    assert get_profile("computer_science").rescale_to_exam is False
    assert get_profile("english").rescale_to_exam is False
