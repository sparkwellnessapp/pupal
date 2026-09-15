/**
 * [OD-R2] Parsing and validating an amount the teacher TYPES.
 *
 * Pure, and deliberately separate from `lib/pricing.ts`: the pricer mirrors
 * the backend byte for byte and must stay free of anything the backend does
 * not have. What the backend does have is the GATE — ceiling, grid — and that
 * half is mirrored here exactly (`graded_test_contract_compiler
 * .typed_points_violations`), so a number the client accepts is a number the
 * server accepts. The parsing half is client-only: the server never sees her
 * keystrokes, only the decimal string this module hands over.
 *
 * ── REFUSE, NEVER SNAP (OD-4 a) ────────────────────────────────────────────
 * 3.3 on a 0.25 grid is HER number. Rounding it to 3.25 would commit a value
 * she did not type — the exact silent repair FC forbids — so an off-grid or
 * out-of-range amount is refused with a sentence that names her number and
 * the limit, and nothing is written until she changes it. The refusal shows
 * LIVE while she types, not only on commit (owner ruling).
 */

import { cmp, dec, divideExact, toIntegralValueHalfUp, toString as decToString } from '@/lib/decimal';
import type { NumericPolicy } from '@/lib/pricing';

export type PointsEntryReason = 'empty' | 'not_a_number' | 'negative' | 'over_max' | 'off_grid';

export type PointsEntryVerdict =
    | { ok: true; value: string }
    | { ok: false; reason: PointsEntryReason };

/**
 * What she typed, as a canonical decimal string — or null when it is not a
 * number at all.
 *
 * Accepts a comma as the decimal separator (a Hebrew keyboard's numeric row
 * produces one as readily as a point) and a bare leading point (`.5`). Rejects
 * everything else: no exponent, no thousands separators, no whitespace inside.
 * A leading minus parses (so the caller can say «below zero» rather than «not
 * a number»), everything after it must still be a plain decimal.
 */
export function parsePointsInput(text: string): string | null {
    const trimmed = text.trim().replace(',', '.');
    if (!/^-?(\d+(\.\d*)?|\.\d+)$/.test(trimmed)) return null;
    const negative = trimmed.startsWith('-');
    let body = negative ? trimmed.slice(1) : trimmed;
    if (body.startsWith('.')) body = `0${body}`;
    if (body.endsWith('.')) body = body.slice(0, -1);
    return negative ? `-${body}` : body;
}

/**
 * The grid, refused when absent. `lib/pricing.ts` refuses the same way: the
 * wire omits the policy rather than defaulting it when the contract will not
 * parse, and a guessed grid would accept numbers the server rejects.
 */
function precisionOf(policy: NumericPolicy): string {
    if (policy?.precision == null || policy.precision === '') {
        throw new Error('points-entry: numeric_policy.precision is missing');
    }
    return policy.precision;
}

/** `amount / precision` is a whole number — the backend's `_on_grid`. */
export function isOnGrid(amount: string, policy: NumericPolicy): boolean {
    const grid = dec(precisionOf(policy));
    const quotient = divideExact(dec(amount), grid);
    return cmp(quotient, toIntegralValueHalfUp(quotient)) === 0;
}

/**
 * The client half of the gate. `maximum` is the ceiling the server will apply:
 * `points_possible` for a criterion, `points` for a credit check, `tariff`
 * for a deduction.
 */
export function validateTypedAmount(
    text: string,
    maximum: string,
    policy: NumericPolicy,
): PointsEntryVerdict {
    if (text.trim() === '') return { ok: false, reason: 'empty' };
    const value = parsePointsInput(text);
    if (value === null) return { ok: false, reason: 'not_a_number' };
    const amount = dec(value);
    if (cmp(amount, dec('0')) < 0) return { ok: false, reason: 'negative' };
    if (cmp(amount, dec(maximum)) > 0) return { ok: false, reason: 'over_max' };
    if (!isOnGrid(value, policy)) return { ok: false, reason: 'off_grid' };
    return { ok: true, value };
}

/** The grid step as the teacher reads it («0.25», «0.5», «1»). */
export function gridStepLabel(policy: NumericPolicy): string {
    return decToString(dec(precisionOf(policy)));
}
