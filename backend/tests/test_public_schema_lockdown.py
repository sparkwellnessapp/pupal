"""SEC-1 — the `public` schema stays locked down (migration 034).

Two halves:
  * against the database (the test DB, via tests/conftest.py): every public table has
    row-level security ON, and the Data API's roles (`anon`, `authenticated`) hold NO
    privilege on any public table, view or sequence;
  * against the migration files: every migration after 034 that creates a table enables
    row-level security on it in the same file (the CLAUDE.md convention), so a new table
    can never ship exposed and be caught only by the next DB check.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
DATA_API_ROLES = ("anon", "authenticated")


async def _connect():
    import asyncpg
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    return await asyncpg.connect(url, statement_cache_size=0, timeout=30)


@pytest.mark.integration
async def test_public_schema_locked_down():
    conn = await _connect()
    try:
        exposed = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity "
            "ORDER BY 1")
        assert [r["tablename"] for r in exposed] == [], "row-level security is OFF on these"

        roles = [r["rolname"] for r in await conn.fetch(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY($1::text[])", list(DATA_API_ROLES))]
        granted = await conn.fetch("""
            SELECT r.role, c.relname, c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN unnest($1::text[]) AS r(role)
            WHERE n.nspname = 'public'
              AND (
                (c.relkind IN ('r', 'p', 'v', 'm', 'f') AND has_table_privilege(
                    r.role, c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'))
                OR
                (c.relkind = 'S' AND has_sequence_privilege(r.role, c.oid, 'USAGE, SELECT, UPDATE'))
              )
            ORDER BY 1, 2""", roles)
        assert [(r["role"], r["relname"], r["relkind"]) for r in granted] == [], (
            "the Data API's roles hold privileges here")
    finally:
        await conn.close()


_CREATE_TABLE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?(\w+)\"?", re.I)


def _enables_rls(sql: str, table: str) -> bool:
    return re.search(
        rf"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?(?:public\.)?\"?{re.escape(table)}\"?\s+"
        rf"ENABLE\s+ROW\s+LEVEL\s+SECURITY\b", sql, re.I) is not None


def test_every_table_created_after_034_enables_row_level_security():
    offenders = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if int(path.name[:3]) <= 34:
            continue
        sql = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        offenders += [f"{path.name}: {t}" for t in _CREATE_TABLE.findall(sql)
                      if not _enables_rls(sql, t)]
    assert offenders == [], "every CREATE TABLE needs ENABLE ROW LEVEL SECURITY in its migration"


def test_the_convention_check_catches_a_table_without_rls():
    """The static check itself: it must see an omission and accept the fix."""
    bad = "CREATE TABLE IF NOT EXISTS public.widgets (id uuid PRIMARY KEY);"
    good = bad + "\nALTER TABLE public.widgets ENABLE ROW LEVEL SECURITY;"
    (table,) = _CREATE_TABLE.findall(bad)
    assert table == "widgets"
    assert not _enables_rls(bad, table) and _enables_rls(good, table)
