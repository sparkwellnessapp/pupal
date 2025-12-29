"""
Pydantic schemas for grading API request/response validation.
Updated with sub-question support for Hebrew tests (א, ב, ג...).
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Rubric Schemas (with sub-question support)
# =============================================================================

class CriterionSchema(BaseModel):
    """A single grading criterion."""
    description: str = Field(..., description="Description of the criterion in Hebrew")
    points: float = Field(..., description="Points allocated for this criterion")


class SubQuestionSchema(BaseModel):
    """A sub-question (א, ב, ג...) within a question."""
    sub_question_id: str = Field(..., description="Sub-question identifier (א, ב, ג, etc.)")
    sub_question_text: Optional[str] = Field(None, description="The sub-question prompt/text")
    total_points: float = Field(0, description="Total points for this sub-question")
    criteria: List[CriterionSchema] = Field(default_factory=list, description="Grading criteria for this sub-question")
    
    @model_validator(mode='after')
    def calculate_total_points(self):
        if self.criteria and self.total_points == 0:
            self.total_points = sum(c.points for c in self.criteria)
        return self


class QuestionSchema(BaseModel):
    """
    A question in the rubric.
    
    Can either have:
    - Direct criteria (no sub-questions), OR
    - Sub-questions (each with their own criteria)
    """
    question_number: int = Field(..., description="Question number (1-based)")
    question_text: Optional[str] = Field(None, description="The main question prompt/text")
    total_points: float = Field(0, description="Total points for this question")
    
    # Either direct criteria OR sub-questions (not both)
    criteria: List[CriterionSchema] = Field(default_factory=list, description="Direct criteria (if no sub-questions)")
    sub_questions: List[SubQuestionSchema] = Field(default_factory=list, description="Sub-questions (א, ב, ג...)")
    
    @model_validator(mode='after')
    def calculate_total_points(self):
        if self.total_points == 0:
            if self.sub_questions:
                self.total_points = sum(sq.total_points for sq in self.sub_questions)
            elif self.criteria:
                self.total_points = sum(c.points for c in self.criteria)
        return self
    
    @model_validator(mode='after')
    def validate_structure(self):
        # Warn if both criteria and sub_questions are provided (unusual but allowed)
        if self.criteria and self.sub_questions:
            # This is technically valid - question might have both direct criteria AND sub-questions
            pass
        return self


class RubricSchema(BaseModel):
    """The full rubric structure."""
    questions: List[QuestionSchema] = Field(default_factory=list, description="List of questions")
    
    @property
    def total_points(self) -> float:
        return sum(q.total_points for q in self.questions)
    
    @property
    def total_criteria(self) -> int:
        count = 0
        for q in self.questions:
            count += len(q.criteria)
            for sq in q.sub_questions:
                count += len(sq.criteria)
        return count


class RubricCreate(BaseModel):
    """Schema for creating/saving a rubric after teacher review."""
    name: Optional[str] = Field(None, description="Optional name for the rubric")
    description: Optional[str] = Field(None, description="Optional description")
    rubric_data: RubricSchema = Field(..., description="The rubric structure")


class RubricResponse(BaseModel):
    """Response schema for rubric endpoints."""
    id: UUID
    created_at: datetime
    name: Optional[str] = None
    description: Optional[str] = None
    total_points: Optional[float] = None
    rubric_json: Dict[str, Any]
    
    class Config:
        from_attributes = True


# =============================================================================
# PDF Preview Schemas
# =============================================================================

class PagePreview(BaseModel):
    """Preview of a single PDF page."""
    page_index: int = Field(..., description="0-based page index")
    page_number: int = Field(..., description="1-based page number for display")
    thumbnail_base64: str = Field(..., description="Base64-encoded thumbnail image (PNG)")
    width: int = Field(..., description="Original page width in pixels")
    height: int = Field(..., description="Original page height in pixels")
    page_pdf_url: Optional[str] = Field(None, description="Signed URL to individual page PDF")



class PreviewRubricPdfResponse(BaseModel):
    """Response from the preview_rubric_pdf endpoint."""
    filename: str
    page_count: int
    pages: List[PagePreview] = Field(default_factory=list, description="List of page previews")


# =============================================================================
# Extraction Request Schemas (Teacher's page mappings)
# =============================================================================

class SubQuestionPageMapping(BaseModel):
    """Mapping of a sub-question to its PDF pages."""
    sub_question_id: str = Field(..., description="Sub-question identifier (א, ב, ג, etc.)")
    sub_question_page_indexes: List[int] = Field(
        default_factory=list, 
        description="Page indexes containing this sub-question's text (optional, may be on same page as question)"
    )
    criteria_page_indexes: List[int] = Field(
        ..., 
        description="Page indexes containing the rubric/criteria table for this sub-question"
    )


class QuestionPageMapping(BaseModel):
    """
    Mapping of a question to its PDF pages.
    
    Two modes:
    1. Question WITHOUT sub-questions: provide question_page_indexes + criteria_page_indexes
    2. Question WITH sub-questions: provide question_page_indexes + sub_questions list
    """
    question_number: int = Field(..., description="Question number (1-based)")
    question_page_indexes: List[int] = Field(
        ..., 
        description="Page indexes containing the main question text"
    )
    
    # For questions WITHOUT sub-questions:
    criteria_page_indexes: List[int] = Field(
        default_factory=list, 
        description="Page indexes containing criteria (only if no sub-questions)"
    )
    
    # For questions WITH sub-questions:
    sub_questions: List[SubQuestionPageMapping] = Field(
        default_factory=list, 
        description="Sub-question mappings (א, ב, ג...)"
    )
    
    @model_validator(mode='after')
    def validate_mapping(self):
        has_direct_criteria = len(self.criteria_page_indexes) > 0
        has_sub_questions = len(self.sub_questions) > 0
        
        if not has_direct_criteria and not has_sub_questions:
            raise ValueError(
                f"Question {self.question_number} must have either criteria_page_indexes or sub_questions"
            )
        
        return self


class ExtractRubricRequest(BaseModel):
    """Request body for extract_rubric with page mappings."""
    name: Optional[str] = Field(None, description="Optional name for the rubric")
    description: Optional[str] = Field(None, description="Optional description")
    question_mappings: List[QuestionPageMapping] = Field(
        ..., 
        description="List of question-to-page mappings"
    )


# =============================================================================
# Extraction Response Schemas (for teacher review/editing)
# =============================================================================

class ExtractedCriterion(BaseModel):
    """An extracted criterion, editable by teacher."""
    description: str
    points: float
    # Metadata for UI
    extraction_confidence: Literal["high", "medium", "low"] = "high"


class ExtractedSubQuestion(BaseModel):
    """An extracted sub-question, editable by teacher."""
    sub_question_id: str
    sub_question_text: Optional[str] = None
    criteria: List[ExtractedCriterion] = Field(default_factory=list)
    total_points: float = 0
    # Metadata
    source_pages: List[int] = Field(default_factory=list, description="Pages this was extracted from")


class ExtractedQuestion(BaseModel):
    """An extracted question, editable by teacher."""
    question_number: int
    question_text: Optional[str] = None
    total_points: float = 0
    
    # Either direct criteria OR sub-questions
    criteria: List[ExtractedCriterion] = Field(default_factory=list)
    sub_questions: List[ExtractedSubQuestion] = Field(default_factory=list)
    
    # Metadata
    source_pages: List[int] = Field(default_factory=list, description="Pages this was extracted from")


class ExtractRubricResponse(BaseModel):
    """
    Response from extract_rubric endpoint.
    
    Contains extracted data for teacher to review and edit before saving.
    NOT saved to DB yet - teacher must call save_rubric after reviewing.
    """
    # Extracted rubric (editable)
    questions: List[ExtractedQuestion] = Field(default_factory=list)
    
    # Summary stats
    total_points: float = 0
    num_questions: int = 0
    num_sub_questions: int = 0
    num_criteria: int = 0
    
    # Optional metadata passed through
    name: Optional[str] = None
    description: Optional[str] = None
    
    @model_validator(mode='after')
    def calculate_stats(self):
        self.num_questions = len(self.questions)
        self.num_sub_questions = sum(len(q.sub_questions) for q in self.questions)
        
        total_criteria = 0
        total_pts = 0
        for q in self.questions:
            total_criteria += len(q.criteria)
            total_pts += sum(c.points for c in q.criteria)
            for sq in q.sub_questions:
                total_criteria += len(sq.criteria)
                total_pts += sum(c.points for c in sq.criteria)
        
        self.num_criteria = total_criteria
        self.total_points = total_pts
        return self


class SaveRubricRequest(BaseModel):
    """
    Request to save the reviewed/edited rubric to database.
    
    Teacher submits this after reviewing ExtractRubricResponse.
    """
    name: Optional[str] = Field(None, description="Name for the rubric")
    description: Optional[str] = Field(None, description="Description")
    questions: List[ExtractedQuestion] = Field(..., description="The reviewed/edited questions")


class SaveRubricResponse(BaseModel):
    """Response after saving rubric to database."""
    id: UUID
    created_at: datetime
    name: Optional[str] = None
    description: Optional[str] = None
    total_points: float
    num_questions: int
    num_criteria: int


# =============================================================================
# Student Test Schemas
# =============================================================================

class AnswerPageMapping(BaseModel):
    """Mapping of a question/sub-question answer to its PDF pages."""
    question_number: int = Field(..., description="Question number (1-based)")
    sub_question_id: Optional[str] = Field(None, description="Sub-question ID (א, ב, ג...) or None")
    page_indexes: List[int] = Field(..., description="Page indexes containing the student's answer code")


class StudentTestPageMappingRequest(BaseModel):
    """Request for student test page mappings (used for batch grading)."""
    answer_mappings: List[AnswerPageMapping] = Field(
        ...,
        description="List of answer-to-page mappings"
    )
    first_page_index: int = Field(
        default=0,
        description="Page index containing student name (usually 0)"
    )


class ParsedStudentAnswer(BaseModel):
    """A parsed student answer."""
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    has_code: bool = True
    extraction_notes: Optional[str] = None


class ParsedStudentTest(BaseModel):
    """Parsed student test result."""
    student_name: str
    filename: str
    answers: List[ParsedStudentAnswer] = Field(default_factory=list)


class PreviewStudentTestResponse(BaseModel):
    """Response from preview_student_test endpoint."""
    filename: str
    page_count: int
    pages: List[PagePreview] = Field(default_factory=list)
    # Extracted student name from first page (if found)
    detected_student_name: Optional[str] = None


class GradeTestsRequest(BaseModel):
    """Request for batch grading student tests."""
    rubric_id: UUID = Field(..., description="ID of the rubric to grade against")
    answer_mappings: List[AnswerPageMapping] = Field(
        ...,
        description="Page mappings for answers (same for all tests)"
    )
    first_page_index: int = Field(
        default=0,
        description="Page index containing student name"
    )


class GradeTestsResponse(BaseModel):
    """Response from batch grading."""
    rubric_id: UUID
    total_tests: int
    successful: int
    failed: int
    graded_tests: List['GradedTestResponse'] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    


# =============================================================================
# Grading Schemas
# =============================================================================

class GradeItemSchema(BaseModel):
    """A single graded criterion."""
    question_number: int = Field(..., description="Which question this belongs to")
    sub_question_id: Optional[str] = Field(None, description="Sub-question ID if applicable (א, ב, etc.)")
    criterion: str = Field(..., description="The graded criterion description")
    mark: str = Field(..., description="Mark given: ✓, ✗, or ✓✗")
    points_earned: float = Field(..., description="Points earned for this criterion")
    points_possible: float = Field(..., description="Points possible for this criterion")
    explanation: Optional[str] = Field(None, description="Explanation for the grade (usually in Hebrew)")
    confidence: str = Field("high", description="Confidence level: high, medium, or low")
    low_confidence_reason: Optional[str] = Field(None, description="Reason if confidence is not high")


class GradedTestSchema(BaseModel):
    """Full grading result for a student test."""
    student_name: str
    filename: Optional[str] = None
    total_score: float
    total_possible: float
    percentage: float
    grades: List[GradeItemSchema] = Field(default_factory=list)
    low_confidence_items: List[str] = Field(default_factory=list)


class GradedTestResponse(BaseModel):
    """Response schema for graded test endpoints."""
    id: UUID
    rubric_id: UUID
    created_at: datetime
    student_name: str
    filename: Optional[str] = None
    total_score: float
    total_possible: float
    percentage: float
    graded_json: Dict[str, Any]
    student_answers_json: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class CreateGradeTestResponse(BaseModel):
    """Response from the create_grade_test endpoint."""
    id: UUID
    rubric_id: UUID
    student_name: str
    total_score: float
    total_possible: float
    percentage: float
    grades: List[GradeItemSchema]
    low_confidence_items: List[str] = Field(default_factory=list)


# =============================================================================
# PDF Annotation Schemas
# =============================================================================

class GradedTestPdfResponse(BaseModel):
    """Response schema for graded PDF endpoints."""
    id: UUID
    graded_test_id: UUID
    rubric_id: UUID
    created_at: datetime
    filename: str
    gcs_uri: str
    file_size_bytes: Optional[float] = None
    
    class Config:
        from_attributes = True


class AnnotatePdfResponse(BaseModel):
    """Response from the annotate_pdf_test endpoint."""
    id: UUID
    graded_test_id: UUID
    rubric_id: UUID
    filename: str
    gcs_uri: str
    download_url: Optional[str] = None


# =============================================================================
# List Response Schemas
# =============================================================================

class GradedTestsListResponse(BaseModel):
    """Response for listing multiple graded tests."""
    rubric_id: UUID
    count: int
    graded_tests: List[GradedTestResponse]


class GradedPdfsListResponse(BaseModel):
    """Response for listing multiple graded PDFs."""
    rubric_id: UUID
    count: int
    graded_pdfs: List[GradedTestPdfResponse]


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int = 400