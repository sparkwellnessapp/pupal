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
from fastapi.responses import JSONResponse
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
from ...models.transcription import Transcription
from ...schemas.classroom import (
    AddStudentToClassRequest,
    ClassDetailResponse,
    ClassMini,
    ClassResponse,
    CreateClassRequest,
    CreateStudentRequest,
    PurgePreviewResponse,
    SignedTestExam,
    SignedTestItem,
    SignedTestsResponse,
    SignedTestThumbnail,
    StudentDetailResponse,
    StudentMini,
    StudentResponse,
    UpdateClassRequest,
    UpdateStudentRequest,
)
from ...services.erasure import (
    GuardedStorage,
    PurgeBlocked,
    PurgeRefused,
    StudentNotFound,
    get_purge_storage,
    plan_purge,
    purge_student,
)
from ...services.student_signed_tests import (
    SignedTestRow,
    signed_tests_count,
    signed_tests_counts,
    signed_tests_for_student,
)
from ...services.thumbnail import page_image_path

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
    )
    db.add(student)
    try:
        await db.commit()
        await db.refresh(student)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים תלמיד בשם זה")
    # A student who was just created has no history — no query needed to know.
    return _student_response(student, signed_tests=0)


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
    # LST-4: the badge count for EVERY student in one grouped statement — the
    # roster with forty students issues exactly as many statements as with one
    # (pinned by test_student_profile's statement count).
    counts = await signed_tests_counts(db, uid)
    return {"students": [
        _student_response(s, signed_tests=counts.get(s.id, 0)) for s in students
    ]}


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
        created_at=student.created_at,
        classes=classes,
        signed_tests_count=await signed_tests_count(db, current_user.id, student.id),
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
    student.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(student)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים תלמיד בשם זה")
    return _student_response(
        student, signed_tests=await signed_tests_count(db, current_user.id, student.id))


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: GuardedStorage = Depends(get_purge_storage),
):
    """[Part B §12, §14] Privacy-complete deletion: the purge, then its verify
    report as the 200 body (M-B4). Replaces §5.4's interim `student_has_data`
    409. 404 for another teacher's student (PRV-4); 409 `grading_in_progress`
    while a grade or job of hers is in flight (PRV-5), touching nothing."""
    await get_owned_or_404(db, Student, student_id, current_user.id)
    await db.close()                      # the purge owns its session and transaction
    try:
        result = await purge_student(user_id=current_user.id, student_id=student_id, storage=storage)
    except StudentNotFound:
        raise HTTPException(status_code=404, detail="Student not found")
    except PurgeBlocked as exc:
        return JSONResponse(status_code=409, content={"detail": "grading_in_progress", "count": exc.count})
    except PurgeRefused as exc:
        logger.error("purge_refused student_id=%s reason=%s detail=%s",
                     student_id, exc.reason, exc.detail)
        return JSONResponse(status_code=409, content={"detail": "purge_refused", "reason": exc.reason})
    return result.payload()


@router.get("/students/{student_id}/purge-preview", response_model=PurgePreviewResponse)
async def get_student_purge_preview(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: GuardedStorage = Depends(get_purge_storage),
):
    """[Part B §12] The purge plan for this student, counted — what the Delete
    dialog states before she confirms. An UNLOCKED read (AM-B6) that never
    writes. Ownership is checked before any storage call (PRV-4: 404)."""
    await get_owned_or_404(db, Student, student_id, current_user.id)
    try:
        plan = await plan_purge(db, user_id=current_user.id, student_id=student_id, storage=storage)
    except StudentNotFound:
        raise HTTPException(status_code=404, detail="Student not found")
    except PurgeRefused as exc:
        # An operator's problem, not hers: ids only in the log (OD-B4), the
        # reason code on the wire.
        logger.error("purge_refused student_id=%s reason=%s detail=%s",
                     student_id, exc.reason, exc.detail)
        return JSONResponse(status_code=409,
                            content={"detail": "purge_refused", "reason": exc.reason})
    return plan.summary()


@router.get("/students/{student_id}/signed-tests", response_model=SignedTestsResponse)
async def get_student_signed_tests(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[student-profile PR §5.1–5.3] Every APPROVED test of this student, one
    row per chain, newest upload first — the profile's rows.

    Named for the invariant it carries (M-A1): `signed-tests` cannot quietly
    grow drafts. The definition lives in ONE place, `student_signed_tests`,
    and the roster badge and the header count derive from the same leaves
    (LST-4). Cross-tenant is 404 (LST-5), like every classroom read.
    """
    await get_owned_or_404(db, Student, student_id, current_user.id)
    result = await signed_tests_for_student(db, current_user.id, student_id)
    return SignedTestsResponse(
        signed_tests_count=result.count,
        truncated=result.truncated,
        signed_tests=[_signed_test_item(row) for row in result.rows],
    )


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

def _student_response(student: Student, *, signed_tests: int) -> StudentResponse:
    return StudentResponse(
        id=student.id,
        full_name=student.full_name,
        created_at=student.created_at,
        signed_tests_count=signed_tests,
    )


def _signed_test_item(row: SignedTestRow) -> SignedTestItem:
    gt = row.graded_test
    return SignedTestItem(
        graded_test_id=gt.id,
        exam=SignedTestExam(
            batch_id=row.batch_id,
            name=row.batch_name,
            rubric_name=row.rubric_name,
            class_name=row.class_name,
            uploaded_at=row.uploaded_at,
        ),
        approved_at=gt.approved_at,
        total_score=gt.total_score,
        total_possible=gt.total_possible,
        thumbnail=SignedTestThumbnail(
            # The SAME resource `BatchGradedItem.page1_image_url` names, minted
            # by the same function — a scan with no rendered page offers none.
            page1_image_url=(
                page_image_path(gt.transcription_id, 1) if row.page_count >= 1 else None
            ),
            stamp_position=row.stamp_position,
        ),
    )


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
