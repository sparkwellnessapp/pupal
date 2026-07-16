import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions } from './rubric-transform';
import { computeAchievablePoints } from './rubric-achievable';
import type { SelectionGroup } from '@/lib/api';

/**
 * R-C parity guard: the client `computeAchievablePoints` mirror must agree with
 * the backend's `compute_achievable_points` on every golden fixture. The backend
 * bakes the achievable total into `fixture.total_points` (INV-4 holds on the
 * goldens by construction), so client(mirror) === GT total is the parity check.
 *
 * Covers both regimes:
 *   - selection: bagrut (choose 4/6 → 100), employee (choose 1/3 → 50)
 *   - non-selection: csharp/foundations/hobby (achievable ≡ offered Σ → 100)
 *
 * Read IN PLACE from the backend eval suite (the canonical fixture owner) —
 * copying would duplicate ground truth (CLAUDE.md §0.4).
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');

const FIXTURES = [
    'bagrut_899371',
    'csharp_plane_combine',
    'employee_course_select1',
    'foundations_cs',
    'hobby_tvshow',
] as const;

function loadGolden(name: string): {
    questions: unknown[];
    selection_groups?: SelectionGroup[];
    total_points: string | number;
} {
    return JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8'));
}

describe('R-C — client computeAchievablePoints mirrors the backend on every golden', () => {
    for (const name of FIXTURES) {
        it(`${name}: achievable(client) === GT total_points`, () => {
            const golden = loadGolden(name);
            const questions = hydrateAnyQuestions(golden.questions);
            const achievable = computeAchievablePoints(questions, golden.selection_groups ?? []);
            expect(achievable).toBeCloseTo(Number(golden.total_points), 5);
        });
    }
});

describe('computeAchievablePoints — unit properties', () => {
    const q = (id: string, pts: number) => ({
        question_id: id, total_points: pts, criteria: [], sub_questions: [],
    }) as never;

    it('no groups → offered sum (reduces to legacy INV-4)', () => {
        expect(computeAchievablePoints([q('q1', 15), q('q2', 50), q('q3', 35)], [])).toBe(100);
    });

    it('choose 1 of 3 → the single best member', () => {
        const groups: SelectionGroup[] = [
            { group_id: 'sg0', choose_k: 1, of_question_ids: ['q1', 'q2', 'q3'] },
        ];
        expect(computeAchievablePoints([q('q1', 15), q('q2', 50), q('q3', 35)], groups)).toBe(50);
    });

    it('mandatory question outside the group still counts', () => {
        const groups: SelectionGroup[] = [
            { group_id: 'sg0', choose_k: 1, of_question_ids: ['q1', 'q2'] },
        ];
        // best-of(q1=10,q2=20)=20  +  mandatory q3=7  = 27
        expect(computeAchievablePoints([q('q1', 10), q('q2', 20), q('q3', 7)], groups)).toBe(27);
    });

    it('dangling member id contributes 0, not a crash', () => {
        const groups: SelectionGroup[] = [
            { group_id: 'sg0', choose_k: 1, of_question_ids: ['q1', 'ghost'] },
        ];
        expect(computeAchievablePoints([q('q1', 10)], groups)).toBe(10);
    });
});
