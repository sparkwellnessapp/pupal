"""
Transcription domain schemas — Draft and Contract.

TranscriptionDraft      → transcriptions.draft_json  (immutable after INSERT)
TranscriptionContract   → transcriptions.contract_json (set once at approval)

contract_version lives INSIDE contract_json JSONB per Phase 0a RD-3.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .ontology_types import AnnotationSeverity


# ---------------------------------------------------------------------------
# Annotation (transcription-domain — NOT the rubric-domain Annotation)
# ---------------------------------------------------------------------------

class TranscriptionAnnotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    severity: AnnotationSeverity
    target_id: str  # "transcription" | "q{n}" | "q{n}.{sub}"
    annotation_type: Literal[
        "vlm_uncertainty",
        "vlm_unparseable",
        "student_name_missing",
        "vlm_low_logprob",       # S11: logprob span-min below threshold
        "reader_disagreement",   # trust layer: independent readers read this span differently
        "code_lint",             # trust layer: deterministic code check (brace balance)
        "segmentation_mismatch",  # student's leading marker contradicts the P2-assigned key
    ]
    message: str  # Hebrew, user-facing
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Draft side
# ---------------------------------------------------------------------------

class TranscriptionDraftAnswer(BaseModel):
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    confidence: float
    page_numbers: List[int] = Field(default_factory=list)


class TranscriptionDraft(BaseModel):
    schema_version: str = "1.0"
    student_name_suggestion: Optional[str] = None  # VLM guess — hint only
    page_count: int
    answers: List[TranscriptionDraftAnswer]
    annotations: List[TranscriptionAnnotation] = Field(default_factory=list)
    model_version: Optional[str] = None
    # D-16 stamp (2026-09-08): the P1/P2 prompt version this draft was produced
    # under — `t1.4-tables` for CS, `t1.4-tables+<subject>` otherwise. Additive:
    # every stored draft parses unchanged (None = pre-seam).
    prompt_version: Optional[str] = None
    transcription_duration_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Selection expectation (review-surface auxiliary — NOT part of the draft)
# ---------------------------------------------------------------------------

class AnswerSpaceSelectionGroup(BaseModel):
    """A rubric SelectionGroup translated into transcription-answer space.

    `of_question_ids` ('q1', 'q2', …) become the `question_number` ints the
    transcription answers actually carry, so review surfaces and triage can
    reason about "choose k of N" without knowing the rubric's shape. Derived
    at read time by `selection_expectation.answer_space_groups` — never
    persisted (the rubric contract stays the single source)."""
    choose_k: int
    question_numbers: List[int]


# ---------------------------------------------------------------------------
# Review overlay (teacher working copy — transcriptions.review_json)
# ---------------------------------------------------------------------------

class TranscriptionReviewAnswer(BaseModel):
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str


class TranscriptionReview(BaseModel):
    """
    The teacher's persisted working copy of a transcription review.

    FULL SNAPSHOT, always: `answers` carries the complete answer set, and its
    (question_number, sub_question_id) key multiset must equal the draft's —
    a mismatched snapshot is rejected (422), never normalized. No merge
    semantics exist anywhere, now or in any future endpoint.

    `student_id` is the teacher's chosen student. It lives here (not in the
    transcriptions.student_id column) because transcriptions_approval_consistency
    forbids the column before approval.

    Lifecycle: writable only while status='transcribed'; set to NULL inside the
    same UPDATE that performs the 'transcribed'→'approved' transition (part of
    the transition write — LCY-1 untouched). Concurrent writes are
    last-write-wins. Accept endpoints remain body-authoritative: this overlay
    is durability for the UI, never the approval input (the future batch
    /submit endpoint is the documented exception — it has no body).
    """
    schema_version: str = "1.0"
    answers: List[TranscriptionReviewAnswer]
    student_id: Optional[str] = None
    updated_at: Optional[str] = None  # server-stamped ISO-8601 at write time


# ---------------------------------------------------------------------------
# Contract side (frozen — teacher-approved)
# ---------------------------------------------------------------------------

class TranscriptionContractAnswer(BaseModel):
    model_config = {"frozen": True}
    # ALPHA-GAP A-4 (D-2): `page_numbers` is dropped from the contract; alpha carries it so a figure scope can reach its page.
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str


class TranscriptionContract(BaseModel):
    model_config = {"frozen": True}
    schema_version: str = "1.0"
    contract_version: str = Field(default_factory=lambda: str(uuid4()))
    answers: List[TranscriptionContractAnswer]
