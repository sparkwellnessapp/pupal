import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class Transcription(Base):
    __tablename__ = "transcriptions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rubric_id       = Column(UUID(as_uuid=True), ForeignKey("rubrics.id"), nullable=False)
    # S11: batch association. NULL for single-test transcriptions.
    batch_id        = Column(UUID(as_uuid=True), ForeignKey("grading_batches.id"), nullable=True)
    student_id      = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=True)
    student_name    = Column(String(255), nullable=True)
    gcs_uri         = Column(String(500), nullable=False)
    gcs_bucket      = Column(String(255), nullable=False)
    gcs_object_path = Column(String(500), nullable=False)
    filename        = Column(String(500), nullable=True)
    draft_json      = Column(JSONB, nullable=False)
    contract_json   = Column(JSONB(none_as_null=True), nullable=True)
    # Teacher review overlay (migration 014): full-snapshot working copy,
    # writable only while status='transcribed'; nulled in the approval
    # transition UPDATE (LCY-1: approved rows are never written).
    review_json     = Column(JSONB(none_as_null=True), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    # Valid values: 'transcribed', 'approved' — enforced by DB CHECK transcriptions_approval_consistency
    status          = Column(String(20), nullable=False, default="transcribed")
    created_at      = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # [032] every FK above is NO ACTION (AM-B1). AM-B4: the scan's student is the
    # scan's teacher's student, and the pair is the target of two tenant FKs.
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="transcriptions_id_user_id_key"),
        ForeignKeyConstraint(["student_id", "user_id"], ["students.id", "students.user_id"],
                             name="transcriptions_student_tenant_fkey"),
    )

    user         = relationship("User", back_populates="transcriptions")
    rubric       = relationship("Rubric", back_populates="transcriptions")
    batch        = relationship("GradingBatch", back_populates="transcriptions")
    student      = relationship("Student", back_populates="transcriptions", foreign_keys=[student_id])
    graded_tests = relationship("GradedTest", back_populates="transcription", passive_deletes=True,
                                foreign_keys="GradedTest.transcription_id")

    def __repr__(self):
        return f"<Transcription(id={self.id}, status={self.status})>"
