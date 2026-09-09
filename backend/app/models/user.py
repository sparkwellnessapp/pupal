"""
User model with subscription management.
"""
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, String, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


def _as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    These columns are declared `DateTime` (naive) on the ORM but are TIMESTAMPTZ
    in the database (migration 001), so the driver hands back AWARE datetimes
    while anything just built in Python (`datetime.utcnow()`) is NAIVE. Comparing
    the two raises `TypeError: can't compare offset-naive and offset-aware
    datetimes` — which is what made `is_subscription_active` explode for every
    `trial` user, 500ing /auth/login, /auth/me and /auth/refresh *after*
    authentication had already succeeded. Normalize before comparing; never
    compare a stored timestamp against a bare `utcnow()`.
    """
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class SubscriptionStatus(PyEnum):
    """User subscription status."""
    trial = "trial"
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class User(Base):
    """
    User model with subscription and payment information.
    
    Supports:
    - Email/password authentication
    - Google OAuth authentication
    - Subscription management (trial → active)
    - Tranzila payment integration
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Null if Google auth
    # [024] The Google ID token's `sub`. THE identity for a Google account —
    # never the email, which a Google account can change over time (Google's own
    # guidance). Declared since 001 and first written by the auth PR.
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    # [024] Proof that whoever holds this account controls the address: stamped
    # when a verification code is redeemed, or at creation for a Google sign-up
    # (Google already proved it, and we require email_verified in the token).
    #
    # NULL means UNPROVEN, and an unproven account gets no session — which is
    # what makes the linking rule meaningful: a Google identity is never linked
    # into an account whose address nobody proved (the nOAuth class).
    #
    # timezone=True: the column is TIMESTAMPTZ, and a naive declaration would
    # serialize without an offset on the write path and with one on every read
    # (the 022 lesson).
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    full_name = Column(String(255), nullable=False)
    # [PR-G6] NULLABLE by design: the onboarding prompt is one field and
    # skippable. A teacher who skips it must still be attributable on the
    # other four override keys — NOT NULL here would either block signup or
    # force us to invent a school.
    school_id = Column(UUID(as_uuid=True), ForeignKey('schools.id'), nullable=True)
    school = relationship('School', back_populates='users')
    # [022] The teacher's full school list, IN HER ORDER. `school_id` above
    # stays the ONE PR-G6 attribution key and holds schools[0]; the junction is
    # the full truth.
    #
    # VIEWONLY, deliberately: the junction carries a `position` column that a
    # plain secondary-relationship write cannot populate, so both surfaces are
    # written by ONE function (school_resolution.set_user_schools) that owns the
    # ordering and the key together. A relationship that could also write them
    # would be a second writer with no way to keep position honest.
    schools = relationship(
        'School',
        secondary='user_schools',
        order_by='user_schools.c.position',
        viewonly=True,
    )
    # [022] Nullable + 'unspecified' is a real answer, not an absence.
    gender = Column(String(20), nullable=True)
    # [022] NULL means "has not finished onboarding". Stamped once, never unset.
    #
    # timezone=True, unlike its neighbours: the DB column is TIMESTAMPTZ (as all
    # of them are), and declaring it naive means the write path binds a naive
    # value and serializes it WITHOUT an offset while every later read carries
    # one — a browser then parses the write-path form as LOCAL time. The
    # neighbours carry that latent bug; a new column does not have to.
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    # ── [028] The onboarding "מתי המבחן הבא שלך?" step + outreach queue ──────
    #
    # timezone=True on every timestamp here: the columns are TIMESTAMPTZ, and a
    # naive declaration serializes without an offset on the write path and with
    # one on every read — a browser then parses the write-path form as LOCAL
    # time (the 022 lesson).
    #
    # Her stated date. NULL when unknown OR never answered; the two are told
    # apart by `next_exam_answered_at`, never by a second flag.
    next_exam_date = Column(Date, nullable=True)
    # ONB-2 (UnknownIsAnAnswer): «עוד לא יודעת» SETS this with a null date.
    next_exam_answered_at = Column(DateTime(timezone=True), nullable=True)
    # Idempotency guard for the 14-day re-ask digest. Re-answering makes her
    # eligible again automatically (sent_at < answered_at), so nothing is ever
    # cleared.
    next_exam_reask_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    # Stored AS TYPED — no format validation anywhere. Normalised to E.164 only
    # on READ, when a wa.me link is built.
    phone = Column(Text, nullable=True)
    # THE consent gate. Storage of `phone` is NOT consent (owner ruling, OD-2):
    # she may be called, and this column is the only thing that authorises a
    # WhatsApp message. Every consumer must read it — the digest emits a wa.me
    # link only when true, and the sheet carries the state beside the number so
    # a human working the queue cannot message a teacher who declined.
    whatsapp_opt_in = Column(Boolean, nullable=False, server_default=text("false"))
    # ONB-4 (OwnedFactsOnly): that she ASKED is ours. When the call was actually
    # scheduled for is Cal.com's, and mirroring it here would go stale the first
    # time she reschedules.
    guided_session_requested_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Subscription
    subscription_status = Column(
        Enum(SubscriptionStatus, name='subscription_status', create_type=False), 
        default=SubscriptionStatus.trial, 
        nullable=False
    )
    started_trial_at = Column(DateTime, default=datetime.utcnow)
    started_pro_at = Column(DateTime, nullable=True)
    
    # Tranzila payment integration
    tranzila_customer_id = Column(String(255), nullable=True)
    tranzila_token = Column(String(255), nullable=True)  # For recurring charges
    tranzila_transaction_id = Column(String(255), nullable=True)
    card_mask = Column(String(10), nullable=True)  # e.g., "****1234"
    last_payment_at = Column(DateTime, nullable=True)
    next_payment_at = Column(DateTime, nullable=True)
    
    # Relationships
    subject_matters = relationship(
        "SubjectMatter",
        secondary="user_subject_matters",
        back_populates="users"
    )
    rubrics         = relationship("Rubric",       back_populates="user")
    raw_rubrics     = relationship("RawRubric",    back_populates="user")
    # DB owns ON DELETE CASCADE on all tables below — ORM defers to it
    students        = relationship("Student",      back_populates="user", passive_deletes=True)
    classes         = relationship("Class",        back_populates="user", passive_deletes=True)
    transcriptions  = relationship("Transcription",back_populates="user", passive_deletes=True)
    graded_tests    = relationship("GradedTest",   back_populates="user", passive_deletes=True)
    grading_batches = relationship("GradingBatch", back_populates="user", passive_deletes=True)
    extraction_jobs = relationship("RubricExtractionJob", back_populates="user", passive_deletes=True)
    owned_shares = relationship(
        "RubricShare",
        foreign_keys="RubricShare.owner_user_id",
        back_populates="owner"
    )
    received_shares = relationship(
        "RubricShare",
        foreign_keys="RubricShare.shared_with_user_id",
        back_populates="shared_with"
    )
    
    @property
    def trial_ends_at(self) -> datetime:
        """Calculate when the trial period ends (14 days from start)."""
        if self.started_trial_at:
            return _as_utc(self.started_trial_at) + timedelta(days=14)
        return datetime.now(timezone.utc)

    @property
    def is_subscription_active(self) -> bool:
        """Check if the user has an active subscription (trial or paid)."""
        if self.subscription_status == SubscriptionStatus.active:
            return True
        if self.subscription_status == SubscriptionStatus.trial:
            return datetime.now(timezone.utc) < self.trial_ends_at
        return False
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, status={self.subscription_status})>"
