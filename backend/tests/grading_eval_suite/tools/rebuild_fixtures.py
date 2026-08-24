"""
F2 — deliberate fixture regeneration. NEVER implicit [D2].

Writes the five transcription-contract snapshots (sibling draft-GT -> contract,
via the F1 converter) into benchmarks/transcriptions/, and the per-fixture
manifests into fixtures/. Requires --yes; refuses to touch the RATIFIED rubric
contract at all (its hash pins every GT [D5]; replacing it is an owner decision
executed through f0_hobby_correction, never here).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..fixtures import SUITE_DIR, sha256_file
from .convert_transcription_gt import SIBLING_DRAFTS, convert_sibling_doc
from .f0_hobby_correction import RATIFIED_PATH

FIVE_DOCS = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk"]
TRANSCRIPTIONS_DIR = SUITE_DIR / "benchmarks" / "transcriptions"
FIXTURES_DIR = SUITE_DIR / "fixtures"


def write_snapshots_and_manifests() -> None:
    if not RATIFIED_PATH.exists():
        raise SystemExit(
            "[F2] refused: the ratified rubric contract does not exist yet — "
            "H1 ratification (f0_hobby_correction --ratify) comes first [R5].")
    TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    rc_rel = RATIFIED_PATH.relative_to(SUITE_DIR).as_posix()
    for doc in FIVE_DOCS:
        contract = convert_sibling_doc(doc)
        tc_path = TRANSCRIPTIONS_DIR / f"{doc}.contract.json"
        tc_path.write_text(contract.model_dump_json(indent=1), encoding="utf-8")
        manifest = {
            "rubric_contract": rc_rel,
            "transcription_contract": tc_path.relative_to(SUITE_DIR).as_posix(),
            "gt": f"benchmarks/gt/{doc}.gt.json",
            "provenance": {
                "gt_source": "teacher_manual",
                "exam": "hobby_tvshow (corrected, H1-ratified)",
                "transcription_source": (SIBLING_DRAFTS / f"{doc}.md").as_posix(),
                "rubric_source": "../rubric_eval_suite/benchmarks/hobby_tvshow.json "
                                 "(via F0 correction)",
                "rubric_contract_sha256": sha256_file(RATIFIED_PATH),
                "transcription_contract_sha256": sha256_file(tc_path),
                "built_by": "tools/rebuild_fixtures.py",
            },
        }
        (FIXTURES_DIR / f"{doc}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[F2] {doc}: snapshot + manifest written "
              f"({len(contract.answers)} answers)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild fixture snapshots (F2 — deliberate)")
    ap.add_argument("--yes", action="store_true",
                    help="required: regeneration is never implicit")
    args = ap.parse_args()
    if not args.yes:
        raise SystemExit("[F2] pass --yes to regenerate (never implicit).")
    write_snapshots_and_manifests()


if __name__ == "__main__":
    main()
