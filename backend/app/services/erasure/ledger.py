"""
The failure ledger (migration 033; M-B2, PRV-3 ObjectsNeverSilentlyKept).

Every object delete that fails after the rows committed is recorded here AND
logged at ERROR — never swallowed. `retry_purge_failures` re-attempts every row
and clears the ones that now succeed. Ids and object paths only (OD-B4).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from app.database import AsyncSessionLocal

from .storage import GuardedStorage

logger = logging.getLogger(__name__)

_ERROR_MAX = 500


@dataclass(frozen=True)
class ObjectFailure:
    bucket: str
    object_name: str
    error: str


async def record_failures(user_id: UUID, student_id: UUID, failures: list[ObjectFailure]) -> None:
    if not failures:
        return
    async with AsyncSessionLocal() as db:
        for f in failures:
            await db.execute(text(
                "INSERT INTO purge_failures (user_id, student_id, bucket, object_name, error) "
                "VALUES (:u, :s, :b, :o, :e) "
                "ON CONFLICT (bucket, object_name) DO UPDATE SET "
                "  attempts = purge_failures.attempts + 1, error = EXCLUDED.error, "
                "  last_attempt_at = now()"),
                {"u": user_id, "s": student_id, "b": f.bucket, "o": f.object_name,
                 "e": f.error[:_ERROR_MAX]})
        await db.commit()


def delete_objects(storage: GuardedStorage, objects) -> tuple[list[tuple[str, str]], list[ObjectFailure]]:
    """Synchronous (M-B1), in a stable order; one failure never stops the rest."""
    deleted, failed = [], []
    for bucket, name in sorted(objects):
        try:
            storage.delete_object(bucket, name)
            deleted.append((bucket, name))
        except Exception as exc:                       # recorded, never swallowed (PRV-3)
            failed.append(ObjectFailure(bucket, name, f"{type(exc).__name__}: {exc}"))
    return deleted, failed


async def retry_purge_failures(*, storage: GuardedStorage) -> int:
    """Re-attempt every ledger row; clear the ones that succeed. Returns how
    many were cleared. The management command wraps this."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT id, student_id, bucket, object_name FROM purge_failures ORDER BY created_at"))).all()
    cleared = 0
    for row_id, student_id, bucket, name in rows:
        try:
            await asyncio.to_thread(storage.delete_object, bucket, name)
        except Exception as exc:
            logger.error("purge_retry_failed student_id=%s bucket=%s object=%s error=%s",
                         student_id, bucket, name, type(exc).__name__)
            async with AsyncSessionLocal() as db:
                await db.execute(text(
                    "UPDATE purge_failures SET attempts = attempts + 1, last_attempt_at = now(), "
                    "error = :e WHERE id = :id"),
                    {"id": row_id, "e": f"{type(exc).__name__}: {exc}"[:_ERROR_MAX]})
                await db.commit()
            continue
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM purge_failures WHERE id = :id"), {"id": row_id})
            await db.commit()
        cleared += 1
        logger.info("purge_retry_cleared student_id=%s bucket=%s object=%s", student_id, bucket, name)
    return cleared
