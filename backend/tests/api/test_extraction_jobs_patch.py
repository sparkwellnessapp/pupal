"""
PR-5 S1-2.2 — PATCH /api/v0/rubrics/extraction-jobs/{job_id} metadata-patch tests.

Mirrors tests/api/test_extraction_jobs.py exactly (fixtures, auth setup, the
fresh-NullPool-session helpers, and the @pytest.mark.integration gate that skips
cleanly when migration 012 is not applied).

The endpoint merges caller-supplied metadata (name / programming_language) into
request_params via a DB-level JSONB `||` concat — NOT a Python read-modify-write.
These tests prove: the merge is additive (existing keys survive), only sent keys
are written (omitted vs explicit-null), cross-tenant is 404, unauth is 401, and a
'failed' job is 409. No GCS / Cloud Tasks / OpenAI — no rows touched by mocks.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from app.models.rubric_extraction_job import RubricExtractionJob

JOBS_URL = "/api/v0/rubrics/extraction-jobs"


# ---------------------------------------------------------------------------
# Direct-DB helpers (copied from test_extraction_jobs.py — same rationale:
# asyncio.run() spins a fresh loop per call, so each uses a fresh NullPool
# engine to stay loop-safe against the app's global pool).
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _fresh_session():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings

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


async def _insert_job(user_id, status="queued", request_params=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        user_id=user_id,
        status=status,
        source_gcs_uri="gs://test-bucket/rubric-sources/test.docx",
        source_filename="test.docx",
        source_sha256=uuid4().hex + uuid4().hex,  # unique 64-char pseudo-sha
        request_params=request_params if request_params is not None
        else {"subject": "computer_science", "locale": "he-IL"},
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


async def _get_request_params(job_id):
    """Read request_params straight from the row (typed JSONB column ⇒ a dict),
    so a test can assert on DB truth independent of the endpoint's echo."""
    async with _fresh_session() as db:
        row = await db.execute(
            select(RubricExtractionJob.request_params)
            .where(RubricExtractionJob.id == job_id)
        )
        return row.scalar()


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


# ===========================================================================
# Always-run: auth boundary
# ===========================================================================

def test_patch_unauthenticated_401(client):
    resp = client.patch(f"{JOBS_URL}/{uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


# ===========================================================================
# Integration: happy path + merge semantics
# ===========================================================================

@pytest.mark.integration
def test_patch_merges_name_and_language_preserving_existing(
    jobs_table, client, user_a, headers_a
):
    """(a) name+language merge into request_params; pre-existing keys survive."""
    job_id = asyncio.run(_insert_job(
        user_a["user"]["id"], status="queued",
        request_params={"subject": "computer_science", "locale": "he-IL",
                        "description": "orig-desc"},
    ))
    try:
        resp = client.patch(
            f"{JOBS_URL}/{job_id}",
            headers=headers_a,
            json={"name": "מחוון שלי", "programming_language": "python"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["job_id"] == str(job_id)
        assert body["status"] == "queued"
        rp = body["request_params"]
        # merged keys
        assert rp["name"] == "מחוון שלי"
        assert rp["programming_language"] == "python"
        # pre-existing keys survive the || concat (not a replace)
        assert rp["subject"] == "computer_science"
        assert rp["locale"] == "he-IL"
        assert rp["description"] == "orig-desc"
        # DB truth matches the echo
        assert asyncio.run(_get_request_params(job_id)) == rp
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_patch_partial_only_name_leaves_other_keys_intact(
    jobs_table, client, user_a, headers_a
):
    """(b) A partial patch (only `name`) proves the || MERGE, not a replace:
    every unrelated key survives and `programming_language` is not injected."""
    job_id = asyncio.run(_insert_job(
        user_a["user"]["id"], status="extracting",
        request_params={"name": "old-name", "subject": "cs", "locale": "he-IL"},
    ))
    try:
        resp = client.patch(
            f"{JOBS_URL}/{job_id}", headers=headers_a, json={"name": "new-name"},
        )
        assert resp.status_code == 200, resp.text
        rp = resp.json()["request_params"]
        assert rp["name"] == "new-name"          # overwritten
        assert rp["subject"] == "cs"             # untouched
        assert rp["locale"] == "he-IL"           # untouched
        assert "programming_language" not in rp  # NOT sent ⇒ NOT added
        assert asyncio.run(_get_request_params(job_id)) == rp
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_patch_explicit_null_vs_omitted(jobs_table, client, user_a, headers_a):
    """(c) explicit null OVERWRITES (JSON null); an omitted field is UNTOUCHED;
    an empty body is an idempotent no-op."""
    job_id = asyncio.run(_insert_job(
        user_a["user"]["id"], status="completed",
        request_params={"name": "keep-me", "subject": "cs"},
    ))
    try:
        # explicit null on programming_language + name OMITTED
        resp = client.patch(
            f"{JOBS_URL}/{job_id}", headers=headers_a,
            json={"programming_language": None},
        )
        assert resp.status_code == 200, resp.text
        rp = resp.json()["request_params"]
        assert rp["programming_language"] is None  # explicit null was written
        assert rp["name"] == "keep-me"             # omitted ⇒ untouched
        assert rp["subject"] == "cs"

        # empty body ⇒ no-op ⇒ state unchanged
        resp2 = client.patch(f"{JOBS_URL}/{job_id}", headers=headers_a, json={})
        assert resp2.status_code == 200, resp2.text
        rp2 = resp2.json()["request_params"]
        assert rp2["name"] == "keep-me"
        assert rp2["programming_language"] is None
        assert asyncio.run(_get_request_params(job_id)) == rp2
    finally:
        asyncio.run(_delete_job(job_id))


# ===========================================================================
# Integration: auth / ownership / status guards
# ===========================================================================

@pytest.mark.integration
def test_patch_cross_tenant_404(jobs_table, client, user_a, headers_a, headers_b):
    """(d) A job owned by A is invisible to B — 404, never 403 (no existence leak),
    and the row is left completely untouched."""
    job_id = asyncio.run(_insert_job(
        user_a["user"]["id"], status="queued",
        request_params={"subject": "cs"},
    ))
    try:
        resp = client.patch(
            f"{JOBS_URL}/{job_id}", headers=headers_b, json={"name": "hijack"},
        )
        assert resp.status_code == 404
        # untouched: the cross-tenant write must not have merged anything
        assert asyncio.run(_get_request_params(job_id)) == {"subject": "cs"}
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_patch_failed_job_409(jobs_table, client, user_a, headers_a):
    """(f) A 'failed' job has nothing to name — 409, and stays untouched."""
    job_id = asyncio.run(_insert_job(
        user_a["user"]["id"], status="failed",
        request_params={"subject": "cs"},
    ))
    try:
        resp = client.patch(
            f"{JOBS_URL}/{job_id}", headers=headers_a, json={"name": "too-late"},
        )
        assert resp.status_code == 409
        assert asyncio.run(_get_request_params(job_id)) == {"subject": "cs"}
    finally:
        asyncio.run(_delete_job(job_id))


@pytest.mark.integration
def test_patch_unknown_job_404(jobs_table, client, headers_a):
    """(g) A well-formed but nonexistent job_id — 404."""
    resp = client.patch(
        f"{JOBS_URL}/{uuid4()}", headers=headers_a, json={"name": "ghost"},
    )
    assert resp.status_code == 404
