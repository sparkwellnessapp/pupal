'use client'

/**
 * «בחירת הגשה» — one student, several sets of photos (SCN-13); she keeps
 * exactly one and the rest are discarded (SCN-14, owner ruling 2026-11-01:
 * no "keep both", no "it is someone else's").
 *
 * Every set is shown in full — every page of the SAVED version, side by side
 * (stacked on a phone) — because the choice is "which of these is the real
 * exam", and that cannot be made from a count and a timestamp. Any set can be
 * kept, the earlier one included; with an approved set in the group, only
 * that one can (approved work is never discarded).
 *
 * The decision takes two clicks: «להשאיר את זו», then a line saying what will
 * be discarded. A refusal is shown INSIDE the dialog and the dialog stays
 * open — the 2026-10-30 failure was a dialog that closed first and reported
 * behind itself.
 */
import { useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Modal } from '@/components/batch/Modal'
import { P, hhmm } from '@/copy/capture'
import { CaptureApiError, getSubmissionVersion, keepSubmission } from '@/lib/capture-api'
import type { CaptureSubmissionRow, CaptureSubmissionsResponse, PageView } from '@/types/capture'
import { canKeep, claimName } from '@/utils/capture-duplicates'

import { PageGrid, PageZoom, SetStatus, useSavedSet } from './CapturedSet'

const COLUMN_THUMB_W = 112

type Zoom = { label: string; pages: PageView[]; index: number }

export function DuplicateDialog({ batchId, group, onClose, onKept, onRefresh }: {
  batchId: string
  /** the rows of ONE duplicate, oldest first; empty = closed */
  group: CaptureSubmissionRow[]
  onClose: () => void
  onKept: (panel: CaptureSubmissionsResponse) => void
  /** the group changed under her (another tab): re-read the panel */
  onRefresh: () => void
}) {
  const [zoom, setZoom] = useState<Zoom | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const open = group.length > 1
  const name = group.length ? claimName(group[0]) : ''

  const close = () => {
    if (busy) return
    setZoom(null); setConfirming(null); setError(null)
    onClose()
  }

  const keep = async (submissionId: string) => {
    setBusy(true); setError(null)
    try {
      const panel = await keepSubmission(batchId, submissionId)
      toast.success(P.keptToast)
      setConfirming(null); setZoom(null)
      onKept(panel)
    } catch (e) {
      if (e instanceof CaptureApiError && e.code === 'not_conflict') {
        setError(P.duplicateGone); onRefresh()
      } else {
        setError(e instanceof CaptureApiError && e.messageHe ? e.messageHe : (e as Error).message)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} labelledBy="duplicate-title" size="lg" testId="duplicate-dialog">
      <div className="max-h-[calc(100dvh-9rem)] overflow-y-auto space-y-4 p-1" dir="rtl">
        <div className="space-y-1">
          <h2 id="duplicate-title" className="text-lg font-semibold text-gray-900">{P.duplicateTitle(name)}</h2>
          <p className="text-sm text-batch-muted">{P.duplicateExplain}</p>
        </div>
        {error && <p className="rounded-lg bg-batch-red-soft px-3 py-2 text-sm text-batch-red-ink" role="alert">{error}</p>}

        {zoom ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-batch-ink">{zoom.label}</p>
            <PageZoom pages={zoom.pages} index={zoom.index}
                      onIndex={(index) => setZoom({ ...zoom, index })} onBack={() => setZoom(null)} />
          </div>
        ) : (
          <div className={`grid gap-3 ${group.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-3'}`}>
            {group.map((row, i) => (
              <SetColumn key={row.submission_id} batchId={batchId} row={row} label={P.setN(i + 1)}
                         keepable={canKeep(group, row)} others={group.length - 1}
                         confirming={confirming === row.submission_id} busy={busy}
                         onAsk={() => { setError(null); setConfirming(row.submission_id) }}
                         onBack={() => setConfirming(null)}
                         onKeep={() => void keep(row.submission_id)}
                         onZoom={(pages, index) => setZoom({ label: P.setN(i + 1), pages, index })} />
            ))}
          </div>
        )}

        <div className="flex justify-end">
          <button type="button" onClick={close} disabled={busy}
                  className="rounded-lg border border-surface-300 px-4 py-2 text-sm text-gray-700 disabled:opacity-50">
            {P.close}
          </button>
        </div>
      </div>
    </Modal>
  )
}

function SetColumn({ batchId, row, label, keepable, others, confirming, busy, onAsk, onBack, onKeep, onZoom }: {
  batchId: string
  row: CaptureSubmissionRow
  label: string
  keepable: boolean
  others: number
  confirming: boolean
  busy: boolean
  onAsk: () => void
  onBack: () => void
  onKeep: () => void
  onZoom: (pages: PageView[], index: number) => void
}) {
  const saved = useSavedSet(() => getSubmissionVersion(batchId, row.submission_id), row.submission_id)
  const approved = row.transcription_status === 'approved'
  return (
    <section className={`flex flex-col gap-3 rounded-lg border p-3 ${confirming ? 'border-primary-500 ring-2 ring-primary-100' : 'border-surface-200'}`}
             data-testid="duplicate-set" aria-label={label}>
      <header className="space-y-0.5 text-sm">
        <p className="font-semibold text-batch-ink">{label}</p>
        <p className="text-batch-muted">
          {[P.pages(row.page_count), row.saved_at ? P.savedAt(hhmm(row.saved_at)) : null,
            row.source === 'teacher' ? P.fromTeacher : P.fromLink].filter(Boolean).join(' · ')}
        </p>
        {approved && (
          <p className="flex items-center gap-1 text-batch-teal-ink"><Check size={14} />{P.approvedSet}</p>
        )}
      </header>

      <SetStatus saved={saved} />
      {saved.state === 'ready' && saved.set.pages.length > 0 && (
        <PageGrid pages={saved.set.pages} width={COLUMN_THUMB_W}
                  onOpen={(index) => onZoom(saved.set.pages, index)} />
      )}

      <div className="mt-auto space-y-2">
        {!keepable ? (
          <p className="text-xs text-batch-muted">{P.otherApproved}</p>
        ) : confirming ? (
          <>
            <p className="text-sm text-batch-ink">{P.keepConfirm(others)}</p>
            <div className="flex gap-2">
              <button type="button" onClick={onKeep} disabled={busy} data-autofocus data-testid="keep-confirm"
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary-600 py-2 text-sm text-white disabled:opacity-60">
                {busy && <Loader2 size={14} className="animate-spin" />}{busy ? P.keeping : P.keepYes}
              </button>
              <button type="button" onClick={onBack} disabled={busy}
                      className="rounded-lg border border-surface-300 px-3 py-2 text-sm text-gray-700 disabled:opacity-50">
                {P.keepBack}
              </button>
            </div>
          </>
        ) : (
          <button type="button" onClick={onAsk} disabled={busy} data-testid="keep-this"
                  className="w-full rounded-lg bg-primary-600 py-2 text-sm text-white hover:bg-primary-700 disabled:opacity-50">
            {P.keepThis}
          </button>
        )}
      </div>
    </section>
  )
}
