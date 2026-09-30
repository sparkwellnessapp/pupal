"""A-10 — the local-DB allow-list, the `db` marker guard and the provider network guard."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests import guards
from tests import local_db

BACKEND = Path(__file__).resolve().parents[1]

PROD_POOLER = ("postgresql+asyncpg://postgres.ngkqawsyqqbhqthgdkpk:x@"
               "aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
TEST_POOLER = ("postgresql+asyncpg://postgres.eqnbojbxsdafwtxvuyuy:x@"
               "aws-0-eu-central-1.pooler.supabase.com:6543/postgres")


# --- the allow-list (pure) -------------------------------------------------------------

@pytest.mark.parametrize("url", [
    PROD_POOLER,
    "postgresql+asyncpg://postgres:x@db.ngkqawsyqqbhqthgdkpk.supabase.co:5432/postgres",
    "postgresql+asyncpg://postgres@127.0.0.1:5432/postgres",      # the machine's own service
    "postgresql+asyncpg://postgres@localhost/vivi_test",           # no port = 5432
    "postgresql+asyncpg://user:password@localhost:5432/grader",    # Settings' placeholder
])
def test_production_and_any_other_local_postgres_are_refused(url):
    assert not local_db.is_allowed_test_target(url)


@pytest.mark.parametrize("url", [
    None, "",                                                      # nothing to connect to
    local_db.LOCAL_DATABASE_URL,
    f"postgresql+asyncpg://postgres@localhost:{local_db.LOCAL_PORT}/vivi_test",
    TEST_POOLER,
    "postgresql+asyncpg://postgres:x@db.eqnbojbxsdafwtxvuyuy.supabase.co:5432/postgres",
])
def test_vivi_test_and_the_local_cluster_are_accepted(url):
    assert local_db.is_allowed_test_target(url)


def _collect_only(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "TEST_DATABASE_URL", local_db.SELECT_ENV)}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "tests/test_a10_guards.py::test_vivi_test_and_the_local_cluster_are_accepted"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)


def test_conftest_refuses_a_session_pointed_at_production():
    # TEST_DATABASE_URL="" stops conftest re-reading it from backend/.env.
    r = _collect_only({"DATABASE_URL": PROD_POOLER, "TEST_DATABASE_URL": ""})
    assert r.returncode != 0
    assert "REFUSING TO RUN" in r.stdout + r.stderr


def test_conftest_accepts_the_local_cluster_by_explicit_opt_in():
    r = _collect_only({local_db.SELECT_ENV: "local", "DATABASE_URL": PROD_POOLER})
    assert r.returncode == 0, r.stdout + r.stderr


def test_conftest_refuses_an_unknown_db_selection():
    r = _collect_only({local_db.SELECT_ENV: "prod"})
    assert r.returncode != 0 and "use 'local' or 'remote'" in r.stdout + r.stderr


# --- the network guard -----------------------------------------------------------------

@pytest.mark.parametrize("host", [
    "api.openai.com", "API.OpenAI.com.", "api.anthropic.com",
    "generativelanguage.googleapis.com", "aiplatform.googleapis.com",
    "europe-west1-aiplatform.googleapis.com", "api.x.ai", "api.smith.langchain.com",
    "eu.api.smith.langchain.com", "api.moonshot.ai",
])
def test_provider_hosts_are_recognised(host):
    assert guards.is_provider_host(host)


@pytest.mark.parametrize("host", [
    "storage.googleapis.com", "oauth2.googleapis.com", "cloudtasks.googleapis.com",
    "aws-0-eu-central-1.pooler.supabase.com", "127.0.0.1", "localhost",
    "notapi.openai.com.evil.example", "api.resend.com",
])
def test_the_db_host_gcs_and_the_rest_are_not(host):
    assert not guards.is_provider_host(host)


def test_the_guard_is_installed_for_the_whole_session():
    assert guards.network_guard_installed()


def _provoke(fn):
    mark = guards.NETWORK.mark()
    with pytest.raises(Exception) as info:
        fn()
    return info, guards.NETWORK.discard_since(mark)


def test_a_socket_lookup_of_a_provider_raises_naming_the_host():
    info, recorded = _provoke(lambda: socket.getaddrinfo("api.openai.com", 443))
    assert info.type is guards.ProviderCallBlocked
    assert "api.openai.com" in str(info.value) and len(recorded) == 1


def test_httpx_and_requests_cannot_route_around_it():
    import httpx
    import requests

    _, recorded = _provoke(lambda: httpx.get("https://api.anthropic.com/v1/messages", timeout=5))
    assert recorded and "api.anthropic.com" in recorded[0]
    _, recorded = _provoke(lambda: requests.get("https://api.x.ai/v1/models", timeout=5))
    assert recorded and "api.x.ai" in recorded[0]


async def test_async_httpx_and_the_openai_sdk_cannot_either():
    import httpx
    import openai

    async def _async_get():
        async with httpx.AsyncClient(timeout=5) as c:
            await c.get("https://generativelanguage.googleapis.com/v1beta/models")

    mark = guards.NETWORK.mark()
    with pytest.raises(Exception):
        await _async_get()
    client = openai.OpenAI(api_key="sk-test", max_retries=0, timeout=5)
    with pytest.raises(openai.APIConnectionError):
        client.models.list()
    recorded = guards.NETWORK.discard_since(mark)
    assert any("generativelanguage.googleapis.com" in m for m in recorded)
    assert any("api.openai.com" in m for m in recorded)


# --- end to end: a swallowed violation still fails its test -----------------------------

def test_swallowed_violations_fail_their_tests_and_db_marked_tests_are_left_alone():
    # Same database as this session; never a gate run (the probes need no DB probe).
    env = {k: v for k, v in os.environ.items() if k != "VIVI_TEST_GATE"}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf",
         "tests/a10_guard_probes/probe_guards.py"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert "2 failed, 1 passed" in out, out
    assert "FAILED tests/a10_guard_probes/probe_guards.py::test_probe_swallowed_provider_call" in out
    assert "api.anthropic.com" in out
    assert ("FAILED tests/a10_guard_probes/probe_guards.py::"
            "test_probe_swallowed_db_connect_in_pure_test") in out
    assert "is not marked `db`" in out


def test_a_pure_test_has_the_db_drivers_blocked():
    import asyncpg
    import psycopg2

    mark = guards.DB.mark()
    with pytest.raises(guards.DbAccessInPureTest):
        asyncpg.connect("postgresql://u@127.0.0.1:1/x")
    with pytest.raises(guards.DbAccessInPureTest):
        psycopg2.connect("postgresql://u@127.0.0.1:1/x")
    assert len(guards.DB.discard_since(mark)) == 2
