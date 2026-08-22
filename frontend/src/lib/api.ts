/**
 * API client for Vivi backend
 */

import { getAuthHeaders } from './auth';
import type { components } from './api-types';
import type { QuestionOntology } from './ontology-types';
import type {
    TranscribeResponse,
    GradeAnswerInput,
    GradeQueuedResponse,
    TranscriptionPageResponse,
} from '@/types/transcription';
import type {
    GradedTestApprovedResponse,
    GradedTestDetailResponse,
    GradedTestDraftResponse,
    GradedTestListItem,
    GradedTestOverrides,
    RevisionResponse,
} from '@/types/graded_test';
import type {
    AcceptCleanItem,
    BatchCreateResponse,
    BatchDetailResponse,
    BatchListItem,
    GradeAnswerInputItem,
} from '@/types/batch';
// Re-export for convenience (used in batch pages)
export type { BatchListItem, BatchDetailResponse, BatchCreateResponse } from '@/types/batch';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// ===========================================================================
// PR-2 — THE FETCH SEAM
// ===========================================================================
// Before PR-2 there was no seam at all: 41 hand-rolled `fetch` sites, each
// repeating the same 4 lines, with no interceptor and no shared error type.
// PR-1's ApiAuthError (5 functions) is the precedent this generalizes.
//
// DELIBERATELY NOT HERE:
//   * NO silent retries. A mutation must never auto-repeat itself (a retried
//     POST /grade is a duplicate grade). Poll-loop retry stays in the hooks,
//     where it is visible, bounded, and terminal-on-auth.
//   * AUTH ENDPOINTS DO NOT ROUTE THROUGH THIS (see auth.tsx). A wrong password
//     legitimately returns 401; if login threw ApiAuthError it would be reported
//     as "session expired" and would trigger the stash-and-logout flow on a
//     failed login. That is the difference between a resilience change and a
//     login-breaking one.

/** E3: what a FastAPI validation failure says to a teacher. Its own `detail`
 *  is an English list, which must never reach an RTL screen. */
export const VALIDATION_ERROR_HE = 'הנתונים שנשלחו אינם תקינים — בדקי את השדות ונסי שוב.';

/** A normalized, typed API failure. `detail` is already the human-facing string. */
export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** 401/403 — TERMINAL for poll loops. Never retry, never back off: stop and surface. */
export class ApiAuthError extends ApiError {
  constructor(status: number) {
    super(status, status === 401
      ? 'פג תוקף ההתחברות — יש להתחבר מחדש'
      : 'אין הרשאה לפעולה זו');
    this.name = 'ApiAuthError';
  }
}

/** Best-effort extraction of the backend's error string (FastAPI `detail`). */
async function normalizeError(response: Response): Promise<ApiError> {
  if (response.status === 401 || response.status === 403) {
    return new ApiAuthError(response.status);
  }
  const data = await response.json().catch(() => null);
  // FastAPI's 422 puts a LIST of validation errors in `detail`, each with an
  // ENGLISH `msg`. Neither branch below could extract it, so a validation
  // failure surfaced as the generic "שגיאת שרת (422)" — and extracting the
  // raw msg would render English on an RTL screen. A Hebrew validation
  // message is the honest surface; the English detail stays in the console
  // for whoever is debugging. (closeout/E3)
  if (Array.isArray(data?.detail)) {
    const first = data.detail[0];
    if (typeof console !== 'undefined' && first?.msg) {
      console.warn('[vivi] validation error', data.detail);
    }
    return new ApiError(response.status, VALIDATION_ERROR_HE);
  }
  const detail =
    (typeof data?.detail === 'string' && data.detail) ||
    (typeof data?.detail?.message_he === 'string' && data.detail.message_he) ||
    `שגיאת שרת (${response.status})`;
  return new ApiError(response.status, detail);
}

/** 401/403 is TERMINAL everywhere — call this from any site that owns its own
 * status branching, so an expired session can never be mistaken for a domain error. */
export function throwIfAuthError(response: Response): void {
  if (response.status === 401 || response.status === 403) {
    throw new ApiAuthError(response.status);
  }
}

/**
 * RAW passthrough: attaches auth headers and resolves the URL, but DOES NOT throw —
 * the caller owns the status. Two legitimate users:
 *   * the streaming transcription fns (they read `response.body` as a ReadableStream,
 *     which a JSON parse would consume);
 *   * the rubric save/update/compile fns, which deliberately READ non-OK responses
 *     (the warnings modal, RubricSaveError) — a throwing helper would break them.
 * Both still call throwIfAuthError so 401 stays terminal.
 */
export async function apiFetchRaw(path: string, init: RequestInit = {}): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  return fetch(url, {
    ...init,
    headers: { ...getAuthHeaders(), ...(init.headers || {}) },
  });
}

/** Auth headers + typed throw on any non-OK status; caller reads the body.
 * This is the path for the ordinary calls (the ones that used to hand-roll
 * `if (!response.ok) throw new Error(detail)` — 21 identical copies of it). */
export async function apiFetchChecked(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await apiFetchRaw(path, init);
  if (!response.ok) throw await normalizeError(response);
  return response;
}

/** The one JSON call path. Every ordinary request goes through here: auth headers in,
 * typed ApiError/ApiAuthError out, parsed body back. */
export async function apiFetch<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetchChecked(path, init);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** JSON-body helper — sets Content-Type only when there is a body to type. */
export function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    ...(body === undefined
      ? {}
      : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  };
}

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


/**
 * @deprecated Legacy PDF-extraction reduction rule. Not used in the ontology path.
 * Legacy format uses `reduction_value` (number) and `is_explicit` (boolean).
 */
export interface ReductionRule {
  description: string;
  reduction_value: number;
  is_explicit: boolean;
}

/**
 * @deprecated Use `RubricCriterion` from `@/types/rubric` instead.
 * Legacy criterion — uses `criterion_description` + `total_points` + `reduction_rules`.
 * The ontology format uses `description` + `points` + `sub_criteria`.
 * Hydrate with `hydrateAnyQuestions()` from `@/utils/rubric-transform`.
 */
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

/**
 * @deprecated Use `RubricSubQuestion` from `@/types/rubric` instead.
 * Legacy sub-question — uses `sub_question_text` and `total_points`.
 * The ontology format uses `text` and `points`.
 * Hydrate with `hydrateAnyQuestions()` from `@/utils/rubric-transform`.
 */
export interface ExtractedSubQuestion {
  sub_question_id: string;
  sub_question_text: string | null;
  criteria: ExtractedCriterion[];
  total_points: number;
  source_pages: number[];
  // Extraction status reporting
  extraction_status?: 'success' | 'partial' | 'failed';
  extraction_error?: string | null;
  // DOCX-specific: trace tables for code execution visualization
  trace_tables?: TraceTableData[];
  // DOCX-specific: context tables that are part of the question content
  // (e.g. class interface definitions, input/output example tables)
  context_tables?: ContextTableData[];
}

/**
 * @deprecated Use `RubricQuestion` from `@/types/rubric` instead.
 * Legacy question — uses `question_number` (number) and mixed field names.
 * The ontology format uses `question_id` (string like "q1") and canonical field names.
 * Hydrate with `hydrateAnyQuestions()` from `@/utils/rubric-transform`.
 */
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
  // DOCX-specific fields
  example_solution?: string | null;
  code_blocks?: string[];
  trace_tables?: TraceTableData[];
  // DOCX-specific: context tables that are part of the question content
  // (e.g. class interface definitions, input/output example tables)
  context_tables?: ContextTableData[];
}

/**
 * A "choose k of N" constraint (PR-3). The extraction pipeline produces these; the
 * compiler needs them to compute the ACHIEVABLE total. The wizard used to DROP them on
 * save, which meant a selection rubric could never be saved at all: the backend saw
 * total_points=50 (achievable) with no groups, recomputed achievable as the full 100,
 * and rejected on INV-4. Carry them through, verbatim.
 */
export interface SelectionGroup {
  group_id: string;
  of_question_ids: string[];
  choose_k: number;
  label?: string | null;
}

/**
 * Step 2c's output — a detected error IN THE TEACHER'S RUBRIC, with the machine's
 * proposed correction and (PR-6 §4) the record of what she decided about it.
 *
 * The provenance fields are optional on the wire because drafts saved before PR-6
 * do not carry them; absent means "no decision recorded", never "dismissed".
 */
export interface PedagogicalMistakeWire {
  mistake_id: string;
  kind: string;
  severity?: string;
  target_id?: string | null;
  explanation: string;
  evidence?: Record<string, unknown> | null;
  suggested_fix?: {
    operation: string;
    description: string;
    params?: Record<string, unknown> | null;
    /** The general edit wire (pipeline ≥ 3.6.0): ordered primitive steps. */
    steps?: Array<Record<string, unknown>> | null;
  } | null;
  requires_teacher_input?: boolean;
  confidence?: number;
  /** D3 — mistake_id of the root cause whose single fix resolves this one too. */
  explained_by?: string | null;
  /** §4 — her decisions are data, and they round-trip. */
  dismissed?: boolean | null;
  dismissed_at?: string | null;
  fix_applied?: boolean | null;
  fix_applied_at?: string | null;
}

export interface ExtractRubricResponse {
  questions: ExtractedQuestion[];
  total_points: number;                 // ACHIEVABLE (selection-aware), not the offered sum
  selection_groups?: SelectionGroup[];
  num_questions: number;
  num_sub_questions: number;
  num_criteria: number;
  name?: string;
  description?: string;
  programming_language?: string;
  // DOCX pipeline metadata
  metadata?: ExtractionMetadata;
  /** Extraction-time annotations (e.g. rubric_mismatch warnings). */
  annotations?: Annotation[];
  /** Step 2c advisories — the explanation + fix half of a finding (PR-6). */
  pedagogical_mistakes?: PedagogicalMistakeWire[];
}

export interface RubricListItem {
  id: string;
  created_at: string;
  name?: string;
  description?: string;
  format?: 'ontology' | 'legacy';
  is_compiled?: boolean;
  needs_recompilation?: boolean;
  total_points?: number;
  total_questions?: number;
}

/** Full rubric detail — returned by getRubric(). Extends RubricListItem with draft/contract JSON. */
export interface RubricDetailItem extends RubricListItem {
  updated_at?: string | null;
  last_compiled_at?: string | null;
  contract_version?: string | null;
  stats?: {
    total_points: number;
    total_questions: number;
    total_criteria: number;
    total_rules: number;
  } | null;
  /** Populated when include_draft=true. Questions live at draft_json.questions. */
  draft_json?: { questions?: unknown[] } & Record<string, unknown> | null;
  contract_json?: Record<string, unknown> | null;
  compilation_warnings?: Annotation[];
}

// =============================================================================
// DOCX Extraction Types (NEW)
// =============================================================================

/**
 * Trace table data structure for code execution visualization
 */
export interface TraceTableData {
  headers: string[];
  rows: Record<string, string>[];
  row_count: number;
}

/**
 * A context/layout table extracted from a DOCX question (class interface,
 * I/O example data, etc.). Uses a raw 2D grid rather than header+rows to
 * correctly handle merged cells, which python-docx expands by repeating
 * cell content — deduplicated during extraction.
 */
export interface ContextTableData {
  /** Optional caption/title shown above the table (e.g. "הפעולה תחזיר את המערך הבא:") */
  title?: string | null;
  /** Raw 2D cell grid: grid[row][col]. Merged-cell duplicates already removed. */
  grid: string[][];
  row_count: number;
  col_count: number;
}

/**
 * An annotation attached to an extracted rubric, flagging issues for teacher review.
 * severity=WARNING gates save with teacher acknowledgment via the ContractCompiler.
 */
export interface Annotation {
  annotation_type:
    | 'grounding_issue'
    | 'narrowness_issue'
    | 'clarity_issue'
    | 'review_flag'
    | 'merge_proposal'
    | 'rubric_mismatch'
    | 'invariant_violation';
  severity: 'error' | 'warning' | 'info';
  message: string;
  /** question_id ("q2"), sub-question anchor ("q2.א"), criterion_id, rule_id, or null (global). */
  target_id: string | null;
  /** Auto-computed ID used for acknowledgment tracking. */
  id: string;
}

/**
 * Metadata about the extraction process
 */
export interface ExtractionMetadata {
  /** Source of extraction */
  source: 'pdf_extraction' | 'docx_extraction';
  /** Pipeline version */
  pipeline_version: string;
  /** Whether LLM was used for classification */
  used_llm: boolean;
  /** Total tables found in document */
  total_tables: number;
  /** Total shapes/textboxes found */
  total_shapes: number;
  /** Number of rubric tables identified */
  rubric_tables: number;
  /** Number of trace tables identified */
  trace_tables: number;
  /** Whether reduction rules extraction was enabled */
  reduction_rules_enabled: boolean;
  /** Total reduction rules extracted */
  total_reduction_rules: number;
  /** Whether human review is recommended */
  requires_human_review?: boolean;
  /** Low confidence element IDs */
  low_confidence_elements?: string[];
  /** Best-effort test title extracted from renderer header (DOCX pipeline) */
  test_title?: string;
  /** Best-effort test date extracted from document header (ISO YYYY-MM-DD) */
  test_date?: string;
}

/**
 * Configuration for DOCX extraction pipeline
 */
export interface DocxExtractionConfig {
  /** Subject domain for domain-specific hints (computer_science, mathematics) */
  subject?: 'computer_science' | 'mathematics' | string;
  /** Document locale for pattern matching */
  locale?: 'he-IL' | 'en-US';
  /** Whether to use LLM for classification (default: true) */
  use_llm_classification?: boolean;
  /** Whether to extract reduction rules (default: true) */
  enable_reduction_rules?: boolean;
  /** Programming language for criterion enhancement */
  programming_language?: string;
  /** Number of self-consistency samples for LLM (1 = disabled) */
  self_consistency_samples?: number;
}

/**
 * A single question returned by the fast DOCX preflight scan (Layers 1-2, no LLM).
 * Used by RubricPurpose to let teachers annotate question intent before full extraction.
 */
export interface DocxPreflightQuestion {
  question_number: number;
  /** First ~200 chars of the question text — shown in the purpose-input tooltip */
  full_text_preview?: string;
}

/** Page mapping for a sub-question within a rubric question (PDF flow) */
export interface SubQuestionPageMapping {
  sub_question_id: string;
  criteria_page_indexes: number[];
}

/** Page mapping for a top-level rubric question (PDF flow) */
export interface QuestionPageMapping {
  question_number: number;
  /** @deprecated Question text is now auto-extracted from the PDF */
  question_page_indexes?: number[];
  criteria_page_indexes: number[];
  sub_questions: SubQuestionPageMapping[];
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
  student_name: string;
  filename: string | null;
  total_score: number;
  total_possible: number;
  percentage: number;
  created_at: string;
  graded_json: {
    student_name?: string;
    filename?: string;
    total_score?: number;
    total_possible?: number;
    percentage?: number;
    grades?: GradeItem[];
    question_grades?: QuestionGrade[];
    low_confidence_items?: string[];
    rubric_mismatch_detected?: boolean;
    rubric_mismatch_reason?: string;
  };
  student_answers_json?: StudentAnswersJson | null;
}

export interface StudentAnswerInput {
  question_number: number;
  sub_question_id: string | null;
  answer_text: string;
}


// =============================================================================
// Rubric API Functions
// =============================================================================




// =============================================================================
// Ontology Rubric Save Types (NEW - Atomic Save+Compile)
// =============================================================================

/** Annotation/warning from compilation */
export interface RubricAnnotation {
  id: string;
  annotation_type: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  target_id?: string | null;
}

/** Validation error detail with Hebrew message */
export interface ValidationErrorDetail {
  location: string;
  message: string;
  message_he: string;
}

/**
 * Structured compilation-error detail — the shape the backend's
 * `rubric_management.py::_compile_error_payload` emits for an INV violation.
 * These fields (location / invariant / expected / actual / message_he) are
 * ALREADY on the wire (verified, PR-4); the frontend simply never modeled them,
 * so RubricErrorDisplay flat-listed `message` and the teacher never saw the
 * named invariant or the arithmetic that PR-3 worked to produce. It rides an
 * HTTPException `detail`, which FastAPI does NOT include in the OpenAPI schema —
 * so this is the ONE response type we hand-write rather than take from codegen
 * (PR-4 finding 5). Keep it in sync with `_compile_error_payload` by hand.
 */
export interface CompileErrorDetail {
  /** Full dotted path of the offending node ("q1.א.2") — the scroll anchor. */
  location: string | null;
  /** The named invariant that broke, e.g. "INV-2". */
  invariant: string | null;
  /** Declared/expected value (stringified Decimal). */
  expected: string | null;
  /** Computed/actual value (stringified Decimal). */
  actual: string | null;
  message: string;
  message_he: string | null;
}

/** Draft rubric in ontology format, as expected by the backend save endpoint */
export interface OntologyRubricDraft {
  questions: QuestionOntology[];
  total_points: number;                 // ACHIEVABLE — must be paired with selection_groups
  /** MUST be round-tripped: without it the backend recomputes achievable as the full
   *  offered sum and rejects the rubric on INV-4. */
  selection_groups?: SelectionGroup[];
  num_questions: number;
  num_sub_questions: number;
  num_criteria: number;
  name?: string;
  description?: string;
  programming_language?: string;
  metadata?: ExtractionMetadata;
  /**
   * PR-6 (A1) — these three were being DROPPED at the save boundary: the draft
   * literal never carried them, so `draft_json` stored an empty annotations list,
   * no advisories at all, and no extraction provenance. Round-tripping them is
   * what lets a reopened rubric still show its findings, its residual text and its
   * advisory-scan status.
   *
   * ⚠️ Sending `annotations` WAKES the compiler's acknowledgment gate, which has
   * never fired in this flow (it acks only WARNING annotations present in the
   * submitted draft). Every save must therefore carry `acknowledged_warning_ids`
   * derived from her decisions — see acknowledgedIdsFor in utils/findings.
   */
  annotations?: Annotation[];
  pedagogical_mistakes?: PedagogicalMistakeWire[];
}

/** Request to save ontology rubric with atomic compilation */
export interface SaveOntologyRubricRequest {
  name: string;
  description?: string;
  draft: OntologyRubricDraft;
  acknowledged_warning_ids?: string[];
  /** PR-1 provenance: the extraction job this draft came from (if any). */
  extraction_job_id?: string;
}

/** Success response from ontology rubric save */
export interface SaveOntologyRubricSuccess {
  rubric_id: string;
  name: string;
  is_ontology_format: true;
  is_compiled: true;
  needs_recompilation: false;
  created_at: string;
  stats: {
    total_points: number;
    total_questions: number;
    total_criteria: number;
    total_sub_criteria: number;
  };
}

/** Response when warnings require acknowledgment */
export interface SaveOntologyRubricWarnings {
  status: 'warnings_require_acknowledgment';
  message_he: string;
  warnings: RubricAnnotation[];
}

/** Error response from validation or compilation failure */
export interface SaveOntologyRubricError {
  error_type: 'validation_failed' | 'compilation_failed';
  message_he: string;
  errors: Array<ValidationErrorDetail | RubricAnnotation | CompileErrorDetail>;
}

/** Union type for save responses */
export type SaveOntologyRubricResponse =
  | SaveOntologyRubricSuccess
  | SaveOntologyRubricWarnings;

/** Type guard for warnings response */
export function isWarningsResponse(
  response: SaveOntologyRubricResponse
): response is SaveOntologyRubricWarnings {
  return 'status' in response && response.status === 'warnings_require_acknowledgment';
}

/** Custom error class for rubric save failures */
export class RubricSaveError extends Error {
  constructor(
    public readonly errorType: 'validation_failed' | 'compilation_failed',
    public readonly messageHe: string,
    public readonly errors: Array<ValidationErrorDetail | RubricAnnotation | CompileErrorDetail>,
  ) {
    super(messageHe);
    this.name = 'RubricSaveError';
  }
}

/**
 * Save ontology rubric with atomic compilation.
 * 
 * INVARIANT: A saved rubric is always a compiled rubric.
 * 
 * @param request - The save request with draft and optional acknowledged warnings
 * @returns Success response or warnings response (never throws for warnings)
 * @throws RubricSaveError for validation/compilation failures
 */
export async function saveOntologyRubric(
  request: SaveOntologyRubricRequest
): Promise<SaveOntologyRubricResponse> {
  const response = await apiFetchRaw(`/api/v0/rubrics/save_ontology_draft`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
          },
    body: JSON.stringify({
      name: request.name,
      description: request.description,
      draft: request.draft,
      acknowledged_warning_ids: request.acknowledged_warning_ids || [],
      extraction_job_id: request.extraction_job_id ?? null,
    }),
  });
  throwIfAuthError(response);   // 401/403 stays terminal; this site owns only 4xx domain branching

  const data = await response.json();

  // 2xx success - could be success or warnings
  if (response.ok) {
    return data as SaveOntologyRubricResponse;
  }

  // 400 error - validation or compilation failure
  if (response.status === 400 && data.detail) {
    const detail = data.detail;
    throw new RubricSaveError(
      detail.error_type || 'validation_failed',
      detail.message_he || 'שגיאה בשמירת המחוון',
      detail.errors || [],
    );
  }

  // Other errors
  throw new Error(data.detail?.message_he || data.detail || `HTTP ${response.status}`);
}

/**
 * Update ontology rubric with atomic recompilation.
 * 
 * @param rubricId - ID of rubric to update
 * @param request - Update request with draft and optional acknowledged warnings
 * @returns Success response or warnings response
 * @throws RubricSaveError for validation/compilation failures
 */
export async function updateOntologyRubric(
  rubricId: string,
  request: Omit<SaveOntologyRubricRequest, 'name'> & { edit_summary?: string }
): Promise<SaveOntologyRubricResponse> {
  const response = await apiFetchRaw(`/api/v0/rubrics/${rubricId}/draft`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
          },
    body: JSON.stringify({
      draft: request.draft,
      acknowledged_warning_ids: request.acknowledged_warning_ids || [],
      edit_summary: request.edit_summary,
    }),
  });
  throwIfAuthError(response);   // 401/403 stays terminal; this site owns only 4xx domain branching

  const data = await response.json();

  if (response.ok) {
    return data as SaveOntologyRubricResponse;
  }

  if (response.status === 400 && data.detail) {
    const detail = data.detail;
    throw new RubricSaveError(
      detail.error_type || 'validation_failed',
      detail.message_he || 'שגיאה בעדכון המחוון',
      detail.errors || [],
    );
  }

  if (response.status === 404) {
    throw new Error('המחוון לא נמצא');
  }

  throw new Error(data.detail?.message_he || data.detail || `HTTP ${response.status}`);
}

export async function getRubric(rubricId: string): Promise<RubricDetailItem> {
  const response = await apiFetchChecked(`/api/v0/rubrics/${rubricId}?include_draft=true`, {
      });


  return response.json();
}

export async function listRubrics(): Promise<RubricListItem[]> {
  const response = await apiFetchChecked(`/api/v0/rubrics`, {
      });


  const data = await response.json();
  return data.rubrics ?? data;
}


// =============================================================================
// DOCX Extraction API Functions (NEW)
// =============================================================================

/**
 * Check if a file is a DOCX document
 */
export function isDocxFile(file: File): boolean {
  return file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    file.name.toLowerCase().endsWith('.docx');
}

/**
 * Check if a file is a PDF document
 */
export function isPdfFile(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

/**
 * Response from the preflight DOCX scan (fast, no LLM).
 */


/**
 * Extract rubric from DOCX file using the new pipeline.
 */
export async function extractRubricFromDocx(
  file: File,
  config: DocxExtractionConfig & {
    name?: string;
    description?: string;
    questionPurposes?: Record<string, string>;
    testTopic?: string;
  } = {}
): Promise<ExtractRubricResponse> {
  if (!isDocxFile(file)) {
    throw new Error('File must be a DOCX document');
  }

  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams();

  if (config.name) params.append('name', config.name);
  if (config.description) params.append('description', config.description);
  if (config.subject) params.append('subject', config.subject);
  if (config.locale) params.append('locale', config.locale);
  if (config.programming_language) params.append('programming_language', config.programming_language);

  if (config.use_llm_classification !== undefined) {
    params.append('use_llm_classification', config.use_llm_classification.toString());
  }
  if (config.enable_reduction_rules !== undefined) {
    params.append('enable_reduction_rules', config.enable_reduction_rules.toString());
  }
  if (config.self_consistency_samples !== undefined) {
    params.append('self_consistency_samples', config.self_consistency_samples.toString());
  }

  // Teacher-provided purpose inputs (sent as multipart form fields)
  if (config.questionPurposes && Object.keys(config.questionPurposes).length > 0) {
    formData.append('question_purposes', JSON.stringify(config.questionPurposes));
  }
  if (config.testTopic) {
    formData.append('test_topic', config.testTopic);
  }

  const url = params.toString()
    ? `${API_BASE}/api/v0/grading/extract_rubric_docx?${params.toString()}`
    : `${API_BASE}/api/v0/grading/extract_rubric_docx`;

  const response = await apiFetchChecked(url, {
    method: 'POST',
        body: formData,
  });


  return response.json();
}

// ---------------------------------------------------------------------------
// PR-1: Async rubric-extraction jobs (submit → poll → result → retry)
// ---------------------------------------------------------------------------

export interface SubmitExtractionJobResponse {
  job_id: string;
  status: string;             // 'queued'
  reused: boolean;            // true = an identical active job already existed
}

export interface ExtractionJobStatus {
  job_id: string;
  status: 'queued' | 'extracting' | 'completed' | 'failed';
  progress_stage: string | null;
  progress_detail: string | null;
  /** extracting + heartbeat lapsed — the server instance died mid-job; retry. */
  stale: boolean;
  error_message: string | null;
  has_result: boolean;
  source_filename: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  elapsed_seconds: number | null;
}

export interface ExtractionJobResult {
  job_id: string;
  result: ExtractRubricResponse;
  warnings: string[];
  errors: string[];
  requires_review: boolean | null;
  provenance: Record<string, unknown>;
}

const EXTRACTION_JOBS_BASE = '/api/v0/rubrics/extraction-jobs';

/** Submit a DOCX for async extraction. Returns immediately with a job id. */
export async function submitExtractionJob(
  file: File,
  config: {
    name?: string;
    description?: string;
    subject?: string;
    locale?: string;
    testTopic?: string;
    questionPurposes?: Record<string, string>;
  } = {}
): Promise<SubmitExtractionJobResponse> {
  if (!isDocxFile(file)) {
    throw new Error('File must be a DOCX document');
  }
  const formData = new FormData();
  formData.append('file', file);
  if (config.name) formData.append('name', config.name);
  if (config.description) formData.append('description', config.description);
  formData.append('subject', config.subject || 'computer_science');
  formData.append('locale', config.locale || 'he-IL');
  if (config.testTopic) formData.append('test_topic', config.testTopic);
  if (config.questionPurposes && Object.keys(config.questionPurposes).length > 0) {
    formData.append('question_purposes', JSON.stringify(config.questionPurposes));
  }

  // Trailing slash is deliberate — avoids a 307 redirect that can drop the body.
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/`, {
    method: 'POST',
        body: formData,
  });
  return response.json();
}

/** Poll one job's status (light — no result payload). */
export async function getExtractionJob(jobId: string): Promise<ExtractionJobStatus> {
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/${jobId}`, {
      });
  return response.json();
}

/** Fetch a completed job's ExtractRubricResponse (+ warnings + provenance). */
export async function getExtractionJobResult(jobId: string): Promise<ExtractionJobResult> {
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/${jobId}/result`, {
      });
  return response.json();
}

/**
 * PR-5 S1-2: patch metadata (name / programming_language) onto a running job.
 * METADATA-ONLY by contract — the runner never reads these; they persist in
 * request_params for save/resume. Backend merges atomically (jsonb ||), so
 * omitted keys are untouched. Fire from the capture card (one combined PATCH).
 */
export async function patchExtractionJobMetadata(
  jobId: string,
  patch: { name?: string | null; programming_language?: string | null },
): Promise<{ job_id: string; status: string }> {
  const response = await apiFetchChecked(
    `${EXTRACTION_JOBS_BASE}/${jobId}`,
    jsonInit('PATCH', patch),
  );
  return response.json();
}

/** Re-queue a failed or stale job. The source DOCX is stored server-side — no re-upload. */
/**
 * LIV-1 — let the teacher END an active extraction she no longer wants to wait
 * for. Deadlines guarantee an orphan eventually expires, but "eventually" is a
 * window in which she is attached to a job she cannot escape; this is her exit.
 * 409 means it already finished — the caller should just re-read the job.
 */
export async function abandonExtractionJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/${jobId}/abandon`, {
    method: 'POST',
  });
  return response.json();
}

export async function retryExtractionJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/${jobId}/retry`, {
    method: 'POST',
      });
  return response.json();
}

/** List jobs (active=true → queued/extracting only: the resume surface). */
export async function listExtractionJobs(
  options: { active?: boolean; limit?: number } = {}
): Promise<ExtractionJobStatus[]> {
  const params = new URLSearchParams();
  if (options.active) params.append('active', 'true');
  if (options.limit) params.append('limit', String(options.limit));
  const qs = params.toString();
  const response = await apiFetchChecked(`${EXTRACTION_JOBS_BASE}/${qs ? `?${qs}` : ''}`, {
      });
  return response.json();
}

/**
 * Universal rubric extraction that automatically detects file type.
 */
/**
 * Universal rubric extraction — DOCX only.
 * Routes to extractRubricFromDocx.
 */
export async function extractRubricUniversal(
  file: File,
  options: {
    name?: string;
    description?: string;
    subject?: DocxExtractionConfig['subject'];
    locale?: DocxExtractionConfig['locale'];
  } = {}
): Promise<ExtractRubricResponse> {
  if (!isDocxFile(file)) {
    throw new Error('Only DOCX files are supported. Please upload a .docx file.');
  }
  return extractRubricFromDocx(file, {
    name: options.name,
    description: options.description,
    subject: options.subject,
    locale: options.locale,
  });
}

// =============================================================================
// Student Test API Functions
// =============================================================================

export async function previewStudentTestPdf(file: File): Promise<PreviewStudentTestResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiFetchChecked(`/api/v0/grading/preview_student_test_pdf`, {
    method: 'POST',
        body: formData,
  });


  return response.json();
}


// =============================================================================
// Graded Tests List API Functions
// =============================================================================

/** @deprecated Use GradedTestListItem from @/types/graded_test instead. */
export interface LegacyGradedTestListItem {
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
export async function listAllGradedTests(): Promise<LegacyGradedTestListItem[]> {
  // First, get all rubrics
  const rubrics = await listRubrics();

  // For now, we'll get graded tests from the graded_tests list per rubric
  // The backend currently returns graded tests in the batch response
  // We need to aggregate them
  const allTests: LegacyGradedTestListItem[] = [];

  // Build a map of rubric names
  const rubricNames = new Map<string, string>();
  for (const r of rubrics) {
    rubricNames.set(r.id, r.name || 'מחוון ללא שם');
  }

  // Fetch graded tests for each rubric
  for (const rubric of rubrics) {
    try {
      const response = await apiFetchChecked(`/api/v0/grading/rubric/${rubric.id}/graded_tests`);
      if (response.ok) {
        const tests: LegacyGradedTestListItem[] = await response.json();
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
  const response = await apiFetchChecked(`/api/v0/grading/graded_test/${testId}`);


  return response.json();
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

export interface ShareHistoryItem {
  id: string;
  recipient_email: string;
  shared_at: string;
  status: 'pending' | 'accepted' | 'revoked';
  accepted_at?: string;
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
  const response = await apiFetchChecked(`/api/v0/rubric_generator/share_email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      rubric_id: rubricId,
      recipient_email: recipientEmail,
      sender_name: senderName,
      include_pdf: includePdf,
    }),
  });


  return response.json();
}

/**
 * Accept a shared rubric (copy to user's account).
 */
export async function acceptRubricShare(
  token: string
): Promise<{ success: boolean; message: string; rubric_id?: string; redirect_url?: string }> {
  const response = await apiFetchChecked(`/api/v0/rubric_generator/accept_share/${token}`, {
      });


  return response.json();
}

export async function getShareHistory(
  rubricId: string
): Promise<{ shares: ShareHistoryItem[]; total_count: number }> {
  const response = await apiFetchChecked(`/api/v0/rubric_generator/share_history/${rubricId}`, {
      });


  return response.json();
}

// =============================================================================
// ONTOLOGY GRADING API (v2.0)
// =============================================================================

import type {
  BatchGradeRequest,
  BatchGradeResponse,
  SessionDetailResponse,
  SessionResumeResponse,
  OntologyGradeRequest,
  OntologyGradeResponse,
  CompileRubricResponse,
} from './ontology-types';

// Re-export ontology types for convenience
export type {
  QuoteValidationStatus,
  ConfidenceLevel,
  FlagReason,
  GradedTestStatus,
  SessionStatus,
  BatchStatus,
  AnswerQuotation,
  EvidenceClaim,
  RuleOutcome,
  CriterionOutcome,
  QuestionOutcome,
  FlaggedOutcome,
  GradedTestDraft,
  OntologyStudentAnswer,
  StudentInput,
  BatchGradeRequest,
  BatchGradeResponse,
  SessionDetailResponse,
  OntologyGradeRequest,
  OntologyGradeResponse,
  CompileRubricResponse,
} from './ontology-types';


// P5: `listBatches` DELETED — zero callers repo-wide, and it spoke a
// competing contract (GET /api/v0/grading/batches, rows keyed on `batch_id`
// with session counters) against the live lister `listGradingBatches`
// (GET /api/v0/batches → BatchListItem). Two listers for one concept is the
// duplicate-schema trap; the dead one goes. If filtering/pagination is ever
// wanted, build it on /api/v0/batches — do not resurrect this.

/**
 * Resume an interrupted grading session.
 * Session will resume from last checkpoint if available.
 *
 * @param sessionId - Session identifier
 * @param force - Force resume even if session appears active
 */
export async function resumeSession(
  sessionId: string,
  force: boolean = false
): Promise<SessionResumeResponse> {
  const response = await apiFetchChecked(`/api/v0/grading/sessions/${sessionId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
          },
    body: JSON.stringify({ force }),
  });


  return response.json();
}

/**
 * Cancel a grading session.
 * Only pending or in-progress sessions can be cancelled.
 */
export async function cancelSession(
  sessionId: string
): Promise<{ session_id: string; status: string; message: string }> {
  const response = await apiFetchChecked(`/api/v0/grading/sessions/${sessionId}`, {
    method: 'DELETE',
      });


  return response.json();
}

/**
 * Compile a rubric to create a grading contract.
 * Required before grading with the ontology agent.
 *
 * @param rubricId - Rubric identifier
 * @param acknowledgedWarningIds - IDs of warnings the user has acknowledged
 */
export async function compileRubric(
  rubricId: string,
  acknowledgedWarningIds: string[] = []
): Promise<CompileRubricResponse> {
  const response = await apiFetchChecked(`/api/v0/rubrics/${rubricId}/compile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
          },
    body: JSON.stringify({ acknowledged_warning_ids: acknowledgedWarningIds }),
  });


  return response.json();
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Format decimal string for display.
 * Removes unnecessary trailing zeros.
 *
 * @example
 * formatPoints("85.00") → "85"
 * formatPoints("85.50") → "85.5"
 * formatPoints(85) → "85"
 */
export function formatPoints(points: string | number): string {
  const num = typeof points === 'string' ? parseFloat(points) : points;
  if (isNaN(num)) return '0';

  // If it's a whole number, return without decimals
  if (num % 1 === 0) {
    return num.toString();
  }

  // Otherwise, show up to 2 decimals, removing trailing zeros
  return num.toFixed(2).replace(/\.?0+$/, '');
}

/**
 * Calculate percentage from two point values.
 * Returns whole number percentage (0-100).
 */
export function calculatePercentage(earned: string | number, possible: string | number): number {
  const e = typeof earned === 'string' ? parseFloat(earned) : earned;
  const p = typeof possible === 'string' ? parseFloat(possible) : possible;

  if (isNaN(e) || isNaN(p) || p === 0) return 0;
  return Math.round((e / p) * 100);
}

/**
 * Get a human-readable label for a flag reason.
 */
export function getFlagReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    no_answer: 'לא נמצאה תשובה',
    quote_not_found: 'לא נמצא ציטוט',
    low_confidence: 'ביטחון נמוך',
    fuzzy_match: 'התאמה לא מדויקת',
    max_retries_exceeded: 'חריגה ממספר ניסיונות',
    unmeasurable: 'לא ניתן למדידה',
    llm_uncertainty: 'חוסר וודאות',
    closed_world_violation: 'חריגה מהמחוון',
  };
  return labels[reason] || reason;
}

/**
 * Get CSS class for confidence level indicator.
 */
export function getConfidenceColorClass(level: string): string {
  switch (level) {
    case 'high':
      return 'text-emerald-500';
    case 'medium':
      return 'text-amber-500';
    case 'low':
      return 'text-red-500';
    default:
      return 'text-gray-400';
  }
}

/**
 * Get icon and color for quote validation status.
 */
export function getQuoteValidationDisplay(status: string): {
  icon: '✓' | '~' | '✗';
  colorClass: string;
  label: string;
} {
  switch (status) {
    case 'exact':
      return { icon: '✓', colorClass: 'text-emerald-500', label: 'התאמה מדויקת' };
    case 'fuzzy':
      return { icon: '~', colorClass: 'text-amber-500', label: 'התאמה חלקית' };
    case 'not_found':
      return { icon: '✗', colorClass: 'text-red-500', label: 'לא נמצא' };
    default:
      return { icon: '~', colorClass: 'text-gray-400', label: 'לא ידוע' };
  }
}



// =============================================================================
// Classroom API — Students, Classes, Membership
// =============================================================================

import type {
  StudentResponse,
  StudentDetailResponse,
  ClassResponse,
  ClassDetailResponse,
  SubjectMatterOption,
  CreateStudentBody,
  UpdateStudentBody,
  CreateClassBody,
  UpdateClassBody,
} from '@/types/classroom';
import { ClassroomConflictError } from '@/types/classroom';

export type {
  StudentResponse,
  StudentDetailResponse,
  ClassResponse,
  ClassDetailResponse,
  SubjectMatterOption,
  CreateStudentBody,
  UpdateStudentBody,
  CreateClassBody,
  UpdateClassBody,
};
export { ClassroomConflictError };

async function _classroomFetch(url: string, options: RequestInit = {}): Promise<Response> {
  // RAW fetch + explicit status ladder: apiFetchChecked threw a generic
  // ApiError on ANY non-OK, which made the 409 branch below DEAD CODE and
  // silently broke every ClassroomConflictError consumer (StudentPicker's
  // inline "student already exists", the identity wave's conflict pills) —
  // discovered by the D4 journey spec, 2026-08-17. 409 must stay a TYPED
  // conflict at this seam; auth stays terminal; other failures normalize.
  const response = await apiFetchRaw(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) ?? {}),
    },
  });
  throwIfAuthError(response);
  if (response.status === 409) {
    const data = await response.json().catch(() => ({ detail: 'ניגוד' }));
    throw new ClassroomConflictError(data.detail ?? 'ניגוד');
  }
  if (!response.ok) throw await normalizeError(response);
  return response;
}

// Students

export async function listStudents(classId?: string): Promise<{ students: StudentResponse[] }> {
  const url = classId
    ? `${API_BASE}/api/v0/classroom/students?class_id=${classId}`
    : `${API_BASE}/api/v0/classroom/students`;
  const res = await _classroomFetch(url);
  return res.json();
}

export async function getStudent(id: string): Promise<StudentDetailResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/students/${id}`);
  return res.json();
}

export async function createStudent(body: CreateStudentBody): Promise<StudentResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/students`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function updateStudent(id: string, body: UpdateStudentBody): Promise<StudentResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/students/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function deleteStudent(id: string): Promise<void> {
  await _classroomFetch(`${API_BASE}/api/v0/classroom/students/${id}`, { method: 'DELETE' });
}

// Classes

export async function listClasses(): Promise<{ classes: ClassResponse[] }> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/classes`);
  return res.json();
}

export async function getClassDetail(id: string): Promise<ClassDetailResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/classes/${id}`);
  return res.json();
}

export async function createClass(body: CreateClassBody): Promise<ClassResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/classes`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function updateClass(id: string, body: UpdateClassBody): Promise<ClassResponse> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/classroom/classes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function deleteClass(id: string): Promise<void> {
  await _classroomFetch(`${API_BASE}/api/v0/classroom/classes/${id}`, { method: 'DELETE' });
}

// Membership

export async function addStudentToClass(classId: string, studentId: string): Promise<void> {
  await _classroomFetch(`${API_BASE}/api/v0/classroom/classes/${classId}/students`, {
    method: 'POST',
    body: JSON.stringify({ student_id: studentId }),
  });
}

export async function removeStudentFromClass(classId: string, studentId: string): Promise<void> {
  await _classroomFetch(
    `${API_BASE}/api/v0/classroom/classes/${classId}/students/${studentId}`,
    { method: 'DELETE' },
  );
}

// Subject matters

export async function listSubjectMatters(): Promise<SubjectMatterOption[]> {
  const res = await _classroomFetch(`${API_BASE}/api/v0/users/subject-matters`);
  return res.json();
}

// =============================================================================
// S4 Transcription endpoints
// =============================================================================

export async function transcribe(
    rubricId: string,
    file: File,
): Promise<TranscribeResponse> {
    const form = new FormData();
    form.append('file', file);
    form.append('rubric_id', rubricId);

    const res = await apiFetchChecked(`/api/v0/transcriptions/transcribe`, {
        method: 'POST',
        headers: { ...getAuthHeaders() }, // no Content-Type — browser sets multipart boundary
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בתמלול' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בתמלול');
    }
    return res.json() as Promise<TranscribeResponse>;
}

export async function submitGrade(params: {
    transcriptionId: string;
    answers: GradeAnswerInput[];
    studentId: string;
}): Promise<GradeQueuedResponse> {
    const res = await apiFetchChecked(`/api/v0/transcriptions/grade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
            transcription_id: params.transcriptionId,
            answers: params.answers,
            student_id: params.studentId,
        }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בשמירת הבדיקה' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בשמירת הבדיקה');
    }
    return res.json() as Promise<GradeQueuedResponse>;
}

// --- Batch-review Phase 2: the teacher review overlay ------------------------
// Wire types are GENERATED (OD-9) — consumed from api-types.ts, no hand mirror.

export type TranscriptionReview = components['schemas']['TranscriptionReview'];
export type TranscriptionReviewSaveRequest = components['schemas']['ReviewSaveRequest'];

/**
 * Persist the teacher's review working copy (transcriptions.review_json).
 * FULL snapshot, last-write-wins. Domain errors surface as ApiError:
 * 409 = transcription already approved (LCY-1); 422 = the snapshot's answer
 * keys don't match the draft. Never called after a successful accept (Δ4).
 */
export async function saveTranscriptionReview(
    transcriptionId: string,
    body: TranscriptionReviewSaveRequest,
): Promise<TranscriptionReview> {
    return apiFetch<TranscriptionReview>(
        `/api/v0/transcriptions/${transcriptionId}/review`,
        jsonInit('PATCH', body),
    );
}

export async function getTranscriptionPage(
    transcriptionId: string,
    pageNumber: number,
): Promise<TranscriptionPageResponse> {
    const res = await apiFetchChecked(`/api/v0/transcriptions/${transcriptionId}/pages/${pageNumber}`,
        { headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בטעינת הדף' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בטעינת הדף');
    }
    return res.json() as Promise<TranscriptionPageResponse>;
}

// =============================================================================
// S8 — Graded test read endpoints
// =============================================================================

/**
 * Poll this endpoint after submitGrade() to track grading progress.
 * Returns a status-only response while grading runs, the full draft once done,
 * or a failure response.
 */
export async function getGradedTest(id: string): Promise<GradedTestDetailResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}`,
        { headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בטעינת הבדיקה' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בטעינת הבדיקה');
    }
    return res.json() as Promise<GradedTestDetailResponse>;
}

/** List all graded tests for the current user (lean summary — no draft JSON). */
export async function listGradedTests(): Promise<GradedTestListItem[]> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_tests`,
        { headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בטעינת הבדיקות' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בטעינת הבדיקות');
    }
    return res.json() as Promise<GradedTestListItem[]>;
}

/**
 * Save teacher overrides onto a draft without approving (ungated, partial-work-safe).
 * Only teacher_overrides is updated; AI outcomes remain immutable.
 */
export async function saveGradedTestDraft(
    id: string,
    overrides: GradedTestOverrides,
): Promise<GradedTestDraftResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}/draft`,
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ overrides }),
        },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה בשמירת הטיוטה' }));
        throw new Error((err as { detail?: string }).detail ?? 'שגיאה בשמירת הטיוטה');
    }
    return res.json() as Promise<GradedTestDraftResponse>;
}

/**
 * Approve a graded test: runs the approval gate, compiles the frozen contract,
 * and atomically freezes the row (status → 'approved').
 *
 * On gate failure the backend returns 422 with structured gate_violations.
 * The caller should display these inline.
 */
export async function approveGradedTest(
    id: string,
    overrides: GradedTestOverrides,
): Promise<GradedTestApprovedResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}/approve`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ overrides }),
        },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'שגיאה באישור הבדיקה' }));
        // Preserve gate_violations for the caller to surface inline
        const detail = (err as { detail?: unknown }).detail;
        const error = new Error(
            typeof detail === 'string' ? detail : 'שגיאה באישור הבדיקה'
        ) as Error & { gateViolations?: unknown[] };
        if (detail && typeof detail === 'object' && 'gate_violations' in detail) {
            error.gateViolations = (detail as { gate_violations: unknown[] }).gate_violations;
        }
        throw error;
    }
    return res.json() as Promise<GradedTestApprovedResponse>;
}

// =============================================================================
// S10 — Revision actions: regrade, manual_edit, retry
// =============================================================================

/**
 * Re-grade an approved test against the current (updated) rubric contract version.
 * Source row must be approved, the leaf of its chain, and stale.
 * Returns a RevisionResponse with the new pending row's id; poll GET /graded_test/{id}
 * exactly as in S8 until status reaches 'draft' or 'failed'.
 */
export async function regradeGradedTest(id: string): Promise<RevisionResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}/regrade`,
        { method: 'POST', headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: unknown }).detail;
        throw new Error(typeof detail === 'string' ? detail : `שגיאה בבדיקה מחדש (${res.status})`);
    }
    return res.json() as Promise<RevisionResponse>;
}

/**
 * Open an approved grade for manual editing — no AI re-grading.
 * Creates a 'draft' successor pre-filled with the previous outcomes and overrides.
 * Returns a RevisionResponse with status='draft'; navigate directly to the review panel.
 */
export async function manualEditGradedTest(id: string): Promise<RevisionResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}/manual_edit`,
        { method: 'POST', headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: unknown }).detail;
        throw new Error(typeof detail === 'string' ? detail : `שגיאה בעריכה ידנית (${res.status})`);
    }
    return res.json() as Promise<RevisionResponse>;
}

/**
 * Re-attempt a failed grading run.
 * Creates a 'pending' successor and fires the grading agent.
 * Returns a RevisionResponse with the new pending row's id; poll as in S8.
 */
export async function retryGradedTest(id: string): Promise<RevisionResponse> {
    const res = await apiFetchChecked(`/api/v0/grading/graded_test/${id}/retry`,
        { method: 'POST', headers: { ...getAuthHeaders() } },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: unknown }).detail;
        throw new Error(typeof detail === 'string' ? detail : `שגיאה בניסיון חוזר (${res.status})`);
    }
    return res.json() as Promise<RevisionResponse>;
}

// =============================================================================
// S11 — Batch grading
// =============================================================================

/** One appended batch file (B9 intake v2). */
export interface BatchFileAppendResponse {
    job_id: string;
    filename: string | null;
    test_count: number;
}

/** B9/U3: metadata-only batch create — the queue appends the files. */
export async function createBatchMetadata(
    rubricId: string,
    classId?: string | null,
    name?: string | null,
): Promise<BatchCreateResponse> {
    return apiFetch<BatchCreateResponse>(
        `/api/v0/batches`,
        jsonInit('POST', {
            rubric_id: rubricId,
            class_id: classId ?? null,
            name: name ?? null,
        }),
    );
}

/** U3: the append failed with an HTTP status — carries the server's Hebrew
 *  detail. A 422 is a VALIDATION verdict (terminal, never retried). */
export class UploadHttpError extends Error {
    constructor(public readonly status: number, detail: string) {
        super(detail);
        this.name = 'UploadHttpError';
    }
}

/** U3: the caller aborted (unmount) — never surfaces as a failure. */
export class UploadAbortError extends Error {
    constructor() {
        super('upload aborted');
        this.name = 'UploadAbortError';
    }
}

export interface XhrUploadHandle {
    promise: Promise<BatchFileAppendResponse>;
    abort: () => void;
}

/**
 * B9/U3: append ONE file to a batch over XHR — fetch cannot observe upload
 * progress (B9.6). Idempotent on client_file_id: a retry with the SAME id
 * returns the existing job instead of duplicating a test (the queue owns the
 * id for the file's lifetime, so retries can never mint a new identity).
 * The returned abort() is fired on unmount — no zombie uploads.
 */
export function appendBatchFileXHR(
    batchId: string,
    file: File,
    clientFileId: string,
    onProgress: (pct: number) => void,
): XhrUploadHandle {
    const xhr = new XMLHttpRequest();
    const promise = new Promise<BatchFileAppendResponse>((resolve, reject) => {
        xhr.open('POST', `${API_BASE}/api/v0/batches/${batchId}/files`);
        for (const [k, v] of Object.entries(getAuthHeaders())) {
            if (k.toLowerCase() !== 'content-type') xhr.setRequestHeader(k, v);
        }
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText) as BatchFileAppendResponse);
                } catch {
                    reject(new UploadHttpError(xhr.status, 'תגובת שרת לא תקינה'));
                }
                return;
            }
            let detail = `שגיאה בהעלאה (${xhr.status})`;
            try {
                const parsed = JSON.parse(xhr.responseText) as { detail?: unknown };
                if (typeof parsed.detail === 'string') detail = parsed.detail;
            } catch { /* keep the generic detail */ }
            reject(new UploadHttpError(xhr.status, detail));
        };
        xhr.onerror = () => reject(new Error('network'));
        xhr.onabort = () => reject(new UploadAbortError());
        const form = new FormData();
        form.append('file', file);
        form.append('client_file_id', clientFileId);
        xhr.send(form);   // no Content-Type — the browser sets the multipart boundary
    });
    return { promise, abort: () => xhr.abort() };
}

/** Poll this for transcription progress and grading progress. */
export async function getBatch(id: string): Promise<BatchDetailResponse> {
    const res = await apiFetchChecked(`/api/v0/batches/${id}`, {
            });
    if (!res.ok) throw new Error(`Failed to fetch batch ${id}: ${res.status}`);
    return res.json() as Promise<BatchDetailResponse>;
}

/**
 * Retry a failed (or expired) transcription job — Cloud Tasks migration.
 * The source PDF is durable in GCS, so no re-upload is involved.
 */
export async function retryBatchJob(
    batchId: string,
    jobId: string,
): Promise<{ job_id: string; status: string }> {
    // F2: apiFetch throws a normalized ApiError whose message IS the server's
    // Hebrew detail (e.g. the retry 409's "המשימה עדיין פעילה או שכבר הושלמה")
    // — no hand-rolled English fallback may shadow it.
    return apiFetch<{ job_id: string; status: string }>(
        `/api/v0/batches/${batchId}/jobs/${jobId}/retry`,
        { method: 'POST' },
    );
}

/** B5: rename a batch (stripped server-side; blank → 422 with Hebrew detail). */
export async function renameBatch(
    batchId: string,
    name: string,
): Promise<{ batch_id: string; name: string }> {
    return apiFetch<{ batch_id: string; name: string }>(
        `/api/v0/batches/${batchId}`,
        jsonInit('PATCH', { name }),
    );
}

export async function listGradingBatches(): Promise<{ batches: BatchListItem[] }> {
    const res = await apiFetchChecked(`/api/v0/batches`, {
            });
    if (!res.ok) throw new Error(`Failed to list batches: ${res.status}`);
    // Backend returns array; wrap for consistency
    const data = await res.json();
    return { batches: Array.isArray(data) ? data : [] };
}

/** One skipped row in a bulk-accept response (B1). */
export interface AcceptCleanSkipped {
    transcription_id: string;
    skipped_reason: 'flagged' | 'has_review_edits' | 'already_approved';
}

/**
 * Bulk-accept all clean transcriptions in one action. "Clean" is a
 * SERVER-guaranteed property (B1): flagged/edited/already-approved items come
 * back in `skipped` and the dashboard surfaces every one (F4).
 */
export async function acceptCleanTranscriptions(
    batchId: string,
    items: AcceptCleanItem[],
): Promise<{ accepted: number; skipped: AcceptCleanSkipped[] }> {
    const data = await apiFetch<{ accepted: number; skipped?: AcceptCleanSkipped[] }>(
        `/api/v0/batches/${batchId}/accept_clean`,
        jsonInit('POST', { items }),
    );
    return { accepted: data.accepted, skipped: data.skipped ?? [] };
}

/**
 * Accept a single flagged transcription with teacher-reviewed answers.
 */
export async function acceptOneTranscription(
    batchId: string,
    transcriptionId: string,
    studentId: string,
    answers: GradeAnswerInputItem[],
): Promise<{ accepted: number }> {
    const res = await apiFetchChecked(`/api/v0/batches/${batchId}/accept/${transcriptionId}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ student_id: studentId, answers }),
        },
    );
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: unknown }).detail;
        throw new Error(typeof detail === 'string' ? detail : `שגיאה באישור תמלול (${res.status})`);
    }
    return res.json() as Promise<{ accepted: number }>;
}
