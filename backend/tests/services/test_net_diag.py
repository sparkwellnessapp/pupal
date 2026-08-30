"""
net_diag — network-vs-provider failure diagnosis (probes mocked; no sockets).
"""
import asyncio
import socket
from unittest.mock import AsyncMock, patch

import app.services.net_diag as nd


def _run(coro):
    return asyncio.run(coro)


def _fresh_cache():
    nd._cache = None


# ---------------------------------------------------------------------------
# DNS-error detection (walks the exception chain)
# ---------------------------------------------------------------------------

def test_is_dns_error_direct_and_nested():
    assert nd.is_dns_error(socket.gaierror(11001, "getaddrinfo failed"))
    outer = RuntimeError("wrapper")
    outer.__cause__ = ConnectionError("x")
    outer.__cause__.__cause__ = socket.gaierror(11001, "boom")
    assert nd.is_dns_error(outer)
    assert nd.is_dns_error(ValueError("[Errno 11001] getaddrinfo failed"))
    assert not nd.is_dns_error(TimeoutError("deadline"))
    assert not nd.is_dns_error(None)


# ---------------------------------------------------------------------------
# Verdict logic (probes mocked)
# ---------------------------------------------------------------------------

def _classify_with(tcp: bool, dns: bool) -> str:
    _fresh_cache()
    with patch.object(nd, "_tcp_ok", AsyncMock(return_value=tcp)), \
         patch.object(nd, "_dns_ok", AsyncMock(return_value=dns)):
        return _run(nd.classify_connectivity())


def test_verdicts():
    assert _classify_with(tcp=False, dns=False) == "local-no-internet"
    assert _classify_with(tcp=True, dns=False) == "local-dns"
    assert _classify_with(tcp=True, dns=True) == "internet-ok"


def test_verdict_is_cached_one_probe_per_window():
    _fresh_cache()
    tcp = AsyncMock(return_value=True)
    dns = AsyncMock(return_value=True)
    with patch.object(nd, "_tcp_ok", tcp), patch.object(nd, "_dns_ok", dns):
        async def twice():
            a = await nd.classify_connectivity()
            b = await nd.classify_connectivity()
            return a, b
        assert _run(twice()) == ("internet-ok", "internet-ok")
    assert tcp.call_count == len(nd._PROBE_IPS)     # probed exactly once
    _fresh_cache()


def test_diagnose_never_raises_and_returns_verdict():
    _fresh_cache()
    with patch.object(nd, "_tcp_ok", AsyncMock(return_value=False)), \
         patch.object(nd, "_dns_ok", AsyncMock(return_value=False)):
        v = _run(nd.diagnose_transport_failure(
            "unit test", socket.gaierror(11001, "getaddrinfo failed")))
    assert v == "local-no-internet"
    _fresh_cache()

    with patch.object(nd, "classify_connectivity",
                      AsyncMock(side_effect=RuntimeError("probe broke"))):
        assert _run(nd.diagnose_transport_failure("unit test")) == "unknown"
