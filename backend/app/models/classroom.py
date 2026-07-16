import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey,
    UniqueConstraint, PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class Class(Base):
    __tablename__ = "classes"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name              = Column(String(255), nullable=False)
    subject_matter_id = Column(Integer, ForeignKey("subject_matters.id", ondelete="SET NULL"), nullable=True)
    school_year       = Column(String(20), nullable=True)
    created_at        = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at        = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="classes_unique_name_per_user"),
    )

    user           = relationship("User", back_populates="classes")
    subject_matter = relationship("SubjectMatter", back_populates="classes")
    memberships    = relationship("ClassMembership", back_populates="school_class", passive_deletes=True)

    def __repr__(self):
        return f"<Class(id={self.id}, name={self.name})>"


class ClassMembership(Base):
    __tablename__ = "class_memberships"

    class_id   = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        PrimaryKeyConstraint("class_id", "student_id"),
    )

    school_class = relationship("Class", back_populates="memberships")
    student      = relationship("Student", back_populates="class_memberships")

    def __repr__(self):
        return f"<ClassMembership(class_id={self.class_id}, student_id={self.student_id})>"
