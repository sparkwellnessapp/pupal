"""
Schema-canon guards: create_all must not run outside development, and the
applied-migration ledger must be checked (loudly) at every boot.

These lock in the three failures that actually fired:
  * a NEW ORM model got a BARE create_all table in prod (no CHECKs, no indexes)
  * migration 011 was PARTIALLY applied and nobody noticed for weeks
  * migration 010's DEFERRABLE attribute silently reverted on dev while the
    ledger stayed green — the whole revision feature broke with zero alarms
    (2026-08-17; hence the constraint-ATTRIBUTE pass in verify_schema_head)

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


class _FakeRows:
    """Raw multi-column rows (the pg_constraint attribute query)."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeConn:
    """Answers the FOUR queries verify_schema_head issues (ledger-exists,
    ledger-rows, pg_constraint, pg_indexes). A double that silently returns
    the wrong SHAPE for an unrecognised query is worse than one that fails:
    when the partial-index pass was added, the unmatched query fell through
    to the ledger branch and every caller blew up on `tuple index out of
    range` — a real signal, but pointing at the double, not the code."""

    def __init__(self, ledger_exists, applied, raises=False, constraint_rows=None,
                 index_rows=None):
        self._ledger_exists = ledger_exists
        self._applied = applied
        self._raises = raises
        # Default: healthy — every expected constraint present with the
        # expected attributes, so ledger-focused tests stay about the ledger.
        self._constraint_rows = (
            constraint_rows if constraint_rows is not None
            else [
                (name, want_deferrable, want_deferred)
                for name, (want_deferrable, want_deferred, _m)
                in database.EXPECTED_CONSTRAINT_ATTRIBUTES.items()
            ]
        )
        # Same idea for the partial-index pass (closeout/A2): healthy by
        # default, with each index's REAL predicate embedded, so ledger- and
        # constraint-focused tests stay about their own subject.
        self._index_rows = (
            index_rows if index_rows is not None
            else [
                (name, f"CREATE UNIQUE INDEX {name} ON public.t USING btree (c) {fragment.upper()}")
                for name, (fragment, _m) in database.EXPECTED_PARTIAL_INDEXES.items()
            ]
        )
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
        if "pg_constraint" in sql:
            return _FakeRows(self._constraint_rows)
        if "pg_indexes" in sql:
            return _FakeRows(self._index_rows)
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
    def _install(ledger_exists=True, applied=None, raises=False, constraint_rows=None,
                 index_rows=None):
        applied = list(EXPECTED_MIGRATIONS) if applied is None else applied
        conn = _FakeConn(ledger_exists, applied, raises, constraint_rows, index_rows)
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
async def test_half_applied_constraint_attribute_is_loud(monkeypatch, fake_db, caplog):
    """
    The 010 case, exactly (2026-08-17): the ledger lists the migration, but the
    constraint's deferrability silently reverted (a create_all-recreated table
    or a half-applied file). The version check alone stayed green while the
    whole revision feature was broken — the attribute pass must alarm and
    name the migration to re-apply.
    """
    _set_env(monkeypatch, "production")
    fake_db(
        applied=list(EXPECTED_MIGRATIONS),
        constraint_rows=[("graded_tests_regraded_to_id_fkey", False, False)],
    )
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False
    assert "constraint-attribute" in caplog.text
    assert "010" in caplog.text
    assert "SCHEMA OK" not in caplog.text


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
    """Rolled-back deploy: DB has migrations this code doesn't know about. Not fatal.

    The "unknown" version is computed from the expected head, not hardcoded —
    a literal next-version goes stale the moment that migration becomes real
    (a hardcoded "014" broke here when migration 014 shipped).
    """
    _set_env(monkeypatch, "production")
    ahead = f"{int(EXPECTED_MIGRATIONS[-1]) + 1:03d}"
    fake_db(applied=list(EXPECTED_MIGRATIONS) + [ahead])
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is False
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert ahead in caplog.text


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


# ---------------------------------------------------------------------------
# Partial-index pass inside verify_schema_head (closeout/A2). The ledger and
# the constraint reader are BOTH blind to these: 017's index is B9's
# idempotency guarantee and lives in pg_index, not pg_constraint.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_partial_index_fails_the_head_check_loudly(monkeypatch, fake_db, caplog):
    _set_env(monkeypatch, "production")
    fake_db(applied=list(EXPECTED_MIGRATIONS), index_rows=[])   # ledger green, index gone
    with caplog.at_level(logging.ERROR, logger="app.database"):
        assert await verify_schema_head() is False
    blob = caplog.text
    assert "partial-index problem" in blob
    assert "invisible to BOTH the ledger and the constraint check" in blob


@pytest.mark.asyncio
async def test_index_present_but_predicate_stripped_is_caught(monkeypatch, fake_db, caplog):
    """The dangerous shape: right name, wrong guarantee. A presence-only check
    would pass while (batch_id, client_file_id) uniqueness silently covered
    every row including the pre-017 NULLs the predicate exists to exclude."""
    _set_env(monkeypatch, "production")
    stripped = [
        (name, f"CREATE UNIQUE INDEX {name} ON public.t USING btree (c)")   # no WHERE
        for name in database.EXPECTED_PARTIAL_INDEXES
    ]
    fake_db(applied=list(EXPECTED_MIGRATIONS), index_rows=stripped)
    with caplog.at_level(logging.ERROR, logger="app.database"):
        assert await verify_schema_head() is False
    assert "lacks" in caplog.text


@pytest.mark.asyncio
async def test_healthy_schema_logs_its_own_coverage(monkeypatch, fake_db, caplog):
    """Owner ruling: the checker states what it can and cannot see, so the
    next blind spot is documented rather than discovered."""
    _set_env(monkeypatch, "production")
    fake_db(applied=list(EXPECTED_MIGRATIONS))
    with caplog.at_level(logging.INFO, logger="app.database"):
        assert await verify_schema_head() is True
    assert "partial index(es) verified" in caplog.text
    assert "NOT covered" in caplog.text
