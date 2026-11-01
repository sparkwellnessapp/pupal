'use client'

/**
 * PageStrip — the pages as thumbnails (§8.1). Each thumbnail is a CLIENT-SIDE
 * geometric preview (D8, `FlattenedPage`) — no server render, so it costs
 * nothing per drag. Lighting cleanup happens only at compilation. Up/down
 * arrows reorder (mobile-safe; no drag-and-drop).
 */
import { ChevronDown, ChevronUp, Loader2, AlertTriangle, Check } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { PageView } from '@/types/capture'

import { FlattenedPage } from './FlattenedPage'

const THUMB_W = 72

export interface StripPage {
  key: string
  page?: PageView
  localSrc?: string
  state: 'uploading' | 'ready' | 'warning' | 'failed' | 'incomplete'
}

export function PageStrip({ pages, selectedKey, copy, canMove = true, onSelect, onMove }: {
  pages: StripPage[]
  selectedKey: string | null
  copy: FlowCopy
  /** false while a photo is still landing or an edit is in flight */
  canMove?: boolean
  onSelect: (key: string) => void
  onMove: (key: string, delta: -1 | 1) => void
}) {
  const movable = canMove ? pages.filter((p) => p.page && p.state !== 'uploading') : []
  return (
    <ol className="flex flex-col gap-2" dir="rtl" aria-label="עמודים">
      {pages.map((p, i) => {
        const idx = movable.findIndex((m) => m.key === p.key)
        return (
          <li key={p.key}
              className={`flex items-center gap-3 rounded-lg border p-2 ${
                selectedKey === p.key ? 'border-primary-500 bg-primary-50' : 'border-surface-200 bg-white'}`}>
            <button type="button" onClick={() => onSelect(p.key)} className="flex flex-1 items-center gap-3 text-right">
              <Thumb page={p} />
              <span className="flex-1 text-sm">
                <span className="block font-medium text-gray-800">{copy.pageN(i + 1)}</span>
                <Badge state={p.state} copy={copy} />
              </span>
            </button>
            {idx >= 0 && (
              <span className="flex">
                {/* 44 px each (a finger, not a cursor). */}
                <button type="button" aria-label={copy.moveUp} disabled={idx === 0}
                        onClick={() => onMove(p.key, -1)}
                        className="flex h-11 w-11 items-center justify-center rounded text-gray-500 hover:bg-surface-100 disabled:opacity-30">
                  <ChevronUp size={18} />
                </button>
                <button type="button" aria-label={copy.moveDown} disabled={idx === movable.length - 1}
                        onClick={() => onMove(p.key, 1)}
                        className="flex h-11 w-11 items-center justify-center rounded text-gray-500 hover:bg-surface-100 disabled:opacity-30">
                  <ChevronDown size={18} />
                </button>
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

function Thumb({ page }: { page: StripPage }) {
  return <FlattenedPage page={page.page} src={page.page?.preview_url || page.localSrc} width={THUMB_W} />
}

function Badge({ state, copy }: { state: StripPage['state']; copy: FlowCopy }) {
  if (state === 'uploading') {
    return <span className="flex items-center gap-1 text-xs text-gray-500"><Loader2 size={12} className="animate-spin" />{copy.badgeUploading}</span>
  }
  if (state === 'failed') return <span className="text-xs text-red-700">{copy.uploadFailed}</span>
  if (state === 'incomplete') return <span className="text-xs text-red-700">{copy.uploadIncomplete}</span>
  if (state === 'warning') {
    return <span className="flex items-center gap-1 text-xs text-amber-700"><AlertTriangle size={12} />{copy.badgeWarning}</span>
  }
  return <span className="flex items-center gap-1 text-xs text-primary-700"><Check size={12} />{copy.badgeReady}</span>
}
