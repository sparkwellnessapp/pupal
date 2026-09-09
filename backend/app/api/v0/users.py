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
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from ...database import get_db
from ..deps import get_owned_or_404
from .auth import build_user_response, get_current_user
from ...models.user import User
from ...models.school import School
from ...models.subject_matter import SubjectMatter
from ...models.rubric_share import RubricShare, SharePermission
from ...models.grading import Rubric, GradedTest
from ...services.cloud_tasks_service import (
    enqueue_onboarding_sheet_task_or_log,
    verify_task_request,
)
from ...services.onboarding_sheet_service import upsert_user_row
from ...services.school_resolution import (
    ensure_user_school,
    resolve_or_create_school,
    set_user_schools,
)
from ...schemas.user import (
    SchoolResponse,
    SubjectMatterResponse,
    UpdateSubjectMattersRequest,
    ShareRubricRequest,
    RubricShareResponse,
    RubricShareListResponse,
    UserResponse,
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


# ---------------------------------------------------------------------------
# PR-G6 — the teacher's school (the fifth override-attribution key)
# ---------------------------------------------------------------------------

class UpdateMeRequest(BaseModel):
    """Exactly one of the two is meaningful per call. `school_id` picks an
    existing school; `school_name` is the one-field onboarding answer and is
    create-or-pick. Sending neither is a no-op, not an error — the prompt is
    skippable by design."""
    school_id: Optional[UUID] = None
    school_name: Optional[str] = None
    school_city: Optional[str] = None


class UpdateMeResponse(BaseModel):
    id: UUID
    school_id: Optional[UUID] = None
    school_name: Optional[str] = None


@router.patch("/me/school", response_model=UpdateMeResponse)
async def update_me(
    body: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UpdateMeResponse:
    """Set the teacher's school. The owning user is ALWAYS current_user
    (CLAUDE.md §9) — there is no user_id in the body or the query string.

    PATH NOTE (open decision, owner): the spec's PR-G6 text says
    `PATCH /users/me`. Mounting ANY method at that exact path turns
    `GET /api/v0/users/me` from 404 into 405 and fires
    `test_duplicate_users_me_is_gone` — the guard left behind by the worst bug
    this codebase shipped (two auth resolvers; a duplicate profile route).
    The guard's intent is intact either way, but it is written as `== 404` and
    weakening a guard of that provenance to accommodate a new endpoint is not a
    call to make in passing. `/me/school` follows the existing sibling
    (`PUT /me/subject-matters`), says what it does, and leaves the guard
    untouched. One line to move it if the owner prefers the spec's path.

    Matching is NORMALIZED-EXACT, never fuzzy: trimmed, internal whitespace
    collapsed, case-folded, mirroring migration 018's unique index. Two schools
    differing by one character are two schools; a fuzzy match would merge real
    institutions with no way back.
    """
    school: Optional[School] = None

    if body.school_id is not None:
        school = await db.get(School, body.school_id)
        if school is None:
            # 404, not 403/422: a school id the caller cannot see and one that
            # does not exist are the same answer (§9 — existence is not leaked).
            raise HTTPException(status_code=404, detail="בית הספר לא נמצא")

    elif body.school_name and body.school_name.strip():
        # The create-or-pick rule lives in ONE place (school_resolution) now that
        # PUT /me/schools is its second caller.
        try:
            school = await resolve_or_create_school(
                db, body.school_name, body.school_city,
            )
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409,
                                detail="בית ספר בשם הזה כבר קיים")

    if school is not None:
        # [022] Both surfaces move together, through the one writer. Membership
        # is a UNION here: this endpoint answers "which school is primary",
        # never "which schools did you drop".
        await ensure_user_school(db, current_user, school)
        await db.commit()

    return UpdateMeResponse(
        id=current_user.id,
        school_id=current_user.school_id,
        school_name=school.name if school is not None else None,
    )


# ---------------------------------------------------------------------------
# Onboarding (migration 022) — the teacher's schools, profile, completion stamp
#
# Three siblings of the two endpoints above. All follow §9: the owning user is
# ALWAYS current_user, never a body field or a query parameter.
#
# PATH NOTE: none of these mounts at `/users/me`. Mounting ANY method there
# turns `GET /api/v0/users/me` from 404 into 405 and fires
# `test_duplicate_users_me_is_gone` — the guard left by the two-auth-resolvers
# incident. They follow the `/me/<thing>` shape the module already uses.
# ---------------------------------------------------------------------------

class SchoolInput(BaseModel):
    """One school as the teacher picked it.

    `ministry_symbol` (סמל מוסד) is present when she chose from the list and
    ABSENT when she typed a school the list lacks. It — not the name — is the
    identity when present (023): the real export has 82 normalized names shared
    by 213 institutions, two of them in the same city.

    Validated as a numeric string rather than as exactly six digits: every symbol
    in today's export is 6 digits, but hard-coding that length would break
    onboarding for a teacher whose school the Ministry numbers differently, and
    the format is not ours to fix. Non-numeric input is junk and is refused,
    because this value becomes an IDENTITY.
    """
    name: str = Field(..., min_length=1, max_length=255)
    city: Optional[str] = Field(None, max_length=255)
    # [0-9], NOT \d: \d is UNICODE-aware in both Python's re and Pydantic's Rust
    # engine, so «١٢٣٤٥٦» (Arabic-Indic digits) passed it — a string a human
    # cannot tell from «123456» but which is a DIFFERENT identity, i.e. exactly
    # the confusable-row hazard this column exists to remove. Caught by
    # test_the_validation_still_refuses_junk.
    ministry_symbol: Optional[str] = Field(None, pattern=r"^[0-9]{4,12}$")


class UpdateSchoolsRequest(BaseModel):
    """FULL REPLACEMENT, like `PUT /me/subject-matters` beside it. There are no
    merge semantics anywhere in this codebase and this is not the place to
    invent them. An empty list is a legitimate answer — the schools step is the
    skippable one — and it clears both the junction and the attribution key."""
    schools: List[SchoolInput] = Field(default_factory=list, max_length=20)


class UpdateProfileRequest(BaseModel):
    """Both fields optional; sending neither is a no-op, not an error.

    `gender` is a closed set including an explicit 'unspecified' — "prefer not
    to say" is an ANSWER and is stored as one. It is collected for future
    address forms; nothing outside onboarding reads it yet (owner ruling D4:
    the product's Hebrew copy is NOT re-gendered by this change)."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    gender: Optional[Literal["female", "male", "unspecified"]] = None


@router.put("/me/schools", response_model=List[SchoolResponse])
async def update_user_schools(
    body: UpdateSchoolsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SchoolResponse]:
    """Replace the teacher's school list.

    THE PR-G6 RULE, in one place: `users.school_id` remains the single
    override-attribution key and is set to the FIRST school in the submitted
    list. The junction (`user_schools`) is the full truth; the column is the key
    drawn from it. Reordering the list moves the attribution key — that is
    intended, and is the only way a single-column key can follow a multi-valued
    answer. `override_attribution.py` is unchanged and keeps reading one column.

    Duplicates in the request collapse under the SAME normalized-exact rule the
    resolver uses, so "Blich, Ramat Gan" twice is one school, and the first
    occurrence keeps its position (which matters — position 0 is the key).
    """
    # Validate the WHOLE list before touching the database. A name rejected
    # halfway through would otherwise have created real `schools` rows for the
    # entries before it — rolled back by the session teardown, but only by luck
    # of the teardown, and only after the writes were issued.
    for entry in body.schools:
        if not entry.name.strip():
            # Whitespace-only survives min_length=1; it is not a school.
            raise HTTPException(status_code=422, detail="שם בית ספר ריק")

    resolved: List[School] = []
    seen_ids: Set[UUID] = set()

    for entry in body.schools:
        try:
            school = await resolve_or_create_school(
                db, entry.name, entry.city, entry.ministry_symbol,
            )
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="בית ספר בשם הזה כבר קיים")
        if school.id in seen_ids:
            continue
        seen_ids.add(school.id)
        resolved.append(school)

    await set_user_schools(db, current_user, resolved)
    await db.commit()

    return [
        SchoolResponse(
            id=s.id, name=s.name, city=s.city, ministry_symbol=s.ministry_symbol,
        )
        for s in resolved
    ]


@router.patch("/me/profile", response_model=UserResponse)
async def update_user_profile(
    body: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update the teacher's own name and/or gender.

    Until now NOTHING could write `full_name` — the profile screen's save button
    called no endpoint at all — so a typo at signup was permanent.

    Answers with the ONE profile shape (`build_user_response`, owned by
    auth.py). A second hand-built copy of that response is the truncation risk
    §6 documents; there is no second copy here.
    """
    if body.full_name is not None:
        name = body.full_name.strip()
        if not name:
            # The column is NOT NULL: a name that strips to nothing is a
            # validation failure, not an erasure.
            raise HTTPException(status_code=422, detail="שם מלא לא יכול להיות ריק")
        current_user.full_name = name

    if body.gender is not None:
        current_user.gender = body.gender

    await db.commit()
    return build_user_response(current_user)


@router.post("/me/onboarding/complete", response_model=UserResponse)
async def complete_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Stamp onboarding as finished. IDEMPOTENT: an already-stamped user keeps
    the original timestamp and gets a 200, so a double-click, a retry, or a
    re-entry can never re-stamp and never 409s.

    A POST rather than a PATCH with a boolean, deliberately: the client does not
    get to UNSET this. Re-running onboarding is an operator action.
    """
    if current_user.onboarding_completed_at is None:
        # AWARE UTC, never a bare utcnow(): the column is TIMESTAMPTZ and the
        # model declares it `DateTime(timezone=True)` to say so. A naive value
        # here would serialize WITHOUT an offset on the write path while every
        # later read carries one — and a browser parses the offset-less form as
        # LOCAL time, 3h off in Israel. Caught by test_complete_is_idempotent,
        # which compares the write-path and read-path values.
        current_user.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()

    return build_user_response(current_user)


# =============================================================================
# [028] The onboarding "מתי המבחן הבא שלך?" step
# =============================================================================
#
# WHY THIS IS ONE ENDPOINT AND NOT TWO. §8 asks for a persistent
# «קבעי שיחה עם נועם» link in the app shell that posts "the same field" to the
# same URL. So this endpoint serves two callers with different intents — the
# onboarding step, and a booking click months later — and the difference is
# expressed by WHICH FIELDS ARE PRESENT, not by a mode flag.
#
# That is why every field is optional and why presence is read from
# `model_fields_set` rather than from None. A booking click that omitted
# `next_exam_date` while the handler treated "absent" as "null" would erase a
# date she gave, and — worse — re-stamp `next_exam_answered_at`, silently
# pushing her 14-day re-ask (§7) out by however long she took to click. The
# absent/null distinction is load-bearing in both directions:
#   * `next_exam_date` ABSENT  -> untouched, and answered_at NOT re-stamped.
#   * `next_exam_date` null    -> ONB-2, «עוד לא יודעת»: a real answer, stored
#                                 as a null date WITH answered_at stamped.

# ONB-1 (MinimalValidation). Two bounds, both about a date that cannot mean
# what it says, and nothing else:
#   * 7 days back, not zero: she may be answering on Sunday about the exam she
#     set for last Thursday, and a timezone is not worth an error message
#     either (see _today_utc).
#   * 18 months forward: past that it is a typo — a mistyped year is the one
#     wrong date a teacher actually produces, and it would sit in the queue
#     forever without ever coming due.
EXAM_DATE_MIN_DAYS_BACK = 7
EXAM_DATE_MAX_MONTHS_AHEAD = 18


def _today_utc() -> date:
    """The reference day for the window above.

    UTC, deliberately, and not Asia/Jerusalem: `zoneinfo` needs a tzdata source
    this project does not ship (no `tzdata` in requirements, and Windows has no
    system copy — the dev box raises ZoneInfoNotFoundError), so a local "today"
    would work in production and fail on a laptop. The window's own slack makes
    the question moot: Israel is UTC+2/+3, so the worst case moves a boundary
    by one day inside a 7-day / 18-month tolerance.
    """
    return datetime.now(timezone.utc).date()


def _plus_months(anchor: date, months: int) -> date:
    """Calendar months, clamped to the target month's last day. Hand-rolled
    because `dateutil` is not a dependency, and 548 days is not 18 months."""
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor.day, last_day))


class OnboardingExamRequest(BaseModel):
    """Every field optional; presence is what carries meaning (see above).

    `phone` has NO format validation, by design (§5): it is stored exactly as
    she typed it and normalised to E.164 only on read, when a wa.me link is
    built. Rejecting a teacher's phone format mid-onboarding is hostility
    disguised as rigour — and there is no format we could enforce that is
    right for every way an Israeli number is written.
    """
    next_exam_date: Optional[date] = None
    phone: Optional[str] = Field(None, max_length=64)
    whatsapp_opt_in: Optional[bool] = None
    guided_session_requested: Optional[bool] = None


class OnboardingExamResponse(BaseModel):
    """The persisted fields, read back off the row after the commit.

    Deliberately NOT `UserResponse`: these columns are not part of the profile
    shape, and widening the one profile response for them would put a second
    hand-maintained mirror in front of `build_user_response` — the truncation
    risk CLAUDE.md §6 documents.

    No `show_booking`: the 14-day threshold is a single frontend constant and
    the block renders reactively on date change, BEFORE submit. A server field
    could only ever answer about the last saved date, one step behind what she
    is looking at.
    """
    next_exam_date: Optional[date]
    next_exam_answered_at: Optional[datetime]
    phone: Optional[str]
    whatsapp_opt_in: bool
    guided_session_requested_at: Optional[datetime]


@router.patch("/me/onboarding-exam", response_model=OnboardingExamResponse)
async def update_onboarding_exam(
    body: OnboardingExamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingExamResponse:
    """Record when her next exam is — and, optionally, how to reach her.

    Ownership per §9: the row written is `current_user`'s, and there is no user
    id on this request to supply. Idempotent and re-callable; she may change
    the date as often as she likes.
    """
    sent = body.model_fields_set
    now = datetime.now(timezone.utc)

    # -- validate BEFORE mutating anything ---------------------------------
    if "next_exam_date" in sent and body.next_exam_date is not None:
        today = _today_utc()
        if body.next_exam_date < today - timedelta(days=EXAM_DATE_MIN_DAYS_BACK):
            raise HTTPException(
                status_code=422,
                detail="התאריך שנבחר כבר עבר. אפשר לבחור תאריך עתידי.",
            )
        if body.next_exam_date > _plus_months(today, EXAM_DATE_MAX_MONTHS_AHEAD):
            raise HTTPException(
                status_code=422,
                detail="התאריך רחוק מדי. אפשר לבחור תאריך בשנה וחצי הקרובה.",
            )

    # The phone AFTER this request, which is what the consent guard must test —
    # she may be ticking the box on a number she gave last week.
    new_phone = current_user.phone
    if "phone" in sent:
        stripped = (body.phone or "").strip()
        # Trimming is not format validation; an empty string is an erasure.
        new_phone = stripped or None

    new_opt_in = bool(current_user.whatsapp_opt_in)
    if "whatsapp_opt_in" in sent and body.whatsapp_opt_in is not None:
        new_opt_in = body.whatsapp_opt_in

    if new_opt_in and not new_phone:
        # Consent to a message we have no way to send. Refusing is the honest
        # answer: storing the tick alone would leave a row that CLAIMS consent
        # for a number that arrives later and was never actually consented to.
        raise HTTPException(
            status_code=422,
            detail="כדי לקבל הודעות בוואטסאפ צריך למלא מספר טלפון.",
        )

    # -- write -------------------------------------------------------------
    current_user.phone = new_phone
    current_user.whatsapp_opt_in = new_opt_in

    if "next_exam_date" in sent:
        current_user.next_exam_date = body.next_exam_date
        # ONB-2: stamped for BOTH a date and «עוד לא יודעת». It is what tells
        # "answered, unknown" apart from "never asked", and re-answering is
        # what makes her eligible for the §7 digest again.
        current_user.next_exam_answered_at = now

    if (
        "guided_session_requested" in sent
        and body.guided_session_requested
        and current_user.guided_session_requested_at is None
    ):
        # FIRST occurrence only (§5). Re-stamping would turn "when she first
        # asked for help" into "when she last clicked a link", and the first is
        # the fact worth having.
        current_user.guided_session_requested_at = now

    await db.commit()

    # Read the persisted values off the row BEFORE the session closes: after
    # `db.close()` these attributes are expired and touching one would issue a
    # lazy refresh on a closed session (MissingGreenlet under asyncio).
    response = OnboardingExamResponse(
        next_exam_date=current_user.next_exam_date,
        next_exam_answered_at=current_user.next_exam_answered_at,
        phone=current_user.phone,
        whatsapp_opt_in=bool(current_user.whatsapp_opt_in),
        guided_session_requested_at=current_user.guided_session_requested_at,
    )

    # The sheet write is OFF this request (§5 / ONB-1). Enqueued after the
    # commit so the handler reads committed state, and after `db.close()` so
    # the enqueue round-trip does not hold a pooled connection idle-in-
    # transaction (the 2026-08-07 rule). Best-effort: a queue failure is not
    # her problem (ONB-8).
    await db.close()
    await enqueue_onboarding_sheet_task_or_log(current_user.id)

    return response


# =============================================================================
# [028] Cloud Tasks target for the sheet projection
# =============================================================================

internal_router = APIRouter(
    prefix="/internal/onboarding-sheet", tags=["internal"],
)


@internal_router.post("/{user_id}/upsert", include_in_schema=False)
async def run_onboarding_sheet_upsert(user_id: UUID, request: Request) -> dict:
    """Project one teacher into the outreach sheet.

    Always 200 on auth success, even on a failed write: a non-2xx would make
    Cloud Tasks redeliver work that has nothing to heal — the DB already holds
    the answer, `upsert_user_row` never raises (ONB-8), and the repair is the
    reconcile command.
    """
    reason = verify_task_request(request)
    if reason is not None:
        logger.warning("internal_onboarding_sheet_rejected user_id=%s reason=%s",
                       user_id, reason)
        raise HTTPException(status_code=403, detail="Forbidden")

    outcome = await upsert_user_row(user_id)
    return {"status": outcome or "skipped"}
