"""
VERIFY — re-run the plan's discovery after the fact (PR §12; PRV-7 VerifiedAfter).

Every table count must be 0, every listing empty. It is not vacuous: on a
student not yet purged it reports exactly what is still there. It also reports
what a listing hides — objects deleted but still RESTORABLE for the bucket's
7-day soft-delete window (OD-B3) — and it asserts the dead tables stay empty
(OD-B1; graded_test_pdfs since 2026-09-23). Unassigned scans in her batches are
carried as a count and job ids for the audit line (OD-B6); they never make a
report unclean, because they were never hers.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional
from uuid import UUID

from sqlalchemy import text

from app.database import AsyncSessionLocal

from .plan import PurgePlan
from .registry import DEAD_TABLES
from .storage import GuardedStorage


@dataclass(frozen=True)
class VerifyReport:
    student_id: UUID
    rows_remaining: Mapping[str, int]              # the plan's rows still present, per table
    student_refs_remaining: int                    # any row still naming her, planned or not
    objects_remaining: frozenset[tuple[str, str]]
    soft_deleted_count: int
    restorable_until: Optional[datetime]
    legacy_tables_empty: bool
    unassigned_count: int
    unassigned_job_ids: frozenset[UUID]

    @property
    def clean(self) -> bool:
        return (all(n == 0 for n in self.rows_remaining.values())
                and self.student_refs_remaining == 0
                and not self.objects_remaining
                and self.legacy_tables_empty)

    def payload(self) -> dict:
        """The wire form (M-B4): counts, not object names; no unassigned scans —
        the teacher has nothing to do about them (OD-B6)."""
        return {
            "clean": self.clean,
            "rows_remaining": dict(self.rows_remaining),
            "objects_remaining": len(self.objects_remaining),
            "soft_deleted_count": self.soft_deleted_count,
            "restorable_until": self.restorable_until.isoformat() if self.restorable_until else None,
            "legacy_tables_empty": self.legacy_tables_empty,
        }


_ROWS = {
    "graded_tests": "SELECT COUNT(*) FROM graded_tests WHERE id = ANY(:ids)",
    "transcription_jobs": "SELECT COUNT(*) FROM transcription_jobs WHERE id = ANY(:ids)",
    "transcriptions": "SELECT COUNT(*) FROM transcriptions WHERE id = ANY(:ids)",
    "students": "SELECT COUNT(*) FROM students WHERE id = ANY(:ids)",
    "class_memberships": "SELECT COUNT(*) FROM class_memberships WHERE class_id = ANY(:ids) AND student_id = :s",
}


async def verify_purged(plan: PurgePlan, *, storage: GuardedStorage) -> VerifyReport:
    async with AsyncSessionLocal() as db:
        remaining = {}
        for table, ids in plan.rows.items():
            remaining[table] = (await db.execute(text(_ROWS[table]),
                                                 {"ids": list(ids), "s": plan.student_id})).scalar_one()
        refs = (await db.execute(text(
            "SELECT (SELECT COUNT(*) FROM graded_tests WHERE student_id = :s)"
            "     + (SELECT COUNT(*) FROM transcriptions WHERE student_id = :s)"
            "     + (SELECT COUNT(*) FROM class_memberships WHERE student_id = :s)"),
            {"s": plan.student_id})).scalar_one()
        dead_rows = 0
        for table in DEAD_TABLES:
            dead_rows += (await db.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()

    def _relist():
        live, soft = set(), []
        for bucket, target in sorted(plan.listed):
            names = storage.list_prefix(bucket, target)
            gone = storage.list_soft_deleted(bucket, target)
            if not target.endswith("/"):                      # a scan: exact only
                names = [n for n in names if n == target]
                gone = [(n, t) for (n, t) in gone if n == target]
            live.update((bucket, n) for n in names)
            soft.extend(gone)
        return live, soft

    live, soft = await asyncio.to_thread(_relist)
    return VerifyReport(
        student_id=plan.student_id,
        rows_remaining=remaining,
        student_refs_remaining=refs,
        objects_remaining=frozenset(live),
        soft_deleted_count=len(soft),
        restorable_until=max((t for (_, t) in soft if t is not None), default=None),
        legacy_tables_empty=dead_rows == 0,
        unassigned_count=plan.unassigned.count,
        unassigned_job_ids=plan.unassigned.job_ids,
    )
