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
    questions: Array<{
      question_number: number;
      total_points: number;
      question_text?: string;
      criteria?: Array<{ description: string; points: number }>;
      sub_questions?: Array<{
        sub_question_id: string;
        sub_question_text?: string;
        criteria: Array<{ description: string; points: number }>;
      }>;
    }>;
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
    grades: Array<{
      question_number?: number;
      sub_question_id?: string;
      criterion: string;
      mark: string;
      points_earned: number;
      points_possible: number;
      explanation?: string;
      confidence: string;
      low_confidence_reason?: string;
    }>;
    question_grades?: Array<{
      question_number: number;
      grades: Array<{
        question_number?: number;
        sub_question_id?: string;
        criterion: string;
        mark: string;
        points_earned: number;
        points_possible: number;
        explanation?: string;
        confidence: string;
        low_confidence_reason?: string;
      }>;
    }>;
    low_confidence_items?: string[];
  };
  // NEW: Student answers (transcribed code)
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