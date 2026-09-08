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


def test_largest_remainder_keeps_an_unwritten_vector_at_zero():
    """Nothing written → nothing invented (the 4-unit fixture's q2 has no marking scheme)."""
    assert [str(v) for v in rx.largest_remainder([D(0), D(0), D(0)], D("10"))] == ["0", "0", "0"]


def test_split_written_consistent_is_exact_and_inconsistent_is_preserved():
    # consistent: 15/24 under a written 39 → largest remainder onto 13, Σ == 13
    pts, ok = rx.split_written([D(15), D(24)], D(39), D("13"))
    assert ok and [str(p) for p in pts] == ["5", "8"]
    # inconsistent (the real q4.ד: 15+3+6+5+5 = 34 under a written 39) → same factor 13/39,
    # each snapped on its own, Σ 11.5 ≠ 13 — her gap survives in proportion
    pts, ok = rx.split_written([D(15), D(3), D(6), D(5), D(5)], D(39), D("13"))
    assert not ok and [str(p) for p in pts] == ["5", "1", "2", "1.75", "1.75"]
    assert sum(pts) == D("11.5")
    # no written total → Σ children stands in, so a weighted-steps-only node is consistent
    pts, ok = rx.split_written([D(20), D(30)], D(0), D("25"))
    assert ok and [str(p) for p in pts] == ["10", "15"]


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


def _compile_fails(draft) -> bool:
    try:
        ContractCompiler().compile(draft, policy=NumericPolicy(),
                                   acknowledged_warnings=[a.id for a in draft.annotations])
    except Exception:
        return True
    return False


def _mismatch(after, target):
    return next(a for a in after.annotations
                if a.annotation_type == "rubric_mismatch" and a.target_id == target)


def test_teacher_weights_that_do_not_add_up_are_kept_flagged_and_block_compile():
    """FC: the teacher wrote 90 % of steps under a 100-point question. The post-pass does
    NOT fill the gap for her: the weights stay as written, the node is flagged with the
    exam-scale and the written numbers, and INV-1 blocks compile until she resolves it."""
    q = _q("q1", crits=[_crit("q1.c0", 50), _crit("q1.c1", 40)])
    after = rx.rescale_to_exam(_draft([q]))
    assert [str(c.points) for c in after.questions[0].criteria] == ["50", "40"]
    a = _mismatch(after, "q1")
    assert (a.expected, a.actual) == ("100", "90")
    assert a.severity.value.lower() == "warning" and a.message_he and "90" in a.message_he
    assert after.extraction_metadata[rx.STAMP_KEY]["unresolved"] == ["q1"]
    assert _compile_fails(after)


def test_the_real_q4_dalet_inconsistency_survives_and_the_teacher_fix_compiles_at_100():
    """The 4-unit fixture, page 15: q4.ד is written 39 % with steps 15+3+6+5+5 = 34 %.
    Every other node adds up. After the post-pass the node carries its 13-point share with
    children 5/1/2/1.75/1.75 (Σ 11.5), one WARNING names it, the rest of the rubric is
    exact, and compile is blocked at that node alone. Her fix (any 13-point split) compiles
    at the exam's real 100."""
    d = _four_unit_draft()
    q5 = next(q for q in d.questions if q.question_id == "q5")
    dalet = next(s for s in q5.sub_questions if s.sub_question_id == "q5.ד")
    dalet.criteria = [_crit(f"q5.ד.c{i}", w) for i, w in enumerate((15, 3, 6, 5, 5))]
    after = rx.rescale_to_exam(d)
    q5a = next(q for q in after.questions if q.question_id == "q5")
    da = next(s for s in q5a.sub_questions if s.sub_question_id == "q5.ד")
    assert str(da.points) == "13"
    assert [str(c.points) for c in da.criteria] == ["5", "1", "2", "1.75", "1.75"]
    a = _mismatch(after, "q5.ד")
    assert (a.expected, a.actual) == ("13", "11.5") and "34" in a.message and "39" in a.message
    assert after.extraction_metadata[rx.STAMP_KEY]["unresolved"] == ["q5.ד"]
    for q in after.questions:                      # every OTHER node is exact
        for s in q.sub_questions:
            if s.sub_question_id != "q5.ד":
                assert sum(c.points for c in s.criteria) == s.points
    assert _compile_fails(after)
    # the teacher's decision — here, proportional onto 13 — and the exam compiles at 100
    fixed = rx.largest_remainder([c.points for c in da.criteria], D("13"))
    da.criteria = [c.model_copy(update={"points": p}) for c, p in zip(da.criteria, fixed)]
    after.annotations = [x for x in after.annotations if x.target_id != "q5.ד"]
    contract = ContractCompiler().compile(after, policy=NumericPolicy())
    assert contract.total_points == D("100")


def test_a_question_with_no_marking_scheme_keeps_zero_parts_and_is_flagged():
    """The 4-unit fixture has NO marking scheme for q2 (vectors): the model emits its
    printed parts at 0. The post-pass keeps them at 0 (never invents), gives q2 its
    33.25 share, flags q2 (expected 33.25, actual 0, written 0 of 100) and compile is
    blocked by INV-1 until she writes the weights; her fill compiles at 100."""
    d = _four_unit_draft()
    q2 = next(q for q in d.questions if q.question_id == "q2")
    q2.criteria = []
    q2.sub_questions = [
        _sq("q2.א", 0, subs=[_sq("q2.א.1", 0, index=0), _sq("q2.א.2", 0, index=1)], index=0),
        _sq("q2.ב", 0, index=1),
        _sq("q2.ג", 0, index=2),
    ]
    after = rx.rescale_to_exam(d)
    q2a = next(q for q in after.questions if q.question_id == "q2")
    assert str(q2a.total_points) == "33.25"
    assert [str(s.points) for s in q2a.sub_questions] == ["0", "0", "0"]
    assert [str(s.points) for s in q2a.sub_questions[0].sub_questions] == ["0", "0"]
    a = _mismatch(after, "q2")
    assert (a.expected, a.actual) == ("33.25", "0")
    assert after.extraction_metadata[rx.STAMP_KEY]["unresolved"] == ["q2"]
    assert _compile_fails(after)
    # her fill: 13.25 / 10 / 10 with א split 6.75 / 6.5 — grid values, INV-1/2 exact —
    # and one criterion per leaf (a leaf with points and no criteria fails INV-2)
    q2a.sub_questions[0].points = D("13.25")
    q2a.sub_questions[1].points = D("10")
    q2a.sub_questions[2].points = D("10")
    leaves = [(q2a.sub_questions[0].sub_questions[0], D("6.75")),
              (q2a.sub_questions[0].sub_questions[1], D("6.5")),
              (q2a.sub_questions[1], D("10")), (q2a.sub_questions[2], D("10"))]
    for leaf, p in leaves:
        leaf.points = p
        leaf.criteria = [_crit(f"{leaf.sub_question_id}.c0", p, desc="פתרון מלא")]
    after.annotations = [x for x in after.annotations if x.target_id != "q2"]
    contract = ContractCompiler().compile(after, policy=NumericPolicy())
    assert contract.total_points == D("100")


def test_a_part_without_a_written_total_takes_the_sum_of_its_steps():
    """She weighted the steps of א (20 + 30) but wrote no total for א itself: the post-pass
    treats Σ steps as its weight (its own arithmetic, never the model's) — consistent,
    exact, unflagged."""
    q = _q("q1", subs=[
        _sq("q1.א", 0, crits=[_crit("q1.א.c0", 20), _crit("q1.א.c1", 30)], index=0),
        _sq("q1.ב", 50, crits=[_crit("q1.ב.c0", 50)], index=1),
    ])
    after = rx.rescale_to_exam(_draft([q]))
    alef, bet = after.questions[0].sub_questions
    assert [str(alef.points), str(bet.points)] == ["50", "50"]
    assert [str(c.points) for c in alef.criteria] == ["20", "30"]
    assert not [a for a in after.annotations if a.annotation_type == "rubric_mismatch"]
    ContractCompiler().compile(after, policy=NumericPolicy())


def test_extraction_time_mismatch_annotations_are_replaced_on_the_exam_scale():
    """The extraction validator's rubric_mismatch annotations speak the per-question
    scale (and the rubric-level one is false by construction after the shares). The
    post-pass replaces them with its own — none where the weights add up — and every
    other annotation type passes through."""
    from app.schemas.ontology_types import Annotation, AnnotationSeverity
    d = _four_unit_draft().model_copy(update={"annotations": [
        Annotation(annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
                   message="Σ questions 500 ≠ 100", target_id=None),
        Annotation(annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
                   message="stale per-question-scale message", target_id="q1"),
        Annotation(annotation_type="review_flag", severity=AnnotationSeverity.INFO,
                   message="passes through", target_id="q3"),
    ]})
    after = rx.rescale_to_exam(d)
    assert [(a.annotation_type, a.target_id) for a in after.annotations] == [("review_flag", "q3")]
    assert after.extraction_metadata[rx.STAMP_KEY]["unresolved"] == []


def test_cs_and_english_never_enter_the_post_pass():
    """The profile flag decides — no subject branch anywhere in the pipeline."""
    from app.subjects import get_profile
    assert get_profile("mathematics").rescale_to_exam is True
    assert get_profile("computer_science").rescale_to_exam is False
    assert get_profile("english").rescale_to_exam is False


def test_an_off_grid_exam_total_is_snapped_once_and_named_never_spread_off_grid():
    """Observed on the real 4-unit run: a draft arrived declaring 33.33 and the shares
    came out 11.33 — points off the 0.25 policy grid the whole product rounds to. The
    denominator is snapped ONCE, before anything is cut from it, the written value is
    kept in the stamp, and a global WARNING names the change."""
    qs = [_q("q1", crits=[_crit("q1.c0", 100)], total="33.33")]
    after = rx.rescale_to_exam(_draft(qs, total="33.33"))
    assert str(after.total_points) == "33.25"
    assert [str(q.total_points) for q in after.questions] == ["33.25"]
    assert all((c.points / D("0.25")) == (c.points / D("0.25")).to_integral_value()
               for q in after.questions for c in q.all_criteria)
    stamp = after.extraction_metadata[rx.STAMP_KEY]
    assert (stamp["exam_total"], stamp["exam_total_written"]) == ("33.25", "33.33")
    a = next(x for x in after.annotations if x.target_id is None)
    assert (a.expected, a.actual) == ("33.25", "33.33")
    ContractCompiler().compile(after, policy=NumericPolicy(),
                               acknowledged_warnings=[x.id for x in after.annotations])


def test_snap_shares_refuses_an_off_grid_total():
    with pytest.raises(ValueError):
        rx.snap_shares(D("33.33"), 3)


def test_a_real_total_is_untouched_and_stamps_no_warning():
    after = rx.rescale_to_exam(_four_unit_draft())
    stamp = after.extraction_metadata[rx.STAMP_KEY]
    assert (stamp["exam_total"], stamp["exam_total_written"]) == ("100", "100")
    assert not [a for a in after.annotations if a.target_id is None]
