import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { markRangesFor, markRangesForAll } from './evidence-highlight';
import { matchForm, matchFormAt } from './math-match';

/**
 * QM-1 — the client places a math quote with the SERVER's rule. The vectors are generated
 * from the Python implementation (`backend/scripts/gen_math_quote_match_vectors.py`), so a
 * drift on either side fails here.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url));
const V = JSON.parse(readFileSync(
    path.resolve(HERE, '../../../backend/tests/fixtures/math_quote_match_vectors.json'), 'utf-8')) as {
    answer: string;
    forms: { text: string; form: string }[];
    quotes: { name: string; quote: string; contained: boolean; expected: boolean; server_status: string }[];
};

describe('the match form is the server\'s, byte for byte', () => {
    for (const { text, form } of V.forms) {
        it(JSON.stringify(text).slice(0, 60), () => {
            expect(matchForm(text)).toBe(form);
        });
    }
});

describe('a certified quote lights the student\'s own marks', () => {
    for (const q of V.quotes) {
        it(q.name, () => {
            expect(matchForm(V.answer).includes(matchForm(q.quote))).toBe(q.contained);
            const ranges = markRangesFor(V.answer, q.quote, 'exact', { math: true });
            if (q.server_status === 'exact') {
                expect(ranges.length).toBeGreaterThan(0);
                expect(ranges.every((r) => r.kind === 'exact')).toBe(true);
            }
        });
    }
});

describe('offsets', () => {
    it('a fragment maps back onto exactly the characters it came from', () => {
        const text = 'נקודה \\((\\sqrt e, -2.25)\\) ולכן';
        const { form, starts, ends } = matchFormAt(text);
        const q = matchForm('\\sqrt{e}');
        const at = form.indexOf(q);
        expect(text.slice(starts[at], ends[at + q.length - 1])).toBe('\\sqrt e');
    });

    it('the bare fragment of a formula is placed inside that formula, on its own line', () => {
        const answer = 'שורה ראשונה \\(x = 1\\)\n\\(f(x) = 2x^2 + 1\\)';
        const [range] = markRangesFor(answer, '2x^2+1', 'exact', { math: true });
        expect(range.line).toBe(1);
        expect(range.kind).toBe('exact');
        expect(answer.split('\n')[1].slice(range.start, range.end)).toBe('2x^2 + 1');
        // the plain rule cannot place it exactly — that was the defect
        expect(markRangesFor(answer, '2x^2+1', 'exact').every((r) => r.kind === 'exact')).toBe(false);
    });

    it('a criterion union in math mode places every span', () => {
        const ranges = markRangesForAll(V.answer, [
            { quote: '2\\ln x - 1 = 0', kind: 'exact' },
            { quote: 'S = 4.8 · 3.6', kind: 'exact' },
        ], { math: true });
        expect(new Set(ranges.map((r) => r.line))).toEqual(new Set([2, 6]));
    });

    it('without the option the plain rule is untouched', () => {
        const code = 'for (int i = 0; i < n; i++) {}';
        expect(markRangesFor(code, 'i < n; i++')).toEqual(markRangesFor(code, 'i < n; i++', 'exact', {}));
    });
});
