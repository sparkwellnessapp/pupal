"""
DOCX Rubric Extraction Pipeline v3.
Location: app/services/docx_v3/__init__.py
"""
from .pipeline import (
    extract_rubric_from_docx,
    ExtractionConfig,
    ExtractionResult,
    ExtractionMetrics,
    ExtractionError,
    PIPELINE_VERSION,
)

__all__ = [
    "extract_rubric_from_docx",
    "ExtractionConfig",
    "ExtractionResult",
    "ExtractionMetrics",
    "ExtractionError",
    "PIPELINE_VERSION",
]