import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { RubricErrorDisplay } from './RubricSaveFlow';
import { RubricSaveError, type CompileErrorDetail } from '@/lib/api';
import type { RubricQuestion } from '@/types/rubric';

// A tree matching the error's q1.א.2 location, so scopeLabel resolves to the
// teacher's naming (PR-5 S1-9) instead of leaking the raw dotted path.
const QUESTIONS: RubricQuestion[] = [
    { question_id: 'q1', total_points: 3, criteria: [], sub_questions: [
        { sub_question_id: 'א', index: 0, points: 3, criteria: [], sub_questions: [
            { sub_question_id: '2', index: 1, points: 3, criteria: [
                { criterion_id: 'c1', index: 0, description: '', points: 2 }] },
        ] },
    ] },
];

/**
 * PR-4 Phase 5.2 — the STRUCTURED compile-error render must surface the fields
 * PR-3 put on the wire (invariant / expected / actual / message_he / location),
 * not just a flat message. This is the "PR-3's payload work finally reaches the
 * teacher's eyes" acceptance. SSR markup is enough to prove the fields render.
 */

const bagrutCompileError = new RubricSaveError(
    'compilation_failed',
    'המחוון לא עבר בדיקה',
    [
        {
            location: 'q1.א.2',
            invariant: 'INV-2',
            expected: '3',
            actual: '2',
            message: 'sub-question q1.א.2: criteria sum (2) != declared (3)',
            message_he: 'סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)',
        } satisfies CompileErrorDetail,
    ],
);

describe('RubricErrorDisplay — structured compile-error render (PR-4)', () => {
    const html = renderToStaticMarkup(<RubricErrorDisplay error={bagrutCompileError} questions={QUESTIONS} />);

    it('renders the named invariant chip', () => {
        expect(html).toContain('INV-2');
    });

    it('renders the expected and actual arithmetic', () => {
        expect(html).toContain('צפוי');
        expect(html).toContain('בפועל');
        expect(html).toContain('>3<');
        expect(html).toContain('>2<');
    });

    it('renders the real Hebrew message (message_he), not the English fallback', () => {
        expect(html).toContain('סכום רכיבי הניקוד');
        expect(html).not.toContain('criteria sum (2) != declared (3)');
    });

    it('the jump target shows the naming LABEL, not the raw dotted path (S1-9)', () => {
        // The location CHIP now speaks the naming law: "מעבר לשאלה 1 · סעיף א · תת-סעיף 2".
        // (The raw "q1.א.2" still appears inside the backend message_he text — that is a
        // separate residual the Sprint-3 finding-voice rework addresses, not S1-9's chip.)
        expect(html).toContain('שאלה 1 · סעיף א · תת-סעיף 2');
        expect(html).toContain('מעבר ל');
    });
});
