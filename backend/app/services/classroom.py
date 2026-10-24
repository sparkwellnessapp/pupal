"""
Students, classes and memberships — the writes, in ONE place.

The classroom router and the capture flows (teacher-page "create student",
the pending-student approval, "create class" on a capture link) all create
through here. Each function FLUSHES inside a SAVEPOINT and never commits: the
caller owns the transaction, and a duplicate-name refusal must not poison it
(a bare IntegrityError at flush aborts the whole transaction in Postgres;
the savepoint rolls back only this insert).

`user_id` is always the caller's authenticated teacher (CLAUDE.md §9).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.classroom import Class, ClassMembership
from ..models.student import Student


class NameTaken(Exception):
    """`students_unique_name_per_user` / `classes_unique_name_per_user` fired."""


async def create_student(db: AsyncSession, *, user_id: UUID, full_name: str) -> Student:
    student = Student(user_id=user_id, full_name=full_name)
    try:
        async with db.begin_nested():
            db.add(student)
            await db.flush()
    except IntegrityError:
        raise NameTaken(full_name) from None
    return student


async def create_class(db: AsyncSession, *, user_id: UUID, name: str,
                       subject_matter_id: Optional[int] = None,
                       school_year: Optional[str] = None) -> Class:
    school_class = Class(user_id=user_id, name=name, subject_matter_id=subject_matter_id,
                         school_year=school_year)
    try:
        async with db.begin_nested():
            db.add(school_class)
            await db.flush()
    except IntegrityError:
        raise NameTaken(name) from None
    return school_class


async def add_membership(db: AsyncSession, *, class_id: UUID, student_id: UUID) -> None:
    """Idempotent. Ownership of BOTH ids is the caller's to check first."""
    existing = await db.scalar(select(ClassMembership).where(
        ClassMembership.class_id == class_id, ClassMembership.student_id == student_id))
    if existing is None:
        db.add(ClassMembership(class_id=class_id, student_id=student_id))
        await db.flush()
