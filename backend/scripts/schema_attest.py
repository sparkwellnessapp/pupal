"""
Schema attestation (closeout A1/A2/A3) — READ-ONLY.

Prints, for the database `DATABASE_URL` names:
  * which environment it actually is (host + database, so a result can never
    be filed against the wrong environment by accident),
  * the applied-migration ledger vs EXPECTED_MIGRATIONS,
  * every constraint attribute the checker knows about (A1: 010's deferrable
    FK — the one that was half-applied and invisible),
  * every partial index it knows about (A3: 017's client_file_id index, which
    IS B9's idempotency guarantee),
  * and the STATED coverage boundary, so what this does NOT prove is on the
    record next to what it does.

RUN IT TWICE around the pre-launch wipe (owner ruling): a TRUNCATE leaves
constraints and indexes alone, but a drop-and-recreate procedure does not,
and the wipe must not take the schema_migrations ledger with it — a blank
ledger with live schema objects is precisely the direction that hid 010.

    python scripts/schema_attest.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import (  # noqa: E402
    EXPECTED_CONSTRAINT_ATTRIBUTES,
    EXPECTED_MIGRATIONS,
    EXPECTED_PARTIAL_INDEXES,
    SCHEMA_CHECK_COVERAGE,
    _constraint_attribute_problems,
    _partial_index_problems,
    _read_constraint_attributes,
    _read_partial_indexes,
    engine,
)


def _redacted_target() -> str:
    """host/database only — never the password.

    Reads the SETTINGS, not the raw environment: the DSN arrives via the .env
    that pydantic loads, so `os.getenv` returns None and the attestation would
    print "(unset)" while happily connecting somewhere. An attestation that
    cannot name its target is unfileable — that is the whole point of this line.
    """
    from app.config import settings
    raw = getattr(settings, "database_url", None) or os.getenv("DATABASE_URL") or "(unset)"
    return raw.rsplit("@", 1)[1] if "@" in raw else raw


def _app_env() -> str:
    from app.config import settings
    return getattr(settings, "app_env", None) or os.getenv("APP_ENV") or "(unset)"


async def main() -> int:
    print("=" * 72)
    print(f"SCHEMA ATTESTATION  ·  target: {_redacted_target()}")
    print(f"APP_ENV={_app_env()}")
    print("=" * 72)

    problems: list[str] = []

    # --- ledger -----------------------------------------------------------
    async with engine.connect() as conn:
        has_ledger = (await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='schema_migrations')"
        ))).scalar()
        applied: set[str] = set()
        if has_ledger:
            applied = {
                r[0] for r in (await conn.execute(
                    text("SELECT version FROM public.schema_migrations")
                )).all()
            }

    if not has_ledger:
        problems.append(
            "schema_migrations ledger is MISSING — DDL provenance unknown. "
            "If this follows the pre-launch wipe, the wipe took the ledger: "
            "re-record every applied version before deploying."
        )
        print("\nLEDGER: ABSENT")
    else:
        missing = sorted(set(EXPECTED_MIGRATIONS) - applied)
        unknown = sorted(applied - set(EXPECTED_MIGRATIONS))
        print(f"\nLEDGER: {len(applied)} applied; head expected {EXPECTED_MIGRATIONS[-1]}")
        if missing:
            problems.append(f"migrations NOT APPLIED: {', '.join(missing)}")
            print(f"  MISSING: {', '.join(missing)}")
        if unknown:
            print(f"  unknown-to-this-code (DB ahead): {', '.join(unknown)}")
        if not missing and not unknown:
            print("  OK — ledger matches EXPECTED_MIGRATIONS exactly")

    # --- A1: constraint attributes ---------------------------------------
    rows = await _read_constraint_attributes(tuple(EXPECTED_CONSTRAINT_ATTRIBUTES))
    found = {name: (d, dd) for name, d, dd in rows}
    print(f"\nCONSTRAINT ATTRIBUTES ({len(EXPECTED_CONSTRAINT_ATTRIBUTES)} checked):")
    for name, (want_d, want_dd, mig) in EXPECTED_CONSTRAINT_ATTRIBUTES.items():
        got = found.get(name)
        state = "MISSING" if got is None else f"condeferrable={got[0]} condeferred={got[1]}"
        verdict = "OK" if got == (want_d, want_dd) else "PROBLEM"
        print(f"  [{verdict}] {name} (migration {mig}) — {state}")
    problems += _constraint_attribute_problems(rows)

    # --- A3: partial indexes ---------------------------------------------
    irows = await _read_partial_indexes(tuple(EXPECTED_PARTIAL_INDEXES))
    idefs = dict(irows)
    print(f"\nPARTIAL INDEXES ({len(EXPECTED_PARTIAL_INDEXES)} checked):")
    for name, (fragment, mig) in EXPECTED_PARTIAL_INDEXES.items():
        got = idefs.get(name)
        if got is None:
            print(f"  [PROBLEM] {name} (migration {mig}) — MISSING")
        elif fragment.lower() not in got.lower():
            print(f"  [PROBLEM] {name} (migration {mig}) — predicate lost: {got}")
        else:
            print(f"  [OK] {name} (migration {mig})")
    problems += _partial_index_problems(irows)

    print(f"\nCOVERAGE: {SCHEMA_CHECK_COVERAGE}")

    print("\n" + "=" * 72)
    if problems:
        print(f"ATTESTATION FAILED — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
    else:
        print("ATTESTATION PASSED — every checked object verified.")
    print("=" * 72)

    await engine.dispose()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
