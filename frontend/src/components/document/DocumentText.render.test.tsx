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

describe('DocumentText — a 1-row [TABLE] data array renders as a table body row (not a header)', () => {
    // prompt 3.4.0-tablemarkers: a data array is preserved as [TABLE N: 1xC] + one
    // pipe row. Its single row is DATA, not a header — so it renders in <tbody>.
    const html = renderToStaticMarkup(
        <DocumentText text={'נתון המערך arr:\n[TABLE 4: 1x8]\n| 2 | 9 | 40 | 3 | 15 | 4 | 5 | 8 |\n|---|---|---|---|---|---|---|---|'} />,
    );
    it('renders a real <table> with the array values as body cells, no <thead>', () => {
        expect(html).toContain('<table');
        expect(html).not.toContain('<thead');   // 1 row ⇒ data, not header
        expect(html).toContain('<td');
        expect(html).not.toContain('<th');
        expect(html).toContain('>40<');
        expect(html).toContain('>15<');
    });
    it('leaks no raw marker or separator', () => {
        expect(html).not.toContain('[TABLE');
        expect(html).not.toContain('|---');
    });
});

describe('DocumentText — a marked example_solution trace table renders as a real <table>', () => {
    // prompt 3.5.0-solutiontables: a filled solution table is preserved as full
    // [TABLE] markdown (header + value rows) → SolutionBlock routes it through
    // DocumentText → a labeled <table>, not plain monospace text.
    const solution = [
        '[TABLE 3: 6x5]',
        '| ערך מוחזר | arr[i]!=1 && arr[i]!=x && x % arr[i]==0 | arr[i] | i | x |',
        '|---|---|---|---|---|',
        '|  | F | 8 | 0 | 6 |',
        '|  | F | 5 | 1 |  |',
        '| T | T | 3 | 4 |  |',
    ].join('\n');
    const html = renderToStaticMarkup(<DocumentText text={solution} />);
    it('renders a <table> with the header row in <thead> and values in <tbody>', () => {
        expect(html).toContain('<table');
        expect(html).toContain('<thead');
        expect(html).toContain('ערך מוחזר');   // header cell
        expect(html).toContain('>8<');          // a filled value
    });
    it('leaks no raw marker or separator', () => {
        expect(html).not.toContain('[TABLE');
        expect(html).not.toContain('|---');
    });
    it('strips highlight ink inside a solution cell', () => {
        const hl = renderToStaticMarkup(<DocumentText text={'[TABLE 5: 2x2]\n| a | b |\n|---|---|\n| 67+9 = [[hl:yellow]]76[[/hl]] | x |'} />);
        expect(hl).not.toContain('[[hl');
        expect(hl).toContain('76');
    });
});

describe('DocumentText — an empty trace scaffold keeps ALL its blank rows (not collapsed to header)', () => {
    // Regression: isSeparator swallowed all-blank pipe rows (|  |  |  |) as |---| separators,
    // collapsing a student trace scaffold to header-only. Blank rows must survive.
    const scaffold = [
        '[TABLE 3: 6x5]',
        '| ערך מוחזר | cond | arr[i] | i | x |',
        '|---|---|---|---|---|',
        '|  |  |  |  |  |',
        '|  |  |  |  |  |',
        '|  |  |  |  |  |',
        '|  |  |  |  |  |',
        '|  |  |  |  |  |',
    ].join('\n');
    const html = renderToStaticMarkup(<DocumentText text={scaffold} />);
    it('renders the header row + all 5 blank data rows (6 <tr> total)', () => {
        expect(html).toContain('<table');
        expect(html).toContain('<thead');
        expect((html.match(/<tr/g) ?? []).length).toBe(6); // 1 header + 5 blank rows
    });
});

describe('DocumentText — a 1×1 table (code wrapped in one cell) is NOT a bordered table', () => {
    // The renderer sometimes wraps a code/prose block in a single-cell [TABLE: 1x1];
    // that is a container, not a grid. DocumentText renders the cell content, no <table>.
    const html = renderToStaticMarkup(
        <DocumentText text={'[TABLE 2: 1x1]\n| public static void main(String[] args) { return sum; } |\n|---|'} />,
    );
    it('renders the cell content, never a <table>', () => {
        expect(html).not.toContain('<table');
        expect(html).not.toContain('[TABLE');
        expect(html).toContain('static');   // content present (bidi-split into <bdi> runs)
        expect(html).toContain('return');
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
