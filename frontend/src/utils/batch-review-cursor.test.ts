import { describe, expect, it } from 'vitest'
import { computeReviewOrder, cursorPosition, type ReviewOrderItem } from './batch-review-cursor'

function item(id: string, flagged: boolean): ReviewOrderItem {
  return { transcription_id: id, flag_verdict: { review_needed: flagged } }
}

describe('computeReviewOrder — flagged-first, stable', () => {
  it('puts flagged items first, preserving payload order within each partition', () => {
    const order = computeReviewOrder([
      item('a', false), item('b', true), item('c', false), item('d', true),
    ])
    expect(order).toEqual(['b', 'd', 'a', 'c'])
  })

  it('all-clean and all-flagged batches keep pure payload order', () => {
    expect(computeReviewOrder([item('a', false), item('b', false)])).toEqual(['a', 'b'])
    expect(computeReviewOrder([item('a', true), item('b', true)])).toEqual(['a', 'b'])
  })

  it('empty batch → empty order', () => {
    expect(computeReviewOrder([])).toEqual([])
  })
})

describe('cursor-order-frozen-under-refresh (Δ10)', () => {
  it('a payload refresh that flips verdicts/statuses does not move the arrows', () => {
    // Route entry: order computed ONCE from the entry payload.
    const entryPayload = [item('a', false), item('b', true), item('c', false)]
    const frozen = computeReviewOrder(entryPayload) // ['b', 'a', 'c']

    // Teacher sits on 'a'. A background refresh now claims 'c' became flagged
    // and 'b' was accepted (verdicts flipped) — the shell must keep using the
    // FROZEN order, so prev/next land on the same ids as before the refresh.
    const before = cursorPosition(frozen, 'a')!
    // (the refreshed payload is deliberately never fed back into the cursor)
    const after = cursorPosition(frozen, 'a')!
    expect(after).toEqual(before)
    expect(after.prevId).toBe('b')
    expect(after.nextId).toBe('c')

    // Counter-factual, proving the freeze is load-bearing: recomputing from
    // the refreshed payload WOULD reshuffle.
    const refreshedPayload = [item('a', false), item('b', false), item('c', true)]
    expect(computeReviewOrder(refreshedPayload)).not.toEqual(frozen)
  })
})

describe('cursorPosition — ends and fallbacks', () => {
  const order = ['x', 'y', 'z']

  it('first item: no prev', () => {
    const pos = cursorPosition(order, 'x')!
    expect(pos.isFirst).toBe(true)
    expect(pos.prevId).toBeNull()
    expect(pos.nextId).toBe('y')
  })

  it('last item: no next — the shell renders back-to-batch', () => {
    const pos = cursorPosition(order, 'z')!
    expect(pos.isLast).toBe(true)
    expect(pos.nextId).toBeNull()
    expect(pos.prevId).toBe('y')
  })

  it('single-item batch: no arrows at all', () => {
    const pos = cursorPosition(['only'], 'only')!
    expect(pos.isFirst).toBe(true)
    expect(pos.isLast).toBe(true)
    expect(pos.prevId).toBeNull()
    expect(pos.nextId).toBeNull()
    expect(pos.total).toBe(1)
  })

  it('missing id (bad deep link / post-entry arrival) → null fallback', () => {
    expect(cursorPosition(order, 'ghost')).toBeNull()
    expect(cursorPosition([], 'ghost')).toBeNull()
  })
})
