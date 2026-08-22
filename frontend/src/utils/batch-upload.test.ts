import { describe, expect, it } from 'vitest'

import {
  aggregatePct,
  allDone,
  composeBatchName,
  detectDuplicates,
  formatMB,
  initQueue,
  isDrained,
  landedCount,
  nextToStart,
  UPLOAD_CONCURRENCY,
  uploadQueueReducer,
  type UploadQueueState,
} from './batch-upload'

/**
 * P4/W1 — the upload pure-logic layer (spec §6 preamble): composeBatchName
 * (B5 client half), detectDuplicates (name+size, advisory), and the
 * upload-queue reducer (U3: queued→uploading(pct)→done|failed, bounded
 * concurrency 6, retry keeps client_file_id, 422 terminal).
 */

const meta = (id: string, size = 1000) => ({
  clientFileId: id,
  filename: `${id}.pdf`,
  size,
})

function queueOf(...ids: string[]): UploadQueueState {
  return initQueue(ids.map((id) => meta(id)))
}

describe('composeBatchName (B5)', () => {
  const date = new Date(2026, 7, 18) // 18.8.2026

  it('composes rubric · class · he-IL short date', () => {
    expect(composeBatchName('מתכונת קיץ', 'יא׳3', date)).toBe('מתכונת קיץ · יא׳3 · 18.8.2026')
  })

  it('omits the class segment (and its separator) when class is absent', () => {
    expect(composeBatchName('מתכונת קיץ', null, date)).toBe('מתכונת קיץ · 18.8.2026')
    expect(composeBatchName('מתכונת קיץ', undefined, date)).toBe('מתכונת קיץ · 18.8.2026')
    expect(composeBatchName('מתכונת קיץ', '  ', date)).toBe('מתכונת קיץ · 18.8.2026')
  })
})

describe('detectDuplicates — advisory, name+size', () => {
  it('marks LATER occurrences of an identical (name, size) pair', () => {
    const dups = detectDuplicates([
      { name: 'a.pdf', size: 100 },
      { name: 'b.pdf', size: 200 },
      { name: 'a.pdf', size: 100 },
      { name: 'a.pdf', size: 100 },
    ])
    expect(dups).toEqual(new Set([2, 3]))
  })

  it('same name with different size is NOT a duplicate', () => {
    expect(detectDuplicates([
      { name: 'a.pdf', size: 100 },
      { name: 'a.pdf', size: 101 },
    ])).toEqual(new Set())
  })

  it('empty and single lists have no duplicates', () => {
    expect(detectDuplicates([])).toEqual(new Set())
    expect(detectDuplicates([{ name: 'a.pdf', size: 1 }])).toEqual(new Set())
  })
})

describe('formatMB — §3.2 LTR size text', () => {
  it('renders one decimal MB', () => {
    expect(formatMB(3.2 * 1024 * 1024)).toBe('3.2 MB')
    expect(formatMB(512 * 1024)).toBe('0.5 MB')
  })
})

describe('applyAddFiles — U2 intake: filtered, surfaced, never silent', () => {
  const pdf = (name: string, bytes = 100) =>
    new File([new Uint8Array(bytes)], name, { type: 'application/pdf' })
  const txt = (name: string) => new File(['hello'], name, { type: 'text/plain' })
  const untyped = (name: string) => new File(['x'], name, { type: '' })

  it('accepts PDFs, excludes non-PDFs and empties WITH reasons (no silent drop)', async () => {
    const { applyAddFiles } = await import('./batch-upload')
    const r = applyAddFiles([], [pdf('a.pdf'), txt('b.txt'), pdf('c.pdf', 0)], 50)
    expect(r.files.map((f) => f.name)).toEqual(['a.pdf'])
    expect(r.excluded).toEqual([
      { filename: 'b.txt', reason: 'לא קובץ PDF' },
      { filename: 'c.pdf', reason: 'קובץ ריק' },
    ])
    expect(r.truncated).toBe(false)
  })

  it('an untyped file with a .pdf extension passes (drag sources omit MIME)', async () => {
    const { applyAddFiles } = await import('./batch-upload')
    const r = applyAddFiles([], [untyped('scan.pdf'), untyped('scan.docx')], 50)
    expect(r.files.map((f) => f.name)).toEqual(['scan.pdf'])
    expect(r.excluded).toEqual([{ filename: 'scan.docx', reason: 'לא קובץ PDF' }])
  })

  it('caps at maxFiles and REPORTS the truncation (§3.2 notice, no silent slice)', async () => {
    const { applyAddFiles } = await import('./batch-upload')
    const existing = Array.from({ length: 49 }, (_, i) => pdf(`e${i}.pdf`))
    const r = applyAddFiles(existing, [pdf('x.pdf'), pdf('y.pdf'), pdf('z.pdf')], 50)
    expect(r.files).toHaveLength(50)
    expect(r.files[49].name).toBe('x.pdf')
    expect(r.truncated).toBe(true)
  })
})

describe('upload-queue reducer — transitions', () => {
  it('initQueue: everything queued, ids preserved', () => {
    const s = queueOf('f1', 'f2')
    expect(s.items.map((i) => i.state.kind)).toEqual(['queued', 'queued'])
    expect(s.items.map((i) => i.clientFileId)).toEqual(['f1', 'f2'])
  })

  it('start → uploading(0); progress clamps into [0,100]; done carries the job id', () => {
    let s = queueOf('f1')
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    expect(s.items[0].state).toEqual({ kind: 'uploading', pct: 0 })
    s = uploadQueueReducer(s, { type: 'progress', clientFileId: 'f1', pct: 250 })
    expect(s.items[0].state).toEqual({ kind: 'uploading', pct: 100 })
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'f1', jobId: 'j1' })
    expect(s.items[0].state).toEqual({ kind: 'done', jobId: 'j1' })
  })

  it('progress on a non-uploading item is a no-op; done is idempotent (first job id wins)', () => {
    let s = queueOf('f1')
    expect(uploadQueueReducer(s, { type: 'progress', clientFileId: 'f1', pct: 50 })).toBe(s)
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'f1', jobId: 'j1' })
    const again = uploadQueueReducer(s, { type: 'done', clientFileId: 'f1', jobId: 'j2' })
    expect(again).toBe(s)
  })

  it('fail lands only from uploading and records the reason + retryability', () => {
    let s = queueOf('f1')
    expect(uploadQueueReducer(s, { type: 'fail', clientFileId: 'f1', reason: 'x', retryable: true })).toBe(s)
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'fail', clientFileId: 'f1', reason: 'לא קובץ PDF', retryable: false })
    expect(s.items[0].state).toEqual({ kind: 'failed', reason: 'לא קובץ PDF', retryable: false })
  })

  it('retry: retryable failed → queued with the SAME client_file_id; 422 (non-retryable) is terminal', () => {
    let s = queueOf('f1', 'f2')
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'fail', clientFileId: 'f1', reason: 'network', retryable: true })
    s = uploadQueueReducer(s, { type: 'retry', clientFileId: 'f1' })
    expect(s.items[0].state).toEqual({ kind: 'queued' })
    expect(s.items[0].clientFileId).toBe('f1')          // the idempotency key survives

    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f2' })
    s = uploadQueueReducer(s, { type: 'fail', clientFileId: 'f2', reason: 'קובץ ריק', retryable: false })
    const after = uploadQueueReducer(s, { type: 'retry', clientFileId: 'f2' })
    expect(after).toBe(s)                                // no-op: a 422 never retries
  })

  it('retry on done or queued is a no-op (idempotence)', () => {
    let s = queueOf('f1')
    expect(uploadQueueReducer(s, { type: 'retry', clientFileId: 'f1' })).toBe(s)
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'f1', jobId: 'j1' })
    expect(uploadQueueReducer(s, { type: 'retry', clientFileId: 'f1' })).toBe(s)
  })
})

describe('upload-queue selectors', () => {
  it('nextToStart respects the concurrency bound of 6 and queue order', () => {
    let s = queueOf('f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8')
    expect(UPLOAD_CONCURRENCY).toBe(6)
    expect(nextToStart(s)).toEqual(['f1', 'f2', 'f3', 'f4', 'f5', 'f6'])
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f2' })
    expect(nextToStart(s)).toEqual(['f3', 'f4', 'f5', 'f6'])
    for (const id of ['f3', 'f4', 'f5', 'f6']) s = uploadQueueReducer(s, { type: 'start', clientFileId: id })
    expect(nextToStart(s)).toEqual([])
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'f2', jobId: 'j2' })
    expect(nextToStart(s)).toEqual(['f7'])
  })

  it('a retry mid-flight re-queues and still respects the bound (U3 edge)', () => {
    let s = queueOf('f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7')
    for (const id of ['f1', 'f2', 'f3', 'f4', 'f5', 'f6']) s = uploadQueueReducer(s, { type: 'start', clientFileId: id })
    s = uploadQueueReducer(s, { type: 'fail', clientFileId: 'f1', reason: 'network', retryable: true })
    s = uploadQueueReducer(s, { type: 'retry', clientFileId: 'f1' })
    // Two uploading (f2, f3) → exactly ONE free slot. Launch order is ITEM
    // order (the visible file-list order) — a retried row reclaims its slot
    // ahead of later never-started rows; no arrival-sequence bookkeeping.
    expect(nextToStart(s)).toEqual(['f1'])
  })

  it('aggregatePct is size-weighted over non-failed items; done=100, queued=0', () => {
    let s = initQueue([meta('big', 3000), meta('small', 1000)])
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'big' })
    s = uploadQueueReducer(s, { type: 'progress', clientFileId: 'big', pct: 50 })
    // 3000×50 / 4000 = 37.5 → rounded
    expect(aggregatePct(s)).toBe(38)
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'big', jobId: 'j' })
    expect(aggregatePct(s)).toBe(75)
  })

  it('drained/allDone/landedCount tell the truth around failures', () => {
    let s = queueOf('f1', 'f2')
    expect(isDrained(s)).toBe(false)
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f1' })
    s = uploadQueueReducer(s, { type: 'done', clientFileId: 'f1', jobId: 'j1' })
    s = uploadQueueReducer(s, { type: 'start', clientFileId: 'f2' })
    s = uploadQueueReducer(s, { type: 'fail', clientFileId: 'f2', reason: 'קובץ ריק', retryable: false })
    expect(isDrained(s)).toBe(true)     // nothing left to run…
    expect(allDone(s)).toBe(false)      // …but NOT all-done: a failure is visible
    expect(landedCount(s)).toBe(1)
  })
})
