"""
S11 Batch grading endpoints.

POST /api/v0/batches                         — create + eager transcription fan-out
GET  /api/v0/batches                         — list (user-scoped)
GET  /api/v0/batches/{id}                    — detail + live roll-up + per-test triage
POST /api/v0/batches/{id}/accept_clean       — bulk-accept clean transcriptions
POST /api/v0/batches/{id}/accept/{tid}       — accept one flagged transcription
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_owned_or_404
from ...config import settings
from ...database import get_db
from ...models.classroom import Class, ClassMembership
from ...models.grading import GradedTest, GradingBatch, Rubric
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.user import User
from ...schemas.batch import (
    AcceptCleanRequest,
    AcceptOneTranscriptionRequest,
    BatchCreateResponse,
    BatchDetailResponse,
    BatchListItem,
    BatchRollup,
    BatchTranscriptionItem,
    FlagVerdictResponse,
)
from ...schemas.transcription import (
    TranscriptionContract,
    TranscriptionContractAnswer,
    TranscriptionDraft,
)
from ...services.batch_triage import FlagVerdict, compute_flag_verdict, match_student
from ...services.grading_runner import run_grading
from ...services.transcribe_one import transcribe_one
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/batches", tags=["batches"])

# ---------------------------------------------------------------------------
# Bounded concurrency semaphore
# ---------------------------------------------------------------------------
# Module-level, lazily initialised so it binds to the running event loop.
# batch_cap(5) × grader_scope_cap(5) = 25 worst-case concurrent LLM calls.

_batch_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _batch_semaphore
    if _batch_semaphore is None:
        _batch_semaphore = asyncio.Semaphore(settings.batch_max_concurrent_tests)
    return _batch_semaphore


async def _transcribe_with_cap(
    pdf_bytes: bytes,
    filename: str | None,
    rubric_id: UUID,
    user_id: UUID,
    batch_id: UUID,
) -> None:
    """Background task: acquire batch semaphore, then transcribe."""
    async with _get_semaphore():
        try:
            await transcribe_one(
                pdf_bytes=pdf_bytes,
                filename=filename,
                rubric_id=rubric_id,
                user_id=user_id,
                batch_id=batch_id,
            )
        except Exception:
            logger.exception(
                "batch_transcription_failed",
                extra={"batch_id": str(batch_id), "filename": filename},
            )


async def _grade_with_cap(graded_test_id: UUID) -> None:
    """Background task: acquire batch semaphore, then run grading."""
    async with _get_semaphore():
        await run_grading(graded_test_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_batch_status(rollup: BatchRollup) -> str:
    """Derive the batch's aggregate status from child counts. Never stored."""
    if rollup.failed > 0 and rollup.total > 0:
        non_failed = rollup.total - rollup.failed
        if rollup.approved >= non_failed:
            return "partially_completed"
    if rollup.total > 0 and rollup.approved == rollup.total:
        return "completed"
    if rollup.transcribing > 0 or rollup.grading > 0 or rollup.draft > 0 or rollup.transcribed > 0:
        return "in_progress"
    return "in_progress"


def _build_rollup(
    batch: GradingBatch,
    transcriptions: list[Transcription],
    graded_tests: list[GradedTest],
) -> BatchRollup:
    transcribed = sum(1 for t in transcriptions if t.status == "transcribed")
    approved_t = sum(1 for t in transcriptions if t.status == "approved")
    grading = sum(1 for g in graded_tests if g.status in ("pending", "grading"))
    draft = sum(1 for g in graded_tests if g.status == "draft")
    approved_g = sum(1 for g in graded_tests if g.status == "approved")
    failed = sum(1 for g in graded_tests if g.status == "failed")
    total = batch.test_count
    transcribing = max(0, total - len(transcriptions))
    return BatchRollup(
        transcribing=transcribing,
        transcribed=transcribed,
        approved_transcription=approved_t,
        grading=grading,
        draft=draft,
        approved=approved_g,
        failed=failed,
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /batches — create + fan out transcription
# ---------------------------------------------------------------------------

@router.post("", response_model=BatchCreateResponse, status_code=201)
async def create_batch(
    files: list[UploadFile] = File(..., description="PDF files to grade"),
    rubric_id: UUID = Form(...),
    class_id: Optional[UUID] = Form(None),
    name: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchCreateResponse:
    """
    Create a batch and immediately fan out transcription for each PDF.
    Returns {batch_id, test_count} after queuing background tasks.
    The frontend polls GET /batches/{id} to track transcription progress.
    """
    rubric = await get_owned_or_404(db, Rubric, rubric_id, current_user.id)
    if not rubric.is_compiled:
        raise HTTPException(400, "המחוון לא עבר קומפילציה")
    if class_id is not None:
        await get_owned_or_404(db, Class, class_id, current_user.id)

    batch = GradingBatch(
        user_id=current_user.id,
        rubric_id=rubric_id,
        rubric_contract_version=rubric.contract_version,
        name=name,
        class_id=class_id,
        status="in_progress",
        test_count=0,       # will be updated below
        started_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.flush()

    # Read all PDF bytes before commit (UploadFile streams close after response)
    pdf_list: list[tuple[bytes, str | None]] = []
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            continue
        pdf_bytes = await f.read()
        if pdf_bytes:
            pdf_list.append((pdf_bytes, f.filename))

    batch.test_count = len(pdf_list)
    await db.commit()
    await db.refresh(batch)

    for pdf_bytes, filename in pdf_list:
        background_tasks.add_task(
            _transcribe_with_cap,
            pdf_bytes, filename, rubric_id, current_user.id, batch.id,
        )

    logger.info("batch_created", extra={
        "batch_id": str(batch.id),
        "test_count": len(pdf_list),
        "class_id": str(class_id) if class_id else None,
    })
    return BatchCreateResponse(batch_id=str(batch.id), test_count=len(pdf_list))


# ---------------------------------------------------------------------------
# GET /batches — list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BatchListItem])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchListItem]:
    """List all batches for the current user, newest first."""
    batches = (await db.execute(
        select(GradingBatch)
        .where(GradingBatch.user_id == current_user.id)
        .order_by(GradingBatch.created_at.desc())
    )).scalars().all()

    items = []
    for batch in batches:
        transcriptions = (await db.execute(
            select(Transcription).where(Transcription.batch_id == batch.id)
        )).scalars().all()
        graded_tests = (await db.execute(
            select(GradedTest).where(GradedTest.batch_id == batch.id)
        )).scalars().all()
        rollup = _build_rollup(batch, list(transcriptions), list(graded_tests))
        items.append(BatchListItem(
            id=batch.id,
            name=batch.name,
            rubric_id=batch.rubric_id,
            class_id=batch.class_id,
            status=_derive_batch_status(rollup),
            created_at=batch.created_at.isoformat(),
            rollup=rollup,
        ))
    return items


# ---------------------------------------------------------------------------
# GET /batches/{id} — detail + live roll-up
# ---------------------------------------------------------------------------

@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchDetailResponse:
    """
    Full batch detail with live roll-up and per-test triage.
    Poll target for both the transcription-review phase and the grading phase.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)

    transcriptions = (await db.execute(
        select(Transcription).where(Transcription.batch_id == batch_id)
    )).scalars().all()

    graded_tests = (await db.execute(
        select(GradedTest).where(GradedTest.batch_id == batch_id)
    )).scalars().all()

    # Index graded_tests by transcription_id for O(1) lookup
    gt_by_tid: dict[str, GradedTest] = {
        str(gt.transcription_id): gt for gt in graded_tests
    }

    # Load class roster for student auto-matching (empty if no class set)
    roster: list[Student] = []
    if batch.class_id:
        roster = list((await db.execute(
            select(Student)
            .join(ClassMembership, ClassMembership.student_id == Student.id)
            .where(ClassMembership.class_id == batch.class_id, Student.user_id == current_user.id)
            .order_by(Student.full_name)
        )).scalars().all())

    # Build per-test items
    test_items: list[BatchTranscriptionItem] = []
    for t in transcriptions:
        draft = TranscriptionDraft.model_validate(t.draft_json)
        student_match = match_student(draft.student_name_suggestion, roster)
        verdict: FlagVerdict = compute_flag_verdict(draft, student_match)
        gt = gt_by_tid.get(str(t.id))
        test_items.append(BatchTranscriptionItem(
            transcription_id=t.id,
            filename=t.filename,
            transcription_status=t.status,
            draft=draft,
            student_name_suggestion=draft.student_name_suggestion,
            matched_student_id=student_match.student_id,
            matched_student_name=student_match.student_name,
            flag_verdict=FlagVerdictResponse(
                review_needed=verdict.review_needed,
                reasons=verdict.reasons,
            ),
            graded_test_id=gt.id if gt else None,
            graded_test_status=gt.status if gt else None,
            total_score=str(gt.total_score) if gt and gt.total_score is not None else None,
            total_possible=str(gt.total_possible) if gt and gt.total_possible is not None else None,
        ))

    rollup = _build_rollup(batch, list(transcriptions), list(graded_tests))
    return BatchDetailResponse(
        id=batch.id,
        name=batch.name,
        rubric_id=batch.rubric_id,
        class_id=batch.class_id,
        status=_derive_batch_status(rollup),
        started_at=batch.started_at.isoformat() if batch.started_at else None,
        completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        created_at=batch.created_at.isoformat(),
        rollup=rollup,
        transcriptions=test_items,
    )


# ---------------------------------------------------------------------------
# POST /batches/{id}/accept_clean — bulk-accept clean transcriptions
# ---------------------------------------------------------------------------

@router.post("/{batch_id}/accept_clean")
async def accept_clean(
    batch_id: UUID,
    body: AcceptCleanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Bulk-accept clean transcriptions (no teacher edits needed).
    For each item:
      - Builds the contract from the transcription's draft answers (accepted as-is).
      - Updates the transcription to 'approved' with student assignment.
      - Inserts a pending GradedTest with batch_id.
      - Queues run_grading via the bounded semaphore.

    All items are committed in a single transaction.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    rubric = await db.get(Rubric, batch.rubric_id)

    queued = 0
    for item in body.items:
        transcription = await get_owned_or_404(
            db, Transcription, item.transcription_id, current_user.id
        )
        if transcription.batch_id != batch_id:
            raise HTTPException(400, f"Transcription {item.transcription_id} does not belong to batch {batch_id}")
        if transcription.status != "transcribed":
            continue    # already accepted; idempotent skip

        # Build contract from draft answers (clean accept = no edits)
        draft = TranscriptionDraft.model_validate(transcription.draft_json)
        contract = TranscriptionContract(
            answers=[
                TranscriptionContractAnswer(
                    question_number=a.question_number,
                    sub_question_id=a.sub_question_id,
                    answer_text=a.answer_text,
                )
                for a in draft.answers
            ]
        )

        student = await get_owned_or_404(db, Student, item.student_id, current_user.id)
        now = datetime.now(timezone.utc)

        # Atomic: approve transcription (satisfies CHECK constraint)
        transcription.contract_json = contract.model_dump(mode="json")
        transcription.student_id = student.id
        transcription.student_name = student.full_name
        transcription.status = "approved"
        transcription.approved_at = now
        transcription.updated_at = now

        # Insert pending graded_test with batch_id
        graded_test = GradedTest(
            user_id=current_user.id,
            rubric_id=batch.rubric_id,
            transcription_id=transcription.id,
            student_id=student.id,
            student_name=student.full_name,
            filename=transcription.filename,
            rubric_contract_version=batch.rubric_contract_version,
            status="pending",
            batch_id=batch_id,
        )
        db.add(graded_test)
        await db.flush()

        background_tasks.add_task(_grade_with_cap, graded_test.id)
        queued += 1

    await db.commit()
    logger.info("batch_accept_clean", extra={"batch_id": str(batch_id), "queued": queued})
    return {"accepted": queued}


# ---------------------------------------------------------------------------
# POST /batches/{id}/accept/{transcription_id} — accept one flagged test
# ---------------------------------------------------------------------------

@router.post("/{batch_id}/accept/{transcription_id}")
async def accept_one(
    batch_id: UUID,
    transcription_id: UUID,
    body: AcceptOneTranscriptionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Accept a single (possibly flagged) transcription with teacher-reviewed answers.
    Same commit pattern as accept_clean but uses the body's answers instead of
    pulling from draft_json, allowing the teacher to correct any detected issues.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    transcription = await get_owned_or_404(db, Transcription, transcription_id, current_user.id)

    if transcription.batch_id != batch_id:
        raise HTTPException(400, f"Transcription {transcription_id} does not belong to batch {batch_id}")
    if transcription.status != "transcribed":
        return {"accepted": 0, "message": "already accepted"}

    contract = TranscriptionContract(
        answers=[
            TranscriptionContractAnswer(
                question_number=a.question_number,
                sub_question_id=a.sub_question_id,
                answer_text=a.answer_text,
            )
            for a in body.answers
        ]
    )

    student = await get_owned_or_404(db, Student, body.student_id, current_user.id)
    now = datetime.now(timezone.utc)

    transcription.contract_json = contract.model_dump(mode="json")
    transcription.student_id = student.id
    transcription.student_name = student.full_name
    transcription.status = "approved"
    transcription.approved_at = now
    transcription.updated_at = now

    graded_test = GradedTest(
        user_id=current_user.id,
        rubric_id=batch.rubric_id,
        transcription_id=transcription.id,
        student_id=student.id,
        student_name=student.full_name,
        filename=transcription.filename,
        rubric_contract_version=batch.rubric_contract_version,
        status="pending",
        batch_id=batch_id,
    )
    db.add(graded_test)
    await db.flush()

    background_tasks.add_task(_grade_with_cap, graded_test.id)
    await db.commit()

    logger.info("batch_accept_one", extra={
        "batch_id": str(batch_id),
        "transcription_id": str(transcription_id),
    })
    return {"accepted": 1}
