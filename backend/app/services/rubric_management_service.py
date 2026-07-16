"""
Rubric Management Service: Business logic for ontology rubric lifecycle.

This service handles the two-artifact architecture:
1. Save/Update Draft (ExtractRubricResponse)
2. Compile to Contract (GradingRubricContract)
3. Retrieve with format detection

Responsibilities:
- Validate ExtractRubricResponse structure
- Calculate statistics (questions, criteria, rules, points)
- Manage compilation state flags
- Coordinate with ContractCompiler for invariant validation

Design Principles:
- Service layer does NOT mutate Pydantic models from ontology_types
- All database operations use async SQLAlchemy
- Clear separation between validation and persistence
"""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.grading import Rubric, GradedTest
from ..schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    CompilationError,
    ExtractRubricResponse,
    GradingRubricContract,
    NumericPolicy,
    WarningsRequireAcknowledgment,
)
from ..schemas.rubric_management import (
    AnnotationSchema,
    CompilationStatus,
    CompileRubricErrorResponse,
    CompileRubricSuccessResponse,
    CompileRubricWarningsResponse,
    NumericPolicySchema,
    RubricDetailResponse,
    RubricFormat,
    RubricListItemSchema,
    RubricListResponse,
    RubricStatsSchema,
    SaveOntologyDraftResponse,
    UpdateDraftResponse,
)
from .contract_compiler import ContractCompiler

logger = logging.getLogger(__name__)


# =============================================================================
# STATISTICS CALCULATION
# =============================================================================

def _count_criteria(node: Dict[str, Any]) -> tuple[int, int]:
    """(criteria, rules) under a question or sub-question, at ANY depth.

    The flat version counted only `node["criteria"]`, so on a nested rubric every
    criterion below depth 1 was invisible — the same nesting-blindness INV-2 had.
    """
    criteria = node.get("criteria") or []
    n_criteria = len(criteria)
    n_rules = sum(len(c.get("rules") or []) for c in criteria)
    for sq in node.get("sub_questions") or []:
        c, r = _count_criteria(sq)
        n_criteria += c
        n_rules += r
    return n_criteria, n_rules


def _contract_total(rubric) -> Optional[float]:
    """The authoritative achievable total of a COMPILED rubric, read from the frozen
    contract. None for an uncompiled draft — there is nothing authoritative to read yet."""
    contract = getattr(rubric, "contract_json", None)
    if not contract:
        return None
    total = contract.get("total_points")
    try:
        return float(total) if total is not None else None
    except (TypeError, ValueError):
        return None


def calculate_rubric_stats(
    draft: Dict[str, Any],
    *,
    contract_total: Optional[float] = None,
) -> RubricStatsSchema:
    """
    Calculate statistics from an ExtractRubricResponse dict.

    ⚠️ `total_points` means ACHIEVABLE (§5). This function used to Σ every question's
    total_points — the OFFERED sum — which on a "choose 1 of 2" exam reported 100 for a
    rubric worth 50. That number is not cosmetic: the save path writes it to the
    `rubrics.total_points` COLUMN, so the row disagreed with its own `contract_json`,
    and the teacher's rubric card advertised a total the grader would never award.
    This was the FIFTH consumer to re-derive the denominator by re-summing.

    So: when a contract exists, its `total_points` is AUTHORITATIVE and is passed in —
    we do not recompute it here. The Σ below survives only as a best-effort estimate for
    an UNCOMPILED draft (no contract exists yet, and a draft may not even be valid); on a
    selection draft it will over-report until compilation, which is the one moment no
    contract can be consulted.
    """
    questions = draft.get("questions", [])

    total_questions = len(questions)
    total_criteria = 0
    total_rules = 0
    total_points = Decimal("0")

    for q in questions:
        c, r = _count_criteria(q)
        total_criteria += c
        total_rules += r

        q_points = q.get("total_points", "0")
        try:
            total_points += Decimal(str(q_points))
        except (ValueError, TypeError, InvalidOperation):
            pass

    return RubricStatsSchema(
        total_points=contract_total if contract_total is not None else float(total_points),
        total_questions=total_questions,
        total_criteria=total_criteria,
        total_rules=total_rules,
    )




# =============================================================================
# DRAFT MANAGEMENT
# =============================================================================

async def save_ontology_draft(
    db: AsyncSession,
    name: str,
    draft: Dict[str, Any],
    description: Optional[str] = None,
    user_id: Optional[UUID] = None,
    acknowledged_warning_ids: Optional[List[str]] = None,
    extraction_job_id: Optional[UUID] = None,
) -> SaveOntologyDraftResponse:
    """
    Save an ExtractRubricResponse as a new rubric with atomic compilation.
    
    INVARIANT: A saved rubric is always a compiled rubric.
    Returns success ONLY if both draft_json and contract_json are saved.
    
    Args:
        db: Async database session
        name: Rubric name
        draft: ExtractRubricResponse dict
        description: Optional description
        user_id: Optional owner user ID
        acknowledged_warning_ids: Warning IDs to acknowledge
        
    Returns:
        SaveOntologyDraftResponse with rubric details
        
    Raises:
        RubricValidationError: If draft structure is invalid
        RubricWarningsError: If warnings require acknowledgment
        RubricCompilationError: If compilation fails with errors
    """
    from .rubric_errors import (
        RubricValidationError,
        RubricCompilationError,
        RubricWarningsError,
    )
    
    logger.info(f"Saving new ontology rubric with atomic compile: {name}")
    acknowledged_warning_ids = acknowledged_warning_ids or []

    # Step 1: Validate draft structure
    try:
        validated_draft = ExtractRubricResponse.model_validate(draft)
        # Stamp the user-provided name so it persists in draft_json and contract_json
        validated_draft.rubric_name = name
        draft_dict = validated_draft.model_dump(mode='json')
    except Exception as e:
        logger.warning(f"Draft validation failed: {e}")
        raise RubricValidationError(
            errors=[{
                "location": "draft",
                "message": str(e),
                "message_he": "מבנה המחוון אינו תקין"
            }]
        )

    # Step 2: Compile to contract
    compiler = ContractCompiler()
    try:
        contract = compiler.compile(
            validated_draft,
            policy=NumericPolicy(),
            acknowledged_warnings=acknowledged_warning_ids,
        )
    except WarningsRequireAcknowledgment as e:
        logger.info(f"Compilation blocked by {len(e.warnings)} warnings")
        raise RubricWarningsError(
            warnings=[_annotation_to_schema(w) for w in e.warnings]
        )
    except CompilationError as e:
        logger.warning(f"Compilation failed: {e}")
        raise RubricCompilationError(
            errors=[_annotation_to_schema(err) for err in e.errors]
        )
    
    # Step 3: Atomic save - BOTH artifacts together
    # The contract is the single source of the total (§5). Do not re-sum.
    stats = calculate_rubric_stats(draft_dict, contract_total=float(contract.total_points))
    
    rubric = Rubric(
        name=name,
        description=description,
        draft_json=draft_dict,
        contract_json=contract.model_dump(mode='json'),
        contract_version=contract.contract_version,
        last_compiled_at=datetime.utcnow(),
        needs_recompilation=False,  # Invariant: always False after save
        total_points=stats.total_points,
        user_id=user_id,
        acknowledged_warnings=acknowledged_warning_ids,
        # PR-1 provenance chain: rubric → extraction job → (prompt, model,
        # tokens, source doc). None for manually-authored rubrics.
        extraction_job_id=extraction_job_id,
    )
    
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    
    logger.info(
        f"Created rubric {rubric.id} with contract {contract.contract_version}: "
        f"{stats.total_questions} questions, {stats.total_criteria} criteria"
    )

    return SaveOntologyDraftResponse(
        rubric_id=rubric.id,
        name=rubric.name,
        is_ontology_format=True,
        is_compiled=True,  # Always True now
        needs_recompilation=False,
        created_at=rubric.created_at,
        stats=stats,
    )


async def update_rubric_draft(
    db: AsyncSession,
    rubric_id: UUID,
    draft: Dict[str, Any],
    user_id: Optional[UUID] = None,
    acknowledged_warning_ids: Optional[List[str]] = None,
    edit_summary: Optional[str] = None,
) -> UpdateDraftResponse:
    """
    Update an existing rubric's draft with atomic recompilation.

    INVARIANT: A saved rubric is always a compiled rubric.
    Returns success ONLY if both draft_json and contract_json are updated.

    Args:
        db: Async database session
        rubric_id: ID of rubric to update
        draft: Updated ExtractRubricResponse dict
        user_id: When provided, only update if the rubric is owned by this user
        acknowledged_warning_ids: Warning IDs to acknowledge
        edit_summary: Optional description of changes

    Returns:
        UpdateDraftResponse with update details

    Raises:
        ValueError: If rubric not found (or not owned by user_id)
        RubricValidationError: If draft structure is invalid
        RubricWarningsError: If warnings require acknowledgment
        RubricCompilationError: If compilation fails with errors
    """
    from .rubric_errors import (
        RubricValidationError,
        RubricCompilationError,
        RubricWarningsError,
    )

    acknowledged_warning_ids = acknowledged_warning_ids or []

    # Fetch rubric — include ownership filter when user_id is provided
    query = select(Rubric).where(Rubric.id == rubric_id)
    if user_id is not None:
        query = query.where(Rubric.user_id == user_id)
    result = await db.execute(query)
    rubric = result.scalar_one_or_none()

    if not rubric:
        raise ValueError(f"Rubric {rubric_id} not found")
    
    logger.info(f"Updating rubric {rubric_id} with atomic compile")
    
    # Store previous contract version for response
    previous_contract_version = rubric.contract_version
    
    # Check if there are existing grades
    grade_count = await db.scalar(
        select(func.count(GradedTest.id)).where(GradedTest.rubric_id == rubric_id)
    )
    has_existing_grades = (grade_count or 0) > 0
    
    if has_existing_grades:
        logger.warning(
            f"Rubric {rubric_id} has {grade_count} existing grades. "
            "Editing may cause inconsistency."
        )
    
    # Step 1: Validate draft structure
    try:
        validated_draft = ExtractRubricResponse.model_validate(draft)
        draft_dict = validated_draft.model_dump(mode='json')
    except Exception as e:
        logger.warning(f"Draft validation failed: {e}")
        raise RubricValidationError(
            errors=[{
                "location": "draft",
                "message": str(e),
                "message_he": "מבנה המחוון אינו תקין"
            }]
        )
    
    # Step 2: Compile to contract
    compiler = ContractCompiler()
    try:
        contract = compiler.compile(
            validated_draft,
            policy=NumericPolicy(),
            acknowledged_warnings=acknowledged_warning_ids,
        )
    except WarningsRequireAcknowledgment as e:
        logger.info(f"Compilation blocked by {len(e.warnings)} warnings")
        raise RubricWarningsError(
            warnings=[_annotation_to_schema(w) for w in e.warnings]
        )
    except CompilationError as e:
        logger.warning(f"Compilation failed: {e}")
        raise RubricCompilationError(
            errors=[_annotation_to_schema(err) for err in e.errors]
        )
    
    # Step 3: Calculate stats — total from the contract, never re-summed (§5)
    stats = calculate_rubric_stats(draft_dict, contract_total=float(contract.total_points))
    
    # Step 4: Atomic update - BOTH artifacts together
    rubric.draft_json = draft_dict
    rubric.contract_json = contract.model_dump(mode='json')
    rubric.contract_version = contract.contract_version
    rubric.last_compiled_at = datetime.utcnow()
    rubric.needs_recompilation = False  # Invariant: always False after save
    rubric.total_points = stats.total_points
    rubric.updated_at = datetime.utcnow()
    rubric.acknowledged_warnings = acknowledged_warning_ids
    
    await db.commit()
    await db.refresh(rubric)
    
    logger.info(
        f"Updated rubric {rubric_id} with contract {contract.contract_version}"
    )

    return UpdateDraftResponse(
        rubric_id=rubric.id,
        updated_at=rubric.updated_at,
        needs_recompilation=False,  # Always False now
        previous_contract_version=previous_contract_version,
        has_existing_grades=has_existing_grades,
        stats=stats,
    )


# =============================================================================
# COMPILATION
# =============================================================================

def _annotation_to_schema(annotation: Annotation) -> AnnotationSchema:
    """Convert ontology Annotation to API schema.

    This is the ONLY chokepoint between the compiler's diagnostics and the teacher's
    screen. It used to drop four fields on the floor (see AnnotationSchema) — the named
    invariant, both numbers, and the Hebrew. Keep it total: if you add a field to
    Annotation, add it here.
    """
    return AnnotationSchema(
        id=annotation.id,
        annotation_type=annotation.annotation_type,
        severity=annotation.severity.value if isinstance(annotation.severity, AnnotationSeverity) else annotation.severity,
        message=annotation.message,
        target_id=annotation.target_id,
        invariant=annotation.invariant,
        expected=annotation.expected,
        actual=annotation.actual,
        message_he=annotation.message_he,
    )


async def compile_rubric(
    db: AsyncSession,
    rubric_id: UUID,
    acknowledged_warning_ids: Optional[List[str]] = None,
    numeric_policy: Optional[NumericPolicySchema] = None,
) -> Tuple[CompilationStatus, Any]:
    """
    Compile a rubric draft to a frozen contract.
    
    Flow:
    1. Fetch rubric, validate draft_json exists
    2. Parse draft as ExtractRubricResponse
    3. Call ContractCompiler with acknowledged warnings
    4. Handle compilation result (success, warnings, errors)
    5. On success: save contract_json, update metadata
    
    Args:
        db: Async database session
        rubric_id: ID of rubric to compile
        acknowledged_warning_ids: Warning IDs teacher acknowledged
        numeric_policy: Optional numeric policy for compilation
        
    Returns:
        Tuple of (CompilationStatus, response object)
        
    Raises:
        ValueError: If rubric not found or has no draft
    """
    acknowledged_warning_ids = acknowledged_warning_ids or []
    
    # Fetch rubric
    result = await db.execute(
        select(Rubric).where(Rubric.id == rubric_id)
    )
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        raise ValueError(f"Rubric {rubric_id} not found")
    
    if not rubric.draft_json:
        raise ValueError(f"Rubric {rubric_id} has no draft to compile")
    
    logger.info(f"Compiling rubric {rubric_id} (attempt #{rubric.compilation_attempts + 1})")
    
    # Increment compilation attempts
    rubric.compilation_attempts = (rubric.compilation_attempts or 0) + 1
    
    # Parse draft as ExtractRubricResponse
    try:
        draft_response = ExtractRubricResponse.model_validate(rubric.draft_json)
    except Exception as e:
        logger.error(f"Failed to parse draft: {e}")
        error_annotation = AnnotationSchema(
            id="parse_error:draft",
            annotation_type="grounding_issue",
            severity="error",
            message=f"Failed to parse draft: {str(e)}",
            target_id=None,
        )
        await db.commit()  # Save incremented attempt count
        return (
            CompilationStatus.COMPILATION_ERROR,
            CompileRubricErrorResponse(
                rubric_id=rubric_id,
                errors=[error_annotation],
                message=f"Draft parsing failed: {str(e)}",
            )
        )
    
    # Build numeric policy
    if numeric_policy:
        policy = NumericPolicy(
            precision=Decimal(numeric_policy.precision),
            rounding_mode=numeric_policy.rounding_mode,
            sum_tolerance=Decimal(numeric_policy.sum_tolerance),
        )
    else:
        policy = NumericPolicy()
    
    # Compile
    compiler = ContractCompiler()
    
    try:
        contract = compiler.compile(
            draft_response,
            policy=policy,
            acknowledged_warnings=acknowledged_warning_ids,
        )
        
        # Success! Save contract
        contract_dict = contract.model_dump(mode='json')
        
        rubric.contract_json = contract_dict
        rubric.contract_version = contract.contract_version
        rubric.last_compiled_at = datetime.utcnow()
        rubric.needs_recompilation = False
        rubric.acknowledged_warnings = acknowledged_warning_ids
        
        await db.commit()
        await db.refresh(rubric)
        
        stats = calculate_rubric_stats(
            rubric.draft_json, contract_total=float(contract.total_points)
        )
        
        logger.info(
            f"Compiled rubric {rubric_id} → contract version {contract.contract_version}"
        )
        
        return (
            CompilationStatus.SUCCESS,
            CompileRubricSuccessResponse(
                rubric_id=rubric_id,
                contract_version=contract.contract_version,
                compiled_at=rubric.last_compiled_at,
                is_compiled=True,
                stats=stats,
            )
        )
        
    except WarningsRequireAcknowledgment as e:
        # Warnings need acknowledgment
        await db.commit()  # Save incremented attempt count
        
        warnings_schemas = [_annotation_to_schema(w) for w in e.warnings]
        
        logger.info(
            f"Rubric {rubric_id} compilation blocked by {len(e.warnings)} warnings"
        )
        
        return (
            CompilationStatus.WARNINGS_REQUIRE_ACKNOWLEDGMENT,
            CompileRubricWarningsResponse(
                rubric_id=rubric_id,
                warnings=warnings_schemas,
            )
        )
        
    except CompilationError as e:
        # Compilation errors
        await db.commit()  # Save incremented attempt count
        
        errors_schemas = [_annotation_to_schema(err) for err in e.errors]
        
        logger.warning(
            f"Rubric {rubric_id} compilation failed with {len(e.errors)} errors"
        )
        
        return (
            CompilationStatus.COMPILATION_ERROR,
            CompileRubricErrorResponse(
                rubric_id=rubric_id,
                errors=errors_schemas,
                message=str(e),
            )
        )
        
    except Exception as e:
        # Unexpected error
        await db.commit()
        logger.error(f"Unexpected compilation error: {e}", exc_info=True)
        
        error_annotation = AnnotationSchema(
            id="unexpected_error:compilation",
            annotation_type="grounding_issue",
            severity="error",
            message=f"Unexpected error: {str(e)}",
            target_id=None,
        )
        
        return (
            CompilationStatus.COMPILATION_ERROR,
            CompileRubricErrorResponse(
                rubric_id=rubric_id,
                errors=[error_annotation],
                message=f"Unexpected compilation error: {str(e)}",
            )
        )


# =============================================================================
# RETRIEVAL
# =============================================================================

async def get_rubric_detail(
    db: AsyncSession,
    rubric_id: UUID,
    user_id: Optional[UUID] = None,
    include_draft: bool = False,
    include_contract: bool = False,
) -> Optional[RubricDetailResponse]:
    """
    Get detailed rubric information.

    Args:
        db: Async database session
        rubric_id: ID of rubric to fetch
        user_id: When provided, only return the rubric if it is owned by this user
        include_draft: Include draft_json in response
        include_contract: Include contract_json in response

    Returns:
        RubricDetailResponse or None if not found (or not owned by user_id)
    """
    query = select(Rubric).where(Rubric.id == rubric_id)
    if user_id is not None:
        query = query.where(Rubric.user_id == user_id)
    result = await db.execute(query)
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        return None
    
    # All rubrics are ontology format
    is_ontology = True
    rubric_format = RubricFormat.ONTOLOGY

    # Calculate stats from draft — but a COMPILED rubric reports its CONTRACT's total,
    # not a re-sum of the draft (which over-reports every selection exam).
    stats = (
        calculate_rubric_stats(rubric.draft_json, contract_total=_contract_total(rubric))
        if rubric.draft_json else None
    )
    
    # Extract unacknowledged warnings from draft annotations
    compilation_warnings = []
    if is_ontology and rubric.draft_json:
        annotations = rubric.draft_json.get("annotations", [])
        acknowledged = set(rubric.acknowledged_warnings or [])
        for ann in annotations:
            if ann.get("severity") == "warning" and ann.get("id") not in acknowledged:
                compilation_warnings.append(AnnotationSchema(
                    id=ann.get("id", ""),
                    annotation_type=ann.get("annotation_type", ""),
                    severity=ann.get("severity", "warning"),
                    message=ann.get("message", ""),
                    target_id=ann.get("target_id"),
                ))
    
    return RubricDetailResponse(
        id=rubric.id,
        name=rubric.name,
        description=rubric.description,
        created_at=rubric.created_at,
        updated_at=rubric.updated_at,
        format=rubric_format,
        is_compiled=rubric.is_compiled,
        needs_recompilation=rubric.needs_recompilation,
        contract_version=rubric.contract_version,
        last_compiled_at=rubric.last_compiled_at,
        stats=stats,
        draft_json=rubric.draft_json if include_draft else None,
        contract_json=rubric.contract_json if include_contract else None,
        compilation_warnings=compilation_warnings,
    )


async def list_rubrics(
    db: AsyncSession,
    format_filter: Optional[RubricFormat] = None,
    compiled_only: bool = False,
    needs_recompilation: Optional[bool] = None,
    user_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> RubricListResponse:
    """
    List rubrics with optional filters.
    
    Args:
        db: Async database session
        format_filter: Filter by format (ontology, legacy)
        compiled_only: Only return compiled rubrics
        needs_recompilation: Filter by recompilation status
        user_id: Filter by owner
        limit: Max results
        offset: Pagination offset
        
    Returns:
        RubricListResponse with filtered results
    """
    # Base query
    query = select(Rubric).order_by(Rubric.created_at.desc())
    
    # Apply filters
    if format_filter == RubricFormat.ONTOLOGY:
        query = query.where(Rubric.draft_json.isnot(None))
    elif format_filter == RubricFormat.LEGACY:
        query = query.where(Rubric.draft_json.is_(None))
    
    if compiled_only:
        query = query.where(
            Rubric.contract_json.isnot(None),
            Rubric.needs_recompilation == False,  # noqa: E712
        )
    
    if needs_recompilation is not None:
        query = query.where(Rubric.needs_recompilation == needs_recompilation)
    
    if user_id:
        query = query.where(Rubric.user_id == user_id)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    # Execute
    result = await db.execute(query)
    rubrics = result.scalars().all()
    
    # Build response items
    items = []
    ontology_count = 0
    legacy_count = 0
    
    for r in rubrics:
        ontology_count += 1
        stats = (
            calculate_rubric_stats(r.draft_json, contract_total=_contract_total(r))
            if r.draft_json else None
        )
        
        items.append(RubricListItemSchema(
            id=r.id,
            name=r.name,
            description=r.description,
            format=RubricFormat.ONTOLOGY,
            is_compiled=r.is_compiled,
            needs_recompilation=r.needs_recompilation,
            total_points=stats.total_points if stats else r.total_points,
            total_questions=stats.total_questions if stats else None,
            created_at=r.created_at,
            updated_at=r.updated_at,
        ))
    
    return RubricListResponse(
        rubrics=items,
        total=total,
        ontology_count=ontology_count,
        legacy_count=legacy_count,
    )


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

async def validate_rubric_can_grade(
    db: AsyncSession,
    rubric_id: UUID,
) -> Tuple[bool, Optional[str], Optional[Rubric]]:
    """
    Validate that a rubric is ready for grading.

    Returns:
        Tuple of (can_grade, error_message, rubric_object)
    """
    result = await db.execute(
        select(Rubric).where(Rubric.id == rubric_id)
    )
    rubric = result.scalar_one_or_none()

    if not rubric:
        return False, f"Rubric {rubric_id} not found", None

    if not rubric.contract_json:
        return (
            False,
            "Rubric has no compiled contract. Call POST /rubrics/{id}/compile first.",
            rubric,
        )

    return True, None, rubric

