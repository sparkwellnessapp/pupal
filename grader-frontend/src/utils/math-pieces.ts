/**
 * One line of a math answer, cut into what `MathText` draws (MATH_RENDERING_PLAN §4).
 *
 * Pure: `(line, marks) → pieces`. Text pieces are split at mark boundaries exactly as
 * `evidence-highlight.ts::segmentsForLine` splits a plain line. A math span is ONE piece
 * and is never split: a rendered formula cannot be half-lit, so a mark that touches any
 * part of a span lights the WHOLE span (plan §4, "Evidence highlighting"). Where an exact
 * and a fuzzy mark both touch it, exact wins — the same precedence the plain painter uses.
 */
import type { LineRange, MarkKind } from './evidence-highlight';
import { splitMath } from './math-spans';

export type MathPiece =
    | { kind: 'text'; text: string; mark: MarkKind | null }
    | {
        kind: 'math';
        /** What KaTeX renders. */
        body: string;
        /** The span exactly as written, delimiters included — what is shown if it cannot render. */
        raw: string;
        mark: MarkKind | null;
    };

type Mark = Pick<LineRange, 'start' | 'end' | 'kind'>;

function strongest(marks: readonly Mark[]): MarkKind | null {
    if (marks.length === 0) return null;
    return marks.some((m) => m.kind === 'exact') ? 'exact' : 'fuzzy';
}

export function mathPieces(line: string, marks: readonly Mark[] = []): MathPiece[] {
    const pieces: MathPiece[] = [];
    for (const seg of splitMath(line).segments) {
        if (seg.kind === 'math') {
            const touching = marks.filter((m) => m.start < seg.end && m.end > seg.start);
            pieces.push({
                kind: 'math',
                body: line.slice(seg.bodyStart, seg.bodyEnd),
                raw: line.slice(seg.start, seg.end),
                mark: strongest(touching),
            });
            continue;
        }
        // text: cut at every mark boundary inside it
        const cuts = new Set<number>([seg.start, seg.end]);
        for (const m of marks) {
            if (m.start > seg.start && m.start < seg.end) cuts.add(m.start);
            if (m.end > seg.start && m.end < seg.end) cuts.add(m.end);
        }
        const points = [...cuts].sort((a, b) => a - b);
        for (let i = 0; i + 1 < points.length; i += 1) {
            const [a, b] = [points[i], points[i + 1]];
            const covering = marks.filter((m) => m.start <= a && m.end >= b);
            const last = pieces[pieces.length - 1];
            const mark = strongest(covering);
            if (last && last.kind === 'text' && last.mark === mark) {
                last.text += line.slice(a, b);            // merge neighbours with one paint
            } else {
                pieces.push({ kind: 'text', text: line.slice(a, b), mark });
            }
        }
    }
    return pieces;
}
