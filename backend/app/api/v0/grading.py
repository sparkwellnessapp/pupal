"""
Grading API endpoints - v0.

Endpoints for rubric extraction (DOCX) and graded test retrieval.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, Form
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_owned_or_404
from ...config import settings
from ...database import get_db
from ...models.grading import GradedTest, GradingBatch, Rubric
from ...models.transcription import Transcription
from ...models.user import User
from ...schemas.graded_test_contract import GradedTestContract
from ...schemas.graded_test_draft import (
    GradedTestDraft, GradedTestOverrides, StampPosition,
)
from ...schemas.graded_test_responses import (
    GradedTestApprovedResponse,
    GradedTestDraftResponse,
    GradedTestFailedResponse,
    GradedTestListItem,
    GradedTestStatusResponse,
)
from ...schemas.ontology_types import GradingRubricContract, NumericPolicy
from ...services.graded_test_contract_compiler import GateError, compile_graded_test
from ...services.gcs_service import get_gcs_service
from ...services.graded_test_revision import extend_chain
from ...services.returned_exam import (
    OVERLAY_KEY,
    current_cache_key,
    effective_stamp_position,
    gcs_object_path,
    render_returned_exam,
    scopes_for_render,
    summary_for_render,
)
from ...services.cloud_tasks_service import enqueue_grading_task_or_log, verify_task_request
from .auth import get_current_user


# ---------------------------------------------------------------------------
# S9 request bodies
# ---------------------------------------------------------------------------

class SaveDraftRequest(BaseModel):
    overrides: GradedTestOverrides
    # [PR-G5] What the CLIENT priced from the same overlay. Optional: an older
    # client simply does not send it and gets no mismatch signal.
    client_totals: Optional[Dict[str, Decimal]] = None


class SaveStampPositionRequest(BaseModel):
    """[OD-1] `null` clears the position, so the test falls back to the batch
    default (or the auto corner). `source` on the way in is IGNORED — the server
    sets "manual"; see the endpoint's docstring."""
    stamp_position: Optional[StampPosition] = None


class StampPositionResponse(BaseModel):
    id: UUID
    status: str
    stamp_position: Optional[StampPosition] = None
    # Always "stale" on a successful move: the render cached under the old
    # position is no longer what she would sign.
    returned_exam_state: Literal["none", "rendering", "ready", "stale"] = "stale"


class ApproveRequest(BaseModel):
    overrides: GradedTestOverrides
    # [PR-G5] The total the teacher SAW. If the server prices differently, the
    # approval is refused with an ERROR annotation — never a silent server win,
    # because freezing a number she never reviewed is the §5 catastrophe.
    client_total: Optional[Decimal] = None
from ...services.pdf_preview_service import generate_pdf_previews
from ...services.document_parser import (
    pdf_to_images,
    image_to_base64,
    extract_student_name_from_page,
)
# Ontology types (single source of truth)
from ...schemas.ontology_types import ExtractRubricResponse as OntologyExtractRubricResponse
from ...schemas.grading import (
    # Preview schemas
    PagePreview,
    PreviewStudentTestResponse,
    # Rubric retrieval
    RubricResponse,
    # Error
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/grading", tags=["grading"])


# =============================================================================
# Rubric Endpoints
# =============================================================================

# =============================================================================
# DOCX Rubric Extraction (v3 Pipeline)
# =============================================================================

@router.post(
    "/extract_rubric_docx",
    response_model=OntologyExtractRubricResponse,
    responses={
        200: {"description": "Extraction successful"},
        400: {"model": ErrorResponse}, 
        500: {"model": ErrorResponse},
    },
    summary="Extract rubric from DOCX file (DEPRECATED — use extraction jobs)",
    description="""
    **DEPRECATED (PR-1):** superseded by the async job flow —
    `POST /api/v0/rubrics/extraction-jobs/` + poll. This endpoint holds the
    HTTP request open for the full extraction and is killed by Cloud Run's
    request timeout on long documents. It remains only until the frontend is
    fully cut over; removal is a later cleanup.

    Extract rubric from a Word document (.docx) using AI-powered structured extraction.

    Returns an ExtractRubricResponse with questions, sub-questions, and criteria
    ready for teacher review in the RubricEditor.

    **Auto-save Mode (auto_save=true):**
    - Saves the extraction result as a draft in the database
    - Returns metadata including `rubric_id` for subsequent editing and compilation

    **Manual Mode (auto_save=false, default):**
    - Returns extraction result only
    - Call `POST /rubrics/save_ontology_draft` to save manually
    """,
    deprecated=True,
)
async def extract_rubric_docx(
    file: UploadFile = File(..., description="Rubric DOCX file"),
    name: Optional[str] = Query(None, description="Optional name for the rubric"),
    description: Optional[str] = Query(None, description="Optional description"),
    subject: Optional[str] = Query("computer_science", description="Subject domain"),
    locale: Optional[str] = Query("he-IL", description="Document locale"),
    auto_save: bool = Query(False, description="Auto-save extraction to database as draft"),
    test_topic: Optional[str] = Form(None, description="Teacher-provided test topic"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract rubric from DOCX using v3 pipeline."""
    from ...schemas.rubric_management import (
        ExtractionMetadata,
        ExtractionNextSteps,
        OntologyExtractionResponse,
    )
    from ...services.rubric_management_service import save_ontology_draft
    
    try:
        # Validate file type
        filename_raw = (file.filename or "").lower()
        if not filename_raw.endswith('.docx'):
            raise HTTPException(status_code=400, detail="File must be a DOCX document.")
        
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        logger.info(f"[v3] Extracting: {file.filename}, {len(file_bytes)} bytes, subject={subject}")
        
        # Import v3 pipeline
        from ...services.docx_v3.pipeline import (
            extract_rubric_from_docx as docx_extract,
            ExtractionConfig,
        )
        
        config = ExtractionConfig(
            subject=subject or "computer_science",
            locale=locale or "he-IL",
        )
        
        rubric_name = name or (file.filename or "rubric").replace('.docx', '').replace('.DOCX', '')
        
        result = await docx_extract(
            file_bytes=file_bytes,
            extraction_config=config,
            name=rubric_name,
            description=description,
            test_topic=test_topic or None,
        )
        
        extraction_response = result.response
        if extraction_response is None:
            raise HTTPException(status_code=500, detail="Extraction produced no result")
        
        logger.info(f"[v3] Extraction successful: {len(extraction_response.questions)} questions")
        
        # Auto-save if requested
        if auto_save:
            try:
                extraction_dict = extraction_response.model_dump(mode='json')
                save_result = await save_ontology_draft(
                    db=db,
                    name=rubric_name,
                    draft=extraction_dict,
                    description=description,
                    user_id=current_user.id,
                )
                rubric_id = save_result.rubric_id
                logger.info(f"[v3] Auto-saved as rubric {rubric_id}")
                
                return OntologyExtractionResponse(
                    extraction_result=extraction_dict,
                    metadata=ExtractionMetadata(
                        rubric_id=rubric_id,
                        was_auto_saved=True,
                        needs_compilation_before_grading=True,
                        next_steps=ExtractionNextSteps(
                            action="compile",
                            endpoint=f"/api/v0/rubrics/{rubric_id}/compile",
                            warnings_preview=[],
                        ),
                    ),
                    stats=save_result.stats,
                )
            except Exception as save_error:
                logger.warning(f"[v3] Auto-save failed: {save_error}")
        
        return extraction_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v3] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error extracting rubric: {str(e)}")


@router.post(
    "/extract-rubric-v2",
    response_model=OntologyExtractRubricResponse,
    responses={
        200: {"description": "Extraction successful"},
        400: {"model": ErrorResponse}, 
        500: {"model": ErrorResponse},
    },
    summary="Universal rubric extraction (DOCX)",
    description="""
    Extract rubric from a DOCX file. This is the recommended endpoint for new integrations.
    
    Auto-detects file type. Only DOCX files are supported.
    
    **Auto-save Mode:**
    When `auto_save=true`, the extracted rubric is saved as a draft and the response
    includes `rubric_id` for subsequent editing and compilation.
    """,
)
async def extract_rubric_v2(
    file: UploadFile = File(..., description="Rubric file (DOCX)"),
    name: Optional[str] = Form(None, description="Optional name for the rubric"),
    description: Optional[str] = Form(None, description="Optional description"),
    auto_save: bool = Form(False, description="Auto-save extraction to database as draft"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Universal rubric extraction â€" routes to DOCX v3 pipeline."""
    from ...schemas.rubric_management import (
        ExtractionMetadata,
        ExtractionNextSteps,
        OntologyExtractionResponse,
    )
    from ...services.rubric_management_service import save_ontology_draft
    
    try:
        filename = (file.filename or "").lower()
        file_bytes = await file.read()
        
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        if not filename.endswith('.docx'):
            raise HTTPException(
                status_code=400, 
                detail=f"Only DOCX files are supported. Got: {filename}"
            )
        
        # Use v3 pipeline
        from ...services.docx_v3.pipeline import (
            extract_rubric_from_docx as docx_extract,
            ExtractionConfig,
        )
        
        logger.info(f"[v2/v3] Extracting: {file.filename}, auto_save={auto_save}")
        
        config = ExtractionConfig(subject="computer_science", locale="he-IL")
        rubric_name = name or (file.filename or "rubric").replace('.docx', '').replace('.DOCX', '')
        
        result = await docx_extract(
            file_bytes=file_bytes,
            extraction_config=config,
            name=rubric_name,
            description=description,
        )
        
        extraction_response = result.response
        if extraction_response is None:
            raise HTTPException(status_code=500, detail="Extraction produced no result")
        
        extraction_dict = extraction_response.model_dump(mode='json')
        
        if auto_save:
            try:
                save_result = await save_ontology_draft(
                    db=db,
                    name=rubric_name,
                    draft=extraction_dict,
                    description=description,
                    user_id=current_user.id,
                )
                rubric_id = save_result.rubric_id
                logger.info(f"[v2/v3] Auto-saved as rubric {rubric_id}")
                
                return OntologyExtractionResponse(
                    extraction_result=extraction_dict,
                    metadata=ExtractionMetadata(
                        rubric_id=rubric_id,
                        was_auto_saved=True,
                        needs_compilation_before_grading=True,
                        next_steps=ExtractionNextSteps(
                            action="compile",
                            endpoint=f"/api/v0/rubrics/{rubric_id}/compile",
                            warnings_preview=[],
                        ),
                    ),
                    stats=save_result.stats,
                )
            except Exception as save_error:
                logger.warning(f"[v2/v3] Auto-save failed: {save_error}")
        
        return extraction_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/v3] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error extracting rubric: {str(e)}")


@router.get(
    "/rubric/{rubric_id}",
    response_model=RubricResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get rubric by ID",
)
async def get_rubric(
    rubric_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RubricResponse:
    """Retrieve a rubric from the database by ID."""
    try:
        rubric = await get_owned_or_404(db, Rubric, rubric_id, current_user.id)
        return RubricResponse(
            id=rubric.id, created_at=rubric.created_at,
            name=rubric.name, description=rubric.description,
            total_points=rubric.total_points, is_compiled=rubric.is_compiled,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting rubric: {str(e)}")


# =============================================================================
# Student Test Endpoints
# =============================================================================

@router.post(
    "/preview_student_test_pdf",
    response_model=PreviewStudentTestResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Preview student test PDF pages",
    description="Upload a student test PDF and get page previews for selecting answer page mappings.",
)
async def preview_student_test_pdf(
    file: UploadFile = File(..., description="Student test PDF file"),
    current_user: User = Depends(get_current_user),
) -> PreviewStudentTestResponse:
    """
    Preview a student test PDF by splitting it into page thumbnails.
    
    Returns:
    - Thumbnail images for each page
    - Detected student name from first page (if found)
    
    The teacher should:
    1. Review the thumbnails
    2. Select which pages contain each question/sub-question answer
    3. Use the same mapping for batch grading all tests
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        pdf_bytes = await file.read()
        
        if len(pdf_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        logger.info(f"Processing student test preview: {file.filename}, size: {len(pdf_bytes)} bytes")
        
        # Generate page previews
        preview_data = generate_pdf_previews(pdf_bytes)
        
        # Try to extract student name from first page
        detected_name = None
        try:
            images = pdf_to_images(pdf_bytes, dpi=100)
            if images:
                first_page_b64 = image_to_base64(images[0], max_size=1000)
                detected_name = extract_student_name_from_page(first_page_b64)
        except Exception as e:
            logger.warning(f"Could not extract student name: {e}")
        
        pages = [
            PagePreview(
                page_index=p["page_index"],
                page_number=p["page_number"],
                thumbnail_base64=p["thumbnail_base64"],
                width=p["width"],
                height=p["height"],
            )
            for p in preview_data["pages"]
        ]
        
        return PreviewStudentTestResponse(
            filename=file.filename,
            page_count=preview_data["page_count"],
            pages=pages,
            detected_student_name=detected_name,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing student test PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")



# S10: stale expression — True when the pinned version differs from the rubric's current.
# LEFT JOIN so deleted rubrics don't drop rows from the list (treated as not-stale).
_stale_expr = case(
    (GradedTest.rubric_contract_version != Rubric.contract_version, True),
    else_=False,
).label("rubric_contract_stale")


@router.get("/graded_tests", response_model=List[GradedTestListItem])
async def get_graded_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GradedTestListItem]:
    """List all graded tests for the current user. Lean list — no draft JSON."""
    result = await db.execute(
        select(GradedTest, _stale_expr)
        .join(Rubric, GradedTest.rubric_id == Rubric.id, isouter=True)
        .where(GradedTest.user_id == current_user.id)
        .order_by(GradedTest.created_at.desc())
    )
    rows = result.all()
    return [
        GradedTestListItem(
            id=r.GradedTest.id,
            student_name=r.GradedTest.student_name,
            filename=r.GradedTest.filename,
            status=r.GradedTest.status,
            total_score=r.GradedTest.total_score,
            total_possible=r.GradedTest.total_possible,
            percentage=r.GradedTest.percentage,
            rubric_contract_version=r.GradedTest.rubric_contract_version,
            created_at=r.GradedTest.created_at.isoformat(),
            rubric_contract_stale=bool(r.rubric_contract_stale),
        )
        for r in rows
    ]


@router.get("/rubric/{rubric_id}/graded_tests", response_model=List[GradedTestListItem])
async def get_graded_tests_by_rubric(
    rubric_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GradedTestListItem]:
    """List graded tests for one rubric. Ownership of the rubric is verified first."""
    await get_owned_or_404(db, Rubric, rubric_id, current_user.id)
    result = await db.execute(
        select(GradedTest, _stale_expr)
        .join(Rubric, GradedTest.rubric_id == Rubric.id, isouter=True)
        .where(GradedTest.user_id == current_user.id, GradedTest.rubric_id == rubric_id)
        .order_by(GradedTest.created_at.desc())
    )
    rows = result.all()
    return [
        GradedTestListItem(
            id=r.GradedTest.id,
            student_name=r.GradedTest.student_name,
            filename=r.GradedTest.filename,
            status=r.GradedTest.status,
            total_score=r.GradedTest.total_score,
            total_possible=r.GradedTest.total_possible,
            percentage=r.GradedTest.percentage,
            rubric_contract_version=r.GradedTest.rubric_contract_version,
            created_at=r.GradedTest.created_at.isoformat(),
            rubric_contract_stale=bool(r.rubric_contract_stale),
        )
        for r in rows
    ]


@router.get(
    "/graded_test/{graded_test_id}",
    # PR-4 Phase 1: give this (the most-consumed graded-test endpoint) a
    # response_model so OpenAPI types its 200 as the 4-shape union instead of an
    # empty `{}` that codegen renders `unknown`. A DISCRIMINATED union is BACKLOG
    # polish — `status` is a plain `str` (no Literal), so there is no discriminator
    # field today; a plain Union is safe here because the four members are
    # isinstance-distinct (no subclassing), so Pydantic v2 serialises each returned
    # instance with its own serializer — no field is dropped, every points
    # field_serializer still fires. Verified against the golden fixtures.
    response_model=Union[
        GradedTestStatusResponse,
        GradedTestDraftResponse,
        GradedTestApprovedResponse,
        GradedTestFailedResponse,
    ],
)
async def get_single_graded_test(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Status-driven detail. Used as the polling target while grading runs (D3).

    pending / grading → lean status response (no draft).
    draft             → full GradedTestDraft + row aggregates.
    failed            → status + error_message.
    approved          → draft + frozen contract (S9) + rubric_contract_stale (S10).
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    # [PR-G8] First open, stamped ONCE. get_owned_or_404 already proved this is
    # the owner, so no other reader can set it — and it is never re-stamped,
    # because "when she first saw it" is not a last-access time. Only a landed
    # grade can be seen: a pending row shows a spinner, not a review.
    if row.opened_at is None and row.status in ("draft", "approved", "failed"):
        row.opened_at = datetime.now(timezone.utc)
        await db.commit()

    if row.status in ("pending", "grading"):
        return GradedTestStatusResponse(
            id=row.id, status=row.status, student_name=row.student_name
        )

    if row.status == "failed":
        return GradedTestFailedResponse(
            id=row.id, status=row.status, error_message=row.error_message
        )

    # S10: compute rubric_contract_stale for draft and approved responses
    rubric_contract_stale = False
    rubric = await db.get(Rubric, row.rubric_id)
    numeric_policy = None
    if rubric is not None:
        rubric_contract_stale = (row.rubric_contract_version != rubric.contract_version)
        # [OD-F8] the rounding rule the client re-prices with. Omitted rather
        # than defaulted when the contract will not parse: a guessed grid is
        # how the screen and the frozen contract come to disagree.
        try:
            if rubric.contract_json:
                numeric_policy = NumericPolicy.model_validate(
                    rubric.contract_json.get("numeric_policy") or {})
        except Exception:                            # noqa: BLE001
            logger.warning("numeric_policy_unavailable",
                           extra={"rubric_id": str(row.rubric_id)})

    if row.status == "draft":
        draft = GradedTestDraft.model_validate(row.draft_json)
        return GradedTestDraftResponse(
            id=row.id,
            status=row.status,
            student_name=row.student_name,
            filename=row.filename,
            total_score=row.total_score,
            total_possible=row.total_possible,
            percentage=row.percentage,
            total_cost_usd=row.total_cost_usd,
            transcription_id=row.transcription_id,
            opened_at=row.opened_at,          # [PR-G8]
            numeric_policy=numeric_policy,    # [OD-F8]
            draft=draft,
            rubric_contract_stale=rubric_contract_stale,
            regraded_from_id=row.regraded_from_id,
        )

    # approved — return draft + frozen contract (S9)
    draft = GradedTestDraft.model_validate(row.draft_json)
    contract = GradedTestContract.model_validate(row.contract_json)
    return GradedTestApprovedResponse(
        id=row.id,
        status=row.status,
        student_name=row.student_name,
        filename=row.filename,
        total_score=row.total_score,
        total_possible=row.total_possible,
        percentage=row.percentage,
        total_cost_usd=row.total_cost_usd,
        transcription_id=row.transcription_id,
        opened_at=row.opened_at,
        numeric_policy=numeric_policy,        # [OD-F8]
        draft=draft,
        contract=contract,
        approved_at=row.approved_at.isoformat(),
        rubric_contract_stale=rubric_contract_stale,
        regraded_from_id=row.regraded_from_id,
    )


# =============================================================================
# S9 — Teacher overrides + approval
# =============================================================================

@router.patch("/graded_test/{graded_test_id}/draft", response_model=GradedTestDraftResponse)
async def save_draft_overrides(
    graded_test_id: UUID,
    body: SaveDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GradedTestDraftResponse:
    """
    Save teacher overrides onto the draft — ungated, partial-work-safe.

    Only draft_json.teacher_overrides is rewritten. AI outcomes (scope_outcomes)
    are never modified. Status stays 'draft'.

    Light validation: closed-world + bounds (no error-annotation check —
    that fires only at approve time).
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    if row.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot save overrides: graded test is '{row.status}', expected 'draft'.",
        )

    draft = GradedTestDraft.model_validate(row.draft_json)

    # Light validation — load rubric just for precision
    rubric = await db.get(Rubric, row.rubric_id)
    if rubric is None or rubric.contract_json is None:
        raise HTTPException(status_code=404, detail="Rubric contract not found.")
    rubric_contract = GradingRubricContract.model_validate(rubric.contract_json)

    # [PR-G5] Gate the OVERLAY (terminals + checks), then RE-PRICE on the
    # server. There is nothing to bound or round any more: an override is a
    # verdict and the pricer derives the number, clamping and snapping.
    from ...services.graded_test_contract_compiler import (
        GateViolation,
        _build_terminal_index,
        _price_by_scope,
    )
    terminal_index, branch_criterion_ids = _build_terminal_index(draft)
    precision = rubric_contract.numeric_policy.precision
    violations = []

    for tid, decisions in body.overrides.terminals.items():
        if tid in branch_criterion_ids:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="branch_criterion",
                message=f"'{tid}' is a branch criterion and cannot be overridden directly.",
            ))
            continue
        if tid not in terminal_index:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="closed_world",
                message=f"Override key '{tid}' is not a known terminal in this graded test.",
            ))
            continue
        known = {c.check_id for c in (terminal_index[tid].checks or [])}
        for decision in decisions:
            if decision.check_id not in known:
                violations.append(GateViolation(
                    terminal_id=tid,
                    violation_kind="closed_world",
                    message=(f"Override on '{tid}' references check "
                             f"'{decision.check_id}', which is not a check of that "
                             f"terminal in this draft."),
                ))

    if violations:
        raise HTTPException(
            status_code=422,
            detail={"gate_violations": [v.__dict__ for v in violations]},
        )

    _ai, final_prices, _eff, _touched = _price_by_scope(
        draft, terminal_index, body.overrides, precision)
    effective_totals = {
        info.terminal_id: final_prices.get(info.terminal_id, info.ai_points_awarded)
        for info in terminal_index.values()
    }
    effective_total = sum(effective_totals.values(), Decimal("0"))
    pricing_mismatch = bool(
        body.client_totals is not None
        and any(Decimal(str(v)) != effective_totals.get(k)
                for k, v in body.client_totals.items())
    )

    rounded_overrides = body.overrides

    # Write only teacher_overrides — AI outcomes untouched
    updated_draft = draft.model_copy(update={"teacher_overrides": rounded_overrides})
    row.draft_json = updated_draft.model_dump(mode="json")
    # [PR-G8] §1.5 calls the card's number "effective (overlay-priced)". The row
    # aggregate is what the batch feed reads, so it must follow her decisions —
    # otherwise every card shows the AI's total until approval, and the pencil
    # number silently disagrees with the review screen she is looking at.
    row.total_score = effective_total
    if row.total_possible:
        row.percentage = (effective_total / row.total_possible * 100
                          ).quantize(Decimal("0.01"))
    await db.commit()

    return GradedTestDraftResponse(
        id=row.id,
        status=row.status,
        student_name=row.student_name,
        filename=row.filename,
        total_score=row.total_score,
        total_possible=row.total_possible,
        percentage=row.percentage,
        total_cost_usd=row.total_cost_usd,
        transcription_id=row.transcription_id,
        opened_at=row.opened_at,
        draft=updated_draft,
        effective_totals=effective_totals,
        effective_total=effective_total,
        pricing_mismatch=pricing_mismatch,
    )


@router.post("/graded_test/{graded_test_id}/approve", response_model=GradedTestApprovedResponse)
async def approve_graded_test(
    graded_test_id: UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GradedTestApprovedResponse:
    """
    Gate + compile + atomically freeze the graded test.

    The body's overrides are authoritative (the teacher's final set at the moment
    of approval). They are persisted onto draft_json.teacher_overrides AND used
    to compile the frozen contract in the same commit.

    Gate: bounds-per-terminal + precision + closed-world + no-error-annotations.
    The gate does NOT re-fire rubric point-sum invariants on awarded points.

    On gate failure: 422 with structured violations; no state change.
    On success: status → 'approved', contract_json written, approved_at set,
    total_score/possible/percentage updated. All in one commit (CHECK constraint
    requires all three together).
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    if row.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve: graded test is '{row.status}', expected 'draft'.",
        )

    rubric = await db.get(Rubric, row.rubric_id)
    if rubric is None or rubric.contract_json is None:
        raise HTTPException(status_code=404, detail="Rubric contract not found.")
    rubric_contract = GradingRubricContract.model_validate(rubric.contract_json)

    draft = GradedTestDraft.model_validate(row.draft_json)

    try:
        contract = compile_graded_test(draft, body.overrides, rubric_contract)

        # [PR-G5] The teacher approves a NUMBER she saw. If the server prices
        # the same overlay differently, freezing the server's answer silently is
        # the §5 catastrophe in miniature — she reviews one total and another one
        # becomes immutable. Refuse, and say so as an ERROR annotation.
        if body.client_total is not None and Decimal(str(body.client_total)) != contract.total_score:
            raise HTTPException(
                status_code=422,
                detail={
                    "pricing_mismatch": True,
                    "client_total": str(body.client_total),
                    "server_total": str(contract.total_score),
                    "annotation": {
                        "severity": "ERROR",
                        "annotation_type": "pricing_mismatch",
                        "target_id": None,
                        "message": (
                            f"הציון שהוצג ({body.client_total}) שונה מהציון שחושב "
                            f"בשרת ({contract.total_score}). האישור נעצר — רענני "
                            f"את הדף ובדקי את הסעיפים לפני אישור."
                        ),
                    },
                },
            )
    except GateError as e:
        raise HTTPException(
            status_code=422,
            detail={"gate_violations": [v.__dict__ for v in e.violations]},
        )

    # Atomic freeze — all six fields in memory before the single commit.
    # The DB CHECK constraint graded_tests_status_consistency requires
    # status='approved' → draft_json IS NOT NULL AND contract_json IS NOT NULL
    # AND approved_at IS NOT NULL — setting all three in one commit is mandatory.
    updated_draft = draft.model_copy(update={"teacher_overrides": body.overrides})
    row.draft_json = updated_draft.model_dump(mode="json")
    row.contract_json = contract.model_dump(mode="json")
    row.total_score = contract.total_score
    row.total_possible = contract.total_possible
    row.percentage = contract.percentage
    row.approved_at = datetime.now(timezone.utc)
    row.status = "approved"
    await db.commit()

    return GradedTestApprovedResponse(
        id=row.id,
        status=row.status,
        student_name=row.student_name,
        filename=row.filename,
        total_score=row.total_score,
        total_possible=row.total_possible,
        percentage=row.percentage,
        total_cost_usd=row.total_cost_usd,
        transcription_id=row.transcription_id,
        opened_at=row.opened_at,
        draft=updated_draft,
        contract=contract,
        approved_at=row.approved_at.isoformat(),
    )


# =============================================================================
# S10 — Revision actions: regrade, manual_edit, retry
# =============================================================================

class RevisionResponse(BaseModel):
    """Returned by all three S10 revision endpoints."""
    graded_test_id: str
    status: str  # 'pending' (regrade/retry) or 'draft' (manual_edit)


# =============================================================================
# PR-G9 — the returned exam (what the STUDENT receives)
# =============================================================================

@router.get("/graded_test/{graded_test_id}/returned-exam")
async def get_returned_exam(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Her student's exam back: the original pages, stamped, plus the feedback.

    APPROVED ONLY. A draft is a proposal the teacher has not accepted; handing
    one to a student would make Vivi the grader, which is the one thing it
    never is.

    Rendered from the CONTRACT, never the draft — what she froze is what the
    student receives. Cached in GCS under a key covering every input that can
    change a pixel; a mismatch re-renders rather than serving the old page.
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id,
                                             current_user.id)
    if row.status != "approved" or not row.contract_json:
        raise HTTPException(
            status_code=409,
            detail="אפשר להחזיר לתלמיד רק מבחן שאושר")

    contract = GradedTestContract.model_validate(row.contract_json)

    batch = await db.get(GradingBatch, row.batch_id) if row.batch_id else None
    include_criteria = bool(getattr(batch, "appendix_include_criteria", False))
    stamp = effective_stamp_position(
        (row.draft_json or {}).get(OVERLAY_KEY, {}).get("stamp_position"),
        getattr(batch, "stamp_position_default", None))

    key = current_cache_key(contract, stamp, include_criteria)
    path = gcs_object_path(row.id, key)
    gcs = get_gcs_service()

    if row.returned_exam_key == key:
        try:
            cached = await run_in_threadpool(gcs.download_bytes, path)
            return Response(content=cached, media_type="application/pdf")
        except Exception:                            # noqa: BLE001
            # The row claims a render that is not in the bucket. Fall through and
            # rebuild it — the key is a claim about the object, and the object is
            # the truth.
            logger.warning("returned_exam_cache_miss",
                           extra={"graded_test_id": str(row.id), "path": path})

    transcription = await db.get(Transcription, row.transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="לא נמצאה הסריקה המקורית")
    source_pdf = await run_in_threadpool(gcs.download_bytes,
                                         transcription.gcs_object_path)

    pdf = await run_in_threadpool(
        render_returned_exam,
        source_pdf,
        row.student_name,
        scopes_for_render(contract, include_criteria),
        summary_for_render(contract),
        stamp,
        include_criteria,
    )
    await run_in_threadpool(gcs.upload_bytes, pdf, path, "application/pdf")

    row.returned_exam_key = key
    await db.commit()
    logger.info("returned_exam_rendered",
                extra={"graded_test_id": str(row.id), "bytes": len(pdf)})
    return Response(content=pdf, media_type="application/pdf")


@router.patch("/graded_test/{graded_test_id}/stamp_position",
              response_model=StampPositionResponse)
async def save_stamp_position(
    graded_test_id: UUID,
    body: SaveStampPositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StampPositionResponse:
    """Move the stamp on an already-signed exam. [OD-1, owner-ruled 2026-09-04]

    WHY THIS ENDPOINT EXISTS AT ALL. §4.3 P3 lets the teacher drag the stamp on
    the returned-exam preview, and that preview renders APPROVED tests only
    (`get_returned_exam` 409s on anything else). But the only endpoint that
    wrote `stamp_position` was `PATCH …/draft`, which 409s on anything that is
    NOT a draft. The two guards are disjoint, so the drag she performs had
    literally nowhere to go.

    WHY IT DOES NOT VIOLATE LCY-2, and why that is not a stretch:
      * What LCY-2 freezes is the GRADING DECISION, and that lives in
        `contract_json`, which contains no stamp. Moving it changes no points,
        no verdicts, and no contract.
      * The codebase ALREADY writes `draft_json` on approved rows for exactly
        this purpose: `rename_batch`'s «apply to all» selects the batch's graded
        tests with no status filter and rewrites their stamp. So this does not
        add an exception — it gives the per-test case the write path the batch
        case has had all along.

    WHY NOT JUST RELAX `PATCH …/draft` — the tempting answer, named so it is not
    chosen later: that endpoint also writes `terminals` and `feedback`, i.e. the
    grading decision. Relaxing it would let a legitimate stamp move carry an
    illegitimate re-grade on the same request. A separate endpoint is what keeps
    the narrow exception narrow.

    IT MUST NOT EXTEND THE CHAIN. Routing this through `manual_edit` would mint
    a new version and un-sign the exam for a cosmetic change — the teacher would
    have to re-approve because she moved a stamp.

    THE SERVER SETS `source="manual"`. `source` decides whether «apply to all»
    may clear the position, so a client that sent "auto" could make the
    teacher's own placement erasable by a later batch-default change. Nothing
    persists "auto" anyway — the corner picker runs at render time
    (`auto_stamp_position`) and its result never reaches the overlay — so a
    position that arrives here is, by construction, one she placed.
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id,
                                             current_user.id)
    if row.status not in ("draft", "approved"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move the stamp: graded test is '{row.status}'.")
    if not row.draft_json:
        raise HTTPException(status_code=409,
                            detail="Cannot move the stamp: no draft on this row.")

    draft = GradedTestDraft.model_validate(row.draft_json)
    overlay = draft.teacher_overrides or GradedTestOverrides()
    position = body.stamp_position
    if position is not None:
        position = position.model_copy(update={"source": "manual"})

    updated = draft.model_copy(update={
        "teacher_overrides": overlay.model_copy(update={"stamp_position": position})})
    row.draft_json = updated.model_dump(mode="json")

    # The stamp is IN the cache key, so a cached render is now a render of a
    # position she has moved away from. Dropping the key is what makes the next
    # fetch re-render; leaving it would serve a page that looks entirely correct
    # and is wrong (§3.5a — the one failure this feature cannot have).
    row.returned_exam_key = None
    await db.commit()

    return StampPositionResponse(
        id=row.id,
        status=row.status,
        stamp_position=position,
        returned_exam_state="stale",
    )


@router.post("/graded_test/{graded_test_id}/regrade", response_model=RevisionResponse)
async def regrade_graded_test(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionResponse:
    """
    Re-grade against the current rubric contract version (stale rows only).

    Creates a pending successor row and enqueues a grading Cloud Task.
    The teacher polls GET /graded_test/{new_id} exactly as in S8.

    Preconditions (→ 409 if violated):
      - Source is owned (→ 404 if not).
      - Source status == 'approved'.
      - Source is the leaf (regraded_to_id IS NULL).
      - Source is stale (pinned contract_version != current rubric contract_version).
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    if row.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regrade: status is '{row.status}', expected 'approved'.",
        )
    if row.regraded_to_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot regrade a non-leaf row (row has already been superseded).",
        )

    rubric = await db.get(Rubric, row.rubric_id)
    if rubric is None or rubric.contract_json is None:
        raise HTTPException(status_code=404, detail="Rubric not found or has no compiled contract.")

    if row.rubric_contract_version == rubric.contract_version:
        raise HTTPException(
            status_code=409,
            detail=(
                "Rubric contract is not stale — use manual_edit to revise "
                "a grade whose rubric has not changed."
            ),
        )

    r2 = await extend_chain(
        db,
        row,
        new_status="pending",
        new_rubric_contract_version=rubric.contract_version,
        new_draft_json=None,
    )

    # Cloud Tasks migration: enqueue AFTER extend_chain's commit; the handler
    # claims the pending row by CAS. Enqueue failure leaves a durable pending
    # row — the grading dispatch backstop reaps it → this same retry chain.
    await enqueue_grading_task_or_log(r2.id)

    return RevisionResponse(graded_test_id=str(r2.id), status=r2.status)


@router.post("/graded_test/{graded_test_id}/manual_edit", response_model=RevisionResponse)
async def manual_edit_graded_test(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionResponse:
    """
    Revise an approved grade by hand — no agent invocation.

    Creates a 'draft' successor pre-loaded with the source row's draft_json
    (AI outcomes + last-approved teacher_overrides) carried verbatim.
    Rubric contract version is preserved (same rubric; teacher is tweaking
    their existing decision, not regrading against a new rubric).

    The returned draft is immediately editable through the S9 review panel.

    Preconditions (→ 409 if violated):
      - Source is owned (→ 404 if not).
      - Source status == 'approved'.
      - Source is the leaf (regraded_to_id IS NULL).
      (No staleness requirement — manual_edit is available regardless of staleness.)
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    if row.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot manual_edit: status is '{row.status}', expected 'approved'.",
        )
    if row.regraded_to_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot revise a non-leaf row (row has already been superseded).",
        )

    # draft_json carried verbatim: AI outcomes + last-approved teacher_overrides.
    # rubric_contract_version preserved: content was produced against this version.
    r2 = await extend_chain(
        db,
        row,
        new_status="draft",
        new_rubric_contract_version=row.rubric_contract_version,
        new_draft_json=row.draft_json,  # JSONB column — already a dict
    )

    return RevisionResponse(graded_test_id=str(r2.id), status=r2.status)


@router.post("/graded_test/{graded_test_id}/retry", response_model=RevisionResponse)
async def retry_graded_test(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionResponse:
    """
    Re-attempt a failed grade.

    Creates a pending successor pinned to the current rubric contract version
    (naturally picks up any rubric updates since the failure) and enqueues a
    grading Cloud Task.

    Preconditions (→ 409 if violated):
      - Source is owned (→ 404 if not).
      - Source status == 'failed'.
      - Source is the leaf (regraded_to_id IS NULL).
    """
    row: GradedTest = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)

    if row.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry: status is '{row.status}', expected 'failed'.",
        )
    if row.regraded_to_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot retry a non-leaf row (row has already been superseded).",
        )

    rubric = await db.get(Rubric, row.rubric_id)
    if rubric is None or rubric.contract_json is None:
        raise HTTPException(status_code=404, detail="Rubric not found or has no compiled contract.")

    r2 = await extend_chain(
        db,
        row,
        new_status="pending",
        new_rubric_contract_version=rubric.contract_version,
        new_draft_json=None,
    )

    await enqueue_grading_task_or_log(r2.id)

    return RevisionResponse(graded_test_id=str(r2.id), status=r2.status)


# =============================================================================
# INTERNAL: grading Cloud Tasks target — NOT behind get_current_user
# =============================================================================

internal_router = APIRouter(prefix="/internal/grading-jobs", tags=["internal"])


@internal_router.post("/{graded_test_id}/run", include_in_schema=False)
async def run_grading_job_task(graded_test_id: UUID, request: Request) -> dict:
    """Executes grading INSIDE this request (CPU guaranteed). Idempotent: the
    runner's first statement is the pending->grading CAS - a duplicate
    delivery (queue maxAttempts=3) or an advanced/terminal row is a 200
    no-op. Always 200 on auth success: a non-2xx would redeliver work the
    row already accounts for."""
    reason = verify_task_request(request)
    if reason is not None:
        logger.warning("internal_grading_run_rejected",
                       extra={"graded_test_id": str(graded_test_id),
                              "reason": reason})
        raise HTTPException(status_code=403, detail="Forbidden")

    from ...services.grading_runner import run_grading

    ran = await run_grading(graded_test_id)
    return {"graded_test_id": str(graded_test_id), "ran": bool(ran)}


class RegenerateFeedbackResponse(BaseModel):
    target: str
    text: str
    # True when the teacher already wrote her own text for this target: the new
    # text is RETURNED for her to consider and the draft is left alone.
    offered_only: bool


@router.post("/graded_test/{graded_test_id}/feedback/regenerate",
             response_model=RegenerateFeedbackResponse)
async def regenerate_feedback(
    graded_test_id: UUID,
    target: str = Query(..., description='scope id, or the literal "summary"'),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegenerateFeedbackResponse:
    """Regenerate the feedback for ONE target.

    OD-G4.2 — her words are never overwritten. If she has already edited this
    target, the fresh text is returned for the UI to offer and the draft is left
    exactly as it was; the decision to take it is hers, not the endpoint's.
    """
    row = await get_owned_or_404(db, GradedTest, graded_test_id, current_user.id)
    if row.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regenerate feedback: graded test is '{row.status}'.")

    draft = GradedTestDraft.model_validate(row.draft_json)

    from ...agents.feedback.agent import FeedbackAgent
    from ...agents.feedback.prompt import render_scope_for_feedback
    from ...agents.feedback.staleness import basis_hash, flatten_checks
    from ...agents.grader.llm_factory import build_chat_model
    from ...schemas.graded_test_draft import FeedbackText

    if not settings.feedback_model_key:
        raise HTTPException(status_code=503,
                            detail="לא הוגדר מודל משוב במערכת.")

    scopes = [(so.question_id if so.sub_question_id is None
               else f"{so.question_id}.{so.sub_question_id}", so)
              for so in draft.scope_outcomes if so.graded_by == "llm"]
    if target != "summary" and target not in {sid for sid, _ in scopes}:
        raise HTTPException(status_code=404,
                            detail=f"Unknown feedback target '{target}'.")

    agent = FeedbackAgent(build_chat_model(settings.feedback_model_provider,
                                           settings.feedback_model_key),
                          model_version=settings.feedback_model_key)
    block, _annotations = await agent.generate(
        [(sid, render_scope_for_feedback(so)) for sid, so in scopes])
    if block is None:
        raise HTTPException(status_code=502, detail="יצירת המשוב נכשלה. נסי שוב.")

    fresh = (block.summary.text if target == "summary"
             else (block.scopes.get(target).text if block.scopes.get(target) else ""))

    # her text stands: return the alternative, change nothing
    if target in (draft.teacher_overrides.feedback or {}):
        return RegenerateFeedbackResponse(target=target, text=fresh, offered_only=True)

    existing = draft.feedback
    if existing is None:
        updated_block = block
    elif target == "summary":
        updated_block = existing.model_copy(update={"summary": FeedbackText(text=fresh)})
    else:
        so = next(so for sid, so in scopes if sid == target)
        new_scopes = dict(existing.scopes)
        new_scopes[target] = FeedbackText(
            text=fresh, basis_hash=basis_hash(list(flatten_checks(so))))
        updated_block = existing.model_copy(update={"scopes": new_scopes})

    row.draft_json = draft.model_copy(update={"feedback": updated_block}).model_dump(mode="json")
    await db.commit()
    return RegenerateFeedbackResponse(target=target, text=fresh, offered_only=False)
