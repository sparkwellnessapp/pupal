"""
P1 exposure items (batch-redesign spec v2): B3 active_jobs · B4 rubric/class
names · B5 rename · B6 approved_answers · B10 list-page liveness parity.

Live-DB integration tests (TestClient against DATABASE_URL), sync-engine row
helpers per the house pattern. Grading kickoff patched at the Cloud-Tasks seam.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy

from tests.api.test_accept_guards import _create_student
from tests.api.test_batch_grading import _clean_draft
from tests.api.test_transcription_review import (
    _cleanup_batch,
    _insert_transcription_sync,
    _sync_engine,
    _user_id,
)

_ENQUEUE_SEAM = "app.api.v0.batch_grading.enqueue_grading_task_or_log"


# ---------------------------------------------------------------------------
# Local sync helpers (batch with class_id; job rows honoring the 016 CHECK)
# ---------------------------------------------------------------------------

def _insert_batch(user_id: str, rubric_id: str, test_count: int = 0,
                  class_id: str | None = None) -> str:
    batch_id = str(uuid.uuid4())
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO grading_batches "
                "(id, created_at, updated_at, user_id, rubric_id, class_id, name, "
                " status, started_at, rubric_contract_version, test_count) "
                "VALUES (:id, now(), now(), :uid, :rid, :cid, NULL, 'in_progress', "
                " now(), 'test-v1', :tc)"
            ),
            {"id": batch_id, "uid": user_id, "rid": rubric_id,
             "cid": class_id, "tc": test_count},
        )
        conn.commit()
    engine.dispose()
    return batch_id


def _insert_job(user_id: str, batch_id: str, rubric_id: str, status: str,
                prio: int, filename: str, *, started: bool = False,
                updated_delta_min: int = 0) -> str:
    """Insert a transcription_jobs row honoring transcription_jobs_status_consistency:
    queued/running ⇒ no finished_at/error_message; failed ⇒ both set."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    updated = now + timedelta(minutes=updated_delta_min)
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO transcription_jobs "
                "(id, user_id, batch_id, rubric_id, status, source_gcs_object_path, "
                " source_filename, doc_priority, attempt_count, created_at, "
                " started_at, finished_at, error_message, updated_at) "
                "VALUES (:id, :uid, :bid, :rid, :status, 'stub.pdf', :fname, :prio, "
                " :attempts, :created, :started, :finished, :error, :updated)"
            ),
            {
                "id": job_id, "uid": user_id, "bid": batch_id, "rid": rubric_id,
                "status": status, "fname": filename, "prio": prio,
                "attempts": 1 if status != "queued" else 0,
                "created": now,
                "started": (now if (started or status in ("running", "failed")) else None),
                "finished": (now if status in ("completed", "failed") else None),
                "error": ("boom: test failure" if status == "failed" else None),
                "updated": updated,
            },
        )
        conn.commit()
    engine.dispose()
    return job_id


def _set_contract_json(tx_id: str, raw_json: str) -> None:
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "UPDATE transcriptions SET contract_json = CAST(:cj AS JSONB) WHERE id = :id"
            ),
            {"cj": raw_json, "id": tx_id},
        )
        conn.commit()
    engine.dispose()


# ---------------------------------------------------------------------------
# B3 — active jobs on batch detail
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_batch_detail_active_jobs_mix(client, user_a, headers_a, rubric_a):
    """queued+running+failed → active_jobs carries the two active ones in
    doc_priority order (running with started_at); failed is a failure card."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=3)
    _insert_job(user_id, batch_id, rubric_id, "queued", 0, "a.pdf")
    _insert_job(user_id, batch_id, rubric_id, "running", 1, "b.pdf", started=True)
    _insert_job(user_id, batch_id, rubric_id, "failed", 2, "c.pdf")
    try:
        resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        aj = body["active_jobs"]
        assert [j["filename"] for j in aj] == ["a.pdf", "b.pdf"]
        assert [j["state"] for j in aj] == ["queued", "running"]
        assert aj[0]["started_at"] is None
        assert aj[1]["started_at"] is not None
        assert all(isinstance(j["attempt_count"], int) for j in aj)
        assert all(j["created_at"] for j in aj)
        # The failed job is a failure card, never an active ghost.
        assert [f["filename"] for f in body["transcription_failures"]] == ["c.pdf"]
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_active_jobs_built_after_reap(client, user_a, headers_a, rubric_a):
    """A running job whose heartbeat lapsed (updated_at 10min old > 5min TTL)
    is reaped ON READ: it appears as a failure, never as an active job."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=1)
    _insert_job(user_id, batch_id, rubric_id, "running", 0, "stale.pdf",
                started=True, updated_delta_min=-10)
    try:
        resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["active_jobs"] == []
        assert [f["filename"] for f in body["transcription_failures"]] == ["stale.pdf"]
        assert body["rollup"]["transcription_failed"] == 1
        assert body["rollup"]["transcribing"] == 0
    finally:
        _cleanup_batch(batch_id, [])


# ---------------------------------------------------------------------------
# B4 — rubric_name / class_name
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_batch_detail_exposes_names(client, user_a, headers_a, rubric_a, class_a):
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    with_class = _insert_batch(user_id, rubric_id, class_id=class_a["id"])
    without_class = _insert_batch(user_id, rubric_id)
    try:
        b1 = client.get(f"/api/v0/batches/{with_class}", headers=headers_a).json()
        assert b1["rubric_name"] == "User A Rubric"
        assert b1["class_name"] == "כיתה א"

        b2 = client.get(f"/api/v0/batches/{without_class}", headers=headers_a).json()
        assert b2["rubric_name"] == "User A Rubric"
        assert b2["class_name"] is None
    finally:
        _cleanup_batch(with_class, [])
        _cleanup_batch(without_class, [])


@pytest.mark.integration
def test_batch_list_exposes_names_without_extra_queries(client, user_a, headers_a,
                                                        rubric_a, class_a):
    """Names on the list payload. (No query-count harness exists — the
    zero-per-batch-round-trips requirement is a code-review note per spec:
    the implementation batch-fetches the user's rubric/class names up front.)"""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, class_id=class_a["id"])
    try:
        resp = client.get("/api/v0/batches", headers=headers_a)
        assert resp.status_code == 200, resp.text
        row = next(b for b in resp.json() if b["id"] == batch_id)
        assert row["rubric_name"] == "User A Rubric"
        assert row["class_name"] == "כיתה א"
    finally:
        _cleanup_batch(batch_id, [])


# ---------------------------------------------------------------------------
# B5 — rename
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rename_batch_ok(client, user_a, headers_a, rubric_a):
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    try:
        resp = client.patch(
            f"/api/v0/batches/{batch_id}",
            json={"name": "  מקבץ כיתה ט׳ · תרגול לולאות  "},
            headers=headers_a,
        )
        assert resp.status_code == 200, resp.text
        # EXACT equality on purpose: this endpoint is the batch's settings
        # patch, and a field appearing here without anyone noticing is how a
        # response starts carrying something the client never agreed to.
        #
        # The four fields beyond {batch_id, name} are PR-G9's: the same PATCH
        # now also sets the appendix and stamp-position defaults, and it REPORTS
        # what that cost — `invalidated_count` returned exams whose cache it
        # dropped, `stamp_applied_count` per-test positions it cleared. Both are
        # reported rather than silently done, so the teacher is told her PDFs
        # will re-render instead of wondering why a download she just made looks
        # different. A rename alone changes neither, hence the zeros.
        #
        # `expected_test_count` (Stage A, migration 025) is the fifth: the same
        # PATCH is now also the RE-DECLARE — how a file that will never land
        # stops blocking completion (R9). It echoes the declaration as it stands
        # so the client can confirm the server's number rather than assume its
        # own. None here because this batch never declared one, and a rename
        # does not invent a declaration.
        assert resp.json() == {
            "batch_id": batch_id, "name": "מקבץ כיתה ט׳ · תרגול לולאות",
            "appendix_include_criteria": False,
            "stamp_position_default": None,
            "invalidated_count": 0,
            "stamp_applied_count": 0,
            "expected_test_count": None,
        }
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        assert detail["name"] == "מקבץ כיתה ט׳ · תרגול לולאות"
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_rename_rejects_blank(client, user_a, headers_a, rubric_a):
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    try:
        for bad in ("", "   "):
            resp = client.patch(
                f"/api/v0/batches/{batch_id}", json={"name": bad}, headers=headers_a,
            )
            assert resp.status_code == 422, f"{bad!r} → {resp.status_code}"
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_rename_cross_tenant_404(client, user_a, headers_a, headers_b, rubric_a):
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    try:
        resp = client.patch(
            f"/api/v0/batches/{batch_id}", json={"name": "גניבה"}, headers=headers_b,
        )
        assert resp.status_code == 404
    finally:
        _cleanup_batch(batch_id, [])


# ---------------------------------------------------------------------------
# B6 — approved items carry the contract answers
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_approved_item_carries_contract_answers(client, user_a, headers_a, rubric_a):
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=1)
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id, _clean_draft().model_dump(mode="json"),
    )
    s_id = _create_student(client, headers_a, f"תלמיד חוזה {uuid4().hex[:6]}")
    try:
        with patch(_ENQUEUE_SEAM):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx}",
                json={"student_id": s_id, "answers": [
                    {"question_number": 1, "sub_question_id": None,
                     "answer_text": "EDITED BY TEACHER"},
                ]},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text

        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        item = next(i for i in detail["transcriptions"] if i["transcription_id"] == tx)
        assert item["transcription_status"] == "approved"
        assert item["approved_answers"] == [{
            "question_number": 1, "sub_question_id": None,
            "answer_text": "EDITED BY TEACHER",
        }]
        # One truth per field: the draft still carries the ORIGINAL VLM text.
        assert item["draft"]["answers"][0]["answer_text"] == "public class Node { int val; }"
    finally:
        _cleanup_batch(batch_id, [tx])


@pytest.mark.integration
def test_corrupt_contract_json_degrades_gracefully(client, user_a, headers_a, rubric_a):
    """A corrupt contract_json on one approved row must omit that item's
    approved_answers — never 500 the whole batch read."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=1)
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id, _clean_draft().model_dump(mode="json"),
    )
    s_id = _create_student(client, headers_a, f"תלמיד שבור {uuid4().hex[:6]}")
    try:
        with patch(_ENQUEUE_SEAM):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx}",
                json={"student_id": s_id, "answers": [
                    {"question_number": 1, "sub_question_id": None, "answer_text": "ok"},
                ]},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text
        _set_contract_json(tx, json.dumps("not-a-contract-object"))

        resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        item = next(i for i in resp.json()["transcriptions"]
                    if i["transcription_id"] == tx)
        assert item["transcription_status"] == "approved"
        assert item["approved_answers"] is None
    finally:
        _cleanup_batch(batch_id, [tx])


# ---------------------------------------------------------------------------
# B10 — list-page liveness parity
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_list_reaps_expired_jobs(client, user_a, headers_a, rubric_a):
    """An expired running job shows as transcription_failed on the LIST —
    without anyone opening the detail page first."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch(user_id, rubric_id, test_count=1)
    _insert_job(user_id, batch_id, rubric_id, "running", 0, "lapsed.pdf",
                started=True, updated_delta_min=-10)
    try:
        resp = client.get("/api/v0/batches", headers=headers_a)
        assert resp.status_code == 200, resp.text
        row = next(b for b in resp.json() if b["id"] == batch_id)
        assert row["rollup"]["transcription_failed"] == 1
        assert row["rollup"]["transcribing"] == 0
    finally:
        _cleanup_batch(batch_id, [])
