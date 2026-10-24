"""
The typed client for scan-service (PR_in_house_scanning.md §7) — and the ONE
retry layer for calling it.

scan-service is private on Cloud Run: every call carries a Google ID token
whose audience is `settings.scan_service_url` (the backend's service account
holds roles/run.invoker on it). There is no SDK retry underneath (httpx has
none), so `compile` owns exactly one bounded retry on TRANSIENT failures —
transport errors and 5xx — inside the caller's deadline. A 4xx is a verdict
(the raw photo is missing; the pipeline version differs) and is never retried.

Injectable: tests replace the client with `set_scan_client(fake)` — no test
ever reaches the network.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import httpx

from ...config import settings

logger = logging.getLogger(__name__)

_RETRY_BACKOFF_S = 5.0
# A second compile attempt is worth starting only with room for a REAL compile
# (20 pages rendered at full resolution): less than this, and the retry merely
# moves the failure later and eats the pipeline's runway.
_MIN_RETRY_BUDGET_S = 60.0


class ScanServiceError(Exception):
    """scan-service answered, and the answer was a refusal (4xx), or it could
    not be reached at all. `code` is the service's machine code or a transport
    label; never a filename or a name (OD-B4)."""

    def __init__(self, code: str, *, status: Optional[int] = None, transient: bool = False):
        super().__init__(code if status is None else f"{status} {code}")
        self.code = code
        self.status = status
        self.transient = transient


@dataclass(frozen=True)
class AnalyzeResult:
    image_w: int
    image_h: int
    corners: list[list[float]]
    corners_source: str
    confidence: float
    quality: dict
    preview_uri: str


@dataclass(frozen=True)
class CompileResult:
    pdf_uri: str
    page_count: int
    bytes: int


class ScanClient(Protocol):
    async def analyze(self, raw_uri: str, preview_uri_out: str, *, timeout_s: float) -> AnalyzeResult: ...
    async def render(self, raw_uri: str, corners, rotation: int, long_side: int, out_uri: str,
                     *, enhance: bool, timeout_s: float) -> None: ...
    async def compile(self, pages_snapshot: list[dict], scan_pipeline_version: str, out_uri: str,
                      *, timeout_s: float) -> CompileResult: ...


def _id_token(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), audience)


class HttpScanClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def _post(self, path: str, body: dict, timeout_s: float) -> dict[str, Any]:
        try:
            token = await asyncio.to_thread(_id_token, self.base_url)
        except Exception as exc:
            # A metadata-server hiccup or missing credentials: typed, so step 0
            # lands it as CaptureCompileFailed (not an untyped crash), and
            # transient, so the one owned retry gets its chance.
            raise ScanServiceError(f"id_token:{type(exc).__name__}", transient=True) from None
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                r = await http.post(f"{self.base_url}{path}", json=body,
                                    headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            raise ScanServiceError("timeout", transient=True) from None
        except httpx.TransportError as exc:
            raise ScanServiceError(type(exc).__name__, transient=True) from None
        if r.status_code >= 500:
            raise ScanServiceError("server_error", status=r.status_code, transient=True)
        if r.status_code >= 400:
            code = "refused"
            try:
                body = r.json()
                if isinstance(body, dict) and isinstance(body.get("code"), str):
                    code = body["code"]
            except ValueError:
                pass
            raise ScanServiceError(code, status=r.status_code)
        try:
            body = r.json()
        except ValueError:
            raise ScanServiceError("bad_response", status=r.status_code) from None
        if not isinstance(body, dict):
            raise ScanServiceError("bad_response", status=r.status_code)
        return body

    async def analyze(self, raw_uri, preview_uri_out, *, timeout_s):
        d = await self._post("/analyze", {"raw_uri": raw_uri, "preview_uri_out": preview_uri_out},
                             timeout_s)
        try:
            return AnalyzeResult(image_w=d["image_w"], image_h=d["image_h"], corners=d["corners"],
                                 corners_source=d["corners_source"], confidence=d["confidence"],
                                 quality=d["quality"], preview_uri=d["preview_uri"])
        except KeyError:
            raise ScanServiceError("bad_response") from None

    async def render(self, raw_uri, corners, rotation, long_side, out_uri, *, enhance, timeout_s):
        await self._post("/render", {"raw_uri": raw_uri, "corners": corners, "rotation": rotation,
                                     "long_side": long_side, "out_uri": out_uri,
                                     "enhance": enhance}, timeout_s)

    async def compile(self, pages_snapshot, scan_pipeline_version, out_uri, *, timeout_s):
        d = await self._post("/compile", {"pages_snapshot": pages_snapshot,
                                          "scan_pipeline_version": scan_pipeline_version,
                                          "out_uri": out_uri}, timeout_s)
        try:
            return CompileResult(pdf_uri=d["pdf_uri"], page_count=d["page_count"],
                                 bytes=d["bytes"])
        except KeyError:
            raise ScanServiceError("bad_response") from None


_client: Optional[ScanClient] = None


def get_scan_client() -> ScanClient:
    global _client
    if _client is None:
        if not settings.scan_service_url:
            raise ScanServiceError("scan_service_unconfigured")
        _client = HttpScanClient(settings.scan_service_url)
    return _client


def set_scan_client(client: Optional[ScanClient]) -> None:
    """Tests inject a fake; production never calls this."""
    global _client
    _client = client


async def compile_with_retry(client: ScanClient, pages_snapshot: list[dict],
                             scan_pipeline_version: str, out_uri: str, *,
                             deadline_s: Optional[float]) -> CompileResult:
    """`deadline_s` is how long the CALLER can still wait (None = the
    configured timeout). One retry, on a transient failure only, and only if
    the deadline can still pay for a second attempt."""
    loop = asyncio.get_running_loop()
    started = loop.time()

    def remaining() -> float:
        cap = settings.scan_compile_timeout_s
        if deadline_s is None:
            return cap
        return min(cap, deadline_s - (loop.time() - started))

    for attempt in (1, 2):
        budget = remaining()
        if budget <= 1.0:
            raise ScanServiceError("budget_exhausted")
        try:
            return await client.compile(pages_snapshot, scan_pipeline_version, out_uri,
                                        timeout_s=budget)
        except ScanServiceError as exc:
            if (not exc.transient or attempt == 2
                    or remaining() < _RETRY_BACKOFF_S + _MIN_RETRY_BUDGET_S):
                raise
            logger.warning("scan_compile transient failure (%s) — retrying once", exc.code)
            await asyncio.sleep(_RETRY_BACKOFF_S)
    raise AssertionError("unreachable")
