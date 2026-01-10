"""
Rubric Verification Layer

Validates extracted rubric data and provides confidence scoring.

Validation checks:
- Point totals match expected
- All criteria have description + points
- No duplicate criteria
- Hebrew text is valid (not garbled)
- Point values are reasonable
- Sub-question IDs are valid Hebrew letters

"""
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from .hybrid_rubric_extractor import (
    HybridExtractionResult,
    FusedQuestion,
    FusedSubQuestion,
    FusedCriterion,
    ConfidenceLevel
)

logger = logging.getLogger(__name__)


# =============================================================================
# Verification Result
# =============================================================================

@dataclass
class VerificationResult:
    """Result of rubric verification."""
    is_valid: bool = True
    confidence: float = 1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


# =============================================================================
# Rubric Verifier
# =============================================================================

class RubricVerifier:
    """
    Validates extracted rubric data.
    
    Provides:
    - Error detection (blocking issues)
    - Warning detection (non-blocking issues)
    - Suggestions for improvement
    - Overall confidence scoring
    """
    
    # Valid Hebrew letters for sub-questions
    HEBREW_LETTERS = set("אבגדהוזחטיכלמנסעפצקרשת")
    
    # Patterns
    GARBLED_TEXT_PATTERN = re.compile(r'[\x00-\x1f]|[^\u0000-\u007F\u0590-\u05FF\s\d.,;:!?()\[\]{}\'\"<>=+\-*/\\@#$%^&_|~`א-ת]')
    
    # Thresholds
    MIN_DESCRIPTION_LENGTH = 5
    MAX_DESCRIPTION_LENGTH = 500
    MIN_POINTS = 0
    MAX_POINTS = 100
    DUPLICATE_SIMILARITY_THRESHOLD = 0.9
    
    def verify(self, result: HybridExtractionResult) -> VerificationResult:
        """
        Run all verification checks on extraction result.
        
        Args:
            result: HybridExtractionResult to verify
            
        Returns:
            VerificationResult with all findings
        """
        errors = []
        warnings = list(result.validation_warnings)  # Include existing warnings
        suggestions = []
        
        # Check each question
        for q in result.questions:
            q_errors, q_warnings, q_suggestions = self._verify_question(q)
            errors.extend(q_errors)
            warnings.extend(q_warnings)
            suggestions.extend(q_suggestions)
        
        # Calculate final confidence
        base_confidence = result.overall_confidence
        error_penalty = len(errors) * 0.20
        warning_penalty = len(warnings) * 0.03
        
        final_confidence = max(0.0, min(1.0, base_confidence - error_penalty - warning_penalty))
        
        # Determine confidence level
        if final_confidence >= 0.85:
            confidence_level = ConfidenceLevel.HIGH
        elif final_confidence >= 0.70:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW
        
        return VerificationResult(
            is_valid=len(errors) == 0,
            confidence=final_confidence,
            confidence_level=confidence_level,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )
    
    def _verify_question(
        self, 
        q: FusedQuestion
    ) -> Tuple[List[str], List[str], List[str]]:
        """Verify a single question."""
        errors = []
        warnings = []
        suggestions = []
        q_num = q.question_number
        
        # Collect all criteria (direct + sub-questions)
        all_criteria = list(q.criteria)
        for sq in q.sub_questions:
            all_criteria.extend(sq.criteria)
        
        # === Check 1: Has criteria ===
        if not all_criteria:
            errors.append(f"שאלה {q_num}: לא נמצאו קריטריונים")
            return errors, warnings, suggestions
        
        # === Check 2: Point values are reasonable ===
        for i, c in enumerate(all_criteria):
            if c.points < self.MIN_POINTS:
                errors.append(f"שאלה {q_num}: קריטריון {i+1} עם נקודות שליליות ({c.points})")
            
            if c.points > self.MAX_POINTS:
                warnings.append(f"שאלה {q_num}: קריטריון {i+1} עם נקודות גבוהות ({c.points})")
            
            if c.points == 0 and not c.deduction_rules:
                suggestions.append(f"שאלה {q_num}: קריטריון {i+1} עם 0 נקודות")
        
        # === Check 3: Descriptions are valid ===
        for i, c in enumerate(all_criteria):
            desc = c.description
            
            if not desc or len(desc) < self.MIN_DESCRIPTION_LENGTH:
                warnings.append(f"שאלה {q_num}: קריטריון {i+1} עם תיאור קצר מדי")
            
            if len(desc) > self.MAX_DESCRIPTION_LENGTH:
                suggestions.append(f"שאלה {q_num}: קריטריון {i+1} עם תיאור ארוך מאוד")
            
            # Check for garbled text
            if self.GARBLED_TEXT_PATTERN.search(desc):
                warnings.append(f"שאלה {q_num}: קריטריון {i+1} עם טקסט לא תקין")
        
        # === Check 4: No duplicate criteria ===
        descriptions = [c.description.strip().lower() for c in all_criteria]
        seen = {}
        for i, desc in enumerate(descriptions):
            if desc in seen and len(desc) > 10:
                warnings.append(f"שאלה {q_num}: קריטריון כפול ({i+1} ו-{seen[desc]+1})")
            else:
                seen[desc] = i
        
        # === Check 5: Total points validation ===
        actual_total = sum(c.points for c in all_criteria)
        if q.total_points > 0 and abs(actual_total - q.total_points) > 0.5:
            warnings.append(
                f"שאלה {q_num}: סכום קריטריונים ({actual_total:.2f}) ≠ סה\"כ ({q.total_points:.2f})"
            )
        
        # === Check 6: Sub-question IDs are valid ===
        for sq in q.sub_questions:
            sq_id = sq.sub_question_id
            if sq_id and sq_id not in self.HEBREW_LETTERS:
                warnings.append(f"שאלה {q_num}: מזהה תת-שאלה לא תקין ({sq_id})")
        
        # === Check 7: Discrepancies between PDF and VLM ===
        discrepant_count = sum(1 for c in all_criteria if c.has_discrepancy)
        if discrepant_count > 0:
            warnings.append(f"שאלה {q_num}: {discrepant_count} קריטריונים עם פער PDF/VLM")
        
        # === Check 8: Low confidence criteria ===
        low_confidence = [c for c in all_criteria if c.confidence < 0.70]
        if low_confidence:
            suggestions.append(
                f"שאלה {q_num}: {len(low_confidence)} קריטריונים עם רמת ביטחון נמוכה - מומלץ לבדוק"
            )
        
        return errors, warnings, suggestions
    
    def verify_single_question(
        self,
        q: FusedQuestion,
        expected_total: Optional[float] = None
    ) -> VerificationResult:
        """
        Verify a single question.
        
        Args:
            q: Question to verify
            expected_total: Expected total points (optional)
            
        Returns:
            VerificationResult for this question
        """
        errors, warnings, suggestions = self._verify_question(q)
        
        # Additional check against expected total
        if expected_total:
            all_criteria = list(q.criteria)
            for sq in q.sub_questions:
                all_criteria.extend(sq.criteria)
            
            actual = sum(c.points for c in all_criteria)
            if abs(actual - expected_total) > 0.5:
                warnings.append(f"סכום ({actual:.2f}) לא תואם לצפוי ({expected_total:.2f})")
        
        # Calculate confidence
        base = q.confidence
        error_penalty = len(errors) * 0.20
        warning_penalty = len(warnings) * 0.03
        confidence = max(0.0, min(1.0, base - error_penalty - warning_penalty))
        
        if confidence >= 0.85:
            level = ConfidenceLevel.HIGH
        elif confidence >= 0.70:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
        
        return VerificationResult(
            is_valid=len(errors) == 0,
            confidence=confidence,
            confidence_level=level,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def verify_extraction(result: HybridExtractionResult) -> VerificationResult:
    """
    Verify a hybrid extraction result.
    
    Args:
        result: HybridExtractionResult to verify
        
    Returns:
        VerificationResult with all findings
    """
    verifier = RubricVerifier()
    return verifier.verify(result)


def add_verification_to_result(
    result: HybridExtractionResult
) -> Dict[str, Any]:
    """
    Add verification to extraction result.
    
    Args:
        result: HybridExtractionResult
        
    Returns:
        Dict with extraction result + verification
    """
    verification = verify_extraction(result)
    
    output = result.to_dict()
    output["verification"] = verification.to_dict()
    
    # Update overall confidence based on verification
    output["overall_confidence"] = verification.confidence
    
    return output
