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


# ── THE QUOTE CHECK IS AN ALIGNMENT, NOT A WINDOW (2026-09-15) ─────────────
#
# It used to slide a window ~1.25× the quote's length across the answer in
# steps of a quarter of the quote's length and keep the best difflib ratio.
# That measure had two defects that were GEOMETRY, not content:
#
#   * the stride: window starts fell only every |q|/4 characters, so a quote
#     starting between two of them was always compared misaligned — with up to
#     |q|/8 of its own characters cut off one end;
#   * the width: difflib's ratio is 2M/(|q|+|window|), so a quote that was
#     ENTIRELY inside its window could score at most 2/2.25 = 0.889. Against a
#     0.85 bar that left 0.04 for any real difference at all.
#
# A student's inline comment inside a constructor (`// פעולה בונה`) plus a
# stride miss scored a genuine, correctly-cited span at 0.845 — refused by
# five thousandths — and a criterion she had actually earned priced at 0
# (graded_test a0cd07ff, 2026-09-15). At the right alignment the same quote
# scored 0.891. (difflib's autojunk also silently changed the arithmetic for
# any window of 200+ characters, treating frequent characters as junk.)
#
# The replacement makes this CLASS of failure impossible rather than rarer:
# the score is the OPTIMUM over every alignment, computed exactly by dynamic
# programming (local alignment with free start and end in the answer). There
# is no window to be wide or narrow and no stride to miss. Where the quote
# sits in the answer cannot affect its score; only its CONTENT can.
#
#   score = max over alignments of
#           ( matched quote chars  −  SKIP_COST × answer chars stepped over
#             between matched chars ) / |quote|
#
# Read it as: what fraction of the quote's characters appear, in order, within
# one stretch of the answer — with text the STUDENT wrote in between (a
# comment, a blank line, a stray token) almost free, and text the MODEL added
# or altered simply unmatched. An exact quote scores 1.0 (and is caught by the
# substring test before we get here). A quote fabricated from common tokens
# scattered across the answer fails, because every character of answer it
# steps over costs it, and scattered matches step over many. The 0.85 bar
# keeps its meaning — 85% of the quote must be there — and now means only that.
#
# THE ONE PARAMETER, AND WHERE IT COMES FROM. At the 0.85 bar a fully matched
# quote can afford 0.15·|q| of penalty, so with SKIP_COST = 0.6 the alignment
# may step over at most 0.15 / 0.6 = 25% of the quote's length of student
# text — exactly the slack the old 1.25× window granted, now applied at the
# best alignment instead of a guessed one. Both ends stay free, so a comment
# at the END of a span costs nothing (the alignment stops before it). What it
# refuses is STITCHING: two fragments cited as one span with half a quote's
# worth of answer between them score ~0.7 — the fabrication signal the eval
# suite's T1-STITCHED rule depends on (a cost of 0.1 let that through at 0.95).
#
# Cost: O(|q|·|answer|) per non-exact quote, in pure Python — ~0.3 s for a
# 200-character quote against a 2 000-character answer. Only ~1% of quotes
# reach it (the rest are exact substrings), so a test pays well under a second.

_SKIP_COST = 0.6      # per answer character the alignment steps over inside the match
_MISMATCH_COST = 1.0  # dominated by skip-both (0 + SKIP_COST); kept for readability


def _coverage_score(quote: str, text: str) -> float:
    """The best alignment score of `quote` inside `text`, in [0, 1]. Exact.

    H[i][j] = best score of an alignment of quote[:i] ending at text[:j]:
      match          H[i-1][j-1] + 1        (quote char found)
      skip quote     H[i-1][j]              (quote char absent: earns nothing)
      skip answer    H[i][j-1] − SKIP_COST  (student text inside the match)
      restart        0                      (free start anywhere in the answer)
    Skipping quote characters is free, so the last row dominates every other;
    the free start and the max over the last row make both ends free in the
    answer. Position-invariant by construction."""
    n, m = len(quote), len(text)
    if n == 0 or m == 0:
        return 0.0
    prev = [0.0] * (m + 1)
    for i in range(1, n + 1):
        qc = quote[i - 1]
        cur = [0.0] * (m + 1)
        for j in range(1, m + 1):
            diag = prev[j - 1] + (1.0 if text[j - 1] == qc else -_MISMATCH_COST)
            up = prev[j]
            left = cur[j - 1] - _SKIP_COST
            v = diag if diag > up else up
            if left > v:
                v = left
            cur[j] = v if v > 0.0 else 0.0
        prev = cur
    return max(prev) / n


def _best_substring_ratio(quote: str, text: str) -> float:
    """The quote's alignment score (see above). The name survives from the
    windowed implementation because the v3 path records it as `ratio`."""
    return _coverage_score(quote, text)


def quote_match_status(quote_text: str, student_answer: str) -> Optional[QuoteValidationStatus]:
    """Pure per-SPAN quote check — the primitive shared by the v3 terminal-level
    validation below and the grader-v5 per-check span validation. Returns None
    for an empty quote (no claim to validate). Same normalization and the same
    0.85 sliding-window bar as _validate_quote — one definition, two callers."""
    if not quote_text:
        return None
    norm_quote = " ".join(quote_text.lower().split())
    norm_answer = " ".join((student_answer or "").lower().split())
    if norm_quote in norm_answer:
        return QuoteValidationStatus.EXACT
    ratio = _best_substring_ratio(norm_quote, norm_answer)
    return QuoteValidationStatus.FUZZY if ratio >= 0.85 else QuoteValidationStatus.NOT_FOUND


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
