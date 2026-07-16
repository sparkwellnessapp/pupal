import { describe, it, expect } from 'vitest';
import { formatPoints } from './rubric-display';
import { validateRubricTotalPoints, validateAllQuestions, validateQuestion } from './rubric-validation';
import { hydrateAnyQuestions, safeParseFloat } from './rubric-transform';
import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';

/**
 * Regression suite for the review-screen crash reported on the bagrut selection
 * exam: "TypeError: e.toFixed is not a function" → "Application error: a
 * client-side exception has occurred", thrown from a page.tsx useMemo.
 *
 * Root cause: the rubric-level declared total (ACHIEVABLE, "100.0") arrived as a
 * Decimal-serialized STRING but was typed `number`, bypassed the safeParseFloat
 * hydration boundary, and reached formatPoints(n.toFixed(2)). isClose short-
 * circuits on a matching total, so ONLY a rubric with a real mismatch — exactly
 * the case the gate exists for — reached the throwing line.
 */

// ---------------------------------------------------------------------------
// formatPoints — the seatbelt
// ---------------------------------------------------------------------------

describe('formatPoints', () => {
    it('formats numbers as before', () => {
        expect(formatPoints(5)).toBe('5');
        expect(formatPoints(5.0)).toBe('5');
        expect(formatPoints(5.25)).toBe('5.25');
        expect(formatPoints(5.249999)).toBe('5.25');
        expect(formatPoints(0)).toBe('0');
    });

    it('does NOT throw on a Decimal string that slipped past the type (the crash)', () => {
        // Before the fix this threw "toFixed is not a function" and unmounted React.
        expect(() => formatPoints('100.0' as unknown as number)).not.toThrow();
        expect(formatPoints('100.0' as unknown as number)).toBe('100');
        expect(formatPoints('15.50' as unknown as number)).toBe('15.5');
    });

    it('degrades garbage to "0" rather than crashing', () => {
        expect(formatPoints(NaN)).toBe('0');
        expect(formatPoints('abc' as unknown as number)).toBe('0');
        expect(formatPoints(undefined as unknown as number)).toBe('0');
    });
});

// ---------------------------------------------------------------------------
// validateRubricTotalPoints — must survive a string total (INV-R3 path)
// ---------------------------------------------------------------------------

function q(id: string, total: number): RubricQuestion {
    return {
        question_id: id,
        total_points: total,
        criteria: [],
        sub_questions: [],
    };
}

describe('validateRubricTotalPoints', () => {
    it('reproduces the exact crash shape and no longer throws', () => {
        // Six 25-point questions (offered 150) against an achievable declared
        // total that arrives as a STRING — the bagrut case. INV-R3 fires because
        // 150 !== 100; the old code then called formatPoints("100.0") and crashed.
        const questions = [1, 2, 3, 4, 5, 6].map((n) => q(`q${n}`, 25));
        const declaredAsString = '100.0' as unknown as number;

        expect(() => validateRubricTotalPoints(questions, declaredAsString)).not.toThrow();

        const issue = validateRubricTotalPoints(questions, declaredAsString);
        expect(issue).not.toBeNull();
        // The numbers render, not "[object Object]" or a crash.
        expect(issue!.message).toContain('100');
        expect(issue!.message).toContain('150');
    });

    it('returns null (no false error) when Σ matches the declared total', () => {
        const questions = [q('q1', 50), q('q2', 50)];
        expect(validateRubricTotalPoints(questions, 100)).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// The boundary itself — hydration must yield numbers for every point value
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// B-11 — recursive validator parity with the backend _walk_sub_question.
// The client INV-R1b must fire at the SAME node the backend does, at any depth.
// ---------------------------------------------------------------------------

function crit(id: string, points: number): RubricCriterion {
    return { criterion_id: id, index: 0, description: '', points };
}
function leaf(id: string, points: number, criteria: RubricCriterion[]): RubricSubQuestion {
    return { sub_question_id: id, index: 0, points, criteria };
}
function parent(id: string, points: number, children: RubricSubQuestion[]): RubricSubQuestion {
    return { sub_question_id: id, index: 0, points, criteria: [], sub_questions: children };
}
function nestedQuestion(sub: RubricSubQuestion[], total: number): RubricQuestion {
    return { question_id: 'q1', total_points: total, criteria: [], sub_questions: sub };
}

describe('B-11 — recursive INV-R1b mirrors _walk_sub_question at any depth', () => {
    it('LEAF mismatch surfaces at the full path q1.א.2 (the real bagrut error)', () => {
        // q1 → א(15) → [1(12, crit 12), 2(3, crit 1.5+0.5=2)]. Leaf 2 sums to 2, declares 3.
        const q = nestedQuestion([
            parent('א', 15, [
                leaf('1', 12, [crit('c1', 12)]),
                leaf('2', 3, [crit('c2', 1.5), crit('c3', 0.5)]),
            ]),
        ], 15);
        const issues = validateQuestion(q, 0, [q]);
        const r1b = issues.filter(i => i.invariant === 'INV-R1b');
        expect(r1b).toHaveLength(1);
        expect(r1b[0].target_id).toBe('q1.א.2');
        expect(r1b[0].severity).toBe('error');
    });

    it('PARENT mismatch surfaces at q1.א (Σ children ≠ parent points)', () => {
        // א declares 15 but its children sum to 14 — a PARENT error the depth-1
        // validator was blind to (it treated a parent as vacuously satisfied).
        const q = nestedQuestion([
            parent('א', 15, [
                leaf('1', 12, [crit('c1', 12)]),
                leaf('2', 2, [crit('c2', 2)]),
            ]),
        ], 15);
        const issues = validateQuestion(q, 0, [q]);
        const r1b = issues.filter(i => i.invariant === 'INV-R1b');
        expect(r1b).toHaveLength(1);
        expect(r1b[0].target_id).toBe('q1.א');
    });

    it('a fully consistent nested tree yields zero issues', () => {
        const q = nestedQuestion([
            parent('א', 15, [
                leaf('1', 12, [crit('c1', 12)]),
                leaf('2', 3, [crit('c2', 1.5), crit('c3', 1.5)]),
            ]),
        ], 15);
        expect(validateQuestion(q, 0, [q])).toHaveLength(0);
    });

    it('INV-R-XOR fires when a node has both criteria and sub_questions', () => {
        // A parent sub-question that ALSO carries a direct criterion — StructureExclusivity.
        const bad = parent('א', 15, [leaf('1', 15, [crit('c1', 15)])]);
        bad.criteria = [crit('cx', 15)]; // both populated
        const q = nestedQuestion([bad], 15);
        const issues = validateQuestion(q, 0, [q]);
        expect(issues.some(i => i.invariant === 'INV-R-XOR' && i.target_id === 'q1.א')).toBe(true);
    });
});

describe('hydration coerces every point value to a number', () => {
    it('safeParseFloat is what the rubric total now passes through', () => {
        expect(safeParseFloat('100.0')).toBe(100);
        expect(safeParseFloat(100)).toBe(100);
        expect(safeParseFloat(null)).toBe(0);
    });

    it('question / sub-question / criterion points come out as numbers, never strings', () => {
        // Wire shape: Decimal serialized as strings, exactly as the backend sends.
        const wire = [
            {
                question_id: 'q1',
                total_points: '25.0',
                criteria: [],
                sub_questions: [
                    { sub_question_id: 'א', points: '12.0', criteria: [
                        { criterion_id: 'c1', description: 'x', points: '12.0' },
                    ] },
                ],
            },
        ];
        const [hq] = hydrateAnyQuestions(wire as never);
        expect(typeof hq.total_points).toBe('number');
        expect(typeof hq.sub_questions[0].points).toBe('number');
        expect(typeof hq.sub_questions[0].criteria[0].points).toBe('number');

        // And a full validation pass over hydrated data never throws.
        expect(() => validateAllQuestions([hq])).not.toThrow();
    });
});
