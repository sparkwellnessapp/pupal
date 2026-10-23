/**
 * OD-2 — the keys INSIDE an editable answer table, as a pure reducer.
 *
 * Returns null for everything the browser (or the page) already does right:
 *  - Tab / Shift+Tab walk the cell inputs in DOM order, which IS source order
 *    (row-major, dir=ltr, virtual cells unfocusable) — wrapping across rows and
 *    leaving the table past its last cell, natively.
 *  - Arrow keys move the caret inside the cell; the page reducer ignores them in
 *    an editable (R3), so they never cross a cell or change items.
 *  - Ctrl/Cmd+Enter reaches the page's approve binding, as from the textarea.
 *  - IME composition (Hebrew input) never acts.
 */

export type CellKeyAction =
    | { kind: 'focus'; row: number; col: number }
    | { kind: 'leave' }
    | { kind: 'stay' };

export interface CellKeyInput {
    key: string;
    shiftKey: boolean;
    ctrlOrMeta: boolean;
    isComposing: boolean;
}

export function resolveCellKey(
    input: CellKeyInput,
    at: { row: number; col: number },
    editable: boolean[][],
): CellKeyAction | null {
    if (input.isComposing) return null;
    if (input.key === 'Escape') return { kind: 'leave' };
    if (input.key !== 'Enter' || input.ctrlOrMeta) return null;

    // Enter walks the column (Shift+Enter walks it up) — never a newline (TBL-4).
    const step = input.shiftKey ? -1 : 1;
    for (let r = at.row + step; r >= 0 && r < editable.length; r += step) {
        if (editable[r]?.[at.col]) return { kind: 'focus', row: r, col: at.col };
    }
    return { kind: 'stay' };
}
