import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, ForeignKey,
    Boolean, Float, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class Rubric(Base):
    """
    Stores rubric data in the two-artifact architecture.

    - draft_json: Teacher-editable ExtractRubricResponse
    - contract_json: Frozen GradingRubricContract for grading
    """
    __tablename__ = "rubrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    name        = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    total_points = Column(Float, nullable=True)

    draft_json    = Column(JSONB, nullable=True)
    contract_json = Column(JSONB, nullable=True)

    contract_version      = Column(String(50), nullable=True)
    last_compiled_at      = Column(DateTime, nullable=True)
    needs_recompilation   = Column(Boolean, default=False, nullable=False)
    acknowledged_warnings = Column(JSONB, default=list)
    compilation_attempts  = Column(Integer, default=0, nullable=False)

    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    raw_rubric_id = Column(UUID(as_uuid=True), ForeignKey("raw_rubrics.id", ondelete="SET NULL"), nullable=True, unique=True)
    # PR-1 provenance chain: rubric → extraction job → (prompt, model, tokens, source doc)
    extraction_job_id = Column(UUID(as_uuid=True), ForeignKey("rubric_extraction_jobs.id", ondelete="SET NULL"), nullable=True)

    user          = relationship("User", back_populates="rubrics")
    raw_rubric    = relationship("RawRubric", back_populates="rubric")
    shares        = relationship("RubricShare", back_populates="rubric", cascade="all, delete-orphan")
    share_history = relationship("RubricShareHistory", back_populates="rubric", cascade="all, delete-orphan")
    # DB owns ON DELETE CASCADE on graded_tests.rubric_id — ORM defers to it
    graded_tests    = relationship("GradedTest", back_populates="rubric", passive_deletes=True)
    transcriptions  = relationship("Transcription", back_populates="rubric", passive_deletes=True)
    grading_batches = relationship("GradingBatch", back_populates="rubric", passive_deletes=True)

    @property
    def is_ontology_format(self) -> bool:
        return self.draft_json is not None

    @property
    def is_compiled(self) -> bool:
        return self.contract_json is not None and not self.needs_recompilation

    @property
    def can_grade(self) -> bool:
        return self.is_compiled

    def __repr__(self):
        return f"<Rubric(id={self.id}, name={self.name}, compiled={self.is_compiled})>"


class GradingBatch(Base):
    __tablename__ = "grading_batches"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                 = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rubric_id               = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    rubric_contract_version = Column(String(50), nullable=False)
    name                    = Column(String(255), nullable=True)
    class_id                = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    # Valid values: 'pending','in_progress','completed','partially_completed','failed'
    # Enforced by DB CHECK grading_batches_status_check; String(30) to fit 'partially_completed'
    status                  = Column(String(30), nullable=False, default="pending")
    # S11: number of PDFs submitted at creation — used to compute in-flight transcription count.
    test_count              = Column(Integer, nullable=False, default=0)
    started_at              = Column(DateTime(timezone=True), nullable=True)
    completed_at            = Column(DateTime(timezone=True), nullable=True)
    created_at              = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at              = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user          = relationship("User", back_populates="grading_batches")
    rubric        = relationship("Rubric", back_populates="grading_batches")
    school_class  = relationship("Class")
    graded_tests  = relationship("GradedTest", back_populates="batch", passive_deletes=True)
    transcriptions = relationship("Transcription", back_populates="batch", passive_deletes=True)

    def __repr__(self):
        return f"<GradingBatch(id={self.id}, status={self.status})>"


class GradedTest(Base):
    __tablename__ = "graded_tests"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                 = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rubric_id               = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    transcription_id        = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    student_id              = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    batch_id                = Column(UUID(as_uuid=True), ForeignKey("grading_batches.id", ondelete="SET NULL"), nullable=True)
    rubric_contract_version = Column(String(50), nullable=False)
    student_name            = Column(String(255), nullable=False)
    filename                = Column(String(500), nullable=True)
    draft_json              = Column(JSONB, nullable=True)
    draft_created_at        = Column(DateTime(timezone=True), nullable=True)
    contract_json           = Column(JSONB, nullable=True)
    approved_at             = Column(DateTime(timezone=True), nullable=True)
    regraded_from_id        = Column(UUID(as_uuid=True), ForeignKey("graded_tests.id", ondelete="SET NULL"), nullable=True)
    regraded_to_id          = Column(UUID(as_uuid=True), ForeignKey("graded_tests.id", ondelete="SET NULL"), nullable=True)
    # Valid values: 'pending','grading','draft','approved','failed'
    # Enforced by DB CHECK graded_tests_status_consistency
    status                  = Column(String(20), nullable=False, default="pending")
    error_message           = Column(Text, nullable=True)
    total_score             = Column(Numeric(10, 2), nullable=True)
    total_possible          = Column(Numeric(10, 2), nullable=True)
    percentage              = Column(Numeric(5, 2), nullable=True)
    llm_calls_count         = Column(Integer, nullable=False, default=0)
    grading_duration_ms     = Column(Integer, nullable=False, default=0)
    model_version           = Column(String(50), nullable=True)
    # S8 cost/token columns (migration 009)
    grading_started_at      = Column(DateTime(timezone=True), nullable=True)
    total_input_tokens      = Column(Integer, nullable=True)
    total_output_tokens     = Column(Integer, nullable=True)
    total_cost_usd          = Column(Numeric(10, 4), nullable=True)
    prompt_version          = Column(String(50), nullable=True)
    created_at              = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at              = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user          = relationship("User", back_populates="graded_tests")
    rubric        = relationship("Rubric", back_populates="graded_tests")
    transcription = relationship("Transcription", back_populates="graded_tests")
    student       = relationship("Student", back_populates="graded_tests")
    batch         = relationship("GradingBatch", back_populates="graded_tests", foreign_keys=[batch_id])

    # Self-referential revision chain — one-to-one doubly-linked list.
    # regraded_from: navigate to the predecessor this row replaces.
    # remote_side=[id]: the "remote" (predecessor) row is identified by its id.
    regraded_from = relationship(
        "GradedTest",
        foreign_keys=[regraded_from_id],
        remote_side=[id],
        uselist=False,
    )
    # regraded_to: navigate to the successor that replaces this row.
    # remote_side=[id]: the "remote" (successor) row is identified by its id.
    regraded_to = relationship(
        "GradedTest",
        foreign_keys=[regraded_to_id],
        remote_side=[id],
        uselist=False,
    )

    def __repr__(self):
        return f"<GradedTest(id={self.id}, status={self.status}, student={self.student_name})>"
