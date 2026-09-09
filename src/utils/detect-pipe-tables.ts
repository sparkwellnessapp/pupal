/**
 * detect-pipe-tables — the transcription surface's table detector.
 *
 * WHY A SECOND DETECTOR EXISTS (read before "consolidating" it with the rubric
 * mirror's): the two live on opposite sides of the pipeline and speak different
 * formats.
 *
 *   - The DOCX rubric path emits EXPLICIT markers — `[TABLE N: RxC rtl]` plus
 *     fully-delimited `| cell | cell |` rows (parser_render.py). That is what
 *     `markdown-parser.ts::parseMarkdownText` consumes.
 *   - The TRANSCRIPTION path emits NO markers at all: P1's prompt states "Page
 *     text is PLAIN TEXT only: no markdown". The pipe grid a handwritten trace
 *     table arrives as is the VLM's own emergent convention — bare rows, no
 *     marker, no separator, and RAGGED (a header of 5 cells above body rows of
 *     4 is the norm, not the exception).
 *
 * Neither existing detector fires on it, verified against real drafts:
 *   parseMarkdownText → one text segment (it needs the `[TABLE]` marker line).
 *   detectTableRuns   → one prose segment (it splits on WHITESPACE, so
 *                       `6 | 0 | 1 | F` is 7 tokens of which 3 are numeric —
 *                       0.43, under its 0.60 gate).
 * And `groupTextBlocks` classifies the block as CODE (the `|` chars alone clear
 * its symbol-density bar), so the naive reuse renders a trace table as an
 * LTR <pre>.
 *
 * BIAS TO PRECISION, exactly as `detect-table-runs.ts` states it: when unsure,
 * do NOT tableize. The fallback is the monospace text she already has — honest.
 * A false positive mangles a real student answer — not honest.
 *
 * FAITHFUL CAPTURE (§2). Ragged rows are padded at the END and never anywhere
 * else: where the missing cell BELONGS is unknowable from the text, and guessing
 * it is the silent relocation the product exists to refuse. Nothing here mutates
 * the answer — it is called at render, the textarea keeps the verbatim text, and
 * the accept payload never sees this module.
 */

import { detectTableRuns } from './detect-table-runs';

export type AnswerSegment =
    | { kind: 'text'; text: string }
    | { kind: 'table'; rows: string[][]; hasHeader: boolean };

const NUMERIC_ISH = /^-?\d+(\.\d+)?$/;
/** A separator row (`|---|---|`) — a marker, never data. Mirrors markdown-parser. */
const SEPARATOR_RE = /^\s*\|?[-\s|]+\|?\s*$/;
/**
 * Tokens that PROVE a line is code rather than a table row. `||` is the one that
 * matters most: `if (a || b)` splits into three "cells", and two such lines in a
 * row would otherwise become a table made of the student's code.
 */
const CODE_TOKENS = ['||', ';', '{', '}'];
/** Trace-table cells are short. Prose that happens to contain a pipe is not. */
const SHORT_CELL_MAX = 12;
const SHORT_CELL_RATIO = 0.7;

function isSeparator(line: string): boolean {
    return line.includes('|') && line.includes('-') && SEPARATOR_RE.test(line);
}

function isCandidate(line: string): boolean {
    if (!line.includes('|')) return false;
    if (CODE_TOKENS.some((t) => line.includes(t))) return false;
    return true;
}

/**
 * Split one row into cells.
 *
 * EDGE PIPES ARE MEANINGFUL and are stripped only when the WHOLE run is in
 * markdown form (every row bounded on both sides). The real drafts settle this:
 * one table carries `| 8 | T | 8 | 0` (leading pipe = a genuinely empty first
 * cell) beside `| | | 0 |` (both edges = empty first AND last), inside the same
 * table as `76 | 2 | f | 76 | 7` (no edges at all). Splitting raw makes all three
 * exactly 5 cells — a perfect rectangle. Stripping per-line collapses the
 * scaffold row to 3 and shears the grid.
 */
function splitCells(line: string, stripEdges: boolean): string[] {
    let s = line.trim();
    if (stripEdges) {
        if (s.startsWith('|')) s = s.slice(1);
        if (s.endsWith('|')) s = s.slice(0, -1);
    }
    return s.split('|').map((c) => c.trim());
}

function shortCellRatio(rows: string[][]): number {
    let total = 0;
    let short = 0;
    for (const row of rows) {
        for (const cell of row) {
            total += 1;
            if (cell.length <= SHORT_CELL_MAX) short += 1;
        }
    }
    return total === 0 ? 0 : short / total;
}

/**
 * A first row is a HEADER when it labels rather than measures: at least one
 * non-empty cell and not a single numeric one among them. A `|---|` separator,
 * if the model ever emits one, settles it outright.
 */
function inferHasHeader(rows: string[][], sawSeparator: boolean): boolean {
    if (rows.length < 2) return false;
    if (sawSeparator) return true;
    const first = rows[0];
    if (!first.some((c) => c !== '')) return false;
    return first.every((c) => !NUMERIC_ISH.test(c));
}

/** Build a table segment from a run's source lines, or null if it fails the bar. */
function buildTable(runLines: string[]): { kind: 'table'; rows: string[][]; hasHeader: boolean } | null {
    const sawSeparator = runLines.some(isSeparator);
    const dataLines = runLines.filter((l) => !isSeparator(l));
    if (dataLines.length < 2) return null;

    const stripEdges = dataLines.every((l) => {
        const t = l.trim();
        return t.startsWith('|') && t.endsWith('|');
    });

    const raw = dataLines.map((l) => splitCells(l, stripEdges));
    if (raw.some((cells) => cells.length < 2)) return null;

    const cols = Math.max(...raw.map((c) => c.length));
    if (cols < 2) return null;
    // FC: pad at the END only. Never guess which column a short row is missing.
    const rows = raw.map((cells) => [...cells, ...Array(cols - cells.length).fill('')]);

    if (shortCellRatio(rows) < SHORT_CELL_RATIO) return null;

    return { kind: 'table', rows, hasHeader: inferHasHeader(rows, sawSeparator) };
}

/**
 * Segment `text` into ordered text and pipe-table runs. Order-preserving: the
 * source lines of the segments, in order, reproduce the input. Pure.
 */
export function detectPipeTables(text: string): AnswerSegment[] {
    if (!text) return [];
    const lines = text.split('\n');
    const segments: AnswerSegment[] = [];
    let buf: string[] = [];

    const flushText = () => {
        if (buf.length > 0) {
            segments.push({ kind: 'text', text: buf.join('\n') });
            buf = [];
        }
    };

    let i = 0;
    while (i < lines.length) {
        if (isCandidate(lines[i])) {
            let j = i;
            while (j < lines.length && isCandidate(lines[j])) j += 1;
            const runLines = lines.slice(i, j);
            const table = runLines.length >= 2 ? buildTable(runLines) : null;
            if (table) {
                flushText();
                segments.push(table);
            } else {
                // Not a table — the run stays verbatim text.
                buf.push(...runLines);
            }
            i = j;
            continue;
        }
        buf.push(lines[i]);
        i += 1;
    }

    flushText();
    return segments;
}

/**
 * The full answer-text segmentation: pipe tables first, then `detectTableRuns`
 * over what is left, so the WHITESPACE grids the same drafts carry (an array's
 * index row above its value row — `0 1 2 3 4 5 6 7` / `8 5 4 15 3 40 9 2`) are
 * recognized by the module that already owns that shape, unchanged.
 */
export function segmentAnswerText(text: string): AnswerSegment[] {
    return detectPipeTables(text).flatMap((seg) => {
        if (seg.kind === 'table') return [seg];
        return detectTableRuns(seg.text).map((s): AnswerSegment =>
            s.kind === 'table'
                ? { kind: 'table', rows: s.rows, hasHeader: s.hasHeader }
                : { kind: 'text', text: s.text },
        );
    });
}

/** Does this answer contain anything worth rendering as a grid? */
export function hasRenderableTable(text: string): boolean {
    return segmentAnswerText(text).some((s) => s.kind === 'table');
}
