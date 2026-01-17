/**
 * API client for Grader Vision backend
 */

import { getAuthHeaders } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// =============================================================================
// Rubric Types
// =============================================================================

export interface PagePreview {
  page_index: number;
  page_number: number;
  thumbnail_base64: string;
  width: number;
  height: number;
  // NEW: Signed URL to individual page PDF for text selection/copying
  page_pdf_url?: string;
}

export interface PreviewRubricPdfResponse {
  filename: string;
  page_count: number;
  pages: PagePreview[];
}

export interface SubQuestionPageMapping {
  sub_question_id: string;
  sub_question_page_indexes: number[];
  criteria_page_indexes: number[];
}

export interface QuestionPageMapping {
  question_number: number;
  question_page_indexes?: number[];  // Optional - question text now auto-extracted from PDF
  criteria_page_indexes: number[];
  sub_questions: SubQuestionPageMapping[];
}

export interface ExtractRubricRequest {
  name?: string;
  description?: string;
  question_mappings: QuestionPageMapping[];
}

// NEW: Reduction rule for detailed grading
export interface ReductionRule {
  description: string;
  reduction_value: number;
  is_explicit: boolean;
}

// UPDATED: Enhanced criterion with structured reduction rules
export interface ExtractedCriterion {
  // Primary fields for enhanced format
  criterion_description: string;
  total_points: number;
  reduction_rules: ReductionRule[];
  notes?: string | null;
  raw_text?: string | null;
  extraction_confidence: 'high' | 'medium' | 'low';

  // Legacy compatibility fields (for backward compatibility with old rubrics)
  description?: string;
  points?: number;
}

export interface ExtractedSubQuestion {
  sub_question_id: string;
  sub_question_text: string | null;
  criteria: ExtractedCriterion[];
  total_points: number;
  source_pages: number[];
  // Extraction status reporting
  extraction_status?: 'success' | 'partial' | 'failed';
  extraction_error?: string | null;
}

export interface ExtractedQuestion {
  question_number: number;
  question_text: string | null;
  total_points: number;
  criteria: ExtractedCriterion[];
  sub_questions: ExtractedSubQuestion[];
  source_pages: number[];
  // Extraction status reporting
  extraction_status?: 'success' | 'partial' | 'failed';
  extraction_error?: string | null;
}

export interface ExtractRubricResponse {
  questions: ExtractedQuestion[];
  total_points: number;
  num_questions: number;
  num_sub_questions: number;
  num_criteria: number;
  name?: string;
  description?: string;
}

export interface SaveRubricRequest {
  name?: string;
  description?: string;
  questions: ExtractedQuestion[];
}

export interface SaveRubricResponse {
  id: string;
  created_at: string;
  name?: string;
  description?: string;
  total_points: number;
  num_questions: number;
  num_criteria: number;
}

export interface RubricListItem {
  id: string;
  created_at: string;
  name?: string;
  description?: string;
  total_points?: number;
  rubric_json: {
    questions: ExtractedQuestion[];
  };
}

// =============================================================================
// Student Test Types
// =============================================================================

export interface PreviewStudentTestResponse {
  filename: string;
  page_count: number;
  pages: PagePreview[];
  detected_student_name?: string;
}

export interface AnswerPageMapping {
  question_number: number;
  sub_question_id: string | null;
  page_indexes: number[];
}

// Student answer structure (transcribed code)
export interface StudentAnswer {
  question_number: number;
  sub_question_id: string | null;
  answer_text: string;
}

export interface StudentAnswersJson {
  student_name: string;
  filename: string;
  answers: StudentAnswer[];
}

// =============================================================================
// Enhanced Grading Types (Evidence & Extra Observations)
// =============================================================================

export interface CodeEvidence {
  quoted_code: string;
  line_numbers?: number[];
  reasoning_chain?: string[];
}

export interface ExtraObservation {
  type: 'syntax_error' | 'logic_error' | 'style_warning' | 'missing_feature' | 'security_issue';
  description: string;
  suggested_deduction: number;
  line_number?: number;
  quoted_code?: string;
  // Frontend-only: tracks if teacher applied this deduction
  applied?: boolean;
  // Frontend-only: allows teacher to adjust the deduction
  adjusted_deduction?: number;
}

export interface GradeItem {
  question_number?: number;
  sub_question_id?: string;
  criterion_index?: number;
  criterion: string;
  mark: string;
  points_earned: number;
  points_possible: number;
  explanation?: string;
  confidence: string;
  low_confidence_reason?: string;
  // New evidence fields
  evidence?: CodeEvidence;
}

export interface QuestionGrade {
  question_number: number;
  grades: GradeItem[];
  extra_observations?: ExtraObservation[];
}

export interface GradedTestResult {
  id: string;
  rubric_id: string;
  created_at: string;
  student_name: string;
  filename?: string;
  total_score: number;
  total_possible: number;
  percentage: number;
  graded_json: {
    grades: GradeItem[];
    question_grades?: QuestionGrade[];
    low_confidence_items?: string[];
    rubric_mismatch_detected?: boolean;
    rubric_mismatch_reason?: string;
  };
  // Student answers (transcribed code)
  student_answers_json?: StudentAnswersJson;
}

export interface GradeTestsResponse {
  rubric_id: string;
  total_tests: number;
  successful: number;
  failed: number;
  graded_tests: GradedTestResult[];
  errors: string[];
}

// =============================================================================
// Rubric API Functions
// =============================================================================

export async function previewRubricPdf(file: File): Promise<PreviewRubricPdfResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/v0/grading/preview_rubric_pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function extractRubric(
  file: File,
  request: ExtractRubricRequest
): Promise<ExtractRubricResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams();
  params.append('question_mappings', JSON.stringify(request.question_mappings));
  if (request.name) params.append('name', request.name);
  if (request.description) params.append('description', request.description);

  const response = await fetch(`${API_BASE}/api/v0/grading/extract_rubric?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function saveRubric(request: SaveRubricRequest): Promise<SaveRubricResponse> {
  const response = await fetch(`${API_BASE}/api/v0/grading/save_rubric`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function getRubric(rubricId: string): Promise<RubricListItem> {
  const response = await fetch(`${API_BASE}/api/v0/grading/rubric/${rubricId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function listRubrics(): Promise<RubricListItem[]> {
  const response = await fetch(`${API_BASE}/api/v0/grading/rubrics`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function updateRubric(
  rubricId: string,
  data: {
    name?: string;
    description?: string;
    questions: ExtractedQuestion[]
  }
): Promise<RubricListItem> {
  const response = await fetch(`${API_BASE}/api/v0/grading/rubric/${rubricId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Student Test API Functions
// =============================================================================

export async function previewStudentTestPdf(file: File): Promise<PreviewStudentTestResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/v0/grading/preview_student_test_pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function gradeTests(
  rubricId: string,
  answerMappings: AnswerPageMapping[],
  files: File[],
  firstPageIndex: number = 0
): Promise<GradeTestsResponse> {
  const formData = new FormData();

  // Append all files
  files.forEach((file) => {
    formData.append('files', file);
  });

  const params = new URLSearchParams();
  params.append('rubric_id', rubricId);
  params.append('answer_mappings', JSON.stringify(answerMappings));
  params.append('first_page_index', firstPageIndex.toString());

  const response = await fetch(`${API_BASE}/api/v0/grading/grade_tests?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Grade a single test - used for progress tracking
export async function gradeSingleTest(
  rubricId: string,
  answerMappings: AnswerPageMapping[],
  file: File,
  firstPageIndex: number = 0
): Promise<GradedTestResult> {
  const formData = new FormData();
  formData.append('files', file);

  const params = new URLSearchParams();
  params.append('rubric_id', rubricId);
  params.append('answer_mappings', JSON.stringify(answerMappings));
  params.append('first_page_index', firstPageIndex.toString());

  const response = await fetch(`${API_BASE}/api/v0/grading/grade_tests?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const result: GradeTestsResponse = await response.json();

  if (result.graded_tests.length > 0) {
    return result.graded_tests[0];
  }

  throw new Error(result.errors[0] || 'Failed to grade test');
}



/**
 * Grade a handwritten test using VLM transcription
 */

export async function gradeHandwrittenTest(
  rubricId: string,
  testFile: File,
  answeredQuestions?: number[],
  firstPageIndex: number = 0
): Promise<GradedTestResult> {
  const formData = new FormData();
  formData.append('test_file', testFile);
  const params = new URLSearchParams();
  params.append('rubric_id', rubricId);
  params.append('first_page_index', firstPageIndex.toString());

  if (answeredQuestions && answeredQuestions.length > 0) {
    params.append('answered_questions', JSON.stringify(answeredQuestions));
  }

  const response = await fetch(`${API_BASE}/api/v0/grading/grade_handwritten_test?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Graded Tests List API Functions
// =============================================================================

export interface GradedTestListItem {
  id: string;
  rubric_id: string;
  student_name: string;
  filename: string | null;
  total_score: number;
  total_possible: number;
  percentage: number;
  created_at: string;
  rubric_name?: string;
}

/**
 * Fetch all graded tests (across all rubrics, for current user)
 */
export async function listAllGradedTests(): Promise<GradedTestListItem[]> {
  // First, get all rubrics
  const rubrics = await listRubrics();

  // For now, we'll get graded tests from the graded_tests list per rubric
  // The backend currently returns graded tests in the batch response
  // We need to aggregate them
  const allTests: GradedTestListItem[] = [];

  // Build a map of rubric names
  const rubricNames = new Map<string, string>();
  for (const r of rubrics) {
    rubricNames.set(r.id, r.name || 'מחוון ללא שם');
  }

  // Fetch graded tests for each rubric
  for (const rubric of rubrics) {
    try {
      const response = await fetch(`${API_BASE}/api/v0/grading/rubric/${rubric.id}/graded_tests`);
      if (response.ok) {
        const tests: GradedTestResult[] = await response.json();
        for (const t of tests) {
          allTests.push({
            id: t.id,
            rubric_id: t.rubric_id,
            student_name: t.student_name,
            filename: t.filename || null,
            total_score: t.total_score,
            total_possible: t.total_possible,
            percentage: t.percentage,
            created_at: t.created_at,
            rubric_name: rubricNames.get(t.rubric_id),
          });
        }
      }
    } catch (e) {
      // Skip rubrics that fail
      console.warn(`Failed to fetch tests for rubric ${rubric.id}:`, e);
    }
  }

  // Sort by created_at descending (newest first)
  allTests.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  return allTests;
}

/**
 * Get a single graded test by ID with full details.
 */
export async function getGradedTestById(testId: string): Promise<GradedTestResult> {
  const response = await fetch(`${API_BASE}/api/v0/grading/graded_test/${testId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch test' }));
    throw new Error(error.detail || `Failed to fetch test: ${response.status}`);
  }

  return response.json();
}


// =============================================================================
// Transcription Review Types & Functions (two-step transcribe → review → grade)
// =============================================================================

export interface TranscribedAnswerWithPages {
  question_number: number;
  sub_question_id: string | null;
  answer_text: string;
  confidence: number;
  transcription_notes: string | null;
  page_indexes: number[];
}

export interface TranscriptionReviewResponse {
  transcription_id: string;
  rubric_id: string;
  student_name: string;
  filename: string;
  total_pages: number;
  pages: PagePreview[];
  answers: TranscribedAnswerWithPages[];
  raw_transcription: string | null;
}

export interface StudentAnswerInput {
  question_number: number;
  sub_question_id: string | null;
  answer_text: string;
}

export interface GradeWithTranscriptionRequest {
  rubric_id: string;
  student_name: string;
  filename: string;
  answers: StudentAnswerInput[];
  answered_question_numbers?: number[];
}

/**
 * Transcribe a handwritten test for teacher review.
 * Step 1 of the transcribe → review → grade flow.
 */
export async function transcribeHandwrittenTest(
  rubricId: string,
  testFile: File,
  firstPageIndex: number = 0,
  answeredQuestions?: number[]
): Promise<TranscriptionReviewResponse> {
  const formData = new FormData();
  formData.append('test_file', testFile);

  const url = new URL(`${API_BASE}/api/v0/grading/transcribe_handwritten_test`);
  url.searchParams.set('rubric_id', rubricId);
  url.searchParams.set('first_page_index', firstPageIndex.toString());

  // Pass answered questions filter if provided
  if (answeredQuestions && answeredQuestions.length > 0) {
    url.searchParams.set('answered_questions', JSON.stringify(answeredQuestions));
  }

  const response = await fetch(url.toString(), {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Transcription failed' }));
    throw new Error(error.detail || `Transcription failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Grade a test using teacher-edited transcription.
 * Step 2 of the transcribe → review → grade flow.
 */
export async function gradeWithTranscription(
  request: GradeWithTranscriptionRequest
): Promise<GradedTestResult> {
  const response = await fetch(`${API_BASE}/api/v0/grading/grade_with_transcription`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Grading failed' }));
    throw new Error(error.detail || `Grading failed: ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Streaming Transcription Types & Functions
// =============================================================================

export type TranscriptionPhase = 'loading' | 'transcribing' | 'verifying' | 'done';

export interface StreamingCallbacks {
  onMetadata: (transcriptionId: string, studentName: string, filename: string, totalPages: number) => void;
  onPage: (page: PagePreview) => void;
  onPhase: (phase: TranscriptionPhase, currentPage?: number, totalPages?: number) => void;
  onChunk: (page: number, delta: string) => void;
  onAnswer: (answer: TranscribedAnswerWithPages) => void;
  onDone: (totalAnswers: number) => void;
  onError: (message: string) => void;
}

/**
 * Stream transcription of a handwritten test using SSE.
 * Uses fetch with ReadableStream since EventSource doesn't support POST with file upload.
 * 
 * @returns A function to abort the stream
 */
export function streamTranscription(
  rubricId: string,
  testFile: File,
  callbacks: StreamingCallbacks,
  options?: { firstPageIndex?: number; answeredQuestions?: number[] }
): { abort: () => void } {
  const abortController = new AbortController();

  const runStream = async () => {
    try {
      const formData = new FormData();
      formData.append('test_file', testFile);

      const params = new URLSearchParams();
      params.set('rubric_id', rubricId);
      params.set('first_page_index', (options?.firstPageIndex ?? 0).toString());

      if (options?.answeredQuestions && options.answeredQuestions.length > 0) {
        params.set('answered_questions', JSON.stringify(options.answeredQuestions));
      }

      const response = await fetch(
        `${API_BASE}/api/v0/grading/stream_transcription?${params.toString()}`,
        {
          method: 'POST',
          body: formData,
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Stream failed' }));
        callbacks.onError(error.detail || `Stream failed: ${response.status}`);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete events (separated by double newlines)
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || ''; // Keep incomplete part

        for (const part of parts) {
          if (!part.trim()) continue;

          const lines = part.split('\n');
          let eventType = '';
          let eventData = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              eventData = line.slice(5).trim();
            }
          }

          if (!eventType || !eventData) continue;

          try {
            const data = JSON.parse(eventData);

            switch (eventType) {
              case 'metadata':
                callbacks.onMetadata(
                  data.transcription_id,
                  data.student_name,
                  data.filename,
                  data.total_pages
                );
                break;

              case 'page':
                callbacks.onPage({
                  page_index: data.page_index,
                  page_number: data.page_number,
                  thumbnail_base64: data.thumbnail_base64,
                  width: data.width,
                  height: data.height,
                });
                break;

              case 'phase':
                callbacks.onPhase(
                  data.phase as TranscriptionPhase,
                  data.current_page,
                  data.total_pages
                );
                break;

              case 'chunk':
                callbacks.onChunk(data.page, data.delta);
                break;

              case 'answer':
                callbacks.onAnswer({
                  question_number: data.question_number,
                  sub_question_id: data.sub_question_id,
                  answer_text: data.answer_text,
                  confidence: data.confidence,
                  transcription_notes: null,
                  page_indexes: data.page_indexes || [],
                });
                break;

              case 'done':
                callbacks.onDone(data.total_answers || 0);
                break;

              case 'error':
                callbacks.onError(data.message);
                break;
            }
          } catch (parseError) {
            console.warn('Failed to parse SSE event:', eventType, eventData, parseError);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.log('Stream aborted');
        return;
      }
      callbacks.onError((error as Error).message || 'Stream connection failed');
    }
  };

  // Start the stream
  runStream();

  return {
    abort: () => abortController.abort(),
  };
}
// =============================================================================
// Streaming Transcription Types & Functions (TWO-PHASE)
// =============================================================================

export interface ReviewFlag {
  line: number;
  reason: string;
}

export interface PageStreamState {
  pageNumber: number;
  rawText: string;
  verifiedText: string;
  markedText: string;  // Text with <Q#> markers
  detectedQuestions: number[];  // Question numbers detected on this page
  confidenceScores: Record<number, number>;  // Confidence per question
  phase: 'raw' | 'verifying' | 'complete';
  isStreaming: boolean;
  reviewFlags: ReviewFlag[];  // Lines flagged for review by error detection
}

export interface TranscriptionStreamState {
  transcriptionId: string;
  rubricId: string;
  studentName: string;
  filename: string;
  totalPages: number;
  pages: PagePreview[];
  currentPhase: TranscriptionPhase;
  currentPage: number;
  phaseMessage: string;
  pageStates: Map<number, PageStreamState>;
  answers: TranscribedAnswerWithPages[];
  isComplete: boolean;
  error: string | null;
}

export interface StreamingCallbacksV2 {
  onMetadata: (data: {
    transcriptionId: string;
    studentName: string;
    filename: string;
    totalPages: number;
    rubricId: string;
  }) => void;
  onPage: (page: PagePreview) => void;
  onPhase: (phase: TranscriptionPhase, currentPage: number, totalPages: number, message: string) => void;
  onRawChunk: (pageNumber: number, delta: string) => void;
  onRawComplete: (pageNumber: number, fullText: string) => void;
  onVerifiedChunk: (pageNumber: number, delta: string) => void;
  onPageComplete: (pageNumber: number, pageIndex: number, markedText: string, detectedQuestions: number[], confidenceScores: Record<number, number>) => void;
  onReviewFlags?: (pageNumber: number, flags: ReviewFlag[]) => void;  // NEW: error detection results
  onAnswer: (answer: TranscribedAnswerWithPages) => void;
  onDone: (totalAnswers: number) => void;
  onError: (message: string) => void;
}

/**
 * Stream two-phase transcription using SSE.
 */
export function streamTranscriptionV2(
  rubricId: string,
  testFile: File,
  callbacks: StreamingCallbacksV2,
  options?: {
    firstPageIndex?: number;
    answeredQuestions?: number[];
  }
): { abort: () => void } {
  const abortController = new AbortController();

  const runStream = async () => {
    try {
      const formData = new FormData();
      formData.append('test_file', testFile);

      const params = new URLSearchParams();
      params.set('rubric_id', rubricId);
      params.set('first_page_index', (options?.firstPageIndex ?? 0).toString());

      if (options?.answeredQuestions && options.answeredQuestions.length > 0) {
        params.set('answered_questions', JSON.stringify(options.answeredQuestions));
      }

      const response = await fetch(
        `${API_BASE}/api/v0/grading/stream_transcription_v2?${params.toString()}`,
        {
          method: 'POST',
          body: formData,
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Stream failed' }));
        callbacks.onError(error.detail || `Stream failed: ${response.status}`);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          if (!part.trim()) continue;

          const lines = part.split('\n');
          let eventType = '';
          let eventData = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              eventData = line.slice(5).trim();
            }
          }

          if (!eventType || !eventData) continue;

          try {
            const data = JSON.parse(eventData);

            switch (eventType) {
              case 'metadata':
                callbacks.onMetadata({
                  transcriptionId: data.transcription_id,
                  studentName: data.student_name,
                  filename: data.filename,
                  totalPages: data.total_pages,
                  rubricId: data.rubric_id,
                });
                break;
              case 'page':
                callbacks.onPage({
                  page_index: data.page_index,
                  page_number: data.page_number,
                  thumbnail_base64: data.thumbnail_base64,
                  width: data.width,
                  height: data.height,
                });
                break;
              case 'phase':
                callbacks.onPhase(
                  data.phase as TranscriptionPhase,
                  data.current_page || 0,
                  data.total_pages || 0,
                  data.message || ''
                );
                break;
              case 'raw_chunk':
                callbacks.onRawChunk(data.page, data.delta);
                break;
              case 'raw_complete':
                callbacks.onRawComplete(data.page, data.full_text);
                break;
              case 'verified_chunk':
                callbacks.onVerifiedChunk(data.page, data.delta);
                break;
              case 'chunk': // Legacy compatibility
                callbacks.onRawChunk(data.page, data.delta);
                break;
              case 'answer':
                callbacks.onAnswer({
                  question_number: data.question_number,
                  sub_question_id: data.sub_question_id,
                  answer_text: data.answer_text,
                  confidence: data.confidence,
                  transcription_notes: null,
                  page_indexes: data.page_indexes || [],
                });
                break;
              case 'page_complete':
                callbacks.onPageComplete(
                  data.page_number,
                  data.page_index,
                  data.text,
                  data.detected_questions || [],
                  data.confidence_scores || {}
                );
                break;
              case 'review_flags':  // NEW: error detection results
                if (callbacks.onReviewFlags) {
                  const flags = (data.lines_to_review || []).map((lineNum: number) => ({
                    line: lineNum,
                    reason: data.reasons?.[String(lineNum)] || 'needs review'
                  }));
                  callbacks.onReviewFlags(data.page, flags);
                }
                break;
              case 'done':
                callbacks.onDone(data.total_answers || 0);
                break;
              case 'error':
                callbacks.onError(data.message);
                break;
            }
          } catch (parseError) {
            console.warn('Failed to parse SSE event:', eventType, eventData, parseError);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') return;
      callbacks.onError((error as Error).message || 'Stream connection failed');
    }
  };

  runStream();
  return { abort: () => abortController.abort() };
}

// State management helpers
export function createInitialStreamState(): TranscriptionStreamState {
  return {
    transcriptionId: '',
    rubricId: '',
    studentName: '',
    filename: '',
    totalPages: 0,
    pages: [],
    currentPhase: 'loading',
    currentPage: 0,
    phaseMessage: 'מעבד PDF...',
    pageStates: new Map(),
    answers: [],
    isComplete: false,
    error: null,
  };
}

export type StreamAction =
  | { type: 'METADATA'; payload: { transcriptionId: string; studentName: string; filename: string; totalPages: number; rubricId: string } }
  | { type: 'PAGE'; payload: PagePreview }
  | { type: 'PHASE'; payload: { phase: TranscriptionPhase; currentPage: number; totalPages: number; message: string } }
  | { type: 'RAW_CHUNK'; payload: { pageNumber: number; delta: string } }
  | { type: 'RAW_COMPLETE'; payload: { pageNumber: number; fullText: string } }
  | { type: 'VERIFIED_CHUNK'; payload: { pageNumber: number; delta: string } }
  | { type: 'PAGE_COMPLETE'; payload: { pageNumber: number; pageIndex: number; markedText: string; detectedQuestions: number[]; confidenceScores: Record<number, number> } }
  | { type: 'REVIEW_FLAGS'; payload: { pageNumber: number; flags: ReviewFlag[] } }  // NEW
  | { type: 'ANSWER'; payload: TranscribedAnswerWithPages }
  | { type: 'DONE'; payload: { totalAnswers: number } }
  | { type: 'ERROR'; payload: { message: string } }
  | { type: 'RESET' };

export function streamReducer(state: TranscriptionStreamState, action: StreamAction): TranscriptionStreamState {
  switch (action.type) {
    case 'METADATA':
      return { ...state, ...action.payload };
    case 'PAGE':
      return { ...state, pages: [...state.pages, action.payload] };
    case 'PHASE':
      return { ...state, currentPhase: action.payload.phase, currentPage: action.payload.currentPage, phaseMessage: action.payload.message };
    case 'RAW_CHUNK': {
      const pageStates = new Map(state.pageStates);
      const existing = pageStates.get(action.payload.pageNumber) || { pageNumber: action.payload.pageNumber, rawText: '', verifiedText: '', markedText: '', detectedQuestions: [], confidenceScores: {}, phase: 'raw' as const, isStreaming: true, reviewFlags: [] };
      pageStates.set(action.payload.pageNumber, { ...existing, rawText: existing.rawText + action.payload.delta, phase: 'raw', isStreaming: true });
      return { ...state, pageStates };
    }
    case 'RAW_COMPLETE': {
      const pageStates = new Map(state.pageStates);
      const existing = pageStates.get(action.payload.pageNumber);
      if (existing) pageStates.set(action.payload.pageNumber, { ...existing, rawText: action.payload.fullText, phase: 'verifying', isStreaming: false });
      return { ...state, pageStates };
    }
    case 'VERIFIED_CHUNK': {
      const pageStates = new Map(state.pageStates);
      const existing = pageStates.get(action.payload.pageNumber) || { pageNumber: action.payload.pageNumber, rawText: '', verifiedText: '', markedText: '', detectedQuestions: [], confidenceScores: {}, phase: 'verifying' as const, isStreaming: true, reviewFlags: [] };
      pageStates.set(action.payload.pageNumber, { ...existing, verifiedText: existing.verifiedText + action.payload.delta, phase: 'verifying', isStreaming: true });
      return { ...state, pageStates };
    }
    case 'PAGE_COMPLETE': {
      const pageStates = new Map(state.pageStates);
      const existing = pageStates.get(action.payload.pageNumber) || { pageNumber: action.payload.pageNumber, rawText: '', verifiedText: '', markedText: '', detectedQuestions: [], confidenceScores: {}, phase: 'complete' as const, isStreaming: false, reviewFlags: [] };
      pageStates.set(action.payload.pageNumber, {
        ...existing,
        markedText: action.payload.markedText,
        detectedQuestions: action.payload.detectedQuestions,
        confidenceScores: action.payload.confidenceScores,
        phase: 'complete',
        isStreaming: false,
      });
      return { ...state, pageStates };
    }
    case 'REVIEW_FLAGS': {  // NEW: handle review flags
      const pageStates = new Map(state.pageStates);
      const existing = pageStates.get(action.payload.pageNumber);
      if (existing) {
        pageStates.set(action.payload.pageNumber, { ...existing, reviewFlags: action.payload.flags });
      }
      return { ...state, pageStates };
    }
    case 'ANSWER': {
      const pageStates = new Map(state.pageStates);
      const pageIdx = action.payload.page_indexes[0];
      if (pageIdx !== undefined) {
        const existing = pageStates.get(pageIdx + 1);
        if (existing) pageStates.set(pageIdx + 1, { ...existing, phase: 'complete', isStreaming: false });
      }
      return { ...state, pageStates, answers: [...state.answers, action.payload] };
    }
    case 'DONE':
      return { ...state, currentPhase: 'done', phaseMessage: 'התמלול הושלם!', isComplete: true };
    case 'ERROR':
      return { ...state, error: action.payload.message };
    case 'RESET':
      return createInitialStreamState();
    default:
      return state;
  }
}

export function streamStateToReviewResponse(state: TranscriptionStreamState): TranscriptionReviewResponse {
  return {
    transcription_id: state.transcriptionId,
    rubric_id: state.rubricId,
    student_name: state.studentName,
    filename: state.filename,
    total_pages: state.totalPages,
    pages: state.pages,
    answers: state.answers,
    raw_transcription: null,
  };
}

// =============================================================================
// Rubric Generator Types & Functions
// =============================================================================

export interface DetectedQuestion {
  question_number: number;
  question_text: string;
  page_indexes: number[];
  sub_questions: string[];
  suggested_points: number | null;
  teacher_points: number | null;
}

export interface UploadPdfResponse {
  upload_id: string;
  page_count: number;
  file_size_mb: number;
}

export interface DetectionEvent {
  type: 'progress' | 'question' | 'complete' | 'error';
  data?: DetectedQuestion | { total_questions: number; questions: DetectedQuestion[] };
  message?: string;
}

export interface ShareHistoryItem {
  id: string;
  recipient_email: string;
  shared_at: string;
  status: 'pending' | 'accepted' | 'revoked';
  accepted_at?: string;
}

/**
 * Upload PDF for rubric generation.
 * Validates size (25MB max) and format.
 */
export async function uploadPdfForGeneration(file: File): Promise<UploadPdfResponse> {
  const MAX_SIZE_MB = 25;
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    throw new Error(`הקובץ גדול מדי (${(file.size / 1024 / 1024).toFixed(1)}MB). המקסימום הוא ${MAX_SIZE_MB}MB`);
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || `Upload failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Stream question detection using SSE.
 * Supports reconnection with lastEventId.
 */
export function streamQuestionDetection(
  uploadId: string,
  callbacks: {
    onProgress: (message: string) => void;
    onQuestion: (question: DetectedQuestion) => void;
    onComplete: (questions: DetectedQuestion[]) => void;
    onError: (error: string) => void;
    onReconnecting?: () => void;
  },
  options?: { maxRetries?: number }
): () => void {
  const maxRetries = options?.maxRetries ?? 3;
  let retryCount = 0;
  let lastEventId: string | null = null;
  let eventSource: EventSource | null = null;
  let isClosed = false;
  const detectedQuestions: DetectedQuestion[] = [];

  const connect = () => {
    if (isClosed) return;

    let url = `${API_BASE}/api/v0/rubric_generator/detect_questions/${uploadId}`;
    if (lastEventId) {
      url += `?lastEventId=${encodeURIComponent(lastEventId)}`;
    }

    eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      retryCount = 0; // Reset on success
      lastEventId = event.lastEventId;

      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'progress':
            callbacks.onProgress(data.message || '');
            break;
          case 'question':
            const question = data.data as DetectedQuestion;
            detectedQuestions.push(question);
            callbacks.onQuestion(question);
            break;
          case 'complete':
            callbacks.onComplete(data.data?.questions || detectedQuestions);
            eventSource?.close();
            break;
          case 'error':
            callbacks.onError(data.message || 'שגיאה בזיהוי שאלות');
            eventSource?.close();
            break;
        }
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      if (isClosed) return;

      if (retryCount < maxRetries) {
        retryCount++;
        callbacks.onReconnecting?.();
        const delay = Math.pow(2, retryCount - 1) * 1000;
        setTimeout(connect, delay);
      } else {
        callbacks.onError('החיבור נכשל. אנא רענן את הדף ונסה שוב.');
      }
    };
  };

  connect();

  return () => {
    isClosed = true;
    eventSource?.close();
  };
}

/**
 * Generate criteria for all questions.
 */
export async function generateCriteria(
  questions: DetectedQuestion[],
  rubricName?: string,
  rubricDescription?: string
): Promise<ExtractRubricResponse> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/generate_criteria`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      questions,
      rubric_name: rubricName,
      rubric_description: rubricDescription,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Generation failed' }));
    throw new Error(error.detail || `Generation failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Regenerate criteria for a single question.
 */
export async function regenerateQuestion(
  questionNumber: number,
  questionText: string,
  subQuestions: string[],
  totalPoints: number
): Promise<ExtractedQuestion> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/regenerate_question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question_number: questionNumber,
      question_text: questionText,
      sub_questions: subQuestions,
      total_points: totalPoints,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Regeneration failed' }));
    throw new Error(error.detail || `Regeneration failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Create annotated PDF with rubric tables.
 */
export async function createRubricPdf(
  rubricId?: string,
  questions?: ExtractedQuestion[],
  includeOriginal: boolean = false,
  originalPdfUploadId?: string
): Promise<{ download_url: string; filename: string }> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/create_pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rubric_id: rubricId,
      questions: questions,
      include_original: includeOriginal,
      original_pdf_upload_id: originalPdfUploadId,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'PDF creation failed' }));
    throw new Error(error.detail || `PDF creation failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Share rubric via email.
 */
export async function shareRubricViaEmail(
  rubricId: string,
  recipientEmail: string,
  senderName: string,
  includePdf: boolean = true
): Promise<{ success: boolean; message: string; share_id?: string }> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/share_email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      rubric_id: rubricId,
      recipient_email: recipientEmail,
      sender_name: senderName,
      include_pdf: includePdf,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Share failed' }));
    throw new Error(error.detail || `Share failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Accept a shared rubric (copy to user's account).
 */
export async function acceptRubricShare(
  token: string
): Promise<{ success: boolean; message: string; rubric_id?: string; redirect_url?: string }> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/accept_share/${token}`, {
    headers: { ...getAuthHeaders() },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Accept failed' }));
    throw new Error(error.detail || `Accept failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Get share history for a rubric.
 */
export async function getShareHistory(
  rubricId: string
): Promise<{ shares: ShareHistoryItem[]; total_count: number }> {
  const response = await fetch(`${API_BASE}/api/v0/rubric_generator/share_history/${rubricId}`, {
    headers: { ...getAuthHeaders() },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch history' }));
    throw new Error(error.detail || `Failed to fetch history: ${response.status}`);
  }

  return response.json();
}

