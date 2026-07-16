"""
Transcription endpoints — S4.

POST /api/v0/transcriptions/transcribe  — upload PDF, VLM, persist draft
POST /api/v0/transcriptions/grade       — approve + create pending graded_tests row
"""
import logging
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ...database import get_db
from .auth import get_current_user
from ...api.deps import get_owned_or_404
from ...config import settings
from ...models.grading import GradedTest, Rubric
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.user import User
from ...schemas.transcription import (
    TranscriptionContract,
    TranscriptionContractAnswer,
    TranscriptionDraft,
)
from ...services.document_parser import image_to_base64
from ...services.gcs_service import get_gcs_service
from ...services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
    pdf_to_images,
)
from ...services.transcription_adapter import build_transcription_draft
from ...services.grading_runner import run_grading
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
        raise HTTPException(status_code=502, detail="שגיאה בתמלול — נסה שנית")

    # Reload the row (committed by transcribe_one) to build the response
    transcription = await db.get(Transcription, UUID(transcription_id))
    await db.refresh(transcription)
    draft = TranscriptionDraft.model_validate(transcription.draft_json)
    return TranscribeResponse(transcription_id=transcription_id, draft=draft)


@router.post("/grade", response_model=GradeQueuedResponse)
async def grade(
    body: GradeRequest,
    background_tasks: BackgroundTasks,
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

    # Fire async grading — runs after response is sent (S8).
    # run_grading owns its own DB session; it must not capture this one.
    background_tasks.add_task(run_grading, graded_test.id)

    logger.info(
        f"Transcription {transcription.id} approved → graded_test {graded_test.id} pending"
    )
    return GradeQueuedResponse(graded_test_id=str(graded_test.id))


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

    # 4. Render the requested page only at PAGE_RENDER_DPI
    try:
        images = await run_in_threadpool(pdf_to_images, pdf_bytes, PAGE_RENDER_DPI)
        if page_number > len(images):
            raise HTTPException(status_code=404, detail="Page not found")
        thumbnail_base64 = image_to_base64(images[page_number - 1])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"PDF render failed page={page_number}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="שגיאה בעיבוד הדף")

    return TranscriptionPageResponse(page_number=page_number, thumbnail_base64=thumbnail_base64)
