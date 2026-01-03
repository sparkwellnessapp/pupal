"""
Raw graded test model for preserving original AI grading results.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class RawGradedTest(Base):
    """
    Stores the original AI-graded test data before teacher adjustments.
    
    This allows comparison between AI grading and final grades,
    useful for:
    - Quality analysis of AI grading accuracy
    - Training data generation
    - Audit trail of teacher modifications
    """
    __tablename__ = "raw_graded_tests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Same structure as graded_tests table
    student_name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    graded_json = Column(JSON, nullable=False)
    total_score = Column(Float, nullable=False)
    total_possible = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    student_answers_json = Column(JSON, nullable=True)
    
    # Grading metadata
    grading_model = Column(String(100), nullable=True)  # e.g., 'gpt-4o'
    grading_duration_ms = Column(Integer, nullable=True)
    transcription_model = Column(String(100), nullable=True)  # For handwritten tests
    transcription_duration_ms = Column(Integer, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="raw_graded_tests")
    rubric = relationship("Rubric")
    graded_test = relationship("GradedTest", back_populates="raw_graded_test", uselist=False)
    
    def __repr__(self):
        return f"<RawGradedTest(id={self.id}, student={self.student_name}, score={self.total_score}/{self.total_possible})>"
