import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { detectTableRuns, type Segment } from './detect-table-runs';

/**
 * PR-5 Sprint 2 §4 — the mini-table parser. The centerpiece assertion is the
 * PRECISION BIAS: real fixture prose (interleaved example arrays, embedded code)
 * must NOT tableize; only clean multi-row grids do. A false positive mangles her
 * words; a false negative degrades to honest preformatted lines.
 */

const tables = (segs: Segment[]) => segs.filter((s): s is Extract<Segment, { kind: 'table' }> => s.kind === 'table');
const proseText = (segs: Segment[]) => segs.filter((s) => s.kind === 'prose').map((s) => (s as { text: string }).text).join('\n');

describe('detectTableRuns — POSITIVE (clean grids tableize)', () => {
    it('a pure numeric grid becomes one headerless table', () => {
        const segs = detectTableRuns('1 2 3\n4 5 6\n7 8 9');
        expect(tables(segs)).toHaveLength(1);
        expect(tables(segs)[0].rows).toEqual([['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9']]);
        expect(tables(segs)[0].hasHeader).toBe(false);
    });

    it('a textual first row of equal width is a header', () => {
        const segs = detectTableRuns('קלט פלט\n1 2\n3 4');
        expect(tables(segs)).toHaveLength(1);
        expect(tables(segs)[0].hasHeader).toBe(true);
        expect(tables(segs)[0].rows[0]).toEqual(['קלט', 'פלט']);
    });

    it('handles negative numbers as numeric tokens', () => {
        const segs = detectTableRuns('7 -3 4\n-7 -4 3\n1 -1 2');
        expect(tables(segs)).toHaveLength(1);
        expect(tables(segs)[0].rows).toHaveLength(3);
    });

    it('isolates a table between prose blocks, order preserved', () => {
        const segs = detectTableRuns('הקדמה כאן\n\n1 2 3\n4 5 6\n\nסיום המשימה');
        expect(tables(segs)).toHaveLength(1);
        expect(segs[0].kind).toBe('prose');
        expect(segs[segs.length - 1].kind).toBe('prose');
        // Reconstruction: source lines survive across segments.
        expect(proseText(segs)).toContain('הקדמה כאן');
        expect(proseText(segs)).toContain('סיום המשימה');
    });
});

describe('detectTableRuns — PRECISION BIAS (ambiguous input stays prose)', () => {
    it('a numbered list is NOT a table ("1." is not numeric-ish)', () => {
        const segs = detectTableRuns('1. ראשון\n2. שני\n3. שלישי');
        expect(tables(segs)).toHaveLength(0);
    });

    it('plain two-line prose is NOT a table (0% numeric)', () => {
        expect(tables(detectTableRuns('שלום עולם\nמה שלומך היום'))).toHaveLength(0);
    });

    it('ragged short code lines are NOT a table (unequal token counts)', () => {
        expect(tables(detectTableRuns('int x = 5;\nreturn x;'))).toHaveLength(0);
    });

    it('a header + a single numeric row is rejected (< 60% numeric)', () => {
        // 2 textual + 2 numeric tokens = 50% < 0.6 → precision bias declines.
        expect(tables(detectTableRuns('קלט פלט\n1 2'))).toHaveLength(0);
    });

    it('a lone numeric row (no run) stays prose', () => {
        expect(tables(detectTableRuns('2 9 40 3 15 4 5 8'))).toHaveLength(0);
    });

    it('empty / whitespace input yields no tables and does not throw', () => {
        expect(detectTableRuns('')).toEqual([]);
        expect(tables(detectTableRuns('   \n  \n'))).toHaveLength(0);
    });
});

// ---------------------------------------------------------------------------
// REAL fixture texts (spec §4: "the golden benchmarks are the test corpus").
// ---------------------------------------------------------------------------

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');

function collectTexts(node: unknown, out: string[] = []): string[] {
    if (Array.isArray(node)) {
        for (const item of node) collectTexts(item, out);
    } else if (node && typeof node === 'object') {
        const obj = node as Record<string, unknown>;
        for (const key of ['question_text', 'text']) {
            if (typeof obj[key] === 'string' && obj[key]) out.push(obj[key] as string);
        }
        for (const v of Object.values(obj)) {
            if (v && typeof v === 'object') collectTexts(v, out);
        }
    }
    return out;
}

describe('detectTableRuns — real bagrut fixture (precision on live data)', () => {
    const bagrut = JSON.parse(readFileSync(path.join(BENCHMARKS, 'bagrut_899371.json'), 'utf-8'));
    const texts = collectTexts(bagrut);

    it('the mirror-array example text keeps its example rows as PROSE, not a table', () => {
        const q2 = texts.find((t) => t.includes('מערך מראה הוא מערך'));
        expect(q2, 'q2 mirror-array text present in fixture').toBeTruthy();
        const segs = detectTableRuns(q2!);
        // Single example arrays interleaved with explanatory prose → never tableized.
        expect(tables(segs)).toHaveLength(0);
        expect(proseText(segs)).toContain('7 -3 4 -7 -4 3');
    });

    it('embedded #C code is never mistaken for a table', () => {
        const codeText = texts.find((t) => t.includes('public static int What'));
        expect(codeText, 'q1 What-code text present in fixture').toBeTruthy();
        expect(tables(detectTableRuns(codeText!))).toHaveLength(0);
    });

    it('never throws on any fixture text (robustness across the corpus)', () => {
        for (const name of ['bagrut_899371', 'csharp_plane_combine', 'employee_course_select1', 'foundations_cs', 'hobby_tvshow']) {
            const fx = JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8'));
            for (const t of collectTexts(fx)) {
                expect(() => detectTableRuns(t)).not.toThrow();
            }
        }
    });
});
