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
 * the answer — it is called at render, and the accept payload never sees it.
 *
 * SPANS (native table editing, 2026-09-24). The derivation is `segmentAnswerSpans`:
 * every segment, every cell and every prose body carries the BYTE SPAN of the
 * answer string it was read from, so an edit can splice exactly that span and
 * nothing else (TBL-2). `segmentAnswerText` / `detectPipeTables` are PROJECTIONS
 * of it — the rendered grid and the editable grid are one derivation, never two
 * that must agree. An end-padding cell is VIRTUAL: it owns no bytes, and says so.
 * The whitespace grids come from `detectTableRuns`, UNCHANGED (the rubric mirror
 * shares it); their line ranges are recovered from its own output shape, which its
 * header guarantees ("concatenating the segments' source lines reproduces the input").
 */

import { detectTableRuns } from './detect-table-runs';

export type AnswerSegment =
    | { kind: 'text'; text: string }
    | { kind: 'table'; rows: string[][]; hasHeader: boolean };

export interface Span { start: number; end: number }

/** One cell of a derived table. A real cell's span is its TRIMMED content; an
 *  empty real cell is a zero-width span at its insertion point. */
export type SpanCell =
    | { virtual: false; text: string; start: number; end: number }
    | { virtual: true; text: '' };

export type SpanSegment =
    /** `body` = the run without its blank edge lines (layout, not content); null when blank. */
    | { kind: 'text'; start: number; end: number; body: Span | null }
    | { kind: 'table'; start: number; end: number; rows: SpanCell[][]; hasHeader: boolean; grid: 'pipe' | 'whitespace' };

type TableSpanSegment = Extract<SpanSegment, { kind: 'table' }>;

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

// ── line index ──────────────────────────────────────────────────────────────

interface Lines { lines: string[]; starts: number[] }

function indexLines(text: string): Lines {
    const lines = text.split('\n');
    const starts: number[] = [];
    let offset = 0;
    for (const line of lines) {
        starts.push(offset);
        offset += line.length + 1;
    }
    return { lines, starts };
}

const lineEnd = (ix: Lines, i: number) => ix.starts[i] + ix.lines[i].length;

/** One piece between two pipes → its trimmed content span, or its insertion point. */
function cellSpan(line: string, offset: number, from: number, to: number): SpanCell {
    const piece = line.slice(from, to);
    const text = piece.trim();
    if (text === '') {
        // `|  |` → between the padding spaces, so a filled cell reads `| v |`.
        const at = offset + from + Math.min(1, to - from);
        return { virtual: false, text: '', start: at, end: at };
    }
    const lead = piece.length - piece.trimStart().length;
    const start = offset + from + lead;
    return { virtual: false, text, start, end: start + text.length };
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
function splitCells(line: string, offset: number, stripEdges: boolean): SpanCell[] {
    let a = line.length - line.trimStart().length;
    let b = Math.max(a, line.trimEnd().length);
    if (stripEdges) {
        if (line[a] === '|' && a < b) a += 1;
        if (b > a && line[b - 1] === '|') b -= 1;
    }
    const cells: SpanCell[] = [];
    let from = a;
    for (let q = a; q <= b; q += 1) {
        if (q === b || line[q] === '|') {
            cells.push(cellSpan(line, offset, from, q));
            from = q + 1;
        }
    }
    return cells;
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

/** Build a table from the source lines [from, to), or null if it fails the bar. */
function buildTable(ix: Lines, from: number, to: number): TableSpanSegment | null {
    const idx = Array.from({ length: to - from }, (_, k) => from + k);
    const sawSeparator = idx.some((i) => isSeparator(ix.lines[i]));
    const data = idx.filter((i) => !isSeparator(ix.lines[i]));
    if (data.length < 2) return null;

    const stripEdges = data.every((i) => {
        const t = ix.lines[i].trim();
        return t.startsWith('|') && t.endsWith('|');
    });

    const raw = data.map((i) => splitCells(ix.lines[i], ix.starts[i], stripEdges));
    if (raw.some((cells) => cells.length < 2)) return null;

    const cols = Math.max(...raw.map((c) => c.length));
    if (cols < 2) return null;
    // FC: pad at the END only. Never guess which column a short row is missing —
    // and the padding is VIRTUAL: it owns no bytes of the answer.
    const rows: SpanCell[][] = raw.map((cells) => [
        ...cells,
        ...Array.from({ length: cols - cells.length }, (): SpanCell => ({ virtual: true, text: '' })),
    ]);
    const texts = rows.map((r) => r.map((c) => c.text));

    if (shortCellRatio(texts) < SHORT_CELL_RATIO) return null;

    return {
        kind: 'table',
        start: ix.starts[from],
        end: lineEnd(ix, to - 1),
        rows,
        hasHeader: inferHasHeader(texts, sawSeparator),
        grid: 'pipe',
    };
}

type PipeRun = { kind: 'text'; from: number; to: number } | TableSpanSegment;

/** The pipe pass over line indices. Order-preserving: the runs tile the lines. */
function pipeRuns(ix: Lines): PipeRun[] {
    const runs: PipeRun[] = [];
    let bufFrom = -1;
    const flushText = (to: number) => {
        if (bufFrom >= 0) {
            runs.push({ kind: 'text', from: bufFrom, to });
            bufFrom = -1;
        }
    };

    let i = 0;
    while (i < ix.lines.length) {
        if (isCandidate(ix.lines[i])) {
            let j = i;
            while (j < ix.lines.length && isCandidate(ix.lines[j])) j += 1;
            const table = j - i >= 2 ? buildTable(ix, i, j) : null;
            if (table) {
                flushText(i);
                runs.push(table);
            } else if (bufFrom < 0) {
                // Not a table — the run stays verbatim text.
                bufFrom = i;
            }
            i = j;
            continue;
        }
        if (bufFrom < 0) bufFrom = i;
        i += 1;
    }

    flushText(ix.lines.length);
    return runs;
}

/** A prose run's body: its lines minus the blank ones at either edge. */
function proseBody(ix: Lines, from: number, to: number): Span | null {
    let f = from;
    while (f < to && ix.lines[f].trim() === '') f += 1;
    if (f === to) return null;
    let l = to - 1;
    while (ix.lines[l].trim() === '') l -= 1;
    // A CRLF line's `\r` is line structure, not her text.
    const end = lineEnd(ix, l) - (ix.lines[l].endsWith('\r') ? 1 : 0);
    return { start: ix.starts[f], end };
}

/** The whitespace pass (detectTableRuns, unchanged) over one pipe-text run. */
function whitespaceRuns(text: string, ix: Lines, from: number, to: number): SpanSegment[] {
    const segText = text.slice(ix.starts[from], lineEnd(ix, to - 1));
    const out: SpanSegment[] = [];
    let li = from;
    for (const s of detectTableRuns(segText)) {
        if (s.kind === 'prose') {
            const n = s.text.split('\n').length;
            out.push({ kind: 'text', start: ix.starts[li], end: lineEnd(ix, li + n - 1), body: proseBody(ix, li, li + n) });
            li += n;
            continue;
        }
        const rows: SpanCell[][] = s.rows.map((_, k) => {
            const line = ix.lines[li + k];
            return Array.from(line.matchAll(/\S+/g), (m): SpanCell => ({
                virtual: false,
                text: m[0],
                start: ix.starts[li + k] + (m.index ?? 0),
                end: ix.starts[li + k] + (m.index ?? 0) + m[0].length,
            }));
        });
        out.push({
            kind: 'table',
            start: ix.starts[li],
            end: lineEnd(ix, li + s.rows.length - 1),
            rows,
            hasHeader: s.hasHeader,
            grid: 'whitespace',
        });
        li += s.rows.length;
    }
    return out;
}

/**
 * THE derivation: the answer as ordered text and table segments, each carrying
 * the byte spans it was read from. Pure; safe to call in render.
 */
export function segmentAnswerSpans(text: string): SpanSegment[] {
    if (!text) return [];
    const ix = indexLines(text);
    return pipeRuns(ix).flatMap((run) =>
        run.kind === 'table' ? [run] : whitespaceRuns(text, ix, run.from, run.to),
    );
}

const projectTable = (t: TableSpanSegment): AnswerSegment => ({
    kind: 'table',
    rows: t.rows.map((r) => r.map((c) => c.text)),
    hasHeader: t.hasHeader,
});

/**
 * Segment `text` into ordered text and pipe-table runs. Order-preserving: the
 * source lines of the segments, in order, reproduce the input. Pure.
 */
export function detectPipeTables(text: string): AnswerSegment[] {
    if (!text) return [];
    const ix = indexLines(text);
    return pipeRuns(ix).map((run) =>
        run.kind === 'table'
            ? projectTable(run)
            : { kind: 'text', text: text.slice(ix.starts[run.from], lineEnd(ix, run.to - 1)) },
    );
}

/**
 * The full answer-text segmentation: pipe tables first, then `detectTableRuns`
 * over what is left, so the WHITESPACE grids the same drafts carry (an array's
 * index row above its value row — `0 1 2 3 4 5 6 7` / `8 5 4 15 3 40 9 2`) are
 * recognized by the module that already owns that shape, unchanged. A projection
 * of `segmentAnswerSpans`.
 */
export function segmentAnswerText(text: string): AnswerSegment[] {
    return segmentAnswerSpans(text).map((s): AnswerSegment =>
        s.kind === 'table' ? projectTable(s) : { kind: 'text', text: text.slice(s.start, s.end) },
    );
}

/** Does this answer contain anything worth rendering as a grid? */
export function hasRenderableTable(text: string): boolean {
    return segmentAnswerSpans(text).some((s) => s.kind === 'table');
}
