"""
Temporary file storage service for rubric generator.

Handles storage of uploaded PDFs during the generation flow.
Files are automatically cleaned up after 1 hour.
"""
import os
import time
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional
import aiofiles

logger = logging.getLogger(__name__)

# Configuration
TEMP_DIR = Path(os.getenv("RUBRIC_TEMP_DIR", "/tmp/rubric_generator"))
TTL_SECONDS = int(os.getenv("RUBRIC_TEMP_TTL_SECONDS", "3600"))  # 1 hour default
CLEANUP_INTERVAL_SECONDS = 900  # 15 minutes
MAX_FILE_SIZE_MB = 25


class TempStorageService:
    """
    Temporary file storage for uploaded PDFs during generation flow.
    
    Features:
    - Content-hash based IDs for idempotency
    - Automatic TTL-based cleanup
    - Async file operations
    """
    
    def __init__(self):
        """Initialize service and ensure temp directory exists."""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"TempStorageService initialized with dir={TEMP_DIR}, TTL={TTL_SECONDS}s")
    
    async def store_pdf(self, pdf_bytes: bytes, original_filename: str = "upload.pdf") -> str:
        """
        Store PDF and return upload_id.
        
        File naming: {content_hash}_{timestamp}.pdf
        This ensures:
        - Same content = same hash prefix (idempotency)
        - Timestamp suffix prevents overwrites
        
        Args:
            pdf_bytes: The PDF file content
            original_filename: Original filename for logging
            
        Returns:
            upload_id: Unique identifier for this upload
            
        Raises:
            ValueError: If file is too large or empty
        """
        # Validate
        if not pdf_bytes:
            raise ValueError("קובץ ריק")
        
        size_mb = len(pdf_bytes) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"הקובץ גדול מדי ({size_mb:.1f}MB). המקסימום הוא {MAX_FILE_SIZE_MB}MB")
        
        # Validate PDF magic bytes
        if not pdf_bytes[:5] == b'%PDF-':
            raise ValueError("הקובץ אינו PDF תקין")
        
        # Generate content-based ID
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
        timestamp = int(time.time())
        upload_id = f"{content_hash}_{timestamp}"
        
        file_path = TEMP_DIR / f"{upload_id}.pdf"
        
        # Store file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(pdf_bytes)
        
        logger.info(f"Stored PDF: upload_id={upload_id}, size={size_mb:.2f}MB, original={original_filename}")
        
        return upload_id
    
    async def get_pdf(self, upload_id: str) -> Optional[bytes]:
        """
        Retrieve PDF by upload_id.
        
        Args:
            upload_id: The ID returned from store_pdf
            
        Returns:
            PDF bytes or None if not found/expired
        """
        # Sanitize upload_id to prevent path traversal
        safe_id = "".join(c for c in upload_id if c.isalnum() or c == '_')
        if safe_id != upload_id:
            logger.warning(f"Invalid upload_id format: {upload_id}")
            return None
        
        file_path = TEMP_DIR / f"{safe_id}.pdf"
        
        if not file_path.exists():
            logger.debug(f"PDF not found: {upload_id}")
            return None
        
        # Check if expired
        file_age = time.time() - file_path.stat().st_mtime
        if file_age > TTL_SECONDS:
            logger.info(f"PDF expired: {upload_id} (age={file_age:.0f}s)")
            # Clean it up
            try:
                file_path.unlink()
            except Exception:
                pass
            return None
        
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    
    async def delete_pdf(self, upload_id: str) -> bool:
        """
        Delete a PDF by upload_id.
        
        Args:
            upload_id: The ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        safe_id = "".join(c for c in upload_id if c.isalnum() or c == '_')
        file_path = TEMP_DIR / f"{safe_id}.pdf"
        
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted PDF: {upload_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete PDF {upload_id}: {e}")
        
        return False
    
    async def cleanup_expired(self) -> int:
        """
        Delete all files older than TTL.
        
        Returns:
            Number of files deleted
        """
        deleted = 0
        cutoff = time.time() - TTL_SECONDS
        
        try:
            for file_path in TEMP_DIR.glob("*.pdf"):
                try:
                    if file_path.stat().st_mtime < cutoff:
                        file_path.unlink()
                        deleted += 1
                        logger.debug(f"Cleaned up expired file: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path.name}: {e}")
        except Exception as e:
            logger.error(f"Cleanup scan failed: {e}")
        
        return deleted
    
    def get_stats(self) -> dict:
        """Get storage statistics for monitoring."""
        try:
            files = list(TEMP_DIR.glob("*.pdf"))
            total_size = sum(f.stat().st_size for f in files)
            
            return {
                "file_count": len(files),
                "total_size_mb": total_size / (1024 * 1024),
                "temp_dir": str(TEMP_DIR),
                "ttl_seconds": TTL_SECONDS,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Global instance
_temp_storage: Optional[TempStorageService] = None


def get_temp_storage() -> TempStorageService:
    """Get or create the global TempStorageService instance."""
    global _temp_storage
    if _temp_storage is None:
        _temp_storage = TempStorageService()
    return _temp_storage


async def cleanup_worker():
    """
    Background worker that cleans up expired temp files.
    
    Runs every 15 minutes. Should be started on app startup.
    """
    storage = get_temp_storage()
    logger.info("Temp storage cleanup worker started")
    
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            deleted = await storage.cleanup_expired()
            if deleted > 0:
                logger.info(f"Temp storage cleanup: deleted {deleted} expired files")
        except asyncio.CancelledError:
            logger.info("Temp storage cleanup worker stopped")
            break
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
            # Continue running despite errors


def start_cleanup_worker() -> asyncio.Task:
    """
    Start the cleanup worker as a background task.
    
    Call this from app startup:
        @app.on_event("startup")
        async def startup():
            start_cleanup_worker()
    
    Returns:
        The asyncio Task (can be cancelled on shutdown)
    """
    return asyncio.create_task(cleanup_worker())
