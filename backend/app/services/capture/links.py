"""
Capture links (§6.2, rulings R5, R6, OD-4).

One link per batch, and creating one requires a class (R6): a batch with no
class gets one now — picked, or created by name — and that becomes the
batch's class, so the link's class IS `grading_batches.class_id` (no copy).

The window is the exam date's Asia/Jerusalem calendar day (R5). The state is
COMPUTED, never stored:

  not_yet_open   today < exam_date
  open           today == exam_date and not closed early
  closed         closed_at set, or today > exam_date

She may close early, and reopen only on the exam date itself.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models.capture import CaptureLink, CaptureSubmission
from ...models.classroom import Class
from ...models.grading import GradingBatch
from .. import classroom as classroom_service
from . import tokens
from .actors import CaptureError

TZ = ZoneInfo("Asia/Jerusalem")


def today_il(now: Optional[datetime] = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(TZ).date()


def link_state(link: CaptureLink, today: date) -> str:
    if link.closed_at is not None or today > link.exam_date:
        return "closed"
    if today < link.exam_date:
        return "not_yet_open"
    return "open"


def _secret() -> str:
    s = settings.capture_token_secret
    if s is None or not s.get_secret_value():
        raise CaptureError(503, "capture_not_configured", "הצילום אינו זמין כרגע")
    return s.get_secret_value()


def link_token(link: CaptureLink) -> str:
    return tokens.link_token(_secret(), link.id, link.token_generation)


def link_url(link: CaptureLink) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/s/{link_token(link)}"


async def get_link(db: AsyncSession, batch_id: UUID) -> Optional[CaptureLink]:
    return (await db.execute(
        select(CaptureLink).where(CaptureLink.batch_id == batch_id))).scalar_one_or_none()


async def resolve_token(db: AsyncSession, token: str) -> Optional[CaptureLink]:
    """The link a student's token names, or None (an unknown token is a 404,
    the same for every reason — a probe learns nothing)."""
    if not token or len(token) > 64:
        return None
    return (await db.execute(
        select(CaptureLink).where(CaptureLink.token_hash == tokens.sha256(token))
    )).scalar_one_or_none()


async def create_link(db: AsyncSession, *, batch: GradingBatch, exam_date: date,
                      class_id: Optional[UUID], new_class_name: Optional[str]) -> CaptureLink:
    if await get_link(db, batch.id) is not None:
        raise CaptureError(409, "link_exists", "כבר קיים קישור לקבוצה הזאת")
    if batch.class_id is None:
        name = (new_class_name or "").strip()
        if (class_id is None) == (not name):
            raise CaptureError(422, "class_required", "יש לבחור כיתה או ליצור כיתה חדשה")
        if class_id is not None:
            owned = await db.scalar(select(Class.id).where(
                Class.id == class_id, Class.user_id == batch.user_id))
            if owned is None:
                raise CaptureError(404, "class_not_found", "הכיתה לא נמצאה")
            batch.class_id = class_id
        else:
            try:
                created = await classroom_service.create_class(db, user_id=batch.user_id, name=name)
            except classroom_service.NameTaken:
                raise CaptureError(409, "class_name_taken",
                                   "כבר קיימת כיתה בשם הזה — בחרי אותה מהרשימה") from None
            batch.class_id = created.id
    # The id is minted HERE because it is inside the token: the row is inserted
    # with its real hash, never a placeholder two concurrent creates would share.
    link = CaptureLink(id=uuid4(), batch_id=batch.id, user_id=batch.user_id,
                       exam_date=exam_date, token_generation=1)
    link.token_hash = tokens.sha256(link_token(link))
    db.add(link)
    await db.flush()
    return link


async def rotate_token(db: AsyncSession, link: CaptureLink) -> None:
    """The emergency lever: the old URL stops working at once."""
    link.token_generation += 1
    link.token_hash = tokens.sha256(link_token(link))
    await db.flush()


async def close_link(db: AsyncSession, link: CaptureLink) -> None:
    if link.closed_at is None:
        link.closed_at = datetime.now(timezone.utc)
        await db.flush()


async def reopen_link(db: AsyncSession, link: CaptureLink) -> None:
    if today_il() != link.exam_date:
        raise CaptureError(409, "reopen_not_today", "ניתן לפתוח מחדש רק ביום המבחן")
    link.closed_at = None
    await db.flush()


async def change_exam_date(db: AsyncSession, link: CaptureLink, exam_date: date) -> None:
    has_any = await db.scalar(select(func.count()).select_from(CaptureSubmission).where(
        CaptureSubmission.link_id == link.id))
    if has_any:
        raise CaptureError(409, "link_in_use", "לא ניתן לשנות את התאריך אחרי שהתחילו הגשות")
    link.exam_date = exam_date
    await db.flush()
