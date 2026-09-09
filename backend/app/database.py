"""
Database configuration for Supabase/PostgreSQL.
Uses SQLAlchemy async for database operations.
"""
import logging
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import settings

logger = logging.getLogger(__name__)

# Create async engine for PostgreSQL (Supabase)
# NullPool closes every connection when it is returned. Under test that is the
# point: a pooled connection that survives the test is still registered with the
# Windows proactor when the lifespan closes the loop, and teardown hangs there
# with every test already green. Production keeps the QueuePool.
_pool_kwargs = (
    {"poolclass": NullPool}                      # sizing kwargs are invalid here
    if settings.db_disable_pooling else
    {"pool_size": 5, "max_overflow": 10, "pool_timeout": 30}
)

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
    pool_recycle=1800,  # Recycle connections every 30 mins
    connect_args={
        "statement_cache_size": 0,
    },
    **_pool_kwargs,
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


async def _dispose_session(session: AsyncSession, where: str) -> None:
    """
    Close a session whose connection may already be dead.

    Supabase's transaction pooler resets connections left idle-in-transaction
    (observed 2026-08-07: a request session held across BackgroundTasks got a
    TCP RST; close() then raised ConnectionDoesNotExistError and detonated the
    ASGI stack AFTER the response was sent). By teardown time the transaction
    died with the connection — nothing real is lost — so: log loudly,
    invalidate so the pool discards the dead connection, never raise.
    """
    try:
        await session.close()
    except Exception:
        logger.warning(
            "%s: session.close() failed (connection likely reset by the "
            "server) — invalidating the dead connection", where, exc_info=True,
        )
        try:
            await session.invalidate()
        except Exception:
            # invalidate() is the cleanup of the cleanup; the failure above is
            # already logged and the pool will pre-ping this connection away.
            pass


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI endpoints to get a database session.
    Yields an async session and ensures it's closed after use.

    NOTE (2026-08-07): FastAPI runs BackgroundTasks INSIDE the dependency
    AsyncExitStack, so this teardown fires only after all of a request's
    background tasks finish. Endpoints that queue long background work must
    `await db.close()` themselves after their final commit (idempotent — this
    teardown then no-ops) so the connection isn't held idle for minutes.

    The session is managed manually (no `async with`) so the ONLY close path
    is _dispose_session — `async with` would close() a second time on exit,
    outside the dead-connection guard.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await _dispose_session(session, "get_db teardown")


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

    Managed manually (no `async with AsyncSessionLocal()`) for the same
    single-close-path reason as get_db.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        # Preserve the ORIGINAL exception: rollback() on a connection the
        # server already reset raises too, and an unguarded rollback here
        # would re-raise THAT — masking the commit failure the caller
        # (e.g. batch_transcription_failed logging) needs to see.
        try:
            await session.rollback()
        except Exception:
            logger.warning(
                "get_db_context: rollback failed (connection likely reset) "
                "— invalidating; the original exception propagates",
                exc_info=True,
            )
            try:
                await session.invalidate()
            except Exception:
                pass
        raise
    finally:
        await _dispose_session(session, "get_db_context teardown")


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
    "008", "009", "010", "011", "012", "013", "014", "015", "016", "017",
    "018", "019", "020", "021", "022", "023", "024", "025", "026", "027",
    "028", "029",
)

# Attribute-level invariants the version ledger CANNOT see (the 010 lesson,
# 2026-08-17): a ledger row proves the migration RAN once in this database's
# history — not that its DDL survived. A create_all-recreated table (or a
# half-applied file) silently reverts attributes like a constraint's
# deferrability while the version check stays green; that exact shape broke
# the entire revision feature (extend_chain's link-R1→flush→insert-R2 order)
# on the dev DB with zero alarms. name → (condeferrable, condeferred, owner).
EXPECTED_CONSTRAINT_ATTRIBUTES: dict = {
    "graded_tests_regraded_to_id_fkey": (True, True, "010"),
}

# Partial unique INDEXES are invisible to the block above: they live in
# pg_index/pg_class, never in pg_constraint, so no constraint reader can ever
# see them no matter how many names it is given (closeout/A2). They carry
# guarantees the product depends on — 017's index IS B9's idempotency
# promise, and the one-leaf indexes are RGC-1 and the extraction-job
# uniqueness rule. name → (expected_indexdef_fragment, owning migration).
# The fragment is matched case-insensitively against pg_indexes.indexdef, so
# it pins the WHERE clause too — a partial index silently recreated without
# its predicate would still be "present" by name while guaranteeing nothing.
# NB: every name here was read off the migration file that creates it, not
# recalled — a wrong name in this table is a FALSE ALARM, which trains
# dismissal exactly as effectively as a missed one does (closeout: the first
# draft of this table guessed `idx_transcription_jobs_client_file_id` and
# reported B9's guarantee missing on a healthy database).
EXPECTED_PARTIAL_INDEXES: dict = {
    # 017 line 17: composite (batch_id, client_file_id) — the same
    # client_file_id may legitimately recur across DIFFERENT batches.
    "idx_transcription_jobs_batch_client_file": (
        "where (client_file_id is not null)", "017",
    ),
    "idx_graded_tests_one_leaf_per_chain": (
        "where (regraded_to_id is null)", "008",
    ),
    "idx_extraction_jobs_one_active_per_source": (
        "where", "012",
    ),
    # 023 line 30: institution identity is unique only AMONG the rows that have
    # a symbol — a free-text school has none and many such rows coexist. Without
    # the predicate this index would forbid the second symbol-less school.
    "idx_schools_ministry_symbol": (
        "where (ministry_symbol is not null)", "023",
    ),
    # 023's OTHER half, and the one whose predicate is easy to lose: the name
    # rule now governs ONLY the symbol-less rows. Recreated without the WHERE it
    # would again forbid two same-named institutions — the exact case 023 was
    # written to allow — while still being "present" by name.
    "idx_schools_normalized_name_symbolless": (
        "where (ministry_symbol is null)", "023",
    ),
    # 024: exactly one LIVE verification code per user. Without the predicate
    # this index would forbid a second code for a user who already verified
    # once — i.e. it would break every re-verification — while still being
    # "present" by name. The predicate IS the rule.
    "idx_email_codes_one_active_per_user": (
        "where (consumed_at is null)", "024",
    ),
    # 026 line 60: exactly one LIVE plan (queued/building/ready) per contract
    # hash. failed and superseded rows are history and coexist; without the
    # predicate a rebuild after a failure would be impossible while the index
    # was still "present" by name. The predicate IS the append-only rule.
    # 028: the re-ask candidate set. WITHOUT the predicate this index would
    # cover every user row — including everyone who gave a date and everyone
    # who never answered — while still being "present" by name, so the
    # candidate query would silently scan the whole table.
    "idx_users_reask_candidates": (
        "where (next_exam_date is null)", "028",
    ),
    "idx_grading_plans_one_live_per_contract": (
        "where (status = any", "026",
    ),
}

# WHAT verify_schema_head CAN AND CANNOT SEE — stated, so the next blind spot
# is documented rather than discovered (owner ruling, closeout/A2):
#   CAN:    applied-migration versions (the ledger, set-compared)
#           constraint deferrability (EXPECTED_CONSTRAINT_ATTRIBUTES)
#           partial-index presence + predicate (EXPECTED_PARTIAL_INDEXES)
#   CANNOT: CHECK-constraint EXPRESSIONS (only a constraint's existence via
#           the attribute table, and only if listed there)
#           column types, nullability, defaults
#           trigger/function bodies
#           row-level security policies
#           anything in a schema other than the connection's search_path
# Extending coverage = add a reader + an expectation table + a line here.
SCHEMA_CHECK_COVERAGE = (
    "migration-version ledger; constraint deferrability; partial-index "
    "presence and predicate. NOT covered: CHECK expressions, column "
    "types/nullability/defaults, triggers, RLS policies."
)


def _partial_index_problems(rows, expected=None) -> list:
    """Pure comparator: pg_indexes rows (indexname, indexdef) vs the expected
    partial-index table. Returns human-readable problems; [] = all verified."""
    expected = EXPECTED_PARTIAL_INDEXES if expected is None else expected
    by_name = {name: (indexdef or "") for name, indexdef in rows}
    problems: list = []
    for name, (want_fragment, migration) in expected.items():
        got = by_name.get(name)
        if got is None:
            problems.append(
                f"partial index {name} is MISSING "
                f"(migration {migration} half-applied? re-apply it)"
            )
        elif want_fragment.lower() not in got.lower():
            problems.append(
                f"partial index {name} exists but its definition lacks "
                f"'{want_fragment}' (got: {got}) — recreated without its "
                f"predicate; migration {migration} must be re-applied"
            )
    return problems


async def _read_partial_indexes(names) -> list:
    """(indexname, indexdef) for the named indexes."""
    if not names:
        return []
    from sqlalchemy import bindparam
    stmt = text(
        "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN :names"
    ).bindparams(bindparam("names", expanding=True))
    async with engine.connect() as conn:
        rows = (await conn.execute(stmt, {"names": list(names)})).all()
    return [(r[0], r[1]) for r in rows]


def _constraint_attribute_problems(rows, expected=None) -> list:
    """Pure comparator (zero-mock-testable): pg_constraint rows
    (conname, condeferrable, condeferred) vs the expected attribute table.
    Returns human-readable problem strings; [] = all verified."""
    expected = EXPECTED_CONSTRAINT_ATTRIBUTES if expected is None else expected
    by_name = {name: (deferrable, deferred) for name, deferrable, deferred in rows}
    problems: list = []
    for name, (want_deferrable, want_deferred, migration) in expected.items():
        got = by_name.get(name)
        if got is None:
            problems.append(
                f"constraint {name} is MISSING "
                f"(migration {migration} half-applied? re-apply it)"
            )
        elif got != (want_deferrable, want_deferred):
            problems.append(
                f"constraint {name} exists but condeferrable={got[0]}, "
                f"condeferred={got[1]} (expected {want_deferrable}/{want_deferred}) "
                f"— migration {migration} half-applied; re-apply it"
            )
    return problems


async def _read_constraint_attributes(names) -> list:
    """(conname, condeferrable, condeferred) for the named constraints."""
    if not names:
        return []
    from sqlalchemy import bindparam
    stmt = text(
        "SELECT conname, condeferrable, condeferred FROM pg_constraint "
        "WHERE conname IN :names"
    ).bindparams(bindparam("names", expanding=True))
    async with engine.connect() as conn:
        rows = (await conn.execute(stmt, {"names": list(names)})).all()
    return [(r[0], bool(r[1]), bool(r[2])) for r in rows]

# create_all() is a DEVELOPMENT BOOTSTRAP ONLY. Anywhere else it is a footgun:
# it silently creates BARE tables for new ORM models — no CHECK constraints, no
# partial indexes, no ALTERs to existing tables — which then masquerade as
# migrated ones. It did exactly that to rubric_extraction_jobs during the PR-1
# deploy. Unknown/unset APP_ENV is treated as production (fail closed: never
# auto-DDL unless someone explicitly said "development").
# One definition, shared with main.py's docs gate (closeout): app.config.
# Kept as a module-level alias so this file's existing callers and tests are
# untouched, but there is exactly ONE answer to "what counts as dev".
from .config import DEV_ENVS as _DEV_ENVS, is_dev_env as _is_dev_env  # noqa: E402


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

        # Attribute-level pass: the ledger can't see a constraint whose
        # attributes silently reverted (see EXPECTED_CONSTRAINT_ATTRIBUTES).
        attr_problems = _constraint_attribute_problems(
            await _read_constraint_attributes(tuple(EXPECTED_CONSTRAINT_ATTRIBUTES))
        )
        # Index pass (closeout/A2): partial unique indexes are NOT constraints
        # and the reader above is structurally blind to them — 017's index is
        # B9's idempotency guarantee, so it gets its own reader.
        index_problems = _partial_index_problems(
            await _read_partial_indexes(tuple(EXPECTED_PARTIAL_INDEXES))
        )

        if not missing and not unknown and not attr_problems and not index_problems:
            logger.info(
                "SCHEMA OK: migration head %s (%d applied; %d constraint "
                "attribute(s) + %d partial index(es) verified). Coverage: %s",
                EXPECTED_MIGRATIONS[-1], len(applied),
                len(EXPECTED_CONSTRAINT_ATTRIBUTES), len(EXPECTED_PARTIAL_INDEXES),
                SCHEMA_CHECK_COVERAGE,
            )
            return True

        if attr_problems:
            logger.error(
                "SCHEMA MISMATCH: %d constraint-attribute problem(s): %s. "
                "The version ledger cannot see these — re-apply the named "
                "migration(s) from backend/migrations/.",
                len(attr_problems), "; ".join(attr_problems),
            )
        if index_problems:
            logger.error(
                "SCHEMA MISMATCH: %d partial-index problem(s): %s. "
                "These are invisible to BOTH the ledger and the constraint "
                "check — re-apply the named migration(s).",
                len(index_problems), "; ".join(index_problems),
            )

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
