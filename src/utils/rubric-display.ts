/**
 * Rubric Display Utilities
 *
 * Human-facing labels derived from positional indices into the questions
 * array. Kept separate from rubric-transform.ts (data shape) and
 * rubric-validation.ts (invariant checks) — display formatting is its own
 * concern with different reasons to change.
 *
 * Why positional indices (not parsed IDs):
 *   - IDs are stable opaque identifiers (e.g. "q_mxyz12ab"). Their format
 *     varies across extraction backends and frontend creation paths.
 *   - The teacher's mental model is positional: "the third question in the
 *     rubric is question 3." When they reorder, the labels reorder with them.
 *   - parseQuestionNumber returns 0 for non-"q1"-format IDs — a latent bug
 *     that would have hit every newly-added question.
 *
 * Locale strategy: Hebrew strings live inline in the function where used.
 * Product is Hebrew-only today. The day we add an English locale, THIS file
 * is the single place that changes — we'll swap a per-locale map for the
 * inline strings. Premature i18n abstraction would be Easy-not-Simple.
 *
 * All functions are pure, side-effect-free, and never mutate inputs.
 */

import type { RubricQuestion } from '@/types/rubric';

// =============================================================================
// Scope discriminator
// =============================================================================

/** A point in the rubric tree that can be referred to in a display label. */
export type DisplayScope =
    | { kind: 'rubric' }
    | { kind: 'question'; qIndex: number }
    | { kind: 'sub_question'; qIndex: number; sqIndex: number }
    | { kind: 'criterion'; qIndex: number; sqIndex?: number; cIndex: number }
    | { kind: 'sub_criterion'; qIndex: number; sqIndex?: number; cIndex: number; scIndex: number };

// =============================================================================
// Label rendering
// =============================================================================

/**
 * Render a Hebrew display label for any scope. Examples:
 *   { kind: 'rubric' }                                   → "המחוון"
 *   { kind: 'question', qIndex: 0 }                      → "שאלה 1"
 *   { kind: 'sub_question', qIndex: 0, sqIndex: 1 }      → "שאלה 1, סעיף 2"
 *   { kind: 'criterion', qIndex: 0, cIndex: 2 }          → "שאלה 1, קריטריון 3"
 *   { kind: 'criterion', qIndex: 0, sqIndex: 1, cIndex: 0 }
 *                                                        → "שאלה 1, סעיף 2, קריטריון 1"
 *
 * If a custom sub-question title is set on the model (RubricSubQuestion.title),
 * this function uses it in place of the positional "סעיף N" default.
 *
 * Whitespace-only titles are treated as empty (fall back to positional default).
 */
export function getDisplayLabel(
    scope: DisplayScope,
    questions: RubricQuestion[]
): string {
    switch (scope.kind) {
        case 'rubric':
            return 'המחוון';

        case 'question':
            return `שאלה ${scope.qIndex + 1}`;

        case 'sub_question': {
            const sqLabel = getSubQuestionLabel(questions, scope.qIndex, scope.sqIndex);
            return `שאלה ${scope.qIndex + 1}, ${sqLabel}`;
        }

        case 'criterion': {
            const qPart = `שאלה ${scope.qIndex + 1}`;
            if (scope.sqIndex !== undefined) {
                const sqLabel = getSubQuestionLabel(questions, scope.qIndex, scope.sqIndex);
                return `${qPart}, ${sqLabel}, קריטריון ${scope.cIndex + 1}`;
            }
            return `${qPart}, קריטריון ${scope.cIndex + 1}`;
        }

        case 'sub_criterion': {
            const parent = getDisplayLabel(
                {
                    kind: 'criterion',
                    qIndex: scope.qIndex,
                    sqIndex: scope.sqIndex,
                    cIndex: scope.cIndex,
                },
                questions
            );
            return `${parent}, תת-קריטריון ${scope.scIndex + 1}`;
        }
    }
}

/**
 * Resolve a sub-question's display label — custom `title` if set and
 * non-whitespace, otherwise the positional default "סעיף N".
 *
 * Internal helper. Callers should use getDisplayLabel for composed paths.
 */
function getSubQuestionLabel(
    questions: RubricQuestion[],
    qIndex: number,
    sqIndex: number
): string {
    const sq = questions[qIndex]?.sub_questions?.[sqIndex];
    const customTitle = sq?.title?.trim();
    return customTitle || defaultSubQuestionTitle(sqIndex);
}

// =============================================================================
// Defaults
// =============================================================================

/**
 * The default positional sub-question label at a given position.
 *
 * Per D3-c: this default is NEVER stored on the data model — it is computed
 * at render time. A sub-question with `title === null/undefined` displays
 * this. A sub-question whose teacher-set `title` is later cleared back to
 * empty also displays this.
 */
export function defaultSubQuestionTitle(positionIndex: number): string {
    return `סעיף ${positionIndex + 1}`;
}

// =============================================================================
// Number formatting
// =============================================================================

/**
 * Format a point value for display in user-facing strings.
 *
 * Strips trailing zeros and caps precision at 2 decimal places. Defends
 * against floating-point drift in cascade arithmetic — e.g. a series of
 * 0.25 additions can produce 5.249999999999999, which we want to render
 * as "5.25" or just "5".
 *
 *   formatPoints(5)        → "5"
 *   formatPoints(5.0)      → "5"
 *   formatPoints(5.25)     → "5.25"
 *   formatPoints(5.249999) → "5.25"
 *   formatPoints(0)        → "0"
 */
export function formatPoints(n: number): string {
    return Number(n.toFixed(2)).toString();
}