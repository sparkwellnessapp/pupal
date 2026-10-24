"""
In-house scanning — the TEACHER's endpoints (PR_in_house_scanning.md §6.2,
§6.4, §6.9–§6.11).

Two kinds of auth, deliberately separate:

  * The link, the handoff and the submissions panel are normal teacher
    endpoints: `get_current_user` + `get_owned_or_404` on the batch (§9;
    cross-tenant → 404).
  * The CAPTURE PAGE (`/capture/teacher/{batch_id}/…`) also accepts a capture
    session — `Authorization: CaptureSession <token>`, obtained on the phone by
    exchanging the desktop's one-time QR (D2/OD-5) — and only for the batch it
    was issued for. Every other route rejects it: it is not a Bearer token,
    so `get_current_user` never even sees it.

Every route answers 404 while `capture_enabled` is off.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_owned_or_404
from ...config import settings
from ...database import get_db
from ...models.classroom import Class
from ...models.grading import GradingBatch
from ...models.student import Student
from ...models.user import User
from ...schemas.capture import (
    CaptureHandoffResponse, CaptureLinkCreateRequest, CaptureLinkPatchRequest,
    CaptureLinkResponse, CaptureSubmissionsResponse, HandoffExchangeRequest,
    HandoffExchangeResponse, NameSuggestResponse, ResolveConflictRequest, ResolvePendingRequest, RosterResponse,
    RosterStudent, StudentAssignRequest, SubmissionView, TeacherCaptureState,
)
from ...services.capture import handoff as handoff_svc
from ...services.capture import links as links_svc
from ...services.capture import name_suggest as name_suggest_svc
from ...services.capture import submissions as svc
from ...services.capture.actors import CaptureError, TeacherActor
from .auth import get_current_user, get_current_user_optional
from .capture_pages import add_page_routes


def require_capture_enabled() -> None:
    if not settings.capture_enabled:
        raise HTTPException(status_code=404, detail="Not Found")


router = APIRouter(prefix="/api/v0", tags=["capture"],
                   dependencies=[Depends(require_capture_enabled)])
capture_page_router = APIRouter(prefix="/api/v0/capture/teacher/{batch_id}",
                                tags=["capture"],
                                dependencies=[Depends(require_capture_enabled)])


async def teacher_actor(batch_id: UUID, request: Request, db: AsyncSession = Depends(get_db),
                        user: Optional[User] = Depends(get_current_user_optional)) -> TeacherActor:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "capturesession" and token.strip():
        actor = await handoff_svc.session_actor(db, token.strip(), batch_id)
        if actor is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return actor
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    await get_owned_or_404(db, GradingBatch, batch_id, user.id)
    return TeacherActor(user_id=user.id, batch_id=batch_id)


# ---------------------------------------------------------------------------
# the link (§6.2)
# ---------------------------------------------------------------------------

async def _link_response(db: AsyncSession, batch: GradingBatch, link) -> CaptureLinkResponse:
    class_name = await db.scalar(select(Class.name).where(Class.id == batch.class_id))
    return CaptureLinkResponse(
        link_id=link.id, batch_id=batch.id, class_id=batch.class_id, class_name=class_name,
        exam_date=link.exam_date, state=links_svc.link_state(link, links_svc.today_il()),
        closed_at=link.closed_at.isoformat() if link.closed_at else None,
        url=links_svc.link_url(link))


async def _owned_link(db, batch_id: UUID, user: User):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, user.id)
    link = await links_svc.get_link(db, batch.id)
    if link is None:
        raise HTTPException(status_code=404, detail="אין קישור לקבוצה הזאת")
    return batch, link


@router.get("/batches/{batch_id}/capture-link", response_model=CaptureLinkResponse)
async def get_capture_link(batch_id: UUID, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    batch, link = await _owned_link(db, batch_id, current_user)
    return await _link_response(db, batch, link)


@router.post("/batches/{batch_id}/capture-link", response_model=CaptureLinkResponse,
             status_code=201)
async def create_capture_link(batch_id: UUID, body: CaptureLinkCreateRequest,
                              db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    existing = await links_svc.get_link(db, batch.id)
    if existing is not None:
        raise CaptureError(409, "link_exists", "כבר קיים קישור לקבוצה הזאת",
                           {"link": (await _link_response(db, batch, existing)).model_dump(mode="json")})
    try:
        link = await links_svc.create_link(db, batch=batch, exam_date=body.exam_date,
                                           class_id=body.class_id,
                                           new_class_name=body.new_class_name)
        await db.commit()
    except IntegrityError:                     # a concurrent create for the same batch
        await db.rollback()
        raise CaptureError(409, "link_exists", "כבר קיים קישור לקבוצה הזאת") from None
    return await _link_response(db, batch, link)


@router.patch("/batches/{batch_id}/capture-link", response_model=CaptureLinkResponse)
async def patch_capture_link(batch_id: UUID, body: CaptureLinkPatchRequest,
                             db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    batch, link = await _owned_link(db, batch_id, current_user)
    await links_svc.change_exam_date(db, link, body.exam_date)
    await db.commit()
    return await _link_response(db, batch, link)


@router.post("/batches/{batch_id}/capture-link/close", response_model=CaptureLinkResponse)
async def close_capture_link(batch_id: UUID, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    batch, link = await _owned_link(db, batch_id, current_user)
    await links_svc.close_link(db, link)
    await db.commit()
    return await _link_response(db, batch, link)


@router.post("/batches/{batch_id}/capture-link/reopen", response_model=CaptureLinkResponse)
async def reopen_capture_link(batch_id: UUID, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    batch, link = await _owned_link(db, batch_id, current_user)
    await links_svc.reopen_link(db, link)
    await db.commit()
    return await _link_response(db, batch, link)


@router.post("/batches/{batch_id}/capture-link/rotate-token", response_model=CaptureLinkResponse)
async def rotate_capture_link(batch_id: UUID, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    batch, link = await _owned_link(db, batch_id, current_user)
    await links_svc.rotate_token(db, link)
    await db.commit()
    return await _link_response(db, batch, link)


# ---------------------------------------------------------------------------
# the phone handoff (§6.4)
# ---------------------------------------------------------------------------

@router.post("/batches/{batch_id}/capture-handoff", response_model=CaptureHandoffResponse)
async def create_capture_handoff(batch_id: UUID, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_user)):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    token, expires = await handoff_svc.issue_handoff(db, user_id=current_user.id, batch_id=batch.id)
    await db.commit()
    url = f"{settings.frontend_base_url.rstrip('/')}/capture/{batch.id}?handoff={token}"
    return CaptureHandoffResponse(handoff_url=url, expires_at=expires.isoformat())


@router.post("/capture/handoff/exchange", response_model=HandoffExchangeResponse)
async def exchange_capture_handoff(body: HandoffExchangeRequest,
                                   db: AsyncSession = Depends(get_db)):
    """Public — the one-time token IS the credential (single use, 10 minutes)."""
    session, batch_id, expires = await handoff_svc.exchange(db, body.handoff_token)
    await db.commit()
    return HandoffExchangeResponse(capture_session=session, batch_id=batch_id,
                                   expires_at=expires.isoformat())


# ---------------------------------------------------------------------------
# the submissions panel (§6.11)
# ---------------------------------------------------------------------------

@router.get("/batches/{batch_id}/capture-submissions", response_model=CaptureSubmissionsResponse)
async def list_capture_submissions(batch_id: UUID, db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_user)):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    return await svc.batch_rows(db, batch)


@router.post("/batches/{batch_id}/capture-submissions/{submission_id}/resolve-pending",
             response_model=CaptureSubmissionsResponse)
async def resolve_pending(batch_id: UUID, submission_id: UUID, body: ResolvePendingRequest,
                          db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    await svc.resolve_pending(db, TeacherActor(current_user.id, batch.id), submission_id,
                              student_id=body.student_id, approve_new=body.approve_new)
    await db.commit()
    return await svc.batch_rows(db, batch)


@router.post("/batches/{batch_id}/capture-submissions/{submission_id}/resolve-conflict",
             response_model=CaptureSubmissionsResponse)
async def resolve_conflict(batch_id: UUID, submission_id: UUID, body: ResolveConflictRequest,
                           db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    await svc.resolve_conflict(db, TeacherActor(current_user.id, batch.id), submission_id,
                               action=body.action, student_id=body.student_id)
    await db.commit()
    return await svc.batch_rows(db, batch)


# ---------------------------------------------------------------------------
# the teacher capture page (§6.10, §8.3) — her session OR a capture session
# ---------------------------------------------------------------------------

@capture_page_router.get("", response_model=TeacherCaptureState)
async def capture_state(actor: TeacherActor = Depends(teacher_actor),
                        db: AsyncSession = Depends(get_db)):
    batch = await db.get(GradingBatch, actor.batch_id)
    class_name = await db.scalar(select(Class.name).where(Class.id == batch.class_id)) \
        if batch.class_id else None
    views = [await svc.submission_view(db, s) for s in await svc.teacher_drafts(db, actor)]
    # Resume what has CONTENT (pages or a student) and at most the newest
    # empty group — reused rather than piling up a chip per abandoned visit.
    filled = [v for v in views if v.pages or v.student is not None]
    empty = [v for v in views if not (v.pages or v.student is not None)]
    drafts = filled + empty[-1:]
    return TeacherCaptureState(batch_id=batch.id, batch_name=batch.name, class_name=class_name,
                               saved_count=await svc.saved_count(db, batch.id), drafts=drafts)


@capture_page_router.get("/students", response_model=RosterResponse)
async def capture_roster(actor: TeacherActor = Depends(teacher_actor),
                         db: AsyncSession = Depends(get_db)):
    """The picker's list under a capture session (which cannot call the
    classroom API): ALL her students, as the class-less batch roster is."""
    rows = (await db.execute(select(Student.id, Student.full_name)
                             .where(Student.user_id == actor.user_id)
                             .order_by(Student.full_name))).all()
    return RosterResponse(students=[RosterStudent(student_id=r[0], display_name=r[1]) for r in rows])


@capture_page_router.post("/submissions", response_model=SubmissionView, status_code=201)
async def create_teacher_submission(actor: TeacherActor = Depends(teacher_actor),
                                    db: AsyncSession = Depends(get_db)):
    sub = await svc.create_teacher_submission(db, actor)
    await db.commit()
    return await svc.submission_view(db, sub)


@capture_page_router.put("/submissions/{submission_id}/student", response_model=SubmissionView)
async def assign_student(submission_id: UUID, body: StudentAssignRequest,
                         actor: TeacherActor = Depends(teacher_actor),
                         db: AsyncSession = Depends(get_db)):
    sub = await svc.assign_student(db, actor, submission_id, student_id=body.student_id,
                                   create_name=body.create.name if body.create else None,
                                   replace_existing=body.replace_existing)
    await db.commit()
    return await svc.submission_view(db, sub)


@capture_page_router.post("/submissions/{submission_id}/name-suggest",
                          response_model=NameSuggestResponse)
async def name_suggest(submission_id: UUID, actor: TeacherActor = Depends(teacher_actor),
                       db: AsyncSession = Depends(get_db)):
    """§6.9 — a pre-fill for her picker, never an assignment (SCN-10/12)."""
    return await name_suggest_svc.suggest(db, actor, submission_id)


add_page_routes(capture_page_router, teacher_actor, view_model=SubmissionView,
                view=svc.submission_view)
