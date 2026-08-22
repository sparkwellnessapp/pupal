/**
 * The batch-review cursor — PURE ordering + navigation logic (plan OD-8, Δ10).
 *
 * THE FREEZE RULE (Δ10): the order is computed ONCE, on route entry, from the
 * batch payload (whose backend order is deterministic: ORDER BY created_at, id
 * — upload order). It is keyed by transcription_id and NEVER recomputed while
 * the teacher navigates: flag verdicts and statuses change as items get
 * accepted, and a live-recomputed flagged-first partition would reshuffle the
 * arrows mid-review. Item STATE stays live; item ORDER does not. Late-arriving
 * transcriptions join only on a fresh route entry.
 *
 * Ordering: flagged-first, stable — flagged items in payload order, then the
 * rest in payload order.
 */

export interface ReviewOrderItem {
  transcription_id: string
  flag_verdict: { review_needed: boolean }
}

export interface CursorPosition {
  /** 0-based position in the frozen order. */
  index: number
  total: number
  prevId: string | null
  nextId: string | null
  isFirst: boolean
  /** At the last item `nextId` is null — the shell renders "back to batch". */
  isLast: boolean
}

/**
 * Compute the frozen traversal order: flagged first, payload order preserved
 * within each partition. Call exactly once per route entry.
 */
export function computeReviewOrder(items: ReviewOrderItem[]): string[] {
  const flagged: string[] = []
  const clean: string[] = []
  for (const item of items) {
    (item.flag_verdict.review_needed ? flagged : clean).push(item.transcription_id)
  }
  return [...flagged, ...clean]
}

/**
 * Locate `currentId` in a frozen order. Returns null when the id is not in the
 * order (bad deep link, or an item that arrived after route entry) — the
 * caller falls back to the batch page.
 */
export function cursorPosition(order: string[], currentId: string): CursorPosition | null {
  const index = order.indexOf(currentId)
  if (index === -1) return null
  return {
    index,
    total: order.length,
    prevId: index > 0 ? order[index - 1] : null,
    nextId: index < order.length - 1 ? order[index + 1] : null,
    isFirst: index === 0,
    isLast: index === order.length - 1,
  }
}

// ---------------------------------------------------------------------------
// OD2 (P3/R6) — the append-only cursor. Δ10's "frozen per entry" becomes
// "prefix-stable": existing entries NEVER move (even if their verdicts
// changed); late arrivals APPEND — flagged at the partition boundary, clean
// at the tail. Totals grow; the counter bump is the only signal.
// ---------------------------------------------------------------------------

export interface FrozenCursor {
  order: string[]
  /** Index of the flagged|clean partition edge (= flagged count). */
  boundary: number
}

export function initialCursor(items: ReviewOrderItem[]): FrozenCursor {
  const order = computeReviewOrder(items)
  const boundary = items.filter((i) => i.flag_verdict.review_needed).length
  return { order, boundary }
}

/**
 * Merge a fresh payload into the cursor, append-only. New ids are judged by
 * THEIR verdict at append time; among themselves they keep payload order.
 * Pure — returns a new cursor (the same object when nothing arrived).
 */
export function appendNewItems(cursor: FrozenCursor, items: ReviewOrderItem[]): FrozenCursor {
  const known = new Set(cursor.order)
  const newFlagged: string[] = []
  const newClean: string[] = []
  for (const item of items) {
    if (known.has(item.transcription_id)) continue
    ;(item.flag_verdict.review_needed ? newFlagged : newClean).push(item.transcription_id)
  }
  if (newFlagged.length === 0 && newClean.length === 0) return cursor
  return {
    order: [
      ...cursor.order.slice(0, cursor.boundary),
      ...newFlagged,
      ...cursor.order.slice(cursor.boundary),
      ...newClean,
    ],
    boundary: cursor.boundary + newFlagged.length,
  }
}

// ---------------------------------------------------------------------------
// R5 — counter semantics: primary = stable 1-based FLAGGED position (approved
// keep their slot — the slot IS the order index); secondary = whole-batch
// position. A clean item has no primary (i null → the primary is omitted).
// ---------------------------------------------------------------------------

export interface CounterInfo {
  i: number | null
  F: number
  k: number
  T: number
}

export function counterInfo(cursor: FrozenCursor, currentId: string): CounterInfo | null {
  const index = cursor.order.indexOf(currentId)
  if (index === -1) return null
  return {
    i: index < cursor.boundary ? index + 1 : null,
    F: cursor.boundary,
    k: index + 1,
    T: cursor.order.length,
  }
}

// ---------------------------------------------------------------------------
// R4/R12 — the advance rule after a successful accept.
//
// Flagged context: scan FORWARD through the flagged partition, then WRAP to
// its start — approving the last row while an earlier flagged row was skipped
// must advance to it, or the interstitial's title ("כל המבחנים שסומנו נבדקו")
// would lie. None left → interstitial when unapproved cleans remain, else
// straight to the dashboard.
//
// Clean context (R12, kept minimal): forward-only within the clean partition;
// exhausted → dashboard (no terminal claim is made, so no wrap is owed).
// ---------------------------------------------------------------------------

export type AdvanceTarget =
  | { kind: 'item'; id: string }
  | { kind: 'interstitial' }
  | { kind: 'dashboard' }

export function advanceTarget(
  cursor: FrozenCursor,
  currentId: string,
  statusById: Record<string, 'transcribed' | 'approved'>,
): AdvanceTarget {
  const { order, boundary } = cursor
  const index = order.indexOf(currentId)
  const unapproved = (id: string) => statusById[id] !== 'approved'

  if (index !== -1 && index < boundary) {
    // Forward through the flagged partition, then wrap to its start.
    for (let step = 1; step < boundary; step += 1) {
      const id = order[(index + step) % boundary]
      if (unapproved(id)) return { kind: 'item', id }
    }
    const cleansRemain = order.slice(boundary).some(unapproved)
    return cleansRemain ? { kind: 'interstitial' } : { kind: 'dashboard' }
  }

  // Clean context: forward-only within the clean partition.
  for (let j = Math.max(index + 1, boundary); j < order.length; j += 1) {
    if (unapproved(order[j])) return { kind: 'item', id: order[j] }
  }
  return { kind: 'dashboard' }
}
