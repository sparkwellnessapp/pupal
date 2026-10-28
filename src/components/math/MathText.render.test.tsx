import { renderToStaticMarkup } from 'react-dom/server';
import { beforeAll, describe, expect, it } from 'vitest';

import { loadKatex } from '@/lib/katex';
import { answerRenderPlan } from '@/utils/answer-mode';
import { mathPieces } from '@/utils/math-pieces';
import { hasMathNotation } from '@/lib/subjects';

import { MathText } from './MathText';
import { ProseMath } from './ProseMath';

/** MATH_RENDERING_PLAN §4 — the typesetting half, zero mocks. */

describe('mathPieces — a mark lights a whole span, never half of one', () => {
    const line = 'מינימום \\((\\sqrt{e}, -2.25)\\) ולכן';
    //            0       8                          30

    it('cuts prose at mark boundaries and keeps a span whole', () => {
        expect(mathPieces(line).map((p) => p.kind)).toEqual(['text', 'math', 'text']);
        const marked = mathPieces(line, [{ start: 3, end: 12, kind: 'exact' }]);
        expect(marked.map((p) => [p.kind, p.mark])).toEqual([
            ['text', null], ['text', 'exact'], ['math', 'exact'], ['text', null],
        ]);
    });

    it('a mark entirely inside a span lights the span', () => {
        const pieces = mathPieces(line, [{ start: 14, end: 16, kind: 'fuzzy' }]);
        expect(pieces.find((p) => p.kind === 'math')!.mark).toBe('fuzzy');
    });

    it('exact wins over fuzzy on one span', () => {
        const pieces = mathPieces(line, [
            { start: 12, end: 14, kind: 'fuzzy' }, { start: 20, end: 22, kind: 'exact' },
        ]);
        expect(pieces.find((p) => p.kind === 'math')!.mark).toBe('exact');
    });

    it('no byte is lost', () => {
        const pieces = mathPieces(line, [{ start: 3, end: 30, kind: 'exact' }]);
        expect(pieces.map((p) => (p.kind === 'math' ? p.raw : p.text)).join('')).toBe(line);
    });
});

describe('MathText', () => {
    beforeAll(async () => { await loadKatex(); });

    it('isolates every span LTR — the coordinate pair cannot reverse', () => {
        const html = renderToStaticMarkup(<MathText text={'הנקודה \\((\\frac{1}{e}, 0)\\) על הגרף'} />);
        expect(html).toMatch(/<bdi dir="ltr" data-math-span="0"/);
        expect(html).toContain('class="katex"');
        expect(html).toContain('הנקודה ');
        // the source survives only in KaTeX's hidden MathML annotation (for screen readers)
        expect(html.replace(/<annotation[^>]*>.*?<\/annotation>/g, '')).not.toContain('\\frac');
    });

    it('a span KaTeX cannot parse is shown as transcribed, with a marker', () => {
        const html = renderToStaticMarkup(<MathText text={'שווה \\(\\frac{1}{\\)'} />);
        expect(html).toContain('data-math-raw="error"');
        expect(html).toContain('\\(\\frac{1}{\\)');
    });

    it('trusts nothing: no link or HTML reaches the page from an answer', () => {
        const html = renderToStaticMarkup(<MathText text={'\\(\\href{javascript:alert(1)}{x}\\)'} />);
        expect(html).not.toMatch(/<a\b|href=/);
    });

    it('text with no span is the text', () => {
        expect(renderToStaticMarkup(<MathText text="תשובה בלי נוסחה" />)).toBe('<span>תשובה בלי נוסחה</span>');
    });
});

describe('the capability decides, never the subject string', () => {
    it('only mathematics has math notation today', () => {
        expect(hasMathNotation('mathematics')).toBe(true);
        expect(hasMathNotation('computer_science')).toBe(false);
        expect(hasMathNotation('english')).toBe(false);
        expect(hasMathNotation(null)).toBe(false);
        expect(hasMathNotation('physics')).toBe(false);
    });

    it('math notation → math mode, RTL', () => {
        expect(answerRenderPlan('\\(x\\)', 'mathematics')).toEqual({ mode: 'math', dir: 'rtl' });
        expect(answerRenderPlan('int x;', 'computer_science').mode).toBe('code');
    });

    it('ProseMath returns CS text untouched, even if it looks like a span', () => {
        const cs = 'String s = "\\(";';
        expect(renderToStaticMarkup(<ProseMath text={cs} subject="computer_science" />))
            .toBe('String s = &quot;\\(&quot;;');
    });
});
