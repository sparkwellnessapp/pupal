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
    pool_recycle=1800,  # Recycle connections every 30 mins
    pool_timeout=30,    # Wait up to 30s for a connection
    connect_args={
        "statement_cache_size": 0,
    },
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
    try:
        from .models import grading, rubric_share  # noqa: F401
        async with engine.connect() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")



async def close_db():
    """
    Close database connections.
    Called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")
