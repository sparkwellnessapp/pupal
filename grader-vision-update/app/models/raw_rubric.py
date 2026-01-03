"""
Raw rubric model for preserving original AI extraction results.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class RawRubric(Base):
    """
    Stores the original AI-extracted rubric data before teacher edits.
    
    This allows comparison between what the AI extracted and what the
    teacher ultimately saved, useful for:
    - Quality analysis of AI extraction
    - Training data generation
    - Audit trail
    """
    __tablename__ = "raw_rubrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Same structure as rubrics table
    rubric_json = Column(JSON, nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    total_points = Column(Float, nullable=True)
    
    # Extraction metadata
    source_filename = Column(String(255), nullable=True)
    extraction_model = Column(String(100), nullable=True)  # e.g., 'gpt-4o'
    extraction_duration_ms = Column(Integer, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="raw_rubrics")
    rubric = relationship("Rubric", back_populates="raw_rubric", uselist=False)
    
    def __repr__(self):
        return f"<RawRubric(id={self.id}, name={self.name}, model={self.extraction_model})>"
