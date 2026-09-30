"""
Pytest configuration for backend.

The backend code uses absolute imports like `from app.services...`.
When running pytest from the repo root, `vivi-codebase/backend` is not
automatically on sys.path, so `import app` fails during test collection.

This file makes the backend package importable for local/CI test runs.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]  # .../vivi-codebase/backend
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# DATABASE ISOLATION GUARD (PR delivery_isolation_scaleup, Task B, 2026-08-23)
#
# The suite used to run against whatever DATABASE_URL the developer's .env
# held — which was PRODUCTION (s2test.com rows sat in the same users table as
# the pilot teacher's real student exams). Two mechanisms close that:
#
#   1. REDIRECT: if TEST_DATABASE_URL is set (in the environment or in
#      backend/.env), it overrides DATABASE_URL before any app import, so
#      Settings resolves the test database.
#   2. HARD GUARD, fail closed: the session ABORTS unless the resolved URL's
#      (host, tenant) is on the allow-list (tests/local_db.py since A-10, which
#      admits localhost ONLY on the local test cluster's port). Supabase's regional pooler
#      host is SHARED across projects, so the tenant ref in the username is
#      part of the identity — host alone would wave production through.
#
# This block runs at conftest import — before pytest collects a single test,
# before app.config's Settings ever instantiates. Do not move it below an
# app import; do not "temporarily" widen the allow-list. If you hit the
# abort at 23:00 the night before launch, the fix is setting
# TEST_DATABASE_URL, never editing this list.
# ---------------------------------------------------------------------------
import os as _os

_ENV_PATH = BACKEND_ROOT / ".env"
if _ENV_PATH.exists():
    # minimal .env read (no dotenv import before sys.path is set)
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        if _line.startswith("TEST_DATABASE_URL=") and "TEST_DATABASE_URL" not in _os.environ:
            _os.environ["TEST_DATABASE_URL"] = _line.split("=", 1)[1].strip()

# NO REAL MAIL FROM A TEST PROCESS — set BEFORE app.config is imported, the
# same way DATABASE_URL is redirected above, because pydantic-settings reads the
# environment once at construction.
#
# CLAUDE.md 9 already says the provider defaults to `console` because "every
# test process is an unconfigured environment". That stopped being true the day
# backend/.env grew EMAIL_PROVIDER=resend for local development: from then on,
# every signup in tests/api/ sent a REAL verification email to a fabricated
# @s2test.com address. It went unnoticed because it worked — until Resend
# rate-limited the sender mid-suite (429 -> the signup endpoint's 502), which
# ERRORED every fixture that signs a user up. The failure was loud; the year of
# silent sends before it was not, and that is the half worth preventing.
#
# An explicit override wins, so a test that deliberately exercises a provider
# can still ask for one.
_os.environ.setdefault("EMAIL_PROVIDER", "console")

# [D-14] The same failure, for the post-pricing student-feedback call (PR-G4).
# `config.feedback_model_key` DEFAULTS to a real model (claude-sonnet-5), so any
# test that runs the grading runner without faking `attach_feedback` called the
# real Anthropic API — paid, network-dependent, and invisible because the call
# degrades to `feedback=None` on failure. Found by A-8 (2026-09-28). Tests that
# exercise feedback set the key and inject a fake model themselves.
_os.environ.setdefault("FEEDBACK_MODEL_KEY", "")

# [A-10] Which database: `VIVI_TEST_DB=local` (explicit opt-in) points the session at
# the dedicated local cluster (scripts/local_test_db.py); unset or `remote` keeps the
# TEST_DATABASE_URL redirect below, exactly as before. Any other value refuses to run,
# so a typo cannot silently fall through to a remote database.
from tests import local_db as _local_db  # imports nothing from app

_selected = _os.environ.get(_local_db.SELECT_ENV, "").strip().lower()
if _selected not in ("", "remote", "local"):
    raise SystemExit(f"{_local_db.SELECT_ENV}={_selected!r}: use 'local' or 'remote'")
if _selected == "local":
    _os.environ["DATABASE_URL"] = _local_db.LOCAL_DATABASE_URL
    _os.environ["DB_DISABLE_POOLING"] = "true"
elif _os.environ.get("TEST_DATABASE_URL"):
    _os.environ["DATABASE_URL"] = _os.environ["TEST_DATABASE_URL"]
    # Pooled connections that outlive a test wedge session teardown on
    # Windows (every test green, process never exits). NullPool under test.
    _os.environ["DB_DISABLE_POOLING"] = "true"


def _effective_database_url():
    """The URL Settings WILL use: the environment first, else the `.env` it reads from
    the working directory. (Reading only the environment let a `.env` holding the
    production DATABASE_URL and no TEST_DATABASE_URL through as "no URL".)"""
    url = _os.environ.get("DATABASE_URL")
    if url:
        return url
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return None


# The allow-list itself lives in tests/local_db.py (is_allowed_test_target): Vivi-Test,
# the local test cluster (127.0.0.1/localhost ON ITS PORT ONLY), or no URL at all.
_effective_url = _effective_database_url()
if not _local_db.is_allowed_test_target(_effective_url):
    _t = _local_db.resolve_db_target(_effective_url)
    raise SystemExit(
        "\n" + "=" * 76 +
        f"\nREFUSING TO RUN: resolved database target is not a test database."
        f"\n  host: {_t.host}\n  port: {_t.port}\n  user: {_t.user}"
        "\nThe test suite must never touch production. Set TEST_DATABASE_URL in"
        "\nbackend/.env to the Vivi-Test project URL, or opt into the local cluster"
        "\nwith VIVI_TEST_DB=local (tests/local_db.py, scripts/local_test_db.py)."
        "\n" + "=" * 76
    )


# [A-10] NETWORK GUARD — installed here, at conftest import, so an import-time call
# during collection is covered too. See tests/guards.py.
from tests import guards as _guards  # noqa: E402

_guards.install_network_guard()


# ---------------------------------------------------------------------------
# [PLAN COMPILER v2 production wiring] No provider is ever called from a plan
# build inside the test process. Every rubric save now kicks a build (W-2), and
# in inline mode that build runs on the app loop during API tests — so the
# model factory is replaced STRUCTURALLY, for every test, with one whose calls
# fail. The build then degrades to the compiler's placeholder wording (W-2's
# guarantee), which is the real production path for a provider outage. Tests
# that want a model inject their own fake through `llm_factory=`.
# ---------------------------------------------------------------------------
import pytest as _pytest


class _NoProviderRunner:
    def __init__(self, schema):
        self.schema = schema

    async def ainvoke(self, messages):
        raise RuntimeError("provider calls are forbidden in tests (plan build)")


class _NoProviderLLM:
    def with_structured_output(self, schema, include_raw=True):
        return _NoProviderRunner(schema)


def _no_provider_factory(model_key: str):
    return _NoProviderLLM()


@_pytest.fixture(autouse=True)
def no_provider_in_plan_builds(monkeypatch):
    import app.services.plan_build_runner as _pbr
    monkeypatch.setattr(_pbr, "default_llm_factory", _no_provider_factory)
    yield


# ---------------------------------------------------------------------------
# [A-7 TEST HYGIENE] Known failures are pinned by name, and a gate run must
# reach the test DB. The rules live in tests/known_failures.py.
# ---------------------------------------------------------------------------
from tests import known_failures as _kf


# [A-10] The `db` marker: a test that touches the database says so. Whole directories
# whose every module is DB-backed are marked here; elsewhere the module carries
# `pytestmark = pytest.mark.db` (or the test its own mark). `integration` (live DB,
# migrations applied) implies `db`. The guard below makes the rule self-enforcing.
DB_TEST_DIRS = ("tests/api/", "tests/models/", "tests/services/erasure/")


def _mark_db_items(items):
    for item in items:
        path = item.nodeid.split("::", 1)[0]
        if path.startswith(DB_TEST_DIRS) or item.get_closest_marker("integration"):
            item.add_marker(_pytest.mark.db)


def pytest_collection_modifyitems(config, items):
    _mark_db_items(items)
    known = _kf.load_known_failures()
    _kf.mark_known_failures(items, known)
    if not (_kf.is_gate_run() or _os.environ.get("VIVI_RUN_SLOW", "").strip() not in ("", "0")):
        skip_slow = _pytest.mark.skip(reason="slow: set VIVI_RUN_SLOW=1 (gate runs include it)")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    if not _kf.is_gate_run():
        return
    rootdir = Path(str(config.rootpath))
    narrowed = set()
    for arg in config.args:
        if "::" in arg:
            p = Path(arg.split("::", 1)[0])
            p = p if p.is_absolute() else Path.cwd() / p
            try:
                narrowed.add(p.resolve().relative_to(rootdir).as_posix())
            except ValueError:
                pass
    stale = _kf.stale_entries(known, [i.nodeid for i in items], narrowed)
    if stale:
        raise _pytest.UsageError(
            "KNOWN_FAILURES.txt names tests that were not collected (renamed or deleted?): "
            + ", ".join(stale))


def pytest_collection_finish(session):
    """A gate run must reach the test DB (A-7) — when it will USE it: a run whose
    selection holds no `db` test (e.g. `-m "not db"`) needs no database at all."""
    if not _kf.is_gate_run() or session.config.option.collectonly:
        return
    if not any(item.get_closest_marker("db") for item in session.items):
        return
    why = _kf.probe_database(_os.environ.get("DATABASE_URL"))
    if why is not None:
        _pytest.exit(f"GATE RUN REFUSED: the test DB is unreachable ({why}). A gate run "
                     "must reach the test DB (A-7); fix the connection and rerun.",
                     returncode=_kf.GATE_DB_UNREACHABLE_EXIT)


# ---------------------------------------------------------------------------
# [A-10] The two guards (tests/guards.py), per test. A violation fails the test that
# made it even when the code under test swallowed the exception; one made outside any
# test (a background thread after its test ended) fails the run at the end.
# ---------------------------------------------------------------------------
def _a10_marks():
    return _guards.NETWORK.mark(), _guards.DB.mark()


def _a10_problems(marks):
    net_mark, db_mark = marks
    return list(dict.fromkeys(_guards.NETWORK.since(net_mark) + _guards.DB.since(db_mark)))


@_pytest.fixture(autouse=True)
def _a10_guards(request, monkeypatch):
    item = request.node
    _guards.NETWORK.current = _guards.DB.current = item.nodeid
    item._a10_marks = _a10_marks()
    if item.get_closest_marker("db") is None:
        _guards.block_db_connections(monkeypatch, item.nodeid)
    try:
        yield
    finally:
        _guards.NETWORK.current = _guards.DB.current = None
    problems = _a10_problems(item._a10_marks)      # what teardown itself provoked
    if problems:
        _pytest.fail("\n".join(problems), pytrace=False)


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A violation during the test body FAILS the test (not "passed + teardown error")."""
    outcome = yield
    marks = getattr(item, "_a10_marks", None)
    if call.when != "call" or marks is None:
        return
    problems = _a10_problems(marks)
    item._a10_marks = _a10_marks()                 # reported here, not again at teardown
    if problems:
        report = outcome.get_result()
        report.outcome = "failed"
        msg = "[A-10 guard]\n" + "\n".join(problems)
        report.longrepr = msg if report.longrepr is None else f"{report.longrepr}\n\n{msg}"


def pytest_sessionfinish(session, exitstatus):
    stray = _guards.NETWORK.outside_tests() + _guards.DB.outside_tests()
    if stray:
        print("\n[A-10] guard violations outside any test:\n  "
              + "\n  ".join(dict.fromkeys(stray)))
        if session.exitstatus == 0:
            session.exitstatus = 1
