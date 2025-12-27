"""
Local test script for the Vision-based grading pipeline.
Tests the complete workflow: PDF -> Screenshots -> Vision AI -> Grading

Usage:
    python local_test_vision.py

Requirements:
    - rubric.pdf and student_test.pdf in the same directory (or update paths below)
    - .env file with OPENAI_API_KEY
    - poppler-utils installed (for pdf2image)
        Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
                 Add bin folder to PATH
        Linux: apt-get install poppler-utils
        macOS: brew install poppler
"""
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.document_parser import RubricParser, StudentTestParser
from app.grading_agent import GradingAgent
from app.pdf_annotator import PDFAnnotator, generate_email_body
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("__main__").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG: Update these paths for your local machine
# ============================================================================
RUBRIC_PATH = r"rubric.pdf"  # Or full path like r"C:\path\to\rubric.pdf"
TEST_PATH = r"student_test.pdf"  # Or full path

# Output directory
OUTPUT_DIR = Path(__file__).parent / "local_test_output"


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")


def save_json(data: dict, filename: str):
    """Save dictionary as JSON file."""
    import json
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Saved: {output_path}")


def save_text(text: str, filename: str):
    """Save text to file."""
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    logger.info(f"✅ Saved: {output_path}")


def save_pdf(pdf_bytes: bytes, filename: str):
    """Save PDF bytes to file."""
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    logger.info(f"✅ Saved: {output_path}")


def main():
    """Run the complete vision-based grading pipeline locally."""
    
    print("\n" + "=" * 80)
    print("🔬 VISION-BASED GRADING PIPELINE - LOCAL TEST")
    print("=" * 80 + "\n")
    
    # Check files exist
    if not os.path.exists(RUBRIC_PATH):
        print(f"❌ Rubric not found: {RUBRIC_PATH}")
        print("   Update RUBRIC_PATH in this script")
        return
    
    if not os.path.exists(TEST_PATH):
        print(f"❌ Student test not found: {TEST_PATH}")
        print("   Update TEST_PATH in this script")
        return
    
    ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ========================================================================
    # STEP 1: Parse Rubric with Vision AI
    # ========================================================================
    print("\n" + "-" * 60)
    print("📋 STEP 1: Parsing Rubric (Vision AI)")
    print("-" * 60)
    
    with open(RUBRIC_PATH, 'rb') as f:
        rubric_bytes = f.read()
    
    logger.info(f"Rubric file size: {len(rubric_bytes)} bytes")
    
    rubric = RubricParser.parse_rubric_pdf(rubric_bytes)
    
    # Save parsed rubric
    save_json(rubric, f"parsed_rubric_{timestamp}.json")
    
    # Display rubric summary
    print("\n📊 Parsed Rubric Summary:")
    total_points = 0
    for q in rubric.get('questions', []):
        q_points = q.get('total_points', 0)
        total_points += q_points
        print(f"   Question {q['question_number']}: {q_points} points, "
              f"{len(q.get('criteria', []))} criteria")
        for c in q.get('criteria', [])[:3]:  # Show first 3 criteria
            print(f"      - {c['description'][:50]}... ({c['points']} pts)")
        if len(q.get('criteria', [])) > 3:
            print(f"      ... and {len(q['criteria']) - 3} more criteria")
    print(f"\n   TOTAL: {total_points} points")
    
    # ========================================================================
    # STEP 2: Parse Student Test with Vision AI
    # ========================================================================
    print("\n" + "-" * 60)
    print("📝 STEP 2: Transcribing Student Test (Vision AI)")
    print("-" * 60)
    
    with open(TEST_PATH, 'rb') as f:
        test_bytes = f.read()
    
    test_filename = os.path.basename(TEST_PATH)
    logger.info(f"Test file: {test_filename}, size: {len(test_bytes)} bytes")
    
    student_test = StudentTestParser.parse_student_test(test_bytes, test_filename)
    
    # Save parsed test
    save_json(student_test, f"parsed_student_test_{timestamp}.json")
    
    # Display test summary
    print(f"\n👤 Student: {student_test.get('student_name')}")
    print(f"📄 Answers transcribed: {len(student_test.get('answers', []))}")
    for ans in student_test.get('answers', []):
        code_preview = ans['answer_text'][:100].replace('\n', ' ')
        print(f"   Q{ans['question_number']}: {code_preview}...")
    
    # ========================================================================
    # STEP 3: Grade the Test
    # ========================================================================
    print("\n" + "-" * 60)
    print("✏️ STEP 3: Grading Test")
    print("-" * 60)
    
    grading_agent = GradingAgent()
    
    grading_results = grading_agent.grade_tests(
        rubric=rubric,
        student_tests=[student_test],
        teacher_email="test@example.com",
        original_message_id="test-123"
    )
    
    graded_results = grading_results["graded_results"]
    low_confidence_notes = grading_results["low_confidence_notes"]
    
    # Save grading results
    save_json(grading_results, f"grading_results_{timestamp}.json")
    
    # Display results
    if graded_results:
        result = graded_results[0]
        score = result.get('total_score', 0)
        possible = result.get('total_possible', 0)
        percentage = result.get('percentage', 0)
        
        print(f"\n📊 Grading Result:")
        print(f"   Score: {score}/{possible} ({percentage:.1f}%)")
        print(f"   Grades: {len(result.get('grades', []))}")
        
        # Show grade breakdown
        for grade in result.get('grades', [])[:5]:
            mark = grade.get('mark', '?')
            criterion = grade.get('criterion', '')[:40]
            pts = f"{grade.get('points_earned', 0)}/{grade.get('points_possible', 0)}"
            print(f"   {mark} {criterion}... ({pts})")
        
        if len(result.get('grades', [])) > 5:
            print(f"   ... and {len(result['grades']) - 5} more criteria")
    
    if low_confidence_notes:
        print(f"\n⚠️ Low Confidence Items: {len(low_confidence_notes)}")
        for note in low_confidence_notes[:3]:
            print(f"   - {note}")
    
    # ========================================================================
    # STEP 4: Create Annotated PDF
    # ========================================================================
    print("\n" + "-" * 60)
    print("📎 STEP 4: Creating Annotated PDF")
    print("-" * 60)
    
    pdf_annotator = PDFAnnotator()
    
    rubric_total = sum(q.get('total_points', 0) for q in rubric.get('questions', []))
    
    annotated_pdf = pdf_annotator.annotate_student_pdf(
        original_pdf_bytes=test_bytes,
        grading_result=graded_results[0],
        student_name=student_test['student_name'],
        rubric_total=rubric_total,
        rubric=rubric
    )
    
    annotated_filename = f"graded_{test_filename.replace('.pdf', '')}_{timestamp}.pdf"
    save_pdf(annotated_pdf, annotated_filename)
    
    # ========================================================================
    # STEP 5: Generate Email Body
    # ========================================================================
    print("\n" + "-" * 60)
    print("📧 STEP 5: Generating Email Body")
    print("-" * 60)
    
    email_body = generate_email_body(
        graded_results=graded_results,
        low_confidence_notes=low_confidence_notes,
        rubric_total=rubric_total,
        rubric=rubric
    )
    
    save_text(email_body, f"email_body_{timestamp}.txt")
    
    print("\nEmail preview:")
    print("-" * 40)
    print(email_body[:500])
    print("..." if len(email_body) > 500 else "")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ VISION PIPELINE TEST COMPLETE")
    print("=" * 80)
    print(f"\n📁 Output files saved to: {OUTPUT_DIR.absolute()}")
    print(f"   - parsed_rubric_{timestamp}.json")
    print(f"   - parsed_student_test_{timestamp}.json")
    print(f"   - grading_results_{timestamp}.json")
    print(f"   - {annotated_filename}")
    print(f"   - email_body_{timestamp}.txt")
    
    print("\n🎉 Success! The vision-based pipeline is working correctly.")
    print("   You can now deploy to Cloud Run.")


if __name__ == "__main__":
    main()
