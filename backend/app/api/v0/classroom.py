"""
Classroom API: Students, Classes, and Class Membership endpoints.

All endpoints require authentication (get_current_user).
All reads are scoped by user_id == current_user.id.
All detail/update/delete use get_owned_or_404.
user_id on every write is current_user.id — never from the request body.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, exists, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_db
from .auth import get_current_user
from ...api.deps import get_owned_or_404
from ...models.user import User
from ...models.student import Student
from ...models.classroom import Class, ClassMembership
from ...models.grading import GradedTest, GradingBatch
from ...schemas.classroom import (
    AddStudentToClassRequest,
    ClassDetailResponse,
    ClassMini,
    ClassResponse,
    CreateClassRequest,
    CreateStudentRequest,
    StudentDetailResponse,
    StudentMini,
    StudentResponse,
    UpdateClassRequest,
    UpdateStudentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/classroom", tags=["classroom"])


# =============================================================================
# Students
# =============================================================================

@router.post("/students", response_model=StudentResponse, status_code=201)
async def create_student(
    body: CreateStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = Student(
        user_id=current_user.id,
        full_name=body.full_name,
        notes=body.notes,
    )
    db.add(student)
    try:
        await db.commit()
        await db.refresh(student)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים תלמיד בשם זה")
    return StudentResponse.model_validate(student)


@router.get("/students", response_model=dict)
async def list_students(
    class_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    if class_id is not None:
        # Verify the class belongs to the current user before filtering by it
        await get_owned_or_404(db, Class, class_id, uid)
        stmt = (
            select(Student)
            .join(ClassMembership, ClassMembership.student_id == Student.id)
            .where(ClassMembership.class_id == class_id, Student.user_id == uid)
            .order_by(Student.full_name)
        )
    else:
        stmt = select(Student).where(Student.user_id == uid).order_by(Student.full_name)

    result = await db.execute(stmt)
    students = result.scalars().all()
    return {"students": [StudentResponse.model_validate(s) for s in students]}


@router.get("/students/{student_id}", response_model=StudentDetailResponse)
async def get_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Student)
        .where(Student.id == student_id, Student.user_id == current_user.id)
        .options(
            selectinload(Student.class_memberships).selectinload(ClassMembership.school_class)
        )
    )
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    classes = [
        ClassMini(id=m.school_class.id, name=m.school_class.name)
        for m in student.class_memberships
        if m.school_class is not None
    ]
    return StudentDetailResponse(
        id=student.id,
        full_name=student.full_name,
        notes=student.notes,
        created_at=student.created_at,
        classes=classes,
    )


@router.patch("/students/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: UUID,
    body: UpdateStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = await get_owned_or_404(db, Student, student_id, current_user.id)

    if body.full_name is not None:
        student.full_name = body.full_name
    if body.notes is not None:
        student.notes = body.notes
    student.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(student)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים תלמיד בשם זה")
    return StudentResponse.model_validate(student)


@router.delete("/students/{student_id}", status_code=204)
async def delete_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = await get_owned_or_404(db, Student, student_id, current_user.id)

    has_tests = await db.scalar(
        select(exists().where(GradedTest.student_id == student.id))
    )
    if has_tests:
        raise HTTPException(status_code=409, detail="לא ניתן למחוק תלמיד עם מבחנים בדוקים")

    await db.delete(student)
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Classes
# =============================================================================

@router.post("/classes", response_model=ClassResponse, status_code=201)
async def create_class(
    body: CreateClassRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_class = Class(
        user_id=current_user.id,
        name=body.name,
        subject_matter_id=body.subject_matter_id,
        school_year=body.school_year,
    )
    db.add(school_class)
    try:
        await db.commit()
        await db.refresh(school_class)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיימת כיתה בשם זה")

    # Reload with subject_matter
    result = await db.execute(
        select(Class)
        .where(Class.id == school_class.id)
        .options(selectinload(Class.subject_matter))
    )
    school_class = result.scalar_one()
    return _class_to_response(school_class, student_count=0)


@router.get("/classes", response_model=dict)
async def list_classes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    count_sub = (
        select(func.count(ClassMembership.student_id))
        .where(ClassMembership.class_id == Class.id)
        .correlate(Class)
        .scalar_subquery()
    )

    stmt = (
        select(Class, count_sub.label("student_count"))
        .where(Class.user_id == uid)
        .options(selectinload(Class.subject_matter))
        .order_by(Class.name)
    )
    rows = (await db.execute(stmt)).all()

    classes = [
        _class_to_response(row.Class, student_count=row.student_count or 0)
        for row in rows
    ]
    return {"classes": classes}


@router.get("/classes/{class_id}", response_model=ClassDetailResponse)
async def get_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Class)
        .where(Class.id == class_id, Class.user_id == current_user.id)
        .options(
            selectinload(Class.subject_matter),
            selectinload(Class.memberships).selectinload(ClassMembership.student),
        )
    )
    school_class = result.scalar_one_or_none()
    if school_class is None:
        raise HTTPException(status_code=404, detail="Class not found")

    # Count members
    student_count = len(school_class.memberships)

    students = [
        StudentMini(id=m.student.id, full_name=m.student.full_name)
        for m in school_class.memberships
        if m.student is not None
    ]

    base = _class_to_response(school_class, student_count=student_count)
    return ClassDetailResponse(
        **base.model_dump(),
        students=students,
    )


@router.patch("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: UUID,
    body: UpdateClassRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_class = await get_owned_or_404(db, Class, class_id, current_user.id)

    if body.name is not None:
        school_class.name = body.name
    if body.subject_matter_id is not None:
        school_class.subject_matter_id = body.subject_matter_id
    elif body.subject_matter_id is None and "subject_matter_id" in body.model_fields_set:
        school_class.subject_matter_id = None
    if body.school_year is not None:
        school_class.school_year = body.school_year
    school_class.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיימת כיתה בשם זה")

    # Reload with subject_matter and count
    count_sub = (
        select(func.count(ClassMembership.student_id))
        .where(ClassMembership.class_id == Class.id)
        .correlate(Class)
        .scalar_subquery()
    )
    row = (await db.execute(
        select(Class, count_sub.label("student_count"))
        .where(Class.id == class_id)
        .options(selectinload(Class.subject_matter))
    )).one()
    return _class_to_response(row.Class, student_count=row.student_count or 0)


@router.delete("/classes/{class_id}", status_code=204)
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_class = await get_owned_or_404(db, Class, class_id, current_user.id)

    has_batches = await db.scalar(
        select(exists().where(GradingBatch.class_id == school_class.id))
    )
    if has_batches:
        raise HTTPException(status_code=409, detail="לא ניתן למחוק כיתה עם בדיקות מבחנים")

    await db.delete(school_class)
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Class Membership
# =============================================================================

@router.post("/classes/{class_id}/students", status_code=204)
async def add_student_to_class(
    class_id: UUID,
    body: AddStudentToClassRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    # Both class and student must belong to current user
    await get_owned_or_404(db, Class, class_id, uid)
    await get_owned_or_404(db, Student, body.student_id, uid)

    existing = await db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == body.student_id,
        )
    )
    if existing:
        return Response(status_code=204)  # idempotent no-op

    db.add(ClassMembership(class_id=class_id, student_id=body.student_id))
    await db.commit()
    return Response(status_code=204)


@router.delete("/classes/{class_id}/students/{student_id}", status_code=204)
async def remove_student_from_class(
    class_id: UUID,
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    await get_owned_or_404(db, Class, class_id, uid)
    await get_owned_or_404(db, Student, student_id, uid)

    membership = await db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == student_id,
        )
    )
    if membership is None:
        return Response(status_code=204)  # no-op

    await db.delete(membership)
    await db.commit()
    return Response(status_code=204)


# =============================================================================
# Helpers
# =============================================================================

def _class_to_response(school_class: Class, student_count: int) -> ClassResponse:
    """Build a ClassResponse from ORM model + derived student count."""
    sm = school_class.subject_matter
    return ClassResponse(
        id=school_class.id,
        name=school_class.name,
        subject_matter_id=school_class.subject_matter_id,
        subject_matter_name=sm.name_he if sm else None,
        school_year=school_class.school_year,
        student_count=student_count,
        created_at=school_class.created_at,
    )
