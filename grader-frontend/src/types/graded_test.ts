/**
 * TypeScript mirrors of backend response schemas (S8 + S9 + S10).
 *
 * Decimal fields from the backend are serialized as strings.
 * Points values (points_possible, points_awarded) come as strings; parse with parseFloat()
 * or keep as strings for display — never do arithmetic on them as numbers.
 */

// ---------------------------------------------------------------------------
// Grading annotation (mirrors GradingAnnotation in graded_test_draft.py)
// ---------------------------------------------------------------------------

export type AnnotationSeverity = 'error' | 'warning' | 'info'

export interface GradingAnnotation {
  id: string
  severity: AnnotationSeverity
  target_id: string
  annotation_type:
    | 'closed_world_violation'
    | 'ungraded_criterion'
    | 'bounds_clamped'
    | 'quote_not_found'
    | 'fuzzy_match'
    | 'no_answer'
    | 'llm_failure'
  message: string
  metadata: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Outcome types (mirror graded_test_draft.py hierarchy)
// ---------------------------------------------------------------------------

export interface FlaggedOutcome {
  criterion_id?: string
  question_id?: string
  reason: string
  message?: string
}

export interface AnswerQuotation {
  quote_text: string
  validation_status: 'exact' | 'fuzzy' | 'not_found'
}

export interface SubCriterionOutcome {
  sub_criterion_id: string
  description: string
  points_possible: string   // Decimal serialized as string
  points_awarded: string
  reasoning: string
  confidence: number
  evidence_quote: AnswerQuotation | null
  flags: FlaggedOutcome[]
}

export interface CriterionOutcome {
  criterion_id: string
  description: string
  points_possible: string
  points_awarded: string
  reasoning: string
  confidence: number
  evidence_quote: AnswerQuotation | null
  sub_criterion_outcomes: SubCriterionOutcome[] | null
  flags: FlaggedOutcome[]
}

export interface ScopeOutcome {
  scope_kind: 'direct' | 'sub_question'
  question_id: string
  sub_question_id: string | null
  points_possible: string
  points_awarded: string
  min_confidence: number
  criterion_outcomes: CriterionOutcome[]
  flags: FlaggedOutcome[]
  // 'excluded_by_selection' (PR-3): a "choose k of N" member that did not make the
  // student's best-k. It is EXCLUDED from the score, not given 0 — the unchosen
  // questions were never owed. NOTE: this mark is PROVISIONAL (computed at grading
  // time); a teacher override can flip which member wins the slot, so the approval
  // gate recomputes it server-side and THAT is what freezes.
  graded_by: 'llm' | 'skipped_no_answer' | 'failed' | 'excluded_by_selection'
  retry_count: number
  input_tokens: number
  output_tokens: number
}

export interface UnmatchedAnswer {
  question_number: number
  sub_question_id: string | null
  answer_text: string
}

// ---------------------------------------------------------------------------
// S9 — Teacher override types (mirrors graded_test_draft.py)
// ---------------------------------------------------------------------------

/** One terminal criterion's teacher edit. */
export interface TeacherOverride {
  points_awarded: string          // Decimal as string
  teacher_comment: string | null
}

/** Sparse map: terminal_id → teacher's override. Only changed terminals appear. */
export type GradedTestOverrides = Record<string, TeacherOverride>

// ---------------------------------------------------------------------------
// S9 — GradedTestContract types (mirrors graded_test_contract.py)
// ---------------------------------------------------------------------------

/** Provenance-preserving frozen record for one terminal criterion. */
export interface ContractTerminalOutcome {
  terminal_id: string
  terminal_kind: 'criterion' | 'sub_criterion'
  description: string
  points_possible: string
  ai_points_awarded: string       // What the AI originally awarded
  ai_reasoning: string
  ai_evidence_quote: AnswerQuotation | null
  was_overridden: boolean
  teacher_comment: string | null
  final_points_awarded: string    // Authoritative: teacher's value if overridden, else AI's
}

export interface ContractScopeOutcome {
  scope_kind: 'direct' | 'sub_question'
  question_id: string
  sub_question_id: string | null
  points_possible: string
  final_points_awarded: string
  terminal_outcomes: ContractTerminalOutcome[]
}

/** Frozen, approved graded test contract (stored in contract_json). */
export interface GradedTestContract {
  schema_version: string
  contract_version: string
  rubric_contract_version: string
  transcription_contract_version: string
  model_version: string
  prompt_version: string
  scope_outcomes: ContractScopeOutcome[]
  total_score: string
  total_possible: string
  percentage: string
  approved_at: string
}

// ---------------------------------------------------------------------------
// GradedTestDraft (mirrors GradedTestDraft in graded_test_draft.py)
// ---------------------------------------------------------------------------

export interface GradedTestDraft {
  schema_version: string
  rubric_contract_version: string
  transcription_contract_version: string
  model_version: string
  prompt_version: string
  scope_outcomes: ScopeOutcome[]
  teacher_overrides: GradedTestOverrides
  annotations: GradingAnnotation[]
  unmatched_transcription_answers: UnmatchedAnswer[]
  llm_calls_count: number
  grading_duration_ms: number
  total_input_tokens: number
  total_output_tokens: number
}

// ---------------------------------------------------------------------------
// Read endpoint response shapes
// ---------------------------------------------------------------------------

/** Returned while grading is in flight (status='pending' or 'grading'). */
export interface GradedTestStatusResponse {
  id: string
  status: 'pending' | 'grading'
  student_name: string
}

/** Returned once grading completes (status='draft' or 'approved'). */
export interface GradedTestDraftResponse {
  id: string
  status: 'draft' | 'approved'
  student_name: string
  filename: string | null
  total_score: string | null
  total_possible: string | null
  percentage: string | null
  total_cost_usd: string | null
  transcription_id: string
  draft: GradedTestDraft
  rubric_contract_stale: boolean        // S10: true if rubric has been recompiled since grading
  regraded_from_id: string | null       // S10: back-pointer to the predecessor row
}

/** Returned once a draft is teacher-approved (status='approved'). S9 */
export interface GradedTestApprovedResponse {
  id: string
  status: 'approved'
  student_name: string
  filename: string | null
  total_score: string | null
  total_possible: string | null
  percentage: string | null
  total_cost_usd: string | null
  transcription_id: string
  draft: GradedTestDraft
  contract: GradedTestContract
  approved_at: string
  rubric_contract_stale: boolean        // S10: true if rubric has been recompiled since approval
  regraded_from_id: string | null       // S10: back-pointer to the predecessor row
}

/** Returned when grading failed (status='failed'). */
export interface GradedTestFailedResponse {
  id: string
  status: 'failed'
  error_message: string | null
}

/** Union of all possible detail responses from GET /graded_test/{id}. */
export type GradedTestDetailResponse =
  | GradedTestStatusResponse
  | GradedTestDraftResponse
  | GradedTestApprovedResponse
  | GradedTestFailedResponse

/** Lean list-view item from GET /graded_tests (no draft JSON). */
export interface GradedTestListItem {
  id: string
  student_name: string
  filename: string | null
  status: string
  total_score: string | null
  total_possible: string | null
  percentage: string | null
  rubric_contract_version: string
  created_at: string
  rubric_contract_stale: boolean        // S10: true if rubric has been recompiled since grading
}

// ---------------------------------------------------------------------------
// S10 — Revision action response
// ---------------------------------------------------------------------------

/** Returned by POST .../regrade, .../manual_edit, .../retry */
export interface RevisionResponse {
  graded_test_id: string
  status: 'pending' | 'draft'
}
