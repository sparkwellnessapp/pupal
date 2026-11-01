'use client'

/**
 * A saved set of photos, as the teacher sees it: the «תמונות» viewer and the
 * duplicate comparison are both built from these pieces.
 *
 *  * `useSavedSet` loads the set that was SAVED — the frozen version sent to
 *    scanning (SCN-2), never a draft a student is still editing.
 *  * `PageGrid` lays its pages out as thumbnails; a click opens one.
 *  * `PageZoom` shows one page large, with «הצגת התמונה המלאה» to see the
 *    whole photo — the check that the crop did not cut part of an answer.
 *
 * Display only (SCN-11): a page with no picture shows a placeholder and the
 * others still render; a failed load says so and offers nothing it cannot do.
 */
import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'

import { P } from '@/copy/capture'
import type { PageView, VersionPages } from '@/types/capture'

import { FlattenedPage } from './FlattenedPage'

export type SavedSet =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'ready'; set: VersionPages }

/** Loads once per `key` (the set's identity); `load` may be a fresh closure
 *  on every render without refetching. */
export function useSavedSet(load: () => Promise<VersionPages>, key: string): SavedSet {
  const [result, setResult] = useState<SavedSet>({ state: 'loading' })
  const loadRef = useRef(load)
  loadRef.current = load
  useEffect(() => {
    let live = true
    setResult({ state: 'loading' })
    loadRef.current().then((set) => { if (live) setResult({ state: 'ready', set }) })
      .catch(() => { if (live) setResult({ state: 'failed' }) })
    return () => { live = false }
  }, [key])
  return result
}

export function SetStatus({ saved }: { saved: SavedSet }) {
  if (saved.state === 'loading') {
    return <p className="flex items-center gap-2 text-sm text-batch-muted"><Loader2 size={14} className="animate-spin" />{P.photosLoading}</p>
  }
  if (saved.state === 'failed') return <p className="text-sm text-batch-red-ink" role="alert">{P.photosFailed}</p>
  if (saved.set.pages.length === 0) return <p className="text-sm text-batch-muted">{P.photosNone}</p>
  return null
}

export function PageGrid({ pages, width, onOpen }: {
  pages: PageView[]
  width: number
  onOpen: (index: number) => void
}) {
  return (
    <ol className="flex flex-wrap gap-3" aria-label={P.photos}>
      {pages.map((page, i) => (
        <li key={page.page_id}>
          <button type="button" onClick={() => onOpen(i)} data-testid="captured-page"
                  className="flex flex-col items-center gap-1 rounded-lg p-1 hover:bg-surface-50 focus-visible:ring-2 focus-visible:ring-primary-300">
            <FlattenedPage page={page} width={width} missingLabel={P.photoMissing} />
            <span className="text-xs text-batch-muted">{P.pageN(i + 1)}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

/** The width a single page may take on this screen: the modal's, less its
 *  gutters — and short enough that the whole page fits the screen's height
 *  (an A4 page is √2 times as tall as it is wide). */
function zoomWidth(): number {
  if (typeof window === 'undefined') return 600
  const byWidth = window.innerWidth - 120
  const byHeight = (window.innerHeight - 280) / Math.SQRT2
  return Math.max(200, Math.min(640, byWidth, byHeight))
}

export function PageZoom({ pages, index, onIndex, onBack }: {
  pages: PageView[]
  index: number
  onIndex: (index: number) => void
  onBack: () => void
}) {
  const [uncropped, setUncropped] = useState(false)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const fit = () => setWidth(zoomWidth())
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
  const page = pages[index]
  // RTL: «הבא» points left, «הקודם» right.
  return (
    <div className="space-y-3" data-testid="page-zoom">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <button type="button" onClick={onBack} className="text-primary-700 underline">{P.backToPages}</button>
        <span className="text-batch-muted">{P.pageN(index + 1)} / {pages.length}</span>
        <button type="button" onClick={() => setUncropped((u) => !u)}
                className="rounded-lg border border-batch-line px-3 py-1.5 text-batch-ink hover:bg-surface-50">
          {uncropped ? P.showCropped : P.showFullPhoto}
        </button>
      </div>
      <div className="flex items-center justify-center gap-2">
        <button type="button" aria-label={P.pageN(index)} disabled={index === 0}
                onClick={() => onIndex(index - 1)}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded text-gray-600 hover:bg-surface-100 disabled:opacity-30">
          <ChevronRight size={20} />
        </button>
        <div>
          <FlattenedPage page={page} width={width} uncropped={uncropped} missingLabel={P.photoMissing} />
        </div>
        <button type="button" aria-label={P.pageN(index + 2)} disabled={index >= pages.length - 1}
                onClick={() => onIndex(index + 1)}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded text-gray-600 hover:bg-surface-100 disabled:opacity-30">
          <ChevronLeft size={20} />
        </button>
      </div>
    </div>
  )
}

/** A set's thumbnails, opening into one large page in place. */
export function BrowsableSet({ pages, width }: { pages: PageView[]; width: number }) {
  const [open, setOpen] = useState<number | null>(null)
  if (open !== null && pages[open]) {
    return <PageZoom pages={pages} index={open} onIndex={setOpen} onBack={() => setOpen(null)} />
  }
  return <PageGrid pages={pages} width={width} onOpen={setOpen} />
}
