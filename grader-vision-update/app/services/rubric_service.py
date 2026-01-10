"""
Rubric service layer.

Handles rubric extraction from PDFs with support for:
- Questions with direct criteria
- Questions with sub-questions (א, ב, ג...), each having their own criteria

World-class features:
- Structured JSON output with OpenAI JSON mode
- Pydantic validation layer for type safety
- Retry mechanism with escalating prompts
- Multi-strategy JSON parsing fallback
"""
import logging
import json
import re
import hashlib
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.grading import Rubric
from ..schemas.grading import (
    QuestionPageMapping,
    SubQuestionPageMapping,
    ExtractedQuestion,
    ExtractedSubQuestion,
    ExtractedCriterion,
    ExtractRubricResponse,
    SaveRubricRequest,
)
from .document_parser import pdf_to_images, image_to_base64, call_vision_llm, get_openai_client

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Validation Models for VLM Output
# =============================================================================

class CriterionOutput(BaseModel):
    """Validated criterion from VLM extraction."""
    description: str = Field(..., min_length=1, description="Criterion description in Hebrew")
    points: float = Field(..., ge=0, le=200, description="Points for this criterion")


class CriteriaExtractionOutput(BaseModel):
    """Validated output from criteria extraction VLM call."""
    total_points: float = Field(0, ge=0, description="Total points (can be 0 if criteria sum is used)")
    criteria: List[CriterionOutput] = Field(default_factory=list, description="List of extracted criteria")

    def compute_total(self) -> float:
        """Compute total from criteria if not provided."""
        return self.total_points or sum(c.points for c in self.criteria)


# =============================================================================
# Semantic Caching for Criteria Extraction
# =============================================================================

# In-memory cache for criteria extraction results (keyed by image hash)
# In production, consider using Redis for persistence across restarts
_criteria_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_MAX_SIZE = 100  # Prevent unbounded memory growth


def _hash_images(images_b64: List[str]) -> str:
    """Create stable hash for image content."""
    combined = "".join(images_b64)
    return hashlib.sha256(combined.encode()).hexdigest()[:24]


def _get_cached_criteria(images_b64: List[str]) -> Optional[Dict[str, Any]]:
    """Check if criteria for these images are already cached."""
    cache_key = _hash_images(images_b64)
    if cache_key in _criteria_cache:
        logger.info(f"Cache HIT for criteria extraction (key={cache_key[:8]}...)")
        return _criteria_cache[cache_key]
    return None


def _cache_criteria(images_b64: List[str], result: Dict[str, Any]) -> None:
    """Cache successful criteria extraction result."""
    # Only cache successful extractions
    if result.get("extraction_status") != "success":
        return
    
    cache_key = _hash_images(images_b64)
    
    # Evict oldest entries if cache is full
    if len(_criteria_cache) >= _CACHE_MAX_SIZE:
        oldest_key = next(iter(_criteria_cache))
        del _criteria_cache[oldest_key]
        logger.debug(f"Evicted cache entry {oldest_key[:8]}...")
    
    _criteria_cache[cache_key] = result
    logger.info(f"Cached criteria extraction (key={cache_key[:8]}..., {len(result.get('criteria', []))} criteria)")


# =============================================================================
# Vision AI Prompts
# =============================================================================

QUESTION_EXTRACTION_SYSTEM_PROMPT = """אתה מומחה בחילוץ שאלות ממבחנים בתכנות.
משימתך: לחלץ את טקסט השאלה מהתמונה.

הוראות:
1. חלץ את טקסט השאלה המלא
2. אם יש תת-שאלות (א, ב, ג...), חלץ גם אותן
3. כלול קוד לדוגמה אם מופיע כחלק מהשאלה
4. שמור על הפורמט המקורי

פורמט פלט (JSON בלבד, ללא markdown):
{
  "question_text": "הטקסט המלא של השאלה הראשית",
  "has_sub_questions": true/false,
  "sub_questions": [
    {"id": "א", "text": "טקסט תת-שאלה א"},
    {"id": "ב", "text": "טקסט תת-שאלה ב"}
  ]
}

אם אין תת-שאלות, החזר רשימה ריקה עבור sub_questions."""

CRITERIA_EXTRACTION_SYSTEM_PROMPT = """אתה מומחה בחילוץ קריטריוני הערכה מטבלאות מחוונים למבחנים בתכנות.

=== דוגמה 1: טבלת קריטריונים פשוטה ===
[תמונה של טבלה עם שלושה קריטריונים]

פלט נכון:
{
  "total_points": 25,
  "criteria": [
    {"description": "הגדרת משתנים פרטיים (private)", "points": 5},
    {"description": "בנאי עם שני פרמטרים", "points": 10},
    {"description": "מתודת toString() מוחזרת כראוי", "points": 10}
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
    {"description": "לולאת for נכונה", "points": 8},
    {"description": "תנאי עצירה", "points": 7}
  ]
}

=== דוגמה 3: רשימת קריטריונים ללא טבלה ===
[תמונה עם רשימה:]
• הגדרת מערך - 5 נק'
• מילוי המערך בלולאה - 10 נק'
• הדפסת התוצאה - 5 נק'

פלט נכון:
{
  "total_points": 20,
  "criteria": [
    {"description": "הגדרת מערך", "points": 5},
    {"description": "מילוי המערך בלולאה", "points": 10},
    {"description": "הדפסת התוצאה", "points": 5}
  ]
}

=== הוראות ===
1. חלץ כל קריטריון בדיוק כפי שמופיע (טבלה, רשימה, או כל פורמט אחר)
2. חלץ את מספר הנקודות לכל קריטריון
3. אם יש עמודות "מלא" ו"חלקי", השתמש בערך המקסימלי ("מלא")
4. שמור על הטקסט העברי במדויק - אל תתרגם או תשנה
5. אם אין קריטריונים גלויים, החזר criteria ריק

פורמט פלט חובה (JSON בלבד):
{
  "total_points": <סכום כל הנקודות>,
  "criteria": [
    {"description": "<תיאור מדויק>", "points": <מספר>},
    ...
  ]
}

חשוב: החזר אך ורק JSON. אל תוסיף הסברים, markdown, או טקסט אחר."""


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


@traceable(name="extract_criteria_structured", run_type="llm")
def _extract_criteria_structured(
    images_b64: List[str],
    context: str,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    Extract criteria using OpenAI's JSON mode for guaranteed valid JSON.
    
    This is the primary extraction strategy - uses response_format=json_object
    which guarantees the response is valid JSON.
    """
    try:
        client = get_openai_client()
        
        # Build content with images
        content = [
            {
                "type": "image_url", 
                "image_url": {
                    "url": f"data:image/png;base64,{img}", 
                    "detail": "high"
                }
            } 
            for img in images_b64
        ]
        content.append({
            "type": "text", 
            "text": f"חלץ את כל קריטריוני ההערכה עבור {context} מטבלת המחוון."
        })
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": CRITERIA_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ],
            response_format={"type": "json_object"},  # Guaranteed JSON!
            max_tokens=4000,
            temperature=temperature
        )
        
        raw_json = response.choices[0].message.content
        
        # Pydantic validation for type safety
        try:
            validated = CriteriaExtractionOutput.model_validate_json(raw_json)
            return {
                "criteria": [c.model_dump() for c in validated.criteria],
                "total_points": validated.compute_total(),
                "extraction_status": "success" if validated.criteria else "partial",
                "extraction_error": None if validated.criteria else "לא נמצאו קריטריונים בטבלה"
            }
        except ValidationError as e:
            logger.warning(f"Pydantic validation failed for {context}: {e}")
            # Fall back to robust parsing
            return None
            
    except Exception as e:
        logger.warning(f"Structured extraction failed for {context}: {e}")
        return None


@traceable(name="extract_criteria", run_type="chain")
def _extract_criteria(
    images_b64: List[str],
    context: str,  # e.g., "שאלה 1" or "שאלה 2 סעיף א"
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Extract criteria from rubric table images with retry mechanism.
    
    World-class features:
    - Semantic caching (avoids redundant API calls for identical images)
    - LangSmith tracing (full observability)
    - Two-tier extraction (JSON mode → fallback parsing)
    - Pydantic validation
    - Retry with escalation
    
    Returns:
        {
            "total_points": float,
            "criteria": [{"description": "...", "points": float}, ...],
            "extraction_status": "success" | "partial" | "failed",
            "extraction_error": Optional[str]
        }
    """
    # Check cache first
    cached = _get_cached_criteria(images_b64)
    if cached:
        return cached
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            temperature = 0.1 if attempt == 0 else 0.05
            
            logger.info(f"Extracting criteria for {context} (attempt {attempt + 1}/{max_retries + 1})")
            
            # Tier 1: Try structured extraction with JSON mode
            result = _extract_criteria_structured(images_b64, context, temperature)
            if result and result.get("criteria"):
                logger.info(f"Structured extraction successful: {len(result['criteria'])} criteria for {context}")
                _cache_criteria(images_b64, result)  # Cache successful result
                return result
            
            # Tier 2: Fallback to generic VLM + robust parsing
            if attempt == 0:
                user_prompt = f"חלץ את כל קריטריוני ההערכה עבור {context} מטבלת המחוון. החזר JSON בלבד."
            else:
                # Retry with more explicit instructions
                user_prompt = f"""חלץ קריטריונים עבור {context}.

חובה להחזיר JSON בפורמט הבא ללא טקסט נוסף:
{{
  "total_points": <מספר>,
  "criteria": [
    {{"description": "<תיאור הקריטריון>", "points": <נקודות>}},
    ...
  ]
}}

אם אתה רואה טבלה עם קריטריונים, חלץ כל שורה. אם אין טבלה, החזר criteria ריק."""
            
            response = call_vision_llm(
                images_b64=images_b64,
                system_prompt=CRITERIA_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=4000,
                temperature=temperature
            )
            
            # Use robust parser
            data = _robust_json_parse(response, context)
            
            # Try Pydantic validation on parsed data
            try:
                validated = CriteriaExtractionOutput.model_validate(data)
                if validated.criteria:
                    logger.info(f"Fallback extraction successful: {len(validated.criteria)} criteria for {context}")
                    result = {
                        "total_points": validated.compute_total(),
                        "criteria": [c.model_dump() for c in validated.criteria],
                        "extraction_status": "success",
                        "extraction_error": None
                    }
                    _cache_criteria(images_b64, result)  # Cache successful result
                    return result
            except ValidationError as ve:
                logger.warning(f"Validation failed for {context}: {ve}")
            
            # Raw criteria without validation (last resort)
            criteria = data.get("criteria", [])
            parse_error = data.get("_parse_error")
            
            if criteria:
                total_points = data.get("total_points") or sum(c.get("points", 0) for c in criteria)
                logger.info(f"Unvalidated extraction: {len(criteria)} criteria for {context}")
                return {
                    "total_points": total_points,
                    "criteria": criteria,
                    "extraction_status": "partial",  # Mark as partial since not validated
                    "extraction_error": None
                }
            
            # No criteria found
            if parse_error:
                last_error = parse_error
                logger.warning(f"Attempt {attempt + 1} for {context}: parse error - {parse_error}")
            else:
                last_error = "לא נמצאו קריטריונים בעמוד"
                logger.warning(f"Attempt {attempt + 1} for {context}: VLM returned empty criteria")
            
        except Exception as e:
            last_error = str(e)
            logger.error(f"Attempt {attempt + 1} for {context} failed: {e}")
    
    # All retries exhausted
    logger.error(f"All {max_retries + 1} attempts failed for {context}")
    return {
        "total_points": 0,
        "criteria": [],
        "extraction_status": "failed",
        "extraction_error": f"לא הצלחנו לחלץ קריטריונים ({last_error}). נסה לסמן עמודים אחרים או הוסף ידנית."
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
    
    # Convert PDF to images once
    all_images = pdf_to_images(pdf_bytes, dpi=150)
    logger.info(f"PDF has {len(all_images)} pages")
    
    # Pre-convert all images to base64
    all_images_b64 = [image_to_base64(img) for img in all_images]
    
    extracted_questions: List[ExtractedQuestion] = []
    
    for mapping in question_mappings:
        q_num = mapping.question_number
        logger.info(f"Processing Question {q_num}")
        
        # --- Step 1: Extract question text ---
        question_images_b64 = [
            all_images_b64[idx] 
            for idx in mapping.question_page_indexes 
            if 0 <= idx < len(all_images_b64)
        ]
        
        question_data = {"question_text": None, "sub_questions": []}
        if question_images_b64:
            question_data = _extract_question_text(question_images_b64, q_num)
            logger.info(f"Q{q_num}: extracted question text, has_sub_questions={question_data.get('has_sub_questions')}")
        
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
                
                # Extract criteria for this sub-question
                criteria_images_b64 = [
                    all_images_b64[idx]
                    for idx in sq_mapping.criteria_page_indexes
                    if 0 <= idx < len(all_images_b64)
                ]
                
                criteria_data = {"criteria": [], "total_points": 0}
                if criteria_images_b64:
                    context = f"שאלה {q_num} סעיף {sq_id}"
                    criteria_data = _extract_criteria(criteria_images_b64, context)
                    logger.info(f"Q{q_num}-{sq_id}: extracted {len(criteria_data['criteria'])} criteria")
                
                extracted_sub_questions.append(ExtractedSubQuestion(
                    sub_question_id=sq_id,
                    sub_question_text=sq_text,
                    criteria=[
                        ExtractedCriterion(
                            description=c.get("description", ""),
                            points=c.get("points", 0),
                            extraction_confidence="high"
                        )
                        for c in criteria_data.get("criteria", [])
                    ],
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
                question_text=question_data.get("question_text"),
                total_points=total_pts,
                criteria=[],  # No direct criteria
                sub_questions=extracted_sub_questions,
                source_pages=mapping.question_page_indexes,
                extraction_status=overall_status,
                extraction_error=None if overall_status == "success" else "חלק מהסעיפים לא חולצו בהצלחה"
            ))
            
        else:
            # Question has NO sub-questions - extract criteria directly
            logger.info(f"Q{q_num}: extracting direct criteria from pages {mapping.criteria_page_indexes}")
            
            criteria_images_b64 = [
                all_images_b64[idx]
                for idx in mapping.criteria_page_indexes
                if 0 <= idx < len(all_images_b64)
            ]
            
            criteria_data = {"criteria": [], "total_points": 0}
            if criteria_images_b64:
                context = f"שאלה {q_num}"
                criteria_data = _extract_criteria(criteria_images_b64, context)
                logger.info(f"Q{q_num}: extracted {len(criteria_data['criteria'])} criteria")
            
            extracted_questions.append(ExtractedQuestion(
                question_number=q_num,
                question_text=question_data.get("question_text"),
                total_points=criteria_data.get("total_points", 0),
                criteria=[
                    ExtractedCriterion(
                        description=c.get("description", ""),
                        points=c.get("points", 0),
                        extraction_confidence="high"
                    )
                    for c in criteria_data.get("criteria", [])
                ],
                sub_questions=[],
                source_pages=mapping.question_page_indexes + mapping.criteria_page_indexes,
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
                        {"description": c.description, "points": c.points}
                        for c in sq.criteria
                    ]
                }
                for sq in q.sub_questions
            ]
            q_data["criteria"] = []
        else:
            q_data["criteria"] = [
                {"description": c.description, "points": c.points}
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