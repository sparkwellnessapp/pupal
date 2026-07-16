"""
Shared FastAPI dependencies.

Canonical pattern for S2–S9: every endpoint that touches a user-owned resource
calls get_owned_or_404 to fetch-and-verify ownership atomically.

Security rule: a resource not owned by the authenticated user is indistinguishable
from a non-existent resource — always 404, never 403.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_owned_or_404(
    db: AsyncSession,
    model,
    obj_id: UUID,
    user_id: UUID,
):
    """Fetch a row by id that the authenticated user owns, else raise 404."""
    result = await db.execute(
        select(model).where(model.id == obj_id, model.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
