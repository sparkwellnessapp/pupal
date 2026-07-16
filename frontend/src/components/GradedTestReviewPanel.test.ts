import { describe, expect, it } from 'vitest';

import { hasSelectionExclusions } from './GradedTestReviewPanel';

/**
 * PR-3 / B-5 — the review panel is the FOURTH consumer of the score.
 *
 * The invariant this pins: NEVER display an aggregate that could disagree with what
 * approval would freeze. When the number is not computable client-side, show NO live
 * aggregate rather than a wrong one.
 *
 * Why it matters: `runningTotal` sums EVERY scope. On a "choose k of N" exam the server
 * counts only the student's best-k and divides by the ACHIEVABLE total, so a client-side
 * sum is the wrong numerator over the right denominator. Rendering it would recreate, on
 * the teacher's screen, the exact "reviewed number ≠ recorded number" disagreement that
 * PR-3 eliminated between the grading runner and the approval gate.
 */
describe('hasSelectionExclusions — the guard on the panel aggregate', () => {
    it('is FALSE for an ordinary rubric, so the live total keeps working', () => {
        expect(hasSelectionExclusions([
            { graded_by: 'llm' },
            { graded_by: 'llm' },
            { graded_by: 'skipped_no_answer' },
        ])).toBe(false);
    });

    it('is FALSE when scopes merely failed or went unanswered — those still COUNT (as zeros)', () => {
        // A mandatory unanswered question is genuinely 0/N. Only selection exclusion
        // removes a scope from BOTH totals, and only that case breaks client math.
        expect(hasSelectionExclusions([
            { graded_by: 'failed' },
            { graded_by: 'skipped_no_answer' },
        ])).toBe(false);
    });

    it('is TRUE as soon as any scope was excluded by selection', () => {
        expect(hasSelectionExclusions([
            { graded_by: 'llm' },
            { graded_by: 'excluded_by_selection' },
            { graded_by: 'skipped_no_answer' },
        ])).toBe(true);
    });

    it('is TRUE on the employee shape: choose 1 of 3, two members excluded', () => {
        expect(hasSelectionExclusions([
            { graded_by: 'llm' },                    // the counted 50-pointer
            { graded_by: 'excluded_by_selection' },  // never owed — NOT a zero
            { graded_by: 'excluded_by_selection' },
        ])).toBe(true);
    });

    it('is FALSE for an empty scope list (nothing to disagree about)', () => {
        expect(hasSelectionExclusions([])).toBe(false);
    });
});
