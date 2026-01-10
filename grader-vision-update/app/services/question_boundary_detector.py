"""
Question Boundary Detector Service

Detects question and sub-question boundaries within transcribed text by analyzing
handwritten page images and inserting <Q#> and <Q#.S> markers at boundaries.

Supports:
- Question markers: <Q1>, <Q2>, etc.
- Sub-question markers: <Q1.א>, <Q2.ב>, <Q1.A>, etc.

This enables page-first architecture where:
- Frontend displays by page always
- Markers indicate which question/sub-question each section belongs to
- Answers are assembled by question only when grading

Usage:
    detector = QuestionBoundaryDetector(provider)
    result = await detector.detect_boundaries(
        page_image_b64="...",
        raw_text="...",
        verified_text="...",
        answered_questions=[2],
        sub_questions={"2": ["א", "ב"]},  # Optional
        page_number=1
    )
"""

import asyncio
import json
import re
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

BOUNDARY_DETECTION_TIMEOUT = 8.0  # seconds (increased for sub-question detection)
CONFIDENCE_THRESHOLD = 0.80  # Lowered slightly for sub-questions

# =============================================================================
# Prompts
# =============================================================================

BOUNDARY_DETECTION_SYSTEM_PROMPT = """You are a precise document analyzer specializing in handwritten academic tests.
Your task is to detect QUESTION and SUB-QUESTION boundaries in student answer sheets.

CAPABILITIES:
- Recognize Hebrew and English question/sub-question markers
- Handle messy handwriting and various notation styles
- Correlate visual position in image with text position
- Understand page layout (margins vs center, underlined headers)

CONSTRAINTS:
- Only insert markers you are confident about (>80% certainty)
- Never modify the transcribed text content itself
- Preserve exact whitespace and formatting

OUTPUT:
Return ONLY valid JSON. No markdown. No explanation."""


BOUNDARY_DETECTION_PROMPT = """## CONTEXT
You are analyzing page {page_number} of a handwritten computer science test.
The student answered: {answered_context}

## INPUT
<transcribed_text>
{transcribed_text}
</transcribed_text>

## TASK
Analyze the attached image and identify where each question/sub-question answer begins.

### WHERE TO LOOK FOR MARKERS

**In the MARGINS (left/right sides of page):**
- Small numbers: "1.", "1)", "2)", "2."
- Hebrew letters as sub-questions: "א.", "ב)", "ג."
- English letters: "A.", "B)", "a.", "b)"
- Combined: "1א", "2ב", "1.א"

**In the CENTER (as titles, often underlined):**
- Full Hebrew: "שאלה 1", "שאלה 2"
- Underlined question headers
- Circled or boxed numbers

**Structural cues:**
- Large gaps/spacing between sections
- Change of class/method (in code)
- Horizontal lines drawn by student

### MARKER PATTERNS TO RECOGNIZE

**Questions:**
- Hebrew: "שאלה 1", "שאלה 2", "ש1", "ש.1"
- Numbers: "1.", "1)", "1:", "#1", "Q1"

**Sub-questions:**
- Hebrew letters: "א", "ב", "ג", "ד" (often with "." or ")")
- English letters: "A", "B", "C", "a)", "b)"
- Combined: "סעיף א", "סעיף ב"

### STEP 1: Visual Analysis
Scan the ENTIRE image, especially:
1. Left/right margins for small markers
2. Page center for underlined titles
3. Between code blocks for separators

### STEP 2: Position Mapping
For each marker found, identify the corresponding position in transcribed text.

### STEP 3: Marker Insertion
Insert markers at each identified boundary:
- <Q#> for main questions (e.g., <Q2>)
- <Q#.S> for sub-questions (e.g., <Q2.א>, <Q1.A>)

## OUTPUT FORMAT
Return valid JSON:
{{
  "analysis": {{
    "markers_found": [
      {{
        "question_number": 2,
        "sub_question_id": null,
        "visual_indicator": "שאלה 2 underlined at center top",
        "location": "center",
        "text_anchor": "public class Employee",
        "confidence": 0.95
      }},
      {{
        "question_number": 2,
        "sub_question_id": "א",
        "visual_indicator": "א) in left margin",
        "location": "margin",
        "text_anchor": "private int id",
        "confidence": 0.88
      }}
    ],
    "reasoning": "Found שאלה 2 centered and underlined. Sub-question א marked in margin."
  }},
  "marked_text": "<Q2><Q2.א>public class Employee {{\\n    private int id;\\n    ..."
}}

## EXAMPLES

### Example 1: Question with sub-questions
Image shows: "שאלה 2" underlined at top, "א)" before first code block, "ב)" before second
marked_text: "<Q2><Q2.א>public class Employee {{ ... }}<Q2.ב>public Department() {{ ... }}"

### Example 2: Question only (no sub-questions)
Image shows: "2." in left margin before code
marked_text: "<Q2>public class Employee {{ private int id; }}"

### Example 3: No visible markers
marked_text: "int x = 5; return x * 2;"
(Return unchanged - do not guess)

## IMPORTANT RULES
1. HIGH CONFIDENCE ONLY: Only insert markers when confidence > 0.80
2. NO HALLUCINATION: If unsure, return text unchanged
3. PRESERVE TEXT: Never modify actual content
4. VALID MARKERS ONLY: Use only question numbers from {answered_questions}
5. SUB-QUESTION FORMAT: Use <Q#.S> format (e.g., <Q2.א>, <Q1.A>)"""


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BoundaryDetectionResult:
    """Result of boundary detection for a single page."""
    marked_text: str
    detected_questions: List[int]
    detected_sub_questions: List[str] = field(default_factory=list)  # ["2.א", "2.ב"]
    confidence_scores: Dict[str, float] = field(default_factory=dict)  # {"2": 0.95, "2.א": 0.88}
    reasoning: Optional[str] = None
    used_fallback: bool = False


# =============================================================================
# Question Boundary Detector
# =============================================================================

class QuestionBoundaryDetector:
    """
    Detects question and sub-question boundaries in transcribed handwritten text.
    
    Uses a focused VLM call to analyze page images and insert <Q#> and <Q#.S> markers
    at question/sub-question boundaries.
    """
    
    def __init__(self, vlm_provider):
        """
        Initialize detector with a VLM provider.
        
        Args:
            vlm_provider: VLM provider instance (OpenAI, Anthropic, etc.)
        """
        self.vlm_provider = vlm_provider
        
    async def detect_boundaries(
        self,
        page_image_b64: str,
        raw_text: str,
        verified_text: str,
        answered_questions: List[int],
        sub_questions: Optional[Dict[str, List[str]]] = None,  # {"2": ["א", "ב"]}
        page_number: int = 1,
    ) -> BoundaryDetectionResult:
        """
        Detect question and sub-question boundaries, insert markers.
        
        Args:
            page_image_b64: Base64-encoded page image
            raw_text: Raw transcription (for position reference)
            verified_text: Verified transcription (where markers are inserted)
            answered_questions: List of question numbers the student answered
            sub_questions: Dict mapping question number to list of sub-question IDs
            page_number: Current page number (1-indexed)
            
        Returns:
            BoundaryDetectionResult with marked text and metadata
        """
        start_time = time.time()
        sub_questions = sub_questions or {}
        
        # Check if we have sub-questions for any answered question
        has_sub_questions = any(
            str(q) in sub_questions and len(sub_questions[str(q)]) > 0
            for q in answered_questions
        )
        
        # Single question with NO sub-questions → wrap entire text
        if len(answered_questions) == 1 and not has_sub_questions:
            q_num = answered_questions[0]
            marked_text = f"<Q{q_num}>{verified_text}"
            logger.info(
                "boundary_detection_skip",
                extra={
                    "page_number": page_number,
                    "reason": "single_question_no_subquestions",
                    "question_number": q_num,
                }
            )
            return BoundaryDetectionResult(
                marked_text=marked_text,
                detected_questions=[q_num],
                detected_sub_questions=[],
                confidence_scores={str(q_num): 1.0},
                reasoning="Single question with no sub-questions - wrapped entire text",
                used_fallback=False,
            )
        
        # Multiple questions OR has sub-questions → Use VLM
        try:
            result = await asyncio.wait_for(
                self._detect_with_vlm(
                    page_image_b64=page_image_b64,
                    verified_text=verified_text,
                    answered_questions=answered_questions,
                    sub_questions=sub_questions,
                    page_number=page_number,
                ),
                timeout=BOUNDARY_DETECTION_TIMEOUT,
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "boundary_detection_complete",
                extra={
                    "page_number": page_number,
                    "markers_found": result.detected_questions,
                    "sub_questions_found": result.detected_sub_questions,
                    "latency_ms": elapsed_ms,
                }
            )
            return result
            
        except asyncio.TimeoutError:
            logger.warning(
                "boundary_detection_timeout",
                extra={
                    "page_number": page_number,
                    "timeout_seconds": BOUNDARY_DETECTION_TIMEOUT,
                }
            )
            return self._create_fallback_result(verified_text, answered_questions, "timeout")
            
        except Exception as e:
            logger.warning(
                "boundary_detection_error",
                extra={
                    "page_number": page_number,
                    "error": str(e),
                }
            )
            return self._create_fallback_result(verified_text, answered_questions, str(e))
    
    async def _detect_with_vlm(
        self,
        page_image_b64: str,
        verified_text: str,
        answered_questions: List[int],
        sub_questions: Dict[str, List[str]],
        page_number: int,
    ) -> BoundaryDetectionResult:
        """Run VLM call for boundary detection."""
        
        # Build answered context string
        answered_context = self._build_answered_context(answered_questions, sub_questions)
        
        # Build prompt
        user_prompt = BOUNDARY_DETECTION_PROMPT.format(
            page_number=page_number,
            answered_questions=answered_questions,
            answered_context=answered_context,
            transcribed_text=verified_text,
        )
        
        # Run VLM call (sync → async wrapper)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.vlm_provider.transcribe_images(
                images_b64=[page_image_b64],
                system_prompt=BOUNDARY_DETECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=4000,
                temperature=0.0,  # Deterministic for boundary detection
            )
        )
        
        # Parse response
        return self._parse_response(response, verified_text, answered_questions, sub_questions)
    
    def _build_answered_context(
        self,
        answered_questions: List[int],
        sub_questions: Dict[str, List[str]],
    ) -> str:
        """Build a human-readable context of answered questions and sub-questions."""
        parts = []
        for q in answered_questions:
            q_str = str(q)
            if q_str in sub_questions and sub_questions[q_str]:
                subs = ", ".join(sub_questions[q_str])
                parts.append(f"שאלה {q} (סעיפים: {subs})")
            else:
                parts.append(f"שאלה {q}")
        return ", ".join(parts) if parts else "all questions"
    
    def _parse_response(
        self,
        response: str,
        original_text: str,
        answered_questions: List[int],
        sub_questions: Dict[str, List[str]],
    ) -> BoundaryDetectionResult:
        """Parse VLM response with validation and fallbacks."""
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError("No JSON found in response")
                
            data = json.loads(json_match.group())
            
            # Extract analysis and marked_text
            analysis = data.get("analysis", {})
            markers_found = analysis.get("markers_found", [])
            marked_text = data.get("marked_text", original_text)
            reasoning = analysis.get("reasoning")
            
            # Filter low-confidence and invalid markers
            marked_text, valid_markers = self._filter_markers(
                marked_text, markers_found, answered_questions, sub_questions
            )
            
            # Validate marked_text preserves original content
            if not self._validate_content_preserved(marked_text, original_text):
                logger.warning("Marked text content differs from original, using original")
                return self._create_fallback_result(
                    original_text, answered_questions, "content_not_preserved"
                )
            
            # Build results
            detected_questions = list(set(
                m["question_number"] for m in valid_markers
            ))
            detected_sub_questions = [
                f"{m['question_number']}.{m['sub_question_id']}"
                for m in valid_markers
                if m.get("sub_question_id")
            ]
            
            # Build confidence scores
            confidence_scores = {}
            for m in valid_markers:
                q_num = m["question_number"]
                sub_id = m.get("sub_question_id")
                key = f"{q_num}.{sub_id}" if sub_id else str(q_num)
                confidence_scores[key] = m.get("confidence", 0.9)
            
            return BoundaryDetectionResult(
                marked_text=marked_text,
                detected_questions=detected_questions,
                detected_sub_questions=detected_sub_questions,
                confidence_scores=confidence_scores,
                reasoning=reasoning,
                used_fallback=False,
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse boundary response: {e}")
            return self._create_fallback_result(
                original_text, answered_questions, f"parse_error: {e}"
            )
    
    def _filter_markers(
        self,
        marked_text: str,
        markers_found: List[Dict],
        answered_questions: List[int],
        sub_questions: Dict[str, List[str]],
    ) -> Tuple[str, List[Dict]]:
        """Remove markers below confidence threshold or with invalid question/sub-question IDs."""
        
        valid_markers = []
        
        for marker in markers_found:
            q_num = marker.get("question_number")
            sub_id = marker.get("sub_question_id")
            confidence = marker.get("confidence", 0)
            
            # Check: confidence above threshold
            if confidence < CONFIDENCE_THRESHOLD:
                self._remove_marker_from_text(marked_text, q_num, sub_id)
                logger.debug(f"Removed low-confidence marker Q{q_num}.{sub_id} (conf={confidence})")
                continue
            
            # Check: question number in answered_questions
            if q_num not in answered_questions:
                marked_text = self._remove_marker_from_text(marked_text, q_num, sub_id)
                logger.debug(f"Removed invalid question marker Q{q_num}")
                continue
            
            # Check: sub-question ID is valid (if provided)
            if sub_id:
                valid_subs = sub_questions.get(str(q_num), [])
                if valid_subs and sub_id not in valid_subs:
                    marked_text = self._remove_marker_from_text(marked_text, q_num, sub_id)
                    logger.debug(f"Removed invalid sub-question marker Q{q_num}.{sub_id}")
                    continue
            
            valid_markers.append(marker)
        
        return marked_text, valid_markers
    
    def _remove_marker_from_text(
        self, text: str, q_num: int, sub_id: Optional[str]
    ) -> str:
        """Remove a specific marker from text."""
        if sub_id:
            tag = f"<Q{q_num}.{sub_id}>"
        else:
            tag = f"<Q{q_num}>"
        return text.replace(tag, "", 1)
    
    def _validate_content_preserved(self, marked_text: str, original_text: str) -> bool:
        """Verify that marked text contains the same content as original (minus markers)."""
        
        # Remove all markers (both question and sub-question)
        text_without_markers = re.sub(r'<Q\d+(?:\.[^>]+)?>', '', marked_text)
        
        # Normalize whitespace for comparison
        normalized_marked = ' '.join(text_without_markers.split())
        normalized_original = ' '.join(original_text.split())
        
        # Allow small differences (within 5% of length)
        if len(normalized_original) == 0:
            return len(normalized_marked) == 0
            
        similarity_threshold = 0.95
        length_ratio = min(len(normalized_marked), len(normalized_original)) / max(len(normalized_marked), len(normalized_original))
        
        return length_ratio >= similarity_threshold
    
    def _create_fallback_result(
        self,
        verified_text: str,
        answered_questions: List[int],
        reason: str,
    ) -> BoundaryDetectionResult:
        """Create fallback result when VLM call fails."""
        
        # Fallback: wrap entire text with first answered question
        if answered_questions:
            first_q = answered_questions[0]
            marked_text = f"<Q{first_q}>{verified_text}"
            detected = [first_q]
            confidence = {str(first_q): 0.7}
        else:
            marked_text = verified_text
            detected = []
            confidence = {}
        
        return BoundaryDetectionResult(
            marked_text=marked_text,
            detected_questions=detected,
            detected_sub_questions=[],
            confidence_scores=confidence,
            reasoning=f"Fallback used: {reason}",
            used_fallback=True,
        )


# =============================================================================
# Helper Functions
# =============================================================================

def parse_question_markers(text: str) -> Tuple[List[int], List[str], str]:
    """
    Parse <Q#> and <Q#.S> markers from text.
    
    Returns:
        Tuple of (detected question numbers, detected sub-questions, clean text)
    """
    # Find all question markers
    q_markers = re.findall(r'<Q(\d+)>', text)
    questions = [int(m) for m in q_markers]
    
    # Find all sub-question markers
    sq_markers = re.findall(r'<Q(\d+\.[^>]+)>', text)
    
    # Clean text
    clean_text = re.sub(r'<Q\d+(?:\.[^>]+)?>', '', text)
    
    return list(set(questions)), sq_markers, clean_text


def extract_question_segments(text: str) -> Dict[str, str]:
    """
    Extract text segments grouped by question/sub-question.
    
    Given: "<Q2><Q2.א>class A {...}<Q2.ב>class B {...}"
    Returns: {"2": "class A {...}", "2.א": "class A {...}", "2.ב": "class B {...}"}
    """
    segments: Dict[str, str] = {}
    
    # Split by markers, keeping the markers
    parts = re.split(r'(<Q\d+(?:\.[^>]+)?>)', text)
    
    current_keys: List[str] = []
    current_text = ""
    
    for part in parts:
        marker_match = re.match(r'<Q(\d+(?:\.[^>]+)?)>', part)
        if marker_match:
            # Save text to all current keys
            for key in current_keys:
                if key in segments:
                    segments[key] += current_text
                else:
                    segments[key] = current_text
            
            # Start new segment
            key = marker_match.group(1)
            current_keys = [key]
            current_text = ""
        else:
            current_text += part
    
    # Save final segment
    for key in current_keys:
        if key in segments:
            segments[key] += current_text
        else:
            segments[key] = current_text
    
    # Strip whitespace from all segments
    return {k: v.strip() for k, v in segments.items() if v.strip()}
