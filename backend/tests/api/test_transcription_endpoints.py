"""
S4 — Transcription endpoint tests (tests 8–17).

Uses FastAPI TestClient (synchronous) against a real database.
VLM and GCS are mocked; all DB operations run against the real test DB.

Test 15 (cross-tenant student) and Test 17 (draft immutability) are the
load-bearing invariant guards.
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.handwriting_transcription_service import (
    TranscribedAnswer,
    TranscriptionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_PDF = b"%PDF-1.0 fake content"


def _canned_result(student_name="אבי כהן"):
    """A minimal TranscriptionResult that build_transcription_draft can consume."""
    return TranscriptionResult(
        student_name=student_name,
        filename="test.pdf",
        answers=[
            TranscribedAnswer(
                question_number=1,
                sub_question_id=None,
                answer_text="public int foo() { return 42; }",
                confidence=0.9,
                page_numbers=[1],
                needed_grounding_retry=False,
            )
        ],
    )


def _patch_transcription_infra(transcription_result=None):
    """
    Mock the external dependencies of POST /transcribe.

    PATCH TARGETS LIVE IN app.services.transcribe_one, NOT app.api.v0.transcription.
    The endpoint delegates the heavy work to transcribe_one() (shared with the batch
    path), and transcribe_one binds HandwritingTranscriptionService / get_vlm_provider
    / get_gcs_service / pdf_to_images into ITS OWN module namespace via
    `from ... import`. Patching those names in the endpoint module — or in the module
    that DEFINES them (app.services.document_parser) — leaves transcribe_one's
    bindings pointing at the real functions, so the real VLM and GCS run against
    b"%PDF-1.0 fake content" and the endpoint returns 502. Patch where a name is
    USED, not where it is defined.

    The engine is pinned to "legacy" because .env sets TRANSCRIPTION_ENGINE=two_phase
    (the code default is "legacy"). Without the pin, transcribe_one takes the
    two-phase branch and runs the real cross-reader VLM pipeline. These are endpoint
    tests — auth, ownership, status codes, persistence — and must not depend on which
    transcription engine happens to be configured.
    """
    if transcription_result is None:
        transcription_result = _canned_result()

    from contextlib import ExitStack
    stack = ExitStack()

    # Hermetic w.r.t. the engine flag (see docstring).
    stack.enter_context(
        patch("app.services.transcribe_one.settings.transcription_engine", "legacy")
    )

    mock_svc_cls = stack.enter_context(
        patch("app.services.transcribe_one.HandwritingTranscriptionService")
    )
    mock_svc_cls.return_value.transcribe_pdf.return_value = transcription_result

    stack.enter_context(
        patch("app.services.transcribe_one.get_vlm_provider", return_value=MagicMock())
    )

    mock_pages = stack.enter_context(
        patch("app.services.transcribe_one.pdf_to_images")
    )
    mock_pages.return_value = [MagicMock()]  # 1 fake PIL Image

    mock_gcs = stack.enter_context(
        patch("app.services.transcribe_one.get_gcs_service")
    )
    mock_gcs.return_value.upload_bytes.return_value = "transcriptions/uid/obj.pdf"

    # The endpoint module still resolves get_gcs_service itself for the /pages
    # download path; keep it stubbed so no test reaches real GCS.
    stack.enter_context(patch("app.api.v0.transcription.get_gcs_service"))

    return stack


# ---------------------------------------------------------------------------
# Test 8 — 401 without token
# ---------------------------------------------------------------------------

def test_8_transcribe_requires_auth(client):
    resp = client.post(
        "/api/v0/transcriptions/transcribe",
        data={"rubric_id": "00000000-0000-0000-0000-000000000001"},
        files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 401


def test_8_grade_requires_auth(client):
    resp = client.post(
        "/api/v0/transcriptions/grade",
        json={
            "transcription_id": "00000000-0000-0000-0000-000000000001",
            "answers": [],
            "student_id": "00000000-0000-0000-0000-000000000002",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 9 — 404 for another user's rubric
# ---------------------------------------------------------------------------

def test_9_transcribe_wrong_rubric_owner(client, headers_b, rubric_a):
    """User B cannot use User A's rubric."""
    rubric_id = rubric_a["rubric_id"]
    with _patch_transcription_infra():
        resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_id},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_b,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 10 — 400 for uncompiled rubric
# ---------------------------------------------------------------------------

def test_10_uncompiled_rubric_rejected(client, headers_a):
    """Rubric with contract_json=None → 400."""
    import sqlalchemy
    from uuid import uuid4
    from app.config import settings

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)

    # Determine user_a's id from headers
    from app.main import app
    from fastapi.testclient import TestClient

    # Get user id from /api/v0/users/me
    me_resp = client.get("/api/v0/users/me", headers=headers_a)
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    rubric_id = str(uuid4())
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO rubrics (id, user_id, name, draft_json, contract_json, needs_recompilation)
                VALUES (:id, :user_id, 'uncompiled', '{}', NULL, false)
            """),
            {"id": rubric_id, "user_id": user_id},
        )
        conn.commit()

    try:
        with _patch_transcription_infra():
            resp = client.post(
                "/api/v0/transcriptions/transcribe",
                data={"rubric_id": rubric_id},
                files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
                headers=headers_a,
            )
        assert resp.status_code == 400
    finally:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("DELETE FROM rubrics WHERE id = :id"), {"id": rubric_id})
            conn.commit()


# ---------------------------------------------------------------------------
# Test 11 — Happy path /transcribe
# ---------------------------------------------------------------------------

def test_11_transcribe_happy_path(client, headers_a, rubric_a):
    import sqlalchemy
    from app.config import settings

    with _patch_transcription_infra():
        resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "transcription_id" in body
    assert "draft" in body
    draft = body["draft"]
    assert draft["schema_version"] == "1.0"
    assert draft["page_count"] == 1
    assert len(draft["answers"]) == 1
    assert draft["answers"][0]["question_number"] == 1

    # Verify DB row
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)
    with engine.connect() as conn:
        row = conn.execute(
            sqlalchemy.text("SELECT * FROM transcriptions WHERE id = :id"),
            {"id": body["transcription_id"]},
        ).fetchone()

    assert row is not None
    assert row.status == "transcribed"
    assert row.contract_json is None
    assert row.student_id is None
    assert row.draft_json is not None
    assert row.gcs_uri.startswith("gs://")


# ---------------------------------------------------------------------------
# Test 12 — VLM failure → 502, no row inserted
# ---------------------------------------------------------------------------

def test_12_vlm_failure_returns_502(client, headers_a, rubric_a):
    import sqlalchemy
    from app.config import settings

    # Same targeting rule as _patch_transcription_infra: patch transcribe_one's
    # namespace, and pin the engine so the mocked legacy branch is the one taken.
    # (Before this fix the test passed for the WRONG reason — the real two-phase
    # pipeline exploded on the fake PDF, so the 502 had nothing to do with MockSvc.)
    with patch("app.services.transcribe_one.settings.transcription_engine", "legacy"), \
         patch("app.services.transcribe_one.HandwritingTranscriptionService") as MockSvc, \
         patch("app.services.transcribe_one.get_vlm_provider", return_value=MagicMock()), \
         patch("app.services.transcribe_one.pdf_to_images", return_value=[MagicMock()]), \
         patch("app.services.transcribe_one.get_gcs_service"):

        MockSvc.return_value.transcribe_pdf.side_effect = RuntimeError("VLM exploded")

        resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Fixture: transcription_a — creates a real transcriptions row via /transcribe
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def transcription_a(client, headers_a, rubric_a):
    with _patch_transcription_infra():
        resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Test 13 — 401 without token for /grade
# ---------------------------------------------------------------------------
# Already covered by test_8_grade_requires_auth


# ---------------------------------------------------------------------------
# Test 14 — 404 for wrong owner + 409 for already-approved
# ---------------------------------------------------------------------------

def test_14_grade_wrong_transcription_owner(client, headers_b, transcription_a, student_a):
    """User B cannot approve User A's transcription."""
    resp = client.post(
        "/api/v0/transcriptions/grade",
        json={
            "transcription_id": transcription_a["transcription_id"],
            "answers": [{"question_number": 1, "sub_question_id": None, "answer_text": "x"}],
            "student_id": student_a["id"],
        },
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_14_grade_already_approved_returns_409(client, headers_a, student_a, rubric_a):
    """Approving a transcription twice → 409."""
    # Create a fresh transcription
    with _patch_transcription_infra():
        t_resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )
    assert t_resp.status_code == 200
    tx_id = t_resp.json()["transcription_id"]

    answers = [{"question_number": 1, "sub_question_id": None, "answer_text": "foo"}]

    # First approval succeeds
    r1 = client.post(
        "/api/v0/transcriptions/grade",
        json={"transcription_id": tx_id, "answers": answers, "student_id": student_a["id"]},
        headers=headers_a,
    )
    assert r1.status_code == 200, r1.text

    # Second approval → 409
    r2 = client.post(
        "/api/v0/transcriptions/grade",
        json={"transcription_id": tx_id, "answers": answers, "student_id": student_a["id"]},
        headers=headers_a,
    )
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# Test 15 — Cross-tenant student (load-bearing invariant guard)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def student_b(client, headers_b):
    """Student owned by user B."""
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": "תלמיד של B"},
        headers=headers_b,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_15_grade_cross_tenant_student_b_owns(client, headers_a, transcription_a, student_b):
    """User A's transcription + User B's student → 404 (cross-tenant isolation)."""
    resp = client.post(
        "/api/v0/transcriptions/grade",
        json={
            "transcription_id": transcription_a["transcription_id"],
            "answers": [{"question_number": 1, "sub_question_id": None, "answer_text": "x"}],
            "student_id": student_b["id"],
        },
        headers=headers_a,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 16 — Happy path /grade
# ---------------------------------------------------------------------------

def test_16_grade_happy_path(client, headers_a, rubric_a, student_a):
    import sqlalchemy
    from app.config import settings

    # Create a fresh transcription
    with _patch_transcription_infra():
        t_resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )
    assert t_resp.status_code == 200
    tx_id = t_resp.json()["transcription_id"]
    original_draft = t_resp.json()["draft"]

    answers = [{"question_number": 1, "sub_question_id": None, "answer_text": "edited answer"}]
    g_resp = client.post(
        "/api/v0/transcriptions/grade",
        json={"transcription_id": tx_id, "answers": answers, "student_id": student_a["id"]},
        headers=headers_a,
    )
    assert g_resp.status_code == 200, g_resp.text
    g_body = g_resp.json()

    assert "graded_test_id" in g_body
    assert g_body["status"] == "pending"

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)
    with engine.connect() as conn:
        tx_row = conn.execute(
            sqlalchemy.text("SELECT * FROM transcriptions WHERE id = :id"),
            {"id": tx_id},
        ).fetchone()
        gt_row = conn.execute(
            sqlalchemy.text("SELECT * FROM graded_tests WHERE id = :id"),
            {"id": g_body["graded_test_id"]},
        ).fetchone()

    # Transcription updated
    assert tx_row.status == "approved"
    assert tx_row.contract_json is not None
    assert tx_row.student_id is not None
    assert tx_row.student_name == student_a["full_name"]
    assert tx_row.approved_at is not None

    # GradedTest created
    assert gt_row is not None
    assert gt_row.status == "pending"
    assert gt_row.rubric_contract_version is not None
    assert gt_row.regraded_to_id is None  # chain head


# ---------------------------------------------------------------------------
# Test 17 — Draft immutability (load-bearing invariant guard)
# ---------------------------------------------------------------------------

def test_17_draft_immutable_after_grade(client, headers_a, rubric_a, student_a):
    """
    draft_json after /grade must be byte-identical to what /transcribe wrote.
    This test guards Phase 0a §3.1: draft is immutable after INSERT.
    """
    import sqlalchemy
    from app.config import settings

    # Create a fresh transcription
    with _patch_transcription_infra():
        t_resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric_a["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers_a,
        )
    assert t_resp.status_code == 200
    tx_id = t_resp.json()["transcription_id"]

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)

    # Snapshot draft_json before /grade
    with engine.connect() as conn:
        row_before = conn.execute(
            sqlalchemy.text("SELECT draft_json FROM transcriptions WHERE id = :id"),
            {"id": tx_id},
        ).fetchone()
    draft_before = row_before.draft_json

    # Approve
    answers = [{"question_number": 1, "sub_question_id": None, "answer_text": "modified by teacher"}]
    g_resp = client.post(
        "/api/v0/transcriptions/grade",
        json={"transcription_id": tx_id, "answers": answers, "student_id": student_a["id"]},
        headers=headers_a,
    )
    assert g_resp.status_code == 200

    # Snapshot draft_json after /grade
    with engine.connect() as conn:
        row_after = conn.execute(
            sqlalchemy.text("SELECT draft_json FROM transcriptions WHERE id = :id"),
            {"id": tx_id},
        ).fetchone()
    draft_after = row_after.draft_json

    # draft_json must be identical — /grade only writes to contract_json
    assert draft_before == draft_after, (
        "draft_json was mutated by /grade — invariant violation!"
    )


# ---------------------------------------------------------------------------
# Helpers for page endpoint tests (S5)
# ---------------------------------------------------------------------------

def _make_minimal_pdf() -> bytes:
    """Create a real 1-page PDF using PyMuPDF (available in requirements.txt)."""
    import fitz
    doc = fitz.open()
    doc.new_page(width=200, height=280)
    return doc.tobytes()


MINIMAL_VALID_PDF = _make_minimal_pdf()


def _patch_gcs_download(pdf_bytes=None):
    """Mock GCS download_bytes for page endpoint tests."""
    from contextlib import ExitStack
    stack = ExitStack()
    mock_gcs = stack.enter_context(
        patch("app.api.v0.transcription.get_gcs_service")
    )
    mock_gcs.return_value.download_bytes.return_value = pdf_bytes or MINIMAL_VALID_PDF
    return stack


# ---------------------------------------------------------------------------
# Test 18 — 401 without token for /pages
# ---------------------------------------------------------------------------

def test_18_page_requires_auth(client):
    resp = client.get(
        "/api/v0/transcriptions/00000000-0000-0000-0000-000000000001/pages/1"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 19 — Ownership: user B cannot fetch user A's pages
# ---------------------------------------------------------------------------

def test_19_page_wrong_owner(client, headers_b, transcription_a):
    with _patch_gcs_download():
        resp = client.get(
            f"/api/v0/transcriptions/{transcription_a['transcription_id']}/pages/1",
            headers=headers_b,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 20 — Happy path: returns base64 PNG, PNG magic bytes present
# ---------------------------------------------------------------------------

def test_20_page_happy_path(client, headers_a, transcription_a):
    import base64

    with _patch_gcs_download(MINIMAL_VALID_PDF):
        resp = client.get(
            f"/api/v0/transcriptions/{transcription_a['transcription_id']}/pages/1",
            headers=headers_a,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page_number"] == 1
    assert isinstance(body["thumbnail_base64"], str)
    assert len(body["thumbnail_base64"]) > 0
    decoded = base64.b64decode(body["thumbnail_base64"])
    assert decoded[:4] == b'\x89PNG', "thumbnail_base64 is not a valid PNG"


# ---------------------------------------------------------------------------
# Test 21 — Out-of-range page → 404
# ---------------------------------------------------------------------------

def test_21_page_out_of_range(client, headers_a, transcription_a):
    # transcription_a has page_count=1 (from _canned_result mock); page 99 doesn't exist
    with _patch_gcs_download():
        resp = client.get(
            f"/api/v0/transcriptions/{transcription_a['transcription_id']}/pages/99",
            headers=headers_a,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 22 — PAGE_RENDER_DPI constant is 150
# ---------------------------------------------------------------------------

def test_22_page_render_dpi_is_150():
    from app.api.v0.transcription import PAGE_RENDER_DPI
    assert PAGE_RENDER_DPI == 150
