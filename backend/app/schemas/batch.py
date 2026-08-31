"""
Request and response schemas for S11 batch grading endpoints.

All Decimal-valued fields (scores) are serialized to str for JSON transport,
mirroring the pattern in graded_test_responses.py.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer

from .transcription import (
    AnswerSpaceSelectionGroup,
    TranscriptionDraft,
    TranscriptionReview,
)


# ---------------------------------------------------------------------------
# Shared sub-types
# ---------------------------------------------------------------------------

class FlagVerdictResponse(BaseModel):
    """Flag triage result for a single transcription."""
    review_needed: bool
    reasons: list[str]   # subset of: "unparseable", "grounding_retry",
                         #  "low_confidence", "low_logprob_span", "code_lint",
                         #  "missing_answers", "segmentation_mismatch",
                         #  "student_unassigned", "student_unmatched"


class BatchTranscriptionItem(BaseModel):
    """
    Per-test item returned in the batch detail / transcription-review payload.
    Includes the full draft for individual review + pre-computed triage data.
    """
    transcription_id: UUID
    filename: Optional[str] = None
    transcription_status: str               # 'transcribed' | 'approved'
    created_at: str                         # row insert time (Δ15: progress-based residue horizon)
    draft: TranscriptionDraft               # full draft for review/display
    review: Optional[TranscriptionReview] = None  # teacher overlay (review_json), if saved
    student_name_suggestion: Optional[str] = None
    matched_student_id: Optional[str] = None    # pre-computed normalized-exact match
    matched_student_name: Optional[str] = None
    flag_verdict: FlagVerdictResponse
    # B6 (approved-item truthfulness): the FROZEN contract's answers, present
    # only when transcription_status == 'approved'. The read-only review view
    # hydrates from these — the draft alone shows pre-edit text (census Q15).
    # Answers only, to keep the payload lean; None on parse failure (per-item
    # degradation, never batch-fatal).
    approved_answers: Optional[list[GradeAnswerInputItem]] = None
    # Populated once a GradedTest row exists for this transcription:
    graded_test_id: Optional[UUID] = None
    graded_test_status: Optional[str] = None
    total_score: Optional[str] = None
    total_possible: Optional[str] = None


class BatchRollup(BaseModel):
    """
    Live pipeline counts for a batch — derived at query time, never stored.
    The `transcribing` count is ephemeral: tests whose background task is still
    in flight (batch.test_count minus transcription rows minus ledgered
    transcription failures — migration 015).
    """
    transcribing: int           # PDFs whose VLM call is in-flight
    transcribed: int            # transcription.status='transcribed' (awaiting review)
    # Closeout/Ruling 1: the flagged-or-touched subset of `transcribed` — i.e.
    # exactly what accept_clean REFUSES. `transcribed - needs_eyes` is the
    # bulk-acceptable remainder. Without this the list page could only report
    # the merged "awaiting decisions" count, which cannot tell one
    # bulk-accept click apart from five full reviews. Defaults to 0 so the
    # field is additive for any client that has not been rebuilt.
    #
    # OPTIONAL BY DESIGN (owner ruling, closeout): None means "not computable
    # for this batch" — a corrupt rubric contract makes the count wrong in a
    # specific direction (selection empties read as missing answers), so the
    # display path OMITS the figure rather than publishing a confident lie.
    # Degrade by omission, same rule as D10's hero stats.
    needs_eyes: Optional[int] = None
    approved_transcription: int # transcription.status='approved' (queued for grading)
    grading: int                # graded_test.status in ('pending', 'grading')
    draft: int                  # graded_test.status='draft'
    approved: int               # graded_test.status='approved'
    failed: int                 # graded_test.status='failed'
    transcription_failed: int = 0  # ledgered transcription failures (dead, not in flight)
    total: int                  # = batch.test_count


class TranscriptionFailureItem(BaseModel):
    """One failed batch document. Cloud Tasks batches source these from
    FAILED TranscriptionJob rows (job_id present ⇒ retryable without
    re-upload); legacy pre-016 batches from the read-only migration-015
    ledger (job_id None ⇒ no retry affordance)."""
    filename: Optional[str] = None
    error: str
    at: str                     # ISO-8601, when the failure was recorded
    net_verdict: Optional[str] = None  # net_diag verdict at failure time, if any
    job_id: Optional[str] = None       # retry handle (Cloud Tasks batches only)


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

class ActiveJobItem(BaseModel):
    """One in-flight document (B3): sourced from the already-fetched
    queued/running TranscriptionJob rows, doc_priority order. Feeds the
    dashboard's transcribing ghosts — name + elapsed, no fabricated ETA."""
    filename: Optional[str] = None
    state: Literal["queued", "running"]
    created_at: str                    # enqueue time (queued clock)
    started_at: Optional[str] = None   # claim time (running only)
    attempt_count: int


class BatchEta(BaseModel):
    """How long until she can start reviewing.

    `kind` is as honest as the inputs allow: `unknown` when no latency profile
    exists for the model, and the client says «עוד רגע» rather than a figure.
    Publishing a number we cannot support would be a confident guess about the
    one thing she is waiting on.
    """
    kind: Literal["first_landing", "remaining", "unknown"]
    seconds: Optional[int] = None


class BatchGradedItem(BaseModel):
    """One graded test on the batch feed (spec §1.5)."""
    graded_test_id: UUID
    student_id: Optional[UUID] = None
    student_name: Optional[str] = None
    status: str                       # pending | grading | draft | approved | failed
    version: int = 1                  # position in the revision chain
    landed_at: Optional[str] = None   # when the draft appeared
    opened_at: Optional[str] = None   # when she first looked
    # EFFECTIVE (overlay-priced) total — the pencil number on the card
    total_awarded: Optional[Decimal] = None
    # Deterministic markers needing her eye (services/look_count.py).
    # OPTIONAL BY DESIGN: None = "not computable for this test" — a draft that
    # will not parse gets no number rather than a reassuring 0, which would be
    # wrong in the dangerous direction (§3.5a, the needs_eyes precedent).
    look_count: Optional[int] = None
    # [R-1] the consistency audit is DEFERRED. The literal "none" ships so the
    # wire shape is complete and the frontend suppresses every audit string.
    audit_touched: Literal["none", "updated", "reapprove"] = "none"
    # [G9] no returned exam is rendered yet
    returned_exam_state: Literal["none", "rendering", "ready", "stale"] = "none"

    @field_serializer("total_awarded")
    def _sd(self, v):
        return None if v is None else str(v)


class BatchDetailResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    rubric_id: UUID
    class_id: Optional[UUID] = None
    # B4: display names, resolved server-side (user-scoped; None if the class
    # was deleted — the SET NULL FK makes that real).
    rubric_name: Optional[str] = None
    class_name: Optional[str] = None
    status: str                     # derived from rollup, not stored
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    rollup: BatchRollup
    transcriptions: list[BatchTranscriptionItem]
    # B3: in-flight documents (queued/running), doc_priority order, built
    # AFTER the liveness reap — active means genuinely active.
    active_jobs: list[ActiveJobItem] = []
    # Rubric selection groups in transcription-answer space (batch-level —
    # every item shares the rubric). [] for selection-free rubrics; the
    # review surface uses it to suppress expected-empty containers live.
    selection_groups: list[AnswerSpaceSelectionGroup] = []
    # Durable per-document failure records (migration 015) — the dashboard
    # renders these as failed cards instead of an eternal spinner.
    transcription_failures: list[TranscriptionFailureItem] = []

    # ── [PR-G8] the grading half of the feed (spec §1.5) ──────────────────
    graded_tests: list[BatchGradedItem] = []
    eta: BatchEta = BatchEta(kind="unknown")
    # [R-1] The consistency audit is DEFERRED to its own PR. It ships as the
    # literal "disabled" — which is in the §1.5 enum — so the frontend renders
    # two steps and suppresses every audit-related string. NOT a dark feature:
    # there is no audit table, no applier and no producer behind it.
    audit_status: Literal["disabled", "pending", "running", "done", "failed"] = "disabled"
    # [G9] rendered-exam settings; defaults until PR-G9 lands their column
    appendix_include_criteria: bool = False
    stamp_position_default: Optional[dict] = None


class BatchListItem(BaseModel):
    id: UUID
    name: Optional[str] = None
    rubric_id: UUID
    class_id: Optional[UUID] = None
    # B4: display names (batch-fetched up front — zero per-batch round-trips).
    rubric_name: Optional[str] = None
    class_name: Optional[str] = None
    status: str
    created_at: str
    rollup: BatchRollup


class BatchCreateRequest(BaseModel):
    """B9 intake v2: metadata-only create. Files arrive one per request via
    POST /batches/{id}/files — the legacy every-PDF-in-one-multipart body hit
    Cloud Run's 32MB request ceiling at ~5 scans."""
    rubric_id: UUID
    class_id: Optional[UUID] = None
    name: Optional[str] = None


class BatchCreateResponse(BaseModel):
    batch_id: str
    test_count: int


class BatchFileAppendResponse(BaseModel):
    """One appended file (B9). Idempotent: a retried append that already
    committed returns the EXISTING job with the same body."""
    job_id: str
    filename: Optional[str] = None
    test_count: int


class AcceptCleanSkippedItem(BaseModel):
    """One skipped row in a bulk-accept response (B1 — server-side clean
    enforcement). Reasons:
      * "flagged"          — the server-side verdict recompute says review_needed
                             (OD1: "clean" is a server-guaranteed property);
      * "has_review_edits" — teacher-touched (Δ1: a saved overlay is never
                             silently discarded by a draft-as-is bulk accept);
      * "already_approved" — idempotent repost / approved via another path.
    """
    transcription_id: str
    skipped_reason: Literal["flagged", "has_review_edits", "already_approved"]


class AcceptCleanResponse(BaseModel):
    """Bulk-accept outcome. `skipped` is additive for the pre-Phase-4 client
    (it parses `accepted` only); the redesign dashboard surfaces every skip."""
    accepted: int
    skipped: list[AcceptCleanSkippedItem] = []


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class BatchRenameRequest(BaseModel):
    """B5: rename a batch. Stripped server-side; blank-after-strip → 422."""
    name: str


class BatchRenameResponse(BaseModel):
    batch_id: str
    name: str


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
