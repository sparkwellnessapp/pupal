# Grader Vision - AI-Powered Test Grading Assistant

A web application that helps teachers grade student tests using AI, with a human-in-the-loop validation workflow.

## Purpose

Grader Vision is designed to **assist** teachers in grading, not replace them. The AI handles the tedious work of:
- Reading and transcribing handwritten/typed student answers
- Matching answers against rubric criteria
- Suggesting grades with explanations

**The teacher always has final approval.** Every AI-generated result goes through a validation step where the teacher can review, adjust, and approve before finalizing grades.

## Key Principles

| Principle | Description |
|-----------|-------------|
| **Validation-Based** | Teacher validates all transcriptions and grades before they're finalized |
| **Transparent** | AI shows confidence levels and reasoning for each grading decision |
| **Efficient** | Reduces grading time while maintaining teacher control |
| **Simple UI** | Intuitive interface for reviewing and approving AI suggestions |

## Workflow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  1. Upload      │ ──► │  2. AI Extracts  │ ──► │  3. Teacher     │
│  Rubric PDF     │     │  Questions +     │     │  Validates      │
│                 │     │  Criteria        │     │  Rubric         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
         ┌────────────────────────────────────────────────┘
         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  4. Upload      │ ──► │  5. AI Grades    │ ──► │  6. Teacher     │
│  Student Tests  │     │  Each Answer     │     │  Validates      │
│                 │     │                  │     │  Grades         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
         ┌────────────────────────────────────────────────┘
         ▼
┌─────────────────┐
│  7. Download    │
│  Annotated PDFs │
└─────────────────┘
```

---

## Current State

### Backend Structure (FastAPI)

```
app/
├── main.py              # FastAPI entry point
├── database.py          # Supabase/PostgreSQL setup
├── config.py            # Environment configuration
├── api/v0/grading.py    # 7 API endpoints (placeholder logic)
├── models/grading.py    # Rubric, GradedTest, GradedTestPdf
├── schemas/grading.py   # Pydantic request/response schemas
└── services/            # Business logic layer
    ├── rubric_service.py
    ├── grading_service.py
    ├── annotation_service.py
    ├── document_parser.py   # Vision AI PDF parsing
    ├── grading_agent.py     # LangGraph grading agent
    └── pdf_annotator.py     # PDF annotation
```

### API Endpoints

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `POST /preview_rubric_pdf` | Split PDF into pages for selection | Placeholder |
| `POST /extract_rubric` | Extract rubric with page mappings | Placeholder |
| `GET /get_rubric` | Retrieve rubric by ID | Placeholder |
| `POST /create_grade_test` | Grade student test | Placeholder |
| `GET /get_graded_tests_jsons` | Get graded test results | Placeholder |
| `POST /annotate_pdf_test` | Create annotated PDF | Placeholder |
| `GET /get_graded_tests_pdfs` | Get annotated PDFs | Placeholder |

### Core Services (Implemented)

- **Vision-based PDF parsing** - GPT-4o extracts text/code from PDF screenshots
- **LangGraph grading agent** - Grades answers against rubric criteria
- **PDF annotation** - Creates graded PDFs with cover pages

---

## Next Steps

### 1. Backend Implementation
- [ ] Implement endpoint logic in `api/v0/grading.py`
- [ ] Implement GCS upload/download in `annotation_service.py`
- [ ] Add PDF preview service (split PDF to thumbnails)
- [ ] Set up Supabase database and run migrations

### 2. Frontend Development
- [ ] Create React/Next.js frontend
- [ ] Rubric upload + page selection UI
- [ ] Rubric validation/editing interface
- [ ] Student test upload (batch)
- [ ] Grading results review/validation UI
- [ ] Download annotated PDFs

### 3. Infrastructure
- [ ] Update Dockerfile for new structure
- [ ] Deploy to Cloud Run
- [ ] Set up Supabase project
- [ ] Configure GCS bucket for PDFs

---

## Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
GCS_BUCKET_NAME=your-bucket

# Optional
GOOGLE_CLOUD_PROJECT=your-project
LOG_LEVEL=INFO
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), Pydantic
- **Database**: Supabase (PostgreSQL)
- **Storage**: Google Cloud Storage
- **AI**: OpenAI GPT-4o (vision), LangGraph
- **PDF Processing**: pdf2image, PyPDF2, ReportLab
