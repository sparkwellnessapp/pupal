import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { expectedEmptyKeys, type AnswerSpaceSelectionGroup } from './selection-expectation';

/**
 * Cross-pinned with the backend: BOTH sides run the SAME cases from
 * backend/tests/fixtures/selection_expectation_cases.json (read in place —
 * the rubric-transform precedent). A rule change must keep both green.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(HERE, '../../../backend/tests/fixtures/selection_expectation_cases.json');

interface FixtureCase {
    name: string;
    groups: AnswerSpaceSelectionGroup[];
    answers: [number, string | null, string][];
    expected_empty: [number, string | null][];
}

const cases: FixtureCase[] = JSON.parse(readFileSync(FIXTURE, 'utf-8')).cases;

function keyOf(q: number, sub: string | null): string {
    return sub ? `q${q}.${sub}` : `q${q}`;
}

describe('expectedEmptyKeys — shared fixture cases (backend-pinned)', () => {
    for (const c of cases) {
        it(c.name, () => {
            const got = expectedEmptyKeys(
                c.answers.map(([question_number, sub_question_id, text]) => ({
                    question_number, sub_question_id, text,
                })),
                c.groups,
            );
            const want = new Set(c.expected_empty.map(([q, sub]) => keyOf(q, sub)));
            expect(Array.from(got).sort()).toEqual(Array.from(want).sort());
        });
    }

    it('returns an empty set for undefined/null groups', () => {
        const answers = [{ question_number: 1, sub_question_id: null, text: '' }];
        expect(expectedEmptyKeys(answers, undefined).size).toBe(0);
        expect(expectedEmptyKeys(answers, null).size).toBe(0);
    });
});
