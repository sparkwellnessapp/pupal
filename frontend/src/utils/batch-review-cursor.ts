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
