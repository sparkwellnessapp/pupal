import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentText } from './DocumentText';

/**
 * Design Recovery Phase 2 — the acceptance is "ZERO raw markers, code as code,
 * bidi correct." SSR markup proves it deterministically (Playwright shots prove
 * the pixels).
 */

const MARKER_TEXT = [
    'לפניכם הפעולה Check בשפת #C:',
    'public static bool Check(int[] arr, int target)',
    '{',
    '    int sum = 0;',
    '    return sum == target;',
    '}',
    'הטבלה הבאה:',
    '[TABLE 1: 3x2]',
    '| קלט | פלט |',
    '|---|---|',
    '| 5 | 8 |',
    'הערה [[color:EE0000]]חשובה[[/color]]: Check(arr, 6) מחזירה true.',
    '[IMAGE: diagram.png]',
].join('\n');

describe('DocumentText — zero raw markers (the acceptance)', () => {
    const html = renderToStaticMarkup(<DocumentText text={MARKER_TEXT} />);

    it('never leaks a raw [TABLE / [[color / [IMAGE marker or pipe separator', () => {
        expect(html).not.toContain('[TABLE');
        expect(html).not.toContain('[[color');
        expect(html).not.toContain('[[/color');
        expect(html).not.toContain('[IMAGE');
        expect(html).not.toContain('|---');
    });

    it('renders the marked table as a real <table> with its cells', () => {
        expect(html).toContain('<table');
        expect(html).toContain('קלט');
        expect(html).toContain('פלט');
        expect(html).toContain('>5<');
        expect(html).toContain('>8<');
    });

    it('groups the code run into ONE <pre> LTR block (not airy paragraphs)', () => {
        const preCount = (html.match(/<pre/g) ?? []).length;
        expect(preCount).toBe(1);
        expect(html).toContain('public static bool Check');
        expect(html).toContain('dir="ltr"');
    });

    it('isolates Latin/code runs with <bdi> (kills the bidi mangling class)', () => {
        expect(html).toContain('<bdi');
    });

    it('renders an [IMAGE] marker as a placeholder, not raw', () => {
        expect(html).toContain('תמונה בלתי-קריאה');
        expect(html).toContain('diagram.png');
    });

    it('the color inner text survives, plain (no red bleed)', () => {
        expect(html).toContain('חשובה');
        expect(html).not.toContain('#EE0000');
    });
});

describe('DocumentText — unmarked numeric grid still tableizes (detectTableRuns fallback)', () => {
    it('a bare numeric run with no marker becomes a mini-table', () => {
        const html = renderToStaticMarkup(<DocumentText text={'תוצאות:\n1 2 3\n4 5 6'} />);
        expect(html).toContain('<table');
    });
    it('empty text renders nothing', () => {
        expect(renderToStaticMarkup(<DocumentText text={'   '} />)).toBe('');
    });
});
