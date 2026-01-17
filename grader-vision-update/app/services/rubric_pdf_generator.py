"""
Rubric PDF generator.

Creates annotated PDFs with rubric tables inserted after each question's pages.
Supports Hebrew RTL text and proper table formatting.
"""
import io
import logging
from typing import List, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Try to load Hebrew-compatible font
try:
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False
    def get_display(text):
        return text


def fix_hebrew_text(text: str) -> str:
    """Fix Hebrew text for proper RTL display in PDF."""
    if not text:
        return ""
    if HAS_BIDI:
        try:
            return get_display(text)
        except Exception:
            pass
    return text


def _register_fonts():
    """Register Unicode-compatible fonts."""
    import os
    import platform
    
    system = platform.system().lower()
    
    font_paths = []
    
    if system == "windows":
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    elif system == "darwin":
        font_paths = [
            "/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    else:  # Linux
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    
    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    
    for i, path in enumerate(font_paths):
        if os.path.exists(path):
            try:
                font_name = "HebrewFont" if i == 0 else "HebrewFontBold"
                pdfmetrics.registerFont(TTFont(font_name, path))
                if i == 0:
                    regular_font = font_name
                else:
                    bold_font = font_name
            except Exception as e:
                logger.warning(f"Failed to register font {path}: {e}")
    
    return regular_font, bold_font


class RubricPdfGenerator:
    """Generate annotated PDFs with rubric tables."""
    
    def __init__(self):
        """Initialize PDF generator with fonts."""
        self.regular_font, self.bold_font = _register_fonts()
        
        self.styles = getSampleStyleSheet()
        
        # Hebrew RTL paragraph style
        self.hebrew_style = ParagraphStyle(
            'Hebrew',
            parent=self.styles['Normal'],
            fontName=self.regular_font,
            fontSize=10,
            alignment=TA_RIGHT,
            leading=14,
            wordWrap='RTL',
        )
        
        self.hebrew_bold_style = ParagraphStyle(
            'HebrewBold',
            parent=self.hebrew_style,
            fontName=self.bold_font,
            fontSize=12,
        )
        
        self.title_style = ParagraphStyle(
            'Title',
            parent=self.styles['Heading1'],
            fontName=self.bold_font,
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
        )
    
    def generate_annotated_pdf(
        self,
        original_pdf_bytes: bytes,
        questions: List[Dict],
        question_page_mappings: Optional[Dict[int, int]] = None,
    ) -> bytes:
        """
        Create PDF with rubric tables inserted after each question.
        
        The key innovation: we preserve 100% of the original PDF and insert
        rubric pages at specific positions (after each question's last page).
        
        Args:
            original_pdf_bytes: The original PDF content
            questions: List of ExtractedQuestion dicts
            question_page_mappings: Optional mapping of question_number -> page_index
                                   to insert rubric after. If not provided, rubric
                                   pages are appended at the end.
        
        Returns:
            Combined PDF as bytes with rubric tables interleaved
        """
        # If no original PDF, just return rubric pages
        if not original_pdf_bytes:
            return self._create_rubric_pages(questions)
        
        try:
            original_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
            
            # Determine insertion strategy
            if question_page_mappings and len(question_page_mappings) > 0:
                # Smart interleaving: insert each rubric after its question's pages
                result_doc = self._insert_rubric_pages_smart(
                    original_doc, questions, question_page_mappings
                )
            else:
                # Fall back to appending all rubric pages at the end
                rubric_pdf_bytes = self._create_rubric_pages(questions)
                rubric_doc = fitz.open(stream=rubric_pdf_bytes, filetype="pdf")
                original_doc.insert_pdf(rubric_doc)
                rubric_doc.close()
                result_doc = original_doc
            
            # Save to bytes
            output = io.BytesIO()
            result_doc.save(output)
            result_doc.close()
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to combine PDFs: {e}", exc_info=True)
            # Fall back to just rubric pages
            return self._create_rubric_pages(questions)
    
    def _insert_rubric_pages_smart(
        self,
        original_doc: fitz.Document,
        questions: List[Dict],
        question_page_mappings: Dict[int, int],
    ) -> fitz.Document:
        """
        Smart insertion: place each rubric page right after the question's content.
        
        Algorithm:
        1. Create individual rubric PDFs for each question
        2. Sort questions by their last page index
        3. Insert from end to beginning (to avoid index shifting issues)
        """
        # Create a new document to hold the result
        result_doc = fitz.open()
        
        # Copy all original pages first
        result_doc.insert_pdf(original_doc)
        original_page_count = result_doc.page_count
        
        # Build a list of (question_number, after_page_index, rubric_bytes)
        insertions = []
        
        for question in questions:
            q_num = question.get("question_number", 0)
            
            # Get the page after which to insert (0-indexed)
            after_page = question_page_mappings.get(q_num)
            
            if after_page is None:
                # Check page_indexes if available
                page_indexes = question.get("page_indexes", [])
                if page_indexes:
                    after_page = max(page_indexes)
                else:
                    # Default to last page
                    after_page = original_page_count - 1
            
            # Ensure within bounds
            after_page = min(after_page, original_page_count - 1)
            
            # Create rubric PDF for this single question
            rubric_bytes = self._create_single_question_rubric(question)
            
            insertions.append((q_num, after_page, rubric_bytes))
        
        # Sort by page index descending (insert from end to avoid index shifting)
        insertions.sort(key=lambda x: x[1], reverse=True)
        
        # Insert rubric pages
        for q_num, after_page, rubric_bytes in insertions:
            try:
                rubric_doc = fitz.open(stream=rubric_bytes, filetype="pdf")
                # Insert after the specified page (insert_pdf inserts AT the given position)
                insert_at = after_page + 1
                result_doc.insert_pdf(rubric_doc, from_page=0, to_page=-1, start_at=insert_at)
                rubric_doc.close()
                logger.debug(f"Inserted rubric for Q{q_num} at page {insert_at}")
            except Exception as e:
                logger.warning(f"Failed to insert rubric for Q{q_num}: {e}")
        
        return result_doc
    
    def _create_single_question_rubric(self, question: Dict) -> bytes:
        """Create a single-page rubric PDF for one question."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Title with question context
        q_num = question.get("question_number", 0)
        title_text = fix_hebrew_text(f"מחוון - שאלה {q_num}")
        title = Paragraph(title_text, self.title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5*cm))
        
        # Add the rubric table
        q_elements = self._create_question_table(question)
        elements.extend(q_elements)
        
        doc.build(elements)
        return buffer.getvalue()

    
    def _create_rubric_pages(self, questions: List[Dict]) -> bytes:
        """Create PDF pages with rubric tables for all questions."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Title
        title = Paragraph(
            fix_hebrew_text("מחוון הערכה"),
            self.title_style
        )
        elements.append(title)
        elements.append(Spacer(1, 0.5*cm))
        
        # Generate table for each question
        for i, question in enumerate(questions):
            q_elements = self._create_question_table(question)
            elements.extend(q_elements)
            
            # Page break between questions (except last)
            if i < len(questions) - 1:
                elements.append(PageBreak())
        
        doc.build(elements)
        return buffer.getvalue()
    
    def _create_question_table(self, question: Dict) -> List:
        """Create rubric table for a single question."""
        elements = []
        
        q_num = question.get("question_number", 0)
        q_points = question.get("total_points", 0)
        
        # Question header
        header_text = fix_hebrew_text(f"שאלה {q_num} ({q_points} נקודות)")
        header = Paragraph(header_text, self.hebrew_bold_style)
        elements.append(header)
        elements.append(Spacer(1, 0.3*cm))
        
        # Handle sub-questions or direct criteria
        sub_questions = question.get("sub_questions", [])
        criteria = question.get("criteria", [])
        
        if sub_questions:
            for sq in sub_questions:
                sq_elements = self._create_subquestion_table(sq, q_num)
                elements.extend(sq_elements)
        elif criteria:
            table = self._create_criteria_table(criteria)
            elements.append(table)
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_subquestion_table(self, sub_question: Dict, q_num: int) -> List:
        """Create table for a sub-question."""
        elements = []
        
        sq_id = sub_question.get("sub_question_id", "")
        sq_points = sub_question.get("total_points", 0)
        
        # Sub-question header
        header_text = fix_hebrew_text(f"סעיף {sq_id} ({sq_points} נקודות)")
        header = Paragraph(header_text, self.hebrew_bold_style)
        elements.append(header)
        elements.append(Spacer(1, 0.2*cm))
        
        criteria = sub_question.get("criteria", [])
        if criteria:
            table = self._create_criteria_table(criteria)
            elements.append(table)
        
        elements.append(Spacer(1, 0.3*cm))
        
        return elements
    
    def _create_criteria_table(self, criteria: List[Dict]) -> Table:
        """Create a table of criteria with reduction rules."""
        # Table data
        data = []
        
        # Header row
        data.append([
            Paragraph(fix_hebrew_text("ניקוד"), self.hebrew_bold_style),
            Paragraph(fix_hebrew_text("קריטריון"), self.hebrew_bold_style),
        ])
        
        for criterion in criteria:
            desc = criterion.get("criterion_description", "")
            points = criterion.get("total_points", 0)
            rules = criterion.get("reduction_rules", [])
            
            # Format description with reduction rules
            desc_parts = [fix_hebrew_text(desc)]
            
            for rule in rules:
                rule_desc = rule.get("description", "")
                rule_value = rule.get("reduction_value", 0)
                desc_parts.append(fix_hebrew_text(f"  • {rule_desc} (-{rule_value})"))
            
            full_desc = "<br/>".join(desc_parts)
            
            data.append([
                Paragraph(str(points), self.hebrew_style),
                Paragraph(full_desc, self.hebrew_style),
            ])
        
        # Create table
        col_widths = [2*cm, 13*cm]
        table = Table(data, colWidths=col_widths)
        
        # Style
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.25, 0.4, 0.95)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), self.bold_font),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), self.regular_font),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Points column centered
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),   # Description RTL
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
            ('BOX', (0, 0), (-1, -1), 1, colors.Color(0.25, 0.4, 0.95)),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 1)]),
        ]))
        
        return table
    
    def generate_rubric_only_pdf(self, questions: List[Dict]) -> bytes:
        """
        Generate a PDF with only the rubric tables (no original document).
        
        Args:
            questions: List of ExtractedQuestion dicts
            
        Returns:
            PDF bytes
        """
        return self._create_rubric_pages(questions)


# Global instance
_generator: Optional[RubricPdfGenerator] = None


def get_rubric_pdf_generator() -> RubricPdfGenerator:
    """Get or create the global RubricPdfGenerator instance."""
    global _generator
    if _generator is None:
        _generator = RubricPdfGenerator()
    return _generator


async def generate_annotated_rubric_pdf(
    original_pdf_bytes: Optional[bytes],
    questions: List[Dict],
) -> bytes:
    """
    Convenience function to generate annotated rubric PDF.
    
    Automatically builds page mappings from the questions' page_indexes
    fields for smart rubric page interleaving.
    
    Args:
        original_pdf_bytes: Optional original PDF to annotate
        questions: List of ExtractedQuestion dicts
        
    Returns:
        Generated PDF as bytes
    """
    generator = get_rubric_pdf_generator()
    
    if original_pdf_bytes:
        # Build page mappings from questions
        # Maps question_number -> last page index where that question appears
        question_page_mappings = {}
        
        for q in questions:
            q_num = q.get("question_number", 0)
            page_indexes = q.get("page_indexes", [])
            
            if page_indexes:
                # Use the last page where this question appears
                question_page_mappings[q_num] = max(page_indexes)
            else:
                # Default: will be handled in the generator
                pass
        
        logger.info(f"Page mappings for rubric insertion: {question_page_mappings}")
        
        return generator.generate_annotated_pdf(
            original_pdf_bytes, 
            questions, 
            question_page_mappings=question_page_mappings
        )
    else:
        return generator.generate_rubric_only_pdf(questions)

