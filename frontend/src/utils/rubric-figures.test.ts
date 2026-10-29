import { describe, expect, it } from 'vitest';

import { boxParam, parseFigureLine } from './rubric-figures';

/** The marker grammar of backend/app/services/docx_v3/rubric_figures.py, read the same way. */
describe('parseFigureLine', () => {
    it('a located drawing', () => {
        const f = parseFigureLine('[איור p3 120,80,560,400: משולש ישר זווית; \\(c=30\\)]');
        expect(f).toEqual({ page: 3, box: [120, 80, 560, 400], description: 'משולש ישר זווית; \\(c=30\\)' });
        expect(boxParam((f as { box: [number, number, number, number] }).box)).toBe('120,80,560,400');
    });

    it('a described-only drawing', () => {
        expect(parseFigureLine('[איור: גרף של שתי פונקציות]')).toEqual({ description: 'גרף של שתי פונקציות', page: null });
    });

    it('prose that mentions a drawing is not a drawing line', () => {
        expect(parseFigureLine('ראו [איור: גרף] למעלה')).toBeNull();
        expect(parseFigureLine('[IMAGE: Picture 1]')).toBeNull();
    });
});
