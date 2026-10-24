"""
scan_client — every answer scan-service can give becomes a TYPED outcome
(ScanServiceError with a code) or a result; never an untyped crash, which
step 0 could not land as a retryable compile failure. No network: httpx's
MockTransport stands in for the service.
"""
import asyncio

import httpx
import pytest

from app.services.capture import scan_client as sc


def _client(monkeypatch, handler):
    monkeypatch.setattr(sc, "_id_token", lambda audience: "tok")
    real = httpx.AsyncClient
    monkeypatch.setattr(sc.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return sc.HttpScanClient("https://scan.test")


def _analyze(client):
    return asyncio.run(client.analyze("gs://b/raw", "gs://b/p.jpg", timeout_s=5))


@pytest.mark.parametrize("response,code,transient", [
    (httpx.Response(200, text="not json"), "bad_response", False),
    (httpx.Response(200, json=["a", "list"]), "bad_response", False),
    (httpx.Response(200, json={"image_w": 1}), "bad_response", False),          # fields missing
    (httpx.Response(422, json=["validation", "detail"]), "refused", False),     # list-shaped 4xx
    (httpx.Response(422, json={"code": "undecodable"}), "undecodable", False),
    (httpx.Response(403, json={"code": "storage_forbidden"}), "storage_forbidden", False),
    (httpx.Response(502, json={"code": "storage_error"}), "server_error", True),
])
def test_every_answer_is_a_typed_outcome(monkeypatch, response, code, transient):
    client = _client(monkeypatch, lambda request: response)
    with pytest.raises(sc.ScanServiceError) as exc:
        _analyze(client)
    assert (exc.value.code, exc.value.transient) == (code, transient)


def test_a_failed_id_token_is_transient_and_typed(monkeypatch):
    def boom(audience):
        raise RuntimeError("metadata server")
    monkeypatch.setattr(sc, "_id_token", boom)
    with pytest.raises(sc.ScanServiceError) as exc:
        _analyze(sc.HttpScanClient("https://scan.test"))
    assert exc.value.code == "id_token:RuntimeError" and exc.value.transient


class _Flaky:
    def __init__(self, failures):
        self.calls, self.failures = 0, failures

    async def compile(self, pages_snapshot, scan_pipeline_version, out_uri, *, timeout_s):
        self.calls += 1
        if self.calls <= self.failures:
            raise sc.ScanServiceError("timeout", transient=True)
        return sc.CompileResult(pdf_uri=out_uri, page_count=1, bytes=10)


def test_one_retry_only_when_the_deadline_can_pay_for_a_real_compile(monkeypatch):
    monkeypatch.setattr(sc, "_RETRY_BACKOFF_S", 0.0)
    flaky = _Flaky(failures=1)
    asyncio.run(sc.compile_with_retry(flaky, [], "v", "gs://b/x.pdf", deadline_s=300))
    assert flaky.calls == 2
    short = _Flaky(failures=1)
    with pytest.raises(sc.ScanServiceError):
        asyncio.run(sc.compile_with_retry(short, [], "v", "gs://b/x.pdf", deadline_s=40))
    assert short.calls == 1                       # 40 s cannot pay for a second compile
