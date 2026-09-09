import { describe, expect, it } from 'vitest'

import {
  barSegments,
  completionReached,
  pollCadenceMs,
  selectHeadline,
  uploadingCount,
} from './batch-dashboard'
import { listActionLine, listBarSegments } from './batch-list'
import { batchStatusLabel } from '@/copy/batch'
import type { Partition } from './batch-partition'

/**
 * Stage A (UPLOAD_LATENCY_PLAN.md) — the client half of "a batch can say
 * still uploading".
 *
 * THE DEFECT (Defect D). B9 intake makes COUNT(jobs) the denominator, so
 * mid-upload a ten-file batch with one file in reads total 1 / transcribing 0 /
 * transcribed 0 — and every completion gate here fires over an upload that has
 * barely started. It does not blur the number; it keeps computing and returns a
 * confident wrong one (§3.5a). Migration 025 supplies `uploading`; these tests
 * pin that every gate now reads it.
 *
 * `uploading` is OPTIONAL on the wire and read as `?? 0` everywhere. That is not
 * a fallback: a server without the field has no declared count, so zero really
 * is the number of outstanding declared files on it. Both deploy orders are
 * therefore safe, and the "absent" cases below pin exactly that.
 */

const rollup = (over: Record<string, number | null> = {}) => ({
  transcribing: 0,
  transcribed: 0,
  grading: 0,
  approved: 0,
  transcription_failed: 0,
  total: 0,
  ...over,
}) as never

const listRollup = (over: Record<string, number | null> = {}) => ({
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
}) as never

const emptyPartition = (): Partition => ({
  identityPills: [],
  identityOnly: [],
  contentFlagged: [],
  touchedClean: [],
  clean: [],
  approved: [],
  unmatchedItems: [],
} as unknown as Partition)

// ---------------------------------------------------------------------------
// uploadingCount — the one read
// ---------------------------------------------------------------------------

describe('uploadingCount', () => {
  it('reads the declared-but-unlanded count', () => {
    expect(uploadingCount(rollup({ uploading: 4 }))).toBe(4)
  })

  it('treats an absent field as zero — an older server tracks no declaration', () => {
    expect(uploadingCount(rollup())).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// completionReached / pollCadenceMs — the gates Defect D fooled
// ---------------------------------------------------------------------------

describe('completionReached', () => {
  it('is FALSE while declared files are still on the wire (Defect D)', () => {
    // The exact shape that used to fire the completion hero: the denominator
    // is honest (10), but nothing has landed, so every other counter is 0.
    expect(completionReached({
      rollup: rollup({ uploading: 10, total: 10 }),
      active_jobs: [],
    })).toBe(false)
  })

  it('is FALSE with nine outstanding even when the one landed file is approved', () => {
    expect(completionReached({
      rollup: rollup({ uploading: 9, approved: 1, total: 10 }),
      active_jobs: [],
    })).toBe(false)
  })

  it('is TRUE once the last file lands and everything else is terminal', () => {
    expect(completionReached({
      rollup: rollup({ uploading: 0, approved: 10, total: 10 }),
      active_jobs: [],
    })).toBe(true)
  })

  it('is unchanged for a payload with no uploading field at all', () => {
    expect(completionReached({
      rollup: rollup({ approved: 3, total: 3 }),
      active_jobs: [],
    })).toBe(true)
  })

  it('is FALSE when declared files never arrived — dead is not done', () => {
    // This assertion is INVERTED from its first version, which pinned the
    // defect: `not_received` files are not in flight, so the original reading
    // was "nothing is moving ⇒ complete". But `total` is the DECLARED count,
    // so the completion hero then announced «כל 3 המבחנים אושרו» over a batch
    // that received one. A batch missing files it was promised is not done.
    expect(completionReached({
      rollup: rollup({ uploading: 0, not_received: 2, approved: 1, total: 3 }),
      active_jobs: [],
    })).toBe(false)
  })
})

describe('pollCadenceMs', () => {
  it('keeps polling at 3s while files are still uploading', () => {
    expect(pollCadenceMs({
      rollup: rollup({ uploading: 5, total: 5 }), active_jobs: [],
    })).toBe(3000)
  })

  it('stops once nothing is uploading, transcribing or grading', () => {
    expect(pollCadenceMs({
      rollup: rollup({ approved: 2, total: 2 }), active_jobs: [],
    })).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// The bars — one visual language across dashboard and list
// ---------------------------------------------------------------------------

describe('barSegments (dashboard)', () => {
  it('gives uploading its own segment, ordered before transcription', () => {
    const segs = barSegments(emptyPartition(), rollup({
      uploading: 4, transcribing: 2, total: 6,
    }))
    expect(segs).toEqual([
      { kind: 'uploading', count: 4 },
      { kind: 'moving', count: 2 },
    ])
  })

  it('separates never-arrived from failed — dead, but not the same death', () => {
    const segs = barSegments(emptyPartition(), rollup({
      not_received: 2, transcription_failed: 1, total: 3,
    }))
    expect(segs).toEqual([
      { kind: 'failed', count: 1 },
      { kind: 'not_received', count: 2 },
    ])
  })

  it('renders nothing new for a legacy payload', () => {
    expect(barSegments(emptyPartition(), rollup({ transcribing: 1, total: 1 })))
      .toEqual([{ kind: 'moving', count: 1 }])
  })
})

describe('listBarSegments', () => {
  it('draws the same split as the dashboard bar', () => {
    expect(listBarSegments(listRollup({
      uploading: 3, transcribing: 1, not_received: 1, transcription_failed: 1,
      total: 6,
    }))).toEqual([
      { kind: 'uploading', count: 3 },
      { kind: 'moving', count: 1 },
      { kind: 'failed', count: 1 },
      { kind: 'not_received', count: 1 },
    ])
  })
})

// ---------------------------------------------------------------------------
// The list's action line — the one batch surface with no upload lane
// ---------------------------------------------------------------------------

describe('listActionLine', () => {
  it('says how many files are still uploading', () => {
    const line = listActionLine(listRollup({ uploading: 4, total: 4 }))
    expect(line).toEqual({ kind: 'uploading', text: '4 קבצים בהעלאה' })
  })

  it('uses the singular form for one file', () => {
    expect(listActionLine(listRollup({ uploading: 1, total: 1 })))
      .toEqual({ kind: 'uploading', text: 'קובץ אחד בהעלאה' })
  })

  it('prefers transcription when both are moving — it is further along', () => {
    const line = listActionLine(listRollup({ uploading: 2, transcribing: 3, total: 5 }))
    expect(line?.kind).toBe('transcribing')
  })

  it('yields to needs-eyes: work she can do outranks files in transit', () => {
    const line = listActionLine(listRollup({
      transcribed: 2, needs_eyes: 2, total: 5,
    }))
    expect(line?.kind).toBe('eyes')
  })

  it('reports never-arrived files in their own words, not as a failure', () => {
    const line = listActionLine(listRollup({
      not_received: 2, approved: 1, total: 3,
    }))
    expect(line).toEqual({
      kind: 'not_received',
      text: '2 קבצים לא הגיעו — אפשר להעלות אותם שוב',
    })
  })

  it('still says "all approved" when nothing was left behind', () => {
    expect(listActionLine(listRollup({ approved: 3, total: 3 })))
      .toEqual({ kind: 'done', text: 'הכל אושר ✓' })
  })
})

// ---------------------------------------------------------------------------
// The status chip
// ---------------------------------------------------------------------------

describe('batchStatusLabel', () => {
  it('says בהעלאה when the only thing happening is files arriving', () => {
    expect(batchStatusLabel('in_progress', { uploading: 3 })).toBe('בהעלאה')
  })

  it('prefers בתמלול when documents are actually being read', () => {
    expect(batchStatusLabel('in_progress', { uploading: 3, transcribing: 1 }))
      .toBe('בתמלול')
  })

  it('never claims she is holding the batch up while files are in transit', () => {
    // The pre-Stage-A answer for this shape was 'ממתין להחלטות'.
    expect(batchStatusLabel('in_progress', { uploading: 2 }))
      .not.toBe('ממתין להחלטות')
  })

  it('is unchanged when nothing is in flight at all', () => {
    expect(batchStatusLabel('in_progress', {})).toBe('ממתין להחלטות')
  })
})

// ---------------------------------------------------------------------------
// The headline
// ---------------------------------------------------------------------------

describe('selectHeadline', () => {
  it('reports the upload tail when nothing else is pending', () => {
    expect(selectHeadline(emptyPartition(), rollup({ uploading: 3, total: 3 })))
      .toBe('3 קבצים עדיין בהעלאה')
  })

  it('does not claim "כמעט שם" for an upload that may have barely started', () => {
    const headline = selectHeadline(emptyPartition(), rollup({ uploading: 9, total: 10 }))
    expect(headline).not.toContain('כמעט שם')
  })

  it('lets the transcription tail win when both are moving', () => {
    expect(selectHeadline(emptyPartition(), rollup({
      uploading: 1, transcribing: 1, total: 2,
    }))).toContain('בתמלול')
  })

  it('does not announce completion while files are still arriving', () => {
    const p = emptyPartition()
    ;(p.approved as unknown[]).push({})
    expect(selectHeadline(p, rollup({ uploading: 4, approved: 1, total: 5 })))
      .toBe('4 קבצים עדיין בהעלאה')
  })
})

// ---------------------------------------------------------------------------
// Stage A review fixes — the three surfaces that consumed the redefined
// `total` / the new `not_received` and published something they could not
// stand behind.
// ---------------------------------------------------------------------------

describe('review fixes', () => {
  it('does NOT call a batch complete when its files never arrived', () => {
    // After the 90-minute backstop an abandoned ten-file batch reads
    // uploading 0 with every other counter 0. Without this clause the green ✓
    // hero rendered «כל 10 המבחנים אושרו» over a batch that received nothing,
    // three lines under a red «נכשל» chip. Before Stage A it was unreachable
    // (total was COUNT(jobs), so the `total > 0` guard held); making `total`
    // the DECLARED count is what opened it.
    expect(completionReached({
      rollup: rollup({ uploading: 0, not_received: 10, total: 10 }),
      active_jobs: [],
    })).toBe(false)
  })

  it('still completes a batch where everything actually arrived', () => {
    expect(completionReached({
      rollup: rollup({ approved: 10, total: 10 }),
      active_jobs: [],
    })).toBe(true)
  })

  it('gives never-arrived files their own segment, never the failure hue', () => {
    // The dashboard said «נכשל» while the list said «לא הגיעו … אפשר להעלות
    // אותם שוב», and the red count pointed at an EMPTY FailedZone — a file
    // that never arrived has no job row, no filename and no retry.
    const segs = barSegments(emptyPartition(), rollup({
      not_received: 2, transcription_failed: 1, total: 3,
    }))
    expect(segs).toEqual([
      { kind: 'failed', count: 1 },
      { kind: 'not_received', count: 2 },
    ])
  })

  it('draws the same distinction on the list bar', () => {
    expect(listBarSegments(listRollup({
      not_received: 2, transcription_failed: 1, total: 3,
    }))).toEqual([
      { kind: 'failed', count: 1 },
      { kind: 'not_received', count: 2 },
    ])
  })
})

describe('the empty-batch zombie (Stage B review fix)', () => {
  it('stops polling a batch that received nothing and expects nothing', () => {
    // Newly reachable: every selected file is rejected 422, the client
    // re-declares `expected = 0`, so `total` is 0 — and `completionReached`
    // can never be true because of its own `total > 0` guard. Before Stage B
    // she never landed here, because the continue button required a landed
    // file. Left alone the dashboard polls a dead batch every 3s forever.
    expect(pollCadenceMs({ rollup: rollup({ total: 0 }), active_jobs: [] })).toBeNull()
  })

  it('keeps polling an empty batch that is still expecting files', () => {
    expect(pollCadenceMs({
      rollup: rollup({ total: 2, uploading: 2 }), active_jobs: [],
    })).toBe(3000)
  })

  it('keeps polling while a job is in flight even with an empty rollup', () => {
    expect(pollCadenceMs({
      rollup: rollup({ total: 0 }), active_jobs: [{ state: 'queued' }],
    })).toBe(3000)
  })
})
