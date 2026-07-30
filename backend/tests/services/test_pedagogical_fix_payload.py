"""
PR-6 backend contract — what Step 2c hands the findings UI.

Two properties the UI depends on and could not previously rely on:

  1. ANCHOR. A sub-question mistake targets the FULL PATH (`q1.א.2`) — the same
     scope vocabulary the client validator, the compiler and the mirror speak. A
     bare `sub_question_id` cannot be paired with its own live blocker, and is
     ambiguous besides (every question has a 'א').

  2. FIX. A point-sum mismatch carries a real `SuggestedFix` whose new value is
     the node's OWN children-sum — nothing invented. `requires_teacher_input`
     stays True: it means "never apply without her", which a one-click proposal
     she must click implements rather than overrides.

Selection-normalization deliberately has NO fix: its intent is unknowable, and
proposing a number there would fabricate teacher content.

Pure and offline — no LLM (llm=None ⇒ Tier A only), no DB.
"""
from decimal import Decimal

from app.schemas.ontology_types import (
    Criterion, ExtractRubricResponse, PedagogicalMistakeKind, Question,
    PedagogicalMistake, SelectionGroup, SubQuestion,
)
from app.services.docx_v3.pedagogical_mistakes import detect_pedagogical_mistakes


def _crit(cid: str, pts: str) -> Criterion:
    return Criterion(criterion_id=cid, index=0, description=f"d-{cid}", points=Decimal(pts))


def _detect(draft: ExtractRubricResponse):
    return detect_pedagogical_mistakes(draft, rendered_markdown="", llm=None)


def _nested_draft() -> ExtractRubricResponse:
    """q1 → א → (1, 2). The inner '2' declares 3 but its criteria sum to 2."""
    inner1 = SubQuestion(sub_question_id="1", index=0, points=Decimal("12"),
                         criteria=[_crit("c1", "12")])
    inner2 = SubQuestion(sub_question_id="2", index=1, points=Decimal("3"),
                         criteria=[_crit("c2", "1.5"), _crit("c3", "0.5")])
    a = SubQuestion(sub_question_id="א", index=0, points=Decimal("15"),
                    criteria=[], sub_questions=[inner1, inner2])
    q = Question(question_id="q1", question_type="coding_task",
                 total_points=Decimal("15"), criteria=[], sub_questions=[a])
    return ExtractRubricResponse(rubric_name="t", total_points=Decimal("15"), questions=[q])


def test_sub_question_mistake_anchors_on_the_full_path():
    found = [m for m in _detect(_nested_draft())
             if m.kind == PedagogicalMistakeKind.POINT_SUM_MISMATCH]
    targets = {m.target_id for m in found}
    assert "q1.א.2" in targets, f"expected the full path, got {targets}"
    assert "2" not in targets, "a BARE sub_question_id is ambiguous across questions"


def test_mistake_id_matches_the_full_path_too():
    m = next(m for m in _detect(_nested_draft()) if m.target_id == "q1.א.2")
    assert m.mistake_id == "pts:q1.א.2"


def test_point_sum_fix_proposes_the_nodes_own_children_sum():
    m = next(m for m in _detect(_nested_draft()) if m.target_id == "q1.א.2")
    assert m.suggested_fix is not None, "the one-click proposal must exist in the payload"
    fix = m.suggested_fix
    assert fix.operation == "adjust_points"
    assert fix.params["new_value"] == "2.0"          # 1.5 + 0.5 — HER arithmetic
    assert fix.params["current_value"] == "3"
    assert fix.params["target"] == "sub_question"
    assert fix.params["field"] == "points"
    # teacher-facing number carries no trailing zeros
    assert fix.description == "עדכני את הניקוד המוצהר ל-2"


def test_requires_teacher_input_stays_true_even_with_a_fix():
    # The flag means "never apply without her" — a proposal she must click IS that.
    m = next(m for m in _detect(_nested_draft()) if m.target_id == "q1.א.2")
    assert m.requires_teacher_input is True
    assert m.suggested_fix is not None


def test_question_level_fix_targets_total_points():
    q = Question(question_id="q1", question_type="coding_task", total_points=Decimal("40"),
                 criteria=[_crit("c1", "10"), _crit("c2", "11")], sub_questions=[])
    draft = ExtractRubricResponse(rubric_name="t", total_points=Decimal("21"), questions=[q])
    m = next(m for m in _detect(draft) if m.target_id == "q1")
    assert m.suggested_fix.params == {
        "target": "question", "field": "total_points",
        "new_value": "21", "current_value": "40",
    }


def test_rubric_level_fix_uses_the_achievable_total():
    q = Question(question_id="q1", question_type="coding_task", total_points=Decimal("21"),
                 criteria=[_crit("c1", "21")], sub_questions=[])
    draft = ExtractRubricResponse(rubric_name="t", total_points=Decimal("100"), questions=[q])
    m = next(m for m in _detect(draft) if m.target_id is None
             and m.kind == PedagogicalMistakeKind.POINT_SUM_MISMATCH)
    assert m.suggested_fix.params["target"] == "rubric"
    assert m.suggested_fix.params["new_value"] == "21"
    assert m.suggested_fix.description == "עדכני את סך נקודות המחוון ל-21"


def test_selection_normalization_proposes_NOTHING():
    """Its intent is unknowable — equalise? drop? scale? Proposing a number here
    would invent teacher content, which Faithful Capture forbids."""
    qs = [
        Question(question_id="q1", question_type="coding_task", total_points=Decimal("25"),
                 criteria=[_crit("c1", "25")], sub_questions=[]),
        Question(question_id="q2", question_type="coding_task", total_points=Decimal("50"),
                 criteria=[_crit("c2", "50")], sub_questions=[]),
    ]
    draft = ExtractRubricResponse(
        rubric_name="t", total_points=Decimal("50"), questions=qs,
        selection_groups=[SelectionGroup(group_id="sg0", of_question_ids=["q1", "q2"], choose_k=1)],
    )
    m = next(m for m in _detect(draft)
             if m.kind == PedagogicalMistakeKind.SELECTION_NORMALIZATION)
    assert m.suggested_fix is None
    assert m.requires_teacher_input is True


def test_a_clean_draft_produces_no_mistakes():
    q = Question(question_id="q1", question_type="coding_task", total_points=Decimal("10"),
                 criteria=[_crit("c1", "10")], sub_questions=[])
    draft = ExtractRubricResponse(rubric_name="t", total_points=Decimal("10"), questions=[q])
    assert _detect(draft) == []


# ---------------------------------------------------------------------------
# PR-6 §6 — THE ACKNOWLEDGMENT WAKE-UP.
#
# The frontend never sent `annotations`, so `compile()`'s acknowledgment gate has
# never fired in the product flow. PR-6 starts sending them (the draft must carry
# its findings to survive a reopen), which WAKES that gate for the first time.
#
# For UI users this server gate is DEFENSIVE: open blockers are stopped client-side
# by the survivor gate, and every decided finding travels with the save as an ack.
# It fires for direct-API callers. Defensive paths that never run in the normal
# flow are exactly the ones that rot untested — hence this explicit battery.
# ---------------------------------------------------------------------------

from app.schemas.ontology_types import (
    Annotation, AnnotationSeverity, NumericPolicy, WarningsRequireAcknowledgment,
)
from app.services.contract_compiler import ContractCompiler


def _clean_draft() -> ExtractRubricResponse:
    q = Question(question_id="q1", question_type="coding_task", total_points=Decimal("10"),
                 criteria=[_crit("c1", "10")], sub_questions=[])
    return ExtractRubricResponse(rubric_name="t", total_points=Decimal("10"), questions=[q])


def _warned_draft() -> ExtractRubricResponse:
    """A clean-summing draft that still carries the extraction's WARNING annotation —
    exactly the shape a resolved finding produces: her arithmetic is right NOW, and
    the static annotation about the original document is still attached."""
    return _clean_draft().model_copy(update={"annotations": [Annotation(
        annotation_type="rubric_mismatch",
        severity=AnnotationSeverity.WARNING,
        message="אזהרה: סכום הנקודות של תת-השאלות בQ1 …",
        target_id="q1",
    )]})


def test_wakeup_no_annotations_compiles_clean_the_pre_pr6_behaviour():
    ContractCompiler().compile(_clean_draft(), policy=NumericPolicy())   # must not raise


def test_wakeup_annotation_without_ack_is_REFUSED():
    try:
        ContractCompiler().compile(_warned_draft(), policy=NumericPolicy())
    except WarningsRequireAcknowledgment as e:
        assert [w.id for w in e.warnings] == ["rubric_mismatch:q1"]
    else:
        raise AssertionError("the gate must refuse an unacknowledged warning annotation")


def test_wakeup_annotation_WITH_ack_compiles_clean():
    contract = ContractCompiler().compile(
        _warned_draft(), policy=NumericPolicy(),
        acknowledged_warnings=["rubric_mismatch:q1"],
    )
    assert contract is not None


def test_the_ack_id_is_the_annotations_own_id_not_a_reconstruction():
    """The client reads ids off the annotation; it never rebuilds f'{type}:{target}'.
    A server-minted id must therefore round-trip unchanged through the gate."""
    draft = _clean_draft().model_copy(update={"annotations": [Annotation(
        annotation_type="rubric_mismatch", severity=AnnotationSeverity.WARNING,
        message="m", target_id="q1", id="server-minted-uuid-1234",
    )]})
    try:
        ContractCompiler().compile(draft, policy=NumericPolicy())
    except WarningsRequireAcknowledgment as e:
        assert [w.id for w in e.warnings] == ["server-minted-uuid-1234"]
    ContractCompiler().compile(draft, policy=NumericPolicy(),
                               acknowledged_warnings=["server-minted-uuid-1234"])


def test_info_and_error_annotations_do_not_enter_the_ack_set():
    """Only WARNING requires acknowledgment: INFO proceeds silently, ERROR blocks
    outright (a different path). Neither should be ack-able."""
    draft = _clean_draft().model_copy(update={"annotations": [Annotation(
        annotation_type="review_flag", severity=AnnotationSeverity.INFO,
        message="m", target_id="q1",
    )]})
    ContractCompiler().compile(draft, policy=NumericPolicy())   # INFO ⇒ no gate


# ---------------------------------------------------------------------------
# PR-6 §4 — provenance round-trips BOTH directions (A3).
# Before this, Pydantic's default extra='ignore' meant these fields were accepted
# and silently discarded: her decision would look saved and be gone on reopen.
# ---------------------------------------------------------------------------

def test_provenance_fields_round_trip_through_the_model():
    draft = _clean_draft().model_copy(update={"pedagogical_mistakes": [PedagogicalMistake(
        mistake_id="pts:q1", kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
        target_id="q1", explanation="e",
        dismissed=True, dismissed_at="2026-07-30T10:00:00Z",
        fix_applied=False, fix_applied_at=None,
    )]})
    revived = ExtractRubricResponse.model_validate_json(draft.model_dump_json())
    m = revived.pedagogical_mistakes[0]
    assert m.dismissed is True
    assert m.dismissed_at == "2026-07-30T10:00:00Z"
    assert m.fix_applied is False


def test_absent_provenance_means_UNDECIDED_not_dismissed():
    """A draft saved before PR-6 has no decisions recorded. None must never be read
    as a decision — that would silently answer a question on her behalf."""
    m = PedagogicalMistake(mistake_id="x", kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
                           target_id="q1", explanation="e")
    assert m.dismissed is None and m.fix_applied is None
    assert m.dismissed is not False, "None and False are different states"


def test_provenance_survives_the_save_shaped_dict_round_trip():
    """The save path does model_validate(dict) → model_dump(mode='json') → JSONB."""
    src = _clean_draft().model_copy(update={"pedagogical_mistakes": [PedagogicalMistake(
        mistake_id="pts:q1.א.2", kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
        target_id="q1.א.2", explanation="e",
        fix_applied=True, fix_applied_at="2026-07-30T11:00:00Z",
    )]})
    as_dict = src.model_dump(mode="json")
    stored = ExtractRubricResponse.model_validate(as_dict).model_dump(mode="json")
    assert stored["pedagogical_mistakes"][0]["fix_applied"] is True
    assert stored["pedagogical_mistakes"][0]["fix_applied_at"] == "2026-07-30T11:00:00Z"
