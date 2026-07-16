"""
Evidence Extractor: DEPRECATED MODULE

╔═══════════════════════════════════════════════════════════════════════════════╗
║                            DEPRECATION NOTICE                                  ║
║                                                                                ║
║  This module is DEPRECATED as of Sprint 3 (2026-02).                          ║
║                                                                                ║
║  The evidence extraction logic has been moved to the TestGrader Agent,        ║
║  which handles LLM-based evaluation with proper ReAct self-correction.        ║
║                                                                                ║
║  Use instead:                                                                  ║
║  - app.agents.test_grader.run_grading_agent() for grading                     ║
║  - app.services.ontology_grading_service.validate_graded_draft() for         ║
║    validation                                                                  ║
║                                                                                ║
║  This module is retained for:                                                  ║
║  1. RuleKind routing information (EXTRACTOR_REGISTRY)                         ║
║  2. Backward compatibility during migration                                    ║
║                                                                                ║
║  All public functions emit DeprecationWarning when called.                    ║
║  This module will be removed in a future version.                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Original Architecture (Phase 1):
- BaseEvidenceExtractor: Abstract interface all extractors implement
- GenericTextExtractor: LLM-based text matching fallback
- EXTRACTOR_REGISTRY: Maps RuleKind → appropriate extractor instance

New Architecture (Phase 2+):
- TestGraderAgent: LangGraph agent that handles all grading
- evaluate_criterion_llm: Node that evaluates all rules in a criterion
- validate_response: Node that validates quotes with ReAct retry loop

Migration Path:
1. Replace calls to evaluate_rule() with TestGraderAgent
2. Replace calls to get_evidence_extractor() with TestGraderAgent
3. Use EXTRACTOR_REGISTRY read-only for rule kind routing info (if needed)
"""
import logging
import warnings
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Optional
from uuid import uuid4

from ..schemas.ontology_types import (
    AnswerQuotation,
    ClaimType,
    ClosedWorldViolation,
    EvidenceClaim,
    # DEAD UNTIL grader redesign — see grader-migration-TODO
    # ReductionRule,
    # RuleKind,
    RuleOutcome,
    # ScoringLevel,
    StudentAnswer,
)

logger = logging.getLogger(__name__)

# =============================================================================
# DEPRECATION MESSAGE
# =============================================================================

_DEPRECATION_MSG = (
    "evidence_extractor module is deprecated as of Sprint 3 (2026-02). "
    "Use TestGraderAgent from app.agents.test_grader instead. "
    "This module will be removed in a future version."
)


def _emit_deprecation_warning(func_name: str) -> None:
    """Emit a deprecation warning for a function call."""
    warnings.warn(
        f"{func_name}() is deprecated. {_DEPRECATION_MSG}",
        DeprecationWarning,
        stacklevel=3
    )
    logger.warning(f"[DEPRECATED] {func_name}() called. {_DEPRECATION_MSG}")


# =============================================================================
# CONSTANTS (Read-only, not deprecated)
# =============================================================================

# Hebrew messages for evidence citations
EMPTY_SUBMISSION_TEXT = "[ריק - לא הוגשה תשובה]"  # "Empty - no answer submitted"
EMPTY_SHORT_TEXT = "[ריק]"  # "Empty"

# Language-specific patterns for code structure detection
# These are provided for informational purposes and may be used
# by the TestGraderAgent for context
LANGUAGE_PATTERNS = {
    "java": ["class ", "public ", "private ", "protected ", "void ", "int ", "String ", "static "],
    "python": ["def ", "class ", "import ", "from "],
    "csharp": ["class ", "public ", "private ", "void ", "int ", "string ", "static "],
    "pseudocode": ["פונקציה", "תחילת", "סוף", "אם", "כל עוד", "לכל"],  # Hebrew pseudocode
}


# =============================================================================
# RULE KIND TO EXTRACTOR STRATEGY MAPPING (Read-only reference)
# =============================================================================

# This mapping is retained for documentation and routing purposes only.
# The actual extraction is now done by TestGraderAgent.
RULE_KIND_STRATEGIES = {
    RuleKind.STRUCTURE_AST: "ast_analysis",      # Requires AST parsing
    RuleKind.EXECUTION_TESTS: "execution",       # Requires code execution
    RuleKind.TEXT_ALIGNMENT: "llm_semantic",     # LLM semantic matching
    RuleKind.REFERENCE_CITATION: "llm_semantic", # LLM for citation check
    RuleKind.FORMAT_REQUIREMENT: "regex",        # Regex pattern matching
    RuleKind.REASONING_QUALITY: "llm_semantic",  # LLM reasoning evaluation
    RuleKind.PRESENCE_CHECK: "keyword",          # Simple keyword/pattern
    RuleKind.NUMERIC_ACCURACY: "numeric_eval",   # Numeric comparison
}


# =============================================================================
# BASE EXTRACTOR (DEPRECATED)
# =============================================================================

class BaseEvidenceExtractor(ABC):
    """
    DEPRECATED: Abstract base class for evidence extraction strategies.
    
    This class is retained for backward compatibility only.
    Use TestGraderAgent instead.
    """
    
    @abstractmethod
    def evaluate(self, rule: ReductionRule, answer: StudentAnswer) -> RuleOutcome:
        """DEPRECATED: Evaluate a single rule against a student answer."""
        pass
    
    def _select_level(
        self, 
        rule: ReductionRule, 
        level_id: str
    ) -> tuple[ScoringLevel, Decimal]:
        """DEPRECATED: Select a scoring level by ID."""
        _emit_deprecation_warning("BaseEvidenceExtractor._select_level")
        for level in rule.levels:
            if level.level_id == level_id:
                return level, level.points
        
        valid_ids = [lv.level_id for lv in rule.levels]
        raise ClosedWorldViolation(
            f"Level '{level_id}' not found in rule '{rule.rule_id}'. "
            f"Valid levels: {valid_ids}"
        )
    
    def _create_outcome(
        self,
        rule: ReductionRule,
        level_id: str,
        claim_type: ClaimType,
        claim_statement: str,
        quote_text: str,
        position_hint: Optional[str] = None
    ) -> RuleOutcome:
        """DEPRECATED: Create a RuleOutcome with evidence structure."""
        _emit_deprecation_warning("BaseEvidenceExtractor._create_outcome")
        level, points = self._select_level(rule, level_id)
        
        return RuleOutcome(
            rule_id=rule.rule_id,
            selected_level_id=level_id,
            points_awarded=points,
            evidence_claim=EvidenceClaim(
                claim_id=str(uuid4())[:8],
                claim_type=claim_type,
                claim_statement=claim_statement[:200],
                matched_level_id=level_id,
                answer_quotations=[
                    AnswerQuotation(
                        quote_text=quote_text,
                        position_hint=position_hint
                    )
                ]
            )
        )


# =============================================================================
# GENERIC TEXT EXTRACTOR (DEPRECATED)
# =============================================================================

class GenericTextExtractor(BaseEvidenceExtractor):
    """
    DEPRECATED: LLM-based generic text extractor.
    
    Use TestGraderAgent for all LLM-based grading.
    """
    
    def __init__(self, llm_client=None):
        """DEPRECATED: Initialize with optional LLM client."""
        _emit_deprecation_warning("GenericTextExtractor.__init__")
        self.llm = llm_client
    
    def evaluate(self, rule: ReductionRule, answer: StudentAnswer) -> RuleOutcome:
        """DEPRECATED: Evaluate rule using LLM-based text analysis."""
        _emit_deprecation_warning("GenericTextExtractor.evaluate")
        
        if not answer.content.strip():
            return self._create_outcome(
                rule=rule,
                level_id="fail",
                claim_type=ClaimType.PRESENCE,
                claim_statement=f"No content found for: {rule.description[:100]}",
                quote_text=EMPTY_SUBMISSION_TEXT,
                position_hint=None
            )
        
        return self._evaluate_simple_presence(rule, answer)
    
    def _evaluate_simple_presence(
        self, 
        rule: ReductionRule, 
        answer: StudentAnswer
    ) -> RuleOutcome:
        """DEPRECATED: Simple presence-based evaluation."""
        content_lines = answer.content.strip().split('\n')
        quote = content_lines[0][:100] if content_lines else "[content exists]"
        
        sorted_levels = sorted(rule.levels, key=lambda x: x.level_order)
        highest_level = sorted_levels[-1] if sorted_levels else None
        
        if not highest_level:
            raise ValueError(f"Rule {rule.rule_id} has no levels defined")
        
        return self._create_outcome(
            rule=rule,
            level_id=highest_level.level_id,
            claim_type=ClaimType.PRESENCE,
            claim_statement=f"Content found for: {rule.description[:80]}",
            quote_text=quote,
            position_hint="start of submission"
        )
    
    def _evaluate_with_llm(
        self, 
        rule: ReductionRule, 
        answer: StudentAnswer
    ) -> RuleOutcome:
        """DEPRECATED: This method is no longer supported."""
        _emit_deprecation_warning("GenericTextExtractor._evaluate_with_llm")
        raise NotImplementedError(
            "LLM evaluation has moved to TestGraderAgent. "
            "Use app.agents.test_grader.run_grading_agent() instead."
        )


# =============================================================================
# PRESENCE CHECK EXTRACTOR (DEPRECATED)
# =============================================================================

class PresenceCheckExtractor(BaseEvidenceExtractor):
    """
    DEPRECATED: Specialized extractor for PRESENCE_CHECK rules.
    
    Use TestGraderAgent for all rule evaluation.
    """
    
    def evaluate(self, rule: ReductionRule, answer: StudentAnswer) -> RuleOutcome:
        """DEPRECATED: Check for presence of expected elements."""
        _emit_deprecation_warning("PresenceCheckExtractor.evaluate")
        
        content = answer.content.strip()
        
        if not content:
            return self._create_outcome(
                rule=rule,
                level_id="fail",
                claim_type=ClaimType.PRESENCE,
                claim_statement="Empty submission - required element missing",
                quote_text=EMPTY_SHORT_TEXT
            )
        
        return self._create_outcome(
            rule=rule,
            level_id="pass",
            claim_type=ClaimType.PRESENCE,
            claim_statement=f"Content found: {rule.description[:80]}",
            quote_text=content[:100]
        )
    
    def _has_code_structure(self, content: str, language: str) -> bool:
        """DEPRECATED: Check if content contains code structure patterns."""
        patterns = LANGUAGE_PATTERNS.get(language, LANGUAGE_PATTERNS["java"])
        return any(p in content for p in patterns)
    
    def _extract_definition(self, code: str, language: str) -> str:
        """DEPRECATED: Extract first definition from code."""
        patterns = LANGUAGE_PATTERNS.get(language, LANGUAGE_PATTERNS["java"])
        for line in code.split('\n'):
            line_stripped = line.strip()
            if any(line_stripped.startswith(p) or p in line_stripped for p in patterns):
                return line_stripped[:100]
        return code.split('\n')[0][:100]


# =============================================================================
# EXTRACTOR REGISTRY (DEPRECATED - Read-only reference)
# =============================================================================

# These instances are deprecated but retained for backward compatibility
_generic_extractor = None  # Lazy initialization
_presence_extractor = None  # Lazy initialization


def _get_deprecated_extractors():
    """Lazily initialize deprecated extractors with warning."""
    global _generic_extractor, _presence_extractor
    if _generic_extractor is None:
        _emit_deprecation_warning("EXTRACTOR_REGISTRY access")
        _generic_extractor = GenericTextExtractor()
        _presence_extractor = PresenceCheckExtractor()
    return _generic_extractor, _presence_extractor


# Registry is now a function to emit warnings on access
def get_extractor_registry() -> Dict[RuleKind, BaseEvidenceExtractor]:
    """
    DEPRECATED: Get the extractor registry.
    
    Returns a dictionary mapping RuleKind to extractors.
    This is deprecated - use TestGraderAgent instead.
    """
    _emit_deprecation_warning("get_extractor_registry")
    generic, presence = _get_deprecated_extractors()
    return {
        RuleKind.STRUCTURE_AST: generic,
        RuleKind.EXECUTION_TESTS: generic,
        RuleKind.TEXT_ALIGNMENT: generic,
        RuleKind.REFERENCE_CITATION: generic,
        RuleKind.FORMAT_REQUIREMENT: generic,
        RuleKind.REASONING_QUALITY: generic,
        RuleKind.PRESENCE_CHECK: presence,
        RuleKind.NUMERIC_ACCURACY: generic,
    }


# For backward compatibility, EXTRACTOR_REGISTRY is kept but accessing it
# will trigger lazy initialization with deprecation warning
class _DeprecatedRegistryProxy:
    """Proxy that emits deprecation warning on access."""
    
    def __getitem__(self, key):
        _emit_deprecation_warning("EXTRACTOR_REGISTRY")
        generic, presence = _get_deprecated_extractors()
        registry = {
            RuleKind.STRUCTURE_AST: generic,
            RuleKind.EXECUTION_TESTS: generic,
            RuleKind.TEXT_ALIGNMENT: generic,
            RuleKind.REFERENCE_CITATION: generic,
            RuleKind.FORMAT_REQUIREMENT: generic,
            RuleKind.REASONING_QUALITY: generic,
            RuleKind.PRESENCE_CHECK: presence,
            RuleKind.NUMERIC_ACCURACY: generic,
        }
        return registry.get(key, generic)
    
    def get(self, key, default=None):
        return self.__getitem__(key) if key in RuleKind else default


EXTRACTOR_REGISTRY = _DeprecatedRegistryProxy()


# =============================================================================
# PUBLIC FUNCTIONS (DEPRECATED)
# =============================================================================

def get_evidence_extractor(kind: RuleKind) -> BaseEvidenceExtractor:
    """
    DEPRECATED: Get the appropriate evidence extractor for a RuleKind.
    
    Use TestGraderAgent from app.agents.test_grader instead.
    
    Args:
        kind: The RuleKind to get an extractor for
        
    Returns:
        BaseEvidenceExtractor instance (deprecated)
    """
    _emit_deprecation_warning("get_evidence_extractor")
    generic, presence = _get_deprecated_extractors()
    
    if kind == RuleKind.PRESENCE_CHECK:
        return presence
    return generic


def evaluate_rule(rule: ReductionRule, answer: StudentAnswer) -> RuleOutcome:
    """
    DEPRECATED: Evaluate a rule against an answer.
    
    This function is deprecated. Use TestGraderAgent instead:
    
    ```python
    from app.agents.test_grader import run_grading_agent
    
    result = run_grading_agent(
        contract=contract,
        student_answers=[answer],
        teacher_id="...",
        student_name="...",
        rubric_id="...",
    )
    ```
    
    Args:
        rule: The reduction rule to evaluate (deprecated)
        answer: The student's answer (deprecated)
        
    Returns:
        RuleOutcome (deprecated)
    """
    _emit_deprecation_warning("evaluate_rule")
    extractor = get_evidence_extractor(rule.rule_kind)
    return extractor.evaluate(rule, answer)


# =============================================================================
# MODULE DEPRECATION WARNING ON IMPORT
# =============================================================================

# Emit warning when module is imported
warnings.warn(
    _DEPRECATION_MSG,
    DeprecationWarning,
    stacklevel=2
)
logger.warning(f"[DEPRECATED] evidence_extractor module imported. {_DEPRECATION_MSG}")
