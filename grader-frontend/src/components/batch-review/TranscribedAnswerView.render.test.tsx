import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { TranscribedAnswerView } from './TranscribedAnswerView';

/**
 * The acceptance for the rendered answer view: the student's trace grid becomes
 * a real <table>, no pipe row survives as text, the prose around it is left
 * alone, and the whole thing is an LTR island (owner-ruled direction policy —
 * the grid must agree with the raw text the teacher edits).
 */

const REAL_ANSWER = [
    'if:',
    'returned | x | i | arr[i] | (arr[i]≠1 && arr[i]≠x && x%arr[i]==0)',
    '6 | 0 | 1 | F',
    '6 | 1 | 5 | F',
    'true | 6 | 4 | 3 | T',
    '',
    '(א, 2) לבדוק אם יש ערך במערך ש-שונה מ-1',
].join('\n');

describe('TranscribedAnswerView', () => {
    const html = renderToStaticMarkup(<TranscribedAnswerView text={REAL_ANSWER} />);

    it('renders the pipe grid as a real table with its cells', () => {
        expect(html).toContain('<table');
        expect(html).toContain('<thead');
        expect(html).toContain('returned');
        expect(html).toContain('arr[i]');
    });

    it('leaves no pipe row rendered as text', () => {
        expect(html).not.toContain('6 | 0 | 1 | F');
        expect(html).not.toContain('true | 6 | 4 | 3 | T');
    });

    it('keeps the surrounding prose verbatim, in a monospace block', () => {
        expect(html).toContain('<pre');
        expect(html).toContain('if:');
        expect(html).toContain('לבדוק אם יש ערך במערך');
    });

    it('is an LTR island and isolates Latin runs per cell', () => {
        expect(html).toContain('dir="ltr"');
        expect(html).toContain('<bdi');
    });

    it('renders nothing but the shell for empty text', () => {
        const empty = renderToStaticMarkup(<TranscribedAnswerView text="" />);
        expect(empty).not.toContain('<table');
        expect(empty).not.toContain('<pre');
    });

    it('says where the marked lines are instead of hiding them', () => {
        const withFlags = renderToStaticMarkup(<TranscribedAnswerView text={REAL_ANSWER} flagCount={2} />);
        expect(withFlags).toContain('שורות מסומנות מוצגות רק בטקסט המקורי');
        expect(html).not.toContain('שורות מסומנות');
    });
});
