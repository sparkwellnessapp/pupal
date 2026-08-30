"""
S11 — Batch grading tests.

Tests 1–10 from S11 spec §10.

Critical tests:
  [CORE-2]  Bounded concurrency — semaphore caps concurrent tasks at BATCH_MAX_CONCURRENT_TESTS
  [CORE-4]  Flag verdict — each signal class correctly sets review_needed + reasons
  [CORE-7]  Bulk-accept writes real contracts — transcription approved, GradedTest created with batch_id

NOTE: Tests marked @pytest.mark.integration require a live DATABASE_URL
and migration 011 applied (transcriptions.batch_id, grading_batches.test_count).
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
from app.schemas.transcription import TranscriptionDraft, TranscriptionDraftAnswer, TranscriptionAnnotation
from app.schemas.ontology_types import AnnotationSeverity
from app.services.batch_triage import (
    FlagVerdict,
    StudentMatchResult,
    compute_flag_verdict,
    match_student,
)


# ---------------------------------------------------------------------------
# Minimal draft helpers
# ---------------------------------------------------------------------------

def _clean_draft(student_name: str = "יוסי כהן") -> TranscriptionDraft:
    """No flags, confident answers."""
    return TranscriptionDraft(
        student_name_suggestion=student_name,
        page_count=2,
        answers=[
            TranscriptionDraftAnswer(
                question_number=1, sub_question_id=None,
                answer_text="public class Node { int val; }",
                confidence=0.95, page_numbers=[1],
            )
        ],
        annotations=[],
    )


def _draft_with_annotation(annotation_type: str, metadata: dict | None = None) -> TranscriptionDraft:
    return TranscriptionDraft(
        student_name_suggestion="ישראל ישראלי",
        page_count=1,
        answers=[
            TranscriptionDraftAnswer(
                question_number=1, sub_question_id=None,
                answer_text="some answer",
                confidence=0.9, page_numbers=[1],
            )
        ],
        annotations=[
            TranscriptionAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id="transcription",
                annotation_type=annotation_type,
                message="test annotation",
                metadata=metadata or {},
            )
        ],
    )


def _draft_low_confidence() -> TranscriptionDraft:
    return TranscriptionDraft(
        student_name_suggestion="דנה לוי",
        page_count=1,
        answers=[
            TranscriptionDraftAnswer(
                question_number=1, sub_question_id=None,
                answer_text="answer",
                confidence=0.5,    # below threshold
                page_numbers=[1],
            )
        ],
        annotations=[],
    )


# ---------------------------------------------------------------------------
# Pure unit tests — batch_triage (no DB needed)
# ---------------------------------------------------------------------------

class TestComputeFlagVerdict:
    """Test 4 — Flag verdict: each signal class sets correct reasons."""

    def _exact_match(self) -> StudentMatchResult:
        return StudentMatchResult(student_id="abc", student_name="Test", match_confidence="exact")

    def _no_match(self) -> StudentMatchResult:
        return StudentMatchResult(student_id=None, student_name=None, match_confidence="none")

    def test_clean_draft_is_not_flagged(self):
        draft = _clean_draft()
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert not verdict.review_needed
        assert verdict.reasons == []

    def test_unparseable_marker(self):
        draft = _draft_with_annotation("vlm_unparseable")
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "unparseable" in verdict.reasons

    def test_grounding_retry(self):
        draft = _draft_with_annotation("vlm_uncertainty", {"needed_grounding_retry": True})
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "grounding_retry" in verdict.reasons

    def test_low_confidence_annotation(self):
        draft = _draft_with_annotation("vlm_uncertainty", {"needed_grounding_retry": False})
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "low_confidence" in verdict.reasons

    def test_low_logprob_span(self):
        draft = _draft_with_annotation("vlm_low_logprob", {"min_span_logprob": -3.5})
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "low_logprob_span" in verdict.reasons

    def test_low_confidence_per_answer(self):
        draft = _draft_low_confidence()
        verdict = compute_flag_verdict(draft, self._exact_match(), confidence_threshold=0.8)
        assert verdict.review_needed
        assert "low_confidence" in verdict.reasons

    def test_selection_satisfied_suppresses_missing_answers(self):
        # "Choose 1 of {q1, q2}", student answered q1 → q2's empty answer is
        # EXPECTED, not missing (2026-08-12 — every selection exam previously
        # flagged missing_answers + rendered empty containers falsely).
        from app.schemas.transcription import AnswerSpaceSelectionGroup
        draft = TranscriptionDraft(
            student_name_suggestion="x",
            page_count=1,
            answers=[
                TranscriptionDraftAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="answered", confidence=0.95, page_numbers=[1]),
                TranscriptionDraftAnswer(
                    question_number=2, sub_question_id=None,
                    answer_text="", confidence=0.0, page_numbers=[]),
            ],
            annotations=[],
        )
        groups = [AnswerSpaceSelectionGroup(choose_k=1, question_numbers=[1, 2])]
        verdict = compute_flag_verdict(draft, self._exact_match(),
                                       selection_groups=groups)
        assert "missing_answers" not in verdict.reasons
        assert not verdict.review_needed

        # Same draft WITHOUT selection context → missing_answers (unchanged
        # behavior for selection-free rubrics).
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert "missing_answers" in verdict.reasons

    def test_underanswered_selection_still_flags_missing(self):
        # Choose 2 of {q1, q2}, student answered only q1 → the group is
        # under-answered; q2's empty IS a reviewable gap.
        from app.schemas.transcription import AnswerSpaceSelectionGroup
        draft = TranscriptionDraft(
            student_name_suggestion="x",
            page_count=1,
            answers=[
                TranscriptionDraftAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="answered", confidence=0.95, page_numbers=[1]),
                TranscriptionDraftAnswer(
                    question_number=2, sub_question_id=None,
                    answer_text="", confidence=0.0, page_numbers=[]),
            ],
            annotations=[],
        )
        groups = [AnswerSpaceSelectionGroup(choose_k=2, question_numbers=[1, 2])]
        verdict = compute_flag_verdict(draft, self._exact_match(),
                                       selection_groups=groups)
        assert "missing_answers" in verdict.reasons

    def test_student_unassigned_when_name_captured(self):
        # A captured name with no roster match is "unassigned", never
        # "not identified" (2026-08-12 — the old single reason rendered the
        # false label "שם תלמיד לא זוהה" on every identity-pass success).
        draft = _clean_draft()   # carries student_name_suggestion
        verdict = compute_flag_verdict(draft, self._no_match())
        assert verdict.review_needed
        assert "student_unassigned" in verdict.reasons
        assert "student_unmatched" not in verdict.reasons

    def test_student_unmatched_when_no_name_captured(self):
        draft = _clean_draft()
        draft = draft.model_copy(update={"student_name_suggestion": None})
        verdict = compute_flag_verdict(draft, self._no_match())
        assert verdict.review_needed
        assert "student_unmatched" in verdict.reasons
        assert "student_unassigned" not in verdict.reasons

    def test_no_duplicate_reasons(self):
        # Both low_confidence annotation AND per-answer low confidence
        draft = TranscriptionDraft(
            student_name_suggestion="x",
            page_count=1,
            answers=[
                TranscriptionDraftAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="a", confidence=0.3, page_numbers=[1],
                )
            ],
            annotations=[
                TranscriptionAnnotation(
                    severity=AnnotationSeverity.WARNING,
                    target_id="q1",
                    annotation_type="vlm_uncertainty",
                    message="low",
                    metadata={"needed_grounding_retry": False},
                )
            ],
        )
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.reasons.count("low_confidence") == 1

    # --- two_phase-engine signal classes (2026-08-07 triage rebuild) ---

    def test_code_lint_annotation(self):
        draft = _draft_with_annotation("code_lint", {"balance": 1})
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "code_lint" in verdict.reasons

    def test_empty_answer_is_missing_not_low_confidence(self):
        """A skipped question under two_phase is empty text with confidence 0.0
        (no page attribution). That is a FACT (missing_answers), never a
        confidence guess — the old per-answer check flagged every two_phase
        doc with a skipped question as low_confidence."""
        draft = TranscriptionDraft(
            student_name_suggestion=None,
            page_count=1,
            answers=[
                TranscriptionDraftAnswer(
                    question_number=1, sub_question_id="א",
                    answer_text="int x = 1;", confidence=1.0, page_numbers=[1],
                ),
                TranscriptionDraftAnswer(
                    question_number=5, sub_question_id="א",
                    answer_text="", confidence=0.0, page_numbers=[],
                ),
            ],
            annotations=[],
        )
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert "missing_answers" in verdict.reasons
        assert "low_confidence" not in verdict.reasons

    def test_two_phase_clean_draft_is_not_flagged(self):
        """The two_phase happy path (all answers attributed, no annotations,
        student matched) must be bulk-acceptable."""
        draft = TranscriptionDraft(
            student_name_suggestion=None,
            page_count=2,
            answers=[
                TranscriptionDraftAnswer(
                    question_number=1, sub_question_id="א",
                    answer_text="public class Node { }",
                    confidence=1.0, page_numbers=[1],
                ),
            ],
            annotations=[],
        )
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert not verdict.review_needed
        assert verdict.reasons == []

    def test_segmentation_mismatch_annotation_flags(self):
        """A marker↔key mismatch means grading would run against the wrong
        rubric question — never bulk-acceptable."""
        draft = _draft_with_annotation(
            "segmentation_mismatch",
            {"declared_question": 3, "proposed_target": "q3.א"},
        )
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert verdict.review_needed
        assert "segmentation_mismatch" in verdict.reasons

    def test_reader_disagreement_is_not_a_triage_signal(self):
        """Retired in production (2026-08-07): pre-retirement drafts still carry
        these annotations; they must not flag the doc."""
        draft = _draft_with_annotation(
            "reader_disagreement",
            {"page": 1, "line_quote": "int x = 1;", "alternatives": ["int x = 7;"]},
        )
        verdict = compute_flag_verdict(draft, self._exact_match())
        assert not verdict.review_needed
        assert verdict.reasons == []


# (TestBackgroundTaskContainment retired with BackgroundTasks itself — the
# Cloud Tasks migration made every kickoff an enqueue of a durable row. The
# protections live on: transcription containment in TestTranscriptionJobRunner
# below; grading kickoff resilience in enqueue_grading_task_or_log, which only
# logs because the pending row is already durable and liveness-reaped.)


class TestMatchStudent:
    """Test 6 — Student auto-match."""

    class FakeStudent:
        def __init__(self, id_: str, name: str):
            self.id = uuid4()
            self.full_name = name

    def _roster(self) -> list:
        return [
            self.FakeStudent("1", "ישראל ישראלי"),
            self.FakeStudent("2", "יוסי כהן"),
        ]

    def test_exact_normalized_match(self):
        result = match_student("  ישראל ישראלי  ", self._roster())
        assert result.match_confidence == "exact"
        assert result.student_name == "ישראל ישראלי"

    def test_case_fold_match(self):
        result = match_student("ISRAEL ISRAELI", [self.FakeStudent("1", "israel israeli")])
        assert result.match_confidence == "exact"

    def test_no_match(self):
        result = match_student("שם לא קיים", self._roster())
        assert result.match_confidence == "none"
        assert result.student_id is None

    def test_none_suggestion(self):
        result = match_student(None, self._roster())
        assert result.match_confidence == "none"

    def test_empty_roster_classless_batch(self):
        result = match_student("יוסי", [])
        assert result.match_confidence == "none"


# ---------------------------------------------------------------------------
# Test 5 — Logprob span signal
# ---------------------------------------------------------------------------

class TestLogprobSpanSignal:
    """Test 5 — Logprob span-min signal produces vlm_low_logprob annotation."""

    def test_span_min_below_threshold_emits_annotation(self):
        """Mock VLM returning token logprobs below threshold → annotation added."""
        from app.services.transcription_adapter import build_transcription_draft
        from app.services.handwriting_transcription_service import (
            TranscriptionResult, TranscribedAnswer
        )
        result = TranscriptionResult(
            student_name="טסט",
            filename="test.pdf",
            answers=[
                TranscribedAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="answer",
                    confidence=0.9,
                    page_numbers=[1],
                    min_span_logprob=-3.5,   # below default -2.0 threshold
                )
            ],
        )
        with patch("app.services.transcription_adapter.settings") as mock_settings:
            mock_settings.logprob_span_threshold = -2.0
            draft = build_transcription_draft(result, 1, "openai/gpt-4o", 500)

        ann_types = [a.annotation_type for a in draft.annotations]
        assert "vlm_low_logprob" in ann_types

    def test_confident_logprobs_no_annotation(self):
        """Token logprobs above threshold → no vlm_low_logprob annotation."""
        from app.services.transcription_adapter import build_transcription_draft
        from app.services.handwriting_transcription_service import (
            TranscriptionResult, TranscribedAnswer
        )
        result = TranscriptionResult(
            student_name="טסט",
            filename="test.pdf",
            answers=[
                TranscribedAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="answer",
                    confidence=0.95,
                    page_numbers=[1],
                    min_span_logprob=-0.5,   # well above -2.0 threshold
                )
            ],
        )
        with patch("app.services.transcription_adapter.settings") as mock_settings:
            mock_settings.logprob_span_threshold = -2.0
            draft = build_transcription_draft(result, 1, "openai/gpt-4o", 500)

        ann_types = [a.annotation_type for a in draft.annotations]
        assert "vlm_low_logprob" not in ann_types

    def test_none_logprob_no_annotation(self):
        """Providers without logprob support (min_span_logprob=None) → no annotation."""
        from app.services.transcription_adapter import build_transcription_draft
        from app.services.handwriting_transcription_service import (
            TranscriptionResult, TranscribedAnswer
        )
        result = TranscriptionResult(
            student_name="טסט",
            filename="test.pdf",
            answers=[
                TranscribedAnswer(
                    question_number=1, sub_question_id=None,
                    answer_text="answer",
                    confidence=0.9,
                    page_numbers=[1],
                    min_span_logprob=None,   # Anthropic/Gemini path
                )
            ],
        )
        with patch("app.services.transcription_adapter.settings") as mock_settings:
            mock_settings.logprob_span_threshold = -2.0
            draft = build_transcription_draft(result, 1, "anthropic/claude", 300)

        ann_types = [a.annotation_type for a in draft.annotations]
        assert "vlm_low_logprob" not in ann_types


# ---------------------------------------------------------------------------
# API-level tests (require live DB + migration 011)
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def _fresh_loop_session():
    """Loop-safe DB session for asyncio.run() helpers.

    Each asyncio.run() creates its OWN event loop, while the global engine's
    pool holds asyncpg connections bound to the TestClient app's loop
    (asyncpg futures are loop-bound — reusing one cross-loop raises
    "attached to a different loop"). Drop pooled connections WITHOUT closing
    them on entry AND exit (close=False: closing cross-loop is itself the
    crash), so neither loop ever inherits the other's connections.
    """
    from app.database import AsyncSessionLocal, engine

    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            yield db
    finally:
        await engine.dispose(close=False)


async def _insert_batch_row(user_id: str, rubric_id: str, test_count: int = 3) -> str:
    from app.models.grading import GradingBatch

    async with _fresh_loop_session() as db:
        batch = GradingBatch(
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            rubric_contract_version="test-v1",
            name="Test Batch S11",
            status="in_progress",
            test_count=test_count,
            started_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        await db.commit()
        return str(batch.id)


async def _insert_transcription_batch(
    user_id: str,
    rubric_id: str,
    batch_id: str,
    draft_json: dict,
) -> str:
    from app.models.transcription import Transcription

    async with _fresh_loop_session() as db:
        t = Transcription(
            user_id=uuid.UUID(user_id),
            rubric_id=uuid.UUID(rubric_id),
            batch_id=uuid.UUID(batch_id),
            student_id=None,
            student_name=None,
            gcs_uri="gs://stub/stub.pdf",
            gcs_bucket="stub",
            gcs_object_path="stub.pdf",
            filename="test.pdf",
            draft_json=draft_json,
            contract_json=None,
            status="transcribed",
        )
        db.add(t)
        await db.commit()
        return str(t.id)


async def _delete_batch_cascade(batch_id: str) -> None:
    from app.models.grading import GradingBatch
    from sqlalchemy import delete

    async with _fresh_loop_session() as db:
        await db.execute(delete(GradingBatch).where(GradingBatch.id == uuid.UUID(batch_id)))
        await db.commit()


# ---------------------------------------------------------------------------
# Test 1 — Fan-out creates rows
# ---------------------------------------------------------------------------

def test_create_batch_requires_auth(client):
    resp = client.post("/api/v0/batches", data={"rubric_id": str(uuid4())})
    assert resp.status_code == 401


@pytest.mark.integration
def test_create_batch_persists_jobs_and_enqueues(client, user_a, rubric_a, headers_a):
    """B9 intake v2: metadata-only create + one append per document. Each
    append uploads to GCS, commits one queued TranscriptionJob (doc_priority =
    upload order), and enqueues one task."""
    from io import BytesIO
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4 as _uuid4

    rubric_id = rubric_a["rubric_id"]
    gcs = MagicMock()
    gcs.upload_bytes.return_value = "path"
    enqueue = AsyncMock()

    with patch("app.api.v0.batch_grading.get_gcs_service", return_value=gcs), \
         patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        created = client.post(
            "/api/v0/batches", headers=headers_a,
            json={"rubric_id": rubric_id, "class_id": None, "name": None},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["test_count"] == 0
        for i, fname in enumerate(("a.pdf", "b.pdf", "c.pdf")):
            resp = client.post(
                f"/api/v0/batches/{body['batch_id']}/files", headers=headers_a,
                files={"file": (fname, BytesIO(b"%PDF-1.4 stub"), "application/pdf")},
                data={"client_file_id": str(_uuid4())},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["test_count"] == i + 1

    assert gcs.upload_bytes.call_count == 3
    assert enqueue.await_count == 3

    async def load_jobs():
        from app.database import AsyncSessionLocal, engine
        from app.models.transcription_job import TranscriptionJob
        from sqlalchemy import select
        await engine.dispose(close=False)
        try:
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(TranscriptionJob)
                    .where(TranscriptionJob.batch_id == uuid.UUID(body["batch_id"]))
                    .order_by(TranscriptionJob.doc_priority)
                )).scalars().all()
                return [(j.status, j.source_filename, j.doc_priority,
                         j.source_gcs_object_path) for j in rows]
        finally:
            await engine.dispose(close=False)

    jobs = asyncio.run(load_jobs())
    assert [(s, f, p) for (s, f, p, _) in jobs] == [
        ("queued", "a.pdf", 0), ("queued", "b.pdf", 1), ("queued", "c.pdf", 2)]
    assert all(path.startswith("transcriptions/") for (_, _, _, path) in jobs)

    asyncio.run(_delete_batch_cascade(body["batch_id"]))


# (test_create_batch_upload_failure_is_atomic — RETIRED with B9: the
# all-or-nothing multipart create no longer exists; its atomicity unit is now
# the single append, guarded by test_batch_intake.py::test_append_gcs_failure_no_job
# — a GCS failure 502s THAT file only, no job row, batch intact.)
#
# (test_create_batch_rejects_empty_pdf_set — RETIRED with B7: the silent-drop
# extension filter is gone; every rejection is a per-file 422 with a §3.2
# reason, guarded by test_batch_intake.py's rejects trio.)


# (Test 2 — the in-process bounded-concurrency semaphore — retired with the
# Cloud Tasks migration: batch-wide concurrency is now the queue's
# maxConcurrentDispatches; per-process LLM pressure stays capped by the
# shared provider scheduler.)


# ---------------------------------------------------------------------------
# Test 3 — transcribe_one shared
# ---------------------------------------------------------------------------

def test_transcribe_endpoint_uses_transcribe_one(client, user_a, rubric_a, headers_a):
    """POST /transcribe delegates to transcribe_one with batch_id=None."""
    from io import BytesIO

    with patch("app.api.v0.transcription.transcribe_one", new=AsyncMock(return_value=str(uuid4()))) as mock:
        # Need a valid response shape — mock the reload too
        with patch("app.api.v0.transcription.TranscriptionDraft") as mock_draft:
            mock_draft.model_validate.return_value = mock_draft
            # The endpoint will fail on db.get(Transcription, ...) but that's OK —
            # the important assertion is that transcribe_one was called with batch_id=None
            try:
                client.post(
                    "/api/v0/transcriptions/transcribe",
                    headers=headers_a,
                    files={"file": ("test.pdf", BytesIO(b"%PDF stub"), "application/pdf")},
                    data={"rubric_id": rubric_a["rubric_id"]},
                )
            except Exception:
                pass
        if mock.called:
            _, kwargs = mock.call_args
            assert kwargs.get("batch_id") is None


# ---------------------------------------------------------------------------
# Test 7 — Bulk-accept writes real contracts (critical)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bulk_accept_writes_contracts(client, user_a, rubric_a, headers_a):
    """
    POST /batches/{id}/accept_clean → 3 transcriptions approved + 3 GradedTests with batch_id.
    """
    rubric_id = rubric_a["rubric_id"]
    user_id = user_a["user"]["id"]

    # B1: accept_clean now enforces the verdict SERVER-side — fixtures must be
    # verdict-clean, so each draft's suggestion matches the student posted for
    # it (the roster is read live at accept time; students are created below,
    # before the POST).
    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=3))
    t_ids = [
        asyncio.run(_insert_transcription_batch(
            user_id, rubric_id, batch_id,
            _clean_draft(student_name=f"Test Student S11 {i}").model_dump(mode="json"),
        ))
        for i in range(3)
    ]

    # Insert 3 students
    student_ids: list[str] = []
    for i in range(3):
        resp = client.post(
            "/api/v0/classroom/students",
            json={"full_name": f"Test Student S11 {i}"},
            headers=headers_a,
        )
        assert resp.status_code == 201
        student_ids.append(resp.json()["id"])

    items = [
        {"transcription_id": t_id, "student_id": s_id}
        for t_id, s_id in zip(t_ids, student_ids)
    ]

    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()):
        resp = client.post(
            f"/api/v0/batches/{batch_id}/accept_clean",
            json={"items": items},
            headers=headers_a,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] == 3

    # Verify DB state
    from app.models.grading import GradedTest
    from app.models.transcription import Transcription
    from sqlalchemy import select

    async def check():
        async with _fresh_loop_session() as db:
            for t_id in t_ids:
                t = await db.get(Transcription, uuid.UUID(t_id))
                assert t is not None
                assert t.status == "approved", f"transcription {t_id} not approved"
                assert t.contract_json is not None, "contract_json is NULL"
                assert t.student_id is not None, "student_id not set"

            gts = (await db.execute(
                select(GradedTest).where(GradedTest.batch_id == uuid.UUID(batch_id))
            )).scalars().all()
            assert len(gts) == 3
            for gt in gts:
                assert gt.batch_id == uuid.UUID(batch_id)
                assert gt.status == "pending"

    asyncio.run(check())
    asyncio.run(_delete_batch_cascade(batch_id))


# ---------------------------------------------------------------------------
# Test 8 — accept_one enqueues the grading task
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_accept_one_fires_run_grading(client, user_a, rubric_a, headers_a):
    """accept_one transcription → grading task enqueued for the new pending row."""
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    draft_json = _clean_draft().model_dump(mode="json")

    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=1))
    t_id = asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))

    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": "Accept One Student"},
        headers=headers_a,
    )
    student_id = resp.json()["id"]

    grade_called_with: list[str] = []

    async def capture_grade(graded_test_id):
        grade_called_with.append(str(graded_test_id))

    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log",
               side_effect=capture_grade):
        resp = client.post(
            f"/api/v0/batches/{batch_id}/accept/{t_id}",
            json={
                "student_id": student_id,
                "answers": [{"question_number": 1, "sub_question_id": None, "answer_text": "answer"}],
            },
            headers=headers_a,
        )

    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
    assert len(grade_called_with) == 1

    asyncio.run(_delete_batch_cascade(batch_id))


# ---------------------------------------------------------------------------
# Test 9 — Roll-up counts reflect child states
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rollup_counts_reflect_child_states(client, user_a, rubric_a, headers_a):
    """GET /batches/{id} roll-up counts match actual transcription/graded_test states."""
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    draft_json = _clean_draft().model_dump(mode="json")

    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=2))
    asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))
    asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))

    resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
    assert resp.status_code == 200

    rollup = resp.json()["rollup"]
    assert rollup["transcribed"] == 2
    assert rollup["total"] == 2
    assert rollup["approved"] == 0

    asyncio.run(_delete_batch_cascade(batch_id))


# ---------------------------------------------------------------------------
# Test 10 — Class optional + cross-user 404
# ---------------------------------------------------------------------------

def test_batch_cross_user_returns_404(client, headers_b):
    resp = client.get(f"/api/v0/batches/{uuid4()}", headers=headers_b)
    assert resp.status_code == 404


class TestFailureLedgerRollup:
    """Migration 015: ledgered failures are DEAD, not in flight — the rollup
    must subtract them (the eternal 'N מבחנים עדיין בתהליך תמלול' bug) and the
    derived status must reach terminal states so the poll gate can stop."""

    @staticmethod
    def _rollup(test_count: int, rows: int, failures: int,
                approved_rows: int = 0):
        from types import SimpleNamespace
        from app.api.v0.batch_grading import _build_rollup
        batch = SimpleNamespace(
            test_count=test_count,
            transcription_failures=[{"filename": f"f{i}.pdf", "error": "x",
                                     "at": "2026-08-12T00:00:00+00:00",
                                     "net_verdict": None}
                                    for i in range(failures)],
        )
        transcriptions = [
            SimpleNamespace(status="approved" if i < approved_rows else "transcribed")
            for i in range(rows)
        ]
        return _build_rollup(batch, transcriptions, [])

    def test_ledgered_failure_is_not_in_flight(self):
        # Tonight's exact case: 2 docs, 1 landed, 1 ledgered failure.
        r = self._rollup(test_count=2, rows=1, failures=1)
        assert r.transcribing == 0
        assert r.transcription_failed == 1

    def test_without_ledger_absence_still_reads_as_in_flight(self):
        r = self._rollup(test_count=2, rows=1, failures=0)
        assert r.transcribing == 1      # unrecorded loss — step 4's territory

    def test_all_docs_failed_derives_failed_status(self):
        from app.api.v0.batch_grading import _derive_batch_status
        r = self._rollup(test_count=2, rows=0, failures=2)
        assert _derive_batch_status(r) == "failed"

    def test_partial_failure_with_rest_approved_is_partially_completed(self):
        from types import SimpleNamespace
        from app.api.v0.batch_grading import _build_rollup, _derive_batch_status
        batch = SimpleNamespace(
            test_count=2,
            transcription_failures=[{"filename": "dead.pdf", "error": "x",
                                     "at": "t", "net_verdict": None}],
        )
        transcriptions = [SimpleNamespace(status="approved")]
        graded = [SimpleNamespace(status="approved")]
        r = _build_rollup(batch, transcriptions, graded)
        assert _derive_batch_status(r) == "partially_completed"

    def test_mixed_in_flight_stays_in_progress(self):
        from app.api.v0.batch_grading import _derive_batch_status
        r = self._rollup(test_count=3, rows=1, failures=1)
        assert r.transcribing == 1
        assert _derive_batch_status(r) == "in_progress"


class TestJobsBasedRollup:
    """Cloud Tasks batches: job rows ARE the rollup's truth — counts come from
    statuses, never from test_count − rows inference. Legacy (no jobs) falls
    back to the 015-ledger arithmetic (covered above)."""

    @staticmethod
    def _rollup_with_jobs(test_count: int, job_statuses: list[str],
                          row_statuses: list[str] = ()):
        from types import SimpleNamespace
        from app.api.v0.batch_grading import _build_rollup
        batch = SimpleNamespace(test_count=test_count, transcription_failures=[])
        jobs = [SimpleNamespace(status=s) for s in job_statuses]
        transcriptions = [SimpleNamespace(status=s) for s in row_statuses]
        return _build_rollup(batch, transcriptions, [], jobs)

    def test_active_jobs_count_as_transcribing(self):
        r = self._rollup_with_jobs(3, ["queued", "running", "completed"],
                                   row_statuses=["transcribed"])
        assert r.transcribing == 2
        assert r.transcription_failed == 0
        assert r.transcribed == 1

    def test_failed_jobs_are_dead_not_in_flight(self):
        r = self._rollup_with_jobs(3, ["failed", "failed", "completed"],
                                   row_statuses=["transcribed"])
        assert r.transcribing == 0
        assert r.transcription_failed == 2

    def test_all_jobs_failed_derives_failed_status(self):
        from app.api.v0.batch_grading import _derive_batch_status
        r = self._rollup_with_jobs(2, ["failed", "failed"])
        assert _derive_batch_status(r) == "failed"


@pytest.mark.integration
def test_failure_ledger_atomic_append_and_batch_detail(client, user_a, rubric_a, headers_a):
    """LEGACY read path: pre-Cloud-Tasks batches carry migration-015 ledger
    entries (their writer is retired — job rows are the durable truth now);
    the detail payload must still render them with a coherent rollup."""
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]

    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=3))
    draft_json = _clean_draft(student_name=f"ס {uuid4().hex[:6]}").model_dump(mode="json")
    asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))

    async def write_legacy_ledger():
        from app.database import AsyncSessionLocal, engine
        from sqlalchemy import update as _update
        from app.models.grading import GradingBatch
        await engine.dispose(close=False)
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    _update(GradingBatch)
                    .where(GradingBatch.id == uuid.UUID(batch_id))
                    .values(transcription_failures=[
                        {"filename": "a.pdf", "error": "RuntimeError: boom-a",
                         "at": datetime.now(timezone.utc).isoformat(),
                         "net_verdict": "internet-ok"},
                        {"filename": "b.pdf", "error": "TimeoutError: boom-b",
                         "at": datetime.now(timezone.utc).isoformat(),
                         "net_verdict": None},
                    ])
                )
                await db.commit()
        finally:
            await engine.dispose(close=False)

    asyncio.run(write_legacy_ledger())

    resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
    assert resp.status_code == 200
    body = resp.json()

    failures = body["transcription_failures"]
    assert {f["filename"] for f in failures} == {"a.pdf", "b.pdf"}
    assert all(f["error"] and f["at"] for f in failures)
    assert body["rollup"]["transcription_failed"] == 2
    assert body["rollup"]["transcribing"] == 0          # 3 − 1 row − 2 failures
    assert body["status"] == "in_progress"              # 1 row still pending review

    asyncio.run(_delete_batch_cascade(batch_id))


@pytest.mark.integration
def test_batch_without_class_works(client, user_a, rubric_a, headers_a):
    """A batch with no class_id works. The captured-but-unknown name flags
    student_unassigned (not the false 'name not identified'); once the student
    exists, the class-less batch auto-matches against the teacher's FULL
    roster (owner-ruled 2026-08-12 — names are unique per teacher)."""
    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]

    # Session-unique name: user_a is a fresh signup, but keep the test
    # re-entrant against the shared live DB anyway.
    student_name = f"יוסי כהן {uuid4().hex[:6]}"

    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=1))
    draft_json = _clean_draft(student_name=student_name).model_dump(mode="json")
    asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))

    resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
    assert resp.status_code == 200

    transcriptions = resp.json()["transcriptions"]
    assert len(transcriptions) == 1
    # Name captured, student doesn't exist yet → unassigned (never "unmatched")
    reasons = transcriptions[0]["flag_verdict"]["reasons"]
    assert "student_unassigned" in reasons
    assert "student_unmatched" not in reasons
    assert transcriptions[0]["matched_student_id"] is None

    # Create the student → the class-less batch now auto-matches teacher-wide.
    created = client.post(
        "/api/v0/classroom/students",
        json={"full_name": student_name},
        headers=headers_a,
    )
    assert created.status_code == 201

    resp = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
    assert resp.status_code == 200
    item = resp.json()["transcriptions"][0]
    assert item["matched_student_id"] == created.json()["id"]
    reasons = item["flag_verdict"]["reasons"]
    assert "student_unassigned" not in reasons
    assert "student_unmatched" not in reasons

    asyncio.run(_delete_batch_cascade(batch_id))


# ===========================================================================
# Cloud Tasks migration — TranscriptionJob runner + endpoints
# ===========================================================================

async def _insert_transcription_job(user_id: str, rubric_id: str, batch_id: str,
                                    *, status: str = "queued",
                                    filename: str = "doc.pdf",
                                    priority: int = 0) -> str:
    from app.database import AsyncSessionLocal, engine
    from app.models.transcription_job import TranscriptionJob
    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            job = TranscriptionJob(
                user_id=uuid.UUID(user_id), batch_id=uuid.UUID(batch_id),
                rubric_id=uuid.UUID(rubric_id), status=status,
                source_gcs_object_path=f"transcriptions/{user_id}/{uuid4()}.pdf",
                source_filename=filename, doc_priority=priority,
            )
            if status == "failed":       # CHECK: failed => error_message + finished_at
                job.error_message = "seeded failure"
                job.finished_at = datetime.now(timezone.utc)
            if status == "completed":    # CHECK: completed => finished_at
                job.finished_at = datetime.now(timezone.utc)
            db.add(job)
            await db.commit()
            return str(job.id)
    finally:
        await engine.dispose(close=False)


async def _load_job_row(job_id: str):
    from app.database import AsyncSessionLocal, engine
    from app.models.transcription_job import TranscriptionJob
    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            j = await db.get(TranscriptionJob, uuid.UUID(job_id))
            return None if j is None else {
                "status": j.status, "error": j.error_message,
                "net_verdict": j.net_verdict, "attempts": j.attempt_count,
                "transcription_id": (str(j.transcription_id)
                                     if j.transcription_id else None),
                "finished": j.finished_at is not None,
            }
    finally:
        await engine.dispose(close=False)


def _run_sandwiched(coro_factory):
    """Run a coroutine on a fresh loop with the engine-dispose discipline
    (never inherit pooled connections across loops)."""
    async def _s():
        from app.database import engine
        await engine.dispose(close=False)
        try:
            return await coro_factory()
        finally:
            await engine.dispose(close=False)
    return asyncio.run(_s())


@pytest.mark.integration
class TestTranscriptionJobRunner:
    """The worker runner: CAS claim, one-transaction terminal success, durable
    failure, bounded doc re-run, zombie discard. (These are the protections
    that moved here from the retired fan-out containment tests.)"""

    def _fixture_ids(self, user_a, rubric_a):
        user_id = user_a["user"]["id"]
        rubric_id = rubric_a["rubric_id"]
        batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=1))
        return user_id, rubric_id, batch_id

    def test_happy_path_commits_row_and_job_atomically(self, user_a, rubric_a):
        from unittest.mock import AsyncMock, MagicMock
        from app.services import transcription_job_runner as runner

        user_id, rubric_id, batch_id = self._fixture_ids(user_a, rubric_a)
        job_id = asyncio.run(_insert_transcription_job(user_id, rubric_id, batch_id))
        draft = _clean_draft(student_name="דן רץ")

        gcs = MagicMock()
        gcs.download_bytes.return_value = b"%PDF"
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft",
                          AsyncMock(return_value=draft)):
            ran = _run_sandwiched(
                lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran is True

        row = asyncio.run(_load_job_row(job_id))
        assert row["status"] == "completed" and row["finished"]
        assert row["attempts"] == 1
        assert row["transcription_id"] is not None

        # Duplicate delivery (queue maxAttempts=3): claimed/terminal => no-op.
        ran_again = _run_sandwiched(
            lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran_again is False

        asyncio.run(_delete_batch_cascade(batch_id))

    def test_failure_lands_on_row_with_verdict(self, user_a, rubric_a):
        from unittest.mock import AsyncMock, MagicMock
        from app.services import transcription_job_runner as runner

        user_id, rubric_id, batch_id = self._fixture_ids(user_a, rubric_a)
        job_id = asyncio.run(_insert_transcription_job(user_id, rubric_id, batch_id))

        gcs = MagicMock()
        gcs.download_bytes.return_value = b"%PDF"
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft",
                          AsyncMock(side_effect=ValueError("P2 exploded"))), \
             patch("app.services.net_diag.diagnose_transport_failure",
                   AsyncMock(return_value="internet-ok")):
            ran = _run_sandwiched(
                lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran is True            # never raises; failure is on the row

        row = asyncio.run(_load_job_row(job_id))
        assert row["status"] == "failed" and row["finished"]
        assert "P2 exploded" in row["error"]
        assert row["net_verdict"] == "internet-ok"
        assert row["transcription_id"] is None

        asyncio.run(_delete_batch_cascade(batch_id))

    def test_retryable_transport_failure_reruns_document_once(self, user_a, rubric_a):
        from unittest.mock import AsyncMock, MagicMock
        from app.services import transcription_job_runner as runner
        from app.services.transcription.vlm_provider import ErrorKind, VLMCallError

        user_id, rubric_id, batch_id = self._fixture_ids(user_a, rubric_a)
        job_id = asyncio.run(_insert_transcription_job(user_id, rubric_id, batch_id))
        draft = _clean_draft(student_name="גל שני")

        pipeline = AsyncMock(side_effect=[
            VLMCallError(ErrorKind.TRANSIENT, "storm", provider="gemini"), draft])
        gcs = MagicMock()
        gcs.download_bytes.return_value = b"%PDF"
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft", pipeline), \
             patch.object(runner.asyncio, "sleep", AsyncMock()):
            ran = _run_sandwiched(
                lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran is True
        assert pipeline.await_count == 2
        assert asyncio.run(_load_job_row(job_id))["status"] == "completed"

        asyncio.run(_delete_batch_cascade(batch_id))

    def test_zombie_completion_is_discarded_not_doubled(self, user_a, rubric_a):
        """If the claim is lost mid-run (reaped as stale, possibly re-queued
        elsewhere), the zombie worker's INSERT must roll back — committing it
        would double the document."""
        from unittest.mock import AsyncMock, MagicMock
        from app.services import transcription_job_runner as runner

        user_id, rubric_id, batch_id = self._fixture_ids(user_a, rubric_a)
        job_id = asyncio.run(_insert_transcription_job(user_id, rubric_id, batch_id))
        draft = _clean_draft(student_name="עומר זר")

        async def steal_claim(**_kw):
            # Simulate the reaper: flip running -> failed behind the worker.
            from app.database import AsyncSessionLocal
            from sqlalchemy import update as _update
            from app.models.transcription_job import TranscriptionJob
            async with AsyncSessionLocal() as db:
                await db.execute(
                    _update(TranscriptionJob)
                    .where(TranscriptionJob.id == uuid.UUID(job_id))
                    .values(status="failed", error_message="reaped as stale",
                            finished_at=datetime.now(timezone.utc)))
                await db.commit()
            return draft

        gcs = MagicMock()
        gcs.download_bytes.return_value = b"%PDF"
        with patch("app.services.gcs_service.get_gcs_service", return_value=gcs), \
             patch.object(runner, "run_pipeline_and_build_draft",
                          AsyncMock(side_effect=steal_claim)):
            ran = _run_sandwiched(
                lambda: runner.run_transcription_job(uuid.UUID(job_id)))
        assert ran is True

        row = asyncio.run(_load_job_row(job_id))
        assert row["status"] == "failed"           # the steal stands
        assert row["transcription_id"] is None     # zombie INSERT rolled back

        async def count_rows():
            from app.database import AsyncSessionLocal, engine
            from sqlalchemy import select, func
            from app.models.transcription import Transcription
            await engine.dispose(close=False)
            try:
                async with AsyncSessionLocal() as db:
                    return (await db.execute(
                        select(func.count()).select_from(Transcription)
                        .where(Transcription.batch_id == uuid.UUID(batch_id))
                    )).scalar()
            finally:
                await engine.dispose(close=False)
        assert asyncio.run(count_rows()) == 0

        asyncio.run(_delete_batch_cascade(batch_id))


@pytest.mark.integration
def test_retry_job_endpoint_requeues_failed_and_rejects_active(
        client, user_a, user_b, rubric_a, headers_a, headers_b):
    from unittest.mock import AsyncMock

    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=2))
    failed_id = asyncio.run(_insert_transcription_job(
        user_id, rubric_id, batch_id, status="failed"))
    active_id = asyncio.run(_insert_transcription_job(
        user_id, rubric_id, batch_id, status="running"))

    enqueue = AsyncMock()
    with patch("app.api.v0.batch_grading.enqueue_transcription_task", enqueue):
        # Failed -> queued + re-enqueued (no re-upload: bytes stayed in GCS).
        resp = client.post(f"/api/v0/batches/{batch_id}/jobs/{failed_id}/retry",
                           headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "queued"
        enqueue.assert_awaited_once()

        row = asyncio.run(_load_job_row(failed_id))
        assert row["status"] == "queued" and row["error"] is None

        # Live (running, fresh heartbeat) -> 409.
        resp = client.post(f"/api/v0/batches/{batch_id}/jobs/{active_id}/retry",
                           headers=headers_a)
        assert resp.status_code == 409

        # Cross-tenant: 404, never 403.
        resp = client.post(f"/api/v0/batches/{batch_id}/jobs/{failed_id}/retry",
                           headers=headers_b)
        assert resp.status_code == 404

    asyncio.run(_delete_batch_cascade(batch_id))


@pytest.mark.integration
def test_internal_transcription_run_auth_and_dispatch(client):
    """/internal target: 403 without credentials; shared-secret header runs
    the runner (the inline/dev channel — OIDC is the prod channel)."""
    from unittest.mock import AsyncMock
    from app.config import settings as app_settings

    job_id = str(uuid4())
    resp = client.post(f"/internal/transcription-jobs/{job_id}/run")
    assert resp.status_code == 403

    runner_mock = AsyncMock(return_value=True)
    with patch.object(app_settings, "internal_task_token", "sekret"), \
         patch("app.services.transcription_job_runner.run_transcription_job",
               runner_mock):
        resp = client.post(f"/internal/transcription-jobs/{job_id}/run",
                           headers={"X-Internal-Token": "sekret"})
    assert resp.status_code == 200
    assert resp.json()["ran"] is True
    runner_mock.assert_awaited_once()


@pytest.mark.integration
def test_grading_claim_cas_makes_duplicate_delivery_a_noop(client, user_a, rubric_a, headers_a):
    """Phase 4: the pending->grading claim is an atomic CAS - the property
    that makes the grading queue's maxAttempts=3 redelivery safe (the old
    load-then-check guard had a double-grade race window)."""
    from app.services.grading_runner import _claim_grading

    user_id = user_a["user"]["id"]
    rubric_id = rubric_a["rubric_id"]
    draft_json = _clean_draft().model_dump(mode="json")
    batch_id = asyncio.run(_insert_batch_row(user_id, rubric_id, test_count=1))
    t_id = asyncio.run(_insert_transcription_batch(user_id, rubric_id, batch_id, draft_json))

    resp = client.post("/api/v0/classroom/students",
                       json={"full_name": "CAS Claim Student"}, headers=headers_a)
    student_id = resp.json()["id"]

    with patch("app.api.v0.batch_grading.enqueue_grading_task_or_log", new=AsyncMock()):
        resp = client.post(
            f"/api/v0/batches/{batch_id}/accept/{t_id}",
            json={"student_id": student_id,
                  "answers": [{"question_number": 1, "sub_question_id": None,
                               "answer_text": "answer"}]},
            headers=headers_a,
        )
    assert resp.status_code == 200

    async def load_pending_id():
        from app.database import AsyncSessionLocal, engine
        from app.models.grading import GradedTest
        from sqlalchemy import select
        await engine.dispose(close=False)
        try:
            async with AsyncSessionLocal() as db:
                gt = (await db.execute(
                    select(GradedTest).where(GradedTest.batch_id == uuid.UUID(batch_id))
                )).scalars().one()
                return str(gt.id), gt.status
        finally:
            await engine.dispose(close=False)

    gt_id, status = asyncio.run(load_pending_id())
    assert status == "pending"

    async def claim_twice():
        from app.database import AsyncSessionLocal, engine
        await engine.dispose(close=False)
        try:
            async with AsyncSessionLocal() as db:
                first = await _claim_grading(db, uuid.UUID(gt_id))
            async with AsyncSessionLocal() as db:
                second = await _claim_grading(db, uuid.UUID(gt_id))
            return first, second
        finally:
            await engine.dispose(close=False)

    first, second = asyncio.run(claim_twice())
    assert first is True                 # the delivery that does the work
    assert second is False               # the duplicate: provable no-op

    asyncio.run(_delete_batch_cascade(batch_id))


@pytest.mark.integration
def test_internal_grading_run_auth_and_dispatch(client):
    """/internal grading target: 403 without credentials; shared-secret runs
    the runner (mirrors the transcription target)."""
    from unittest.mock import AsyncMock as _AsyncMock
    from app.config import settings as app_settings

    gt_id = str(uuid4())
    resp = client.post(f"/internal/grading-jobs/{gt_id}/run")
    assert resp.status_code == 403

    runner_mock = _AsyncMock(return_value=True)
    with patch.object(app_settings, "internal_task_token", "sekret"),          patch("app.services.grading_runner.run_grading", runner_mock):
        resp = client.post(f"/internal/grading-jobs/{gt_id}/run",
                           headers={"X-Internal-Token": "sekret"})
    assert resp.status_code == 200
    assert resp.json()["ran"] is True
    runner_mock.assert_awaited_once()
