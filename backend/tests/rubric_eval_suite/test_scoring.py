"""
Known-answer regression test for the rubric scorer — the instrument's own guard.

Two cases:
  (1) PERFECT: predicted == GT  -> every metric 1.0, gate PASSES. If this fails, the
      instrument is broken (it would fail correct extractions). Most important assertion.
  (2) PERTURBED: predicted == GT with SEVEN injected errors, each isolated to a metric:
        E1 drop a criterion whose text IS in render   -> recall<1, extraction_loss
        E2 drop a criterion whose text is NOT in render-> recall<1, render_loss
        E3 add a spurious criterion                    -> precision<1
        E4 wrong points on a matched criterion         -> point_exactness<1
        E5 flatten a nested sub-question (branch->leaf) -> subquestion_structure_match<1
        E6 wrong selection (choose_k)                  -> selection_match=False, totals wrong
        E7 drop expected example_solution + annotation -> solution_fidelity<1, annotation_match=False

Run: PYTHONPATH=. python tests/rubric_eval_suite/tests/test_scoring.py
"""
from __future__ import annotations

from decimal import Decimal as D

from app.schemas.ontology_types import (
    Annotation, AnnotationSeverity, Criterion, ExtractRubricResponse,
    Question, SelectionGroup, SubCriterion, SubQuestion,
)
from tests.rubric_eval_suite.runner import score_only


# ---- builders ---------------------------------------------------------------
def crit(cid, desc, pts, subs=None):
    return Criterion(criterion_id=cid, index=0, description=desc, points=D(str(pts)),
                     sub_criteria=subs)


def subc(scid, desc, pts):
    return SubCriterion(sub_criterion_id=scid, index=0, description=desc, points=D(str(pts)))


def build_gt() -> ExtractRubricResponse:
    # Q1 (50): nested. א(30)=branch[(1) trace 20, (2) purpose 10]; ב(20)=leaf
    ss1 = SubQuestion(sub_question_id="1", index=0, text="trace the loop", points=D("20"),
                      example_solution="i=0; i=1; return 3",
                      criteria=[crit("q1.א.1.c0", "fill the trace table correctly", 20,
                                     subs=[subc("s0", "rows correct", 14), subc("s1", "final value", 6)])])
    ss2 = SubQuestion(sub_question_id="2", index=1, text="state the purpose", points=D("10"),
                      criteria=[crit("q1.א.2.c0", "purpose of the routine in one sentence", 10)])
    sqA = SubQuestion(sub_question_id="א", index=0, points=D("30"), sub_questions=[ss1, ss2])
    sqB = SubQuestion(sub_question_id="ב", index=1, text="return value of What", points=D("20"),
                      criteria=[crit("q1.ב.c0", "correct returned value", 10),
                                crit("q1.ב.c1", "justification of the value", 10)])
    q1 = Question(question_id="q1", total_points=D("50"), sub_questions=[sqA, sqB])

    # Q2 (50): leaf with direct criteria + sub-criteria + a solution
    q2 = Question(question_id="q2", total_points=D("50"), example_solution="public int f(){...}",
                  criteria=[crit("q2.c0", "method signature and loop structure", 30,
                                 subs=[subc("a", "signature", 20), subc("b", "loop bounds", 10)]),
                            crit("q2.c1", "correct accumulation and return", 20)])

    # Q3 (50): leaf; carries an EXPECTED faithful-teacher-error annotation
    q3 = Question(question_id="q3", total_points=D("50"),
                  criteria=[crit("q3.c0", "base case handled", 25),
                            crit("q3.c1", "recursive step is correct", 25)])

    return ExtractRubricResponse(
        rubric_id="gt", rubric_name="known_answer", total_points=D("100"),
        questions=[q1, q2, q3],
        selection_groups=[SelectionGroup(group_id="sg0", choose_k=2,
                                         of_question_ids=["q1", "q2", "q3"])],
        annotations=[Annotation(annotation_type="rubric_mismatch",
                                severity=AnnotationSeverity.WARNING,
                                message="Q3 header vs criteria mismatch in source (faithful).",
                                target_id="q3")],
    )


def render_for(gt: ExtractRubricResponse, omit_texts) -> str:
    """A render containing every criterion description EXCEPT those in omit_texts."""
    chunks = []
    for q in gt.questions:
        for c in q.all_criteria:
            if c.description in omit_texts:
                continue
            chunks.append(c.description)
            for sc in (c.sub_criteria or []):
                chunks.append(sc.description)
    return "\n".join(chunks)


def approx(x, y, eps=1e-9):
    return abs(x - y) <= eps


def test_perfect_passes():
    gt = build_gt()
    pred = gt.model_copy(deep=True)
    render = render_for(gt, omit_texts=set())
    rs = score_only(pred, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert rs.valid
    for m in ["question_recall", "question_precision", "subquestion_structure_match",
              "criterion_recall", "criterion_precision", "subcriterion_recall",
              "subcriterion_precision", "point_exactness", "example_solution_fidelity"]:
        assert approx(getattr(rs, m), 1.0), f"PERFECT: {m}={getattr(rs, m)} (expected 1.0)"
    assert rs.total_points_correct and rs.selection_match and rs.annotation_match
    assert rs.point_sum_consistency
    assert rs.render_loss_count == 0 and rs.extraction_loss_count == 0
    # text diagnostics: sub-question texts exist and match -> 1.0; no GT
    # question-level text in this fixture -> None (not-comparable, never 0.0)
    assert rs.subquestion_text_fidelity_min == 1.0, rs.subquestion_text_fidelity_min
    assert rs.text_line_recall_min == 1.0, rs.text_line_recall_min
    assert rs.question_text_fidelity_min is None, rs.question_text_fidelity_min
    assert rs.gate_pass, f"PERFECT should pass; failures={rs.gate_failures}"
    print("  [ok] perfect extraction passes the gate, all metrics 1.0")


def test_perturbed_fails_each_metric():
    gt = build_gt()
    pred = gt.model_copy(deep=True)

    # E1: drop q2.c1 (text IS in render) -> recall<1, extraction_loss
    pred.questions[1].criteria = [c for c in pred.questions[1].criteria if c.criterion_id != "q2.c1"]
    # E3: add spurious criterion on q2 -> precision<1
    pred.questions[1].criteria.append(crit("q2.cX", "spurious invented criterion", 5))
    # E4: wrong points on q2.c0 (still matches by description) -> point_exactness<1
    pred.questions[1].criteria[0].points = D("28")
    # E2: drop q3.c1 AND omit its text from render -> recall<1, render_loss
    pred.questions[2].criteria = [c for c in pred.questions[2].criteria if c.criterion_id != "q3.c1"]
    # E5: flatten q1.א (branch -> leaf with criteria) -> structure mismatch
    pred.questions[0].sub_questions[0] = SubQuestion(
        sub_question_id="א", index=0, points=D("30"),
        criteria=[crit("q1.א.flat", "flattened single criterion", 30)])
    # E6: wrong selection (choose 3 of 3) -> selection_match=False, achievable 150 != 100
    pred.selection_groups = [SelectionGroup(group_id="sg0", choose_k=3,
                                            of_question_ids=["q1", "q2", "q3"])]
    # E7: drop q2 example_solution + the expected annotation
    pred.questions[1].example_solution = None
    pred.annotations = []

    render = render_for(gt, omit_texts={"recursive step is correct"})  # q3.c1 -> render_loss
    rs = score_only(pred, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})

    assert rs.valid
    assert rs.question_recall == 1.0 and rs.question_precision == 1.0, "questions unchanged"
    assert rs.subquestion_structure_match < 1.0, "E5 flatten should drop structure match"
    assert rs.criterion_recall < 1.0, "E1/E2/E5 dropped criteria"
    assert rs.criterion_precision < 1.0, "E3 spurious criterion"
    assert rs.point_exactness < 1.0, "E4 wrong points"
    assert rs.selection_match is False, "E6 wrong selection"
    assert rs.total_points_correct is False, "E6 makes achievable wrong"
    assert approx(rs.example_solution_fidelity, 0.0) or rs.example_solution_fidelity < 1.0, "E7 missing solution"
    assert rs.annotation_match is False, "E7 dropped annotation"
    assert rs.extraction_loss_count >= 1, "q2.c1 dropped but in render -> extraction_loss"
    assert rs.render_loss_count >= 1, "q3.c1 dropped and not in render -> render_loss"
    assert rs.gate_pass is False
    # the perturbation must surface as MANY gate failures, not one
    assert len(rs.gate_failures) >= 7, f"expected >=7 gate failures, got {rs.gate_failures}"
    print(f"  [ok] perturbed: gate FAIL with {len(rs.gate_failures)} failures; "
          f"attribution render={rs.render_loss_count} extraction={rs.extraction_loss_count}")


def test_faithful_teacher_error_passes_when_reproduced():
    """A genuinely-inconsistent rubric, faithfully reproduced + flagged, must PASS."""
    gt = build_gt()
    # make Q3 genuinely inconsistent in BOTH gt and pred (criteria sum 60 != header 50),
    # and have both carry the rubric_mismatch annotation. Faithful reproduction -> PASS.
    gt.questions[2].criteria = [crit("q3.c0", "base case handled", 35),
                                crit("q3.c1", "recursive step is correct", 25)]
    pred = gt.model_copy(deep=True)
    render = render_for(gt, omit_texts=set())
    rs = score_only(pred, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert rs.point_sum_consistency is False, "Q3 is genuinely inconsistent"
    assert rs.annotation_match is True, "both carry the expected rubric_mismatch annotation"
    assert rs.gate_pass is True, ("faithful reproduction of an inconsistent rubric must PASS; "
                                  f"failures={rs.gate_failures}")
    print("  [ok] faithful teacher-error reproduction passes (consistency NOT gated)")


def test_truncation_is_invalid():
    gt = build_gt()
    pred = gt.model_copy(deep=True)
    rs = score_only(pred, gt, render_for(gt, set()), meta={"finish_reason": "MAX_TOKENS"})
    assert rs.valid is False and rs.gate_pass is False
    print("  [ok] truncated extraction marked invalid (validity before significance)")


def test_pedagogical_match_gates_both_directions():
    """Step 2c is gated: a missed detection fails AND a false positive on a clean
    rubric fails. Target ids match across conventions ('q2' vs '2') via canon_q,
    but criterion-style targets must NOT be digit-mangled into collisions."""
    from app.schemas.ontology_types import (
        PedagogicalMistake, PedagogicalMistakeKind, SuggestedFix,
    )

    def mk(kind, target, op=None):
        return PedagogicalMistake(
            mistake_id=f"t:{kind.value}:{target}", kind=kind,
            target_id=target, explanation="x", evidence={"note": "y"},
            suggested_fix=(SuggestedFix(operation=op, description="d", params={}) if op else None),
            requires_teacher_input=op is None, confidence=0.9,
        )

    gt = build_gt()
    gt.pedagogical_mistakes = [mk(PedagogicalMistakeKind.STRUCTURAL_MISLABEL, "q2", "reassign_subquestion")]
    render = render_for(gt, set())

    # 1) MISS: predicted has none -> gate fails on pedagogical_mismatch
    pred = gt.model_copy(deep=True); pred.pedagogical_mistakes = []
    rs = score_only(pred, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert not rs.pedagogical_match and "pedagogical_mismatch" in rs.gate_failures, rs.gate_failures

    # 2) MATCH across id conventions: predicted targets '2' where GT says 'q2' -> match
    pred2 = gt.model_copy(deep=True)
    pred2.pedagogical_mistakes = [mk(PedagogicalMistakeKind.STRUCTURAL_MISLABEL, "2", "reassign_subquestion")]
    rs2 = score_only(pred2, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert rs2.pedagogical_match, (rs2.missing_pedagogical, rs2.spurious_pedagogical)
    assert rs2.gate_pass, rs2.gate_failures

    # 3) FALSE POSITIVE on a clean GT: predicting a mistake where GT has none fails
    gt_clean = build_gt()
    pred3 = gt_clean.model_copy(deep=True)
    pred3.pedagogical_mistakes = [mk(PedagogicalMistakeKind.SELECTION_NORMALIZATION, None)]
    rs3 = score_only(pred3, gt_clean, render_for(gt_clean, set()), meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert not rs3.pedagogical_match and "pedagogical_mismatch" in rs3.gate_failures

    # 4) criterion-style targets are NOT digit-mangled: 'q1_sq_a_c2' != 'q12'
    gt4 = build_gt()
    gt4.pedagogical_mistakes = [mk(PedagogicalMistakeKind.POINT_SUM_MISMATCH, "q1_sq_a_c2")]
    pred4 = gt4.model_copy(deep=True)
    pred4.pedagogical_mistakes = [mk(PedagogicalMistakeKind.POINT_SUM_MISMATCH, "q12")]
    rs4 = score_only(pred4, gt4, render_for(gt4, set()), meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert not rs4.pedagogical_match, "digit-concatenation collision — canon applied to a non-question id"
    print("  [ok] pedagogical_match gates both directions; id conventions match; no digit collisions")


def test_text_null_semantics():
    """GT-null => None (never 0.0); pred-null/GT-full => 0.0; both-null => None;
    aggregates None when no GT-text nodes exist at a level."""
    gt = build_gt()
    render = render_for(gt, set())

    # 1) GT null + pred present => None (the old 0.0 wall is gone)
    pred = gt.model_copy(deep=True)
    pred.questions[0].question_text = "hallucinated context the GT does not carry"
    rs = score_only(pred, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    q1_scope = next(s for s in rs.scopes if s.scope_id == "q1")
    assert q1_scope.text_ratio is None and q1_scope.text_line_recall is None
    assert rs.question_text_fidelity_min is None  # no question in build_gt has GT text

    # 2) GT present + pred null => 0.0 (a real miss)
    pred2 = gt.model_copy(deep=True)
    pred2.questions[0].sub_questions[1].text = None          # GT ב has text
    rs2 = score_only(pred2, gt, render, meta={"cost_usd": 0.05, "finish_reason": "stop"})
    b_scope = next(s for s in rs2.scopes if s.scope_id.endswith(".ב"))
    assert b_scope.text_ratio == 0.0 and b_scope.text_line_recall == 0.0
    assert rs2.subquestion_text_fidelity_min == 0.0
    assert rs2.text_line_recall_min == 0.0
    assert rs2.gate_pass, f"text is UNGATED — a text miss must not fail the gate: {rs2.gate_failures}"

    # 3) both null => None; sqA (branch) has no text on either side
    rs3 = score_only(gt.model_copy(deep=True), gt, render,
                     meta={"cost_usd": 0.05, "finish_reason": "stop"})
    a_scope = next(s for s in rs3.scopes if s.scope_id.endswith(".א") and s.kind == "sub_question")
    assert a_scope.text_ratio is None and a_scope.text_line_recall is None

    # 4) aggregates None when NO nodes carry GT text at all
    gt4 = build_gt()
    for q in gt4.questions:
        for sq in q.all_sub_questions:
            sq.text = None
    rs4 = score_only(gt4.model_copy(deep=True), gt4, render_for(gt4, set()),
                     meta={"cost_usd": 0.05, "finish_reason": "stop"})
    assert rs4.question_text_fidelity_min is None
    assert rs4.subquestion_text_fidelity_min is None
    assert rs4.text_line_recall_min is None
    print("  [ok] text null semantics: GT-null=>None, pred-null=>0.0, both-null=>None, empty=>None aggregates")


def test_line_recall_catches_dropped_line_that_ratio_misses():
    """THE metric's justification: `ratio` is length-weighted, so silently
    dropping one constraint line from a long spec still scores ~0.93+ — the
    doc-ratio blindspot. text_line_recall is the omission detector."""
    gt = build_gt()
    # lines must be mutually DISSIMILAR (< LINE_TAU to each other), or the
    # dropped line would still "match" a neighbor and recall would stay 1.0
    long_text = "\n".join([
        "the method signature must be public static int[] Merge(int[] a, int[] b)",
        "allocate the result array before the main loop begins",
        "iterate both arrays with two independent index variables",
        "when values are equal, prefer the element from the first array",
        "null input arrays must raise an explicit error message",
        "the running index may never exceed either array length",
        "copy any remaining tail elements after the loop terminates",
        "return the merged array as the single return value",
    ])
    gt.questions[0].sub_questions[1].text = long_text
    pred = gt.model_copy(deep=True)
    kept = long_text.split("\n")
    del kept[4]                                   # silently drop one middle line
    pred.questions[0].sub_questions[1].text = "\n".join(kept)

    rs = score_only(pred, gt, render_for(gt, set()),
                    meta={"cost_usd": 0.05, "finish_reason": "stop"})
    b_scope = next(s for s in rs.scopes if s.scope_id.endswith(".ב"))
    assert b_scope.text_ratio is not None and b_scope.text_ratio >= 0.9, (
        f"ratio {b_scope.text_ratio} should stay HIGH — that is the blindspot")
    assert b_scope.text_line_recall is not None and b_scope.text_line_recall < 1.0, (
        "line recall must catch the dropped line")
    assert rs.text_line_recall_min < 1.0
    assert rs.gate_pass, f"UNGATED: the diagnostic must not gate: {rs.gate_failures}"
    print(f"  [ok] blindspot: ratio={b_scope.text_ratio} stays high, "
          f"line_recall={b_scope.text_line_recall} catches the omission, gate unaffected")


def test_text_fields_survive_artifact_boundary():
    """The three new fields must survive to_dict() and render in the reports
    (the pattern institutionalized by the pedagogical regression test)."""
    import tempfile
    from pathlib import Path
    from tests.rubric_eval_suite.reporting import aggregate, write_rubric_report, write_summary
    from tests.rubric_eval_suite.schemas import SuiteResult

    gt = build_gt()
    rs = score_only(gt.model_copy(deep=True), gt, render_for(gt, set()),
                    meta={"cost_usd": 0.05, "finish_reason": "stop", "rubric_name": "known_answer"})
    d = rs.to_dict()
    for k in ("question_text_fidelity_min", "subquestion_text_fidelity_min", "text_line_recall_min"):
        assert k in d, f"{k} missing from results.json row"
    assert any(s.get("text_line_recall") is not None for s in d["scopes"]), \
        "per-scope text_line_recall missing from artifacts"

    suite = SuiteResult(provenance={}, per_rubric=[rs], aggregates=aggregate([rs]))
    for k in ("question_text_fidelity_min", "subquestion_text_fidelity_min", "text_line_recall_min"):
        assert k in suite.aggregates["worst_rubric"], f"{k} missing from aggregates"
    with tempfile.TemporaryDirectory() as td:
        report = write_rubric_report(rs, Path(td)).read_text(encoding="utf-8")
        assert "Text fidelity (UNGATED diagnostic)" in report
        assert "text_line_recall_min" in report
        summary = write_summary(suite, Path(td)).read_text(encoding="utf-8")
        assert "subquestion_text_fidelity_min" in summary
    print("  [ok] text metrics survive to_dict(), aggregates, per-rubric report and summary")


def test_bidi_marks_do_not_break_text_match():
    """Real ink embeds LRM/RLM around Latin-in-Hebrew (measured in csharp fixture);
    GT is typed clean. The normal form must equate them or verbatim extraction
    scores a fake mismatch."""
    from tests.rubric_eval_suite import normalize as nz
    marked = "כתבו פעולה חיצונית בשם \u200eCombine\u200e בשפת \u200eC#\u200e"
    clean = "כתבו פעולה חיצונית בשם Combine בשפת C#"
    assert nz.norm_text(marked) == nz.norm_text(clean)
    assert nz.ratio(marked, clean) == 1.0
    print("  [ok] Cf format chars stripped from comparison normal form")


if __name__ == "__main__":
    test_perfect_passes()
    test_perturbed_fails_each_metric()
    test_faithful_teacher_error_passes_when_reproduced()
    test_truncation_is_invalid()
    test_pedagogical_match_gates_both_directions()
    test_text_null_semantics()
    test_line_recall_catches_dropped_line_that_ratio_misses()
    test_text_fields_survive_artifact_boundary()
    test_bidi_marks_do_not_break_text_match()
    print("ALL SCORER SELF-TESTS PASSED")
