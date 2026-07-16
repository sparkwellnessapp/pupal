"""
Rubric Normalizer.

Single-point conversion from any rubric format to canonical GradingCriterion models.
This is the ONLY place format detection and conversion happens.
"""
import logging
from typing import Dict, Any, List, Optional

from ..schemas.grading_agent_models import (
    GradingRule,
    GradingCriterion,
    GradingSubQuestion,
    GradingQuestion,
    NormalizedRubric,
)

logger = logging.getLogger(__name__)


def normalize_rubric(raw_rubric: Dict[str, Any]) -> NormalizedRubric:
    """
    Convert any rubric format to canonical NormalizedRubric.
    
    This is called ONCE at the grading system boundary.
    All downstream code uses the canonical models.
    
    Supports:
    - Legacy format: questions → criteria[{description, points}]
    - Enhanced format: questions → criteria[{criterion_description, total_points, reduction_rules}]
    - Mixed format: some criteria legacy, some enhanced
    """
    questions = []
    
    for q in raw_rubric.get("questions", []):
        question = _normalize_question(q)
        questions.append(question)
    
    rubric = NormalizedRubric(
        questions=questions,
        name=raw_rubric.get("name"),
        description=raw_rubric.get("description"),
        programming_language=raw_rubric.get("programming_language"),
    )
    
    logger.info(
        f"Normalized rubric: {len(questions)} questions, "
        f"{rubric.total_criteria} criteria, {rubric.total_rules} rules, "
        f"{rubric.total_points} total points"
        + (f", language: {rubric.programming_language}" if rubric.programming_language else "")
    )
    
    return rubric


def _normalize_question(raw_question: Dict[str, Any]) -> GradingQuestion:
    """Normalize a single question with its criteria or sub-questions."""
    question_number = raw_question.get("question_number", 0)
    question_text = raw_question.get("question_text")
    
    # Check for sub-questions first
    raw_sub_questions = raw_question.get("sub_questions", [])
    if raw_sub_questions:
        sub_questions = [
            _normalize_sub_question(sq, sq_idx)
            for sq_idx, sq in enumerate(raw_sub_questions)
        ]
        return GradingQuestion(
            question_number=question_number,
            question_text=question_text,
            sub_questions=sub_questions,
        )
    
    # Direct criteria
    raw_criteria = raw_question.get("criteria", [])
    criteria = [
        _normalize_criterion(c, idx)
        for idx, c in enumerate(raw_criteria)
    ]
    
    return GradingQuestion(
        question_number=question_number,
        question_text=question_text,
        criteria=criteria,
    )


def _normalize_sub_question(
    raw_sub: Dict[str, Any], 
    sub_idx: int
) -> GradingSubQuestion:
    """Normalize a sub-question (א, ב, ג)."""
    sub_id = raw_sub.get("sub_question_id", f"sub_{sub_idx}")
    raw_criteria = raw_sub.get("criteria", [])
    
    criteria = [
        _normalize_criterion(c, idx)
        for idx, c in enumerate(raw_criteria)
    ]
    
    return GradingSubQuestion(
        sub_question_id=sub_id,
        criteria=criteria,
        total_points=sum(c.total_points for c in criteria),
    )


def _normalize_criterion(raw: Dict[str, Any], index: int) -> GradingCriterion:
    """
    Normalize a criterion from any format to canonical GradingCriterion.
    
    Detects format based on field presence:
    - Enhanced: has 'criterion_description' AND 'reduction_rules'
    - Legacy: has 'description' AND 'points'
    """
    # Detect format
    has_reduction_rules = bool(raw.get("reduction_rules"))
    has_enhanced_fields = "criterion_description" in raw or "total_points" in raw
    
    if has_reduction_rules or has_enhanced_fields:
        return _normalize_enhanced_criterion(raw, index)
    else:
        return _normalize_legacy_criterion(raw, index)


def _normalize_enhanced_criterion(raw: Dict[str, Any], index: int) -> GradingCriterion:
    """Convert enhanced format (with reduction_rules) to canonical model."""
    # Extract description (try both field names)
    description = (
        raw.get("criterion_description") or 
        raw.get("description") or 
        f"קריטריון {index + 1}"
    )
    
    # Extract total points
    total_points = float(raw.get("total_points") or raw.get("points") or 0)
    
    # Convert reduction rules
    rules = []
    for i, r in enumerate(raw.get("reduction_rules", [])):
        rules.append(GradingRule(
            index=i,
            description=r.get("description", f"כלל {i + 1}"),
            deduction_points=float(r.get("reduction_value", 0)),
            is_explicit=r.get("is_explicit", True),
        ))
    
    # If no rules but has total points, create synthetic "all-or-nothing" rule
    if not rules and total_points > 0:
        rules.append(GradingRule(
            index=0,
            description=description,
            deduction_points=total_points,
            is_explicit=False,  # Synthetic rule
        ))
        logger.debug(f"Created synthetic rule for criterion {index}: {description[:30]}...")
    
    return GradingCriterion(
        index=index,
        description=description,
        total_points=total_points,
        rules=rules,
        source_format="enhanced",
    )


def _normalize_legacy_criterion(raw: Dict[str, Any], index: int) -> GradingCriterion:
    """Convert legacy format (description + points) to canonical model."""
    description = raw.get("description", f"קריטריון {index + 1}")
    points = float(raw.get("points", 0))
    
    # Legacy criteria become single all-or-nothing rules
    rules = [
        GradingRule(
            index=0,
            description=description,
            deduction_points=points,
            is_explicit=False,  # Inferred as single rule
        )
    ]
    
    return GradingCriterion(
        index=index,
        description=description,
        total_points=points,
        rules=rules,
        source_format="legacy",
    )


def denormalize_to_legacy(rubric: NormalizedRubric) -> Dict[str, Any]:
    """
    Convert normalized rubric back to legacy format.
    Used for backward compatibility with existing code.
    """
    questions = []
    
    for q in rubric.questions:
        criteria = []
        for c in q.all_criteria:
            criteria.append({
                "description": c.description,
                "points": c.total_points,
            })
        
        questions.append({
            "question_number": q.question_number,
            "question_text": q.question_text,
            "total_points": q.total_points,
            "criteria": criteria,
        })
    
    return {
        "name": rubric.name,
        "description": rubric.description,
        "questions": questions,
    }
