"""An UNSCORED part is a fact to surface, not a parse failure (multisubject Phase 2).

The 4-unit Math fixture has no marking scheme for q2 (vectors): the first real-provider
run had the model faithfully emit 0 for q2's parts, and the extraction schema's `gt=0`
rejected the whole document at the SDK parse — a teacher's omission became an opaque
job failure. Now: the schema accepts 0 on sub-question nodes (`ge=0`), the validator
spends no retry on an unscored part (SQ_ZERO_CRITERIA is retryable only for a SCORED
part — retrying would only tempt the model to invent criteria), the Draft carries the
node for the teacher, and compile is blocked by INV-1 until she writes the weights.

No provider: the pipeline's single LLM seam is patched (the seam test's pattern).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.ontology_types import NumericPolicy
from app.services.contract_compiler import ContractCompiler
from app.services.docx_v3.parser_render import RenderStats
from app.services.docx_v3.pipeline import (
    CriterionExtraction,
    ExtractionConfig,
    QuestionExtraction,
    RubricExtraction,
    SubQuestionExtraction,
    extract_rubric_from_docx,
)


def _q2_like_extraction() -> RubricExtraction:
    """q1 scored as usual; q2 present with its printed parts and NO weights anywhere."""
    return RubricExtraction(
        document_title="t",
        total_points=100,
        questions=[
            QuestionExtraction(
                question_number=1, question_text="שאלה 1", total_points=100,
                criteria=[CriterionExtraction(description="הצבה (100%)", points=100)],
                sub_questions=[],
            ),
            QuestionExtraction(
                question_number=2, question_text="שאלה 2", total_points=100,
                criteria=[],
                sub_questions=[
                    SubQuestionExtraction(sub_question_id="א", text="הביעו את הווקטורים", points=0),
                    SubQuestionExtraction(sub_question_id="ב", text="מצאו את שיעורי הקודקודים", points=0),
                    SubQuestionExtraction(sub_question_id="ג", text="חשבו את שטח המשולש", points=0),
                ],
            ),
        ],
    )


def _meta():
    return {"input_tokens": 10, "output_tokens": 5, "finish_reason": "stop", "model": "test-model"}


async def _run(config: ExtractionConfig):
    llm = AsyncMock(return_value=(_q2_like_extraction(), _meta()))
    with patch("app.services.docx_v3.parser_render.render_docx_to_markdown_with_stats",
               return_value=("RENDERED DOC", RenderStats())), \
         patch("app.services.docx_v3.pipeline._call_llm", new=llm), \
         patch("app.services.docx_v3.pipeline.detect_pedagogical_mistakes", return_value=[]):
        result = await extract_rubric_from_docx(
            file_bytes=b"PK\x03\x04fake", extraction_config=config, name="test",
        )
    return result, llm


@pytest.mark.asyncio
async def test_unscored_parts_survive_extraction_without_a_retry_and_reach_the_teacher():
    result, llm = await _run(ExtractionConfig(subject="mathematics"))
    assert llm.await_count == 1                      # no retry spent on the omission
    assert result.metadata["retry_count"] == 0
    resp = result.response
    q2 = next(q for q in resp.questions if q.question_id == "q2")
    assert [s.points for s in q2.sub_questions] == [Decimal(0)] * 3
    # the validator still names each unscored part for her (warning strings, not annotations)
    assert sum("SQ_ZERO_CRITERIA" in w for w in result.warnings) == 3
    # the mathematics post-pass ran: q2 keeps its printed 100 (no group), parts stay 0,
    # and ONE rubric_mismatch names q2 on the exam scale
    stamp = resp.extraction_metadata["rescale_to_exam"]
    assert stamp["unresolved"] == ["q2"]
    a = next(x for x in resp.annotations if x.annotation_type == "rubric_mismatch")
    assert (a.target_id, a.expected, a.actual) == ("q2", "100", "0")
    # compile is blocked at q2 (INV-1) until she writes the weights
    with pytest.raises(Exception):
        ContractCompiler().compile(resp, policy=NumericPolicy(),
                                   acknowledged_warnings=[x.id for x in resp.annotations])
    # her fill compiles
    from app.schemas.ontology_types import Criterion
    for s, p in zip(q2.sub_questions, (Decimal("40"), Decimal("40"), Decimal("20"))):
        s.points = p
        s.criteria = [Criterion(criterion_id=f"q2.{s.sub_question_id}.c0", index=0,
                                description="פתרון מלא", points=p)]
    resp.annotations = []
    # Two mandatory questions of 100 and no selection group, so the exam is out of 200 —
    # what THIS fixture pins is that her fill compiles at all; the 4-unit fixture's real
    # 100 lives in test_rescale_to_exam.py.
    assert ContractCompiler().compile(resp, policy=NumericPolicy()).total_points == Decimal("200")


@pytest.mark.asyncio
async def test_cs_baseline_gets_the_same_draft_without_the_post_pass():
    """CS never produces a 0 here, but if it did the path is the same minus the post-pass:
    the extraction validator's own rubric_mismatch (Σ parts 0 ≠ declared 100) reaches
    the teacher and nothing is invented."""
    result, llm = await _run(ExtractionConfig())
    assert llm.await_count == 1
    resp = result.response
    assert "rescale_to_exam" not in resp.extraction_metadata
    q2 = next(q for q in resp.questions if q.question_id == "q2")
    assert [s.points for s in q2.sub_questions] == [Decimal(0)] * 3
    assert any(a.annotation_type == "rubric_mismatch" and a.target_id == "q2" for a in resp.annotations)
