"""Re-check a student id, purged or not (PR §14.6; PRV-7).

    python -m app.scripts.verify_purge <student_id> --user <teacher_id>
        [--transcription-id ID ...] [--graded-test-id ID ...]

NOT YET PURGED: the student's plan is computed read-only and verified — every
row and object still there is reported (the verifier is not vacuous).

ALREADY PURGED: the plan cannot be recomputed from rows that are gone, so this
checks what CAN be checked from the database — no row still names her, no
object of hers is waiting in the purge_failures ledger, the dead tables are
empty — and re-lists storage for the ids you pass. Those ids are in the
purge's audit line (`purge_audit … transcription_ids=… graded_test_ids=…`).
Exit 0 means clean.
"""
import argparse
import asyncio
import sys
from uuid import UUID

from sqlalchemy import text

from ..database import AsyncSessionLocal
from ..services.erasure import (
    DEAD_TABLES,
    PurgePlan,
    StudentNotFound,
    UnassignedScans,
    get_purge_storage,
    plan_purge,
    returned_exams_prefix,
    thumbs_prefix,
    verify_purged,
)


async def run(student_id: UUID, user_id: UUID, transcription_ids, graded_test_ids) -> int:
    storage = get_purge_storage()
    async with AsyncSessionLocal() as db:
        try:
            plan = await plan_purge(db, user_id=user_id, student_id=student_id, storage=storage)
        except StudentNotFound:
            plan = None
    if plan is None:
        targets = frozenset(
            {(b, thumbs_prefix(t)) for b in storage.known_buckets for t in transcription_ids}
            | {(b, returned_exams_prefix(g)) for b in storage.known_buckets for g in graded_test_ids})
        empty = frozenset()
        plan = PurgePlan(
            user_id=user_id, student_id=student_id,
            rows={"class_memberships": empty, "graded_tests": frozenset(graded_test_ids),
                  "transcription_jobs": empty, "transcriptions": frozenset(transcription_ids),
                  "students": frozenset({student_id})},
            objects=empty, listed=targets, batch_recounts=empty, legacy_count_batches=empty,
            failure_scrubs={}, scrub_filenames=empty, blockers=(),
            unassigned=UnassignedScans(0, empty), signed_tests_count=0)
        print(f"student {student_id}: no row — checking what remains of a purge")
    report = await verify_purged(plan, storage=storage)
    async with AsyncSessionLocal() as db:
        ledger = (await db.execute(text(
            "SELECT COUNT(*) FROM purge_failures WHERE student_id = :s"), {"s": student_id})).scalar_one()
    print(f"rows remaining:          {dict(report.rows_remaining)}")
    print(f"rows still naming her:   {report.student_refs_remaining}")
    print(f"objects remaining:       {len(report.objects_remaining)}")
    print(f"soft-deleted (restorable until {report.restorable_until}): {report.soft_deleted_count}")
    print(f"dead tables empty ({', '.join(DEAD_TABLES)}): {report.legacy_tables_empty}")
    print(f"purge_failures rows:     {ledger}")
    clean = report.clean and ledger == 0
    print("CLEAN" if clean else "NOT CLEAN")
    return 0 if clean else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("student_id", type=UUID)
    ap.add_argument("--user", type=UUID, required=True, help="the teacher who owns (owned) her")
    ap.add_argument("--transcription-id", type=UUID, action="append", default=[])
    ap.add_argument("--graded-test-id", type=UUID, action="append", default=[])
    args = ap.parse_args()
    return asyncio.run(run(args.student_id, args.user, args.transcription_id, args.graded_test_id))


if __name__ == "__main__":
    sys.exit(main())
