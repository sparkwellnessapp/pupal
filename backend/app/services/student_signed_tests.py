"""
THE definition of «a student's signed tests» — one place, three consumers
(PR_student_profile.md §5.1; CLAUDE.md §0.4).

The profile's list, the profile's count and the roster's badge all derive from
`signed_leaves` below. A badge that disagrees with the profile is therefore not
a bug that can exist here — it would have to be two definitions, and there is
one (LST-4 CountEqualsList).

Named invariants this module carries:

  LST-1 ApprovedOnly     only `status = 'approved'` rows ever appear or count.
  LST-2 OneRowPerChain   chain identity is `(transcription_id, rubric_id)`; the
                         row shown is the approved row with the greatest
                         `approved_at`. A chain whose leaf is a draft still
                         shows its last approved version; a chain with no
                         approved row does not appear at all (OD-5).
  LST-4 CountEqualsList  one definition; the roster count is ONE grouped
                         statement over it, never a query per student.
  LST-5 OwnerScoped      every SELECT here carries `user_id`. The student FK is
                         not the scope — a row of another teacher that named
                         this student id would still be that teacher's row.

Display order (M-A3): the exam event's upload date, newest first — the batch's
`created_at`, or the scan's own `created_at` when the test never had a batch
(single-flow) — then `approved_at` DESC, then `id`, so a tie is deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models.classroom import Class
from ..models.grading import GradedTest, GradingBatch, Rubric
from ..models.transcription import Transcription
from .returned_exam import OVERLAY_KEY, effective_stamp_position

#: §5.3 — tens of tests per student per year, so there is no pagination. Past
#: this the list is cut and SAYS so (`truncated`); the count is always true.
SIGNED_TESTS_CAP = 200


def signed_leaves(user_id: UUID) -> Select:
    """LST-1 + LST-2 as one SELECT: for every chain `(transcription_id,
    rubric_id)` of this teacher, the approved row with the greatest
    `approved_at` — and no row for a chain that has none.

    `DISTINCT ON` is PostgreSQL's own spelling of "one row per group, chosen by
    the ORDER BY"; the trailing `id` makes a same-instant tie deterministic.
    """
    return (
        select(GradedTest)
        .where(GradedTest.user_id == user_id, GradedTest.status == "approved")
        .distinct(GradedTest.transcription_id, GradedTest.rubric_id)
        .order_by(
            GradedTest.transcription_id,
            GradedTest.rubric_id,
            GradedTest.approved_at.desc(),
            GradedTest.id,
        )
    )


@dataclass(frozen=True)
class SignedTestRow:
    """One profile row: the approved graded test plus the facts the row states
    about it — the exam event (M-A4: the stored name, or the parts), the class,
    the upload date, and what the thumbnail needs to draw the stamp."""
    graded_test: GradedTest
    batch_id: Optional[UUID]
    batch_name: Optional[str]
    rubric_name: Optional[str]
    class_name: Optional[str]
    uploaded_at: datetime
    stamp_default: Optional[dict]
    page_count: int

    @property
    def stamp_position(self) -> Optional[dict]:
        """The RESOLVED position — the same precedence the returned exam's PDF
        uses (`effective_stamp_position`: her per-test overlay, else the batch
        default, else nothing — the client then draws the auto corner exactly
        as the returned page does). One resolver, so the 100 px thumbnail and
        the full page cannot put the stamp in two places (OD-8, FA-3)."""
        overlay = (self.graded_test.draft_json or {}).get(OVERLAY_KEY) or {}
        return effective_stamp_position(overlay.get("stamp_position"), self.stamp_default)


@dataclass(frozen=True)
class SignedTests:
    rows: list[SignedTestRow]
    #: The TRUE count, cap or no cap (§5.3).
    count: int
    truncated: bool


async def signed_tests_for_student(
    db: AsyncSession, user_id: UUID, student_id: UUID, *, cap: int = SIGNED_TESTS_CAP,
) -> SignedTests:
    """The profile's rows and count, in ONE statement: `count(*) OVER ()` runs
    before the LIMIT, so the count is the whole set even when the list is cut."""
    leaves = (
        signed_leaves(user_id)
        .where(GradedTest.student_id == student_id)
        .subquery("signed_leaves")
    )
    leaf = aliased(GradedTest, leaves)
    uploaded_at = func.coalesce(GradingBatch.created_at, Transcription.created_at)

    stmt = (
        select(
            leaf,
            GradingBatch.id.label("batch_id"),
            GradingBatch.name.label("batch_name"),
            GradingBatch.stamp_position_default.label("stamp_default"),
            Rubric.name.label("rubric_name"),
            Class.name.label("class_name"),
            uploaded_at.label("uploaded_at"),
            Transcription.draft_json["page_count"].as_integer().label("page_count"),
            func.count().over().label("total"),
        )
        .join(Transcription, Transcription.id == leaf.transcription_id)
        .outerjoin(GradingBatch, GradingBatch.id == leaf.batch_id)
        .outerjoin(Rubric, Rubric.id == leaf.rubric_id)
        .outerjoin(Class, Class.id == GradingBatch.class_id)
        .order_by(uploaded_at.desc(), leaf.approved_at.desc(), leaf.id)
        .limit(cap)
    )
    records = (await db.execute(stmt)).all()

    rows = [
        SignedTestRow(
            graded_test=r[0],
            batch_id=r.batch_id,
            batch_name=r.batch_name,
            rubric_name=r.rubric_name,
            class_name=r.class_name,
            uploaded_at=r.uploaded_at,
            stamp_default=r.stamp_default,
            page_count=int(r.page_count or 0),
        )
        for r in records
    ]
    count = int(records[0].total) if records else 0
    return SignedTests(rows=rows, count=count, truncated=count > len(rows))


async def signed_tests_count(db: AsyncSession, user_id: UUID, student_id: UUID) -> int:
    """The profile header's count — the same leaves, counted."""
    leaves = (
        signed_leaves(user_id)
        .where(GradedTest.student_id == student_id)
        .subquery("signed_leaves")
    )
    return int(await db.scalar(select(func.count()).select_from(leaves)) or 0)


async def signed_tests_counts(db: AsyncSession, user_id: UUID) -> dict[UUID, int]:
    """The roster's badges — every student of this teacher, ONE grouped
    statement (LST-4). A student with no signed test is simply absent; the
    caller reads `.get(id, 0)`."""
    leaves = signed_leaves(user_id).subquery("signed_leaves")
    stmt = select(leaves.c.student_id, func.count()).group_by(leaves.c.student_id)
    return {student_id: int(n) for student_id, n in (await db.execute(stmt)).all()}
