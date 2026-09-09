"""
Authentication service with JWT token management.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models.user import User, SubscriptionStatus
from ..config import settings


# JWT Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days


class AuthService:
    """Service for authentication operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    
    @staticmethod
    def create_access_token(user_id: UUID, email: str, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email address with eager loading of relationships.

        `User.schools` is eager-loaded for the same reason `subject_matters` is:
        build_user_response touches it, and an async lazy load at that point
        raises MissingGreenlet — a 500 AFTER authentication already succeeded,
        which is the exact shape of the 2026-08-17 timestamp incident.
        """
        query = select(User).where(User.email == email).options(
            selectinload(User.subject_matters),
            selectinload(User.schools),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get a user by ID with eager loading of relationships.

        See get_user_by_email: `User.schools` must be eager — this is the loader
        behind get_current_user, so EVERY authenticated request builds a profile
        response from it.
        """
        query = select(User).where(User.id == user_id).options(
            selectinload(User.subject_matters),
            selectinload(User.schools),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_google_id(db: AsyncSession, google_id: str) -> Optional[User]:
        """Look a user up by the Google ID token's `sub`.

        `sub` is THE identity for a Google account — unique across all Google
        accounts and never reused — whereas the email on that account can
        change. Eager-loads the same collections as the other loaders so the
        profile response never triggers an async lazy load.
        """
        query = select(User).where(User.google_id == google_id).options(
            selectinload(User.subject_matters),
            selectinload(User.schools),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_google_user(
        db: AsyncSession,
        email: str,
        google_id: str,
        full_name: str,
    ) -> User:
        """Create an account from a verified Google identity.

        `password_hash` stays NULL — there is no password, and
        `authenticate_user` already refuses to log in a row without one, so
        this account can only ever be entered through Google.

        `email_verified_at` is stamped at creation: Google proved the address,
        and `GoogleClaims` refused the token unless `email_verified` was true.

        Does not commit; the caller owns the transaction (unlike `create_user`,
        which predates that convention).
        """
        user = User(
            email=email,
            password_hash=None,
            google_id=google_id,
            full_name=full_name,
            subscription_status=SubscriptionStatus.trial,
            started_trial_at=datetime.utcnow(),
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user, attribute_names=["subject_matters", "schools"])
        return user

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        password: str,
        full_name: str,
    ) -> User:
        """Create a new user."""
        hashed_password = AuthService.hash_password(password)
        
        user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
            subscription_status=SubscriptionStatus.trial,
            started_trial_at=datetime.utcnow(),
        )
        
        db.add(user)
        # [024] FLUSH, not commit. Signup is now ONE transaction: the user row
        # and the verification code land together, or neither does. It used to
        # commit here, which would have left an un-rollback-able account behind
        # whenever the code email failed to send — a teacher stuck with an
        # address she can neither use nor re-register. Its single caller
        # (auth.signup) owns the commit.
        await db.flush()
        # BOTH collections, because signup answers with build_user_response(user)
        # on THIS object: an unloaded collection there is an async lazy load
        # (MissingGreenlet) at the end of a successful signup.
        await db.refresh(user, attribute_names=["subject_matters", "schools"])

        return user
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = await AuthService.get_user_by_email(db, email)
        
        if not user:
            return None
        
        if not user.password_hash:
            # User uses Google auth, cannot login with password
            return None
        
        if not AuthService.verify_password(password, user.password_hash):
            return None
        
        return user


# Singleton instance
auth_service = AuthService()







