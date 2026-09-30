"""A-10 — two structural test guards, wired by tests/conftest.py.

1. NETWORK GUARD — no test reaches an LLM provider (CLAUDE.md §8: never call OpenAI in
   tests). Installed at the socket layer (`socket.getaddrinfo`, `socket.gethostbyname`),
   which every Python HTTP stack goes through — httpx (sync and async), requests/urllib3,
   and the provider SDKs built on them — so no client can route around it. A blocked
   lookup RAISES `ProviderCallBlocked` naming the host, and is also RECORDED: code under
   test that swallows exceptions (the feedback call degrades to `feedback=None` on any
   failure — D-14) must not turn the violation into a pass, so conftest fails the test
   that made the call, and the run for a call made outside any test.

2. DB GUARD — a test not marked `db` never opens a database connection. Installed per
   test at the drivers' connect entry points (`asyncpg.connect` — which SQLAlchemy's
   asyncpg dialect resolves at call time — and `psycopg2.connect`), with the same
   raise-and-record shape, so `verify_schema_head`'s catch-all cannot hide a pure test
   that booted the app.

The test DB host and GCS are deliberately NOT blocked.
"""
from __future__ import annotations

import socket
import threading
from typing import Callable, List, Optional

# Suffix match: the host itself or any subdomain of it.
PROVIDER_HOST_SUFFIXES = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",      # Gemini (AI Studio)
    "aiplatform.googleapis.com",              # Gemini on Vertex AI (global endpoint)
    "api.x.ai",
    "smith.langchain.com",                    # LangSmith tracing (api., eu.api., …)
    "api.moonshot.ai",                        # Kimi
    "api.moonshot.cn",
)


def is_provider_host(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    if not isinstance(host, str):
        return False
    h = host.strip().lower().rstrip(".")
    if h.endswith("-aiplatform.googleapis.com"):   # Vertex regional: europe-west1-aiplatform…
        return True
    return any(h == s or h.endswith("." + s) for s in PROVIDER_HOST_SUFFIXES)


class ProviderCallBlocked(RuntimeError):
    """Deliberately NOT an OSError: network-retry code must not mistake it for a blip."""


class DbAccessInPureTest(RuntimeError):
    pass


class Recorder:
    """Thread-safe log of violations, tagged with the test running when they happened."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current: Optional[str] = None
        self.events: List[tuple] = []           # (nodeid or None, message)

    def record(self, message: str) -> None:
        with self._lock:
            self.events.append((self.current, message))

    def mark(self) -> int:
        with self._lock:
            return len(self.events)

    def since(self, mark: int) -> List[str]:
        with self._lock:
            return [m for _, m in self.events[mark:]]

    def discard_since(self, mark: int) -> List[str]:
        """For the guards' OWN tests: take back what they provoked on purpose."""
        with self._lock:
            taken = [m for _, m in self.events[mark:]]
            del self.events[mark:]
            return taken

    def outside_tests(self) -> List[str]:
        with self._lock:
            return [m for nid, m in self.events if nid is None]


NETWORK = Recorder()
DB = Recorder()

_installed = False
_real_getaddrinfo: Callable = socket.getaddrinfo
_real_gethostbyname: Callable = socket.gethostbyname


def _blocked(host) -> ProviderCallBlocked:
    msg = (f"outbound call to LLM provider host {host!r} blocked: tests must never reach a "
           f"provider (tests/guards.py). Inject a fake model instead.")
    NETWORK.record(msg)
    return ProviderCallBlocked(msg)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if is_provider_host(host):
        raise _blocked(host)
    return _real_getaddrinfo(host, *args, **kwargs)


def _guarded_gethostbyname(host):
    if is_provider_host(host):
        raise _blocked(host)
    return _real_gethostbyname(host)


def install_network_guard() -> None:
    global _installed
    if _installed:
        return
    socket.getaddrinfo = _guarded_getaddrinfo
    socket.gethostbyname = _guarded_gethostbyname
    _installed = True


def network_guard_installed() -> bool:
    return socket.getaddrinfo is _guarded_getaddrinfo


def block_db_connections(monkeypatch, nodeid: str) -> None:
    """Replace the drivers' connect functions for one test (undone by monkeypatch)."""
    def refuse(driver: str):
        def _connect(*args, **kwargs):
            msg = (f"{nodeid} opened a database connection ({driver}) but is not marked "
                   "`db`. Mark it `@pytest.mark.db` (or its module `pytestmark`), or keep "
                   "it pure (tests/guards.py).")
            DB.record(msg)
            raise DbAccessInPureTest(msg)
        return _connect

    try:
        import asyncpg
        import asyncpg.connection
        monkeypatch.setattr(asyncpg, "connect", refuse("asyncpg"))
        monkeypatch.setattr(asyncpg.connection, "connect", refuse("asyncpg"))
    except ImportError:                                   # pragma: no cover
        pass
    try:
        import psycopg2
        monkeypatch.setattr(psycopg2, "connect", refuse("psycopg2"))
    except ImportError:                                   # pragma: no cover
        pass
