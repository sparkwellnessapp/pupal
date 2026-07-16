"""
Pydantic schemas for classroom (students + classes) API endpoints.

These are thin API response shapes, distinct from the ORM models.
user_id is never included in responses — ownership is implicit.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested mini-schemas (used inside detail responses)
# ---------------------------------------------------------------------------

class ClassMini(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True


class StudentMini(BaseModel):
    id: UUID
    full_name: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Student schemas
# ---------------------------------------------------------------------------

class StudentResponse(BaseModel):
    id: UUID
    full_name: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StudentDetailResponse(StudentResponse):
    classes: List[ClassMini] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CreateStudentRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None


class UpdateStudentRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Class schemas
# ---------------------------------------------------------------------------

class ClassResponse(BaseModel):
    id: UUID
    name: str
    subject_matter_id: Optional[int] = None
    subject_matter_name: Optional[str] = None
    school_year: Optional[str] = None
    student_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ClassDetailResponse(ClassResponse):
    students: List[StudentMini] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CreateClassRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject_matter_id: Optional[int] = None
    school_year: Optional[str] = Field(None, max_length=20)


class UpdateClassRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject_matter_id: Optional[int] = None
    school_year: Optional[str] = Field(None, max_length=20)


# ---------------------------------------------------------------------------
# Membership schemas
# ---------------------------------------------------------------------------

class AddStudentToClassRequest(BaseModel):
    student_id: UUID
