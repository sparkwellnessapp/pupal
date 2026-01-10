"""
Hybrid Rubric Extraction Engine

This is the main orchestrator that combines PDF text extraction with VLM analysis
to achieve 98%+ accuracy in rubric parsing.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  Layer A: PDF Extraction (pdfplumber)                       │
│  • Accurate point values (100% for simple tables)           │
│  • Section number detection                                 │
│  • Question header totals                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer B: VLM Extraction (GPT-4o Vision)                    │
│  • Full descriptions                                        │
│  • Deduction rules                                          │
│  • Complex table understanding                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer C: Fusion & Verification                             │
│  • PDF points + VLM descriptions                            │
│  • Sum validation                                           │
│  • Confidence scoring                                       │
└─────────────────────────────────────────────────────────────┘

Strategy:
- PDF points are used when available (more accurate)
- VLM descriptions are used for completeness
- Cross-validation catches errors
- Confidence scores guide manual review

Author: Vivi Engineering
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .pdf_text_extractor import (
    PDFCriteriaExtractor,
    PDFExtractionResult,
    QuestionHeader
)
from .vlm_rubric_extractor import (
    VLMRubricExtractor,
    VLMCriteriaResult,
    VLMQuestionResult,
    prepare_images_for_vlm,
    VLMConfig
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ExtractionSource(str, Enum):
    """Source of extracted data."""
    PDF_TEXT = "pdf_text"
    VLM = "vlm"
    FUSED = "fused"
    MANUAL = "manual"


class ConfidenceLevel(str, Enum):
    """Confidence level for extraction."""
    HIGH = "high"      # ≥ 0.85 - no review needed
    MEDIUM = "medium"  # 0.70-0.85 - review recommended
    LOW = "low"        # < 0.70 - manual verification required


@dataclass
class FusedCriterion:
    """A criterion fused from PDF and VLM sources."""
    description: str
    points: float
    source: ExtractionSource = ExtractionSource.VLM
    confidence: float = 1.0
    section_number: Optional[int] = None
    deduction_rules: List[str] = field(default_factory=list)
    
    # Provenance tracking for debugging
    pdf_points: Optional[float] = None
    vlm_points: Optional[float] = None
    has_discrepancy: bool = False
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.70:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "points": self.points,
            "source": self.source.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "section_number": self.section_number,
            "deduction_rules": self.deduction_rules,
            "has_discrepancy": self.has_discrepancy,
        }


@dataclass
class FusedSubQuestion:
    """A sub-question with fused criteria."""
    sub_question_id: str
    sub_question_text: Optional[str] = None
    criteria: List[FusedCriterion] = field(default_factory=list)
    total_points: float = 0
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub_question_id": self.sub_question_id,
            "sub_question_text": self.sub_question_text,
            "criteria": [c.to_dict() for c in self.criteria],
            "total_points": self.total_points,
            "extraction_confidence": self.confidence,
        }


@dataclass
class FusedQuestion:
    """A complete question with fused extraction results."""
    question_number: int
    question_text: Optional[str] = None
    total_points: float = 0
    criteria: List[FusedCriterion] = field(default_factory=list)
    sub_questions: List[FusedSubQuestion] = field(default_factory=list)
    confidence: float = 1.0
    source_pages: List[int] = field(default_factory=list)
    
    # Metadata
    pdf_criteria_count: int = 0
    vlm_criteria_count: int = 0
    fused_criteria_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_number": self.question_number,
            "question_text": self.question_text,
            "total_points": self.total_points,
            "criteria": [c.to_dict() for c in self.criteria],
            "sub_questions": [sq.to_dict() for sq in self.sub_questions],
            "extraction_confidence": self.confidence,
            "source_pages": self.source_pages,
            "extraction_metadata": {
                "pdf_criteria_count": self.pdf_criteria_count,
                "vlm_criteria_count": self.vlm_criteria_count,
                "fused_criteria_count": self.fused_criteria_count,
            }
        }


@dataclass
class HybridExtractionResult:
    """Complete result from hybrid extraction."""
    questions: List[FusedQuestion] = field(default_factory=list)
    overall_confidence: float = 1.0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    
    # Metadata
    pdf_headers_found: int = 0
    total_pdf_criteria: int = 0
    total_vlm_criteria: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "questions": [q.to_dict() for q in self.questions],
            "overall_confidence": self.overall_confidence,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "extraction_metadata": {
                "pdf_headers_found": self.pdf_headers_found,
                "total_pdf_criteria": self.total_pdf_criteria,
                "total_vlm_criteria": self.total_vlm_criteria,
            }
        }


# =============================================================================
# Fusion Logic
# =============================================================================

class CriteriaFuser:
    """
    Fuses PDF and VLM extracted criteria.
    
    Strategy:
    - Use PDF point values (more accurate)
    - Use VLM descriptions (more complete)
    - Match by section_number first, then by points similarity
    - Flag discrepancies for review
    """
    
    POINTS_MATCH_THRESHOLD = 0.1  # Max diff to consider points matching
    
    @staticmethod
    def fuse(
        pdf_criteria: List[Dict],
        vlm_criteria: List[Dict],
        expected_total: Optional[float] = None
    ) -> Tuple[List[FusedCriterion], float]:
        """
        Fuse PDF and VLM criteria.
        
        Args:
            pdf_criteria: Criteria from PDF extraction
            vlm_criteria: Criteria from VLM extraction
            expected_total: Expected total points (for validation)
            
        Returns:
            (list of fused criteria, confidence score)
        """
        if not pdf_criteria and not vlm_criteria:
            return [], 0.0
        
        # PDF-only fallback
        if not vlm_criteria:
            fused = CriteriaFuser._from_pdf_only(pdf_criteria)
            return fused, 0.80
        
        # VLM-only fallback
        if not pdf_criteria:
            fused = CriteriaFuser._from_vlm_only(vlm_criteria)
            return fused, 0.70
        
        # Full fusion
        fused = []
        used_vlm_indexes = set()
        
        for pdf_c in pdf_criteria:
            # Skip deduction-only rows (they'll be attached to main criteria)
            if pdf_c.get("is_deduction"):
                continue
            
            # Find best matching VLM criterion
            best_match_idx = CriteriaFuser._find_best_vlm_match(
                pdf_c, vlm_criteria, used_vlm_indexes
            )
            
            if best_match_idx is not None:
                used_vlm_indexes.add(best_match_idx)
                vlm_c = vlm_criteria[best_match_idx]
                
                # Check for point value discrepancy
                has_discrepancy = abs(pdf_c["points"] - vlm_c["points"]) > CriteriaFuser.POINTS_MATCH_THRESHOLD
                
                fused.append(FusedCriterion(
                    description=vlm_c.get("description", pdf_c.get("description", "")),
                    points=pdf_c["points"],  # PDF points are more reliable
                    source=ExtractionSource.FUSED,
                    confidence=0.95 if not has_discrepancy else 0.75,
                    section_number=pdf_c.get("section_number") or vlm_c.get("section_number"),
                    deduction_rules=vlm_c.get("deduction_rules", []),
                    pdf_points=pdf_c["points"],
                    vlm_points=vlm_c["points"],
                    has_discrepancy=has_discrepancy,
                ))
            else:
                # No VLM match - use PDF only
                fused.append(FusedCriterion(
                    description=pdf_c.get("description", ""),
                    points=pdf_c["points"],
                    source=ExtractionSource.PDF_TEXT,
                    confidence=0.85,
                    section_number=pdf_c.get("section_number"),
                    pdf_points=pdf_c["points"],
                ))
        
        # Add unmatched VLM criteria (might be missed by PDF)
        for i, vlm_c in enumerate(vlm_criteria):
            if i not in used_vlm_indexes:
                fused.append(FusedCriterion(
                    description=vlm_c.get("description", ""),
                    points=vlm_c["points"],
                    source=ExtractionSource.VLM,
                    confidence=0.70,
                    section_number=vlm_c.get("section_number"),
                    deduction_rules=vlm_c.get("deduction_rules", []),
                    vlm_points=vlm_c["points"],
                ))
        
        # Calculate overall confidence
        if not fused:
            return [], 0.0
        
        avg_confidence = sum(c.confidence for c in fused) / len(fused)
        
        # Bonus for PDF+VLM agreement
        fused_count = sum(1 for c in fused if c.source == ExtractionSource.FUSED)
        agreement_bonus = (fused_count / len(fused)) * 0.1
        
        # Penalty for total mismatch
        total_penalty = 0
        if expected_total:
            actual_total = sum(c.points for c in fused)
            if abs(actual_total - expected_total) > 0.5:
                total_penalty = 0.15
        
        confidence = min(1.0, max(0.0, avg_confidence + agreement_bonus - total_penalty))
        
        return fused, confidence
    
    @staticmethod
    def _find_best_vlm_match(
        pdf_c: Dict,
        vlm_criteria: List[Dict],
        used_indexes: set
    ) -> Optional[int]:
        """Find best matching VLM criterion for a PDF criterion."""
        pdf_section = pdf_c.get("section_number")
        pdf_points = pdf_c["points"]
        
        best_idx = None
        best_score = 0
        
        for i, vlm_c in enumerate(vlm_criteria):
            if i in used_indexes:
                continue
            
            score = 0
            
            # Section number match (highest priority)
            vlm_section = vlm_c.get("section_number")
            if pdf_section and vlm_section == pdf_section:
                score += 1.0
            
            # Points match (secondary)
            if abs(pdf_points - vlm_c["points"]) < CriteriaFuser.POINTS_MATCH_THRESHOLD:
                score += 0.5
            elif abs(pdf_points - vlm_c["points"]) < 1.0:
                score += 0.2
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        return best_idx if best_score > 0.3 else None
    
    @staticmethod
    def _from_pdf_only(pdf_criteria: List[Dict]) -> List[FusedCriterion]:
        """Create fused criteria from PDF only."""
        return [
            FusedCriterion(
                description=c.get("description", ""),
                points=c["points"],
                source=ExtractionSource.PDF_TEXT,
                confidence=0.85,
                section_number=c.get("section_number"),
                pdf_points=c["points"],
            )
            for c in pdf_criteria
            if not c.get("is_deduction")
        ]
    
    @staticmethod
    def _from_vlm_only(vlm_criteria: List[Dict]) -> List[FusedCriterion]:
        """Create fused criteria from VLM only."""
        return [
            FusedCriterion(
                description=c.get("description", ""),
                points=c["points"],
                source=ExtractionSource.VLM,
                confidence=0.70,
                section_number=c.get("section_number"),
                deduction_rules=c.get("deduction_rules", []),
                vlm_points=c["points"],
            )
            for c in vlm_criteria
        ]


# =============================================================================
# Main Hybrid Extractor
# =============================================================================

class HybridRubricExtractor:
    """
    Main orchestrator for hybrid rubric extraction.
    
    Combines PDF text extraction with VLM analysis for maximum accuracy.
    
    Usage:
        extractor = HybridRubricExtractor(pdf_bytes)
        result = await extractor.extract(question_mappings)
    """
    
    # Hebrew letters for sub-question mapping
    HEBREW_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"
    
    def __init__(self, pdf_bytes: bytes, openai_client=None):
        """
        Initialize hybrid extractor.
        
        Args:
            pdf_bytes: PDF file content
            openai_client: Optional OpenAI client instance
        """
        self.pdf_bytes = pdf_bytes
        self.vlm_extractor = VLMRubricExtractor(openai_client)
        self._images_b64: Optional[List[str]] = None
    
    def _get_images_b64(self) -> List[str]:
        """Lazy-load page images."""
        if self._images_b64 is None:
            self._images_b64 = prepare_images_for_vlm(
                self.pdf_bytes,
                dpi=VLMConfig.DPI
            )
        return self._images_b64
    
    async def extract(
        self,
        question_mappings: List[Dict],
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> HybridExtractionResult:
        """
        Extract complete rubric using hybrid approach.
        
        Args:
            question_mappings: List of question page mappings
            name: Optional rubric name
            description: Optional rubric description
            
        Returns:
            HybridExtractionResult with all questions
        """
        questions = []
        all_warnings = []
        total_pdf_criteria = 0
        total_vlm_criteria = 0
        
        # Get images for VLM
        images_b64 = self._get_images_b64()
        
        # Extract question headers from PDF
        with PDFCriteriaExtractor(self.pdf_bytes) as pdf_extractor:
            headers = pdf_extractor.find_question_headers()
            header_map = {h.question_number: h for h in headers}
            
            for mapping in question_mappings:
                q_result = await self._extract_question(
                    mapping=mapping,
                    pdf_extractor=pdf_extractor,
                    header_map=header_map,
                    images_b64=images_b64
                )
                
                questions.append(q_result["question"])
                all_warnings.extend(q_result.get("warnings", []))
                total_pdf_criteria += q_result.get("pdf_count", 0)
                total_vlm_criteria += q_result.get("vlm_count", 0)
        
        # Calculate overall confidence
        if questions:
            confidences = [q.confidence for q in questions]
            overall_confidence = sum(confidences) / len(confidences)
        else:
            overall_confidence = 0
        
        return HybridExtractionResult(
            questions=questions,
            overall_confidence=overall_confidence,
            validation_warnings=all_warnings,
            pdf_headers_found=len(headers),
            total_pdf_criteria=total_pdf_criteria,
            total_vlm_criteria=total_vlm_criteria,
        )
    
    async def _extract_question(
        self,
        mapping: Dict,
        pdf_extractor: PDFCriteriaExtractor,
        header_map: Dict[int, QuestionHeader],
        images_b64: List[str]
    ) -> Dict:
        """Extract a single question with hybrid approach."""
        q_num = mapping["question_number"]
        warnings = []
        
        # Get expected total from header
        header = header_map.get(q_num)
        expected_total = header.total_points if header else None
        
        # --- PDF Extraction ---
        criteria_pages = mapping.get("criteria_page_indexes", [])
        pdf_result = pdf_extractor.extract_from_pages(criteria_pages)
        pdf_criteria = pdf_result.criteria
        
        logger.info(f"Q{q_num}: PDF extracted {len(pdf_criteria)} criteria")
        
        # --- VLM Extraction ---
        vlm_criteria = []
        question_text = None
        vlm_sub_questions = []
        
        # Question text from VLM
        question_pages = mapping.get("question_page_indexes", [])
        if question_pages:
            question_imgs = [images_b64[i] for i in question_pages if i < len(images_b64)]
            if question_imgs:
                q_result = self.vlm_extractor.extract_question_text(question_imgs, q_num)
                question_text = q_result.question_text
                vlm_sub_questions = q_result.sub_questions
        
        # Criteria from VLM
        if criteria_pages:
            criteria_imgs = [images_b64[i] for i in criteria_pages if i < len(images_b64)]
            if criteria_imgs:
                vlm_result = self.vlm_extractor.extract_criteria(
                    criteria_imgs,
                    f"שאלה {q_num}"
                )
                vlm_criteria = vlm_result.to_dict_list()
        
        logger.info(f"Q{q_num}: VLM extracted {len(vlm_criteria)} criteria")
        
        # --- Fusion ---
        fused_criteria, confidence = CriteriaFuser.fuse(
            pdf_criteria, vlm_criteria, expected_total
        )
        
        # Handle sub-questions if present
        sub_questions = []
        if mapping.get("sub_questions"):
            sub_questions = self._build_sub_questions(
                mapping["sub_questions"],
                fused_criteria,
                vlm_sub_questions
            )
            # Clear direct criteria when using sub-questions
            if sub_questions:
                fused_criteria = []
        
        # Calculate total points
        if sub_questions:
            total_points = sum(sq.total_points for sq in sub_questions)
        else:
            total_points = sum(c.points for c in fused_criteria)
        
        # Validate against expected
        if expected_total and abs(total_points - expected_total) > 0.5:
            warnings.append(
                f"שאלה {q_num}: סכום ({total_points}) ≠ צפוי ({expected_total})"
            )
        
        question = FusedQuestion(
            question_number=q_num,
            question_text=question_text,
            total_points=expected_total or total_points,
            criteria=fused_criteria,
            sub_questions=sub_questions,
            confidence=confidence,
            source_pages=question_pages + criteria_pages,
            pdf_criteria_count=len(pdf_criteria),
            vlm_criteria_count=len(vlm_criteria),
            fused_criteria_count=len(fused_criteria) + sum(len(sq.criteria) for sq in sub_questions),
        )
        
        return {
            "question": question,
            "warnings": warnings,
            "pdf_count": len(pdf_criteria),
            "vlm_count": len(vlm_criteria),
        }
    
    def _build_sub_questions(
        self,
        sq_mappings: List[Dict],
        criteria: List[FusedCriterion],
        vlm_sub_questions: List[Dict]
    ) -> List[FusedSubQuestion]:
        """Map criteria to sub-questions based on section numbers."""
        sub_questions = []
        
        for i, sq_mapping in enumerate(sq_mappings):
            sq_id = sq_mapping.get("sub_question_id")
            section_num = i + 1  # -1 → section 1, -2 → section 2
            
            # Get criteria for this section
            sq_criteria = [c for c in criteria if c.section_number == section_num]
            
            # Get text from VLM sub-questions
            sq_text = None
            for vlm_sq in vlm_sub_questions:
                if vlm_sq.get("id") == sq_id:
                    sq_text = vlm_sq.get("text")
                    break
            
            # Calculate confidence
            if sq_criteria:
                sq_confidence = sum(c.confidence for c in sq_criteria) / len(sq_criteria)
            else:
                sq_confidence = 0.5  # Low confidence if no criteria matched
            
            sub_questions.append(FusedSubQuestion(
                sub_question_id=sq_id,
                sub_question_text=sq_text,
                criteria=sq_criteria,
                total_points=sum(c.points for c in sq_criteria),
                confidence=sq_confidence,
            ))
        
        return sub_questions


# =============================================================================
# Convenience Functions
# =============================================================================

async def extract_rubric_hybrid(
    pdf_bytes: bytes,
    question_mappings: List[Dict],
    name: Optional[str] = None,
    description: Optional[str] = None,
    openai_client=None
) -> HybridExtractionResult:
    """
    Main entry point for hybrid rubric extraction.
    
    Args:
        pdf_bytes: PDF file content
        question_mappings: List of question page mappings from frontend
        name: Optional rubric name
        description: Optional rubric description
        openai_client: Optional OpenAI client
        
    Returns:
        HybridExtractionResult with all questions and validation info
    """
    extractor = HybridRubricExtractor(pdf_bytes, openai_client)
    return await extractor.extract(question_mappings, name, description)
