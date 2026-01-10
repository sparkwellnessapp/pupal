"""
VLM Extraction Layer for Rubric Parsing

This module provides Vision Language Model (VLM) based extraction of rubric content.
It's the "Layer B" in the hybrid extraction architecture.

Key optimizations:
- DPI 200 for better text recognition (especially small red text in tables)
- JSON mode for reliable structured output (no markdown-trapped strings)
- Specialized prompts for Hebrew CS rubrics
- Caching for repeated extractions

Location: app/services/vlm_rubric_extractor.py
"""
import io
import json
import base64
import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from PIL import Image
from pdf2image import convert_from_bytes
from openai import OpenAI
from langsmith import traceable

from ..config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class VLMConfig:
    """Configuration for VLM extraction."""
    
    # Image settings - DPI 200 is sweet spot for accuracy vs cost
    DPI = 200
    MAX_IMAGE_SIZE = 2000  # Max dimension before resize
    
    # Model settings
    MODEL = "gpt-4o"
    MAX_TOKENS = 4000
    TEMPERATURE = 0.1
    
    # Cache settings
    CACHE_MAX_SIZE = 100


# =============================================================================
# Robust JSON Parsing (fallback for edge cases)
# =============================================================================

def _robust_json_parse(response: str, context: str = "") -> Dict[str, Any]:
    """
    Robustly parse JSON from VLM response, handling:
    - Markdown code blocks
    - Leading/trailing text
    - Truncated JSON
    - Multiple JSON objects
    
    This is a fallback for when JSON mode still produces malformed output.
    
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
# Data Classes
# =============================================================================

@dataclass
class VLMCriterion:
    """A criterion extracted by VLM."""
    description: str
    points: float
    section_number: Optional[int] = None
    deduction_rules: List[str] = field(default_factory=list)


@dataclass
class VLMCriteriaResult:
    """Result of VLM criteria extraction."""
    criteria: List[VLMCriterion] = field(default_factory=list)
    total_points: float = 0
    extraction_status: str = "success"
    error: Optional[str] = None
    
    @property
    def criteria_count(self) -> int:
        return len(self.criteria)
    
    def to_dict_list(self) -> List[Dict]:
        """Convert criteria to list of dicts for fusion."""
        return [
            {
                "description": c.description,
                "points": c.points,
                "section_number": c.section_number,
                "deduction_rules": c.deduction_rules,
                "source": "vlm"
            }
            for c in self.criteria
        ]


@dataclass
class VLMQuestionResult:
    """Result of VLM question text extraction."""
    question_number: int
    question_text: Optional[str] = None
    total_points: Optional[float] = None
    has_sub_questions: bool = False
    sub_questions: List[Dict[str, str]] = field(default_factory=list)
    extraction_status: str = "success"
    error: Optional[str] = None


# =============================================================================
# Prompts
# =============================================================================

CRITERIA_EXTRACTION_SYSTEM_PROMPT = """אתה מומחה בחילוץ קריטריוני הערכה מטבלאות מחוונים למבחנים בתכנות.

=== דוגמה 1: טבלת קריטריונים פשוטה ===
[תמונה של טבלה עם שלושה קריטריונים]

פלט נכון:
{
  "total_points": 25,
  "criteria": [
    {"section_number": 1, "description": "הגדרת משתנים פרטיים (private)", "points": 5, "deduction_rules": []},
    {"section_number": 2, "description": "בנאי עם שני פרמטרים", "points": 10, "deduction_rules": []},
    {"section_number": 3, "description": "מתודת toString() מוחזרת כראוי", "points": 10, "deduction_rules": []}
  ]
}

=== דוגמה 2: טבלה עם עמודות מלא/חלקי ===
[תמונה של טבלה עם עמודות "מלא" ו"חלקי"]

| קריטריון | מלא | חלקי |
|----------|-----|------|
| לולאת for נכונה | 8 | 4 |
| תנאי עצירה | 7 | 3 |

פלט נכון (השתמש בערך "מלא"):
{
  "total_points": 15,
  "criteria": [
    {"section_number": 1, "description": "לולאת for נכונה", "points": 8, "deduction_rules": []},
    {"section_number": 2, "description": "תנאי עצירה", "points": 7, "deduction_rules": []}
  ]
}

=== דוגמה 3: טבלה עם כללי הורדה ===
[תמונה של טבלה עם "להוריד" שורות]

פלט נכון:
{
  "total_points": 15,
  "criteria": [
    {
      "section_number": 1, 
      "description": "כותרת הפעולה וחתימה נכונה", 
      "points": 1.5,
      "deduction_rules": ["אם שכחו static להוריד 0.5"]
    }
  ]
}

=== מבנה טיפוסי של טבלת מחוון ===
הטבלה מכילה:
- עמודת "רכיב הערכה" (תיאור הקריטריון) - בצד ימין
- עמודת "ניקוד" (נקודות) - באמצע
- עמודת אחוזים (%) - בצד שמאל (אופציונלי)

=== סוגי שורות ===
1. **קריטריון ראשי** - יש לו מספר סעיף (-1, -2, וכו') ונקודות
2. **כלל הורדה** - מכיל את המילה "להוריד" וקשור לקריטריון שמעליו
3. **שורת סיכום** - מכילה "סה"כ" - אל תכלול ברשימת הקריטריונים

=== הוראות חשובות ===
1. חלץ את התיאור המלא - אל תקצר
2. שמור על מספר הסעיף: -1 הופך ל-1, -2 ל-2, וכו'
3. קבץ כללי הורדה (שורות עם "להוריד") תחת הקריטריון הרלוונטי כ-deduction_rules
4. אל תכלול שורות כותרת או סיכום ברשימת הקריטריונים
5. התעלם מהערות בשוליים (Commented [...])
6. קרא בדיוק את מספרי הנקודות - אל תנחש!
7. אם יש עמודות "מלא" ו"חלקי", השתמש בערך המקסימלי ("מלא")

=== פורמט פלט (JSON בלבד) ===
{
  "criteria": [
    {
      "section_number": 1,
      "description": "תיאור מלא של הקריטריון",
      "points": 5.25,
      "deduction_rules": ["אם שכחו X להוריד Y"]
    }
  ],
  "total_points": 35
}

חשוב: החזר אך ורק JSON. אל תוסיף הסברים, markdown, או טקסט אחר."""


QUESTION_EXTRACTION_SYSTEM_PROMPT = """אתה מומחה בחילוץ טקסט שאלות ממבחנים בתכנות.

=== משימה ===
חלץ את טקסט השאלה המלא מהתמונה.

=== מה לחלץ ===
1. כותרת השאלה (שאלה X - Y נקודות)
2. הוראות השאלה המלאות
3. תת-שאלות (א, ב, ג, ד, ה, ו, ז) - אם קיימות
4. דוגמאות קוד או פלט - אם מופיעים

=== הוראות ===
1. שמור על הטקסט המקורי - אל תתרגם או תשנה
2. כלול קוד לדוגמה אם מופיע
3. אם אין תת-שאלות, החזר רשימה ריקה
4. חלץ רק את השאלה המבוקשת, לא שאלות אחרות

=== פורמט פלט (JSON בלבד) ===
{
  "question_number": 1,
  "total_points": 15,
  "question_text": "הטקסט המלא של השאלה הראשית...",
  "has_sub_questions": true,
  "sub_questions": [
    {"id": "א", "text": "טקסט תת-שאלה א"},
    {"id": "ב", "text": "טקסט תת-שאלה ב"}
  ]
}"""


# =============================================================================
# VLM Rubric Extractor
# =============================================================================

class VLMRubricExtractor:
    """
    Extracts rubric content using Vision Language Model.
    
    Optimized for:
    - Full description extraction (PDF often truncates)
    - Complex table layout understanding
    - Deduction rules extraction
    - Sub-question structure detection
    
    Usage:
        extractor = VLMRubricExtractor(client)
        result = extractor.extract_criteria(images_b64, "שאלה 1")
    """
    
    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize VLM extractor.
        
        Args:
            client: OpenAI client instance (will create if not provided)
        """
        self._client = client
        self._cache: Dict[str, Any] = {}
    
    @property
    def client(self) -> OpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            from ..config import settings
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client
    
    @traceable(name="vlm_extract_criteria", run_type="llm")
    def extract_criteria(
        self,
        images_b64: List[str],
        context: str = "",
        max_retries: int = 2
    ) -> VLMCriteriaResult:
        """
        Extract criteria from table images using VLM.
        
        Args:
            images_b64: Base64-encoded page images
            context: Additional context (e.g., "שאלה 2")
            max_retries: Number of retries on failure
            
        Returns:
            VLMCriteriaResult with extracted criteria
        """
        # Check cache
        cache_key = self._cache_key(images_b64, "criteria")
        if cache_key in self._cache:
            logger.debug(f"VLM cache hit for criteria extraction")
            return self._cache[cache_key]
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            # Use different prompt on retry
            if attempt == 0:
                user_prompt = f"חלץ את כל קריטריוני ההערכה מטבלת המחוון."
                if context:
                    user_prompt += f" הקשר: {context}"
            else:
                # More explicit prompt on retry
                user_prompt = f"""חלץ קריטריונים עבור {context if context else 'השאלה'}.

חובה להחזיר JSON בפורמט הבא:
{{
  "total_points": <מספר>,
  "criteria": [
    {{"description": "<תיאור הקריטריון>", "points": <נקודות>, "section_number": <מספר>}},
    ...
  ]
}}

אם אתה רואה טבלה עם קריטריונים, חלץ כל שורה. אם אין טבלה, החזר criteria ריק."""
            
            try:
                logger.info(f"Extracting criteria for {context} (attempt {attempt + 1}/{max_retries + 1})")
                
                response = self._call_vlm_json(
                    images_b64=images_b64,
                    system_prompt=CRITERIA_EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt
                )
                
                result = self._parse_criteria_response(response)
                
                # Cache successful result
                if result.extraction_status == "success" and result.criteria:
                    self._cache_result(cache_key, result)
                    logger.info(f"Extracted {len(result.criteria)} criteria for {context}")
                    return result
                
                # If no criteria found, try again
                if not result.criteria:
                    last_error = "לא נמצאו קריטריונים"
                    logger.warning(f"Attempt {attempt + 1}: no criteria found for {context}")
                    continue
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt + 1} failed for {context}: {e}")
        
        # All retries exhausted
        logger.error(f"All {max_retries + 1} attempts failed for {context}")
        return VLMCriteriaResult(
            extraction_status="failed",
            error=f"לא הצלחנו לחלץ קריטריונים ({last_error})"
        )
    
    @traceable(name="vlm_extract_question", run_type="llm")
    def extract_question_text(
        self,
        images_b64: List[str],
        question_number: int
    ) -> VLMQuestionResult:
        """
        Extract question text and sub-questions using VLM.
        
        Args:
            images_b64: Base64-encoded page images
            question_number: Question number to extract
            
        Returns:
            VLMQuestionResult with extracted content
        """
        user_prompt = f"חלץ את טקסט שאלה {question_number} מהתמונה."
        
        try:
            response = self._call_vlm_json(
                images_b64=images_b64,
                system_prompt=QUESTION_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=3000
            )
            
            return self._parse_question_response(response, question_number)
            
        except Exception as e:
            logger.error(f"VLM question extraction failed: {e}")
            return VLMQuestionResult(
                question_number=question_number,
                extraction_status="failed",
                error=str(e)
            )
    
    def _call_vlm_json(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = VLMConfig.MAX_TOKENS
    ) -> Dict[str, Any]:
        """
        Call VLM with JSON mode enabled.
        
        This uses response_format={"type": "json_object"} to prevent
        markdown-trapped strings that break parsing.
        """
        # Build content array with images first
        content = []
        
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high"
                }
            })
        
        # Add text prompt after images
        content.append({
            "type": "text",
            "text": user_prompt
        })
        
        logger.info(f"Calling VLM with {len(images_b64)} images (JSON mode)")
        
        response = self.client.chat.completions.create(
            model=VLMConfig.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=max_tokens,
            temperature=VLMConfig.TEMPERATURE,
            response_format={"type": "json_object"}  # KEY: Ensures valid JSON
        )
        
        result_text = response.choices[0].message.content
        logger.info(f"VLM response: {len(result_text)} chars")
        
        # Parse JSON (should always work with json_object mode, but use robust parser as fallback)
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return _robust_json_parse(result_text, "VLM response")
    
    def _parse_criteria_response(self, data: Dict) -> VLMCriteriaResult:
        """Parse criteria extraction response."""
        criteria = []
        
        for c in data.get("criteria", []):
            criteria.append(VLMCriterion(
                description=c.get("description", ""),
                points=float(c.get("points", 0)),
                section_number=c.get("section_number"),
                deduction_rules=c.get("deduction_rules", [])
            ))
        
        return VLMCriteriaResult(
            criteria=criteria,
            total_points=float(data.get("total_points", 0)),
            extraction_status="success"
        )
    
    def _parse_question_response(
        self, 
        data: Dict, 
        question_number: int
    ) -> VLMQuestionResult:
        """Parse question extraction response."""
        return VLMQuestionResult(
            question_number=data.get("question_number", question_number),
            question_text=data.get("question_text"),
            total_points=data.get("total_points"),
            has_sub_questions=data.get("has_sub_questions", False),
            sub_questions=data.get("sub_questions", []),
            extraction_status="success"
        )
    
    def _cache_key(self, images_b64: List[str], prefix: str) -> str:
        """Generate cache key for images."""
        content = prefix + "".join(img[:100] for img in images_b64)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _cache_result(self, key: str, result: Any) -> None:
        """Cache extraction result with LRU eviction."""
        if len(self._cache) >= VLMConfig.CACHE_MAX_SIZE:
            # Remove oldest entry
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        
        self._cache[key] = result
        logger.debug(f"Cached VLM result (key={key[:8]}...)")


# =============================================================================
# Image Utilities
# =============================================================================

def pdf_to_images_optimized(
    pdf_bytes: bytes,
    dpi: int = VLMConfig.DPI
) -> List[Image.Image]:
    """
    Convert PDF to images at optimized DPI.
    
    Uses DPI 200 by default (sweet spot for accuracy vs token cost).
    
    Args:
        pdf_bytes: PDF file content
        dpi: Resolution (200 recommended for rubrics)
        
    Returns:
        List of PIL Images
    """
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            fmt='PNG'
        )
        logger.info(f"Converted PDF to {len(images)} images at {dpi} DPI")
        return images
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise


def image_to_base64_optimized(
    image: Image.Image,
    max_size: int = VLMConfig.MAX_IMAGE_SIZE
) -> str:
    """
    Convert PIL Image to base64, resizing if needed.
    
    Args:
        image: PIL Image
        max_size: Maximum dimension
        
    Returns:
        Base64-encoded PNG string
    """
    # Resize if too large
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        logger.debug(f"Resized image to {new_size}")
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    
    return base64.standard_b64encode(buffer.read()).decode('utf-8')


def prepare_images_for_vlm(
    pdf_bytes: bytes,
    page_indexes: Optional[List[int]] = None,
    dpi: int = VLMConfig.DPI
) -> List[str]:
    """
    Prepare PDF pages as base64 images for VLM.
    
    Args:
        pdf_bytes: PDF file content
        page_indexes: Specific pages to convert (None = all)
        dpi: Resolution for conversion
        
    Returns:
        List of base64-encoded images
    """
    images = pdf_to_images_optimized(pdf_bytes, dpi)
    
    if page_indexes:
        images = [images[i] for i in page_indexes if i < len(images)]
    
    return [image_to_base64_optimized(img) for img in images]