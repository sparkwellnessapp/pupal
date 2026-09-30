"""A-10 probes, run ONLY in a subprocess by tests/test_a10_guards.py (the file name does
not match `test_*.py`, so the suite never collects it). Each probe provokes a guard and
SWALLOWS the exception, exactly as degrading production code would: the guard must still
fail the test. The last probe proves a `db`-marked test is left alone."""
import asyncio
import socket

import pytest


def test_probe_swallowed_provider_call():
    try:
        socket.getaddrinfo("api.anthropic.com", 443)
    except Exception:
        pass


def test_probe_swallowed_db_connect_in_pure_test():
    import asyncpg
    try:
        asyncio.run(asyncpg.connect("postgresql://u@127.0.0.1:1/x", timeout=2))
    except Exception:
        pass


@pytest.mark.db
def test_probe_db_marked_test_may_connect():
    import asyncpg
    with pytest.raises(OSError):          # a REAL refusal from port 1, not the guard
        asyncio.run(asyncpg.connect("postgresql://u@127.0.0.1:1/x", timeout=2))
