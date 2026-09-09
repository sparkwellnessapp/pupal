"""
GT skeletons for bagrut_899371 (exam 2).

Mirrors `build_gt_skeleton.py`'s shape exactly so the authoring session is
muscle memory. Two deliberate differences, both forced by exam 2 and both
recorded here rather than discovered mid-session:

  * **Exam-namespaced output.** `din_ezra` sat BOTH exams, and
    `benchmarks/gt/din_ezra.gt.json` is already hobby_tvshow's ratified GT.
    Writing exam 2 beside it would overwrite ratified ground truth, so exam-2
    skeletons live under `benchmarks/gt/bagrut_899371/`. Hobby paths are
    untouched, which is what keeps its regression byte-identical.
  * **Reads the compiled contract directly**, not `load_bundle`. The suite's
    fixture registry is still single-exam (the harness task); this tool does
    not wait on it, because the owner's authoring session does not.

`points_possible` and `description` are authoring aids, not `FixtureGT` fields —
same as exam 1. The loader validates the typed subset and refuses a partial
file; that refusal is the completion check.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
CONTRACT = SUITE / "compiled_rubric_bagrut.json"
TRANSCRIPTIONS = SUITE / "compiled_transcriptions_bagrut"
OUT = SUITE / "benchmarks" / "gt" / "bagrut_899371"

EXAM_ID = "bagrut_899371"
FIXTURES = ["din_ezra", "itay_kraft", "noam_breinshtein", "raz_cohen",
            "roni_ben_ezra", "yael_kogan", "yahli_cohen"]

# q1.א.1.c0 is inexpressible until the R-E `counted` check kind lands: 17 cells
# at 0.7 has no on-grid split of 12. Every OTHER terminal is authorable now, so
# the skeleton ships with this one marked rather than held back.
PENDING_COUNTED = "q1.א.1.c0"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminals_in_contract_order(contract: dict) -> list:
    """Contract order = the compiler's scope walk, so the owner grades in
    document order. Scopes are LEAVES at any depth (PR-3): q1 nests two levels."""
    out = []

    def criteria_of(node):
        for crit in node.get("criteria") or []:
            subs = crit.get("sub_criteria") or []
            if subs:
                for sub in subs:
                    out.append({
                        "terminal_id": sub["sub_criterion_id"],
                        "points_possible": str(sub["points"]),
                        "description": sub["description"],
                        "awarded": None,
                        "evidence_exists": None,
                        "note": "",
                    })
            else:
                entry = {
                    "terminal_id": crit["criterion_id"],
                    "points_possible": str(crit["points"]),
                    "description": crit["description"],
                    "awarded": None,
                    "evidence_exists": None,
                    "note": "",
                }
                if crit["criterion_id"] == PENDING_COUNTED:
                    entry["note"] = (
                        "PENDING R-E `counted` check kind — 17 cells at 0.7 has "
                        "no on-grid representation of 12. Author the other "
                        "terminals first; this one needs the counted award "
                        "form (snap_to_grid(12 × cells_correct / 17)).")
                out.append(entry)

    def walk(node):
        subs = node.get("sub_questions") or []
        if subs:
            for sub in subs:
                walk(sub)
        else:
            criteria_of(node)

    for question in contract["questions"]:
        walk(question)
    return out


def build(fixture: str, contract: dict, rubric_hash: str) -> dict:
    tpath = TRANSCRIPTIONS / f"{fixture}.json"
    return {
        "fixture": fixture,
        "exam_id": EXAM_ID,
        "rubric_contract_hash": rubric_hash,
        "transcription_contract_hash": sha256_of(tpath),
        # [M1, 2026-08-25] the ruled v0 GT class: agent-proposed judgments,
        # owner-validated, both parties on record — honestly non-blind.
        "gt_source": "teacher_validated",
        "blind": False,
        "proposed_by": "claude-fable-5 (design-partner session)",
        "validated_by": "Noam",
        "authored_by": "Noam",
        "authored_at": "",                # OWNER stamps at completion
        "terminals": terminals_in_contract_order(contract),
        "ungradable_scopes": [],          # [C-2] fill per GRADING_GT_CONVENTIONS
        "_instructions": (
            "Fill awarded (Decimal string on the 0.25 grid), evidence_exists "
            "(bool), optional note, per terminal; add ungradable_scopes per C-2; "
            "stamp authored_at (ISO-8601) when done; delete this key. The loader "
            "refuses partial files — that is the completion check. "
            "NOTE: this exam is choose-4-of-6 (selection_groups sg0). A question "
            "the student did not answer is NOT a zero — leave its terminals "
            "unawarded and let selection scoring exclude them; awarding 0 would "
            "penalise a choice the exam invited."),
    }


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    rubric_hash = sha256_of(CONTRACT)
    OUT.mkdir(parents=True, exist_ok=True)

    ids = None
    for fixture in FIXTURES:
        skeleton = build(fixture, contract, rubric_hash)
        got = [t["terminal_id"] for t in skeleton["terminals"]]
        if ids is None:
            ids = got
        elif got != ids:
            raise SystemExit(f"{fixture}: terminal id set differs from the first "
                             f"fixture — skeletons must be identical in shape")
        path = OUT / f"{fixture}.gt.skeleton.json"
        path.write_text(json.dumps(skeleton, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print(f"  {path.relative_to(SUITE.parents[1])}  "
              f"({len(got)} terminals, transcription "
              f"{skeleton['transcription_contract_hash'][:12]}…)")

    print(f"\nrubric_contract_hash pinned in all {len(FIXTURES)}: {rubric_hash}")
    print(f"terminals per skeleton: {len(ids)}")


if __name__ == "__main__":
    main()
