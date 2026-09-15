import { describe, expect, it } from 'vitest';

import type { NumericPolicy } from '@/lib/pricing';
import { gridStepLabel, isOnGrid, parsePointsInput, validateTypedAmount } from './points-entry';

const QUARTER: NumericPolicy = { precision: '0.25', rounding_mode: 'half_up', total_points: '100' } as NumericPolicy;
const HALF: NumericPolicy = { ...QUARTER, precision: '0.5' };

describe('points-entry — parsing what she typed', () => {
    it('reads plain decimals, a comma separator and a bare leading point', () => {
        expect(parsePointsInput('3')).toBe('3');
        expect(parsePointsInput(' 2.5 ')).toBe('2.5');
        expect(parsePointsInput('2,5')).toBe('2.5');
        expect(parsePointsInput('.5')).toBe('0.5');
        expect(parsePointsInput('3.')).toBe('3');
        expect(parsePointsInput('-1')).toBe('-1');
    });

    it('rejects anything that is not one number', () => {
        // (`1,000` is NOT rejected: a comma is the decimal separator here, so it reads as 1.000)
        for (const bad of ['', 'abc', '1e2', '1 2', '1..5', '1,0,0', '2/5', '+3']) {
            expect(parsePointsInput(bad)).toBeNull();
        }
    });
});

describe('points-entry — the client half of the gate (mirrors typed_points_violations)', () => {
    it('accepts an on-grid amount within the ceiling', () => {
        expect(validateTypedAmount('2.25', '5', QUARTER)).toEqual({ ok: true, value: '2.25' });
        expect(validateTypedAmount('5', '5', QUARTER)).toEqual({ ok: true, value: '5' });
        expect(validateTypedAmount('0', '5', QUARTER)).toEqual({ ok: true, value: '0' });
    });

    it('refuses above the ceiling, below zero, and off the grid — never snaps', () => {
        expect(validateTypedAmount('6', '5', QUARTER)).toEqual({ ok: false, reason: 'over_max' });
        expect(validateTypedAmount('-0.25', '5', QUARTER)).toEqual({ ok: false, reason: 'negative' });
        expect(validateTypedAmount('3.3', '5', QUARTER)).toEqual({ ok: false, reason: 'off_grid' });
        // the same number is fine on a grid it fits
        expect(validateTypedAmount('2.5', '5', HALF)).toEqual({ ok: true, value: '2.5' });
        expect(validateTypedAmount('2.25', '5', HALF)).toEqual({ ok: false, reason: 'off_grid' });
    });

    it('tells an empty field from a non-number, so the popover stays quiet while she clears it', () => {
        expect(validateTypedAmount('', '5', QUARTER)).toEqual({ ok: false, reason: 'empty' });
        expect(validateTypedAmount('x', '5', QUARTER)).toEqual({ ok: false, reason: 'not_a_number' });
    });

    it('isOnGrid and the step label agree with the policy', () => {
        expect(isOnGrid('0.75', QUARTER)).toBe(true);
        expect(isOnGrid('0.7', QUARTER)).toBe(false);
        expect(gridStepLabel(QUARTER)).toBe('0.25');
        expect(gridStepLabel(HALF)).toBe('0.5');
    });

    it('refuses to validate without a grid, like the pricer', () => {
        expect(() => validateTypedAmount('1', '5', { ...QUARTER, precision: null } as unknown as NumericPolicy))
            .toThrow(/precision/);
    });
});
