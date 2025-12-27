/**
 * API client for Grader Vision backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// =============================================================================
// Types matching backend schemas
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

// =============================================================================
// API Functions
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

  // Build query params
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
