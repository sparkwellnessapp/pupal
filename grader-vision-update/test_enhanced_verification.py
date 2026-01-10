"""
Test script to verify the enhanced consistency checks and hallucination detection.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.handwriting_transcription_service import (
    HandwritingTranscriptionService,
    get_vlm_provider,
    pdf_path_to_images,
    image_to_base64,
)

def test_enhanced_verification():
    """Test the enhanced consistency verification."""
    print("Testing Enhanced Consistency Verification")
    print("="*60)
    
    # Create service with OpenAI 
    service = HandwritingTranscriptionService(
        vlm_provider=get_vlm_provider("openai")
    )
    
    # Load the test PDF images
    debug_dir = Path("debug_handwritten_pages")
    page_files = sorted(debug_dir.glob("*_page_*.png"))
    
    if not page_files:
        print("No debug pages found! Run the main transcription first.")
        return
    
    print(f"Found {len(page_files)} debug pages")
    
    # Test just page 1
    page1_path = [p for p in page_files if "_page_1.png" in str(p)]
    if page1_path:
        import base64
        with open(page1_path[0], "rb") as f:
            page_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        print(f"\nProcessing: {page1_path[0].name}")
        print("-"*60)
        
        # Call the grounded transcription
        result = service._transcribe_page_grounded(
            page_b64=page_b64,
            page_number=1,
            question_context=""
        )
        
        if result:
            grounding = result.get("visual_grounding", {})
            print(f"\nVisual Grounding:")
            print(f"  Class: {grounding.get('class_name')}")
            print(f"  Fields: {grounding.get('field_names')}")
            
            # The verification should have already run and logged warnings
            print("\n[Check logs above for hallucination warnings]")


if __name__ == "__main__":
    test_enhanced_verification()
