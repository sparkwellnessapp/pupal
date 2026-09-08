'use client';

import { useEffect, useRef } from 'react';

import { answerLines, answerRenderPlan } from '@/utils/answer-mode';
import { splitLineByQuote, type Highlight } from '@/utils/evidence-highlight';

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
 * The active mark is scrolled into view, but only when the highlight came from
 * the KEYBOARD or a pin. Scrolling on hover would yank the page out from under
 * the mouse that caused it.
 */

export interface AnswerBlockProps {
    answer: string;
    highlight: Highlight;
    /** Suppress auto-scroll: the highlight is following the mouse. */
    transient?: boolean;
    /**
     * The rubric's subject key (multisubject Phase 3a). Decides the render plan:
     * english → prose LTR, mathematics → prose RTL, computer_science / absent →
     * today's heuristic. An essay with a digit in it is still an essay.
     */
    subject?: string | null;
}

export function AnswerBlock({ answer, highlight, transient = false, subject }: AnswerBlockProps) {
    const markRef = useRef<HTMLElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (transient || !markRef.current || !containerRef.current) return;
        const mark = markRef.current.getBoundingClientRect();
        const box = containerRef.current.getBoundingClientRect();
        if (mark.top < box.top || mark.bottom > box.bottom) {
            markRef.current.scrollIntoView({ block: 'center' });
        }
    }, [highlight.quote, transient]);

    const plan = answerRenderPlan(answer, subject);
    const mode = plan.mode;
    const lines = answerLines(answer, mode);
    let markAssigned = false;

    const renderSegments = (text: string) =>
        splitLineByQuote(text, highlight.quote).map((segment, i) => {
            if (!segment.marked) return <span key={i}>{segment.text}</span>;
            const isFirst = !markAssigned;
            markAssigned = true;
            return (
                <mark
                    key={i}
                    ref={isFirst ? markRef : undefined}
                    data-highlight={highlight.kind}
                    data-pinned={highlight.pinned ? 'true' : 'false'}
                    className={
                        highlight.kind === 'fuzzy'
                            // Fuzzy is drawn as an underline, not a fill: the
                            // span is approximate, and a solid block would
                            // claim a precision Vivi did not have.
                            ? 'bg-transparent border-b-2 border-dashed border-grade-amber-dot text-inherit'
                            : [
                                'rounded-mark bg-primary-100 text-inherit',
                                'shadow-[0_0_0_2px_theme(colors.primary.100)]',
                                highlight.pinned
                                    ? 'shadow-[0_0_0_2px_theme(colors.primary.100),0_2px_0_0_theme(colors.primary.600)]'
                                    : '',
                            ].join(' ')
                    }
                >
                    {segment.text}
                </mark>
            );
        });

    if (mode === 'prose') {
        return (
            <div
                ref={containerRef}
                dir={plan.dir}
                data-answer-mode="prose"
                data-answer-dir={plan.dir}
                className={`mb-3.5 max-h-answer-max overflow-auto rounded-grade-ctl border
                    border-grade-line-2 bg-grade-bar px-4 py-3 text-gr-prose ${
                    plan.dir === 'ltr' ? 'text-left' : 'text-right'}`}
            >
                {lines.map((line) => (
                    <div key={line.number}>{renderSegments(line.text) as React.ReactNode}</div>
                ))}
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            dir="ltr"
            data-answer-mode="code"
            className="mb-3.5 max-h-answer-max overflow-auto rounded-grade-ctl border
                border-grade-line-2 bg-grade-bar py-3 pl-2 pr-3.5 text-left
                font-mono text-gr-answer"
        >
            {lines.map((line) => (
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
                        {renderSegments(line.text) as React.ReactNode}
                    </span>
                </div>
            ))}
        </div>
    );
}
