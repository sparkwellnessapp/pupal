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
| **User-Centric UI** | Modern React-based interface for effortless review and approval |

## Workflow

```mermaid
graph TD
    A[Upload Rubric PDF] --> B[AI Extracts Questions & Criteria]
    B --> C[Teacher Validates Rubric]
    C --> D[Upload Student Tests]
    D --> E[AI Grades Each Answer]
    E --> F[Teacher Validates Grades]
    F --> G[Download Annotated PDFs]
```

---

## Current State

### Project Structure

The project is split into two main components:
- **Backend**: FastAPI service for AI processing and data management.
- **Frontend**: Next.js application for the user interface.

#### Backend (FastAPI)
```
grader-vision-update/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # Supabase (PostgreSQL) configuration
│   ├── config.py            # Settings and env management
│   ├── api/v0/grading.py    # Grading API endpoints
│   ├── models/grading.py    # SQLAlchemy models (Rubric, GradedTest, etc.)
│   ├── schemas/grading.py   # Pydantic validation schemas
│   └── services/            # Business logic layer
│       ├── rubric_service.py      # Rubric extraction logic
│       ├── grading_service.py     # Test grading orchestration
│       ├── annotation_service.py  # PDF annotation & GCS uploads
│       ├── document_parser.py     # Vision-based PDF to text extraction
│       ├── grading_agent.py       # LangGraph-powered grading agent
│       ├── pdf_annotator.py       # ReportLab PDF generator
│       └── pdf_preview_service.py # PDF to image thumbnail service
```

#### Frontend (Next.js)
```
grader-frontend/
├── src/
│   ├── app/                 # Next.js App Router (page.tsx)
│   ├── components/          # Reusable UI components (RubricEditor, GradingResults, etc.)
│   └── lib/                 # Utility functions and API client (api.ts)
```

### API Endpoints (`/api/v0/grading/...`)

| Endpoint | Method | Purpose | Implementation |
|----------|--------|---------|----------------|
| `/list_rubrics` | `GET` | List all saved rubrics | ✅ Implemented |
| `/preview_rubric_pdf` | `POST` | Generate thumbnails for rubric PDF | ✅ Implemented |
| `/extract_rubric` | `POST` | Extract structured rubric using Vision AI | ✅ Implemented |
| `/save_rubric` | `POST` | Save reviewed rubric to database | ✅ Implemented |
| `/get_rubric` | `GET` | Retrieve rubric by ID | ✅ Implemented |
| `/preview_student_test_pdf` | `POST` | Thumbnails and name extraction for student test | ✅ Implemented |
| `/grade_tests` | `POST` | Batch grade multiple student tests | ✅ Implemented |
| `/create_grade_test` | `POST` | Grade a single student test | ✅ Implemented |
| `/get_graded_tests` | `GET` | List all graded tests for a rubric | ✅ Implemented |
| `/annotate_pdf_test` | `POST` | Create annotated PDF for a graded test | ✅ Implemented |
| `/get_graded_pdfs` | `GET` | List all graded PDFs for a rubric | ✅ Implemented |

### Core Services

- **Vision-based PDF parsing** - GPT-4o processes PDF screenshots to extract text/code with high accuracy.
- **LangGraph grading agent** - Advanced multi-step grading logic that maps student answers to rubric criteria.
- **PDF annotation** - Generates profesional graded PDFs with cover pages and inline feedback.
- **RTL Support** - Built-in support for Hebrew (RTL) in both the UI and generated PDFs.

---

## Environment Variables

### Backend (`grader-vision-update/.env`)
```env
# AI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Infrastructure
GOOGLE_CLOUD_PROJECT=your-project
GCS_BUCKET_NAME=grader-vision-pdfs
TEACHER_EMAIL=your-email@example.com

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
```

### Frontend (`grader-frontend/.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8080
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (Async), Pydantic, PostgreSQL
- **Frontend**: Next.js 14, React, Tailwind CSS, Lucide React
- **AI**: OpenAI GPT-4o (Vision), LangGraph
- **PDF**: pdf2image, ReportLab, PyPDF2
- **Storage**: Google Cloud Storage (GCS)
- **Infrastructure**: Docker, Google Cloud Run

---

## Local Development

Follow these steps to set up and run the application on your local machine.

### System Dependencies

1. **Python 3.11+**: Ensure you have Python installed.
2. **Node.js 18+**: Required for the frontend.
3. **Poppler**: Required by `pdf2image` for PDF processing.
   - **Windows**: Download from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) and add the `bin` folder to your system PATH.
   - **macOS**: `brew install poppler`
   - **Linux**: `sudo apt-get install poppler-utils`

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd grader-vision-update
   ```
2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment**:
   Create a `.env` file based on the template in the [Environment Variables](#environment-variables) section.
5. **Run the server**:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd grader-frontend
   ```
2. **Install dependencies**:
   ```bash
   npm install
   ```
3. **Configure environment**:
   Create a `.env.local` file with:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8080
   ```
4. **Run the development server**:
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:3000`.

---

## Next Steps

### 1. Finalize GCS Integration
- [ ] Complete `upload_pdf_to_gcs` and `download_pdf_from_gcs` implementations in `annotation_service.py`.
- [ ] Implement signed URL generation for secure PDF downloads.

### 2. Infrastructure & Deployment
- [ ] Configure CI/CD pipeline for Cloud Run deployment.
- [ ] Set up Supabase project with automated migrations.
- [ ] Verify GCS bucket permissions.

### 3. UX Enhancements
- [ ] Add real-time grading progress updates via WebSockets or polling.
- [ ] Improve student name detection accuracy.
- [ ] Add support for "re-grading" specific questions.
