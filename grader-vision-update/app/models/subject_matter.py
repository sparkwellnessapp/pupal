"""
Subject matter models for categorizing rubrics by educational subject.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


# Junction table for many-to-many relationship between users and subject matters
user_subject_matters = Table(
    'user_subject_matters',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('subject_matter_id', Integer, ForeignKey('subject_matters.id', ondelete='CASCADE'), primary_key=True),
)


class SubjectMatter(Base):
    """
    Lookup table for educational subject matters.
    
    Used to categorize rubrics and filter by subject.
    Contains Hebrew and English names for UI display.
    """
    __tablename__ = "subject_matters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    name_en = Column(String(100), nullable=False)
    name_he = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship(
        "User", 
        secondary=user_subject_matters, 
        back_populates="subject_matters"
    )
    
    def __repr__(self):
        return f"<SubjectMatter(id={self.id}, code={self.code}, name_he={self.name_he})>"
