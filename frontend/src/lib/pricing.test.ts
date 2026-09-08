import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    applyOverlay,
    priceScopeChecks,
    priceScopeChecksDetailed,
    type NumericPolicy,
    type PricingCheck,
    type ScopeTerminal,
} from './pricing';

/**
 * `pricer-parity` (PR spec §7, phase F0) — the TS mirror of
 * `backend/app/services/pricing.py` must reproduce the published §1.7 vectors
 * BYTE-FOR-BYTE, and must agree with the backend's own pure tests case for
 * case.
 *
 * Two halves, both required:
 *   1. the §1.7 vectors, read IN PLACE from the backend (never copied —
 *      CLAUDE.md §0.4; `rubric-achievable.test.ts` set that precedent);
 *   2. a 1:1 mirror of `backend/tests/services/test_pricing_composition.py`,
 *      because the observed cohort cannot exercise charge-group dedup or the
 *      teacher-authority rule. The coverage assertions below fail LOUDLY if
 *      the fixture set grows to cover them, so the mirror is re-verified
 *      instead of silently continuing to claim AI-only parity.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BACKEND = path.resolve(HERE, '../../../backend');
const FIXTURES = path.join(BACKEND, 'tests', 'fixtures', 'grade_review');
const CONTRACT = path.join(
    BACKEND, 'tests', 'grading_eval_suite', 'benchmarks', 'contracts',
    'hobby_tvshow_corrected.contract.json',
);

interface Vector {
    case: string;
    student: string;
    terminal_id: string;
    overlay: Record<string, unknown>;
    checks: PricingCheck[];
    expected_points_awarded: string;
    points_possible: string;
}

const vectors: Vector[] = JSON.parse(
    readFileSync(path.join(FIXTURES, 'pricing_vectors.json'), 'utf-8'));

/**
 * The whole numeric policy, read from the rubric contract that priced these
 * drafts — not a hardcoded 0.25 the fixture set cannot defend.
 *
 * All three fields travel (owner ruling, 2026-08-31): `precision` alone leaves
 * the client free to round an exact .5 differently from the server, and on a
 * 0.25 grid that is precisely where the boundaries fall. `numeric_policy` now
 * rides `GradedTestDraftResponse` and `GradedTestApprovedResponse`.
 */
const POLICY: NumericPolicy = JSON.parse(readFileSync(CONTRACT, 'utf-8')).numeric_policy;

const check = (cid: string, over: Partial<PricingCheck> = {}): PricingCheck => ({
    check_id: cid,
    kind: 'required',
    points: '0',
    tariff: null,
    partial_fraction: '0.5',
    verdict: 'met',
    quote_status: 'exact',
    charge_group: null,
    ...over,
});

describe('pricer-parity — the §1.7 vectors, byte for byte', () => {
    it('reads a real fixture set at the contract precision', () => {
        expect(POLICY.precision).toBe('0.25');
        expect(POLICY.rounding_mode).toBe('half_up');
        expect(vectors.length).toBeGreaterThan(100);
    });

    it('reproduces every published vector exactly', () => {
        const wrong: string[] = [];
        for (const v of vectors) {
            const got = priceScopeChecks(
                [{
                    terminal_id: v.terminal_id,
                    points_possible: v.points_possible,
                    checks: v.checks,
                }],
                POLICY,
            )[v.terminal_id];
            if (got !== v.expected_points_awarded) {
                wrong.push(`${v.case}: got ${got}, want ${v.expected_points_awarded}`);
            }
        }
        expect(wrong).toEqual([]);
    });

    it('records what the observed cohort CANNOT cover, so growth is loud', () => {
        // PR-G5 has not published overlay vectors yet (MANIFEST.json `pending`).
        // When it does, this fails and the mirror gets verified against them.
        const withOverlay = vectors.filter((v) => Object.keys(v.overlay ?? {}).length > 0);
        expect(withOverlay.map((v) => v.case)).toEqual([]);

        // The generator predates `charge_group` on Check, so no published
        // vector can exercise scope-wide dedup — it is pinned by the mirrored
        // unit tests below instead. Drop this when the generator emits it.
        const withGroup = vectors.filter((v) => v.checks.some((c) => c.charge_group));
        expect(withGroup.map((v) => v.case)).toEqual([]);
    });
});

/** 1:1 with backend `tests/services/test_pricing_composition.py`. */
describe('pricer-parity — the rules the vectors cannot show', () => {
    const one = (t: ScopeTerminal[], ids?: Set<string>) => priceScopeChecks(t, POLICY, ids);

    it('prices met / partially_met / not_met on a required check', () => {
        expect(one([
            {
                terminal_id: 't1', points_possible: '4',
                checks: [check('t1.k1', { points: '4', verdict: 'met' })],
            },
            {
                terminal_id: 't2', points_possible: '4',
                checks: [check('t2.k1', { points: '4', verdict: 'partially_met' })],
            },
            {
                terminal_id: 't3', points_possible: '4',
                checks: [check('t3.k1', { points: '4', verdict: 'not_met' })],
            },
        ])).toEqual({ t1: '4.00', t2: '2.00', t3: '0' });
    });

    it('refuses AI credit on an unverified span (the invented-credit guard)', () => {
        expect(one([{
            terminal_id: 't1', points_possible: '4',
            checks: [check('t1.k1', { points: '4', verdict: 'met', quote_status: 'not_found' })],
        }]).t1).toBe('0');
    });

    it('does NOT evidence-gate a check the TEACHER decided', () => {
        expect(one([{
            terminal_id: 't1', points_possible: '4',
            checks: [check('t1.k1', { points: '4', verdict: 'met', quote_status: 'not_found' })],
        }], new Set(['t1.k1'])).t1).toBe('4.00');
    });

    it('dedups a charge_group across the WHOLE scope, at the max fired amount', () => {
        expect(one([
            {
                terminal_id: 't1', points_possible: '5', checks: [
                    check('t1.k1', { points: '5', verdict: 'met' }),
                    check('t1.k2', { kind: 'tariff', tariff: '1', verdict: 'not_met', charge_group: 'g' }),
                ],
            },
            {
                terminal_id: 't2', points_possible: '5', checks: [
                    check('t2.k1', { points: '5', verdict: 'met' }),
                    check('t2.k2', { kind: 'tariff', tariff: '2', verdict: 'not_met', charge_group: 'g' }),
                ],
            },
            // '5.0', not '5.00': 5 ÷ 0.25 reduces to Decimal('2E+1') (ideal
            // exponent 2), and 2E+1 × 0.25 lands at exponent −1. Probed
            // against the real backend pricer, not reasoned about — and it is
            // the same rule that puts eight '5.0' entries in the vector file.
        ])).toEqual({ t1: '3.00', t2: '5.0' });
    });

    it('never lets a note_only check move points', () => {
        expect(one([{
            terminal_id: 't1', points_possible: '4', checks: [
                check('t1.k1', { points: '4', verdict: 'met' }),
                check('t1.k2', { kind: 'note_only', verdict: 'not_met' }),
            ],
        }]).t1).toBe('4.00');
    });

    it('clamps below zero and reports the pre-clamp raw', () => {
        const got = priceScopeChecksDetailed([{
            terminal_id: 't1', points_possible: '2', checks: [
                check('t1.k1', { points: '2', verdict: 'met' }),
                check('t1.k2', { kind: 'tariff', tariff: '5', verdict: 'not_met' }),
            ],
        }], POLICY);
        expect(got.t1.awarded).toBe('0');
        expect(got.t1.raw).toBe('-3');
    });

    it('coerces partially_met on a binary tariff to fired', () => {
        expect(one([{
            terminal_id: 't1', points_possible: '5', checks: [
                check('t1.k1', { points: '5', verdict: 'met' }),
                check('t1.k2', { kind: 'tariff', tariff: '1', verdict: 'partially_met' }),
            ],
        }]).t1).toBe('4.00');
    });

    it('treats a null points value as no credit, never as invented credit', () => {
        // `points` types as `string | null` on the generated wire (a serializer
        // artifact — Python's Check.points is required). Conservative by
        // policy: a check with no stated credit earns none.
        expect(one([{
            terminal_id: 't1', points_possible: '4',
            checks: [check('t1.k1', { points: null, verdict: 'met' })],
        }]).t1).toBe('0');
    });
});

/**
 * The three states the observed cohort could not produce, now on disk
 * (`draft_SYNTHETIC_edge_cases.json`, owner ruling 2026-08-31): a `not_found`
 * quote, a `fuzzy` quote, and a `skipped_no_answer` scope.
 *
 * F2 owns how they RENDER — the highlight, the amber chip, the "no answer"
 * line. What belongs here is what they do to the POINTS, because that is where
 * getting them wrong is invisible: a `met` on a span that is not in the answer
 * must earn nothing, and if it quietly earned its points instead, the score
 * would look perfectly ordinary on the one test that most needs her eye.
 */
describe('the three edge-case states, on the real synthetic draft', () => {
    const synthetic = JSON.parse(
        readFileSync(path.join(FIXTURES, 'draft_SYNTHETIC_edge_cases.json'), 'utf-8'));
    const touched = synthetic._synthetic_touched as
        { not_found: string; fuzzy: string; skipped: string };

    /** Every terminal in the draft, flattened the way the review surface will. */
    const terminals = (): { scope: string; terminal: ScopeTerminal }[] =>
        (synthetic.scope_outcomes ?? []).flatMap((scope: {
            question_id: string; graded_by: string;
            criterion_outcomes: Record<string, unknown>[];
        }) => (scope.criterion_outcomes ?? []).flatMap((crit) => {
            const leaves = (crit.sub_criterion_outcomes as Record<string, unknown>[] | null)
                ?.length ? crit.sub_criterion_outcomes as Record<string, unknown>[] : [crit];
            return leaves.map((leaf) => ({
                scope: scope.question_id,
                terminal: {
                    terminal_id: (leaf.sub_criterion_id ?? leaf.criterion_id) as string,
                    points_possible: leaf.points_possible as string,
                    checks: (leaf.checks ?? []) as PricingCheck[],
                },
            }));
        }));

    const findCheck = (checkId: string) => {
        for (const { terminal } of terminals()) {
            const found = terminal.checks.find((c) => c.check_id === checkId);
            if (found) return { terminal, check: found };
        }
        throw new Error(`synthetic fixture no longer carries ${checkId}`);
    };

    it('carries all three states, self-labelled as synthetic', () => {
        expect(synthetic._synthetic).toBe(true);
        expect(synthetic._synthetic_reason).toMatch(/not_found|fuzzy|skipped/i);
        expect(touched.not_found).toBeTruthy();
        expect(touched.fuzzy).toBeTruthy();
        expect(touched.skipped).toBeTruthy();
    });

    it('1 · not_found: a met check on an unfound span earns NOTHING', () => {
        const { terminal, check } = findCheck(touched.not_found);
        expect(check.quote_status).toBe('not_found');
        expect(check.verdict).toBe('met');            // the model claimed it

        const withGuard = priceScopeChecks([terminal], POLICY)[terminal.terminal_id];
        const asIfFound = priceScopeChecks(
            [{ ...terminal, checks: terminal.checks.map((c) => c.check_id === check.check_id
                ? { ...c, quote_status: 'exact' as const } : c) }],
            POLICY,
        )[terminal.terminal_id];

        // The guard must actually COST something here, or this fixture is
        // proving nothing: if both numbers matched, the check would be earning
        // zero for some unrelated reason and the test would pass vacuously.
        expect(withGuard).not.toBe(asIfFound);
    });

    it('2 · fuzzy: a near-miss span is verified, and DOES earn its points', () => {
        const { terminal, check } = findCheck(touched.fuzzy);
        expect(check.quote_status).toBe('fuzzy');

        const withFuzzy = priceScopeChecks([terminal], POLICY)[terminal.terminal_id];
        const asIfNotFound = priceScopeChecks(
            [{ ...terminal, checks: terminal.checks.map((c) => c.check_id === check.check_id
                ? { ...c, quote_status: 'not_found' as const } : c) }],
            POLICY,
        )[terminal.terminal_id];

        // fuzzy is a RENDERING distinction (dashed underline + chip), not a
        // pricing one — the span was found, so credit stands. Dropping it into
        // the not_found bucket would silently deduct points on a match Vivi
        // actually made.
        expect(withFuzzy).not.toBe(asIfNotFound);
    });

    it('3 · skipped_no_answer: the scope has no checks and scores zero', () => {
        // Found by graded_by, NOT by question_id: the generator appends a COPY
        // of the last scope, so the synthetic skipped scope and the real graded
        // one share `q2`. Filtering by id silently mixes real terminals into
        // the assertion — which is how this test first passed a scope that
        // still had points in it.
        const skipped = (synthetic.scope_outcomes ?? []).find(
            (s: { graded_by: string }) => s.graded_by === 'skipped_no_answer');
        expect(skipped).toBeDefined();

        const scopeTerminals: ScopeTerminal[] = (skipped.criterion_outcomes ?? [])
            .flatMap((crit: Record<string, unknown>) => {
                const subs = crit.sub_criterion_outcomes as Record<string, unknown>[] | null;
                const leaves = subs?.length ? subs : [crit];
                return leaves.map((leaf) => ({
                    terminal_id: (leaf.sub_criterion_id ?? leaf.criterion_id) as string,
                    points_possible: leaf.points_possible as string,
                    checks: (leaf.checks ?? []) as PricingCheck[],
                }));
            });
        expect(scopeTerminals.every((t) => t.checks.length === 0)).toBe(true);

        const priced = priceScopeChecks(scopeTerminals, POLICY);
        expect(Object.values(priced).every((v) => Number(v) === 0)).toBe(true);
        // An empty checks list must price as zero, not throw — a skipped scope
        // is a normal outcome she has to be shown, not an error state.
        expect(Object.keys(priced).length).toBeGreaterThan(0);
    });
});

/**
 * THE ROUNDING MODE, and why the mirror refuses the ones it cannot honour.
 *
 * `numeric_policy.rounding_mode` now reaches the client (owner ruling), and the
 * reason given was exact: half_up and half_even disagree on every exact .5,
 * which on a 0.25 grid is where the boundaries fall.
 *
 * But NO CODE IN THE BACKEND READS THAT FIELD. Both `services/pricing.py:48`
 * and `agents/grader/pricer.py:81` hardcode `ROUND_HALF_UP`; the only other
 * reference echoes it through rubric_management. So a client that dutifully
 * honoured a `half_even` policy would round DIFFERENTLY FROM THE SERVER — it
 * would re-create the divergence the field was sent to close, just pointed the
 * other way. Until the server reads its own policy, agreeing is what matters
 * and the mirror refuses anything it cannot prove the server does too.
 */
describe('rounding mode — the mirror never guesses what the server does', () => {
    const terminal: ScopeTerminal[] = [{
        terminal_id: 't1', points_possible: '4',
        checks: [check('t1.k1', { points: '3', verdict: 'partially_met' })],   // 1.5
    }];

    it('prices under half_up, which is what both server sites hardcode', () => {
        expect(priceScopeChecks(terminal, { ...POLICY, rounding_mode: 'half_up' }).t1)
            .toBe('1.50');
    });

    it('REFUSES a mode the server does not implement, naming why', () => {
        expect(() => priceScopeChecks(terminal, { ...POLICY, rounding_mode: 'half_even' }))
            .toThrow(/half_up/);
        expect(() => priceScopeChecks(terminal, { ...POLICY, rounding_mode: 'floor' }))
            .toThrow(/rounding_mode/);
    });

    it('refuses a policy with no precision rather than assuming a grid', () => {
        expect(() => priceScopeChecks(terminal, { ...POLICY, precision: undefined }))
            .toThrow(/precision/);
    });
});

describe('applyOverlay — sparse by construction', () => {
    const checks = [
        check('k1', { points: '2' }),
        check('k2', { points: '2', verdict: 'not_met' }),
    ];

    it('passes untouched checks through and reports what she decided', () => {
        const { effective, touched } = applyOverlay(checks, [{ check_id: 'k2', verdict: 'met' }]);
        expect(effective.map((c) => c.verdict)).toEqual(['met', 'met']);
        expect([...touched]).toEqual(['k2']);
        expect(checks[1].verdict).toBe('not_met');       // never mutates the draft
    });

    it('ignores an override for a check that is not in this terminal', () => {
        const { effective, touched } = applyOverlay(checks, [{ check_id: 'ghost', verdict: 'met' }]);
        expect(effective).toEqual(checks);
        expect([...touched]).toEqual([]);
    });

    it('an empty overlay is the identity', () => {
        expect(applyOverlay(checks, []).effective).toEqual(checks);
        expect(applyOverlay(checks, undefined).effective).toEqual(checks);
    });
});

describe('pricer-parity — counted (PLAN COMPILER v2, C3; mirrors tests/agents/test_counted_kind.py)', () => {
    const one = (t: ScopeTerminal[], ids?: Set<string>) => priceScopeChecks(t, POLICY, ids);
    const counted = (over: Partial<PricingCheck> = {}): PricingCheck =>
        check('t.k1', { kind: 'counted', points: '12', unit_count: 17, ...over });
    const terminal = (c: PricingCheck): ScopeTerminal[] =>
        [{ terminal_id: 't', points_possible: '12', checks: [c] }];

    it("produces noam's 10.5: 12 × 15/17 snapped with the terminal on the 0.25 grid", () => {
        expect(one(terminal(counted({ verdict: 'partially_met', units_correct: 15 })))).toEqual({ t: '10.50' });
    });

    it("carries Python's 28-digit quotient as the raw", () => {
        const d = priceScopeChecksDetailed(terminal(counted({ verdict: 'partially_met', units_correct: 15 })), POLICY);
        expect(d.t.raw).toBe('10.58823529411764705882352941');
        expect(d.t.awarded).toBe('10.50');
    });

    it('met and not_met are the two ends', () => {
        expect(one(terminal(counted({ verdict: 'met' })))).toEqual({ t: '12.00' });
        expect(one(terminal(counted({ verdict: 'not_met', quote_status: null })))).toEqual({ t: '0' });
    });

    it('a partial verdict with no count earns nothing — an invented count is a number nobody emitted', () => {
        expect(one(terminal(counted({ verdict: 'partially_met', units_correct: null })))).toEqual({ t: '0' });
    });

    it('clamps the count into range', () => {
        expect(one(terminal(counted({ verdict: 'partially_met', units_correct: 99 })))).toEqual({ t: '12.00' });
        expect(one(terminal(counted({ verdict: 'partially_met', units_correct: -3 })))).toEqual({ t: '0' });
    });

    it('is evidence-gated like a required check', () => {
        expect(one(terminal(counted({ verdict: 'partially_met', units_correct: 15, quote_status: 'not_found' }))))
            .toEqual({ t: '0' });
    });
});
