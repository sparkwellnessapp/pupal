"""
Grading API endpoints - v0.

All endpoints for rubric extraction, test grading, and PDF annotation.
Updated to support the new two-phase rubric extraction with sub-questions.
"""
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, Body, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
    QuestionMapping,
    RubricQuestion,
    GROUNDED_SYSTEM_PROMPT,
    GROUNDED_TRANSCRIPTION_PROMPT,
)
from ...database import get_db, AsyncSessionLocal
from ...models.grading import Rubric, GradedTest
from ...services.pdf_preview_service import generate_pdf_previews
from ...services.grading_service import (
    parse_student_test_with_mappings,
    grade_student_test,
    grade_student_tests_batch,
    save_graded_test,
    get_graded_tests_by_rubric_id,
    get_graded_test_by_id,
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
    # Transcription review schemas
    TranscribedAnswerWithPages,
    TranscriptionReviewResponse,
    StudentAnswerInput,
    GradeWithTranscriptionRequest,
)
from ...services.gcs_service import get_gcs_service

import os

# Feature flag for new Document AI pipeline
USE_DOCAI_PIPELINE = os.getenv("USE_DOCAI_PIPELINE", "false").lower() == "true"


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

        # Upload PDF pages to GCS and get signed URLs
        try:
            gcs = get_gcs_service()
            _, page_paths = gcs.upload_pdf_with_pages(
                pdf_bytes, 
                file.filename or "rubric.pdf",
                folder="rubric-previews"
            )
            page_urls = gcs.get_signed_urls_for_pages(page_paths, expiration_minutes=120)
            
            # Add URLs to page previews
            for i, page in enumerate(pages):
                if i < len(page_urls):
                    page.page_pdf_url = page_urls[i]
                    
        except Exception as e:
            logger.warning(f"Failed to upload PDF pages to GCS: {e}")
            logger.warning(f"GCS Error Type: {type(e).__name__}")
            import traceback
            logger.warning(f"GCS Traceback: {traceback.format_exc()}")
            # Graceful degradation - pages still work without URLs
        
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


@router.put(
    "/rubric/{rubric_id}",
    response_model=RubricResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update rubric by ID",
    description="Update an existing rubric's name, description, or content.",
)
async def update_rubric(
    rubric_id: UUID,
    request: SaveRubricRequest,
    db: AsyncSession = Depends(get_db),
) -> RubricResponse:
    """
    Update an existing rubric.
    """
    try:
        rubric = await get_rubric_by_id(db, rubric_id)
        
        if not rubric:
            raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")
        
        # Update fields
        if request.name is not None:
            rubric.name = request.name
        if request.description is not None:
            rubric.description = request.description
        
        # Update rubric_json with questions
        rubric_content = {
            "questions": [q.model_dump() for q in request.questions]
        }
        rubric.rubric_json = rubric_content
        
        # Recalculate total points
        total_points = 0
        for q in request.questions:
            total_points += q.total_points or 0
        rubric.total_points = total_points
        
        await db.commit()
        await db.refresh(rubric)
        
        logger.info(f"Updated rubric {rubric_id}: {rubric.name}")
        
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
        logger.error(f"Error updating rubric: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating rubric: {str(e)}")


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


# =============================================================================
# Grading Endpoints
# =============================================================================

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




@router.post(
    "/grade_handwritten_test",
    response_model=GradedTestResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Grade a handwritten test",
    description="Transcribe and grade a handwritten student test PDF against a rubric.",
)
async def grade_handwritten_test(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    test_file: UploadFile = File(..., description="Handwritten test PDF"),
    first_page_index: int = Query(0, description="Page index containing student name"),
    answered_questions: Optional[str] = Query(None, description="Optional JSON list of question numbers answered (e.g. '[1, 2]')"),
    db: AsyncSession = Depends(get_db),
) -> GradedTestResponse:
    """
    Grade a handwritten test using Vision AI transcription.
    
    Process:
    1. Transcribe handwritten code via VLM (Vision Language Model).
    2. Format transcription into structured student answers.
    3. Grade answers against the rubric using the grading agent.
    4. Save and return results.
    """
    import json
    
    # Validation: Parse active questions filter
    question_numbers: Optional[List[int]] = None
    if answered_questions:
        try:
            question_numbers = json.loads(answered_questions)
            if not isinstance(question_numbers, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="answered_questions must be a valid JSON list of integers")

    # Fetch Rubric
    rubric = await get_rubric_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")

    # Read and Validate PDF
    if not test_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    pdf_bytes = await test_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    filename = test_file.filename or "handwritten_test.pdf"
    logger.info(f"Processing handwritten test: {filename} for rubric {rubric_id}")

    # Prepare Rubric Structure for Guided Transcription
    rubric_questions = []
    all_q_nums = []
    
    for q in rubric.rubric_json.get("questions", []):
        q_num = q.get("question_number", 1)
        all_q_nums.append(q_num)
        sub_ids = [sq.get("sub_question_id", "") for sq in q.get("sub_questions", [])]
        
        rubric_questions.append(RubricQuestion(
            question_number=q_num,
            question_text=q.get("question_text"),
            sub_questions=sub_ids,
            total_points=q.get("total_points", 0),
        ))

    # Default to all questions if no filter provided
    target_questions = set(question_numbers) if question_numbers else set(all_q_nums)

    # Initialize Transcription Service
    try:
        # Use OpenAI by default as per project standard
        provider = get_vlm_provider("openai")
        service = HandwritingTranscriptionService(vlm_provider=provider)
        
        transcription_result = service.transcribe_pdf(
            pdf_bytes=pdf_bytes,
            filename=filename,
            rubric_questions=rubric_questions,
            question_mappings=None,  # Auto-detection mode
            answered_question_numbers=list(target_questions),  # Filter to answered questions only
            first_page_index=first_page_index,
            dpi=200,
        )
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription service error: {str(e)}")

    # Format for Grading Agent
    student_test_data = {
        "student_name": transcription_result.student_name or "Unknown Student",
        "filename": filename,
        "answers": [
            {
                "question_number": ans.question_number,
                "sub_question_id": ans.sub_question_id,
                "answer_text": ans.answer_text,
            }
            for ans in transcription_result.answers
            if ans.question_number in target_questions
        ],
    }

    # Filter rubric to only include answered questions
    filtered_rubric = {
        **rubric.rubric_json,
        "questions": [
            q for q in rubric.rubric_json.get("questions", [])
            if q.get("question_number") in target_questions
        ]
    }
    # Recalculate total_points for filtered rubric
    filtered_rubric["total_points"] = sum(
        q.get("total_points", 0) for q in filtered_rubric["questions"]
    )
    
    logger.info(f"Grading with filtered rubric: {len(filtered_rubric['questions'])} questions (target: {target_questions})")

    # Execute Grading
    try:
        grading_result = await grade_student_test(
            rubric=filtered_rubric,
            student_test=student_test_data,
        )
    except Exception as e:
        logger.error(f"Grading agent failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grading agent error: {str(e)}")

    # Save Results
    try:
        # Pass transcribed answers to be saved alongside grades
        saved_test = await save_graded_test(
            db=db,
            rubric_id=rubric_id,
            grading_result=grading_result,
            student_answers=student_test_data,
        )
    except Exception as e:
        logger.error(f"Database save failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save grading results")

    return GradedTestResponse(
        id=saved_test.id,
        rubric_id=saved_test.rubric_id,
        created_at=saved_test.created_at,
        student_name=saved_test.student_name,
        filename=saved_test.filename,
        total_score=saved_test.total_score,
        total_possible=saved_test.total_possible,
        percentage=saved_test.percentage,
        graded_json=saved_test.graded_json,
        student_answers_json=saved_test.student_answers_json,
    )


# =============================================================================
# Transcription Review Endpoints (separate transcribe → review → grade flow)
# =============================================================================

@router.post(
    "/transcribe_handwritten_test",
    response_model=TranscriptionReviewResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Transcribe handwritten test for review",
    description="Transcribe a handwritten test PDF and return results for teacher review/editing before grading.",
)
async def transcribe_handwritten_test(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    test_file: UploadFile = File(..., description="Handwritten test PDF"),
    first_page_index: int = Query(0, description="Page index containing student name"),
    answered_questions: Optional[str] = Query(None, description="JSON list of question numbers answered (e.g. '[2]' for only Q2)"),
    db: AsyncSession = Depends(get_db),
) -> TranscriptionReviewResponse:
    """
    Transcribe a handwritten test for teacher review.
    
    Returns page thumbnails alongside transcribed answers so the teacher can:
    1. Compare AI transcription with original handwriting
    2. Edit/correct any transcription errors
    3. Then proceed to grading with the corrected transcription
    
    This is step 1 of the transcribe → review → grade flow.
    """
    import uuid
    
    # Fetch Rubric
    rubric = await get_rubric_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")

    # Read and Validate PDF
    if not test_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    pdf_bytes = await test_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    filename = test_file.filename or "handwritten_test.pdf"
    logger.info(f"Transcribing handwritten test for review: {filename}")

    # Convert PDF to images for thumbnails
    try:
        images = pdf_to_images(pdf_bytes, dpi=150)
        page_previews = []
        for i, img in enumerate(images):
            thumb_b64 = image_to_base64(img, max_size=800)
            page_previews.append(PagePreview(
                page_index=i,
                page_number=i + 1,
                thumbnail_base64=thumb_b64,
                width=img.width,
                height=img.height,
            ))
    except Exception as e:
        logger.error(f"Failed to generate page previews: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    # Prepare Rubric Structure for Guided Transcription
    rubric_questions = []
    all_q_nums = []
    
    for q in rubric.rubric_json.get("questions", []):
        q_num = q.get("question_number", 1)
        all_q_nums.append(q_num)
        sub_ids = [sq.get("sub_question_id", "") for sq in q.get("sub_questions", [])]
        
        rubric_questions.append(RubricQuestion(
            question_number=q_num,
            question_text=q.get("question_text"),
            sub_questions=sub_ids,
            total_points=q.get("total_points", 0),
        ))

    # Parse answered_questions if provided
    import json as json_module
    target_q_nums: Optional[List[int]] = None
    if answered_questions:
        try:
            target_q_nums = json_module.loads(answered_questions)
            if not isinstance(target_q_nums, list):
                raise ValueError("Must be a list")
            logger.info(f"Filtering to answered questions: {target_q_nums}")
        except (json_module.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid answered_questions format: {answered_questions}, using all questions")
            target_q_nums = None
    
    # Use filtered questions or all
    questions_to_transcribe = target_q_nums if target_q_nums else all_q_nums
    logger.info(f"Transcribing questions: {questions_to_transcribe}")

    # Transcribe using configured pipeline
    try:
        if USE_DOCAI_PIPELINE:
            # Use new Document AI + VLM repair pipeline
            logger.info("Using Document AI pipeline (USE_DOCAI_PIPELINE=true)")
            from transcription_rnd.adapter import transcribe_with_docai
            transcription_result = transcribe_with_docai(
                pdf_bytes=pdf_bytes,
                filename=filename,
                rubric_questions=rubric_questions,
                answered_question_numbers=questions_to_transcribe,
                first_page_index=first_page_index,
            )
        else:
            # Use existing VLM-only pipeline (default)
            provider = get_vlm_provider("openai")
            service = HandwritingTranscriptionService(vlm_provider=provider)
            
            transcription_result = service.transcribe_pdf(
                pdf_bytes=pdf_bytes,
                filename=filename,
                rubric_questions=rubric_questions,
                question_mappings=None,  # Auto-detection mode
                answered_question_numbers=questions_to_transcribe,
                first_page_index=first_page_index,
                dpi=200,
            )
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription service error: {str(e)}")

    # Build response with page context
    answers_with_pages = []
    for ans in transcription_result.answers:
        # New DocAI pipeline provides page_indexes, VLM pipeline doesn't
        page_idxs = getattr(ans, 'page_indexes', []) or []
        answers_with_pages.append(TranscribedAnswerWithPages(
            question_number=ans.question_number,
            sub_question_id=ans.sub_question_id,
            answer_text=ans.answer_text,
            confidence=getattr(ans, 'confidence', 0.9) or 0.9,
            transcription_notes=getattr(ans, 'transcription_notes', None),
            page_indexes=page_idxs,
        ))

    logger.info(f"Transcription complete: {len(answers_with_pages)} answers for {filename}")

    return TranscriptionReviewResponse(
        transcription_id=str(uuid.uuid4()),
        rubric_id=str(rubric_id),
        student_name=transcription_result.student_name or "Unknown Student",
        filename=filename,
        total_pages=len(page_previews),
        pages=page_previews,
        answers=answers_with_pages,
        raw_transcription=transcription_result.raw_transcription,
    )


@router.post(
    "/stream_transcription",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Stream handwritten test transcription via SSE",
    description="Stream transcription with real-time text output. PDF processing happens first (blocking), then raw VLM transcription streams token-by-token, then grounded verification replaces as final chunk.",
)
async def stream_transcription(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    test_file: UploadFile = File(..., description="Handwritten test PDF"),
    first_page_index: int = Query(0, description="Page index containing student name"),
    answered_questions: Optional[str] = Query(None, description="JSON list of question numbers answered"),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream transcription of a handwritten test using Server-Sent Events (SSE).
    
    Flow:
    1. PDF processing (blocking) - generates page thumbnails
    2. Streams page thumbnails as 'page' events
    3. Streams raw VLM transcription token-by-token as 'chunk' events
    4. Sends grounded verification result as 'answer' events (replaces raw)
    5. Sends 'done' event when complete
    
    Event format: "event: {type}\\ndata: {json}\\n\\n"
    """
    import uuid as uuid_module
    import json as json_module
    
    # === BLOCKING PHASE: Validate and process PDF ===
    
    # Fetch Rubric (use the database session before starting generator)
    rubric = await get_rubric_by_id(db, rubric_id)
    if not rubric:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': f'Rubric {rubric_id} not found'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # Validate PDF
    if not test_file.filename.lower().endswith('.pdf'):
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': 'File must be a PDF'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    pdf_bytes = await test_file.read()
    if not pdf_bytes:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': 'Empty file uploaded'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    filename = test_file.filename or "handwritten_test.pdf"
    logger.info(f"Starting streaming transcription: {filename}")
    
    # Process PDF to images (blocking - happens before stream starts)
    try:
        images = pdf_to_images(pdf_bytes, dpi=150)
        images_for_transcription = pdf_to_images(pdf_bytes, dpi=200)  # Higher DPI for transcription
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': f'Failed to process PDF: {str(e)}'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # Prepare rubric structure
    rubric_questions = []
    all_q_nums = []
    for q in rubric.rubric_json.get("questions", []):
        q_num = q.get("question_number", 1)
        all_q_nums.append(q_num)
        sub_ids = [sq.get("sub_question_id", "") for sq in q.get("sub_questions", [])]
        rubric_questions.append(RubricQuestion(
            question_number=q_num,
            question_text=q.get("question_text"),
            sub_questions=sub_ids,
            total_points=q.get("total_points", 0),
        ))
    
    # Parse answered_questions
    target_q_nums = None
    if answered_questions:
        try:
            target_q_nums = json_module.loads(answered_questions)
            if not isinstance(target_q_nums, list):
                target_q_nums = None
        except json_module.JSONDecodeError:
            target_q_nums = None
    
    questions_to_transcribe = target_q_nums if target_q_nums else all_q_nums
    
    # Build question context for prompts
    question_context = ""
    if rubric_questions:
        questions_info = []
        for q in rubric_questions:
            if target_q_nums and q.question_number not in target_q_nums:
                continue
            q_info = f"שאלה {q.question_number}"
            if q.sub_questions:
                q_info += f" (סעיפים: {', '.join(q.sub_questions)})"
            questions_info.append(q_info)
        if questions_info:
            question_context = f"Student may have answered: {', '.join(questions_info)}"
    
    # Get VLM provider
    provider = get_vlm_provider("openai")
    
    # Extract student name from first page
    try:
        first_page_b64 = image_to_base64(images[first_page_index], max_size=800)
        student_name = extract_student_name_from_page(first_page_b64)
    except Exception:
        student_name = None
    
    if not student_name:
        # Try to extract from filename
        import re
        name_match = re.match(r'^([^-_0-9]+)', filename)
        student_name = name_match.group(1).strip() if name_match else "Unknown Student"
    
    transcription_id = str(uuid_module.uuid4())
    
    # === STREAMING PHASE ===
    async def event_generator():
        import asyncio
        
        try:
            # Send metadata
            yield f"event: metadata\ndata: {json_module.dumps({'transcription_id': transcription_id, 'student_name': student_name, 'filename': filename, 'total_pages': len(images)})}\n\n"
            
            # Send page thumbnails
            for i, img in enumerate(images):
                thumb_b64 = image_to_base64(img, max_size=800)
                page_data = {
                    "page_index": i,
                    "page_number": i + 1,
                    "thumbnail_base64": thumb_b64,
                    "width": img.width,
                    "height": img.height,
                }
                yield f"event: page\ndata: {json_module.dumps(page_data)}\n\n"
            
            # Process each page
            all_answers = []
            
            for page_idx, page_img in enumerate(images_for_transcription):
                page_number = page_idx + 1
                
                # Send phase update
                yield f"event: phase\ndata: {json_module.dumps({'phase': 'transcribing', 'current_page': page_number, 'total_pages': len(images)})}\n\n"
                
                # Prepare image for VLM
                page_b64 = image_to_base64(page_img, max_size=2000)
                
                # Build grounded prompt
                user_prompt = GROUNDED_TRANSCRIPTION_PROMPT.format(
                    page_number=page_number,
                    question_context=question_context,
                )
                
                # Stream raw transcription
                accumulated_text = ""
                try:
                    for chunk in provider.transcribe_images_stream(
                        images_b64=[page_b64],
                        system_prompt=GROUNDED_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        max_tokens=4000,
                        temperature=0.1,
                    ):
                        accumulated_text += chunk
                        # Send chunk event
                        yield f"event: chunk\ndata: {json_module.dumps({'page': page_number, 'delta': chunk})}\n\n"
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Streaming error on page {page_number}: {e}")
                    yield f"event: error\ndata: {json_module.dumps({'message': f'Transcription error on page {page_number}: {str(e)}'})}\n\n"
                    continue
                
                # Parse the accumulated response into structured data
                try:
                    # Try to extract JSON from the response
                    json_match = re.search(r'\{[\s\S]*\}', accumulated_text)
                    if json_match:
                        parsed = json_module.loads(json_match.group())
                        transcription = parsed.get("transcription", {})
                        
                        for ans in transcription.get("answers", []):
                            answer_data = {
                                "question_number": ans.get("question_number", 1),
                                "sub_question_id": ans.get("sub_question_id"),
                                "answer_text": ans.get("answer_text", ""),
                                "confidence": ans.get("confidence", 0.9),
                                "page_indexes": [page_idx],
                            }
                            all_answers.append(answer_data)
                            
                            # Send answer event
                            yield f"event: answer\ndata: {json_module.dumps(answer_data)}\n\n"
                except Exception as parse_error:
                    logger.warning(f"Failed to parse transcription response: {parse_error}")
                    # Send raw text as a single answer
                    answer_data = {
                        "question_number": 1,
                        "sub_question_id": None,
                        "answer_text": accumulated_text,
                        "confidence": 0.5,
                        "page_indexes": [page_idx],
                    }
                    all_answers.append(answer_data)
                    yield f"event: answer\ndata: {json_module.dumps(answer_data)}\n\n"
            
            # Signal completion
            yield f"event: done\ndata: {json_module.dumps({'total_answers': len(all_answers)})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream generator error: {e}", exc_info=True)
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post(
    "/grade_with_transcription",
    response_model=GradedTestResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Grade using teacher-edited transcription",
    description="Grade a test using teacher-reviewed/edited transcription. Step 2 of transcribe → review → grade flow.",
)
async def grade_with_edited_transcription(
    request: GradeWithTranscriptionRequest,
    db: AsyncSession = Depends(get_db),
) -> GradedTestResponse:
    """
    Grade a test using teacher-edited transcription.
    
    This is step 2 of the transcribe → review → grade flow.
    The teacher has already reviewed and corrected the AI transcription,
    so we skip the VLM transcription step and grade directly.
    """
    # Fetch Rubric
    rubric = await get_rubric_by_id(db, request.rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail=f"Rubric {request.rubric_id} not found")

    logger.info(f"Grading with edited transcription: {request.filename} ({len(request.answers)} answers)")

    # Determine which questions to grade
    all_q_nums = [q.get("question_number") for q in rubric.rubric_json.get("questions", [])]
    target_questions = set(request.answered_question_numbers or all_q_nums)

    # Format for Grading Agent
    student_test_data = {
        "student_name": request.student_name,
        "filename": request.filename,
        "answers": [
            {
                "question_number": ans.question_number,
                "sub_question_id": ans.sub_question_id,
                "answer_text": ans.answer_text,
            }
            for ans in request.answers
            if ans.question_number in target_questions
        ],
    }

    # Filter rubric to only include answered questions
    filtered_rubric = {
        **rubric.rubric_json,
        "questions": [
            q for q in rubric.rubric_json.get("questions", [])
            if q.get("question_number") in target_questions
        ]
    }
    filtered_rubric["total_points"] = sum(
        q.get("total_points", 0) for q in filtered_rubric["questions"]
    )

    # Execute Grading
    try:
        grading_result = await grade_student_test(
            rubric=filtered_rubric,
            student_test=student_test_data,
        )
    except Exception as e:
        logger.error(f"Grading failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")

    # Save Result
    graded_test = GradedTest(
        rubric_id=request.rubric_id,
        student_name=request.student_name,
        student_answers_json=student_test_data,
        graded_json=grading_result,
        total_score=grading_result.get("total_score", 0),
        total_possible=filtered_rubric["total_points"],
        percentage=round(
            grading_result.get("total_score", 0) / filtered_rubric["total_points"] * 100
            if filtered_rubric["total_points"] > 0 else 0,
            1
        ),
    )
    
    db.add(graded_test)
    await db.commit()
    await db.refresh(graded_test)

    logger.info(f"Grading complete: {request.student_name} scored {graded_test.total_score}/{graded_test.total_possible}")

    return GradedTestResponse(
        id=graded_test.id,
        rubric_id=graded_test.rubric_id,
        created_at=graded_test.created_at,
        student_name=graded_test.student_name,
        total_score=graded_test.total_score,
        total_possible=graded_test.total_possible,
        percentage=graded_test.percentage,
        graded_json=graded_test.graded_json,
        student_answers_json=graded_test.student_answers_json,
    )



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
    tests = await get_graded_tests_by_rubric_id(db, rubric_id)
    
    return GradedTestsListResponse(
        rubric_id=rubric_id,
        count=len(tests),
        graded_tests=[
            GradedTestResponse(
                id=t.id,
                rubric_id=t.rubric_id,
                created_at=t.created_at,
                student_name=t.student_name,
                filename=t.filename,
                total_score=t.total_score,
                total_possible=t.total_possible,
                percentage=t.percentage,
                graded_json=t.graded_json,
                student_answers_json=t.student_answers_json,
            )
            for t in tests
        ],
    )


@router.get(
    "/rubric/{rubric_id}/graded_tests",
    response_model=list[GradedTestResponse],
    responses={404: {"model": ErrorResponse}},
    summary="Get all graded tests for a rubric (path param)",
    description="Retrieve all graded tests for a rubric using path parameter.",
)
async def get_graded_tests_by_rubric(
    rubric_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[GradedTestResponse]:
    """
    Get all graded tests for a given rubric ID (path parameter version).
    """
    tests = await get_graded_tests_by_rubric_id(db, rubric_id)
    
    return [
        GradedTestResponse(
            id=t.id,
            rubric_id=t.rubric_id,
            created_at=t.created_at,
            student_name=t.student_name,
            filename=t.filename,
            total_score=t.total_score,
            total_possible=t.total_possible,
            percentage=t.percentage,
            graded_json=t.graded_json,
            student_answers_json=t.student_answers_json,
        )
        for t in tests
    ]


@router.get(
    "/graded_test/{graded_test_id}",
    response_model=GradedTestResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single graded test by ID",
    description="Retrieve full details of a graded test by its ID.",
)
async def get_single_graded_test(
    graded_test_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> GradedTestResponse:
    """
    Get full details of a graded test by ID.
    """
    test = await get_graded_test_by_id(db, graded_test_id)
    
    if not test:
        raise HTTPException(status_code=404, detail=f"Graded test {graded_test_id} not found")
    
    return GradedTestResponse(
        id=test.id,
        rubric_id=test.rubric_id,
        created_at=test.created_at,
        student_name=test.student_name,
        filename=test.filename,
        total_score=test.total_score,
        total_possible=test.total_possible,
        percentage=test.percentage,
        graded_json=test.graded_json,
        student_answers_json=test.student_answers_json,
    )






# =============================================================================
# Two-Phase Streaming Transcription Endpoint
# =============================================================================

VERIFICATION_SYSTEM_PROMPT = """You are a VERIFICATION SCANNER. Your job is to VERIFY and CORRECT a previous transcription.

=== YOUR TASK ===
1. COMPARE the raw transcription against what you see in the image
2. FIX any hallucinations or errors
3. OUTPUT only the corrected code

=== CRITICAL RULES ===
- If the raw transcription invented code that isn't on the page, REMOVE IT
- If the raw transcription missed code that IS on the page, ADD IT
- Preserve exact spacing, indentation, and formatting from the image
- Do NOT fix student errors - only fix transcription errors
- Use [?] for illegible characters - NEVER guess

=== OUTPUT ===
Return ONLY valid JSON with the corrected transcription."""


VERIFICATION_PROMPT = """Compare this raw transcription against the handwritten page image.

RAW TRANSCRIPTION (may contain errors):
```
{raw_transcription}
```

VISUAL GROUNDING FROM IMAGE:
- Identified class name: {class_name}
- Identified methods: {methods}
- Identified fields: {fields}

YOUR TASK:
1. Look at each line in the raw transcription
2. Verify it matches what's ACTUALLY written on the page
3. Fix any hallucinations or transcription errors
4. Keep student's actual errors (bugs, typos they wrote)

Return corrected JSON:
{{
  "transcription": {{
    "student_name": "{student_name}",
    "page_number": {page_number},
    "answers": [
      {{
        "question_number": 1,
        "sub_question_id": null,
        "answer_text": "CORRECTED code here",
        "confidence": 0.95
      }}
    ]
  }},
  "corrections_made": ["list of corrections if any"]
}}

{question_context}"""


def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from VLM response."""
    import re
    import json as json_module 
    try:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_module.loads(json_match.group())
    except json_module.JSONDecodeError:
        pass
    return None


def extract_visual_grounding(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Extract visual grounding info from parsed response."""
    grounding = parsed.get("visual_grounding", {})
    return {
        "class_name": grounding.get("class_name", "unknown"),
        "methods": grounding.get("method_names", []),
        "fields": grounding.get("field_names", []),
    }


@router.post(
    "/stream_transcription_v2",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Two-phase streaming transcription (raw → verified)",
    description="Stream handwriting transcription with two phases per page.",
)
async def stream_transcription_v2(
    rubric_id: UUID = Query(..., description="ID of the rubric"),
    test_file: UploadFile = File(..., description="Handwritten test PDF"),
    first_page_index: int = Query(0, description="Page index containing student name"),
    answered_questions: Optional[str] = Query(None, description="JSON list of question numbers answered"),
    db: AsyncSession = Depends(get_db),
):
    """Two-phase streaming transcription endpoint."""
    import uuid as uuid_module
    import json as json_module
    import re
    import asyncio
    
    # Fetch Rubric
    rubric = await get_rubric_by_id(db, rubric_id)
    if not rubric:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': f'Rubric {rubric_id} not found'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # Validate PDF
    if not test_file.filename.lower().endswith('.pdf'):
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': 'File must be a PDF'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    pdf_bytes = await test_file.read()
    if not pdf_bytes:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': 'Empty file uploaded'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    filename = test_file.filename or "handwritten_test.pdf"
    logger.info(f"Starting two-phase streaming transcription: {filename}")
    
    # Process PDF to images
    try:
        images_thumbnail = pdf_to_images(pdf_bytes, dpi=150)
        images_hires = pdf_to_images(pdf_bytes, dpi=200)
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': f'Failed to process PDF: {str(e)}'})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # Prepare rubric structure
    rubric_questions = []
    all_q_nums = []
    for q in rubric.rubric_json.get("questions", []):
        q_num = q.get("question_number", 1)
        all_q_nums.append(q_num)
        sub_ids = [sq.get("sub_question_id", "") for sq in q.get("sub_questions", [])]
        rubric_questions.append(RubricQuestion(
            question_number=q_num,
            question_text=q.get("question_text"),
            sub_questions=sub_ids,
            total_points=q.get("total_points", 0),
        ))
    
    # Parse answered_questions
    target_q_nums = None
    if answered_questions:
        try:
            target_q_nums = json_module.loads(answered_questions)
            if not isinstance(target_q_nums, list):
                target_q_nums = None
        except json_module.JSONDecodeError:
            target_q_nums = None
    
    # Build question context
    question_context = ""
    if rubric_questions:
        questions_info = []
        for q in rubric_questions:
            if target_q_nums and q.question_number not in target_q_nums:
                continue
            q_info = f"שאלה {q.question_number}"
            if q.sub_questions:
                q_info += f" (סעיפים: {', '.join(q.sub_questions)})"
            questions_info.append(q_info)
        if questions_info:
            question_context = f"Student may have answered: {', '.join(questions_info)}"
    
    # Get VLM provider
    provider = get_vlm_provider("openai")
    
    # Student name - extracted from filename (teacher provides name via frontend)
    name_match = re.match(r'^([^-_0-9]+)', filename)
    student_name = name_match.group(1).strip() if name_match else "Unknown Student"
    
    transcription_id = str(uuid_module.uuid4())
    
    async def event_generator():
        try:
            # 1. Send metadata
            yield f"event: metadata\ndata: {json_module.dumps({'transcription_id': transcription_id, 'student_name': student_name, 'filename': filename, 'total_pages': len(images_thumbnail), 'rubric_id': str(rubric_id)})}\n\n"
            
            # 2. Send all page thumbnails
            for i, img in enumerate(images_thumbnail):
                thumb_b64 = image_to_base64(img, max_size=800)
                page_data = {
                    "page_index": i,
                    "page_number": i + 1,
                    "thumbnail_base64": thumb_b64,
                    "width": img.width,
                    "height": img.height,
                }
                yield f"event: page\ndata: {json_module.dumps(page_data)}\n\n"
            
            # 3. Process each page
            all_answers = []
            
            for page_idx, (thumb_img, hires_img) in enumerate(zip(images_thumbnail, images_hires)):
                page_number = page_idx + 1
                
                # Phase 1: Raw transcription
                yield f"event: phase\ndata: {json_module.dumps({'phase': 'transcribing', 'current_page': page_number, 'total_pages': len(images_hires), 'message': 'קורא תשובות בכתב יד...'})}\n\n"
                
                page_b64 = image_to_base64(hires_img, max_size=2000)
                user_prompt = GROUNDED_TRANSCRIPTION_PROMPT.format(
                    page_number=page_number,
                    question_context=question_context,
                )
                
                # Stream raw transcription
                raw_accumulated = ""
                try:
                    if hasattr(provider, 'transcribe_images_stream'):
                        for chunk in provider.transcribe_images_stream(
                            images_b64=[page_b64],
                            system_prompt=GROUNDED_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                            max_tokens=4000,
                            temperature=0.1,
                        ):
                            raw_accumulated += chunk
                            yield f"event: raw_chunk\ndata: {json_module.dumps({'page': page_number, 'delta': chunk})}\n\n"
                            await asyncio.sleep(0.005)
                    else:
                        raw_accumulated = provider.transcribe_images(
                            images_b64=[page_b64],
                            system_prompt=GROUNDED_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                        )
                        yield f"event: raw_chunk\ndata: {json_module.dumps({'page': page_number, 'delta': raw_accumulated})}\n\n"
                except Exception as e:
                    logger.error(f"Raw transcription error on page {page_number}: {e}")
                    yield f"event: error\ndata: {json_module.dumps({'message': f'Transcription error on page {page_number}: {str(e)}'})}\n\n"
                    continue
                
                yield f"event: raw_complete\ndata: {json_module.dumps({'page': page_number, 'full_text': raw_accumulated})}\n\n"
                
                # Parse raw response
                raw_parsed = parse_json_response(raw_accumulated)
                if not raw_parsed:
                    answer_data = {
                        "question_number": 1,
                        "sub_question_id": None,
                        "answer_text": raw_accumulated,
                        "confidence": 0.5,
                        "page_indexes": [page_idx],
                    }
                    all_answers.append(answer_data)
                    yield f"event: answer\ndata: {json_module.dumps(answer_data)}\n\n"
                    continue
                
                grounding = extract_visual_grounding(raw_parsed)
                raw_transcription = raw_parsed.get("transcription", {})
                raw_answers = raw_transcription.get("answers", [])
                
                # Phase 2: Verification
                yield f"event: phase\ndata: {json_module.dumps({'phase': 'verifying', 'current_page': page_number, 'total_pages': len(images_hires), 'message': 'מאמת ומתקן טעויות...'})}\n\n"
                
                raw_text_for_verify = "\n".join([a.get("answer_text", "") for a in raw_answers]) if raw_answers else raw_accumulated
                
                verify_prompt = VERIFICATION_PROMPT.format(
                    raw_transcription=raw_text_for_verify,
                    class_name=grounding.get("class_name", "unknown"),
                    methods=grounding.get("methods", []),
                    fields=grounding.get("fields", []),
                    student_name=student_name or "null",
                    page_number=page_number,
                    question_context=question_context,
                )
                
                verified_accumulated = ""
                try:
                    if hasattr(provider, 'transcribe_images_stream'):
                        for chunk in provider.transcribe_images_stream(
                            images_b64=[page_b64],
                            system_prompt=VERIFICATION_SYSTEM_PROMPT,
                            user_prompt=verify_prompt,
                            max_tokens=4000,
                            temperature=0.0,
                        ):
                            verified_accumulated += chunk
                            yield f"event: verified_chunk\ndata: {json_module.dumps({'page': page_number, 'delta': chunk})}\n\n"
                            await asyncio.sleep(0.005)
                    else:
                        verified_accumulated = provider.transcribe_images(
                            images_b64=[page_b64],
                            system_prompt=VERIFICATION_SYSTEM_PROMPT,
                            user_prompt=verify_prompt,
                        )
                        yield f"event: verified_chunk\ndata: {json_module.dumps({'page': page_number, 'delta': verified_accumulated})}\n\n"
                except Exception as e:
                    logger.error(f"Verification error on page {page_number}: {e}")
                    for raw_ans in raw_answers:
                        answer_data = {
                            "question_number": raw_ans.get("question_number", 1),
                            "sub_question_id": raw_ans.get("sub_question_id"),
                            "answer_text": raw_ans.get("answer_text", ""),
                            "confidence": raw_ans.get("confidence", 0.8),
                            "page_indexes": [page_idx],
                        }
                        all_answers.append(answer_data)
                        yield f"event: answer\ndata: {json_module.dumps(answer_data)}\n\n"
                    continue
                
                # Parse verified response
                verified_parsed = parse_json_response(verified_accumulated)
                verified_answers = []
                verified_text_for_boundary = ""
                
                if verified_parsed:
                    verified_transcription = verified_parsed.get("transcription", {})
                    verified_answers = verified_transcription.get("answers", [])
                    verified_text_for_boundary = "\n".join([a.get("answer_text", "") for a in verified_answers])
                else:
                    # Fallback to raw answers if verification parse fails
                    verified_answers = raw_answers
                    verified_text_for_boundary = "\n".join([a.get("answer_text", "") for a in raw_answers]) if raw_answers else raw_accumulated
                
                # Phase 3: Question Boundary Detection
                # Import detector here to avoid circular imports
                from ...services.question_boundary_detector import QuestionBoundaryDetector
                
                questions_to_transcribe = target_q_nums if target_q_nums else all_q_nums
                detector = QuestionBoundaryDetector(provider)
                
                # Build sub-questions dict from rubric
                sub_questions_dict = {}
                for rq in rubric_questions:
                    if rq.sub_questions:
                        sub_questions_dict[str(rq.question_number)] = rq.sub_questions
                
                try:
                    boundary_result = await detector.detect_boundaries(
                        page_image_b64=page_b64,
                        raw_text=raw_text_for_verify,
                        verified_text=verified_text_for_boundary,
                        answered_questions=questions_to_transcribe,
                        sub_questions=sub_questions_dict,
                        page_number=page_number,
                    )
                    
                    marked_text = boundary_result.marked_text
                    detected_questions = boundary_result.detected_questions
                    confidence_scores = boundary_result.confidence_scores
                    
                except Exception as e:
                    logger.warning(f"Boundary detection failed on page {page_number}: {e}")
                    # Fallback: use first answered question
                    first_q = questions_to_transcribe[0] if questions_to_transcribe else 1
                    marked_text = f"<Q{first_q}>{verified_text_for_boundary}"
                    detected_questions = [first_q]
                    confidence_scores = {first_q: 0.7}
                
                # Emit page_complete event with marked text
                page_complete_data = {
                    "page_number": page_number,
                    "page_index": page_idx,
                    "text": marked_text,
                    "detected_questions": detected_questions,
                    "confidence_scores": confidence_scores,
                }
                yield f"event: page_complete\ndata: {json_module.dumps(page_complete_data)}\n\n"
                
                # Also emit individual answer events for backwards compatibility
                for ans in verified_answers:
                    # Determine question number from boundary detection or answer
                    q_num = detected_questions[0] if detected_questions else ans.get("question_number", 1)
                    answer_data = {
                        "question_number": q_num,
                        "sub_question_id": ans.get("sub_question_id"),
                        "answer_text": ans.get("answer_text", ""),
                        "confidence": ans.get("confidence", 0.95),
                        "page_indexes": [page_idx],
                    }
                    all_answers.append(answer_data)
                    yield f"event: answer\ndata: {json_module.dumps(answer_data)}\n\n"
            
            # 4. Done
            yield f"event: phase\ndata: {json_module.dumps({'phase': 'done', 'current_page': len(images_hires), 'total_pages': len(images_hires), 'message': 'התמלול הושלם!'})}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'total_answers': len(all_answers)})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream generator error: {e}", exc_info=True)
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
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