import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect } from 'vitest';

import {
    applyCellEdit,
    applyTextRunEdit,
    createCellSession,
    rebaseSegments,
    segmentAnswerSpans,
    type SpanCell,
    type SpanSegment,
} from './answer-segments';
import { segmentAnswerText } from './detect-pipe-tables';

/**
 * The SEGMENT MODEL (native table editing, 2026-09-24) — zero mocks.
 *
 * An answer is a sequence of segments, each OWNING a span of the canonical
 * string. The string stays the only truth (TBL-1); every edit splices its own
 * span and nothing else (TBL-2); a cell edit can never change the table's shape
 * (TBL-4). These tests pin those three claims against every real table-bearing
 * answer we hold: the four live drafts the detector was built on, the P1 prompt's
 * own example, and the trace tables in the bagrut ground truth — read IN PLACE
 * (CRLF and all), never copied, so the GT and this model cannot drift.
 */

// ── fixtures ────────────────────────────────────────────────────────────────

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

/** Verbatim from P1_SYSTEM (prompt t1.4-tables) — the shape production now emits. */
const P1_EXAMPLE = [
    'א) 1)',
    '| x | i | arr[i] | ret |',
    '| 6 | 0 | 8 |  |',
    '|  | 1 | 5 |  |',
    '|  | 2 | 3 | T |',
    '',
    '(א, 2) הפעולה בודקת אם יש ערך במערך',
].join('\n');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GT_DIR = path.resolve(HERE, '../../../backend/tests/transcription_eval_suit/draft_benchmarks');

/** Every `=== Qn ===` section of every GT draft that carries a pipe row, bytes untouched. */
function gtTableAnswers(): Array<[string, string]> {
    const out: Array<[string, string]> = [];
    for (const f of readdirSync(GT_DIR).filter((n) => n.endsWith('.md'))) {
        const raw = readFileSync(path.join(GT_DIR, f), 'utf-8');
        const parts = raw.split(/^=== .* ===\r?\n/m);
        parts.forEach((body, i) => {
            if (/^\s*\|.*\|/m.test(body)) out.push([`${f}#${i}`, body]);
        });
    }
    return out;
}

const GT = gtTableAnswers();
const ALL: Array<[string, string]> = [
    ['REAL_A', REAL_A],
    ['REAL_C', REAL_C],
    ['REAL_D', REAL_D],
    ['P1_EXAMPLE', P1_EXAMPLE],
    ...GT,
];

// ── helpers ─────────────────────────────────────────────────────────────────

type TableSeg = Extract<SpanSegment, { kind: 'table' }>;
const tablesOf = (segs: SpanSegment[]) => segs.filter((s): s is TableSeg => s.kind === 'table');
const realCells = (t: TableSeg) =>
    t.rows.flatMap((row, r) => row.map((cell, c) => ({ cell, r, c }))).filter(({ cell }) => !cell.virtual) as
        Array<{ cell: Extract<SpanCell, { virtual: false }>; r: number; c: number }>;
const shape = (segs: SpanSegment[]) =>
    segs.map((s) => (s.kind === 'table' ? `table:${s.rows.length}x${s.rows[0].length}` : 'text'));

/** Seeded PRNG (mulberry32) — the property runs are reproducible. */
function prng(seed: number) {
    return () => {
        seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}
const ALNUM = 'abcdefghijklmnopqrstuvwxyz0123456789';
function randomToken(rand: () => number, digitsOnly: boolean): string {
    const alphabet = digitsOnly ? '0123456789' : ALNUM;
    const n = 1 + Math.floor(rand() * 5);
    return Array.from({ length: n }, () => alphabet[Math.floor(rand() * alphabet.length)]).join('');
}

// ── the model is a lens over the string ─────────────────────────────────────

describe('segmentAnswerSpans — derived from the string, never beside it (TBL-1)', () => {
    // The bagrut GT drafts are LOCAL fixtures (untracked in this public repo; on
    // the owner's machine: 3 documents, 6 trace tables). Where they exist, every
    // GT section that carries a pipe row must read as exactly one pipe table.
    it.skipIf(GT.length === 0)('reads every GT trace table in place, one per section', () => {
        for (const [, t] of GT) {
            expect(tablesOf(segmentAnswerSpans(t)).filter((s) => s.grid === 'pipe')).toHaveLength(1);
        }
    });

    it.each(ALL)('%s: every real cell is exactly the slice it claims', (_name, text) => {
        for (const t of tablesOf(segmentAnswerSpans(text))) {
            for (const { cell } of realCells(t)) {
                expect(text.slice(cell.start, cell.end)).toBe(cell.text);
            }
        }
    });

    it.each(ALL)('%s: agrees with the display detector cell for cell', (_name, text) => {
        // The rendered grid and the editable grid are ONE derivation: same
        // segment kinds, same dimensions, same cell texts, same header verdict.
        const spans = segmentAnswerSpans(text);
        const display = segmentAnswerText(text);
        expect(shape(spans)).toEqual(
            display.map((s) => (s.kind === 'table' ? `table:${s.rows.length}x${s.rows[0].length}` : 'text')),
        );
        const dt = display.filter((s) => s.kind === 'table') as Array<{ rows: string[][]; hasHeader: boolean }>;
        tablesOf(spans).forEach((t, i) => {
            expect(t.rows.map((row) => row.map((c) => c.text))).toEqual(dt[i].rows);
            expect(t.hasHeader).toBe(dt[i].hasHeader);
        });
    });

    it.each(ALL)('%s: segments tile the string in order, joined only by newlines', (_name, text) => {
        const segs = segmentAnswerSpans(text);
        let cursor = 0;
        for (const s of segs) {
            expect(s.start).toBeGreaterThanOrEqual(cursor);
            // Whatever lies between two segments is line structure, never content.
            expect(text.slice(cursor, s.start)).toMatch(/^\n*$/);
            cursor = s.end;
        }
        expect(text.slice(cursor)).toMatch(/^\n*$/);
    });

    it('a ragged row\'s END padding is VIRTUAL — it owns no bytes and says so', () => {
        const [t] = tablesOf(segmentAnswerSpans(REAL_A));
        expect(t.rows[1][4]).toEqual({ virtual: true, text: '' });
        expect(t.rows[5][4].virtual).toBe(false);
    });

    it('whitespace grids (detectTableRuns, unchanged) get token spans', () => {
        const [grid] = tablesOf(segmentAnswerSpans(REAL_C));
        expect(grid.grid).toBe('whitespace');
        const cells = realCells(grid);
        expect(cells).toHaveLength(16);
        for (const { cell } of cells) expect(REAL_C.slice(cell.start, cell.end)).toBe(cell.text);
    });
});

// ── TBL-2: an edit changes only its own span ────────────────────────────────

describe('applyCellEdit — MinimalDiff (TBL-2)', () => {
    it.each(ALL)('%s: re-typing every cell\'s own text is byte-identity', (_name, text) => {
        for (const t of tablesOf(segmentAnswerSpans(text))) {
            for (const { cell } of realCells(t)) {
                const r = applyCellEdit(text, cell, cell.text);
                expect(r).toEqual({ ok: true, text });
            }
        }
    });

    it.each(ALL)('%s: property — a structure-free edit touches only that cell\'s span', (name, text) => {
        const rand = prng(name.length * 7919);
        for (const t of tablesOf(segmentAnswerSpans(text))) {
            for (const { cell, r, c } of realCells(t)) {
                const next = randomToken(rand, t.grid === 'whitespace');
                const res = applyCellEdit(text, cell, next);
                if (!res.ok) {
                    // The only honest refusal for a pipe-free, newline-free,
                    // space-free token is a derived-shape change — never silent.
                    expect(res.reason).toBe('structure');
                    continue;
                }
                expect(res.text.slice(0, cell.start)).toBe(text.slice(0, cell.start));
                expect(res.text.slice(cell.start + next.length)).toBe(text.slice(cell.end));
                expect(res.text.slice(cell.start, cell.start + next.length)).toBe(next);
                const after = tablesOf(segmentAnswerSpans(res.text));
                const same = after.find((a) => a.start === t.start)!;
                expect(same.rows.length).toBe(t.rows.length);
                expect(same.rows[0].length).toBe(t.rows[0].length);
                expect(same.rows[r][c].text).toBe(next);
            }
        }
    });

    it('P1-shaped tables accept every structure-free edit (no refusals on the shape production emits)', () => {
        const rand = prng(42);
        for (const [, text] of [['P1_EXAMPLE', P1_EXAMPLE] as const, ...GT]) {
            for (const t of tablesOf(segmentAnswerSpans(text)).filter((s) => s.grid === 'pipe')) {
                for (const { cell } of realCells(t)) {
                    expect(applyCellEdit(text, cell, randomToken(rand, false)).ok).toBe(true);
                }
            }
        }
    });

    it('fills an EMPTY cell between its padding spaces: `|  |` → `| v |`, and back', () => {
        const [t] = tablesOf(segmentAnswerSpans(P1_EXAMPLE));
        const empty = t.rows[2][0];                            // '|  | 1 | 5 |  |' — x written once
        expect(empty).toMatchObject({ virtual: false, text: '' });
        const filled = applyCellEdit(P1_EXAMPLE, empty, '6');
        expect(filled.ok).toBe(true);
        if (!filled.ok) return;
        expect(filled.text).toContain('| 6 | 1 | 5 |  |');
        // Emptying it again restores the original bytes exactly.
        const session = createCellSession(empty);
        const typed = session.apply(P1_EXAMPLE, '6');
        expect(typed.ok && session.apply(typed.text, '')).toEqual({ ok: true, text: P1_EXAMPLE });
    });

    it('keeps CRLF, padding, and a `|---|` separator row byte-identical', () => {
        const crlf = '| x | i |\r\n|---|---|\r\n| 6 | 0 |\r\n';
        const [t] = tablesOf(segmentAnswerSpans(crlf));
        const res = applyCellEdit(crlf, t.rows[1][1], '9');
        expect(res).toEqual({ ok: true, text: '| x | i |\r\n|---|---|\r\n| 6 | 9 |\r\n' });
    });
});

// ── the session: a focused cell owns its span while she types ───────────────

describe('createCellSession — the caret\'s span, keystroke by keystroke', () => {
    it('types a multi-word value one key at a time without eating the space', () => {
        const [t] = tablesOf(segmentAnswerSpans(P1_EXAMPLE));
        const session = createCellSession(t.rows[1][2]);        // '8'
        let text = P1_EXAMPLE;
        for (const v of ['8', '8 ', '8 o', '8 or', '8 or 9']) {
            const r = session.apply(text, v);
            expect(r.ok).toBe(true);
            if (r.ok) text = r.text;
        }
        expect(text).toContain('| 6 | 0 | 8 or 9 |  |');
        // Nothing else moved.
        expect(text.replace('8 or 9', '8')).toBe(P1_EXAMPLE);
    });

    it('typing back to the original value restores the original bytes', () => {
        const [t] = tablesOf(segmentAnswerSpans(P1_EXAMPLE));
        const session = createCellSession(t.rows[0][2]);        // 'arr[i]'
        let text = P1_EXAMPLE;
        for (const v of ['arr[', 'arr[j', 'arr[j]', 'arr[', 'arr[i', 'arr[i]']) {
            const r = session.apply(text, v);
            if (r.ok) text = r.text;
        }
        expect(text).toBe(P1_EXAMPLE);
    });
});

// ── TBL-4: a cell edit can never change the table's shape (R5 edge cases) ────

describe('applyCellEdit — StructurePreserving (TBL-4)', () => {
    const [p1] = tablesOf(segmentAnswerSpans(P1_EXAMPLE));
    const bodyCell = p1.rows[1][1];                                // '0'

    it('refuses a typed `|` — the detector has no escape convention (`\\|` splits too)', () => {
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, 'a | b')).toEqual({ ok: false, reason: 'pipe' });
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, 'a || b')).toEqual({ ok: false, reason: 'pipe' });
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, 'a \\| b')).toEqual({ ok: false, reason: 'pipe' });
    });

    it('refuses a newline — Enter never breaks a row', () => {
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, '0\n1')).toEqual({ ok: false, reason: 'newline' });
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, '0\r1')).toEqual({ ok: false, reason: 'newline' });
    });

    it('refuses a code token that would dissolve the whole table (`;` `{` `}`)', () => {
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, 'x=1;')).toEqual({ ok: false, reason: 'structure' });
        expect(applyCellEdit(P1_EXAMPLE, bodyCell, '{1}')).toEqual({ ok: false, reason: 'structure' });
    });

    it('refuses content long enough to tip the detector\'s short-cell bar', () => {
        // 3 of 4 cells short (0.75) clears the 0.7 bar; a second long cell (0.5) does not.
        const two = '| a | a rather long header |\n| 1 | 2 |';
        const [t] = tablesOf(segmentAnswerSpans(two));
        const long = 'a considerably longer cell value';
        expect(applyCellEdit(two, t.rows[1][0], long)).toEqual({ ok: false, reason: 'structure' });
    });

    it('refuses writing into a VIRTUAL (end-padded) cell — it owns no bytes', () => {
        const [t] = tablesOf(segmentAnswerSpans(REAL_A));
        expect(applyCellEdit(REAL_A, t.rows[1][4], 'T')).toEqual({ ok: false, reason: 'virtual' });
    });

    it('whitespace grid: a space or an empty token would change the token count — refused', () => {
        const [grid] = tablesOf(segmentAnswerSpans(REAL_C));
        const cell = grid.rows[1][3];                              // '15'
        expect(applyCellEdit(REAL_C, cell, '1 5')).toEqual({ ok: false, reason: 'structure' });
        expect(applyCellEdit(REAL_C, cell, '')).toEqual({ ok: false, reason: 'structure' });
        expect(applyCellEdit(REAL_C, cell, '13')).toMatchObject({ ok: true });
    });

    it('a header without an alignment row, and rows with no edge pipes, edit in place', () => {
        const bare = 'x | i\n6 | 0';
        const [t] = tablesOf(segmentAnswerSpans(bare));
        expect(applyCellEdit(bare, t.rows[0][1], 'j')).toEqual({ ok: true, text: 'x | j\n6 | 0' });
    });

    it('Hebrew cells edit as bytes, like any other', () => {
        const heb = '| ערך | מוחזר |\n| 6 | אמת |';
        const [t] = tablesOf(segmentAnswerSpans(heb));
        expect(applyCellEdit(heb, t.rows[1][1], 'שקר')).toEqual({ ok: true, text: '| ערך | מוחזר |\n| 6 | שקר |' });
    });
});

// ── text runs ───────────────────────────────────────────────────────────────

describe('applyTextRunEdit — prose outside the table', () => {
    it('splices only the run\'s body; the table beside it is byte-identical', () => {
        const segs = segmentAnswerSpans(P1_EXAMPLE);
        const prose = segs[segs.length - 1];
        expect(prose.kind).toBe('text');
        if (prose.kind !== 'text' || !prose.body) throw new Error('expected a prose body');
        const next = applyTextRunEdit(P1_EXAMPLE, prose.body, '(א, 2) הפעולה בודקת אם יש ערך אחר במערך');
        expect(next).toBe(P1_EXAMPLE.replace('ערך במערך', 'ערך אחר במערך'));
    });

    it('a run\'s body excludes the blank lines that separate it from a table', () => {
        const segs = segmentAnswerSpans(P1_EXAMPLE);
        const prose = segs[segs.length - 1];
        if (prose.kind !== 'text' || !prose.body) throw new Error('expected a prose body');
        expect(P1_EXAMPLE.slice(prose.body.start, prose.body.end)).toBe('(א, 2) הפעולה בודקת אם יש ערך במערך');
    });

    it('code adjacent to a table with no blank line stays its own run', () => {
        const text = 'int x = 5;\n| x | i |\n| 6 | 0 |';
        const segs = segmentAnswerSpans(text);
        expect(shape(segs)).toEqual(['text', 'table:2x2']);
        const code = segs[0];
        if (code.kind !== 'text' || !code.body) throw new Error('expected a code body');
        expect(applyTextRunEdit(text, code.body, 'int x = 6;')).toBe('int x = 6;\n| x | i |\n| 6 | 0 |');
    });
});

// ── OD-5: the layout holds still while she types ────────────────────────────

describe('rebaseSegments — a frozen layout stays true to the string across edits', () => {
    it('after cell, empty-cell and prose edits, every span still slices to what it shows', () => {
        let text = P1_EXAMPLE;
        let layout = segmentAnswerSpans(text);
        const step = (span: { start: number; end: number }, next: string) => {
            const nextText = text.slice(0, span.start) + next + text.slice(span.end);
            layout = rebaseSegments(layout, nextText, { start: span.start, oldEnd: span.end, newEnd: span.start + next.length });
            text = nextText;
        };
        const cellAt = (r: number, c: number) => {
            const cell = tablesOf(layout)[0].rows[r][c];
            if (cell.virtual) throw new Error('virtual');
            return cell;
        };
        step(cellAt(0, 2), 'arr[j]');          // longer
        step(cellAt(2, 0), '6');               // an EMPTY cell (zero-width span)
        step(cellAt(1, 2), '8 ');              // a trailing space the detector would trim
        const prose = layout[layout.length - 1];
        if (prose.kind !== 'text' || !prose.body) throw new Error('prose');
        step(prose.body, ['שורה חדשה', 'ועוד אחת'].join('\n'));

        const last = layout[layout.length - 1];
        if (last.kind !== 'text' || !last.body) throw new Error('prose');
        expect(text.slice(last.body.start, last.body.end)).toBe(['שורה חדשה', 'ועוד אחת'].join('\n'));
        for (const seg of layout) {
            if (seg.kind === 'text') continue;
            for (const row of seg.rows) for (const cell of row) {
                if (!cell.virtual) expect(text.slice(cell.start, cell.end)).toBe(cell.text);
            }
        }
        expect(cellAt(1, 2).text).toBe('8 ');  // the session's bytes, not the trimmed reading
        expect(text).toBe([
            'א) 1)',
            '| x | i | arr[j] | ret |',
            '| 6 | 0 | 8  |  |',
            '| 6 | 1 | 5 |  |',
            '|  | 2 | 3 | T |',
            '',
            'שורה חדשה',
            'ועוד אחת',
        ].join('\n'));
        // And a fresh derivation agrees with the carried one wherever the shape held.
        const fresh = tablesOf(segmentAnswerSpans(text))[0];
        expect(fresh.rows.map((r) => r.map((c) => c.text.trim())))
            .toEqual(tablesOf(layout)[0].rows.map((r) => r.map((c) => c.text.trim())));
    });
});
