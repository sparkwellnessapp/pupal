"""
PR-1 — pipeline on_progress seam + task-auth unit tests.

Pure tests: mocked LLM (never OpenAI), mocked renderer, no DB, no network.

The load-bearing assertions:
  1. on_progress=None ⇒ result identical to a run with a callback (the seam
     is observability-only; PIPELINE_VERSION 3.2.0's no-behavior-change claim).
  2. A callback that RAISES never affects the extraction (rule 2 of the seam).
  3. The expected stage sequence fires in order.
  4. verify_task_request: shared-secret and bearer rejection paths.
"""
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from app.services.docx_v3.pipeline import (
    CriterionExtraction,
    ExtractionConfig,
    ProgressEvent,
    QuestionExtraction,
    RubricExtraction,
    extract_rubric_from_docx,
)


# ---------------------------------------------------------------------------
# Helpers: a minimal valid extraction (passes validation on attempt 1)
# ---------------------------------------------------------------------------

def _make_extraction() -> RubricExtraction:
    return RubricExtraction(
        document_title="t",
        total_points=100,
        questions=[
            QuestionExtraction(
                question_number=1,
                question_text="שאלה 1",
                total_points=100,
                criteria=[CriterionExtraction(description="קריטריון", points=100)],
                sub_questions=[],
            )
        ],
    )


def _call_meta() -> Dict[str, Any]:
    return {"input_tokens": 10, "output_tokens": 5, "finish_reason": "stop", "model": "test-model"}


def _patches():
    """Patch the three side-effecting collaborators of the pipeline."""
    return (
        patch(
            "app.services.docx_v3.parser_render.render_docx_to_markdown",
            return_value="RENDERED DOC",
        ),
        patch(
            "app.services.docx_v3.pipeline._call_llm",
            new=AsyncMock(return_value=(_make_extraction(), _call_meta())),
        ),
        patch(
            "app.services.docx_v3.pipeline.detect_pedagogical_mistakes",
            return_value=[],
        ),
    )


async def _run(on_progress=None):
    p1, p2, p3 = _patches()
    with p1, p2, p3:
        return await extract_rubric_from_docx(
            file_bytes=b"PK\x03\x04fake",
            extraction_config=ExtractionConfig(),
            name="test",
            on_progress=on_progress,
        )


def _dump_without_generated_ids(response) -> dict:
    """model_dump minus the per-run uuid4 rubric_id — everything else must be
    byte-identical across runs."""
    d = response.model_dump(mode="json")
    d.pop("rubric_id", None)
    return d


# ---------------------------------------------------------------------------
# 1. on_progress=None ⇒ identical result to a run with a callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_none_callback_identical_result():
    result_none = await _run(on_progress=None)

    events: List[ProgressEvent] = []
    result_cb = await _run(on_progress=events.append)

    assert result_none.response is not None and result_cb.response is not None
    # The extraction payload must be byte-identical (modulo the per-run uuid4 rubric_id)
    assert _dump_without_generated_ids(result_none.response) == _dump_without_generated_ids(result_cb.response)
    assert result_none.warnings == result_cb.warnings
    assert result_none.errors == result_cb.errors
    assert result_none.requires_review == result_cb.requires_review
    # Provenance identical (timings excluded — wall-clock differs by nature)
    assert result_none.metrics.input_tokens == result_cb.metrics.input_tokens
    assert result_none.metrics.output_tokens == result_cb.metrics.output_tokens
    assert result_none.metrics.retry_count == result_cb.metrics.retry_count
    # And the callback run actually observed events
    assert len(events) > 0


# ---------------------------------------------------------------------------
# 2. Raising callback never affects the extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raising_callback_does_not_affect_extraction():
    def bomb(_event: ProgressEvent) -> None:
        raise RuntimeError("progress persistence exploded")

    result_none = await _run(on_progress=None)
    result_bomb = await _run(on_progress=bomb)

    assert result_bomb.response is not None
    assert _dump_without_generated_ids(result_bomb.response) == _dump_without_generated_ids(result_none.response)
    assert result_bomb.errors == result_none.errors


# ---------------------------------------------------------------------------
# 3. Expected stage sequence, in order; async callbacks supported
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_sequence_and_async_callback():
    events: List[ProgressEvent] = []

    async def collect(event: ProgressEvent) -> None:  # async callback flavor
        events.append(event)

    result = await _run(on_progress=collect)
    assert result.response is not None

    stages = [e.stage for e in events]
    # Clean single-attempt run: render → llm_call → validate → build →
    # pedagogical(start) → pedagogical(done) → complete
    assert stages == [
        "render", "llm_call", "validate", "build",
        "pedagogical", "pedagogical", "complete",
    ]
    # llm_call/validate carry the 1-based attempt
    assert events[1].attempt == 1 and events[2].attempt == 1
    # validate carries cumulative token counts
    assert events[2].input_tokens == 10 and events[2].output_tokens == 5
    # every event stamps elapsed time
    assert all(e.elapsed_s is not None for e in events)
    # complete carries final token totals
    assert events[-1].input_tokens == 10 and events[-1].output_tokens == 5


# ---------------------------------------------------------------------------
# 4. verify_task_request — auth decision table (no network: bad-token paths)
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers


def test_verify_shared_secret_accepts_match():
    from app.services.cloud_tasks_service import verify_task_request

    with patch("app.services.cloud_tasks_service.settings") as s:
        s.internal_task_token = "sekrit"
        assert verify_task_request(_FakeRequest({"X-Internal-Token": "sekrit"})) is None


def test_verify_shared_secret_rejects_mismatch():
    from app.services.cloud_tasks_service import verify_task_request

    with patch("app.services.cloud_tasks_service.settings") as s:
        s.internal_task_token = "sekrit"
        assert verify_task_request(_FakeRequest({"X-Internal-Token": "wrong"})) == "bad shared secret"


def test_verify_rejects_missing_bearer():
    from app.services.cloud_tasks_service import verify_task_request

    with patch("app.services.cloud_tasks_service.settings") as s:
        s.internal_task_token = None
        assert verify_task_request(_FakeRequest({})) == "missing bearer token"


def test_verify_rejects_garbage_bearer():
    from app.services.cloud_tasks_service import verify_task_request

    with patch("app.services.cloud_tasks_service.settings") as s:
        s.internal_task_token = None
        s.service_base_url = "https://example.run.app"
        reason = verify_task_request(_FakeRequest({"Authorization": "Bearer garbage"}))
        assert reason is not None and reason.startswith("oidc verification failed")
