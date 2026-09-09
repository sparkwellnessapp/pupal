import { describe, it, expect } from 'vitest';

import { detectPipeTables, segmentAnswerText, hasRenderableTable, type AnswerSegment } from './detect-pipe-tables';

/**
 * The fixtures below are REAL production answer texts (four transcribed trace
 * tables from live drafts, 2026-08-23). Synthetic fixtures would have hidden the
 * two facts that shaped the detector: the grids are RAGGED (a 5-cell header over
 * 4-cell body rows), and edge pipes carry MEANING (a leading `|` is an empty
 * first cell, not markdown furniture).
 */

// ── the four real drafts ────────────────────────────────────────────────────

/** q1.א — 5-cell header, 4-cell body, a 5-cell final row, then Hebrew prose. */
const REAL_A = [
    'if:',
    'returned | x | i | arr[i] | (arr[i]≠1 && arr[i]≠x && x%arr[i]==0)',
    '6 | 0 | 1 | F',
    '6 | 1 | 5 | F',
    '6 | 2 | 4 | F',
    '6 | 3 | 15 | F',
    'true | 6 | 4 | 3 | T',
    '',
    '(א, 2) לבדוק אם יש ערך במערך ש-שונה מ-1',
    'מתחלק בו x-שהתקבל כפעולה ו x-שונה מ',
    'בלי שארית.',
].join('\n');

/** q1.ב — a long header cell (`check(arr, arr[i])`) and a lone `22` after the grid. */
const REAL_B = [
    '1 (ב)',
    'if:',
    'arr[i] | sum | i | check(arr, arr[i]) | returned',
    '1 | 1 | 0 | T',
    '5 | 13 | 1 | T',
    '4 | 17 | 2 | T',
    '15 | 17 | 3 | F',
    '3 | 20 | 4 | T',
    '40 | 20 | 5 | F',
    '9 | 20 | 6 | F',
    '2 | 22 | 7 | T',
    '22',
    '',
    '(ב 2) הפעולה מחזירה את סכום הערכים במערך שהם מתחלקים',
    'במספרים אחרים במערך.',
].join('\n');

/** A whitespace array grid ABOVE a pipe grid, plus a wrapped header word (`ערך`). */
const REAL_C = [
    '0 1 2 3 4 5 6 7',
    '8 5 4 15 3 40 9 2',
    '',
    'ערך',
    'מוחזר | x | arr[i] | if | i',
    '6 | 8 | f | 0',
    '| 5 | f | 1',
    '| 4 | f | 2',
    '| 15 | f | 3',
    'True | 3 | T | 4',
    '',
    '2. מטרת הפעולה היא למצוא',
    '1 מספר שהוא קטן ושהוא מתחלק בו והוא לא.',
].join('\n');

/** Mixed edge pipes inside ONE table — the case that settled the split rule. */
const REAL_D = [
    'ערך',
    'מוחזר | arr[i] | if | sum | i',
    '| | | 0 |',
    '| 8 | T | 8 | 0',
    '| 5 | f | 8 | 1',
    '| 4 | T | 12 | 2',
    '| 15 | T | 27 | 3',
    '| 3 | f | 27 | 4',
    '| 40 | T | 67 | 5',
    '| 9 | T | 76 | 6',
    '76 | 2 | f | 76 | 7',
].join('\n');

const tables = (segs: AnswerSegment[]) => segs.filter((s): s is Extract<AnswerSegment, { kind: 'table' }> => s.kind === 'table');

describe('detectPipeTables — the four real drafts', () => {
    it('REAL_A: one 5-column table, header detected, prose kept out of it', () => {
        const segs = detectPipeTables(REAL_A);
        const t = tables(segs);
        expect(t).toHaveLength(1);
        expect(t[0].hasHeader).toBe(true);
        expect(t[0].rows).toHaveLength(6);
        expect(t[0].rows.every((r) => r.length === 5)).toBe(true);
        expect(t[0].rows[0][0]).toBe('returned');
        // FC: the 4-cell body row is padded at the END, never re-aligned.
        expect(t[0].rows[1]).toEqual(['6', '0', '1', 'F', '']);
        expect(t[0].rows[5]).toEqual(['true', '6', '4', '3', 'T']);
        // The Hebrew explanation stays text.
        const text = segs.filter((s) => s.kind === 'text').map((s) => (s as { text: string }).text).join('\n');
        expect(text).toContain('לבדוק אם יש ערך במערך');
        expect(text).toContain('if:');
    });

    it('REAL_B: tolerates a long header cell; the trailing `22` is not swallowed', () => {
        const t = tables(detectPipeTables(REAL_B));
        expect(t).toHaveLength(1);
        expect(t[0].rows).toHaveLength(9);
        expect(t[0].rows[0]).toEqual(['arr[i]', 'sum', 'i', 'check(arr, arr[i])', 'returned']);
        expect(t[0].rows[1]).toEqual(['1', '1', '0', 'T', '']);
        const text = detectPipeTables(REAL_B).filter((s) => s.kind === 'text').map((s) => (s as { text: string }).text).join('\n');
        expect(text).toContain('22');
    });

    it('REAL_C: a leading pipe is an EMPTY FIRST CELL, not furniture', () => {
        const t = tables(detectPipeTables(REAL_C));
        expect(t).toHaveLength(1);
        expect(t[0].rows[0]).toEqual(['מוחזר', 'x', 'arr[i]', 'if', 'i']);
        expect(t[0].rows[1]).toEqual(['6', '8', 'f', '0', '']);
        expect(t[0].rows[2]).toEqual(['', '5', 'f', '1', '']);
        expect(t[0].rows[5]).toEqual(['True', '3', 'T', '4', '']);
    });

    it('REAL_D: mixed edge pipes in one table still yield a perfect rectangle', () => {
        const t = tables(detectPipeTables(REAL_D));
        expect(t).toHaveLength(1);
        expect(t[0].rows).toHaveLength(10);
        expect(t[0].rows.every((r) => r.length === 5)).toBe(true);
        expect(t[0].rows[1]).toEqual(['', '', '', '0', '']);   // the empty scaffold row
        expect(t[0].rows[2]).toEqual(['', '8', 'T', '8', '0']);
        expect(t[0].rows[9]).toEqual(['76', '2', 'f', '76', '7']);
    });
});

describe('detectPipeTables — precision bias (never mangle a real answer)', () => {
    const notATable = (text: string) => {
        expect(tables(detectPipeTables(text))).toHaveLength(0);
        expect(detectPipeTables(text).map((s) => (s as { text: string }).text).join('\n')).toBe(text);
    };

    it('refuses consecutive `||` code lines', () => {
        notATable(['if (a || b)', 'if (c || d)'].join('\n'));
    });

    it('refuses lines carrying statement terminators or braces', () => {
        notATable(['x = a | b;', 'y = c | d;'].join('\n'));
        notATable(['while (p | q) {', 'do (r | s) {'].join('\n'));
    });

    it('refuses a lone pipe line (a run needs two)', () => {
        notATable('returned | x | i');
    });

    it('refuses prose that merely contains a pipe (cells too long)', () => {
        notATable([
            'הפעולה מחזירה את סכום הערכים | וגם בודקת את התנאי הראשון בלולאה',
            'הפעולה השנייה מחזירה false | כאשר המערך ריק לחלוטין ואין בו ערכים',
        ].join('\n'));
    });

    it('treats an all-numeric first row as data, not a header', () => {
        const t = tables(detectPipeTables(['1 | 2 | 3', '4 | 5 | 6'].join('\n')));
        expect(t[0].hasHeader).toBe(false);
    });

    it('honours a markdown `|---|` separator when one appears', () => {
        const t = tables(detectPipeTables(['| קלט | פלט |', '|---|---|', '| 5 | 8 |'].join('\n')));
        expect(t).toHaveLength(1);
        expect(t[0].hasHeader).toBe(true);
        // Whole run is markdown-bounded ⇒ edges ARE furniture here.
        expect(t[0].rows).toEqual([['קלט', 'פלט'], ['5', '8']]);
    });
});

describe('detectPipeTables — order preservation', () => {
    it('reproduces the input from the segments, in order', () => {
        for (const src of [REAL_A, REAL_B, REAL_C, REAL_D]) {
            const rebuilt = detectPipeTables(src)
                .map((s) => (s.kind === 'text' ? s.text.split('\n').length : s.rows.length))
                .reduce((a, b) => a + b, 0);
            // Every source line lands in exactly one segment (no table here has a
            // separator line, so table rows === source lines).
            expect(rebuilt).toBe(src.split('\n').length);
        }
    });
});

describe('segmentAnswerText — composes with the whitespace-grid detector', () => {
    it('REAL_C yields TWO grids: the array (whitespace) and the trace (pipes)', () => {
        const t = tables(segmentAnswerText(REAL_C));
        expect(t).toHaveLength(2);
        // detectTableRuns owns this one, unchanged.
        expect(t[0].rows).toEqual([
            ['0', '1', '2', '3', '4', '5', '6', '7'],
            ['8', '5', '4', '15', '3', '40', '9', '2'],
        ]);
        expect(t[0].hasHeader).toBe(false);
        expect(t[1].rows[0]).toEqual(['מוחזר', 'x', 'arr[i]', 'if', 'i']);
    });

    it('leaves Hebrew prose alone', () => {
        const segs = segmentAnswerText(REAL_C);
        const text = segs.filter((s) => s.kind === 'text').map((s) => (s as { text: string }).text).join('\n');
        expect(text).toContain('מטרת הפעולה היא למצוא');
        expect(text).toContain('ערך');
    });

    it('hasRenderableTable agrees with the segmentation', () => {
        expect(hasRenderableTable(REAL_A)).toBe(true);
        expect(hasRenderableTable(REAL_D)).toBe(true);
        expect(hasRenderableTable('public int foo()\nreturn 1')).toBe(false);
        expect(hasRenderableTable('')).toBe(false);
    });
});
