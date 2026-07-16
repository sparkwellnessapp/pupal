"""
Grading API endpoints - v0.

Endpoints for rubric extraction (DOCX) and graded test retrieval.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.deps import get_owned_or_404
from ...database import get_db
from ...models.grading import GradedTest, Rubric
from ...models.user import User
from ...schemas.graded_test_contract import GradedTestContract
from ...schemas.graded_test_draft import GradedTestDraft, GradedTestOverrides
from ...schemas.graded_test_responses import (
    GradedTestApprovedResponse,
    GradedTestDraftResponse,
    GradedTestFailedResponse,
    GradedTestListItem,
    GradedTestStatusResponse,
)
from ...schemas.ontology_types import GradingRubricContract
from ...services.graded_test_contract_compiler import GateError, compile_graded_test
from ...services.graded_test_revision import extend_chain
from ...services.grading_runner import run_grading
from .auth import get_current_user


# ---------------------------------------------------------------------------
# S9 request bodies
# ---------------------------------------------------------------------------

class SaveDraftRequest(BaseModel):
    overrides: GradedTestOverrides


class ApproveRequest(BaseModel):
    overrides: GradedTestOverrides
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
    if rubric is not None:
        rubric_contract_stale = (row.rubric_contract_version != rubric.contract_version)

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

    # Run a subset of the gate: closed-world + bounds (no error-annotation check)
    # We reuse the compiler's helper for the terminal index, then validate manually.
    from ...services.graded_test_contract_compiler import (
        GateViolation,
        _build_terminal_index,
    )
    from decimal import ROUND_HALF_UP
    terminal_index, branch_criterion_ids = _build_terminal_index(draft)
    precision = rubric_contract.numeric_policy.precision
    violations = []
    rounded_overrides: GradedTestOverrides = {}

    for tid, override in body.overrides.items():
        rounded = (override.points_awarded / precision).to_integral_value(
            rounding=ROUND_HALF_UP
        ) * precision
        rounded_override = override.model_copy(update={"points_awarded": rounded})
        rounded_overrides[tid] = rounded_override

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
        info = terminal_index[tid]
        if rounded < 0 or rounded > info.points_possible:
            violations.append(GateViolation(
                terminal_id=tid,
                violation_kind="out_of_bounds",
                message=(
                    f"Override for '{tid}': {rounded} is outside [0, {info.points_possible}]."
                ),
            ))

    if violations:
        raise HTTPException(
            status_code=422,
            detail={"gate_violations": [v.__dict__ for v in violations]},
        )

    # Write only teacher_overrides — AI outcomes untouched
    updated_draft = draft.model_copy(update={"teacher_overrides": rounded_overrides})
    row.draft_json = updated_draft.model_dump(mode="json")
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
        draft=updated_draft,
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


@router.post("/graded_test/{graded_test_id}/regrade", response_model=RevisionResponse)
async def regrade_graded_test(
    graded_test_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionResponse:
    """
    Re-grade against the current rubric contract version (stale rows only).

    Creates a pending successor row and fires run_grading via BackgroundTasks.
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

    # Fire async grading — runs after response is sent (S8 pattern).
    # run_grading owns its own DB session; must not capture this one.
    background_tasks.add_task(run_grading, r2.id)

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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionResponse:
    """
    Re-attempt a failed grade.

    Creates a pending successor pinned to the current rubric contract version
    (naturally picks up any rubric updates since the failure) and fires
    run_grading via BackgroundTasks.

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

    background_tasks.add_task(run_grading, r2.id)

    return RevisionResponse(graded_test_id=str(r2.id), status=r2.status)
