'use client';

import { useMemo } from 'react';

import { answerLines, answerRenderPlan } from '@/utils/answer-mode';
import { markRangesForAll, segmentsForLine, type Highlight, type LineRange }
    from '@/utils/evidence-highlight';

/**
 * The student's answer, in one of two modes (R5) — a PURE render of
 * `(answer, highlight)`.
 *
 * prose  every line Hebrew-only → RTL, the UI face, right-aligned
 * code   anything else → a `dir="ltr"` island, Fira Code, numbered lines, and
 *        a Hebrew comment gets `dir="rtl"` on its text span ALONE, keeping the
 *        island's left alignment and its indentation (OD-F2, ruled left)
 *
 * ⚠ `unicode-bidi: plaintext` IS FALSIFIED. It takes paragraph direction from
 * the first strong character, so `// תכונות` goes RTL-base and the `//` jumps
 * to the RIGHT of the Hebrew — the exact defect it was proposed to fix. The
 * Playwright bounding-box test is the standing guard; do not reintroduce it
 * from first principles (CLAUDE.md §10).
 *
 * ── IT SCROLLS NOTHING ────────────────────────────────────────────────────
 * This block used to centre the first mark inside its own container whenever
 * the highlight changed and the change had not come from a hover. That was a
 * SECOND reveal, living beside `GradeReviewSurface.reveal`, deciding from state
 * what the other decides from intent — and two reveals cannot stay in agreement
 * (§0.4). The surface now owns it outright: it knows WHY the highlight changed,
 * it lands the span at the pane's upper third (OD-9), and it skips the scroll
 * when the span is already comfortably in view (M-2). Nothing here reads or
 * writes a scroll offset; this is a pure render of `(answer, highlight)`.
 */

export interface AnswerBlockProps {
    answer: string;
    /** Anchors this answer so the quote button can scroll to THIS one. */
    scopeId?: string;
    highlight: Highlight;
    /**
     * The rubric's subject key (multisubject Phase 3a). Decides the render plan:
     * english → prose LTR, mathematics → prose RTL, computer_science / absent →
     * today's heuristic. An essay with a digit in it is still an essay.
     */
    subject?: string | null;
}

export function AnswerBlock({ answer, highlight, subject, scopeId }: AnswerBlockProps) {
    // WHERE THE SPANS LIVE, decided ONCE over the whole answer. Per line it was
    // undecidable: a five-line quote is a substring of no single line.
    //
    // `spanKey` is a stable identity for what is lit, because `spans` is a fresh
    // array on every parent render — depending on it directly would re-run the
    // matcher, and re-fire the scroll effect, for no change at all.
    //
    // JSON, not a hand-rolled join: a quote can contain any delimiter a join
    // might pick, and two different span lists that serialise to one key would
    // silently skip a repaint. `JSON.stringify` is injective on this shape.
    const spanKey = JSON.stringify(highlight.spans);
    const ranges = useMemo(
        () => markRangesForAll(answer, highlight.spans),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [answer, spanKey],
    );
    const rangesByLine = useMemo(() => {
        const out = new Map<number, LineRange[]>();
        for (const range of ranges) {
            const bucket = out.get(range.line);
            if (bucket) bucket.push(range);
            else out.set(range.line, [range]);
        }
        return out;
    }, [ranges]);

    const plan = answerRenderPlan(answer, subject);
    const mode = plan.mode;
    const lines = answerLines(answer, mode);

    const renderSegments = (text: string, lineIndex: number) =>
        segmentsForLine(text, rangesByLine.get(lineIndex) ?? []).map((segment, i) => {
            if (!segment.marked) return <span key={i}>{segment.text}</span>;
            return (
                <mark
                    key={i}
                    // The kind is recorded PER SEGMENT as data (a criterion's
                    // union can mix exact and fuzzy spans), but since the owner
                    // ruling of 2026-09-11 it is not PAINTED differently: one
                    // teal fill for every placed span. The dashed amber
                    // underline that used to mark a fuzzy span is gone.
                    data-highlight={segment.kind}
                    data-pinned={highlight.pinned ? 'true' : 'false'}
                    className={[
                        'rounded-mark bg-primary-100 text-inherit',
                        'shadow-[0_0_0_2px_theme(colors.primary.100)]',
                        highlight.pinned
                            ? 'shadow-[0_0_0_2px_theme(colors.primary.100),0_2px_0_0_theme(colors.primary.600)]'
                            : '',
                    ].join(' ')}
                >
                    {segment.text}
                </mark>
            );
        });

    if (mode === 'prose') {
        return (
            <div
                dir={plan.dir}
                data-answer-for={scopeId}
                data-answer-mode="prose"
                data-answer-dir={plan.dir}
                className={`gr-card__pane-body scroll-mt-scope rounded-grade-ctl border
                    border-grade-line-2 bg-grade-bar px-4 py-3 text-gr-prose ${
                    plan.dir === 'ltr' ? 'text-left' : 'text-right'}`}
            >
                {lines.map((line, index) => (
                    <div key={line.number}>
                        {renderSegments(line.text, index) as React.ReactNode}
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div
            dir="ltr"
            data-answer-for={scopeId}
            data-answer-mode="code"
            className="gr-card__pane-body scroll-mt-scope rounded-grade-ctl border
                border-grade-line-2 bg-grade-bar py-3 pl-2 pr-3.5 text-left
                font-mono text-gr-answer"
        >
            {lines.map((line, index) => (
                <div key={line.number} className="flex gap-3">
                    <span
                        aria-hidden="true"
                        className="w-gutter flex-none select-none pt-0.5 text-right
                            text-gr-sm text-grade-pencil-2"
                    >
                        {line.number}
                    </span>
                    <span
                        dir={line.dir}
                        data-line-dir={line.dir}
                        className={
                            line.dir === 'rtl'
                                // A Hebrew comment reads RTL but stays in the
                                // island's own font-flow and alignment.
                                ? 'flex-1 whitespace-pre-wrap font-sans text-gr-rtl'
                                : 'flex-1 whitespace-pre'
                        }
                    >
                        {renderSegments(line.text, index) as React.ReactNode}
                    </span>
                </div>
            ))}
        </div>
    );
}
