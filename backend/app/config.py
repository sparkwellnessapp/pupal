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

    # Transcription VLM provider settings (S4)
    transcription_vlm_provider: str = "openai"
    transcription_vlm_model: str = "gpt-4o"
    transcription_debug_dump: bool = False  # gate debug file writes in production

    # Transcription engine selector.
    #   "legacy"    — HandwritingTranscriptionService (S4 architecture; default)
    #   "two_phase" — P1 perception + P2 segmentation + cross-reader trust layer
    #                 (the eval-suite-validated pipeline; see
    #                 app/services/transcription/two_phase/ + two_phase_engine.py).
    #                 Requires GEMINI_API_KEY + ANTHROPIC_API_KEY + OPENAI_API_KEY.
    transcription_engine: str = "legacy"

    # S11: Batch concurrency cap.
    # batch_cap(5) × grader_scope_cap(5) = 25 worst-case concurrent LLM calls.
    batch_max_concurrent_tests: int = 5

    # S11: Logprob span-min thresholds for vlm_low_logprob flagging.
    # logprob scale: 0.0 = certain, -∞ = impossible. -2.0 ≈ 13.5% token probability.
    # Calibration guesses — E2 will tune from real teacher corrections.
    logprob_span_threshold: float = -2.0   # any sliding window below this → flag
    logprob_span_window: int = 5           # sliding-window width in tokens

    # S11: Per-answer VLM confidence threshold for flagging.
    # Shadows the older confidence_threshold; used specifically by batch triage.
    transcription_confidence_threshold: float = 0.8

    # PR-1: async rubric-extraction job lifecycle.
    # Execution substrate for extraction jobs (ADR-1):
    #   "cloud_tasks" — enqueue a Cloud Tasks HTTP task targeting
    #                   /internal/extraction-jobs/{id}/run; extraction runs
    #                   INSIDE that request so CPU is guaranteed (prod default).
    #   "inline"      — asyncio.create_task in-process. LOCAL DEV ONLY: under
    #                   prod Cloud Run config (CPU throttled post-response,
    #                   min-instances 0) an in-process background task is
    #                   throttled/killed after the response returns.
    extraction_execution_mode: str = "cloud_tasks"
    # Heartbeat TTL: an 'extracting' job whose updated_at is older than this is
    # reported stale (instance died mid-job) and becomes retryable.
    extraction_heartbeat_ttl_minutes: int = 15
    # Cloud Tasks queue + OIDC identity for the task → /internal call.
    cloud_tasks_location: str = "europe-west1"
    cloud_tasks_queue: str = "rubric-extraction"
    cloud_tasks_invoker_sa: Optional[str] = None
    # Base URL of THIS service (Cloud Run URL) — target for enqueued tasks.
    service_base_url: Optional[str] = None
    # Shared-secret fallback auth for /internal/extraction-jobs/{id}/run
    # (inline/dev mode, where no OIDC token exists).
    internal_task_token: Optional[str] = None
    # Max accepted rubric DOCX upload size.
    extraction_max_upload_mb: int = 15

    # PR-2: the extraction task's total wall budget, in seconds.
    # 840 = Cloud Run request timeout (900) − 60s reserve. The runner measures its
    # OWN pre-work (GCS download etc.) against a monotonic t0 and passes
    # `840 − elapsed` down as the pipeline deadline — pre-work is MEASURED, never
    # assumed away (its library bound is 120s, which a flat 60s reserve would not
    # have covered). Keep in lockstep with the Cloud Run --timeout and the Cloud
    # Tasks dispatchDeadline: budget < request timeout, always.
    extraction_task_budget_s: float = 840.0

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
    
    # Classifier LLM settings
    # Primary model for DOCX rubric classification and verification.
    # gpt-5.2 is OpenAI's strongest reasoning model as of Feb 2026.
    # If the API returns an unknown-model error, verify the exact string at
    # https://platform.openai.com/docs/models and update here.
    CLASSIFIER_MODEL_OPENAI: str    = "gpt-5.2-2025-12-11"
    CLASSIFIER_MODEL_ANTHROPIC: str = "claude-sonnet-4-20250514"

    # 8192 covers the largest rubrics (multi-question, many sub-questions,
    # full example solutions). 4096 was the previous limit and caused
    # Q2+ content to be silently truncated mid-generation.
    CLASSIFIER_MAX_TOKENS: int = 8192

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


settings = Settings()


# =============================================================================
# LangSmith tracing interface
# =============================================================================

# Master toggle for LangSmith tracing.
# - False: disable tracing for all nodes below, regardless of their individual flags.
# - True:  enable tracing only for nodes whose *_trace flag is True.
langsmith_interface_trace: bool = True

# --- DOCX rubric pipeline (docx_rubric_service / classifier / enhancer) ---

# Layer: Orchestrator (DOCX rubric extraction)
# Input: DOCX bytes + ExtractionConfig
# Output: ExtractionResult (includes ExtractRubricResponse, RubricStructure, metadata)
# Purpose: Top-level DOCX rubric extraction chain.
docx_rubric_service_extract_rubric_from_docx_trace: bool = False

# Layer: 3 — Classifier (document header metadata)
# Input: [DOCUMENT_HEADER] text slice from renderer
# Output: HeaderMetadataResponse (test_title, test_date, evidence)
# Purpose: Extracts grounded test title/date before classification.
docx_classifier_call_llm_header_metadata_trace: bool = False

# Layer: 3 — Classifier (per-question chunk classification)
# Input: Prompt with TEXT/TABLE chunks for one question
# Output: QuestionChunkClassificationResponse (roles, table types, row mappings)
# Purpose: Classifies question structure and tables in chunk pipeline.
docx_classifier_call_llm_chunk_classification_trace: bool = False

# Layer: 3 — Classifier (full-document classification)
# Input: Full rendered document text
# Output: ClassificationResponse dict (questions, tables, row_to_sub_question)
# Purpose: Legacy / fallback full-document rubric classification.
docx_classifier_call_llm_classification_trace: bool = False

# Layer: 3 — Classifier (verification)
# Input: Verification prompt with rendered document + classification JSON
# Output: VerificationResult dict (is_valid, corrections)
# Purpose: Audits classifier output against the source document.
docx_classifier_call_llm_verification_trace: bool = False

# Layer: 4 — Question enhancer (Call 1: purpose + criteria rebalancing)
# Input: QuestionEnhancementContext + raw criteria
# Output: QuestionEnhancementResult (purpose + complete, normalized criteria)
# Purpose: Infers question purpose and locks teacher criteria.
question_enhancer_call_enhance_question_criteria_trace: bool = False

# Layer: 4 — Question enhancer (Step 1B: proposals)
# Input: QuestionEnhancementContext + base criteria
# Output: ProposalResult (proposed criteria + enhanced_distribution)
# Purpose: Proposes additional criteria and point redistribution for teacher review.
question_enhancer_call_propose_criteria_trace: bool = False

# Layer: 4 — Question enhancer (Call 2: rules + levels)
# Input: One criterion description + context (purpose, SQ text, solution)
# Output: CriterionRulesResult (rules, levels, evaluation_guidance)
# Purpose: Generates reduction rules, levels, and guidance per criterion.
question_enhancer_call_generate_rules_and_levels_trace: bool = False

# Layer: 4 — Question enhancer (main pipeline entry)
# Input: raw_criteria + QuestionEnhancementContext
# Output: EnhancementOutput (base_criteria + optional proposals)
# Purpose: Full ontological enhancement chain for DOCX rubric.
question_enhancer_enhance_criteria_for_question_trace: bool = False

# Layer: 4 — Question enhancer (post-acceptance)
# Input: accepted criteria list (+ context)
# Output: Enhanced criteria list with rules/levels
# Purpose: Runs Call 2 on teacher-accepted criteria proposals.
question_enhancer_enhance_accepted_criteria_trace: bool = False


# --- Test Grader agent (graph + nodes) ---

# Layer: Grading graph node (evaluation LLM call)
# Input: GradingAgentState (current_criterion + student answer + feedback)
# Output: Updated state with pending_evaluation JSON
# Purpose: Core LLM grading call for a single rubric criterion.
test_grader_evaluate_criterion_llm_trace: bool = False

# Layer: Grading graph node (validation + routing)
# Input: GradingAgentState with pending_evaluation and contract
# Output: Updated state (accept / retry / skip decision)
# Purpose: Validates LLM grading output and steers ReAct loop.
test_grader_validate_response_trace: bool = True

# Layer: Grading graph entrypoint
# Input: Contract, student answers, metadata
# Output: Final grading state with graded_test_draft
# Purpose: Top-level grading workflow chain for a full test.
test_grader_run_grading_agent_trace: bool = True


# --- PDF rubric generator (rubric_generator_service) ---

# Layer: Question detection (PDF → questions)
# Input: PDF bytes
# Output: List[DetectedQuestion] (numbers, texts, SQ IDs, suggested points)
# Purpose: Detects exam questions and basic structure from PDF text.
rubric_generator_service_detect_questions_from_pdf_trace: bool = False

# Layer: Criteria generation per question
# Input: DetectedQuestion + total_points + context
# Output: ExtractedQuestion with generated criteria and rules
# Purpose: LLM-based rubric synthesis for a single question.
rubric_generator_service_generate_criteria_for_question_trace: bool = False

# Layer: Full rubric generation
# Input: List[DetectedQuestion] with points
# Output: LegacyExtractRubricResponse for RubricEditor
# Purpose: Generates a complete rubric from detected questions.
rubric_generator_service_generate_full_rubric_trace: bool = False


# --- PDF rubric extraction / enhancement (rubric_service) ---

# Layer: VLM example solution extraction
# Input: Base64 page images + context
# Output: List[str] of sanitized example solutions
# Purpose: Extracts teacher example code solutions from rubric PDFs.
rubric_service_extract_example_solutions_from_pages_trace: bool = False

# Layer: Enhanced criteria extraction (3-stage pipeline)
# Input: PDF bytes + images + page indexes + context
# Output: Dict with criteria list, total_points, status, example_solutions
# Purpose: Extracts and enhances rubric criteria from PDF tables.
rubric_service_extract_criteria_enhanced_trace: bool = False

# Layer: Question text extraction (PDF text → questions)
# Input: Full PDF text + question numbers
# Output: Dict with question texts and SQ breakdown
# Purpose: Extracts clean question stems and sub-question texts from PDFs.
rubric_service_extract_all_questions_trace: bool = False

# Layer: Rubric extraction with page mappings
# Input: PDF bytes + QuestionPageMappings + metadata
# Output: LegacyExtractRubricResponse with questions and criteria
# Purpose: High-level rubric extraction pipeline for PDFs.
rubric_service_extract_rubric_with_page_mappings_trace: bool = False


# --- VLM rubric extractor (vlm_rubric_extractor) ---

# Layer: VLM criteria extraction
# Input: Base64 rubric images + context
# Output: VLMCriteriaResult (criteria, total_points, status)
# Purpose: Vision-based rubric table interpretation.
vlm_rubric_extractor_extract_criteria_trace: bool = False

# Layer: VLM question text extraction
# Input: Base64 question images + question_number
# Output: VLMQuestionResult (text, total_points, SQs, status)
# Purpose: Vision-based extraction of question text and sub-questions.
vlm_rubric_extractor_extract_question_text_trace: bool = False


# --- Vision document parser (document_parser) ---

# Layer: Student name extraction (vision)
# Input: Base64 first-page image
# Output: Optional student name string
# Purpose: Extracts student name from test header.
document_parser_extract_student_name_from_page_trace: bool = False

# Layer: Student code extraction (vision)
# Input: Base64 answer page images + question/sub-question ids
# Output: Dict with answer_text, has_code, metadata
# Purpose: Transcribes student code answers from scanned tests.
document_parser_extract_code_from_pages_trace: bool = False

