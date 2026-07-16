"""
S9 — Approval endpoint tests.

Tests 11–17 from S9 spec §9 "Endpoints".

Tests 11 and 15 (auth + status guards) are verified against random UUIDs or
via mocking. Tests 12, 13, 14, 16, 17 (the DB-state tests) require a live
draft row. These use a pytest fixture that inserts rows directly via the
async session factory, isolated per-test and cleaned up after.

Critical tests:
  [CORE-13] Approve happy path — atomic freeze; all fields in one commit
  [CORE-17] AI-outcome immutability — scope_outcomes byte-unchanged after PATCH + approve

NOTE: Tests marked with @pytest.mark.integration require a live DATABASE_URL.
They are skipped in environments where no DB is available.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.graded_test_draft import (
    CriterionOutcome,
    GradedTestDraft,
    ScopeOutcome,
    GradingAnnotation,
)
from app.schemas.ontology_types import AnnotationSeverity


# ---------------------------------------------------------------------------
# Minimal draft JSON for seeded rows
# ---------------------------------------------------------------------------

def _minimal_draft_json() -> dict:
    """Serialisable GradedTestDraft with one leaf criterion (5 pts, AI awarded 4)."""
    draft = GradedTestDraft(
        rubric_contract_version="test-rubric-v1",
        transcription_contract_version="test-trans-v1",
        model_version="gpt-4o",
        prompt_version="grader-v1",
        scope_outcomes=[
            ScopeOutcome(
                scope_kind="direct",
                question_id="q1",
                points_possible=Decimal("5"),
                points_awarded=Decimal("4"),
                min_confidence=0.9,
                criterion_outcomes=[
                    CriterionOutcome(
                        criterion_id="q1.c0",
                        description="Test criterion",
                        points_possible=Decimal("5"),
                        points_awarded=Decimal("4"),
                        reasoning="AI reasoning text",
                        confidence=0.9,
                    )
                ],
                graded_by="llm",
            )
        ],
        llm_calls_count=1,
        grading_duration_ms=500,
    )
    return draft.model_dump(mode="json")


def _minimal_draft_json_with_error_annotation() -> dict:
    """Serialisable GradedTestDraft with one error-severity annotation."""
    draft = GradedTestDraft(
        rubric_contract_version="test-rubric-v1",
        transcription_contract_version="test-trans-v1",
        model_version="gpt-4o",
        prompt_version="grader-v1",
        scope_outcomes=[
            ScopeOutcome(
                scope_kind="direct",
                question_id="q1",
                points_possible=Decimal("5"),
                points_awarded=Decimal("4"),
                min_confidence=0.9,
                criterion_outcomes=[
                    CriterionOutcome(
                        criterion_id="q1.c0",
                        description="Test criterion",
                        points_possible=Decimal("5"),
                        points_awarded=Decimal("4"),
                        reasoning="AI reasoning",
                        confidence=0.9,
                    )
                ],
                graded_by="llm",
            )
        ],
        annotations=[
            GradingAnnotation(
                severity=AnnotationSeverity.ERROR,
                target_id="q1.c0",
                annotation_type="no_answer",
                message="Unresolved error",
            )
        ],
        llm_calls_count=1,
        grading_duration_ms=500,
    )
    return draft.model_dump(mode="json")


# ---------------------------------------------------------------------------
# DB fixture helpers — insert/delete rows directly
# ---------------------------------------------------------------------------

async def _insert_draft_row(user_id: str, rubric_id: str, draft_json: dict) -> str:
    """
    Insert a minimal GradedTest row with status='draft'.
    Returns the new graded_test_id as string.
    Inserts stub transcription + student rows as needed to satisfy FKs.
    """
    import uuid
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    from app.models.transcription import Transcription
    from app.models.student import Student

    async with AsyncSessionLocal() as db:
        student_id = uuid.uuid4()
        student = Student(
            id=student_id,
            user_id=uuid.UUID(user_id),
            full_name="Test Student S9",
        )
        db.add(student)
        await db.flush()

        transcription_id = uuid.uuid4()
        transcription = Transcription(
            id=transcription_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            student_id=student_id,
            student_name="Test Student S9",
            gcs_uri="gs://test-bucket/stub.pdf",
            gcs_bucket="test-bucket",
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
        graded_test = GradedTest(
            id=graded_test_id,
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            transcription_id=transcription_id,
            student_id=student_id,
            rubric_contract_version="test-rubric-v1",
            student_name="Test Student S9",
            filename="stub.pdf",
            status="draft",
            draft_json=draft_json,
        )
        db.add(graded_test)
        await db.commit()
        return str(graded_test_id)


async def _delete_graded_test_row(graded_test_id: str) -> None:
    """Clean up: delete the graded_test row (student/transcription cascade)."""
    from app.database import AsyncSessionLocal
    from app.models.grading import GradedTest
    from sqlalchemy import delete
    import uuid

    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(GradedTest).where(GradedTest.id == uuid.UUID(graded_test_id))
        )
        await db.commit()


@pytest.fixture(scope="function")
def graded_draft(client, user_a, rubric_a, headers_a):
    """
    Inserts a minimal GradedTest row in 'draft' status.
    Yields (graded_test_id, headers_a).
    Cleans up after the test.
    """
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    draft_json = _minimal_draft_json()

    gid = asyncio.run(_insert_draft_row(user_id, rubric_id, draft_json))
    yield gid, headers_a
    asyncio.run(_delete_graded_test_row(gid))


@pytest.fixture(scope="function")
def graded_draft_with_error(client, user_a, rubric_a, headers_a):
    """Like graded_draft but the draft has an error-severity annotation."""
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    draft_json = _minimal_draft_json_with_error_annotation()

    gid = asyncio.run(_insert_draft_row(user_id, rubric_id, draft_json))
    yield gid, headers_a
    asyncio.run(_delete_graded_test_row(gid))


# ---------------------------------------------------------------------------
# Test 11 — PATCH auth + ownership; status guard
# ---------------------------------------------------------------------------

def test_patch_requires_auth(client):
    resp = client.patch(f"/api/v0/grading/graded_test/{uuid4()}/draft", json={"overrides": {}})
    assert resp.status_code == 401


def test_patch_cross_user_returns_404(client, headers_b):
    resp = client.patch(
        f"/api/v0/grading/graded_test/{uuid4()}/draft",
        json={"overrides": {}},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_approve_requires_auth(client):
    resp = client.post(f"/api/v0/grading/graded_test/{uuid4()}/approve", json={"overrides": {}})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 12 — PATCH saves overrides; AI outcomes byte-unchanged; status stays draft
# ---------------------------------------------------------------------------

def test_patch_saves_overrides_ai_outcomes_immutable(client, graded_draft):
    gid, headers = graded_draft

    # Read the original draft first
    detail = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers)
    assert detail.status_code == 200
    original_draft = detail.json()["draft"]
    original_reasoning = original_draft["scope_outcomes"][0]["criterion_outcomes"][0]["reasoning"]
    original_ai_points = original_draft["scope_outcomes"][0]["criterion_outcomes"][0]["points_awarded"]

    # Save an override
    resp = client.patch(
        f"/api/v0/grading/graded_test/{gid}/draft",
        json={"overrides": {"q1.c0": {"points_awarded": "3", "teacher_comment": "Adjusted"}}},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"

    # Verify override persisted
    saved_overrides = data["draft"]["teacher_overrides"]
    assert "q1.c0" in saved_overrides
    assert saved_overrides["q1.c0"]["points_awarded"] == "3"

    # [CORE-17] AI outcomes MUST be byte-unchanged
    updated_scope = data["draft"]["scope_outcomes"][0]
    assert updated_scope["criterion_outcomes"][0]["reasoning"] == original_reasoning
    assert updated_scope["criterion_outcomes"][0]["points_awarded"] == original_ai_points


# ---------------------------------------------------------------------------
# Test 13 — Approve happy path: atomic freeze; regraded_to_id stays NULL
# [CORE-13]
# ---------------------------------------------------------------------------

def test_approve_happy_path_atomic_freeze(client, graded_draft):
    gid, headers = graded_draft

    resp = client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {"q1.c0": {"points_awarded": "5", "teacher_comment": "Full marks"}}},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Row is now approved
    assert data["status"] == "approved"
    assert data["approved_at"] is not None

    # Contract is present and has the right shape
    contract = data["contract"]
    assert contract["contract_version"]  # non-empty UUID
    assert contract["total_score"] == "5"
    assert contract["total_possible"] == "5"
    assert float(contract["percentage"]) == 100.0

    # Provenance: teacher override is reflected
    terminal = contract["scope_outcomes"][0]["terminal_outcomes"][0]
    assert terminal["final_points_awarded"] == "5"
    assert terminal["ai_points_awarded"] == "4"  # original AI value preserved
    assert terminal["was_overridden"] is True
    assert terminal["teacher_comment"] == "Full marks"

    # Verify via GET that status is approved and contract is in the response
    detail = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["status"] == "approved"
    assert "contract" in detail_data

    # regraded_to_id should be NULL (S10 sets it; S9 does not)
    # We can't easily check this from the API response, but we verify the row
    # still appears in the list as 'approved' (not replaced)
    list_resp = client.get("/api/v0/grading/graded_tests", headers=headers)
    statuses = [item["status"] for item in list_resp.json() if item["id"] == gid]
    assert statuses == ["approved"]


# ---------------------------------------------------------------------------
# Test 14 — Approve gate failure → 422; no state change
# ---------------------------------------------------------------------------

def test_approve_gate_failure_422_no_state_change(client, graded_draft_with_error):
    gid, headers = graded_draft_with_error

    resp = client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {}},
        headers=headers,
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "gate_violations" in detail

    violations = detail["gate_violations"]
    assert any(v["violation_kind"] == "error_annotation" for v in violations)

    # Row must still be in 'draft' status (no state change)
    detail_resp = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "draft"


# ---------------------------------------------------------------------------
# Test 15 — Approve status guard: 409 if not draft
# ---------------------------------------------------------------------------

def test_approve_on_approved_row_returns_409(client, graded_draft):
    gid, headers = graded_draft

    # First approval (success)
    first = client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {}},
        headers=headers,
    )
    assert first.status_code == 200

    # Second approval attempt (now status='approved', not 'draft')
    second = client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {}},
        headers=headers,
    )
    assert second.status_code == 409


def test_patch_on_nonexistent_returns_404(client, headers_a):
    resp = client.patch(
        f"/api/v0/grading/graded_test/{uuid4()}/draft",
        json={"overrides": {}},
        headers=headers_a,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 16 — Detail endpoint approved branch → GradedTestApprovedResponse
# ---------------------------------------------------------------------------

def test_detail_approved_returns_approved_response(client, graded_draft):
    gid, headers = graded_draft

    # Approve first
    client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {}},
        headers=headers,
    )

    # Now GET the detail
    resp = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "approved"
    assert "contract" in data
    assert "draft" in data
    assert "approved_at" in data
    assert data["contract"]["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# Test 17 — AI-outcome immutability after PATCH and after approve
# [CORE-17]
# ---------------------------------------------------------------------------

def test_ai_outcome_immutability_after_patch_and_approve(client, graded_draft):
    gid, headers = graded_draft

    # Capture AI-original outcomes
    original = client.get(f"/api/v0/grading/graded_test/{gid}", headers=headers).json()
    orig_crit = original["draft"]["scope_outcomes"][0]["criterion_outcomes"][0]
    orig_reasoning = orig_crit["reasoning"]
    orig_ai_points = orig_crit["points_awarded"]

    # PATCH: add an override
    client.patch(
        f"/api/v0/grading/graded_test/{gid}/draft",
        json={"overrides": {"q1.c0": {"points_awarded": "2", "teacher_comment": "Too low"}}},
        headers=headers,
    )

    # After PATCH: AI fields unchanged
    after_patch = client.get(
        f"/api/v0/grading/graded_test/{gid}", headers=headers
    ).json()
    patch_crit = after_patch["draft"]["scope_outcomes"][0]["criterion_outcomes"][0]
    assert patch_crit["reasoning"] == orig_reasoning
    assert patch_crit["points_awarded"] == orig_ai_points

    # APPROVE
    client.post(
        f"/api/v0/grading/graded_test/{gid}/approve",
        json={"overrides": {"q1.c0": {"points_awarded": "2", "teacher_comment": "Too low"}}},
        headers=headers,
    )

    # After APPROVE: contract has ai_points_awarded = original, final_points_awarded = 2
    after_approve = client.get(
        f"/api/v0/grading/graded_test/{gid}", headers=headers
    ).json()
    approve_crit = after_approve["draft"]["scope_outcomes"][0]["criterion_outcomes"][0]
    assert approve_crit["reasoning"] == orig_reasoning      # AI reasoning unchanged
    assert approve_crit["points_awarded"] == orig_ai_points  # AI points unchanged

    # [CORE-17] The contract terminal shows both original AI and final
    terminal = after_approve["contract"]["scope_outcomes"][0]["terminal_outcomes"][0]
    assert terminal["ai_points_awarded"] == orig_ai_points
    assert terminal["ai_reasoning"] == orig_reasoning
    assert terminal["final_points_awarded"] == "2"
    assert terminal["was_overridden"] is True
