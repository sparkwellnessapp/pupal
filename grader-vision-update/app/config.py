"""
Configuration settings for Test Grader AI.
Loads settings from environment variables and .env file.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI settings
    openai_api_key: str
    openai_model: str = "gpt-4o"  # For text grading
    openai_vision_model: str = "gpt-4o"  # For vision/transcription tasks
    
    # Google Cloud settings
    google_cloud_project: str
    pubsub_topic_name: str = "gmail-test-grader"
    
    # Gmail settings (optional - only for legacy email-based grading)
    gmail_credentials_file: str = "config/gmail_credentials.json"
    gmail_token_file: str = "config/token.json"
    teacher_email: Optional[str] = None  # Only needed for email-based grading
    
    # Application settings
    app_env: str = "production"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"
    
    # CORS settings (comma-separated list of allowed origins)
    # IMPORTANT: CORS origins must be scheme://host:port only - NO paths!
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://vivi-assistant.com"
    
    # Grading settings
    confidence_threshold: float = 0.7
    max_concurrent_jobs: int = 3
    max_tokens_per_request: int = 4000
    temp_file_retention_hours: int = 1
    
    # Vision processing settings
    vision_dpi: int = 150  # DPI for PDF to image conversion
    vision_max_image_size: int = 1500  # Max dimension for images sent to VLM
    
    # Parallel transcription settings
    parallel_transcription_enabled: bool = True  # Feature flag for async parallel processing
    max_parallel_pages: int = 3  # Max concurrent VLM calls (reduced to avoid overwhelming API)
    vlm_timeout_seconds: int = 90  # Per-call timeout for VLM requests (increased for vision)
    vlm_max_retries: int = 2  # Number of retry attempts before degraded fallback
    vlm_retry_backoff_base: int = 3  # Exponential backoff base: 3s, 9s
    
    # LangSmith settings
    langchain_tracing_v2: Optional[str] = "false"
    langchain_endpoint: Optional[str] = "https://api.smith.langchain.com"
    langchain_api_key: Optional[str] = None
    langchain_project: Optional[str] = "Test-Grader-AI"
    
    # Database settings (Supabase/PostgreSQL)
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/grader"
    
    # Google Cloud Storage settings
    gcs_bucket_name: str = "grader-vision-pdfs"
    gcs_credentials_file: Optional[str] = None  # Uses default credentials if not set
    
    # Rubric Generator settings
    frontend_base_url: str = "https://vivi-assistant.com"  # Production domain
    rubric_generation_model: str = "gpt-4o"
    rubric_llm_timeout_seconds: int = 60
    
    # Grading Agent settings
    grading_timeout_seconds: int = 60  # Timeout for each LLM grading call
    grading_max_retries: int = 3       # Max retry attempts for transient failures
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


settings = Settings()
