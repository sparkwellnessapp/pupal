import { describe, it, expect } from 'vitest';
import {
    dec, add, sub, mul, divideExact, divideContext, toIntegralValueHalfUp,
    cmp, pyMin, pyMax, toString as decToString,
} from './decimal';

/**
 * The mirror of Python `decimal` that `pricing.ts` needs — and ONLY that.
 *
 * Why exact decimals at all, when `rubric-achievable.ts` documents that plain
 * `number` is safe for teacher point values: that function compares a sum
 * against a tolerance. This one produces the STRING the teacher reads and the
 * server freezes, and the §1.7 vectors are byte-exact `str(Decimal)` output —
 * `"5.0"`, `"4.00"` and `"0"` are all the same arithmetic with different ideal
 * exponents. A mirror that renders `4` where the wire says `4.00` is the
 * selection-scoring incident in miniature (CLAUDE.md §5).
 *
 * Every expectation below was PROBED against CPython, not reasoned about.
 */
describe('decimal — Python parity on the operations the pricer uses', () => {
    it('parses and re-renders plain and scientific forms', () => {
        expect(decToString(dec('0'))).toBe('0');
        expect(decToString(dec('0.75'))).toBe('0.75');
        expect(decToString(dec('4.00'))).toBe('4.00');
        expect(decToString(dec('-0.5'))).toBe('-0.5');
        expect(decToString(dec('2E+1'))).toBe('2E+1');
    });

    it('add/sub take the MIN exponent, like Decimal', () => {
        expect(decToString(add(dec('1'), dec('2')))).toBe('3');
        expect(decToString(add(dec('1'), dec('0.50')))).toBe('1.50');
        expect(decToString(sub(dec('0'), dec('0')))).toBe('0');
        expect(decToString(sub(dec('0'), dec('0.5')))).toBe('-0.5');
    });

    it('mul ADDS exponents (this is what makes n × precision render 4.00)', () => {
        expect(decToString(mul(dec('16'), dec('0.25')))).toBe('4.00');
        expect(decToString(mul(dec('2E+1'), dec('0.25')))).toBe('5.0');
        expect(decToString(mul(dec('1.5'), dec('0.5')))).toBe('0.75');
    });

    it('exact division reduces toward the IDEAL exponent (ea - eb)', () => {
        // CPython: Decimal('0')/Decimal('0.25') -> Decimal('0E+2')
        expect(decToString(divideExact(dec('0'), dec('0.25')))).toBe('0E+2');
        // Decimal('5')/Decimal('0.25') -> Decimal('2E+1')   <- the "5.0" story
        expect(decToString(divideExact(dec('5'), dec('0.25')))).toBe('2E+1');
        expect(decToString(divideExact(dec('10'), dec('0.25')))).toBe('4E+1');
        expect(decToString(divideExact(dec('4'), dec('0.25')))).toBe('16');
        expect(decToString(divideExact(dec('0.75'), dec('0.25')))).toBe('3');
    });

    it('refuses a non-terminating quotient LOUDLY rather than rounding silently', () => {
        expect(() => divideExact(dec('1'), dec('3'))).toThrow(/non-terminating/i);
    });

    it('to_integral_value(ROUND_HALF_UP) leaves a non-negative exponent alone', () => {
        expect(decToString(toIntegralValueHalfUp(dec('2E+1')))).toBe('2E+1');
        expect(decToString(toIntegralValueHalfUp(dec('0E+2')))).toBe('0E+2');
        expect(decToString(toIntegralValueHalfUp(dec('1.5')))).toBe('2');
        expect(decToString(toIntegralValueHalfUp(dec('2.5')))).toBe('3');   // HALF_UP, not HALF_EVEN
        expect(decToString(toIntegralValueHalfUp(dec('-2.5')))).toBe('-3'); // away from zero
        expect(decToString(toIntegralValueHalfUp(dec('1.4')))).toBe('1');
    });

    it('min/max return the FIRST argument on numeric equality (CPython semantics)', () => {
        // Load-bearing: _snap's `max(lo, min(value, hi))` returns the literal
        // Decimal("0") on a zero award, and THAT exponent is what renders "0".
        expect(decToString(pyMin(dec('5'), dec('5.00')))).toBe('5');
        expect(decToString(pyMax(dec('0'), dec('0.00')))).toBe('0');
        expect(cmp(dec('5'), dec('5.00'))).toBe(0);
        expect(cmp(dec('0.5'), dec('0.25'))).toBe(1);
    });
});

describe('divideContext — CPython default context (prec 28, ROUND_HALF_EVEN)', () => {
    it('is divideExact when the quotient terminates', () => {
        expect(decToString(divideContext(dec('12'), dec('4')))).toBe('3');
        expect(decToString(divideContext(dec('1'), dec('4')))).toBe('0.25');
    });

    it("carries the 28 digits the backend's raw carries: 12 × 15 / 17", () => {
        // Python: Decimal(12) * Decimal(15) / Decimal(17)
        expect(decToString(divideContext(mul(dec('12'), dec('15')), dec('17'))))
            .toBe('10.58823529411764705882352941');
    });

    it('rounds half-even at the 28th digit, like CPython', () => {
        expect(decToString(divideContext(dec('1'), dec('3')))).toBe('0.3333333333333333333333333333');
        expect(decToString(divideContext(dec('2'), dec('3')))).toBe('0.6666666666666666666666666667');
        expect(decToString(divideContext(dec('1'), dec('300')))).toBe('0.003333333333333333333333333333');
    });
});
