import { describe, it, expect } from 'vitest';

import { resolveCellKey } from './table-cell-keymap';

/**
 * OD-2 — the keys INSIDE an editable answer table, as a pure reducer.
 *
 * `null` means "the browser's own behaviour": Tab/Shift+Tab walk the cell
 * inputs in DOM order, which IS source order (row-major, dir=ltr), wraps across
 * rows and leaves the table past its last cell — natively, so it is not
 * re-implemented. Arrow keys move the caret inside the cell and never cross a
 * cell (the page reducer already ignores them in an editable, R3/R6).
 * Ctrl/Cmd+Enter is ALSO null: it must reach the page's approve binding, the
 * same as from the answer textarea.
 */

// A 3x3 grid whose middle row's last cell is VIRTUAL (end padding — no bytes).
const EDITABLE = [
    [true, true, true],
    [true, true, false],
    [true, true, true],
];
const key = (k: string, extra: Partial<{ shiftKey: boolean; ctrlOrMeta: boolean; isComposing: boolean }> = {}) => ({
    key: k, shiftKey: false, ctrlOrMeta: false, isComposing: false, ...extra,
});

describe('resolveCellKey', () => {
    it('Enter moves to the same column, next row — never a newline (TBL-4)', () => {
        expect(resolveCellKey(key('Enter'), { row: 0, col: 1 }, EDITABLE)).toEqual({ kind: 'focus', row: 1, col: 1 });
    });

    it('Enter skips a virtual cell in that column', () => {
        expect(resolveCellKey(key('Enter'), { row: 0, col: 2 }, EDITABLE)).toEqual({ kind: 'focus', row: 2, col: 2 });
    });

    it('Enter on the last row stays put (consumed, no newline, no approve)', () => {
        expect(resolveCellKey(key('Enter'), { row: 2, col: 0 }, EDITABLE)).toEqual({ kind: 'stay' });
    });

    it('Shift+Enter moves up the column', () => {
        expect(resolveCellKey(key('Enter', { shiftKey: true }), { row: 2, col: 2 }, EDITABLE))
            .toEqual({ kind: 'focus', row: 0, col: 2 });
    });

    it('Escape leaves the table', () => {
        expect(resolveCellKey(key('Escape'), { row: 1, col: 1 }, EDITABLE)).toEqual({ kind: 'leave' });
    });

    it('Tab, Shift+Tab and the arrows are the browser\'s', () => {
        for (const k of ['Tab', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'a', '5']) {
            expect(resolveCellKey(key(k), { row: 1, col: 1 }, EDITABLE)).toBeNull();
        }
        expect(resolveCellKey(key('Tab', { shiftKey: true }), { row: 1, col: 1 }, EDITABLE)).toBeNull();
    });

    it('Ctrl/Cmd+Enter is left for the page (approve), exactly as in the textarea', () => {
        expect(resolveCellKey(key('Enter', { ctrlOrMeta: true }), { row: 0, col: 0 }, EDITABLE)).toBeNull();
    });

    it('IME composition never acts (Hebrew input)', () => {
        expect(resolveCellKey(key('Enter', { isComposing: true }), { row: 0, col: 0 }, EDITABLE)).toBeNull();
        expect(resolveCellKey(key('Escape', { isComposing: true }), { row: 0, col: 0 }, EDITABLE)).toBeNull();
    });
});
