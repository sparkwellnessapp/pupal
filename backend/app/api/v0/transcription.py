"""
Transcription endpoints — S4.

POST /api/v0/transcriptions/transcribe  — upload PDF, VLM, persist draft
POST /api/v0/transcriptions/grade       — approve + create pending graded_tests row
"""
import logging
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ...database import get_db
from .auth import get_current_user
from ...api.deps import get_owned_or_404
from ...api.guards import ensure_answer_keys_match_draft
from ...config import settings
from ...models.grading import GradedTest, Rubric
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.user import User
from ...schemas.transcription import (
    AnswerSpaceSelectionGroup,
    TranscriptionContract,
    TranscriptionContractAnswer,
    TranscriptionDraft,
    TranscriptionReview,
    TranscriptionReviewAnswer,
)
from ...services.selection_expectation import answer_space_groups
from ...services.document_parser import image_to_base64
from ...services.gcs_service import get_gcs_service
from ...services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
    pdf_to_images,
    render_pdf_page,
)
from ...services.transcription_adapter import build_transcription_draft
from ...services.cloud_tasks_service import enqueue_grading_task_or_log
from ...services.transcribe_one import transcribe_one

logger = logging.getLogger(__name__)

PAGE_RENDER_DPI = 150  # DPI for per-page thumbnail rendering

router = APIRouter(prefix="/api/v0/transcriptions", tags=["transcriptions"])


# ---------------------------------------------------------------------------
# Request / Response shapes
# ---------------------------------------------------------------------------

class TranscribeResponse(BaseModel):
    transcription_id: str
    draft: TranscriptionDraft
    # Rubric selection groups in answer space — the review surface suppresses
    # expected-empty containers on "choose k of N" exams. [] when selection-free.
    selection_groups: list[AnswerSpaceSelectionGroup] = []


class GradeAnswerInput(BaseModel):
    question_number: int
    sub_question_id: str | None = None
    answer_text: str


class GradeRequest(BaseModel):
    transcription_id: UUID
    answers: list[GradeAnswerInput]
    student_id: UUID


class GradeQueuedResponse(BaseModel):
    graded_test_id: str
    status: str = "pending"


class ReviewSaveRequest(BaseModel):
    """Full-snapshot review save. `answers` reuses the /grade answer shape."""
    answers: list[GradeAnswerInput]
    student_id: UUID | None = None


class TranscriptionPageResponse(BaseModel):
    page_number: int
    thumbnail_base64: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(..., description="Student test PDF"),
    rubric_id: UUID = Form(..., description="Compiled rubric to grade against"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    """
    Single-test transcription. Delegates to transcribe_one() (shared with batch path).
    Ownership + compiled checks happen here in request context; the heavy work
    (VLM + GCS + DB) runs inside transcribe_one's own session.
    """
    # Ownership + compiled check (in request context where Depends(get_db) lives)
    rubric = await get_owned_or_404(db, Rubric, rubric_id, current_user.id)
    if not rubric.is_compiled:
        raise HTTPException(
            status_code=400,
            detail="המחוון לא עבר קומפילציה — יש להשלים אותו לפני בדיקת מבחנים",
        )
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Answer-space selection groups for the review surface (pure; computed
    # while the rubric row is loaded, before the session is released).
    selection_groups = answer_space_groups(rubric.contract_json)

    # Release the connection for the 60-90s transcription (transcribe_one owns
    # its own short-lived sessions): an idle-in-transaction connection here
    # gets reset by the Supabase pooler and the post-pipeline reload would 502
    # a transcription that actually succeeded. The db.get below transparently
    # re-acquires a fresh pooled connection (pool_pre_ping revalidates).
    await db.close()

    try:
        transcription_id = await transcribe_one(
            pdf_bytes=pdf_bytes,
            filename=file.filename,
            rubric_id=rubric_id,
            user_id=current_user.id,
            batch_id=None,
        )
    except Exception as exc:
        logger.error(f"transcribe_one failed: {exc}", exc_info=True)
        from ...services.net_diag import diagnose_transport_failure
        await diagnose_transport_failure(f"single-flow transcription of {file.filename}", exc)
        raise HTTPException(status_code=502, detail="שגיאה בתמלול — נסה שנית")

    # Reload the row (committed by transcribe_one) to build the response
    transcription = await db.get(Transcription, UUID(transcription_id))
    await db.refresh(transcription)
    draft = TranscriptionDraft.model_validate(transcription.draft_json)
    return TranscribeResponse(
        transcription_id=transcription_id,
        draft=draft,
        selection_groups=selection_groups,
    )


@router.post("/grade", response_model=GradeQueuedResponse)
async def grade(
    body: GradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GradeQueuedResponse:
    # 1. Auth + ownership checks
    transcription = await get_owned_or_404(
        db, Transcription, body.transcription_id, current_user.id
    )
    if transcription.status != "transcribed":
        raise HTTPException(status_code=409, detail="התמלול כבר אושר")

    student = await get_owned_or_404(db, Student, body.student_id, current_user.id)

    # 2. Load rubric to pin contract_version at INSERT time (VER-2)
    rubric = await get_owned_or_404(db, Rubric, transcription.rubric_id, current_user.id)

    # 3. Build frozen contract from teacher-submitted answers
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

    now = datetime.now(timezone.utc)

    # 4. Atomic: UPDATE transcription + INSERT graded_tests in one commit (IDN-3)
    transcription.contract_json = contract.model_dump(mode="json")
    transcription.student_id = student.id
    transcription.student_name = student.full_name   # denormalized from validated record
    transcription.status = "approved"
    transcription.approved_at = now
    transcription.updated_at = now
    # The review overlay's job ends at approval. Nulling it here is part of the
    # 'transcribed'→'approved' TRANSITION write, not a mutation of an approved
    # row — LCY-1 untouched. After this commit the PATCH /review path 409s.
    transcription.review_json = None

    graded_test = GradedTest(
        user_id=current_user.id,
        rubric_id=transcription.rubric_id,
        transcription_id=transcription.id,
        student_id=student.id,
        student_name=student.full_name,             # denormalized
        filename=transcription.filename,
        rubric_contract_version=rubric.contract_version,  # pinned now per VER-2
        status="pending",
        draft_json=None,        # populated in S8
        contract_json=None,
        regraded_from_id=None,  # chain head
        regraded_to_id=None,    # current leaf
    )
    db.add(graded_test)

    await db.commit()
    await db.refresh(graded_test)
    graded_test_id = graded_test.id
    # Release the connection before the enqueue round-trip (idempotent;
    # teardown no-ops — the 2026-08-07 pooler discipline).
    await db.close()

    # Cloud Tasks migration: enqueue AFTER commit; the handler claims the
    # pending row by CAS. An enqueue failure leaves a durable pending row —
    # grading_job_liveness's dispatch backstop reaps it → revision-retry.
    await enqueue_grading_task_or_log(graded_test_id)

    logger.info(
        f"Transcription {transcription.id} approved → graded_test {graded_test.id} pending"
    )
    return GradeQueuedResponse(graded_test_id=str(graded_test.id))


@router.patch("/{transcription_id}/review", response_model=TranscriptionReview)
async def save_review(
    transcription_id: UUID,
    body: ReviewSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TranscriptionReview:
    """
    Persist the teacher's review working copy (transcriptions.review_json).

    Rules (batch-review plan, Δ2/Δ3/Δ16):
      * Allowed only while status='transcribed' — 409 otherwise (LCY-1: an
        approved transcription is read-only; the overlay is nulled at approval).
      * FULL SNAPSHOT: the body's (question_number, sub_question_id) key
        multiset must exactly equal the draft's — 422 on mismatch, never
        silently normalized/filled/pruned.
      * A non-null student_id is ownership-validated NOW (cross-tenant → 404,
        §9), not left to detonate at accept.
      * Concurrency: last-write-wins. Two tabs saving concurrently is accepted;
        the later write replaces the earlier whole-snapshot.
      * Approval stays body-authoritative — accept endpoints never read this
        overlay; it exists so edits survive navigation/refresh.
    """
    # 1. Ownership + lifecycle guards
    transcription = await get_owned_or_404(
        db, Transcription, transcription_id, current_user.id
    )
    if transcription.status != "transcribed":
        raise HTTPException(
            status_code=409, detail="התמלול כבר אושר — לא ניתן לשמור שינויים"
        )

    # 2. Full-snapshot guard: key multiset must equal the draft's exactly.
    # Shared with accept_one (B2, api/guards.py) — the approval write must
    # never validate less than this overlay save.
    draft = TranscriptionDraft.model_validate(transcription.draft_json)
    ensure_answer_keys_match_draft(draft, body.answers)

    # 3. Student ownership at write time (Δ16) — same check /grade performs.
    if body.student_id is not None:
        await get_owned_or_404(db, Student, body.student_id, current_user.id)

    # 4. Full-snapshot write, server-stamped.
    now = datetime.now(timezone.utc)
    review = TranscriptionReview(
        answers=[
            TranscriptionReviewAnswer(
                question_number=a.question_number,
                sub_question_id=a.sub_question_id,
                answer_text=a.answer_text,
            )
            for a in body.answers
        ],
        student_id=str(body.student_id) if body.student_id is not None else None,
        updated_at=now.isoformat(),
    )
    transcription.review_json = review.model_dump(mode="json")
    transcription.updated_at = now
    await db.commit()
    return review


@router.get("/{transcription_id}/pages/{page_number}", response_model=TranscriptionPageResponse)
async def get_transcription_page(
    transcription_id: UUID,
    page_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TranscriptionPageResponse:
    # 1. Ownership guard
    transcription = await get_owned_or_404(db, Transcription, transcription_id, current_user.id)

    # 2. Range check against draft_json page_count (fast path — no GCS needed)
    page_count = (transcription.draft_json or {}).get("page_count", 0)
    if not (1 <= page_number <= page_count):
        raise HTTPException(status_code=404, detail="Page not found")

    # 3. Fetch PDF from GCS (backend-to-backend; no CORS issue)
    gcs = get_gcs_service()
    try:
        pdf_bytes = await run_in_threadpool(gcs.download_bytes, transcription.gcs_object_path)
    except Exception as exc:
        logger.error(f"GCS download failed for {transcription.gcs_object_path}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="שגיאה בטעינת הקובץ")

    # 4. Render ONLY the requested page at PAGE_RENDER_DPI (Phase 1.5 — the
    # previous code rasterized the whole PDF per request, so a full review of
    # an N-page test cost N² page renders).
    try:
        image = await run_in_threadpool(
            render_pdf_page, pdf_bytes, page_number, PAGE_RENDER_DPI
        )
        thumbnail_base64 = image_to_base64(image)
    except ValueError:
        # draft page_count can exceed the actual PDF — same guard the
        # full-render path had via len(images).
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as exc:
        logger.error(f"PDF render failed page={page_number}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="שגיאה בעיבוד הדף")

    return TranscriptionPageResponse(page_number=page_number, thumbnail_base64=thumbnail_base64)
