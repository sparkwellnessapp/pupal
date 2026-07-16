import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class Student(Base):
    __tablename__ = "students"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name  = Column(String(255), nullable=False)
    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "full_name", name="students_unique_name_per_user"),
    )

    user              = relationship("User", back_populates="students")
    class_memberships = relationship("ClassMembership", back_populates="student", passive_deletes=True)
    transcriptions    = relationship("Transcription", back_populates="student", passive_deletes=True)
    graded_tests      = relationship("GradedTest", back_populates="student", passive_deletes=True)

    def __repr__(self):
        return f"<Student(id={self.id}, full_name={self.full_name})>"
