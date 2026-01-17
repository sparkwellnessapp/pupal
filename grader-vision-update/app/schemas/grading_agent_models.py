"""
Grading Agent Domain Models.

Canonical data structures for the grading system.
These are the single source of truth - all formats convert TO these models.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Literal, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


# =============================================================================
# CONFIDENCE FRAMEWORK
# =============================================================================

class ConfidenceLevel(str, Enum):
    """Calibrated confidence levels for grading verdicts."""
    HIGH = "high"      # >95% accurate: exact code evidence found
    MEDIUM = "medium"  # 70-95%: partial evidence or edge case
    LOW = "low"        # <70%: guessing, needs human review


# =============================================================================
# CANONICAL DOMAIN MODELS (Internal Use)
# =============================================================================

@dataclass
class GradingRule:
    """A single deduction condition within a criterion."""
    index: int                          # For reliable LLM matching
    description: str
    deduction_points: float
    is_explicit: bool = True            # False if rule was inferred by AI
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "deduction_points": self.deduction_points,
            "is_explicit": self.is_explicit
        }


@dataclass 
class GradingCriterion:
    """Canonical criterion representation used throughout grading."""
    index: int                          # Question-level index (0-based)
    description: str
    total_points: float
    rules: List[GradingRule]
    source_format: Literal["legacy", "enhanced"] = "enhanced"
    
    @property
    def has_rules(self) -> bool:
        """Check if criterion has explicit reduction rules."""
        return len(self.rules) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "total_points": self.total_points,
            "rules": [r.to_dict() for r in self.rules],
            "source_format": self.source_format
        }


@dataclass
class GradingSubQuestion:
    """A sub-question (א, ב, ג) with its criteria."""
    sub_question_id: str               # Hebrew letter or identifier
    criteria: List[GradingCriterion] = field(default_factory=list)
    total_points: float = 0


@dataclass
class GradingQuestion:
    """A question with its criteria or sub-questions."""
    question_number: int
    question_text: Optional[str] = None
    criteria: List[GradingCriterion] = field(default_factory=list)
    sub_questions: List[GradingSubQuestion] = field(default_factory=list)
    
    @property
    def total_points(self) -> float:
        """Calculate total points from criteria or sub-questions."""
        if self.sub_questions:
            return sum(sq.total_points for sq in self.sub_questions)
        return sum(c.total_points for c in self.criteria)
    
    @property
    def all_criteria(self) -> List[GradingCriterion]:
        """Get all criteria (direct or from sub-questions)."""
        if self.sub_questions:
            return [c for sq in self.sub_questions for c in sq.criteria]
        return self.criteria


@dataclass
class NormalizedRubric:
    """Fully normalized rubric ready for grading."""
    questions: List[GradingQuestion]
    name: Optional[str] = None
    description: Optional[str] = None
    
    @property
    def total_points(self) -> float:
        return sum(q.total_points for q in self.questions)
    
    @property
    def total_criteria(self) -> int:
        return sum(len(q.all_criteria) for q in self.questions)
    
    @property
    def total_rules(self) -> int:
        return sum(len(c.rules) for q in self.questions for c in q.all_criteria)


# =============================================================================
# LLM OUTPUT SCHEMAS (Pydantic Enforced)
# =============================================================================

class RuleVerdict(BaseModel):
    """LLM's verdict on a single reduction rule."""
    rule_index: int = Field(..., description="Index of the rule being evaluated")
    verdict: Literal["PASS", "FAIL"] = Field(..., description="PASS=satisfied, FAIL=violated")
    evidence: str = Field(..., min_length=1, description="Code evidence or explanation")
    confidence: ConfidenceLevel = Field(..., description="How confident is this verdict")
    explanation: str = Field("", description="Hebrew explanation for the teacher")
    
    class Config:
        use_enum_values = True


class CriterionEvaluation(BaseModel):
    """Evaluation of all rules within a single criterion."""
    criterion_index: int = Field(..., description="Index of the criterion")
    rule_verdicts: List[RuleVerdict] = Field(default_factory=list)
    extra_observations: List[str] = Field(default_factory=list, description="Additional issues found")


class GradingLLMResponse(BaseModel):
    """
    Root response schema from the grading LLM.
    All LLM output is validated through this model.
    """
    evaluations: List[CriterionEvaluation] = Field(default_factory=list)
    rubric_mismatch_detected: bool = Field(False, description="True if student answered wrong topic")
    rubric_mismatch_reason: Optional[str] = None
    low_confidence_items: List[str] = Field(default_factory=list)


# =============================================================================
# GRADING RESULT MODELS
# =============================================================================

@dataclass
class CriterionResult:
    """Result of grading a single criterion."""
    criterion: GradingCriterion
    verdicts: List[RuleVerdict]
    points_earned: float
    points_deducted: float
    fully_evaluated: bool               # True if all rules evaluated with high/medium confidence
    
    @property
    def low_confidence_count(self) -> int:
        return sum(1 for v in self.verdicts if v.confidence == ConfidenceLevel.LOW)


@dataclass
class QuestionResult:
    """Result of grading a single question."""
    question_number: int
    criterion_results: List[CriterionResult]
    extra_observations: List[str] = field(default_factory=list)
    
    @property
    def points_earned(self) -> float:
        return sum(cr.points_earned for cr in self.criterion_results)
    
    @property
    def total_possible(self) -> float:
        return sum(cr.criterion.total_points for cr in self.criterion_results)


@dataclass
class GradingResult:
    """Complete grading result for a student test."""
    student_name: str
    filename: Optional[str]
    question_results: List[QuestionResult]
    rubric_mismatch_detected: bool = False
    rubric_mismatch_reason: Optional[str] = None
    grading_trace_id: Optional[str] = None
    
    @property
    def total_score(self) -> float:
        return sum(qr.points_earned for qr in self.question_results)
    
    @property
    def total_possible(self) -> float:
        return sum(qr.total_possible for qr in self.question_results)
    
    @property
    def percentage(self) -> float:
        if self.total_possible == 0:
            return 0.0
        return (self.total_score / self.total_possible) * 100
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to legacy format for backward compatibility."""
        flat_grades = []
        question_grades = []
        
        for qr in self.question_results:
            q_grades = []
            for cr in qr.criterion_results:
                grade = {
                    "criterion": cr.criterion.description,
                    "criterion_index": cr.criterion.index,
                    "points_earned": cr.points_earned,
                    "points_possible": cr.criterion.total_points,
                    "mark": "✓" if cr.points_earned == cr.criterion.total_points else (
                        "✗" if cr.points_earned == 0 else "✓✗"
                    ),
                    "confidence": "low" if cr.low_confidence_count > 0 else "high",
                    "explanation": ", ".join(v.explanation for v in cr.verdicts if v.explanation),
                    "rule_verdicts": [
                        {
                            "rule_index": v.rule_index,
                            "verdict": v.verdict,
                            "evidence": v.evidence,
                            "confidence": v.confidence
                        }
                        for v in cr.verdicts
                    ]
                }
                q_grades.append(grade)
                flat_grades.append({**grade, "question_number": qr.question_number})
            
            question_grades.append({
                "question_number": qr.question_number,
                "grades": q_grades,
                "extra_observations": qr.extra_observations
            })
        
        return {
            "student_name": self.student_name,
            "filename": self.filename,
            "total_score": self.total_score,
            "total_possible": self.total_possible,
            "percentage": self.percentage,
            "question_grades": question_grades,
            "grades": flat_grades,
            "rubric_mismatch_detected": self.rubric_mismatch_detected,
            "rubric_mismatch_reason": self.rubric_mismatch_reason,
            "low_confidence_items": [
                f"Q{qr.question_number}: {cr.criterion.description[:40]}..."
                for qr in self.question_results
                for cr in qr.criterion_results
                if cr.low_confidence_count > 0
            ]
        }


# =============================================================================
# OBSERVABILITY: GRADING TRACE
# =============================================================================

@dataclass
class GradingTrace:
    """Complete audit trail for debugging grading operations."""
    trace_id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Input context
    question_number: int = 0
    criterion_count: int = 0
    rule_count: int = 0
    student_code_length: int = 0
    
    # LLM interaction
    prompt_token_count: int = 0
    response_token_count: int = 0
    llm_latency_ms: int = 0
    llm_model: str = ""
    raw_response_preview: str = ""      # First 500 chars for debugging
    
    # Validation results
    parse_success: bool = True
    validation_errors: List[str] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_repaired: int = 0             # How many were filled in by repair layer
    
    # Output
    final_score: float = 0
    total_possible: float = 0
    low_confidence_count: int = 0
    
    def log_summary(self) -> str:
        """Generate a single-line log summary."""
        return (
            f"GRADING_TRACE[{self.trace_id}] Q{self.question_number}: "
            f"{self.final_score:.1f}/{self.total_possible:.1f} "
            f"(rules={self.rules_evaluated}, repaired={self.rules_repaired}, "
            f"low_conf={self.low_confidence_count}, latency={self.llm_latency_ms}ms)"
        )
