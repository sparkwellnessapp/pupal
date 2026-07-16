"""Does the compiler's diagnosis actually REACH the teacher?

Every test here was written after a bug that a fully-green suite did not catch, because
the suite tested the compiler and the payload builder in isolation and never asked what
survived the trip between them. The answer, on deploy day, was: not much. A real INV-2
violation arrived at the teacher's RTL Hebrew screen as

    {"location": "q1.א.2", "invariant": null, "expected": null, "actual": null,
     "message_he": "Sub-question q1.א.2: criteria sum (2.0) differs from..."}

— the named invariant gone, both numbers gone, and an ENGLISH sentence in the field named
`message_he`. The compiler was right the whole time. The MIRROR was lossy.

So these tests assert on the boundary, not the endpoints of it.
"""
from decimal import Decimal

import pytest

from app.schemas.ontology_types import Annotation, AnnotationSeverity
from app.services.rubric_management_service import (
    _annotation_to_schema,
    _contract_total,
    calculate_rubric_stats,
)


# ---------------------------------------------------------------------------
# The mirror must be TOTAL
# ---------------------------------------------------------------------------

def test_annotation_to_schema_carries_every_field_a_teacher_needs():
    """The four fields PR-3 added must survive the conversion to the API schema.

    They did not. AnnotationSchema mirrored 5 of Annotation's 9 fields, and the payload
    builder read the missing ones with getattr(..., None) — so the loss was SILENT and
    degraded into nulls plus an English fallback rather than crashing.
    """
    ann = Annotation(
        annotation_type="invariant_violation",
        severity=AnnotationSeverity.ERROR,
        message="Sub-question q1.א.2: criteria sum (2) differs from declared points (3) by 1",
        message_he="סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)",
        target_id="q1.א.2",
        invariant="INV-2",
        expected="3",
        actual="2",
    )

    schema = _annotation_to_schema(ann)

    assert schema.target_id == "q1.א.2"
    assert schema.invariant == "INV-2"
    assert schema.expected == "3"
    assert schema.actual == "2"
    assert schema.message_he == ann.message_he
    assert schema.message_he != schema.message, "Hebrew field must not hold the English string"


def test_annotation_schema_mirrors_every_annotation_field():
    """A structural guard, so the NEXT field added to Annotation cannot go missing.

    This is the test that would have caught the bug at the moment it was introduced,
    rather than in production three weeks later.
    """
    from app.schemas.rubric_management import AnnotationSchema

    annotation_fields = set(Annotation.model_fields)
    schema_fields = set(AnnotationSchema.model_fields)

    # Fields the API deliberately does not expose. Anything else missing is a leak.
    intentionally_dropped = {"confidence", "source_span", "metadata"} & annotation_fields
    missing = annotation_fields - schema_fields - intentionally_dropped

    assert not missing, (
        f"AnnotationSchema is missing {sorted(missing)} — a mirror that omits fields "
        f"silently truncates the teacher's diagnosis. Add them to AnnotationSchema AND "
        f"to _annotation_to_schema, or add them to intentionally_dropped with a reason."
    )


# ---------------------------------------------------------------------------
# total_points means ACHIEVABLE — the fifth consumer
# ---------------------------------------------------------------------------

SELECTION_DRAFT = {
    "questions": [
        {"question_id": "q1", "total_points": "50", "criteria": [{"criterion_id": "c1", "points": "50"}]},
        {"question_id": "q2", "total_points": "50", "criteria": [{"criterion_id": "c2", "points": "50"}]},
    ],
    "selection_groups": [{"group_id": "g1", "choose_k": 1, "member_question_ids": ["q1", "q2"]}],
}


def test_stats_report_the_contract_total_not_a_re_sum():
    """A "choose 1 of 2" exam offers 100 and is worth 50.

    The old Σ-every-question reported 100 — and the save path writes that number to the
    `rubrics.total_points` COLUMN, so the row contradicted its own contract_json and the
    rubric card advertised a total the grader would never award. Fifth re-summing site.
    """
    stats = calculate_rubric_stats(SELECTION_DRAFT, contract_total=50.0)
    assert stats.total_points == 50.0, "the contract is the single source of the total"


def test_stats_fall_back_to_the_offered_sum_only_when_uncompiled():
    """An uncompiled draft has no contract to consult — the estimate is all there is.

    Documented, not accidental: this is the ONE moment the number may over-report, and it
    is corrected the instant compilation produces a contract.
    """
    stats = calculate_rubric_stats(SELECTION_DRAFT)
    assert stats.total_points == 100.0


def test_criteria_are_counted_at_any_depth():
    """The flat count saw only depth-1 criteria — the same nesting-blindness INV-2 had."""
    nested = {
        "questions": [{
            "question_id": "q1",
            "total_points": "10",
            "sub_questions": [{
                "sub_question_id": "א",
                "points": "10",
                "sub_questions": [
                    {"sub_question_id": "1", "points": "7",
                     "criteria": [{"criterion_id": "c1", "points": "7"}]},
                    {"sub_question_id": "2", "points": "3",
                     "criteria": [{"criterion_id": "c2", "points": "1.5"},
                                  {"criterion_id": "c3", "points": "1.5"}]},
                ],
            }],
        }],
    }
    stats = calculate_rubric_stats(nested, contract_total=10.0)
    assert stats.total_criteria == 3, "criteria two levels down are still criteria"


@pytest.mark.parametrize("contract_json,expected", [
    ({"total_points": "50"}, 50.0),
    ({"total_points": 50}, 50.0),
    (None, None),                      # uncompiled draft — nothing authoritative to read
    ({}, None),
    ({"total_points": None}, None),
    ({"total_points": "garbage"}, None),
])
def test_contract_total_reads_the_frozen_contract(contract_json, expected):
    class _Row:
        pass
    row = _Row()
    row.contract_json = contract_json
    assert _contract_total(row) == expected
