'use client'

/**
 * «תמונות» — the photos one student sent, as they were SAVED (the version
 * that went to scanning): every page, in order, cropped and turned as it was
 * sent, one click from the whole uncropped photo.
 */
import { Modal } from '@/components/batch/Modal'
import { P, hhmm } from '@/copy/capture'
import { getSubmissionVersion } from '@/lib/capture-api'
import type { CaptureSubmissionRow } from '@/types/capture'
import { claimName } from '@/utils/capture-duplicates'

import { BrowsableSet, SetStatus, useSavedSet } from './CapturedSet'

const THUMB_W = 140

export function PhotosDialog({ batchId, row, onClose }: {
  batchId: string
  row: CaptureSubmissionRow | null
  onClose: () => void
}) {
  return (
    <Modal open={row !== null} onClose={onClose} labelledBy="photos-title" size="lg" testId="photos-dialog">
      {row && <Photos batchId={batchId} row={row} onClose={onClose} />}
    </Modal>
  )
}

function Photos({ batchId, row, onClose }: { batchId: string; row: CaptureSubmissionRow; onClose: () => void }) {
  const saved = useSavedSet(() => getSubmissionVersion(batchId, row.submission_id), row.submission_id)
  return (
    <div className="max-h-[calc(100dvh-9rem)] overflow-y-auto space-y-4 p-1" dir="rtl">
      <div className="space-y-0.5">
        <h2 id="photos-title" className="text-lg font-semibold text-gray-900">{P.photosTitle(claimName(row))}</h2>
        <p className="text-sm text-batch-muted">
          {[P.pages(row.page_count), row.saved_at ? P.savedAt(hhmm(row.saved_at)) : null,
            row.source === 'teacher' ? P.fromTeacher : P.fromLink].filter(Boolean).join(' · ')}
        </p>
      </div>
      <SetStatus saved={saved} />
      {saved.state === 'ready' && saved.set.pages.length > 0 && (
        <BrowsableSet pages={saved.set.pages} width={THUMB_W} />
      )}
      <div className="flex justify-end">
        <button type="button" onClick={onClose} data-autofocus
                className="rounded-lg border border-surface-300 px-4 py-2 text-sm text-gray-700">{P.close}</button>
      </div>
    </div>
  )
}
