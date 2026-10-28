import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';

import { FIG_KIND_HE } from '@/copy/math';
import type { Figure } from '@/types/transcription';

import { figureLines, matchFigures } from './figure-lines';

/** The same cases as backend `tests/services/test_figures.py` (the matcher is mirrored). */
const fig = (page: number, n: number): Figure => ({
    figure_no: n, page_number: page, kind: 'function_sketch', box_2d: [300, 100, 800, 900], features: [],
});
const TEXT = 'ב.\n[איור 1: סקיצה של f]\n\\(f\'(x)=0\\)\n[איור 1: סקיצה של g]';

describe('figure lines ↔ readings (mirror of services/figures.py)', () => {
    it('finds lines in order', () => {
        expect(figureLines(TEXT)).toEqual([{ line: 1, n: 1 }, { line: 3, n: 1 }]);
    });

    it('tells two «איור 1» apart by page order', () => {
        const m = matchFigures(TEXT, [fig(11, 1), fig(10, 1)]);
        expect(m.pairs.map((p) => [p.line, p.figure.page_number])).toEqual([[1, 10], [3, 11]]);
        expect(m.unread).toEqual([]);
        expect(m.orphans).toEqual([]);
    });

    it('an unread line is recorded; a figure without its line is an orphan', () => {
        expect(matchFigures(TEXT, [fig(10, 1)]).unread).toEqual([3]);
        expect(matchFigures('\\(x=2\\)', [fig(10, 1)]).orphans).toHaveLength(1);
    });
});

describe('the Hebrew names of reading kinds are one list in two languages', () => {
    it('matches backend figures.KIND_HE exactly', () => {
        const here = path.dirname(fileURLToPath(import.meta.url));
        const src = readFileSync(path.resolve(here, '../../../backend/app/services/figures.py'), 'utf-8');
        const block = src.slice(src.indexOf('KIND_HE = {'), src.indexOf('}', src.indexOf('KIND_HE = {')));
        const backend = Object.fromEntries([...block.matchAll(/"(\w+)":\s*"([^"]+)"/g)].map((m) => [m[1], m[2]]));
        expect(Object.keys(backend).length).toBe(15);
        expect(FIG_KIND_HE).toEqual(backend);
    });
});
