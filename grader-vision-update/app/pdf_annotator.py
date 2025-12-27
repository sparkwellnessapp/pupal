"""
PDF annotator for adding grades and feedback to student test PDFs.
FIXED VERSION: 
- Proper RTL Hebrew support and Unicode fonts
- Cross-platform font support (Windows, Linux, macOS)
- Groups grades by question
- No text truncation - proper wrapping
"""
import logging
import os
from io import BytesIO
from typing import Dict, List, Optional

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from PyPDF2 import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# Try to import bidi for RTL support
try:
    from bidi.algorithm import get_display
    HAS_BIDI = True
    logger.info("python-bidi loaded for RTL support")
except ImportError:
    HAS_BIDI = False
    logger.warning("python-bidi not installed. Hebrew text may appear reversed.")
    def get_display(text):
        return text


# System font paths for Unicode fonts with Hebrew support
# Check multiple locations for cross-platform support
FONT_SEARCH_PATHS = {
    # Linux paths
    "linux": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ],
    # Windows paths - Arial supports Hebrew well
    "windows": [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
        ("C:/Windows/Fonts/david.ttf", "C:/Windows/Fonts/davidbd.ttf"),
    ],
    # macOS paths
    "darwin": [
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
}


def _register_fonts() -> tuple:
    """
    Register Unicode-compatible fonts that support Hebrew.
    Returns (regular_font_name, bold_font_name)
    Works on Windows, Linux, and macOS.
    """
    import platform
    
    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    
    # Determine OS
    system = platform.system().lower()
    if system == "windows":
        font_paths = FONT_SEARCH_PATHS["windows"]
    elif system == "darwin":
        font_paths = FONT_SEARCH_PATHS["darwin"]
    else:
        font_paths = FONT_SEARCH_PATHS["linux"]
    
    logger.info(f"Searching for fonts on {system}...")
    
    # Try each font pair
    for regular_path, bold_path in font_paths:
        try:
            if os.path.exists(regular_path):
                # Generate unique font name from filename
                font_name = os.path.basename(regular_path).replace('.ttf', '').replace('.TTF', '')
                bold_name = font_name + "-Bold"
                
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                regular_font = font_name
                logger.info(f"✅ Registered {font_name} from {regular_path}")
                
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    bold_font = bold_name
                    logger.info(f"✅ Registered {bold_name} from {bold_path}")
                else:
                    # Use regular font for bold if bold not found
                    bold_font = font_name
                    logger.info(f"Using {font_name} for bold (bold variant not found)")
                
                # Found working fonts, stop searching
                break
                
        except Exception as e:
            logger.debug(f"Could not register font from {regular_path}: {e}")
            continue
    
    if regular_font == "Helvetica":
        logger.warning("⚠️ No Unicode font found! Hebrew text will not display correctly.")
        logger.warning("Install Arial or DejaVu fonts for Hebrew support.")
    
    return regular_font, bold_font


# Unicode mark mappings with ASCII fallbacks
MARK_DISPLAY = {
    "✓": ("✓", "[V]"),      # Check mark
    "✗": ("✗", "[X]"),      # X mark
    "✓✗": ("✓✗", "[V/X]"),  # Partial
}


def fix_hebrew_text(text: str) -> str:
    """
    Fix Hebrew text for proper RTL display in PDF.
    Uses the bidi algorithm to reorder characters correctly.
    """
    if not text:
        return text
    
    # Check if text contains Hebrew characters
    has_hebrew = any('\u0590' <= char <= '\u05FF' for char in text)
    
    if has_hebrew and HAS_BIDI:
        try:
            return get_display(text)
        except Exception as e:
            logger.warning(f"Bidi conversion failed: {e}")
            return text
    
    return text


class PDFAnnotator:
    """Annotates student PDFs with grading results."""
    
    def __init__(self):
        """Initialize the PDF annotator with Unicode fonts if available."""
        self.regular_font, self.bold_font = _register_fonts()
        self.has_unicode = self.regular_font != "Helvetica"
        
        logger.info(f"PDFAnnotator initialized with font: {self.regular_font}, unicode={self.has_unicode}, bidi={HAS_BIDI}")
    
    def _get_mark_display(self, mark: str) -> str:
        """Get the display version of a mark, with fallback for non-Unicode fonts."""
        if mark in MARK_DISPLAY:
            unicode_mark, ascii_mark = MARK_DISPLAY[mark]
            return unicode_mark if self.has_unicode else ascii_mark
        return mark
    
    def annotate_student_pdf(
        self,
        original_pdf_bytes: bytes,
        grading_result: Dict,
        student_name: str,
        rubric_total: int = None,
        rubric: Dict = None
    ) -> bytes:
        """
        Add a cover page with grading summary to the student's PDF.
        
        Args:
            original_pdf_bytes: Original PDF as bytes
            grading_result: Grading results from the agent
            student_name: Student's name
            rubric_total: Total points from rubric (overrides calculated)
            rubric: Full rubric dict for question grouping
        """
        try:
            reader = PdfReader(BytesIO(original_pdf_bytes))
            writer = PdfWriter()
            
            # Calculate totals
            total_earned = grading_result.get('total_score', 0)
            total_possible = rubric_total if rubric_total else grading_result.get('total_possible', 0)
            
            # Recalculate percentage with rubric total
            if rubric_total:
                percentage = (total_earned / rubric_total * 100) if rubric_total > 0 else 0
            else:
                percentage = grading_result.get('percentage', 0)
            
            # Create cover page
            cover_page = self._create_cover_page(
                student_name=student_name,
                total_earned=total_earned,
                total_possible=total_possible,
                percentage=percentage,
                grading_result=grading_result,
                rubric=rubric
            )
            writer.add_page(cover_page)
            
            # Add original pages
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                writer.add_page(page)
            
            # Write to bytes
            output = BytesIO()
            writer.write(output)
            output.seek(0)
            
            return output.read()
        
        except Exception as e:
            logger.error(f"Error annotating PDF: {e}", exc_info=True)
            # Return original PDF if annotation fails
            return original_pdf_bytes
    
    def _create_cover_page(
        self,
        student_name: str,
        total_earned: int,
        total_possible: int,
        percentage: float,
        grading_result: Dict,
        rubric: Dict = None
    ) -> object:
        """
        Create a cover page with grading summary.
        Groups grades by question if rubric is provided.
        """
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter
        
        # Title
        can.setFont(self.bold_font, 20)
        can.drawString(50, height - 50, "Grading Summary")
        
        # Student name (with RTL fix)
        can.setFont(self.regular_font, 14)
        fixed_name = fix_hebrew_text(student_name)
        can.drawString(50, height - 90, f"Student: {fixed_name}")
        
        # Final grade - prominent
        can.setFont(self.bold_font, 18)
        can.drawString(50, height - 120, f"FINAL GRADE: {total_earned}/{total_possible}")
        
        can.setFont(self.regular_font, 14)
        can.drawString(50, height - 145, f"({percentage:.1f}%)")
        
        # Separator line
        y_pos = height - 165
        
        all_grades = grading_result.get('grades', [])
        
        # Group grades by question
        grades_by_question = self._group_grades_by_question(all_grades, rubric)
        
        # Render each question's grades
        for q_num, q_data in sorted(grades_by_question.items()):
            # Check if we need a new page
            if y_pos < 150:
                can.showPage()
                can.setFont(self.regular_font, 10)
                y_pos = height - 50
            
            # Question header
            can.setLineWidth(1)
            can.line(50, y_pos, 520, y_pos)
            y_pos -= 20
            
            q_earned = q_data['earned']
            q_possible = q_data['possible']
            q_percentage = (q_earned / q_possible * 100) if q_possible > 0 else 0
            
            can.setFont(self.bold_font, 12)
            # Color code by question performance
            if q_percentage >= 80:
                can.setFillColor(HexColor("#228B22"))  # Green
            elif q_percentage >= 60:
                can.setFillColor(HexColor("#FF8C00"))  # Orange
            else:
                can.setFillColor(HexColor("#CC0000"))  # Red
            
            can.drawString(50, y_pos, f"Question {q_num}: {q_earned}/{q_possible} ({q_percentage:.0f}%)")
            can.setFillColor(HexColor("#000000"))
            y_pos -= 18
            
            # Render each grade in this question
            for grade in q_data['grades']:
                y_pos = self._render_grade_item(can, grade, y_pos, width, height)
                
                # Check if we need a new page
                if y_pos < 80:
                    can.showPage()
                    can.setFont(self.regular_font, 10)
                    y_pos = height - 50
        
        # Final summary section
        y_pos -= 10
        can.setLineWidth(1)
        can.line(50, y_pos, 520, y_pos)
        y_pos -= 25
        
        can.setFont(self.bold_font, 12)
        can.drawString(50, y_pos, "Summary:")
        y_pos -= 18
        
        # Generate summary based on score
        can.setFont(self.regular_font, 10)
        if percentage >= 90:
            summary = "Excellent work! Strong understanding demonstrated across all areas."
        elif percentage >= 80:
            summary = "Very good work. Shows solid grasp of most concepts."
        elif percentage >= 70:
            summary = "Good work. Some areas need improvement (see details above)."
        elif percentage >= 60:
            summary = "Satisfactory. Review failed criteria and practice more."
        else:
            summary = "Needs significant improvement. Please review all concepts carefully."
        
        can.drawString(60, y_pos, summary)
        y_pos -= 20
        
        # Add stats
        full_marks = sum(1 for g in all_grades if g.get('mark') == '✓')
        partial_marks = sum(1 for g in all_grades if g.get('mark') == '✓✗')
        failed_marks = sum(1 for g in all_grades if g.get('mark') == '✗')
        
        can.setFont(self.regular_font, 9)
        v_mark = self._get_mark_display('✓')
        x_mark = self._get_mark_display('✗')
        p_mark = self._get_mark_display('✓✗')
        
        can.setFillColor(HexColor("#228B22"))
        can.drawString(60, y_pos, f"{v_mark} Fully met: {full_marks} criteria")
        y_pos -= 14
        
        can.setFillColor(HexColor("#FF8C00"))
        can.drawString(60, y_pos, f"{p_mark} Partial credit: {partial_marks} criteria")
        y_pos -= 14
        
        can.setFillColor(HexColor("#CC0000"))
        can.drawString(60, y_pos, f"{x_mark} Not met: {failed_marks} criteria")
        can.setFillColor(HexColor("#000000"))
        
        can.save()
        
        # Create PDF page from canvas
        packet.seek(0)
        new_pdf = PdfReader(packet)
        return new_pdf.pages[0]
    
    def _group_grades_by_question(self, all_grades: List[Dict], rubric: Dict = None) -> Dict:
        """
        Group grades by question number.
        Uses rubric structure if provided, otherwise infers from criteria text.
        """
        grades_by_question = {}
        
        if rubric and rubric.get('questions'):
            # Map grades to questions based on rubric structure
            grade_idx = 0
            for q in rubric['questions']:
                q_num = q['question_number']
                num_criteria = len(q.get('criteria', []))
                
                q_grades = all_grades[grade_idx:grade_idx + num_criteria]
                grade_idx += num_criteria
                
                q_earned = sum(g.get('points_earned', 0) for g in q_grades)
                q_possible = sum(g.get('points_possible', 0) for g in q_grades)
                
                grades_by_question[q_num] = {
                    'earned': q_earned,
                    'possible': q_possible,
                    'grades': q_grades
                }
        else:
            # Fallback: Put all grades in "Question 1"
            total_earned = sum(g.get('points_earned', 0) for g in all_grades)
            total_possible = sum(g.get('points_possible', 0) for g in all_grades)
            
            grades_by_question[1] = {
                'earned': total_earned,
                'possible': total_possible,
                'grades': all_grades
            }
        
        return grades_by_question
    
    def _render_grade_item(self, can, grade: Dict, y_pos: float, width: float, height: float) -> float:
        """
        Render a single grade item with proper text wrapping.
        Returns the new y_pos after rendering.
        """
        raw_mark = grade.get('mark', '?')
        mark = self._get_mark_display(raw_mark)
        criterion = grade.get('criterion', 'Unknown')
        explanation = grade.get('explanation', '')
        points_earned = grade.get('points_earned', 0)
        points_possible = grade.get('points_possible', 0)
        
        # Color by result
        if raw_mark == '✓':
            can.setFillColor(HexColor("#228B22"))  # Green
        elif raw_mark == '✗':
            can.setFillColor(HexColor("#CC0000"))  # Red
        else:
            can.setFillColor(HexColor("#FF8C00"))  # Orange
        
        # Draw mark and points
        can.setFont(self.bold_font, 10)
        can.drawString(55, y_pos, f"{mark}")
        can.drawString(80, y_pos, f"[{points_earned}/{points_possible}]")
        
        can.setFillColor(HexColor("#000000"))
        
        # Draw criterion text - wrap if needed
        can.setFont(self.regular_font, 9)
        fixed_criterion = fix_hebrew_text(criterion)
        
        # Available width for criterion text (after mark and points)
        text_start_x = 130
        available_width = 390
        
        # Word wrap the criterion
        criterion_lines = simpleSplit(fixed_criterion, self.regular_font, 9, available_width)
        
        for i, line in enumerate(criterion_lines):
            if i == 0:
                can.drawString(text_start_x, y_pos, line)
            else:
                y_pos -= 12
                can.drawString(text_start_x, y_pos, line)
        
        y_pos -= 14
        
        # Show explanation for partial or failed marks
        if raw_mark in ['✗', '✓✗'] and explanation:
            can.setFont(self.regular_font, 8)
            can.setFillColor(HexColor("#555555"))
            
            # Fix Hebrew in explanation
            fixed_explanation = fix_hebrew_text(explanation)
            
            # Word wrap explanation
            explanation_lines = simpleSplit(fixed_explanation, self.regular_font, 8, 380)
            for exp_line in explanation_lines[:3]:  # Max 3 lines per explanation
                can.drawString(80, y_pos, f"→ {exp_line}")
                y_pos -= 11
            
            can.setFillColor(HexColor("#000000"))
        
        return y_pos


def generate_email_body(
    graded_results: List[Dict],
    low_confidence_notes: List[str] = None,
    rubric_total: int = None,
    rubric: Dict = None
) -> str:
    """
    Generate a formatted email body with detailed grading by question.
    
    Args:
        graded_results: List of grading results
        low_confidence_notes: Items needing manual review
        rubric_total: Total possible points from rubric
        rubric: Full rubric dict for question grouping
        
    Returns:
        Formatted email body text in Hebrew
    """
    lines = []
    lines.append("שלום!")
    lines.append("")
    lines.append(f"הדירוג הושלם עבור {len(graded_results)} מבחן/ים.")
    lines.append("")
    
    # Detailed grading for each student
    for result in graded_results:
        student_name = result.get("student_name", "Unknown")
        total_score = result.get("total_score", 0)
        total_possible = rubric_total if rubric_total else result.get("total_possible", 0)
        
        # Recalculate percentage with rubric total
        if rubric_total:
            percentage = (total_score / rubric_total * 100) if rubric_total > 0 else 0
        else:
            percentage = result.get("percentage", 0)
        
        lines.append("━" * 35)
        lines.append(f"תלמיד/ה: {student_name}")
        lines.append(f"ציון סופי: {total_score}/{total_possible} ({percentage:.1f}%)")
        lines.append("━" * 35)
        lines.append("")
        
        # Group grades by question
        all_grades = result.get('grades', [])
        grades_by_question = _group_grades_for_email(all_grades, rubric)
        
        for q_num, q_data in sorted(grades_by_question.items()):
            q_earned = q_data['earned']
            q_possible = q_data['possible']
            
            lines.append(f"שאלה {q_num}: {q_earned}/{q_possible}")
            
            for grade in q_data['grades']:
                mark = grade.get('mark', '?')
                criterion = grade.get('criterion', '')
                explanation = grade.get('explanation', '')
                points_earned = grade.get('points_earned', 0)
                points_possible = grade.get('points_possible', 0)
                
                # Truncate very long criteria for email readability
                if len(criterion) > 65:
                    criterion = criterion[:62] + "..."
                
                lines.append(f"  {mark}  {criterion} ({points_earned}/{points_possible})")
                
                # Add explanation for partial/failed
                if mark in ['✗', '✓✗'] and explanation:
                    lines.append(f"      → {explanation}")
            
            lines.append("")
    
    # Low confidence items
    if low_confidence_notes:
        lines.append("⚠️ פריטים הדורשים בדיקה ידנית:")
        lines.append("")
        for note in low_confidence_notes:
            lines.append(f"• {note}")
        lines.append("")
    
    lines.append("קבצי PDF מדורגים מצורפים.")
    lines.append("")
    lines.append("בברכה,")
    lines.append("מערכת הדירוג האוטומטית")
    
    return "\n".join(lines)


def _group_grades_for_email(all_grades: List[Dict], rubric: Dict = None) -> Dict:
    """Helper function to group grades by question for email body."""
    grades_by_question = {}
    
    if rubric and rubric.get('questions'):
        grade_idx = 0
        for q in rubric['questions']:
            q_num = q['question_number']
            num_criteria = len(q.get('criteria', []))
            
            q_grades = all_grades[grade_idx:grade_idx + num_criteria]
            grade_idx += num_criteria
            
            q_earned = sum(g.get('points_earned', 0) for g in q_grades)
            q_possible = sum(g.get('points_possible', 0) for g in q_grades)
            
            grades_by_question[q_num] = {
                'earned': q_earned,
                'possible': q_possible,
                'grades': q_grades
            }
    else:
        # Fallback: all in "Question 1"
        total_earned = sum(g.get('points_earned', 0) for g in all_grades)
        total_possible = sum(g.get('points_possible', 0) for g in all_grades)
        
        grades_by_question[1] = {
            'earned': total_earned,
            'possible': total_possible,
            'grades': all_grades
        }
    
    return grades_by_question