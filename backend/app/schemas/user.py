"""
Pydantic schemas for user-related API operations.
"""
from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# =============================================================================
# Subject Matter Schemas
# =============================================================================

class SubjectMatterResponse(BaseModel):
    """Response schema for subject matter."""
    id: int
    code: str
    name_en: str
    name_he: str
    
    class Config:
        from_attributes = True


class UpdateSubjectMattersRequest(BaseModel):
    """Request to update user's subject matters."""
    subject_matter_ids: List[int] = Field(..., description="List of subject matter IDs to assign")


# =============================================================================
# User Schemas
# =============================================================================

class UserResponse(BaseModel):
    """Response schema for user profile."""
    id: UUID
    email: str
    full_name: str
    subscription_status: str
    started_trial_at: Optional[datetime] = None
    started_pro_at: Optional[datetime] = None
    trial_ends_at: datetime
    is_subscription_active: bool
    subject_matters: List[SubjectMatterResponse] = Field(default_factory=list)
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(..., min_length=1)


class UserLoginRequest(BaseModel):
    """Request for user login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response with authentication token."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# =============================================================================
# Rubric Sharing Schemas
# =============================================================================

class ShareRubricRequest(BaseModel):
    """Request to share a rubric with another user."""
    email: EmailStr = Field(..., description="Email of the user to share with")
    permission: Literal["view", "edit"] = Field("view", description="Permission level")


class RubricShareResponse(BaseModel):
    """Response schema for a rubric share."""
    id: UUID
    rubric_id: UUID
    shared_with_email: str
    shared_with_name: str
    permission: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RubricShareListResponse(BaseModel):
    """Response for listing all shares of a rubric."""
    rubric_id: UUID
    owner_email: str
    shares: List[RubricShareResponse] = Field(default_factory=list)


# =============================================================================
# User's Rubrics Response (includes shared rubrics)
# =============================================================================

class UserRubricResponse(BaseModel):
    """A rubric in the user's list (owned or shared)."""
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    total_points: Optional[float] = None
    created_at: datetime
    is_owned: bool = Field(..., description="True if user owns this rubric")
    permission: Optional[str] = Field(None, description="Permission level if shared (null if owned)")
    owner_name: Optional[str] = Field(None, description="Owner name if shared (null if owned)")
    
    class Config:
        from_attributes = True


class UserRubricsListResponse(BaseModel):
    """Response for listing user's rubrics."""
    owned_count: int
    shared_count: int
    rubrics: List[UserRubricResponse]
