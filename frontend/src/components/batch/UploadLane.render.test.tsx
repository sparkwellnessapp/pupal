/**
 * Stage B — the upload lane's rules, as markup (house pattern:
 * renderToStaticMarkup, no DOM). The journeys spec drives the behaviour end to
 * end; this pins the decisions that are easy to regress silently and expensive
 * to notice — which rows offer which affordance, and when the lane is allowed
 * to disappear.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { UploadLane } from '@/components/batch/UploadLane'
import type { UploadItemState, UploadQueueState } from '@/utils/batch-upload'

const noop = () => {}

const item = (clientFileId: string, filename: string, state: UploadItemState) =>
  ({ clientFileId, filename, size: 1_048_576, state })

const queue = (...items: ReturnType<typeof item>[]): UploadQueueState =>
  ({ items })

const render = (q: UploadQueueState) =>
  renderToStaticMarkup(
    <UploadLane queue={q} onRetry={noop} onRemove={noop} onDismiss={noop} />,
  )

describe('UploadLane', () => {
  it('shows progress for a transfer in flight', () => {
    const html = render(queue(item('a', 'a.pdf', { kind: 'uploading', pct: 42 })))
    expect(html).toContain('zone-upload')
    expect(html).toContain('a.pdf')
    expect(html).toContain('42%')
    expect(html).toContain('data-state="uploading"')
  })

  it('renders the SERVER reason verbatim on a failure', () => {
    // The §3.2 vocabulary the upload page used to show. Paraphrasing it here
    // would put a second, quieter opinion next to the server's verdict.
    const html = render(queue(
      item('a', 'bad.pdf', { kind: 'failed', reason: 'לא קובץ PDF', retryable: false }),
    ))
    expect(html).toContain('לא קובץ PDF')
  })

  it('offers retry ONLY where a retry can heal anything', () => {
    // A 422 is a validation verdict — an invalid file does not become valid by
    // being sent again, and offering the button would promise otherwise.
    const terminal = render(queue(
      item('a', 'bad.pdf', { kind: 'failed', reason: 'לא קובץ PDF', retryable: false }),
    ))
    expect(terminal).not.toContain('upload-lane-retry')
    expect(terminal).toContain('upload-lane-remove')

    const transient = render(queue(
      item('a', 'flaky.pdf', { kind: 'failed', reason: 'נכשל', retryable: true }),
    ))
    expect(transient).toContain('upload-lane-retry')
  })

  it('keeps a landed file free of both affordances', () => {
    // Removing a landed file would re-declare below COUNT(jobs), which the
    // server refuses — so the button must not exist to be pressed.
    // Paired with an in-flight sibling so the lane is still rendering at all —
    // on its own, a landed file is exactly the case where the lane bows out.
    const html = render(queue(
      item('a', 'ok.pdf', { kind: 'done', jobId: 'j1' }),
      item('b', 'next.pdf', { kind: 'uploading', pct: 10 }),
    ))
    expect(html).toContain('data-state="done"')
    expect(html).not.toContain('upload-lane-remove')
    expect(html).not.toContain('upload-lane-retry')
  })

  it('STAYS when files were left behind, and offers the dismiss', () => {
    // A batch that is quietly short is the silent drop U4 exists to kill, so
    // the list outlives the transfers until she has seen it.
    const html = render(queue(
      item('a', 'ok.pdf', { kind: 'done', jobId: 'j1' }),
      item('b', 'bad.pdf', { kind: 'failed', reason: 'לא קובץ PDF', retryable: false }),
    ))
    expect(html).toContain('zone-upload')
    expect(html).toContain('upload-lane-dismiss')
  })

  it('disappears once everything landed — the documents are the subject now', () => {
    const html = render(queue(
      item('a', 'ok.pdf', { kind: 'done', jobId: 'j1' }),
      item('b', 'ok2.pdf', { kind: 'done', jobId: 'j2' }),
    ))
    expect(html).toBe('')
  })

  it('renders nothing for an empty queue', () => {
    expect(render(queue())).toBe('')
  })

  it('prints sizes as LTR islands (§3.1)', () => {
    const html = render(queue(item('a', 'a.pdf', { kind: 'queued' })))
    expect(html).toContain('dir="ltr"')
    expect(html).toContain('1.0 MB')
  })
})
