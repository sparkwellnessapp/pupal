"""
Rubric generator service.

AI-powered rubric generation from exam PDFs:
1. Detect question boundaries from PDF text
2. Generate criteria with reduction rules for each question
3. Support per-question regeneration

Uses streaming for real-time feedback during question detection.
"""
import logging
import json
import re
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from app.tracing import trace_if_enabled

from .rubric_service import (
    extract_full_pdf_text,
    enhance_criterion_with_rules,
    validate_and_fix_enhanced_criterion,
    _extract_json_from_response,
    get_openai_client,
    get_language_prompt_context,
)
from ..schemas.grading import (
    ExtractedQuestion,
    ExtractedSubQuestion,
    EnhancedCriterion,
    ReductionRule,
    LegacyExtractRubricResponse,
)

logger = logging.getLogger(__name__)

from ..config import settings


# =============================================================================
# Data Models
# =============================================================================

class DetectedQuestion(BaseModel):
    """A question detected from the PDF."""
    question_number: int
    question_text: str
    page_indexes: List[int] = Field(default_factory=list)
    sub_questions: List[str] = Field(default_factory=list)  # ["א", "ב", "ג"]
    suggested_points: Optional[float] = None
    teacher_points: Optional[float] = None


@dataclass
class DetectionEvent:
    """Event emitted during question detection stream."""
    type: str  # "progress", "question", "complete", "error"
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    event_id: int = 0


class GenerateCriteriaRequest(BaseModel):
    """Request for criteria generation."""
    questions: List[DetectedQuestion]
    rubric_name: Optional[str] = None
    rubric_description: Optional[str] = None


class RegenerateQuestionRequest(BaseModel):
    """Request to regenerate criteria for a single question."""
    question_number: int
    question_text: str
    sub_questions: List[str] = Field(default_factory=list)
    total_points: float


# =============================================================================
# Question Detection
# =============================================================================

QUESTION_DETECTION_PROMPT = """<role>
אתה מומחה בזיהוי מבנה מבחנים בעברית במדעי המחשב.
</role>

<task>
נתח את הטקסט וזהה את כל השאלות במבחן.
עבור כל שאלה, חלץ:
1. מספר השאלה
2. טקסט השאלה המלא (כולל קוד אם קיים)
3. תת-שאלות (סעיפים) אם קיימות (א, ב, ג וכו')
4. הערכת ניקוד מומלצת לפי המורכבות
</task>

<question_patterns>
זהה שאלות לפי:
- "שאלה X" או "שאלה X -" או "שאלה X:"
- "X." בתחילת שורה עם טקסט שאלה
- כותרת עם נקודות: "שאלה 2 (35 נקודות)"
</question_patterns>

<sub_question_patterns>
זהה תת-שאלות לפי:
- "א.", "ב.", "ג." וכו' בתחילת שורה
- "א)", "ב)", "ג)" וכו'
- כותרות סעיפים עם ניקוד: "א. (10 נקודות)"
</sub_question_patterns>

<points_estimation>
הערך את הניקוד לפי:
- שאלת קוד פשוטה (פונקציה אחת): 10-15 נקודות
- שאלת קוד בינונית (מספר פונקציות/מחלקה): 20-30 נקודות
- שאלת קוד מורכבת (אלגוריתם/רקורסיה/OOP): 30-45 נקודות
- שאלה תיאורטית קצרה: 5-10 נקודות
</points_estimation>

<critical_ignore>
התעלם לחלוטין מ:
🚫 טבלאות מחוון/ניקוד (שורות עם "רכיב הערכה", "ניקוד", "%")
🚫 כותרות עמודים, שם מורה, שם תלמיד
🚫 הוראות כלליות על המבחן
</critical_ignore>

<output_format>
{
  "questions": [
    {
      "question_number": 1,
      "question_text": "טקסט השאלה המלא כולל קוד...",
      "sub_questions": ["א", "ב"],
      "suggested_points": 30,
      "page_hint": "נמצא בעמודים 1-2"
    }
  ],
  "total_estimated_points": 100
}
</output_format>"""


@trace_if_enabled(
    "rubric_generator_service_detect_questions_from_pdf_trace",
    name="detect_questions_from_pdf",
)
async def detect_questions_from_pdf(
    pdf_bytes: bytes,
    max_retries: int = 2,
) -> List[DetectedQuestion]:
    """
    Detect all questions from a PDF.
    
    Uses pdfplumber for text extraction + GPT-4o for intelligent parsing.
    
    Args:
        pdf_bytes: The PDF file content
        max_retries: Number of retry attempts
        
    Returns:
        List of detected questions
    """
    # Extract text from PDF
    pdf_text = extract_full_pdf_text(pdf_bytes)
    
    if not pdf_text or len(pdf_text.strip()) < 50:
        logger.warning("PDF text extraction returned very little text")
        return []
    
    logger.info(f"Extracted {len(pdf_text)} chars from PDF for question detection")
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            client = get_openai_client()
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat.completions.create,
                    model=settings.rubric_generation_model,
                    messages=[
                        {"role": "system", "content": QUESTION_DETECTION_PROMPT},
                        {"role": "user", "content": f"טקסט המבחן:\n\n{pdf_text}\n\nהחזר JSON בלבד."}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=8000,
                    temperature=0.1,
                ),
                timeout=settings.rubric_llm_timeout_seconds,
            )
            
            content = response.choices[0].message.content
            if not content:
                logger.warning(f"Empty response on attempt {attempt + 1}")
                continue
            
            data = _extract_json_from_response(content)
            if not data or "questions" not in data:
                logger.warning(f"Invalid response format on attempt {attempt + 1}")
                continue
            
            questions = []
            for q in data.get("questions", []):
                # Parse page hint into indexes if present
                page_indexes = []
                page_hint = q.get("page_hint", "")
                if page_hint:
                    # Extract numbers from "עמודים 1-2" or similar
                    numbers = re.findall(r'\d+', page_hint)
                    page_indexes = [int(n) - 1 for n in numbers]  # Convert to 0-indexed
                
                questions.append(DetectedQuestion(
                    question_number=q.get("question_number", 0),
                    question_text=q.get("question_text", ""),
                    page_indexes=page_indexes,
                    sub_questions=q.get("sub_questions", []),
                    suggested_points=q.get("suggested_points"),
                ))
            
            logger.info(f"Detected {len(questions)} questions from PDF")
            return questions
            
        except Exception as e:
            last_error = e
            logger.warning(f"Question detection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
    
    logger.error(f"Question detection failed after {max_retries} attempts: {last_error}")
    return []


async def detect_questions_stream(
    pdf_bytes: bytes,
) -> AsyncGenerator[DetectionEvent, None]:
    """
    Stream question detection events for real-time UI updates.
    
    Yields events:
    - {"type": "progress", "message": "..."}
    - {"type": "question", "data": {...}}
    - {"type": "complete", "data": {"total_questions": N}}
    - {"type": "error", "message": "..."}
    """
    event_id = 0
    
    # Progress: Starting
    event_id += 1
    yield DetectionEvent(
        type="progress",
        message="מחלץ טקסט מהמסמך...",
        event_id=event_id,
    )
    
    try:
        # Extract text
        pdf_text = extract_full_pdf_text(pdf_bytes)
        
        if not pdf_text or len(pdf_text.strip()) < 50:
            event_id += 1
            yield DetectionEvent(
                type="error",
                message="לא הצלחנו לחלץ טקסט מהמסמך. ודא שזהו קובץ PDF תקין עם טקסט.",
                event_id=event_id,
            )
            return
        
        event_id += 1
        yield DetectionEvent(
            type="progress",
            message="מזהה שאלות במסמך...",
            event_id=event_id,
        )
        
        # Detect questions using AI
        questions = await detect_questions_from_pdf(pdf_bytes)
        
        if not questions:
            event_id += 1
            yield DetectionEvent(
                type="progress",
                message="לא זוהו שאלות אוטומטית. ניתן להוסיף שאלות ידנית.",
                event_id=event_id,
            )
        
        # Yield each question
        for question in questions:
            event_id += 1
            yield DetectionEvent(
                type="question",
                data=question.dict(),
                event_id=event_id,
            )
            # Small delay between questions for UI effect
            await asyncio.sleep(0.1)
        
        # Complete
        event_id += 1
        yield DetectionEvent(
            type="complete",
            data={
                "total_questions": len(questions),
                "questions": [q.dict() for q in questions],
            },
            event_id=event_id,
        )
        
    except Exception as e:
        logger.error(f"Question detection stream error: {e}", exc_info=True)
        event_id += 1
        yield DetectionEvent(
            type="error",
            message=f"שגיאה בזיהוי שאלות: {str(e)}",
            event_id=event_id,
        )


# =============================================================================
# Criteria Generation
# =============================================================================

RUBRIC_GENERATION_PROMPT = """<role>
אתה פרופסור ומומחה עולמי להוראת מדעי המחשב עם 25 שנות ניסיון ביצירת מחוונים.
התמחותך היא ביצירת קריטריונים מדויקים וכללי הורדת נקודות ספציפיים.
</role>

<task>
צור מחוון הערכה מקצועי עבור השאלה הבאה.

עבור כל קריטריון:
1. תאר מה נבדק בבהירות ובקצרה
2. הקצה ניקוד מתאים (סה"כ חייב להיות בדיוק {total_points} נקודות)
3. פרק לכללי הורדת נקודות ספציפיים שמורה יכול לזהות בקוד

כללי הכרחיים:
- סכום כל ה-total_points של הקריטריונים = {total_points} בדיוק
- סכום כל ה-reduction_rules בכל קריטריון = total_points של אותו קריטריון
- כל כלל הורדה חייב להיות ספציפי ובר-זיהוי בקוד
- אסור "טעות כללית", "שגיאה אחרת", "בעיה נוספת"
</task>

<error_taxonomy>
טקסונומיית שגיאות נפוצות לפי נושא:

| נושא | שגיאות נפוצות |
|------|---------------|
| חתימת מתודה | שם שגוי, סוג מוחזר שגוי, פרמטרים (מספר/סוג/סדר), חסר static, חסר public |
| לולאות | משתנה לולאה, תנאי עצירה, קידום, off-by-one |
| מערכים | גודל שגוי, אינדקס מחוץ לתחום, אתחול |
| תנאים | תנאי שגוי, חסר else, סדר תנאים |
| OOP | בנאי שגוי, חסר new, null reference |
| ערכים | return שגוי, אתחול חסר, סוג משתנה |
</error_taxonomy>

<output_schema>
{{
  "criteria": [
    {{
      "criterion_description": "תיאור הקריטריון",
      "total_points": 5.0,
      "reduction_rules": [
        {{"description": "שגיאה ספציפית", "reduction_value": 2.0, "is_explicit": false}}
      ]
    }}
  ]
}}
</output_schema>

<examples>
דוגמה - שאלה על לולאה ומערך (20 נקודות):
{{
  "criteria": [
    {{
      "criterion_description": "חתימת הפעולה נכונה",
      "total_points": 4,
      "reduction_rules": [
        {{"description": "שם הפעולה שגוי", "reduction_value": 1, "is_explicit": false}},
        {{"description": "סוג מוחזר שגוי", "reduction_value": 1.5, "is_explicit": false}},
        {{"description": "פרמטרים שגויים (מספר/סוג)", "reduction_value": 1.5, "is_explicit": false}}
      ]
    }},
    {{
      "criterion_description": "לולאה נכונה על המערך",
      "total_points": 8,
      "reduction_rules": [
        {{"description": "תנאי עצירה שגוי (i<n vs i<=n-1)", "reduction_value": 3, "is_explicit": false}},
        {{"description": "אתחול משתנה הלולאה שגוי", "reduction_value": 2, "is_explicit": false}},
        {{"description": "קידום משתנה הלולאה שגוי", "reduction_value": 3, "is_explicit": false}}
      ]
    }},
    {{
      "criterion_description": "לוגיקת החישוב נכונה",
      "total_points": 8,
      "reduction_rules": [
        {{"description": "אתחול מונה/סכום שגוי", "reduction_value": 2, "is_explicit": false}},
        {{"description": "תנאי הבדיקה שגוי", "reduction_value": 3, "is_explicit": false}},
        {{"description": "ערך מוחזר שגוי", "reduction_value": 3, "is_explicit": false}}
      ]
    }}
  ]
}}
✓ סכום: 4+8+8=20
</examples>"""


@trace_if_enabled(
    "rubric_generator_service_generate_criteria_for_question_trace",
    name="generate_criteria_for_question",
)
async def generate_criteria_for_question(
    question: DetectedQuestion,
    total_points: float,
    subject_context: Optional[str] = None,
    programming_language: Optional[str] = None,
    max_retries: int = 3,
) -> ExtractedQuestion:
    """
    Generate criteria + reduction rules for a single question.
    
    Args:
        question: The detected question with text
        total_points: Total points for this question
        subject_context: Optional subject description
        programming_language: Optional programming language for context
        max_retries: Number of retry attempts
        
    Returns:
        ExtractedQuestion with generated criteria
    """
    if not question.question_text:
        logger.warning(f"Empty question text for question {question.question_number}")
        return _create_fallback_question(question, total_points)
    
    prompt = RUBRIC_GENERATION_PROMPT.format(total_points=total_points)
    
    # Format sub-questions info if present
    sub_q_info = ""
    if question.sub_questions:
        sub_q_info = f"\nתת-שאלות: {', '.join(question.sub_questions)}"
    
    # Add subject context if provided
    context_info = ""
    if subject_context:
        context_info = f"\nנושא המבחן: {subject_context}"
    
    # Add programming language context if provided
    language_context = get_language_prompt_context(programming_language)
    
    user_content = f"""שאלה {question.question_number}:{sub_q_info}{context_info}
{language_context}
{question.question_text}

סה"כ נקודות: {total_points}

החזר JSON בלבד."""
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            client = get_openai_client()
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat.completions.create,
                    model=settings.rubric_generation_model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=4000,
                    temperature=0.15,
                ),
                timeout=settings.rubric_llm_timeout_seconds,
            )
            
            content = response.choices[0].message.content
            if not content:
                logger.warning(f"Empty response for Q{question.question_number} attempt {attempt + 1}")
                continue
            
            data = _extract_json_from_response(content)
            if not data or "criteria" not in data:
                logger.warning(f"Invalid response format for Q{question.question_number}")
                continue
            
            # Build enhanced criteria
            enhanced_criteria = []
            for c in data.get("criteria", []):
                criterion_dict = {
                    "criterion_description": c.get("criterion_description", ""),
                    "total_points": c.get("total_points", 0),
                    "reduction_rules": c.get("reduction_rules", []),
                    "notes": None,
                    "raw_text": None,
                    "extraction_confidence": "high",
                }
                # Validate and fix
                fixed = validate_and_fix_enhanced_criterion(criterion_dict)
                
                enhanced_criteria.append(EnhancedCriterion(
                    criterion_description=fixed["criterion_description"],
                    total_points=fixed["total_points"],
                    reduction_rules=[ReductionRule(**r) for r in fixed["reduction_rules"]],
                    notes=fixed.get("notes"),
                    raw_text=fixed.get("raw_text"),
                    extraction_confidence=fixed.get("extraction_confidence", "high"),
                ))
            
            # Handle sub-questions
            if question.sub_questions:
                # Distribute criteria among sub-questions
                return _distribute_criteria_to_subquestions(
                    question, enhanced_criteria, total_points
                )
            
            actual_total = sum(c.total_points for c in enhanced_criteria)
            
            return ExtractedQuestion(
                question_number=question.question_number,
                question_text=question.question_text,
                total_points=actual_total,
                criteria=enhanced_criteria,
                sub_questions=[],
                source_pages=question.page_indexes,
                extraction_status="success",
            )
            
        except Exception as e:
            last_error = e
            logger.warning(f"Criteria generation for Q{question.question_number} attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    
    logger.error(f"Criteria generation failed for Q{question.question_number}: {last_error}")
    return _create_fallback_question(question, total_points)


def _create_fallback_question(question: DetectedQuestion, total_points: float) -> ExtractedQuestion:
    """Create a basic question structure when generation fails."""
    return ExtractedQuestion(
        question_number=question.question_number,
        question_text=question.question_text,
        total_points=total_points,
        criteria=[
            EnhancedCriterion(
                criterion_description="קריטריון כללי - יש לערוך",
                total_points=total_points,
                reduction_rules=[
                    ReductionRule(
                        description="טעות בפתרון",
                        reduction_value=total_points,
                        is_explicit=False,
                    )
                ],
                notes="לא הצלחנו ליצור קריטריונים אוטומטית - יש לערוך ידנית",
                extraction_confidence="low",
            )
        ],
        sub_questions=[],
        source_pages=question.page_indexes,
        extraction_status="partial",
        extraction_error="נוצר קריטריון כללי - יש לערוך",
    )


def _distribute_criteria_to_subquestions(
    question: DetectedQuestion,
    criteria: List[EnhancedCriterion],
    total_points: float,
) -> ExtractedQuestion:
    """Distribute generated criteria among sub-questions."""
    num_subs = len(question.sub_questions)
    if num_subs == 0:
        return ExtractedQuestion(
            question_number=question.question_number,
            question_text=question.question_text,
            total_points=total_points,
            criteria=criteria,
            sub_questions=[],
            source_pages=question.page_indexes,
            extraction_status="success",
        )
    
    # Split criteria roughly evenly among sub-questions
    criteria_per_sub = max(1, len(criteria) // num_subs)
    
    sub_questions = []
    criteria_index = 0
    
    for i, sub_id in enumerate(question.sub_questions):
        # Last sub-question gets remaining criteria
        if i == num_subs - 1:
            sub_criteria = criteria[criteria_index:]
        else:
            sub_criteria = criteria[criteria_index:criteria_index + criteria_per_sub]
            criteria_index += criteria_per_sub
        
        sub_total = sum(c.total_points for c in sub_criteria)
        
        sub_questions.append(ExtractedSubQuestion(
            sub_question_id=sub_id,
            sub_question_text=None,  # Could extract from question text
            criteria=sub_criteria,
            total_points=sub_total,
            source_pages=question.page_indexes,
            extraction_status="success",
        ))
    
    return ExtractedQuestion(
        question_number=question.question_number,
        question_text=question.question_text,
        total_points=sum(sq.total_points for sq in sub_questions),
        criteria=[],  # No direct criteria when using sub-questions
        sub_questions=sub_questions,
        source_pages=question.page_indexes,
        extraction_status="success",
    )


# =============================================================================
# Main Generation Functions
# =============================================================================

@trace_if_enabled(
    "rubric_generator_service_generate_full_rubric_trace",
    name="generate_full_rubric",
)
async def generate_full_rubric(
    questions: List[DetectedQuestion],
    rubric_name: Optional[str] = None,
    rubric_description: Optional[str] = None,
    programming_language: Optional[str] = None,
) -> LegacyExtractRubricResponse:
    """
    Generate complete rubric from detected questions.
    
    Generates criteria for all questions in parallel for speed.
    
    Args:
        questions: List of detected questions with points set
        rubric_name: Optional name for the rubric
        rubric_description: Optional description
        programming_language: Optional programming language for context
        
    Returns:
        LegacyExtractRubricResponse ready for RubricEditor display
    """
    if not questions:
        return LegacyExtractRubricResponse(
            questions=[],
            name=rubric_name,
            description=rubric_description,
            programming_language=programming_language,
        )
    
    logger.info(f"Generating rubric with {len(questions)} questions")
    
    # Generate all questions in parallel
    tasks = [
        generate_criteria_for_question(
            question=q,
            total_points=q.teacher_points or q.suggested_points or 10,
            subject_context=rubric_description,
            programming_language=programming_language,
        )
        for q in questions
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    extracted_questions = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Failed to generate Q{questions[i].question_number}: {result}")
            # Use fallback
            extracted_questions.append(_create_fallback_question(
                questions[i],
                questions[i].teacher_points or questions[i].suggested_points or 10,
            ))
        else:
            extracted_questions.append(result)
    
    response = LegacyExtractRubricResponse(
        questions=extracted_questions,
        name=rubric_name,
        description=rubric_description,
        programming_language=programming_language,
    )
    
    logger.info(f"Generated rubric: {response.num_questions} questions, {response.num_criteria} criteria, {response.total_points} points")
    
    return response


async def regenerate_single_question(
    question_number: int,
    question_text: str,
    sub_questions: List[str],
    total_points: float,
    programming_language: Optional[str] = None,
) -> ExtractedQuestion:
    """
    Regenerate criteria for a single question.
    
    Used when teacher clicks "refresh" on one question.
    
    Args:
        question_number: Question number
        question_text: Full question text
        sub_questions: List of sub-question IDs
        total_points: Total points for the question
        programming_language: Optional programming language for context
        
    Returns:
        New ExtractedQuestion with regenerated criteria
    """
    detected = DetectedQuestion(
        question_number=question_number,
        question_text=question_text,
        sub_questions=sub_questions,
    )
    
    return await generate_criteria_for_question(
        detected, 
        total_points,
        programming_language=programming_language,
    )
