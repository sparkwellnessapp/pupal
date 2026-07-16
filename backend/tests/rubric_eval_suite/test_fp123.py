"""FP1–FP3 self-tests: the representational-ceiling removal, falsified without APIs.

THE EXPRESSIBILITY ROUND-TRIP (the load-bearing test): for every GT benchmark,
inverse-map the GT into the LLM-facing RubricExtraction shape — i.e. construct
exactly what a PERFECT model would emit — then run the pipeline's deterministic
tail (_clean_extraction → _validate_extraction → _downgrade_persistent_mismatches
→ _build_response) and score the result against the same GT. Before FP1/FP2 this
was IMPOSSIBLE for employee (no selection fields) and 899371 (no nesting): the
ceiling was in the grammar. If all five fixtures now pass their gate, the ceiling
is removed; whatever fails in the live eval afterwards is model behavior, not
representation.

Honesty note on FP3: it is a PROMPT change; its falsifier is the live eval, not
this file. What IS tested here is the FP3-critical deterministic flow: the cleaner
must no longer reconcile faithful teacher mismatches (899371 q1.א.2: components
1.5+0.5 under a declared 3), and the tail must convert the persistent mismatch
into exactly the rubric_mismatch annotation GT expects.

Run: PYTHONPATH=. python tests/rubric_eval_suite/tests/test_fp123.py
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.services.docx_v3.pipeline import (
    RubricExtraction, QuestionExtraction, SubQuestionExtraction,
    InnerSubQuestionExtraction, CriterionExtraction, SubCriterionExtraction,
    SelectionGroupExtraction,
    _achievable_from_extraction, _clean_extraction, _validate_extraction,
    _downgrade_persistent_mismatches, _get_mismatch_fingerprints, _build_response,
)
from app.schemas.ontology_types import (
    ExtractRubricResponse, compute_achievable_points,
)
from tests.rubric_eval_suite.runner import score_only

BENCH = Path("tests/rubric_eval_suite/benchmarks")


# ---------------------------------------------------------------------------
# GT -> RubricExtraction inverse mapping (what a perfect LLM would emit)
# ---------------------------------------------------------------------------

def _inv_criterion(c) -> CriterionExtraction:
    return CriterionExtraction(
        description=c.description, points=float(c.points),
        sub_criteria=[SubCriterionExtraction(description=sc.description, points=float(sc.points))
                      for sc in (c.sub_criteria or [])],
    )


def _inv_inner(sq) -> InnerSubQuestionExtraction:
    assert not sq.sub_questions, "GT nests deeper than 2 — bounded schema needs extending"
    # GT texts pass through UNTOUCHED (no placeholder injection): the round-trip
    # is the text-fidelity ceiling proof — a perfect extraction must score 1.0.
    return InnerSubQuestionExtraction(
        sub_question_id=sq.sub_question_id, text=sq.text,
        points=float(sq.points), example_solution=sq.example_solution,
        criteria=[_inv_criterion(c) for c in sq.criteria],
    )


def gt_to_extraction(gt: ExtractRubricResponse) -> RubricExtraction:
    qs = []
    for q in gt.questions:
        sqs = []
        for sq in q.sub_questions:
            sqs.append(SubQuestionExtraction(
                sub_question_id=sq.sub_question_id, text=sq.text,
                points=float(sq.points), example_solution=sq.example_solution,
                criteria=[_inv_criterion(c) for c in sq.criteria],
                sub_questions=[_inv_inner(isq) for isq in sq.sub_questions],
            ))
        qs.append(QuestionExtraction(
            question_number=int(q.question_id[1:]),
            # QuestionExtraction.question_text is a required str; "" is the
            # LLM-facing encoding of "no prose" (the scorer's presence test
            # treats "" and null identically, so GT-null round-trips to None)
            question_text=q.question_text or "",
            total_points=float(q.total_points),
            example_solution=q.example_solution,
            criteria=[_inv_criterion(c) for c in q.criteria],
            sub_questions=sqs,
        ))
    groups = [SelectionGroupExtraction(
        question_numbers=[int(qid[1:]) for qid in g.of_question_ids],
        choose_k=g.choose_k, label=g.label,
    ) for g in gt.selection_groups]
    return RubricExtraction(
        total_points=float(gt.total_points), questions=qs, selection_groups=groups)


def run_tail(ext: RubricExtraction, name: str) -> ExtractRubricResponse:
    """The deterministic post-LLM pipeline, with the persistent-mismatch downgrade
    simulated the way _extract_with_retry produces it (every mismatch fingerprint
    counts as persistent here — there is no retry without an LLM)."""
    ext = _clean_extraction(ext)
    issues = _validate_extraction(ext)
    issues = _downgrade_persistent_mismatches(issues, _get_mismatch_fingerprints(issues))
    resp, _warnings = _build_response(ext, name, issues)
    return resp


# ---------------------------------------------------------------------------
# 1) THE EXPRESSIBILITY ROUND-TRIP — all five fixtures
# ---------------------------------------------------------------------------

def test_expressibility_round_trip_all_fixtures():
    # Text-fidelity ceiling expectations. PR-1 populated GT text on all five
    # fixtures (foundations_cs included — 8 text nodes), so a PERFECT round-trip
    # scores 1.0 on every text metric for every fixture. (None would mean a
    # fixture has ZERO GT-text nodes — none do post-PR-1.)
    # PRE-REGISTERED (PREDICTIONS.md): any round-trip score < 1.0 means the
    # builder or normalizer mangles long text — an instrument bug found
    # offline before it costs a live run.
    TEXT_CEILING = {
        "bagrut_899371": 1.0, "csharp_plane_combine": 1.0,
        "employee_course_select1": 1.0, "foundations_cs": 1.0,
        "hobby_tvshow": 1.0,
    }
    from app.services.docx_v3.pedagogical_mistakes import (
        detect_pedagogical_mistakes, _ALLOWED_TIER_B_KINDS,
    )
    for j in sorted(BENCH.glob("*.json")):
        gt = ExtractRubricResponse.model_validate_json(j.read_text(encoding="utf-8"))
        resp = run_tail(gt_to_extraction(gt), j.stem)
        # THE PEDAGOGICAL CONSISTENCY INVARIANT (R2 ruling, 2026-07-10):
        #     GT pedagogical expectations ≡ TierA(faithful draft) ∪ expected-Tier-B
        # Tier A is DETERMINISTIC over the draft, so on a faithful draft its output
        # is a function of GT itself — GT must expect exactly it, or the gate is
        # un-passable by construction (the bagrut point_sum_mismatch contradiction).
        # So: run the REAL Tier A here (llm=None → no Tier B), and inject ONLY the
        # Tier-B-expected entries (hobby's structural_mislabel) from GT — those are
        # LLM judgments, tested live and in the mocked Tier-B tests, not here.
        tier_b_expected = [m for m in (gt.pedagogical_mistakes or [])
                           if m.kind in _ALLOWED_TIER_B_KINDS]
        tier_a_real = detect_pedagogical_mistakes(resp, rendered_markdown="", llm=None)
        resp = resp.model_copy(update={"pedagogical_mistakes": tier_a_real + tier_b_expected})
        rs = score_only(resp, gt, "x", meta={"rubric_name": j.stem})
        assert rs.pedagogical_match, (
            f"{j.stem}: pedagogical invariant BROKEN — GT expectations must equal "
            f"TierA(faithful draft) ∪ expected-Tier-B. missing={rs.missing_pedagogical} "
            f"spurious={rs.spurious_pedagogical}. Fix GT via a Tier-A probe "
            f"transcription, never by hand.")
        assert rs.gate_pass, (
            f"{j.stem}: round-trip gate FAILED — the internal schema/tail still "
            f"cannot express this GT: {rs.gate_failures}")
        exp = TEXT_CEILING[j.stem]
        for m in ("question_text_fidelity_min", "subquestion_text_fidelity_min",
                  "text_line_recall_min"):
            got = getattr(rs, m)
            assert got == exp, (
                f"{j.stem}: round-trip {m}={got} (expected {exp}) — the "
                f"builder/normalizer mangles GT text (instrument bug)")
        print(f"  [ok] {j.stem}: round-trip passes the gate; text ceiling = {exp}")


# ---------------------------------------------------------------------------
# 2) FP1 specifics
# ---------------------------------------------------------------------------

def test_achievable_mirror_pinned_to_ontology():
    """The float mirror and the ontology Decimal rule must agree — including the
    no-groups reduction and the dangling-member-contributes-0 rule."""
    for j in sorted(BENCH.glob("*.json")):
        gt = ExtractRubricResponse.model_validate_json(j.read_text(encoding="utf-8"))
        mirror = _achievable_from_extraction(gt_to_extraction(gt))
        onto = compute_achievable_points(gt.questions, gt.selection_groups)
        assert abs(Decimal(str(mirror)) - onto) < Decimal("0.001"), (j.stem, mirror, onto)
    # dangling member: group references q9 which doesn't exist -> contributes 0
    ext = RubricExtraction(total_points=0, questions=[
        QuestionExtraction(question_number=1, question_text="t", total_points=20,
                           criteria=[CriterionExtraction(description="d", points=20)])],
        selection_groups=[SelectionGroupExtraction(question_numbers=[1, 9], choose_k=2)])
    assert _achievable_from_extraction(ext) == 20.0
    print("  [ok] achievable mirror pinned to ontology rule (all fixtures + dangling member)")


def test_employee_totals_and_no_spurious_annotations():
    gt = ExtractRubricResponse.model_validate_json((BENCH / "employee_course_select1.json").read_text(encoding="utf-8"))
    resp = run_tail(gt_to_extraction(gt), "employee")
    assert resp.total_points == Decimal("50"), resp.total_points  # achievable, not Σ=100
    assert resp.selection_groups and resp.selection_groups[0].choose_k == 1
    assert resp.annotations == [], [a.message for a in resp.annotations]
    print("  [ok] employee: total=50 (selection-aware), one choose-1 group, ZERO annotations")


def test_899371_no_spurious_rubric_annotation():
    """Σ offered = 150, choose 4 -> achievable 100. The legacy hardcoded-100 RUBRIC
    check fired here; selection-aware it must not — GT expects exactly ONE
    annotation (q1.א.2), nothing rubric-scoped."""
    gt = ExtractRubricResponse.model_validate_json((BENCH / "bagrut_899371.json").read_text(encoding="utf-8"))
    resp = run_tail(gt_to_extraction(gt), "bagrut")
    assert resp.total_points == Decimal("100"), resp.total_points
    assert all(a.target_id is not None for a in resp.annotations), (
        "rubric-scoped (global) annotation fabricated on a selection exam")
    print("  [ok] 899371: achievable=100, no fabricated RUBRIC-scope annotation")


def test_tier_a_selection_normalization_activates():
    from app.services.docx_v3.pedagogical_mistakes import detect_pedagogical_mistakes
    gt = ExtractRubricResponse.model_validate_json((BENCH / "employee_course_select1.json").read_text(encoding="utf-8"))
    resp = run_tail(gt_to_extraction(gt), "employee")
    mistakes = detect_pedagogical_mistakes(resp, rendered_markdown="", llm=None)  # Tier A only
    kinds = {(m.kind.value if hasattr(m.kind, "value") else m.kind) for m in mistakes}
    assert "selection_normalization" in kinds, kinds
    resp = resp.model_copy(update={"pedagogical_mistakes": mistakes})
    rs = score_only(resp, gt, "x", meta={"rubric_name": "employee_course_select1"})
    assert rs.pedagogical_match, (rs.missing_pedagogical, rs.spurious_pedagogical)
    print("  [ok] Tier A selection_normalization fires on real draft and matches GT")


# ---------------------------------------------------------------------------
# 3) FP2 specifics
# ---------------------------------------------------------------------------

def test_nested_subquestion_ids_and_structure():
    gt = ExtractRubricResponse.model_validate_json((BENCH / "bagrut_899371.json").read_text(encoding="utf-8"))
    resp = run_tail(gt_to_extraction(gt), "bagrut")
    q1 = next(q for q in resp.questions if q.question_id == "q1")
    a = next(sq for sq in q1.sub_questions if sq.sub_question_id == "א")
    assert [isq.sub_question_id for isq in a.sub_questions] == ["1", "2"]
    inner2 = a.sub_questions[1]
    assert [c.criterion_id for c in inner2.criteria] == ["q1.א.2.c0", "q1.א.2.c1"]
    print("  [ok] nested SQs mapped with GT-convention criterion ids (q1.א.2.c0)")


# ---------------------------------------------------------------------------
# 4) FP3-critical deterministic flow: never-reconcile in the cleaner + the
#    faithful-mismatch annotation
# ---------------------------------------------------------------------------

def test_faithful_mismatch_survives_cleaner_and_becomes_annotation():
    gt = ExtractRubricResponse.model_validate_json((BENCH / "bagrut_899371.json").read_text(encoding="utf-8"))
    resp = run_tail(gt_to_extraction(gt), "bagrut")
    q1 = next(q for q in resp.questions if q.question_id == "q1")
    a2 = next(sq for sq in next(s for s in q1.sub_questions if s.sub_question_id == "א").sub_questions
              if sq.sub_question_id == "2")
    # the cleaner must NOT have reconciled 1.5+0.5 into the declared 3
    assert a2.points == Decimal("3"), a2.points
    assert [float(c.points) for c in a2.criteria] == [1.5, 0.5]
    anns = [(a.annotation_type, a.target_id) for a in resp.annotations]
    assert ("rubric_mismatch", "q1.א.2") in anns, anns
    print("  [ok] faithful 1.5+0.5-under-3 preserved; rubric_mismatch(q1.א.2) emitted")


def test_cleaner_still_recalcs_on_actual_removal():
    """The recalc restriction must not break crossed-out absorption: removing a
    0-point criterion still adjusts the SQ's points."""
    ext = RubricExtraction(total_points=0, questions=[QuestionExtraction(
        question_number=1, question_text="t", total_points=10,
        sub_questions=[SubQuestionExtraction(
            sub_question_id="א", text="t", points=10,
            criteria=[CriterionExtraction(description="keep", points=6),
                      CriterionExtraction(description="struck", points=0)])])])
    ext = _clean_extraction(ext)
    sq = ext.questions[0].sub_questions[0]
    assert len(sq.criteria) == 1 and sq.points == 6
    print("  [ok] crossed-out removal still recalcs the affected node's points")


if __name__ == "__main__":
    test_expressibility_round_trip_all_fixtures()
    test_achievable_mirror_pinned_to_ontology()
    test_employee_totals_and_no_spurious_annotations()
    test_899371_no_spurious_rubric_annotation()
    test_tier_a_selection_normalization_activates()
    test_nested_subquestion_ids_and_structure()
    test_faithful_mismatch_survives_cleaner_and_becomes_annotation()
    test_cleaner_still_recalcs_on_actual_removal()
    print("ALL FP1-3 SELF-TESTS PASSED")
