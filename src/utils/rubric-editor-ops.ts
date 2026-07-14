/**
 * Rubric Editor Operations
 *
 * Pure, side-effect-free functions for every structural edit a teacher can
 * make in the RubricEditor. Each function returns a NEW array/object —
 * never mutates state in place. Safe to pass directly to React setState.
 *
 * ─── Cascade rule (single source of truth — do not re-implement elsewhere) ───
 *
 *   - Editing criterion.points cascades up ONE LEVEL to the direct parent
 *     (sq.points if sub-questions exist, else q.total_points). The cascade
 *     is performed by recalculateParentsFromCriteria in rubric-transform.ts,
 *     called from updateCriterion in RubricEditor.tsx — nowhere else.
 *
 *   - All other point fields (sq.points, q.total_points, rubric.total_points,
 *     sub_criterion.points) move ONLY by explicit teacher edit. There is no
 *     cascade down. There is no cascade across siblings.
 *
 *   - Structural ops (add / remove / reorder criteria, add / remove
 *     sub-questions or questions) NEVER redistribute or rescale. A removed
 *     criterion leaves a gap; the validator (rubric-validation.ts) surfaces
 *     the gap as an Annotation that blocks save until the teacher resolves
 *     it.
 *
 * Why no top-down cascade: it would silently "fix" violations the teacher
 * never asked us to fix, making it impossible for the validator to do its
 * job and breaking the trust property in CLAUDE.md. The teacher is always
 * the authority over every point field.
 *
 * @see rubric-transform.ts — recalculateParentsFromCriteria (the one cascade)
 * @see rubric-validation.ts — live invariant checks
 */

import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';

// =============================================================================
// POINT MATH HELPERS
// =============================================================================

/**
 * Round `value` to the nearest quarter-point (0.25) increment.
 * This matches NumericPolicy.precision = "0.25" on the backend.
 */
export function roundToQuarter(value: number): number {
    return Math.round(value * 4) / 4;
}

// =============================================================================
// INTERNAL HELPERS
// =============================================================================

/**
 * Generate a short unique ID suffix (timestamp + random).
 * Used for new question_id, criterion_id, sub_question_id, etc.
 */
function uid(): string {
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

/**
 * Build a new empty criterion with a guaranteed unique criterion_id.
 * New criteria are always 0 points — the teacher assigns explicitly.
 */
function makeEmptyCriterion(index: number, points: number): RubricCriterion {
    return {
        criterion_id: `c_${uid()}`,
        index,
        description: '',
        points,
        sub_criteria: null,
    };
}

// =============================================================================
// QUESTION CRUD
// =============================================================================

/**
 * Add a new empty question to the list. The new question gets 0 points by
 * default (teacher must assign points explicitly). The existing questions
 * are NOT rescaled — INV-R3 (rubric total) will flag the resulting mismatch
 * and prompt the teacher.
 *
 * One empty criterion is added as a placeholder.
 */
export function addQuestion(questions: RubricQuestion[]): RubricQuestion[] {
    const newQuestion: RubricQuestion = {
        question_id: `q_${uid()}`,
        question_type: 'short_answer',
        question_text: '',
        total_points: 0,
        criteria: [makeEmptyCriterion(0, 0)],
        sub_questions: [],
        allow_multiple_valid_forms: false,
        example_solution: null,
    };
    return [...questions, newQuestion];
}

/**
 * Remove the question at `qIndex`. Strict per the cascade rule:
 *   - No redistribution. Σ q.total_points now changes; INV-R3 fires
 *     against the unchanged rubric.total_points; teacher resolves.
 *   - No reindexing of question_id (IDs are stable identifiers, not
 *     positions).
 */
export function removeQuestion(
    questions: RubricQuestion[],
    qIndex: number
): RubricQuestion[] {
    return questions.filter((_, i) => i !== qIndex);
}

/**
 * Change the total_points of one question. Pure assignment — no cascade.
 *
 * Consequences this op may surface as Annotations:
 *   - INV-R1: Σ sub_questions.points or Σ direct criteria.points may no
 *     longer equal the new q.total_points.
 *   - INV-R3: Σ q.total_points may no longer equal rubric.total_points.
 */
export function changeQuestionPoints(
    questions: RubricQuestion[],
    qIndex: number,
    newPoints: number
): RubricQuestion[] {
    return questions.map((q, i) =>
        i !== qIndex ? q : { ...q, total_points: roundToQuarter(newPoints) }
    );
}

// =============================================================================
// SUB-QUESTION CRUD
// =============================================================================

/**
 * Add a new empty sub-question to the question at `qIndex`.
 *
 * The new sub-question gets 0 points (teacher assigns explicitly).
 * The question's direct `criteria` are NOT automatically moved —
 * teacher uses existing Add Criterion buttons inside the sub-question.
 */
export function addSubQuestion(
    questions: RubricQuestion[],
    qIndex: number
): RubricQuestion[] {
    return questions.map((q, i) => {
        if (i !== qIndex) return q;

        const newIndex = (q.sub_questions || []).length;
        const newSubQ: RubricSubQuestion = {
            sub_question_id: `sq_${uid()}`,
            index: newIndex,
            text: '',
            points: 0,
            criteria: [makeEmptyCriterion(0, 0)],
        };
        return {
            ...q,
            sub_questions: [...(q.sub_questions || []), newSubQ],
        };
    });
}

/**
 * Remove the sub-question at `sqIndex` from the question at `qIndex`.
 * Strict per the cascade rule: no redistribution among surviving
 * sub-questions, no rescale of q.total_points. The validator surfaces
 * the resulting INV-R1 mismatch and the teacher resolves it.
 *
 * The surviving sub-questions are reindexed so their `.index` field
 * stays contiguous (positional metadata, not point math).
 */
export function removeSubQuestion(
    questions: RubricQuestion[],
    qIndex: number,
    sqIndex: number
): RubricQuestion[] {
    return questions.map((q, i) => {
        if (i !== qIndex) return q;
        const remaining = q.sub_questions
            .filter((_, si) => si !== sqIndex)
            .map((sq, si) => ({ ...sq, index: si }));
        return { ...q, sub_questions: remaining };
    });
}

/**
 * Change the points of a sub-question. Pure assignment — no cascade.
 *
 * Consequences this op may surface as Annotations:
 *   - INV-R1: Σ sq.points may no longer equal q.total_points.
 *   - INV-R1b: Σ sq.criteria.points may no longer equal the new sq.points.
 */
export function changeSubQuestionPoints(
    questions: RubricQuestion[],
    qIndex: number,
    sqIndex: number,
    newPoints: number
): RubricQuestion[] {
    return questions.map((q, i) => {
        if (i !== qIndex) return q;
        const updatedSubQs = q.sub_questions.map((sq, si) =>
            si !== sqIndex ? sq : { ...sq, points: roundToQuarter(newPoints) }
        );
        return { ...q, sub_questions: updatedSubQs };
    });
}

// =============================================================================
// EXAMPLE SOLUTION
// =============================================================================

/**
 * Set (or clear) the example_solution for the question at `qIndex`.
 * Pass `null` to remove it.
 */
export function setExampleSolution(
    questions: RubricQuestion[],
    qIndex: number,
    text: string | null
): RubricQuestion[] {
    return questions.map((q, i) =>
        i !== qIndex ? q : { ...q, example_solution: text }
    );
}

// =============================================================================
// TEXT / METADATA EDITS
// =============================================================================

/** Update the question_text for the question at `qIndex`. */
export function setQuestionText(
    questions: RubricQuestion[],
    qIndex: number,
    text: string
): RubricQuestion[] {
    return questions.map((q, i) =>
        i !== qIndex ? q : { ...q, question_text: text }
    );
}

/** Update the question_type for the question at `qIndex`. */
export function setQuestionType(
    questions: RubricQuestion[],
    qIndex: number,
    type: RubricQuestion['question_type']
): RubricQuestion[] {
    return questions.map((q, i) =>
        i !== qIndex ? q : { ...q, question_type: type }
    );
}

/** Update the text of one sub-question. */
export function setSubQuestionText(
    questions: RubricQuestion[],
    qIndex: number,
    sqIndex: number,
    text: string
): RubricQuestion[] {
    return questions.map((q, i) => {
        if (i !== qIndex) return q;
        const updatedSubQs = q.sub_questions.map((sq, si) =>
            si !== sqIndex ? sq : { ...sq, text }
        );
        return { ...q, sub_questions: updatedSubQs };
    });
}