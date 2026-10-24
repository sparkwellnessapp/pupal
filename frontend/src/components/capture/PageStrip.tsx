'use client'

/**
 * PageStrip — the pages as thumbnails (§8.1). Each thumbnail is a CLIENT-SIDE
 * geometric preview (D8): the photo mapped through a CSS `matrix3d` from the
 * page's quad onto a rectangle of the page's own aspect (A4 when D11 says so),
 * then turned by its rotation — no server render, so it costs nothing per
 * drag. Lighting cleanup happens only at compilation. Up/down arrows reorder
 * (mobile-safe; no drag-and-drop).
 */
import { ChevronDown, ChevronUp, Loader2, AlertTriangle, Check } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { PageView } from '@/types/capture'
import { previewAspect, quadToRectMatrix3d, toQuad } from '@/utils/capture-geometry'

const THUMB_W = 72

export interface StripPage {
  key: string
  page?: PageView
  localSrc?: string
  state: 'uploading' | 'ready' | 'warning' | 'failed' | 'incomplete'
}

export function PageStrip({ pages, selectedKey, copy, onSelect, onMove }: {
  pages: StripPage[]
  selectedKey: string | null
  copy: FlowCopy
  onSelect: (key: string) => void
  onMove: (key: string, delta: -1 | 1) => void
}) {
  const movable = pages.filter((p) => p.page && p.state !== 'uploading')
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
              <span className="flex flex-col">
                <button type="button" aria-label={copy.moveUp} disabled={idx === 0}
                        onClick={() => onMove(p.key, -1)}
                        className="flex h-[22px] w-11 items-center justify-center rounded text-gray-500 hover:bg-surface-100 disabled:opacity-30">
                  <ChevronUp size={16} />
                </button>
                <button type="button" aria-label={copy.moveDown} disabled={idx === movable.length - 1}
                        onClick={() => onMove(p.key, 1)}
                        className="flex h-[22px] w-11 items-center justify-center rounded text-gray-500 hover:bg-surface-100 disabled:opacity-30">
                  <ChevronDown size={16} />
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
  const src = page.page?.preview_url || page.localSrc
  const w = page.page?.image_w ?? 0
  const h = page.page?.image_h ?? 0
  if (!src || !page.page || !w || !h) {
    return <span className="block shrink-0 rounded bg-surface-100" style={{ width: THUMB_W, height: THUMB_W * Math.SQRT2 }} />
  }
  const quad = toQuad(page.page.corners)
  const aspect = previewAspect(quad, w, h)
  const boxH = THUMB_W * aspect
  const rotation = page.page.rotation ?? 0
  const turned = rotation === 90 || rotation === 270
  // The preview image is scaled down from the oriented original; the quad is
  // normalized, so scaling the image to any width keeps the mapping exact.
  const imgW = 400
  const imgH = (400 * h) / w
  return (
    <span className="relative block shrink-0 overflow-hidden rounded border border-surface-200 bg-white"
          style={{ width: turned ? boxH : THUMB_W, height: turned ? THUMB_W : boxH }}>
      {/* The page box, centred and turned: correct for every quarter turn by
          construction (the outer box already has the turned size). */}
      <span className="absolute left-1/2 top-1/2 block" style={{
        width: THUMB_W, height: boxH,
        transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
      }}>
        <span className="absolute inset-0 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="" width={imgW} height={imgH}
               style={{ width: imgW, height: imgH, maxWidth: 'none', transformOrigin: '0 0',
                        transform: quadToRectMatrix3d(quad, imgW, imgH, THUMB_W, boxH) }} />
        </span>
      </span>
    </span>
  )
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
