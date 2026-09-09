import { describe, it, expect } from 'vitest';

import { formatPoints, formatPointsPair } from './points-display';

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
