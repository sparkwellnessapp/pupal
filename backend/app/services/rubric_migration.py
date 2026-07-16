"""
Rubric Migration Utilities.

Provides bidirectional conversion between legacy rubric formats and
the new ontological type system.

Key Functions:
- migrate_legacy_to_ontology: Convert legacy ExtractRubricOutput → ExtractRubricResponse
- migrate_grading_agent_to_ontology: Convert GradingCriterion → Criterion
- export_to_legacy: Convert ontology types back to legacy format

Usage:
    # Migrate stored rubric
    response = migrate_legacy_to_ontology(legacy_rubric_dict)
    
    # Compile to contract
    contract = response.compile()
"""
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    Criterion,
    # DEAD UNTIL grader redesign — see grader-migration-TODO
    # EvidencePolicy,
    ExtractRubricResponse,
    # MeasurabilityStatus,
    NumericPolicy,
    Question,
    QuestionType,
    # ReductionRule,
    # RuleKind,
    # ScoringLevel,
    SkillTarget,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LEGACY FORMAT DETECTION
# =============================================================================

def detect_rubric_format(data: Dict[str, Any]) -> str:
    """
    Detect the format of a rubric dictionary.
    
    Returns:
        'v1_legacy': Old format with description/points only
        'v1_enhanced': Has reduction_rules but old structure
        'v2_ontology': New ontological format (ExtractRubricResponse)
    """
    # Check for v2 markers
    if data.get("schema_version") == "2.0":
        return "v2_ontology"
    
    # Check if questions have criteria with reduction_rules
    for q in data.get("questions", []):
        for c in q.get("criteria", []):
            if "reduction_rules" in c or "criterion_description" in c:
                return "v1_enhanced"
    
    return "v1_legacy"


# =============================================================================
# LEGACY → ONTOLOGY MIGRATION
# =============================================================================

def migrate_legacy_to_ontology(
    legacy_data: Dict[str, Any],
    programming_language: Optional[str] = None,
    subject: str = "computer_science"
) -> ExtractRubricResponse:
    """
    Migrate legacy rubric format to ExtractRubricResponse.
    
    Handles both v1_legacy and v1_enhanced formats.
    
    Args:
        legacy_data: Legacy rubric dictionary
        programming_language: Programming language (Java, Python, etc.)
        subject: Subject matter identifier
        
    Returns:
        ExtractRubricResponse ready for compilation
    """
    format_type = detect_rubric_format(legacy_data)
    logger.info(f"Migrating rubric from format: {format_type}")
    
    if format_type == "v2_ontology":
        # Already in new format, just parse
        return ExtractRubricResponse.model_validate(legacy_data)
    
    # Extract common fields
    rubric_id = legacy_data.get("rubric_id", str(uuid4()))
    rubric_name = legacy_data.get("name", legacy_data.get("rubric_name", ""))
    
    # Calculate total points
    total_points = Decimal("0")
    questions: List[Question] = []
    annotations: List[Annotation] = []
    
    for q_idx, raw_q in enumerate(legacy_data.get("questions", [])):
        question, q_annotations = _migrate_question(raw_q, q_idx, format_type)
        questions.append(question)
        annotations.extend(q_annotations)
        total_points += question.total_points
    
    # Create response
    response = ExtractRubricResponse(
        schema_version="2.0",
        rubric_id=rubric_id,
        rubric_name=rubric_name,
        subject=subject,
        programming_language=programming_language or legacy_data.get("programming_language"),
        total_points=total_points,
        questions=questions,
        annotations=annotations,
        extraction_metadata={
            "migrated_from": format_type,
            "source_fields": list(legacy_data.keys())
        }
    )
    
    logger.info(
        f"Migration complete: {len(questions)} questions, "
        f"{sum(len(q.criteria) for q in questions)} criteria, "
        f"{len(annotations)} annotations"
    )
    
    return response


def _migrate_question(
    raw_q: Dict[str, Any],
    q_idx: int,
    format_type: str
) -> tuple[Question, List[Annotation]]:
    """Migrate a single question to ontology format."""
    annotations: List[Annotation] = []
    
    question_id = raw_q.get("question_id", f"q{q_idx + 1}")
    question_number = raw_q.get("question_number", q_idx + 1)
    
    # Detect question type from context
    question_text = raw_q.get("question_text", "")
    question_type = _infer_question_type(question_text, raw_q)
    
    # Migrate criteria
    criteria: List[Criterion] = []
    raw_criteria = raw_q.get("criteria", [])
    
    # Handle sub-questions by flattening
    for sq in raw_q.get("sub_questions", []):
        raw_criteria.extend(sq.get("criteria", []))
    
    for c_idx, raw_c in enumerate(raw_criteria):
        criterion, c_annotations = _migrate_criterion(
            raw_c, c_idx, format_type, question_id
        )
        criteria.append(criterion)
        annotations.extend(c_annotations)
    
    total_points = sum(c.points for c in criteria)
    
    return Question(
        question_id=question_id,
        question_type=question_type,
        question_text=question_text or None,
        total_points=total_points,
        criteria=criteria
    ), annotations


def _migrate_criterion(
    raw_c: Dict[str, Any],
    c_idx: int,
    format_type: str,
    question_id: str
) -> tuple[Criterion, List[Annotation]]:
    """Migrate a single criterion to ontology format with INV-2 compliance."""
    annotations: List[Annotation] = []
    
    criterion_id = raw_c.get("criterion_id", f"{question_id}_c{c_idx + 1}")
    
    # Extract description (try multiple field names)
    description = (
        raw_c.get("criterion_description") or
        raw_c.get("description") or
        f"קריטריון {c_idx + 1}"
    )
    
    # Extract points
    points = Decimal(str(
        raw_c.get("total_points") or
        raw_c.get("points") or
        "0"
    ))
    
    # Migrate rules
    rules: List[ReductionRule] = []
    
    if format_type == "v1_enhanced":
        # Has reduction_rules
        for r_idx, raw_r in enumerate(raw_c.get("reduction_rules", [])):
            rule = _migrate_reduction_rule(raw_r, r_idx, criterion_id, points)
            rules.append(rule)
    
    # === INV-2 COMPLIANCE: Ensure rules sum to criterion points ===
    if rules:
        rules_sum = sum(r.max_points for r in rules)
        
        if rules_sum < points:
            # Add remainder rule to satisfy INV-2
            remainder = points - rules_sum
            rules.append(ReductionRule(
                rule_id=f"{criterion_id}_r{len(rules)}",
                index=len(rules),
                description="נקודות על נכונות כללית",  # "Points for general correctness"
                max_points=remainder,
                scoring_type="binary",
                rule_kind=RuleKind.PRESENCE_CHECK,
            ))
            annotations.append(Annotation(
                annotation_type="review_flag",
                severity=AnnotationSeverity.INFO,
                message=f"Added remainder rule ({remainder} pts) for INV-2 compliance",
                target_id=criterion_id
            ))
        
        elif rules_sum > points:
            # Scale down proportionally to satisfy INV-2
            scale_factor = points / rules_sum
            for rule in rules:
                rule.max_points = (rule.max_points * scale_factor).quantize(Decimal("0.01"))
            annotations.append(Annotation(
                annotation_type="review_flag",
                severity=AnnotationSeverity.WARNING,
                message=f"Scaled rules from {rules_sum} to {points} pts for INV-2 compliance",
                target_id=criterion_id
            ))
    
    # If no rules, create synthetic all-or-nothing rule
    if not rules:
        rules.append(ReductionRule(
            rule_id=f"{criterion_id}_r0",
            index=0,
            description=description,
            max_points=points,
            scoring_type="binary",
            rule_kind=RuleKind.PRESENCE_CHECK,
        ))
        
        # Flag synthetic rules
        annotations.append(Annotation(
            annotation_type="review_flag",
            severity=AnnotationSeverity.INFO,
            message=f"Synthetic rule created for criterion '{description[:50]}...'",
            target_id=criterion_id
        ))
    
    # Determine measurability
    measurability = MeasurabilityStatus.MEASURABLE
    if "?" in description or "subjective" in description.lower():
        measurability = MeasurabilityStatus.PARTIALLY_MEASURABLE
        annotations.append(Annotation(
            annotation_type="review_flag",
            severity=AnnotationSeverity.WARNING,
            message=f"Criterion may be subjective: '{description[:50]}...'",
            target_id=criterion_id
        ))
    
    return Criterion(
        criterion_id=criterion_id,
        index=c_idx,
        description=description,
        points=points,
        measurability_status=measurability,
        rules=rules
    ), annotations


def _migrate_reduction_rule(
    raw_r: Dict[str, Any],
    r_idx: int,
    criterion_id: str,
    criterion_points: Decimal
) -> ReductionRule:
    """
    Migrate a reduction rule to ontology format.
    
    SEMANTIC MAPPING:
    Legacy model: reduction_value = point allocation for this rule component
                 (e.g., "3 points for correct loop structure")
    Ontology model: max_points = maximum awardable points (same as allocation)
    
    Both models represent "what this sub-component is worth" - the difference
    is that the ontology model makes levels explicit while legacy assumes binary.
    
    NOTE: If legacy model used true DEDUCTION semantics (points lost on failure
    rather than allocation), the caller should handle that conversion.
    """
    rule_id = raw_r.get("rule_id", f"{criterion_id}_r{r_idx}")
    
    description = raw_r.get("description", f"כלל {r_idx + 1}")
    
    # Legacy reduction_value = point allocation for this rule
    reduction_value = Decimal(str(raw_r.get("reduction_value", 0)))
    max_points = reduction_value  # Same semantic: points for this component
    
    # Infer rule kind from description
    rule_kind = _infer_rule_kind(description)
    
    return ReductionRule(
        rule_id=rule_id,
        index=r_idx,
        description=description,
        max_points=max_points,
        scoring_type="binary",  # Legacy rules are binary
        rule_kind=rule_kind,
    )


def _infer_question_type(text: str, raw_q: Dict[str, Any]) -> QuestionType:
    """Infer question type from text and context."""
    text_lower = text.lower()
    
    # Check for coding indicators
    coding_keywords = ["כתבו", "כתוב", "פונקציה", "מחלקה", "class", "def", "code"]
    if any(kw in text_lower for kw in coding_keywords):
        return QuestionType.CODING_TASK
    
    # Check for trace table
    if "טבלת" in text_lower and "מעקב" in text_lower:
        return QuestionType.TRACE_TABLE
    
    # Check for computation
    if "חשבו" in text_lower or "חשב" in text_lower:
        return QuestionType.COMPUTATION
    
    return QuestionType.SHORT_ANSWER


def _infer_rule_kind(description: str) -> RuleKind:
    """Infer rule kind from description."""
    desc_lower = description.lower()
    
    # Structure indicators
    if any(kw in desc_lower for kw in ["מחלקה", "class", "פונקציה", "def", "method"]):
        return RuleKind.STRUCTURE_AST
    
    # Execution indicators
    if any(kw in desc_lower for kw in ["פלט", "output", "result", "ריצה"]):
        return RuleKind.EXECUTION_TESTS
    
    # Format indicators
    if any(kw in desc_lower for kw in ["format", "תבנית", "סגנון"]):
        return RuleKind.FORMAT_REQUIREMENT
    
    # Presence indicators (default)
    return RuleKind.PRESENCE_CHECK


# =============================================================================
# ONTOLOGY → LEGACY EXPORT
# =============================================================================

def export_to_legacy(response: ExtractRubricResponse) -> Dict[str, Any]:
    """
    Export ExtractRubricResponse to legacy format.
    
    Used for backward compatibility with existing grading agent.
    Note: Multi-level rules are converted to binary (information loss).
    """
    questions = []
    multi_level_warnings = []
    
    for q in response.questions:
        criteria = []
        for c in q.criteria:
            # Convert reduction rules back to legacy format
            reduction_rules = []
            for r in c.rules:
                # Warn about multi-level information loss
                if len(r.levels) > 2:
                    multi_level_warnings.append(
                        f"Rule {r.rule_id} has {len(r.levels)} levels, converted to binary"
                    )
                
                reduction_rules.append({
                    "description": r.description,
                    "reduction_value": float(r.max_points),
                    "is_explicit": True
                })
            
            criteria.append({
                "criterion_description": c.description,
                "total_points": float(c.points),
                "reduction_rules": reduction_rules
            })
        
        questions.append({
            "question_number": _extract_question_number(q.question_id),
            "question_text": q.question_text,
            "total_points": float(q.total_points),
            "criteria": criteria
        })
    
    if multi_level_warnings:
        logger.warning(
            f"Legacy export lost information: {len(multi_level_warnings)} "
            f"multi-level rules converted to binary"
        )
    
    return {
        "rubric_id": response.rubric_id,
        "name": response.rubric_name,
        "programming_language": response.programming_language,
        "questions": questions
    }


def _extract_question_number(question_id: str) -> int:
    """
    Extract numeric part from question ID robustly.
    
    Handles: 'q1', 'q1a', 'question_1', '1' -> 1
    Falls back to 1 with warning if no number found.
    """
    match = re.search(r'\d+', question_id)
    if not match:
        logger.warning(
            f"Could not extract number from question_id '{question_id}', "
            f"defaulting to 1"
        )
        return 1
    return int(match.group())


# =============================================================================
# GRADING AGENT MODELS → ONTOLOGY
# =============================================================================

def migrate_grading_criterion_to_ontology(
    grading_criterion,  # GradingCriterion from grading_agent_models
    criterion_id: str
) -> Criterion:
    """
    Migrate a GradingCriterion to ontology Criterion.
    
    Used when integrating existing grading agent with new ontology.
    """
    rules: List[ReductionRule] = []
    
    for r in grading_criterion.rules:
        rules.append(ReductionRule(
            rule_id=f"{criterion_id}_r{r.index}",
            index=r.index,
            description=r.description,
            max_points=Decimal(str(r.deduction_points)),
            scoring_type="binary",
            rule_kind=_infer_rule_kind(r.description),
        ))
    
    return Criterion(
        criterion_id=criterion_id,
        index=grading_criterion.index,
        description=grading_criterion.description,
        points=Decimal(str(grading_criterion.total_points)),
        rules=rules
    )
