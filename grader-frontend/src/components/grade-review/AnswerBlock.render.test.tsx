import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { AnswerBlock } from './AnswerBlock';

/**
 * The quote highlight, rendered.
 *
 * The pure matcher is covered in `grade-review-pure.test.ts`; this asserts the
 * half that actually failed for the teacher — that a `<mark>` reaches the DOM.
 * The old renderer matched per LINE with a raw `indexOf`, so a quote spanning
 * several lines produced no mark at all while the toast announced one. Measured
 * over 25 real graded tests: 338 of 1,420 quote buttons (24%) drew nothing.
 */

/** The real answer and quote from the reported case (criterion q1.א.c0). */
const ANSWER = [
    'public class Hobby',
    '{',
    'private string hobbyName ;',
    'private bool isSportive ;',
    'private int durationInMinutes ;',
    '}',
].join('\n');

const MULTILINE_QUOTE = [
    'public class Hobby',
    '{',
    'private string hobbyName ;',
    'private bool isSportive ;',
    'private int durationInMinutes ;',
].join('\n');

// `kind: 'none'` used to be how "paint nothing" was said. In the plural shape
// that IS the empty span list, so the call sites below are unchanged.
const render = (quote: string | null, kind: 'exact' | 'fuzzy' | 'none' = 'exact') =>
    renderToStaticMarkup(
        <AnswerBlock
            answer={ANSWER}
            highlight={{
                spans: quote && kind !== 'none' ? [{ quote, kind }] : [],
                pinned: true,
            }}
            subject="computer_science"
        />,
    );

const markCount = (html: string) => (html.match(/<mark/g) ?? []).length;

describe('AnswerBlock — the quote highlight', () => {
    it('marks a MULTI-LINE quote, once per line it spans', () => {
        const html = render(MULTILINE_QUOTE);
        // Five lines of quote → a mark on each; they cannot be one element
        // because each line is its own row in the code island.
        expect(markCount(html)).toBe(5);
    });

    it('marks a single-line quote exactly once', () => {
        expect(markCount(render('private bool isSportive ;'))).toBe(1);
    });

    it('draws NOTHING when the quote is not in the answer', () => {
        // Degrade by omission — never underline an arbitrary region.
        expect(markCount(render('int totallyDifferentThing = 42 ;'))).toBe(0);
    });

    it('draws nothing when there is no quote', () => {
        expect(markCount(render(null, 'none'))).toBe(0);
    });

    it('paints a fuzzy quote exactly like an exact one', () => {
        // Owner ruling 2026-09-11: one teal fill for exact and fuzzy alike. The
        // dashed amber underline is gone; `data-highlight` still records the
        // kind as data, so the two renders differ in that attribute ONLY.
        const fuzzy = render('private bool isSportve ;', 'fuzzy');
        const exact = render('private bool isSportive ;', 'exact');
        expect(markCount(fuzzy)).toBe(1);
        expect(fuzzy).not.toContain('border-dashed');
        expect(fuzzy).toContain('data-highlight="fuzzy"');
        // Same classes, verbatim. (The marked TEXT may differ — the fuzzy
        // locator trims its window to word boundaries — so the comparison is
        // on the paint, not on the whole markup.)
        const classOf = (html: string) => html.match(/<mark[^>]*class="([^"]*)"/)?.[1];
        expect(classOf(fuzzy)).toBeDefined();
        expect(classOf(fuzzy)).toBe(classOf(exact));
    });

    it('preserves the answer text exactly, marked or not', () => {
        // A matcher that loses or duplicates a character would corrupt the one
        // artefact the teacher is judging.
        const strip = (html: string) =>
            html.replace(/<[^>]+>/g, '').replace(/&#x27;/g, "'").replace(/&quot;/g, '"');
        const withMarks = strip(render(MULTILINE_QUOTE));
        const without = strip(render(null, 'none'));
        expect(withMarks).toBe(without);
    });

    it('carries the scroll margin that clears the sticky bar', () => {
        // `scrollIntoView({ block: 'start' })` would otherwise land the answer
        // BEHIND the sticky header — a jump the teacher reads as "nothing
        // happened", which is the same complaint the mark bug produced.
        expect(render(MULTILINE_QUOTE)).toContain('scroll-mt-scope');
    });
});
