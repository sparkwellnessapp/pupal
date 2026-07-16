"""
GraderAgent deterministic validator — pure function, no LLM calls.

validate_scope_grading() is the testable heart of grading correctness.
Four checks applied to the LLM's QuestionGradingResponse for one scope:
  1. Closed-world re-check (defense in depth)
  2. Bounds & precision (all arithmetic in Decimal)
  3. Quote validation (sliding-window fuzzy match via difflib)
  4. Annotation production (severity-coded, target-scoped)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from app.schemas.graded_test_draft import GradingAnnotation
from app.schemas.gradable import GradableScope
from app.schemas.ontology_types import (
    AnnotationSeverity,
    AnswerQuotation,
    FlaggedOutcome,
    FlagReason,
    NumericPolicy,
    QuoteValidationStatus,
)
from app.agents.grader.schemas import QuestionGradingResponse


# ---------------------------------------------------------------------------
# Internal result types
# ---------------------------------------------------------------------------

@dataclass
class ValidatedTerminalGrade:
    terminal_id: str
    points_awarded: Decimal
    reasoning: str
    confidence: float
    evidence_quote: Optional[AnswerQuotation]
    flags: List[FlaggedOutcome] = field(default_factory=list)


@dataclass
class ValidationResult:
    validated_grades: List[ValidatedTerminalGrade]
    annotations: List[GradingAnnotation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_terminal_map(scope: GradableScope) -> Dict[str, Decimal]:
    """
    Map each terminal criterion ID → its max points value.
    Terminals are: sub_criterion_ids when sub_criteria exist, else criterion_id.
    """
    terminals: Dict[str, Decimal] = {}
    for criterion in scope.criteria:
        if criterion.sub_criteria:
            for sc in criterion.sub_criteria:
                terminals[sc.sub_criterion_id] = sc.points
        else:
            terminals[criterion.criterion_id] = criterion.points
    return terminals


def _scope_target_id(scope: GradableScope) -> str:
    """Build a scope-level target_id for annotations."""
    if scope.sub_question_id:
        return f"{scope.question_id}.{scope.sub_question_id}"
    return scope.question_id


def _best_substring_ratio(quote: str, text: str) -> float:
    """
    Sliding-window best-substring match ratio.

    A short exact quote inside a long answer must NOT be scored as NOT_FOUND.
    We slide a window of approximately quote-length across the text and return
    the best SequenceMatcher ratio found.
    """
    q_len = len(quote)
    if q_len == 0:
        return 0.0
    if q_len >= len(text):
        return difflib.SequenceMatcher(None, quote, text).ratio()

    best = 0.0
    step = max(1, q_len // 4)          # step ~25% of quote length
    window_size = q_len + (q_len // 4)  # window slightly wider than quote

    for i in range(0, len(text) - q_len + 1, step):
        window = text[i : i + window_size]
        r = difflib.SequenceMatcher(None, quote, window).ratio()
        if r > best:
            best = r
            if best >= 0.85:
                return best  # short-circuit once threshold is met
    return best


def _validate_quote(
    quote_text: str,
    student_answer: str,
    terminal_id: str,
    points_awarded: Decimal,
) -> Tuple[Optional[AnswerQuotation], List[FlaggedOutcome], List[GradingAnnotation]]:
    """
    Validate a quote against the student answer.
    Returns (evidence_quote | None, flags, annotations).
    """
    flags: List[FlaggedOutcome] = []
    annotations: List[GradingAnnotation] = []

    # Empty quote on zero award — fine, no evidence needed
    if not quote_text and points_awarded == Decimal("0"):
        return None, flags, annotations

    # Empty quote on non-zero award — flag it
    if not quote_text:
        flags.append(FlaggedOutcome(
            criterion_id=terminal_id,
            reason=FlagReason.QUOTE_NOT_FOUND,
            message="Points awarded without evidence quote",
        ))
        annotations.append(GradingAnnotation(
            severity=AnnotationSeverity.WARNING,
            target_id=terminal_id,
            annotation_type="quote_not_found",
            message="ניתנו נקודות ללא ציטוט ראיה מתשובת התלמיד",
        ))
        return None, flags, annotations

    # Normalize for comparison
    norm_quote = " ".join(quote_text.lower().split())
    norm_answer = " ".join(student_answer.lower().split())

    if norm_quote in norm_answer:
        status = QuoteValidationStatus.EXACT
        evidence_quote = AnswerQuotation(quote_text=quote_text, validation_status=status)
        return evidence_quote, flags, annotations

    ratio = _best_substring_ratio(norm_quote, norm_answer)

    if ratio >= 0.85:
        status = QuoteValidationStatus.FUZZY
        flags.append(FlaggedOutcome(
            criterion_id=terminal_id,
            reason=FlagReason.FUZZY_MATCH,
            message=f"Quote fuzzy-matched (ratio={ratio:.2f})",
        ))
        annotations.append(GradingAnnotation(
            severity=AnnotationSeverity.INFO,
            target_id=terminal_id,
            annotation_type="fuzzy_match",
            message="הציטוט נמצא בדמיון חלקי לתשובת התלמיד (לא תואם מדויק)",
            metadata={"ratio": round(ratio, 3)},
        ))
    else:
        status = QuoteValidationStatus.NOT_FOUND
        flags.append(FlaggedOutcome(
            criterion_id=terminal_id,
            reason=FlagReason.QUOTE_NOT_FOUND,
            message="Quote not found in student answer",
        ))
        annotations.append(GradingAnnotation(
            severity=AnnotationSeverity.WARNING,
            target_id=terminal_id,
            annotation_type="quote_not_found",
            message="הציטוט לא נמצא בתשובת התלמיד — נדרשת בדיקת מורה",
        ))

    evidence_quote = AnswerQuotation(quote_text=quote_text, validation_status=status)
    return evidence_quote, flags, annotations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_scope_grading(
    response: QuestionGradingResponse,
    scope: GradableScope,
    numeric_policy: NumericPolicy,
) -> ValidationResult:
    """
    Apply four deterministic checks to the LLM's response for one scope.

    Returns ValidatedTerminalGrade entries (one per terminal in the scope,
    always — missing terminals synthesized as zero) and all produced
    GradingAnnotations.
    """
    terminal_map = _get_terminal_map(scope)
    all_annotations: List[GradingAnnotation] = []
    validated_grades: List[ValidatedTerminalGrade] = []

    # ── Step 1: Closed-world re-check ────────────────────────────────────────
    returned_ids = {g.terminal_criterion_id for g in response.grades}
    extra_ids = returned_ids - terminal_map.keys()
    for extra_id in extra_ids:
        # Extra ID: drop the grade, annotate error
        all_annotations.append(GradingAnnotation(
            severity=AnnotationSeverity.ERROR,
            target_id=extra_id,
            annotation_type="closed_world_violation",
            message=f"מודל החזיר ציון לקריטריון לא מוכר: {extra_id}",
            metadata={"extra_id": extra_id, "scope": _scope_target_id(scope)},
        ))

    # Build lookup of valid (in-scope) grades
    valid_grade_map = {
        g.terminal_criterion_id: g
        for g in response.grades
        if g.terminal_criterion_id in terminal_map
    }

    # ── Steps 2–5: Process each terminal in the scope ───────────────────────
    for terminal_id, max_points in terminal_map.items():
        term_flags: List[FlaggedOutcome] = []
        term_annotations: List[GradingAnnotation] = []

        if terminal_id not in valid_grade_map:
            # Missing terminal — synthesize zero-point grade
            term_flags.append(FlaggedOutcome(
                criterion_id=terminal_id,
                reason=FlagReason.UNGRADED_CRITERION,
                message=f"Terminal {terminal_id} was not graded by the LLM",
            ))
            term_annotations.append(GradingAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id=terminal_id,
                annotation_type="ungraded_criterion",
                message=f"קריטריון {terminal_id} לא קיבל ציון מהמודל",
            ))
            all_annotations.extend(term_annotations)
            validated_grades.append(ValidatedTerminalGrade(
                terminal_id=terminal_id,
                points_awarded=Decimal("0"),
                reasoning="",
                confidence=0.0,
                evidence_quote=None,
                flags=term_flags,
            ))
            continue

        grade = valid_grade_map[terminal_id]

        # Step 2: Bounds & precision
        raw = Decimal(str(grade.points_awarded))  # float→Decimal at boundary
        clamped = max(Decimal("0"), min(raw, max_points))
        precision = numeric_policy.precision
        rounded = (clamped / precision).to_integral_value(rounding=ROUND_HALF_UP) * precision

        if rounded != raw:
            term_flags.append(FlaggedOutcome(
                criterion_id=terminal_id,
                reason=FlagReason.BOUNDS_CLAMPED,
                message=f"points_awarded clamped/rounded: {raw} → {rounded}",
            ))
            term_annotations.append(GradingAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id=terminal_id,
                annotation_type="bounds_clamped",
                message=f"ציון {terminal_id} עוגל/הוגבל: {raw} → {rounded}",
                metadata={"original": str(raw), "clamped": str(rounded)},
            ))

        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, grade.confidence))

        # Step 3: Quote validation
        evidence_quote, q_flags, q_annotations = _validate_quote(
            grade.quote_text,
            scope.student_answer_text or "",
            terminal_id,
            rounded,
        )
        term_flags.extend(q_flags)
        term_annotations.extend(q_annotations)
        all_annotations.extend(term_annotations)

        validated_grades.append(ValidatedTerminalGrade(
            terminal_id=terminal_id,
            points_awarded=rounded,
            reasoning=grade.reasoning,
            confidence=confidence,
            evidence_quote=evidence_quote,
            flags=term_flags,
        ))

    return ValidationResult(validated_grades=validated_grades, annotations=all_annotations)
