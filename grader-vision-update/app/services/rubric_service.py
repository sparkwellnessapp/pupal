"""
Rubric service layer.

Handles rubric extraction from PDFs with support for:
- Questions with direct criteria
- Questions with sub-questions (א, ב, ג...), each having their own criteria
"""
import logging
import json
from typing import Optional, Dict, Any, List
from uuid import UUID

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
from .document_parser import pdf_to_images, image_to_base64, call_vision_llm

logger = logging.getLogger(__name__)


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

CRITERIA_EXTRACTION_SYSTEM_PROMPT = """אתה מומחה בחילוץ קריטריוני הערכה מטבלאות מחוונים.
משימתך: לחלץ את כל קריטריוני ההערכה וערכי הנקודות שלהם מהתמונה.

הוראות:
1. חלץ כל קריטריון בדיוק כפי שמופיע בטבלה
2. חלץ את מספר הנקודות לכל קריטריון
3. אם יש מספר עמודות נקודות (כמו "מלא" ו"חלקי"), השתמש בערך המקסימלי
4. שמור על הטקסט העברי במדויק

פורמט פלט (JSON בלבד, ללא markdown):
{
  "total_points": 40,
  "criteria": [
    {"description": "תיאור הקריטריון בעברית", "points": 5},
    {"description": "קריטריון נוסף", "points": 10}
  ]
}

חלץ את כל הקריטריונים. אל תדלג על אף אחד."""


# =============================================================================
# Extraction Functions
# =============================================================================

def _clean_json_response(response: str) -> str:
    """Clean markdown formatting from JSON response."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


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
        data = json.loads(cleaned)
        
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


def _extract_criteria(
    images_b64: List[str],
    context: str  # e.g., "שאלה 1" or "שאלה 2 סעיף א"
) -> Dict[str, Any]:
    """
    Extract criteria from rubric table images.
    
    Returns:
        {
            "total_points": float,
            "criteria": [{"description": "...", "points": float}, ...]
        }
    """
    user_prompt = f"חלץ את כל קריטריוני ההערכה עבור {context} מטבלת המחוון. החזר JSON בלבד."
    
    try:
        response = call_vision_llm(
            images_b64=images_b64,
            system_prompt=CRITERIA_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=3000,
            temperature=0.1
        )
        
        cleaned = _clean_json_response(response)
        data = json.loads(cleaned)
        
        criteria = data.get("criteria", [])
        total_points = data.get("total_points") or sum(c.get("points", 0) for c in criteria)
        
        return {
            "total_points": total_points,
            "criteria": criteria
        }
        
    except Exception as e:
        logger.error(f"Error extracting criteria for {context}: {e}")
        return {
            "total_points": 0,
            "criteria": []
        }


# =============================================================================
# Main Extraction Function
# =============================================================================

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
                    source_pages=sq_mapping.criteria_page_indexes
                ))
            
            # Create question with sub-questions
            total_pts = sum(sq.total_points for sq in extracted_sub_questions)
            extracted_questions.append(ExtractedQuestion(
                question_number=q_num,
                question_text=question_data.get("question_text"),
                total_points=total_pts,
                criteria=[],  # No direct criteria
                sub_questions=extracted_sub_questions,
                source_pages=mapping.question_page_indexes
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
                source_pages=mapping.question_page_indexes + mapping.criteria_page_indexes
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