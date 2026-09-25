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

/**
 * Native table editing (2026-09-24). Given an `onChange`, the view is the
 * EDITOR for a table-bearing answer: every text run is a textarea over its own
 * span, every cell that owns bytes — header row included — is an input, and a
 * virtual (end-padded) cell is visibly NOT one. Read-only keeps today's markup.
 */
describe('TranscribedAnswerView — editable segments', () => {
    const P1_ANSWER = [
        'א) 1)',
        '| x | i | arr[i] | ret |',
        '| 6 | 0 | 8 |  |',
        '|  | 1 | 5 |  |',
        '',
        '(א, 2) הפעולה בודקת אם יש ערך במערך',
    ].join('\n');
    const editable = renderToStaticMarkup(<TranscribedAnswerView text={P1_ANSWER} onChange={() => {}} />);
    const count = (html: string, needle: string) => html.split(needle).length - 1;

    it('renders one input per cell, header row included', () => {
        expect(count(editable, 'data-testid="answer-cell"')).toBe(12);
        expect(editable).toMatch(/<th[^>]*>[^]*?<input[^>]*value="arr\[i\]"/);
        expect(editable).toContain('value="8"');
    });

    it('renders every text run as its own textarea, holding exactly its span', () => {
        expect(count(editable, 'data-testid="answer-text-run"')).toBe(2);
        expect(editable).toContain('>א) 1)</textarea>');
        expect(editable).toContain('>(א, 2) הפעולה בודקת אם יש ערך במערך</textarea>');
    });

    it('every cell is a pure LTR island — never unicode-bidi: plaintext', () => {
        expect(editable).toMatch(/<input[^>]*dir="ltr"[^>]*data-testid="answer-cell"|<input[^>]*data-testid="answer-cell"[^>]*dir="ltr"/);
        expect(editable).not.toContain('plaintext');
    });

    it('marks an end-padded cell as absent instead of offering an input', () => {
        const html = renderToStaticMarkup(<TranscribedAnswerView text={REAL_ANSWER} onChange={() => {}} />);
        // REAL_ANSWER: a 5-cell header over two 4-cell rows ⇒ 2 virtual cells.
        expect(count(html, 'data-testid="answer-cell-absent"')).toBe(2);
    });

    it('read-only keeps the display markup: no inputs, no textareas', () => {
        const ro = renderToStaticMarkup(<TranscribedAnswerView text={P1_ANSWER} onChange={() => {}} readOnly />);
        expect(ro).not.toContain('<input');
        expect(ro).not.toContain('<textarea');
        expect(ro).toContain('<table');
    });
});
