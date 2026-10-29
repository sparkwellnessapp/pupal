import { renderToStaticMarkup } from 'react-dom/server';
import { beforeAll, describe, expect, it } from 'vitest';

import { RubricDocument } from '@/components/RubricDocument';
import { loadKatex } from '@/lib/katex';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';

import { MathInline, MathLines, MathNotationContext } from './MathNotationContext';

/**
 * A rubric's text is typeset only on a math-notation surface. Word equations reach the
 * rubric as `\( … \)` spans (`omml_latex.py`); without this the teacher reviewed her own
 * fractions as `\frac{1}{e}`. Zero mocks: real KaTeX, real mirror.
 */

/** The visible markup: KaTeX's MathML annotation carries the source by design. */
const visible = (html: string) => html.replace(/<annotation[^>]*>[\s\S]*?<\/annotation>/g, '');

beforeAll(async () => { await loadKatex(); });

describe('MathInline', () => {
    const text = 'האסימפטוטה היא \\(x = \\frac{1}{e}\\)';

    it('outside a provider, text stays text — the CS and transcription default', () => {
        expect(renderToStaticMarkup(<MathInline text={text} />)).toBe(
            'האסימפטוטה היא \\(x = \\frac{1}{e}\\)');
    });

    it('under math notation, the span is typeset and the Hebrew kept', () => {
        const html = renderToStaticMarkup(
            <MathNotationContext.Provider value><MathInline text={text} /></MathNotationContext.Provider>);
        expect(html).toContain('class="katex"');
        expect(html).toContain('האסימפטוטה היא');
        expect(visible(html)).not.toContain('\\frac');
    });

    it('a line with no span renders the same string either way', () => {
        const plain = 'השיפוע חיובי';
        expect(renderToStaticMarkup(
            <MathNotationContext.Provider value><MathInline text={plain} /></MathNotationContext.Provider>,
        )).toBe(plain);
    });

    it('MathLines keeps the line breaks', () => {
        const html = renderToStaticMarkup(
            <MathNotationContext.Provider value><MathLines text={'א \\(x=1\\)\nב \\(y=2\\)'} /></MathNotationContext.Provider>);
        expect(html).toContain('<br/>');
        expect((html.match(/class="katex"/g) ?? []).length).toBe(2);
    });
});

describe('the rubric mirror typesets a math rubric and only a math rubric', () => {
    const questions = hydrateAnyQuestions([{
        question_id: 'q1',
        question_number: 1,
        question_text: 'נתונה הפונקציה \\(f(x) = \\frac{1}{e^x}\\)',
        total_points: 10,
        criteria: [{ criterion_id: 'q1.c0', description: 'מציאת \\(f\'(x)\\) נכונה', points: 10 }],
        example_solution: '\\(f\'(x) = -e^{-x}\\)',
    }]);
    const render = (subject: string) => renderToStaticMarkup(
        <RubricDocument questions={questions} onQuestionsChange={() => {}} rubricName="מחוון" subject={subject} />);

    it('mathematics: the question, the criterion and the solution are typeset', () => {
        const html = render('mathematics');
        expect((html.match(/class="katex"/g) ?? []).length).toBeGreaterThanOrEqual(2);
        expect(visible(html)).not.toContain('\\frac{1}{e^x}');
        expect(visible(html)).not.toContain("\\(f'(x)\\)");
    });

    it('computer_science: nothing is typeset — the renderer it always had', () => {
        const html = render('computer_science');
        expect(html).not.toContain('class="katex"');
        expect(html.replace(/<\/?bdi[^>]*>/g, '')).toContain('\\frac{1}{e^x}');
    });
});

describe('a bare formula quoted from inside a span is drawn as the formula', () => {
    it('wraps bare LaTeX under mathematics, and only there', async () => {
        const { asDisplayedQuote } = await import('@/components/grade-review/CriterionRowV6');
        expect(asDisplayedQuote("f'(x)=4x", 'mathematics')).toBe("\\(f'(x)=4x\\)");
        expect(asDisplayedQuote('\\frac{1}{e}', 'mathematics')).toBe('\\(\\frac{1}{e}\\)');
        expect(asDisplayedQuote('נקודת מינימום (\\sqrt{e}, -2.25)', 'mathematics'))
            .toBe('נקודת מינימום (\\sqrt{e}, -2.25)');                // Hebrew stays text
        expect(asDisplayedQuote('לכן \\(x=3\\)', 'mathematics')).toBe('לכן \\(x=3\\)');
        expect(asDisplayedQuote('x = 3;', 'computer_science')).toBe('x = 3;');
        expect(asDisplayedQuote('כי הנגזרת חיובית', 'mathematics')).toBe('כי הנגזרת חיובית');
    });
});
