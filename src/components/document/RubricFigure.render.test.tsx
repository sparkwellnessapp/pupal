import { renderToStaticMarkup } from 'react-dom/server';
import { beforeAll, describe, expect, it } from 'vitest';

import { MathNotationContext } from '@/components/math/MathNotationContext';
import { loadKatex } from '@/lib/katex';

import { DocumentText } from './DocumentText';
import { RubricFigureSourceContext } from './RubricFigure';

/** A rubric's drawing renders as a figure — her drawing (once fetched) over its reading. */
beforeAll(async () => { await loadKatex(); });

const QUESTION = 'נתון משולש ישר זווית:\n[איור p3 238,732,358,884: משולש ישר זווית; זווית \\(50^{\\circ}\\), יתר 30]\nמצאו את x.';

describe('a drawing line in rubric text', () => {
    it('becomes a figure with its description, the math typeset', () => {
        const html = renderToStaticMarkup(
            <MathNotationContext.Provider value>
                <RubricFigureSourceContext.Provider value={{ kind: 'job', id: 'j1' }}>
                    <DocumentText text={QUESTION} />
                </RubricFigureSourceContext.Provider>
            </MathNotationContext.Provider>);
        expect(html).toContain('data-rubric-figure="3"');
        expect(html).toContain('<figcaption');
        expect(html).toContain('class="katex"');
        expect(html).toContain('data-figure-loading');            // the crop is on its way
        expect(html).not.toContain('[איור p3');                   // the marker itself is never shown
        expect(html.replace(/<[^>]+>/g, '')).toContain('מצאו את x.');
    });

    it('with no source document there is no image at all — only the reading', () => {
        const html = renderToStaticMarkup(<DocumentText text={QUESTION} />);
        expect(html).toContain('<figcaption');
        expect(html).not.toContain('data-figure-loading');
        expect(html).not.toContain('<img');
    });

    it('a described-only drawing renders its reading', () => {
        const html = renderToStaticMarkup(<DocumentText text={'[איור: גרף של שתי פונקציות]'} />);
        expect(html).toContain('data-rubric-figure="described"');
        expect(html).toContain('גרף של שתי פונקציות');
    });
});
