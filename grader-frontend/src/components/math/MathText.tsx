'use client';

/**
 * One line of a student's answer with its mathematics typeset (MATH_RENDERING_PLAN §4).
 *
 * Prose is text; each `\( … \)` span is KaTeX inside `<bdi dir="ltr">`.
 *
 * ⚠ THE ISOLATION IS NOT DECORATION. Measured in Chromium on the student's own lines
 * (docs/math-rendering/render-test): KaTeX inheriting the page's `dir="rtl"` drew
 * `(1/e, 0)` as `(0, 1/e)` — a different point — flipped the `cases` brace, and scrambled
 * `S₁₀ = 1.875 S₅`. Inside an LTR isolate every line rendered correctly. The Playwright
 * bounding-box test `math-rtl-coordinate-order` is the standing guard; run it against any
 * change to this markup.
 *
 * A span KaTeX cannot parse is shown AS TRANSCRIBED, delimiters and all, with a marker —
 * never hidden, never half-rendered (plan §4: "a span that fails to render shows raw with a
 * marker"). Before KaTeX has loaded, every span shows that way, unmarked.
 *
 * A mark that touches part of a span lights the whole span (`math-pieces.ts`).
 */
import type { ReactNode } from 'react';

import { MATH_UNRENDERED_TITLE } from '@/copy/math';
import { renderMathBody, useKatex } from '@/lib/katex';
import type { LineRange, MarkKind } from '@/utils/evidence-highlight';
import { mathPieces } from '@/utils/math-pieces';

export interface MathTextProps {
    /** ONE line of the answer (a math span never crosses a line — convention 3). */
    text: string;
    /** Marked ranges inside this line, as `markRangesForAll` produces them. */
    marks?: readonly Pick<LineRange, 'start' | 'end' | 'kind'>[];
    /** How a marked piece is painted; the caller owns the highlight look. */
    renderMark?: (children: ReactNode, kind: MarkKind, key: string) => ReactNode;
    /** A span was clicked (the transcription editor opens it). Index among this line's spans. */
    onSpanClick?: (spanIndex: number) => void;
    /** Rendered spans become focusable buttons when `onSpanClick` is given. */
    spanLabel?: string;
    /** Draw this node IN PLACE of span `index` (the open span editor). */
    replaceSpan?: { index: number; node: ReactNode };
}

export function MathText({ text, marks = [], renderMark, onSpanClick, spanLabel, replaceSpan }: MathTextProps) {
    const pieces = mathPieces(text, marks);
    const katex = useKatex(pieces.some((p) => p.kind === 'math'));
    let spanIndex = -1;
    return (
        <>
            {pieces.map((piece, i) => {
                const key = `p${i}`;
                let node: ReactNode;
                if (piece.kind === 'text') {
                    node = <span key={key}>{piece.text}</span>;
                } else {
                    spanIndex += 1;
                    const index = spanIndex;
                    if (replaceSpan && replaceSpan.index === index) {
                        return <bdi key={key} dir="ltr" data-math-span={index}>{replaceSpan.node}</bdi>;
                    }
                    const rendered = katex ? renderMathBody(katex, piece.body) : null;
                    const failed = rendered !== null && !rendered.ok;
                    const inner = rendered && rendered.ok
                        ? <span data-math-rendered="" dangerouslySetInnerHTML={{ __html: rendered.html }} />
                        : (
                            <span
                                data-math-raw={failed ? 'error' : 'pending'}
                                title={failed ? MATH_UNRENDERED_TITLE : undefined}
                                className={[
                                    'font-mono text-[0.92em]',
                                    failed ? 'underline decoration-amber-500 decoration-dotted underline-offset-4' : '',
                                ].join(' ')}
                            >
                                {piece.raw}
                            </span>
                        );
                    node = (
                        <bdi key={key} dir="ltr" data-math-span={index} className="[unicode-bidi:isolate]">
                            {onSpanClick ? (
                                <button
                                    type="button"
                                    aria-label={spanLabel}
                                    data-math-edit={index}
                                    onClick={(e) => { e.stopPropagation(); onSpanClick(index); }}
                                    className="rounded-sm px-0.5 hover:bg-primary-50 focus:outline-none focus:ring-2 focus:ring-primary-400"
                                >
                                    {inner}
                                </button>
                            ) : inner}
                        </bdi>
                    );
                }
                return piece.mark && renderMark ? renderMark(node, piece.mark, `m${i}`) : node;
            })}
        </>
    );
}
