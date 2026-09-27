"""The approval half of CWV-3 / CWV-4 / GATE-1, on legacy drafts.

Drafts graded before CWV-1 carry an ERROR `closed_world_violation` annotation
whose target is an id that exists nowhere in the draft (graded_test 271813b4:
`q1.a.1.c0.k1`). Nothing on the review screen can resolve it, so under GATE-1
it must not block. What the gate still protects is what she SIGNS:

  * the frozen contract names no id outside the draft's closed world (CWV-3);
  * the frozen total is the total she was shown (CWV-4);
  * a REAL check that received no machine verdict is decided by her before it
    freezes — the OD-R1 «every check decided» bar, now at check granularity
    (OD-4). That is a block she resolves in place, with the keys she already has.
"""
from __future__ import annotations

import json

import pytest

from app.schemas.graded_test_draft import GradingAnnotation
from app.schemas.ontology_types import AnnotationSeverity
from app.services.graded_test_contract_compiler import GateError, compile_graded_test

from .test_graded_test_contract_compiler import (
    _draft, _leaf_criterion, _no_ov, _ov, _pinned, _rubric_contract, _scope,
)

STRAY = "q1.a.1.c0.k1"


def _legacy_stray():
    return GradingAnnotation(
        severity=AnnotationSeverity.ERROR, target_id=STRAY,
        annotation_type="closed_world_violation",
        message=f"המודל החזיר פסיקה לבדיקה לא מוכרת: {STRAY}",
        metadata={"extra_id": STRAY, "scope": "q1.א.1"})


def _no_verdict(terminal_id="q1.c0", check_id="q1.c0.k1"):
    return GradingAnnotation(
        severity=AnnotationSeverity.WARNING, target_id=terminal_id,
        annotation_type="unverified_check",
        message="הבדיקה 'x' לא אומתה — לא ניתן זיכוי",
        metadata={"check_id": check_id})


def test_a_legacy_stray_verdict_annotation_no_longer_blocks():
    """H1 on a legacy row: the stray is gone, every real check has its verdict."""
    draft = _draft(annotations=[_legacy_stray()])
    contract = compile_graded_test(draft, _no_ov(), _rubric_contract(total_points="5"))
    assert contract is not None


def test_the_contract_carries_no_unknown_id():
    draft = _draft(annotations=[_legacy_stray()])
    contract = compile_graded_test(draft, _no_ov(), _rubric_contract(total_points="5"))
    assert STRAY not in json.dumps(contract.model_dump(mode="json"), ensure_ascii=False)


def test_the_frozen_total_is_the_total_she_was_shown():
    """CWV-4: the stray never reached the pricer, so both sides price the same
    verdict set — the draft's checks plus her overlay."""
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[
        _leaf_criterion("q1.c0", points_possible="5", points_awarded="4"),
        _leaf_criterion("q1.c1", points_possible="10", points_awarded="10")])],
        annotations=[_legacy_stray()])
    shown = sum(s.points_awarded for s in draft.scope_outcomes)
    contract = compile_graded_test(draft, _no_ov(), _rubric_contract(total_points="15"))
    assert contract.total_score == shown


def test_a_real_check_with_no_verdict_blocks_until_she_decides_it():
    """H4 — the production row's consequence. A machine zero no one read must
    not freeze (the §5 catastrophe OD-R1 exists for), so she decides it; the
    violation names a thing she can act on and carries no machine vocabulary."""
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[
        _leaf_criterion("q1.c0", points_possible="5", points_awarded="0")])],
        annotations=[_legacy_stray(), _no_verdict()])

    with pytest.raises(GateError) as exc_info:
        compile_graded_test(draft, _no_ov(), _rubric_contract(total_points="5"))
    violations = exc_info.value.violations
    assert [v.violation_kind for v in violations] == ["undecided_check"]
    assert violations[0].terminal_id == "q1.c0"

    contract = compile_graded_test(
        draft, _ov("q1.c0", "q1.c0.k1", "met"), _rubric_contract(total_points="5"))
    assert contract.total_score == 5


def test_a_typed_criterion_amount_also_decides_its_no_verdict_check():
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[
        _leaf_criterion("q1.c0", points_possible="5", points_awarded="0")])],
        annotations=[_no_verdict()])
    assert compile_graded_test(draft, _pinned("q1.c0", "3"),
                               _rubric_contract(total_points="5"))


def test_llm_failure_stays_as_it_was():
    """Not widened: a crashed scope's rule is unchanged by this PR (R6 lists its
    no-checks dead end as a follow-up)."""
    ann = GradingAnnotation(severity=AnnotationSeverity.ERROR, target_id="q1",
                            annotation_type="llm_failure", message="x")
    with pytest.raises(GateError):
        compile_graded_test(_draft(annotations=[ann]), _no_ov(), _rubric_contract())
