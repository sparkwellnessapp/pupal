import { describe, expect, it } from 'vitest'

import { barSegments, type RollupLike } from './batch-dashboard'
import { partitionItems, type PartitionItem } from './batch-partition'
import { assignZones, isIdentityPending } from './zone-assignment'

/**
 * ZC-1 (owner directive 2026-08-22, REFINED 2026-08-23): every uploaded
 * transcription lands in EXACTLY ONE actionable zone — the needs-eyes rows
 * or the clean panel:
 *
 *     transcribed = Σ(eyesRows) + Σ(cleanRows)
 *
 * The identity wave is an accelerator OVERLAY, never a home. v1 sent
 * identity-pending items (ONLY flag = a successfully-extracted NEW name —
 * דן בסיוק's shape) to the EYES rows; the owner refined: their home is the
 * CLEAN panel (which carries the per-item link), their name rides the wave,
 * and they are excluded from the bulk-accept count until the student exists.
 * The sum is unchanged — v1's real bug (an item with NO home) stays dead.
 */

let seq = 0
function item(over: Partial<PartitionItem> = {}): PartitionItem {
  seq += 1
  return {
    transcription_id: `t-${seq}`,
    filename: `f${seq}.pdf`,
    transcription_status: 'transcribed',
    review: null,
    student_name_suggestion: null,
    flag_verdict: { review_needed: false, reasons: [] },
    ...over,
  }
}

const flagged = (reasons: string[], over: Partial<PartitionItem> = {}) =>
  item({ flag_verdict: { review_needed: true, reasons }, ...over })

function assertZC1(items: PartitionItem[]) {
  const z = assignZones(items)
  const transcribed = items.filter((i) => i.transcription_status === 'transcribed')
  expect(z.eyesRows.length + z.cleanRows.length,
    'ZC-1: transcribed = Σ(eyesRows) + Σ(cleanRows)').toBe(transcribed.length)
  expect(z.eyesRows.length + z.cleanRows.length + z.approved.length).toBe(items.length)
  // exactly-one: no item in two zones
  const ids = [...z.eyesRows, ...z.cleanRows, ...z.approved].map((i) => i.transcription_id)
  expect(new Set(ids).size).toBe(ids.length)
  return z
}

describe('assignZones — ZC-1 membership', () => {
  it('THE rule (v2): student_unassigned-only (clean content, new name) is a CLEAN row, wave overlaid', () => {
    // דן בסיוק: no annotations, suggestion extracted, student not yet created.
    const dan = flagged(['student_unassigned'], { student_name_suggestion: 'דן בסיוק' })
    const z = assertZC1([dan])
    expect(z.cleanRows.map((i) => i.transcription_id)).toEqual([dan.transcription_id])
    expect(z.eyesRows).toEqual([])
    // …but NOT bulk-acceptable until the student exists.
    expect(isIdentityPending(dan)).toBe(true)
  })

  it('touched identity-pending loses its pending status: Δ1 wins, it needs her eyes', () => {
    const touched = flagged(['student_unassigned'], { review: { answers: [] } })
    const z = assertZC1([touched])
    expect(z.eyesRows).toHaveLength(1)
    expect(isIdentityPending(touched)).toBe(false)
  })

  it('student_unmatched-only stays an eyes row (was already included)', () => {
    const z = assertZC1([flagged(['student_unmatched'])])
    expect(z.eyesRows).toHaveLength(1)
  })

  it('both identity reasons → EYES (unmatched means she must identify by hand)', () => {
    const z = assertZC1([flagged(['student_unassigned', 'student_unmatched'])])
    expect(z.eyesRows).toHaveLength(1)
    expect(z.cleanRows).toEqual([])
  })

  it('content + identity flags → one row, once (never duplicated across buckets)', () => {
    const z = assertZC1([flagged(['unparseable', 'student_unassigned'])])
    expect(z.eyesRows).toHaveLength(1)
  })

  it('touched-clean (saved overlay, clean verdict) is an eyes row (Δ1: not bulk-acceptable)', () => {
    const touched = item({ review: { answers: [] } })
    const z = assertZC1([touched])
    expect(z.eyesRows).toHaveLength(1)
    expect(z.cleanRows).toEqual([])
  })

  it('clean, matched, untouched → the clean panel', () => {
    const z = assertZC1([item()])
    expect(z.cleanRows).toHaveLength(1)
    expect(z.eyesRows).toEqual([])
  })

  it('approved items belong to neither actionable zone', () => {
    const z = assertZC1([item({ transcription_status: 'approved' })])
    expect(z.approved).toHaveLength(1)
    expect(z.eyesRows.length + z.cleanRows.length).toBe(0)
  })

  it('empty batch: all zones empty, sum holds trivially', () => {
    assertZC1([])
  })
})

// Historical note: in the live batch these four carried `code_lint`, which
// was retired as a triage reason on 2026-09-06 (too noisy). The shape this
// pins — a content flag + an identity flag is ONE eyes row, never two — is
// what matters, so the fixture uses a reason the server still emits.
describe("assignZones — the owner's 6-fixture batch, exactly", () => {
  it('4 content-flagged + 1 identity-pending + 1 clean-matched → 4 eyes + 2 clean = 6', () => {
    const items = [
      flagged(['unparseable', 'student_unassigned'], { filename: 'איתי קראפט.pdf' }),
      flagged(['unparseable', 'student_unassigned'], { filename: 'דין עזרא.pdf' }),
      flagged(['unparseable', 'student_unassigned'], { filename: 'יהלי כהן.pdf' }),
      flagged(['unparseable', 'student_unassigned'], { filename: 'טל גורבן.pdf' }),
      flagged(['student_unassigned'], { filename: 'דן בסיוק.pdf', student_name_suggestion: 'דן בסיוק' }),
      item({ filename: 'איתי כתב.pdf' }),
    ]
    const z = assertZC1(items)
    expect(z.eyesRows).toHaveLength(4)                       // the content-flagged four
    expect(z.cleanRows).toHaveLength(2)                      // matched + pending
    expect(z.cleanRows.map((i) => i.filename)).toContain('איתי כתב.pdf')
    expect(z.cleanRows.map((i) => i.filename)).toContain('דן בסיוק.pdf')
    // The pending row is in clean but NOT in the bulk-acceptable subset.
    expect(z.cleanRows.filter((i) => !isIdentityPending(i))).toHaveLength(1)
  })
})

describe('assignZones — display order and surface parity', () => {
  it('rows group content-flagged, then unmatched-identity, then touched (the D6 shape)', () => {
    const content = flagged(['unparseable'])
    const unmatched = flagged(['student_unmatched'])
    const touched = item({ review: { answers: [] } })
    // payload order deliberately shuffled; a pending item goes to CLEAN.
    const pending = flagged(['student_unassigned'])
    const z = assignZones([touched, pending, unmatched, content])
    expect(z.eyesRows.map((i) => i.transcription_id))
      .toEqual([content, unmatched, touched].map((i) => i.transcription_id))
    expect(z.cleanRows.map((i) => i.transcription_id)).toEqual([pending.transcription_id])
  })

  it("PARITY: the honesty bar's eyes count === eyesRows.length (kills the 10-vs-8 class)", () => {
    const items = [
      flagged(['unparseable']), flagged(['student_unassigned']),
      flagged(['student_unmatched']), item({ review: {} }),
      item(), item({ transcription_status: 'approved' }),
    ]
    const z = assignZones(items)
    const rollup: RollupLike = {
      transcribing: 0, transcribed: 0, grading: 0, approved: 0,
      transcription_failed: 0, total: 0,
    }
    const eyesSegment = barSegments(partitionItems(items), rollup)
      .find((s) => s.kind === 'eyes')
    expect(eyesSegment?.count).toBe(z.eyesRows.length)
  })
})
