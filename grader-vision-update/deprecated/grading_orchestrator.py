"""
Grading Orchestrator - Coordinates the grading workflow and email sending.
VISION-COMPATIBLE VERSION: Works with Vision AI document parsing.
"""
import logging
from typing import Dict, List, Tuple, Optional
from io import BytesIO

from .grading_agent import GradingAgent
from .pdf_annotator import PDFAnnotator, generate_email_body
from .gmail_handler import GmailHandler
from .config import settings

logger = logging.getLogger(__name__)


class GradingOrchestrator:
    """Orchestrates the full grading workflow."""
    
    def __init__(self, gmail_handler: GmailHandler):
        """
        Initialize the orchestrator.
        
        Args:
            gmail_handler: Configured Gmail handler for sending emails
        """
        self.gmail = gmail_handler
        self.grading_agent = GradingAgent()
        self.pdf_annotator = PDFAnnotator()
    
    def process_grading_request(
        self,
        rubric: Dict,
        student_tests: List[Dict],
        original_pdfs: Dict[str, bytes],
        teacher_email: str,
        original_message_id: str
    ) -> str:
        """
        Process a full grading request.
        
        Args:
            rubric: Parsed rubric dictionary (from Vision AI)
            student_tests: List of student test data with transcribed answers
            original_pdfs: Dictionary mapping filenames to original PDF bytes
            teacher_email: Email address to send results to
            original_message_id: Original email message ID for threading
            
        Returns:
            Sent message ID
        """
        logger.info("=" * 80)
        logger.info("STARTING GRADING ORCHESTRATION (Vision Pipeline)")
        logger.info("=" * 80)
        logger.info(f"Students: {len(student_tests)}")
        logger.info(f"Teacher: {teacher_email}")
        
        # Calculate rubric total for accurate scoring
        rubric_total = sum(q.get('total_points', 0) for q in rubric.get('questions', []))
        logger.info(f"📊 Total possible points from rubric: {rubric_total}")
        
        # Log rubric summary
        for q in rubric.get('questions', []):
            logger.info(f"  Q{q['question_number']}: {q['total_points']} points, "
                       f"{len(q.get('criteria', []))} criteria")
        
        # Step 1: Grade all tests
        logger.info("\n" + "-" * 40)
        logger.info("STEP 1: Grading transcribed answers...")
        logger.info("-" * 40)
        
        grading_results = self.grading_agent.grade_tests(
            rubric=rubric,
            student_tests=student_tests,
            teacher_email=teacher_email,
            original_message_id=original_message_id
        )
        
        graded_results = grading_results["graded_results"]
        low_confidence_notes = grading_results["low_confidence_notes"]
        
        logger.info(f"\n✅ Grading complete. {len(graded_results)} tests graded.")
        logger.info(f"⚠️ Low confidence items: {len(low_confidence_notes)}")
        
        # Log grading results summary
        for result in graded_results:
            score = result.get('total_score', 0)
            percentage = (score / rubric_total * 100) if rubric_total > 0 else 0
            logger.info(
                f"  {result.get('student_name')}: "
                f"{score}/{rubric_total} ({percentage:.1f}%)"
            )
        
        # Step 2: Create annotated PDFs
        logger.info("\n" + "-" * 40)
        logger.info("STEP 2: Creating annotated PDFs...")
        logger.info("-" * 40)
        
        attachments = []
        
        for result in graded_results:
            filename = result.get("filename", "unknown.pdf")
            student_name = result.get("student_name", "Unknown")
            
            original_pdf = original_pdfs.get(filename)
            if not original_pdf:
                logger.warning(f"⚠️ Original PDF not found for {filename}")
                continue
            
            try:
                annotated_pdf = self.pdf_annotator.annotate_student_pdf(
                    original_pdf_bytes=original_pdf,
                    grading_result=result,
                    student_name=student_name,
                    rubric_total=rubric_total,
                    rubric=rubric
                )
                
                output_filename = f"graded_{filename}"
                attachments.append((output_filename, annotated_pdf))
                logger.info(f"  ✅ Created: {output_filename}")
                
            except Exception as e:
                logger.error(f"  ❌ Error annotating PDF for {student_name}: {e}")
        
        # Step 3: Generate email body
        logger.info("\n" + "-" * 40)
        logger.info("STEP 3: Generating email body...")
        logger.info("-" * 40)
        
        email_body = generate_email_body(
            graded_results=graded_results,
            low_confidence_notes=low_confidence_notes,
            rubric_total=rubric_total,
            rubric=rubric
        )
        
        logger.debug("Email body preview:")
        logger.debug("-" * 40)
        logger.debug(email_body[:500] + "...")
        
        # Step 4: Send email
        logger.info("\n" + "-" * 40)
        logger.info("STEP 4: Sending email...")
        logger.info("-" * 40)
        
        subject = f"דירוג הושלם - {len(graded_results)} מבחנים"
        
        message_id = self.gmail.send_email(
            to=teacher_email,
            subject=subject,
            body=email_body,
            attachments=attachments,
            reply_to_message_id=original_message_id
        )
        
        logger.info(f"✅ Email sent successfully!")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Attachments: {len(attachments)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("GRADING ORCHESTRATION COMPLETE")
        logger.info("=" * 80)
        
        return message_id


def validate_grading_result(result: Dict) -> bool:
    """
    Validate that a grading result has all required fields.
    
    Args:
        result: Grading result dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['student_name', 'total_score', 'total_possible', 'grades']
    
    for field in required_fields:
        if field not in result:
            logger.warning(f"Missing required field: {field}")
            return False
    
    if not result.get('grades'):
        logger.warning("Grades list is empty")
        return False
    
    for grade in result['grades']:
        if 'points_earned' not in grade or 'points_possible' not in grade:
            logger.warning(f"Invalid grade entry: {grade}")
            return False
    
    return True
