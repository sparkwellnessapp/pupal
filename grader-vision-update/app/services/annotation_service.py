"""
Annotation service layer.

Handles PDF annotation and Google Cloud Storage operations.
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from io import BytesIO
from google.cloud import storage

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.grading import GradedTestPdf, GradedTest
from ..config import settings
from .pdf_annotator import PDFAnnotator

logger = logging.getLogger(__name__)

# Singleton instances
_pdf_annotator: Optional[PDFAnnotator] = None
_gcs_client: Optional[storage.Client] = None


def get_pdf_annotator() -> PDFAnnotator:
    """Get or create the PDF annotator singleton."""
    global _pdf_annotator
    if _pdf_annotator is None:
        _pdf_annotator = PDFAnnotator()
    return _pdf_annotator


def get_gcs_client() -> storage.Client:
    """Get or create the GCS client singleton."""
    global _gcs_client
    if _gcs_client is None:
        if settings.gcs_credentials_file:
            _gcs_client = storage.Client.from_service_account_json(settings.gcs_credentials_file)
        else:
            _gcs_client = storage.Client(project=settings.google_cloud_project)
    return _gcs_client


async def annotate_graded_test_pdf(
    original_pdf_bytes: bytes,
    grading_result: Dict[str, Any],
    rubric: Dict[str, Any],
    student_name: str,
) -> bytes:
    """
    Create an annotated PDF with grading results.
    
    Args:
        original_pdf_bytes: The original student test PDF
        grading_result: The grading result dictionary
        rubric: The rubric JSON structure
        student_name: Student's name
        
    Returns:
        Annotated PDF as bytes
    """
    logger.info(f"Annotating PDF for student: {student_name}")
    
    annotator = get_pdf_annotator()
    
    # Calculate rubric total
    rubric_total = sum(
        q.get('total_points', 0) 
        for q in rubric.get('questions', [])
    )
    
    annotated_pdf = annotator.annotate_student_pdf(
        original_pdf_bytes=original_pdf_bytes,
        grading_result=grading_result,
        student_name=student_name,
        rubric_total=rubric_total,
        rubric=rubric,
    )
    
    logger.info(f"PDF annotated successfully, size: {len(annotated_pdf)} bytes")
    return annotated_pdf


async def upload_pdf_to_gcs(
    pdf_bytes: bytes,
    filename: str,
    rubric_id: UUID,
    graded_test_id: UUID,
) -> Dict[str, Any]:
    """
    Upload an annotated PDF to Google Cloud Storage.
    
    Args:
        pdf_bytes: The PDF file as bytes
        filename: Desired filename for the PDF
        rubric_id: Associated rubric ID
        graded_test_id: Associated graded test ID
        
    Returns:
        Dictionary with GCS metadata (uri, bucket, path)
    """
    # TODO: Implement GCS upload
    # 1. Initialize GCS client
    # 2. Upload to bucket with path: graded_pdfs/{rubric_id}/{graded_test_id}/{filename}
    # 3. Return metadata
    
    bucket_name = settings.gcs_bucket_name if hasattr(settings, 'gcs_bucket_name') else "grader-vision-pdfs"
    object_path = f"graded_pdfs/{rubric_id}/{graded_test_id}/{filename}"
    gcs_uri = f"gs://{bucket_name}/{object_path}"
    
    logger.warning("GCS upload not yet implemented - returning placeholder URI")
    
    return {
        "gcs_uri": gcs_uri,
        "gcs_bucket": bucket_name,
        "gcs_object_path": object_path,
        "file_size_bytes": len(pdf_bytes),
    }


async def save_graded_pdf(
    db: AsyncSession,
    graded_test_id: UUID,
    rubric_id: UUID,
    filename: str,
    gcs_metadata: Dict[str, Any],
) -> GradedTestPdf:
    """
    Save graded PDF metadata to the database.
    
    Args:
        db: Database session
        graded_test_id: ID of the graded test
        rubric_id: ID of the rubric
        filename: PDF filename
        gcs_metadata: GCS storage metadata
        
    Returns:
        The created GradedTestPdf model instance
    """
    graded_pdf = GradedTestPdf(
        graded_test_id=graded_test_id,
        rubric_id=rubric_id,
        filename=filename,
        gcs_uri=gcs_metadata["gcs_uri"],
        gcs_bucket=gcs_metadata["gcs_bucket"],
        gcs_object_path=gcs_metadata["gcs_object_path"],
        file_size_bytes=gcs_metadata.get("file_size_bytes"),
    )
    
    db.add(graded_pdf)
    await db.commit()
    await db.refresh(graded_pdf)
    
    logger.info(f"Saved graded PDF metadata with ID: {graded_pdf.id}")
    return graded_pdf


async def get_graded_pdf_by_id(db: AsyncSession, pdf_id: UUID) -> Optional[GradedTestPdf]:
    """
    Retrieve a graded PDF record from the database by ID.
    
    Args:
        db: Database session
        pdf_id: The graded PDF's UUID
        
    Returns:
        The GradedTestPdf model instance, or None if not found
    """
    result = await db.execute(
        select(GradedTestPdf).where(GradedTestPdf.id == pdf_id)
    )
    return result.scalar_one_or_none()


async def get_graded_pdfs_by_rubric_id(
    db: AsyncSession,
    rubric_id: UUID,
) -> List[GradedTestPdf]:
    """
    Retrieve all graded PDFs for a given rubric.
    
    Args:
        db: Database session
        rubric_id: The rubric's UUID
        
    Returns:
        List of GradedTestPdf model instances
    """
    result = await db.execute(
        select(GradedTestPdf)
        .where(GradedTestPdf.rubric_id == rubric_id)
        .order_by(GradedTestPdf.created_at.desc())
    )
    return list(result.scalars().all())


async def download_pdf_from_gcs(gcs_uri: str) -> bytes:
    """
    Download a PDF from Google Cloud Storage.
    
    Args:
        gcs_uri: The GCS URI (gs://bucket/path)
        
    Returns:
        PDF file as bytes
    """
    # TODO: Implement GCS download
    # 1. Parse bucket and path from URI
    # 2. Initialize GCS client
    # 3. Download and return bytes
    
    logger.warning("GCS download not yet implemented")
    raise NotImplementedError("GCS download not yet implemented")


async def generate_signed_url(gcs_uri: str, expiration_minutes: int = 60) -> str:
    """
    Generate a signed URL for downloading a PDF from GCS.
    
    Args:
        gcs_uri: The GCS URI
        expiration_minutes: URL expiration time in minutes
        
    Returns:
        Signed download URL
    """
    # TODO: Implement signed URL generation
    logger.warning("Signed URL generation not yet implemented")
    return gcs_uri  # Placeholder
