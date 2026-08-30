"""
B9 live smoke (phase evidence, spec §5/B9): 40 files × ~3MB through the real
create-then-append chain — real DB, real GCS, real FOR-UPDATE serialization.
The ONLY patched seam is the Cloud Tasks enqueue (otherwise 40 real VLM
transcription runs would fire).

Explicit-run only: B9_SMOKE=1 pytest tests/api/test_b9_smoke.py -s
The timing output is pasted into batch_redesign_LOG.md as the launch-blocker
proof (the legacy single-multipart intake could not transit 40×3MB at all —
Cloud Run's 32MB request ceiling).
"""
import io
import os
import time
from statistics import mean
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("B9_SMOKE"),
                       reason="explicit smoke only (set B9_SMOKE=1)"),
]

N_FILES = 40
FILE_MB = 3


def test_b9_live_smoke_40_files(client, user_a, headers_a, rubric_a):
    payload = b"%PDF-1.4\n" + os.urandom(FILE_MB * 1024 * 1024 - 16)
    enqueue = AsyncMock()

    with patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        t0 = time.monotonic()
        created = client.post(
            "/api/v0/batches", headers=headers_a,
            json={"rubric_id": rubric_a["rubric_id"], "class_id": None,
                  "name": "B9 smoke 40×3MB"},
        )
        assert created.status_code == 201, created.text
        batch_id = created.json()["batch_id"]
        t_create = time.monotonic() - t0

        append_times: list[float] = []
        for i in range(N_FILES):
            ta = time.monotonic()
            resp = client.post(
                f"/api/v0/batches/{batch_id}/files", headers=headers_a,
                files={"file": (f"scan_{i:02d}.pdf", io.BytesIO(payload),
                                "application/pdf")},
                data={"client_file_id": str(uuid4())},
            )
            assert resp.status_code == 200, f"file {i}: {resp.text}"
            assert resp.json()["test_count"] == i + 1
            append_times.append(time.monotonic() - ta)

        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
        assert detail.status_code == 200
        rollup = detail.json()["rollup"]

    total_s = time.monotonic() - t0
    print("\n=== B9 LIVE SMOKE ===")
    print(f"files: {N_FILES} × {FILE_MB}MB  (total {N_FILES * FILE_MB}MB)")
    print(f"create: {t_create * 1000:.0f}ms")
    print(f"appends: total {sum(append_times):.1f}s · "
          f"mean {mean(append_times):.2f}s · "
          f"min {min(append_times):.2f}s · max {max(append_times):.2f}s")
    print(f"wall-clock end-to-end: {total_s:.1f}s")
    print(f"final rollup: {rollup}")
    print(f"enqueues fired: {enqueue.await_count}")

    assert rollup["total"] == N_FILES
    assert rollup["transcribing"] == N_FILES
    assert rollup["transcription_failed"] == 0
    assert enqueue.await_count == N_FILES

    # Leave nothing behind on the shared dev DB.
    from tests.api.test_transcription_review import _cleanup_batch
    _cleanup_batch(batch_id, [])
