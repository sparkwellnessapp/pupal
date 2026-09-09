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
#      (host, tenant) is on the allow-list below. Supabase's regional pooler
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
from urllib.parse import urlparse as _urlparse

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

if _os.environ.get("TEST_DATABASE_URL"):
    _os.environ["DATABASE_URL"] = _os.environ["TEST_DATABASE_URL"]
    # Pooled connections that outlive a test wedge session teardown on
    # Windows (every test green, process never exits). NullPool under test.
    _os.environ["DB_DISABLE_POOLING"] = "true"

# (host, username-suffix) pairs a test session may touch. None = any user.
_ALLOWED_TEST_TARGETS = (
    ("localhost", None),
    ("127.0.0.1", None),
    # Vivi-Test — the dedicated Supabase test project (eu-central-1)
    ("aws-0-eu-central-1.pooler.supabase.com", ".eqnbojbxsdafwtxvuyuy"),
    ("db.eqnbojbxsdafwtxvuyuy.supabase.co", None),
)


def _resolve_db_target() -> tuple[str, str]:
    url = _os.environ.get("DATABASE_URL", "")
    if not url:
        # Settings falls back to its localhost default — safe.
        return ("localhost", "")
    p = _urlparse(url.replace("postgresql+asyncpg://", "postgresql://"))
    return (p.hostname or "", p.username or "")


_host, _user = _resolve_db_target()
_ok = any(
    _host == h and (suffix is None or _user.endswith(suffix))
    for h, suffix in _ALLOWED_TEST_TARGETS
)
if not _ok:
    raise SystemExit(
        "\n" + "=" * 76 +
        f"\nREFUSING TO RUN: resolved database target is not a test database."
        f"\n  host: {_host}\n  user: {_user}"
        "\nThe test suite must never touch production. Set TEST_DATABASE_URL in"
        "\nbackend/.env to the Vivi-Test project URL (see tests/conftest.py"
        "\n_ALLOWED_TEST_TARGETS), or run against localhost."
        "\n" + "=" * 76
    )


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
