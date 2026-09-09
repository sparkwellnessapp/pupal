"""Email verification — the stateful half (migration 024).

Owns the `email_verification_codes` row lifecycle. The POLICY (what is expired,
what may be attempted, how long until a resend is allowed) lives in the pure
`verification_codes` module; this module only carries it out against a database.

ONE ACTIVE ROW PER USER, and it is reused rather than replaced. That is not
tidiness — it is what makes the attempt budget hold. If a resend inserted a new
row, an attacker could refresh their way to unlimited guesses; here a resend
mints a new secret into the SAME row, and `resend_count` bounds how many times
that can happen. Worst case is MAX_RESENDS × MAX_ATTEMPTS guesses against a
6-digit space, over at most a few minutes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.auth_verification import EmailVerificationCode
from ..models.user import User
from .verification_codes import (
    CODE_TTL,
    AttemptVerdict,
    CodeState,
    ResendVerdict,
    expiry_from,
    generate_code,
    hash_code,
    may_attempt,
    may_resend,
    seconds_until_resend,
    verify_code,
)
from .verification_email import send_verification_code


logger = logging.getLogger(__name__)

TTL_MINUTES = int(CODE_TTL.total_seconds() // 60)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _state(row: EmailVerificationCode) -> CodeState:
    return CodeState(
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
        attempts=row.attempts,
        last_sent_at=row.last_sent_at,
        resend_count=row.resend_count,
    )


async def _active_code(db: AsyncSession, user_id) -> Optional[EmailVerificationCode]:
    """The live row for this user, if any — the one the partial unique index
    guarantees is at most one."""
    return (
        await db.execute(
            select(EmailVerificationCode).where(
                EmailVerificationCode.user_id == user_id,
                EmailVerificationCode.consumed_at.is_(None),
            )
        )
    ).scalar_one_or_none()


class StartOutcome(str, Enum):
    SENT = "sent"
    COOLDOWN = "cooldown"
    TOO_MANY_RESENDS = "too_many_resends"
    SEND_FAILED = "send_failed"


@dataclass(frozen=True)
class StartResult:
    outcome: StartOutcome
    retry_after_seconds: int = 0


async def start_or_resend(
    db: AsyncSession, user: User, *, is_resend: bool
) -> StartResult:
    """Mint a code, store its hash, and email it.

    `is_resend` distinguishes the first send of a signup (always allowed — she
    just created the account) from a teacher pressing "send it again" (rate
    limited). The row is the same either way.

    Does not commit; the caller owns the transaction. The email, however, is
    sent BEFORE the commit — see the note at the send site.
    """
    row = await _active_code(db, user.id)
    now = _now()

    if row is not None and is_resend:
        verdict = may_resend(_state(row), now)
        if verdict is ResendVerdict.COOLDOWN:
            return StartResult(StartOutcome.COOLDOWN,
                               seconds_until_resend(_state(row), now))
        if verdict is ResendVerdict.TOO_MANY_RESENDS:
            return StartResult(StartOutcome.TOO_MANY_RESENDS)

    code = generate_code()

    if row is None:
        row = EmailVerificationCode(
            user_id=user.id,
            code_hash=hash_code(code),
            expires_at=expiry_from(now),
            last_sent_at=now,
        )
        db.add(row)
    else:
        # REUSE the row. A new secret and a fresh attempt budget, but
        # `resend_count` keeps climbing — which is what bounds the total number
        # of guesses across all resends.
        row.code_hash = hash_code(code)
        row.expires_at = expiry_from(now)
        row.attempts = 0
        row.resend_count = row.resend_count + 1
        row.last_sent_at = now

    await db.flush()

    # Sent before the commit, deliberately. If the send fails we return
    # SEND_FAILED and the caller rolls back, so a teacher is never left holding
    # an account whose code went nowhere. The opposite order — commit, then
    # send — cannot be undone when the send fails.
    result = await send_verification_code(user.email, code, TTL_MINUTES)
    if not result.success:
        return StartResult(StartOutcome.SEND_FAILED)

    return StartResult(StartOutcome.SENT)


class VerifyOutcome(str, Enum):
    VERIFIED = "verified"
    NO_PENDING_CODE = "no_pending_code"
    WRONG_CODE = "wrong_code"
    EXPIRED = "expired"
    TOO_MANY_ATTEMPTS = "too_many_attempts"


async def verify(db: AsyncSession, user: User, code: str) -> VerifyOutcome:
    """Check a submitted code and, if it matches, mark the address proven.

    A wrong guess costs an attempt whether or not the code was right, and the
    attempt is recorded on the row so it survives across instances.

    Does not commit; the caller owns the transaction.
    """
    row = await _active_code(db, user.id)
    if row is None:
        return VerifyOutcome.NO_PENDING_CODE

    now = _now()
    verdict = may_attempt(_state(row), now)
    if verdict is AttemptVerdict.EXPIRED:
        return VerifyOutcome.EXPIRED
    if verdict is AttemptVerdict.TOO_MANY_ATTEMPTS:
        return VerifyOutcome.TOO_MANY_ATTEMPTS
    if verdict is AttemptVerdict.ALREADY_USED:
        # The index says this cannot happen (an active row is unconsumed by
        # definition), so treat it as "nothing pending" rather than inventing a
        # fifth answer for a state the schema forbids.
        return VerifyOutcome.NO_PENDING_CODE

    # Count the attempt BEFORE comparing. If the comparison somehow raised, the
    # attacker would otherwise get a free guess.
    row.attempts = row.attempts + 1

    if not verify_code(code, row.code_hash):
        return VerifyOutcome.WRONG_CODE

    row.consumed_at = now
    user.email_verified_at = now
    logger.info("email verified for user %s", user.id)
    return VerifyOutcome.VERIFIED
