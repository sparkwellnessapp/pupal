/**
 * THE CROSS-STACK TABLE CONTRACT (2026-08-29).
 *
 * Three parties have to agree on one shape for a hand-drawn trace table, and
 * nothing but this file makes them agree:
 *
 *   1. P1 emits it            — `two_phase/prompts.py::P1_SYSTEM`, prompt version
 *                               `t1.4-tables`, which carries the worked example
 *                               reproduced verbatim below.
 *   2. The GT is authored in it — `TRANSCRIPTION_GT_CONVENTIONS.md` §5.2a.
 *   3. This surface renders it  — `detect-pipe-tables.ts` → `TranscribedAnswerView`.
 *
 * The pin matters because the scorer compares FORMAT as well as content: two
 * faithful readings of one table written in different shapes measured 0.9648
 * against a 0.98 gate. If the prompt's example and this detector ever drift, the
 * benchmark fails for reasons that have nothing to do with perception — so the
 * example is duplicated here ON PURPOSE, and this test is what catches the drift.
 * (Same idea as the segmentation-check.ts ↔ segmentation_check.py fixture pin.)
 *
 * Keep P1_EXAMPLE byte-identical to the block in P1_SYSTEM.
 */

import { describe, it, expect } from 'vitest';
import { segmentAnswerText } from './detect-pipe-tables';

/** Verbatim from P1_SYSTEM (prompt t1.4-tables). Do not "tidy" the spacing. */
const P1_EXAMPLE = [
    '| x | i | arr[i] | ret |',
    '| 6 | 0 | 8 |  |',
    '|  | 1 | 5 |  |',
    '|  | 2 | 3 | T |',
].join('\n');

function onlyTable(text: string) {
    const segs = segmentAnswerText(text);
    const tables = segs.filter((s) => s.kind === 'table');
    expect(tables).toHaveLength(1);
    return tables[0] as { kind: 'table'; rows: string[][]; hasHeader: boolean };
}

describe('P1 table contract — the shape the prompt pins is the shape this renders', () => {
    it('renders the prompt example as an exact 4x4 grid with a header', () => {
        const t = onlyTable(P1_EXAMPLE);
        expect(t.hasHeader).toBe(true);
        expect(t.rows).toEqual([
            ['x', 'i', 'arr[i]', 'ret'],
            ['6', '0', '8', ''],
            ['', '1', '5', ''],
            ['', '2', '3', 'T'],
        ]);
    });

    it('every value sits under its own header — the anti-shift property', () => {
        const { rows } = onlyTable(P1_EXAMPLE);
        const header = rows[0];
        const col = (name: string, r: number) => rows[r][header.indexOf(name)];
        // The sparse FIRST column is the dangerous case: `x` is written once, so
        // rows 2-3 would be short at the front if the blank were skipped.
        expect(col('x', 2)).toBe('');
        expect(col('i', 2)).toBe('1');
        expect(col('arr[i]', 2)).toBe('5');
        expect(col('ret', 3)).toBe('T');
    });

    it('SKIPPING the blank cell instead is what the prompt forbids, and why', () => {
        // The same ink with row 2's leading blank omitted — what P1 emitted before
        // t1.4 pinned the shape.
        const skipped = [
            '| x | i | arr[i] | ret |',
            '| 6 | 0 | 8 |  |',
            '| 1 | 5 |  |',
        ].join('\n');
        const t = onlyTable(skipped);
        const header = t.rows[0];
        // `1` is an `i` value, but it is rendered under `x`. Silently.
        expect(t.rows[2][header.indexOf('x')]).toBe('1');
        expect(t.rows[2][header.indexOf('x')]).not.toBe('');
    });

    it('rejects the shapes the prompt forbids: a caption and a separator row', () => {
        const withCaption = `[TABLE 1: 4x4 ltr]\n${P1_EXAMPLE}`;
        // The caption survives as a stray text segment above the grid.
        const segs = segmentAnswerText(withCaption);
        expect(segs.some((s) => s.kind === 'text' && s.text.includes('[TABLE'))).toBe(true);

        // A separator row is dropped by the detector, so it buys nothing here — but
        // it costs fabricated `--` operators on the scorer, which is why it is out.
        const withSeparator = [
            '| x | i | arr[i] | ret |',
            '|---|---|---|---|',
            '| 6 | 0 | 8 |  |',
            '|  | 1 | 5 |  |',
        ].join('\n');
        expect(onlyTable(withSeparator).rows).toHaveLength(3);
    });

    it('unpadded pipes are refused outright — `||` reads as code, not an empty cell', () => {
        const tight = ['|x|i|arr[i]|ret|', '|6|0|8||', '||1|5||'].join('\n');
        expect(segmentAnswerText(tight).some((s) => s.kind === 'table')).toBe(false);
    });

    it('does not invent a table out of code containing a pipe', () => {
        const code = 'if (a || b)\n{\n    x = 1;\n}';
        expect(segmentAnswerText(code).some((s) => s.kind === 'table')).toBe(false);
    });
});
