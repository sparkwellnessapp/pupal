import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    priceV6,
    type DraftV6View,
    type PricedTest,
    type PricingOverlay,
    type ViewCheck,
} from './pricing-v6';

/**
 * PRC-7 — the TS mirror of `backend/app/services/pricing_v6.py` computes the
 * same result from the same JSON, on EVERY vector of `pricing_v6_vectors.json`
 * (the hand cases E1–E10 and the amendments' named cases, plus the 500 seeded
 * generated cases), read IN PLACE from the backend — never copied (CLAUDE.md
 * §0.4; `pricing.test.ts` set the precedent).
 *
 * The comparison is the WHOLE `PricedTest`, byte for byte: every decimal is
 * compared as its `str(Decimal)` string (so `"0.50"` ≠ `"0.5"` — the exponent
 * is part of the contract), and every field the Python model dumps — statuses,
 * `moved_by_pin` / `moved_from_terminal_id`, chips, flags, `counted` — is
 * compared, with no key allowed to be missing or extra. The backend side pins
 * the file itself (`tests/fixtures/test_pricing_v6_vectors.py` regenerates it
 * byte-identically from `scripts/gen_pricing_v6_vectors.py`).
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BACKEND = path.resolve(HERE, '../../../backend');
const FIXTURES = path.join(BACKEND, 'tests', 'fixtures', 'grade_review');

interface Vector {
    case: string;
    kind: 'hand' | 'generated';
    input: { view: DraftV6View; overlay: PricingOverlay | null };
    expected: PricedTest;
}

const vectors: Vector[] = JSON.parse(
    readFileSync(path.join(FIXTURES, 'pricing_v6_vectors.json'), 'utf-8'));

describe('pricing-v6 parity — every vector of pricing_v6_vectors.json', () => {
    it('the file carries the expected families (≥ 30 hand, exactly 500 generated)', () => {
        const hand = vectors.filter((v) => v.kind === 'hand');
        const generated = vectors.filter((v) => v.kind === 'generated');
        expect(hand.length).toBeGreaterThanOrEqual(30);
        expect(generated.length).toBe(500);
        expect(hand.length + generated.length).toBe(vectors.length);
        for (const e of ['E1', 'E2', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10']) {
            expect(hand.some((v) => v.case.startsWith(`${e}:`)), e).toBe(true);
        }
    });

    it.each(vectors.map((v) => [v.case, v] as const))('%s', (_name, v) => {
        const got = priceV6(v.input.view, v.input.overlay);
        expect(got).toStrictEqual(v.expected);
    });

    it('every vector, one count (the number the report quotes)', () => {
        let passing = 0;
        const failing: string[] = [];
        for (const v of vectors) {
            const got = priceV6(v.input.view, v.input.overlay);
            if (JSON.stringify(canonical(got)) === JSON.stringify(canonical(v.expected))) {
                passing += 1;
            } else {
                failing.push(v.case);
            }
        }
        expect(failing).toEqual([]);
        expect(passing).toBe(vectors.length);
        expect(vectors.length).toBe(544);
    });
});

describe('pricing-v6 — the input is not mutated, and the order is the plan order', () => {
    it('pricing leaves the view and overlay untouched', () => {
        for (const v of vectors.slice(0, 60)) {
            const before = JSON.stringify(v.input);
            priceV6(v.input.view, v.input.overlay);
            expect(JSON.stringify(v.input)).toBe(before);
        }
    });

    it('a shuffled `checks` array prices identically (plan_index is THE order)', () => {
        for (const v of vectors) {
            const reversed: DraftV6View = { ...v.input.view, checks: [...v.input.view.checks].reverse() };
            expect(priceV6(reversed, v.input.overlay)).toStrictEqual(v.expected);
        }
    });
});

describe('pricing-v6 — V7 is a precondition of step 4 (a consuming path refuses)', () => {
    it('a charge group spanning two scopes throws instead of charging once in each', () => {
        const binary = (cid: string, tid: string): ViewCheck => ({
            plan: {
                check_id: cid, role: 'credit', priced_terminal_id: tid,
                options: [{ option_id: 'full', value: '2' }, { option_id: 'absent', value: '0' }],
            },
            plan_index: 0, model_option_id: 'full', quote_status: 'exact',
        });
        const fault = (cid: string, tid: string): ViewCheck => ({
            plan: {
                check_id: cid, role: 'fault', priced_terminal_id: tid, charge_group: 'g',
                options: [{ option_id: 'none', value: '0' }, { option_id: 'f1', value: '-1' }],
            },
            plan_index: 0, model_option_id: 'f1', quote_status: 'exact',
        });
        const checks = [binary('A.c1', 'A'), fault('A.f1', 'A'), binary('B.c1', 'B'), fault('B.f1', 'B')]
            .map((c, i) => ({ ...c, plan_index: i }));
        const view: DraftV6View = {
            precision: '0.25',
            terminals: [
                { terminal_id: 'A', question_id: 'q1', sub_question_id: null, points_possible: '2' },
                { terminal_id: 'B', question_id: 'q2', sub_question_id: null, points_possible: '2' },
            ],
            checks,
            selection: { total_points: '4', question_order: ['q1', 'q2'], groups: [] },
        };
        expect(() => priceV6(view, null)).toThrow(/spans scopes/);
    });
});

/** Key-sorted deep copy, so the count above compares content, not key order. */
function canonical(x: unknown): unknown {
    if (Array.isArray(x)) return x.map(canonical);
    if (x !== null && typeof x === 'object') {
        const out: Record<string, unknown> = {};
        for (const k of Object.keys(x as Record<string, unknown>).sort()) {
            out[k] = canonical((x as Record<string, unknown>)[k]);
        }
        return out;
    }
    return x;
}
