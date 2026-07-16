"""
Unified LLM output schemas for the DOCX extraction pipeline.

DESIGN PRINCIPLES:
1. Single source of truth for all LLM-generated structures
2. All models use Pydantic for automatic validation
3. Schemas only contain information the LLM can actually provide
4. Element IDs are NOT included - they are resolved via annotation linking
"""
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Classification Output Models
# =============================================================================

class QuestionClassification(BaseModel):
    """
    LLM output for question boundary detection.
    
    DESIGN: We only ask for information the LLM can actually see in the prompt.
    Element IDs are NOT visible to the LLM - they are handled by annotation linking.
    """
    question_number: int = Field(description="The question number (1, 2, 3, etc.)")
    total_points: Optional[float] = Field(default=None, description="Total points if visible, e.g. '(30 נקודות)'")
    question_text_snippet: str = Field(
        default="",
        description="First ~50 chars of the question header for verification"
    )
    has_sub_questions: bool = Field(
        default=False,
        description="True if question has sub-sections (א, ב, ג or a, b, c)"
    )
    confidence: float = Field(default=0.8, ge=0, le=1, description="Confidence in this classification (0-1)")
    reasoning: str = Field(default="", description="Brief explanation for this classification")


class SubQuestionClassification(BaseModel):
    """
    LLM output for sub-question detection.
    
    DESIGN: Element IDs are NOT provided - they are resolved via annotation linking.
    """
    sub_question_id: str = Field(description="Sub-question identifier (א, ב, a, b, etc.)")
    parent_question: int = Field(description="Parent question number")
    total_points: Optional[float] = Field(default=None, description="Points for this sub-question")
    sub_question_text_snippet: str = Field(
        default="",
        description="First ~50 chars of the sub-question text for verification"
    )


class TableClassification(BaseModel):
    """LLM output for table classification."""
    table_id: str = Field(description="ID of the table from [TABLE: {id} - ...] header")
    table_type: str = Field(description="Type: RUBRIC_TABLE, TRACE_TABLE, EXAMPLE_DATA_TABLE, CODE_TABLE, QUESTION_LAYOUT_TABLE, or OTHER_TABLE")
    belongs_to_question: Optional[int] = Field(default=None, description="Question number this table belongs to")
    belongs_to_sub_question: Optional[str] = Field(default=None, description="Sub-question ID if applicable")
    confidence: float = Field(default=0.8, ge=0, le=1, description="Confidence (0-1)")
    reasoning: str = Field(default="", description="Brief explanation")


class DocumentClassificationResult(BaseModel):
    """Complete LLM classification response for a document."""
    questions: List[QuestionClassification] = Field(default_factory=list)
    sub_questions: List[SubQuestionClassification] = Field(default_factory=list)
    tables: List[TableClassification] = Field(default_factory=list)


# =============================================================================
# Enhancement Output Models
# =============================================================================

class ReductionRule(BaseModel):
    """A specific point deduction rule for a grading criterion."""
    description: str = Field(..., min_length=3, description="Description of the error that causes this deduction")
    reduction_value: float = Field(..., gt=0, description="Points to deduct for this error")
    is_explicit: bool = Field(default=False, description="True if explicitly stated in original text")


class EnhancedCriterion(BaseModel):
    """
    An enhanced grading criterion with reduction rules.
    
    VALIDATION: The sum of all reduction_value must equal total_points.
    """
    criterion_description: str = Field(..., min_length=3, description="Clean, readable criterion description")
    raw_text: str = Field(default="", description="Original text as backup")
    total_points: float = Field(..., ge=0, description="Total points for this criterion")
    reduction_rules: List[ReductionRule] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, description="Additional notes if any")
    
    @model_validator(mode='after')
    def validate_reduction_sum(self):
        """Ensure reduction rules sum to total_points."""
        if self.reduction_rules:
            actual_sum = sum(r.reduction_value for r in self.reduction_rules)
            if abs(actual_sum - self.total_points) > 0.01:
                raise ValueError(
                    f"reduction_rules sum ({actual_sum}) != total_points ({self.total_points}). "
                    f"Adjust reduction_value amounts to match exactly."
                )
        return self
