/**
 * Which test she reviews next (R2, spec §3).
 *
 * THE RULE: **next skips, never waits.** `next` is the next LANDED and
 * UNAPPROVED test in cursor order; anything still grading is stepped over and
 * revisited later. When nothing landed is left, the route shows the WaitCard —
 * who is being graded now and how long — rather than a spinner on an empty
 * screen.
 *
 * Why skipping is the right default: she has thirty papers and Vivi grades them
 * out of order. A `next` that waited for test 8 to finish would sit her in
 * front of a blank surface while tests 9–14 were ready — turning a queue she
 * could be working through into a queue she is watching. Skipping keeps her
 * hands busy and costs only that she meets test 8 a few minutes later.
 *
 * ── THE CURSOR IS FROZEN AT ROUTE ENTRY (OD2, inherited) ──────────────────
 * Order never reshuffles under her. Late arrivals APPEND; an existing entry
 * never moves, even when its status changes. This is the same append-only
 * cursor the transcription flow proved out — a page-held cursor silently
 * reshuffled mid-review, which is why it lives in the LAYOUT.
 */

export type GradedStatus = 'pending' | 'grading' | 'draft' | 'approved' | 'failed';

export interface CursorItem {
    graded_test_id: string;
    status: GradedStatus;
    student_name?: string | null;
    landed_at?: string | null;
}

export interface GradeCursor {
    /** Frozen at entry; append-only afterwards. */
    order: string[];
    byId: Record<string, CursorItem>;
}

/** Landed = there is a draft to review. */
export function isLanded(item: CursorItem | undefined): boolean {
    return item?.status === 'draft';
}

/** Reviewable = landed and not yet signed. `approved` opens the preview instead. */
export function isReviewable(item: CursorItem | undefined): boolean {
    return isLanded(item);
}

export function initialCursor(items: readonly CursorItem[]): GradeCursor {
    return {
        order: items.map((i) => i.graded_test_id),
        byId: Object.fromEntries(items.map((i) => [i.graded_test_id, i])),
    };
}

/**
 * Merge a fresh payload: statuses update in place, new ids APPEND.
 *
 * The prefix is stable by construction — existing ids keep their index no
 * matter what the server now says about them.
 */
export function mergeCursor(cursor: GradeCursor, items: readonly CursorItem[]): GradeCursor {
    const byId = { ...cursor.byId };
    const order = [...cursor.order];
    for (const item of items) {
        if (!(item.graded_test_id in byId)) order.push(item.graded_test_id);
        byId[item.graded_test_id] = item;
    }
    return { order, byId };
}

export type Direction = 'next' | 'prev';

/**
 * Step from `currentId` to the next reviewable test.
 *
 * Walks the frozen order in `direction`, skipping anything not reviewable, and
 * does NOT wrap: reaching the end means there is nothing landed left to review,
 * which is the WaitCard's cue. Wrapping instead would silently send her back to
 * the top and make "am I done?" unanswerable.
 */
export function step(
    cursor: GradeCursor,
    currentId: string,
    direction: Direction,
): string | null {
    const at = cursor.order.indexOf(currentId);
    if (at === -1) return null;
    const delta = direction === 'next' ? 1 : -1;
    for (let i = at + delta; i >= 0 && i < cursor.order.length; i += delta) {
        const id = cursor.order[i];
        if (isReviewable(cursor.byId[id])) return id;
    }
    return null;
}

/**
 * Where approve sends her (OD-F4: auto-advance, ruled).
 *
 * Forward first, then BACKWARD to pick up tests that were still grading when
 * she passed them. That backward sweep is the other half of "skips, never
 * waits": without it, everything skipped on the way down would be stranded and
 * she would have to hunt for them on the dashboard.
 */
export function advanceAfterApprove(cursor: GradeCursor, currentId: string): string | null {
    return step(cursor, currentId, 'next') ?? step(cursor, currentId, 'prev');
}

export interface QueueState {
    /** The next landed test, if any. */
    nextLanded: CursorItem | null;
    /** Being graded right now — what the WaitCard and QueueLine name. */
    grading: CursorItem[];
    /** Landed-but-unapproved tests she stepped over. */
    skipped: number;
    /** Nothing landed left: the WaitCard shows. */
    exhausted: boolean;
}

export function queueState(cursor: GradeCursor, currentId: string): QueueState {
    const nextId = step(cursor, currentId, 'next');
    const items = cursor.order.map((id) => cursor.byId[id]).filter(Boolean);
    const grading = items.filter((i) => i.status === 'grading' || i.status === 'pending');
    const reviewable = items.filter((i) => isReviewable(i) && i.graded_test_id !== currentId);
    return {
        nextLanded: nextId ? cursor.byId[nextId] : null,
        grading,
        // Anything reviewable that is NOT the one `next` will hand her: she has
        // walked past it, and the queue line says so rather than letting it
        // vanish.
        skipped: Math.max(0, reviewable.length - (nextId ? 1 : 0)),
        exhausted: nextId === null && !reviewable.length,
    };
}
