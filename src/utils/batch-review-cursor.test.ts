/**
 * OD2/R4/R5/R12 — the append-only cursor, counters, and advance rules.
 * (P3; the e2e freeze-spec rewrite is the integration guard — these are the
 * pure-logic truths.)
 */
import { describe, expect, it } from 'vitest'

import {
  advanceTarget,
  appendNewItems,
  counterInfo,
  initialCursor,
  type FrozenCursor,
} from '@/utils/batch-review-cursor'

const item = (id: string, flagged: boolean) => ({
  transcription_id: id,
  flag_verdict: { review_needed: flagged },
})

const statuses = (m: Record<string, 'transcribed' | 'approved'>) => m

describe('initialCursor + appendNewItems (OD2 — prefix-stable, append-only)', () => {
  it('entry: flagged-first with the boundary at the partition edge', () => {
    const c = initialCursor([item('a', false), item('b', true), item('c', false)])
    expect(c.order).toEqual(['b', 'a', 'c'])
    expect(c.boundary).toBe(1)
  })

  it('flagged arrival lands AT the boundary; clean at the tail; prefix untouched', () => {
    let c = initialCursor([item('a', false), item('b', true), item('c', false)])
    c = appendNewItems(c, [
      item('a', false), item('b', true), item('c', false),   // existing — ignored
      item('d', true),                                        // new flagged
      item('e', false),                                       // new clean
    ])
    expect(c.order).toEqual(['b', 'd', 'a', 'c', 'e'])
    expect(c.boundary).toBe(2)
  })

  it('existing ids NEVER move, even when their verdict flipped in the payload', () => {
    let c = initialCursor([item('b', true), item('a', false)])
    c = appendNewItems(c, [item('b', false), item('a', true)])   // flipped
    expect(c.order).toEqual(['b', 'a'])
    expect(c.boundary).toBe(1)
  })

  it('no-reorder under a shuffled payload: appends keep PAYLOAD order among themselves', () => {
    let c = initialCursor([item('b', true)])
    c = appendNewItems(c, [item('z', false), item('y', true), item('x', true)])
    expect(c.order).toEqual(['b', 'y', 'x', 'z'])
    expect(c.boundary).toBe(3)
  })
})

describe('counterInfo (R5)', () => {
  const cursor: FrozenCursor = { order: ['b', 'd', 'a', 'c'], boundary: 2 }

  it('primary = stable flagged position; secondary = whole-batch position', () => {
    expect(counterInfo(cursor, 'd')).toEqual({ i: 2, F: 2, k: 2, T: 4 })
  })

  it('approved items keep their slot (stability is positional, not status-based)', () => {
    // Nothing in counterInfo consults status — the slot IS the order index.
    expect(counterInfo(cursor, 'b')).toEqual({ i: 1, F: 2, k: 1, T: 4 })
  })

  it('a clean item has NO primary position (i null) — the primary is omitted', () => {
    expect(counterInfo(cursor, 'a')).toEqual({ i: null, F: 2, k: 3, T: 4 })
  })

  it('an OD2 append bumps F and T for everyone', () => {
    const grown = appendNewItems(cursor, [item('n', true)])
    expect(counterInfo(grown, 'b')).toEqual({ i: 1, F: 3, k: 1, T: 5 })
  })

  it('unknown id → null', () => {
    expect(counterInfo(cursor, 'zzz')).toBeNull()
  })
})

describe('advanceTarget (R4 flagged walk · R12 clean walk)', () => {
  const cursor: FrozenCursor = { order: ['f1', 'f2', 'f3', 'c1', 'c2'], boundary: 3 }

  it('advances to the next unapproved flagged, skipping approved', () => {
    const s = statuses({ f1: 'approved', f2: 'approved', f3: 'transcribed', c1: 'transcribed', c2: 'transcribed' })
    expect(advanceTarget(cursor, 'f1', s)).toEqual({ kind: 'item', id: 'f3' })
  })

  it('WRAPS to an earlier skipped flagged item before any interstitial', () => {
    const s = statuses({ f1: 'transcribed', f2: 'approved', f3: 'approved', c1: 'transcribed', c2: 'transcribed' })
    expect(advanceTarget(cursor, 'f3', s)).toEqual({ kind: 'item', id: 'f1' })
  })

  it('all flagged approved + cleans remain → interstitial', () => {
    const s = statuses({ f1: 'approved', f2: 'approved', f3: 'approved', c1: 'transcribed', c2: 'transcribed' })
    expect(advanceTarget(cursor, 'f3', s)).toEqual({ kind: 'interstitial' })
  })

  it('all flagged approved + zero unapproved cleans → straight to dashboard', () => {
    const s = statuses({ f1: 'approved', f2: 'approved', f3: 'approved', c1: 'approved', c2: 'approved' })
    expect(advanceTarget(cursor, 'f3', s)).toEqual({ kind: 'dashboard' })
  })

  it('R12: accept on a CLEAN item advances to the next clean — never into flagged', () => {
    const s = statuses({ f1: 'transcribed', f2: 'transcribed', f3: 'transcribed', c1: 'approved', c2: 'transcribed' })
    expect(advanceTarget(cursor, 'c1', s)).toEqual({ kind: 'item', id: 'c2' })
  })

  it('R12: clean walk exhausted → dashboard (even with flagged remaining)', () => {
    const s = statuses({ f1: 'transcribed', f2: 'transcribed', f3: 'transcribed', c1: 'transcribed', c2: 'approved' })
    expect(advanceTarget(cursor, 'c2', s)).toEqual({ kind: 'dashboard' })
  })
})
