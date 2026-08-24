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
