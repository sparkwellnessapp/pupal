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
    openai_model: str = "gpt-4-turbo-preview"  # For text grading
    openai_vision_model: str = "gpt-4o"  # For vision/transcription tasks
    
    # Google Cloud settings
    google_cloud_project: str
    pubsub_topic_name: str = "gmail-test-grader"
    
    # Gmail settings
    gmail_credentials_file: str = "config/gmail_credentials.json"
    gmail_token_file: str = "config/token.json"
    teacher_email: str
    
    # Application settings
    app_env: str = "production"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"
    
    # Grading settings
    confidence_threshold: float = 0.7
    max_concurrent_jobs: int = 3
    max_tokens_per_request: int = 4000
    temp_file_retention_hours: int = 1
    
    # Vision processing settings
    vision_dpi: int = 150  # DPI for PDF to image conversion
    vision_max_image_size: int = 1500  # Max dimension for images sent to VLM
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


settings = Settings()
