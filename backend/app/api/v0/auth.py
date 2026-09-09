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

from ...config import settings
from ...database import get_db
from ...models.user import User
from ...services.auth_service import auth_service, ACCESS_TOKEN_EXPIRE_HOURS
from ...services import auth_nonce, email_verification
from ...services.email_verification import StartOutcome, VerifyOutcome
from ...services.google_identity import (
    AccountFacts,
    GoogleClaimsError,
    LinkOutcome,
    decide_link,
)
from ...services.google_token_verifier import (
    GoogleAuthUnavailable,
    GoogleTokenInvalid,
    verify_google_credential,
)
from ...schemas.user import SchoolResponse, UserResponse, SubjectMatterResponse


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


class SignupPendingResponse(BaseModel):
    """[024] What signup returns now: NOT a session.

    Owner ruling A4 — an address nobody proved gets no session. The teacher
    holds this while she fetches the code; `/verify-email` is what issues the
    JWT. `verification_required` is always True and is there so a client can
    branch on the SHAPE rather than on the absence of a field.
    """
    verification_required: bool = True
    email: EmailStr
    resend_available_in_seconds: int = 0


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    # Exactly six digits. [0-9] and not \d: \d is Unicode-aware in Pydantic's
    # Rust engine, so «١٢٣٤٥٦» would pass — a string that renders like a code
    # but is a different one.
    code: str = Field(..., pattern=r"^[0-9]{6}$")


class ResendCodeRequest(BaseModel):
    email: EmailStr


class GoogleNonceResponse(BaseModel):
    """A one-shot nonce for the Sign in with Google button."""
    nonce: str


class GoogleAuthRequest(BaseModel):
    """`credential` is the ID token the GIS button hands the browser."""
    credential: str = Field(..., min_length=1)
    nonce: str = Field(..., min_length=1)


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
        # [022] onboarding. `user.schools` must be EAGER-loaded by whoever
        # produced this User (auth_service does it for every loader) — an async
        # lazy load here is a MissingGreenlet 500 after auth already succeeded.
        gender=user.gender,
        onboarding_completed_at=user.onboarding_completed_at,
        schools=[
            SchoolResponse(
                id=s.id, name=s.name, city=s.city,
                ministry_symbol=s.ministry_symbol,
            )
            for s in (user.schools or [])
        ],
        primary_school_id=user.school_id,
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
    
    # [024] A4: correct credentials are NOT enough — the address must have been
    # proven. Without this check the whole ruling is decorative: an attacker who
    # pre-registers victim@school.org simply logs in with the password he chose,
    # and the account the Google linking rule treats as "untrustworthy" is one
    # he is already sitting inside.
    #
    # 403, not 401: the password was right. The client uses this to open the
    # verification panel instead of telling her she typed her password wrong.
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="החשבון עדיין לא אומת. שלחנו קוד לכתובת המייל שלך.",
        )

    # Create access token
    access_token = auth_service.create_access_token(user.id, user.email)
    
    logger.info(f"User {user.email} logged in successfully")
    
    return AuthResponse(
        access_token=access_token,
        user=build_user_response(user),
    )


@router.post("/signup", response_model=SignupPendingResponse)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> SignupPendingResponse:
    """Create an account and email a verification code.

    ⚠️ [024] THIS NO LONGER RETURNS A SESSION (owner ruling A4). The account
    exists but is unusable until `/verify-email` redeems the code, because an
    account nobody proved is exactly what makes the Google linking rule
    dangerous: an attacker who can pre-register victim@school.org and be
    treated as its owner is the pre-account-hijacking hole (nOAuth, 2023).

    Any client reading `access_token` from this response is out of date.
    """
    existing_user = await auth_service.get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="כתובת האימייל כבר רשומה במערכת",
        )

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

    result = await email_verification.start_or_resend(db, user, is_resend=False)
    if result.outcome is StartOutcome.SEND_FAILED:
        # The code went nowhere, so the account is unreachable. Roll the whole
        # signup back rather than leaving her with an address she can never
        # prove and an email she can never re-register.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="לא הצלחנו לשלוח את קוד האימות. אפשר לנסות שוב.",
        )

    await db.commit()
    logger.info("New user %s signed up; awaiting email verification", user.id)

    return SignupPendingResponse(email=user.email)


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Redeem a verification code. THIS is where a signup gets its session."""
    user = await auth_service.get_user_by_email(db, request.email)
    if user is None:
        # Same answer as a wrong code: distinguishing them turns this endpoint
        # into an address oracle.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="הקוד שגוי או שפג תוקפו")

    outcome = await email_verification.verify(db, user, request.code)
    await db.commit()          # the attempt counter must persist either way

    if outcome is VerifyOutcome.TOO_MANY_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="יותר מדי ניסיונות. אפשר לבקש קוד חדש.")
    if outcome is not VerifyOutcome.VERIFIED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="הקוד שגוי או שפג תוקפו")

    access_token = auth_service.create_access_token(user.id, user.email)
    return AuthResponse(access_token=access_token, user=build_user_response(user))


@router.post("/resend-code", response_model=MessageResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def resend_code(
    request: ResendCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send the pending code again.

    ALWAYS answers 202 with the same body — for an unknown address, an already
    verified one, a cooldown, or a success. Anything else makes this endpoint a
    way to ask "does this teacher have a Vivi account?", and the honest answer
    to that question is none of the caller's business.
    """
    uniform = MessageResponse(message="אם הכתובת רשומה, שלחנו אליה קוד חדש.")

    user = await auth_service.get_user_by_email(db, request.email)
    if user is None or user.email_verified_at is not None:
        return uniform

    await email_verification.start_or_resend(db, user, is_resend=True)
    await db.commit()
    return uniform


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


# =============================================================================
# Sign in with Google (owner ruling A2 — the ID-token flow)
#
# The browser gets a signed ID token from Google and posts it here; we verify it
# and mint OUR OWN session JWT. No redirect URIs, no client secret, no refresh
# tokens: the only thing Google is asked for is "who is this", and the answer is
# consumed once.
# =============================================================================

@router.get("/google/nonce", response_model=GoogleNonceResponse)
async def google_nonce(
    db: AsyncSession = Depends(get_db),
) -> GoogleNonceResponse:
    """Mint the one-shot nonce the Sign in with Google button must embed.

    Public by necessity — it is fetched before anyone is signed in — and
    harmless: a nonce authorizes nothing on its own. It is only ever meaningful
    inside a token Google signed.
    """
    nonce = await auth_nonce.issue_nonce(db)
    await db.commit()
    return GoogleNonceResponse(nonce=nonce)


@router.post("/google", response_model=AuthResponse)
async def google_sign_in(
    request: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Sign in (or sign up) with a Google ID token.

    The order below is deliberate: the nonce is spent FIRST, so a replayed
    credential is refused before we spend a network round-trip verifying a token
    we already know we will not accept.
    """
    if not await auth_nonce.consume_nonce(db, request.nonce):
        # Unknown, already spent, or expired — one answer.
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="ההתחברות פגה. אפשר לנסות שוב.")

    try:
        claims = await verify_google_credential(request.credential)
    except GoogleAuthUnavailable:
        await db.rollback()
        # OURS, not hers: 503 so nobody debugs a misconfiguration as a rejected
        # Google account.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="ההתחברות עם Google אינה זמינה כרגע.")
    except (GoogleTokenInvalid, GoogleClaimsError):
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="לא הצלחנו לאמת את החשבון מול Google.")

    by_google_id = await auth_service.get_user_by_google_id(db, claims.subject)
    by_email = await auth_service.get_user_by_email(db, claims.email)

    outcome = decide_link(
        AccountFacts(str(by_google_id.id), by_google_id.email_verified_at is not None)
        if by_google_id else None,
        AccountFacts(str(by_email.id), by_email.email_verified_at is not None)
        if by_email else None,
    )

    if outcome is LinkOutcome.REFUSE_UNVERIFIED_EMAIL:
        # THE nOAuth GUARD. An account holds this address but never proved it,
        # so it may have been registered BY someone else in her name. Linking
        # here would hand that someone her Google identity.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="כבר קיים חשבון עם הכתובת הזאת שלא אומת. "
                   "יש לאמת אותו במייל לפני חיבור חשבון Google.",
        )

    if outcome is LinkOutcome.SIGN_IN_EXISTING_GOOGLE:
        user = by_google_id
    elif outcome is LinkOutcome.LINK_TO_VERIFIED_EMAIL:
        user = by_email
        user.google_id = claims.subject
        logger.info("linked Google identity to verified account %s", user.id)
    else:
        user = await auth_service.create_google_user(
            db=db,
            email=claims.email,
            google_id=claims.subject,
            full_name=claims.full_name or claims.email.split("@")[0],
        )
        logger.info("created account %s from Google sign-in", user.id)

    await db.commit()

    access_token = auth_service.create_access_token(user.id, user.email)
    return AuthResponse(access_token=access_token, user=build_user_response(user))
