import { describe, expect, it } from 'vitest'
import { untranscribedResidue } from './batch-residue'

const T0 = Date.parse('2026-08-04T10:00:00Z')
const min = (n: number) => n * 60_000
const iso = (msFromT0: number) => new Date(T0 + msFromT0).toISOString()

describe('untranscribedResidue — Δ15 progress-based horizon', () => {
  it('no missing rows → never visible', () => {
    const r = untranscribedResidue({
      testCount: 3, batchCreatedAt: iso(0),
      itemCreatedAts: [iso(1), iso(2), iso(3)], now: T0 + min(60),
    })
    expect(r).toEqual({ missing: 0, visible: false })
  })

  it('a healthy large batch mid-fan-out never shows the line (progress resets the clock)', () => {
    // 40-test batch, 12 minutes in, rows still landing: newest row 2 min ago.
    const r = untranscribedResidue({
      testCount: 40, batchCreatedAt: iso(0),
      itemCreatedAts: Array.from({ length: 8 }, (_, i) => iso(min(i + 3))),
      now: T0 + min(12),
    })
    expect(r.missing).toBe(32)
    expect(r.visible).toBe(false)   // last progress at +10min, only 2min ago
  })

  it('no new row for over 10 minutes → genuinely stuck → visible', () => {
    const r = untranscribedResidue({
      testCount: 3, batchCreatedAt: iso(0),
      itemCreatedAts: [iso(min(1)), iso(min(2))], now: T0 + min(13),
    })
    expect(r).toEqual({ missing: 1, visible: true })   // last progress +2min, 11min ago
  })

  it('zero rows: the batch creation time itself is the progress anchor', () => {
    const fresh = untranscribedResidue({
      testCount: 5, batchCreatedAt: iso(0), itemCreatedAts: [], now: T0 + min(9),
    })
    expect(fresh.visible).toBe(false)
    const stuck = untranscribedResidue({
      testCount: 5, batchCreatedAt: iso(0), itemCreatedAts: [], now: T0 + min(11),
    })
    expect(stuck).toEqual({ missing: 5, visible: true })
  })

  it('exactly at the horizon boundary is not yet visible (strictly past)', () => {
    const r = untranscribedResidue({
      testCount: 2, batchCreatedAt: iso(0), itemCreatedAts: [iso(0)], now: T0 + min(10),
    })
    expect(r.visible).toBe(false)
  })
})
