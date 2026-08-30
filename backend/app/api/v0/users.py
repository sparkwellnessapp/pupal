"""
User API endpoints - v0.

Endpoints for user management, subject matters, and rubric sharing.

Auth: every route here uses the ONE shared dependency, `auth.get_current_user`
(CLAUDE.md §9). This module used to define its own local `get_current_user` that
read a `user_id` QUERY PARAMETER and trusted it — no header, no signature, no
expiry. It failed in both directions at once: valid session tokens were rejected
(401) while anonymous callers who supplied `?user_id=<victim>` were served, up to
and including an unauthenticated write. It is deleted, not repaired: two auth
implementations cannot stay in agreement, which is the whole reason §9 exists.
`tests/api/test_users_auth.py::test_users_routes_use_canonical_auth` is the
structural guard that keeps a replacement from coming back.

The profile read that lived here (`GET /users/me`) was a caller-less duplicate of
`GET /auth/me` and was removed; `auth.py` owns the profile shape.
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ...database import get_db
from ..deps import get_owned_or_404
from .auth import get_current_user
from ...models.user import User
from ...models.subject_matter import SubjectMatter
from ...models.rubric_share import RubricShare, SharePermission
from ...models.grading import Rubric, GradedTest
from ...schemas.user import (
    SubjectMatterResponse,
    UpdateSubjectMattersRequest,
    ShareRubricRequest,
    RubricShareResponse,
    RubricShareListResponse,
    UserRubricResponse,
    UserRubricsListResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/users", tags=["users"])


# =============================================================================
# Subject Matters Endpoints
# =============================================================================

@router.get("/subject-matters", response_model=List[SubjectMatterResponse])
async def get_all_subject_matters(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> List[SubjectMatterResponse]:
    """
    Get all available subject matters.
    
    Returns the complete list of subject matters for dropdowns.
    """
    query = select(SubjectMatter).order_by(SubjectMatter.name_he)
    result = await db.execute(query)
    subject_matters = result.scalars().all()
    
    return [
        SubjectMatterResponse(
            id=sm.id,
            code=sm.code,
            name_en=sm.name_en,
            name_he=sm.name_he,
        )
        for sm in subject_matters
    ]


# =============================================================================
# User Profile Endpoints
#
# The profile READ lives at GET /api/v0/auth/me and only there. This module
# carried a byte-identical duplicate whose response was built by hand; it had no
# caller (the frontend has always used /auth/me) and two hand-maintained copies
# of one response shape is the truncation risk §0.4 warns about.
# =============================================================================

@router.get("/me/subject-matters", response_model=List[SubjectMatterResponse])
async def get_user_subject_matters(
    user: User = Depends(get_current_user),
) -> List[SubjectMatterResponse]:
    """
    Get the current user's assigned subject matters.
    """
    return [
        SubjectMatterResponse(
            id=sm.id,
            code=sm.code,
            name_en=sm.name_en,
            name_he=sm.name_he,
        )
        for sm in user.subject_matters
    ]


@router.put("/me/subject-matters", response_model=List[SubjectMatterResponse])
async def update_user_subject_matters(
    request: UpdateSubjectMattersRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SubjectMatterResponse]:
    """
    Update the current user's subject matters.
    
    Replaces all existing subject matter assignments with the provided list.
    """
    # Fetch the subject matters
    query = select(SubjectMatter).where(SubjectMatter.id.in_(request.subject_matter_ids))
    result = await db.execute(query)
    subject_matters = result.scalars().all()
    
    if len(subject_matters) != len(request.subject_matter_ids):
        raise HTTPException(status_code=400, detail="One or more subject matter IDs are invalid")
    
    # Update user's subject matters
    user.subject_matters = list(subject_matters)
    await db.commit()
    
    return [
        SubjectMatterResponse(
            id=sm.id,
            code=sm.code,
            name_en=sm.name_en,
            name_he=sm.name_he,
        )
        for sm in user.subject_matters
    ]


# =============================================================================
# User's Rubrics Endpoints
# =============================================================================

@router.get("/me/rubrics", response_model=UserRubricsListResponse)
async def get_user_rubrics(
    owned_only: bool = Query(False, description="Only return owned rubrics"),
    shared_only: bool = Query(False, description="Only return shared rubrics"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRubricsListResponse:
    """
    Get all rubrics for the current user.
    
    Includes both owned rubrics and rubrics shared with the user.
    """
    rubrics = []
    owned_count = 0
    shared_count = 0
    
    # Fetch owned rubrics
    if not shared_only:
        query = select(Rubric).where(Rubric.user_id == user.id).order_by(Rubric.created_at.desc())
        result = await db.execute(query)
        owned_rubrics = result.scalars().all()
        owned_count = len(owned_rubrics)
        
        for r in owned_rubrics:
            rubrics.append(UserRubricResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                total_points=r.total_points,
                created_at=r.created_at,
                is_owned=True,
                permission=None,
                owner_name=None,
            ))
    
    # Fetch shared rubrics
    if not owned_only:
        query = (
            select(RubricShare)
            .where(RubricShare.shared_with_user_id == user.id)
            .options(
                selectinload(RubricShare.rubric),
                selectinload(RubricShare.owner),
            )
        )
        result = await db.execute(query)
        shares = result.scalars().all()
        shared_count = len(shares)
        
        for share in shares:
            r = share.rubric
            rubrics.append(UserRubricResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                total_points=r.total_points,
                created_at=r.created_at,
                is_owned=False,
                permission=share.permission.value,
                owner_name=share.owner.full_name,
            ))
    
    return UserRubricsListResponse(
        owned_count=owned_count,
        shared_count=shared_count,
        rubrics=rubrics,
    )


@router.get("/me/graded-tests", response_model=List[dict])
async def get_user_graded_tests(
    rubric_id: Optional[UUID] = Query(None, description="Filter by rubric ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Get all graded tests for the current user.
    
    Optionally filter by rubric ID.
    """
    query = select(GradedTest).where(GradedTest.user_id == user.id)
    
    if rubric_id:
        query = query.where(GradedTest.rubric_id == rubric_id)
    
    query = query.order_by(GradedTest.created_at.desc())
    result = await db.execute(query)
    tests = result.scalars().all()
    
    return [
        {
            "id": str(t.id),
            "rubric_id": str(t.rubric_id),
            "student_name": t.student_name,
            "filename": t.filename,
            "total_score": t.total_score,
            "total_possible": t.total_possible,
            "percentage": t.percentage,
            "created_at": t.created_at.isoformat(),
        }
        for t in tests
    ]


# =============================================================================
# Rubric Sharing Endpoints
# =============================================================================

@router.post("/rubrics/{rubric_id}/share", response_model=RubricShareResponse)
async def share_rubric(
    rubric_id: UUID,
    request: ShareRubricRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricShareResponse:
    """
    Share a rubric with another user by email.
    
    Only the rubric owner can share it.
    """
    # Ownership: a rubric the caller does not own is indistinguishable from a
    # nonexistent one (§9 — 404, never 403).
    await get_owned_or_404(db, Rubric, rubric_id, user.id)

    # Find target user
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with email {request.email} not found")

    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot share rubric with yourself")

    # Check if already shared
    query = select(RubricShare).where(
        RubricShare.rubric_id == rubric_id,
        RubricShare.shared_with_user_id == target_user.id,
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Rubric already shared with this user")

    # Create share
    share = RubricShare(
        rubric_id=rubric_id,
        owner_user_id=user.id,
        shared_with_user_id=target_user.id,
        permission=SharePermission(request.permission),
    )
    db.add(share)
    try:
        await db.commit()
    except IntegrityError:
        # uq_rubric_share (rubric_id, shared_with_user_id) — the check above is
        # a TOCTOU window, so a concurrent share lands here. §9: 409 after
        # rollback, never a bare 500.
        await db.rollback()
        raise HTTPException(status_code=409, detail="Rubric already shared with this user")
    await db.refresh(share)

    return RubricShareResponse(
        id=share.id,
        rubric_id=share.rubric_id,
        shared_with_email=target_user.email,
        shared_with_name=target_user.full_name,
        permission=share.permission.value,
        created_at=share.created_at,
    )


@router.get("/rubrics/{rubric_id}/shares", response_model=RubricShareListResponse)
async def get_rubric_shares(
    rubric_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RubricShareListResponse:
    """
    Get all shares for a rubric.
    
    Only the rubric owner can view shares.
    """
    # Ownership: 404 for a rubric the caller does not own (§9).
    await get_owned_or_404(db, Rubric, rubric_id, user.id)

    # Get shares
    query = (
        select(RubricShare)
        .where(RubricShare.rubric_id == rubric_id)
        .options(selectinload(RubricShare.shared_with))
    )
    result = await db.execute(query)
    shares = result.scalars().all()
    
    return RubricShareListResponse(
        rubric_id=rubric_id,
        owner_email=user.email,
        shares=[
            RubricShareResponse(
                id=s.id,
                rubric_id=s.rubric_id,
                shared_with_email=s.shared_with.email,
                shared_with_name=s.shared_with.full_name,
                permission=s.permission.value,
                created_at=s.created_at,
            )
            for s in shares
        ],
    )


@router.delete("/rubrics/{rubric_id}/shares/{share_id}")
async def delete_rubric_share(
    rubric_id: UUID,
    share_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Remove a rubric share.
    
    Only the rubric owner can remove shares.
    """
    # Ownership: 404 for a rubric the caller does not own (§9).
    await get_owned_or_404(db, Rubric, rubric_id, user.id)

    # Find and delete share
    query = select(RubricShare).where(
        RubricShare.id == share_id,
        RubricShare.rubric_id == rubric_id,
    )
    result = await db.execute(query)
    share = result.scalar_one_or_none()
    
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    
    await db.delete(share)
    await db.commit()
    
    return {"message": "Share removed successfully"}
