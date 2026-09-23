"""
Tenant isolation of STUDENT ASSIGNMENT — every path that writes `student_id`
onto a transcription or a graded test refuses another teacher's student.

Why this file exists (student-profile PR, Part A item 3). The profile's LST-5
note implied that a graded test owned by one teacher could reference another
teacher's student, so every writer was audited. All of them check:

  path                                    ownership of the student
  POST /transcriptions/grade              get_owned_or_404  — pinned by
                                          test_transcription_endpoints::test_15_…
  PATCH /transcriptions/{id}/review       get_owned_or_404  — pinned by
                                          test_transcription_review::test_review_cross_tenant_student_404
  POST /batches/{id}/accept/{t}           get_owned_or_404  — pinned HERE
  POST /batches/{id}/accept_clean         get_owned_or_404  — pinned HERE
  auto-match (batch_triage.match_student) roster is `Student.user_id == user_id`
  inline create (StudentPicker)           POST /classroom/students, user_id = current_user
  regrade / manual_edit / retry           extend_chain copies from an OWNED row

The two batch accepts were the only writers with no test saying so. Production
was read on 2026-09-22 and carries ZERO rows violating tenant or student
consistency on any edge; migration 032 (Part B, AM-B4) makes the database
enforce it structurally. Until then these tests are the guarantee.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


@asynccontextmanager
async def _session():
    from app.database import AsyncSessionLocal, engine

    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            yield db
    finally:
        await engine.dispose(close=False)


def _clean_draft_json(student_name: str) -> dict:
    """A draft `accept_clean` will call clean: no annotations, confident
    answers, and a name suggestion that matches the teacher's own roster."""
    from app.schemas.transcription import TranscriptionDraft, TranscriptionDraftAnswer

    return TranscriptionDraft(
        student_name_suggestion=student_name,
        page_count=1,
        answers=[TranscriptionDraftAnswer(
            question_number=1, sub_question_id=None, answer_text="x = 1",
            confidence=0.95, page_numbers=[1])],
        annotations=[],
    ).model_dump(mode="json")


async def _batch_with_transcription(user_id: str, rubric_id: str, draft_json: dict) -> tuple[str, str]:
    from app.models.grading import GradingBatch
    from app.models.transcription import Transcription

    async with _session() as db:
        batch = GradingBatch(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            rubric_contract_version="test-v1", name="tenant isolation",
            status="in_progress", test_count=1, started_at=datetime.now(timezone.utc))
        db.add(batch)
        await db.flush()
        t = Transcription(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id), batch_id=batch.id,
            gcs_uri="gs://stub/stub.pdf", gcs_bucket="stub", gcs_object_path="stub.pdf",
            filename="stub.pdf", draft_json=draft_json, status="transcribed")
        db.add(t)
        await db.commit()
        return str(batch.id), str(t.id)


async def _state(transcription_id: str) -> tuple[str, object, int]:
    async with _session() as db:
        row = (await db.execute(text(
            "SELECT status, student_id FROM transcriptions WHERE id = :t"),
            {"t": uuid.UUID(transcription_id)})).one()
        graded = await db.scalar(text(
            "SELECT COUNT(*) FROM graded_tests WHERE transcription_id = :t"),
            {"t": uuid.UUID(transcription_id)})
        return row.status, row.student_id, int(graded)


def _student(client, headers, name: str) -> str:
    resp = client.post("/api/v0/classroom/students", json={"full_name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.integration
def test_accept_one_refuses_another_teachers_student_and_writes_nothing(
        client, headers_a, headers_b, user_a, rubric_a):
    name = f"בידוד {uuid.uuid4().hex[:6]}"
    batch_id, t_id = asyncio.run(_batch_with_transcription(
        user_a["user"]["id"], rubric_a["rubric_id"], _clean_draft_json(name)))
    foreign = _student(client, headers_b, name)

    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()) as enqueue:
        resp = client.post(
            f"/api/v0/batches/{batch_id}/accept/{t_id}",
            json={"student_id": foreign,
                  "answers": [{"question_number": 1, "sub_question_id": None, "answer_text": "x = 1"}]},
            headers=headers_a)

    assert resp.status_code == 404, resp.text
    # Nothing moved: the scan is still hers to assign, no grade exists, and no
    # grading task was queued for a row that must not exist.
    assert asyncio.run(_state(t_id)) == ("transcribed", None, 0)
    enqueue.assert_not_called()


@pytest.mark.integration
def test_accept_clean_refuses_another_teachers_student_and_writes_nothing(
        client, headers_a, headers_b, user_a, rubric_a):
    """The item must reach the ownership check to prove it: the draft's name
    matches a student in A's OWN roster, so the server-side clean verdict
    passes, and only then is the posted (foreign) id looked up."""
    name = f"בידוד {uuid.uuid4().hex[:6]}"
    _student(client, headers_a, name)          # makes the verdict clean for A
    batch_id, t_id = asyncio.run(_batch_with_transcription(
        user_a["user"]["id"], rubric_a["rubric_id"], _clean_draft_json(name)))
    foreign = _student(client, headers_b, name)

    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()) as enqueue:
        resp = client.post(
            f"/api/v0/batches/{batch_id}/accept_clean",
            json={"items": [{"transcription_id": t_id, "student_id": foreign}]},
            headers=headers_a)

    assert resp.status_code == 404, resp.text
    assert asyncio.run(_state(t_id)) == ("transcribed", None, 0)
    enqueue.assert_not_called()
