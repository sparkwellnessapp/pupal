"""Email verification codes — the pure half.

Generation, hashing, and the decision "may this attempt proceed / may this code
be resent". No database, no clock of its own: `now` is always an argument, which
is what makes expiry and cooldown testable without sleeping.

Policy, per OWASP/NIST practice for out-of-band codes:
  * 6 digits, uniformly random from a CSPRNG
  * 10-minute lifetime
  * bcrypt at rest — even the database must not hold a recoverable code
  * 5 attempts, then the code is dead (not merely wrong)
  * 60-second resend cooldown, and a cap on resends per code
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import bcrypt


CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_RESENDS = 5


def generate_code() -> str:
    """A fresh 6-digit code.

    `secrets.randbelow` over the whole range, NOT `"".join(choice(digits))` and
    not `randint` from `random`: this value is a credential, so it comes from
    the CSPRNG, and the leading zero is preserved by formatting rather than by
    luck (a code of "004512" is as valid as any other and must stay six chars).
    """
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def hash_code(code: str) -> str:
    """bcrypt, the same hasher the passwords use.

    A one-time code is short-lived, but it is still a shared secret that opens
    an account, and a database dump must not yield working codes.
    """
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_code(candidate: str, code_hash: str) -> bool:
    """Constant-time comparison via bcrypt's own checker.

    Returns False rather than raising on a malformed hash: a corrupt row must
    fail closed, not 500.
    """
    try:
        return bcrypt.checkpw(candidate.encode("utf-8"), code_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def expiry_from(now: datetime) -> datetime:
    """When a code minted at `now` stops being acceptable."""
    return _aware(now) + CODE_TTL


class AttemptVerdict(str, Enum):
    """Whether an incoming code may be checked at all."""

    OK = "ok"                      #: proceed to the (expensive) hash comparison
    EXPIRED = "expired"            #: past its 10 minutes
    ALREADY_USED = "already_used"  #: consumed — a code is single-use
    TOO_MANY_ATTEMPTS = "too_many_attempts"


@dataclass(frozen=True)
class CodeState:
    """The row, reduced to what the decisions depend on."""

    expires_at: datetime
    consumed_at: Optional[datetime]
    attempts: int
    last_sent_at: datetime
    resend_count: int


def may_attempt(state: CodeState, now: datetime) -> AttemptVerdict:
    """Guard the verify path.

    ORDER IS DELIBERATE. Consumption and expiry are checked BEFORE the attempt
    count, and all three before the caller runs bcrypt — bcrypt is intentionally
    slow, and a dead code deserves none of that compute. Checking cheap facts
    first is both the correct behaviour and the cheap one.
    """
    if state.consumed_at is not None:
        return AttemptVerdict.ALREADY_USED
    if _aware(now) >= _aware(state.expires_at):
        return AttemptVerdict.EXPIRED
    if state.attempts >= MAX_ATTEMPTS:
        return AttemptVerdict.TOO_MANY_ATTEMPTS
    return AttemptVerdict.OK


class ResendVerdict(str, Enum):
    OK = "ok"
    COOLDOWN = "cooldown"          #: too soon since the last send
    TOO_MANY_RESENDS = "too_many_resends"


def may_resend(state: CodeState, now: datetime) -> ResendVerdict:
    """Guard the resend path.

    The cooldown is what stops the endpoint being a free mailbomb aimed at any
    address an attacker types; the cap is what stops a patient one.
    """
    if state.resend_count >= MAX_RESENDS:
        return ResendVerdict.TOO_MANY_RESENDS
    if _aware(now) - _aware(state.last_sent_at) < RESEND_COOLDOWN:
        return ResendVerdict.COOLDOWN
    return ResendVerdict.OK


def seconds_until_resend(state: CodeState, now: datetime) -> int:
    """How long the client should disable its resend button. Never negative."""
    elapsed = _aware(now) - _aware(state.last_sent_at)
    remaining = (RESEND_COOLDOWN - elapsed).total_seconds()
    return max(0, int(remaining + 0.999))       # round up: never promise early


def _aware(dt: datetime) -> datetime:
    """Coerce to aware UTC before comparing.

    Every timestamp column in this database is TIMESTAMPTZ, so a value READ from
    the DB is aware while one just built in Python may not be. Comparing the two
    raises TypeError — the failure that 500'd /auth/login for 271 users in the
    2026-08-17 incident. Normalize instead of trusting the caller.
    """
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
