"""
Rubric Generator API endpoints.

Endpoints for the rubric generator feature:
- Upload PDF for question detection
- Stream question detection
- Generate criteria for questions
- Regenerate single question
- Create annotated PDF
- Share rubric via email
- Accept shared rubric
- Get share history
"""
import logging
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, Body, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, EmailStr

from ...database import get_db
from ...config import settings
from ...models.grading import Rubric
from ...models.user import User
from ...models.rubric_share import RubricShareToken, RubricShareHistory
from ...services.temp_storage_service import get_temp_storage
from ...services.rubric_generator_service import (
    detect_questions_stream,
    generate_full_rubric,
    regenerate_single_question,
    DetectedQuestion,
    GenerateCriteriaRequest,
)
from ...services.rubric_pdf_generator import generate_annotated_rubric_pdf
from ...services.email_service import send_rubric_share_email, get_email_service
from ...services.gcs_service import get_gcs_service
from ...services.rubric_service import save_rubric as save_rubric_to_db, get_rubric_by_id
from ...schemas.grading import (
    ExtractRubricResponse,
    ExtractedQuestion,
    SaveRubricRequest,
)
from ...utils.rate_limiter import check_ai_rate_limit
from .auth import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/rubric_generator", tags=["rubric_generator"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class UploadPdfResponse(BaseModel):
    """Response from PDF upload."""
    upload_id: str
    page_count: int
    file_size_mb: float


class DetectedQuestionResponse(BaseModel):
    """A detected question."""
    question_number: int
    question_text: str
    page_indexes: List[int] = []
    sub_questions: List[str] = []
    suggested_points: Optional[float] = None


class GenerateCriteriaRequestSchema(BaseModel):
    """Request to generate criteria for questions."""
    questions: List[DetectedQuestion]
    rubric_name: Optional[str] = None
    rubric_description: Optional[str] = None
    programming_language: Optional[str] = None


class RegenerateQuestionRequestSchema(BaseModel):
    """Request to regenerate a single question."""
    question_number: int
    question_text: str
    sub_questions: List[str] = []
    total_points: float
    programming_language: Optional[str] = None


class CreatePdfRequest(BaseModel):
    """Request to create annotated PDF."""
    rubric_id: Optional[UUID] = None
    questions: Optional[List[dict]] = None  # If not using saved rubric
    include_original: bool = False
    original_pdf_upload_id: Optional[str] = None


class CreatePdfResponse(BaseModel):
    """Response from PDF creation."""
    download_url: str
    filename: str


class ShareEmailRequest(BaseModel):
    """Request to share rubric via email."""
    rubric_id: UUID
    recipient_email: EmailStr
    include_pdf: bool = True
    sender_name: str


class ShareEmailResponse(BaseModel):
    """Response from email sharing."""
    success: bool
    message: str
    share_id: Optional[UUID] = None


class AcceptShareResponse(BaseModel):
    """Response from accepting a share."""
    success: bool
    message: str
    rubric_id: Optional[UUID] = None
    redirect_url: Optional[str] = None


class ShareHistoryItem(BaseModel):
    """A share history entry."""
    id: UUID
    recipient_email: str
    shared_at: datetime
    status: str  # "pending", "accepted", "revoked"
    accepted_at: Optional[datetime] = None


class ShareHistoryResponse(BaseModel):
    """Response with share history."""
    shares: List[ShareHistoryItem]
    total_count: int


# =============================================================================
# Upload Endpoint
# =============================================================================

@router.post(
    "/upload",
    response_model=UploadPdfResponse,
    summary="Upload PDF for rubric generation",
    description="Upload a PDF containing exam questions. Returns upload_id for subsequent detection.",
)
async def upload_pdf_for_generation(
    file: UploadFile = File(..., description="PDF file containing exam questions"),
) -> UploadPdfResponse:
    """
    Upload PDF and validate before detection.
    
    Validations:
    - File type: PDF only
    - File size: Max 25MB
    """
    # Validate content type
    if not file.content_type or not file.content_type.endswith("pdf"):
        raise HTTPException(status_code=400, detail="הקובץ חייב להיות PDF")
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="שגיאה בקריאת הקובץ")
    
    # Store in temp storage (validates size and format)
    try:
        temp_storage = get_temp_storage()
        upload_id = await temp_storage.store_pdf(content, file.filename or "upload.pdf")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to store PDF: {e}")
        raise HTTPException(status_code=500, detail="שגיאה בשמירת הקובץ")
    
    # Get page count
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        page_count = len(doc)
        doc.close()
    except Exception as e:
        logger.warning(f"Failed to get page count: {e}")
        page_count = 0
    
    file_size_mb = len(content) / (1024 * 1024)
    
    logger.info(f"PDF uploaded: upload_id={upload_id}, pages={page_count}, size={file_size_mb:.2f}MB")
    
    return UploadPdfResponse(
        upload_id=upload_id,
        page_count=page_count,
        file_size_mb=round(file_size_mb, 2),
    )


# =============================================================================
# Question Detection Endpoint (SSE)
# =============================================================================

@router.get(
    "/detect_questions/{upload_id}",
    summary="Stream question detection",
    description="SSE stream of question detection events. Supports reconnection with lastEventId.",
)
async def detect_questions_endpoint(
    upload_id: str,
    lastEventId: Optional[str] = Query(None, description="Last event ID for reconnection"),
):
    """
    SSE stream of question detection events.
    
    Events:
    - progress: {"type": "progress", "message": "..."}
    - question: {"type": "question", "data": {...}}
    - complete: {"type": "complete", "data": {"total_questions": N}}
    - error: {"type": "error", "message": "..."}
    """
    # Get PDF from temp storage
    temp_storage = get_temp_storage()
    pdf_bytes = await temp_storage.get_pdf(upload_id)
    
    if not pdf_bytes:
        async def error_stream():
            yield f'data: {json.dumps({"type": "error", "message": "הקובץ לא נמצא או פג תוקף. אנא העלה שוב."})}\n\n'
        
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    # Parse lastEventId for resume
    skip_until = 0
    if lastEventId:
        try:
            skip_until = int(lastEventId)
        except ValueError:
            pass
    
    async def event_stream():
        async for event in detect_questions_stream(pdf_bytes):
            # Skip already-sent events on reconnect
            if event.event_id <= skip_until:
                continue
            
            event_data = {
                "type": event.type,
            }
            if event.data:
                event_data["data"] = event.data
            if event.message:
                event_data["message"] = event.message
            
            yield f"id: {event.event_id}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# =============================================================================
# Criteria Generation Endpoints
# =============================================================================

@router.post(
    "/generate_criteria",
    response_model=ExtractRubricResponse,
    summary="Generate criteria for questions",
    description="Generate rubric criteria with reduction rules for all provided questions.",
    dependencies=[Depends(check_ai_rate_limit)],
)
async def generate_criteria_endpoint(
    request: GenerateCriteriaRequestSchema = Body(...),
) -> ExtractRubricResponse:
    """
    Generate criteria for all questions in parallel.
    
    Each question should have teacher_points set (or will use suggested_points).
    """
    if not request.questions:
        raise HTTPException(status_code=400, detail="חייב לספק לפחות שאלה אחת")
    
    logger.info(f"Generating criteria for {len(request.questions)} questions")
    
    try:
        response = await generate_full_rubric(
            questions=request.questions,
            rubric_name=request.rubric_name,
            rubric_description=request.rubric_description,
            programming_language=request.programming_language,
        )
        return response
    except Exception as e:
        logger.error(f"Criteria generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת הקריטריונים: {str(e)}")


@router.post(
    "/regenerate_question",
    response_model=ExtractedQuestion,
    summary="Regenerate criteria for one question",
    description="Regenerate criteria for a single question without affecting others.",
    dependencies=[Depends(check_ai_rate_limit)],
)
async def regenerate_question_endpoint(
    request: RegenerateQuestionRequestSchema = Body(...),
) -> ExtractedQuestion:
    """
    Regenerate criteria for a single question.
    Used when teacher clicks "refresh" on one question.
    """
    try:
        result = await regenerate_single_question(
            question_number=request.question_number,
            question_text=request.question_text,
            sub_questions=request.sub_questions,
            total_points=request.total_points,
            programming_language=request.programming_language,
        )
        return result
    except Exception as e:
        logger.error(f"Question regeneration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה ברענון השאלה: {str(e)}")


# =============================================================================
# PDF Generation Endpoint
# =============================================================================

@router.post(
    "/create_pdf",
    response_model=CreatePdfResponse,
    summary="Create annotated rubric PDF",
    description="Generate a PDF with rubric tables for all questions.",
)
async def create_pdf_endpoint(
    request: CreatePdfRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> CreatePdfResponse:
    """
    Generate annotated PDF with rubric tables.
    """
    # Get questions from rubric or request
    questions_data = []
    rubric_name = "rubric"
    
    if request.rubric_id:
        rubric = await get_rubric_by_id(db, request.rubric_id)
        if not rubric:
            raise HTTPException(status_code=404, detail="מחוון לא נמצא")
        questions_data = rubric.rubric_json.get("questions", [])
        rubric_name = rubric.name or f"rubric_{rubric.id}"
    elif request.questions:
        questions_data = request.questions
    else:
        raise HTTPException(status_code=400, detail="חייב לספק rubric_id או questions")
    
    # Get original PDF if requested
    original_pdf = None
    if request.include_original and request.original_pdf_upload_id:
        temp_storage = get_temp_storage()
        original_pdf = await temp_storage.get_pdf(request.original_pdf_upload_id)
    
    # Generate PDF
    try:
        pdf_bytes = await generate_annotated_rubric_pdf(original_pdf, questions_data)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת ה-PDF: {str(e)}")
    
    # Upload to GCS for download
    try:
        gcs = get_gcs_service()
        filename = f"{rubric_name}_rubric.pdf"
        gcs_path = f"generated_rubrics/{uuid4()}/{filename}"
        
        gcs.upload_bytes(pdf_bytes, gcs_path, content_type="application/pdf")
        download_url = gcs.generate_signed_url(gcs_path, expiration_minutes=24 * 60)  # 24 hours
        
        return CreatePdfResponse(
            download_url=download_url,
            filename=filename,
        )
    except Exception as e:
        logger.error(f"GCS upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="שגיאה בהעלאת הקובץ")


# =============================================================================
# Share Endpoints
# =============================================================================

@router.post(
    "/share_email",
    response_model=ShareEmailResponse,
    summary="Share rubric via email",
    description="Send rubric share email with download link and Vivi invite.",
)
async def share_email_endpoint(
    request: ShareEmailRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareEmailResponse:
    """
    Share rubric via email.
    
    Creates a share token, generates PDF, and sends email.
    """
    # Get rubric
    rubric = await get_rubric_by_id(db, request.rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="מחוון לא נמצא")
    
    rubric_name = rubric.name or "מחוון ללא שם"
    
    # Generate PDF if requested
    generated_pdf_path = None
    download_url = None
    
    if request.include_pdf:
        try:
            questions_data = rubric.rubric_json.get("questions", [])
            pdf_bytes = await generate_annotated_rubric_pdf(None, questions_data)
            
            # Upload to GCS
            gcs = get_gcs_service()
            gcs_path = f"shared_rubrics/{request.rubric_id}/{secrets.token_hex(8)}.pdf"
            gcs.upload_bytes(pdf_bytes, gcs_path, content_type="application/pdf")
            
            generated_pdf_path = gcs_path
            download_url = gcs.generate_signed_url(gcs_path, expiration_hours=24 * 30)  # 30 days
        except Exception as e:
            logger.error(f"PDF generation for share failed: {e}")
            # Continue without PDF
    
    # Create share token
    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    share_token = RubricShareToken(
        token=token,
        rubric_id=request.rubric_id,
        sender_user_id=current_user.id,
        recipient_email=request.recipient_email,
        expires_at=expires_at,
        generated_pdf_gcs_path=generated_pdf_path,
    )
    
    db.add(share_token)
    
    # Create share history entry
    history_entry = RubricShareHistory(
        rubric_id=request.rubric_id,
        sender_user_id=current_user.id,
        recipient_email=request.recipient_email,
        share_token_id=share_token.id,
    )
    db.add(history_entry)
    
    await db.commit()
    await db.refresh(share_token)
    
    # Generate URLs
    base_url = settings.frontend_base_url
    invite_url = f"{base_url}/signup?share_token={token}"
    
    if not download_url:
        download_url = f"{base_url}/api/v0/rubric_generator/share_download/{token}"
    
    # Send email
    try:
        email_service = get_email_service()
        if not email_service.is_configured():
            logger.warning("Email service not configured - skipping email send")
            return ShareEmailResponse(
                success=True,
                message="המחוון נשמר לשיתוף, אך שליחת המייל כרגע לא זמינה",
                share_id=share_token.id,
            )
        
        result = await send_rubric_share_email(
            recipient_email=request.recipient_email,
            sender_name=request.sender_name,
            rubric_name=rubric_name,
            download_url=download_url,
            invite_url=invite_url,
        )
        
        if result.success:
            return ShareEmailResponse(
                success=True,
                message=f"המחוון נשלח בהצלחה ל-{request.recipient_email}",
                share_id=share_token.id,
            )
        else:
            return ShareEmailResponse(
                success=False,
                message=result.error or "שגיאה בשליחת המייל",
                share_id=share_token.id,
            )
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return ShareEmailResponse(
            success=False,
            message="שגיאה בשליחת המייל",
            share_id=share_token.id,
        )


@router.get(
    "/share_download/{token}",
    summary="Download shared rubric PDF",
    description="Download the PDF for a shared rubric. No login required.",
)
async def share_download_endpoint(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Download PDF for a shared rubric.
    Token is NOT consumed - user can still accept share later.
    """
    # Find token
    result = await db.execute(
        select(RubricShareToken).where(RubricShareToken.token == token)
    )
    share_token = result.scalar_one_or_none()
    
    if not share_token:
        raise HTTPException(status_code=404, detail="קישור לא תקין")
    
    if share_token.is_expired:
        raise HTTPException(status_code=410, detail="הקישור פג תוקף. בקש מהשולח לשתף שוב.")
    
    if not share_token.generated_pdf_gcs_path:
        raise HTTPException(status_code=404, detail="ה-PDF לא זמין")
    
    # Generate signed URL and redirect
    try:
        gcs = get_gcs_service()
        download_url = gcs.generate_signed_url(share_token.generated_pdf_gcs_path, expiration_hours=1)
        return RedirectResponse(url=download_url)
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail="שגיאה בהורדת הקובץ")


@router.get(
    "/accept_share/{token}",
    response_model=AcceptShareResponse,
    summary="Accept shared rubric",
    description="Accept a shared rubric and copy it to your account.",
)
async def accept_share_endpoint(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Accept a shared rubric (copy to user's account).
    
    If user is logged in, copies rubric immediately.
    If not logged in, returns redirect to login page with token.
    """
    # Find token
    result = await db.execute(
        select(RubricShareToken).where(RubricShareToken.token == token)
    )
    share_token = result.scalar_one_or_none()
    
    if not share_token:
        return AcceptShareResponse(
            success=False,
            message="קישור לא תקין",
        )
    
    if share_token.is_expired:
        return AcceptShareResponse(
            success=False,
            message="הקישור פג תוקף. בקש מהשולח לשתף שוב.",
        )
    
    if not current_user:
        # Redirect to login/signup with token
        base_url = settings.frontend_base_url
        return AcceptShareResponse(
            success=True,
            message="יש להתחבר כדי לקבל את המחוון",
            redirect_url=f"{base_url}/login?share_token={token}",
        )
    
    # Check if already accepted
    if share_token.is_accepted:
        return AcceptShareResponse(
            success=True,
            message="המחוון כבר נוסף לחשבונך!",
            rubric_id=share_token.copied_rubric_id,
            redirect_url=f"/my-rubrics?shared={share_token.copied_rubric_id}",
        )
    
    # User is logged in - copy the rubric
    original_rubric = await get_rubric_by_id(db, share_token.rubric_id)
    if not original_rubric:
        return AcceptShareResponse(
            success=False,
            message="המחוון המקורי לא נמצא",
        )
    
    # Create copy with user ownership
    copied_rubric = Rubric(
        rubric_json=original_rubric.rubric_json,
        name=f"{original_rubric.name or 'מחוון'} (משותף)",
        description=original_rubric.description,
        total_points=original_rubric.total_points,
        user_id=current_user.id,
    )
    db.add(copied_rubric)
    await db.flush()  # Get the ID
    
    # Update token
    share_token.accepted_at = datetime.utcnow()
    share_token.copied_rubric_id = copied_rubric.id
    
    # Update history
    result = await db.execute(
        select(RubricShareHistory).where(RubricShareHistory.share_token_id == share_token.id)
    )
    history = result.scalar_one_or_none()
    if history:
        history.accepted_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(f"User {current_user.email} accepted shared rubric {share_token.rubric_id} -> {copied_rubric.id}")
    
    return AcceptShareResponse(
        success=True,
        message="המחוון נוסף בהצלחה למחוונים שלך!",
        rubric_id=copied_rubric.id,
        redirect_url=f"/my-rubrics?shared={copied_rubric.id}",
    )


@router.get(
    "/share_history/{rubric_id}",
    response_model=ShareHistoryResponse,
    summary="Get share history for a rubric",
    description="Get list of all shares for a rubric. Only owner can view.",
)
async def get_share_history_endpoint(
    rubric_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareHistoryResponse:
    """
    Get share history for a rubric.
    """
    # Verify rubric exists
    rubric = await get_rubric_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="מחוון לא נמצא")
    
    # Verify ownership (skip if rubric has no user_id for legacy data)
    if rubric.user_id and rubric.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="אין הרשאה לצפות בהיסטוריה")
    
    # Get history
    result = await db.execute(
        select(RubricShareHistory)
        .where(RubricShareHistory.rubric_id == rubric_id)
        .order_by(RubricShareHistory.shared_at.desc())
    )
    history_entries = result.scalars().all()
    
    shares = [
        ShareHistoryItem(
            id=h.id,
            recipient_email=h.recipient_email,
            shared_at=h.shared_at,
            status=h.status,
            accepted_at=h.accepted_at,
        )
        for h in history_entries
    ]
    
    return ShareHistoryResponse(
        shares=shares,
        total_count=len(shares),
    )
