"""Instrument guard for the FIX-EFFECT check (scoring.py::fix_effect_check).

Two halves, and the second is the one that matters:

1. VECTORS — tests/fixtures/edit_step_points_cases.json, read IN PLACE and also
   read by frontend/src/utils/edit-steps.test.ts, which runs them through the REAL
   applier (src/utils/edit-steps.ts). The scorer's job is to PREDICT what accepting
   a fix does; if the two implementations drift, this gate either passes a broken
   fix or fails a good one and nothing says which. The vectors are the contract.

2. KNOWN-ANSWER on the real thing — the suite's own discipline (test_scoring.py:
   "a perfect extraction scores 1.0 and PASSES; a copy with injected errors FAILS
   with the right per-metric signal"). Here: take a REAL prediction whose fix is
   correct, delete the source-side set_points step, and require the check to flip.
   That injected error IS the regression the owner found live on 2026-08-24.

Run: PYTHONPATH=. python -m pytest tests/rubric_eval_suite/test_fix_effect.py -q
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.rubric_eval_suite.scoring import (fix_effect_check, fx_simulate,
                                             _fx_build, _fx_resolve)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "edit_step_points_cases.json"
RESULTS = Path(__file__).resolve().parent / "results"


# --------------------------------------------------------------------------- #
# expanding the neutral vector shape into what the scorer reads
# --------------------------------------------------------------------------- #
def _crit(points: str):
    return SimpleNamespace(points=Decimal(points), description="c", sub_criteria=None)


def _sub(d: dict):
    return SimpleNamespace(
        sub_question_id=d["sub_question_id"],
        points=Decimal(d["points"]) if d.get("points") is not None else None,
        criteria=[_crit(p) for p in (d.get("criteria") or [])],
        sub_questions=[_sub(k) for k in (d.get("sub_questions") or [])],
    )


def _question(d: dict):
    return SimpleNamespace(
        question_id=d["question_id"],
        total_points=Decimal(d["total_points"]) if d.get("total_points") is not None else None,
        criteria=[_crit(p) for p in (d.get("criteria") or [])],
        sub_questions=[_sub(s) for s in (d.get("sub_questions") or [])],
    )


def _step(d: dict):
    return SimpleNamespace(
        op=d["op"], scope=d.get("scope"), to_scope=d.get("to_scope"),
        criterion_index=d.get("criterion_index"), value=d.get("value"),
        current_value=d.get("current_value"), text=d.get("text"),
    )


def _draft(case: dict, steps):
    """A predicted-draft stand-in carrying ONE mistake with the case's fix."""
    return SimpleNamespace(
        questions=[_question(q) for q in case["questions"]],
        pedagogical_mistakes=[SimpleNamespace(
            mistake_id="vec", kind="structural_mislabel",
            suggested_fix=SimpleNamespace(steps=[_step(s) for s in steps]),
        )],
    )


def _cases():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


# --------------------------------------------------------------------------- #
# 1. the cross-pinned vectors
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["name"][:60])
def test_points_semantics_match_the_cross_pinned_vectors(case):
    """The scorer's simulation must land on the SAME declared points the real
    applier produces. frontend/src/utils/edit-steps.test.ts asserts the identical
    expected_points from the identical file."""
    draft = _draft(case, case["steps"])
    consistent, violations = fix_effect_check(draft)
    # observe THE implementation rather than re-deriving it: a test that replays the
    # steps itself can drift from the check it is supposed to guard.
    roots, _touched, _rubric, problems = fx_simulate(draft, [_step(s) for s in case["steps"]])
    assert not problems, problems

    for scope, expected in case["expected_points"].items():
        chain = _fx_resolve(roots, scope)
        assert chain is not None, f"{case['name']}: scope {scope} vanished"
        got = chain[-1].declared
        assert got == Decimal(expected), (
            f"{case['name']}: {scope} declared {got}, cross-pinned vector says {expected}. "
            f"If frontend/src/utils/edit-steps.ts changed on purpose, update the vectors "
            f"in the SAME commit — that divergence is the signal.")

    assert consistent is case["expected_consistent"], (
        f"{case['name']}: fix_effect_consistent={consistent}, "
        f"expected {case['expected_consistent']}; violations={violations}")


def test_vacuous_when_no_fix_is_proposed():
    """None, not False: a draft with no suggested_fix must SKIP the criterion, the
    way the cost check is skipped when cost_usd is None. Otherwise the four fixtures
    that never exercise a fix would red for having nothing to check."""
    draft = SimpleNamespace(questions=[], pedagogical_mistakes=[
        SimpleNamespace(mistake_id="m", kind="point_sum_mismatch", suggested_fix=None)])
    assert fix_effect_check(draft) == (None, [])
    assert fix_effect_check(SimpleNamespace(questions=[], pedagogical_mistakes=[])) == (None, [])


# --------------------------------------------------------------------------- #
# 2. known-answer against a REAL prediction (the injected-error discipline)
# --------------------------------------------------------------------------- #
def _real_hobby_prediction():
    """A persisted prediction whose fix IS correct (gpt-5.5 emits the source-side
    step on every draw). Skips rather than fails if the artifacts were pruned."""
    for run in sorted(RESULTS.glob("*_prod_gpt55"), reverse=True):
        p = run / "predictions" / "hobby_tvshow_r0.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    pytest.skip("no persisted gpt-5.5 hobby prediction in results/")


def _from_wire(d: dict):
    def crit(c):
        return SimpleNamespace(points=Decimal(str(c["points"])), description=c.get("description"),
                               sub_criteria=None)

    def sub(s):
        return SimpleNamespace(
            sub_question_id=s.get("sub_question_id"),
            points=Decimal(str(s["points"])) if s.get("points") is not None else None,
            criteria=[crit(c) for c in (s.get("criteria") or [])],
            sub_questions=[sub(k) for k in (s.get("sub_questions") or [])])

    def mistake(m):
        f = m.get("suggested_fix")
        return SimpleNamespace(
            mistake_id=m.get("mistake_id"), kind=m.get("kind"),
            suggested_fix=(SimpleNamespace(steps=[_step(s) for s in (f.get("steps") or [])])
                           if f else None))

    return SimpleNamespace(
        questions=[SimpleNamespace(
            question_id=q.get("question_id"),
            total_points=Decimal(str(q["total_points"])) if q.get("total_points") is not None else None,
            criteria=[crit(c) for c in (q.get("criteria") or [])],
            sub_questions=[sub(s) for s in (q.get("sub_questions") or [])]) for q in d["questions"]],
        pedagogical_mistakes=[mistake(m) for m in (d.get("pedagogical_mistakes") or [])])


def test_real_correct_fix_passes_and_the_injected_omission_is_caught_by_the_DIAGNOSTIC():
    """THE known-answer pair, on real model output, AFTER the applier learned to repair
    a move source (2026-08-24).

    The omission injected below — deleting the source-side set_points — is the exact
    thing terra emitted 0/7 times in production. Two verdicts now, and the split is
    the whole point of the design:

      fix_effect_consistent : TRUE  — it is no longer teacher-visible. The applier
                                      repairs the source, so accepting the fix still
                                      lands on a rubric that adds up. Gating on it
                                      would fail a fix that hurts nobody.
      fix_plan_complete     : FALSE — the MODEL still forgot a step. Ungated, but
                                      recorded, so making the bug harmless does not
                                      make the model-quality difference invisible
                                      (gpt-5.5 emits it 6/6, terra 0/7).
    """
    wire = _real_hobby_prediction()

    ok, violations = fix_effect_check(_from_wire(wire))
    assert ok is True, f"a known-good fix must pass; violations={violations}"
    assert fix_effect_check(_from_wire(wire), repair_source=False)[0] is True, (
        "a COMPLETE plan must also be complete without the app's help")

    broken = json.loads(json.dumps(wire))          # deep copy
    removed = 0
    for m in broken.get("pedagogical_mistakes") or []:
        f = m.get("suggested_fix")
        if not f:
            continue
        keep = [st for st in (f.get("steps") or [])
                if not (st.get("op") == "set_points" and st.get("criterion_index") is None
                        and (st.get("scope") or "").count(".") == 1)]
        removed += len(f.get("steps") or []) - len(keep)
        f["steps"] = keep
    assert removed == 1, f"expected to inject exactly one omission, removed {removed}"

    harmless, _ = fix_effect_check(_from_wire(broken))
    assert harmless is True, (
        "with the source auto-repair in place the omission must NOT be teacher-visible")

    incomplete, violations2 = fix_effect_check(_from_wire(broken), repair_source=False)
    assert incomplete is False, "the diagnostic MUST still see the model's omission"
    assert any("declares" in v and "sum to" in v for v in violations2), violations2


# --------------------------------------------------------------------------- #
# 3. OPTION A — a fix is judged by what it CLAIMS (owner ruling 2026-08-24)
# --------------------------------------------------------------------------- #
def _two_level_draft(steps):
    """q1 declares 25 = 12 + 13; the sub-question's own criteria sum to 12.
    Any step that lowers the child to 12 leaves q1 at 25 against 24."""
    case = {"questions": [{
        "question_id": "q1", "total_points": "25",
        "sub_questions": [
            {"sub_question_id": "א", "points": "12", "criteria": ["12"]},
            {"sub_question_id": "ב", "points": "13", "criteria": ["12"]},
        ]}]}
    return _draft(case, steps)


def test_local_points_fix_is_not_held_to_its_ancestors():
    """Tier A's minimal fallback: set the node to the sum its own criteria state.
    It reconciles the node it targeted (13 -> 12) and leaves q1 at 25 vs 24 — which
    is NOT its failure. Repointing q1 to 24 would mean writing a number the teacher
    never wrote, the one thing _adjust_points_fix exists to avoid."""
    ok, violations = fix_effect_check(_two_level_draft(
        [{"op": "set_points", "scope": "q1.ב", "value": "12", "current_value": "13"}]))
    assert ok is True, violations


def test_structural_fix_IS_held_to_its_ancestors():
    """A move-bearing plan claims root-cause resolution, so the ancestors are part of
    its promise. Same arithmetic damage as above, different claim, different verdict —
    and THIS is the shape of the regression found in production on 2026-08-24."""
    ok, violations = fix_effect_check(_two_level_draft([
        {"op": "move_criterion", "scope": "q1.ב", "criterion_index": 0, "to_scope": "q1.ג"},
    ]))
    assert ok is False
    assert any("q1" in v and "25" in v for v in violations), violations
