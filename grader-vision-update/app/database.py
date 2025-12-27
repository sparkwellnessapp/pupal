"""
Database configuration for Supabase/PostgreSQL.
Uses SQLAlchemy async for database operations.
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import settings

logger = logging.getLogger(__name__)

# Create async engine for PostgreSQL (Supabase)
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for all models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI endpoints to get a database session.
    Yields an async session and ensures it's closed after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Initialize the database by creating all tables.
    Called on application startup.
    """
    async with engine.begin() as conn:
        # Import models to ensure they're registered with Base
        from .models import grading  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified successfully")


async def close_db():
    """
    Close database connections.
    Called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")
