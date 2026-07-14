/**
 * Ontology Types for Vivi Grading System v2.0
 *
 * This file defines TypeScript types that mirror the backend ontology_types.py.
 * These types are the contract between frontend and backend for grading operations.
 *
 * @see API_GUIDE.md for endpoint documentation
 * @see ontology_types.py for backend source of truth
 */

// =============================================================================
// ENUMS
// =============================================================================

/**
 * Result of validating a quote against the student's answer.
 * Used to show teachers how confident the AI is about evidence citations.
 */
export type QuoteValidationStatus = 'exact' | 'fuzzy' | 'not_found';

/**
 * Calibrated confidence levels for grading decisions.
 * Guides teacher review attention:
 * - high: >95% accurate, exact evidence found
 * - medium: 70-95%, partial evidence or edge case
 * - low: <70%, definitely needs human review
 */
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/**
 * Reasons for flagging an outcome for teacher review.
 * Displayed in the UI to explain why an item needs attention.
 */
export type FlagReason =
    | 'no_answer'
    | 'quote_not_found'
    | 'low_confidence'
    | 'fuzzy_match'
    | 'max_retries_exceeded'
    | 'unmeasurable'
    | 'llm_uncertainty'
    | 'closed_world_violation';

/**
 * Status of a graded test in its lifecycle.
 * Follows the Draft → Contract pattern.
 */
export type GradedTestStatus = 'draft' | 'pending_review' | 'approved' | 'saved' | 'released';

/**
 * Status of a grading session.
 */
export type SessionStatus = 'initialized' | 'grading' | 'completed' | 'failed';

/**
 * Status of a batch grading operation.
 */
export type BatchStatus =
    | 'processing'
    | 'in_progress'
    | 'completed'
    | 'partially_completed'
    | 'failed';

/**
 * Type of evidence claim made by the grading agent.
 */
export type ClaimType = 'presence' | 'correctness' | 'coverage' | 'constraint' | 'quality';

// =============================================================================
// EVIDENCE TYPES
// =============================================================================

/**
 * Citation from student's actual work.
 * The quote_text is the ground truth evidence.
 */
export interface AnswerQuotation {
    /** The actual quoted text from student work */
    quote_text: string;
    /** Human-readable hint like 'line 5' or 'in function main' */
    position_hint?: string;
    /** v2.0: Validation result against original answer */
    validation_status?: QuoteValidationStatus;
}

/**
 * Atomic evidence unit supporting a grading decision.
 * Links a claim statement to quoted evidence from student work.
 */
export interface EvidenceClaim {
    /** Unique identifier for this claim */
    claim_id: string;
    /** Type of claim being made */
    claim_type: ClaimType;
    /** Human-readable statement explaining the evidence (Hebrew, max 200 chars) */
    claim_statement: string;
    /** Which scoring level this evidence supports */
    matched_level_id: string;
    /** Direct quotes from student answer */
    answer_quotations: AnswerQuotation[];
    /** v2.0: AI confidence in this claim */
    confidence_level?: ConfidenceLevel;
}

// =============================================================================
// RUBRIC TYPES (Input to Grading)
// =============================================================================

/**
 * A single graded sub-part of a criterion (wire format).
 */
export interface SubCriterionOntology {
    sub_criterion_id: string;
    index: number;
    description: string;
    /** Points as string for decimal precision */
    points: string;
}

/**
 * A criterion within a question.
 */
export interface CriterionOntology {
    criterion_id: string;
    index: number;
    description: string;
    /** Points as string for decimal precision */
    points: string;
    skill_targets?: string[];
    requirements?: string[];
    /**
     * Optional sub-criteria breakdown. When present, INV-3 requires
     * Σ sub_criteria.points == criterion.points.
     */
    sub_criteria?: SubCriterionOntology[] | null;
}

/**
 * A sub-question within a parent question.
 *
 * Mirrors the foundational ontology (§4.3):
 *   SubQuestion { sub_question_id, index, text, points, criteria[] }
 *
 * Hebrew sub-question IDs use Hebrew letters: "א", "ב", "ג"
 * English sub-question IDs use Latin letters: "a", "b", "c"
 */
/**
 * Raw 2D grid table extracted from a DOCX question (class interface definitions,
 * I/O example tables, etc.). Uses a grid rather than header+rows because DOCX
 * merged cells are expanded by python-docx into repeated adjacent values —
 * deduplication is applied during extraction.
 */
export interface ContextTableData {
  /** Optional caption/title shown above the table (e.g. "הפעולה תחזיר את המערך הבא:") */
  title?: string | null;
  /** Raw 2D cell grid: grid[row][col]. Merged-cell duplicates already removed. */
  grid: string[][];
  row_count: number;
  col_count: number;
}

export interface SubQuestion {
    sub_question_id: string;
    index: number;
    /** UX-only display title. null/undefined → frontend renders positional default. */
    title?: string | null;
    text?: string;
    /** Points as string for decimal precision (wire format) */
    points: string;
    criteria: CriterionOntology[];
}

/**
 * A question in the rubric.
 */
export interface QuestionOntology {
    question_id: string;
    question_type?: 'short_answer' | 'coding_task' | 'trace_table' | 'computation' | 'proof' | 'essay' | 'source_analysis';
    question_text?: string;
    /** Total points as string for decimal precision */
    total_points: string;
    criteria: CriterionOntology[];
    sub_questions?: SubQuestion[];
    allow_multiple_valid_forms?: boolean;
    skill_targets?: Array<{ id: string; name: string; priority: string }>;
    requirements?: Array<{ id: string; description: string; promoted: boolean }>;
    // DOCX pipeline fields — populated during extraction, passed through to the UI
    example_solution?: string | null;
    trace_tables?: Array<{ headers: string[]; rows: Record<string, string>[]; row_count: number }>;
    context_tables?: ContextTableData[];
}

// Canonical type aliases (use these for clarity when referring to ontology wire types)
export type Question = QuestionOntology;
export type Criterion = CriterionOntology;

/**
 * Annotation on a rubric element (warning or error).
 */
export interface Annotation {
    id: string;
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
    target_id?: string | null;
}

// =============================================================================
// GRADING OUTCOME TYPES (Output from Grading)
// =============================================================================

/**
 * Result of evaluating a single rule.
 * Contains the selected level, points awarded, and supporting evidence.
 */
export interface RuleOutcome {
    /** Reference to the rule in the rubric */
    rule_id: string;
    /** Which scoring level was selected */
    selected_level_id: string;
    /** Points awarded as string for decimal precision */
    points_awarded: string;
    /** Evidence supporting this decision */
    evidence_claim: EvidenceClaim;
    /** Whether this rule needs teacher review */
    needs_review: boolean;
    /** Why this rule was flagged */
    review_reason?: string;
}

/**
 * Result of evaluating a criterion (group of rules).
 */
export interface CriterionOutcome {
    /** Reference to the criterion in the rubric */
    criterion_id: string;
    /** Total points earned for this criterion */
    points_earned: string;
    /** Total points possible for this criterion */
    points_possible: string;
    /** v2.0: Human-readable summary of reasoning (Hebrew, 2-4 sentences) */
    reasoning_summary?: string;
    /** v2.0: Whether any rules in this criterion need review */
    needs_review: boolean;
    /** Individual rule outcomes */
    rule_outcomes: RuleOutcome[];
}

/**
 * Result of evaluating a question.
 */
export interface QuestionOutcome {
    /** Reference to the question in the rubric */
    question_id: string;
    /** Optional sub-question ID */
    sub_question_id?: string;
    /** Total points earned for this question */
    points_earned: string;
    /** Total points possible for this question */
    points_possible: string;
    /** Individual criterion outcomes */
    criterion_outcomes: CriterionOutcome[];
}

/**
 * A flagged item that needs teacher review.
 * Aggregated at the test level for quick filtering.
 */
export interface FlaggedOutcome {
    /** Rule that was flagged (if rule-level) */
    rule_id?: string;
    /** Criterion that was flagged (if criterion-level) */
    criterion_id?: string;
    /** Question containing the flagged item */
    question_id?: string;
    /** Why this item was flagged */
    reason: FlagReason;
    /** Human-readable message */
    message?: string;
}

/**
 * Complete grading result for a student test.
 * This is the draft state before teacher approval.
 */
export interface GradedTestDraft {
    /** Unique identifier for this draft */
    draft_id: string;
    /** Session that produced this draft */
    session_id: string;
    /** Rubric contract used for grading */
    rubric_contract_id: string;
    /** Version of the contract (for consistency checking) */
    contract_version: string;
    /** Student identifier */
    student_id?: string;
    /** Student name */
    student_name: string;
    /** Source file reference */
    filename?: string;

    // --- Grading Results ---
    /** Outcomes for each question */
    question_outcomes: QuestionOutcome[];
    /** Total points earned */
    total_points_earned: string;
    /** Total points possible */
    total_points_possible: string;

    // --- Metadata ---
    /** Current status in lifecycle */
    status: GradedTestStatus;
    /** When grading completed */
    graded_at: string;
    /** Time taken to grade in milliseconds */
    grading_duration_ms: number;
    /** Model version used */
    model_version: string;
    /** Number of LLM API calls made */
    llm_calls_count: number;

    // --- Quality Signals ---
    /** Warnings generated during grading */
    warnings: string[];
    /** Items flagged for teacher review */
    flagged_outcomes: FlaggedOutcome[];

    // --- Metrics ---
    /** Total rules evaluated */
    total_rules_evaluated?: number;
    /** Rules with valid quote matches */
    rules_with_valid_quotes?: number;
    /** Rules flagged for review */
    rules_flagged_for_review?: number;
    /** Criteria that were skipped */
    skipped_criteria?: string[];
}

// =============================================================================
// STUDENT ANSWER TYPES (Input to Grading)
// =============================================================================

/**
 * A single student answer for grading (ontology format).
 * Different from legacy StudentAnswerInput which uses question_number.
 */
export interface OntologyStudentAnswer {
    /** Question ID this answer belongs to */
    question_id: string;
    /** The student's answer text/code */
    content: string;
    /** Content type: text, code, or image_transcription */
    content_type?: 'text' | 'code' | 'image_transcription';
}

/**
 * A student's complete test data for batch grading.
 */
export interface StudentInput {
    /** Student name */
    student_name: string;
    /** Source file reference */
    filename?: string;
    /** All answers from this student */
    answers: OntologyStudentAnswer[];
}

// =============================================================================
// BATCH GRADING TYPES
// =============================================================================

/**
 * Request to start batch grading.
 */
export interface BatchGradeRequest {
    /** ID of the rubric (must have compiled contract) */
    rubric_id: string;
    /** List of students to grade */
    students: StudentInput[];
    /** Optional batch name for display */
    batch_name?: string;
    /** Optional class identifier */
    class_id?: string;
    /** Whether to save GradedTest records (default: true) */
    save_results?: boolean;
}

/**
 * Response after starting batch grading.
 * Returns immediately with batch_id for progress polling.
 */
export interface BatchGradeResponse {
    /** Unique identifier for this batch */
    batch_id: string;
    /** Contract version being used */
    contract_version: string;
    /** Initial status (always 'processing') */
    status: 'processing';
    /** Total number of students in batch */
    total_students: number;
    /** URL to poll for progress */
    progress_url: string;
}

/**
 * Summary of a grading session within a batch.
 */
export interface SessionSummary {
    /** Session identifier */
    session_id: string;
    /** Student name */
    student_name: string;
    /** Current status */
    status: SessionStatus;
    /** Progress string (e.g., "5/12 criteria") */
    progress: string;
    /** Score if completed (e.g., "85/100") */
    score?: string;
    /** Percentage if completed */
    percentage?: number;
    /** Number of flagged items */
    flagged_count: number;
}

/**
 * Detailed progress response for a batch.
 * Used for real-time progress display.
 */
export interface BatchProgressResponse {
    /** Batch identifier */
    batch_id: string;
    /** Batch name if provided */
    batch_name?: string;
    /** Current batch status */
    status: BatchStatus;
    /** Contract version being used */
    contract_version: string;
    /** Total students in batch */
    total_students: number;
    /** Number of completed sessions */
    completed: number;
    /** Number of failed sessions */
    failed: number;
    /** Number of sessions currently grading */
    in_progress: number;
    /** Number of sessions waiting to start */
    pending: number;
    /** Overall progress percentage (0-100) */
    progress_percentage: number;
    /** Estimated time remaining in seconds */
    estimated_remaining_seconds?: number;
    /** When batch started */
    started_at?: string;
    /** When batch completed */
    completed_at?: string;
    /** Individual session summaries */
    sessions: SessionSummary[];
}

// =============================================================================
// SESSION MANAGEMENT TYPES
// =============================================================================

/**
 * Detailed information about a grading session.
 * Used for session detail view and resume functionality.
 */
export interface SessionDetailResponse {
    /** Session identifier */
    session_id: string;
    /** Rubric being used */
    rubric_id: string;
    /** Parent batch if part of batch */
    batch_id?: string;
    /** Contract version */
    contract_version: string;
    /** Student name */
    student_name: string;
    /** Source file reference */
    filename?: string;
    /** Current status */
    status: SessionStatus;
    /** Progress percentage (0-100) */
    progress_percentage: number;
    /** Total questions in rubric */
    total_questions: number;
    /** Total criteria to evaluate */
    total_criteria: number;
    /** Criteria completed so far */
    completed_criteria: number;
    /** Current question being processed */
    current_question_idx: number;
    /** Current criterion being processed */
    current_criterion_idx: number;
    /** Number of LLM calls made */
    llm_calls_count: number;
    /** Total LLM latency in ms */
    total_llm_latency_ms: number;
    /** Warnings generated */
    warnings: string[];
    /** Number of flagged items */
    flagged_count: number;
    /** Criteria that were skipped */
    skipped_criteria: string[];
    /** When session started */
    started_at?: string;
    /** When session completed */
    completed_at?: string;
    /** Full draft if completed and requested */
    graded_test_draft?: GradedTestDraft;
}

/**
 * Request to resume an interrupted session.
 */
export interface SessionResumeRequest {
    /** Force resume even if session appears active */
    force?: boolean;
}

/**
 * Response after resuming a session.
 */
export interface SessionResumeResponse {
    session_id: string;
    status: 'resuming';
    resumption_mode: 'from_snapshot' | 'from_start';
    progress_from: string;
    message: string;
    progress_url: string;
}

// =============================================================================
// SINGLE GRADING TYPES
// =============================================================================

/**
 * Request to grade a single student with ontology agent.
 */
export interface OntologyGradeRequest {
    /** Rubric ID (must be compiled) */
    rubric_id: string;
    /** Student name */
    student_name: string;
    /** Source file reference */
    filename?: string;
    /** Student's answers */
    answers: OntologyStudentAnswer[];
}

/**
 * Response from single ontology grading.
 */
export interface OntologyGradeResponse {
    /** Session identifier */
    session_id: string;
    /** Result status */
    status: 'completed' | 'failed';
    /** Student name */
    student_name: string;
    /** Total points earned as string */
    total_points_earned: string;
    /** Total points possible as string */
    total_points_possible: string;
    /** Percentage score */
    percentage: number;
    /** Time taken in ms */
    grading_duration_ms: number;
    /** LLM calls made */
    llm_calls_count: number;
    /** Warnings generated */
    warnings: string[];
    /** Flagged items for review */
    flagged_outcomes: FlaggedOutcome[];
    /** Full grading result */
    graded_test_draft: GradedTestDraft;
}

// =============================================================================
// RUBRIC COMPILATION TYPES
// =============================================================================

/**
 * Warning that requires acknowledgment before compilation.
 */
export interface CompilationWarning {
    id: string;
    type: string;
    severity: 'warning';
    message: string;
    target_id?: string;
}

/**
 * Response from rubric compilation attempt.
 */
export interface CompileRubricResponse {
    status: 'compiled' | 'warnings_require_acknowledgment' | 'compilation_error';
    rubric_id?: string;
    contract_version?: string;
    compiled_at?: string;
    is_compiled?: boolean;
    stats?: {
        total_questions: number;
        total_criteria: number;
        total_sub_criteria: number;
    };
    warnings?: CompilationWarning[];
    errors?: Array<{
        id: string;
        type: string;
        severity: 'error';
        message: string;
        target_id?: string;
    }>;
}

// =============================================================================
// UTILITY TYPES
// =============================================================================

/**
 * Generic API error response.
 */
export interface ApiErrorResponse {
    detail: string;
    error_code?: string;
    errors?: Array<{
        field: string;
        message: string;
    }>;
}