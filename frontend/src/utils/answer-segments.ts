/**
 * answer-segments — editing an answer IN PLACE through its derived segments
 * (native table editing, 2026-09-24).
 *
 * An answer is a sequence of segments — prose runs and tables — each OWNING a
 * byte span of the canonical string (`segmentAnswerSpans`, detect-pipe-tables.ts).
 * The string is the only truth; the grid is a lens over it:
 *
 *   TBL-1 SourceIsTruth     — nothing here holds a second table model. Every
 *                              operation takes the string and returns the string.
 *   TBL-2 MinimalDiff       — an edit splices exactly its own span. Padding,
 *                              pipes, separator rows, CRLF, other cells: untouched.
 *                              No parse→reserialize, ever.
 *   TBL-4 StructurePreserving — a cell edit that would change what the detector
 *                              derives (segment kinds, any table's rows×cols, or
 *                              the edited cell's own reading) is REFUSED, never
 *                              repaired. The guard is the detector itself, run on
 *                              the candidate string — so it has no rules of its
 *                              own to drift from the rendering.
 *
 * A typed `|` is refused outright: the detector splits on every pipe and has no
 * escape convention (`\|` splits too — R5), so there is no way to write one
 * INSIDE a cell that reads back as the same cell.
 */

import { segmentAnswerSpans, type Span, type SpanCell, type SpanSegment } from './detect-pipe-tables';

export { segmentAnswerSpans };
export type { Span, SpanCell, SpanSegment };

export type CellEditRefusal = 'pipe' | 'newline' | 'virtual' | 'structure';
export type CellEditResult = { ok: true; text: string } | { ok: false; reason: CellEditRefusal };

/** What the detector derives, reduced to what a cell edit must never change. */
function shapeOf(segs: SpanSegment[]): string {
    return segs
        .map((s) => (s.kind === 'table' ? `${s.grid}:${s.rows.length}x${s.rows[0]?.length ?? 0}` : 'text'))
        .join(',');
}

/**
 * Does the candidate string still read the edited region as ONE cell holding
 * `next` (trimmed, as the detector reads every cell)? The region contains no
 * pipe and no newline, so it cannot straddle two pipe cells; a zero-width
 * (emptied) cell may sit one byte off the region, hence the ±1 reach.
 */
function readsBack(segs: SpanSegment[], start: number, next: string): boolean {
    const end = start + next.length;
    const want = next.trim();
    for (const s of segs) {
        if (s.kind !== 'table' || s.start > end || s.end < start) continue;
        for (const row of s.rows) {
            for (const cell of row) {
                if (cell.virtual) continue;
                if (cell.start <= end + 1 && cell.end >= start - 1 && cell.text === want) return true;
            }
        }
    }
    return false;
}

function editSpan(text: string, span: Span, next: string): CellEditResult {
    if (next.includes('|')) return { ok: false, reason: 'pipe' };
    if (/[\r\n]/.test(next)) return { ok: false, reason: 'newline' };
    const candidate = text.slice(0, span.start) + next + text.slice(span.end);
    if (candidate === text) return { ok: true, text };
    const after = segmentAnswerSpans(candidate);
    if (shapeOf(after) !== shapeOf(segmentAnswerSpans(text))) return { ok: false, reason: 'structure' };
    if (!readsBack(after, span.start, next)) return { ok: false, reason: 'structure' };
    return { ok: true, text: candidate };
}

/**
 * A focused cell's typing session. It owns the span it last WROTE — not the
 * span a fresh derivation would read — because the detector trims: after
 * `8` → `8 ` a re-derived cell is still `8`, and the next key must replace the
 * three bytes she has typed, not two of them.
 */
export function createCellSession(cell: SpanCell) {
    let span: Span | null = cell.virtual ? null : { start: cell.start, end: cell.end };
    return {
        apply(text: string, next: string): CellEditResult {
            if (!span) return { ok: false, reason: 'virtual' };
            const res = editSpan(text, span, next);
            if (res.ok) span = { start: span.start, end: span.start + next.length };
            return res;
        },
    };
}

/** One cell edit against the string. Refused edits change nothing. */
export function applyCellEdit(text: string, cell: SpanCell, next: string): CellEditResult {
    return createCellSession(cell).apply(text, next);
}

/** A prose edit: splice the run's body. Prose may hold anything, newlines included. */
export function applyTextRunEdit(text: string, body: Span, next: string): string {
    return text.slice(0, body.start) + next + text.slice(body.end);
}

/**
 * Carry a derived layout across one splice without re-deriving it (OD-5: the
 * layout holds still while she types, so a keystroke can never re-segment the
 * answer under the caret). `edit` replaced [start, oldEnd) with bytes ending at
 * `newEnd`. A START moves only when it lies past the edit; an END moves when it
 * lies at or past the edit's old end — so the edited span, its containing
 * segment, and everything after it land exactly on the new string.
 */
export function rebaseSegments(
    segs: SpanSegment[],
    text: string,
    edit: { start: number; oldEnd: number; newEnd: number },
): SpanSegment[] {
    const delta = edit.newEnd - edit.oldEnd;
    const s = (p: number) => (p > edit.start && p >= edit.oldEnd ? p + delta : p);
    const e = (p: number) => (p >= edit.oldEnd ? p + delta : p);
    const span = (x: Span): Span => ({ start: s(x.start), end: e(x.end) });
    return segs.map((seg): SpanSegment => {
        if (seg.kind === 'text') {
            return { ...seg, ...span(seg), body: seg.body && span(seg.body) };
        }
        return {
            ...seg,
            ...span(seg),
            rows: seg.rows.map((row) => row.map((cell): SpanCell => {
                if (cell.virtual) return cell;
                const moved = span(cell);
                return { virtual: false, ...moved, text: text.slice(moved.start, moved.end) };
            })),
        };
    });
}
