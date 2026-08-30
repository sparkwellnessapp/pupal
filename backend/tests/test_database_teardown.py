"""
Session-teardown resilience (2026-08-07 incident).

The Supabase transaction pooler resets connections left idle-in-transaction.
Two hardening properties are pinned here, both pure (fake sessions, no DB):

  * get_db teardown NEVER raises: a dead connection's close() failure is
    logged and the connection invalidated — not detonated through the ASGI
    stack after the response was already sent.
  * get_db_context preserves the ORIGINAL exception when rollback() also
    fails on the dead connection — the commit failure the caller needs to
    see must not be masked by the rollback failure.
"""
import asyncio
from unittest.mock import patch

import pytest

from app.database import get_db, get_db_context


class _FakeSession:
    def __init__(self, close_raises=False, rollback_raises=False):
        self.close_raises = close_raises
        self.rollback_raises = rollback_raises
        self.calls: list[str] = []

    async def close(self):
        self.calls.append("close")
        if self.close_raises:
            raise ConnectionError("connection was closed in the middle of operation")

    async def rollback(self):
        self.calls.append("rollback")
        if self.rollback_raises:
            raise ConnectionError("connection was closed in the middle of operation")

    async def invalidate(self):
        self.calls.append("invalidate")


def _run(coro):
    return asyncio.run(coro)


def test_get_db_teardown_swallows_dead_connection_close():
    session = _FakeSession(close_raises=True)
    with patch("app.database.AsyncSessionLocal", return_value=session):
        async def drive():
            gen = get_db()
            yielded = await gen.__anext__()
            assert yielded is session
            # Generator finalization runs the finally block — must NOT raise.
            await gen.aclose()
        _run(drive())
    assert "close" in session.calls
    assert "invalidate" in session.calls       # dead connection discarded


def test_get_db_teardown_noop_on_healthy_close():
    session = _FakeSession()
    with patch("app.database.AsyncSessionLocal", return_value=session):
        async def drive():
            gen = get_db()
            await gen.__anext__()
            await gen.aclose()
        _run(drive())
    assert session.calls == ["close"]          # no invalidate on the happy path


def test_get_db_context_preserves_original_exception_over_rollback_failure():
    session = _FakeSession(close_raises=True, rollback_raises=True)
    original = RuntimeError("commit failed: the error the caller must see")
    with patch("app.database.AsyncSessionLocal", return_value=session):
        async def drive():
            with pytest.raises(RuntimeError) as excinfo:
                async with get_db_context():
                    raise original
            assert excinfo.value is original   # NOT the rollback ConnectionError
        _run(drive())
    # rollback attempted, its failure invalidated, close attempted + invalidated
    assert session.calls == ["rollback", "invalidate", "close", "invalidate"]


def test_get_db_context_happy_path_closes_once():
    session = _FakeSession()
    with patch("app.database.AsyncSessionLocal", return_value=session):
        async def drive():
            async with get_db_context() as db:
                assert db is session
        _run(drive())
    assert session.calls == ["close"]
