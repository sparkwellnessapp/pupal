"""
PR-1 — extraction-job endpoint + lifecycle tests.

Two tiers:
  * Always-run: auth boundaries (401 on public endpoints, 403 on the internal
    task target) — no DB rows touched.
  * @pytest.mark.integration: require a live DATABASE_URL WITH migration 012
    applied. The module-level `jobs_table` fixture skips them cleanly when the
    table does not exist yet (pre-migration environments).

GCS and Cloud Tasks are always mocked — no bucket writes, no queue, no OpenAI.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from app.models.rubric_extraction_job import RubricExtractionJob

DOCX_BYTES = b"PK\x03\x04" + b"fake-docx-payload"
JOBS_URL = "/api/v0/rubrics/extraction-jobs"


# ---------------------------------------------------------------------------
# Direct-DB helpers. Each call builds a FRESH NullPool engine: asyncio.run()
# spins a new event loop per call, and the app's global engine pools
# connections bound to the TestClient's loop — reusing it raises
# "attached to a different loop". NullPool + dispose = loop-safe.
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def _fresh_session():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings

    # statement_cache_size=0 mirrors app/database.py — required through the
    # Supabase PgBouncer pooler (else DuplicatePreparedStatementError).
    engine = create_async_engine(
        settings.database_url, poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            yield db
    finally:
        await engine.dispose()


async def _table_exists() -> bool:
    async with _fresh_session() as db:
        row = await db.execute(text("SELECT to_regclass('public.rubric_extraction_jobs')"))
        return row.scalar() is not None


async def _insert_job(user_id, status="queued", **overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        user_id=user_id,
        status=status,
        source_gcs_uri="gs://test-bucket/rubric-sources/test.docx",
        source_filename="test.docx",
        source_sha256=uuid4().hex + uuid4().hex,  # unique 64-char pseudo-sha
        request_params={"name": "t", "subject": "computer_science", "locale": "he-IL"},
    )
    if status == "extracting":
        defaults.update(started_at=now)
    elif status == "completed":
        defaults.update(started_at=now, finished_at=now,
                        result_json={"questions": [], "total_points": "100"})
    elif status == "failed":
        defaults.update(started_at=None, finished_at=now, error_message="boom")
    defaults.update(overrides)

    async with _fresh_session() as db:
        job = RubricExtractionJob(**defaults)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job.id


async def _delete_job(job_id):
    async with _fresh_session() as db:
        await db.execute(delete(RubricExtractionJob).where(RubricExtractionJob.id == job_id))
        await db.commit()


async def _set_updated_at(job_id, dt):
    """Backdate the heartbeat (ORM onupdate would clobber it on normal writes)."""
    async with _fresh_session() as db:
        await db.execute(
            text("UPDATE rubric_extraction_jobs SET updated_at = :dt WHERE id = :id"),
            {"dt": dt, "id": str(job_id)},
        )
        await db.commit()


@pytest.fixture(scope="module")
def jobs_table(client):
    """Skip integration tests cleanly when migration 012 is not applied."""
    try:
        exists = asyncio.run(_table_exists())
    except Exception as e:  # no live DB at all
        pytest.skip(f"no live database: {e}")
    if not exists:
        pytest.skip("migration 012 not applied (rubric_extraction_jobs missing)")
    return True


def _mock_gcs():
    gcs = MagicMock()
    gcs.bucket_name = "test-bucket"
    gcs.upload_bytes = MagicMock(return_value="rubric-sources/x.docx")
    return gcs


def _submit(client, headers, content=DOCX_BYTES, filename="rubric.docx", **form):
    with patch("app.services.gcs_service.get_gcs_service", return_value=_mock_gcs()), \
         patch("app.api.v0.rubric_extraction_jobs.enqueue_extraction_task", new=AsyncMock()):
        return client.post(
            f"{JOBS_URL}/",
            headers=headers,
            files={"file": (filename, content,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data=form,
        )


# ===========================================================================
# Always-run: auth boundaries
# ===========================================================================

def test_submit_unauthenticated_401(client):
    resp = client.post(f"{JOBS_URL}/", files={"file": ("r.docx", DOCX_BYTES)})
    assert resp.status_code == 401


def test_status_unauthenticated_401(client):
    resp = client.get(f"{JOBS_URL}/{uuid4()}")
    assert resp.status_code == 401


def test_list_unauthenticated_401(client):
    resp = client.get(f"{JOBS_URL}/")
    assert resp.status_code == 401


def test_retry_unauthenticated_401(client):
    resp = client.post(f"{JOBS_URL}/{uuid4()}/retry")
    assert resp.status_code == 401


def test_internal_run_rejected_without_credentials(client):
    """The Cloud Tasks target must reject unauthenticated calls with 403 —
    it is NOT behind get_current_user, so this is verify_task_request's job."""
    resp = client.post(f"/internal/extraction-jobs/{uuid4()}/run")
    assert resp.status_code == 403


def test_internal_run_rejected_with_bad_shared_secret(client):
    with patch("app.services.cloud_tasks_service.settings") as s:
        s.internal_task_token = "right-token"
        resp = client.post(
            f"/internal/extraction-jobs/{uuid4()}/run",
            headers={"X-Internal-Token": "wrong-token"},
        )
    assert resp.status_code == 403


# ===========================================================================
# Integration: submit / ADR-3 reuse / validation
# ===========================================================================

@pytest.mark.integration
def test_submit_rejects_non_docx_magic(jobs_table, client, headers_a):
    resp = _submit(client, headers_a, content=b"not-a-zip-file")
    assert resp.status_code == 400


@pytest.mark.integration
def test_submit_rejects_empty_file(jobs_table, client, headers_a):
    resp = _submit(client, headers_a, content=b"")
    assert resp.status_code == 400


@pytest.mark.integration
def test_submit_then_resubmit_reuses_active_job(jobs_table, client, headers_a):
    """ADR-3: double-click / second tab converges on the SAME job, no 409."""
    content = b"PK\x03\x04" + uuid4().bytes  # unique doc per test run
    r1 = _submit(client, headers_a, content=content)
    assert r1.status_code == 202, r1.text
    body1 = r1.json()
    assert body1["reused"] is False and body1["status"] == "queued"

    try:
        r2 = _submit(client, headers_a, content=content)
        assert r2.status_code == 202, r2.text
        body2 = r2.json()
        assert body2["reused"] is True
        assert body2["job_id"] == body1["job_id"]
    finally:
        asyncio.run(_delete_job(body1["job_id"]))


# ===========================================================================
# Integration: status / stale / result / cross-tenant
# ===========================================================================

@pytest.mark.integration
def test_status_and_cross_tenant_404(jobs_table, client, user_a, headers_a, headers_b):
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="queued"))
    try:
        resp = client.get(f"{JOBS_URL}/{job_id}", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued" and body["stale"] is False
        assert body["has_result"] is False

        # Cross-tenant: 404, never 403 (existence must not leak)
        resp_b = client.get(f"{JOBS_URL}/{job_id}", headers=headers_b)
        assert resp_b.status_code == 404
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_stale_extracting_is_reported(jobs_table, client, user_a, headers_a):
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="extracting"))
    try:
        asyncio.run(_set_updated_at(job_id, datetime.now(timezone.utc) - timedelta(hours=1)))
        resp = client.get(f"{JOBS_URL}/{job_id}", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["stale"] is True
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_result_409_until_completed_then_200(jobs_table, client, user_a, headers_a):
    queued_id = asyncio.run(_insert_job(user_a["user"]["id"], status="queued"))
    done_id = asyncio.run(_insert_job(user_a["user"]["id"], status="completed",
                                      prompt_version="test-prompt", input_tokens=7))
    try:
        assert client.get(f"{JOBS_URL}/{queued_id}/result", headers=headers_a).status_code == 409
        resp = client.get(f"{JOBS_URL}/{done_id}/result", headers=headers_a)
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == {"questions": [], "total_points": "100"}
        assert body["provenance"]["prompt_version"] == "test-prompt"
        assert body["provenance"]["input_tokens"] == 7
    finally:
        asyncio.run(_delete_job(queued_id))
        asyncio.run(_delete_job(done_id))


# ===========================================================================
# Integration: retry transitions
# ===========================================================================

@pytest.mark.integration
def test_retry_from_failed_requeues(jobs_table, client, user_a, headers_a):
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="failed"))
    try:
        with patch("app.api.v0.rubric_extraction_jobs.enqueue_extraction_task", new=AsyncMock()):
            resp = client.post(f"{JOBS_URL}/{job_id}/retry", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        status = client.get(f"{JOBS_URL}/{job_id}", headers=headers_a).json()
        assert status["status"] == "queued" and status["error_message"] is None
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_retry_from_healthy_extracting_409(jobs_table, client, user_a, headers_a):
    """A live (non-stale) extraction must NOT be re-queued underneath itself."""
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="extracting"))
    try:
        resp = client.post(f"{JOBS_URL}/{job_id}/retry", headers=headers_a)
        assert resp.status_code == 409
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_retry_from_stale_extracting_requeues(jobs_table, client, user_a, headers_a):
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="extracting"))
    try:
        asyncio.run(_set_updated_at(job_id, datetime.now(timezone.utc) - timedelta(hours=1)))
        with patch("app.api.v0.rubric_extraction_jobs.enqueue_extraction_task", new=AsyncMock()):
            resp = client.post(f"{JOBS_URL}/{job_id}/retry", headers=headers_a)
        assert resp.status_code == 200
        status = client.get(f"{JOBS_URL}/{job_id}", headers=headers_a).json()
        assert status["status"] == "queued" and status["started_at"] is None
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_retry_completed_409(jobs_table, client, user_a, headers_a):
    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="completed"))
    try:
        resp = client.post(f"{JOBS_URL}/{job_id}/retry", headers=headers_a)
        assert resp.status_code == 409
    finally:
        asyncio.run(_delete_job(job_id))


# ===========================================================================
# Integration: runner CAS + DB CHECK constraint
# ===========================================================================

@pytest.mark.integration
def test_runner_cas_double_delivery_noop(jobs_table, user_a):
    """queued→extracting CAS: first claim wins, duplicate delivery is a no-op.

    The runner uses the app's global engine (get_db_context), whose pooled
    connections are bound to the TestClient's loop — so we patch in a
    loop-local session maker and run BOTH claims inside one asyncio.run."""
    from unittest.mock import patch as _patch

    from app.services.rubric_extraction_runner import _claim_job

    async def _claim_twice(job_id):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.config import settings

        engine = create_async_engine(
            settings.database_url, poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            with _patch("app.database.AsyncSessionLocal", maker):
                first = await _claim_job(job_id)
                second = await _claim_job(job_id)
            return first, second
        finally:
            await engine.dispose()

    job_id = asyncio.run(_insert_job(user_a["user"]["id"], status="queued"))
    try:
        first, second = asyncio.run(_claim_twice(job_id))
        assert first is True
        assert second is False  # already extracting — duplicate delivery no-op
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_check_constraint_rejects_illegal_write(jobs_table, user_a):
    """status='completed' with result_json NULL must violate
    rubric_extraction_jobs_status_consistency."""
    from sqlalchemy import null
    from sqlalchemy.exc import DBAPIError, IntegrityError

    # sqlalchemy.null(), not Python None: the JSON type renders None as
    # 'null'::jsonb (JSON null), which is NOT SQL NULL and would satisfy the
    # CHECK's IS NOT NULL arm.
    with pytest.raises((IntegrityError, DBAPIError)):
        asyncio.run(_insert_job(user_a["user"]["id"], status="completed", result_json=null()))
