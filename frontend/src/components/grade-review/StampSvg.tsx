/**
 * The approval stamp — THE mark that says "the teacher decided".
 *
 * One component, five call sites (pile card, review mini-thumb, preview page
 * strip, the draggable page-1 stamp, and the backend's PDF twin). It is the
 * only place in the product where the handwriting face appears, because it is
 * the only thing that is literally ink on paper; and it is the only red thing
 * on a surface where grey means "Vivi proposes" (§0.3, the ink grammar).
 *
 * DESIGN DECISIONS, so nobody re-litigates them at a call site:
 *
 *  * The −7° rotation lives INSIDE the svg. The mockup applied it in CSS and
 *    promptly drifted — −8° on the card, −7° on the drag. The spec rules −7°
 *    and calls for geometry identical to the PDF's, so the rotation is part of
 *    the drawing, not of the layout. `stamp-svg-single-source` pins this.
 *  * The colours are literal hex, not tokens, ON PURPOSE. This is the one
 *    component whose output must match a PDF the backend renders from its own
 *    palette; a Tailwind class cannot cross that boundary, and a token that
 *    someone re-themes later would silently desynchronise the two.
 *  * The score is drawn LTR-isolated. It sits inside an RTL document and a
 *    bare numeral next to punctuation reorders.
 *  * The press animation is opt-in and `motion-safe:` — approval is an event
 *    worth a beat, and reduced-motion users get the stamp without it.
 *
 * @see vivi-grade-review-mockup-v2.html `stampSvg()` — the visual source
 */

export const STAMP_ROTATION_DEG = -7;

/** Teacher red (§0.3). Literal by design — see the module doc. */
const TEACHER_RED = '#C8102E';

export interface StampSvgProps {
    /** The effective total, as the pricer renders it. */
    score: string | number;
    /** Rendered box in px. Card 64, mini-thumb 30, preview 118. */
    size?: number;
    className?: string;
    /** Play the press-down beat (the approval moment). */
    pressed?: boolean;
}

export function StampSvg({ score, size = 64, className, pressed = false }: StampSvgProps) {
    const text = String(score);
    // A four-character score ("100.5") has to breathe inside the same ellipse.
    const fontSize = text.length > 3 ? 42 : 50;

    return (
        <svg
            role="img"
            aria-label={`אושר ונחתם · ${text}`}
            viewBox="0 0 120 120"
            width={size}
            height={size}
            className={[
                pressed ? 'motion-safe:animate-stamp-press' : '',
                className ?? '',
            ].filter(Boolean).join(' ') || undefined}
        >
            <g transform={`rotate(${STAMP_ROTATION_DEG} 60 60)`}>
                <path
                    d="M61 12c27-2 46 16 48 43 2 26-17 49-45 52C36 109 13 91 11 63 9 36 31 14 61 12z"
                    fill="none"
                    stroke={TEACHER_RED}
                    strokeWidth="3"
                    strokeLinecap="round"
                    opacity=".92"
                />
                <path
                    d="M57 17c23-3 43 13 45 39 2 24-14 43-38 46"
                    fill="none"
                    stroke={TEACHER_RED}
                    strokeWidth="1.5"
                    opacity=".5"
                />
                <text
                    x="60"
                    y="77"
                    textAnchor="middle"
                    fontFamily="Caveat, cursive"
                    fontWeight="700"
                    fontSize={fontSize}
                    fill={TEACHER_RED}
                    style={{ direction: 'ltr', unicodeBidi: 'isolate' }}
                >
                    {text}
                </text>
            </g>
        </svg>
    );
}
