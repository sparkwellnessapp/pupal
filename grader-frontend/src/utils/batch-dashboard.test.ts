/**
 * P2 — dashboard selectors (zero-mock): selectHeadline (D3, §3.2 precedence),
 * barSegments (D2), the D6 chip counters, the D7 elapsed formatter, the D12
 * cadence selector, and the D10 completion trigger. All §3.2 strings come
 * from the C1 copy module — tests assert through it, never inline copies.
 */
import { describe, expect, it } from 'vitest'

import {
  barSegments,
  completionReached,
  sessionCompletionMinutes,
  formatElapsed,
  missingAnswersCount,
  pollCadenceMs,
  selectHeadline,
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
// D3 — selectHeadline, §3.2 precedence top-down
// ---------------------------------------------------------------------------

describe('selectHeadline (§3.2 precedence)', () => {
  it('identity wave wins, with the still-transcribing suffix', () => {
    const p = partitionItems([identity('a', 'נועה שריד'), identity('b', 'איתי כהן')])
    expect(selectHeadline(p, rollup({ transcribing: 3, total: 5 }))).toBe(
      'ויוי זיהתה 2 תלמידים חדשים בכתב היד — בדקי את האיות וצרי את כולם. השאר בדרך.',
    )
  })

  it('identity wave without transcribing omits the suffix (AM3 singular)', () => {
    const p = partitionItems([identity('a', 'נועה שריד')])
    expect(selectHeadline(p, rollup({ total: 1 }))).toBe(
      'ויוי זיהתה תלמיד חדש בכתב היד — בדקי את האיות וצרי אותו.',
    )
  })

  it('steady: both clauses', () => {
    const p = partitionItems([flagged('f1'), flagged('f2'), item('c1'), item('c2'), item('c3')])
    expect(selectHeadline(p, rollup({ total: 5 }))).toBe(
      '2 מבחנים צריכים את העיניים שלך · 3 מוכנים לאישור מרוכז',
    )
  })

  it('steady: clause omitted when its count is 0 (AM3 singular)', () => {
    const onlyFlagged = partitionItems([flagged('f1')])
    expect(selectHeadline(onlyFlagged, rollup({ total: 1 }))).toBe(
      'מבחן אחד צריך את העיניים שלך',
    )
    const onlyClean = partitionItems([item('c1'), item('c2')])
    expect(selectHeadline(onlyClean, rollup({ total: 2 }))).toBe(
      '2 מוכנים לאישור מרוכז',
    )
  })

  it('touchedClean counts toward "needs your eyes" (honesty over flattery)', () => {
    const p = partitionItems([item('tc', { review: { answers: [] } })])
    expect(selectHeadline(p, rollup({ total: 1 }))).toBe(
      'מבחן אחד צריך את העיניים שלך',
    )
  })

  it('only transcribing left', () => {
    const p = partitionItems([approved('a1')])
    expect(selectHeadline(p, rollup({ transcribing: 4, total: 5 }))).toBe(
      'כמעט שם — 4 מבחנים אחרונים בתמלול',
    )
  })

  it('all terminal → the completion line over the batch total', () => {
    const p = partitionItems([approved('a1'), approved('a2')])
    expect(selectHeadline(p, rollup({ total: 2, approved: 2 }))).toBe(
      'סיימת — כל 2 המבחנים אושרו',
    )
  })

  it('empty batch → null (no headline invented)', () => {
    expect(selectHeadline(partitionItems([]), rollup())).toBeNull()
  })
})

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
    expect(pollCadenceMs({
      rollup: rollup({ approved: 2, total: 2 }), active_jobs: [],
    })).toBeNull()
  })
})

describe('completionReached (D10)', () => {
  it('requires no transcribing, no transcribed, no active jobs, and rows', () => {
    expect(completionReached({
      rollup: rollup({ approved: 3, total: 3 }), active_jobs: [],
    })).toBe(true)
    expect(completionReached({
      rollup: rollup({ transcribing: 1, total: 3 }), active_jobs: [],
    })).toBe(false)
    expect(completionReached({
      rollup: rollup({ transcribed: 1, total: 3 }), active_jobs: [],
    })).toBe(false)
    expect(completionReached({
      rollup: rollup({ approved: 3, total: 3 }),
      active_jobs: [{ state: 'queued' }],
    })).toBe(false)
    expect(completionReached({ rollup: rollup(), active_jobs: [] })).toBe(false)
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
