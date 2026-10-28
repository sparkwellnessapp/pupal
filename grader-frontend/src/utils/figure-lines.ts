/**
 * Figure lines ↔ figure readings — the client MIRROR of `backend/app/services/figures.py`
 * (`match_figures`), so the review surface shows each reading under the line that names
 * its drawing, exactly as FIG-1 will freeze it. Pinned to the same cases by
 * `figure-lines.test.ts` / `tests/services/test_figures.py`.
 *
 * Lines in text order; for each `[איור N:` the first unused figure numbered N, in page
 * order. A line with no reading is UNREAD (shown as such); a figure with no line is an
 * orphan (not shown — the server drops it at approval, with the line she deleted).
 */
import type { Figure } from '@/types/transcription';

export const FIGURE_LINE = /\[איור\s*(\d+)\s*:/;

export interface FigureLineMatch {
    pairs: { line: number; figure: Figure }[];
    unread: number[];
    orphans: Figure[];
}

export function figureLines(text: string): { line: number; n: number }[] {
    const out: { line: number; n: number }[] = [];
    (text ?? '').split('\n').forEach((ln, i) => {
        const m = FIGURE_LINE.exec(ln);
        if (m) out.push({ line: i, n: Number(m[1]) });
    });
    return out;
}

export function matchFigures(text: string, figures: readonly Figure[]): FigureLineMatch {
    const pool = [...figures].sort((a, b) => a.page_number - b.page_number || a.figure_no - b.figure_no);
    const used = pool.map(() => false);
    const pairs: FigureLineMatch['pairs'] = [];
    const unread: number[] = [];
    for (const { line, n } of figureLines(text)) {
        const j = pool.findIndex((f, k) => !used[k] && f.figure_no === n);
        if (j === -1) {
            unread.push(line);
        } else {
            used[j] = true;
            pairs.push({ line, figure: pool[j] });
        }
    }
    return { pairs, unread, orphans: pool.filter((_, k) => !used[k]) };
}
