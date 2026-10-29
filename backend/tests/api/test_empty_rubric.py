"""
The 0-question rubric incident (2026-10-25..29) — every door it walked through, closed.

A frontend stale closure saved the review page's FIRST-RENDER state, the compiler
accepted it (every point-sum invariant is vacuous on an empty rubric), and three
teachers got a rubric that looked saved. Every exam transcribed against it failed
in ~1 s inside the spec parser, net_diag blamed the network, and the screen told
her to try again — which could never succeed.

Pinned here, end to end against the real endpoints:
  * INV-7 refuses the exact draft production saved (the save door);
  * a batch cannot be created, fed, or retried against a 0-question rubric
    compiled before INV-7 (the queueing doors), and says WHY in Hebrew;
  * the batch detail carries `rubric_has_questions` so the screen can name the
    rubric and stop offering a retry;
  * the runner fails such a job up front — no download, no model call, no
    network verdict.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.deps import EMPTY_RUBRIC_DETAIL_HE
from tests.api.test_batch_grading import (
    _delete_batch_cascade,
    _fresh_loop_session,
    _insert_batch_row,
    _insert_transcription_job,
    _load_job_row,
    _run_sandwiched,
)

pytestmark = pytest.mark.integration

#: The draft_json production stored for rubric d660a143 (2026-10-29), minus its
#: random rubric_id: the page's first-render state, verbatim.
INCIDENT_DRAFT = {
    "name": None,
    "subject": "computer_science",
    "metadata": {},
    "annotations": [],
    "description": None,
    "rubric_name": "מחוון",
    "total_points": "0",
    "schema_version": "2.0",
    "approach_classes": [],
    "document_context": None,
    "selection_groups": [],
    "extraction_metadata": {},
    "pedagogical_mistakes": [],
    "programming_language": None,
    "questions": [],
}


async def _insert_legacy_empty_rubric(user_id: str) -> str:
    """A 0-question rubric as production holds three of them: compiled BEFORE
    INV-7, so it can only be made by writing the row directly."""
    from app.models.grading import Rubric
    from app.schemas.ontology_types import GradingRubricContract, NumericPolicy

    version = str(uuid4())
    # Through the real type, so the row parses exactly as production's three do.
    contract = GradingRubricContract(
        rubric_id=str(uuid4()), contract_version=version, subject="computer_science",
        numeric_policy=NumericPolicy(), questions=[], total_points=0,
    ).model_dump(mode="json")
    async with _fresh_loop_session() as db:
        r = Rubric(
            name="מחוון",
            user_id=uuid.UUID(user_id),
            subject="computer_science",
            draft_json=INCIDENT_DRAFT,
            contract_json=contract,
            contract_version=version,
            needs_recompilation=False,
            total_points=0,
        )
        db.add(r)
        await db.commit()
        return str(r.id)


async def _delete_rubric(rubric_id: str) -> None:
    from sqlalchemy import text

    async with _fresh_loop_session() as db:
        await db.execute(text("DELETE FROM grading_plans WHERE rubric_id = :r"),
                         {"r": uuid.UUID(rubric_id)})
        await db.execute(text("DELETE FROM rubrics WHERE id = :r"),
                         {"r": uuid.UUID(rubric_id)})
        await db.commit()


@pytest.fixture
def empty_rubric_id(user_a):
    rid = asyncio.run(_insert_legacy_empty_rubric(user_a["user"]["id"]))
    yield rid
    asyncio.run(_delete_rubric(rid))


def test_save_refuses_the_incident_draft_with_INV_7(client, headers_a):
    resp = client.post(
        "/api/v0/rubrics/save_ontology_draft",
        json={"name": "מחוון", "draft": INCIDENT_DRAFT, "acknowledged_warning_ids": []},
        headers=headers_a,
    )
    assert resp.status_code == 400, resp.text
    errors = resp.json()["detail"]["errors"]
    assert any(e.get("invariant") == "INV-7" for e in errors), errors


def test_create_batch_refuses_an_empty_rubric(client, headers_a, empty_rubric_id):
    resp = client.post("/api/v0/batches",
                       json={"rubric_id": empty_rubric_id, "expected_test_count": 4},
                       headers=headers_a)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == EMPTY_RUBRIC_DETAIL_HE


def test_append_and_retry_refuse_on_a_batch_pinned_to_an_empty_rubric(
        client, user_a, headers_a, empty_rubric_id):
    user_id = user_a["user"]["id"]
    batch_id = asyncio.run(_insert_batch_row(user_id, empty_rubric_id, test_count=1))
    failed_id = asyncio.run(_insert_transcription_job(
        user_id, empty_rubric_id, batch_id, status="failed"))
    try:
        resp = client.post(
            f"/api/v0/batches/{batch_id}/files",
            files={"file": ("exam.pdf", b"%PDF-1.4 stub", "application/pdf")},
            data={"client_file_id": str(uuid4())},
            headers=headers_a,
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == EMPTY_RUBRIC_DETAIL_HE

        enqueue = AsyncMock()
        with patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
            resp = client.post(f"/api/v0/batches/{batch_id}/jobs/{failed_id}/retry",
                               headers=headers_a)
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == EMPTY_RUBRIC_DETAIL_HE
        enqueue.assert_not_awaited()
        assert asyncio.run(_load_job_row(failed_id))["status"] == "failed"
    finally:
        asyncio.run(_delete_batch_cascade(batch_id))


def test_detail_says_whether_the_rubric_can_read_anything(
        client, user_a, headers_a, rubric_a, empty_rubric_id):
    user_id = user_a["user"]["id"]
    empty_batch = asyncio.run(_insert_batch_row(user_id, empty_rubric_id, test_count=1))
    good_batch = asyncio.run(_insert_batch_row(user_id, rubric_a["rubric_id"], test_count=1))
    try:
        resp = client.get(f"/api/v0/batches/{empty_batch}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["rubric_has_questions"] is False

        resp = client.get(f"/api/v0/batches/{good_batch}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["rubric_has_questions"] is True
    finally:
        asyncio.run(_delete_batch_cascade(empty_batch))
        asyncio.run(_delete_batch_cascade(good_batch))


def test_runner_fails_an_empty_rubric_job_up_front_with_no_network_verdict(
        user_a, empty_rubric_id):
    from app.services import transcription_job_runner as runner

    user_id = user_a["user"]["id"]
    batch_id = asyncio.run(_insert_batch_row(user_id, empty_rubric_id, test_count=1))
    job_id = asyncio.run(_insert_transcription_job(user_id, empty_rubric_id, batch_id))
    gcs = MagicMock()
    pipeline = AsyncMock()
    diagnose = AsyncMock(return_value="internet-ok")
    try:
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft", pipeline), \
             patch("app.services.net_diag.diagnose_transport_failure", diagnose):
            ran = _run_sandwiched(lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran is True

        row = asyncio.run(_load_job_row(job_id))
        assert row["status"] == "failed" and row["finished"]
        assert row["error"].startswith("RubricUnusable:")
        assert "no questions" in row["error"]
        assert row["net_verdict"] is None
        gcs.download_bytes.assert_not_called()
        pipeline.assert_not_awaited()
        diagnose.assert_not_awaited()
    finally:
        asyncio.run(_delete_batch_cascade(batch_id))
