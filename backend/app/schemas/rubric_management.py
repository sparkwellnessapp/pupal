"""
Pydantic schemas for Ontology Rubric Management API.

These schemas support the two-artifact architecture:
- Draft (ExtractRubricResponse): Teacher-editable, rich metadata
- Contract (GradingRubricContract): Frozen, minimal, for grading

The lifecycle is:
1. Extract → ExtractRubricResponse (auto-save or manual save)
2. Edit → Update draft_json
3. Compile → GradingRubricContract (validates all invariants)
4. Grade → Uses frozen contract

All schemas enforce proper validation and provide clear API documentation.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# ENUMS
# =============================================================================

class RubricFormat(str, Enum):
    """Format of a rubric."""
    ONTOLOGY = "ontology"
    LEGACY = "legacy"


class CompilationStatus(str, Enum):
    """Status of compilation request."""
    SUCCESS = "success"
    WARNINGS_REQUIRE_ACKNOWLEDGMENT = "warnings_require_acknowledgment"
    COMPILATION_ERROR = "compilation_error"


# =============================================================================
# SHARED RESPONSE MODELS
# =============================================================================

class RubricStatsSchema(BaseModel):
    """Statistics about a rubric's structure."""
    total_points: float = Field(..., description="Total points across all questions")
    total_questions: int = Field(..., description="Number of questions")
    total_criteria: int = Field(..., description="Total criteria across all questions")
    total_rules: int = Field(..., description="Total reduction rules across all criteria")


class AnnotationSchema(BaseModel):
    """
    A compilation annotation (error, warning, or info).
    
    Errors block compilation.
    Warnings require acknowledgment.
    Info is purely informational.
    """
    id: str = Field(..., description="Unique ID for acknowledgment tracking")
    annotation_type: str = Field(
        ...,
        description="Type: grounding_issue, narrowness_issue, clarity_issue, review_flag"
    )
    severity: str = Field(..., description="Severity: error, warning, info")
    message: str = Field(..., description="Human-readable message")
    target_id: Optional[str] = Field(None, description="criterion_id or rule_id affected")

    # PR-3 (deploy-day fix): this schema is a MIRROR of ontology_types.Annotation, and a
    # mirror that omits fields is a mirror that LIES. It carried 5 of the 9 fields, so the
    # compiler's `invariant`/`expected`/`actual`/`message_he` were silently dropped on the
    # way to the teacher: the API answered a real INV-2 violation with nulls and an ENGLISH
    # sentence in a field named `message_he`, on an RTL screen. Every field added to
    # Annotation must be added here too — or better, delete this mirror (§0.4).
    invariant: Optional[str] = Field(None, description="Named invariant, e.g. INV-2")
    expected: Optional[str] = Field(None, description="The declared value")
    actual: Optional[str] = Field(None, description="The computed value")
    message_he: Optional[str] = Field(None, description="Hebrew message — the one a teacher reads")


# =============================================================================
# SAVE DRAFT REQUEST/RESPONSE
# =============================================================================

class SaveOntologyDraftRequest(BaseModel):
    """
    Request to save an ExtractRubricResponse with atomic compilation.
    
    The draft field should contain the full ExtractRubricResponse JSON
    from the extraction pipeline (DOCX or PDF-to-ontology conversion).
    """
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=255,
        description="Name for the rubric (required)"
    )
    description: Optional[str] = Field(
        None, 
        max_length=2000,
        description="Optional description"
    )
    draft: Dict[str, Any] = Field(
        ..., 
        description="ExtractRubricResponse JSON from extraction pipeline"
    )
    acknowledged_warning_ids: List[str] = Field(
        default_factory=list,
        description="Warning IDs to acknowledge from previous save attempt"
    )
    extraction_job_id: Optional[UUID] = Field(
        None,
        description="PR-1 provenance: the extraction job this draft came from "
                    "(stamped onto the rubric row; None for manual authoring)"
    )

    @field_validator('draft')
    @classmethod
    def validate_draft_structure(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that draft has minimum required structure."""
        if 'questions' not in v:
            raise ValueError("Draft must contain 'questions' field")
        if not isinstance(v['questions'], list):
            raise ValueError("'questions' must be a list")
        return v


class SaveOntologyDraftResponse(BaseModel):
    """Response after saving a draft."""
    rubric_id: UUID = Field(..., description="ID of the created/updated rubric")
    name: str
    is_ontology_format: bool = Field(True, description="Always true for ontology drafts")
    is_compiled: bool = Field(False, description="False - draft needs compilation")
    needs_recompilation: bool = Field(False, description="False for new drafts")
    created_at: datetime
    stats: RubricStatsSchema


# =============================================================================
# UPDATE DRAFT REQUEST/RESPONSE
# =============================================================================

class UpdateDraftRequest(BaseModel):
    """
    Request to update an existing draft with atomic compilation.
    
    The draft field should contain the complete updated ExtractRubricResponse.
    If warnings from a previous attempt need acknowledgment, include their IDs.
    """
    draft: Dict[str, Any] = Field(
        ..., 
        description="Updated ExtractRubricResponse JSON"
    )
    acknowledged_warning_ids: List[str] = Field(
        default_factory=list,
        description="Warning IDs to acknowledge from previous save attempt"
    )
    edit_summary: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional summary of changes made"
    )
    
    @field_validator('draft')
    @classmethod
    def validate_draft_structure(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that draft has minimum required structure."""
        if 'questions' not in v:
            raise ValueError("Draft must contain 'questions' field")
        if not isinstance(v['questions'], list):
            raise ValueError("'questions' must be a list")
        return v


class UpdateDraftResponse(BaseModel):
    """Response after updating a draft."""
    rubric_id: UUID
    updated_at: datetime
    needs_recompilation: bool = Field(
        ..., 
        description="True if contract exists and will need recompilation"
    )
    previous_contract_version: Optional[str] = Field(
        None, 
        description="Previous contract version (None if never compiled)"
    )
    has_existing_grades: bool = Field(
        False,
        description="Warning: True if graded tests exist using current contract"
    )
    stats: RubricStatsSchema


class EnhanceCriterionInput(BaseModel):
    """A single criterion to enhance with Call 2 (rules + levels)."""
    criterion_id: str = Field(..., description="Client-side criterion ID (preserved in output)")
    description: str = Field(..., min_length=1, description="Criterion description text")
    points: float = Field(..., gt=0, description="Point value for this criterion")


class EnhanceCriteriaRequest(BaseModel):
    """Request body for post-acceptance enhancement."""
    criteria: List[EnhanceCriterionInput] = Field(
        ..., min_length=1, max_length=20,
        description="Criteria to enhance (typically 1-5 newly accepted proposals)"
    )
    question_purpose: str = Field(
        default="(not available)",
        description="Question purpose from Step 1B ProposalResult — improves Call 2 quality"
    )
    sub_question_text: Optional[str] = Field(
        default=None, description="Sub-question task text (if criteria belong to a sub-question)"
    )
    example_solution: Optional[str] = Field(
        default=None, description="Example solution (truncated, for code-aware hints)"
    )
    programming_language: Optional[str] = Field(
        default=None, description="Programming language for code-aware condition_hints"
    )
    locale: str = Field(default="he-IL", description="Language locale")


class EnhancedCriterionOutput(BaseModel):
    """A single criterion enhanced with reduction rules."""
    criterion_id: str
    description: str
    points: float
    reduction_rules: List[dict] = Field(
        default_factory=list,
        description="Generated rules with scoring levels (empty if enhancement failed)"
    )


class EnhanceCriteriaResponse(BaseModel):
    """Response with enhanced criteria containing rules + levels."""
    criteria: List[EnhancedCriterionOutput]
    total_rules: int = Field(description="Total reduction rules generated across all criteria")

# =============================================================================
# COMPILE REQUEST/RESPONSE
# =============================================================================

class NumericPolicySchema(BaseModel):
    """
    Numeric handling configuration for compilation.
    
    Controls point calculations, rounding, and sum validation.
    """
    precision: str = Field(
        default="0.25",
        description="Smallest point increment (e.g., '0.25' for quarter-points)"
    )
    rounding_mode: str = Field(
        default="half_up",
        description="Python decimal rounding mode"
    )
    sum_tolerance: str = Field(
        default="0.01",
        description="Maximum allowed deviation in point sum validation"
    )
    
    @field_validator('precision', 'sum_tolerance')
    @classmethod
    def validate_decimal_string(cls, v: str) -> str:
        """Validate that string can be parsed as Decimal."""
        try:
            Decimal(v)
        except Exception:
            raise ValueError(f"Invalid decimal string: {v}")
        return v


class CompileRubricRequest(BaseModel):
    """
    Request to compile a draft to a frozen contract.
    
    If there are warnings that need acknowledgment, include their IDs
    in acknowledged_warning_ids to proceed with compilation.
    """
    acknowledged_warning_ids: List[str] = Field(
        default_factory=list,
        description="List of warning annotation IDs to acknowledge"
    )
    numeric_policy: Optional[NumericPolicySchema] = Field(
        None,
        description="Optional numeric policy (uses defaults if not provided)"
    )


class CompileRubricSuccessResponse(BaseModel):
    """Response on successful compilation."""
    status: CompilationStatus = CompilationStatus.SUCCESS
    rubric_id: UUID
    contract_version: str = Field(..., description="New contract version UUID")
    compiled_at: datetime
    is_compiled: bool = True
    stats: RubricStatsSchema


class CompileRubricWarningsResponse(BaseModel):
    """Response when warnings require acknowledgment."""
    status: CompilationStatus = CompilationStatus.WARNINGS_REQUIRE_ACKNOWLEDGMENT
    rubric_id: UUID
    warnings: List[AnnotationSchema] = Field(
        ...,
        description="Warnings that must be acknowledged to proceed"
    )
    message: str = Field(
        default="Compilation blocked: warnings require acknowledgment",
        description="Human-readable message"
    )


class CompileRubricErrorResponse(BaseModel):
    """Response when compilation fails due to errors."""
    status: CompilationStatus = CompilationStatus.COMPILATION_ERROR
    rubric_id: UUID
    errors: List[AnnotationSchema] = Field(
        ...,
        description="Errors that must be fixed before compilation"
    )
    message: str = Field(
        default="Compilation failed: errors must be resolved",
        description="Human-readable message"
    )


# Union type for compile response
CompileRubricResponse = Union[
    CompileRubricSuccessResponse,
    CompileRubricWarningsResponse,
    CompileRubricErrorResponse
]


# =============================================================================
# GET RUBRIC RESPONSE (Enhanced)
# =============================================================================

class RubricDetailResponse(BaseModel):
    """
    Enhanced rubric details response.
    
    Includes both legacy and ontology fields for backward compatibility.
    Use query params to control which large JSON fields to include.
    """
    # Core fields
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Format detection
    format: RubricFormat = Field(
        ...,
        description="'ontology' if draft_json exists, else 'legacy'"
    )
    
    # Compilation status (ontology only)
    is_compiled: bool = Field(
        False,
        description="True if contract_json exists and needs_recompilation is False"
    )
    needs_recompilation: bool = Field(
        False,
        description="True if draft was edited after last compilation"
    )
    contract_version: Optional[str] = Field(
        None,
        description="Current contract version (None if never compiled)"
    )
    last_compiled_at: Optional[datetime] = None
    
    # Statistics
    stats: Optional[RubricStatsSchema] = None
    
    # Large JSON fields (optional, controlled by query params)
    draft_json: Optional[Dict[str, Any]] = Field(
        None,
        description="ExtractRubricResponse (only if include_draft=true)"
    )
    contract_json: Optional[Dict[str, Any]] = Field(
        None,
        description="GradingRubricContract (only if include_contract=true)"
    )

    # Warnings for UI
    compilation_warnings: List[AnnotationSchema] = Field(
        default_factory=list,
        description="Unacknowledged warnings from draft annotations"
    )


# =============================================================================
# LIST RUBRICS RESPONSE (Enhanced)
# =============================================================================

class RubricListItemSchema(BaseModel):
    """Summary of a rubric for list views."""
    id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    format: RubricFormat
    is_compiled: bool
    needs_recompilation: bool
    total_points: Optional[float] = None
    total_questions: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RubricListResponse(BaseModel):
    """Response for listing rubrics."""
    rubrics: List[RubricListItemSchema]
    total: int = Field(..., description="Total count matching filters")
    ontology_count: int = Field(..., description="Count of ontology format rubrics")
    legacy_count: int = Field(..., description="Count of legacy format rubrics")
    

# =============================================================================
# ERROR SCHEMAS
# =============================================================================

class RubricNotFoundError(BaseModel):
    """Error when rubric not found."""
    detail: str = "Rubric not found"
    rubric_id: UUID


class CompilationRequiredError(BaseModel):
    """Error when grading attempted without compiled contract."""
    detail: str = "Rubric must be compiled before grading"
    rubric_id: UUID
    suggestion: str = "Call POST /rubrics/{rubric_id}/compile first"


class RecompilationRequiredError(BaseModel):
    """Error when grading attempted with stale contract."""
    detail: str = "Rubric was edited after last compilation"
    rubric_id: UUID
    last_compiled_at: Optional[datetime] = None
    suggestion: str = "Call POST /rubrics/{rubric_id}/compile to recompile"


# =============================================================================
# ATOMIC SAVE+COMPILE ERRORS (Exception classes)
# =============================================================================

class RubricSaveError(Exception):
    """Base exception for rubric save errors."""
    
    def __init__(self, error_type: str, errors: List[Any], message_he: str = ""):
        super().__init__(message_he or error_type)
        self.error_type = error_type
        self.errors = errors
        self.message_he = message_he


class RubricValidationError(RubricSaveError):
    """Raised when rubric draft validation fails."""
    
    def __init__(self, errors: List[Any], message_he: str = "המחוון אינו תקין"):
        super().__init__("validation_failed", errors, message_he)


class RubricCompilationError(RubricSaveError):
    """Raised when rubric compilation fails with errors."""
    
    def __init__(self, errors: List[Any], message_he: str = "שגיאה בהכנת המחוון"):
        super().__init__("compilation_failed", errors, message_he)


class RubricWarningsError(RubricSaveError):
    """Raised when compilation has warnings that need acknowledgment."""
    
    def __init__(self, warnings: List[Any], message_he: str = "נמצאו אזהרות שדורשות אישור"):
        super().__init__("warnings_require_acknowledgment", warnings, message_he)


# =============================================================================
# ATOMIC SAVE+COMPILE RESPONSE SCHEMAS
# =============================================================================

class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error."""
    location: str = Field(..., description="Location in rubric (e.g., 'questions[1].criteria[2]')")
    message: str = Field(..., description="Technical error message")
    message_he: str = Field(..., description="User-facing Hebrew message")


class SaveRubricErrorResponse(BaseModel):
    """Error response for failed rubric save/compile."""
    error_type: str = Field(..., description="Type: validation_failed, compilation_failed")
    message_he: str = Field(..., description="User-facing Hebrew message")
    errors: List[ValidationErrorDetail] = Field(default_factory=list)


class SaveRubricWarningsResponse(BaseModel):
    """Response when save requires warning acknowledgment."""
    status: str = Field(default="warnings_require_acknowledgment")
    message_he: str = Field(default="נמצאו אזהרות שדורשות אישור")
    warnings: List[AnnotationSchema] = Field(default_factory=list)


class SaveRubricSuccessResponse(BaseModel):
    """Success response for atomic save+compile."""
    success: bool = True
    rubric_id: UUID
    contract_version: str = Field(..., description="The compiled contract version UUID")
    stats: Optional[RubricStatsSchema] = None


# =============================================================================
# EXTRACTION RESPONSE WRAPPER (for auto-save flow)
# =============================================================================

class ExtractionNextSteps(BaseModel):
    """Next steps after extraction."""
    action: str = Field(
        default="compile",
        description="Recommended next action"
    )
    endpoint: str = Field(
        ...,
        description="Endpoint to call for next action"
    )
    warnings_preview: List[str] = Field(
        default_factory=list,
        description="Preview of compilation warnings (if any)"
    )


class ExtractionMetadata(BaseModel):
    """
    Metadata about an extraction result.
    
    Included when extraction saves to database automatically.
    """
    rubric_id: Optional[UUID] = Field(
        None,
        description="ID of saved rubric (only if auto_save=true)"
    )
    was_auto_saved: bool = Field(
        False,
        description="True if extraction was saved to database"
    )
    needs_compilation_before_grading: bool = Field(
        True,
        description="Always true - ontology rubrics require compilation"
    )
    next_steps: Optional[ExtractionNextSteps] = Field(
        None,
        description="Recommended next steps (only if auto_save=true)"
    )


class OntologyExtractionResponse(BaseModel):
    """
    Response wrapper for DOCX extraction with metadata.
    
    Combines the extraction result with save metadata and next steps.
    Used when auto_save is requested or for enriched extraction responses.
    """
    # The actual extraction result (ExtractRubricResponse fields)
    extraction_result: Dict[str, Any] = Field(
        ...,
        description="The full ExtractRubricResponse JSON"
    )
    
    # Metadata about the extraction
    metadata: ExtractionMetadata = Field(
        ...,
        description="Extraction and save metadata"
    )
    
    # Statistics computed from extraction
    stats: Optional[RubricStatsSchema] = Field(
        None,
        description="Statistics computed from extracted rubric"
    )

