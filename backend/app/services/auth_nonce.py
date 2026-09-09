"""Single-use nonces for Sign in with Google (migration 024).

A Google `credential` is a bearer token: whoever holds it can present it until
it expires (~1 hour). The nonce is what makes ours single-use — we mint it, GIS
embeds it in the token Google signs, and we accept a token only if its nonce is
one we issued and have not already spent.

WHY A ROW AND NOT AN HMAC. A stateless signed nonce proves *we minted it* but
cannot prove *it has not been used*, which is the entire property being bought.
Consumption is a fact about the past; facts about the past need storage.

Only the SHA-256 of the nonce is stored. The table can be read by anyone with
database access and still yields nothing that can be replayed.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.auth_verification import AuthNonce


logger = logging.getLogger(__name__)

#: Long enough to be unguessable, short enough to travel in a URL/JSON body.
NONCE_BYTES = 32

#: The window between "the page asked for a nonce" and "the teacher clicked the
#: Google button". Generous for a human, far too short to farm.
NONCE_TTL = timedelta(minutes=5)


def _hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def _now() -> datetime:
    """Aware UTC. Every timestamp column here is TIMESTAMPTZ, so a naive value
    would either fail the bind or compare wrongly against a stored one."""
    return datetime.now(timezone.utc)


async def issue_nonce(db: AsyncSession) -> str:
    """Mint a nonce, store its hash, and return the nonce itself — the only
    moment it exists outside the caller's browser.

    Does not commit: the caller owns the transaction.
    """
    nonce = secrets.token_urlsafe(NONCE_BYTES)
    db.add(AuthNonce(nonce_hash=_hash(nonce), expires_at=_now() + NONCE_TTL))
    await db.flush()
    return nonce


async def consume_nonce(db: AsyncSession, nonce: Optional[str]) -> bool:
    """Spend a nonce. True only if it was ours, unspent, and unexpired.

    The check and the spend are ONE atomic UPDATE with the conditions in its
    WHERE clause, not a read followed by a write. A read-then-write here is a
    race: two requests replaying the same stolen credential could both read
    "unconsumed" before either wrote, and both would be admitted — which is
    precisely the attack this function exists to stop. `rowcount == 1` means
    this call is the one that spent it.

    Does not commit: the caller owns the transaction, so a nonce is spent only
    if the sign-in it authorized also lands.
    """
    if not nonce:
        return False

    result = await db.execute(
        update(AuthNonce)
        .where(
            AuthNonce.nonce_hash == _hash(nonce),
            AuthNonce.consumed_at.is_(None),
            AuthNonce.expires_at > _now(),
        )
        .values(consumed_at=_now())
    )
    return result.rowcount == 1


async def purge_expired_nonces(db: AsyncSession) -> int:
    """Delete nonces that can no longer be spent. Returns how many went.

    Housekeeping only — an expired nonce is already refused by `consume_nonce`,
    so this never changes behaviour, it only stops an append-only table from
    growing forever. Safe to run at any time, from anywhere.
    """
    result = await db.execute(delete(AuthNonce).where(AuthNonce.expires_at <= _now()))
    return result.rowcount or 0
