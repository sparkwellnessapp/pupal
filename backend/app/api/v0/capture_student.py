"""
In-house scanning — the STUDENT link (public; PR_in_house_scanning.md §6.3).

Base: /api/v0/capture/s/{token}. The token resolves the link (unknown → a
generic 404, the same for every reason). SCN-7 is the whole contract: a link
token plus a device secret grants reading the link's state, identifying ONE
name, and creating / editing / saving the device's OWN submission — within
this batch, on its exam date, while the link is open. Nothing else.

A known link in a non-open state answers its state on GET, and 410 (with the
state) to every mutation.

Referrer-Policy: no-referrer and Cache-Control: no-store ride every response
on this prefix (the middleware in main.py), errors included.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.capture import CaptureLink
from ...models.classroom import Class
from ...models.grading import GradingBatch
from ...schemas.capture import (
    ExamLabel, IdentifyMatch, IdentifyRequest, IdentifyResponse, StudentLinkInfo,
    StudentSubmissionCreateRequest, StudentSubmissionCreateResponse, StudentSubmissionView,
)
from ...services.capture import links as links_svc
from ...services.capture import submissions as svc
from ...services.capture import tokens
from ...services.capture.actors import CaptureError, StudentActor
from ...services.capture.naming import identify
from ...utils.rate_limiter import InMemoryRateLimiter
from .capture_pages import add_page_routes
from .capture_teacher import require_capture_enabled

STUDENT_PREFIX = "/api/v0/capture/s/"

router = APIRouter(prefix="/api/v0/capture/s/{token}", tags=["capture-student"],
                   dependencies=[Depends(require_capture_enabled)])

# Best-effort, per instance (D12): the DB caps (150 submissions per link, 20
# pages per submission) are the real guarantee. These are an ANTI-FLOOD
# ceiling, not a per-person limit, and the number is set for the actual room:
# a class of 30–40 students submits from ONE school WiFi address in the same
# few minutes, typos and «לא, זה לא אני» included. The spec's 10/min per
# token+IP would lock most of the class out of identify; 120/min stops a
# script and never a class.
_identify_limiter = InMemoryRateLimiter(max_requests=120, window_seconds=60)
_create_limiter = InMemoryRateLimiter(max_requests=120, window_seconds=60)


def _client_ip(request: Request) -> str:
    """The address Google's front end saw. Cloud Run APPENDS it to
    X-Forwarded-For, so the LAST hop is the real one — the first is whatever
    the client chose to send, and keying on it let anyone mint a fresh
    rate-limit bucket per request."""
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    return hops[-1] if hops else (request.client.host if request.client else "?")


def _limit(limiter: InMemoryRateLimiter, token: str, request: Request) -> None:
    if not limiter.check(f"{tokens.sha256(token).hex()[:16]}:{_client_ip(request)}"):
        raise CaptureError(429, "rate_limited", "יותר מדי ניסיונות — חכו דקה ונסו שוב")


async def _link(token: str, db: AsyncSession) -> CaptureLink:
    link = await links_svc.resolve_token(db, token)
    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return link


async def student_actor(token: str, db: AsyncSession = Depends(get_db),
                        x_capture_device: Optional[str] = Header(None)) -> StudentActor:
    """For MUTATIONS: the link must be open (410 otherwise)."""
    link = await _link(token, db)
    state = links_svc.link_state(link, links_svc.today_il())
    if state != "open":
        raise CaptureError(410, f"link_{state}", "", {"state": state})
    return StudentActor(link_id=link.id, batch_id=link.batch_id, user_id=link.user_id,
                        device_hash=tokens.sha256(x_capture_device) if x_capture_device else None)


@router.get("", response_model=StudentLinkInfo)
async def link_info(token: str, db: AsyncSession = Depends(get_db),
                    x_capture_device: Optional[str] = Header(None)):
    link = await _link(token, db)
    batch = await db.get(GradingBatch, link.batch_id)
    class_name = await db.scalar(select(Class.name).where(Class.id == batch.class_id))
    state = links_svc.link_state(link, links_svc.today_il())
    own = None
    if state == "open" and x_capture_device:
        sub = await svc.own_submission(db, link, tokens.sha256(x_capture_device))
        own = await svc.student_submission_view(db, sub) if sub else None
    return StudentLinkInfo(state=state, own_submission=own, exam_label=ExamLabel(
        batch_name=batch.name, class_name=class_name, exam_date=link.exam_date))


@router.post("/identify", response_model=IdentifyResponse)
async def identify_name(token: str, body: IdentifyRequest, request: Request,
                        actor: StudentActor = Depends(student_actor),
                        db: AsyncSession = Depends(get_db)):
    """SCN-9: the single exact match's display name, or null. Never an id,
    never another name, never a count."""
    _limit(_identify_limiter, token, request)
    batch = await db.get(GradingBatch, actor.batch_id)
    match = await identify(db, class_id=batch.class_id, user_id=actor.user_id, name=body.name)
    return IdentifyResponse(match=IdentifyMatch(display_name=match.full_name) if match else None)


@router.post("/submissions", response_model=StudentSubmissionCreateResponse, status_code=201)
async def create_submission(token: str, body: StudentSubmissionCreateRequest, request: Request,
                            actor: StudentActor = Depends(student_actor),
                            db: AsyncSession = Depends(get_db)):
    _limit(_create_limiter, token, request)
    link = await db.get(CaptureLink, actor.link_id)
    sub, secret = await svc.create_student_submission(db, link=link, name=body.name,
                                                      confirm_match=body.confirm_match)
    await db.commit()
    return StudentSubmissionCreateResponse(submission_id=sub.id, device_secret=secret)


add_page_routes(router, student_actor, view_model=StudentSubmissionView,
                view=svc.student_submission_view)
