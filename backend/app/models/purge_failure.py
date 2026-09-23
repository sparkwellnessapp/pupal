"""The purge's failure ledger (migration 033; M-B2, PRV-3)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PurgeFailure(Base):
    """One object a student purge could not delete. Written AFTER her rows are
    gone, so `student_id` deliberately has no foreign key; ids and an object
    path only — never a name."""
    __tablename__ = "purge_failures"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    student_id      = Column(UUID(as_uuid=True), nullable=False, index=True)
    bucket          = Column(Text, nullable=False)
    object_name     = Column(Text, nullable=False)
    error           = Column(Text, nullable=False)
    attempts        = Column(Integer, nullable=False, default=1)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_attempt_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
