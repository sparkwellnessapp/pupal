"""
User model with subscription management.
"""
import uuid
from datetime import datetime, timedelta
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


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
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
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
    rubrics = relationship("Rubric", back_populates="user")
    graded_tests = relationship("GradedTest", back_populates="user")
    raw_rubrics = relationship("RawRubric", back_populates="user")
    raw_graded_tests = relationship("RawGradedTest", back_populates="user")
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
            return self.started_trial_at + timedelta(days=14)
        return datetime.utcnow()
    
    @property
    def is_subscription_active(self) -> bool:
        """Check if the user has an active subscription (trial or paid)."""
        if self.subscription_status == SubscriptionStatus.active:
            return True
        if self.subscription_status == SubscriptionStatus.trial:
            return datetime.utcnow() < self.trial_ends_at
        return False
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, status={self.subscription_status})>"
