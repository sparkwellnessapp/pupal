import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentText, SolutionBody } from './DocumentText';

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

/**
 * SolutionBody — the answer key. Three rulings, one renderer:
 *   1. text/code WRAPS (grows downward); only a table may scroll — a grid can't reflow.
 *   2. EVERY solution sits in the same grey box, tied to the "פתרון לדוגמה" toggle.
 *   3. Hebrew/mixed free text renders RTL; code stays one LTR block; tables keep
 *      their own content-inferred direction (the RTL must not leak into them).
 */
const HEBREW_PROSE = 'תשובה: הפעולה מקבלת מערך מספרים וערך x, ומטרתה לבדוק האם קיים מחלק.';
const CODE_WITH_HEBREW = [
    'public static bool IsMirror(int[] arr)',
    '{',
    '// בדיקה ראשונית: אורך זוגי',
    'return true;',
    '}',
].join('\n');
const HEBREW_TABLE = [
    '[TABLE 3: 3x5]',
    '| ערך מוחזר | cond | arr[i] | i | x |',
    '|---|---|---|---|---|',
    '| T | T | 3 | 4 |  |',
].join('\n');

describe('SolutionBody — uniform grey surface (ask 2)', () => {
    it.each([
        ['prose', HEBREW_PROSE],
        ['code', CODE_WITH_HEBREW],
        ['table', HEBREW_TABLE],
    ])('a %s solution renders inside the SAME grey box', (_kind, text) => {
        const html = renderToStaticMarkup(<SolutionBody text={text} />);
        expect(html).toContain('bg-surface-50');
        expect(html).toContain('border-surface-200');
    });

    it('renders nothing for an empty solution (absence stays absent)', () => {
        expect(renderToStaticMarkup(<SolutionBody text="   " />)).toBe('');
    });
});

describe('SolutionBody — no horizontal scrolling for text/code (ask 1)', () => {
    it('code WRAPS instead of scrolling, and carries no scroll container', () => {
        const html = renderToStaticMarkup(<SolutionBody text={CODE_WITH_HEBREW} />);
        expect(html).toContain('whitespace-pre-wrap');
        expect(html).toContain('break-words');
        expect(html).not.toContain('overflow-x-auto');
    });

    it('a whole program on ONE 1000-char line still wraps (no scrollbar)', () => {
        const long = `public static void main(String[] args) { ${'int x=0; '.repeat(120)}}`;
        const html = renderToStaticMarkup(<SolutionBody text={long} />);
        expect(html).toContain('whitespace-pre-wrap');
        expect(html).not.toContain('overflow-x-auto');
    });

    it('a TABLE may still scroll — a grid cannot reflow (the agreed exception)', () => {
        const html = renderToStaticMarkup(<SolutionBody text={HEBREW_TABLE} />);
        expect(html).toContain('overflow-x-auto');
        expect(html).toContain('<table');
    });
});

describe('SolutionBody — direction (ask 3)', () => {
    it('Hebrew free text renders RTL-aware prose, not an LTR code block', () => {
        const html = renderToStaticMarkup(<SolutionBody text={HEBREW_PROSE} />);
        expect(html).toContain('unicode-bidi:plaintext'); // the Prose treatment
        expect(html).not.toContain('<pre');               // NOT monospace code
        expect(html).toContain('תשובה');
    });

    it('mixed Hebrew+English free text is prose too, with the Latin isolated', () => {
        const html = renderToStaticMarkup(<SolutionBody text={'טענת כניסה: הפעולה מקבלת מערך arr ומחזירה true'} />);
        expect(html).not.toContain('<pre');
        expect(html).toContain('<bdi');   // Latin runs isolated so RTL can't reorder them
    });

    it('code stays ONE LTR block even though its comments are Hebrew', () => {
        const html = renderToStaticMarkup(<SolutionBody text={CODE_WITH_HEBREW} />);
        expect((html.match(/<pre/g) ?? []).length).toBe(1);  // ONE block, not fragments
        expect(html).toContain('dir="ltr"');
        expect(html).toContain('בדיקה ראשונית');             // the Hebrew comment rode along
    });

    it('a table keeps its OWN direction — the container RTL does not leak in', () => {
        const html = renderToStaticMarkup(<SolutionBody text={HEBREW_TABLE} />);
        // the Hebrew-bearing grid stays rtl (her Word column order), set explicitly
        expect(html).toContain('dir="rtl"');
        // and a Latin-only grid is NOT dragged rtl by the surrounding container
        const latinTable = '[TABLE 5: 2x4]\n| sum | i | arr[i] | check |\n|---|---|---|---|\n| 0 | 1 | 8 | T |';
        const ltr = renderToStaticMarkup(<SolutionBody text={latinTable} />);
        expect(ltr).toContain('dir="ltr"');
    });
});

/**
 * Table DIRECTION is a property of the source document, not of the cell contents.
 * parser_render reads OOXML `<w:tblPr><w:bidiVisual/>` and writes it into the
 * marker; the renderer CONSERVES it. Guessing from content mirrored 16 tables
 * across the five fixtures — in both directions.
 */
describe('DocTable — conserves the source table direction', () => {
    /** The direction of the TABLE itself (its own wrapper), not of any ancestor. */
    const tableDir = (html: string) =>
        /class="my-3 overflow-x-auto"\s+dir="(rtl|ltr)"/.exec(html)?.[1];

    const counts = (d: string) => [
        `[TABLE 13: 2x21 ${d}]`,
        '| 20 | 19 | 18 |',
        '|---|---|---|',
        '| 0 | 0 | 1 |',
    ].join('\n');

    it('an RTL table of digits renders RTL (first logical cell = RIGHTMOST, as Word lays it out)', () => {
        // The bug: all-numeric content made the old guesser say "ltr", so bagrut's
        // counts row rendered 20→0 left-to-right while Word shows 0→20.
        expect(tableDir(renderToStaticMarkup(<DocumentText text={counts('rtl')} />))).toBe('rtl');
    });

    it('the same table declared ltr renders LTR — the token decides, not the digits', () => {
        expect(tableDir(renderToStaticMarkup(<DocumentText text={counts('ltr')} />))).toBe('ltr');
    });

    it('an LTR table that merely CONTAINS Hebrew is not dragged RTL', () => {
        // bagrut T9/T10: `| 7 | -3 | … | המערך בתחילת הפעולה: |` is an LTR table.
        const text = ['[TABLE 9: 2x4 ltr]', '| 7 | -3 | 4 | המערך בתחילת הפעולה: |', '|---|---|---|---|', '| 1 | 2 | 3 | ד |'].join('\n');
        expect(tableDir(renderToStaticMarkup(<DocumentText text={text} />))).toBe('ltr');
    });

    it('a marker with NO token still parses, falling back to the content guess (legacy)', () => {
        const text = ['[TABLE 3: 2x2]', '| ערך מוחזר | x |', '|---|---|', '| T | 4 |'].join('\n');
        const html = renderToStaticMarkup(<DocumentText text={text} />);
        expect(html).toContain('<table');      // renders, does not break
        expect(tableDir(html)).toBe('rtl');    // Hebrew ⇒ guessed rtl
    });

    it('the direction token never leaks into the rendered text', () => {
        const html = renderToStaticMarkup(<DocumentText text={counts('rtl')} />);
        expect(html).not.toContain('rtl]');
        expect(html).not.toContain('[TABLE');
    });
});
