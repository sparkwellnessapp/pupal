import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { StampSvg, STAMP_ROTATION_DEG } from './StampSvg';

/**
 * `stamp-svg-single-source` (PR spec §7, phase F0).
 *
 * The stamp appears in five places — pile card, review mini-thumb, preview page
 * strip, the draggable page-1 stamp, and (as its twin) the rendered PDF. It is
 * the ONE mark that says "the teacher decided", so it has to be the same mark
 * every time: a second geometry is a second promise. The mockup already drifted
 * (−8° on the card, −7° on the drag); the spec rules −7°, so the rotation lives
 * INSIDE the svg where no call site can restate it differently.
 */
describe('StampSvg — one component, one geometry', () => {
    it('renders identical geometry at every call site, size aside', () => {
        // Strip only the presentation attributes a call site is allowed to
        // vary. `\s` on the front keeps `stroke-width` out of the match and
        // stops the removal leaving ragged whitespace behind.
        const geometry = (markup: string) =>
            markup.replace(/\s(?:width|height|class)="[^"]*"/g, '');

        const card = renderToStaticMarkup(<StampSvg score="84" size={64} />);
        const mini = renderToStaticMarkup(<StampSvg score="84" size={30} />);
        const preview = renderToStaticMarkup(<StampSvg score="84" size={118} className="x" />);

        expect(geometry(card)).toBe(geometry(mini));
        expect(geometry(card)).toBe(geometry(preview));
    });

    it('carries the −7° rotation inside the svg, not on the call site', () => {
        expect(STAMP_ROTATION_DEG).toBe(-7);
        expect(renderToStaticMarkup(<StampSvg score="84" />)).toContain('rotate(-7');
    });

    it('draws the double-stroke ellipse in teacher red and nothing else', () => {
        const markup = renderToStaticMarkup(<StampSvg score="84" />);
        expect(markup.match(/stroke="#C8102E"/g)).toHaveLength(2);
        expect(markup).toContain('fill="#C8102E"');
        expect(markup).not.toMatch(/#0D9488|#7C3AED/);
    });

    it('writes the score in the handwriting face — the only ink on paper', () => {
        const markup = renderToStaticMarkup(<StampSvg score="84" />);
        expect(markup).toContain('>84<');
        expect(markup).toMatch(/font-family="Caveat/);
    });

    it('shrinks the face for a long score so it never spills the ellipse', () => {
        const short = renderToStaticMarkup(<StampSvg score="84" />);
        const long = renderToStaticMarkup(<StampSvg score="100.5" />);
        expect(short).toContain('font-size="50"');
        expect(long).toContain('font-size="42"');
    });

    it('accepts a number as readily as the pricer string', () => {
        expect(renderToStaticMarkup(<StampSvg score={84} />)).toContain('>84<');
    });

    it('names itself to a screen reader in Hebrew, feminine-voice-free', () => {
        const markup = renderToStaticMarkup(<StampSvg score="84" />);
        expect(markup).toContain('aria-label="אושר ונחתם · 84"');
        expect(markup).toContain('role="img"');
    });

    it('isolates the score numeral from RTL reordering', () => {
        // A bare numeral inside an RTL document can reorder next to punctuation.
        expect(renderToStaticMarkup(<StampSvg score="84" />)).toContain('direction:ltr');
    });

    it('only animates when the press is asked for (approval is the event)', () => {
        expect(renderToStaticMarkup(<StampSvg score="84" />)).not.toContain('stamp-press');
        expect(renderToStaticMarkup(<StampSvg score="84" pressed />))
            .toContain('motion-safe:animate-stamp-press');
    });
});
