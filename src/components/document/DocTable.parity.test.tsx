import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { DocTable } from './DocTable';

/**
 * OD-7 (native table editing, 2026-09-24): DocTable grew an optional
 * `renderCell` so the transcription surface can put an input in each cell
 * without forking the table markup. The rubric mirror never passes it, and its
 * rendering must not move by one byte. The golden below was captured from the
 * component BEFORE the prop existed; this test is the proof that it did not.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GOLDEN = path.join(HERE, '__golden__', 'DocTable.before-renderCell.json');

const CASES: Record<string, Parameters<typeof DocTable>[0]> = {
    'header-inferred': { rows: [['קלט', 'פלט'], ['5', '8'], ['int x', 'x+1']] },
    'explicit-ltr-header': { rows: [['x', 'i', 'arr[i]'], ['6', '0', '8'], ['', '1', '5']], dir: 'ltr', hasHeader: true },
    'rtl-no-header': { rows: [['1', '2'], ['3', '4']], dir: 'rtl', hasHeader: false },
    'single-row': { rows: [['0', '1', '2', '3']] },
    'nested': {
        rows: [['a', 'b'], ['c', 'd']],
        nestedTables: [{ rows: [['n1', 'n2'], ['n3', 'n4']] } as never],
    },
};

const render = () => Object.fromEntries(
    Object.entries(CASES).map(([k, props]) => [k, renderToStaticMarkup(<DocTable {...props} />)]),
);

describe('DocTable — the mirror\'s markup is unchanged by renderCell (OD-7)', () => {
    it('renders byte-identically to the pre-renderCell golden', () => {
        expect(render()).toEqual(JSON.parse(readFileSync(GOLDEN, 'utf-8')));
    });
});
