"""
Fixture manifests for exam 2 (bagrut_899371) — and `exam_id` on the hobby five.

THE POINT OF THE HARNESS IS THAT THIS TOOL IS THE WHOLE DROP. Exam 2 becomes
scoreable by writing seven manifests and one key on five existing ones; no
runner change, no scorer change, no new pairing convention. If this file ever
needs to grow a special case for a third exam, the harness failed.

Two things it does NOT do, deliberately:

  * it does not invent GT. The manifests point at `benchmarks/gt/bagrut_899371/`,
    where the owner's authoring session lands its files; `load_bundle(...,
    require_gt=True)` refuses until they exist, which is R1 working as designed.
  * it does not invent a plan. `plans/bagrut_899371.plan.json` is the owner's to
    ratify; a config that maps exam 2 before it exists refuses at resolution,
    pre-spend.

Idempotent: re-running rewrites the same bytes.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
FIXTURES = SUITE / "fixtures"

EXAM_ID = "bagrut_899371"
HOBBY_EXAM_ID = "hobby_tvshow"

BAGRUT_STUDENTS = ["din_ezra", "itay_kraft", "noam_breinshtein", "raz_cohen",
                   "roni_ben_ezra", "yael_kogan", "yahli_cohen"]

HOBBY_STUDENTS = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber",
                  "yonatan_basiuk"]

# ⚠ `din_ezra` sat BOTH exams. That is exactly why fixture names are
# EXAM-NAMESPACED here (`bagrut_899371.din_ezra`) and why the GT skeletons live
# under `benchmarks/gt/bagrut_899371/`: the hobby fixture `din_ezra` already
# owns its name, its manifest, and a RATIFIED GT, and a collision would have
# overwritten ground truth.
def bagrut_fixture_name(student: str) -> str:
    return f"{EXAM_ID}.{student}"


def write(path: Path, payload: dict) -> bool:
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return True


def main() -> None:
    changed = []

    # 1. exam 2 — seven new manifests
    for student in BAGRUT_STUDENTS:
        name = bagrut_fixture_name(student)
        payload = {
            "exam_id": EXAM_ID,
            "rubric_contract": "compiled_rubric_bagrut.json",
            "transcription_contract":
                f"compiled_transcriptions_bagrut/{student}.json",
            "gt": f"benchmarks/gt/{EXAM_ID}/{student}.gt.json",
            "provenance": {
                "exam": "bagrut_899371 (מתכונת, choose 4 of 6)",
                "student": student,
                "built_by": "tools/build_bagrut_fixtures.py",
                "gt_status": "AWAITING OWNER AUTHORING — load_bundle refuses "
                             "until the file exists (R1)",
            },
        }
        if write(FIXTURES / f"{name}.json", payload):
            changed.append(f"{name}.json")

    # 2. the hobby five — add the routing key, touch nothing else
    for student in HOBBY_STUDENTS:
        path = FIXTURES / f"{student}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("exam_id") == HOBBY_EXAM_ID:
            continue
        # exam_id FIRST so the routing fact reads before the payload paths
        merged = {"exam_id": HOBBY_EXAM_ID}
        merged.update(data)
        if write(path, merged):
            changed.append(f"{student}.json")

    print(f"{len(changed)} manifest(s) written" if changed else "unchanged")
    for name in changed:
        print(f"  {name}")


if __name__ == "__main__":
    main()
