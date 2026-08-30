"""
Step-1 upload hardening (2026-08-12): the source-PDF upload must be patient
on weak uplinks and must never take a finished pipeline result down with it.

  * gcs_service.upload_bytes — resumable chunks + explicit request timeout +
    a 300s SDK retry budget (the 120s default died mid-body on hotel WiFi).
  * transcribe_one._join_upload_with_retry — a failed overlapped upload is
    re-attempted ON ITS OWN (never the pipeline), then and only then raises.

No network, no GCS: SDK boundary mocked.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.transcribe_one as t1
from app.services.gcs_service import (
    GCSService,
    _UPLOAD_CHUNK_BYTES,
    _UPLOAD_REQUEST_TIMEOUT_S,
    _UPLOAD_RETRY,
    _UPLOAD_RETRY_DEADLINE_S,
)


# ---------------------------------------------------------------------------
# upload_bytes — the patient-upload policy reaches the SDK call
# ---------------------------------------------------------------------------

def _service_with_mock_bucket() -> tuple[GCSService, MagicMock]:
    svc = GCSService.__new__(GCSService)   # skip __init__ (settings + client)
    svc.bucket_name = "test-bucket"
    svc.bucket = MagicMock()
    return svc, svc.bucket


def test_upload_bytes_uses_resumable_chunks_and_patient_policy():
    svc, bucket = _service_with_mock_bucket()
    blob = bucket.blob.return_value

    result = svc.upload_bytes(b"pdf-bytes", "transcriptions/u/x.pdf")

    assert result == "transcriptions/u/x.pdf"
    bucket.blob.assert_called_once_with(
        "transcriptions/u/x.pdf", chunk_size=_UPLOAD_CHUNK_BYTES
    )
    blob.upload_from_string.assert_called_once()
    kwargs = blob.upload_from_string.call_args.kwargs
    assert kwargs["timeout"] == _UPLOAD_REQUEST_TIMEOUT_S
    assert kwargs["retry"] is _UPLOAD_RETRY
    assert kwargs["content_type"] == "application/pdf"


def test_upload_retry_budget_is_extended_beyond_sdk_default():
    # The observed failure was the SDK's default 120s budget expiring.
    assert _UPLOAD_RETRY._timeout == _UPLOAD_RETRY_DEADLINE_S == 300.0
    assert _UPLOAD_CHUNK_BYTES % (256 * 1024) == 0   # GCS chunk-size contract


# ---------------------------------------------------------------------------
# _join_upload_with_retry — upload-only recovery
# ---------------------------------------------------------------------------

async def _failing_upload():
    raise ConnectionError("write stalled")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(t1, "_UPLOAD_RETRY_BACKOFF_S", 0.0)


def test_join_upload_happy_path_touches_nothing():
    async def scenario():
        task = asyncio.create_task(asyncio.sleep(0))
        with patch.object(t1, "get_gcs_service") as get_svc:
            await t1._join_upload_with_retry(task, b"x", "p.pdf", "f.pdf")
            get_svc.assert_not_called()
    _run(scenario())


def test_join_upload_recovers_on_first_reattempt():
    async def scenario():
        task = asyncio.create_task(_failing_upload())
        gcs = MagicMock()
        gcs.upload_bytes.return_value = "p.pdf"
        with patch.object(t1, "get_gcs_service", return_value=gcs):
            await t1._join_upload_with_retry(task, b"x", "p.pdf", "f.pdf")
        assert gcs.upload_bytes.call_count == 1
        gcs.upload_bytes.assert_called_with(b"x", "p.pdf", "application/pdf")
    _run(scenario())


def test_join_upload_exhausts_reattempts_then_raises_last_error():
    async def scenario():
        task = asyncio.create_task(_failing_upload())
        gcs = MagicMock()
        gcs.upload_bytes.side_effect = TimeoutError("still stalled")
        diag = AsyncMock(return_value="internet-ok")
        with patch.object(t1, "get_gcs_service", return_value=gcs), \
             patch("app.services.net_diag.diagnose_transport_failure", diag):
            with pytest.raises(TimeoutError, match="still stalled"):
                await t1._join_upload_with_retry(task, b"x", "p.pdf", "f.pdf")
        assert gcs.upload_bytes.call_count == t1._UPLOAD_EXTRA_ATTEMPTS
        diag.assert_awaited_once()
    _run(scenario())
