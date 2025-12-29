"""
Grading API endpoints - v0.

All endpoints for rubric extraction, test grading, and PDF annotation.
Updated to support the new two-phase rubric extraction with sub-questions.
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...database import get_db, AsyncSessionLocal
from ...models.grading import Rubric
from ...services.pdf_preview_service import generate_pdf_previews
from ...services.grading_service import (
    parse_student_test_with_mappings,
    grade_student_test,
    grade_student_tests_batch,
    save_graded_test,
    get_graded_tests_by_rubric_id,
)
from ...services.rubric_service import (
    get_rubric_by_id,
    extract_rubric_with_page_mappings,
    save_rubric as save_rubric_to_db,
    list_rubrics as list_rubrics_service,
)
from ...services.document_parser import (
    pdf_to_images,
    image_to_base64,
    extract_student_name_from_page,
)
from ...schemas.grading import (
    # Preview schemas
    PagePreview,
    PreviewRubricPdfResponse,
    PreviewStudentTestResponse,
    # Extraction request schemas
    QuestionPageMapping,
    ExtractRubricRequest,
    # Extraction response schemas (for editing)
    ExtractRubricResponse,
    # Save schemas
    SaveRubricRequest,
    SaveRubricResponse,
    # Rubric retrieval
    RubricResponse,
    # Student test schemas
    AnswerPageMapping,
    GradeTestsRequest,
    GradeTestsResponse,
    # Grading schemas
    GradedTestResponse,
    CreateGradeTestResponse,
    GradedTestPdfResponse,
    AnnotatePdfResponse,
    GradedTestsListResponse,
    GradedPdfsListResponse,
    # Error
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/grading", tags=["grading"])


# =============================================================================
# Rubric Endpoints
# =============================================================================

@router.get("/rubrics", response_model=list[dict])
async def list_rubrics(
    db: AsyncSession = Depends(get_db),
):
    """
    List all saved rubrics (name, id, created_at).
    Returns newest first.
    """
    query = select(Rubric).order_by(Rubric.created_at.desc())
    result = await db.execute(query)
    rubrics = result.scalars().all()
    
    return [
        {
            "id": str(rubric.id),
            "name": rubric.name,
            "description": rubric.description,
            "created_at": rubric.created_at.isoformat(),
            "total_points": rubric.rubric_json.get("total_points") if rubric.rubric_json else None,
            "rubric_json": rubric.rubric_json,
        }
        for rubric in rubrics
    ]

@router.post(
    "/preview_rubric_pdf",
    response_model=PreviewRubricPdfResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Preview rubric PDF pages",
    description="Upload a PDF and get page previews for the user to select question/criteria mappings.",
)
async def preview_rubric_pdf(
    file: UploadFile = File(..., description="Rubric PDF file"),
) -> PreviewRubricPdfResponse:
    """
    Preview a rubric PDF by splitting it into page thumbnails.
    
    Returns:
    - Thumbnail images for each page (base64-encoded)
    - Page count and dimensions
    
    The frontend should display these thumbnails and allow the user to:
    1. Select which pages contain each question's text
    2. Select which pages contain the rubric/criteria for each question or sub-question
    
    Then call extract_rubric with the mappings.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Read PDF bytes
        pdf_bytes = await file.read()
        
        if len(pdf_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        logger.info(f"Processing PDF preview: {file.filename}, size: {len(pdf_bytes)} bytes")
        
        # Generate page previews
        preview_data = generate_pdf_previews(pdf_bytes)
        
        # Build response
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
        
        return PreviewRubricPdfResponse(
            filename=file.filename,
            page_count=preview_data["page_count"],
            pages=pages,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.post(
    "/extract_rubric",
    response_model=ExtractRubricResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Extract rubric from PDF with page mappings",
    description="""
    Extract questions and grading criteria from a PDF using user-defined page mappings.
    
    This endpoint does NOT save to the database. It returns the extracted data for 
    the teacher to review and edit. After editing, call /save_rubric to persist.
    
    Supports:
    - Questions with direct criteria (no sub-questions)
    - Questions with sub-questions (א, ב, ג...), each with their own criteria table
    """,
)
async def extract_rubric(
    file: UploadFile = File(..., description="Rubric PDF file"),
    name: Optional[str] = Query(None, description="Optional name for the rubric"),
    description: Optional[str] = Query(None, description="Optional description"),
    question_mappings: str = Query(..., description="JSON-encoded list of QuestionPageMapping objects"),
) -> ExtractRubricResponse:
    """
    Extract rubric from a PDF file using Vision AI with page mappings.
    
    The question_mappings should be a JSON string containing an array of mappings.
    Each mapping defines:
    - question_number: Which question (1, 2, 3...)
    - question_page_indexes: Pages containing the question text
    - criteria_page_indexes: Pages containing criteria (if no sub-questions)
    - sub_questions: Array of sub-question mappings (if has sub-questions)
    
    Returns extracted data for review - NOT saved to database yet.
    """
    import json
    
    try:
        # Validate file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        pdf_bytes = await file.read()
        if len(pdf_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Parse question mappings from JSON string
        try:
            mappings_data = json.loads(question_mappings)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in question_mappings: {str(e)}")
        
        if not mappings_data or not isinstance(mappings_data, list):
            raise HTTPException(status_code=400, detail="question_mappings must be a non-empty array")
        
        # Convert to Pydantic models
        try:
            parsed_mappings = [QuestionPageMapping(**m) for m in mappings_data]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid mapping structure: {str(e)}")
        
        logger.info(f"Extracting rubric from {file.filename} with {len(parsed_mappings)} question mappings")
        
        # Extract rubric using Vision AI
        response = await extract_rubric_with_page_mappings(
            pdf_bytes=pdf_bytes,
            question_mappings=parsed_mappings,
            name=name,
            description=description,
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error extracting rubric: {str(e)}")


@router.post(
    "/save_rubric",
    response_model=SaveRubricResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Save reviewed rubric to database",
    description="Save a rubric after the teacher has reviewed and edited the extracted data.",
)
async def save_rubric(
    request: SaveRubricRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> SaveRubricResponse:
    """
    Save a reviewed/edited rubric to the database.
    
    Call this after the teacher has reviewed the extraction results from /extract_rubric
    and made any necessary edits.
    """
    try:
        if not request.questions:
            raise HTTPException(status_code=400, detail="At least one question is required")
        
        # Save to database
        rubric = await save_rubric_to_db(db=db, request=request)
        
        # Calculate stats
        num_criteria = sum(
            len(q.criteria) + sum(len(sq.criteria) for sq in q.sub_questions)
            for q in request.questions
        )
        
        return SaveRubricResponse(
            id=rubric.id,
            created_at=rubric.created_at,
            name=rubric.name,
            description=rubric.description,
            total_points=rubric.total_points,
            num_questions=len(request.questions),
            num_criteria=num_criteria,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving rubric: {str(e)}")


@router.get(
    "/rubric/{rubric_id}",
    response_model=RubricResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get rubric by ID",
    description="Retrieve a previously saved rubric by its ID.",
)
async def get_rubric(
    rubric_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RubricResponse:
    """
    Retrieve a rubric from the database by ID.
    """
    try:
        rubric = await get_rubric_by_id(db, rubric_id)
        
        if not rubric:
            raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")
        
        return RubricResponse(
            id=rubric.id,
            created_at=rubric.created_at,
            name=rubric.name,
            description=rubric.description,
            total_points=rubric.total_points,
            rubric_json=rubric.rubric_json,
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


@router.post(
    "/grade_tests",
    response_model=GradeTestsResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Grade batch of student tests",
    description="Upload multiple student test PDFs and grade them against a rubric using page mappings.",
)
async def grade_tests(
    rubric_id: UUID = Query(..., description="ID of the rubric to grade against"),
    answer_mappings: str = Query(..., description="JSON-encoded list of AnswerPageMapping objects"),
    first_page_index: int = Query(0, description="Page index containing student name"),
    files: List[UploadFile] = File(..., description="Student test PDF files"),
    db: AsyncSession = Depends(get_db),
) -> GradeTestsResponse:
    """
    Grade a batch of student tests using the specified rubric and page mappings.
    
    The answer_mappings should be a JSON string containing an array of mappings:
    [
        {"question_number": 1, "sub_question_id": null, "page_indexes": [2]},
        {"question_number": 2, "sub_question_id": "א", "page_indexes": [3]},
        {"question_number": 2, "sub_question_id": "ב", "page_indexes": [4]}
    ]
    
    All tests must have the same structure (same page layout).
    """
    import json
    
    try:
        # Fetch rubric
        rubric = await get_rubric_by_id(db, rubric_id)
        if not rubric:
            raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")
        
        # Parse answer mappings
        try:
            mappings_data = json.loads(answer_mappings)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in answer_mappings: {str(e)}")
        
        if not mappings_data or not isinstance(mappings_data, list):
            raise HTTPException(status_code=400, detail="answer_mappings must be a non-empty array")
        
        try:
            parsed_mappings = [AnswerPageMapping(**m) for m in mappings_data]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid mapping structure: {str(e)}")
        
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="At least one test file is required")
        
        for f in files:
            if not f.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {f.filename} must be a PDF")
        
        logger.info(f"Grading {len(files)} tests against rubric {rubric_id}")
        
        # Parse all student tests
        parsed_tests = []
        parse_errors = []
        
        for f in files:
            try:
                pdf_bytes = await f.read()
                if len(pdf_bytes) == 0:
                    parse_errors.append(f"{f.filename}: Empty file")
                    continue
                
                parsed = await parse_student_test_with_mappings(
                    pdf_bytes=pdf_bytes,
                    filename=f.filename,
                    answer_mappings=parsed_mappings,
                    first_page_index=first_page_index,
                )
                parsed_tests.append(parsed)
                
            except Exception as e:
                logger.error(f"Error parsing {f.filename}: {e}")
                parse_errors.append(f"{f.filename}: {str(e)}")
        
        if not parsed_tests:
            raise HTTPException(
                status_code=400, 
                detail=f"No tests could be parsed. Errors: {parse_errors}"
            )
        
        # Grade all tests
        grading_results = await grade_student_tests_batch(
            rubric=rubric.rubric_json,
            student_tests=parsed_tests,
        )
        
        # Build a lookup map for parsed tests by student name/filename
        # This lets us match grading results back to their original parsed answers
        parsed_tests_lookup: Dict[str, Dict[str, Any]] = {}
        for parsed in parsed_tests:
            # Use filename as primary key, student_name as fallback
            key = parsed.get("filename") or parsed.get("student_name", "")
            if key:
                parsed_tests_lookup[key] = parsed
        
        # Save results to database
        saved_tests = []
        save_errors = []
        
        for result in grading_results.get("graded_results", []):
            try:
                # Find the matching parsed test to get student answers
                result_key = result.get("filename") or result.get("student_name", "")
                student_answers = parsed_tests_lookup.get(result_key)
                
                # Use a fresh session for each save to avoid connection issues
                async with AsyncSessionLocal() as save_db:
                    saved = await save_graded_test(
                        db=save_db,
                        rubric_id=rubric_id,
                        grading_result=result,
                        student_answers=student_answers,  # NEW: pass student answers
                    )
                    saved_tests.append(GradedTestResponse(
                        id=saved.id,
                        rubric_id=saved.rubric_id,
                        created_at=saved.created_at,
                        student_name=saved.student_name,
                        filename=saved.filename,
                        total_score=saved.total_score,
                        total_possible=saved.total_possible,
                        percentage=saved.percentage,
                        graded_json=saved.graded_json,
                        student_answers_json=saved.student_answers_json,  # NEW: include in response
                    ))
            except Exception as e:
                logger.error(f"Error saving graded test: {e}")
                save_errors.append(f"{result.get('student_name', 'Unknown')}: {str(e)}")
        
        all_errors = parse_errors + save_errors
        
        return GradeTestsResponse(
            rubric_id=rubric_id,
            total_tests=len(files),
            successful=len(saved_tests),
            failed=len(files) - len(saved_tests),
            graded_tests=saved_tests,
            errors=all_errors,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch grading: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error grading tests: {str(e)}")


# =============================================================================
# Grading Endpoints
# =============================================================================

@router.post(
    "/grade_test",
    response_model=CreateGradeTestResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Grade a student test",
    description="Upload a student test PDF and grade it against an existing rubric.",
)
async def create_grade_test(
    rubric_id: UUID = Query(..., description="ID of the rubric to grade against"),
    file: UploadFile = File(..., description="Student test PDF file"),
    db: AsyncSession = Depends(get_db),
) -> CreateGradeTestResponse:
    """
    Grade a student test using the specified rubric.
    
    Process:
    1. Parse student test PDF using Vision AI to transcribe answers
    2. Grade answers against the rubric using GPT-4
    3. Store grading results in database
    4. Return grading results
    """
    # TODO: Implement grading logic
    raise HTTPException(status_code=501, detail="Endpoint not yet implemented")


@router.get(
    "/graded_tests",
    response_model=GradedTestsListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get all graded tests for a rubric",
    description="Retrieve all graded test JSONs associated with a specific rubric.",
)
async def get_graded_tests(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    db: AsyncSession = Depends(get_db),
) -> GradedTestsListResponse:
    """
    Get all graded tests for a given rubric ID.
    """
    # TODO: Implement get graded tests logic
    raise HTTPException(status_code=501, detail="Endpoint not yet implemented")


# =============================================================================
# PDF Annotation Endpoints
# =============================================================================

@router.post(
    "/annotate_pdf",
    response_model=AnnotatePdfResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Annotate a graded test PDF",
    description="Create an annotated PDF with grading marks and feedback for a graded test.",
)
async def annotate_pdf_test(
    graded_test_id: UUID = Query(..., description="ID of the graded test to annotate"),
    file: UploadFile = File(..., description="Original student test PDF file"),
    db: AsyncSession = Depends(get_db),
) -> AnnotatePdfResponse:
    """
    Create an annotated PDF for a graded test.
    """
    # TODO: Implement PDF annotation logic
    raise HTTPException(status_code=501, detail="Endpoint not yet implemented")


@router.get(
    "/graded_pdfs",
    response_model=GradedPdfsListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get all graded PDF references for a rubric",
    description="Retrieve all graded PDF metadata and download URLs for a specific rubric.",
)
async def get_graded_pdfs(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    db: AsyncSession = Depends(get_db),
) -> GradedPdfsListResponse:
    """
    Get all graded test PDFs for a given rubric ID.
    """
    # TODO: Implement get graded PDFs logic
    raise HTTPException(status_code=501, detail="Endpoint not yet implemented")