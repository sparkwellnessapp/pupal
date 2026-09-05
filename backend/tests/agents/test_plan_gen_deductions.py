"""
plan-gen/v2 — deduction detection (deterministic). V11 (disposition
completeness) retired with the Opus decomposer (PLAN COMPILER v2, R-4): the
compiler makes every detected deduction a slot BY CONSTRUCTION.

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

from app.agents.grader.plan_schemas import GradingPlan
from app.agents.plan_compiler.stage0 import contract_scopes
from app.agents.plan_gen.prompt import detect_deductions

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
