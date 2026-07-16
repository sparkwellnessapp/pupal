"""
Database configuration for Supabase/PostgreSQL.
Uses SQLAlchemy async for database operations.
"""
import logging
from sqlalchemy import text
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


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_context():
    """
    Context manager for getting a database session outside of FastAPI.
    
    Use this in background tasks or other async code that needs
    a database session but isn't a FastAPI endpoint.
    
    Example:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# -----------------------------------------------------------------------------
# Schema canon
# -----------------------------------------------------------------------------
# The SQL files in backend/migrations/ are the ONLY source of DDL truth outside
# development. Every migration ends by INSERTing its version into
# schema_migrations as its LAST statement, so that row is a commit token: a
# partially-applied migration leaves no token and shows up here as a gap.
#
# When you add a migration, add its version here. That is the whole protocol.
EXPECTED_MIGRATIONS = (
    "001", "002", "003", "004", "005", "006", "007",
    "008", "009", "010", "011", "012", "013",
)

# create_all() is a DEVELOPMENT BOOTSTRAP ONLY. Anywhere else it is a footgun:
# it silently creates BARE tables for new ORM models — no CHECK constraints, no
# partial indexes, no ALTERs to existing tables — which then masquerade as
# migrated ones. It did exactly that to rubric_extraction_jobs during the PR-1
# deploy. Unknown/unset APP_ENV is treated as production (fail closed: never
# auto-DDL unless someone explicitly said "development").
_DEV_ENVS = frozenset({"development", "dev", "local", "test", "testing"})


def _is_dev_env() -> bool:
    return settings.app_env.strip().lower() in _DEV_ENVS


async def _read_ledger():
    """Returns (ledger_exists, applied_versions). Raises on connection failure."""
    async with engine.connect() as conn:
        exists = (await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'schema_migrations')"
        ))).scalar()
        if not exists:
            return False, set()
        applied = {
            row[0] for row in
            (await conn.execute(text("SELECT version FROM public.schema_migrations"))).all()
        }
        return True, applied


async def verify_schema_head() -> bool:
    """
    Compare the applied-migration ledger against EXPECTED_MIGRATIONS and log
    loudly on any mismatch. Returns True if the schema is at the expected head.

    Deliberately NEVER raises and never crashes the app: a deploy that lands
    mid-migration-window must still boot (and still serve /health) so the
    operator can finish applying migrations. The point is to turn "partially
    applied migration" from a forensic discovery months later into a first-boot
    alarm.
    """
    try:
        ledger_exists, applied = await _read_ledger()

        if not ledger_exists:
            if _is_dev_env():
                logger.warning(
                    "SCHEMA: no schema_migrations ledger (fresh dev database). "
                    "Apply migrations/013_schema_migrations_ledger.sql to enable head checks."
                )
            else:
                logger.error(
                    "SCHEMA MISMATCH: schema_migrations ledger is MISSING outside development. "
                    "This database's DDL provenance is unknown. Apply "
                    "migrations/013_schema_migrations_ledger.sql."
                )
            return False

        expected = set(EXPECTED_MIGRATIONS)
        missing = sorted(expected - applied)   # code expects DDL the DB doesn't have
        unknown = sorted(applied - expected)   # DB has DDL this code doesn't know about

        if not missing and not unknown:
            logger.info(
                "SCHEMA OK: migration head %s (%d applied)",
                EXPECTED_MIGRATIONS[-1], len(applied),
            )
            return True

        # Missing is the dangerous direction: the running code assumes columns,
        # constraints and indexes that may not exist. This is the 011 alarm.
        if missing:
            logger.error(
                "SCHEMA MISMATCH: %d migration(s) NOT APPLIED: %s. Expected head %s, "
                "DB head %s. The running code assumes DDL this database does not have "
                "(a partially-applied migration leaves no commit-token row). "
                "Apply the missing migrations from backend/migrations/.",
                len(missing), ", ".join(missing), EXPECTED_MIGRATIONS[-1],
                max(applied) if applied else "(none)",
            )
        # Unknown is usually a rollback deploy: DB ahead of code. Not fatal.
        if unknown:
            logger.warning(
                "SCHEMA: database has %d migration(s) this code does not know about: %s. "
                "Likely a rolled-back deploy (DB ahead of code).",
                len(unknown), ", ".join(unknown),
            )
        return False

    except Exception as e:
        # Never let the schema check itself take the service down.
        logger.error("SCHEMA: head check failed to run: %s", e)
        return False


async def _should_bootstrap() -> bool:
    """
    create_all() is allowed ONLY for a fresh development database — one that is
    NOT under migration management.

    Two independent conditions, both required:

      1. APP_ENV is a dev env. (Unset/unknown ⇒ production ⇒ no.)
      2. The target database has no schema_migrations ledger.

    (2) is the load-bearing one. Gating on APP_ENV alone does NOT protect
    production, because a developer's .env routinely carries APP_ENV=development
    AND the live DATABASE_URL (that is how this repo's integration tests run).
    Under an APP_ENV-only gate, that boot would still create_all the PRODUCTION
    database — the exact footgun we are closing. The ledger's presence says "this
    database is owned by migrations", which is a property of the DATABASE, not of
    the process's opinion about itself. Migrations own it; hands off.
    """
    if not _is_dev_env():
        logger.info(
            "create_all SKIPPED (APP_ENV=%s): migrations are the only DDL source "
            "outside development.", settings.app_env,
        )
        return False
    try:
        ledger_exists, _ = await _read_ledger()
    except Exception as e:
        # Can't prove the DB is unmanaged ⇒ don't touch it.
        logger.error("create_all SKIPPED: could not read the migration ledger: %s", e)
        return False

    if ledger_exists:
        logger.info(
            "create_all SKIPPED: this database is migration-managed (schema_migrations "
            "present), even though APP_ENV=%s. Apply migrations to change its schema.",
            settings.app_env,
        )
        return False
    return True


async def init_db():
    """
    Startup DDL bootstrap + schema verification.

    Fresh dev database: create_all() so a new local setup works out of the box.
    Migration-managed database (any env): create_all is skipped entirely.
    Always: verify the applied-migration ledger and shout if it doesn't match.
    """
    if await _should_bootstrap():
        try:
            from .models import grading, rubric_share  # noqa: F401
            async with engine.connect() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.commit()
            logger.info(
                "Database bootstrapped via create_all (fresh development database). "
                "Apply backend/migrations/*.sql to bring it under migration management."
            )
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    await verify_schema_head()



async def close_db():
    """
    Close database connections.
    Called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")
