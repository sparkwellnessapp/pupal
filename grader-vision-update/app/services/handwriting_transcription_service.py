"""
Handwriting Transcription Service

A robust service for transcribing handwritten code from scanned PDFs.
Designed for high accuracy (95%+ target) with pluggable VLM backends.

Features:
- Pluggable VLM providers (OpenAI, Anthropic, Google)
- Rubric-aware extraction (guided by question structure)
- Support for selective question answering (student choice)
- Multi-page answer support
- Standalone testing with accuracy metrics

Usage:
    python handwriting_transcription_service.py --test
    python handwriting_transcription_service.py --pdf path/to/test.pdf
    python handwriting_transcription_service.py --pdf test.pdf --provider anthropic --model claude-sonnet-4-20250514
"""

import os
import io
import json
import base64
import logging
import argparse
import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from pdf2image import convert_from_bytes, convert_from_path
from PIL import Image
from dotenv import load_dotenv
from langsmith import traceable

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QuestionMapping:
    """Mapping of a question/sub-question to PDF pages."""
    question_number: int
    sub_question_id: Optional[str] = None  # א, ב, ג, etc.
    page_indexes: List[int] = field(default_factory=list)
    is_answered: bool = True  # For choice questions - whether student answered this


@dataclass 
class TranscribedAnswer:
    """A single transcribed answer."""
    question_number: int
    sub_question_id: Optional[str]
    answer_text: str
    confidence: float = 1.0
    transcription_notes: Optional[str] = None


@dataclass
class TranscriptionResult:
    """Complete transcription result for a student test."""
    student_name: str
    filename: str
    answers: List[TranscribedAnswer]
    raw_transcription: Optional[str] = None  # Full raw output for debugging


@dataclass
class RubricQuestion:
    """Question structure from rubric for guided extraction."""
    question_number: int
    question_text: Optional[str] = None
    sub_questions: List[str] = field(default_factory=list)  # ["א", "ב", "ג"]
    total_points: float = 0


# =============================================================================
# VLM Provider Interface
# =============================================================================

class VLMProvider(ABC):
    """Abstract base class for Vision Language Model providers."""
    
    @abstractmethod
    @traceable(run_type="tool")
    def transcribe_images(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        """
        Send images to VLM and get transcription.
        
        Args:
            images_b64: List of base64-encoded images
            system_prompt: System instructions
            user_prompt: User prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Returns:
            Model response text
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class OpenAIProvider(VLMProvider):
    """OpenAI GPT-4o Vision provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        
    @property
    def name(self) -> str:
        return f"OpenAI/{self.model}"
    
    @traceable(run_type="llm", name="OpenAI Vision")
    def transcribe_images(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        content = []
        
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high"
                }
            })
        
        content.append({"type": "text", "text": user_prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content


class AnthropicProvider(VLMProvider):
    """Anthropic Claude Vision provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        
    @property
    def name(self) -> str:
        return f"Anthropic/{self.model}"
    
    @traceable(run_type="llm", name="Claude Vision")
    def transcribe_images(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        content = []
        
        for img_b64 in images_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64
                }
            })
        
        content.append({"type": "text", "text": user_prompt})
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content}]
        )
        
        return response.content[0].text


class GoogleProvider(VLMProvider):
    """Google Gemini Vision provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(model)
        self._model_name = model
        
    @property
    def name(self) -> str:
        return f"Google/{self._model_name}"
    
    @traceable(run_type="llm", name="Gemini Vision")
    def transcribe_images(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        import google.generativeai as genai
        
        parts = []
        
        # Add images
        for img_b64 in images_b64:
            img_bytes = base64.b64decode(img_b64)
            parts.append({
                "mime_type": "image/png",
                "data": img_bytes
            })
        
        # Add prompt (combine system + user)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        parts.append(full_prompt)
        
        response = self.model.generate_content(
            parts,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
        )
        
        return response.text


def get_vlm_provider(provider_name: str = "openai", **kwargs) -> VLMProvider:
    """
    Factory function to get VLM provider by name.
    
    Args:
        provider_name: One of "openai", "anthropic", "google"
        **kwargs: Provider-specific arguments (api_key, model, etc.)
        
    Returns:
        VLMProvider instance
    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
    }
    
    if provider_name.lower() not in providers:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers.keys())}")
    
    return providers[provider_name.lower()](**kwargs)


# =============================================================================
# Image Processing
# =============================================================================

def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF bytes to PIL Images."""
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt='PNG')
    logger.info(f"Converted PDF to {len(images)} images at {dpi} DPI")
    return images


def pdf_path_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF file path to PIL Images."""
    images = convert_from_path(pdf_path, dpi=dpi, fmt='PNG')
    logger.info(f"Converted PDF to {len(images)} images at {dpi} DPI")
    return images


def enhance_for_transcription(image: Image.Image) -> Image.Image:
    """
    Enhance an image for better handwriting transcription.
    
    Applies:
    1. Contrast enhancement (makes dark text darker, light background lighter)
    2. Sharpening (improves edge definition)
    3. Brightness normalization
    """
    from PIL import ImageEnhance, ImageFilter, ImageOps
    
    try:
        # Convert to RGB if needed (handles grayscale or RGBA)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 1. Auto-contrast: stretches the histogram for better dynamic range
        image = ImageOps.autocontrast(image, cutoff=1)
        
        # 2. Enhance contrast (make dark text stand out more)
        contrast_enhancer = ImageEnhance.Contrast(image)
        image = contrast_enhancer.enhance(1.4)  # 1.4x contrast boost
        
        # 3. Slight sharpening for clearer edges
        sharpness_enhancer = ImageEnhance.Sharpness(image)
        image = sharpness_enhancer.enhance(1.3)  # 1.3x sharpening
        
        # 4. Slight brightness adjustment to ensure background is white
        brightness_enhancer = ImageEnhance.Brightness(image)
        image = brightness_enhancer.enhance(1.05)  # Slight brightening
        
        logger.debug("Applied image enhancement for transcription")
        return image
        
    except Exception as e:
        logger.warning(f"Image enhancement failed, using original: {e}")
        return image


def image_to_base64(image: Image.Image, max_size: int = 2000, enhance: bool = True) -> str:
    """
    Convert PIL Image to base64 string, resizing if needed.
    Using higher max_size for better handwriting recognition.
    
    Args:
        image: PIL Image
        max_size: Maximum dimension (width or height)
        enhance: Whether to apply contrast/sharpening enhancement
    """
    # Apply enhancement for better transcription
    if enhance:
        image = enhance_for_transcription(image)
    
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        logger.debug(f"Resized image to {new_size}")
    
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    
    return base64.standard_b64encode(buffer.read()).decode('utf-8')


# =============================================================================
# Prompts
# =============================================================================

HANDWRITING_SYSTEM_PROMPT = """You are a world-class expert in literal handwriting transcription for technical programming and CS exams .
Your absolute priority is FIDELITY. You are a biological scanner, NOT a programmer.

STRICT TRANSCRIPTION RULES:
1. NO AUTO-FIXING: Do NOT fix syntax errors, typos, or logic bugs. If the student wrote it wrong, transcribe it wrong.
2. NO VARIABLE HALLUCINATION: Transcribe variable names EXACTLY as written (e.g., if they wrote 'numStudents' do not write 'numOfStudents').
3. TRUST EYES OVER BRAIN: Visual evidence from the image ALWAYS overrides your linguistic or programming internal knowledge.
4. LITERAL CHARACTER MAPPING: 
   - If a line is missing a semicolon, do not add it.
   - If braces are mismatched, keep them mismatched.
   - Preserve all original casing unless visually ambiguous.

HEBREW & VISUAL ANCHORS HANDLING:
- **Structural Markers**: You will see Hebrew markers indicating questions (e.g., "שאלה 1", "סעיף א", "א.", "ב)", "ג-"). 
  -> Do NOT transcribe these markers into the code. They are external structure.
- **Embedded Comments**: If Hebrew text appears *inside* the code line (e.g., "int x = 5; // מונה"), transcribe it exactly as is.

OUTPUT: Return ONLY a valid JSON object. No conversational text. No markdown blocks."""


def build_extraction_prompt(
    rubric_questions: Optional[List[RubricQuestion]] = None,
    question_mappings: Optional[List[QuestionMapping]] = None,
    answered_question_numbers: Optional[List[int]] = None,
) -> str:
    """
    Build the user prompt for extraction, optionally guided by rubric structure.
    
    Args:
        rubric_questions: List of questions from the rubric (for context)
        question_mappings: Optional page mappings (if provided, use specific pages)
        answered_question_numbers: List of question numbers the student answered
    """
    
    if question_mappings:
        # Guided extraction with page mappings - we know exactly what to extract
        questions_info = []
        for mapping in question_mappings:
            if not mapping.is_answered:
                continue
            q_info = f"שאלה {mapping.question_number}"
            if mapping.sub_question_id:
                q_info += f" סעיף {mapping.sub_question_id}"
            questions_info.append(q_info)
        
        questions_str = ", ".join(questions_info)
        
        return f"""תמלל את הקוד מהתמונות הבאות.
השאלות שצריך לתמלל: {questions_str}

החזר JSON בפורמט הבא:
{{
  "student_name": "שם התלמיד אם מופיע בראש הדף, אחרת null",
  "answers": [
    {{
      "question_number": 1,
      "sub_question_id": "א" או null אם אין סעיף,
      "answer_text": "הקוד המתומלל כאן",
      "confidence": 0.95
    }}
  ]
}}

הערות:
- תמלל כל שאלה/סעיף בנפרד
- confidence הוא מספר בין 0 ל-1 המציין את הביטחון בתמלול
- אם חלק מהקוד לא קריא, ציין זאת ב-confidence נמוך יותר"""

    elif rubric_questions:
        # Rubric-aware extraction - auto-detect questions based on rubric structure
        # Build question info string
        questions_info = []
        for q in rubric_questions:
            # Filter to answered questions if specified
            if answered_question_numbers and q.question_number not in answered_question_numbers:
                continue
            
            q_info = f"שאלה {q.question_number}"
            if q.sub_questions:
                sub_q_str = ", ".join(q.sub_questions)
                q_info += f" (סעיפים: {sub_q_str})"
            questions_info.append(q_info)
        
        questions_str = "\n".join(f"  - {q}" for q in questions_info)
        
        return f"""תמלל את הקוד מהתמונות הבאות.

התלמיד עונה על השאלות הבאות:
{questions_str}

זהה את התשובות לפי סימונים שהתלמיד כתב בדף, כגון:
- מספור: "1.", "2)", "3:"
- כותרות: "שאלה 1", "שאלה 2"
- סימוני סעיפים: "א.", "ב.", "ג." או "א)", "ב)", "ג)"
- קווים מפרידים בין שאלות

החזר JSON בפורמט הבא:
{{
  "student_name": "שם התלמיד אם מופיע בראש הדף, אחרת null",
  "answers": [
    {{
      "question_number": 1,
      "sub_question_id": "א" או null אם אין סעיף,
      "answer_text": "הקוד המתומלל כאן",
      "confidence": 0.95
    }}
  ]
}}

הערות חשובות:
- תמלל כל שאלה/סעיף בנפרד כאובייקט נפרד במערך answers
- אם יש סעיפים (א, ב, ג), צור אובייקט נפרד לכל סעיף עם sub_question_id מתאים
- confidence הוא מספר בין 0 ל-1 המציין את הביטחון בתמלול
- אם חלק מהקוד לא קריא, ציין confidence נמוך יותר
- תמלל את הקוד בדיוק כפי שנכתב, כולל שגיאות"""

    else:
        # Unguided extraction - transcribe everything visible
        return """תמלל את כל הקוד מהתמונות הבאות.
זהה שאלות וסעיפים לפי הסימונים בדף (שאלה 1, סעיף א, וכו').

החזר JSON בפורמט הבא:
{
  "student_name": "שם התלמיד אם מופיע בראש הדף, אחרת null",
  "answers": [
    {
      "question_number": 1,
      "sub_question_id": "א" או null אם אין סעיף,
      "answer_text": "הקוד המתומלל כאן",
      "confidence": 0.95
    }
  ]
}

הערות:
- תמלל כל שאלה/סעיף בנפרד
- confidence הוא מספר בין 0 ל-1 המציין את הביטחון בתמלול
- אם יש מספר שאלות בדף, תמלל את כולן"""


# =============================================================================
# Main Transcription Service
# =============================================================================

class HandwritingTranscriptionService:
    """
    Service for transcribing handwritten code from scanned PDFs.
    """
    
    def __init__(self, vlm_provider: Optional[VLMProvider] = None):
        """
        Initialize the service.
        
        Args:
            vlm_provider: VLM provider to use. If None, creates default OpenAI provider.
        """
        self.vlm_provider = vlm_provider or get_vlm_provider("openai")
        logger.info(f"Initialized HandwritingTranscriptionService with {self.vlm_provider.name}")
    
    @traceable(name="Transcribe PDF")
    def transcribe_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        question_mappings: Optional[List[QuestionMapping]] = None,
        rubric_questions: Optional[List[RubricQuestion]] = None,
        answered_question_numbers: Optional[List[int]] = None,
        first_page_index: int = 0,
        dpi: int = 200,
    ) -> TranscriptionResult:
        """
        Transcribe a handwritten test PDF.
        
        Args:
            pdf_bytes: PDF file as bytes
            filename: Original filename
            question_mappings: Optional mappings of questions to pages (for page-by-page extraction)
            rubric_questions: Optional rubric structure for guided extraction
            answered_question_numbers: Optional list of question numbers the student answered
            first_page_index: Page index containing student name
            dpi: DPI for PDF rendering (higher = better quality but slower)
            
        Returns:
            TranscriptionResult with student name and answers
        """
        logger.info(f"=" * 60)
        logger.info(f"TRANSCRIBING: {filename}")
        logger.info(f"Provider: {self.vlm_provider.name}")
        if answered_question_numbers:
            logger.info(f"Answered questions: {answered_question_numbers}")
        logger.info(f"=" * 60)
        
        # Convert PDF to images
        images = pdf_to_images(pdf_bytes, dpi=dpi)
        images_b64 = [image_to_base64(img) for img in images]
        
        if question_mappings:
            # Transcribe question by question based on mappings
            return self._transcribe_with_mappings(
                images_b64=images_b64,
                filename=filename,
                question_mappings=question_mappings,
                rubric_questions=rubric_questions,
                first_page_index=first_page_index,
            )
        else:
            # Transcribe all pages at once (auto-detect questions)
            return self._transcribe_all_pages(
                images_b64=images_b64,
                filename=filename,
                rubric_questions=rubric_questions,
                answered_question_numbers=answered_question_numbers,
            )
    
    @traceable
    def transcribe_pdf_path(
        self,
        pdf_path: str,
        question_mappings: Optional[List[QuestionMapping]] = None,
        rubric_questions: Optional[List[RubricQuestion]] = None,
        first_page_index: int = 0,
        dpi: int = 200,
    ) -> TranscriptionResult:
        """Transcribe from file path."""
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        return self.transcribe_pdf(
            pdf_bytes=pdf_bytes,
            filename=Path(pdf_path).name,
            question_mappings=question_mappings,
            rubric_questions=rubric_questions,
            first_page_index=first_page_index,
            dpi=dpi,
        )
    
    @traceable(name="Transcribe All Pages")
    def _transcribe_all_pages(
        self,
        images_b64: List[str],
        filename: str,
        rubric_questions: Optional[List[RubricQuestion]] = None,
        answered_question_numbers: Optional[List[int]] = None,
    ) -> TranscriptionResult:
        """Transcribe all pages in one VLM call."""
        
        user_prompt = build_extraction_prompt(
            rubric_questions=rubric_questions,
            question_mappings=None,
            answered_question_numbers=answered_question_numbers,
        )
        
        logger.info(f"Sending {len(images_b64)} pages to VLM...")
        
        # DEBUG: Save pages being sent to VLM
        try:
            import base64
            from pathlib import Path
            debug_dir = Path("debug_handwritten_pages")
            debug_dir.mkdir(exist_ok=True)
            
            # Clear old debug files
            for old_file in debug_dir.glob("*.png"):
                old_file.unlink()
            
            # Save each page
            safe_filename = "".join(c if c.isalnum() or c in "-_" else "_" for c in filename[:50])
            for i, img_b64 in enumerate(images_b64):
                img_bytes = base64.b64decode(img_b64)
                page_path = debug_dir / f"{safe_filename}_page_{i + 1}.png"
                page_path.write_bytes(img_bytes)
            
            logger.info(f"DEBUG: Saved {len(images_b64)} pages to {debug_dir.absolute()}")
        except Exception as e:
            logger.warning(f"DEBUG: Failed to save debug pages: {e}")
        
        response = self.vlm_provider.transcribe_images(
            images_b64=images_b64,
            system_prompt=HANDWRITING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8000,
            temperature=0.1,
        )
        
        logger.info(f"Received response: {len(response)} chars")
        
        return self._parse_response(response, filename)
    
    @traceable(name="Transcribe With Mappings")
    def _transcribe_with_mappings(
        self,
        images_b64: List[str],
        filename: str,
        question_mappings: List[QuestionMapping],
        rubric_questions: Optional[List[RubricQuestion]] = None,
        first_page_index: int = 0,
    ) -> TranscriptionResult:
        """Transcribe question by question based on page mappings."""
        
        # Extract student name from first page
        student_name = self._extract_student_name(images_b64[first_page_index])
        
        answers = []
        
        for mapping in question_mappings:
            if not mapping.is_answered:
                logger.info(f"Skipping Q{mapping.question_number} (not answered)")
                continue
            
            # Get images for this question
            question_images = [
                images_b64[idx] 
                for idx in mapping.page_indexes 
                if 0 <= idx < len(images_b64)
            ]
            
            if not question_images:
                logger.warning(f"No valid pages for Q{mapping.question_number}")
                continue
            
            context = f"Q{mapping.question_number}"
            if mapping.sub_question_id:
                context += f"-{mapping.sub_question_id}"
            
            logger.info(f"Transcribing {context} from {len(question_images)} pages...")
            
            # Build focused prompt for this question
            user_prompt = self._build_single_question_prompt(mapping)
            
            response = self.vlm_provider.transcribe_images(
                images_b64=question_images,
                system_prompt=HANDWRITING_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=4000,
                temperature=0.1,
            )
            
            # Parse single answer
            answer = self._parse_single_answer(response, mapping)
            answers.append(answer)
            
            preview = answer.answer_text[:80].replace('\n', ' ')
            logger.info(f"  {context}: {preview}...")
        
        return TranscriptionResult(
            student_name=student_name or self._extract_name_from_filename(filename),
            filename=filename,
            answers=answers,
        )
    
    @traceable(name="Build Prompt")
    def _build_single_question_prompt(self, mapping: QuestionMapping) -> str:
        """Build prompt for a single question extraction."""
        context = f"שאלה {mapping.question_number}"
        if mapping.sub_question_id:
            context += f" סעיף {mapping.sub_question_id}"
        
        return f"""תמלל את הקוד עבור {context} מהתמונות.

החזר JSON בלבד:
{{
  "answer_text": "הקוד המתומלל",
  "confidence": 0.95
}}"""
    
    @traceable(name="Extract Name")
    def _extract_student_name(self, first_page_b64: str) -> Optional[str]:
        """Extract student name from first page."""
        prompt = """חלץ את שם התלמיד מהדף.
חפש בכותרת הדף ליד "שם התלמיד:" או טקסט דומה.

החזר JSON בלבד:
{
  "student_name": "השם או null אם לא נמצא"
}"""
        
        try:
            response = self.vlm_provider.transcribe_images(
                images_b64=[first_page_b64],
                system_prompt="אתה מומחה בזיהוי שמות מטפסים סרוקים.",
                user_prompt=prompt,
                max_tokens=200,
                temperature=0.1,
            )
            
            data = self._parse_json(response)
            name = data.get("student_name")
            if name and name != "null":
                logger.info(f"Extracted student name: {name}")
                return name
        except Exception as e:
            logger.warning(f"Error extracting student name: {e}")
        
        return None
    
    @traceable(name="Parse Response")
    def _parse_response(self, response: str, filename: str) -> TranscriptionResult:
        """Parse VLM response into TranscriptionResult."""
        data = self._parse_json(response)
        
        answers = []
        for ans in data.get("answers", []):
            answers.append(TranscribedAnswer(
                question_number=ans.get("question_number", 1),
                sub_question_id=ans.get("sub_question_id"),
                answer_text=ans.get("answer_text", ""),
                confidence=ans.get("confidence", 1.0),
            ))
        
        student_name = data.get("student_name")
        if not student_name:
            student_name = self._extract_name_from_filename(filename)
        
        return TranscriptionResult(
            student_name=student_name,
            filename=filename,
            answers=answers,
            raw_transcription=response,
        )
    
    @traceable(name="Parse Single Answer")
    def _parse_single_answer(self, response: str, mapping: QuestionMapping) -> TranscribedAnswer:
        """Parse VLM response for a single answer."""
        data = self._parse_json(response)
        
        return TranscribedAnswer(
            question_number=mapping.question_number,
            sub_question_id=mapping.sub_question_id,
            answer_text=data.get("answer_text", data.get("code", "")),
            confidence=data.get("confidence", 1.0),
        )
    
    def _parse_json(self, response: str) -> Dict[str, Any]:
        """Parse JSON from VLM response, handling markdown formatting."""
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines)
            # Remove 'json' prefix if present
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Response: {response[:500]}...")
            return {}
    
    def _extract_name_from_filename(self, filename: str) -> str:
        """Extract student name from filename."""
        # Remove extension
        name = Path(filename).stem
        # Remove common suffixes
        for suffix in ["-כתביד", "_כתביד", "-handwritten", "_handwritten"]:
            if suffix in name:
                name = name.split(suffix)[0]
        # Replace separators with spaces
        name = name.replace("-", " ").replace("_", " ")
        return name.strip()


# =============================================================================
# Testing & Accuracy Measurement
# =============================================================================

def normalize_code(code: str) -> str:
    """Normalize code for comparison."""
    # Remove extra whitespace
    lines = [line.rstrip() for line in code.split('\n')]
    # Remove empty lines at start/end
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return '\n'.join(lines)


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two texts using difflib."""
    norm1 = normalize_code(text1)
    norm2 = normalize_code(text2)
    
    # Use SequenceMatcher for similarity
    matcher = difflib.SequenceMatcher(None, norm1, norm2)
    return matcher.ratio()


def calculate_line_accuracy(transcribed: str, ground_truth: str) -> Tuple[float, List[str]]:
    """
    Calculate line-by-line accuracy and return diff.
    
    Returns:
        Tuple of (accuracy_ratio, diff_lines)
    """
    trans_lines = normalize_code(transcribed).split('\n')
    truth_lines = normalize_code(ground_truth).split('\n')
    
    # Generate unified diff
    diff = list(difflib.unified_diff(
        truth_lines,
        trans_lines,
        fromfile='ground_truth',
        tofile='transcribed',
        lineterm=''
    ))
    
    # Calculate accuracy
    matcher = difflib.SequenceMatcher(None, trans_lines, truth_lines)
    
    return matcher.ratio(), diff


def test_transcription_accuracy(
    service: HandwritingTranscriptionService,
    pdf_path: str,
    ground_truth: str,
    question_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Test transcription accuracy against ground truth.
    
    Args:
        service: Transcription service instance
        pdf_path: Path to test PDF
        ground_truth: Expected transcription text
        question_number: If provided, only compare this question
        
    Returns:
        Dictionary with accuracy metrics and diff
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING: {pdf_path}")
    logger.info(f"{'='*60}")
    
    # Transcribe
    result = service.transcribe_pdf_path(pdf_path, dpi=200)
    
    # Get transcribed text
    if question_number:
        transcribed_answers = [a for a in result.answers if a.question_number == question_number]
        transcribed = '\n'.join(a.answer_text for a in transcribed_answers)
    else:
        transcribed = '\n'.join(a.answer_text for a in result.answers)
    
    # Calculate metrics
    overall_similarity = calculate_similarity(transcribed, ground_truth)
    line_accuracy, diff = calculate_line_accuracy(transcribed, ground_truth)
    
    # Character-level accuracy
    norm_trans = normalize_code(transcribed)
    norm_truth = normalize_code(ground_truth)
    char_matches = sum(1 for a, b in zip(norm_trans, norm_truth) if a == b)
    char_accuracy = char_matches / max(len(norm_truth), 1)
    
    return {
        "pdf_path": pdf_path,
        "student_name": result.student_name,
        "provider": service.vlm_provider.name,
        "metrics": {
            "overall_similarity": overall_similarity,
            "line_accuracy": line_accuracy,
            "char_accuracy": char_accuracy,
            "transcribed_length": len(norm_trans),
            "ground_truth_length": len(norm_truth),
        },
        "transcribed": transcribed,
        "ground_truth": ground_truth,
        "diff": diff,
        "passed": overall_similarity >= 0.95,
    }


def print_test_results(results: Dict[str, Any]):
    """Pretty print test results."""
    print(f"\n{'='*60}")
    print(f"TEST RESULTS: {results['pdf_path']}")
    print(f"Student: {results['student_name']}")
    print(f"Provider: {results['provider']}")
    print(f"{'='*60}")
    
    metrics = results['metrics']
    print(f"\n📊 ACCURACY METRICS:")
    print(f"  Overall Similarity: {metrics['overall_similarity']*100:.1f}%")
    print(f"  Line Accuracy:      {metrics['line_accuracy']*100:.1f}%")
    print(f"  Character Accuracy: {metrics['char_accuracy']*100:.1f}%")
    print(f"  Transcribed Length: {metrics['transcribed_length']} chars")
    print(f"  Ground Truth Length: {metrics['ground_truth_length']} chars")
    
    if results['passed']:
        print(f"\n✅ PASSED (>= 95% similarity)")
    else:
        print(f"\n❌ FAILED (< 95% similarity)")
    
    if results['diff']:
        print(f"\n📝 DIFF (first 50 lines):")
        for line in results['diff'][:50]:
            print(f"  {line}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def parse_ground_truth_file(filepath: str) -> Dict[str, Dict[int, str]]:
    """
    Parse ground truth file with multiple students/questions.
    
    Expected format:
    Student Name - שאלה N:
    code here...
    ----
    
    Returns:
        {student_name: {question_number: code}}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {}
    current_student = None
    current_question = None
    current_code = []
    
    for line in content.split('\n'):
        # Check for new student/question header
        if ' - שאלה ' in line and line.strip().endswith(':'):
            # Save previous if exists
            if current_student and current_question is not None:
                if current_student not in results:
                    results[current_student] = {}
                results[current_student][current_question] = '\n'.join(current_code).strip()
            
            # Parse new header
            parts = line.split(' - שאלה ')
            current_student = parts[0].strip()
            q_part = parts[1].replace(':', '').strip()
            current_question = int(q_part) if q_part.isdigit() else int(q_part.split()[0])
            current_code = []
        
        elif line.startswith('---'):
            # Separator - continue accumulating code for same question
            continue
        
        else:
            current_code.append(line)
    
    # Save last entry
    if current_student and current_question is not None:
        if current_student not in results:
            results[current_student] = {}
        results[current_student][current_question] = '\n'.join(current_code).strip()
    
    return results


def main():
    """CLI entry point for testing."""
    parser = argparse.ArgumentParser(description="Handwriting Transcription Service")
    parser.add_argument("--test", action="store_true", help="Run tests with sample files")
    parser.add_argument("--pdf", type=str, help="Path to PDF file to transcribe")
    parser.add_argument("--ground-truth", type=str, help="Path to ground truth file")
    parser.add_argument("--provider", type=str, default="openai", 
                       choices=["openai", "anthropic", "google"],
                       help="VLM provider to use")
    parser.add_argument("--model", type=str, help="Model name override")
    parser.add_argument("--dpi", type=int, default=200, help="DPI for PDF rendering")
    
    args = parser.parse_args()
    
    # Create provider
    provider_kwargs = {}
    if args.model:
        provider_kwargs["model"] = args.model
    
    try:
        provider = get_vlm_provider(args.provider, **provider_kwargs)
    except Exception as e:
        logger.error(f"Failed to create provider: {e}")
        logger.info("Make sure you have the required API key set:")
        logger.info("  OPENAI_API_KEY for OpenAI")
        logger.info("  ANTHROPIC_API_KEY for Anthropic")
        logger.info("  GOOGLE_API_KEY for Google")
        return
    
    service = HandwritingTranscriptionService(vlm_provider=provider)
    
    if args.test:
        # Run with test files from uploads
        test_dir = Path("/mnt/user-data/uploads")
        
        # Find test files
        pdf_files = list(test_dir.glob("*כתביד*.pdf"))
        ground_truth_file = test_dir / "manual_test_transcript.txt"
        
        if not pdf_files:
            logger.error("No test PDF files found")
            return
        
        if not ground_truth_file.exists():
            logger.error("Ground truth file not found")
            return
        
        # Parse ground truth
        ground_truth = parse_ground_truth_file(str(ground_truth_file))
        logger.info(f"Loaded ground truth for {len(ground_truth)} students")
        
        # Test each PDF
        all_results = []
        for pdf_path in pdf_files:
            # Extract student name from filename
            student_key = None
            for name in ground_truth.keys():
                # Normalize names for comparison
                name_normalized = name.replace(" ", "-").replace(" ", "_")
                filename_normalized = pdf_path.stem
                if name_normalized in filename_normalized or name.replace(" ", "-") in filename_normalized:
                    student_key = name
                    break
            
            if not student_key:
                logger.warning(f"No ground truth found for {pdf_path.name}")
                continue
            
            # Get all questions for this student
            student_truth = ground_truth[student_key]
            combined_truth = '\n\n'.join(student_truth.values())
            
            results = test_transcription_accuracy(
                service=service,
                pdf_path=str(pdf_path),
                ground_truth=combined_truth,
            )
            
            print_test_results(results)
            all_results.append(results)
        
        # Summary
        if all_results:
            avg_similarity = sum(r['metrics']['overall_similarity'] for r in all_results) / len(all_results)
            passed = sum(1 for r in all_results if r['passed'])
            print(f"\n{'='*60}")
            print(f"SUMMARY")
            print(f"{'='*60}")
            print(f"Tests: {len(all_results)}")
            print(f"Passed: {passed}/{len(all_results)}")
            print(f"Average Similarity: {avg_similarity*100:.1f}%")
    
    elif args.pdf:
        # Transcribe single file
        result = service.transcribe_pdf_path(args.pdf, dpi=args.dpi)
        
        print(f"\n{'='*60}")
        print(f"TRANSCRIPTION RESULT")
        print(f"{'='*60}")
        print(f"Student: {result.student_name}")
        print(f"File: {result.filename}")
        print(f"Answers: {len(result.answers)}")
        
        for answer in result.answers:
            q_label = f"Q{answer.question_number}"
            if answer.sub_question_id:
                q_label += f"-{answer.sub_question_id}"
            print(f"\n--- {q_label} (confidence: {answer.confidence:.0%}) ---")
            print(answer.answer_text)
        
        # Compare with ground truth if provided
        if args.ground_truth:
            with open(args.ground_truth, 'r', encoding='utf-8') as f:
                truth = f.read()
            
            combined = '\n\n'.join(a.answer_text for a in result.answers)
            similarity = calculate_similarity(combined, truth)
            print(f"\n📊 Similarity to ground truth: {similarity*100:.1f}%")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()