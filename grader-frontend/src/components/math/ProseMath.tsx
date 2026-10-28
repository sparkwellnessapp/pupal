'use client';

/**
 * Text that MAY carry mathematics — a quotation, Vivi's explanation line, feedback for
 * the student — drawn with its spans typeset when the subject has math notation
 * (MATH_RENDERING_PLAN §4, "MathText on every surface that shows answer text").
 *
 * The text itself is returned untouched when there is nothing to typeset, so a CS or
 * English surface renders exactly the string it rendered before, and so does a math
 * line written in words.
 */
import { Fragment } from 'react';

import { hasMathNotation } from '@/lib/subjects';
import { hasMath } from '@/utils/math-spans';

import { MathText } from './MathText';

export function ProseMath({ text, subject }: { text: string; subject?: string | null }) {
    if (!hasMathNotation(subject) || !hasMath(text)) return <>{text}</>;
    return (
        <>
            {text.split('\n').map((line, i) => (
                <Fragment key={i}>
                    {i > 0 && <br />}
                    <MathText text={line} />
                </Fragment>
            ))}
        </>
    );
}
