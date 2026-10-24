"""
In-house scanning — the BATCH side (rulings OD-1, OD-2, OD-3; migration 036).

  OD-2  a WITHDRAWN job (a superseded capture version, a discarded submission)
        and its scan are not part of the batch: one test per read path —
        get_batch, list_batches, the rollup, accept_clean, accept_one, the
        per-document retry — and accepting or retrying one answers 409.
  OD-3  a capture scan's student comes from the submission while it is
        `transcribed`: CONFIRMED → an exact, bulk-acceptable match; PENDING or
        CONFLICT → never clean; once APPROVED the transcription is the truth
        and the approved student is written back onto the submission.
  OD-1  step 0 of the runner compiles a capture job's PDF when it is missing,
        skips when it exists, and lands a refusal as a failed, retryable job.

Rows are seeded directly (the capture service has its own tests); the scan
service and GCS are fakes — nothing here reaches a network.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text

from app.schemas.transcription import TranscriptionDraft, TranscriptionDraftAnswer
from tests.api.test_batch_grading import _fresh_loop_session, _load_job_row, _run_sandwiched

pytestmark = pytest.mark.integration

NOW = lambda: datetime.now(timezone.utc)                                    # noqa: E731


def _draft(name: str = "שם שנקרא מהדף") -> dict:
    return TranscriptionDraft(
        student_name_suggestion=name, page_count=1,
        answers=[TranscriptionDraftAnswer(question_number=1, sub_question_id=None,
                                          answer_text="x = 1", confidence=0.95,
                                          page_numbers=[1])],
        annotations=[],
    ).model_dump(mode="json")


async def _batch(user_id: str, rubric_id: str) -> uuid.UUID:
    from app.models.grading import GradingBatch

    async with _fresh_loop_session() as db:
        b = GradingBatch(user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
                         rubric_contract_version="test-v1", name="capture batch",
                         status="in_progress", test_count=0, started_at=NOW())
        db.add(b)
        await db.commit()
        return b.id


async def _student(user_id: str) -> tuple[uuid.UUID, str]:
    from app.models.student import Student

    name = f"תלמידת צילום {uuid.uuid4().hex[:6]}"
    async with _fresh_loop_session() as db:
        s = Student(user_id=uuid.UUID(user_id), full_name=name)
        db.add(s)
        await db.commit()
        return s.id, name


async def _capture(user_id: str, rubric_id: str, batch_id: uuid.UUID, *, state: str,
                   student_id=None, pending_name=None, withdrawn=False,
                   job_status="completed", with_scan=True) -> dict:
    """One saved capture submission with one version and its job (and, for a
    completed job, its `transcribed` scan). state ∈ confirmed|pending|conflict."""
    from app.models.capture import CaptureLink, CapturePage, CaptureSubmission, CaptureVersion
    from app.models.transcription import Transcription
    from app.models.transcription_job import TranscriptionJob
    from app.services.capture import paths

    uid, rid = uuid.UUID(user_id), uuid.UUID(rubric_id)
    async with _fresh_loop_session() as db:
        link_id = None
        if state != "confirmed":
            link_id = (await db.execute(text(
                "SELECT id FROM capture_links WHERE batch_id = :b"), {"b": batch_id})).scalar()
            if link_id is None:
                link_id = uuid.uuid4()
                db.add(CaptureLink(id=link_id, batch_id=batch_id, user_id=uid,
                                   token_hash=uuid.uuid4().bytes, exam_date=NOW().date()))
                await db.flush()
        sub = CaptureSubmission(
            batch_id=batch_id, user_id=uid,
            source="teacher" if state == "confirmed" else "student_link",
            link_id=link_id, device_secret_hash=None if link_id is None else uuid.uuid4().bytes,
            student_id=student_id, student_state=state, pending_student_name=pending_name,
            conflict_note="duplicate_student" if state == "conflict" else None, status="draft")
        db.add(sub)
        await db.flush()
        page = CapturePage(submission_id=sub.id, raw_gcs_uri="gs://b/x", content_type="image/jpeg",
                           status="analyzed", image_w=10, image_h=10,
                           corners=[[0, 0], [1, 0], [1, 1], [0, 1]], corners_source="full_frame",
                           position=1)
        version = CaptureVersion(submission_id=sub.id, version_no=1,
                                 pages_snapshot=[{"page_id": "p"}], scan_pipeline_version="scan-v1.0")
        db.add_all([page, version])
        await db.flush()
        await db.execute(text("UPDATE capture_submissions SET status='saved', current_version_id=:v "
                              "WHERE id=:s"), {"v": version.id, "s": sub.id})
        path = paths.pdf_path(sub.id, version.id)
        t_id = None
        if job_status == "completed" and with_scan:
            t = Transcription(user_id=uid, rubric_id=rid, batch_id=batch_id, gcs_uri=f"gs://b/{path}",
                              gcs_bucket="b", gcs_object_path=path, filename="x.pdf",
                              draft_json=_draft(), status="transcribed")
            db.add(t)
            await db.flush()
            t_id = t.id
        job = TranscriptionJob(
            user_id=uid, batch_id=batch_id, rubric_id=rid, status=job_status,
            source_gcs_object_path=path, source_filename="x.pdf", capture_version_id=version.id,
            transcription_id=t_id, withdrawn_at=NOW() if withdrawn else None,
            finished_at=NOW() if job_status in ("completed", "failed") else None,
            error_message="boom" if job_status == "failed" else None)
        db.add(job)
        await db.commit()
        return {"sub": sub.id, "version": version.id, "job": job.id, "t": t_id, "path": path}


async def _drop(batch_id: uuid.UUID) -> None:
    async with _fresh_loop_session() as db:
        b = {"b": batch_id}
        await db.execute(text(
            "DELETE FROM graded_tests WHERE transcription_id IN "
            "(SELECT id FROM transcriptions WHERE batch_id = :b)"), b)
        await db.execute(text("DELETE FROM transcription_jobs WHERE batch_id = :b"), b)
        await db.execute(text("DELETE FROM transcriptions WHERE batch_id = :b"), b)
        await db.execute(text("DELETE FROM capture_pages WHERE submission_id IN "
                              "(SELECT id FROM capture_submissions WHERE batch_id = :b)"), b)
        await db.execute(text(
            "WITH v AS (DELETE FROM capture_versions WHERE submission_id IN "
            " (SELECT id FROM capture_submissions WHERE batch_id = :b) RETURNING 1) "
            "DELETE FROM capture_submissions WHERE batch_id = :b"), b)
        await db.execute(text("DELETE FROM capture_links WHERE batch_id = :b"), b)
        await db.execute(text("DELETE FROM grading_batches WHERE id = :b"), b)
        await db.commit()


@pytest.fixture
def ids(user_a, rubric_a):
    batch_id = asyncio.run(_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    yield user_a["user"]["id"], rubric_a["rubric_id"], batch_id
    asyncio.run(_drop(batch_id))


def _seed(ids, **kw):
    user_id, rubric_id, batch_id = ids
    return asyncio.run(_capture(user_id, rubric_id, batch_id, **kw))


def _detail(client, headers, batch_id):
    r = client.get(f"/api/v0/batches/{batch_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# OD-2 — a withdrawn job is not part of the batch, on every read path
# ---------------------------------------------------------------------------

def _live_and_withdrawn(ids):
    sid, _ = asyncio.run(_student(ids[0]))
    live = _seed(ids, state="confirmed", student_id=sid)
    gone = _seed(ids, state="confirmed", student_id=sid, withdrawn=True)
    return live, gone


def test_get_batch_omits_a_withdrawn_job_and_its_scan(client, headers_a, ids):
    live, gone = _live_and_withdrawn(ids)
    body = _detail(client, headers_a, ids[2])
    tids = {t["transcription_id"] for t in body["transcriptions"]}
    assert tids == {str(live["t"])}


def test_the_rollup_counts_live_jobs_only(client, headers_a, ids):
    _live_and_withdrawn(ids)
    _seed(ids, state="confirmed", student_id=asyncio.run(_student(ids[0]))[0],
          withdrawn=True, job_status="queued")
    _seed(ids, state="confirmed", student_id=asyncio.run(_student(ids[0]))[0],
          withdrawn=True, job_status="failed")
    rollup = _detail(client, headers_a, ids[2])["rollup"]
    assert rollup["total"] == 1
    assert rollup["transcribing"] == 0 and rollup["transcription_failed"] == 0
    body = _detail(client, headers_a, ids[2])
    assert body["active_jobs"] == [] and body["transcription_failures"] == []


def test_list_batches_omits_a_withdrawn_job(client, headers_a, ids):
    _live_and_withdrawn(ids)
    rows = client.get("/api/v0/batches", headers=headers_a).json()
    (row,) = [r for r in rows if r["id"] == str(ids[2])]
    assert row["rollup"]["total"] == 1
    assert row["rollup"]["transcribed"] == 1


def test_accept_one_of_a_withdrawn_scan_is_409(client, headers_a, ids):
    sid, _ = asyncio.run(_student(ids[0]))
    gone = _seed(ids, state="confirmed", student_id=sid, withdrawn=True)
    r = client.post(f"/api/v0/batches/{ids[2]}/accept/{gone['t']}", headers=headers_a,
                    json={"student_id": str(sid),
                          "answers": [{"question_number": 1, "sub_question_id": None,
                                       "answer_text": "x = 1"}]})
    assert r.status_code == 409, r.text


def test_accept_clean_of_a_withdrawn_scan_is_409_and_accepts_nothing(client, headers_a, ids):
    sid, _ = asyncio.run(_student(ids[0]))
    live = _seed(ids, state="confirmed", student_id=sid)
    gone = _seed(ids, state="confirmed", student_id=sid, withdrawn=True)
    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()):
        r = client.post(f"/api/v0/batches/{ids[2]}/accept_clean", headers=headers_a, json={
            "items": [{"transcription_id": str(live["t"]), "student_id": str(sid)},
                      {"transcription_id": str(gone["t"]), "student_id": str(sid)}]})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["transcription_id"] == str(gone["t"])
    statuses = {t["transcription_status"] for t in _detail(client, headers_a, ids[2])["transcriptions"]}
    assert statuses == {"transcribed"}                       # all-or-nothing: nothing accepted


def test_retrying_a_withdrawn_failed_job_is_409(client, headers_a, ids):
    sid, _ = asyncio.run(_student(ids[0]))
    gone = _seed(ids, state="confirmed", student_id=sid, withdrawn=True, job_status="failed")
    with patch("app.api.v0.batch_grading.enqueue_transcription_task", new=AsyncMock()) as enq:
        r = client.post(f"/api/v0/batches/{ids[2]}/jobs/{gone['job']}/retry", headers=headers_a)
    assert r.status_code == 409
    enq.assert_not_called()
    assert asyncio.run(_load_job_row(str(gone["job"])))["status"] == "failed"


# ---------------------------------------------------------------------------
# OD-3 — the capture student overlay
# ---------------------------------------------------------------------------

def _item(client, headers, batch_id, t_id):
    (item,) = [t for t in _detail(client, headers, batch_id)["transcriptions"]
               if t["transcription_id"] == str(t_id)]
    return item


def test_a_confirmed_capture_student_is_a_clean_exact_match_and_bulk_acceptable(client, headers_a, ids):
    """Case 1. The page read a DIFFERENT name; the confirmed student wins."""
    sid, name = asyncio.run(_student(ids[0]))
    cap = _seed(ids, state="confirmed", student_id=sid)
    item = _item(client, headers_a, ids[2], cap["t"])
    assert item["matched_student_id"] == str(sid)
    assert item["student_name_suggestion"] == name
    assert item["flag_verdict"] == {"review_needed": False, "reasons": []}
    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()):
        r = client.post(f"/api/v0/batches/{ids[2]}/accept_clean", headers=headers_a, json={
            "items": [{"transcription_id": str(cap["t"]), "student_id": str(sid)}]})
    assert r.status_code == 200 and r.json()["accepted"] == 1, r.text


@pytest.mark.parametrize("state,reason", [("pending", "capture_student_pending"),
                                          ("conflict", "capture_conflict")])
def test_pending_or_conflict_is_never_clean(client, headers_a, ids, state, reason):
    """Case 2: needs her eyes — counted needs-eyes, refused by bulk accept."""
    sid, _ = asyncio.run(_student(ids[0]))
    cap = _seed(ids, state=state, pending_name="שם שהוקלד", student_id=sid if state == "conflict" else None)
    item = _item(client, headers_a, ids[2], cap["t"])
    assert item["flag_verdict"]["review_needed"] is True
    assert reason in item["flag_verdict"]["reasons"]
    assert item["matched_student_id"] is None
    assert item["student_name_suggestion"] == "שם שהוקלד"
    assert _detail(client, headers_a, ids[2])["rollup"]["needs_eyes"] == 1
    r = client.post(f"/api/v0/batches/{ids[2]}/accept_clean", headers=headers_a, json={
        "items": [{"transcription_id": str(cap["t"]), "student_id": str(sid)}]})
    assert r.status_code == 200
    assert r.json()["accepted"] == 0
    assert r.json()["skipped"][0]["skipped_reason"] == "flagged"


def test_after_approval_the_transcription_is_the_truth_and_is_written_back(client, headers_a, ids):
    """Case 3: she approves a PENDING submission as someone else; the overlay
    no longer applies, and the submission now names the approved student."""
    other, other_name = asyncio.run(_student(ids[0]))
    cap = _seed(ids, state="pending", pending_name="שם שהוקלד")
    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()):
        r = client.post(f"/api/v0/batches/{ids[2]}/accept/{cap['t']}", headers=headers_a,
                        json={"student_id": str(other),
                              "answers": [{"question_number": 1, "sub_question_id": None,
                                           "answer_text": "x = 1"}]})
    assert r.status_code == 200, r.text
    item = _item(client, headers_a, ids[2], cap["t"])
    assert item["transcription_status"] == "approved"
    assert "capture_student_pending" not in item["flag_verdict"]["reasons"]

    async def submission():
        async with _fresh_loop_session() as db:
            return (await db.execute(text(
                "SELECT student_id, student_state FROM capture_submissions WHERE id = :s"),
                {"s": cap["sub"]})).one()
    assert tuple(asyncio.run(submission())) == (other, "confirmed")


# ---------------------------------------------------------------------------
# OD-1 — step 0 of the runner
# ---------------------------------------------------------------------------

class _FakeScan:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    async def compile(self, pages_snapshot, scan_pipeline_version, out_uri, *, timeout_s):
        from app.services.capture.scan_client import CompileResult

        self.calls.append((pages_snapshot, scan_pipeline_version, out_uri, timeout_s))
        if self.error:
            raise self.error
        return CompileResult(pdf_uri=out_uri, page_count=1, bytes=1234)


def _run_job(job_id, *, scan, object_size):
    from app.services import transcription_job_runner as runner
    from app.services.capture.scan_client import set_scan_client
    from tests.api.test_batch_grading import _clean_draft

    gcs = MagicMock()
    gcs.object_size.return_value = object_size
    gcs.download_bytes.return_value = b"%PDF"
    pipeline = AsyncMock(return_value=_clean_draft(student_name="שם"))
    set_scan_client(scan)
    try:
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft", pipeline):
            _run_sandwiched(lambda: runner.run_transcription_job(job_id))
    finally:
        set_scan_client(None)
    return gcs, pipeline


def test_step0_compiles_a_missing_pdf_from_the_frozen_snapshot_then_transcribes(ids):
    cap = _seed(ids, state="pending", pending_name="ש", job_status="queued")
    scan = _FakeScan()
    gcs, pipeline = _run_job(cap["job"], scan=scan, object_size=None)
    (snapshot, version, out_uri, timeout_s), = scan.calls
    assert snapshot == [{"page_id": "p"}] and version == "scan-v1.0"
    assert out_uri.endswith(cap["path"])                     # the deterministic path (SCN-4)
    assert 0 < timeout_s <= 300
    gcs.download_bytes.assert_called_once_with(cap["path"])
    assert pipeline.await_count == 1
    assert asyncio.run(_load_job_row(str(cap["job"])))["status"] == "completed"


def test_step0_skips_when_the_pdf_is_already_there(ids):
    """A redelivered or retried job after a compile that landed (SCN-4)."""
    cap = _seed(ids, state="pending", pending_name="ש", job_status="queued")
    scan = _FakeScan()
    _run_job(cap["job"], scan=scan, object_size=4321)
    assert scan.calls == []
    assert asyncio.run(_load_job_row(str(cap["job"])))["status"] == "completed"


def test_step0_refusal_fails_the_job_retryably_and_never_transcribes(ids):
    """SCN-11: a missing raw photo → no partial PDF, a failed (retryable) job."""
    from app.services.capture.scan_client import ScanServiceError

    cap = _seed(ids, state="pending", pending_name="ש", job_status="queued")
    _, pipeline = _run_job(cap["job"], scan=_FakeScan(ScanServiceError("raw_missing", status=422)),
                           object_size=None)
    row = asyncio.run(_load_job_row(str(cap["job"])))
    assert row["status"] == "failed" and "raw_missing" in row["error"]
    assert row["net_verdict"] is None                        # not a network fact
    assert pipeline.await_count == 0
