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
