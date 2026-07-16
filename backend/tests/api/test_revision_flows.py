"""
S10 — Revision flow tests: regrade, manual_edit, retry.

Tests 1–19 from S10 spec §9.

Core invariant tests (the load-bearing ones):
  [CORE-1]  No two-leaf violation — proves the §2 deferred-FK ordering works
  [CORE-2]  Exactly one leaf after revision
  [CORE-3]  History immutability — LCY-2
  [CORE-4]  Bidirectional chain links — RGC-2

All tests marked @pytest.mark.integration require a live DATABASE_URL
and migration 010 applied. Tests mocking run_grading do not require a live
OpenAI key — they only test the endpoint + DB state.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.graded_test_draft import (
    CriterionOutcome,
    GradedTestDraft,
    ScopeOutcome,
)


# ---------------------------------------------------------------------------
# Minimal draft + contract JSON helpers
# ---------------------------------------------------------------------------

def _minimal_draft_json(rubric_version: str = "test-rubric-v1") -> dict:
    """GradedTestDraft with one 5-pt criterion, AI awarded 4, teacher override 5."""
    draft = GradedTestDraft(
        rubric_contract_version=rubric_version,
        transcription_contract_version="test-trans-v1",
        model_version="gpt-4o",
        prompt_version="grader-v1",
        scope_outcomes=[
            ScopeOutcome(
                scope_kind="direct",
                question_id="q1",
                points_possible=Decimal("100"),
                points_awarded=Decimal("80"),
                min_confidence=0.85,
                criterion_outcomes=[
                    CriterionOutcome(
                        criterion_id="q1.c0",
                        description="Test criterion",
                        points_possible=Decimal("100"),
                        points_awarded=Decimal("80"),
                        reasoning="AI says 80",
                        confidence=0.85,
                    )
                ],
                graded_by="llm",
            )
        ],
        teacher_overrides={"q1.c0": {"points_awarded": "90", "teacher_comment": "good"}},
        llm_calls_count=1,
        grading_duration_ms=400,
    )
    return draft.model_dump(mode="json")


def _minimal_contract_json() -> dict:
    """Minimal GradedTestContract JSON (used for approved rows)."""
    return {
        "schema_version": "1.0",
        "contract_version": str(uuid4()),
        "rubric_contract_version": "test-rubric-v1",
        "transcription_contract_version": "test-trans-v1",
        "model_version": "gpt-4o",
        "prompt_version": "grader-v1",
        "scope_outcomes": [
            {
                "scope_kind": "direct",
                "question_id": "q1",
                "sub_question_id": None,
                "points_possible": "100",
                "final_points_awarded": "90",
                "terminal_outcomes": [
                    {
                        "terminal_id": "q1.c0",
                        "terminal_kind": "criterion",
                        "description": "Test criterion",
                        "points_possible": "100",
                        "ai_points_awarded": "80",
                        "ai_reasoning": "AI says 80",
                        "ai_evidence_quote": None,
                        "was_overridden": True,
                        "teacher_comment": "good",
                        "final_points_awarded": "90",
                    }
                ],
            }
        ],
        "total_score": "90",
        "total_possible": "100",
        "percentage": "90.00",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# DB helpers — insert / delete rows directly
# ---------------------------------------------------------------------------

async def _insert_approved_row(
    user_id: str,
    rubric_id: str,
    *,
    rubric_contract_version: str = "stale-version-s10",
    regraded_from_id: str | None = None,
    regraded_to_id: str | None = None,
) -> tuple[str, str]:
    """
    Insert an approved GradedTest leaf.
    Returns (graded_test_id, transcription_id).
    """
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    from app.models.student import Student
    from app.models.transcription import Transcription

    async with AsyncSessionLocal() as db:
        student_id = uuid.uuid4()
        student = Student(
            id=student_id,
            user_id=uuid.UUID(user_id),
            full_name="Test Student S10",
        )
        db.add(student)
        await db.flush()

        transcription_id = uuid.uuid4()
        transcription = Transcription(
            id=transcription_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            student_id=student_id,
            student_name="Test Student S10",
            gcs_uri="gs://stub/stub.pdf",
            gcs_bucket="stub",
            gcs_object_path="stub.pdf",
            filename="stub.pdf",
            draft_json={"stub": True},
            contract_json={"stub": True, "contract_version": str(uuid.uuid4())},
            approved_at=datetime.now(timezone.utc),
            status="approved",
        )
        db.add(transcription)
        await db.flush()

        graded_test_id = uuid.uuid4()
        draft_json = _minimal_draft_json(rubric_contract_version)
        contract_json = _minimal_contract_json()
        contract_json["rubric_contract_version"] = rubric_contract_version

        graded_test = GradedTest(
            id=graded_test_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            transcription_id=transcription_id,
            student_id=student_id,
            rubric_contract_version=rubric_contract_version,
            student_name="Test Student S10",
            filename="stub.pdf",
            status="approved",
            draft_json=draft_json,
            contract_json=contract_json,
            approved_at=datetime.now(timezone.utc),
            total_score=Decimal("90"),
            total_possible=Decimal("100"),
            percentage=Decimal("90.00"),
            regraded_from_id=uuid.UUID(regraded_from_id) if regraded_from_id else None,
            regraded_to_id=uuid.UUID(regraded_to_id) if regraded_to_id else None,
        )
        db.add(graded_test)
        await db.commit()
        return str(graded_test_id), str(transcription_id)


async def _insert_failed_row(
    user_id: str,
    rubric_id: str,
    *,
    regraded_to_id: str | None = None,
) -> tuple[str, str]:
    """Insert a failed GradedTest leaf. Returns (graded_test_id, transcription_id)."""
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    from app.models.student import Student
    from app.models.transcription import Transcription

    async with AsyncSessionLocal() as db:
        student_id = uuid.uuid4()
        student = Student(
            id=student_id,
            user_id=uuid.UUID(user_id),
            full_name="Test Student S10 Failed",
        )
        db.add(student)
        await db.flush()

        transcription_id = uuid.uuid4()
        transcription = Transcription(
            id=transcription_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            student_id=student_id,
            student_name="Test Student S10 Failed",
            gcs_uri="gs://stub/stub.pdf",
            gcs_bucket="stub",
            gcs_object_path="stub.pdf",
            filename="stub.pdf",
            draft_json={"stub": True},
            contract_json=None,
            status="transcribed",
        )
        db.add(transcription)
        await db.flush()

        graded_test_id = uuid.uuid4()
        graded_test = GradedTest(
            id=graded_test_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            transcription_id=transcription_id,
            student_id=student_id,
            rubric_contract_version="failed-version-s10",
            student_name="Test Student S10 Failed",
            filename="stub.pdf",
            status="failed",
            error_message="LLM timed out",
            regraded_to_id=uuid.UUID(regraded_to_id) if regraded_to_id else None,
        )
        db.add(graded_test)
        await db.commit()
        return str(graded_test_id), str(transcription_id)


async def _fetch_row(graded_test_id: str) -> dict:
    """Fetch a GradedTest row and return a plain dict of its key fields."""
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    import uuid

    async with AsyncSessionLocal() as db:
        row: GradedTest = await db.get(GradedTest, uuid.UUID(graded_test_id))
        if row is None:
            return {}
        return {
            "id": str(row.id),
            "status": row.status,
            "draft_json": row.draft_json,
            "contract_json": row.contract_json,
            "approved_at": row.approved_at,
            "regraded_from_id": str(row.regraded_from_id) if row.regraded_from_id else None,
            "regraded_to_id": str(row.regraded_to_id) if row.regraded_to_id else None,
            "rubric_contract_version": row.rubric_contract_version,
        }


async def _delete_row_cascade(graded_test_id: str) -> None:
    """Delete a graded_test row (and its orphaned student/transcription siblings)."""
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    from sqlalchemy import delete
    import uuid

    async with AsyncSessionLocal() as db:
        await db.execute(delete(GradedTest).where(GradedTest.id == uuid.UUID(graded_test_id)))
        await db.commit()


# ---------------------------------------------------------------------------
# Helper: get the rubric's current contract_version
# ---------------------------------------------------------------------------

def _get_rubric_contract_version(client: TestClient, rubric_id: str, headers: dict) -> str:
    resp = client.get(f"/api/v0/rubrics/{rubric_id}", headers=headers)
    assert resp.status_code == 200, f"Rubric fetch failed: {resp.text}"
    data = resp.json()
    # contract_version lives inside contract_json
    cv = data.get("contract_version") or (
        data.get("contract_json") or {}
    ).get("contract_version", "")
    return str(cv)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def stale_approved_leaf(client, user_a, rubric_a, headers_a):
    """
    Approved leaf with rubric_contract_version='stale-version-s10'.
    The rubric's real contract_version will differ → rubric_contract_stale = True.
    """
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    gid, _ = asyncio.run(
        _insert_approved_row(uid, rid, rubric_contract_version="stale-version-s10")
    )
    yield gid, headers_a
    asyncio.run(_delete_row_cascade(gid))


@pytest.fixture(scope="function")
def nonstale_approved_leaf(client, user_a, rubric_a, headers_a):
    """
    Approved leaf whose rubric_contract_version matches the rubric's current version
    → rubric_contract_stale = False.
    """
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    # Fetch the rubric's real contract_version so the row is non-stale
    resp = client.get(f"/api/v0/rubrics/{rid}", headers=headers_a)
    assert resp.status_code == 200
    rubric_data = resp.json()
    current_cv = rubric_data.get("contract_version", "")
    if not current_cv:
        # Fallback: use contract_json if contract_version is a top-level field
        current_cv = (rubric_data.get("contract_json") or {}).get("contract_version", "non-stale-version")

    gid, _ = asyncio.run(
        _insert_approved_row(uid, rid, rubric_contract_version=current_cv)
    )
    yield gid, headers_a
    asyncio.run(_delete_row_cascade(gid))


@pytest.fixture(scope="function")
def failed_leaf(client, user_a, rubric_a, headers_a):
    """Failed GradedTest leaf."""
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    gid, _ = asyncio.run(_insert_failed_row(uid, rid))
    yield gid, headers_a
    asyncio.run(_delete_row_cascade(gid))


# ---------------------------------------------------------------------------
# CORE-1 — No two-leaf violation (the §2 deferred-FK ordering proof)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_no_two_leaf_violation_on_regrade(client, stale_approved_leaf):
    """
    The chain-extension transaction must commit without UniqueViolationError
    on idx_graded_tests_one_leaf_per_chain.

    If migration 010 is missing OR the ordering is wrong, this test fails with
    a 500 (DB integrity error).
    """
    gid, headers = stale_approved_leaf

    with patch("app.api.v0.grading.run_grading", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)

    assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_no_two_leaf_violation_on_manual_edit(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_no_two_leaf_violation_on_retry(client, failed_leaf):
    gid, headers = failed_leaf
    with patch("app.api.v0.grading.run_grading", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/retry", headers=headers)
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# CORE-2 — Exactly one leaf after revision (RGC-1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_exactly_one_leaf_after_regrade(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf

    with patch("app.api.v0.grading.run_grading", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    r1 = asyncio.run(_fetch_row(gid))
    r2 = asyncio.run(_fetch_row(r2_id))

    # R1 is no longer the leaf
    assert r1["regraded_to_id"] == r2_id, "R1.regraded_to_id should point to R2"
    # R2 is the sole leaf
    assert r2["regraded_to_id"] is None, "R2.regraded_to_id should be NULL (new leaf)"

    # Clean up R2 (R1 cleaned by fixture)
    asyncio.run(_delete_row_cascade(r2_id))


@pytest.mark.integration
def test_exactly_one_leaf_after_manual_edit(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf

    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    r1 = asyncio.run(_fetch_row(gid))
    r2 = asyncio.run(_fetch_row(r2_id))

    assert r1["regraded_to_id"] == r2_id
    assert r2["regraded_to_id"] is None

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# CORE-3 — History immutability — LCY-2
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_history_immutable_after_manual_edit(client, stale_approved_leaf):
    """
    After manual_edit: R1's draft_json, contract_json, approved_at, status
    must be byte-unchanged. Only regraded_to_id may differ.
    """
    gid, headers = stale_approved_leaf

    r1_before = asyncio.run(_fetch_row(gid))

    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    r1_after = asyncio.run(_fetch_row(gid))

    assert r1_after["draft_json"] == r1_before["draft_json"], "draft_json mutated"
    assert r1_after["contract_json"] == r1_before["contract_json"], "contract_json mutated"
    assert r1_after["approved_at"] == r1_before["approved_at"], "approved_at mutated"
    assert r1_after["status"] == r1_before["status"], "status mutated"
    # Only regraded_to_id changed
    assert r1_after["regraded_to_id"] == r2_id

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# CORE-4 — Bidirectional chain links — RGC-2
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bidirectional_links_after_regrade(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf

    with patch("app.api.v0.grading.run_grading", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    r1 = asyncio.run(_fetch_row(gid))
    r2 = asyncio.run(_fetch_row(r2_id))

    assert r1["regraded_to_id"] == r2_id
    assert r2["regraded_from_id"] == gid

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# Regrade precondition tests
# ---------------------------------------------------------------------------

def test_regrade_requires_auth(client):
    resp = client.post(f"/api/v0/grading/graded_test/{uuid4()}/regrade")
    assert resp.status_code == 401


def test_regrade_cross_user_returns_404(client, headers_b):
    resp = client.post(
        f"/api/v0/grading/graded_test/{uuid4()}/regrade",
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_regrade_409_on_nonstale(client, nonstale_approved_leaf):
    gid, headers = nonstale_approved_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 409
    assert "stale" in resp.json()["detail"].lower() or "manual_edit" in resp.json()["detail"]


@pytest.mark.integration
def test_regrade_409_on_non_approved(client, failed_leaf):
    """Source status must be 'approved', not 'failed'."""
    gid, headers = failed_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 409
    assert "approved" in resp.json()["detail"]


@pytest.mark.integration
def test_regrade_409_on_non_leaf(client, user_a, rubric_a, headers_a):
    """A row with regraded_to_id set cannot be regraded."""
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    # Insert a row that already has a forward pointer (non-leaf)
    r2_id = str(uuid4())
    r1_id, _ = asyncio.run(
        _insert_approved_row(uid, rid, rubric_contract_version="stale-version", regraded_to_id=r2_id)
    )
    try:
        resp = client.post(f"/api/v0/grading/graded_test/{r1_id}/regrade", headers=headers_a)
        assert resp.status_code == 409
        assert "non-leaf" in resp.json()["detail"].lower() or "superseded" in resp.json()["detail"].lower()
    finally:
        asyncio.run(_delete_row_cascade(r1_id))


@pytest.mark.integration
def test_regrade_returns_pending_and_fires_agent(client, stale_approved_leaf):
    """Regrade response has status='pending' and run_grading is invoked with R2.id."""
    gid, headers = stale_approved_leaf

    fired_with: list[str] = []

    async def capture_run_grading(graded_test_id):
        fired_with.append(str(graded_test_id))

    with patch("app.api.v0.grading.run_grading", side_effect=capture_run_grading):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    r2_id = body["graded_test_id"]

    assert len(fired_with) == 1
    assert fired_with[0] == r2_id

    asyncio.run(_delete_row_cascade(r2_id))


@pytest.mark.integration
def test_regrade_r2_pins_new_rubric_contract_version(client, stale_approved_leaf, rubric_a, headers_a):
    """R2 must pin the rubric's CURRENT contract_version, not the stale one."""
    gid, headers = stale_approved_leaf

    with patch("app.api.v0.grading.run_grading", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    r2 = asyncio.run(_fetch_row(r2_id))
    r1 = asyncio.run(_fetch_row(gid))

    assert r2["rubric_contract_version"] != r1["rubric_contract_version"], (
        "R2 should have a DIFFERENT rubric_contract_version than the stale R1"
    )
    assert r2["rubric_contract_version"] != "stale-version-s10"

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# Manual-edit precondition + carry-forward tests
# ---------------------------------------------------------------------------

def test_manual_edit_requires_auth(client):
    resp = client.post(f"/api/v0/grading/graded_test/{uuid4()}/manual_edit")
    assert resp.status_code == 401


def test_manual_edit_cross_user_returns_404(client, headers_b):
    resp = client.post(
        f"/api/v0/grading/graded_test/{uuid4()}/manual_edit",
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_manual_edit_409_on_non_approved(client, failed_leaf):
    gid, headers = failed_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 409
    assert "approved" in resp.json()["detail"]


@pytest.mark.integration
def test_manual_edit_409_on_non_leaf(client, user_a, rubric_a, headers_a):
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    r2_id = str(uuid4())
    r1_id, _ = asyncio.run(
        _insert_approved_row(uid, rid, rubric_contract_version="stale-version", regraded_to_id=r2_id)
    )
    try:
        resp = client.post(f"/api/v0/grading/graded_test/{r1_id}/manual_edit", headers=headers_a)
        assert resp.status_code == 409
    finally:
        asyncio.run(_delete_row_cascade(r1_id))


@pytest.mark.integration
def test_manual_edit_allowed_on_nonstale(client, nonstale_approved_leaf):
    """manual_edit is available on non-stale rows (unlike regrade)."""
    gid, headers = nonstale_approved_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]
    asyncio.run(_delete_row_cascade(r2_id))


@pytest.mark.integration
def test_manual_edit_carries_draft_json_verbatim(client, stale_approved_leaf):
    """
    R2.draft_json == R1.draft_json (AI outcomes + teacher_overrides verbatim).
    R2.status == 'draft'.
    R2.rubric_contract_version == R1.rubric_contract_version (unchanged).
    No agent invoked.
    """
    gid, headers = stale_approved_leaf

    fired: list = []

    async def should_not_fire(graded_test_id):
        fired.append(graded_test_id)

    with patch("app.api.v0.grading.run_grading", side_effect=should_not_fire):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "draft"
    r2_id = body["graded_test_id"]

    # Agent must NOT have been called
    assert fired == [], "run_grading should not be called for manual_edit"

    r1 = asyncio.run(_fetch_row(gid))
    r2 = asyncio.run(_fetch_row(r2_id))

    assert r2["draft_json"] == r1["draft_json"], "draft_json not carried verbatim"
    assert r2["rubric_contract_version"] == r1["rubric_contract_version"], (
        "rubric_contract_version should be unchanged for manual_edit"
    )
    assert r2["status"] == "draft"

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# Retry precondition tests
# ---------------------------------------------------------------------------

def test_retry_requires_auth(client):
    resp = client.post(f"/api/v0/grading/graded_test/{uuid4()}/retry")
    assert resp.status_code == 401


def test_retry_cross_user_returns_404(client, headers_b):
    resp = client.post(
        f"/api/v0/grading/graded_test/{uuid4()}/retry",
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_retry_409_on_non_failed(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/retry", headers=headers)
    assert resp.status_code == 409
    assert "failed" in resp.json()["detail"]


@pytest.mark.integration
def test_retry_409_on_non_leaf(client, user_a, rubric_a, headers_a):
    uid = user_a["user"]["id"]
    rid = rubric_a["rubric_id"]
    # Insert a failed row that already has a successor
    r2_id = str(uuid4())
    r1_id, _ = asyncio.run(_insert_failed_row(uid, rid, regraded_to_id=r2_id))
    try:
        resp = client.post(f"/api/v0/grading/graded_test/{r1_id}/retry", headers=headers_a)
        assert resp.status_code == 409
    finally:
        asyncio.run(_delete_row_cascade(r1_id))


@pytest.mark.integration
def test_retry_fires_agent(client, failed_leaf):
    gid, headers = failed_leaf

    fired_with: list[str] = []

    async def capture(graded_test_id):
        fired_with.append(str(graded_test_id))

    with patch("app.api.v0.grading.run_grading", side_effect=capture):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/retry", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    r2_id = body["graded_test_id"]

    assert fired_with == [r2_id], "run_grading should be called with the new row's id"

    asyncio.run(_delete_row_cascade(r2_id))


# ---------------------------------------------------------------------------
# rubric_contract_stale in list and detail responses
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rubric_contract_stale_true_in_list(client, stale_approved_leaf, headers_a):
    gid, headers = stale_approved_leaf
    resp = client.get("/api/v0/grading/graded_tests", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    match = next((i for i in items if i["id"] == gid), None)
    assert match is not None, "Row not found in list"
    assert match["rubric_contract_stale"] is True


@pytest.mark.integration
def test_rubric_contract_stale_false_in_list(client, nonstale_approved_leaf, headers_a):
    gid, headers = nonstale_approved_leaf
    resp = client.get("/api/v0/grading/graded_tests", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    match = next((i for i in items if i["id"] == gid), None)
    assert match is not None, "Row not found in list"
    assert match["rubric_contract_stale"] is False


@pytest.mark.integration
def test_rubric_contract_stale_in_approved_detail(client, stale_approved_leaf):
    gid, headers = stale_approved_leaf
    resp = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert "rubric_contract_stale" in body
    assert body["rubric_contract_stale"] is True


@pytest.mark.integration
def test_regraded_from_id_in_detail_after_manual_edit(client, stale_approved_leaf):
    """The successor row's detail response includes regraded_from_id."""
    gid, headers = stale_approved_leaf

    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200
    r2_id = resp.json()["graded_test_id"]

    detail = client.get(f"/api/v0/grading/graded_test/{r2_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("regraded_from_id") == gid

    asyncio.run(_delete_row_cascade(r2_id))
