"""
PDF Text Extraction Layer for Rubric Parsing

This module provides accurate extraction of point values and structure from PDF rubrics
using pdfplumber. It's the "Layer A" in the hybrid extraction architecture.

Key capabilities:
- High-precision point value extraction (100% accuracy for simple tables)
- Section number detection (-1, -2 → sub-questions א, ב)
- Multi-page table support
- Question header detection with totals
- Word-position fallback for complex tables

Author: Vivi Engineering
"""
import io
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

import pdfplumber

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PDFTableRow:
    """A row extracted from a PDF criteria table."""
    row_index: int
    description: str = ""
    points: Optional[float] = None
    percentage: Optional[str] = None
    section_number: Optional[int] = None
    is_header: bool = False
    is_total: bool = False
    is_deduction: bool = False
    raw_cells: List[str] = field(default_factory=list)


@dataclass
class PDFCriteriaTable:
    """A complete criteria table extracted from PDF."""
    page_num: int
    rows: List[PDFTableRow] = field(default_factory=list)
    total_points: Optional[float] = None
    
    @property
    def criteria_count(self) -> int:
        """Count of actual criteria (excluding headers, totals)."""
        return sum(1 for r in self.rows 
                   if r.points is not None and not r.is_header and not r.is_total)
    
    @property
    def criteria_rows(self) -> List[PDFTableRow]:
        """Only the actual criteria rows."""
        return [r for r in self.rows 
                if r.points is not None and not r.is_header and not r.is_total]


@dataclass
class QuestionHeader:
    """A question header found in PDF (שאלה X - Y נקודות)."""
    question_number: int
    total_points: float
    page_index: int
    match_text: str


@dataclass
class PDFExtractionResult:
    """Complete result from PDF text extraction."""
    criteria: List[Dict[str, Any]] = field(default_factory=list)
    total_points: Optional[float] = None
    question_headers: List[QuestionHeader] = field(default_factory=list)
    tables_found: int = 0
    extraction_method: str = "table"  # "table" or "word_position"


# =============================================================================
# PDF Criteria Extractor
# =============================================================================

class PDFCriteriaExtractor:
    """
    Extracts criteria and point values from PDF rubrics using pdfplumber.
    
    This is optimized for Hebrew CS test rubrics with:
    - RTL text layout
    - Tables with points in Hebrew format
    - Section numbering (-1, -2, etc.)
    - Deduction rules (להוריד)
    
    Usage:
        with PDFCriteriaExtractor(pdf_bytes) as extractor:
            result = extractor.extract_from_pages([1, 2])
            headers = extractor.find_question_headers()
    """
    
    # Regex patterns for Hebrew rubric format
    POINTS_PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*$')
    SECTION_PATTERN = re.compile(r'-(\d+)\s')
    SECTION_PATTERN_ALT = re.compile(r'(\d+)\s*[-–]')
    TOTAL_PATTERN = re.compile(r'סה"כ|סה״כ|כ"הס|סהכ', re.UNICODE)
    HEADER_PATTERN = re.compile(r'רכיב\s*הערכה|ניקוד|אחוז', re.UNICODE)
    DEDUCTION_PATTERN = re.compile(r'להוריד|הורד', re.UNICODE)
    COMMENT_PATTERN = re.compile(r'Commented\s*\[', re.IGNORECASE)
    PERCENTAGE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*%')
    
    QUESTION_HEADER_PATTERN = re.compile(
        r'שאלה\s*(\d+)\s*[-–]\s*(\d+(?:\.\d+)?)\s*נקודות',
        re.UNICODE
    )
    
    # Row grouping tolerance for word-position extraction
    ROW_Y_TOLERANCE = 12  # pixels
    
    def __init__(self, pdf_bytes: bytes):
        """
        Initialize extractor with PDF bytes.
        
        Args:
            pdf_bytes: PDF file content as bytes
        """
        self.pdf_bytes = pdf_bytes
        self._pdf: Optional[pdfplumber.PDF] = None
    
    def __enter__(self):
        """Context manager entry - open PDF."""
        self._pdf = pdfplumber.open(io.BytesIO(self.pdf_bytes))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close PDF."""
        if self._pdf:
            self._pdf.close()
            self._pdf = None
    
    @property
    def num_pages(self) -> int:
        """Number of pages in the PDF."""
        return len(self._pdf.pages) if self._pdf else 0
    
    def find_question_headers(self) -> List[QuestionHeader]:
        """
        Find all question headers in the PDF.
        
        Looks for patterns like "שאלה 1 - 15 נקודות"
        
        Returns:
            List of QuestionHeader objects
        """
        if not self._pdf:
            return []
        
        headers = []
        
        for page_idx, page in enumerate(self._pdf.pages):
            text = page.extract_text() or ""
            
            for match in self.QUESTION_HEADER_PATTERN.finditer(text):
                headers.append(QuestionHeader(
                    question_number=int(match.group(1)),
                    total_points=float(match.group(2)),
                    page_index=page_idx,
                    match_text=match.group(0)
                ))
        
        logger.info(f"Found {len(headers)} question headers in PDF")
        return headers
    
    def extract_from_pages(
        self, 
        page_indexes: List[int],
        prefer_word_extraction: bool = False
    ) -> PDFExtractionResult:
        """
        Extract criteria from specified pages.
        
        Args:
            page_indexes: 0-indexed page numbers to extract from
            prefer_word_extraction: If True, prefer word-position method
            
        Returns:
            PDFExtractionResult with extracted criteria
        """
        if not self._pdf:
            logger.error("PDF not opened. Use 'with' statement.")
            return PDFExtractionResult()
        
        all_criteria = []
        total_points = None
        tables_found = 0
        extraction_method = "table"
        
        for page_idx in page_indexes:
            if page_idx >= self.num_pages:
                logger.warning(f"Page index {page_idx} out of range (max: {self.num_pages - 1})")
                continue
            
            page = self._pdf.pages[page_idx]
            
            # Try table extraction first (unless word extraction preferred)
            if not prefer_word_extraction:
                page_tables = page.extract_tables()
                
                for raw_table in page_tables:
                    if not raw_table or len(raw_table) < 2:
                        continue
                    
                    # Skip comment tables
                    first_cell = str(raw_table[0][0] or "")
                    if self.COMMENT_PATTERN.search(first_cell):
                        continue
                    
                    parsed_table = self._parse_table(raw_table, page_idx)
                    if parsed_table.criteria_count > 0:
                        tables_found += 1
                        
                        # Add criteria
                        for row in parsed_table.criteria_rows:
                            all_criteria.append({
                                "description": row.description,
                                "points": row.points,
                                "section_number": row.section_number,
                                "is_deduction": row.is_deduction,
                                "source": "pdf_table",
                                "page": page_idx
                            })
                        
                        # Capture total
                        if parsed_table.total_points:
                            total_points = parsed_table.total_points
            
            # Try word-position extraction if table extraction yielded few results
            table_criteria_count = len([c for c in all_criteria if c.get("page") == page_idx])
            
            if table_criteria_count < 3 or prefer_word_extraction:
                word_result = self._extract_via_word_positions(page, page_idx)
                
                if word_result.criteria_count > table_criteria_count:
                    # Remove table-extracted criteria for this page
                    all_criteria = [c for c in all_criteria if c.get("page") != page_idx]
                    
                    # Add word-extracted criteria
                    for row in word_result.criteria_rows:
                        all_criteria.append({
                            "description": row.description,
                            "points": row.points,
                            "section_number": row.section_number,
                            "is_deduction": row.is_deduction,
                            "source": "pdf_words",
                            "page": page_idx
                        })
                    
                    if word_result.total_points:
                        total_points = word_result.total_points
                    
                    extraction_method = "word_position"
                    logger.info(f"Page {page_idx}: Used word-position extraction "
                               f"({word_result.criteria_count} vs {table_criteria_count} criteria)")
        
        return PDFExtractionResult(
            criteria=all_criteria,
            total_points=total_points,
            tables_found=tables_found,
            extraction_method=extraction_method
        )
    
    def _parse_table(self, raw_table: List[List], page_num: int) -> PDFCriteriaTable:
        """Parse a raw pdfplumber table into structured criteria."""
        result = PDFCriteriaTable(page_num=page_num)
        
        # Identify column positions
        col_positions = self._identify_columns(raw_table)
        points_col = col_positions.get("points")
        desc_col = col_positions.get("description")
        
        if points_col is None:
            return result
        
        for row_idx, raw_row in enumerate(raw_table):
            parsed_row = self._parse_row(
                raw_row, row_idx, points_col, desc_col
            )
            if parsed_row:
                result.rows.append(parsed_row)
                
                if parsed_row.is_total and parsed_row.points:
                    result.total_points = parsed_row.points
        
        return result
    
    def _identify_columns(self, table: List[List]) -> Dict[str, int]:
        """
        Identify which columns contain points vs descriptions.
        
        Analyzes column content to find:
        - Points column (numeric values)
        - Description column (longest text)
        - Percentage column (% values)
        """
        if not table or not table[0]:
            return {}
        
        num_cols = max(len(row) for row in table)
        col_stats = {i: {
            "numeric": 0,
            "percentage": 0,
            "text_length": 0,
            "non_empty": 0
        } for i in range(num_cols)}
        
        # Analyze all rows
        for row in table:
            for col_idx, cell in enumerate(row):
                if not cell:
                    continue
                
                cell_str = str(cell).strip()
                if not cell_str:
                    continue
                
                col_stats[col_idx]["non_empty"] += 1
                
                # Check for percentage
                if self.PERCENTAGE_PATTERN.match(cell_str) or cell_str.endswith('%'):
                    col_stats[col_idx]["percentage"] += 1
                # Check for numeric (standalone number)
                elif self.POINTS_PATTERN.match(cell_str):
                    col_stats[col_idx]["numeric"] += 1
                else:
                    col_stats[col_idx]["text_length"] += len(cell_str)
        
        result = {}
        
        # Filter to active columns (at least 2 non-empty cells)
        active_cols = [col for col, stats in col_stats.items() 
                       if stats["non_empty"] >= 2]
        
        if not active_cols:
            return {}
        
        # Find percentage column
        pct_candidates = [(col, col_stats[col]["percentage"]) 
                          for col in active_cols if col_stats[col]["percentage"] > 0]
        if pct_candidates:
            result["percentage"] = max(pct_candidates, key=lambda x: x[1])[0]
        
        # Find points column (numeric, not percentage)
        numeric_candidates = [(col, col_stats[col]["numeric"]) 
                              for col in active_cols 
                              if col_stats[col]["numeric"] > 0 
                              and col != result.get("percentage")]
        if numeric_candidates:
            result["points"] = max(numeric_candidates, key=lambda x: x[1])[0]
        
        # Find description column (most text, not already assigned)
        text_candidates = [(col, col_stats[col]["text_length"]) 
                           for col in active_cols 
                           if col not in result.values()]
        if text_candidates:
            result["description"] = max(text_candidates, key=lambda x: x[1])[0]
        
        return result
    
    def _parse_row(
        self,
        raw_row: List,
        row_idx: int,
        points_col: Optional[int],
        desc_col: Optional[int]
    ) -> Optional[PDFTableRow]:
        """Parse a single table row."""
        
        def get_cell(col: Optional[int]) -> str:
            if col is None or col >= len(raw_row):
                return ""
            return str(raw_row[col] or "").strip()
        
        points_str = get_cell(points_col)
        desc_str = get_cell(desc_col)
        
        # Store raw cells
        raw_cells = [str(c) if c else "" for c in raw_row]
        
        # Check if header row
        if self.HEADER_PATTERN.search(desc_str) or self.HEADER_PATTERN.search(points_str):
            return PDFTableRow(
                row_index=row_idx,
                is_header=True,
                raw_cells=raw_cells
            )
        
        # Check if total row
        is_total = bool(self.TOTAL_PATTERN.search(desc_str))
        
        # Parse points value
        points = None
        points_match = self.POINTS_PATTERN.match(points_str)
        if points_match:
            try:
                points = float(points_match.group(1))
            except ValueError:
                pass
        
        # If no points found, this isn't a criteria row
        if points is None and not is_total:
            return None
        
        # Extract section number from description
        section_number = None
        section_match = self.SECTION_PATTERN.search(desc_str)
        if section_match:
            section_number = int(section_match.group(1))
        else:
            # Try alternate pattern
            alt_match = self.SECTION_PATTERN_ALT.search(desc_str)
            if alt_match:
                section_number = int(alt_match.group(1))
        
        # Check if deduction rule
        is_deduction = bool(self.DEDUCTION_PATTERN.search(desc_str))
        
        return PDFTableRow(
            row_index=row_idx,
            description=desc_str,
            points=points,
            section_number=section_number,
            is_header=False,
            is_total=is_total,
            is_deduction=is_deduction,
            raw_cells=raw_cells
        )
    
    def _extract_via_word_positions(
        self, 
        page, 
        page_num: int
    ) -> PDFCriteriaTable:
        """
        Alternative extraction using word positions.
        
        Groups words by Y position to reconstruct rows for complex tables.
        """
        result = PDFCriteriaTable(page_num=page_num)
        
        try:
            words = page.extract_words()
            if not words:
                return result
            
            # Group words by Y position
            y_groups: Dict[int, List] = {}
            for w in words:
                y_key = round(w['top'] / self.ROW_Y_TOLERANCE) * self.ROW_Y_TOLERANCE
                if y_key not in y_groups:
                    y_groups[y_key] = []
                y_groups[y_key].append(w)
            
            row_idx = 0
            for y_key in sorted(y_groups.keys()):
                row_words = sorted(y_groups[y_key], key=lambda w: w['x0'])
                row_text = ' '.join(w['text'] for w in row_words)
                
                # Look for point value
                points = None
                section_number = None
                is_total = bool(self.TOTAL_PATTERN.search(row_text))
                is_deduction = bool(self.DEDUCTION_PATTERN.search(row_text))
                
                for w in row_words:
                    text = w['text'].strip()
                    
                    # Point value
                    match = self.POINTS_PATTERN.match(text)
                    if match and points is None:
                        try:
                            val = float(match.group(1))
                            # Must be reasonable (0.25 to 100)
                            if 0.25 <= val <= 100:
                                points = val
                        except ValueError:
                            pass
                    
                    # Section number
                    sec_match = self.SECTION_PATTERN.search(text)
                    if sec_match and section_number is None:
                        section_number = int(sec_match.group(1))
                
                if points is None:
                    continue
                
                # Check if header
                if self.HEADER_PATTERN.search(row_text):
                    continue
                
                if is_total:
                    result.total_points = points
                    result.rows.append(PDFTableRow(
                        row_index=row_idx,
                        description=row_text,
                        points=points,
                        is_total=True,
                        raw_cells=[row_text]
                    ))
                else:
                    result.rows.append(PDFTableRow(
                        row_index=row_idx,
                        description=row_text,
                        points=points,
                        section_number=section_number,
                        is_deduction=is_deduction,
                        raw_cells=[row_text]
                    ))
                
                row_idx += 1
            
            return result
            
        except Exception as e:
            logger.warning(f"Word-position extraction failed for page {page_num}: {e}")
            return result


# =============================================================================
# Convenience Functions
# =============================================================================

def extract_pdf_points(
    pdf_bytes: bytes,
    page_indexes: List[int]
) -> PDFExtractionResult:
    """
    Quick extraction of point values from PDF pages.
    
    Args:
        pdf_bytes: PDF file content
        page_indexes: 0-indexed pages to extract from
        
    Returns:
        PDFExtractionResult with extracted criteria and totals
    """
    with PDFCriteriaExtractor(pdf_bytes) as extractor:
        return extractor.extract_from_pages(page_indexes)


def find_question_headers(pdf_bytes: bytes) -> List[QuestionHeader]:
    """
    Find all question headers in a PDF.
    
    Args:
        pdf_bytes: PDF file content
        
    Returns:
        List of QuestionHeader objects
    """
    with PDFCriteriaExtractor(pdf_bytes) as extractor:
        return extractor.find_question_headers()
