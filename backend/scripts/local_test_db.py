"""A-10 — the LOCAL test database: a dedicated PostgreSQL 17 cluster for T0/T1.

    python scripts/local_test_db.py up        # initdb (once) → start → create db → schema → print URL
    python scripts/local_test_db.py down      # stop the cluster
    python scripts/local_test_db.py reset     # drop the database and rebuild it from the snapshot
    python scripts/local_test_db.py url       # print the URL
    python scripts/local_test_db.py snapshot [--down FILE]   # maintainer: re-dump the schema from Vivi-Test

Then run the suite against it with the explicit opt-in:

    VIVI_TEST_DB=local python -m pytest ...

WHY A NATIVE CLUSTER AND NOT A CONTAINER. The owner's ruling says "container"; Docker
Desktop does not start on the development machine, and PostgreSQL 17.6 — production's
exact version — is installed natively. This script builds a DEDICATED cluster (its own
data directory, its own port, localhost-only, trust auth for 127.0.0.1 alone) and never
touches the machine's own PostgreSQL service or its data. (Decided — pending owner veto.)

WHERE THE SCHEMA COMES FROM. Not from replaying `migrations/`: the `rubrics` and
`grading_batches` base tables predate migration 001 (created by `create_all`), several
early migrations are not idempotent, and 001/002 seed rows Vivi-Test does not have. So
the schema is a committed `pg_dump --schema-only --schema=public` of Vivi-Test
(`tests/local_db_schema/schema.sql`, plus its `schema_migrations` rows), loaded into a
database that first gets what Supabase itself provides and the schema needs
(`init.sql`: the `anon`/`authenticated` NOLOGIN roles, the `extensions` schema with
uuid-ossp and pgcrypto on the search_path). Any migration FILE in this checkout whose
version is not in the loaded ledger is then applied on top, in order — so a branch that
adds migration 0NN gets it locally with no snapshot refresh. `snapshot` regenerates the
committed files and REFUSES when Vivi-Test's ledger names a version this checkout does
not have (a branch's migration applied to the shared test DB) unless `--down FILE`
reverses it first; after the down, the ledger must equal this checkout's migrations.

Speed settings (fsync/synchronous_commit/full_page_writes off) are for a disposable test
cluster only; the timezone (UTC), encoding (UTF8), ICU en-US collation and the 120 s
statement_timeout match Vivi-Test.

Nothing here prints a password: the local cluster has none, and `snapshot` hands the
Vivi-Test password to pg_dump through PGPASSWORD only.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tests.local_db import (  # noqa: E402  (one place for the address)
    LOCAL_APP_ROLE, LOCAL_DATABASE, LOCAL_DATABASE_URL, LOCAL_HOST, LOCAL_PORT,
    VIVI_TEST_TENANT, resolve_db_target,
)

SCHEMA_DIR = BACKEND / "tests" / "local_db_schema"
INIT_SQL = SCHEMA_DIR / "init.sql"
SCHEMA_SQL = SCHEMA_DIR / "schema.sql"
LEDGER_SQL = SCHEMA_DIR / "ledger.sql"
MIGRATIONS = BACKEND / "migrations"

SUPERUSER = "vivi_admin"          # the cluster's bootstrap superuser; the app never uses it
PG_MAJOR = "17"
DEFAULT_WINDOWS_BIN = Path(r"C:\Program Files\PostgreSQL\17\bin")
DEFAULT_DATA_DIR = Path.home() / ".vivi" / "pgdata17"

CLUSTER_CONF = f"""
# --- A-10 local test cluster (scripts/local_test_db.py) ---
listen_addresses = '{LOCAL_HOST}'
port = {LOCAL_PORT}
timezone = 'UTC'
log_timezone = 'UTC'
statement_timeout = '120s'
max_connections = 100
# disposable test data: durability off for speed
fsync = off
synchronous_commit = off
full_page_writes = off
"""
HBA = f"host all all {LOCAL_HOST}/32 trust\n"


def die(msg: str) -> None:
    print(f"local_test_db: {msg}", file=sys.stderr)
    raise SystemExit(1)


def pg_bin(args) -> Path:
    cand = args.pg_bin or os.environ.get("PG_BIN")
    if cand:
        return Path(cand)
    if DEFAULT_WINDOWS_BIN.exists():
        return DEFAULT_WINDOWS_BIN
    found = shutil.which("pg_ctl")
    if not found:
        die("no PostgreSQL binaries: pass --pg-bin or set PG_BIN")
    return Path(found).parent


def exe(args, name: str) -> str:
    p = pg_bin(args) / (name + (".exe" if os.name == "nt" else ""))
    if not p.exists():
        die(f"{p} not found")
    return str(p)


def data_dir(args) -> Path:
    return Path(args.data_dir or os.environ.get("VIVI_LOCAL_PG_DATA") or DEFAULT_DATA_DIR)


def run(cmd, check=True, env=None, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True, env=env)
    if check and r.returncode != 0:
        die(f"{Path(cmd[0]).name} failed ({r.returncode}):\n{r.stdout or ''}{r.stderr or ''}")
    return r


def psql(args, sql: str | None = None, *, db: str = "postgres", user: str = SUPERUSER,
         file: Path | None = None, check=True):
    cmd = [exe(args, "psql"), "-h", LOCAL_HOST, "-p", str(LOCAL_PORT), "-U", user, "-d", db,
           "-X", "-q", "-v", "ON_ERROR_STOP=1", "-At"]
    cmd += ["-f", str(file)] if file else ["-c", sql]
    return run(cmd, check=check, env=dict(os.environ, PGCLIENTENCODING="UTF8"))


def check_version(args) -> None:
    out = run([exe(args, "postgres"), "--version"]).stdout.strip()
    if not re.search(rf"\b{PG_MAJOR}\.\d+", out):
        die(f"need PostgreSQL {PG_MAJOR} (production's major); found: {out}")


def ensure_cluster(args) -> Path:
    check_version(args)
    d = data_dir(args)
    if not (d / "PG_VERSION").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        print(f"initdb -> {d}")
        run([exe(args, "initdb"), "-D", str(d), "-U", SUPERUSER, "-A", "trust", "-E", "UTF8",
             "--locale=C", "--locale-provider=icu", "--icu-locale=en-US"])
        with open(d / "postgresql.conf", "a", encoding="utf-8") as f:
            f.write(CLUSTER_CONF)
        (d / "pg_hba.conf").write_text(HBA, encoding="utf-8")
    return d


def is_running(args, d: Path) -> bool:
    return run([exe(args, "pg_ctl"), "status", "-D", str(d)], check=False).returncode == 0


def start(args, d: Path) -> None:
    if is_running(args, d):
        return
    log = d.parent / (d.name + ".log")
    print(f"starting the cluster on {LOCAL_HOST}:{LOCAL_PORT} (log: {log})")
    # capture=False: pg_ctl's child keeps the pipes open on Windows and a captured run
    # would wait on it forever.
    r = subprocess.run([exe(args, "pg_ctl"), "start", "-w", "-t", "60", "-D", str(d),
                        "-l", str(log)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        die(f"pg_ctl start failed; see {log}")


def ensure_database(args) -> bool:
    """Roles and the database. True when the database was created just now."""
    psql(args, file=INIT_SQL)
    exists = psql(args, f"SELECT 1 FROM pg_database WHERE datname = '{LOCAL_DATABASE}'").stdout.strip()
    if exists:
        return False
    psql(args, f"CREATE DATABASE {LOCAL_DATABASE} OWNER {LOCAL_APP_ROLE} TEMPLATE template0 "
               "ENCODING 'UTF8' LOCALE_PROVIDER icu ICU_LOCALE 'en-US' LOCALE 'C'")
    return True


def prepare_database(args, db: str) -> None:
    """What Supabase provides and the schema needs, then an empty `public` for the dump."""
    psql(args, db=db, sql=(
        "CREATE SCHEMA IF NOT EXISTS extensions; "
        'CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA extensions; '
        "CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA extensions; "
        f"GRANT USAGE ON SCHEMA extensions TO {LOCAL_APP_ROLE}, anon, authenticated; "
        f"ALTER DATABASE {db} SET search_path = \"$user\", public, extensions; "
        "DROP SCHEMA IF EXISTS public CASCADE;"))


def ledger(args, db: str) -> set[str]:
    out = psql(args, db=db, user=LOCAL_APP_ROLE,
               sql="SELECT version FROM public.schema_migrations").stdout
    return {v.strip() for v in out.splitlines() if v.strip()}


def checkout_migrations() -> dict[str, Path]:
    return {p.name[:3]: p for p in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))}


def load_schema(args, db: str) -> None:
    prepare_database(args, db)
    psql(args, db=db, user=LOCAL_APP_ROLE, file=SCHEMA_SQL)
    psql(args, db=db, user=LOCAL_APP_ROLE, file=LEDGER_SQL)


def apply_pending(args, db: str) -> list[str]:
    have = ledger(args, db)
    applied = []
    for version, path in checkout_migrations().items():
        if version not in have:
            print(f"applying {path.name} (not in the snapshot's ledger)")
            psql(args, db=db, user=LOCAL_APP_ROLE, file=path)
            applied.append(version)
    return applied


def cmd_up(args) -> None:
    d = ensure_cluster(args)
    start(args, d)
    if ensure_database(args):
        load_schema(args, LOCAL_DATABASE)
    apply_pending(args, LOCAL_DATABASE)
    missing = sorted(set(checkout_migrations()) - ledger(args, LOCAL_DATABASE))
    if missing:
        die(f"ledger still lacks {missing}")
    print(f"ready: {LOCAL_DATABASE_URL}")
    print("run the suite with:  VIVI_TEST_DB=local python -m pytest ...")


def cmd_down(args) -> None:
    d = data_dir(args)
    if (d / "PG_VERSION").exists() and is_running(args, d):
        run([exe(args, "pg_ctl"), "stop", "-D", str(d), "-m", "fast", "-w"])
        print("stopped")


def cmd_reset(args) -> None:
    d = ensure_cluster(args)
    start(args, d)
    psql(args, f"DROP DATABASE IF EXISTS {LOCAL_DATABASE} WITH (FORCE)")
    cmd_up(args)


def _vivi_test_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    env = BACKEND / ".env"
    if not url and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    t = resolve_db_target(url)
    if t is None or not t.user.endswith("." + VIVI_TEST_TENANT):
        die("snapshot reads ONLY the Vivi-Test project: set TEST_DATABASE_URL to it")
    return url


def _strip_restrict(text: str) -> str:
    # pg_dump 17.6 brackets its output with a random \restrict key; drop it so a
    # regenerated snapshot diffs only where the schema changed.
    return "".join(l for l in text.splitlines(keepends=True)
                   if not l.startswith(("\\restrict ", "\\unrestrict ")))


def _dump_local(args, db: str, out: Path) -> None:
    base = [exe(args, "pg_dump"), "-h", LOCAL_HOST, "-p", str(LOCAL_PORT), "-U", LOCAL_APP_ROLE,
            "-d", db, "--no-owner", "--no-privileges"]
    run(base + ["--schema-only", "--schema=public", "-f", str(out / "schema.sql")])
    run(base + ["--data-only", "--table=public.schema_migrations", "-f", str(out / "ledger.sql")])


def cmd_snapshot(args) -> None:
    url = _vivi_test_url()
    p = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    d = ensure_cluster(args)
    start(args, d)
    psql(args, file=INIT_SQL)
    scratch = "vivi_snapshot_scratch"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = dict(os.environ, PGPASSWORD=unquote(p.password or ""), PGSSLMODE="require")
        # Session-mode pooler port: pg_dump's SETs must share one backend.
        remote = [exe(args, "pg_dump"), "-h", p.hostname, "-p", "5432", "-U", unquote(p.username),
                  "-d", (p.path or "/postgres").lstrip("/") or "postgres",
                  "--no-owner", "--no-privileges"]
        run(remote + ["--schema-only", "--schema=public", "-f", str(tmp / "schema.sql")], env=env)
        run(remote + ["--data-only", "--table=public.schema_migrations",
                      "-f", str(tmp / "ledger.sql")], env=env)
        psql(args, f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)")
        psql(args, f"CREATE DATABASE {scratch} OWNER {LOCAL_APP_ROLE} TEMPLATE template0 "
                   "ENCODING 'UTF8' LOCALE_PROVIDER icu ICU_LOCALE 'en-US' LOCALE 'C'")
        try:
            prepare_database(args, scratch)
            psql(args, db=scratch, user=LOCAL_APP_ROLE, file=tmp / "schema.sql")
            psql(args, db=scratch, user=LOCAL_APP_ROLE, file=tmp / "ledger.sql")
            if args.down:
                psql(args, db=scratch, user=LOCAL_APP_ROLE, file=Path(args.down))
            have, want = ledger(args, scratch), set(checkout_migrations())
            if have != want:
                die("Vivi-Test's ledger does not match this checkout's migrations: "
                    f"only on Vivi-Test {sorted(have - want)}, only here {sorted(want - have)}. "
                    "Reverse the extra ones with --down FILE, or snapshot from a checkout "
                    "that has them.")
            out = tmp / "out"
            out.mkdir()
            _dump_local(args, scratch, out)
            SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
            header = (
                f"-- A-10 snapshot of Vivi-Test ({VIVI_TEST_TENANT}), schema `public`, at ledger "
                f"head {max(want)}.\n-- Generated {date.today().isoformat()} by "
                "`python scripts/local_test_db.py snapshot` — do not hand-edit; regenerate.\n"
                + (f"-- Reversed before dumping (on Vivi-Test, not in this checkout): "
                   f"{Path(args.down).name}\n" if args.down else ""))
            for name in ("schema.sql", "ledger.sql"):
                text = _strip_restrict((out / name).read_text(encoding="utf-8"))
                (SCHEMA_DIR / name).write_text(header + text, encoding="utf-8", newline="\n")
        finally:
            psql(args, f"DROP DATABASE IF EXISTS {scratch} WITH (FORCE)", check=False)
    print(f"wrote {SCHEMA_SQL.relative_to(BACKEND)} and {LEDGER_SQL.relative_to(BACKEND)}; "
          "run `reset` to rebuild the local database from them")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=("up", "down", "reset", "url", "snapshot"))
    ap.add_argument("--data-dir", help="cluster data dir (default: $VIVI_LOCAL_PG_DATA or ~/.vivi/pgdata17)")
    ap.add_argument("--pg-bin", help="PostgreSQL 17 bin dir (default: $PG_BIN, the Windows "
                                     "install dir, or PATH)")
    ap.add_argument("--down", help="snapshot only: SQL that reverses migrations Vivi-Test has "
                                   "and this checkout does not")
    args = ap.parse_args(argv)
    if args.command == "url":
        print(LOCAL_DATABASE_URL)
        return
    {"up": cmd_up, "down": cmd_down, "reset": cmd_reset, "snapshot": cmd_snapshot}[args.command](args)


if __name__ == "__main__":
    main()
