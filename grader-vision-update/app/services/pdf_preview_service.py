"""
PDF Preview service layer.

Handles PDF splitting and thumbnail generation for the preview flow.
"""
import logging
from typing import List, Dict, Any

from .document_parser import pdf_to_images, image_to_base64

logger = logging.getLogger(__name__)


def generate_pdf_previews(
    pdf_bytes: bytes,
    thumbnail_max_size: int = 400,
    dpi: int = 100,
) -> Dict[str, Any]:
    """
    Generate page previews for a PDF file.
    
    Args:
        pdf_bytes: The PDF file as bytes
        thumbnail_max_size: Maximum dimension for thumbnails
        dpi: DPI for rendering (lower = smaller thumbnails, faster)
        
    Returns:
        Dictionary with page_count and list of page previews
    """
    logger.info("Generating PDF page previews...")
    
    # Convert PDF to images at lower DPI for thumbnails
    images = pdf_to_images(pdf_bytes, dpi=dpi)
    
    pages = []
    for idx, img in enumerate(images):
        # Get original dimensions before resizing
        original_width, original_height = img.size
        
        # Convert to base64 thumbnail
        thumbnail_b64 = image_to_base64(img, max_size=thumbnail_max_size)
        
        pages.append({
            "page_index": idx,
            "page_number": idx + 1,
            "thumbnail_base64": thumbnail_b64,
            "width": original_width,
            "height": original_height,
        })
    
    logger.info(f"Generated {len(pages)} page previews")
    
    return {
        "page_count": len(pages),
        "pages": pages,
    }
