"""
Rubric sharing model for explicit rubric sharing between users.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class SharePermission(PyEnum):
    """Permission level for shared rubrics."""
    view = "view"
    edit = "edit"


class RubricShare(Base):
    """
    Explicit sharing of rubrics between users.
    
    A rubric owner can share their rubric with other users,
    granting either view or edit permissions.
    """
    __tablename__ = "rubric_shares"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(
        Enum(SharePermission, name='share_permission', create_type=False), 
        default=SharePermission.view, 
        nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('rubric_id', 'shared_with_user_id', name='uq_rubric_share'),
    )
    
    # Relationships
    rubric = relationship("Rubric", back_populates="shares")
    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_shares")
    shared_with = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_shares")
    
    def __repr__(self):
        return f"<RubricShare(rubric={self.rubric_id}, shared_with={self.shared_with_user_id}, permission={self.permission})>"


class RubricShareToken(Base):
    """
    Token for email-based rubric sharing.
    
    Flow:
    1. Teacher shares → token created, email sent
    2. Recipient clicks invite link with token
    3. If new user: signup → token consumed → rubric copied
    4. If existing user: login → token consumed → rubric copied
    5. PDF download link works independently (no token consumption)
    """
    __tablename__ = "rubric_share_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(64), unique=True, nullable=False, index=True)
    
    # Source rubric (to copy from)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    sender_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Recipient info
    recipient_email = Column(String(255), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  # 30 days from creation
    accepted_at = Column(DateTime, nullable=True)  # When rubric was copied
    
    # Generated PDF for download (GCS path)
    generated_pdf_gcs_path = Column(String(500), nullable=True)
    
    # The copied rubric (after acceptance)
    copied_rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    rubric = relationship("Rubric", foreign_keys=[rubric_id])
    sender = relationship("User", foreign_keys=[sender_user_id])
    copied_rubric = relationship("Rubric", foreign_keys=[copied_rubric_id])
    
    def __repr__(self):
        return f"<RubricShareToken(token={self.token[:8]}..., recipient={self.recipient_email})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_accepted(self) -> bool:
        """Check if token has been used."""
        return self.accepted_at is not None


class RubricShareHistory(Base):
    """
    Track all shares for a rubric.
    
    Provides history view for the rubric owner showing
    who the rubric was shared with and the status.
    """
    __tablename__ = "rubric_share_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    sender_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Recipient
    recipient_email = Column(String(255), nullable=False)
    
    # Status timestamps
    shared_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Link to token
    share_token_id = Column(UUID(as_uuid=True), ForeignKey("rubric_share_tokens.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    rubric = relationship("Rubric", back_populates="share_history")
    sender = relationship("User")
    share_token = relationship("RubricShareToken")
    
    def __repr__(self):
        return f"<RubricShareHistory(rubric={self.rubric_id}, recipient={self.recipient_email}, status={self.status})>"
    
    @property
    def status(self) -> str:
        """Get current status of this share."""
        if self.revoked_at:
            return "revoked"
        if self.accepted_at:
            return "accepted"
        return "pending"
