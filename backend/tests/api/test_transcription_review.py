"""
Batch transcription review, Phase 1 — the teacher review overlay.

PATCH /api/v0/transcriptions/{id}/review (transcriptions.review_json) plus the
approval-transition null-out in all three approval paths and the accept_clean
exclusion rule (plan Δ1/Δ2/Δ3/Δ10/Δ16).

Named tests required by the Phase-1 GO ruling:
  * cross-tenant PATCH → 404
  * PATCH on approved → 409
  * key-set mismatch triplet → 422 (missing / extra / duplicate)
  * cross-tenant student_id in body → 404 (Δ16)
  * overlay-nulled-at-approval across all three paths + subsequent PATCH 409 (Δ3)
  * clean-item-edited-then-bulk-accept incl. the skip report (Δ1)
  * batch-detail ordering asserted deterministic (Δ10)

Uses FastAPI TestClient against the real database (migration 014 applied).
VLM/GCS mocked via test_transcription_endpoints helpers; grading kickoff
patched out — never call OpenAI in tests.
"""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import sqlalchemy

from app.config import settings
from app.services.handwriting_transcription_service import (
    TranscribedAnswer,
    TranscriptionResult,
)

from tests.api.test_transcription_endpoints import (
    FAKE_PDF,
    _patch_transcription_infra,
)
from tests.api.test_batch_grading import _clean_draft


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _two_answer_result() -> TranscriptionResult:
    """Two answers — (q1, None) and (q2, 'א') — so key-set mismatches are real."""
    return TranscriptionResult(
        student_name="רז כהן",
        filename="test.pdf",
        answers=[
            TranscribedAnswer(
                question_number=1, sub_question_id=None,
                answer_text="public int foo() { return 1; }",
                confidence=0.9, page_numbers=[1],
            ),
            TranscribedAnswer(
                question_number=2, sub_question_id="א",
                answer_text="public int bar() { return 2; }",
                confidence=0.9, page_numbers=[1],
            ),
        ],
    )


FULL_SNAPSHOT = [
    {"question_number": 1, "sub_question_id": None, "answer_text": "edited 1"},
    {"question_number": 2, "sub_question_id": "א", "answer_text": "edited 2"},
]


def _make_transcription(client, headers, rubric) -> str:
    """Create a real 'transcribed' row via /transcribe (VLM/GCS mocked)."""
    with _patch_transcription_infra(transcription_result=_two_answer_result()):
        resp = client.post(
            "/api/v0/transcriptions/transcribe",
            data={"rubric_id": rubric["rubric_id"]},
            files={"file": ("test.pdf", io.BytesIO(FAKE_PDF), "application/pdf")},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["transcription_id"]


def _patch_review(client, headers, tx_id: str, answers=None, student_id=None):
    return client.patch(
        f"/api/v0/transcriptions/{tx_id}/review",
        json={"answers": answers if answers is not None else FULL_SNAPSHOT,
              "student_id": student_id},
        headers=headers,
    )


def _db_row(tx_id: str):
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)
    with engine.connect() as conn:
        row = conn.execute(
            sqlalchemy.text("SELECT * FROM transcriptions WHERE id = :id"),
            {"id": tx_id},
        ).fetchone()
    engine.dispose()
    return row


def _user_id(signup_response: dict) -> str:
    """The signup AuthResponse carries the user object — no extra request."""
    return signup_response["user"]["id"]


def _sync_engine():
    return sqlalchemy.create_engine(
        settings.database_url.replace("+asyncpg", "+psycopg2")
    )


def _insert_batch_sync(user_id: str, rubric_id: str, test_count: int) -> str:
    """Direct row insert via the SYNC engine — no event loop involved.

    (The neighboring test_batch_grading helpers use asyncio.run() against the
    app's shared async engine, whose pooled connections are bound to the
    TestClient loop — that pattern currently RuntimeErrors; see Phase-1 report.)
    """
    batch_id = str(uuid.uuid4())
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO grading_batches "
                "(id, created_at, user_id, rubric_id, name, status, started_at, "
                " rubric_contract_version, test_count) "
                "VALUES (:id, now(), :uid, :rid, 'Review P1 Batch', 'in_progress', "
                " now(), 'test-v1', :tc)"
            ),
            {"id": batch_id, "uid": user_id, "rid": rubric_id, "tc": test_count},
        )
        conn.commit()
    engine.dispose()
    return batch_id


def _insert_transcription_sync(
    user_id: str, rubric_id: str, batch_id: str, draft_json: dict,
    created_at: datetime | None = None,
) -> str:
    tx_id = str(uuid.uuid4())
    ts = created_at or datetime.now(timezone.utc)
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO transcriptions "
                "(id, user_id, rubric_id, batch_id, gcs_uri, gcs_bucket, "
                " gcs_object_path, filename, draft_json, status, created_at, updated_at) "
                "VALUES (:id, :uid, :rid, :bid, 'gs://stub/stub.pdf', 'stub', "
                " 'stub.pdf', 'test.pdf', CAST(:dj AS JSONB), 'transcribed', :ts, :ts)"
            ),
            {"id": tx_id, "uid": user_id, "rid": rubric_id, "bid": batch_id,
             "dj": json.dumps(draft_json), "ts": ts},
        )
        conn.commit()
    engine.dispose()
    return tx_id


def _cleanup_batch(batch_id: str, transcription_ids: list[str]) -> None:
    """Delete graded_tests → transcriptions → batch (FK-order agnostic)."""
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)
    with engine.connect() as conn:
        for tid in transcription_ids:
            conn.execute(
                sqlalchemy.text("DELETE FROM graded_tests WHERE transcription_id = :id"),
                {"id": tid},
            )
            conn.execute(
                sqlalchemy.text("DELETE FROM transcriptions WHERE id = :id"),
                {"id": tid},
            )
        conn.execute(
            sqlalchemy.text("DELETE FROM grading_batches WHERE id = :id"),
            {"id": batch_id},
        )
        conn.commit()
    engine.dispose()


@pytest.fixture(scope="module")
def student_b(client, headers_b):
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": "תלמיד של משתמש ב"},
        headers=headers_b,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Auth + ownership
# ---------------------------------------------------------------------------

def test_review_requires_auth(client):
    resp = client.patch(
        f"/api/v0/transcriptions/{uuid.uuid4()}/review",
        json={"answers": [], "student_id": None},
    )
    assert resp.status_code == 401


def test_review_cross_tenant_404(client, headers_a, headers_b, rubric_a):
    """User B PATCHes User A's transcription → 404 (never 403 — §9)."""
    tx_id = _make_transcription(client, headers_a, rubric_a)
    resp = _patch_review(client, headers_b, tx_id)
    assert resp.status_code == 404


def test_review_cross_tenant_student_404(client, headers_a, rubric_a, student_b):
    """Δ16: User B's student in the body → 404 at WRITE time, not at accept."""
    tx_id = _make_transcription(client, headers_a, rubric_a)
    resp = _patch_review(client, headers_a, tx_id, student_id=student_b["id"])
    assert resp.status_code == 404
    # Nothing was persisted by the rejected write
    assert _db_row(tx_id).review_json is None


# ---------------------------------------------------------------------------
# Happy path — full snapshot persisted, server-stamped
# ---------------------------------------------------------------------------

def test_review_happy_path_persists_full_snapshot(client, headers_a, rubric_a, student_a):
    tx_id = _make_transcription(client, headers_a, rubric_a)

    resp = _patch_review(client, headers_a, tx_id, student_id=student_a["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["schema_version"] == "1.0"
    assert body["student_id"] == student_a["id"]
    assert body["updated_at"] is not None          # server-stamped
    assert [a["answer_text"] for a in body["answers"]] == ["edited 1", "edited 2"]

    row = _db_row(tx_id)
    assert row.status == "transcribed"             # save is NOT approval
    assert row.student_id is None                  # CHECK-protected column untouched
    assert row.review_json is not None
    assert row.review_json["student_id"] == student_a["id"]
    assert len(row.review_json["answers"]) == 2

    # Last-write-wins: a second full snapshot replaces the first wholesale
    second = [
        {"question_number": 1, "sub_question_id": None, "answer_text": "v2"},
        {"question_number": 2, "sub_question_id": "א", "answer_text": "v2b"},
    ]
    resp2 = _patch_review(client, headers_a, tx_id, answers=second)
    assert resp2.status_code == 200
    row2 = _db_row(tx_id)
    assert [a["answer_text"] for a in row2.review_json["answers"]] == ["v2", "v2b"]
    assert row2.review_json["student_id"] is None  # whole-snapshot replace, no merge


# ---------------------------------------------------------------------------
# Full-snapshot guard — the mismatch triplet → 422 (Δ2)
# ---------------------------------------------------------------------------

def test_review_key_set_mismatch_422(client, headers_a, rubric_a):
    tx_id = _make_transcription(client, headers_a, rubric_a)

    missing = [FULL_SNAPSHOT[0]]                                   # q2.א missing
    extra = FULL_SNAPSHOT + [
        {"question_number": 3, "sub_question_id": None, "answer_text": "ghost"}
    ]
    duplicate = [FULL_SNAPSHOT[0], FULL_SNAPSHOT[0],               # q1 twice
                 FULL_SNAPSHOT[1]]

    for bad in (missing, extra, duplicate):
        resp = _patch_review(client, headers_a, tx_id, answers=bad)
        assert resp.status_code == 422, f"body={bad} → {resp.status_code}: {resp.text}"

    # Never normalized silently: nothing was persisted by any rejected write
    assert _db_row(tx_id).review_json is None


# ---------------------------------------------------------------------------
# Lifecycle — approved is read-only; overlay nulled at approval (Δ3, LCY-1)
# ---------------------------------------------------------------------------

def test_overlay_nulled_at_approval_grade_path(client, headers_a, rubric_a, student_a):
    """/grade path: overlay saved → approval nulls it in the transition → PATCH 409."""
    tx_id = _make_transcription(client, headers_a, rubric_a)
    assert _patch_review(client, headers_a, tx_id).status_code == 200
    assert _db_row(tx_id).review_json is not None

    with patch("app.api.v0.transcription.enqueue_grading_task_or_log"):   # never enqueue grading in tests
        g = client.post(
            "/api/v0/transcriptions/grade",
            json={
                "transcription_id": tx_id,
                "answers": FULL_SNAPSHOT,
                "student_id": student_a["id"],
            },
            headers=headers_a,
        )
    assert g.status_code == 200, g.text

    row = _db_row(tx_id)
    assert row.status == "approved"
    assert row.review_json is None                 # nulled IN the transition write

    resp = _patch_review(client, headers_a, tx_id)
    assert resp.status_code == 409                 # LCY-1: approved is read-only


@pytest.mark.integration
def test_overlay_nulled_at_approval_accept_one(client, user_a, headers_a, rubric_a, student_a):
    """accept_one path: same transition null-out + subsequent PATCH 409."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch_sync(user_id, rubric_a["rubric_id"], test_count=1)
    tx_id = _insert_transcription_sync(
        user_id, rubric_a["rubric_id"], batch_id,
        _clean_draft().model_dump(mode="json"),
    )
    try:
        one_answer = [{"question_number": 1, "sub_question_id": None,
                       "answer_text": "reviewed"}]
        assert _patch_review(client, headers_a, tx_id, answers=one_answer).status_code == 200

        with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log"):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx_id}",
                json={"student_id": student_a["id"], "answers": one_answer},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text

        row = _db_row(tx_id)
        assert row.status == "approved"
        assert row.review_json is None
        assert _patch_review(client, headers_a, tx_id, answers=one_answer).status_code == 409
    finally:
        _cleanup_batch(batch_id, [tx_id])


@pytest.mark.integration
def test_clean_item_edited_then_bulk_accept(client, user_a, headers_a, rubric_a, student_a):
    """
    Δ1 named test: a clean item with a saved overlay is EXCLUDED from bulk
    accept server-side (edited item stays 'transcribed', overlay intact, skip
    reported); the untouched clean item approves — with review_json NULL and a
    subsequent PATCH 409 (the accept_clean leg of the Δ3 null-out).
    """
    user_id = _user_id(user_a)
    batch_id = _insert_batch_sync(user_id, rubric_a["rubric_id"], test_count=2)
    # B1: the untouched item must be verdict-CLEAN server-side to approve —
    # its suggestion matches student_a ("תלמיד א"), who is posted for it.
    draft = _clean_draft(student_name="תלמיד א").model_dump(mode="json")
    tx_edited = _insert_transcription_sync(user_id, rubric_a["rubric_id"], batch_id, draft)
    tx_untouched = _insert_transcription_sync(user_id, rubric_a["rubric_id"], batch_id, draft)
    try:
        one_answer = [{"question_number": 1, "sub_question_id": None,
                       "answer_text": "teacher edit"}]
        assert _patch_review(client, headers_a, tx_edited, answers=one_answer).status_code == 200

        with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log"):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": [
                    {"transcription_id": tx_edited, "student_id": student_a["id"]},
                    {"transcription_id": tx_untouched, "student_id": student_a["id"]},
                ]},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["accepted"] == 1
        assert body["skipped"] == [{
            "transcription_id": tx_edited,
            "skipped_reason": "has_review_edits",
        }]

        edited = _db_row(tx_edited)
        assert edited.status == "transcribed"                  # NOT approved
        assert edited.review_json is not None                  # overlay intact
        assert edited.review_json["answers"][0]["answer_text"] == "teacher edit"

        untouched = _db_row(tx_untouched)
        assert untouched.status == "approved"
        assert untouched.review_json is None                   # Δ3, accept_clean leg
        assert _patch_review(client, headers_a, tx_untouched,
                             answers=one_answer).status_code == 409
    finally:
        _cleanup_batch(batch_id, [tx_edited, tx_untouched])


# ---------------------------------------------------------------------------
# Batch detail — deterministic order (Δ10) + payload additions (review, created_at)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_batch_detail_order_deterministic(client, user_a, headers_a, rubric_a):
    user_id = _user_id(user_a)
    batch_id = _insert_batch_sync(user_id, rubric_a["rubric_id"], test_count=3)
    draft = _clean_draft().model_dump(mode="json")
    # Distinct created_at per row: the ORDER BY (created_at, id) must reflect
    # insertion order without relying on sub-millisecond clock resolution.
    base = datetime.now(timezone.utc)
    tx_ids = [
        _insert_transcription_sync(
            user_id, rubric_a["rubric_id"], batch_id, draft,
            created_at=base + timedelta(seconds=i),
        )
        for i in range(3)
    ]
    try:
        # Overlay on the middle item, so the payload exercises both review states
        one_answer = [{"question_number": 1, "sub_question_id": None,
                       "answer_text": "middle edit"}]
        assert _patch_review(client, headers_a, tx_ids[1], answers=one_answer).status_code == 200

        def fetch_order():
            resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
            assert resp.status_code == 200, resp.text
            return resp.json()["transcriptions"]

        first = fetch_order()
        second = fetch_order()

        order1 = [t["transcription_id"] for t in first]
        order2 = [t["transcription_id"] for t in second]
        assert order1 == order2                    # stable across polls
        assert order1 == tx_ids                    # (created_at, id) = insertion order

        # Δ15 field: item-level created_at present and ISO-parseable
        for t in first:
            datetime.fromisoformat(t["created_at"])

        # Overlay exposure: present on the edited item, null elsewhere
        by_id = {t["transcription_id"]: t for t in first}
        assert by_id[tx_ids[1]]["review"] is not None
        assert by_id[tx_ids[1]]["review"]["answers"][0]["answer_text"] == "middle edit"
        assert by_id[tx_ids[0]]["review"] is None
        assert by_id[tx_ids[2]]["review"] is None
    finally:
        _cleanup_batch(batch_id, tx_ids)
