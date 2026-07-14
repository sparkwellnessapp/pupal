/**
 * Hydration / Dehydration for rubric types.
 *
 * Hydration  (backend → frontend): string point values → number
 * Dehydration (frontend → backend): number point values → string
 *
 * These functions are the ONLY place numeric coercion happens.
 * Frontend state always stores numbers; the wire format always uses strings.
 *
 * Design rules:
 *  - NO type casts (`as`). Every field is assigned explicitly.
 *  - NO format sniffing (no `criterion_description || description` fallbacks).
 *  - safeParseFloat is the ONLY coercion utility.
 *
 * @see types/rubric.ts — display-ready types (numbers)
 * @see ontology-types.ts — wire types (strings)
 */

import type {
    RubricQuestion,
    RubricSubQuestion,
    RubricCriterion,
    RubricSubCriterion,
    ProposalSet,
    ProposedCriterion,
    EnhancedPointEntry,
} from '@/types/rubric';
import type {
    QuestionOntology,
    CriterionOntology,
    SubQuestion,
} from '@/lib/ontology-types';

// ─────────────────────────────────────────────────────────
// THE ONLY COERCION UTILITY
// ─────────────────────────────────────────────────────────

/**
 * Safely parse any backend value to a number.
 * Handles string (Decimal serialization), number, undefined, null.
 * Returns 0 for garbage input. This is the ONLY numeric coercion
 * function in the codebase. Do not inline parseFloat() elsewhere.
 */
export function safeParseFloat(value: string | number | undefined | null): number {
    if (value === undefined || value === null) return 0;
    const num = typeof value === 'number' ? value : parseFloat(value);
    return isNaN(num) ? 0 : num;
}

// ─────────────────────────────────────────────────────────
// HYDRATION: Backend → Frontend (string → number)
// Called ONCE when data arrives from backend.
// ─────────────────────────────────────────────────────────

export function hydrateQuestions(questions: QuestionOntology[]): RubricQuestion[] {
    return (questions || []).map(hydrateQuestion);
}

function hydrateQuestion(q: QuestionOntology): RubricQuestion {
    // `raw` provides access to fields present on the wire JSON but not declared
    // in the QuestionOntology interface (code_blocks, extraction_status, etc.).
    // Double-cast through `unknown` is the standard TypeScript escape hatch.
    const raw = q as unknown as Record<string, unknown>;

    return {
        question_id: q.question_id,
        question_type: q.question_type,
        question_text: q.question_text,
        total_points: safeParseFloat(q.total_points),
        allow_multiple_valid_forms: q.allow_multiple_valid_forms,
        skill_targets: q.skill_targets,
        requirements: q.requirements,
        criteria: (q.criteria || []).map(hydrateCriterion),
        sub_questions: ((q.sub_questions) || []).map(hydrateSubQuestion),
        // Declared on QuestionOntology — access directly
        example_solution: q.example_solution,
        trace_tables: q.trace_tables,
        context_tables: q.context_tables,
        // Not declared on QuestionOntology — access via raw
        code_blocks: raw.code_blocks as string[] | undefined,
        extraction_status: raw.extraction_status as RubricQuestion['extraction_status'],
        extraction_error: raw.extraction_error as string | null | undefined,
        // Proposals — ephemeral, hydrated from backend but not dehydrated on save
        proposals: hydrateProposalSet(raw.proposals),
    };
}

function hydrateSubQuestion(sq: SubQuestion): RubricSubQuestion {
    // Access extra DOCX fields that may exist on the raw JSON
    const raw = sq as unknown as Record<string, unknown>;

    return {
        sub_question_id: sq.sub_question_id,
        index: sq.index,
        title: (raw.title as string | null | undefined) ?? null,
        text: sq.text,
        points: safeParseFloat(sq.points),
        criteria: (sq.criteria || []).map(hydrateCriterion),
        // DOCX extraction metadata (pass through)
        trace_tables: raw.trace_tables as RubricSubQuestion['trace_tables'],
        extraction_status: raw.extraction_status as RubricSubQuestion['extraction_status'],
        extraction_error: raw.extraction_error as string | null | undefined,
        // Proposals — ephemeral, hydrated from backend but not dehydrated on save
        proposals: hydrateProposalSet(raw.proposals),
    };
}

function hydrateCriterion(c: CriterionOntology): RubricCriterion {
    const raw = c as unknown as Record<string, unknown>;

    const rawSubCriteria = raw.sub_criteria as Array<{
        sub_criterion_id?: string; index?: number; description: string; points: string | number;
    }> | null | undefined;
    const sub_criteria = rawSubCriteria?.length
        ? rawSubCriteria.map((sc, i): RubricSubCriterion => ({
            sub_criterion_id: (sc.sub_criterion_id) || `sc${i}`,
            index: sc.index ?? i,
            description: sc.description,
            points: safeParseFloat(sc.points),
        }))
        : null;

    return {
        criterion_id: c.criterion_id,
        index: c.index,
        description: c.description,
        points: safeParseFloat(c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        extraction_confidence: raw.extraction_confidence as RubricCriterion['extraction_confidence'],
        notes: raw.notes as string | null | undefined,
        sub_criteria,
    };
}


/**
 * Hydrate proposal data from backend wire format.
 *
 * Proposals are EPHEMERAL — they exist between extraction and teacher decision.
 * They are NOT dehydrated on save (silently dropped).
 *
 * Returns null if no proposals or proposals are empty.
 */
function hydrateProposalSet(raw: unknown): ProposalSet | null {
    if (!raw || typeof raw !== 'object') return null;

    const data = raw as Record<string, unknown>;

    const rawProposed = Array.isArray(data.proposed_criteria) ? data.proposed_criteria : [];
    if (rawProposed.length === 0) return null;

    const proposed_criteria: ProposedCriterion[] = rawProposed.map(
        (pc: Record<string, unknown>, idx: number) => ({
            temp_id: (typeof pc.temp_id === 'string' ? pc.temp_id : null) || `proposed_${Date.now()}_${idx}`,
            description: String(pc.description || ''),
            points: safeParseFloat(pc.points as string | number | undefined),
            explanation: String(pc.explanation || ''),
        })
    );

    const rawDist = Array.isArray(data.enhanced_distribution) ? data.enhanced_distribution : [];
    const enhanced_distribution: EnhancedPointEntry[] = rawDist.map(
        (entry: Record<string, unknown>) => ({
            // Backend now always emits criterion_id (the real frontend key).
            // Do NOT fall back to original_row_idx — that is a backend-internal
            // row sequence number and never matches any criterion_id in the frontend.
            criterion_id: String(entry.criterion_id || ''),
            points: safeParseFloat(entry.points as string | number | undefined),
        })
    );

    return { proposed_criteria, enhanced_distribution, question_purpose: String(data.question_purpose || '') };
}

// ─────────────────────────────────────────────────────────
// DEHYDRATION: Frontend → Backend (number → string)
// Called ONCE when saving to backend.
// Field-by-field construction — NO type casts.
//
// NOTE: `proposals` is intentionally NOT dehydrated. Proposals are
// ephemeral UI state — they exist between extraction and teacher
// accept/reject, then disappear. They are never persisted.
// ─────────────────────────────────────────────────────────

export function dehydrateQuestions(questions: RubricQuestion[]): QuestionOntology[] {
    return questions.map(dehydrateQuestion);
}

function dehydrateQuestion(q: RubricQuestion): QuestionOntology {
    const result: QuestionOntology = {
        question_id: q.question_id,
        question_type: q.question_type,
        question_text: q.question_text,
        total_points: String(q.total_points),
        allow_multiple_valid_forms: q.allow_multiple_valid_forms,
        skill_targets: q.skill_targets,
        requirements: q.requirements,
        criteria: q.criteria.map(dehydrateCriterion),
        sub_questions: (q.sub_questions || []).map(dehydrateSubQuestion),
    };
    return result;
}

function dehydrateSubQuestion(sq: RubricSubQuestion): SubQuestion {
    return {
        sub_question_id: sq.sub_question_id,
        index: sq.index,
        title: sq.title ?? null,
        text: sq.text,
        points: String(sq.points),
        criteria: sq.criteria.map(dehydrateCriterion),
    };
}

function dehydrateCriterion(c: RubricCriterion): CriterionOntology {
    return {
        criterion_id: c.criterion_id,
        index: c.index,
        description: c.description,
        points: String(c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        sub_criteria: c.sub_criteria?.map(sc => ({
            sub_criterion_id: sc.sub_criterion_id,
            index: sc.index,
            description: sc.description,
            points: String(sc.points),
        })) ?? null,
    };
}

// ─────────────────────────────────────────────────────────
// PARENT-FROM-CRITERIA CASCADE
// The ONLY silent correction in the editor. Read the JSDoc.
// ─────────────────────────────────────────────────────────

/**
 * One-level bottom-up cascade: recompute each criterion's direct structural
 * parent so it equals Σ of its criteria.
 *
 *   - Question has sub_questions: each sq.points = Σ sq.criteria.points.
 *     q.total_points is NEVER touched here — INV-R1 surfaces any mismatch.
 *   - Question has direct criteria only: q.total_points = Σ q.criteria.points.
 *
 * This is the ONLY silent correction in the editor. Every other consistency
 * check surfaces through rubric-validation.ts as an Annotation that blocks
 * save until the teacher resolves it manually.
 *
 * Call this ONLY after an operation that may change criterion.points
 * (i.e. updateCriterion). Idempotent — safe to call when nothing changed.
 *
 * Do NOT call after:
 *   - structural ops on criteria (add / remove / reorder)
 *       → would mask the gap a removal is supposed to leave behind
 *         (Q1-strict: removed criterion's points are NOT redistributed)
 *   - edits to sq.points, q.total_points, sub_criterion.points
 *       → would re-introduce top-down silent correction
 *
 * Returns a new array (immutable).
 */
export function recalculateParentsFromCriteria(
    questions: RubricQuestion[]
): RubricQuestion[] {
    return questions.map((q) => {
        if (q.sub_questions && q.sub_questions.length > 0) {
            // Cascade into each sub-question; q.total_points stays put.
            const updatedSubQs = q.sub_questions.map((sq) => ({
                ...sq,
                points: sq.criteria.reduce((sum, c) => sum + c.points, 0),
            }));
            return { ...q, sub_questions: updatedSubQs };
        }
        // Direct-criteria question: cascade straight into q.total_points.
        const directSum = q.criteria.reduce((sum, c) => sum + c.points, 0);
        return { ...q, total_points: directSum };
    });
}

// ─────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────

/** Parse question number from question_id: "q1" → 1, "q12" → 12 */
export function parseQuestionNumber(questionId: string): number {
    const match = questionId.match(/q(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
}

/**
 * Detect whether raw JSON is ontology format or legacy format.
 *
 * Ontology format has `question_id` (string like "q1").
 * Legacy format has `question_number` (number like 1).
 *
 * Returns 'ontology' | 'legacy' | 'unknown'.
 */
export function detectRubricFormat(
    questions: unknown[]
): 'ontology' | 'legacy' | 'unknown' {
    if (!Array.isArray(questions) || questions.length === 0) return 'unknown';
    const first = questions[0] as Record<string, unknown>;
    if (typeof first.question_id === 'string') return 'ontology';
    if (typeof first.question_number === 'number') return 'legacy';
    return 'unknown';
}

// ─────────────────────────────────────────────────────────
// LEGACY HYDRATION ADAPTER
// Converts ExtractedQuestion[] (legacy PDF pipeline) to RubricQuestion[].
// Used to keep the PDF extraction path working during migration.
// ─────────────────────────────────────────────────────────

/**
 * Hydrate from legacy format (ExtractedQuestion[]) to display-ready RubricQuestion[].
 * Handles field renaming: criterion_description → description, total_points → points, etc.
 */
export function hydrateLegacyQuestions(questions: unknown[]): RubricQuestion[] {
    return (questions || []).map((q: any, qi: number) => {
        const criteria = (q.criteria || []).map((c: any, ci: number) =>
            hydrateLegacyCriterion(c, ci)
        );
        const subQuestions = (q.sub_questions || []).map((sq: any, si: number) =>
            hydrateLegacySubQuestion(sq, si)
        );
        return {
            question_id: q.question_id || `q${q.question_number}`,
            question_type: q.question_type,
            question_text: q.question_text ?? undefined,
            total_points: safeParseFloat(q.total_points),
            criteria,
            sub_questions: subQuestions,
            allow_multiple_valid_forms: q.allow_multiple_valid_forms,
            // DOCX-specific (pass through)
            example_solution: q.example_solution,
            code_blocks: q.code_blocks,
            trace_tables: q.trace_tables,
            context_tables: q.context_tables,
            extraction_status: q.extraction_status,
            extraction_error: q.extraction_error,
        } satisfies RubricQuestion;
    });
}

function hydrateLegacyCriterion(c: any, index: number): RubricCriterion {
    const rawSubCriteria = c.sub_criteria as Array<{
        sub_criterion_id?: string; index?: number; description: string; points: string | number;
    }> | null | undefined;
    const sub_criteria = rawSubCriteria?.length
        ? rawSubCriteria.map((sc, i): RubricSubCriterion => ({
            sub_criterion_id: sc.sub_criterion_id || `sc${i}`,
            index: sc.index ?? i,
            description: sc.description,
            points: safeParseFloat(sc.points),
        }))
        : null;

    return {
        criterion_id: c.criterion_id || `c${index}`,
        index: c.index ?? index,
        description: c.criterion_description || c.description || '',
        points: safeParseFloat(c.total_points ?? c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        extraction_confidence: c.extraction_confidence,
        notes: c.notes,
        sub_criteria,
    };
}

function hydrateLegacySubQuestion(sq: any, index: number): RubricSubQuestion {
    return {
        sub_question_id: sq.sub_question_id || `sq${index}`,
        index: sq.index ?? index,
        title: (sq.title as string | null | undefined) ?? null,
        text: sq.sub_question_text ?? sq.text ?? undefined,
        points: safeParseFloat(sq.total_points ?? sq.points),
        criteria: (sq.criteria || []).map((c: any, ci: number) =>
            hydrateLegacyCriterion(c, ci)
        ),
        trace_tables: sq.trace_tables,
        extraction_status: sq.extraction_status,
        extraction_error: sq.extraction_error,
    };
}

/**
 * Universal hydration: auto-detects format and converts to RubricQuestion[].
 * Use this when you don't know whether data is ontology or legacy format.
 */
export function hydrateAnyQuestions(questions: unknown[]): RubricQuestion[] {
    const format = detectRubricFormat(questions);
    if (format === 'ontology') {
        return hydrateQuestions(questions as QuestionOntology[]);
    }
    // Legacy or unknown — use legacy adapter which handles both gracefully
    return hydrateLegacyQuestions(questions);
}