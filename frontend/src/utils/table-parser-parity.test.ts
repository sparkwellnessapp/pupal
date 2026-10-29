/**
 * TABLE PARSER PARITY — the review UI's detector and the eval suite's table
 * diagnostic must read every table identically.
 *
 * The eval suite scores transcribed tables (MISSION_transcription_accuracy.md
 * §4.3) against the convention this surface renders (OD-T1). The backend has no
 * parser of its own, so `backend/tests/transcription_eval_suit/diag_tables.py`
 * MIRRORS `detectPipeTables` line for line. Mirrors drift; this pins them.
 *
 * `table_parser_parity.json` holds every table-bearing text in the real corpus
 * plus the detector's documented edge cases. `expected` is THIS module's output
 * (run once with WRITE_TABLE_PARITY=1), and the Python side asserts the same
 * file — the segmentation-check.ts ↔ segmentation_check.py precedent. A change
 * to the detector turns one of the two red, which is the point.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { detectPipeTables } from './detect-pipe-tables';

const FIXTURE = resolve(__dirname, '../../../backend/tests/transcription_eval_suit/table_parser_parity.json');

type Case = { id: string; text: string; expected?: Array<{ rows: string[][]; hasHeader: boolean }> };

function tablesOf(text: string) {
    return detectPipeTables(text)
        .filter((s): s is Extract<typeof s, { kind: 'table' }> => s.kind === 'table')
        .map((t) => ({ rows: t.rows, hasHeader: t.hasHeader }));
}

describe('table parser parity (review UI ↔ eval diagnostic)', () => {
    const data = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as { note: string; cases: Case[] };

    if (process.env.WRITE_TABLE_PARITY === '1') {
        it('writes the expected output from the live detector', () => {
            for (const c of data.cases) c.expected = tablesOf(c.text);
            writeFileSync(FIXTURE, JSON.stringify(data, null, 1) + '\n', 'utf-8');
        });
        return;
    }

    it('every case carries an expected output', () => {
        expect(data.cases.every((c) => Array.isArray(c.expected))).toBe(true);
    });

    for (const c of data.cases) {
        it(`reads ${c.id} as recorded`, () => {
            expect(tablesOf(c.text)).toEqual(c.expected);
        });
    }
});
