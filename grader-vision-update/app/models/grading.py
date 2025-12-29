"""
SQLAlchemy ORM models for grading system.
Stores rubrics, graded tests, and references to graded PDFs in GCS.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class Rubric(Base):
    """
    Stores parsed rubric data extracted from PDFs.
    
    The rubric_json contains the structured rubric with questions and criteria:
    {
        "questions": [
            {
                "question_number": 1,
                "total_points": 40,
                "criteria": [
                    {"description": "...", "points": 10},
                    ...
                ]
            },
            ...
        ]
    }
    """
    __tablename__ = "rubrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # The full rubric structure as JSON
    rubric_json = Column(JSON, nullable=False)
    
    # Optional metadata
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    total_points = Column(Float, nullable=True)
    
    # Relationships
    graded_tests = relationship("GradedTest", back_populates="rubric", cascade="all, delete-orphan")
    graded_pdfs = relationship("GradedTestPdf", back_populates="rubric", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Rubric(id={self.id}, name={self.name}, total_points={self.total_points})>"


class GradedTest(Base):
    """
    Stores graded test results as JSON.
    
    The graded_json contains the full grading result:
    {
        "student_name": "...",
        "filename": "...",
        "total_score": 85,
        "total_possible": 100,
        "percentage": 85.0,
        "grades": [
            {
                "criterion": "...",
                "mark": "✓",
                "points_earned": 10,
                "points_possible": 10,
                "explanation": "...",
                "confidence": "high"
            },
            ...
        ],
        "low_confidence_items": [...]
    }
    
    The student_answers_json contains the transcribed student answers:
    {
        "student_name": "...",
        "filename": "...",
        "answers": [
            {
                "question_number": 1,
                "sub_question_id": null,
                "answer_text": "code..."
            },
            ...
        ]
    }
    """
    __tablename__ = "graded_tests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Student identification
    student_name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    
    # Grading results
    graded_json = Column(JSON, nullable=False)
    total_score = Column(Float, nullable=False)
    total_possible = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    
    # Student answers (transcribed code) - NEW COLUMN
    student_answers_json = Column(JSON, nullable=True)
    
    # Relationships
    rubric = relationship("Rubric", back_populates="graded_tests")
    graded_pdf = relationship("GradedTestPdf", back_populates="graded_test", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<GradedTest(id={self.id}, student={self.student_name}, score={self.total_score}/{self.total_possible})>"


class GradedTestPdf(Base):
    """
    Stores references to annotated graded PDFs in Google Cloud Storage.
    
    PDFs are stored in GCS, this table stores the reference (gcs_uri) and metadata.
    """
    __tablename__ = "graded_test_pdfs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graded_test_id = Column(UUID(as_uuid=True), ForeignKey("graded_tests.id", ondelete="CASCADE"), nullable=False, unique=True)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # GCS storage reference
    gcs_uri = Column(String(500), nullable=False)  # gs://bucket/path/to/file.pdf
    gcs_bucket = Column(String(255), nullable=False)
    gcs_object_path = Column(String(500), nullable=False)
    
    # File metadata
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Float, nullable=True)
    content_type = Column(String(100), default="application/pdf")
    
    # Relationships
    graded_test = relationship("GradedTest", back_populates="graded_pdf")
    rubric = relationship("Rubric", back_populates="graded_pdfs")
    
    def __repr__(self):
        return f"<GradedTestPdf(id={self.id}, filename={self.filename}, gcs_uri={self.gcs_uri})>"