"""
Google Cloud Storage service for PDF management.
Handles uploading PDFs, splitting into pages, and generating signed URLs.
"""
import os
import uuid
import logging
from datetime import timedelta
from typing import List, Optional, Tuple
from io import BytesIO

from google.cloud import storage
from PyPDF2 import PdfReader, PdfWriter

from ..config import settings

logger = logging.getLogger(__name__)


class GCSService:
    """Service for Google Cloud Storage operations."""
    
    def __init__(self):
        self.bucket_name = settings.gcs_bucket_name
        
        # Initialize client with credentials file if provided, else ADC
        if settings.gcs_credentials_file and os.path.exists(settings.gcs_credentials_file):
            self.client = storage.Client.from_service_account_json(settings.gcs_credentials_file)
            logger.info(f"GCS Service initialized with credentials file: {settings.gcs_credentials_file}")
        else:
            # Uses Application Default Credentials (works on Cloud Run automatically)
            # For local dev, set GOOGLE_APPLICATION_CREDENTIALS env var to service account JSON path
            self.client = storage.Client()
            
        self.bucket = self.client.bucket(self.bucket_name)
        logger.info(f"GCS Service initialized with bucket: {self.bucket_name}")
    
    def upload_bytes(
        self, 
        data: bytes, 
        object_path: str, 
        content_type: str = "application/pdf"
    ) -> str:
        """
        Upload bytes to GCS.
        
        Returns:
            The GCS object path
        """
        blob = self.bucket.blob(object_path)
        blob.upload_from_string(data, content_type=content_type)
        logger.debug(f"Uploaded to gs://{self.bucket_name}/{object_path}")
        return object_path
    
    def generate_signed_url(
        self, 
        object_path: str, 
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for temporary read access.
        
        Args:
            object_path: Path to the object in GCS
            expiration_minutes: URL validity period (default 60 minutes)
            
        Returns:
            Signed URL string
        """
        blob = self.bucket.blob(object_path)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        return url
    
    def split_pdf_to_pages(self, pdf_bytes: bytes) -> List[bytes]:
        """
        Split a PDF into individual single-page PDFs.
        
        Args:
            pdf_bytes: The full PDF as bytes
            
        Returns:
            List of bytes, each representing a single-page PDF
        """
        reader = PdfReader(BytesIO(pdf_bytes))
        pages = []
        
        for i in range(len(reader.pages)):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            page_buffer = BytesIO()
            writer.write(page_buffer)
            pages.append(page_buffer.getvalue())
        
        logger.debug(f"Split PDF into {len(pages)} pages")
        return pages
    
    def upload_pdf_with_pages(
        self, 
        pdf_bytes: bytes, 
        filename: str,
        folder: str = "rubrics"
    ) -> Tuple[str, List[str]]:
        """
        Upload a PDF and its individual pages to GCS.
        
        Args:
            pdf_bytes: The PDF file as bytes
            filename: Original filename
            folder: GCS folder prefix
            
        Returns:
            Tuple of (full_pdf_path, list_of_page_paths)
        """
        # Generate unique session ID for this upload
        session_id = str(uuid.uuid4())[:8]
        base_name = os.path.splitext(filename)[0]
        
        # Upload full PDF
        full_pdf_path = f"{folder}/{session_id}/{filename}"
        self.upload_bytes(pdf_bytes, full_pdf_path)
        
        # Split and upload individual pages
        page_bytes_list = self.split_pdf_to_pages(pdf_bytes)
        page_paths = []
        
        for i, page_bytes in enumerate(page_bytes_list):
            page_path = f"{folder}/{session_id}/pages/{base_name}_page_{i + 1}.pdf"
            self.upload_bytes(page_bytes, page_path)
            page_paths.append(page_path)
        
        logger.info(f"Uploaded PDF with {len(page_paths)} pages to {folder}/{session_id}/")
        return full_pdf_path, page_paths
    
    def get_signed_urls_for_pages(
        self, 
        page_paths: List[str], 
        expiration_minutes: int = 60
    ) -> List[str]:
        """
        Generate signed URLs for a list of page paths.
        
        Args:
            page_paths: List of GCS object paths
            expiration_minutes: URL validity period
            
        Returns:
            List of signed URLs
        """
        return [
            self.generate_signed_url(path, expiration_minutes)
            for path in page_paths
        ]
    
    def delete_folder(self, folder_path: str) -> int:
        """
        Delete all objects in a folder (cleanup).
        
        Args:
            folder_path: The folder prefix to delete
            
        Returns:
            Number of objects deleted
        """
        blobs = list(self.bucket.list_blobs(prefix=folder_path))
        for blob in blobs:
            blob.delete()
        logger.info(f"Deleted {len(blobs)} objects from {folder_path}")
        return len(blobs)


# Singleton instance
_gcs_service: Optional[GCSService] = None


def get_gcs_service() -> GCSService:
    """Get or create the GCS service singleton."""
    global _gcs_service
    if _gcs_service is None:
        _gcs_service = GCSService()
    return _gcs_service