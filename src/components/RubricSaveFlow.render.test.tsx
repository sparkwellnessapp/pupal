import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { RubricErrorDisplay } from './RubricSaveFlow';
import { RubricSaveError, type CompileErrorDetail } from '@/lib/api';

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
    const html = renderToStaticMarkup(<RubricErrorDisplay error={bagrutCompileError} />);

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

    it('renders a jump-to-node anchor carrying the full dotted path', () => {
        expect(html).toContain('q1.א.2');
        expect(html).toContain('מעבר לרכיב');
    });
});
