import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';

import { hasMath, spliceMathBody, splitMath } from './math-spans';

/**
 * One definition of "where the math is", two languages: these are the SAME vectors the
 * backend's `tests/services/test_math_notation.py` reads, read in place (never copied —
 * CLAUDE.md §0.4).
 */
const HERE = path.dirname(fileURLToPath(import.meta.url));
const VECTORS = JSON.parse(readFileSync(
    path.resolve(HERE, '../../../backend/tests/fixtures/math_spans_vectors.json'), 'utf-8')) as {
    cases: { name: string; text: string; segments: [string, number, number, number, number][];
        unclosed: number[]; stray: number[] }[];
};

describe('splitMath — the shared vectors', () => {
    it('has cases', () => expect(VECTORS.cases.length).toBeGreaterThan(5));
    for (const c of VECTORS.cases) {
        it(c.name, () => {
            const res = splitMath(c.text);
            expect(res.segments.map((s) => [s.kind, s.start, s.end, s.bodyStart, s.bodyEnd]))
                .toEqual(c.segments);
            expect(res.unclosedAt).toEqual(c.unclosed);
            expect(res.strayCloseAt).toEqual(c.stray);
            // no byte lost or doubled
            expect(res.segments.map((s) => c.text.slice(s.start, s.end)).join('')).toBe(c.text);
        });
    }
});

describe('hasMath / spliceMathBody', () => {
    it('detects spans', () => {
        expect(hasMath('ש \\(x\\)')).toBe(true);
        expect(hasMath('public int x;')).toBe(false);
        expect(hasMath('')).toBe(false);
    });

    it('replaces one body and nothing else', () => {
        const text = 'א \\(x=1\\) ב \\(y=2\\)';
        const second = splitMath(text).segments.filter((s) => s.kind === 'math')[1];
        expect(spliceMathBody(text, second, 'y=3')).toBe('א \\(x=1\\) ב \\(y=3\\)');
    });
});
