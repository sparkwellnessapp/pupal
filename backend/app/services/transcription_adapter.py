"""
Adapter: TranscriptionResult → TranscriptionDraft.

Pure function. Service stays annotation-agnostic; adapter derives annotations
from the service's signals (confidence, [?] markers, retry flag, logprob span).
"""
from ..config import settings
from ..schemas.ontology_types import AnnotationSeverity
from ..schemas.transcription import (
    TranscriptionAnnotation,
    TranscriptionDraft,
    TranscriptionDraftAnswer,
)
from ..services.handwriting_transcription_service import TranscriptionResult

LOW_CONFIDENCE_THRESHOLD = 0.7


def _answer_target(question_number: int, sub_question_id) -> str:
    base = f"q{question_number}"
    return f"{base}.{sub_question_id}" if sub_question_id else base


def build_transcription_draft(
    result: TranscriptionResult,
    page_count: int,
    model_version: str,
    duration_ms: int,
) -> TranscriptionDraft:
    answers = []
    annotations = []

    for ans in result.answers:
        target = _answer_target(ans.question_number, ans.sub_question_id)

        answers.append(TranscriptionDraftAnswer(
            question_number=ans.question_number,
            sub_question_id=ans.sub_question_id,
            answer_text=ans.answer_text,
            confidence=ans.confidence,
            page_numbers=ans.page_numbers,
        ))

        # [?] markers → vlm_unparseable (warning)
        if "[?]" in ans.answer_text:
            annotations.append(TranscriptionAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id=target,
                annotation_type="vlm_unparseable",
                message="חלקים מהתשובה לא היו קריאים בתמלול",
            ))

        # grounding retry needed → vlm_uncertainty (warning) with metadata for triage
        if ans.needed_grounding_retry:
            annotations.append(TranscriptionAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id=target,
                annotation_type="vlm_uncertainty",
                message="התמלול של שאלה זו דרש אימות נוסף — מומלץ לבדוק מול המקור",
                metadata={"needed_grounding_retry": True},
            ))

        # low confidence → vlm_uncertainty (info) — only if no retry flag
        elif ans.confidence < LOW_CONFIDENCE_THRESHOLD:
            annotations.append(TranscriptionAnnotation(
                severity=AnnotationSeverity.INFO,
                target_id=target,
                annotation_type="vlm_uncertainty",
                message="רמת ביטחון נמוכה בתמלול",
                metadata={"needed_grounding_retry": False},
            ))

    # S11: logprob span-min signal — worst-case across all answers
    # (min_span_logprob lives on each answer from the page that produced it)
    span_mins = [
        ans.min_span_logprob
        for ans in result.answers
        if getattr(ans, "min_span_logprob", None) is not None
    ]
    if span_mins:
        worst = min(span_mins)
        if worst < settings.logprob_span_threshold:
            annotations.append(TranscriptionAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id="transcription",
                annotation_type="vlm_low_logprob",
                message="זוהתה אי-ודאות בתמלול — מומלץ לבדוק מול המקור",
                metadata={
                    "min_span_logprob": worst,
                    "threshold": settings.logprob_span_threshold,
                },
            ))

    # missing student name → student_name_missing (info)
    if not result.student_name:
        annotations.append(TranscriptionAnnotation(
            severity=AnnotationSeverity.INFO,
            target_id="transcription",
            annotation_type="student_name_missing",
            message="לא זוהה שם תלמיד — נא לבחור תלמיד",
        ))

    return TranscriptionDraft(
        student_name_suggestion=result.student_name or None,
        page_count=page_count,
        answers=answers,
        annotations=annotations,
        model_version=model_version,
        transcription_duration_ms=duration_ms,
    )
