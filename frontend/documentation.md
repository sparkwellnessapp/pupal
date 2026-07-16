# Pupil Frontend Documentation

Pupil is the React-based frontend for the Grader Vision system. It provides an intuitive interface for teachers to extract rubrics from PDFs, grade student tests in bulk, and review AI-generated results.

## Architecture

- **Framework**: [Next.js 14](https://nextjs.org/) (App Router)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Icons**: [Lucide React](https://lucide.dev/)
- **State Management**: Local React State (useState, useCallback) in main `page.tsx`

## Project Structure

```
grader-frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx            # Main application entry point & state orchestrator
│   │   ├── layout.tsx          # Root layout with fonts and providers
│   │   └── globals.css         # Tailwind directives and custom design tokens
│   ├── components/
│   │   ├── AnswerMappingPanel.tsx   # UI for mapping test pages to questions
│   │   ├── FileUpload.tsx           # Single file upload component
│   │   ├── MultiFileUpload.tsx      # Batch file upload component
│   │   ├── PageThumbnail.tsx        # Grid & individual page preview logic
│   │   ├── QuestionMappingPanel.tsx # UI for mapping rubric pages to criteria
│   │   ├── RubricEditor.tsx         # Editable list of extracted criteria
│   │   ├── RubricSelector.tsx       # Selection list for saved rubrics
│   │   └── GradingResults.tsx       # Dashboard for reviewing graded tests
│   └── lib/
│       └── api.ts              # Fetch-based client for FastAPI backend
```

## Core Flows

### 1. Rubric Creation Flow
1. **Upload**: User uploads a rubric PDF.
2. **Preview**: `previewRubricPdf` generates thumbnails.
3. **Map**: User uses `QuestionMappingPanel` to select which pages contain question text vs. criteria.
4. **Extract**: `extractRubric` sends mappings to backend for Vision AI parsing.
5. **Review**: User edits results in `RubricEditor`.
6. **Save**: `saveRubric` persists the rubric to the database.

### 2. Batch Grading Flow
1. **Select Rubric**: User chooses a saved rubric via `RubricSelector`.
2. **Upload Tests**: User uploads multiple student test PDFs.
3. **Map Answers**: For each test, user maps specific pages to rubric questions via `AnswerMappingPanel`.
4. **Grade**: `gradeSingleTest` is called sequentially for each test.
5. **Review**: Results are displayed in `GradingResults` with score breakdowns and AI explanations.

## API Integration

The frontend communicates with the backend via `src/lib/api.ts`. It uses the `NEXT_PUBLIC_API_URL` environment variable to locate the FastAPI server (defaults to `http://localhost:8080`).

Key interfaces include:
- `QuestionPageMapping`: Links PDF page indexes to questions.
- `ExtractedQuestion`: The structured data returned by Vision AI.
- `GradedTestResult`: The final grading data including scores and feedback.

## Setup & Development

Refer to the main project `README.md` for local setup instructions using `npm install` and `npm run dev`.
