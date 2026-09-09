"""Auth state that is neither a user nor a session: verification codes and
sign-in nonces (migration 024).

Both tables exist for the same reason — a one-time secret needs somewhere to be
single-use — and both store a HASH rather than the secret itself. Neither is ever
read for its value; they are only ever matched against something a caller
presents.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EmailVerificationCode(Base):
    """A pending 6-digit code for one user.

    `code_hash` is bcrypt, like a password: even the database must not hold a
    recoverable one-time code.

    `attempts` and `resend_count` live on the ROW, not in process memory,
    because Cloud Run runs up to 60 instances — an in-process counter is
    per-instance, so it would hand an attacker 60x the budget while the logs
    claimed the limit held.

    At most one row per user has `consumed_at IS NULL`, enforced by the partial
    unique index `idx_email_codes_one_active_per_user` rather than by
    delete-then-insert bookkeeping, which is a race and not a rule.
    """

    __tablename__ = "email_verification_codes"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No index=True: the migration creates none, and the ORM must mirror the
    # migrated schema rather than claim an index the database does not have
    # (CLAUDE.md §8). None is needed — the ONLY query is "the live code for this
    # user", which `idx_email_codes_one_active_per_user` already covers.
    user_id      = Column(UUID(as_uuid=True),
                          ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False)
    code_hash    = Column(Text, nullable=False)
    expires_at   = Column(DateTime(timezone=True), nullable=False)
    consumed_at  = Column(DateTime(timezone=True), nullable=True)
    attempts     = Column(Integer, nullable=False, default=0)
    resend_count = Column(Integer, nullable=False, default=0)
    # server_default, not a Python default: the DDL already says DEFAULT now(),
    # and a Python default on a timezone=True column must be AWARE or asyncpg
    # refuses the bind. Letting the database fill it removes that trap entirely
    # and keeps one definition of "now" (the 022 lesson, from the other side).
    last_sent_at = Column(DateTime(timezone=True), nullable=False,
                          server_default=func.now())
    created_at   = Column(DateTime(timezone=True), nullable=False,
                          server_default=func.now())

    user = relationship("User")

    def __repr__(self) -> str:            # never render the hash
        return (f"<EmailVerificationCode user={self.user_id} "
                f"consumed={self.consumed_at is not None}>")


class AuthNonce(Base):
    """A single-use nonce for Sign in with Google.

    A stolen Google `credential` is a valid bearer token for its ~1h lifetime.
    This row is what makes it single-use: minted by us, embedded in the signed ID
    token by Google, and accepted exactly once.

    The primary key IS the sha256 of the nonce — the nonce itself is never
    stored, and the hash is the only thing ever looked up.
    """

    __tablename__ = "auth_nonces"

    nonce_hash  = Column(Text, primary_key=True)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False,
                         server_default=func.now())

    def __repr__(self) -> str:            # never render the hash
        return f"<AuthNonce consumed={self.consumed_at is not None}>"
