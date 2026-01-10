# Frontend Project Structure

This document outlines the structure of the `grader-frontend` application, a generic React-based grading interface built with Next.js 14 (App Router).

## 📂 High-Level Directory Structure

```
grader-frontend/
├── .env.local              # Local environment variables
├── .gitignore              # Git ignore rules
├── documentation.md        # Project documentation
├── next-env.d.ts           # Next.js TypeScript declarations
├── next.config.js          # Next.js configuration
├── package-lock.json       # Dependency lock file
├── package.json            # Project dependencies and scripts
├── postcss.config.js       # PostCSS configuration
├── tailwind.config.ts      # Tailwind CSS configuration
├── tsconfig.json           # TypeScript configuration
├── public/                 # Static assets (images, logos)
│   ├── VIVI-logo-no-slogan.png
│   ├── vivi-logo-new.png
│   ├── vivi-logo-no-background-no-slogan.png
│   ├── vivi-logo-no-background.png
│   ├── vivi-logo-with-backkground.png
│   └── vivi-logo.png
└── src/
    ├── app/                # Next.js App Router
    │   ├── login/
    │   │   └── page.tsx    # Login page
    │   ├── my-graded-tests/
    │   │   └── page.tsx    # Graded tests history page
    │   ├── my-rubrics/
    │   │   └── page.tsx    # Saved rubrics management page
    │   ├── profile/
    │   │   └── page.tsx    # User profile page
    │   ├── signup/
    │   │   └── page.tsx    # Signup page
    │   ├── globals.css     # Global styles
    │   ├── layout.tsx      # Root layout
    │   └── page.tsx        # Main dashboard / grading flow
    ├── components/         # React components
    │   ├── AnswerMappingPanel.tsx    # Student answer mapping UI
    │   ├── FileUpload.tsx            # Single file upload component
    │   ├── GradingResults.tsx        # Results display and PDF generation
    │   ├── MultiFileUpload.tsx       # Batch file upload component
    │   ├── PageThumbnail.tsx         # PDF page preview component
    │   ├── QuestionMappingPanel.tsx  # Question-to-page mapping UI
    │   ├── RubricEditor.tsx          # Rubric creation/editing UI
    │   ├── RubricSelector.tsx        # Rubric selection UI
    │   ├── SidebarLayout.tsx         # Main app shell layout
    │   └── TranscriptionReviewPage.tsx # Handwritten transcription review UI
    └── lib/                # Shared utilities
        ├── api.ts          # API client and type definitions
        └── auth.tsx        # Authentication logic
```

## 🏗️ Core Application (`src/app/`)

*   **`layout.tsx`**: The root layout component. Wraps the entire application, providing global styles (font, standard CSS) and metadata.
*   **`globals.css`**: Global CSS styles and Tailwind directives.
*   **`page.tsx`**: The main "Dashboard" and grading flow orchestrator. This is a large, stateful component that manages the entire grading lifecycle:
    *   **Modes**: Handwritten vs. Printed test grading.
    *   **Steps**: Rubric selection -> File Upload -> Mapping/Transcription -> Review -> Grading -> Results.
    *   **State**: Manages upload state, current rubric, mappings, and progress.
*   **`auth.tsx`**: (In `lib`, but relevant here) Contains authentication context and hooks.
*   **Sub-routes**:
    *   `login/`: Login page.
    *   `signup/`: Signup page.
    *   `profile/`: User profile management.
    *   `my-rubrics/`: List of user's saved rubrics.
    *   `my-graded-tests/`: History of graded tests.

## 🧩 Components (`src/components/`)

### Core Layout & Navigation
*   **`SidebarLayout.tsx`**: The main application shell containing the sidebar navigation and content area. Wraps most pages.

### Grading Flow Components (Printed & General)
*   **`RubricSelector.tsx`**: Component for selecting existing rubrics or starting new ones.
*   **`RubricEditor.tsx`**: A complex interface for creating and editing grading rubrics (questions, criteria, points).
*   **`FileUpload.tsx` & `MultiFileUpload.tsx`**: Components for handling PDF file uploads. `MultiFileUpload` handles batch uploads.
*   **`PageThumbnail.tsx`**: Renders a preview of a PDF page (base64 or URL). Used extensively in reviews and results.
*   **`QuestionMappingPanel.tsx`**:  Used in the "Page Mapping" step for printed tests to assign specific PDF pages to rubric questions.
*   **`AnswerMappingPanel.tsx`**: Used to map student answers to questions.

### Vision & Transcription Components (Handwritten)
*   **`TranscriptionReviewPage.tsx`**: A critical component for the vision-based handwriting flow.
    *   **Purpose**: Allows teachers to review and correct AI transcriptions pending styling validation or low-confidence alerts.
    *   **Features**: Split-screen view (Original PDF vs. Transcription), streaming support (progressive text display), editing capabilities, and "Continue" logic.
    *   **Streaming**: Supports real-time updates via props (`isStreaming`, `streamingPhase`, `streamingText`).

### Results & Visualization
*   **`GradingResults.tsx`**: Displays the final graded feedback.
    *   Shows score summary, per-question breakdown, and AI feedback.
    *   Generates a downloadable PDF report.

## 🛠️ Utilities & Logic (`src/lib/`)

*   **`api.ts`**: The central API client for backend communication.
    *   **Types**: Defines shared TypeScript interfaces (`Rubric`, `GradedTest`, `TranscriptionReviewResponse`, etc.).
    *   **Functions**: `fetch` wrappers for all endpoints (`transcribeHandwrittenTest`, `streamTranscription`, `gradeWithTranscription`, etc.).
    *   **Streaming**: Includes the `streamTranscription` helper for handling Server-Sent Events (SSE).
*   **`auth.tsx`**: Authentication provider using a custom auth context (likely JWT based).

## 🎨 Styling & Configuration

*   **Tailwind CSS**: Used for all styling (`tailwind.config.ts`).
*   **Fonts**: Uses `Inter` (via `next/font/google`).
*   **Icons**: Uses `lucide-react` for iconography.
