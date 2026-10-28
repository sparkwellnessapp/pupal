/**
 * Where the mathematics is in an answer string (MATH_RENDERING_PLAN §4).
 *
 * The client MIRROR of `backend/app/services/math_notation/spans.py`, pinned to the same
 * vectors (`backend/tests/fixtures/math_spans_vectors.json`, read in place by
 * `math-spans.test.ts`). Under a subject with math notation, P1 writes every piece of
 * mathematics between `\(` and `\)`; everything else — Hebrew words, units, markers —
 * is outside.
 *
 * THE ANSWER STRING STAYS THE ONLY TRUTH. A segment is a pair of offsets into it, never a
 * copy, so the renderer and the span editor read and splice the same bytes.
 *
 *   `\(` opens and the next `\)` closes; spans do not nest.
 *   A stray `\)` and an unclosed `\(` stay TEXT — a span that cannot be delimited is
 *   never guessed into one, and the renderer shows it raw.
 *   `\\` is an escaped backslash, never the start of a delimiter.
 */

export type MathSegment = {
    kind: 'text' | 'math';
    /** Offsets into the answer; a math segment's cover its delimiters. End exclusive. */
    start: number;
    end: number;
    /** What is between the delimiters (equal to start/end for text). */
    bodyStart: number;
    bodyEnd: number;
};

export interface MathSplit {
    segments: MathSegment[];
    unclosedAt: number[];
    strayCloseAt: number[];
}

export function splitMath(text: string): MathSplit {
    const segments: MathSegment[] = [];
    const unclosedAt: number[] = [];
    const strayCloseAt: number[] = [];
    let cursor = 0;
    let openAt = -1;
    let i = 0;
    while (i < text.length - 1) {
        if (text[i] !== '\\') {
            i += 1;
            continue;
        }
        const next = text[i + 1];
        if (next === '(') {
            if (openAt !== -1) unclosedAt.push(openAt);
            openAt = i;
        } else if (next === ')') {
            if (openAt === -1) {
                strayCloseAt.push(i);
            } else {
                if (openAt > cursor) {
                    segments.push({ kind: 'text', start: cursor, end: openAt, bodyStart: cursor, bodyEnd: openAt });
                }
                segments.push({ kind: 'math', start: openAt, end: i + 2, bodyStart: openAt + 2, bodyEnd: i });
                cursor = i + 2;
                openAt = -1;
            }
        }
        i += 2;   // `\\`, `\(`, `\)` and any other `\x` are two characters
    }
    if (openAt !== -1) unclosedAt.push(openAt);
    if (cursor < text.length) {
        segments.push({ kind: 'text', start: cursor, end: text.length, bodyStart: cursor, bodyEnd: text.length });
    }
    return { segments, unclosedAt, strayCloseAt };
}

export function hasMath(text: string): boolean {
    return splitMath(text ?? '').segments.some((s) => s.kind === 'math');
}

/** Replace one span's body, keeping its delimiters and every other byte. */
export function spliceMathBody(text: string, segment: MathSegment, body: string): string {
    return text.slice(0, segment.bodyStart) + body + text.slice(segment.bodyEnd);
}
