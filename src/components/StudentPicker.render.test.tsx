import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { StudentPicker } from './StudentPicker';

/**
 * B-25 identity-hint seeding — the suggested student name must sit IN the
 * input (ready for the one-click "צור תלמיד חדש"), not beside it. Observed
 * live 2026-08-12: an empty input rendering the placeholder next to a
 * populated suggestion label, forcing the teacher to retype the name.
 *
 * SSR pins the mount-time seeding (useState initial). The late-arrival path
 * (suggestion prop appearing after mount) is the reactive effect in the
 * component; effects don't run under SSR, so that branch is covered by the
 * guard conditions it shares with this one.
 */

describe('StudentPicker — identity-hint seeding', () => {
    it('seeds the closed input with the suggested name', () => {
        const html = renderToStaticMarkup(
            <StudentPicker value={null} onChange={() => {}} suggestedName="דן בסיוק" />,
        );
        expect(html).toContain('value="דן בסיוק"');
        // The generic search placeholder must not be the visible state.
        expect(html).not.toContain('value=""');
    });

    it('renders an empty input when there is no suggestion', () => {
        const html = renderToStaticMarkup(
            <StudentPicker value={null} onChange={() => {}} suggestedName={null} />,
        );
        expect(html).toContain('value=""');
        expect(html).toContain('חפש תלמיד...');
    });

    it('trims whitespace-only suggestions to the empty state', () => {
        const html = renderToStaticMarkup(
            <StudentPicker value={null} onChange={() => {}} suggestedName="   " />,
        );
        expect(html).toContain('value=""');
    });
});
