"""
Fixture-pipeline tools guards [F0/F1/F4] — all in-memory, reading sibling GT
files read-only (the scope fence allows read + snapshot). Zero API calls.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

SIBLING_TR = Path(__file__).resolve().parents[1] / "transcription_eval_suit"
SIBLING_RU = Path(__file__).resolve().parents[1] / "rubric_eval_suite"

FIVE_DOCS = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk"]


# ---------------------------------------------------------------------------
# F1 — draft-GT markdown -> TranscriptionContract, parity-guarded
# ---------------------------------------------------------------------------

def test_converter_parity_on_all_five_docs():
    """[F1] the converter must reproduce the sibling loader's answers
    byte-identically (keys and text) on every seed doc, or the pipeline aborts."""
    from tests.transcription_eval_suit.ground_truth import load_ground_truth
    from .tools.convert_transcription_gt import convert_gold_document

    for doc in FIVE_DOCS:
        p = SIBLING_TR / "draft_benchmarks" / f"{doc}.md"
        gold = load_ground_truth(p)
        contract = convert_gold_document(gold)
        got = [(a.question_number, a.sub_question_id, a.answer_text)
               for a in contract.answers]
        want = [(a.question_number, a.sub_question_id, a.answer_text)
                for a in gold.answers]
        assert got == want, f"{doc}: converter diverges from the sibling loader"
        assert len(got) == len(set((q, s) for q, s, _ in got))   # unique keys


# ---------------------------------------------------------------------------
# F0 — hobby correction: original blocks, corrected compiles [R5/H1]
# ---------------------------------------------------------------------------

def test_original_hobby_gt_blocks_compilation():
    from app.services.contract_compiler import CompilationError
    from .tools.f0_hobby_correction import load_original, compile_response

    original = load_original()
    with pytest.raises(CompilationError) as exc:
        compile_response(original)
    msg = str(exc.value)
    assert "q2" in msg    # the two q2 sum shadows are the blockers


def test_corrected_hobby_compiles_clean_with_recorded_fix():
    """[R5/H1] the fix_proposal applied mechanically: c6 moves to a new ג,
    sums reconcile at every level, id renamed path-honestly [DL-5]."""
    from .tools.f0_hobby_correction import (
        apply_recorded_fix, compile_response, load_original)

    corrected = apply_recorded_fix(load_original())
    contract = compile_response(corrected)          # must NOT raise
    assert contract.total_points == Decimal("100")

    q2 = next(q for q in contract.questions if q.question_id == "q2")
    subs = {sq.sub_question_id: sq for sq in q2.sub_questions}
    assert set(subs) == {"א", "ב", "ג"}
    assert subs["ג"].points == Decimal("16")
    assert [c.criterion_id for c in subs["ג"].criteria] == ["q2.ג.c0"]   # [DL-5]
    # [DL-7 / H1-A1, ratified 2026-08-24]: a moved criterion renames its
    # CHILDREN with it — DL-5's own principle applied to the terminal level
    # the original proposal didn't know existed.
    gimel_children = [sc.sub_criterion_id for sc in (subs["ג"].criteria[0].sub_criteria or [])]
    assert gimel_children == ["q2.ג.c0.s0", "q2.ג.c0.s1", "q2.ג.c0.s2", "q2.ג.c0.s3"], gimel_children
    assert subs["ג"].criteria[0].points == Decimal("16")
    # ב no longer carries the mislabeled component and its sums reconcile
    assert sum(c.points for c in subs["ב"].criteria) == Decimal("29") == subs["ב"].points
    assert sum(sq.points for sq in q2.sub_questions) == q2.total_points == Decimal("60")
    # the stale error-description artifacts were dropped [DL-6]
    assert corrected.annotations == []
    assert corrected.pedagogical_mistakes == []


# ---------------------------------------------------------------------------
# F4 — GT skeleton: every terminal pre-populated, judgments empty
# ---------------------------------------------------------------------------

def test_gt_skeleton_prepopulates_all_terminals():
    from . import synth
    from .tools.build_gt_skeleton import build_skeleton

    bundle = synth.make_bundle()          # no GT needed
    sk = build_skeleton(bundle)
    ids = [t["terminal_id"] for t in sk["terminals"]]
    assert set(ids) == set(bundle.terminal_infos)
    assert all(t["awarded"] is None for t in sk["terminals"])       # owner fills
    assert all(t["evidence_exists"] is None for t in sk["terminals"])
    assert sk["blind"] is True and sk["gt_source"] == "teacher_manual"
    assert sk["fixture"] == "synthetic"
    # points shown as authoring aid, but NOT a FixtureGT field (stripped on load)
    assert all("points_possible" in t for t in sk["terminals"])


# ---------------------------------------------------------------------------
# Path-honesty structural guard [H1-A1 ruling, 2026-08-24] — closes the CLASS
# DL-7 was an instance of: every terminal id in every loaded fixture universe
# must be prefixed by its full ancestor chain (sub-criterion by its criterion
# id, criterion by its scope target). Would have caught DL-7 at birth.
# ---------------------------------------------------------------------------

FIXTURE_NAMES = FIVE_DOCS


def test_terminal_ids_are_path_honest_in_all_bundles():
    from .fixtures import load_bundle
    offenders = []
    for name in FIXTURE_NAMES:
        bundle = load_bundle(name, require_gt=False)
        for scope in bundle.gradable_test.scopes:
            target = (scope.question_id if scope.sub_question_id is None
                      else f"{scope.question_id}.{scope.sub_question_id}")
            for criterion in scope.criteria:
                if not criterion.criterion_id.startswith(target + "."):
                    offenders.append((name, target, criterion.criterion_id))
                for sc in (criterion.sub_criteria or []):
                    if not sc.sub_criterion_id.startswith(criterion.criterion_id + "."):
                        offenders.append((name, criterion.criterion_id, sc.sub_criterion_id))
    assert not offenders, f"path-dishonest ids (child not prefixed by parent): {offenders}"
