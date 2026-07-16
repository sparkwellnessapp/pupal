"""
Authentication API endpoints.
"""
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field

from ...database import get_db
from ...models.user import User
from ...services.auth_service import auth_service, ACCESS_TOKEN_EXPIRE_HOURS
from ...schemas.user import UserResponse, SubjectMatterResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/auth", tags=["auth"])

# Security scheme for JWT
security = HTTPBearer(auto_error=False)


# =============================================================================
# Request/Response Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class SignupRequest(BaseModel):
    """Signup request body."""
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    """Authentication response with token and user."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_HOURS * 3600
    user: UserResponse


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# =============================================================================
# Auth Helper
# =============================================================================

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user from JWT token (optional - returns None if not authenticated)."""
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = auth_service.decode_token(token)
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user = await auth_service.get_user_by_id(db, UUID(user_id))
        return user
    except Exception:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from JWT token (required - raises 401 if not authenticated)."""
    user = await get_current_user_optional(credentials, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def build_user_response(user: User) -> UserResponse:
    """Build UserResponse from User model."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        subscription_status=user.subscription_status.value,
        started_trial_at=user.started_trial_at,
        started_pro_at=user.started_pro_at,
        trial_ends_at=user.trial_ends_at,
        is_subscription_active=user.is_subscription_active,
        subject_matters=[
            SubjectMatterResponse(
                id=sm.id,
                code=sm.code,
                name_en=sm.name_en,
                name_he=sm.name_he,
            )
            for sm in (user.subject_matters or [])
        ],
        created_at=user.created_at,
    )


# =============================================================================
# Auth Endpoints
# =============================================================================

@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate user with email and password.
    
    Returns JWT access token and user info.
    """
    user = await auth_service.authenticate_user(db, request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email או סיסמה שגויים",
        )
    
    # Create access token
    access_token = auth_service.create_access_token(user.id, user.email)
    
    logger.info(f"User {user.email} logged in successfully")
    
    return AuthResponse(
        access_token=access_token,
        user=build_user_response(user),
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Create a new user account.
    
    Returns JWT access token and user info.
    """
    # Check if email already exists
    existing_user = await auth_service.get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="כתובת האימייל כבר רשומה במערכת",
        )
    
    # Create user
    try:
        user = await auth_service.create_user(
            db=db,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="שגיאה ביצירת החשבון",
        )
    
    # Create access token
    access_token = auth_service.create_access_token(user.id, user.email)
    
    logger.info(f"New user {user.email} signed up successfully")
    
    return AuthResponse(
        access_token=access_token,
        user=build_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get the current authenticated user's profile.
    """
    return build_user_response(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Logout the current user.
    
    Note: Since we use stateless JWT tokens, this is just a confirmation.
    The client should discard the token.
    """
    logger.info(f"User {user.email} logged out")
    return MessageResponse(message="התנתקת בהצלחה")


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    user: User = Depends(get_current_user),
) -> AuthResponse:
    """
    Refresh the access token for the current user.
    """
    access_token = auth_service.create_access_token(user.id, user.email)
    
    return AuthResponse(
        access_token=access_token,
        user=build_user_response(user),
    )
