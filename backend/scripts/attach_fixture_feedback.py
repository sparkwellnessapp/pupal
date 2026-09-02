# -*- coding: utf-8 -*-
"""
Attach PR-G4 feedback to the §1.7 fixture drafts. THIS SCRIPT SPENDS MONEY.

WHY IT IS A SEPARATE SCRIPT. `gen_grade_review_fixtures.py` states its own rule:
"a fixture generator that could spend money is a fixture generator someone runs
by accident." So the generator stays free and deterministic, and the one step
that calls a provider lives here, behind an explicit invocation.

WHY IT DOES NOT REGRADE. `attach_feedback` is a pure draft -> draft transform:
it reads the already-priced verdicts and writes prose about them (PR-G4 —
"never before pricing"). It needs no rubric, no transcription, and no grading
call. So the feedback for a published fixture costs ONE feedback call per test
(~$0.056 at the OD-B3 pin), not a re-grade.

WHERE THE RESULT LANDS. A sidecar `<run>/feedback/<student>.json` beside the
drafts it describes — never into the draft files themselves. An eval results
directory is provenance: the drafts in it are what the grader produced on that
run, and editing them would make the run a record of something that never
happened. The generator reads the sidecar and merges it into the emitted
fixture, which keeps `--check` deterministic and free.

    python scripts/attach_fixture_feedback.py --from-run <results_dir>
    python scripts/attach_fixture_feedback.py --from-run <dir> --dry-run

`--dry-run` renders and prints the call plan, spending nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

STUDENTS = ("dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk")


def _draft_path(run_dir: Path, student: str) -> Path:
    for cand in sorted((run_dir / "drafts").glob(f"{student}_r*.json")):
        if not cand.name.endswith(".meta.json"):
            return cand
    raise SystemExit(f"run {run_dir.name} has no draft for {student}")


async def _one(student: str, path: Path, out_dir: Path, dry_run: bool) -> dict:
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.agents.feedback.runner import attach_feedback

    draft = GradedTestDraft.model_validate(json.loads(path.read_text(encoding="utf-8")))
    llm_scopes = [so for so in draft.scope_outcomes if so.graded_by == "llm"]
    if dry_run:
        return {"student": student, "scopes": len(llm_scopes), "wrote": False}

    after = await attach_feedback(draft)
    if after.feedback is None:
        # NEVER write a half-result. `feedback=None` is a first-class wire state
        # (PR-G4), and a fixture that silently records a failed call as "no
        # feedback exists" would teach the frontend the wrong lesson.
        reasons = [a.annotation_type for a in after.annotations
                   if a.annotation_type == "feedback_unavailable"]
        return {"student": student, "scopes": len(llm_scopes), "wrote": False,
                "error": reasons or ["no feedback returned"]}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{student}.json").write_text(
        json.dumps(after.feedback.model_dump(mode="json"),
                   ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    return {"student": student, "scopes": len(llm_scopes), "wrote": True,
            "texts": len(after.feedback.scopes),
            "summary_chars": len(after.feedback.summary.text or "")}


async def _main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-run", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--students", default=",".join(STUDENTS))
    args = ap.parse_args()

    run_dir = Path(args.from_run)
    if not run_dir.is_absolute():
        run_dir = BACKEND / run_dir
    students = [s for s in args.students.split(",") if s]

    from app.config import settings
    print(f"pin: {settings.feedback_model_provider}/{settings.feedback_model_key}")
    if not settings.feedback_model_key:
        raise SystemExit("feedback_model_key is unset — nothing to call")

    out_dir = run_dir / "feedback"
    results = []
    for student in students:
        r = await _one(student, _draft_path(run_dir, student), out_dir, args.dry_run)
        results.append(r)
        print(f"  {student:16s} scopes={r['scopes']:2d} "
              f"{'wrote ' + str(r.get('texts')) + ' text(s)' if r['wrote'] else 'SKIPPED ' + str(r.get('error', 'dry-run'))}")

    failed = [r["student"] for r in results if not r["wrote"] and not args.dry_run]
    if failed:
        raise SystemExit(f"feedback call failed for: {failed} — nothing written for them")
    if not args.dry_run:
        print(f"\n{len(results)} sidecar(s) -> {out_dir.relative_to(BACKEND)}")
        print("next: python scripts/gen_grade_review_fixtures.py --from-run "
              f"{run_dir.name and run_dir.relative_to(BACKEND)}")


if __name__ == "__main__":
    asyncio.run(_main())
