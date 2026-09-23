/**
 * P2 — dashboard selectors (zero-mock):
 * barSegments (D2), the D6 chip counters, the D7 elapsed formatter, the D12
 * cadence selector, the D10 transcription-completion trigger and the §5.1F
 * sign-off trigger. All strings come from the C1 copy module — tests assert
 * through it, never inline copies.
 */
import { describe, expect, it } from 'vitest'

import {
  barSegments,
  completionReached,
  sessionCompletionMinutes,
  formatElapsed,
  missingAnswersCount,
  pollCadenceMs,
  signOffReached,
  unclearCount,
} from '@/utils/batch-dashboard'
import { partitionItems, type PartitionItem } from '@/utils/batch-partition'

function item(id: string, over: Partial<PartitionItem> = {}): PartitionItem {
  return {
    transcription_id: id,
    filename: `${id}.pdf`,
    transcription_status: 'transcribed',
    review: null,
    student_name_suggestion: null,
    flag_verdict: { review_needed: false, reasons: [] },
    ...over,
  }
}

const identity = (id: string, name: string) =>
  item(id, {
    flag_verdict: { review_needed: true, reasons: ['student_unassigned'] },
    student_name_suggestion: name,
  })
const flagged = (id: string) =>
  item(id, { flag_verdict: { review_needed: true, reasons: ['missing_answers'] } })
const approved = (id: string) => item(id, { transcription_status: 'approved' })

const rollup = (over: Record<string, number> = {}) => ({
  transcribing: 0, transcribed: 0, approved_transcription: 0, grading: 0,
  draft: 0, approved: 0, failed: 0, transcription_failed: 0, total: 0, ...over,
})

// ---------------------------------------------------------------------------
// D3's `selectHeadline` suite is GONE with the function (§5.1B).
//
// The headline said the same KIND of thing as the turn line, derived
// separately and rendered two lines apart. The turn line is now the only
// sentence of its kind on the page and is covered, row by row, in
// `batch-stage.test.ts` — one derivation, one suite. Leaving this one here
// would have been two green suites over two screens that disagreed.
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// D2 — barSegments
// ---------------------------------------------------------------------------

describe('barSegments (D2)', () => {
  it('orders approved · clean · eyes · moving · failed and drops zero segments', () => {
    const p = partitionItems([
      approved('a1'), item('c1'),
      flagged('f1'), identity('i1', 'דנה לוי'),
      item('tc', { review: { answers: [] } }),
    ])
    const segs = barSegments(p, rollup({ transcribing: 2, transcription_failed: 1, total: 8 }))
    expect(segs).toEqual([
      { kind: 'approved', count: 1 },
      // ZC-1 v2 (2026-08-23): the identity-pending item ('דנה לוי' — clean
      // content, new name only, untouched) counts as CLEAN, its home.
      { kind: 'clean', count: 2 },
      { kind: 'eyes', count: 2 },       // contentFlagged + touchedClean
      { kind: 'moving', count: 2 },
      { kind: 'failed', count: 1 },
    ])
  })

  it('all-zero → empty list (bar hidden, no 6px slivers of nothing)', () => {
    expect(barSegments(partitionItems([]), rollup())).toEqual([])
  })

  it('single-state batch → one segment', () => {
    const p = partitionItems([item('c1'), item('c2')])
    expect(barSegments(p, rollup({ total: 2 }))).toEqual([{ kind: 'clean', count: 2 }])
  })
})

// ---------------------------------------------------------------------------
// D6 — chip counters
// ---------------------------------------------------------------------------

const draftWith = (answers: Array<[number, string | null, string]>) => ({
  schema_version: '1.0',
  student_name_suggestion: null,
  page_count: 1,
  answers: answers.map(([q, sub, text]) => ({
    question_number: q, sub_question_id: sub, answer_text: text,
    confidence: 0.9, page_numbers: [1],
  })),
  annotations: [],
  model_version: null,
  transcription_duration_ms: null,
})

describe('D6 counters', () => {
  it('missingAnswersCount excludes selection-explained emptiness', () => {
    // SATISFIED group (2 of choose-2 attempted): the remaining empty is
    // EXPECTED — not missing. Without groups it counts as missing.
    const satisfied = draftWith([[1, null, ''], [2, null, 'תשובה'], [3, null, 'תשובה פה']])
    const groups = [{ choose_k: 2, question_numbers: [1, 2, 3] }]
    expect(missingAnswersCount(satisfied, groups)).toBe(0)
    expect(missingAnswersCount(satisfied, [])).toBe(1)

    // UNDER-answered group (1 of choose-2): the student still owes one —
    // NOTHING is expected-empty, both empties count (mirrors the server
    // triage + the surface's pinned suppress-nothing-when-under-answered).
    const under = draftWith([[1, null, ''], [2, null, ''], [3, null, 'תשובה פה']])
    expect(missingAnswersCount(under, groups)).toBe(2)
  })

  it('unclearCount sums [?] occurrences across answers', () => {
    const draft = draftWith([[1, null, 'x = [?] + [?]'], [2, null, 'נקי'], [3, 'א', '[?]']])
    expect(unclearCount(draft)).toBe(3)
  })
})

// ---------------------------------------------------------------------------
// D7 — elapsed formatter
// ---------------------------------------------------------------------------

describe('formatElapsed (D7)', () => {
  it('formats mm:ss', () => {
    const t0 = new Date('2026-08-17T10:00:00Z')
    expect(formatElapsed('2026-08-17T09:58:47Z', t0)).toBe('1:13')
    expect(formatElapsed('2026-08-17T09:59:59Z', t0)).toBe('0:01')
  })

  it('clamps clock skew at 0:00', () => {
    const t0 = new Date('2026-08-17T10:00:00Z')
    expect(formatElapsed('2026-08-17T10:00:05Z', t0)).toBe('0:00')
  })
})

// ---------------------------------------------------------------------------
// D1 — relative time
// ---------------------------------------------------------------------------

describe('relativeTimeHe (D1)', () => {
  const now = new Date('2026-08-17T12:00:00Z')
  it('coarse Hebrew buckets', async () => {
    const { relativeTimeHe } = await import('@/utils/batch-dashboard')
    expect(relativeTimeHe('2026-08-17T11:59:40Z', now)).toBe('לפני רגע')
    expect(relativeTimeHe('2026-08-17T11:56:00Z', now)).toBe('לפני 4 דקות')
    expect(relativeTimeHe('2026-08-17T09:00:00Z', now)).toBe('לפני 3 שעות')
    expect(relativeTimeHe('2026-08-15T12:00:00Z', now)).toBe('לפני 2 ימים')
  })
})

// ---------------------------------------------------------------------------
// D12 — cadence · D10 — completion trigger
// ---------------------------------------------------------------------------

describe('pollCadenceMs (D12)', () => {
  const activeBatch = { rollup: rollup({ transcribing: 1, total: 3 }), active_jobs: [] }
  it('3s while transcription decisions pending', () => {
    expect(pollCadenceMs({
      rollup: rollup({ transcribed: 2, total: 3 }), active_jobs: [],
    })).toBe(3000)
    expect(pollCadenceMs(activeBatch)).toBe(3000)
  })
  it('5s while only grading is in flight', () => {
    expect(pollCadenceMs({
      rollup: rollup({ grading: 2, approved_transcription: 2, total: 2 }),
      active_jobs: [],
    })).toBe(5000)
  })
  it('stops when nothing moves', () => {
    // A signed batch has a gate-passed transcription behind every grade —
    // `approved_transcription` is what the wire actually carries here, and
    // the accounting below is what tells this apart from a torn snapshot.
    expect(pollCadenceMs({
      rollup: rollup({ approved_transcription: 2, approved: 2, total: 2 }), active_jobs: [],
    })).toBeNull()
  })

  it('KEEPS polling over a document the rollup cannot place (the torn snapshot)', () => {
    // 2026-09-19: a completed job whose transcription row was not yet visible
    // produced `total 1` with every other count zero. That is byte-identical
    // to "the one document already passed the gate", so this returned null,
    // the dashboard stopped asking, and it froze on «הושלם» over an unreviewed
    // paper. An unaccounted document is still moving — 3s, like any other.
    expect(pollCadenceMs({
      rollup: rollup({ total: 1 }), active_jobs: [],
    })).toBe(3000)
  })
})

describe('completionReached (D10)', () => {
  it('requires no transcribing, no transcribed, no active jobs, and rows', () => {
    expect(completionReached({
      rollup: rollup({ approved_transcription: 3, approved: 3, total: 3 }), active_jobs: [],
    })).toBe(true)
    expect(completionReached({
      rollup: rollup({ transcribing: 1, total: 3 }), active_jobs: [],
    })).toBe(false)
    expect(completionReached({
      rollup: rollup({ transcribed: 1, total: 3 }), active_jobs: [],
    })).toBe(false)
    expect(completionReached({
      rollup: rollup({ approved_transcription: 3, approved: 3, total: 3 }),
      active_jobs: [{ state: 'queued' }],
    })).toBe(false)
    expect(completionReached({ rollup: rollup(), active_jobs: [] })).toBe(false)
  })

  it('is NEVER inferred from absence: a document the rollup cannot place is not done', () => {
    // The identity `uploading + not_received + transcribing + transcription_failed
    // + transcribed + approved_transcription === total` holds on every
    // consistent server snapshot. The one way it fails is a torn read — and a
    // torn read is precisely a document that has passed nothing.
    expect(completionReached({
      rollup: rollup({ total: 1 }), active_jobs: [],
    })).toBe(false)
    // Two of three accounted for, one not: still not done, whatever else is 0.
    expect(completionReached({
      rollup: rollup({ approved_transcription: 2, approved: 2, total: 3 }), active_jobs: [],
    })).toBe(false)
    // …and the fully accounted-for version of the same batch IS done.
    expect(completionReached({
      rollup: rollup({ approved_transcription: 3, approved: 3, total: 3 }), active_jobs: [],
    })).toBe(true)
  })
})

describe('sessionCompletionMinutes (C2) — the hero never reports a week as minutes', () => {
  const created = '2026-08-14T09:00:00.000Z'          // genuinely days old
  const now = new Date('2026-08-21T09:00:00.000Z').getTime()   // +7 days

  it('OMITS the duration when this session never saw the batch running (a revisit)', () => {
    // The exact bug: first observation IS now, so elapsed-since-created would
    // render 10080 דקות on the peak-end moment.
    expect(sessionCompletionMinutes(created, now, false)).toBeNull()
  })

  it('reports the real elapsed time when this session watched it complete', () => {
    const startedThisSession = new Date(now - 26 * 60_000).toISOString()
    expect(sessionCompletionMinutes(startedThisSession, now, true)).toBe(26)
  })

  it('never reports zero — a sub-minute batch still took a minute of her life', () => {
    const justNow = new Date(now - 4_000).toISOString()
    expect(sessionCompletionMinutes(justNow, now, true)).toBe(1)
  })

  it('omits rather than throwing on an unparseable timestamp', () => {
    expect(sessionCompletionMinutes('not-a-date', now, true)).toBeNull()
  })
})

describe('E1 (closeout) — nothing promises grading it cannot deliver', () => {
  it('the completed lane has the same zero-guard as its subordinate sibling', async () => {
    const { GradingLane } = await import('@/components/batch/GradingLane')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const React = await import('react')
    // Both variants, both counts zero → nothing rendered.
    for (const variant of ['completed', 'subordinate'] as const) {
      const html = renderToStaticMarkup(
        React.createElement(GradingLane, {
          variant, draftCount: 0, gradingCount: 0, onOpenGrades: () => {},
        }),
      )
      expect(html, `${variant} lane rendered with 0/0`).toBe('')
    }
  })

  it('the lane is silenced entirely until grading is proven live', async () => {
    const { SHOW_GRADING_LANE } = await import('@/lib/flags')
    // A deliberate, reversible ruling — not an accident. When grading works,
    // flipping this returns the lane WITH its zero-guard intact.
    expect(SHOW_GRADING_LANE).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// §5.1F — the sign-off trigger: the ONE moment the flow celebrates.
// ---------------------------------------------------------------------------

describe('signOffReached (§5.1F)', () => {
  const batch = (over: Record<string, number>) => ({ rollup: rollup(over) })

  it('fires only when every test in the batch is SIGNED', () => {
    expect(signOffReached(batch({ total: 3, approved: 3 }))).toBe(true)
  })

  it('does NOT fire on transcription completion — the mid-flow hero this replaced', () => {
    // Every transcription approved, every grade still a draft. `completionReached`
    // says true here, which is exactly why it could not be the celebration trigger.
    const transcriptionsDone = batch({ total: 3, approved_transcription: 3, draft: 3 })
    expect(completionReached(transcriptionsDone)).toBe(true)
    expect(signOffReached(transcriptionsDone)).toBe(false)
  })

  it('does not fire while one signature is outstanding', () => {
    expect(signOffReached(batch({ total: 3, approved: 2, draft: 1 }))).toBe(false)
  })

  it('an empty batch is not a finished one', () => {
    expect(signOffReached(batch({ total: 0, approved: 0 }))).toBe(false)
  })
})
