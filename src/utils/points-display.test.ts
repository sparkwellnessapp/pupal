import { describe, it, expect } from 'vitest';

import { formatPoints, formatPointsPair, subtractPoints } from './points-display';

/**
 * The display half of the pricing seam. The EXACT value travels; only what
 * reaches the screen is trimmed.
 *
 * This exists because the first F2 screenshots showed `7.50 / 8` and
 * `1.00 / 1` down the whole checklist — the pricer's byte-exact Decimal
 * strings, correct on the wire and wrong on a test paper. The mockup's own
 * numbers are `9 / 10` and `3 / 3`.
 */
describe('formatPoints', () => {
    it('drops trailing zeros a teacher would never write', () => {
        expect(formatPoints('4.00')).toBe('4');
        expect(formatPoints('7.50')).toBe('7.5');
        expect(formatPoints('10.0')).toBe('10');
        expect(formatPoints('0')).toBe('0');
        expect(formatPoints('0.00')).toBe('0');
    });

    it('keeps a quarter point — it is a real mark she awards', () => {
        expect(formatPoints('0.75')).toBe('0.75');
        expect(formatPoints('2.25')).toBe('2.25');
        expect(formatPoints('0.50')).toBe('0.5');
    });

    it('NEVER rounds — trimming only', () => {
        // If this ever rounded, a 0.25 grid would silently lose quarter points
        // on screen while the contract froze the real number.
        expect(formatPoints('3.75')).toBe('3.75');
        expect(formatPoints('99.25')).toBe('99.25');
    });

    it('handles negatives without producing a bare minus', () => {
        expect(formatPoints('-3')).toBe('-3');
        expect(formatPoints('-0.50')).toBe('-0.5');
        expect(formatPoints('-0.00')).toBe('0');
    });

    it('passes through anything it does not understand, unmangled', () => {
        // Honest: showing a raw value beats silently reformatting a shape this
        // function has never seen (a scientific form, say).
        expect(formatPoints('2E+1')).toBe('2E+1');
        expect(formatPoints('')).toBe('');
        expect(formatPoints(null)).toBe('');
        expect(formatPoints(undefined)).toBe('');
    });

    it('formats the pair the checklist actually shows', () => {
        expect(formatPointsPair('7.50', '8')).toBe('7.5 / 8');
        expect(formatPointsPair('4.00', '4.00')).toBe('4 / 4');
    });

    it('does not round-trip through a float', () => {
        // 0.1 + 0.2 arithmetic must never get near a grade.
        expect(formatPoints('0.10')).toBe('0.1');
        expect(formatPoints('1.10')).toBe('1.1');
        expect(formatPoints('123456789.50')).toBe('123456789.5');
    });
});

// ---------------------------------------------------------------------------
// §5.5 — the deduction. «Where did he lose points» is her first read, and the
// amber dots do not answer it (a full-marks question can carry one).
// ---------------------------------------------------------------------------

describe('subtractPoints', () => {
    it('reports what was lost, trimmed', () => {
        expect(subtractPoints('10', '7.5')).toBe('2.5')
        expect(subtractPoints('12.00', '8.00')).toBe('4')
        expect(subtractPoints('3', '2.75')).toBe('0.25')
    })

    it('renders NOTHING when nothing was lost — the row stays quiet', () => {
        expect(subtractPoints('8', '8')).toBeNull()
        expect(subtractPoints('8.00', '8')).toBeNull()
    })

    it('never reports a NEGATIVE deduction from an over-awarded row', () => {
        // The pricer clamps, but a clamped row can still reach a render, and
        // «−-2» beside a grade is worse than no figure at all.
        expect(subtractPoints('5', '7')).toBeNull()
    })

    it('is exact — no float round-trip', () => {
        // 0.3 - 0.1 through Number is 0.19999999999999998.
        expect(subtractPoints('0.3', '0.1')).toBe('0.2')
    })

    it('renders no deduction for an input it cannot parse, rather than a guess', () => {
        expect(subtractPoints('לא ידוע', '3')).toBeNull()
        expect(subtractPoints(null, '3')).toBeNull()
        expect(subtractPoints('3', undefined)).toBeNull()
    })
})
