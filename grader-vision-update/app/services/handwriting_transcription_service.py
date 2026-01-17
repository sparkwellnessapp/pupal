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
import re
import json
import base64
import logging
import argparse
import difflib
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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

# Debug output directory for raw VLM responses
DEBUG_RESPONSES_DIR = Path("debug_vlm_responses")
DEBUG_RESPONSES_DIR.mkdir(exist_ok=True)


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
    
    def transcribe_images_stream(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ):
        """
        Stream transcription from VLM token-by-token.
        
        Args:
            images_b64: List of base64-encoded images
            system_prompt: System instructions
            user_prompt: User prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Yields:
            Text chunks as they are generated
        """
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
        
        # Use streaming mode
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True  # Enable streaming
        )
        
        # Yield chunks as they arrive
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AsyncOpenAIProvider(VLMProvider):
    """
    Async OpenAI GPT-4o Vision provider.
    
    Uses the native AsyncOpenAI client for proper async support.
    This allows asyncio.wait_for() to actually cancel the HTTP request
    instead of just abandoning a thread (which still consumes tokens).
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        from openai import OpenAI, AsyncOpenAI
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        # Keep sync client for backwards compatibility with sync methods
        self._sync_client = OpenAI(api_key=self._api_key)
        # Async client for new async methods
        self._async_client = AsyncOpenAI(api_key=self._api_key)
        self.model = model
    
    @property
    def name(self) -> str:
        return f"AsyncOpenAI/{self.model}"
    
    @traceable(run_type="llm", name="OpenAI Vision Sync")
    def transcribe_images(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        """Sync transcription - for backwards compatibility."""
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
        
        response = self._sync_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content
    
    @traceable(run_type="llm", name="OpenAI Vision Async")
    async def transcribe_images_async(
        self,
        images_b64: List[str],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ) -> str:
        """
        Native async transcription - allows proper timeout cancellation.
        
        When asyncio.wait_for() times out, this will actually cancel
        the HTTP request instead of leaving it running in a thread.
        """
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
        
        response = await self._async_client.chat.completions.create(
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
        provider_name: One of "openai", "async_openai", "anthropic", "google"
        **kwargs: Provider-specific arguments (api_key, model, etc.)
        
    Returns:
        VLMProvider instance
        
    Note: Use "async_openai" for parallel transcription with proper timeout cancellation.
    """
    providers = {
        "openai": OpenAIProvider,
        "async_openai": AsyncOpenAIProvider,  # Native async for parallel processing
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

HANDWRITING_SYSTEM_PROMPT = """You are a FORENSIC HANDWRITING OCR SCANNER. Your job is character-level transcription.

=== CORE IDENTITY ===
You are NOT a programmer. You are NOT a code reviewer. You are a HUMAN PHOTOCOPIER.
Your output must be a pixel-perfect text representation of what the student's hand wrote.
If grading discovers bugs, that is intentional - the teacher uses YOUR transcription to grade THEIR mistakes.

=== CRITICAL RULES ===
1. TRANSCRIBE BUGS AS WRITTEN
   - Student wrote "if (x = 5)" instead of "if (x == 5)"? → Output "if (x = 5)"
   - Missing semicolon? → Keep it missing
   - Wrong variable name "numStudnets"? → Write "numStudnets" (typo preserved)
   - Infinite loop? → Transcribe the infinite loop
   - Syntax error? → Transcribe the syntax error

2. NEVER INVENT CHARACTERS
   - If you can't read a character clearly, use [?] as placeholder
   - Do NOT guess what "should logically be there"
   - Example: You see "ret_rn x" but can't read middle char → write "ret[?]rn x", NOT "return x"

3. PRESERVE WHITESPACE & FORMATTING
   - Match the student's indentation exactly (use spaces, not tabs unless specifically visible)
   - Preserve blank lines as written
   - Do not "beautify" or reformat

4. HEBREW STRUCTURAL MARKERS
   - "שאלה 1", "סעיף א", "א.", "ב)" etc. are SECTION HEADERS, not code
   - Do NOT include these in answer_text
   - Hebrew COMMENTS inside code (e.g., "// מונה") ARE transcribed

=== CONFIDENCE SCORING ===
- 1.0 = Every character is clearly legible
- 0.8-0.9 = Some characters required careful interpretation
- 0.5-0.7 = Significant portions unclear, used [?] placeholders
- Below 0.5 = Mostly illegible, transcription unreliable

=== OUTPUT ===
Return ONLY valid JSON. No markdown. No explanation. No code blocks."""


# =============================================================================
# Optimized Single-Call Grounded Transcription Prompt
# =============================================================================

# System prompt for grounded transcription (single call per page)
GROUNDED_SYSTEM_PROMPT = """You are a HANDWRITING OCR SCANNER - NOT a code generator.

=== CRITICAL DISTINCTION ===
❌ WRONG: Generating code you think the student SHOULD have written
✅ RIGHT: Copying character-by-character what is ACTUALLY written

=== YOUR TASK ===
1. FIRST: Read the page and identify what class/methods/fields are PHYSICALLY WRITTEN
2. THEN: Copy the code character-by-character, including all mistakes

=== STRICT RULES ===
• Transcribe ONLY visible handwritten ink marks on the paper
• If the student wrote "Emploeyy" with a typo → output "Emploeyy"
• If a semicolon is missing → leave it missing
• If a brace is wrong → keep it wrong
• Use [?] for illegible characters - NEVER guess
• Do NOT complete, fix, or beautify anything

=== ⛔ ANTI-HALLUCINATION RULES ===
For assignment statements like "this.X = Y":
• You MUST be able to physically SEE both "X" and "Y" written on the page
• If you cannot clearly read what comes after "this." → write "this.[?]"
• If you cannot clearly read what comes after "=" → write "= [?]"
• NEVER invent variable names that "should" logically be there
• NEVER assume a constructor parameter name matches a field name

Example:
• You see "this." followed by unclear text, then "=" then unclear text
• ✅ CORRECT: "this.[?] = [?];"
• ❌ WRONG: "this.issenior = issenior;" (if you guessed this)

=== OUTPUT ===
Return ONLY valid JSON matching the schema. No explanations."""


# Combined prompt that forces visual grounding BEFORE transcription
GROUNDED_TRANSCRIPTION_PROMPT = """Look at this handwritten code page and transcribe it.

=== STEP 1: IDENTIFY (fill visual_grounding FIRST) ===
Read the page carefully. What class name do you see after the word "class"?
What method names can you physically see written?

=== STEP 2: TRANSCRIBE (fill transcription SECOND) ===
Copy the code CHARACTER BY CHARACTER. The class name you write MUST match what you identified in Step 1.

{{
  "visual_grounding": {{
    "class_name": "The EXACT word written after 'class' (copy letter by letter) or null",
    "method_names": ["list each method name you can physically see"],
    "field_names": ["list variable names you can see"],
    "approximate_lines": 0
  }},
  "transcription": {{
    "student_name": "name at top of page or null",
    "page_number": {page_number},
    "answers": [
      {{
        "question_number": 1,
        "sub_question_id": null,
        "answer_text": "COPY the code here - class name MUST match visual_grounding.class_name",
        "confidence": 0.95
      }}
    ]
  }}
}}

=== VALIDATION BEFORE RESPONDING ===
✓ Check: Does the class name in answer_text match visual_grounding.class_name?
✓ Check: Did you preserve typos, missing semicolons, and errors?
✓ Check: Are you transcribing what's written, not what's expected?

{question_context}"""


# Legacy prompts kept for backwards compatibility with _transcribe_with_mappings
SINGLE_PAGE_SYSTEM_PROMPT = GROUNDED_SYSTEM_PROMPT



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
        
        return f"""Transcribe the handwritten code from the images.
Questions to transcribe: {questions_str}

⚠️ CRITICAL: Transcribe EXACTLY what is written, including ALL errors, typos, and bugs.
Do NOT fix anything. If the student wrote wrong code, output wrong code.

Return JSON in this format:
{{
  "student_name": "Student name if visible at top of page, otherwise null",
  "answers": [
    {{
      "question_number": 1,
      "sub_question_id": "א" or null if no sub-question,
      "answer_text": "The EXACT transcribed code here - bugs and all",
      "confidence": 0.95
    }}
  ]
}}

Rules:
- Transcribe each question/sub-question separately
- confidence is 0-1 indicating transcription clarity (NOT code correctness)
- Use [?] for illegible characters - do NOT guess"""

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
        
        return f"""Transcribe the handwritten code from the images.

Student answered these questions:
{questions_str}

Identify answers by handwritten markers like:
- Numbers: "1.", "2)", "3:"
- Headers: "שאלה 1", "שאלה 2"
- Sub-question markers: "א.", "ב.", "ג." or "א)", "ב)", "ג)"
- Separator lines between questions

⚠️ CRITICAL: Transcribe EXACTLY what is written, including ALL errors, typos, and bugs.
- Student wrote "if (x = 5)" instead of "=="? → Output "if (x = 5)"
- Missing semicolon? → Keep it missing
- Typo in variable name? → Keep the typo
- Do NOT fix, improve, or beautify the code in any way

Return JSON:
{{
  "student_name": "Student name if visible, otherwise null",
  "answers": [
    {{
      "question_number": 1,
      "sub_question_id": "א" or null,
      "answer_text": "EXACT transcribed code - preserve all bugs",
      "confidence": 0.95
    }}
  ]
}}

Notes:
- Create separate object for each sub-question (א, ב, ג)
- confidence = transcription clarity (NOT code quality)
- Use [?] for unclear characters - never guess"""

    else:
        # Unguided extraction - transcribe everything visible
        return """Transcribe ALL handwritten code from the images.
Identify questions/sub-questions by markers like "שאלה 1", "סעיף א", etc.

⚠️ CRITICAL: Transcribe EXACTLY what is written, including ALL errors.
Do NOT fix syntax errors, typos, or logic bugs. Output exactly what you see.

Return JSON:
{
  "student_name": "Student name if visible, otherwise null",
  "answers": [
    {
      "question_number": 1,
      "sub_question_id": "א" or null,
      "answer_text": "EXACT code as written - bugs preserved",
      "confidence": 0.95
    }
  ]
}

Rules:
- Transcribe each question separately
- confidence = how clearly you can read it (NOT code correctness)
- Use [?] for illegible characters"""


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
        """
        Optimized transcription using SINGLE CALL per page with PARALLEL processing.
        
        Key optimizations:
        1. Single VLM call per page (combines identification + transcription)
        2. Parallel processing of all pages using ThreadPoolExecutor
        3. Consistency verification with optional retry
        
        This reduces cost by 50% and latency by 3-5x compared to sequential 2-call approach.
        """
        
        logger.info(f"{'='*60}")
        logger.info(f"OPTIMIZED PARALLEL TRANSCRIPTION: {len(images_b64)} pages")
        logger.info(f"{'='*60}")
        
        # DEBUG: Save pages being sent to VLM
        self._save_debug_pages(images_b64, filename)
        
        # Build question context once (shared across all pages)
        question_context = self._build_question_context(rubric_questions, answered_question_numbers)
        
        # Process all pages in PARALLEL using ThreadPoolExecutor
        def process_page(args):
            page_idx, page_b64 = args
            return self._transcribe_page_grounded(
                page_b64=page_b64,
                page_number=page_idx + 1,
                question_context=question_context,
            )
        
        # Use ThreadPoolExecutor for parallel VLM calls
        with ThreadPoolExecutor(max_workers=min(len(images_b64), 5)) as executor:
            page_results = list(executor.map(process_page, enumerate(images_b64)))
        
        # Extract student name from first page
        student_name = None
        if page_results and page_results[0]:
            transcription = page_results[0].get("transcription", {})
            student_name = transcription.get("student_name")
        
        # Log results
        for idx, result in enumerate(page_results):
            if result:
                grounding = result.get("visual_grounding", {})
                logger.info(f"Page {idx + 1}: class={grounding.get('class_name', 'none')}")
        
        # Merge all page transcriptions into unified result
        return self._merge_grounded_results(
            page_results=page_results,
            filename=filename,
            student_name=student_name,
        )
    
    def _build_question_context(
        self,
        rubric_questions: Optional[List[RubricQuestion]],
        answered_question_numbers: Optional[List[int]],
    ) -> str:
        """Build question context string for prompts."""
        if not rubric_questions:
            return ""
        
        questions_info = []
        for q in rubric_questions:
            if answered_question_numbers and q.question_number not in answered_question_numbers:
                continue
            q_info = f"שאלה {q.question_number}"
            if q.sub_questions:
                q_info += f" (סעיפים: {', '.join(q.sub_questions)})"
            questions_info.append(q_info)
        
        if questions_info:
            return f"Student may have answered: {', '.join(questions_info)}"
        return ""
    
    @traceable(name="Transcribe Page Grounded")
    def _transcribe_page_grounded(
        self,
        page_b64: str,
        page_number: int,
        question_context: str = "",
    ) -> Dict[str, Any]:
        """
        Single VLM call that combines visual grounding + transcription.
        
        The structured output forces the model to identify elements BEFORE transcribing,
        which prevents confabulation.
        """
        # Build the prompt with page number and question context
        user_prompt = GROUNDED_TRANSCRIPTION_PROMPT.format(
            page_number=page_number,
            question_context=question_context,
        )
        
        logger.info(f"  Page {page_number}: Sending grounded transcription request...")
        
        response = self.vlm_provider.transcribe_images(
            images_b64=[page_b64],
            system_prompt=GROUNDED_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=4000,
            temperature=0.1,
        )
        
        # DEBUG: Save raw VLM response for analysis
        self._save_debug_response(page_number, response, user_prompt)
        
        result = self._parse_json(response)
        
        # Verify consistency between grounding and transcription
        if result and not self._verify_consistency(result):
            logger.warning(f"  Page {page_number}: Consistency mismatch detected, retrying...")
            # Retry with explicit grounding instruction
            result = self._retry_with_forced_grounding(page_b64, page_number, result, question_context)
        
        return result
    
    def _verify_consistency(self, result: Dict[str, Any]) -> bool:
        """
        Verify that the transcribed code matches the identified visual elements.
        
        Checks:
        1. Class name in transcription matches visual_grounding.class_name
        2. At least some identified methods appear in transcription
        3. At least some identified fields appear in transcription
        
        Returns True if consistent, False if mismatch detected.
        """
        grounding = result.get("visual_grounding", {})
        transcription = result.get("transcription", {})
        
        # Collect all transcribed code
        all_code = ""
        for ans in transcription.get("answers", []):
            all_code += " " + ans.get("answer_text", "")
        all_code_lower = all_code.lower()
        
        mismatches = []
        
        # 1. Check class name
        identified_class = grounding.get("class_name")
        if identified_class and identified_class.strip():
            identified_class_lower = identified_class.lower().strip()
            # Find "class X" pattern
            match = re.search(r'\bclass\s+(\w+)', all_code, re.IGNORECASE)
            if match:
                transcribed_class = match.group(1).lower().strip()
                if transcribed_class != identified_class_lower:
                    mismatches.append(f"CLASS: identified '{identified_class}' but transcribed '{match.group(1)}'")
        
        # 2. Check method names (at least 50% should appear)
        identified_methods = grounding.get("method_names", [])
        if identified_methods and len(identified_methods) > 0:
            found_methods = 0
            missing_methods = []
            for method in identified_methods:
                if method and method.lower() in all_code_lower:
                    found_methods += 1
                else:
                    missing_methods.append(method)
            
            coverage = found_methods / len(identified_methods)
            if coverage < 0.5:
                mismatches.append(f"METHODS: only {found_methods}/{len(identified_methods)} found. Missing: {missing_methods}")
        
        # 3. Check field names (at least 50% should appear)
        identified_fields = grounding.get("field_names", [])
        if identified_fields and len(identified_fields) > 0:
            found_fields = 0
            missing_fields = []
            for field in identified_fields:
                if field and field.lower() in all_code_lower:
                    found_fields += 1
                else:
                    missing_fields.append(field)
            
            coverage = found_fields / len(identified_fields)
            if coverage < 0.5:
                mismatches.append(f"FIELDS: only {found_fields}/{len(identified_fields)} found. Missing: {missing_fields}")
        
        # 4. Check for HALLUCINATED variables (in code but not identified)
        # Find all "this.X = Y" patterns and verify BOTH X and Y are legitimate
        if identified_fields and len(identified_fields) > 0:
            identified_set = set(f.lower() for f in identified_fields if f)
            
            # Also collect method parameter names as valid RHS values
            method_params = set()
            # Find constructor/method declarations: MethodName(Type param1, Type param2, ...)
            param_matches = re.findall(r'\w+\s*\([^)]*\)', all_code)
            for match in param_matches:
                # Extract parameter names (last word before comma/paren)
                params = re.findall(r'(?:,\s*|\(\s*)\w+\s+(\w+)(?:\s*[,)])', match)
                method_params.update(p.lower() for p in params)
            
            valid_rhs = identified_set | method_params | {'false', 'true', 'null', '0', '1'}
            
            # Find this.X = Y patterns with both sides
            this_assignments = re.findall(r'this\.(\w+)\s*=\s*(\w+)', all_code, re.IGNORECASE)
            for lhs, rhs in this_assignments:
                # Check LHS (the field being assigned)
                if lhs.lower() not in identified_set:
                    mismatches.append(f"HALLUCINATION (LHS): 'this.{lhs}' but '{lhs}' not in fields {list(identified_fields)}")
                
                # Check RHS (the value being assigned) - skip numeric literals
                if not rhs.isdigit() and rhs.lower() not in valid_rhs:
                    mismatches.append(f"HALLUCINATION (RHS): '{rhs}' in 'this.{lhs} = {rhs}' is not a known field/param. Expected: {list(valid_rhs)}")
        
        if mismatches:
            logger.warning(f"    Consistency mismatches detected:")
            for m in mismatches:
                logger.warning(f"      - {m}")
            return False
        
        return True
    
    def _retry_with_forced_grounding(
        self,
        page_b64: str,
        page_number: int,
        original_result: Dict[str, Any],
        question_context: str,
    ) -> Dict[str, Any]:
        """
        Retry transcription with explicit instruction to use the identified class name.
        """
        grounding = original_result.get("visual_grounding", {})
        identified_class = grounding.get("class_name", "")
        
        forced_prompt = f"""You previously identified the class on this page as: {identified_class}

Now transcribe the code EXACTLY as written, ensuring the class name matches your identification.

Return JSON:
{{
  "visual_grounding": {{
    "class_name": "{identified_class}",
    "method_names": {json.dumps(grounding.get('method_names', []))},
    "field_names": {json.dumps(grounding.get('field_names', []))},
    "approximate_lines": {grounding.get('approximate_lines', 0)}
  }},
  "transcription": {{
    "student_name": null,
    "page_number": {page_number},
    "answers": [
      {{
        "question_number": 1,
        "sub_question_id": null,
        "answer_text": "EXACT CODE with class {identified_class} - transcribe what you see",
        "confidence": 0.9
      }}
    ]
  }}
}}

{question_context}

CRITICAL: The class name MUST be {identified_class} as you identified."""

        response = self.vlm_provider.transcribe_images(
            images_b64=[page_b64],
            system_prompt=GROUNDED_SYSTEM_PROMPT,
            user_prompt=forced_prompt,
            max_tokens=4000,
            temperature=0.0,  # Zero temperature for retry
        )
        
        return self._parse_json(response)
    
    def _merge_grounded_results(
        self,
        page_results: List[Dict[str, Any]],
        filename: str,
        student_name: Optional[str],
    ) -> TranscriptionResult:
        """
        Merge grounded transcription results from all pages.
        """
        answers_by_question: Dict[Tuple[int, Optional[str]], List[Dict]] = {}
        
        for page_idx, result in enumerate(page_results):
            if not result:
                continue
            
            # Log what we got from each page
            grounding = result.get("visual_grounding", {})
            transcription = result.get("transcription", {})
            
            logger.info(f"  Merge: Page {page_idx + 1}")
            logger.info(f"    Visual grounding: class={grounding.get('class_name')}, methods={grounding.get('method_names', [])}")
            
            for ans in transcription.get("answers", []):
                q_num = ans.get("question_number", 0)
                sub_id = ans.get("sub_question_id")
                answer_text = ans.get("answer_text", "")
                confidence = ans.get("confidence", 0.9)
                
                # Log answer preview
                preview = answer_text[:80].replace('\n', ' ') if answer_text else "(empty)"
                logger.info(f"    Q{q_num}{f'-{sub_id}' if sub_id else ''}: {preview}...")
                
                key = (q_num, sub_id)
                if key not in answers_by_question:
                    answers_by_question[key] = []
                
                if answer_text.strip():
                    answers_by_question[key].append({
                        "text": answer_text,
                        "confidence": confidence,
                        "page": page_idx + 1,  # Track which page
                    })
        
        # Build final answers
        final_answers = []
        # Sort with custom key to handle None sub_ids (None sorts before strings)
        def sort_key(item):
            (q_num, sub_id), _ = item
            return (q_num, "" if sub_id is None else sub_id)
        
        for (q_num, sub_id), answer_parts in sorted(answers_by_question.items(), key=sort_key):
            combined_text = "\n".join(part["text"] for part in answer_parts)
            # Use minimum confidence across parts (most conservative)
            min_confidence = min((part["confidence"] for part in answer_parts), default=0.9)
            
            final_answers.append(TranscribedAnswer(
                question_number=q_num,
                sub_question_id=sub_id,
                answer_text=combined_text,
                confidence=min_confidence,
            ))
        
        if not student_name:
            student_name = self._extract_name_from_filename(filename)
        
        return TranscriptionResult(
            student_name=student_name,
            filename=filename,
            answers=final_answers,
        )
    
    def _save_debug_pages(self, images_b64: List[str], filename: str):
        """Save debug copies of pages being processed."""
        try:
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
    
    def _save_debug_response(self, page_number: int, raw_response: str, prompt_used: str):
        """
        Save raw VLM response to debug file for analysis.
        
        Creates a timestamped file with:
        - The prompt sent to the VLM
        - The raw response received
        - Parsed visual_grounding vs transcription for easy comparison
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = DEBUG_RESPONSES_DIR / f"page_{page_number}_{timestamp}.txt"
            
            # Try to parse the response for analysis
            parsed = self._parse_json(raw_response)
            grounding = parsed.get("visual_grounding", {}) if parsed else {}
            transcription = parsed.get("transcription", {}) if parsed else {}
            
            content = f"""{'='*80}
RAW VLM RESPONSE DEBUG - Page {page_number}
Timestamp: {datetime.now().isoformat()}
{'='*80}

--- PROMPT SENT ---
{prompt_used}

--- RAW RESPONSE ---
{raw_response}

--- PARSED VISUAL GROUNDING ---
Class Name: {grounding.get('class_name', 'N/A')}
Method Names: {grounding.get('method_names', [])}
Field Names: {grounding.get('field_names', [])}
Approx Lines: {grounding.get('approximate_lines', 'N/A')}

--- PARSED TRANSCRIPTION ---
Student Name: {transcription.get('student_name', 'N/A')}
Page Number: {transcription.get('page_number', 'N/A')}
Answers:
"""
            for i, ans in enumerate(transcription.get("answers", [])):
                content += f"""
  Answer {i+1}:
    Question: {ans.get('question_number', '?')}{f"-{ans.get('sub_question_id')}" if ans.get('sub_question_id') else ''}
    Confidence: {ans.get('confidence', 'N/A')}
    Code:
{self._indent_code(ans.get('answer_text', ''))}
"""
            
            debug_file.write_text(content, encoding='utf-8')
            logger.info(f"DEBUG: Saved raw VLM response to {debug_file.name}")
            
        except Exception as e:
            logger.warning(f"DEBUG: Failed to save response: {e}")
    
    def _indent_code(self, code: str, spaces: int = 6) -> str:
        """Helper to indent code for debug output."""
        if not code:
            return "      (empty)"
        indent = " " * spaces
        return "\n".join(indent + line for line in code.split("\n"))
    
    def _merge_page_transcriptions(
        self,
        page_transcriptions: List[Dict[str, Any]],
        filename: str,
        student_name: Optional[str],
    ) -> TranscriptionResult:
        """
        Merge transcriptions from individual pages into a unified result.
        
        Handles cases where answers span multiple pages by combining them.
        """
        # Collect all answers, grouping by question number
        answers_by_question: Dict[Tuple[int, Optional[str]], List[str]] = {}
        
        for page_data in page_transcriptions:
            for ans in page_data.get("answers", []):
                q_num = ans.get("question_number", 0)
                sub_id = ans.get("sub_question_id")
                answer_text = ans.get("answer_text", "")
                
                key = (q_num, sub_id)
                if key not in answers_by_question:
                    answers_by_question[key] = []
                
                if answer_text.strip():
                    answers_by_question[key].append(answer_text)
        
        # Build final answers, combining multi-page answers
        final_answers = []
        for (q_num, sub_id), texts in sorted(answers_by_question.items()):
            combined_text = "\n".join(texts)
            final_answers.append(TranscribedAnswer(
                question_number=q_num,
                sub_question_id=sub_id,
                answer_text=combined_text,
                confidence=0.9,  # Slightly lower for merged answers
            ))
        
        if not student_name:
            student_name = self._extract_name_from_filename(filename)
        
        return TranscriptionResult(
            student_name=student_name,
            filename=filename,
            answers=final_answers,
        )
    
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