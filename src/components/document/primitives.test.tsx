import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CodeBlock } from './CodeBlock';
import { DisclosureRow } from './DisclosureRow';
import { EditableText } from './EditableText';
import { EditablePoints, coercePointsInput } from './EditablePoints';

/**
 * PR-5 S2 primitives. vitest is node-env (no jsdom, by convention), so:
 *   - PURE logic (points coercion) is unit-tested directly;
 *   - RESTING render is asserted via SSR markup;
 *   - interactive commit/cancel/keyboard is covered by Playwright (the mirror journey).
 */

describe('coercePointsInput — the one coercion path (string-wire seatbelt)', () => {
    it('parses the Decimal string the wire actually sends', () => {
        expect(coercePointsInput('12.0')).toBe(12);
        expect(coercePointsInput('1.5')).toBe(1.5);
        expect(coercePointsInput('  3 ')).toBe(3);
    });
    it('clamps negatives to 0 and never NaNs on garbage', () => {
        expect(coercePointsInput('-3')).toBe(0);
        expect(coercePointsInput('abc')).toBe(0);
        expect(coercePointsInput('')).toBe(0);
    });
    it('passes real numbers through', () => {
        expect(coercePointsInput(2.25)).toBe(2.25);
        expect(coercePointsInput(0)).toBe(0);
    });
});

describe('CodeBlock — LTR island', () => {
    it('renders dir=ltr with the code', () => {
        const html = renderToStaticMarkup(<CodeBlock code={'int x = 5;\nreturn x;'} />);
        expect(html).toContain('dir="ltr"');
        expect(html).toContain('int x = 5;');
    });
    it('renders nothing for empty/whitespace code', () => {
        expect(renderToStaticMarkup(<CodeBlock code={'   '} />)).toBe('');
    });
});

describe('DisclosureRow — D10 chevron-only-when-content rule', () => {
    it('WITH content: a toggle button (collapsed) renders', () => {
        const html = renderToStaticMarkup(
            <DisclosureRow label="פתרון לדוגמה" toggleLabel="פתרון לדוגמה"><pre>code</pre></DisclosureRow>,
        );
        expect(html).toContain('<button');
        expect(html).toContain('aria-expanded="false"');
        expect(html).toContain('פתרון לדוגמה');
        // Collapsed ⇒ content not in the DOM.
        expect(html).not.toContain('<pre>code</pre>');
    });
    it('WITHOUT content: label only, NO chevron/button', () => {
        const html = renderToStaticMarkup(<DisclosureRow label="שאלה 2" />);
        expect(html).not.toContain('<button');
        expect(html).toContain('שאלה 2');
    });
});

describe('EditableText — typography at rest', () => {
    it('renders the value with the given dir and an edit affordance', () => {
        const html = renderToStaticMarkup(
            <EditableText value={'שלום'} onCommit={() => {}} ariaLabel="טקסט" dir="rtl" />,
        );
        expect(html).toContain('שלום');
        expect(html).toContain('dir="rtl"');
        expect(html).toContain('role="button"');
    });
    it('empty + placeholder shows the muted add-affordance text', () => {
        const html = renderToStaticMarkup(
            <EditableText value={''} onCommit={() => {}} ariaLabel="טקסט" placeholder="הוסיפי טקסט" />,
        );
        expect(html).toContain('הוסיפי טקסט');
        expect(html).toContain('italic');
    });
    it('readOnly renders plain text — no button role', () => {
        const html = renderToStaticMarkup(
            <EditableText value={'קבוע'} onCommit={() => {}} ariaLabel="טקסט" readOnly />,
        );
        expect(html).toContain('קבוע');
        expect(html).not.toContain('role="button"');
    });
});

describe('EditablePoints — ledger chip at rest', () => {
    it('renders formatPoints(value) with tabular-nums as an editable button', () => {
        const html = renderToStaticMarkup(
            <EditablePoints value={12} onCommit={() => {}} ariaLabel="ניקוד" />,
        );
        expect(html).toContain('>12<');
        expect(html).toContain('tabular-nums');
        expect(html).toContain('<button');
    });
    it('formats a Decimal-ish number without float drift', () => {
        const html = renderToStaticMarkup(
            <EditablePoints value={5.249999999999} onCommit={() => {}} ariaLabel="ניקוד" />,
        );
        expect(html).toContain('>5.25<');
    });
    it('readOnly is a span, not a button (parent cascaded sum)', () => {
        const html = renderToStaticMarkup(
            <EditablePoints value={7} onCommit={() => {}} ariaLabel="ניקוד" readOnly />,
        );
        expect(html).toContain('>7<');
        expect(html).not.toContain('<button');
    });
    it('changed toggles the cascade-glow hook (E-3)', () => {
        const html = renderToStaticMarkup(
            <EditablePoints value={7} onCommit={() => {}} ariaLabel="ניקוד" changed />,
        );
        expect(html).toContain('points-cascade-glow');
    });
});
