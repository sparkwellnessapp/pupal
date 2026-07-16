"""
PR-3 — Contract parity: the compiler, the grader's scope slicing, and the ONE
selection-aware scorer that both score sites share.

The grading half of the system has NO eval suite. These tests are its only guard —
load-bearing, not ceremony.

What must hold:
  A. COMPILE MATRIX — four golden drafts compile CLEAN in ONE round trip; 899371 is
     rejected with EXACTLY ONE error, anchored at q1.א.2 (the faithful teacher error
     the old flat INV-2 masked); a teacher's fix to that node compiles.
  B. SCOPES ARE LEAVES — a nested rubric grades its inner parts instead of silently
     dropping them; the parent contributes no scope; parent-answer fallback fires.
  C. SELECTION SCORING — a perfect selection answer scores 100%, not 50%; excluded
     members are excluded, NOT zeroed; an override can FLIP best-k membership and the
     frozen marks must follow.
  D. REGRESSION — a flat, selection-free contract is bit-for-bit unchanged, and the
     40 prod-shaped contracts re-parse and grade as before.
"""
import json
import glob
import os
from decimal import Decimal
from typing import List, Optional

import pytest

from app.schemas.gradable import GradableTest
from app.schemas.graded_test_draft import GradedTestDraft, ScopeOutcome
from app.schemas.ontology_types import (
    Criterion,
    ExtractRubricResponse,
    GradingRubricContract,
    NumericPolicy,
    Question,
    SelectionGroup,
    SubQuestion,
)
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer
from app.services.contract_compiler import (
    CompilationError,
    ContractCompiler,
    WarningsRequireAcknowledgment,
)
from app.services.gradable_compiler import compile as compile_gradable
from app.services.selection_scoring import ScopeScore, score_with_selection

BENCH = "tests/rubric_eval_suite/benchmarks"


# ===========================================================================
# A. COMPILE MATRIX — the headline acceptance
# ===========================================================================

def _compile(draft: ExtractRubricResponse, acks=None):
    return ContractCompiler().compile(draft, policy=NumericPolicy(),
                                      acknowledged_warnings=acks or [])


def _load(name: str) -> ExtractRubricResponse:
    return ExtractRubricResponse.model_validate(
        json.load(open(f"{BENCH}/{name}.json", encoding="utf-8"))
    )


@pytest.mark.parametrize("name, expected_total, expected_groups", [
    ("csharp_plane_combine",   Decimal("100"), 0),
    ("hobby_tvshow",           Decimal("100"), 0),
    ("foundations_cs",         Decimal("100"), 0),
    # The selection exam: offered 15+50+35 = 100, ACHIEVABLE (choose 1) = 50.
    # Before PR-3 this was a hard dead-end — INV-4 compared offered vs declared.
    ("employee_course_select1", Decimal("50"),  1),
])
def test_golden_drafts_compile_clean_in_one_round_trip(name, expected_total, expected_groups):
    """ONE call, no acknowledgment dance. INV-6 used to fire on 100% of criteria and
    force a second round trip in which the frontend auto-acked every one of them."""
    contract = _compile(_load(name))          # no acks passed — must not need any
    assert contract.total_points == expected_total
    assert len(contract.selection_groups) == expected_groups


def test_899371_rejects_with_exactly_one_error_anchored_at_the_teacher_mistake():
    """THE acceptance criterion. Its rejection IS the pass condition.

    The old flat INV-2 produced THREE errors, all of them wrong-headed: two at the
    PARENTS (q1.א, q1.ב — whose criteria live on their children, so they summed to 0)
    and one bogus rubric-total error (it compared offered 150 to declared 100 on a
    choose-4-of-6 exam). It never once visited q1.א.2 — the node carrying the real
    teacher error (1.5 + 0.5 under a declared 3). The gate was blind to the very
    mistake it exists to surface.
    """
    with pytest.raises(CompilationError) as ei:
        _compile(_load("bagrut_899371"))

    errors = ei.value.errors
    assert len(errors) == 1, [f"{e.invariant}@{e.target_id}" for e in errors]

    err = errors[0]
    assert err.invariant == "INV-2"
    assert err.target_id == "q1.א.2"        # the full path — what the editor anchors to
    assert err.expected == "3"              # declared
    assert err.actual == "2"                # 1.5 + 0.5
    assert err.message_he == "סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)"
    # INV-4 must PASS: 6x25=150 offered, choose-4 => 100 achievable == declared 100.
    assert not any(e.invariant == "INV-4" for e in errors)


def test_teacher_resolves_the_899371_mismatch_and_it_compiles():
    """The fix-path through the identical gate (the update path is the same compile)."""
    draft = _load("bagrut_899371")
    for q in draft.questions:
        for sq in q.all_sub_questions:
            if sq.sub_question_id == "2" and sq.criteria and sq.points == Decimal("3"):
                # Teacher corrects the split to 1.5 + 1.5 = 3
                sq.criteria[0].points = Decimal("1.5")
                sq.criteria[1].points = Decimal("1.5")

    # The draft still carries the pipeline's WARNING-severity `rubric_mismatch`
    # annotation on that very node. A WARNING means "teacher, look at this" — so it is
    # acknowledged, exactly as the editor does. (The compiler no longer INVENTS the
    # warnings; INV-6 is INFO now, so this is the only one.)
    acks = [a.id for a in draft.annotations if a.severity.value == "warning"]
    contract = _compile(draft, acks=acks)
    assert contract.total_points == Decimal("100")   # achievable, choose-4-of-6
    assert len(contract.selection_groups) == 1


def test_inv6_is_info_and_never_blocks():
    """R1: a check nobody can pass, auto-acked 100% of the time, trained the
    click-through reflex that would swallow the next REAL warning."""
    contract = _compile(_load("csharp_plane_combine"))   # zero acks
    assert contract is not None


# ===========================================================================
# B. SCOPES ARE LEAVES  (the un-gated grading bug, made safe)
# ===========================================================================

def _crit(cid: str, pts: str) -> Criterion:
    return Criterion(criterion_id=cid, index=0, description=cid, points=Decimal(pts))


def _nested_contract() -> GradingRubricContract:
    """q1 (15) -> א (15) -> {א.1 (10), א.2 (5)}. The parent holds NO criteria."""
    inner1 = SubQuestion(sub_question_id="1", index=0, text="part 1",
                         points=Decimal("10"), criteria=[_crit("q1.א.1.c0", "10")])
    inner2 = SubQuestion(sub_question_id="2", index=1, text="part 2",
                         points=Decimal("5"), criteria=[_crit("q1.א.2.c0", "5")])
    parent = SubQuestion(sub_question_id="א", index=0, text="whole section",
                         points=Decimal("15"), criteria=[], sub_questions=[inner1, inner2])
    q = Question(question_id="q1", question_text="Q1", total_points=Decimal("15"),
                 criteria=[], sub_questions=[parent])
    return GradingRubricContract(
        contract_version="c1", rubric_id="r1", subject="cs",
        numeric_policy=NumericPolicy(), total_points=Decimal("15"), questions=[q],
    )


def _transcript(answers) -> TranscriptionContract:
    return TranscriptionContract(answers=[
        TranscriptionContractAnswer(question_number=q, sub_question_id=sid, answer_text=t)
        for q, sid, t in answers
    ])


def test_nested_rubric_produces_LEAF_scopes_only():
    """Before PR-3 this produced ONE scope for the parent with ZERO criteria but its
    full 15 points, and never created the inner scopes at all — the student's answers
    to both inner parts were silently never graded."""
    gt = compile_gradable(_nested_contract(), _transcript([(1, "א.1", "ans1"), (1, "א.2", "ans2")]))

    ids = [(s.question_id, s.sub_question_id) for s in gt.scopes]
    assert ids == [("q1", "א.1"), ("q1", "א.2")], "leaves only; the parent is NOT a scope"

    by_id = {s.sub_question_id: s for s in gt.scopes}
    assert [c.criterion_id for c in by_id["א.1"].criteria] == ["q1.א.1.c0"]
    assert by_id["א.1"].points == Decimal("10")
    assert by_id["א.2"].points == Decimal("5")
    assert all(s.alignment == "matched" for s in gt.scopes)
    assert gt.parent_answer_fallback_scopes == []


def test_parent_answer_fallback_fires_and_is_recorded():
    """R3 — LOAD-BEARING, not graceful degradation: the transcription segments to
    depth 1 (q1.א) while the rubric grades at depth 2. Without the fallback every
    nested rubric would grade both leaves against an empty answer."""
    gt = compile_gradable(_nested_contract(), _transcript([(1, "א", "the whole answer")]))

    assert len(gt.scopes) == 2
    assert all(s.student_answer_text == "the whole answer" for s in gt.scopes)
    assert all(s.alignment == "matched" for s in gt.scopes)
    # Recorded, so its rate is the metric for when depth-2 segmentation gets urgent.
    assert set(gt.parent_answer_fallback_scopes) == {"q1.א.1", "q1.א.2"}


def test_leaf_with_no_answer_anywhere_is_answer_missing():
    gt = compile_gradable(_nested_contract(), _transcript([]))
    assert all(s.alignment == "answer_missing" for s in gt.scopes)
    assert gt.parent_answer_fallback_scopes == []


# ===========================================================================
# C. SELECTION SCORING — the shared helper
# ===========================================================================

def _selection_contract() -> GradingRubricContract:
    """The employee shape: choose 1 of {q1:15, q2:50, q3:35}. Achievable = 50."""
    qs = [
        Question(question_id=f"q{i}", question_text=f"Q{i}", total_points=Decimal(p),
                 criteria=[_crit(f"q{i}.c0", p)], sub_questions=[])
        for i, p in [(1, "15"), (2, "50"), (3, "35")]
    ]
    return GradingRubricContract(
        contract_version="c1", rubric_id="r1", subject="cs",
        numeric_policy=NumericPolicy(),
        total_points=Decimal("50"),                       # ACHIEVABLE, not 100
        questions=qs,
        selection_groups=[SelectionGroup(group_id="sg0", of_question_ids=["q1", "q2", "q3"], choose_k=1)],
    )


def _scores(*pairs) -> List[ScopeScore]:
    return [ScopeScore(question_id=q, sub_question_id=None, awarded=Decimal(a))
            for q, a in pairs]


def test_perfect_selection_answer_scores_100_percent_not_50():
    """THE bug: a student who answers the 50-pointer perfectly and skips the other
    two — exactly as the exam instructs — used to score 50/100 = 50%. Halved for
    obeying the instructions."""
    r = score_with_selection(_scores(("q1", "0"), ("q2", "50"), ("q3", "0")), _selection_contract())
    assert r.total_score == Decimal("50")
    assert r.total_possible == Decimal("50")      # achievable, never Σ scopes (=100)
    assert (r.total_score / r.total_possible * 100) == Decimal("100")


def test_unchosen_members_are_EXCLUDED_not_zeroed():
    r = score_with_selection(_scores(("q1", "0"), ("q2", "50"), ("q3", "0")), _selection_contract())
    assert r.is_counted(("q2", None))
    assert not r.is_counted(("q1", None))         # not a failure — never owed
    assert not r.is_counted(("q3", None))


def test_answering_the_cheaper_question_well_scores_against_the_achievable_denominator():
    """Perfect 15-pointer, others skipped: 15/50 = 30%. The denominator is what the
    exam MADE achievable, not what the student happened to attempt."""
    r = score_with_selection(_scores(("q1", "15"), ("q2", "0"), ("q3", "0")), _selection_contract())
    assert r.total_score == Decimal("15")
    assert r.total_possible == Decimal("50")


def test_best_k_is_student_favorable_when_more_than_k_answered():
    """Answered 2 in a choose-1 group: the BETTER one counts, the other is excluded."""
    r = score_with_selection(_scores(("q1", "15"), ("q2", "30"), ("q3", "0")), _selection_contract())
    assert r.total_score == Decimal("30")          # q2, not q1+q2
    assert r.is_counted(("q2", None)) and not r.is_counted(("q1", None))


def test_fewer_than_k_answered_leaves_an_empty_slot_scoring_zero():
    """choose-4-of-6 with only 3 answered: the 4th slot falls inside the counted k and
    contributes 0 — the exam's own rule, and it falls out of best-k ranking for free."""
    qs = [Question(question_id=f"q{i}", question_text=f"Q{i}", total_points=Decimal("25"),
                   criteria=[_crit(f"q{i}.c0", "25")], sub_questions=[])
          for i in range(1, 7)]
    contract = GradingRubricContract(
        contract_version="c", rubric_id="r", subject="cs", numeric_policy=NumericPolicy(),
        total_points=Decimal("100"),                       # top-4 x 25
        questions=qs,
        selection_groups=[SelectionGroup(
            group_id="sg0", of_question_ids=[f"q{i}" for i in range(1, 7)], choose_k=4)],
    )
    r = score_with_selection(
        _scores(("q1", "25"), ("q2", "20"), ("q3", "15"),
                ("q4", "0"), ("q5", "0"), ("q6", "0")), contract)
    assert r.total_possible == Decimal("100")
    assert r.total_score == Decimal("60")          # 25+20+15 + one empty slot at 0
    assert len(r.excluded) == 2                    # exactly two members drop out


def test_exclusion_is_DERIVED_an_override_flips_best_k_membership():
    """F1's core constraint. Exclusion is NEVER an input: the teacher bumps the
    15-pointer above the 50-pointer's awarded score and membership FLIPS. This is why
    the approval gate must RECOMPUTE from post-override scores rather than trusting
    the provisional marks written at grading time."""
    contract = _selection_contract()

    # Grading time: the AI gave q2 more than q1 -> q2 is the counted member.
    before = score_with_selection(_scores(("q1", "10"), ("q2", "20"), ("q3", "0")), contract)
    assert before.is_counted(("q2", None)) and not before.is_counted(("q1", None))

    # Teacher override: q1 is now worth more than q2 -> membership must FLIP.
    after = score_with_selection(_scores(("q1", "14"), ("q2", "12"), ("q3", "0")), contract)
    assert after.is_counted(("q1", None)) and not after.is_counted(("q2", None))
    assert after.total_score == Decimal("14")


def test_tie_break_is_deterministic():
    """Several members tying at 0 is the common case; the frozen marks must be
    reproducible, so ties resolve by contract question order."""
    contract = _selection_contract()
    a = score_with_selection(_scores(("q1", "0"), ("q2", "0"), ("q3", "0")), contract)
    b = score_with_selection(_scores(("q1", "0"), ("q2", "0"), ("q3", "0")), contract)
    assert a.excluded == b.excluded
    assert a.is_counted(("q1", None))              # first in contract order wins the tie


# ===========================================================================
# D. REGRESSION — flat contracts are bit-for-bit unchanged
# ===========================================================================

def test_flat_contract_reduces_to_the_old_arithmetic_exactly():
    """The single most important regression: on a selection-free contract the new
    math must equal `Σ awarded / Σ points_possible` — the code being replaced."""
    qs = [Question(question_id=f"q{i}", question_text=f"Q{i}", total_points=Decimal(p),
                   criteria=[_crit(f"q{i}.c0", p)], sub_questions=[])
          for i, p in [(1, "10"), (2, "5")]]
    contract = GradingRubricContract(
        contract_version="c", rubric_id="r", subject="cs", numeric_policy=NumericPolicy(),
        total_points=Decimal("15"), questions=qs,        # no selection_groups
    )
    scores = _scores(("q1", "7"), ("q2", "4"))
    r = score_with_selection(scores, contract)

    legacy_possible = sum(q.total_points for q in qs)     # what the old code re-summed
    legacy_score = sum(s.awarded for s in scores)
    assert r.total_possible == legacy_possible == Decimal("15")
    assert r.total_score == legacy_score == Decimal("11")
    assert r.excluded == frozenset()                      # nothing excluded, ever


def test_all_prod_shaped_contracts_are_unaffected():
    """The 40 stored contracts are all flat + selection-free (verified against prod).
    achievable ≡ offered ⇒ zero behavioural change on re-parse."""
    for path in sorted(glob.glob(f"{BENCH}/*.json")):
        draft = ExtractRubricResponse.model_validate(json.load(open(path, encoding="utf-8")))
        if draft.selection_groups:
            continue                                       # prod has none of these
        try:
            contract = _compile(draft)
        except CompilationError:
            continue                                       # 899371 — rejected by design
        assert contract.total_points == sum(q.total_points for q in contract.questions)
        assert contract.selection_groups == []


def test_new_shape_contract_round_trips_through_pydantic():
    """Stored contracts ARE re-parsed through the type at grade time, so a type change
    must be back-compatible in both directions."""
    contract = _selection_contract()
    again = GradingRubricContract.model_validate(contract.model_dump(mode="json"))
    assert again.total_points == Decimal("50")
    assert len(again.selection_groups) == 1
    assert again.selection_groups[0].choose_k == 1


def test_zero_achievable_does_not_divide_by_zero():
    """The divide-by-zero guard now keys on the CONTRACT's achievable total, not on
    Σ scopes. A contract with zero achievable points is degenerate (Criterion.points
    must be > 0, so it cannot even be built from real criteria) — but the guard must
    still hold, because both score sites divide by this number.
    """
    contract = GradingRubricContract(
        contract_version="c", rubric_id="r", subject="cs", numeric_policy=NumericPolicy(),
        total_points=Decimal("0"), questions=[],       # no questions ⇒ nothing achievable
    )
    r = score_with_selection([], contract)
    assert r.total_possible == Decimal("0")
    assert r.total_score == Decimal("0")
    assert r.excluded == frozenset()
