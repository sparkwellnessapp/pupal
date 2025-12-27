"""
Document parsing utilities for rubrics and student tests.
VISION-BASED VERSION: Uses screenshots + GPT-4o Vision for extraction.
Replaces fragile PyPDF2 text extraction with reliable visual AI parsing.
"""
import logging
import json
import base64
import io
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from openai import OpenAI
from pdf2image import convert_from_bytes
from PIL import Image

from .config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client singleton."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[Image.Image]:
    """
    Convert PDF bytes to a list of PIL Images.
    
    Args:
        pdf_bytes: PDF file as bytes
        dpi: Resolution for rendering (150 is good balance of quality/size)
        
    Returns:
        List of PIL Image objects, one per page
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


def image_to_base64(image: Image.Image, max_size: int = 1500) -> str:
    """
    Convert PIL Image to base64 string, resizing if needed.
    
    Args:
        image: PIL Image object
        max_size: Maximum dimension (width or height)
        
    Returns:
        Base64-encoded PNG string
    """
    # Resize if too large (save tokens and API costs)
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


def call_vision_llm(
    images_b64: List[str],
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o",
    max_tokens: int = 4000,
    temperature: float = 0.1
) -> str:
    """
    Call GPT-4o Vision API with images.
    
    Args:
        images_b64: List of base64-encoded images
        system_prompt: System instructions
        user_prompt: User prompt/question
        model: Model to use (gpt-4o recommended for vision)
        max_tokens: Maximum response tokens
        temperature: Sampling temperature
        
    Returns:
        Model response text
    """
    client = get_openai_client()
    
    # Build content array with images
    content = []
    
    for i, img_b64 in enumerate(images_b64):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_b64}",
                "detail": "high"  # Use high detail for text extraction
            }
        })
    
    # Add text prompt after images
    content.append({
        "type": "text",
        "text": user_prompt
    })
    
    logger.info(f"Calling {model} with {len(images_b64)} images...")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        max_tokens=max_tokens,
        temperature=temperature
    )
    
    result = response.choices[0].message.content
    logger.info(f"Vision LLM response: {len(result)} chars")
    
    return result


class RubricParser:
    """Parser for rubric PDFs using Vision AI."""
    
    SYSTEM_PROMPT = """You are an expert at extracting grading rubrics from PDF images.
Your task is to identify ALL grading criteria and their point values.

IMPORTANT:
- The rubric is in Hebrew
- Look for tables or structured lists showing criteria and points
- Each criterion has a description and a point value
- Questions are marked with "שאלה X - Y נקודות" (Question X - Y points)
- Criteria are usually in table format with points in one column

OUTPUT FORMAT:
Return ONLY valid JSON (no markdown, no extra text):
{
  "questions": [
    {
      "question_number": 1,
      "total_points": 40,
      "criteria": [
        {"description": "criterion description in Hebrew", "points": 5},
        {"description": "another criterion", "points": 10}
      ]
    }
  ]
}

RULES:
1. Extract EVERY criterion you can see
2. Preserve Hebrew text exactly as shown
3. Sum of criteria points should equal question total_points
4. If you can't determine question number, use sequential numbering"""

    USER_PROMPT = """Extract the complete grading rubric from these PDF page images.

Look for:
1. Question headers like "שאלה 1 - 40 נקודות" 
2. Grading criteria tables with Hebrew descriptions and point values
3. Any structured list of what to grade

Return the complete rubric as JSON."""
    
    @staticmethod
    def parse_rubric_pdf(pdf_bytes: bytes) -> Dict:
        """
        Parse rubric PDF using Vision AI.
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Rubric dictionary with questions and criteria
        """
        try:
            logger.info("=" * 60)
            logger.info("PARSING RUBRIC (Vision Mode)")
            logger.info("=" * 60)
            
            # Convert PDF to images
            images = pdf_to_images(pdf_bytes, dpi=150)
            
            # Convert all pages to base64
            # For rubrics, we typically need all pages
            images_b64 = [image_to_base64(img) for img in images]
            
            logger.info(f"Prepared {len(images_b64)} page images for VLM")
            
            # Call Vision LLM
            response = call_vision_llm(
                images_b64=images_b64,
                system_prompt=RubricParser.SYSTEM_PROMPT,
                user_prompt=RubricParser.USER_PROMPT,
                temperature=0.1
            )
            
            # Parse JSON response
            rubric = RubricParser._parse_response(response)
            
            # Validate and log
            num_questions = len(rubric.get('questions', []))
            total_criteria = sum(
                len(q.get('criteria', [])) 
                for q in rubric.get('questions', [])
            )
            total_points = sum(
                q.get('total_points', 0) 
                for q in rubric.get('questions', [])
            )
            
            logger.info(f"✅ Rubric parsed: {num_questions} questions, "
                       f"{total_criteria} criteria, {total_points} total points")
            
            return rubric
            
        except Exception as e:
            logger.error(f"Error parsing rubric: {e}", exc_info=True)
            return {'questions': []}
    
    @staticmethod
    def _parse_response(response: str) -> Dict:
        """Parse and validate JSON response from VLM."""
        # Clean markdown wrappers if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last line (```json and ```)
            cleaned = "\n".join(lines[1:-1])
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw response: {response[:500]}...")
            return {'questions': []}
        
        # Validate structure
        if 'questions' not in data:
            logger.warning("Response missing 'questions' key, wrapping...")
            data = {'questions': data if isinstance(data, list) else []}
        
        # Ensure all questions have required fields
        for q in data['questions']:
            if 'question_number' not in q:
                q['question_number'] = 1
            if 'total_points' not in q:
                q['total_points'] = sum(c.get('points', 0) for c in q.get('criteria', []))
            if 'criteria' not in q:
                q['criteria'] = []
        
        return data


class StudentTestParser:
    """Parser for student test PDFs using Vision AI for transcription."""
    
    SYSTEM_PROMPT = """You are an expert at transcribing student programming test answers from PDF images.
Your task is to extract the CODE that students wrote for each question.

IMPORTANT:
- Tests are in Hebrew but CODE is in C#/Java
- Questions are marked with "שאלה X" (Question X)
- Student code appears after instruction markers like "הוסיפו לכאן את ההקלדה" (Add your typing here)
- ONLY extract the student's actual code, not the instructions or examples
- Code may be handwritten or typed

OUTPUT FORMAT:
Return ONLY valid JSON (no markdown, no extra text):
{
  "student_name": "name if visible, or 'Unknown'",
  "answers": [
    {
      "question_number": 1,
      "answer_text": "public class Example {\n    // student code here\n}"
    }
  ]
}

RULES:
1. Transcribe code EXACTLY as written (preserve syntax, even if wrong)
2. Include all code for each question
3. If no code is visible for a question, set answer_text to empty string ""
4. Preserve code formatting and indentation
5. Do NOT include Hebrew instructions in the code"""

    USER_PROMPT_TEMPLATE = """Transcribe all student code answers from these test pages.

The student's name is in the filename: {filename}

For each question (שאלה), extract ONLY the code the student wrote.
Look for code after markers like "הוסיפו לכאן את ההקלדה".

Return JSON with the student name and all their code answers."""
    
    @staticmethod
    def parse_student_test(pdf_bytes: bytes, filename: str) -> Dict:
        """
        Parse student test PDF using Vision AI for transcription.
        
        Args:
            pdf_bytes: PDF file as bytes
            filename: Original filename (used for student name extraction)
            
        Returns:
            Student test dictionary with answers
        """
        try:
            logger.info("=" * 60)
            logger.info(f"PARSING STUDENT TEST: {filename} (Vision Mode)")
            logger.info("=" * 60)
            
            # Convert PDF to images
            images = pdf_to_images(pdf_bytes, dpi=150)
            
            # Convert all pages to base64
            images_b64 = [image_to_base64(img) for img in images]
            
            logger.info(f"Prepared {len(images_b64)} page images for VLM")
            
            # Build user prompt with filename
            user_prompt = StudentTestParser.USER_PROMPT_TEMPLATE.format(
                filename=filename
            )
            
            # Call Vision LLM
            response = call_vision_llm(
                images_b64=images_b64,
                system_prompt=StudentTestParser.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=6000,  # Student code can be lengthy
                temperature=0.1
            )
            
            # Parse response
            result = StudentTestParser._parse_response(response, filename)
            
            logger.info(f"✅ Student test parsed: {result['student_name']}, "
                       f"{len(result['answers'])} answers extracted")
            
            # Log answer previews
            for ans in result['answers']:
                code_preview = ans['answer_text'][:80].replace('\n', ' ')
                logger.info(f"  Q{ans['question_number']}: {code_preview}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing student test: {e}", exc_info=True)
            return {
                'student_name': StudentTestParser._extract_name_from_filename(filename),
                'filename': filename,
                'answers': []
            }
    
    @staticmethod
    def _parse_response(response: str, filename: str) -> Dict:
        """Parse and validate JSON response from VLM."""
        # Clean markdown wrappers
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw response: {response[:500]}...")
            return {
                'student_name': StudentTestParser._extract_name_from_filename(filename),
                'filename': filename,
                'answers': []
            }
        
        # Ensure required fields
        if 'student_name' not in data or not data['student_name']:
            data['student_name'] = StudentTestParser._extract_name_from_filename(filename)
        
        data['filename'] = filename
        
        if 'answers' not in data:
            data['answers'] = []
        
        # Ensure answer structure
        for ans in data['answers']:
            if 'question_number' not in ans:
                ans['question_number'] = 1
            if 'answer_text' not in ans:
                ans['answer_text'] = ''
        
        # Sort by question number
        data['answers'] = sorted(data['answers'], key=lambda x: x.get('question_number', 0))
        
        return data
    
    @staticmethod
    def _extract_name_from_filename(filename: str) -> str:
        """Extract student name from filename."""
        import re
        name = filename.replace('.pdf', '').replace('_', ' ')
        # Remove common prefixes
        name = re.sub(r'תיקון[_ ]?מבחן[_ ]?', '', name)
        name = re.sub(r'test[_ ]?', '', name, flags=re.IGNORECASE)
        name = name.strip()
        return name if name else "Unknown Student"


# Legacy compatibility - keep DocumentParser class for any code that imports it
class DocumentParser:
    """Base class for document parsing (legacy compatibility)."""
    
    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """
        Extract text from PDF - now uses Vision AI.
        DEPRECATED: Use RubricParser or StudentTestParser directly.
        """
        logger.warning("DocumentParser.extract_text_from_pdf is deprecated. "
                      "Use RubricParser or StudentTestParser instead.")
        
        # Fallback to basic text extraction for compatibility
        import PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""
