'use client';

/**
 * "This surface shows a subject with math notation" — provided ONCE by a surface that knows
 * the rubric's subject (the rubric document mirror), read by the shared text renderers deep
 * inside it (`BidiText`, the criterion cells) so each `\( … \)` span is typeset where it
 * stands. A rubric whose Word equations became LaTeX spans (`omml_latex.py`) would otherwise
 * show the teacher `\frac{1}{e}` in place of her own fraction.
 *
 * DEFAULT FALSE, and that is the safety property: a renderer outside a provider — the
 * transcription surface, every CS and English rubric — draws exactly the text it drew before.
 */
import { createContext, Fragment, useContext } from 'react';

import { hasMath } from '@/utils/math-spans';

import { MathText } from './MathText';

export const MathNotationContext = createContext(false);

export function useMathNotation(): boolean {
    return useContext(MathNotationContext);
}

/** `text`, with its math spans typeset when the surface has math notation. */
export function MathInline({ text }: { text: string }) {
    const math = useMathNotation();
    if (!math || !hasMath(text)) return <>{text}</>;
    return <MathText text={text} />;
}

/** `MathInline` over several lines (feedback, a rewrite): one line per `\n`. */
export function MathLines({ text }: { text: string }) {
    return (
        <>
            {text.split('\n').map((line, i) => (
                <Fragment key={i}>
                    {i > 0 && <br />}
                    <MathInline text={line} />
                </Fragment>
            ))}
        </>
    );
}
