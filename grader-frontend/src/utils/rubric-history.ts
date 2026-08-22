/**
 * PR-5 S2 E-1 — the page-level undo stack, as pure functions.
 *
 * A snapshot is the FULL editable tuple {questions, declaredTotal, name} (ruled:
 * a questions-only stack would make Ctrl+Z silently no-op after a rename or total
 * edit, teaching her the mechanism can't be trusted). It is bounded at 50 and,
 * crucially, stores `questions` BY REFERENCE — the immutable ops give structural
 * sharing, so 50 snapshots share almost the whole tree and cost is trivial. NEVER
 * clone snapshots here; that would defeat the sharing (and re-introduce the exact
 * corruption the "ops imported, never forked" invariant prevents).
 *
 * No redo at MVP (deliberate; backlogged) — this is undo only.
 */

import type { RubricQuestion } from '@/types/rubric';

export interface RubricSnapshot {
    questions: RubricQuestion[];
    declaredTotal: number | undefined;
    name: string;
}

export const HISTORY_CAP = 50;

/**
 * Push a pre-edit snapshot. Keeps at most `cap` entries (drops the oldest). Returns
 * a NEW array; the snapshot is stored by reference (no deep copy — see file docs).
 */
export function pushSnapshot(
    stack: RubricSnapshot[],
    snapshot: RubricSnapshot,
    cap = HISTORY_CAP,
): RubricSnapshot[] {
    const next = stack.concat(snapshot);
    return next.length > cap ? next.slice(next.length - cap) : next;
}

/**
 * Pop the most-recent snapshot (the state to restore). Returns the popped snapshot
 * (or null when empty) and the remaining stack.
 */
export function popSnapshot(
    stack: RubricSnapshot[],
): { snapshot: RubricSnapshot | null; stack: RubricSnapshot[] } {
    if (stack.length === 0) return { snapshot: null, stack };
    return { snapshot: stack[stack.length - 1], stack: stack.slice(0, -1) };
}
