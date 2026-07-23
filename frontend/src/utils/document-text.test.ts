import { describe, it, expect } from 'vitest';
import { stripColorMarkers, imageMarkerName, isCodeLine, groupTextBlocks, bidiRuns } from './document-text';

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
