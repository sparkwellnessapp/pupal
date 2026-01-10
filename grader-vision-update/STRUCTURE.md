# Backend Structure - Grader Vision

## Overview

This is a FastAPI-based backend for automated grading of handwritten programming tests using Vision AI (GPT-4o). The system extracts rubrics from PDF documents and grades student submissions against them.

## Directory Structure

```
grader-vision-update/
├── app/                          # Main application package
│   ├── api/                      # API endpoints (FastAPI routers)
│   │   └── v0/                   # API version 0
│   │       ├── auth.py           # Authentication endpoints (login, register, Supabase)
│   │       ├── grading.py        # Main grading endpoints (rubrics, tests, grading)
│   │       └── users.py          # User management endpoints
│   │
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── grading.py            # Rubric, GradedTest, GradedTestPdf models
│   │   ├── user.py               # User, Subscription models
│   │   ├── raw_rubric.py         # Raw rubric storage
│   │   ├── raw_graded_test.py    # Raw graded test storage
│   │   ├── rubric_share.py       # Rubric sharing (teacher collaboration)
│   │   └── subject_matter.py     # Subject/course definitions
│   │
│   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── grading.py            # Rubric, Test, Criterion schemas
│   │   └── user.py               # User-related schemas
│   │
│   ├── services/                 # Business logic layer
│   │   ├── rubric_service.py            # Rubric extraction orchestration (MAIN)
│   │   ├── hybrid_rubric_extractor.py   # Hybrid PDF+VLM extraction
│   │   ├── pdf_text_extractor.py        # PDF text extraction (pdfplumber)
│   │   ├── vlm_rubric_extractor.py      # VLM-only rubric extraction
│   │   ├── rubric_verifier.py           # Extraction validation
│   │   ├── handwriting_transcription_service.py  # Handwriting → text (VLM)
│   │   ├── grading_service.py           # Grading logic
│   │   ├── grading_agent.py             # LLM-based grading agent
│   │   ├── document_parser.py           # PDF → images, VLM calls
│   │   ├── pdf_preview_service.py       # PDF thumbnails for UI
│   │   ├── pdf_annotator.py             # Generate annotated grade PDFs
│   │   ├── annotation_service.py        # PDF annotation wrapper (unused)
│   │   ├── gcs_service.py               # Google Cloud Storage operations
│   │   └── auth_service.py              # Supabase auth integration
│   │
│   ├── config.py                 # Settings from environment variables
│   ├── database.py               # Async SQLAlchemy + PostgreSQL
│   └── main.py                   # FastAPI app entry point
│
├── migrations/                   # Alembic database migrations
├── deprecated/                   # Old code kept for reference
├── .env                          # Environment variables (secrets)
├── requirements.txt              # Python dependencies
└── Dockerfile                    # Container build
```

## Core Services

### 1. Rubric Extraction Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    rubric_service.py                         │
│                  (Main Orchestrator)                         │
└──────────────────────────────────┬───────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ pdf_text_extractor│    │ vlm_rubric_       │    │ rubric_verifier   │
│ (PDF Layer)       │    │ extractor         │    │ (Validation)      │
│ - pdfplumber      │    │ (VLM Layer)       │    │                   │
│ - Point detection │    │ - GPT-4o Vision   │    │ - Cross-check     │
│ - Table parsing   │    │ - Descriptions    │    │ - Confidence      │
└───────────────────┘    └───────────────────┘    └───────────────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
                    ┌───────────────────────────┐
                    │ hybrid_rubric_extractor   │
                    │ (Fusion Layer)            │
                    │ - PDF + VLM merge         │
                    │ - Confidence scoring      │
                    └───────────────────────────┘
```

### 2. Handwriting Transcription

```
┌─────────────────────────────────────────────────────────────┐
│          handwriting_transcription_service.py               │
│                                                             │
│  PDF → Images → VLM (GPT-4o) → Structured JSON             │
│                                                             │
│  Features:                                                  │
│  - Parallel page processing (ThreadPoolExecutor)           │
│  - Grounded transcription (visual + text together)         │
│  - Consistency verification with retry                     │
│  - Confidence scoring per answer                           │
└─────────────────────────────────────────────────────────────┘
```

### 3. Grading Pipeline

```
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Rubric        │ +  │ Student       │ →  │ Grading       │
│ (from DB)     │    │ Answers       │    │ Agent         │
└───────────────┘    │ (transcribed) │    │ (LLM)         │
                     └───────────────┘    └───────────────┘
                                                 │
                                                 ▼
                                    ┌───────────────────────┐
                                    │ GradedTest            │
                                    │ - Scores per criterion│
                                    │ - Explanations        │
                                    │ - Confidence levels   │
                                    └───────────────────────┘
```

## API Endpoints (v0)

### Rubric Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v0/preview_rubric_pdf` | Upload PDF, get page thumbnails |
| POST | `/v0/extract_rubric` | Extract rubric with page mappings |
| POST | `/v0/save_rubric` | Save extracted rubric to DB |
| GET | `/v0/rubrics` | List all rubrics |
| GET | `/v0/rubrics/{id}` | Get rubric by ID |

### Student Test Processing
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v0/preview_student_test` | Upload student PDF, get pages |
| POST | `/v0/transcribe_handwritten_test` | OCR handwritten code |
| POST | `/v0/grade_with_edited_transcription` | Grade edited transcription |

### Grading
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v0/grade_tests` | Batch grade multiple tests |
| GET | `/v0/graded_tests/{rubric_id}` | List graded tests |
| POST | `/v0/annotate_pdf_test` | Generate annotated PDF |

## Database Models

```
┌─────────────────┐       ┌─────────────────┐
│     Rubric      │       │    GradedTest   │
├─────────────────┤       ├─────────────────┤
│ id (UUID)       │←──────│ rubric_id       │
│ user_id         │       │ student_name    │
│ name            │       │ total_score     │
│ description     │       │ graded_json     │
│ rubric_json     │       │ created_at      │
│ total_points    │       └─────────────────┘
│ created_at      │
└─────────────────┘
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│  RubricShare    │       │      User       │
├─────────────────┤       ├─────────────────┤
│ rubric_id       │       │ id (UUID)       │
│ shared_with_id  │       │ email           │
│ permission      │       │ subscription    │
└─────────────────┘       └─────────────────┘
```

## Key Technologies

| Technology | Purpose |
|------------|---------|
| **FastAPI** | Web framework |
| **SQLAlchemy** | Async ORM |
| **PostgreSQL** | Database (via Supabase) |
| **OpenAI GPT-4o** | Vision AI for extraction |
| **pdfplumber** | PDF text extraction |
| **pdf2image** | PDF → images |
| **ReportLab** | PDF generation |
| **LangSmith** | LLM observability |
| **Google Cloud Storage** | File storage |
| **Supabase** | Auth + hosted Postgres |

## Environment Variables

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql+asyncpg://...

# Supabase Auth
SUPABASE_URL=https://...
SUPABASE_KEY=...
SUPABASE_JWT_SECRET=...

# Google Cloud Storage
GCS_BUCKET_NAME=...
GOOGLE_APPLICATION_CREDENTIALS=...

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
```

## Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload --port 8080

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Files NOT in Active Use

| File | Status | Notes |
|------|--------|-------|
| `app/grading_orchestrator.py` | ❌ Unused | Legacy orchestrator |
| `app/pdf_annotator.py` | ❌ Unused | Only used by orchestrator |
| `app/services/annotation_service.py` | ❌ Unused | Wrapper, never imported |
| `deprecated/*` | ❌ Deprecated | Old implementations |
