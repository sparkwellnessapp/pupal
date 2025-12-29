"""
Grading service layer.

Handles test grading and database operations for graded tests.
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.grading import GradedTest, Rubric
from ..schemas.grading import AnswerPageMapping
from .document_parser import StudentTestParser
from .grading_agent import GradingAgent

logger = logging.getLogger(__name__)

# Singleton grading agent instance
_grading_agent: Optional[GradingAgent] = None


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize objects for JSON serialization.
    Ensures non-standard objects (like OpenAI Usage) are converted to strings.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


def get_grading_agent() -> GradingAgent:
    """Get or create the grading agent singleton."""
    global _grading_agent
    if _grading_agent is None:
        _grading_agent = GradingAgent()
    return _grading_agent


async def parse_student_test_with_mappings(
    pdf_bytes: bytes,
    filename: str,
    answer_mappings: List[AnswerPageMapping],
    first_page_index: int = 0,
) -> Dict[str, Any]:
    """
    Parse a student test PDF using Vision AI with page mappings.
    
    Args:
        pdf_bytes: The PDF file as bytes
        filename: Original filename for fallback student name extraction
        answer_mappings: List of AnswerPageMapping defining which pages contain which answers
        first_page_index: Page index containing student name (usually 0)
        
    Returns:
        Parsed student test with transcribed answers:
        {
            "student_name": "...",
            "filename": "...",
            "answers": [
                {
                    "question_number": 1,
                    "sub_question_id": None,
                    "answer_text": "code..."
                },
                ...
            ]
        }
    """
    logger.info(f"Parsing student test with mappings: {filename}")
    
    # Convert Pydantic models to dicts
    mappings_dict = [
        {
            "question_number": m.question_number,
            "sub_question_id": m.sub_question_id,
            "page_indexes": m.page_indexes,
        }
        for m in answer_mappings
    ]
    
    return StudentTestParser.parse_student_test_with_mappings(
        pdf_bytes=pdf_bytes,
        filename=filename,
        answer_mappings=mappings_dict,
        first_page_index=first_page_index,
    )


async def parse_student_test(pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Parse a student test PDF using Vision AI (legacy, no mappings).
    
    Args:
        pdf_bytes: The PDF file as bytes
        filename: Original filename for student name extraction
        
    Returns:
        Parsed student test with transcribed answers
    """
    logger.info(f"Parsing student test (legacy): {filename}")
    return StudentTestParser.parse_student_test(pdf_bytes, filename)


async def grade_student_test(
    rubric: Dict[str, Any],
    student_test: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Grade a student test against a rubric.
    
    Args:
        rubric: The rubric JSON structure
        student_test: The parsed student test with answers
        
    Returns:
        Grading results dictionary
    """
    logger.info(f"Grading test for student: {student_test.get('student_name')}")
    
    agent = get_grading_agent()
    results = agent.grade_tests(
        rubric=rubric,
        student_tests=[student_test],
        teacher_email="api@grader.local",  # Placeholder for API usage
        original_message_id="api-request",
    )
    
    if results.get("graded_results"):
        return results["graded_results"][0]
    
    raise ValueError("Grading failed: no results returned")


async def grade_student_tests_batch(
    rubric: Dict[str, Any],
    student_tests: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Grade multiple student tests against a rubric.
    
    Args:
        rubric: The rubric JSON structure
        student_tests: List of parsed student tests with answers
        
    Returns:
        Batch grading results
    """
    logger.info(f"Batch grading {len(student_tests)} tests")
    
    agent = get_grading_agent()
    results = agent.grade_tests(
        rubric=rubric,
        student_tests=student_tests,
        teacher_email="api@grader.local",
        original_message_id="api-batch-request",
    )
    
    return results


async def save_graded_test(
    db: AsyncSession,
    rubric_id: UUID,
    grading_result: Dict[str, Any],
    student_answers: Optional[Dict[str, Any]] = None,
) -> GradedTest:
    """
    Save a graded test to the database.
    
    Args:
        db: Database session
        rubric_id: ID of the rubric used for grading
        grading_result: The full grading result dictionary
        student_answers: The parsed student answers (code transcriptions)
        
    Returns:
        The created GradedTest model instance
    """
    # Sanitize data to ensure it's valid JSON for database
    sanitized_result = sanitize_for_json(grading_result)
    sanitized_answers = sanitize_for_json(student_answers) if student_answers else None
    
    graded_test = GradedTest(
        rubric_id=rubric_id,
        student_name=sanitized_result.get("student_name", "Unknown"),
        filename=sanitized_result.get("filename"),
        graded_json=sanitized_result,
        total_score=sanitized_result.get("total_score", 0),
        total_possible=sanitized_result.get("total_possible", 0),
        percentage=sanitized_result.get("percentage", 0),
        student_answers_json=sanitized_answers,
    )
    
    db.add(graded_test)
    await db.commit()
    await db.refresh(graded_test)
    
    logger.info(f"Saved graded test with ID: {graded_test.id}")
    return graded_test


async def get_graded_test_by_id(db: AsyncSession, graded_test_id: UUID) -> Optional[GradedTest]:
    """
    Retrieve a graded test from the database by ID.
    
    Args:
        db: Database session
        graded_test_id: The graded test's UUID
        
    Returns:
        The GradedTest model instance, or None if not found
    """
    result = await db.execute(
        select(GradedTest).where(GradedTest.id == graded_test_id)
    )
    return result.scalar_one_or_none()


async def get_graded_tests_by_rubric_id(
    db: AsyncSession,
    rubric_id: UUID,
) -> List[GradedTest]:
    """
    Retrieve all graded tests for a given rubric.
    
    Args:
        db: Database session
        rubric_id: The rubric's UUID
        
    Returns:
        List of GradedTest model instances
    """
    result = await db.execute(
        select(GradedTest)
        .where(GradedTest.rubric_id == rubric_id)
        .order_by(GradedTest.created_at.desc())
    )
    return list(result.scalars().all())