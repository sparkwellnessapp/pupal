"""
net_diag — one-line network diagnosis for transport failures (2026-08-12).

Motivation: two days of ReadTimeout/DNS storms (hotel WiFi) were repeatedly
mis-read as provider incidents because nothing distinguished "this machine's
network is broken" from "the provider is slow". This module answers that with
an ACTIVE PROBE run only when something has already failed:

  * TCP connect to well-known IP LITERALS (no DNS involved) — tests raw
    internet reachability through the router/ISP/VPN.
  * getaddrinfo on well-known hostnames — tests the DNS resolver path
    (hotel captive portals and VPNs break this first).

Verdicts:
  local-no-internet — TCP to raw IPs fails: the LINK is down (WiFi/router/
                      ISP/VPN). Provider is definitively not the cause.
  local-dns         — internet reachable but hostnames don't resolve: the
                      RESOLVER is broken (ISP DNS / captive portal / VPN).
  internet-ok       — the machine can reach the internet and resolve names;
                      the failure is provider-side or payload/congestion
                      (large uploads on a weak/shared uplink stall first).

The probe is cheap (<~3s, failure paths only) and the verdict is cached for
30s so a burst of failing calls produces ONE diagnosis, not a probe storm.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import time

logger = logging.getLogger(__name__)

# IP literals (DNS-free reachability): Cloudflare + Quad9 public resolvers'
# TCP/443. Both failing while the machine is "online" is effectively
# impossible without a local network problem.
_PROBE_IPS = ("1.1.1.1", "9.9.9.9")
# Independent, always-up hostnames for the resolver check.
_PROBE_HOSTS = ("cloudflare.com", "amazon.com")
_PROBE_TIMEOUT_S = 3.0
_VERDICT_TTL_S = 30.0

_cache: tuple[float, str] | None = None
_probe_lock = asyncio.Lock()


def is_dns_error(exc: BaseException | None) -> bool:
    """Walk the exception chain for a DNS-resolution failure."""
    seen = 0
    while exc is not None and seen < 10:
        if isinstance(exc, socket.gaierror) or "getaddrinfo" in str(exc):
            return True
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return False


async def _tcp_ok(ip: str) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443), timeout=_PROBE_TIMEOUT_S)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _dns_ok(host: str) -> bool:
    try:
        await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, 443),
            timeout=_PROBE_TIMEOUT_S)
        return True
    except Exception:
        return False


async def classify_connectivity() -> str:
    """Active probe -> 'local-no-internet' | 'local-dns' | 'internet-ok'.
    Cached for 30s; concurrent callers share one probe."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _VERDICT_TTL_S:
        return _cache[1]
    async with _probe_lock:
        now = time.monotonic()
        if _cache is not None and now - _cache[0] < _VERDICT_TTL_S:
            return _cache[1]
        tcp_results = await asyncio.gather(*[_tcp_ok(ip) for ip in _PROBE_IPS])
        if not any(tcp_results):
            verdict = "local-no-internet"
        else:
            dns_results = await asyncio.gather(
                *[_dns_ok(h) for h in _PROBE_HOSTS])
            verdict = "internet-ok" if any(dns_results) else "local-dns"
        _cache = (time.monotonic(), verdict)
        return verdict


async def diagnose_transport_failure(
    context: str,
    exc: BaseException | None = None,
) -> str:
    """Probe + emit ONE unambiguous diagnosis line. Never raises."""
    try:
        verdict = await classify_connectivity()
        dns_hint = " (the failing call itself died on DNS resolution)" \
            if is_dns_error(exc) else ""
        if verdict == "local-no-internet":
            logger.error(
                "NETWORK DIAGNOSIS [%s]: LOCAL NETWORK DOWN — this machine "
                "cannot reach the internet at all (raw-IP probe failed). "
                "WiFi/router/ISP/VPN problem; the provider is NOT the "
                "cause.%s", context, dns_hint)
        elif verdict == "local-dns":
            logger.error(
                "NETWORK DIAGNOSIS [%s]: LOCAL DNS FAILURE — internet is "
                "reachable but hostname resolution is broken (ISP DNS / "
                "captive portal / VPN). The provider is NOT the cause.%s",
                context, dns_hint)
        else:
            logger.warning(
                "NETWORK DIAGNOSIS [%s]: internet reachable and DNS working — "
                "the failure looks provider-side or payload/congestion "
                "related (large uploads stall first on weak/shared uplinks, "
                "e.g. hotel WiFi).%s", context, dns_hint)
        return verdict
    except Exception:
        logger.warning("NETWORK DIAGNOSIS [%s]: probe itself failed", context,
                       exc_info=True)
        return "unknown"
