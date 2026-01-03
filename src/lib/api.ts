/**
 * API client for Grader Vision backend
 */

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
  question_page_indexes: number[];
  criteria_page_indexes: number[];
  sub_questions: SubQuestionPageMapping[];
}

export interface ExtractRubricRequest {
  name?: string;
  description?: string;
  question_mappings: QuestionPageMapping[];
}

export interface ExtractedCriterion {
  description: string;
  points: number;
  extraction_confidence: 'high' | 'medium' | 'low';
}

export interface ExtractedSubQuestion {
  sub_question_id: string;
  sub_question_text: string | null;
  criteria: ExtractedCriterion[];
  total_points: number;
  source_pages: number[];
}

export interface ExtractedQuestion {
  question_number: number;
  question_text: string | null;
  total_points: number;
  criteria: ExtractedCriterion[];
  sub_questions: ExtractedSubQuestion[];
  source_pages: number[];
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
