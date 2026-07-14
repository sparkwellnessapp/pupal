/**
 * Display-ready rubric types for the editor.
 *
 * These mirror the backend ontology types (ontology_types.py) but use `number`
 * for all point fields, making them safe for JavaScript arithmetic.
 *
 * INVARIANT: All point fields are `number` in frontend state.
 *   Hydration  (load from backend): safeParseFloat(string) → number
 *   Dehydration (save to backend):  String(number) → string
 *
 * NO _display_* fields. NO string points. NO dual representations.
 *
 * @see ontology_types.py — backend source of truth
 * @see rubric-transform.ts — hydration / dehydration functions
 */

// =============================================================================
// RUBRIC EDITOR TYPES (numbers for all point fields)
// =============================================================================

/**
 * A context/layout table extracted from a DOCX question (class interface
 * definitions, I/O example tables, etc.). Uses a raw 2D grid to correctly
 * handle merged cells, which python-docx expands into repeated adjacent values.
 */
export interface ContextTableData {
    /** Optional caption/title shown above the table (e.g. "הפעולה תחזיר את המערך הבא:") */
    title?: string | null;
    /** Raw 2D cell grid: grid[row][col]. Merged-cell duplicates already removed. */
    grid: string[][];
    row_count: number;
    col_count: number;
}

export interface RubricSubCriterion {
    sub_criterion_id: string;
    index: number;
    description: string;
    /** Points for this sub-criterion (number — parsed from backend Decimal string) */
    points: number;
}

export interface RubricCriterion {
    criterion_id: string;
    index: number;
    description: string;
    /** Points for this criterion (number — parsed from backend Decimal string) */
    points: number;
    skill_targets?: string[];
    requirements?: string[];
    extraction_confidence?: 'high' | 'medium' | 'low';
    notes?: string | null;
    /**
     * Optional graded sub-parts. When present, INV-3 requires Σ sub_criteria.points == criterion.points.
     * Null when the criterion is graded as an atomic unit.
     */
    sub_criteria?: RubricSubCriterion[] | null;
}

export interface RubricSubQuestion {
    sub_question_id: string;
    index: number;
    /**
     * Editable display title (e.g. "אלגוריתמים" or "חלק תיאורטי").
     * UX metadata only — does NOT participate in any rubric invariant and is
     * stripped from GradingRubricContract by the backend ContractCompiler.
     *
     * When null/undefined/whitespace, the frontend renders the positional
     * default "סעיף ${index + 1}" via getDisplayLabel in rubric-display.ts.
     * Only teacher-customized titles are stored here — the default is never
     * written so reordering shifts the displayed default automatically.
     */
    title?: string | null;
    text?: string;
    /** Points for this sub-question (number — parsed from backend Decimal string) */
    points: number;
    criteria: RubricCriterion[];
    // DOCX extraction metadata (passed through)
    trace_tables?: Array<{ headers: string[]; rows: Record<string, string>[]; row_count: number }>;
    extraction_status?: 'success' | 'partial' | 'failed';
    extraction_error?: string | null;
    /** AI-proposed criteria awaiting teacher accept/reject (ephemeral — not saved) */
    proposals?: ProposalSet | null;
}

export interface RubricQuestion {
    question_id: string;
    question_type?: 'short_answer' | 'coding_task' | 'trace_table' | 'computation' | 'proof' | 'essay' | 'source_analysis';
    question_text?: string;
    /** Total points for this question (number — parsed from backend Decimal string) */
    total_points: number;
    criteria: RubricCriterion[];
    sub_questions: RubricSubQuestion[];
    allow_multiple_valid_forms?: boolean;
    skill_targets?: Array<{ id: string; name: string; priority: string }>;
    requirements?: Array<{ id: string; description: string; promoted: boolean }>;
    // DOCX-specific display fields (preserved from extraction, passed through)
    example_solution?: string | null;
    code_blocks?: string[];
    trace_tables?: Array<{ headers: string[]; rows: Record<string, string>[]; row_count: number }>;
    /** Context tables (e.g. class interfaces, I/O data) — grid format for merged-cell support */
    context_tables?: ContextTableData[];
    // Extraction metadata (passed through)
    extraction_status?: 'success' | 'partial' | 'failed';
    extraction_error?: string | null;
    /** AI-proposed criteria awaiting teacher accept/reject (ephemeral — not saved) */
    proposals?: ProposalSet | null;
}

// =============================================================================
// PROPOSAL TYPES (ephemeral — not persisted to backend on save)
// =============================================================================

/**
 * A single AI-proposed criterion with an explanation for the teacher.
 * These are NOT real criteria until the teacher accepts the batch.
 */
export interface ProposedCriterion {
    /** Temporary client-side ID (not persisted) */
    temp_id: string;
    /** Criterion description (observable grading requirement) */
    description: string;
    /** Proposed point value in the enhanced distribution */
    points: number;
    /** 1-2 line justification for the teacher: why this criterion is needed */
    explanation: string;
}

/**
 * Redistributed points for a single existing teacher criterion.
 * Applied only when the teacher accepts proposed criteria.
 */
export interface EnhancedPointEntry {
    /** criterion_id of the existing criterion */
    criterion_id: string;
    /** New point value after redistribution to fund proposed criteria */
    points: number;
}

/**
 * AI proposal set for a single scope (question or sub-question).
 *
 * Ephemeral: dropped on save. Only exists between extraction and teacher decision.
 * If proposed_criteria is empty, no gaps were found.
 */
export interface ProposalSet {
    proposed_criteria: ProposedCriterion[];
    /**
     * Redistributed points for each existing criterion IF proposals are accepted.
     * Empty when proposed_criteria is empty.
     * Keyed by criterion_id (maps to existing criteria in the scope).
     */
    enhanced_distribution: EnhancedPointEntry[];
    /**
     * Question purpose inferred by Step 1B. Threaded to post-acceptance Call 2
     * for higher-quality rule generation. Empty string if unavailable.
     */
    question_purpose: string;
}