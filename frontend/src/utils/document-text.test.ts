import { describe, it, expect } from 'vitest';
import { stripColorMarkers, imageMarkerName, isCodeLine, groupTextBlocks, bidiRuns, looksLikeCode } from './document-text';

describe('stripColorMarkers', () => {
    it('removes the markers, keeps inner text verbatim', () => {
        expect(stripColorMarkers('הערה [[color:EE0000]]חשובה[[/color]] כאן')).toBe('הערה חשובה כאן');
    });
    it('handles multiple spans', () => {
        expect(stripColorMarkers('[[color:FF0000]]a[[/color]] and [[color:00FF00]]b[[/color]]')).toBe('a and b');
    });
    it('is a no-op with no markers', () => {
        expect(stripColorMarkers('plain')).toBe('plain');
    });
    it('also strips highlight [[hl:…]] markers, keeping inner text', () => {
        expect(stripColorMarkers('67+9 = [[hl:yellow]]76[[/hl]]')).toBe('67+9 = 76');
        expect(stripColorMarkers('[[hl:green]]a[[/hl]] and [[color:FF0000]]b[[/color]]')).toBe('a and b');
    });
});

describe('imageMarkerName', () => {
    it('extracts the filename', () => {
        expect(imageMarkerName('[IMAGE: diagram.png]')).toBe('diagram.png');
        expect(imageMarkerName('  [IMAGE:bar]  ')).toBe('bar');
    });
    it('falls back to a generic name for an empty marker', () => {
        expect(imageMarkerName('[IMAGE: ]')).toBe('תמונה');
    });
    it('returns null for non-image lines', () => {
        expect(imageMarkerName('a line [IMAGE: x] inline')).toBeNull(); // must be the WHOLE line
        expect(imageMarkerName('regular text')).toBeNull();
    });
});

describe('isCodeLine', () => {
    it('detects code by keyword / terminator / braces / symbol density', () => {
        expect(isCodeLine('public static bool Check(int[] arr)')).toBe(true);
        expect(isCodeLine('{')).toBe(true);
        expect(isCodeLine('    int sum = 0;')).toBe(true);
        expect(isCodeLine('        return sum == target;')).toBe(true);
        expect(isCodeLine('for (int i = 0; i < n; i++)')).toBe(true);
    });
    it('treats Hebrew as prose, always', () => {
        expect(isCodeLine('הפעולה Check מחזירה ערך')).toBe(false);
        expect(isCodeLine('שלום עולם')).toBe(false);
    });
    it('does not flag ordinary sparse Latin prose', () => {
        expect(isCodeLine('the plane has 3 engines')).toBe(false);
    });
    it('blank line is not code', () => {
        expect(isCodeLine('   ')).toBe(false);
    });
});

describe('groupTextBlocks', () => {
    it('fuses a consecutive code run into ONE code block, prose around it', () => {
        const text = 'לפניכם הפעולה:\npublic static int F()\n{\n  return 0;\n}\nהטבלה הבאה:';
        const blocks = groupTextBlocks(text);
        expect(blocks.map((b) => b.kind)).toEqual(['prose', 'code', 'prose']);
        const code = blocks[1] as { kind: 'code'; text: string };
        expect(code.text.split('\n')).toHaveLength(4); // signature { return } — one block
    });
    it('extracts [IMAGE] lines as image blocks', () => {
        const blocks = groupTextBlocks('טקסט\n[IMAGE: d.png]\nעוד טקסט');
        expect(blocks.map((b) => b.kind)).toEqual(['prose', 'image', 'prose']);
        expect((blocks[1] as { name: string }).name).toBe('d.png');
    });
    it('demotes a lone code-ish line to prose (precision bias)', () => {
        const blocks = groupTextBlocks('ראו new Plane() בהמשך');
        expect(blocks.every((b) => b.kind === 'prose')).toBe(true);
    });
});

describe('bidiRuns', () => {
    it('isolates Latin/code runs from Hebrew', () => {
        const runs = bidiRuns('הפעולה Check מחזירה true');
        const latin = runs.filter((r) => r.latin).map((r) => r.text);
        expect(latin).toContain('Check');
        expect(latin).toContain('true');
        expect(runs.some((r) => !r.latin && r.text.includes('הפעולה'))).toBe(true);
    });
    it('reassembles to the original text', () => {
        const t = 'x = arr[i] + 1; שלום';
        expect(bidiRuns(t).map((r) => r.text).join('')).toBe(t);
    });
    it('pure Hebrew yields a single non-latin run', () => {
        const runs = bidiRuns('שלום עולם');
        expect(runs).toHaveLength(1);
        expect(runs[0].latin).toBe(false);
    });
});

describe('looksLikeCode — block-level, tolerant of Hebrew comments', () => {
    // The ruling: a code answer key stays ONE LTR block even though its comments
    // are Hebrew. Only genuinely prose answers become RTL text.
    it('C# with Hebrew // comments is CODE (must not fragment)', () => {
        const sol = [
            'public static bool IsMirror(int[] arr)',
            '{',
            '// בדיקה ראשונית: אורך זוגי',
            'if (arr.Length % 2 != 0)',
            'return false;',
            '}',
        ].join('\n');
        expect(looksLikeCode(sol)).toBe(true);
    });

    it('a whole program collapsed onto ONE long line is still CODE', () => {
        // foundations q2: the 1x1 container cell arrives as a single ~1000-char line.
        expect(looksLikeCode('public static void main(String[] args) { int n=0; // מונה ... }')).toBe(true);
    });

    it('a Hebrew prose answer is NOT code', () => {
        expect(looksLikeCode('תשובה: הפעולה מקבלת מערך מספרים וערך x, ומטרתה לבדוק האם קיים מחלק.')).toBe(false);
    });

    it('a mixed Hebrew/English prose answer is NOT code', () => {
        expect(looksLikeCode('טענת כניסה: הפעולה מקבלת מערך arr\nטענת יציאה: מוחזר true אם המערך מראה')).toBe(false);
    });

    it('a returned-value line with arithmetic is NOT code (it is her sentence)', () => {
        expect(looksLikeCode('ערך מוחזר: 76\n0 + 8 + 4 + 15 + 40 + 9 = 76')).toBe(false);
    });

    it('a lone statement is code (a one-line answer key)', () => {
        expect(looksLikeCode('n1=n1+n3;')).toBe(true);
    });

    it('empty text is not code', () => {
        expect(looksLikeCode('')).toBe(false);
        expect(looksLikeCode('   \n  ')).toBe(false);
    });
});

describe('bidiRuns — neutral-only runs keep source order (faithful capture)', () => {
    // A pure-arithmetic line has NO strong character, so inside an RTL paragraph
    // the bidi algorithm reorders it and her sum renders backwards. Isolating it
    // as one LTR run preserves exactly what she wrote.
    it('isolates a whole arithmetic expression as ONE ltr run', () => {
        const runs = bidiRuns('0 + 8 + 4 + 15 + 40 + 9 = 76');
        expect(runs).toHaveLength(1);
        expect(runs[0].latin).toBe(true);
        expect(runs[0].text).toBe('0 + 8 + 4 + 15 + 40 + 9 = 76');
    });
    it('still stops at Hebrew — no trailing space swallowed', () => {
        const latin = bidiRuns('הפעולה Check מחזירה true').filter((r) => r.latin).map((r) => r.text);
        expect(latin).toContain('Check');
        expect(latin).toContain('true');
    });
    it('keeps a Hebrew label with its number ("ערך מוחזר: 76")', () => {
        const runs = bidiRuns('ערך מוחזר: 76');
        expect(runs.map((r) => r.text).join('')).toBe('ערך מוחזר: 76');
        expect(runs.filter((r) => r.latin).map((r) => r.text)).toEqual(['76']);
    });
    it('reassembles verbatim for a mixed code/Hebrew line', () => {
        const t = 'x = arr[i] + 1; שלום';
        expect(bidiRuns(t).map((r) => r.text).join('')).toBe(t);
    });
});

describe('isCodeLine — Hebrew in a COMMENT or STRING does not make a line prose', () => {
    // The bug: "Hebrew anywhere ⇒ prose" tore a class body in half at every line
    // carrying a Hebrew inline comment, and the orphaned `}` then fell out too.
    it('a declaration with a Hebrew inline comment is CODE', () => {
        expect(isCodeLine('private TvShow [] arrShows;\t\t// כל תוכניות הטלויזיה')).toBe(true);
        expect(isCodeLine('private int countHobbies ;\t\t// מספר התחביבים בפועל (קטן או שווה לגודל המערך')).toBe(true);
    });
    it('a comment-only line is CODE, whatever language its words are in', () => {
        expect(isCodeLine('// בנאי')).toBe(true);
        expect(isCodeLine('/* הערה */')).toBe(true);
        expect(isCodeLine('// a plain english note')).toBe(true);
    });
    it('a statement whose STRING is Hebrew is CODE (the literal is data, not prose)', () => {
        expect(isCodeLine('Console.WriteLine("שלום עולם");')).toBe(true);
    });
    it('a `//` inside a string cannot truncate the line', () => {
        expect(isCodeLine('var url = "http://example.com";')).toBe(true);
    });

    // ── the other half of the contract: real Hebrew prose is STILL prose ──
    it('plain Hebrew prose stays prose', () => {
        expect(isCodeLine('הפעולה מקבלת מערך ומחזירה את סכום האיברים')).toBe(false);
        expect(isCodeLine('שלום עולם')).toBe(false);
        expect(isCodeLine('הפעולה Check מחזירה ערך')).toBe(false);
    });
    it('Hebrew prose that merely mentions code is prose', () => {
        expect(isCodeLine('הניחו כי קיימות פעולות Get / Set עבור תכונות המחלקה.')).toBe(false);
        expect(isCodeLine('ראו new Plane() בהמשך')).toBe(false);
    });
    it('Hebrew prose containing a quoted word is prose', () => {
        expect(isCodeLine('סדנאות "דומות" הן סדנאות בעלות אותו שם')).toBe(false);
    });
    it('Hebrew prose mentioning #C is prose (# is not comment syntax here)', () => {
        expect(isCodeLine('לפניכם הפעולה Check בשפת #C:')).toBe(false);
    });
});

describe('groupTextBlocks — a class body with Hebrew comments stays ONE code block', () => {
    it('the TvRate case: 4 lines, one block, nothing demoted to prose', () => {
        const text = [
            'public class TvRate',
            '{',
            'private TvShow [] arrShows;\t\t// כל תוכניות הטלויזיה',
            '         }',
        ].join('\n');
        const blocks = groupTextBlocks(text);
        expect(blocks.map((b) => b.kind)).toEqual(['code']);
        expect((blocks[0] as { text: string }).text.split('\n')).toHaveLength(4);
    });

    it('the SchoolHobbies case survives blank-line separation from the renderer', () => {
        const text = [
            'public class SchoolHobbies', '', '{', '',
            'private Hobby [] hobbies;\t\t// כל התחביבים של תלמידי בית הספר', '',
            'private int countHobbies ;\t\t// מספר התחביבים בפועל', '',
            '// בנאי', '',
            'public SchoolHobbies (int size)', '', '{', '',
            'hobbies = new Hobby [size];', '', 'countHobbies = 0;', '', '}', '', '}',
        ].join('\n');
        const kinds = groupTextBlocks(text).map((b) => b.kind);
        expect(kinds).toEqual(['code']);          // ONE block, not five fragments
    });

    it('prose around a code block still separates correctly (no over-capture)', () => {
        const text = [
            'להלן כותרת המחלקה , התכונות ופעולה בונה:',
            'public class SchoolHobbies',
            '{',
            'private Hobby [] hobbies;\t// כל התחביבים',
            '}',
            'הניחו כי קיימות פעולות Get לכל תכונות המחלקה.',
        ].join('\n');
        expect(groupTextBlocks(text).map((b) => b.kind)).toEqual(['prose', 'code', 'prose']);
    });

    it('a LONE Hebrew comment in prose is demoted back to prose (the safety net)', () => {
        const blocks = groupTextBlocks('הסבר ראשון\n// הערה חשובה\nהסבר שני');
        expect(blocks.every((b) => b.kind === 'prose')).toBe(true);
    });
});
