"""
Rubric Management API: Ontology rubric lifecycle endpoints.

This module provides REST API endpoints for the two-artifact architecture:

1. Draft Management:
   - POST /rubrics/save_ontology_draft - Save extraction result as draft
   - PUT /rubrics/{id}/draft - Update draft after teacher edits

2. Compilation:
   - POST /rubrics/{id}/compile - Compile draft to frozen contract

3. Retrieval:
   - GET /rubrics/{id} - Get rubric details with format detection
   - GET /rubrics - List rubrics with filters

All ontology rubrics follow the lifecycle:
  Extract → Save Draft → Edit → Compile → Grade

Errors are returned with proper HTTP status codes and detailed messages.
"""
import logging
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from .auth import get_current_user
from ...api.deps import get_owned_or_404

from ...models.user import User
from ...models.grading import Rubric
from ...schemas.rubric_management import (
    CompilationStatus,
    CompileRubricRequest,
    CompileRubricErrorResponse,
    CompileRubricSuccessResponse,
    CompileRubricWarningsResponse,
    RubricDetailResponse,
    RubricFormat,
    RubricListResponse,
    SaveOntologyDraftRequest,
    SaveOntologyDraftResponse,
    SaveRubricWarningsResponse,
    UpdateDraftRequest,
    UpdateDraftResponse,
)
from ...services.rubric_management_service import (
    compile_rubric,
    get_rubric_detail,
    list_rubrics,
    save_ontology_draft,
    update_rubric_draft,
)
from ...services.rubric_errors import (
    RubricSaveError,
    RubricValidationError,
    RubricCompilationError,
    RubricWarningsError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/rubrics", tags=["rubric-management"])

def _compile_error_payload(errors) -> list:
    """The compile-rejection payload the editor renders (PR-3, additive on E11).

    Every existing key is preserved, so the current flat-list renderer keeps working
    untouched. What is ADDED is what a teacher can actually act on:

      location   — the FULL PATH of the offending node (`q1.א.2`), not a wall of text.
                   This is the anchor the editor needs to scroll to the right row.
      invariant  — which named rule broke ("INV-2"), so the message is explainable.
      expected   — the declared value.
      actual     — the computed value.
      message_he — the REAL Hebrew. This used to be the ENGLISH string duplicated into
                   a Hebrew-named field, i.e. an RTL UI confidently rendering English at
                   the one moment a teacher is being told her rubric is wrong.
    """
    out = []
    for err in errors:
        if not hasattr(err, "message"):      # already a plain dict — pass through
            out.append(err)
            continue
        out.append({
            "location": err.target_id,
            "invariant": getattr(err, "invariant", None),
            "expected": getattr(err, "expected", None),
            "actual": getattr(err, "actual", None),
            "message": err.message,
            "message_he": getattr(err, "message_he", None) or err.message,
        })
    return out



# =============================================================================
# DRAFT MANAGEMENT ENDPOINTS
# =============================================================================

@router.post(
    "/save_ontology_draft",
    response_model=Union[SaveOntologyDraftResponse, SaveRubricWarningsResponse],
    status_code=201,
    responses={
        201: {"description": "Draft saved and compiled successfully"},
        400: {"description": "Validation or compilation error"},
        422: {"description": "Validation error in request body"},
    },
    summary="Save extraction result as ontology rubric with atomic compilation",
    description="""
    Save an ExtractRubricResponse from the extraction pipeline as a new rubric.
    
    **INVARIANT: A saved rubric is always a compiled rubric.**
    Validates the draft, compiles to contract, and saves both atomically.
    
    If compilation produces warnings, returns 200 with `status: warnings_require_acknowledgment`.
    Re-submit with `acknowledged_warning_ids` to proceed.
    
    **Request Body:**
    - `name`: Required rubric name
    - `description`: Optional description
    - `draft`: The ExtractRubricResponse JSON from extraction
    - `acknowledged_warning_ids`: Warning IDs from previous attempt (if any)
    """,
)
async def save_ontology_draft_endpoint(
    request: SaveOntologyDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save an ExtractRubricResponse as a new ontology rubric with atomic compilation.
    """
    try:
        result = await save_ontology_draft(
            db=db,
            name=request.name,
            draft=request.draft,
            description=request.description,
            acknowledged_warning_ids=getattr(request, 'acknowledged_warning_ids', None),
            user_id=current_user.id,
            extraction_job_id=request.extraction_job_id,
        )
        
        logger.info(f"Created ontology rubric: {result.rubric_id} (compiled)")
        return result
        
    except RubricWarningsError as e:
        # Return warnings for frontend modal
        logger.info(f"Save blocked by warnings: {len(e.errors)} warnings")
        return SaveRubricWarningsResponse(
            warnings=e.errors,
            message_he=e.message_he,
        )
    except RubricValidationError as e:
        logger.warning(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail={
            "error_type": e.error_type,
            "message_he": e.message_he,
            "errors": e.errors,
        })
    except RubricCompilationError as e:
        logger.warning(f"Compilation failed: {e}")
        raise HTTPException(status_code=400, detail={
            "error_type": e.error_type,
            "message_he": e.message_he,
            "errors": _compile_error_payload(e.errors),
        })
    except ValueError as e:
        logger.warning(f"Invalid draft: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving draft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save draft: {str(e)}")


@router.put(
    "/{rubric_id}/draft",
    response_model=Union[UpdateDraftResponse, SaveRubricWarningsResponse],
    responses={
        200: {"description": "Draft updated and compiled successfully"},
        400: {"description": "Validation or compilation error"},
        404: {"description": "Rubric not found"},
    },
    summary="Update rubric draft with atomic recompilation",
    description="""
    Update an existing rubric's draft with atomic recompilation.
    
    **INVARIANT: A saved rubric is always a compiled rubric.**
    Validates the draft, recompiles to contract, and saves both atomically.
    
    If compilation produces warnings, returns 200 with `status: warnings_require_acknowledgment`.
    Re-submit with `acknowledged_warning_ids` to proceed.
    
    **Warning:** If graded tests exist for this rubric, the response will include
    `has_existing_grades=True` to alert the teacher.
    
    **Request Body:**
    - `draft`: Updated ExtractRubricResponse JSON
    - `acknowledged_warning_ids`: Warning IDs from previous attempt (if any)
    - `edit_summary`: Optional description of changes made
    """,
)
async def update_draft_endpoint(
    rubric_id: UUID,
    request: UpdateDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a rubric's draft with atomic recompilation.
    """
    try:
        result = await update_rubric_draft(
            db=db,
            rubric_id=rubric_id,
            draft=request.draft,
            user_id=current_user.id,
            acknowledged_warning_ids=request.acknowledged_warning_ids,
            edit_summary=request.edit_summary,
        )
        
        logger.info(f"Updated rubric {rubric_id} with new contract")
        return result
        
    except RubricWarningsError as e:
        # Return warnings for frontend modal
        logger.info(f"Update blocked by warnings: {len(e.errors)} warnings")
        return SaveRubricWarningsResponse(
            warnings=e.errors,
            message_he=e.message_he,
        )
    except RubricValidationError as e:
        logger.warning(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail={
            "error_type": e.error_type,
            "message_he": e.message_he,
            "errors": e.errors,
        })
    except RubricCompilationError as e:
        logger.warning(f"Compilation failed: {e}")
        raise HTTPException(status_code=400, detail={
            "error_type": e.error_type,
            "message_he": e.message_he,
            "errors": _compile_error_payload(e.errors),
        })
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error updating draft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update draft: {str(e)}")


# =============================================================================
# COMPILATION ENDPOINT
# =============================================================================

@router.post(
    "/{rubric_id}/compile",
    response_model=Union[
        CompileRubricSuccessResponse,
        CompileRubricWarningsResponse,
        CompileRubricErrorResponse,
    ],
    responses={
        200: {
            "description": "Compilation result",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Successful compilation",
                            "value": {
                                "status": "success",
                                "rubric_id": "...",
                                "contract_version": "...",
                                "compiled_at": "...",
                                "is_compiled": True,
                                "stats": {"total_points": 100, "total_questions": 3}
                            }
                        },
                        "warnings": {
                            "summary": "Warnings require acknowledgment",
                            "value": {
                                "status": "warnings_require_acknowledgment",
                                "rubric_id": "...",
                                "warnings": [
                                    {"id": "narrowness_issue:q1.c0", "message": "..."}
                                ]
                            }
                        },
                        "error": {
                            "summary": "Compilation error",
                            "value": {
                                "status": "compilation_error",
                                "rubric_id": "...",
                                "errors": [
                                    {"id": "grounding_issue:q1", "message": "..."}
                                ]
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "Rubric not found"},
        400: {"description": "Rubric has no draft to compile"},
    },
    summary="Compile draft to frozen contract",
    description="""
    Compile a rubric's draft to a frozen GradingRubricContract.
    
    **Compilation validates:**
    - INV-1: Point sum per question matches declared total
    - INV-2: Point sum per criterion matches declared total
    - INV-5: Level coverage (handled by model validators)
    - INV-6: Criterion alignment (warning if no skill target)
    
    **Possible Outcomes:**
    
    1. **Success** (`status: "success"`):
       - Contract is saved to `contract_json`
       - `contract_version` is set (new UUID)
       - Rubric is ready for grading
    
    2. **Warnings** (`status: "warnings_require_acknowledgment"`):
       - Warnings exist that must be acknowledged
       - Resubmit with `acknowledged_warning_ids` containing the warning IDs
    
    3. **Errors** (`status: "compilation_error"`):
       - Errors must be fixed in the draft before compilation
       - Update the draft via `PUT /rubrics/{id}/draft`
    
    **Request Body:**
    - `acknowledged_warning_ids`: List of warning IDs to acknowledge
    - `numeric_policy`: Optional numeric handling config
    """,
)
async def compile_rubric_endpoint(
    rubric_id: UUID,
    request: CompileRubricRequest = CompileRubricRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Union[
    CompileRubricSuccessResponse,
    CompileRubricWarningsResponse,
    CompileRubricErrorResponse,
]:
    """
    Compile a rubric draft to a frozen contract.
    """
    await get_owned_or_404(db, Rubric, rubric_id, current_user.id)
    try:
        status, response = await compile_rubric(
            db=db,
            rubric_id=rubric_id,
            acknowledged_warning_ids=request.acknowledged_warning_ids,
            numeric_policy=request.numeric_policy,
        )
        
        if status == CompilationStatus.SUCCESS:
            logger.info(f"Successfully compiled rubric {rubric_id}")
        elif status == CompilationStatus.WARNINGS_REQUIRE_ACKNOWLEDGMENT:
            logger.info(f"Rubric {rubric_id} has {len(response.warnings)} warnings")
        else:
            logger.warning(f"Rubric {rubric_id} compilation failed")
        
        return response
        
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        if "no draft" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error compiling rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compilation failed: {str(e)}")


# =============================================================================
# RETRIEVAL ENDPOINTS
# =============================================================================

@router.get(
    "/{rubric_id}",
    response_model=RubricDetailResponse,
    responses={
        200: {"description": "Rubric details"},
        404: {"description": "Rubric not found"},
    },
    summary="Get rubric details",
    description="""
    Get detailed information about a rubric.
    
    **Query Parameters:**
    - `include_draft`: Include full `draft_json` in response (default: false)
    - `include_contract`: Include full `contract_json` in response (default: false)
    
    **Response includes:**
    - Format detection (ontology vs legacy)
    - Compilation status and version
    - Statistics (questions, criteria, rules, points)
    - Unacknowledged compilation warnings
    """,
)
async def get_rubric_endpoint(
    rubric_id: UUID,
    include_draft: bool = Query(False, description="Include draft_json in response"),
    include_contract: bool = Query(False, description="Include contract_json in response"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RubricDetailResponse:
    """
    Get detailed rubric information.
    """
    result = await get_rubric_detail(
        db=db,
        rubric_id=rubric_id,
        user_id=current_user.id,
        include_draft=include_draft,
        include_contract=include_contract,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Rubric {rubric_id} not found")
    
    return result


@router.get(
    "",
    response_model=RubricListResponse,
    responses={
        200: {"description": "List of rubrics"},
    },
    summary="List rubrics with filters",
    description="""
    List rubrics with optional filters.
    
    **Query Parameters:**
    - `format`: Filter by format (`ontology`, `legacy`, or omit for all)
    - `compiled_only`: Only return rubrics with compiled contracts
    - `needs_recompilation`: Filter by recompilation status
    - `limit`: Max results (default: 100)
    - `offset`: Pagination offset (default: 0)
    
    **Response includes:**
    - List of rubric summaries
    - Total count matching filters
    - Counts by format (ontology vs legacy)
    """,
)
async def list_rubrics_endpoint(
    format: Optional[RubricFormat] = Query(None, description="Filter by format"),
    compiled_only: bool = Query(False, description="Only return compiled rubrics"),
    needs_recompilation: Optional[bool] = Query(None, description="Filter by recompilation status"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RubricListResponse:
    """
    List rubrics with optional filters.
    """
    result = await list_rubrics(
        db=db,
        format_filter=format,
        compiled_only=compiled_only,
        needs_recompilation=needs_recompilation,
        limit=limit,
        offset=offset,
        user_id=current_user.id,
    )
    
    return result

