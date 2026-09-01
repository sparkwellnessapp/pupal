"""
plan-gen/v2 — deduction detection (deterministic) and V11 (completeness).

Phase 0 measured why this moved into code. The generator READ the missed
deduction's concept — it emitted charge_group="max_instead_of_min" — and still
anchored it to the wrong sub-criterion at the wrong amount. Locating a deduction
phrase in Hebrew prose, copying its number, and knowing whose text contains it
are string and lookup tasks. Only "which sub-criterion does this modify" is
judgement, and V11 narrows that to a bounded choice among named candidates.

Detector calibration is against the RATIFIED plan, which the PLAYBOOK entry of
2026-09-01 permits for a new rule: the artefact is the standard.
"""
from __future__ import annotations

import io
from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
from app.agents.plan_gen.dispositions import (
    escape_hatch_count, validate_dispositions)
from app.agents.plan_gen.generator import contract_scopes
from app.agents.plan_gen.prompt import DetectedDeduction, detect_deductions
from app.agents.plan_gen.schemas import Disposition

PLAN = "tests/grading_eval_suite/plans/hobby_tvshow.plan.json"


def _detected():
    from tests.grading_eval_suite.fixtures import load_bundle

    bundle = load_bundle("dan_basiuk")
    out = {}
    for key, q, sub in contract_scopes(bundle.rubric_contract):
        label = f"{key[0]}.{key[1]}" if key[1] else key[0]
        out[label] = detect_deductions(q, sub)
    return out, bundle.terminal_infos


# ---------------------------------------------------------------------------
# detector-finds-every-reference-tariff
# ---------------------------------------------------------------------------

def test_detector_finds_every_reference_tariff():
    """All 12 GENERATED-source tariffs, from their own source text, with the
    owning terminal among the candidates.

    The other two of the reference's 14 are source="ruling" — an owner ruling
    citing a GT note, and an owner tariff tag. Neither is a deduction phrase in
    the teacher's text, so no detector reading the rubric can find them. They
    are layer 1 by definition, and this test asserts the reachable set rather
    than pretending otherwise.
    """
    plan = GradingPlan.model_validate_json(io.open(PLAN, encoding="utf-8").read())
    detected, infos = _detected()

    def scope_of(tid):
        info = infos[tid]
        return (f"{info.question_id}.{info.sub_question_id}"
                if info.sub_question_id else info.question_id)

    targets = [(t.terminal_id, c.tariff_amount)
               for t in plan.terminals for c in t.checks
               if c.kind == "tariff" and c.source == "generated"]
    assert len(targets) == 12

    missed = []
    for tid, amount in targets:
        hits = [d for d in detected.get(scope_of(tid), [])
                if d.polarity == "deduct" and d.amount == amount
                and tid in d.candidate_terminal_ids]
        if not hits:
            missed.append(f"{tid}@{amount}")
    assert not missed, f"detector missed derivable tariffs: {missed}"


def test_the_phase_0_miss_is_now_detected_with_the_right_candidate():
    """The one derivable tariff v1 got wrong. The detector must surface it at
    amount 3 with s3 among the candidates, so the model's only remaining job is
    choosing between named siblings."""
    detected, _ = _detected()
    hits = [d for d in detected["q2.ב"]
            if d.polarity == "deduct" and d.amount == Decimal("3")
            and "q2.ב.c4.s3" in d.candidate_terminal_ids]
    assert hits, "the Phase-0 miss is not detected with s3 as a candidate"


def test_the_single_note_only_is_detected_as_no_deduct():
    detected, _ = _detected()
    hits = [d for d in detected["q2.ב"]
            if d.polarity == "no_deduct"
            and "q2.ב.c4.s3" in d.candidate_terminal_ids]
    assert hits, "the reference's note_only marker is not detected"
    assert hits[0].amount is None, "a no-deduct marker must carry no amount"


# ---------------------------------------------------------------------------
# negation-is-never-read-as-deduction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,polarity", [
    ("אם לא בדקו את הקלט להוריד 2", "deduct"),
    ("אם לא בדקו את הקלט לא להוריד, רק לציין", "no_deduct"),
    ("אין להוריד נקודות על סגנון", "no_deduct"),
    ("לא מורידים על שמות משתנים", "no_deduct"),
])
def test_negation_is_never_read_as_deduction(text, polarity):
    """A do-not-deduct instruction read as a deduction would apply a penalty the
    teacher explicitly waived — worse than missing one."""
    from app.agents.plan_gen.prompt import _scan

    hits = _scan(text)
    assert hits, f"nothing detected in {text!r}"
    assert hits[0][2] == polarity, hits


# ---------------------------------------------------------------------------
# V11
# ---------------------------------------------------------------------------

def _marker(mid="d1", amount="1", polarity="deduct", cands=("t",)):
    return DetectedDeduction(
        marker_id=mid, quote="marker clause",
        amount=None if polarity == "no_deduct" else Decimal(amount),
        polarity=polarity, source_field="t.description",
        candidate_terminal_ids=cands)


def _terminal(amount="1"):
    return [TerminalPlan(terminal_id="t", points_possible=Decimal("2"), checks=[
        PlanCheck(check_id="t.k1", description_he="req", kind="required",
                  points=Decimal("2"), rubric_quote="q" * 20),
        PlanCheck(check_id="t.t1", description_he="tar", kind="tariff",
                  points=Decimal("0"), tariff_amount=Decimal(amount),
                  rubric_quote="q" * 20)])]


def test_v11_rejects_a_dropped_marker():
    """The whole point: a detected deduction the model simply ignored."""
    errs = validate_dispositions([_marker()], [], _terminal())
    assert any("NO disposition" in e for e in errs), errs


def test_v11_rejects_a_substituted_amount():
    """v1's actual failure — the concept read, the number invented. The teacher
    wrote 3; a plan that deducts 1 is not a rounding difference, it is a
    different rule."""
    errs = validate_dispositions(
        [_marker(amount="3")],
        [Disposition(marker_id="d1", disposition="tariff", check_id="t.t1")],
        _terminal(amount="1"))
    assert any("copy the number the teacher wrote" in e for e in errs), errs


def test_v11_rejects_a_no_deduct_marker_disposed_as_tariff():
    errs = validate_dispositions(
        [_marker(polarity="no_deduct")],
        [Disposition(marker_id="d1", disposition="tariff", check_id="t.t1")],
        _terminal())
    assert any("may not be disposed as a tariff" in e for e in errs), errs


def test_v11_rejects_an_anchor_outside_the_candidates():
    errs = validate_dispositions(
        [_marker(cands=("other",))],
        [Disposition(marker_id="d1", disposition="tariff", check_id="t.t1")],
        _terminal())
    assert any("not among its candidates" in e for e in errs), errs


def test_v11_requires_a_reason_for_the_escape_hatch():
    errs = validate_dispositions(
        [_marker()],
        [Disposition(marker_id="d1", disposition="not_a_deduction")],
        _terminal())
    assert any("no reason" in e for e in errs), errs

    clean = validate_dispositions(
        [_marker()],
        [Disposition(marker_id="d1", disposition="not_a_deduction",
                     reason="describes a past score, not a grading rule")],
        _terminal())
    assert not clean, clean


def test_v11_accepts_a_faithful_disposition():
    errs = validate_dispositions(
        [_marker(amount="1")],
        [Disposition(marker_id="d1", disposition="tariff", check_id="t.t1",
                     reason="modifies the loop definition")],
        _terminal(amount="1"))
    assert not errs, errs


def test_escape_hatch_is_counted_not_gated():
    """`not_a_deduction` is legitimate but is the only way out of V11, so
    inflation is the signal it is being used as one. Counted every run."""
    assert escape_hatch_count([
        Disposition(marker_id="d1", disposition="tariff", check_id="t.t1"),
        Disposition(marker_id="d2", disposition="not_a_deduction", reason="x"),
        Disposition(marker_id="d3", disposition="not_a_deduction", reason="y"),
    ]) == 2
