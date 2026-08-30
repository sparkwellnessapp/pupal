"""
P1 intake v2 (batch-redesign spec v2, items B7 + B9).

B9 — create-then-append: POST /batches is metadata-only; files arrive one per
request via POST /batches/{id}/files with a client-generated idempotency key
(client_file_id). FOR UPDATE serializes appends; jobs are the rollup's truth.
B7 — honest per-file validation (magic bytes, non-empty, size cap) with §3.2
reasons; a rejected file never becomes a job and never reaches GCS.

Live-DB integration tests. GCS + Cloud Tasks patched at the module seams.
"""
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import sqlalchemy

from app.config import settings
from tests.api.test_batch_exposure import _insert_batch
from tests.api.test_batch_grading import _clean_draft
from tests.api.test_transcription_review import (
    _cleanup_batch,
    _insert_transcription_sync,
    _sync_engine,
    _user_id,
)

PDF_BYTES = b"%PDF-1.4 stub content for intake tests"


def _job_rows(batch_id: str) -> list[tuple]:
    engine = _sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sqlalchemy.text(
                "SELECT status, source_filename, doc_priority, client_file_id "
                "FROM transcription_jobs WHERE batch_id = :bid ORDER BY doc_priority"
            ),
            {"bid": batch_id},
        ).fetchall()
    engine.dispose()
    return [tuple(r) for r in rows]


def _set_test_count(batch_id: str, n: int) -> None:
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE grading_batches SET test_count = :n WHERE id = :id"),
            {"n": n, "id": batch_id},
        )
        conn.commit()
    engine.dispose()


def _create_batch(client, headers, rubric_id: str, name: str | None = None) -> str:
    resp = client.post(
        "/api/v0/batches",
        json={"rubric_id": rubric_id, "class_id": None, "name": name},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["test_count"] == 0
    return body["batch_id"]


def _append(client, headers, batch_id: str, filename: str = "scan.pdf",
            content: bytes = PDF_BYTES, client_file_id: str | None = None):
    return client.post(
        f"/api/v0/batches/{batch_id}/files",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
        data={"client_file_id": client_file_id or str(uuid4())},
    )


def _intake_mocks():
    gcs = MagicMock()
    gcs.upload_bytes.return_value = "ok"
    enqueue = AsyncMock()
    return gcs, enqueue


# ---------------------------------------------------------------------------
# B9 — create-then-append
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_batch_metadata_only(client, user_a, headers_a, rubric_a):
    batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"], name="מקבץ B9")
    try:
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        assert detail["name"] == "מקבץ B9"
        assert detail["rollup"]["total"] == 0
        assert detail["active_jobs"] == []
        assert detail["transcriptions"] == []
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_create_batch_uncompiled_rubric_400(client, user_a, headers_a):
    resp = client.post(
        "/api/v0/batches",
        json={"rubric_id": str(uuid4()), "class_id": None, "name": None},
        headers=headers_a,
    )
    assert resp.status_code == 404  # unknown rubric = not owned = 404


@pytest.mark.integration
def test_append_file_creates_job_and_enqueues(client, user_a, headers_a, rubric_a):
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            resp = _append(client, headers_a, batch_id, filename="a.pdf")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["filename"] == "a.pdf"
            assert body["test_count"] == 1

            rows = _job_rows(batch_id)
            assert len(rows) == 1
            status, fname, prio, cfid = rows[0]
            assert (status, fname, prio) == ("queued", "a.pdf", 0)
            assert cfid is not None
            assert gcs.upload_bytes.call_count == 1
            assert str(gcs.upload_bytes.call_args[0][1]).startswith("transcriptions/")
            assert enqueue.await_count == 1

            detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
            assert detail["rollup"]["total"] == 1
            assert [j["filename"] for j in detail["active_jobs"]] == ["a.pdf"]
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_append_idempotent_on_retry(client, user_a, headers_a, rubric_a):
    """Same client_file_id twice → one job, both responses 200 with the SAME
    body; the retry never enqueues a second task."""
    gcs, enqueue = _intake_mocks()
    cfid = str(uuid4())
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            first = _append(client, headers_a, batch_id, client_file_id=cfid)
            second = _append(client, headers_a, batch_id, client_file_id=cfid)
            assert first.status_code == 200 and second.status_code == 200
            assert first.json() == second.json()

            assert len(_job_rows(batch_id)) == 1
            assert enqueue.await_count == 1
            detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
            assert detail["rollup"]["total"] == 1
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_append_serializes_doc_priority(client, user_a, headers_a, rubric_a):
    """Two concurrent appends → distinct doc_priority {0,1} (FOR UPDATE on the
    batch row serializes the count+insert)."""
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(_append, client, headers_a, batch_id, f"p{i}.pdf")
                    for i in range(2)
                ]
                results = [f.result() for f in futures]
            assert all(r.status_code == 200 for r in results), [r.text for r in results]

            rows = _job_rows(batch_id)
            assert sorted(r[2] for r in rows) == [0, 1]      # distinct priorities
            counts = sorted(r.json()["test_count"] for r in results)
            assert counts == [1, 2]
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_rollup_total_from_jobs(client, user_a, headers_a, rubric_a):
    """B9.5: for jobs-based batches rollup.total = COUNT(jobs) — the stored
    test_count column is NOT the source (sabotaged to 99 to prove it)."""
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            _append(client, headers_a, batch_id, "a.pdf")
            _append(client, headers_a, batch_id, "b.pdf")
            _set_test_count(batch_id, 99)

            detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
            assert detail["rollup"]["total"] == 2
            assert detail["rollup"]["transcribing"] == 2
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_legacy_batch_rollup_unchanged(client, user_a, headers_a, rubric_a):
    """Pre-016 batches (no job rows): the ledger/inference path still governs —
    total = stored test_count, transcribing inferred over absence."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=3)
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id, _clean_draft().model_dump(mode="json"),
    )
    try:
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        assert detail["rollup"]["total"] == 3
        assert detail["rollup"]["transcribed"] == 1
        assert detail["rollup"]["transcribing"] == 2      # 3 − 1 rows − 0 ledger
    finally:
        _cleanup_batch(batch_id, [tx])


# ---------------------------------------------------------------------------
# B7 — honest per-file validation (§3.2 reasons; nothing silently dropped)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_append_rejects_fake_pdf(client, user_a, headers_a, rubric_a):
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            resp = _append(client, headers_a, batch_id, "photo.pdf",
                           content=b"\xff\xd8\xff JPEG bytes actually")
            assert resp.status_code == 422, resp.text
            assert resp.json()["detail"] == "לא קובץ PDF"
            assert _job_rows(batch_id) == []                # no job row
            assert gcs.upload_bytes.call_count == 0         # validated BEFORE GCS
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_append_rejects_empty(client, user_a, headers_a, rubric_a):
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            resp = _append(client, headers_a, batch_id, "empty.pdf", content=b"")
            assert resp.status_code == 422, resp.text
            assert resp.json()["detail"] == "קובץ ריק"
            assert _job_rows(batch_id) == []
            assert gcs.upload_bytes.call_count == 0
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_append_rejects_oversize(client, user_a, headers_a, rubric_a):
    gcs, enqueue = _intake_mocks()
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue), \
         patch.object(settings, "batch_max_upload_file_mb", 1):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            big = b"%PDF-1.4 " + b"x" * (1024 * 1024 + 64)
            resp = _append(client, headers_a, batch_id, "big.pdf", content=big)
            assert resp.status_code == 422, resp.text
            assert resp.json()["detail"] == "גדול מדי (1MB)"
            assert _job_rows(batch_id) == []
            assert gcs.upload_bytes.call_count == 0
        finally:
            _cleanup_batch(batch_id, [])


# ---------------------------------------------------------------------------
# Failure semantics on the new path
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_append_gcs_failure_no_job(client, user_a, headers_a, rubric_a):
    """Per-file atomicity (replaces the retired all-or-nothing create): a GCS
    failure 502s THIS file only; no job row, batch intact for other appends."""
    gcs, enqueue = _intake_mocks()
    gcs.upload_bytes.side_effect = TimeoutError("uplink stalled")
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            resp = _append(client, headers_a, batch_id, "stall.pdf")
            assert resp.status_code == 502, resp.text
            assert "stall.pdf" in resp.json()["detail"]
            assert _job_rows(batch_id) == []
            assert enqueue.await_count == 0

            gcs.upload_bytes.side_effect = None
            ok = _append(client, headers_a, batch_id, "next.pdf")
            assert ok.status_code == 200                    # batch still usable
        finally:
            _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_append_enqueue_failure_marks_job_failed(client, user_a, headers_a, rubric_a):
    """Enqueue failure AFTER commit → the existing failed-with-reason path
    (durable red card, retryable) — never an unreachable 'queued' row."""
    gcs, _ = _intake_mocks()
    boom = AsyncMock(side_effect=RuntimeError("tasks API down"))
    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", boom):
        batch_id = _create_batch(client, headers_a, rubric_a["rubric_id"])
        try:
            resp = _append(client, headers_a, batch_id, "doomed.pdf")
            assert resp.status_code == 200, resp.text       # append itself succeeded

            rows = _job_rows(batch_id)
            assert len(rows) == 1
            assert rows[0][0] == "failed"
            detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
            assert [f["filename"] for f in detail["transcription_failures"]] == ["doomed.pdf"]
        finally:
            _cleanup_batch(batch_id, [])
