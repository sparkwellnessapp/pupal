"""
Rubric service layer.

Handles rubric extraction from PDFs with support for:
- Questions with direct criteria
- Questions with sub-questions (א, ב, ג...), each having their own criteria

World-class features:
- PDF-native table extraction via pdfplumber for 100% accuracy
- 3-stage pipeline: PDF extraction → LLM enhancement → validation
- Structured reduction rules for better grading
- RTL text normalization using python-bidi
"""
import logging
import json
import re
import io
import asyncio
from typing import Optional, Dict, Any, List
from uuid import UUID

import pdfplumber
from pydantic import BaseModel, Field, ValidationError
from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# RTL text handling
try:
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("python-bidi not installed, RTL text may appear reversed")

from ..models.grading import Rubric
from ..schemas.grading import (
    QuestionPageMapping,
    SubQuestionPageMapping,
    ExtractedQuestion,
    ExtractedSubQuestion,
    EnhancedCriterion,
    ReductionRule,
    ExtractRubricResponse,
    SaveRubricRequest,
)
from .document_parser import pdf_to_images, image_to_base64, call_vision_llm, get_openai_client
from .vlm_rubric_extractor import QUESTION_EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _normalize_rtl_text(text: str) -> str:
    """
    Normalize RTL (Hebrew/Arabic) text extracted from PDFs.
    
    pdfplumber extracts text in visual order which can reverse RTL text.
    This function uses the Unicode BiDi algorithm to restore correct logical order.
    
    Args:
        text: Raw text extracted from PDF
        
    Returns:
        Text with proper RTL ordering
    """
    if not text or not HAS_BIDI:
        return text
    
    # Check if text contains Hebrew characters
    hebrew_pattern = re.compile(r'[\u0590-\u05FF]')
    if not hebrew_pattern.search(text):
        return text  # No Hebrew, return as-is
    
    try:
        # get_display converts logical order to visual order
        # Since pdfplumber may already give us visual order, we need to 
        # apply it to get back to logical order for storage
        # The trick: if text is already in wrong visual order, applying get_display fixes it
        return get_display(text)
    except Exception as e:
        logger.warning(f"RTL normalization failed: {e}")
        return text


# =============================================================================
# Stage 1: PDF-Native Table Extraction
# =============================================================================

RUBRIC_HEADER_INDICATORS = {"רכיב", "הערכה", "ניקוד", "קריטריון", "נקודות", "%"}


def extract_tables_from_pdf_native(
    pdf_bytes: bytes,
    page_indexes: List[int]
) -> List[Dict]:
    """
    Extract tables from PDF using pdfplumber for 100% accurate text extraction.
    """
    tables = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_idx in page_indexes:
                if page_idx >= len(pdf.pages):
                    continue
                    
                page = pdf.pages[page_idx]
                page_tables = page.extract_tables()
                
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) > 0:
                        # Clean and normalize RTL text in each cell
                        cleaned_rows = [
                            [_normalize_rtl_text(cell.strip()) if cell else "" for cell in row]
                            for row in table
                        ]
                        tables.append({
                            "page_index": page_idx,
                            "table_index": table_idx,
                            "rows": cleaned_rows,
                            "extraction_method": "pdf_native"
                        })
                        
        logger.info(f"Extracted {len(tables)} tables from {len(page_indexes)} pages via pdfplumber")
        
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        
    return tables


def _is_valid_rubric_table(table: Dict) -> bool:
    """
    Check if table is a valid rubric criteria table.
    
    Accept tables that have:
    1. At least 2 rows (header + data)
    2. Numeric values in data rows (typically points/percentages)
    3. At least one column with substantial text (criterion descriptions)
    """
    rows = table.get("rows", [])
    if len(rows) < 2:
        return False
    
    # Check for numeric values and text content in data rows
    has_numeric_data = False
    has_text_content = False
    
    for row in rows[1:]:  # Skip header
        if len(row) >= 2:
            for cell in row:
                cell_str = str(cell).strip() if cell else ""
                # Check for numeric (points or percentage)
                if re.match(r'^\d+(?:\.\d+)?%?$', cell_str):
                    has_numeric_data = True
                # Check for substantial text (description)
                elif len(cell_str) > 10:
                    has_text_content = True
        
        if has_numeric_data and has_text_content:
            return True
    
    return False


def _detect_column_roles(rows: List[List[str]]) -> Dict[str, int]:
    """
    Intelligently detect column roles for Hebrew RTL rubric tables.
    
    Hebrew tables are RTL so pdfplumber reads them as:
    - Column 0 (leftmost) = typically percentage or empty
    - Column 1 = typically points (ניקוד)
    - Column -1 (rightmost) = typically description (רכיב הערכה)
    
    Returns dict with 'description', 'points', 'percentage' column indexes.
    """
    if not rows or len(rows) < 2:
        return {"description": -1, "points": 1, "percentage": 0}
    
    num_cols = max(len(row) for row in rows)
    
    # Analyze each column's content
    column_analysis = []
    for col_idx in range(num_cols):
        col_data = {
            "avg_text_length": 0,
            "numeric_count": 0,
            "percentage_count": 0,
            "text_count": 0,
            "total_rows": 0
        }
        
        for row in rows[1:]:  # Skip header
            if col_idx >= len(row):
                continue
            
            cell = str(row[col_idx]).strip() if row[col_idx] else ""
            col_data["total_rows"] += 1
            col_data["avg_text_length"] += len(cell)
            
            # Percentage pattern (e.g., "10%", "20%")
            if re.match(r'^\d+(?:\.\d+)?%$', cell):
                col_data["percentage_count"] += 1
            # Numeric pattern (standalone number)
            elif re.match(r'^\d+(?:\.\d+)?$', cell):
                col_data["numeric_count"] += 1
            # Text (substantial content)
            elif len(cell) > 5:
                col_data["text_count"] += 1
        
        if col_data["total_rows"] > 0:
            col_data["avg_text_length"] /= col_data["total_rows"]
        
        column_analysis.append(col_data)
    
    # Find description column (most text, longest average length)
    description_col = -1  # Default to last column (RTL assumption)
    max_text_score = 0
    
    for col_idx, analysis in enumerate(column_analysis):
        text_score = analysis["text_count"] * 10 + analysis["avg_text_length"]
        if text_score > max_text_score:
            max_text_score = text_score
            description_col = col_idx
    
    # Find points column (mostly numeric, not percentage)
    points_col = 1  # Default
    max_numeric_score = 0
    
    for col_idx, analysis in enumerate(column_analysis):
        if col_idx == description_col:
            continue
        numeric_score = analysis["numeric_count"] - analysis["percentage_count"]
        if numeric_score > max_numeric_score:
            max_numeric_score = numeric_score
            points_col = col_idx
    
    # Find percentage column (if exists)
    percentage_col = -1
    max_pct_count = 0
    
    for col_idx, analysis in enumerate(column_analysis):
        if analysis["percentage_count"] > max_pct_count:
            max_pct_count = analysis["percentage_count"]
            percentage_col = col_idx
    
    logger.debug(f"Column roles detected: description={description_col}, points={points_col}, percentage={percentage_col}")
    
    return {
        "description": description_col,
        "points": points_col,
        "percentage": percentage_col
    }


def _extract_points(row: List[str], points_column_index: int = 1) -> float:
    """
    Extract points from table row, avoiding embedded numbers in description.
    """
    # Try expected column first (must be standalone number)
    if len(row) > points_column_index:
        cell = str(row[points_column_index]).strip()
        if re.match(r'^\d+(?:\.\d+)?$', cell):
            return float(cell)
    
    # Fallback: scan columns 1+ for standalone numbers (skip column 0)
    for cell in row[1:]:
        cell_str = str(cell).strip() if cell else ""
        if re.match(r'^\d+(?:\.\d+)?$', cell_str):
            return float(cell_str)
    
    return 0.0


# =============================================================================
# Stage 1b: VLM Fallback
# =============================================================================

VLM_RUBRIC_EXTRACTION_PROMPT = """אתה מומחה בחילוץ טבלאות מחוונים.

=== הוראות קריטיות ===
1. העתק טקסט בדיוק - אל תשנה
2. תאים רב-שורתיים: הפרד עם \\n
3. כלול כללי הורדה ("להוריד X")
4. temperature=0

=== פורמט פלט (JSON בלבד) ===
{
  "rows": [
    {"row_index": 1, "criterion_full_text": "...", "points": 3.0, "percentage": 20}
  ]
}"""


async def _extract_tables_vlm_fallback(
    images_b64: List[str],
    context: str
) -> List[Dict]:
    """VLM fallback with asyncio.to_thread to avoid blocking event loop."""
    try:
        client = get_openai_client()
        
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}", "detail": "high"}} 
            for img in images_b64
        ]
        content.append({"type": "text", "text": f"חלץ את טבלת המחוון עבור {context}."})
        
        # Wrap sync call to not block event loop
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": VLM_RUBRIC_EXTRACTION_PROMPT},
                {"role": "user", "content": content}
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.0
        )
        
        data = json.loads(response.choices[0].message.content)
        rows_data = data.get("rows", [])
        
        if rows_data:
            return [{
                "page_index": -1,
                "table_index": 0,
                "rows": [[r.get("criterion_full_text", ""), str(r.get("points", 0)), str(r.get("percentage", ""))] for r in rows_data],
                "extraction_method": "vlm_fallback"
            }]
            
    except Exception as e:
        logger.error(f"[{context}] VLM fallback failed: {e}")
        
    return []


# =============================================================================
# Stage 2: LLM Criterion Enhancement
# =============================================================================

CRITERION_ENHANCEMENT_PROMPT = """<role>
אתה פרופסור ומומחה עולמי להוראת מדעי המחשב, עם 25 שנות ניסיון ביצירת מחוונים, הערכת מבחני בגרות, והכשרת מורים.
אתה מבין לעומק את סוגי השגיאות הנפוצות של תלמידי תיכון בתכנות.
</role>

<task>
נתח קריטריון הערכה ופרק אותו לכללי הורדת נקודות (reduction_rules) ספציפיים, מקצועיים ושימושיים.
</task>

<bidi_text_cleanup>
🔴 חשוב מאוד: הטקסט שמגיע אליך עשוי להיות מעורבב בגלל בעיית RTL/LTR!

דוגמאות לטקסט מעורבב שצריך לתקן:
❌ מעורבב: "בדיקה age s חתימה מתאימה והחזרה3 2 bool פעולה פנימית2 -4 isToddler"
✅ נקי: "פעולה פנימית isToddler - חתימה מתאימה (פרמטר מסוג int, מחזירה bool)"

❌ מעורבב: "AddBaby במחלקה Gan 6- 2 3 בדיקה אם יש מקום במערך"  
✅ נקי: "פעולה AddBaby במחלקה Gan - בדיקה אם יש מקום במערך"

❌ מעורבב: "CalcMonthlyIncome 7- פעולה חיצונית int / double"
✅ נקי: "פעולה חיצונית CalcMonthlyIncome - מחזירה int או double"

עקרונות לניקוי:
1. שים שמות פונקציות באנגלית במיקום הנכון לפי ההקשר
2. מספרים שמייצגים נקודות (כמו "6-" או "-4") הם ניקוד - לא לכלול בתיאור
3. סוגי נתונים (int, bool, double, string) שייכים לתיאור החתימה
4. בנה משפט עברי קריא וברור
</bidi_text_cleanup>

<critical_constraints>
🚫 אילוץ מוחלט #1: אסור כללים גנריים!
   ❌ אסור: "טעות כללית", "שגיאה אחרת", "בעיה נוספת", "שאר השגיאות"
   ✅ חובה: כללים ספציפיים שמורה יכול לזהות בקוד התלמיד

🚫 אילוץ מוחלט #2: סכום הנקודות!
   סכום כל reduction_value חייב להיות שווה בדיוק ל-total_points

🚫 אילוץ מוחלט #3: תקן את טקסט הקריטריון!
   criterion_description חייב להיות טקסט עברי **קריא ומסודר** - לא הטקסט המעורבב המקורי!
</critical_constraints>

<error_taxonomy>
השתמש בטקסונומיה זו לבחירת כללים ספציפיים לפי נושא:

| נושא | מילות מפתח | שגיאות נפוצות |
|------|------------|---------------|
| חתימת מתודה | כותרת, חתימה, פעולה | שם שגוי, סוג מוחזר שגוי, רשימת פרמטרים (מספר/סוג/סדר), חסר static, חסר public |
| לולאות | for, while, loop | משתנה לולאה, תנאי עצירה, קידום i++, מספר חזרות, off-by-one |
| מערכים | array, מערך, [] | גודל שגוי, אינדקס מחוץ לתחום, אתחול, נוסחת הגבול i<n |
| תנאים | if, else, switch | תנאי שגוי, חסר else, סדר תנאים, תנאי מיותר |
| OOP | class, אובייקט, new | בנאי שגוי, חסר new, null reference, this |
| קלט/פלט | print, Scanner | פורמט שגוי, nextLine vs nextInt, הודעה למשתמש |
| ערכים | return, משתנים | return שגוי, אתחול חסר, סוג משתנה שגוי |
</error_taxonomy>

<thinking_process>
לפני שתענה, עבור על שלבי החשיבה הבאים (פנימית, לא להציג בפלט):

שלב 1: זיהוי הנושא
- מה הקריטריון מתאר? (מתודה? לולאה? מערך? OOP?)
- אילו מילות מפתח מופיעות?

שלב 2: חילוץ כללים מפורשים
- האם יש "להוריד X" או "X נק'" בטקסט?
- אלו הופכים ל-is_explicit: true

שלב 3: הסקת כללים נוספים
- כמה נקודות נותרו אחרי הכללים המפורשים?
- אילו שגיאות ספציפיות רלוונטיות לנושא מהטקסונומיה?
- חלק את הנקודות הנותרות בין הכללים המוסקים

שלב 4: אימות
- האם סכום הנקודות = total_points?
- האם כל הכללים ספציפיים (לא גנריים)?
- האם criterion_description שומר על הניסוח המקורי?
</thinking_process>

<examples>
דוגמה 1 - חתימת מתודה:
קלט: "כותרת הפעולה, חתימה נכונה\nאם שכחו static להוריד 0.5"
total_points: 1.5

פלט:
{
  "criterion_description": "כותרת הפעולה, חתימה נכונה",
  "raw_text": "כותרת הפעולה, חתימה נכונה\nאם שכחו static להוריד 0.5",
  "reduction_rules": [
    {"description": "חסר static", "reduction_value": 0.5, "is_explicit": true},
    {"description": "שם הפעולה שגוי", "reduction_value": 0.5, "is_explicit": false},
    {"description": "רשימת פרמטרים שגויה (מספר, סוג או סדר)", "reduction_value": 0.5, "is_explicit": false}
  ]
}
✓ סכום: 0.5+0.5+0.5=1.5

---

דוגמה 2 - לולאה:
קלט: "שימוש נכון בלולאה"
total_points: 3

פלט:
{
  "criterion_description": "שימוש נכון בלולאה",
  "raw_text": "שימוש נכון בלולאה",
  "reduction_rules": [
    {"description": "הגדרת משתנה הלולאה שגויה", "reduction_value": 1, "is_explicit": false},
    {"description": "תנאי עצירה שגוי", "reduction_value": 1, "is_explicit": false},
    {"description": "קידום/הקטנה של משתנה הלולאה", "reduction_value": 1, "is_explicit": false}
  ]
}
✓ סכום: 1+1+1=3

---

דוגמה 3 - מערך:
קלט: "מעבר נכון על המערך וספירת איברים"
total_points: 4

פלט:
{
  "criterion_description": "מעבר נכון על המערך וספירת איברים",
  "raw_text": "מעבר נכון על המערך וספירת איברים",
  "reduction_rules": [
    {"description": "נוסחת הגבול שגויה (i<n או i<=n-1)", "reduction_value": 1.5, "is_explicit": false},
    {"description": "תנאי הספירה שגוי", "reduction_value": 1.5, "is_explicit": false},
    {"description": "אתחול מונה הספירה", "reduction_value": 1, "is_explicit": false}
  ]
}
✓ סכום: 1.5+1.5+1=4
</examples>

<wrong_examples>
❌ שגוי: {"description": "טעות כללית אחרת", "reduction_value": 1}
   למה? "טעות כללית" לא עוזר למורה - מה בדיוק לבדוק?

❌ שגוי: {"description": "שגיאות נוספות", "reduction_value": 2}
   למה? לא ספציפי - המורה לא יודע מה לחפש

✅ נכון: {"description": "רשימת פרמטרים שגויה (מספר, סוג או סדר)", "reduction_value": 0.5}
   למה? ספציפי - המורה יודע בדיוק מה לבדוק בקוד!
</wrong_examples>

<output_schema>
{
  "criterion_description": "תיאור נקי וקריא בעברית (מתוקן מהטקסט המעורבב!)",
  "raw_text": "הטקסט המלא המקורי כגיבוי",
  "reduction_rules": [
    {
      "description": "תיאור ספציפי של השגיאה",
      "reduction_value": 0.5,
      "is_explicit": true/false
    }
  ],
  "notes": null
}
</output_schema>

<final_checklist>
לפני החזרת התשובה, וודא:
☐ criterion_description = טקסט עברי נקי וקריא (לא מעורבב!)
☐ סכום reduction_value = total_points בדיוק
☐ כל כלל הוא ספציפי (לא "טעות כללית"!)
☐ כללים מפורשים מסומנים is_explicit: true
☐ כללים מוסקים מסומנים is_explicit: false
☐ הפלט הוא JSON תקני בלבד
</final_checklist>"""


def _extract_json_from_response(content: str) -> Optional[Dict]:
    """
    Extract JSON from LLM response that may contain markdown or reasoning text.
    o4-mini often returns JSON wrapped in ```json blocks or with reasoning prefix.
    """
    if not content or not content.strip():
        return None
    
    content = content.strip()
    
    # Try direct JSON parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Extract from ```json ... ``` code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Find JSON object in text (starts with { ends with })
    brace_match = re.search(r'\{[\s\S]*\}', content)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def _create_fallback_criterion(criterion_text: str, total_points: float) -> Dict:
    """
    Create a basic structured criterion when LLM enhancement fails.
    Ensures we never lose extracted criteria data.
    """
    return {
        "criterion_description": criterion_text.split('\n')[0].strip()[:100],  # First line, max 100 chars
        "total_points": total_points,
        "reduction_rules": [{
            "description": criterion_text,
            "reduction_value": total_points,
            "is_explicit": True
        }],
        "notes": "הוזן ללא פירוק לכללים - יש לערוך ידנית",
        "raw_text": criterion_text,
        "extraction_confidence": "low"
    }


@traceable(name="enhance_criterion_with_rules", run_type="llm")
async def enhance_criterion_with_rules(
    raw_criterion: Dict,
    total_question_points: float,
    max_retries: int = 2
) -> Optional[Dict]:
    """
    Transform raw criterion into structured format with reduction rules.
    
    Robust implementation with:
    - Retry logic for transient failures
    - JSON extraction from various response formats
    - Fallback to raw criterion on complete failure
    """
    criterion_text = raw_criterion.get("criterion_full_text", "")
    total_points = float(raw_criterion.get("points", 0))
    
    if not criterion_text or total_points <= 0:
        return None
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            client = get_openai_client()
            
            # Use gpt-4o with JSON mode for reliability
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o",  # Back to gpt-4o for JSON reliability
                messages=[
                    {"role": "system", "content": CRITERION_ENHANCEMENT_PROMPT},
                    {"role": "user", "content": f"קריטריון: \"{criterion_text}\"\ntotal_points: {total_points}"}
                ],
                response_format={"type": "json_object"},  # Ensure JSON output
                max_tokens=2000,
                temperature=0.1
            )
            
            response_content = response.choices[0].message.content
            
            if not response_content:
                logger.warning(f"Empty response on attempt {attempt + 1}")
                continue
            
            # Extract JSON from response
            data = _extract_json_from_response(response_content)
            
            if not data:
                logger.warning(f"Failed to parse JSON on attempt {attempt + 1}: {response_content[:200]}")
                continue
            
            return {
                "criterion_description": data.get("criterion_description", criterion_text.split('\n')[0]),
                "total_points": total_points,
                "reduction_rules": data.get("reduction_rules", []),
                "notes": data.get("notes"),
                "raw_text": criterion_text,
                "extraction_confidence": "high"
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"Criterion enhancement attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)  # Brief delay before retry
    
    # All retries failed - return fallback structure instead of None
    logger.error(f"Criterion enhancement failed after {max_retries} attempts: {last_error}")
    logger.info(f"Using fallback for criterion: {criterion_text[:50]}...")
    return _create_fallback_criterion(criterion_text, total_points)


# =============================================================================
# Stage 3: Validation & Fixing
# =============================================================================

def validate_and_fix_enhanced_criterion(criterion: Dict) -> Dict:
    """Validate and fix reduction rules sum."""
    total_points = criterion.get("total_points", 0)
    rules = criterion.get("reduction_rules", [])
    
    if not rules:
        criterion["reduction_rules"] = [{
            "description": criterion.get("criterion_description") or criterion.get("raw_text", "כללי"),
            "reduction_value": total_points,
            "is_explicit": False
        }]
        criterion["extraction_confidence"] = "low"
        return criterion
    
    # Filter invalid, cap at total_points
    valid_rules = [r for r in rules if r.get("reduction_value", 0) > 0]
    for rule in valid_rules:
        if rule["reduction_value"] > total_points:
            rule["reduction_value"] = total_points
    
    rules_sum = sum(r["reduction_value"] for r in valid_rules)
    
    if abs(rules_sum - total_points) <= 0.01:
        criterion["reduction_rules"] = valid_rules
        return criterion
    
    if rules_sum < total_points:
        # Add catch-all
        difference = round(total_points - rules_sum, 2)
        valid_rules.append({
            "description": "טעות כללית אחרת",
            "reduction_value": difference,
            "is_explicit": False
        })
        criterion["extraction_confidence"] = "medium"
        
    elif rules_sum > total_points:
        # Scale down with minimum threshold
        scale_factor = total_points / rules_sum
        for rule in valid_rules:
            rule["reduction_value"] = max(0.01, round(rule["reduction_value"] * scale_factor, 2))
        
        # Fix rounding errors
        new_sum = sum(r["reduction_value"] for r in valid_rules)
        if abs(new_sum - total_points) > 0.01:
            valid_rules[-1]["reduction_value"] += round(total_points - new_sum, 2)
        
        criterion["extraction_confidence"] = "medium"
    
    criterion["reduction_rules"] = valid_rules
    return criterion


# =============================================================================
# Main Enhanced Extraction Pipeline
# =============================================================================

@traceable(name="extract_criteria_enhanced", run_type="chain")
async def extract_criteria_enhanced(
    pdf_bytes: bytes,
    images_b64: List[str],
    page_indexes: List[int],
    context: str
) -> Dict[str, Any]:
    """
    Enhanced 3-stage criteria extraction pipeline.
    
    Returns:
        {
            "criteria": List[EnhancedCriterion dict],
            "total_points": float,
            "extraction_status": "success" | "partial" | "failed",
            "extraction_method": "pdf_native" | "vlm_fallback",
            "extraction_error": Optional[str]
        }
    """
    logger.info(f"[{context}] Starting enhanced extraction, pages: {page_indexes}")
    
    # Stage 1: PDF-native extraction
    tables = extract_tables_from_pdf_native(pdf_bytes, page_indexes)
    valid_tables = [t for t in tables if _is_valid_rubric_table(t)]
    
    extraction_method = "pdf_native"
    raw_criteria = []
    
    if valid_tables:
        logger.info(f"[{context}] Found {len(valid_tables)} valid rubric tables via pdfplumber")
        for table in valid_tables:
            rows = table.get("rows", [])
            
            # Intelligently detect column roles for RTL Hebrew tables
            column_roles = _detect_column_roles(rows)
            desc_col = column_roles["description"]
            pts_col = column_roles["points"]
            
            logger.info(f"[{context}] Detected columns: description={desc_col}, points={pts_col}")
            
            for row_idx, row in enumerate(rows[1:], 1):
                if len(row) >= 2:
                    # Extract text from detected description column
                    description = row[desc_col] if desc_col < len(row) else row[-1]
                    # Extract points from detected points column
                    points = _extract_points(row, pts_col)
                    
                    # Skip rows with empty descriptions or only percentages
                    desc_text = str(description).strip() if description else ""
                    if len(desc_text) < 5 or re.match(r'^\d+(?:\.\d+)?%?$', desc_text):
                        continue
                    
                    raw_criteria.append({
                        "criterion_full_text": desc_text,
                        "points": points,
                        "row_index": row_idx
                    })
    else:
        # Stage 1b: VLM fallback
        logger.info(f"[{context}] No valid tables, falling back to VLM")
        extraction_method = "vlm_fallback"
        
        vlm_tables = await _extract_tables_vlm_fallback(images_b64, context)
        for table in vlm_tables:
            rows = table.get("rows", [])
            # For VLM fallback, use same column detection
            column_roles = _detect_column_roles(rows) if rows else {"description": 0, "points": 1, "percentage": -1}
            desc_col = column_roles["description"]
            pts_col = column_roles["points"]
            
            for row_idx, row in enumerate(rows):
                if len(row) >= 2:
                    description = row[desc_col] if desc_col < len(row) else row[-1]
                    points = _extract_points(row, pts_col)
                    
                    desc_text = str(description).strip() if description else ""
                    if len(desc_text) < 5 or re.match(r'^\d+(?:\.\d+)?%?$', desc_text):
                        continue
                    
                    raw_criteria.append({
                        "criterion_full_text": desc_text,
                        "points": points,
                        "row_index": row_idx
                    })
    
    if not raw_criteria:
        return {
            "criteria": [],
            "total_points": 0,
            "extraction_status": "failed",
            "extraction_method": extraction_method,
            "extraction_error": "לא נמצאו קריטריונים בעמודים"
        }
    
    total_points = sum(c.get("points", 0) for c in raw_criteria)
    logger.info(f"[{context}] Enhancing {len(raw_criteria)} criteria in parallel")
    
    # Stage 2: Enhance all criteria in PARALLEL
    enhancement_tasks = [
        enhance_criterion_with_rules(raw, total_points) 
        for raw in raw_criteria
    ]
    enhanced_results = await asyncio.gather(*enhancement_tasks, return_exceptions=True)
    
    # Stage 3: Validate and handle failures
    enhanced_criteria = []
    for idx, result in enumerate(enhanced_results):
        if isinstance(result, dict):
            fixed = validate_and_fix_enhanced_criterion(result)
            enhanced_criteria.append(fixed)
        elif isinstance(result, Exception):
            # Create fallback for any exception that slipped through
            logger.warning(f"[{context}] Criterion enhancement exception: {result}")
            if idx < len(raw_criteria):
                raw = raw_criteria[idx]
                fallback = _create_fallback_criterion(
                    raw.get("criterion_full_text", ""),
                    float(raw.get("points", 0))
                )
                enhanced_criteria.append(fallback)
    
    # Determine status based on confidence levels
    low_confidence_count = sum(1 for c in enhanced_criteria if c.get("extraction_confidence") == "low")
    
    if len(enhanced_criteria) == 0:
        status = "failed"
    elif low_confidence_count == len(enhanced_criteria):
        status = "partial"  # All fallbacks
    elif low_confidence_count > 0:
        status = "partial"  # Some fallbacks
    else:
        status = "success"
    
    return {
        "criteria": enhanced_criteria,
        "total_points": total_points,
        "extraction_status": status,
        "extraction_method": extraction_method,
        "extraction_error": None if status != "failed" else "שגיאה בהפקת כללי הורדה"
    }


# =============================================================================
# Question Text Extraction (kept for question text)
# =============================================================================


# =============================================================================
# Extraction Functions
# =============================================================================

def _clean_json_response(response: str) -> str:
    """Clean markdown formatting from JSON response (kept for backwards compat)."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


def _robust_json_parse(response: str, context: str = "") -> Dict[str, Any]:
    """
    Robustly parse JSON from VLM response, handling:
    - Markdown code blocks
    - Leading/trailing text
    - Truncated JSON
    - Multiple JSON objects
    
    Returns parsed dict or empty structure on failure.
    """
    import re
    
    if not response or not response.strip():
        logger.warning(f"Empty VLM response for {context}")
        return {"criteria": [], "total_points": 0, "_parse_error": "Empty response"}
    
    original = response
    
    # Try 1: Direct parse
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass
    
    # Try 2: Remove markdown code blocks
    cleaned = response.strip()
    if "```" in cleaned:
        # Extract content between ``` markers
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', cleaned)
        if match:
            cleaned = match.group(1).strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
    
    # Try 3: Find JSON object in response
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        json_str = cleaned[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix common issues
            fixed = json_str.replace("'", '"')
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    
    # Try 4: Find JSON array in response
    start = cleaned.find('[')
    end = cleaned.rfind(']')
    if start != -1 and end != -1 and end > start:
        json_str = cleaned[start:end+1]
        try:
            arr = json.loads(json_str)
            # If we got an array of criteria, wrap it
            if isinstance(arr, list) and len(arr) > 0:
                return {"criteria": arr, "total_points": sum(c.get("points", 0) for c in arr if isinstance(c, dict))}
        except json.JSONDecodeError:
            pass
    
    # All parsing attempts failed
    logger.error(f"JSON parsing failed for {context}. Response preview: {original[:200]}...")
    return {"criteria": [], "total_points": 0, "_parse_error": f"Could not parse: {original[:100]}..."}


# =============================================================================
# PDF-Native Question Text Extraction (NEW)
# =============================================================================

def extract_full_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extract full text from PDF using pdfplumber with RTL normalization.
    
    Returns all pages joined with page break markers for LLM context.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                raw_text = page.extract_text() or ""
                normalized = _normalize_rtl_text(raw_text)
                pages_text.append(normalized)
            return "\n\n---PAGE---\n\n".join(pages_text)
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        return ""


QUESTION_TEXT_EXTRACTION_PROMPT = """<role>
אתה מומחה בחילוץ טקסט שאלות ממבחנים בתכנות עבריים.
</role>

<task>
חלץ את טקסט השאלות המבוקשות מהטקסט. עבור כל מספר שאלה:
1. מצא את השאלה בטקסט
2. העתק את הטקסט המלא מילה במילה
3. זהה תת-שאלות (א, ב, ג...) אם קיימות
4. כלול דוגמאות קוד בדיוק כפי שהן
</task>

<critical_ignore>
התעלם לחלוטין מ:
🚫 טבלאות מחוון - טקסט עם נקודות (3.5, 2.25) ואחוזים (15%, 20%) לידו
🚫 שורות כמו: "רכיב הערכה | ניקוד | אחוז"
🚫 קריטריונים לניקוד כמו: "כותרת הפעולה וחתימה נכונה 1.5"
🚫 שדות מטא: שם תלמיד, שם מורה, זמן מבחן
🚫 כותרות/תחתיות עמודים
</critical_ignore>

<question_patterns>
זהה שאלות לפי:
- "שאלה X" או "שאלה X -"
- "X." או "X)" בתחילת שורה עם טקסט שאלה
- כותרת עם נקודות: "שאלה 2 - 35 נקודות"
</question_patterns>

<sub_question_patterns>
זהה תת-שאלות לפי:
- אותיות עבריות בתחילת שורה: א., ב., ג., ד., ה., ו., ז.
- "א)", "ב)", "ג)" או "א.", "ב.", "ג."
- תחילת פסקה חדשה עם אות עברית ונקודה
</sub_question_patterns>

<code_handling>
קוד מופיע בתוך שאלות. שמור אותו בדיוק:
- שמור רווחים ופורמט
- שמור typing כמו: int, double, bool, string
- שמור שמות מתודות כמו: House(), GetArea(), SetRooms()
</code_handling>

<output_format>
{
  "questions": [
    {
      "question_number": 1,
      "question_text": "טקסט השאלה המלא ללא תת-שאלות...",
      "sub_questions": [
        {"id": "א", "text": "טקסט תת-שאלה א..."},
        {"id": "ב", "text": "טקסט תת-שאלה ב..."}
      ]
    }
  ]
}
</output_format>"""


@traceable(name="extract_all_questions", run_type="llm")
async def extract_all_questions(
    pdf_text: str,
    question_numbers: List[int],
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Single LLM call to extract ALL question texts from PDF.
    
    Uses gpt-4o-mini for speed/cost with JSON mode.
    Includes retry logic with fallback to empty extraction.
    
    Args:
        pdf_text: Full PDF text extracted by pdfplumber
        question_numbers: List of question numbers to extract [1, 2, 3]
        max_retries: Number of retry attempts
    
    Returns:
        {
            "questions": [{"question_number": 1, "question_text": "...", "sub_questions": [...]}],
            "extraction_success": True/False,
            "failed_questions": []  # Question numbers that couldn't be extracted
        }
    """
    if not pdf_text or not question_numbers:
        return {
            "questions": [],
            "extraction_success": False,
            "failed_questions": question_numbers
        }
    
    # Build user message with explicit question numbers
    # Note: Must include 'json' keyword for response_format=json_object
    user_content = f"""שאלות לחילוץ: {question_numbers}

טקסט המסמך:
{pdf_text}

החזר תשובה בפורמט json בלבד."""
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            client = get_openai_client()
            
            # Use asyncio.to_thread to avoid blocking event loop
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {"role": "system", "content": QUESTION_TEXT_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                max_tokens=8000,  # Enough for multiple questions
                temperature=0.1
            )
            
            response_content = response.choices[0].message.content
            
            if not response_content:
                logger.warning(f"Empty question extraction response on attempt {attempt + 1}")
                continue
            
            # Extract JSON from response
            data = _extract_json_from_response(response_content)
            
            if not data or "questions" not in data:
                logger.warning(f"Invalid question extraction format on attempt {attempt + 1}")
                continue
            
            extracted_questions = data.get("questions", [])
            extracted_numbers = {q.get("question_number") for q in extracted_questions}
            failed_numbers = [n for n in question_numbers if n not in extracted_numbers]
            
            logger.info(f"Extracted {len(extracted_questions)} questions, failed: {failed_numbers}")
            
            return {
                "questions": extracted_questions,
                "extraction_success": len(failed_numbers) == 0,
                "failed_questions": failed_numbers
            }
            
        except Exception as e:
            last_error = e
            logger.warning(f"Question extraction attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
    
    # All retries failed - return empty with failure flag
    logger.error(f"Question extraction failed after {max_retries} attempts: {last_error}")
    return {
        "questions": [
            {"question_number": qn, "question_text": None, "sub_questions": [], "extraction_failed": True}
            for qn in question_numbers
        ],
        "extraction_success": False,
        "failed_questions": question_numbers
    }


# =============================================================================
# Legacy VLM Question Text Extraction (DEPRECATED)
# =============================================================================



def _extract_question_text(
    images_b64: List[str],
    question_number: int
) -> Dict[str, Any]:
    """
    Extract question text and sub-questions from images.
    
    Returns:
        {
            "question_text": "...",
            "has_sub_questions": bool,
            "sub_questions": [{"id": "א", "text": "..."}, ...]
        }
    """
    user_prompt = f"חלץ את טקסט שאלה {question_number} מהתמונה. החזר JSON בלבד."
    
    try:
        response = call_vision_llm(
            images_b64=images_b64,
            system_prompt=QUESTION_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.1
        )
        
        cleaned = _clean_json_response(response)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error for question {question_number}. Raw response: {response}")
            raise je
        
        return {
            "question_text": data.get("question_text", ""),
            "has_sub_questions": data.get("has_sub_questions", False),
            "sub_questions": data.get("sub_questions", [])
        }
        
    except Exception as e:
        logger.error(f"Error extracting question {question_number} text: {e}")
        return {
            "question_text": None,
            "has_sub_questions": False,
            "sub_questions": []
        }


# =============================================================================
# Main Extraction Function
# =============================================================================

@traceable(name="extract_rubric_with_page_mappings", run_type="chain")
async def extract_rubric_with_page_mappings(
    pdf_bytes: bytes,
    question_mappings: List[QuestionPageMapping],
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> ExtractRubricResponse:
    """
    Extract rubric from specific PDF pages based on user-defined mappings.
    
    Supports:
    - Questions with direct criteria (no sub-questions)
    - Questions with sub-questions (א, ב, ג...), each having their own criteria table
    
    Args:
        pdf_bytes: The PDF file as bytes
        question_mappings: List of QuestionPageMapping objects
        name: Optional rubric name
        description: Optional description
            
    Returns:
        ExtractRubricResponse with extracted questions for teacher review
    """
    logger.info(f"Extracting rubric with {len(question_mappings)} question mappings")
    
    # Convert PDF to images once (for criteria extraction)
    all_images = pdf_to_images(pdf_bytes, dpi=150)
    logger.info(f"PDF has {len(all_images)} pages")
    
    # Pre-convert all images to base64
    all_images_b64 = [image_to_base64(img) for img in all_images]
    
    # --- NEW: PDF-native question text extraction ---
    # Extract full PDF text once
    full_pdf_text = extract_full_pdf_text(pdf_bytes)
    logger.info(f"Extracted {len(full_pdf_text)} chars of text from PDF")
    
    # Extract all question texts in a single LLM call
    question_numbers = [m.question_number for m in question_mappings]
    questions_data = await extract_all_questions(full_pdf_text, question_numbers)
    
    # Build lookup for quick access: {question_number: question_data}
    questions_lookup: Dict[int, Dict] = {}
    for q in questions_data.get("questions", []):
        qn = q.get("question_number")
        if qn:
            questions_lookup[qn] = q
    
    logger.info(f"Extracted question texts for: {list(questions_lookup.keys())}")
    
    extracted_questions: List[ExtractedQuestion] = []
    
    for mapping in question_mappings:
        q_num = mapping.question_number
        logger.info(f"Processing Question {q_num}")
        
        # Get question data from LLM extraction
        question_data = questions_lookup.get(q_num, {})
        question_text = question_data.get("question_text")
        llm_sub_questions = question_data.get("sub_questions", [])
        extraction_failed = question_data.get("extraction_failed", False)
        
        # --- Step 2: Handle based on structure ---
        
        if mapping.sub_questions:
            # Question HAS sub-questions - extract criteria for each
            extracted_sub_questions: List[ExtractedSubQuestion] = []
            
            for sq_mapping in mapping.sub_questions:
                sq_id = sq_mapping.sub_question_id
                logger.info(f"Q{q_num} sub-question {sq_id}: extracting criteria from pages {sq_mapping.criteria_page_indexes}")
                
                # Get sub-question text from the question extraction (if available)
                sq_text = None
                for sq in question_data.get("sub_questions", []):
                    if sq.get("id") == sq_id:
                        sq_text = sq.get("text")
                        break
                
                # Extract criteria for this sub-question using new 3-stage pipeline
                criteria_images_b64 = [
                    all_images_b64[idx]
                    for idx in sq_mapping.criteria_page_indexes
                    if 0 <= idx < len(all_images_b64)
                ]
                
                criteria_data = {"criteria": [], "total_points": 0, "extraction_status": "failed", "extraction_error": None}
                if criteria_images_b64:
                    context = f"שאלה {q_num} סעיף {sq_id}"
                    criteria_data = await extract_criteria_enhanced(
                        pdf_bytes=pdf_bytes,
                        images_b64=criteria_images_b64,
                        page_indexes=sq_mapping.criteria_page_indexes,
                        context=context
                    )
                    logger.info(f"Q{q_num}-{sq_id}: extracted {len(criteria_data['criteria'])} criteria")
                
                # Build EnhancedCriterion objects from pipeline response
                enhanced_criteria = []
                for c in criteria_data.get("criteria", []):
                    enhanced_criteria.append(EnhancedCriterion(
                        criterion_description=c.get("criterion_description", ""),
                        total_points=c.get("total_points", 0),
                        reduction_rules=[ReductionRule(**r) for r in c.get("reduction_rules", [])],
                        notes=c.get("notes"),
                        raw_text=c.get("raw_text"),
                        extraction_confidence=c.get("extraction_confidence", "high")
                    ))
                
                extracted_sub_questions.append(ExtractedSubQuestion(
                    sub_question_id=sq_id,
                    sub_question_text=sq_text,
                    criteria=enhanced_criteria,
                    total_points=criteria_data.get("total_points", 0),
                    source_pages=sq_mapping.criteria_page_indexes,
                    extraction_status=criteria_data.get("extraction_status", "success"),
                    extraction_error=criteria_data.get("extraction_error")
                ))
            
            # Create question with sub-questions
            # Determine overall extraction status from sub-questions
            sub_statuses = [sq.extraction_status for sq in extracted_sub_questions]
            if all(s == "success" for s in sub_statuses):
                overall_status = "success"
            elif any(s == "failed" for s in sub_statuses):
                overall_status = "partial" if any(s == "success" for s in sub_statuses) else "failed"
            else:
                overall_status = "partial"
            
            total_pts = sum(sq.total_points for sq in extracted_sub_questions)
            extracted_questions.append(ExtractedQuestion(
                question_number=q_num,
                question_text=question_text,
                total_points=total_pts,
                criteria=[],  # No direct criteria
                sub_questions=extracted_sub_questions,
                source_pages=mapping.criteria_page_indexes,
                extraction_status=overall_status,
                extraction_error=None if overall_status == "success" else "חלק מהסעיפים לא חולצו בהצלחה"
            ))
            
        else:
            # Question has NO sub-questions - extract criteria directly using 3-stage pipeline
            logger.info(f"Q{q_num}: extracting direct criteria from pages {mapping.criteria_page_indexes}")
            
            criteria_images_b64 = [
                all_images_b64[idx]
                for idx in mapping.criteria_page_indexes
                if 0 <= idx < len(all_images_b64)
            ]
            
            criteria_data = {"criteria": [], "total_points": 0, "extraction_status": "failed", "extraction_error": None}
            if criteria_images_b64:
                context = f"שאלה {q_num}"
                criteria_data = await extract_criteria_enhanced(
                    pdf_bytes=pdf_bytes,
                    images_b64=criteria_images_b64,
                    page_indexes=mapping.criteria_page_indexes,
                    context=context
                )
                logger.info(f"Q{q_num}: extracted {len(criteria_data['criteria'])} criteria")
            
            # Build EnhancedCriterion objects from pipeline response
            enhanced_criteria = []
            for c in criteria_data.get("criteria", []):
                enhanced_criteria.append(EnhancedCriterion(
                    criterion_description=c.get("criterion_description", ""),
                    total_points=c.get("total_points", 0),
                    reduction_rules=[ReductionRule(**r) for r in c.get("reduction_rules", [])],
                    notes=c.get("notes"),
                    raw_text=c.get("raw_text"),
                    extraction_confidence=c.get("extraction_confidence", "high")
                ))
            
            extracted_questions.append(ExtractedQuestion(
                question_number=q_num,
                question_text=question_text,
                total_points=criteria_data.get("total_points", 0),
                criteria=enhanced_criteria,
                sub_questions=[],
                source_pages=mapping.criteria_page_indexes,
                extraction_status=criteria_data.get("extraction_status", "success"),
                extraction_error=criteria_data.get("extraction_error")
            ))
    
    # Build response
    response = ExtractRubricResponse(
        questions=extracted_questions,
        name=name,
        description=description
    )
    
    logger.info(
        f"Extraction complete: {response.num_questions} questions, "
        f"{response.num_sub_questions} sub-questions, "
        f"{response.num_criteria} criteria, "
        f"{response.total_points} total points"
    )
    
    return response


# =============================================================================
# Database Operations
# =============================================================================

def _convert_criterion_to_dict(criterion) -> Dict[str, Any]:
    """
    Convert a criterion (EnhancedCriterion or CriterionSchema) to dict format.
    
    Handles both old format (description/points) and new format 
    (criterion_description/total_points/reduction_rules).
    """
    # Try new EnhancedCriterion format first
    if hasattr(criterion, 'criterion_description'):
        result = {
            "criterion_description": criterion.criterion_description,
            "total_points": criterion.total_points,
            # Preserve backward compatibility
            "description": criterion.criterion_description,
            "points": criterion.total_points,
        }
        
        # Include reduction_rules if present
        if hasattr(criterion, 'reduction_rules') and criterion.reduction_rules:
            result["reduction_rules"] = [
                {
                    "description": r.description,
                    "reduction_value": r.reduction_value,
                    "is_explicit": r.is_explicit
                }
                for r in criterion.reduction_rules
            ]
        
        # Include optional fields
        if hasattr(criterion, 'notes') and criterion.notes:
            result["notes"] = criterion.notes
        if hasattr(criterion, 'raw_text') and criterion.raw_text:
            result["raw_text"] = criterion.raw_text
        if hasattr(criterion, 'extraction_confidence'):
            result["extraction_confidence"] = criterion.extraction_confidence
        
        return result
    
    # Fall back to old CriterionSchema format
    return {
        "description": criterion.description,
        "points": criterion.points,
        # For grading compatibility
        "criterion_description": criterion.description,
        "total_points": criterion.points,
    }

async def save_rubric(
    db: AsyncSession,
    request: SaveRubricRequest,
) -> Rubric:
    """
    Save a reviewed/edited rubric to the database.
    
    Converts ExtractedQuestion format to storage format.
    """
    # Convert to storage format
    questions_json = []
    total_points = 0
    
    for q in request.questions:
        q_data = {
            "question_number": q.question_number,
            "question_text": q.question_text,
            "total_points": q.total_points,
        }
        
        if q.sub_questions:
            q_data["sub_questions"] = [
                {
                    "sub_question_id": sq.sub_question_id,
                    "sub_question_text": sq.sub_question_text,
                    "total_points": sq.total_points,
                    "criteria": [
                        _convert_criterion_to_dict(c)
                        for c in sq.criteria
                    ]
                }
                for sq in q.sub_questions
            ]
            q_data["criteria"] = []
        else:
            q_data["criteria"] = [
                _convert_criterion_to_dict(c)
                for c in q.criteria
            ]
            q_data["sub_questions"] = []
        
        total_points += q.total_points
        questions_json.append(q_data)
    
    rubric_json = {"questions": questions_json}
    
    rubric = Rubric(
        rubric_json=rubric_json,
        name=request.name,
        description=request.description,
        total_points=total_points,
    )
    
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    
    logger.info(f"Saved rubric with ID: {rubric.id}, {len(questions_json)} questions, {total_points} points")
    return rubric


async def get_rubric_by_id(db: AsyncSession, rubric_id: UUID) -> Optional[Rubric]:
    """Retrieve a rubric from the database by ID."""
    result = await db.execute(
        select(Rubric).where(Rubric.id == rubric_id)
    )
    return result.scalar_one_or_none()


async def list_rubrics(db: AsyncSession, limit: int = 50) -> List[Rubric]:
    """List all rubrics, most recent first."""
    result = await db.execute(
        select(Rubric).order_by(Rubric.created_at.desc()).limit(limit)
    )
    return result.scalars().all()