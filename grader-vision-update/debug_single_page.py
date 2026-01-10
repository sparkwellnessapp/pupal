"""
Single Page Transcription Debug Script

This script tests the transcription pipeline on individual pages to isolate issues.
It provides detailed output comparing visual grounding claims vs actual transcription.

Usage:
    python debug_single_page.py                           # Test all 3 pages
    python debug_single_page.py --page 1                  # Test only page 1
    python debug_single_page.py --provider anthropic      # Test with Claude
"""

import os
import sys
import argparse
import base64
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
    GROUNDED_SYSTEM_PROMPT,
    GROUNDED_TRANSCRIPTION_PROMPT,
)


def load_debug_image(page_number: int) -> str:
    """Load a debug page image and return as base64."""
    debug_dir = Path("debug_handwritten_pages")
    
    # Find the page file (handles Hebrew filenames)
    page_files = list(debug_dir.glob(f"*_page_{page_number}.png"))
    
    if not page_files:
        raise FileNotFoundError(f"No page {page_number} found in {debug_dir}")
    
    page_path = page_files[0]
    print(f"Loading: {page_path.name}")
    
    with open(page_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def test_single_page(page_number: int, provider_name: str = "openai", model: str = None):
    """Test transcription on a single page with detailed output."""
    
    print(f"\n{'='*80}")
    print(f"SINGLE PAGE DEBUG TEST - Page {page_number}")
    print(f"Provider: {provider_name}" + (f" ({model})" if model else ""))
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*80}\n")
    
    # Load the image
    try:
        page_b64 = load_debug_image(page_number)
        print(f"✓ Image loaded ({len(page_b64)} chars base64)\n")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return None
    
    # Create provider
    kwargs = {}
    if model:
        kwargs["model"] = model
    provider = get_vlm_provider(provider_name, **kwargs)
    print(f"✓ Using provider: {provider.name}\n")
    
    # Build prompt
    prompt = GROUNDED_TRANSCRIPTION_PROMPT.format(
        page_number=page_number,
        question_context=""
    )
    
    print("--- SENDING PROMPT ---")
    print(prompt[:500] + "...\n")
    
    # Call VLM
    print("⏳ Calling VLM...")
    response = provider.transcribe_images(
        images_b64=[page_b64],
        system_prompt=GROUNDED_SYSTEM_PROMPT,
        user_prompt=prompt,
        max_tokens=4000,
        temperature=0.1,
    )
    print(f"✓ Response received ({len(response)} chars)\n")
    
    # Save raw response
    output_dir = Path("debug_vlm_responses")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"single_page_{page_number}_{provider_name}_{timestamp}.txt"
    
    output_content = f"""{'='*80}
SINGLE PAGE DEBUG - Page {page_number}
Provider: {provider.name}
Timestamp: {datetime.now().isoformat()}
{'='*80}

--- SYSTEM PROMPT ---
{GROUNDED_SYSTEM_PROMPT}

--- USER PROMPT ---
{prompt}

--- RAW RESPONSE ---
{response}
"""
    
    output_file.write_text(output_content, encoding='utf-8')
    print(f"✓ Saved to: {output_file}\n")
    
    # Parse and analyze
    print("--- RAW RESPONSE ---")
    print(response[:2000])
    if len(response) > 2000:
        print(f"\n... ({len(response) - 2000} more chars)")
    print("\n")
    
    # Try to parse JSON
    try:
        import json
        # Clean markdown code blocks
        cleaned = response
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        
        parsed = json.loads(cleaned)
        
        print("--- PARSED ANALYSIS ---")
        
        grounding = parsed.get("visual_grounding", {})
        print("\n🔍 VISUAL GROUNDING (what VLM claims to SEE):")
        print(f"   Class Name:  {grounding.get('class_name', 'N/A')}")
        print(f"   Methods:     {grounding.get('method_names', [])}")
        print(f"   Fields:      {grounding.get('field_names', [])}")
        print(f"   ~Lines:      {grounding.get('approximate_lines', 'N/A')}")
        
        transcription = parsed.get("transcription", {})
        print(f"\n📝 TRANSCRIPTION (what VLM actually WROTE):")
        print(f"   Student:     {transcription.get('student_name', 'N/A')}")
        
        for i, ans in enumerate(transcription.get("answers", [])):
            code = ans.get("answer_text", "")
            print(f"\n   Answer {i+1} (Q{ans.get('question_number', '?')}, conf={ans.get('confidence', 'N/A')}):")
            print("   " + "-"*40)
            for line in code.split("\n")[:20]:  # First 20 lines
                print(f"   | {line}")
            if len(code.split("\n")) > 20:
                print(f"   ... ({len(code.split(chr(10))) - 20} more lines)")
        
        # Consistency check
        print(f"\n{'='*60}")
        print("CONSISTENCY CHECK")
        print(f"{'='*60}")
        
        identified_class = grounding.get('class_name', '')
        if identified_class:
            # Check if identified class appears in transcription
            import re
            for ans in transcription.get("answers", []):
                code = ans.get("answer_text", "")
                match = re.search(r'\bclass\s+(\w+)', code, re.IGNORECASE)
                if match:
                    transcribed_class = match.group(1)
                    if transcribed_class.lower() != identified_class.lower():
                        print(f"⚠️  CLASS MISMATCH!")
                        print(f"    Identified: '{identified_class}'")
                        print(f"    Transcribed: '{transcribed_class}'")
                    else:
                        print(f"✓ Class name consistent: '{identified_class}'")
        
        # Check methods
        methods = grounding.get('method_names', [])
        if methods:
            all_code = " ".join(ans.get("answer_text", "") for ans in transcription.get("answers", []))
            missing = [m for m in methods if m and m.lower() not in all_code.lower()]
            if missing:
                print(f"⚠️  MISSING METHODS in transcription: {missing}")
            else:
                print(f"✓ All {len(methods)} methods found in transcription")
        
        return parsed
        
    except json.JSONDecodeError as e:
        print(f"\n✗ Failed to parse JSON: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Debug single page transcription")
    parser.add_argument("--page", type=int, default=None, help="Page number to test (1, 2, or 3)")
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic", "google"])
    parser.add_argument("--model", default=None, help="Specific model to use")
    parser.add_argument("--all", action="store_true", help="Test all pages")
    
    args = parser.parse_args()
    
    if args.page:
        test_single_page(args.page, args.provider, args.model)
    else:
        # Test all 3 pages
        for page in [1, 2, 3]:
            print(f"\n{'#'*80}")
            print(f"# TESTING PAGE {page}")
            print(f"{'#'*80}")
            test_single_page(page, args.provider, args.model)
            print("\n")


if __name__ == "__main__":
    main()
