"""
EXECUTE — delete exactly the plan (PR §14; PRV-2, PRV-3, PRV-5, PRV-6).

  1. Rows: ONE transaction. Children first, the student row LAST — never the
     student first with the constraints doing the rest (ruling 2026-09-22):
     since migration 032 every FK out of the student-data tables is NO ACTION,
     so a row the plan did not name makes its parent's delete RAISE, the
     transaction rolls back, and not one row is gone (`plan_stale`). The batch
     count is recomputed from rows (M-B6; never for a pre-jobs-era batch,
     census E) and her entries in the dormant 015 failure ledger are scrubbed.
  2. Objects: after the commit, synchronously (M-B1). A failure lands in the
     purge_failures ledger and an ERROR line (PRV-3). Nothing is deleted from
     storage before the rows committed (PRV-2).

`purge_student` is the real path (AM-B6): the student row is locked
`FOR UPDATE` and the plan is computed INSIDE that transaction, so a concurrent
assignment to her either committed first — and is in the plan — or blocks on
the lock and then fails its own FK check. Batch rows are locked in id order
before the recount (append_file takes the same lock). It then verifies
(PRV-7) and writes one audit line: ids and counts, never a name (OD-B4).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Mapping, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

from .ledger import ObjectFailure, delete_objects, record_failures
from .plan import PurgeBlocked, PurgePlan, PurgeRefused, StudentNotFound, plan_purge
from .storage import GuardedStorage
from .verify import VerifyReport, verify_purged

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    plan: PurgePlan
    rows_deleted: Mapping[str, int]
    objects_deleted: frozenset[tuple[str, str]]
    failures: tuple[ObjectFailure, ...]
    verify: Optional[VerifyReport] = None

    def payload(self) -> dict:
        """DELETE's 200 body (M-B4): what was verified, in counts."""
        return {
            "verify": self.verify.payload() if self.verify else None,
            "rows_deleted": dict(self.rows_deleted),
            "objects_deleted": len(self.objects_deleted),
            "failures": len(self.failures),
        }


async def _lock_student(db: AsyncSession, user_id: UUID, student_id: UUID) -> None:
    found = await db.scalar(text(
        "SELECT id FROM students WHERE id = :s AND user_id = :u FOR UPDATE"),
        {"s": student_id, "u": user_id})
    if found is None:
        raise StudentNotFound(str(student_id))


async def _delete_rows(db: AsyncSession, plan: PurgePlan) -> dict[str, int]:
    """The plan's rows, in dependency order, inside the caller's transaction."""
    batches = sorted(plan.batch_recounts | plan.legacy_count_batches | set(plan.failure_scrubs), key=str)
    if batches:
        # AM-B6: the same lock append_file takes, in a stable order.
        await db.execute(text(
            "SELECT id FROM grading_batches WHERE id = ANY(:b) ORDER BY id FOR UPDATE"), {"b": batches})

    s, rows = plan.student_id, plan.rows
    steps = (
        ("class_memberships",
         "DELETE FROM class_memberships WHERE student_id = :s AND class_id = ANY(:ids)"),
        # Whole revision chains in ONE statement: NO ACTION checks at statement
        # end, and regraded_to_id is deferred to commit.
        ("graded_tests", "DELETE FROM graded_tests WHERE id = ANY(:ids)"),
        ("transcription_jobs", "DELETE FROM transcription_jobs WHERE id = ANY(:ids)"),
        ("transcriptions", "DELETE FROM transcriptions WHERE id = ANY(:ids)"),
    )
    deleted: dict[str, int] = {}
    for table, sql in steps:
        result = await db.execute(text(sql), {"ids": list(rows[table]), "s": s})
        deleted[table] = result.rowcount
        if result.rowcount != len(rows[table]):
            raise PurgeRefused("plan_stale", f"{table}: planned {len(rows[table])}, "
                                             f"deleted {result.rowcount}")

    if plan.failure_scrubs:
        await db.execute(text(
            "UPDATE grading_batches SET transcription_failures = ("
            "  SELECT COALESCE(jsonb_agg(e), '[]'::jsonb)"
            "    FROM jsonb_array_elements(transcription_failures) AS e"
            "   WHERE NOT (COALESCE(e->>'filename', '') = ANY(:names)))"
            " WHERE id = ANY(:b)"),
            {"names": sorted(plan.scrub_filenames), "b": list(plan.failure_scrubs)})
    if plan.batch_recounts:
        await db.execute(text(
            "UPDATE grading_batches b SET test_count ="
            " (SELECT COUNT(*) FROM transcription_jobs j WHERE j.batch_id = b.id)"
            " WHERE b.id = ANY(:b)"), {"b": list(plan.batch_recounts)})

    # LAST — and by then nothing may still reference her, or this raises.
    result = await db.execute(text("DELETE FROM students WHERE id = :s AND user_id = :u"),
                              {"s": s, "u": plan.user_id})
    deleted["students"] = result.rowcount
    if result.rowcount != 1:
        raise PurgeRefused("plan_stale", "the student row was not there to delete")
    return deleted


async def _commit_rows(db: AsyncSession, plan: PurgePlan) -> dict[str, int]:
    try:
        deleted = await _delete_rows(db, plan)
        await db.commit()                                  # the deferred FK is checked HERE
        return deleted
    except IntegrityError as exc:
        await db.rollback()
        raise PurgeRefused("plan_stale", type(exc.orig).__name__ if exc.orig else "IntegrityError") from None
    except BaseException:
        await db.rollback()
        raise


async def _objects_after_commit(plan: PurgePlan, storage: GuardedStorage):
    deleted, failed = await asyncio.to_thread(delete_objects, storage, plan.objects)
    for f in failed:
        logger.error("purge_object_failed user_id=%s student_id=%s bucket=%s object=%s error=%s",
                     plan.user_id, plan.student_id, f.bucket, f.object_name, f.error)
    await record_failures(plan.user_id, plan.student_id, failed)
    return frozenset(deleted), tuple(failed)


async def execute_purge(plan: PurgePlan, *, storage: GuardedStorage) -> PurgeResult:
    """Delete exactly `plan` — no discovery (PRV-6). A plan that no longer
    matches the database fails closed (`plan_stale`) with no storage call."""
    if plan.blockers:
        raise PurgeBlocked(len(plan.blockers))
    async with AsyncSessionLocal() as db:
        await _lock_student(db, plan.user_id, plan.student_id)
        rows_deleted = await _commit_rows(db, plan)
    objects, failures = await _objects_after_commit(plan, storage)
    return PurgeResult(plan=plan, rows_deleted=rows_deleted, objects_deleted=objects, failures=failures)


async def purge_student(*, user_id: UUID, student_id: UUID, storage: GuardedStorage) -> PurgeResult:
    """The purge (AM-B6): lock, plan, refuse on blockers, delete, verify, audit."""
    async with AsyncSessionLocal() as db:
        try:
            await _lock_student(db, user_id, student_id)
            plan = await plan_purge(db, user_id=user_id, student_id=student_id, storage=storage)
            if plan.blockers:
                raise PurgeBlocked(len(plan.blockers))
        except BaseException:
            await db.rollback()
            raise
        rows_deleted = await _commit_rows(db, plan)

    objects, failures = await _objects_after_commit(plan, storage)
    report = await verify_purged(plan, storage=storage)
    logger.info(
        "purge_audit user_id=%s student_id=%s rows=%s objects_deleted=%d failures=%d "
        "clean=%s soft_deleted=%d restorable_until=%s legacy_count_batches=%s "
        "unassigned=%d unassigned_job_ids=%s transcription_ids=%s graded_test_ids=%s",
        user_id, student_id, dict(sorted(rows_deleted.items())), len(objects), len(failures),
        report.clean, report.soft_deleted_count,
        report.restorable_until.isoformat() if report.restorable_until else None,
        sorted(map(str, plan.legacy_count_batches)),
        report.unassigned_count, sorted(map(str, report.unassigned_job_ids)),
        # Ids, never names: what `python -m app.scripts.verify_purge` re-lists later.
        sorted(map(str, plan.rows["transcriptions"])), sorted(map(str, plan.rows["graded_tests"])))
    return PurgeResult(plan=plan, rows_deleted=rows_deleted, objects_deleted=objects,
                       failures=failures, verify=report)
