import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import type { NumericPolicy } from '@/lib/pricing';
import { RV_POINTS_EDIT_TITLE, RV_POINTS_TYPED_TITLE } from '@/copy/grade-review';
import { PointsInput } from './PointsInput';

/**
 * [OD-R2] The editable figure, rendered. Typing and the live refusal are
 * browser behaviour and live in `e2e/grade-review.spec.ts`; this pins the
 * three static shapes — resting control, open field, read-only text.
 */

const POLICY: NumericPolicy = { precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01' };

const render = (over: Partial<React.ComponentProps<typeof PointsInput>> = {}) =>
    renderToStaticMarkup(
        <PointsInput
            target="check"
            value="2"
            max="4"
            policy={POLICY}
            typed={false}
            overridden={false}
            editing={false}
            onEditingChange={() => undefined}
            onCommit={() => undefined}
            {...over}
        />,
    );

describe('PointsInput — the editable figure', () => {
    it('rests as a button that reads «awarded / max» and says what a click does', () => {
        const html = render();
        expect(html).toContain('<button');
        expect(html).toContain('data-points-editing="false"');
        expect(html).toContain(`title="${RV_POINTS_EDIT_TITLE}"`);
        expect(html.replace(/<[^>]+>/g, '')).toBe('2 / 4');
    });

    it('a typed figure says so, and paints turquoise like every other decision of hers', () => {
        const html = render({ typed: true, overridden: true });
        expect(html).toContain('data-points-typed="true"');
        expect(html).toContain(`title="${RV_POINTS_TYPED_TITLE}"`);
        expect(html).toContain('text-primary-700');
        expect(html).not.toContain('text-grade-red');
    });

    it('opens as a decimal field seeded with the current figure, LTR, no popover while valid', () => {
        const html = render({ editing: true });
        expect(html).toContain('data-points-input="check"');
        expect(html).toMatch(/inputmode="decimal"/i);
        expect(html).toContain('dir="ltr"');
        expect(html).toContain('value="2"');
        expect(html).not.toContain('data-points-error');
    });

    it('is plain text when read-only — no button, no field', () => {
        const html = render({ readOnly: true, editing: true });
        expect(html).not.toContain('<button');
        expect(html).not.toContain('<input');
        expect(html).toContain('data-points-target="check"');
    });
});
