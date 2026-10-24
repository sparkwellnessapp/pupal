"""
Names on the student link (§6.3, D16, SCN-9).

The student types a name; it is matched against the LINK'S CLASS roster by
the one normalizer (`batch_triage.normalize_name` — exact after
normalization, token-order independent). Exactly one match → that student;
zero or several → no match. The caller may return the single match's display
name to the student and NOTHING else: no id, no other name, no count
(SCN-9). The server recomputes the match on every call and never trusts a
client-sent id.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.classroom import ClassMembership
from ...models.student import Student
from ..batch_triage import match_student, normalize_name


async def class_roster(db: AsyncSession, class_id: Optional[UUID], user_id: UUID) -> list[Student]:
    if class_id is None:
        return []
    return list((await db.execute(
        select(Student)
        .join(ClassMembership, ClassMembership.student_id == Student.id)
        .where(ClassMembership.class_id == class_id, Student.user_id == user_id)
        .order_by(Student.full_name)
    )).scalars().all())


async def identify(db: AsyncSession, *, class_id: Optional[UUID], user_id: UUID,
                   name: str) -> Optional[Student]:
    roster = await class_roster(db, class_id, user_id)
    m = match_student(name, roster)
    if m.match_confidence != "exact":
        return None
    return next(s for s in roster if str(s.id) == m.student_id)


def same_name(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b) and normalize_name(a) == normalize_name(b)
