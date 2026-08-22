import { describe, expect, it } from 'vitest'

import { listActionLine, listBarSegments } from './batch-list'

/**
 * P5/L1 — the list row's two derivations, both pure. Everything here is
 * computed from `rollup` ALONE: the list payload carries no `transcriptions[]`,
 * so the clean|eyes split the dashboard draws is NOT available (the phase's
 * open decision). The interim tells a coarser truth honestly; it never
 * invents the split.
 */

const rollup = (over: Partial<Record<string, number | null>> = {}) => ({
  transcribing: 0,
  transcribed: 0,
  approved_transcription: 0,
  grading: 0,
  draft: 0,
  approved: 0,
  failed: 0,
  transcription_failed: 0,
  needs_eyes: 0,
  total: 0,
  ...over,
})

describe('listBarSegments — the REAL clean|eyes split (Ruling 1)', () => {
  it('splits transcribed into bulk-acceptable vs needs-eyes using the server count', () => {
    // 2 approved, 5 awaiting: 2 flagged/touched + 3 bulk-acceptable, 3 in
    // flight, 1 dead.
    const segs = listBarSegments(rollup({
      approved: 2, transcribed: 5, needs_eyes: 2,
      transcribing: 3, transcription_failed: 1, total: 11,
    }))
    expect(segs).toEqual([
      { kind: 'approved', count: 2 },
      { kind: 'clean', count: 3 },     // 5 transcribed − 2 needing eyes
      { kind: 'eyes', count: 2 },
      { kind: 'moving', count: 3 },
      { kind: 'failed', count: 1 },
    ])
  })

  it('clamps a server count that exceeds transcribed (never a negative clean slice)', () => {
    const segs = listBarSegments(rollup({ transcribed: 2, needs_eyes: 9, total: 2 }))
    expect(segs).toEqual([{ kind: 'eyes', count: 2 }])
  })

  it('counts every post-transcription decision state as clean-waiting (nothing vanishes mid-pipeline)', () => {
    // approved_transcription/grading/draft are past the transcription gate but
    // not yet fully approved — they must still occupy the bar, or a batch in
    // grading would render as half-empty.
    const segs = listBarSegments(rollup({
      transcribed: 1, approved_transcription: 2, grading: 3, draft: 4, approved: 5, total: 15,
    }))
    expect(segs).toEqual([
      { kind: 'approved', count: 5 },
      { kind: 'clean', count: 10 },    // 2+3+4 in grading + 1 bulk-acceptable
    ])
  })

  it('drops zero-count segments and returns [] for an empty batch', () => {
    expect(listBarSegments(rollup({ approved: 3, total: 3 })))
      .toEqual([{ kind: 'approved', count: 3 }])
    expect(listBarSegments(rollup())).toEqual([])
  })
})

describe('listActionLine — one line per §3.2, precedence top-down', () => {
  it('transcribing wins: the batch is still arriving', () => {
    expect(listActionLine(rollup({ transcribing: 4, transcribed: 2, total: 6 })))
      .toEqual({ kind: 'transcribing', text: '4 בתמלול' })
    expect(listActionLine(rollup({ transcribing: 1, total: 1 })))
      .toEqual({ kind: 'transcribing', text: 'מבחן אחד בתמלול' })   // AM3 proposed
  })

  it('all approved → the §3.2 completion line', () => {
    expect(listActionLine(rollup({ approved: 6, total: 6 })))
      .toEqual({ kind: 'done', text: 'הכל אושר ✓' })
  })

  it('needs-eyes wins and reads §3.2 verbatim — the sharp signal, not a paraphrase', () => {
    expect(listActionLine(rollup({ transcribed: 5, needs_eyes: 4, approved: 1, total: 6 })))
      .toEqual({ kind: 'eyes', text: '4 דורשים עיון' })
    expect(listActionLine(rollup({ transcribed: 1, needs_eyes: 1, total: 1 })))
      .toEqual({ kind: 'eyes', text: 'מבחן אחד דורש עיון' })   // AM3
  })

  it('all-clean-but-unapproved still owes her a bulk accept (pending, not done)', () => {
    expect(listActionLine(rollup({ transcribed: 5, needs_eyes: 0, total: 5 })))
      .toEqual({ kind: 'pending', text: '5 ממתינים להחלטה' })
  })

  it('a batch whose work is entirely in grading is NOT "all approved"', () => {
    // The completion line must mean COMPLETE — draft/grading rows still owe
    // the teacher a grade review.
    expect(listActionLine(rollup({ approved: 2, draft: 3, grading: 1, total: 6 }))?.kind)
      .toBe('pending')
  })

  it('failures alone → the failure line, never a false completion', () => {
    expect(listActionLine(rollup({ approved: 2, transcription_failed: 1, total: 3 })))
      .toEqual({ kind: 'failed', text: 'תמלול אחד נכשל' })
  })

  it('an empty batch has no action line at all', () => {
    expect(listActionLine(rollup())).toBeNull()
  })
})


describe('degrade by omission — needs_eyes === null (owner ruling, closeout)', () => {
  it('falls back to ONE merged awaiting segment instead of inventing a split', () => {
    const segs = listBarSegments(rollup({
      approved: 1, transcribed: 6, needs_eyes: null, total: 7,
    }))
    expect(segs).toEqual([
      { kind: 'approved', count: 1 },
      { kind: 'eyes', count: 6 },   // merged: coarser, never wrong
    ])
    // and specifically NOT a confident zero-eyes reading
    expect(segs.find((s) => s.kind === 'clean')).toBeUndefined()
  })

  it('omits the needs-eyes ACTION LINE too, falling back to the merged count', () => {
    expect(listActionLine(rollup({ transcribed: 6, needs_eyes: null, total: 6 })))
      .toEqual({ kind: 'pending', text: '6 ממתינים להחלטה' })
  })

  it('a null count never reads as "all clear"', () => {
    const a = listActionLine(rollup({ transcribed: 3, needs_eyes: null, approved: 1, total: 4 }))
    expect(a?.kind).not.toBe('done')
  })
})
