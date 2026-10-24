"""
The teacher's phone handoff (D2, ruling OD-5).

On her computer «צילום מבחנים» shows a QR. It carries a one-time handoff token
(10 minutes); the phone exchanges it — once — for a capture session (12 hours)
scoped to THIS batch. The session grants the teacher capture page for that
batch and nothing else: it is not a login, `get_current_user` cannot read it,
and every other route rejects it. Both tokens are opaque and random; only
their sha256 is stored (the auth_nonces pattern), and the one-time consume is
ONE atomic UPDATE whose conditions are in its WHERE clause — a read-then-write
is the race a single-use token exists to prevent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models.capture import CaptureHandoff
from . import tokens
from .actors import CaptureError, TeacherActor


async def issue_handoff(db: AsyncSession, *, user_id: UUID, batch_id: UUID) -> tuple[str, datetime]:
    token = tokens.random_token()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.capture_handoff_ttl_minutes)
    db.add(CaptureHandoff(user_id=user_id, batch_id=batch_id, handoff_hash=tokens.sha256(token),
                          handoff_expires_at=expires))
    await db.flush()
    return token, expires


async def exchange(db: AsyncSession, handoff_token: str) -> tuple[str, UUID, datetime]:
    session = tokens.random_token()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=settings.capture_session_ttl_hours)
    row = (await db.execute(
        update(CaptureHandoff)
        .where(CaptureHandoff.handoff_hash == tokens.sha256(handoff_token),
               CaptureHandoff.consumed_at.is_(None),
               CaptureHandoff.revoked_at.is_(None),
               CaptureHandoff.handoff_expires_at > now)
        .values(consumed_at=now, session_hash=tokens.sha256(session), session_expires_at=expires)
        .returning(CaptureHandoff.batch_id)
    )).scalar_one_or_none()
    if row is None:
        raise CaptureError(410, "handoff_invalid",
                           "הקוד כבר שומש או שפג תוקפו — סרקי שוב את הקוד מהמחשב")
    return session, row, expires


async def session_actor(db: AsyncSession, session_token: str, batch_id: UUID) -> Optional[TeacherActor]:
    """The capture session's actor, ONLY for the batch it was issued for."""
    now = datetime.now(timezone.utc)
    row = (await db.execute(
        select(CaptureHandoff.user_id, CaptureHandoff.batch_id).where(
            CaptureHandoff.session_hash == tokens.sha256(session_token),
            CaptureHandoff.revoked_at.is_(None),
            CaptureHandoff.session_expires_at > now)
    )).one_or_none()
    if row is None or row.batch_id != batch_id:
        return None
    return TeacherActor(user_id=row.user_id, batch_id=batch_id)
