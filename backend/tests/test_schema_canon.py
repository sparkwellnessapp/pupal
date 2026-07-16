"""
Schema-canon guards: create_all must not run outside development, and the
applied-migration ledger must be checked (loudly) at every boot.

These lock in the two failures that actually fired during the PR-1 deploy:
  * a NEW ORM model got a BARE create_all table in prod (no CHECKs, no indexes)
  * migration 011 was PARTIALLY applied and nobody noticed for weeks

No live DDL: the engine is faked so these run anywhere.
"""
import logging
from types import SimpleNamespace

import pytest

from app import database
from app.database import (
    EXPECTED_MIGRATIONS,
    _is_dev_env,
    init_db,
    verify_schema_head,
)


# --- fake engine -------------------------------------------------------------

class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def all(self):
        return [(v,) for v in self._value]


class _FakeConn:
    """Answers the two queries verify_schema_head issues, in order."""

    def __init__(self, ledger_exists, applied, raises=False):
        self._ledger_exists = ledger_exists
        self._applied = applied
        self._raises = raises
        self.create_all_ran = False

    async def __aenter__(self):
        if self._raises:
            raise RuntimeError("connection refused")
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, *a, **kw):
        sql = str(stmt)
        if "information_schema.tables" in sql:
            return _FakeResult(self._ledger_exists)
        return _FakeResult(self._applied)

    async def run_sync(self, fn):
        self.create_all_ran = True

    async def commit(self):
        pass


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return self._conn


@pytest.fixture
def fake_db(monkeypatch):
    def _install(ledger_exists=True, applied=None, raises=False):
        applied = list(EXPECTED_MIGRATIONS) if applied is None else applied
        conn = _FakeConn(ledger_exists, applied, raises)
        monkeypatch.setattr(database, "engine", _FakeEngine(conn))
        return conn
    return _install


def _set_env(monkeypatch, env):
    monkeypatch.setattr(database.settings, "app_env", env)


# --- env gate ----------------------------------------------------------------

@pytest.mark.parametrize("env", ["development", "dev", "local", "test", "DEVELOPMENT"])
def test_dev_envs_are_dev(monkeypatch, env):
    _set_env(monkeypatch, env)
    assert _is_dev_env() is True


@pytest.mark.parametrize("env", ["production", "prod", "staging", "", "  ", "PRODUCTION", "whatever"])
def test_everything_else_is_not_dev_fail_closed(monkeypatch, env):
    """Unknown/unset APP_ENV must NOT be treated as dev — never auto-DDL by accident."""
    _set_env(monkeypatch, env)
    assert _is_dev_env() is False


@pytest.mark.asyncio
async def test_init_db_skips_create_all_in_production(monkeypatch, fake_db):
    """THE footgun: a new ORM model must never get a bare auto-created table in prod."""
    _set_env(monkeypatch, "production")
    conn = fake_db()
    await init_db()
    assert conn.create_all_ran is False


@pytest.mark.asyncio
async def test_init_db_runs_create_all_on_a_fresh_dev_database(monkeypatch, fake_db):
    """Dev bootstrap keeps working — a fresh local DB (no ledger) still comes up."""
    _set_env(monkeypatch, "development")
    conn = fake_db(ledger_exists=False)
    await init_db()
    assert conn.create_all_ran is True


@pytest.mark.asyncio
async def test_dev_env_pointed_at_a_migration_managed_db_does_not_create_all(
    monkeypatch, fake_db
):
    """
    The hole an APP_ENV-only gate leaves open, and the reason _should_bootstrap
    also checks the ledger.

    A developer's .env routinely carries APP_ENV=development together with the
    LIVE DATABASE_URL — that is exactly how this repo's integration tests run.
    An APP_ENV-only gate would happily create_all the PRODUCTION database from a
    laptop. The ledger's presence is a property of the DATABASE, not of the
    process's opinion about itself, so it wins.
    """
    _set_env(monkeypatch, "development")
    conn = fake_db(ledger_exists=True, applied=list(EXPECTED_MIGRATIONS))
    await init_db()
    assert conn.create_all_ran is False


@pytest.mark.asyncio
async def test_unreadable_ledger_does_not_create_all(monkeypatch, fake_db):
    """Can't prove the DB is unmanaged ⇒ don't touch it."""
    _set_env(monkeypatch, "development")
    conn = fake_db(raises=True)
    await init_db()
    assert conn.create_all_ran is False


# --- head check --------------------------------------------------------------

@pytest.mark.asyncio
async def test_head_ok_when_ledger_matches(monkeypatch, fake_db, caplog):
    _set_env(monkeypatch, "production")
    fake_db(applied=list(EXPECTED_MIGRATIONS))
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is True
    assert "SCHEMA OK" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_partially_applied_migration_is_a_gap_not_a_head_regression(
    monkeypatch, fake_db, caplog
):
    """
    The 011 case, exactly. 011's commit token is absent (it half-applied) while
    012 and 013 landed after it.

    A `MAX(version)` head check would read 013, compare it to expected head 013,
    and report ALL CLEAR. Only the set difference catches the hole.
    """
    _set_env(monkeypatch, "production")
    applied = [v for v in EXPECTED_MIGRATIONS if v != "011"]
    fake_db(applied=applied)

    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "a missing migration must be logged at ERROR"
    assert "011" in caplog.text
    assert "NOT APPLIED" in caplog.text
    # and the naive check would NOT have caught it:
    assert max(applied) == EXPECTED_MIGRATIONS[-1]


@pytest.mark.asyncio
async def test_missing_ledger_is_an_error_in_production(monkeypatch, fake_db, caplog):
    _set_env(monkeypatch, "production")
    fake_db(ledger_exists=False)
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert "MISSING" in caplog.text


@pytest.mark.asyncio
async def test_missing_ledger_is_only_a_warning_in_development(monkeypatch, fake_db, caplog):
    """A fresh create_all-bootstrapped dev DB has no ledger. That's fine, not an alarm."""
    _set_env(monkeypatch, "development")
    fake_db(ledger_exists=False)
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


@pytest.mark.asyncio
async def test_db_ahead_of_code_warns_but_does_not_error(monkeypatch, fake_db, caplog):
    """Rolled-back deploy: DB has migrations this code doesn't know about. Not fatal."""
    _set_env(monkeypatch, "production")
    fake_db(applied=list(EXPECTED_MIGRATIONS) + ["014"])
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert "014" in caplog.text


@pytest.mark.asyncio
async def test_head_check_never_crashes_the_app(monkeypatch, fake_db, caplog):
    """
    A deploy landing mid-migration-window must still boot and still serve /health.
    The alarm is a log line, never an exception.
    """
    _set_env(monkeypatch, "production")
    fake_db(raises=True)
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False   # must not raise
    assert "head check failed to run" in caplog.text


@pytest.mark.asyncio
async def test_init_db_does_not_propagate_check_failure(monkeypatch, fake_db):
    _set_env(monkeypatch, "production")
    fake_db(raises=True)
    await init_db()   # must not raise


# --- the protocol itself -----------------------------------------------------

def test_expected_migrations_matches_migration_files_on_disk():
    """
    The one rule: add a migration file, add its version to EXPECTED_MIGRATIONS.
    This test is what makes forgetting impossible.
    """
    from pathlib import Path

    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    on_disk = sorted(
        p.name.split("_")[0]
        for p in migrations_dir.glob("*.sql")
    )
    assert on_disk == sorted(EXPECTED_MIGRATIONS), (
        "backend/migrations/ and EXPECTED_MIGRATIONS in app/database.py disagree. "
        "Every migration file must be listed (and vice versa)."
    )


def test_every_migration_ends_with_its_commit_token():
    """
    The commit-token convention: a migration's INSERT into schema_migrations must
    be its LAST statement, so partial application leaves no row and the gap check
    above can see it. Enforced from 013 forward (001-012 were backfilled).
    """
    from pathlib import Path

    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    offenders = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.name.split("_")[0]
        if version < "013":
            continue  # backfilled by 013; they predate the convention
        body = path.read_text(encoding="utf-8")
        # strip trailing comments/blank lines, then look at the last statement
        code = "\n".join(
            line for line in body.splitlines() if not line.strip().startswith("--")
        )
        statements = [s.strip() for s in code.split(";") if s.strip()]
        tail = " ".join(statements[-2:]).lower()  # allow a trailing COMMIT
        if "insert into public.schema_migrations" not in tail or f"'{version}'" not in tail:
            offenders.append(path.name)

    assert not offenders, (
        f"these migrations do not end with their own commit token: {offenders}. "
        "Every migration must finish with: INSERT INTO public.schema_migrations "
        "(version, note) VALUES ('<version>', '...') ON CONFLICT DO NOTHING;"
    )
