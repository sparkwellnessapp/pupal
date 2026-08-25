"""
GT loader guards [§5 of the mission] + the R1 blind-sequencing mechanics.
All object-level except the manifest round-trip, which uses a tmp dir.
Zero API calls.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path

import pytest

from . import synth
from .fixtures import (
    BlindSequencingError,
    GTValidationError,
    assemble_bundle,
    assert_blind_sequencing,
    load_bundle,
    sha256_file,
)


def _gt(awards=None, **overrides):
    return synth.make_gt(awards or synth.GT_PERFECT, **overrides)


# ---------------------------------------------------------------------------
# Guards [§5]: totality, bounds, precision grid, blind flag, ungradable keys
# ---------------------------------------------------------------------------

def test_totality_missing_terminal_rejected():
    gt = synth.make_gt({"q1.c0": "2", "q1.c1.s0": "1", "q1.c1.s1": "2"})  # q2.א.c0 absent
    with pytest.raises(GTValidationError, match="totality"):
        synth.make_bundle(gt)


def test_totality_unknown_terminal_rejected():
    gt = synth.make_gt({**synth.GT_PERFECT, "q9.ghost": "1"})
    with pytest.raises(GTValidationError, match="totality"):
        synth.make_bundle(gt)


def test_duplicate_terminal_rejected():
    gt = _gt()
    dup = gt.model_copy(update={"terminals": gt.terminals + [gt.terminals[0]]})
    with pytest.raises(GTValidationError, match="duplicate"):
        synth.make_bundle(dup)


def test_bounds_rejected():
    gt = synth.make_gt({**synth.GT_PERFECT, "q1.c0": "2.5"})   # possible = 2
    with pytest.raises(GTValidationError, match="bounds"):
        synth.make_bundle(gt)


def test_precision_grid_rejected():
    gt = synth.make_gt({**synth.GT_PERFECT, "q1.c0": "1.1"})   # not on the 0.25 grid
    with pytest.raises(GTValidationError, match="precision"):
        synth.make_bundle(gt)


def test_blind_flag_required_for_teacher_manual():
    """[R1] gt_source=teacher_manual demands blind: true."""
    gt = _gt(blind=False)
    with pytest.raises(GTValidationError, match="blind"):
        synth.make_bundle(gt)


def test_ungradable_scope_must_exist():
    gt = _gt(ungradable=[("q7", None, "no such scope")])
    with pytest.raises(GTValidationError, match="ungradable"):
        synth.make_bundle(gt)


def test_valid_gt_loads():
    bundle = synth.make_bundle(_gt())
    assert bundle.gt is not None
    assert set(bundle.terminal_infos) == set(synth.GT_PERFECT)


# ---------------------------------------------------------------------------
# Manifest round-trip + hash pinning [D5][F3]
# ---------------------------------------------------------------------------

def _write_fixture_tree(root: Path, gt_hash_tamper: bool = False) -> str:
    (root / "benchmarks" / "contracts").mkdir(parents=True)
    (root / "benchmarks" / "transcriptions").mkdir(parents=True)
    (root / "benchmarks" / "gt").mkdir(parents=True)
    (root / "fixtures").mkdir()
    rc, tc = synth.make_contract(), synth.make_transcription(
        [(1, None, synth.ANSWER_Q1), (2, "א", synth.ANSWER_Q2A)])
    rc_p = root / "benchmarks" / "contracts" / "synthetic.contract.json"
    tc_p = root / "benchmarks" / "transcriptions" / "synthetic.contract.json"
    rc_p.write_text(rc.model_dump_json(indent=1), encoding="utf-8")
    tc_p.write_text(tc.model_dump_json(indent=1), encoding="utf-8")
    gt = _gt().model_copy(update={
        "rubric_contract_hash": ("0" * 64) if gt_hash_tamper else sha256_file(rc_p),
        "transcription_contract_hash": sha256_file(tc_p),
    })
    gt_p = root / "benchmarks" / "gt" / "synthetic.gt.json"
    gt_p.write_text(gt.model_dump_json(indent=1), encoding="utf-8")
    manifest = {
        "rubric_contract": "benchmarks/contracts/synthetic.contract.json",
        "transcription_contract": "benchmarks/transcriptions/synthetic.contract.json",
        "gt": "benchmarks/gt/synthetic.gt.json",
        "provenance": {"gt_source": "teacher_manual", "note": "synthetic test tree"},
    }
    (root / "fixtures" / "synthetic.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return "synthetic"


def test_manifest_round_trip_and_hash_pin(tmp_path):
    name = _write_fixture_tree(tmp_path)
    bundle = load_bundle(name, suite_dir=tmp_path, require_gt=True)
    assert bundle.gt is not None and bundle.rubric_contract_hash


def test_hash_mismatch_rejected(tmp_path):
    """[D5] a recompiled rubric cannot silently invalidate the GT authored against it."""
    name = _write_fixture_tree(tmp_path, gt_hash_tamper=True)
    with pytest.raises(GTValidationError, match="hash"):
        load_bundle(name, suite_dir=tmp_path, require_gt=True)


def test_grade_requires_gt(tmp_path):
    """[R1] no grade-mode run on a fixture until its GT exists."""
    name = _write_fixture_tree(tmp_path)
    (tmp_path / "benchmarks" / "gt" / "synthetic.gt.json").unlink()
    with pytest.raises(GTValidationError, match="R1"):
        load_bundle(name, suite_dir=tmp_path, require_gt=True)
    # ...but metadata-only loading (no scoring) is allowed
    b = load_bundle(name, suite_dir=tmp_path, require_gt=False)
    assert b.gt is None


# ---------------------------------------------------------------------------
# R1 blind sequencing: GT authored AFTER a cached draft existed => refuse
# ---------------------------------------------------------------------------

def test_blind_sequencing_refuses_stale_gt(tmp_path):
    results = tmp_path / "results"
    old_run = results / "20260820-120000_gpt-4o" / "drafts"
    old_run.mkdir(parents=True)
    (old_run / "hobby_r0.json").write_text("{}", encoding="utf-8")
    gt = _gt(authored_at="2026-08-24T10:00:00")     # authored AFTER that draft run
    with pytest.raises(BlindSequencingError, match="R1"):
        assert_blind_sequencing("hobby", gt, results)


def test_blind_sequencing_allows_drafts_after_gt(tmp_path):
    results = tmp_path / "results"
    new_run = results / "20260825-090000_gpt-4o" / "drafts"
    new_run.mkdir(parents=True)
    (new_run / "hobby_r0.json").write_text("{}", encoding="utf-8")
    gt = _gt(authored_at="2026-08-24T10:00:00")     # drafts POSTDATE the GT: fine
    assert_blind_sequencing("hobby", gt, results)   # no raise


def test_blind_sequencing_ignores_other_fixtures(tmp_path):
    results = tmp_path / "results"
    old_run = results / "20260820-120000_gpt-4o" / "drafts"
    old_run.mkdir(parents=True)
    (old_run / "other_r0.json").write_text("{}", encoding="utf-8")
    gt = _gt(authored_at="2026-08-24T10:00:00")
    assert_blind_sequencing("hobby", gt, results)   # different fixture: no violation


# ---------------------------------------------------------------------------
# M1 provenance amendment (owner-ratified, carryover 2026-08-25):
# gt_source ∈ {teacher_manual, teacher_validated, production_approval};
# teacher_validated requires blind: false + proposed_by + validated_by.
# v0 gates on the teacher_validated class per owner ruling;
# production_approval stays non-gating.
# ---------------------------------------------------------------------------

M1_STAMP = dict(gt_source="teacher_validated", blind=False,
                proposed_by="claude-fable-5 (design-partner session)",
                validated_by="Noam")


def test_m1_teacher_validated_accepted():
    gt = synth.make_gt(synth.GT_PERFECT, **M1_STAMP)
    bundle = synth.make_bundle(gt)
    assert bundle.gt.gt_source == "teacher_validated"
    assert bundle.gt.proposed_by and bundle.gt.validated_by


def test_m1_teacher_validated_refuses_blind_true():
    gt = synth.make_gt(synth.GT_PERFECT, **{**M1_STAMP, "blind": True})
    with pytest.raises(GTValidationError, match="teacher_validated"):
        synth.make_bundle(gt)


def test_m1_teacher_validated_requires_attribution():
    for drop in ("proposed_by", "validated_by"):
        stamp = {**M1_STAMP, drop: None}
        gt = synth.make_gt(synth.GT_PERFECT, **stamp)
        with pytest.raises(GTValidationError, match="M1"):
            synth.make_bundle(gt)


def test_m1_teacher_manual_still_requires_blind():
    # the original R1 class is unchanged by M1
    gt = synth.make_gt(synth.GT_PERFECT, blind=False)
    with pytest.raises(GTValidationError, match="blind"):
        synth.make_bundle(gt)
