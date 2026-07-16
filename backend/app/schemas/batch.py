"""
Request and response schemas for S11 batch grading endpoints.

All Decimal-valued fields (scores) are serialized to str for JSON transport,
mirroring the pattern in graded_test_responses.py.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from .transcription import TranscriptionDraft


# ---------------------------------------------------------------------------
# Shared sub-types
# ---------------------------------------------------------------------------

class FlagVerdictResponse(BaseModel):
    """Flag triage result for a single transcription."""
    review_needed: bool
    reasons: list[str]   # subset of: "unparseable", "grounding_retry",
                         #  "low_confidence", "low_logprob_span", "student_unmatched"


class BatchTranscriptionItem(BaseModel):
    """
    Per-test item returned in the batch detail / transcription-review payload.
    Includes the full draft for individual review + pre-computed triage data.
    """
    transcription_id: UUID
    filename: Optional[str] = None
    transcription_status: str               # 'transcribed' | 'approved'
    draft: TranscriptionDraft               # full draft for review/display
    student_name_suggestion: Optional[str] = None
    matched_student_id: Optional[str] = None    # pre-computed normalized-exact match
    matched_student_name: Optional[str] = None
    flag_verdict: FlagVerdictResponse
    # Populated once a GradedTest row exists for this transcription:
    graded_test_id: Optional[UUID] = None
    graded_test_status: Optional[str] = None
    total_score: Optional[str] = None
    total_possible: Optional[str] = None


class BatchRollup(BaseModel):
    """
    Live pipeline counts for a batch — derived at query time, never stored.
    The `transcribing` count is ephemeral: tests whose background task is still
    in flight (batch.test_count minus the number of transcription rows so far).
    """
    transcribing: int           # PDFs whose VLM call is in-flight
    transcribed: int            # transcription.status='transcribed' (awaiting review)
    approved_transcription: int # transcription.status='approved' (queued for grading)
    grading: int                # graded_test.status in ('pending', 'grading')
    draft: int                  # graded_test.status='draft'
    approved: int               # graded_test.status='approved'
    failed: int                 # graded_test.status='failed'
    total: int                  # = batch.test_count


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

class BatchDetailResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    rubric_id: UUID
    class_id: Optional[UUID] = None
    status: str                     # derived from rollup, not stored
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    rollup: BatchRollup
    transcriptions: list[BatchTranscriptionItem]


class BatchListItem(BaseModel):
    id: UUID
    name: Optional[str] = None
    rubric_id: UUID
    class_id: Optional[UUID] = None
    status: str
    created_at: str
    rollup: BatchRollup


class BatchCreateResponse(BaseModel):
    batch_id: str
    test_count: int


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class AcceptCleanItem(BaseModel):
    """One item in a bulk-clean-accept request."""
    transcription_id: UUID
    student_id: UUID            # confirmed: auto-matched or teacher-picked


class AcceptCleanRequest(BaseModel):
    """
    Bulk-accept all clean transcriptions.
    The backend builds each contract from the transcription's draft_json
    (no teacher edits for clean tests — teacher is confirming as-is).
    """
    items: list[AcceptCleanItem]


class GradeAnswerInputItem(BaseModel):
    """One reviewed answer in an individual-accept request."""
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str


class AcceptOneTranscriptionRequest(BaseModel):
    """Accept a single flagged transcription with optional teacher edits."""
    student_id: UUID
    answers: list[GradeAnswerInputItem]     # teacher's reviewed / edited answers
