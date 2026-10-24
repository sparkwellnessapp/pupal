'use client'

/**
 * CornerEditor — the post-capture screen IS the corner editor (D8): no extra
 * step. The photo, the detected page as a quad, four handles to drag
 * (pointer events, ≥ 44 px targets) and a loupe above the finger while
 * dragging. A shape that is not a page (concave, crossing, < 5%) snaps back;
 * a release PATCHes the corners after 400 ms of quiet. The quality notice
 * WARNS and never blocks (D10).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Crop, Maximize, RotateCw, Camera, Trash2 } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { PageView, Quad, Rotation } from '@/types/capture'
import { clamp01, isValidQuad, toQuad, type QuadPts } from '@/utils/capture-geometry'

const HANDLE = 44
const LOUPE = 112
const ZOOM = 2.5

export function CornerEditor({ page, localSrc, copy, onCorners, onRotate, onReset, onRetake, onRemove }: {
  page: PageView
  /** The photo as captured on this device — shown until (or instead of) the preview. */
  localSrc?: string
  copy: FlowCopy
  onCorners: (q: Quad) => void
  onRotate: (r: Rotation) => void
  onReset: (to: 'auto' | 'full_frame') => void
  onRetake: () => void
  onRemove: () => void
}) {
  const src = page.preview_url || localSrc || ''
  const [quad, setQuad] = useState<QuadPts>(() => toQuad(page.corners))
  const [drag, setDrag] = useState<number | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const lastGood = useRef<QuadPts>(quad)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  // A server-side change (reset, a fresh analysis) replaces the local quad —
  // never while a finger is on a handle.
  useEffect(() => {
    if (drag === null) {
      const q = toQuad(page.corners)
      setQuad(q)
      lastGood.current = q
    }
  }, [page.corners, page.page_id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => clearTimeout(timer.current), [])

  const toNorm = useCallback((clientX: number, clientY: number): [number, number] => {
    const r = box.current!.getBoundingClientRect()
    return [clamp01((clientX - r.left) / r.width), clamp01((clientY - r.top) / r.height)]
  }, [])

  const onDown = (i: number) => (e: React.PointerEvent) => {
    e.preventDefault()
    ;(e.target as Element).setPointerCapture(e.pointerId)
    setDrag(i)
  }
  const onMove = (e: React.PointerEvent) => {
    if (drag === null) return
    const p = toNorm(e.clientX, e.clientY)
    setQuad((q) => q.map((pt, j) => (j === drag ? p : pt)) as QuadPts)
  }
  const onUp = () => {
    if (drag === null) return
    setDrag(null)
    if (!isValidQuad(quad)) {                       // snap back to the last page-shaped quad
      setQuad(lastGood.current)
      return
    }
    lastGood.current = quad
    clearTimeout(timer.current)
    const q = quad.map((p) => [p[0], p[1]])
    timer.current = setTimeout(() => onCorners(q), 400)
  }

  const reasons = (page.quality?.reasons ?? []) as (keyof FlowCopy['quality'])[]
  const points = quad.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')
  const dragPt = drag !== null ? quad[drag] : null

  return (
    <div className="space-y-3" dir="rtl">
      <div
        ref={box}
        className="relative mx-auto w-full max-w-md touch-none select-none overflow-visible rounded-lg bg-surface-100"
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        data-testid="corner-editor"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {src && <img src={src} alt="" className="block w-full rounded-lg" draggable={false} />}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none"
             className="pointer-events-none absolute inset-0 h-full w-full">
          <polygon points={points} fill="rgba(13,148,136,0.12)" stroke="rgb(13,148,136)"
                   strokeWidth={0.6} vectorEffect="non-scaling-stroke" />
        </svg>
        {quad.map(([x, y], i) => (
          <button
            key={i}
            type="button"
            aria-label={`פינה ${i + 1}`}
            onPointerDown={onDown(i)}
            className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, width: HANDLE, height: HANDLE }}
          >
            <span className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary-600 shadow" />
          </button>
        ))}
        {dragPt && src && (
          <div
            aria-hidden
            className="pointer-events-none absolute z-10 rounded-full border-2 border-white shadow-lg"
            style={{
              width: LOUPE, height: LOUPE,
              left: `calc(${dragPt[0] * 100}% - ${LOUPE / 2}px)`,
              top: `calc(${dragPt[1] * 100}% - ${LOUPE + HANDLE}px)`,
              backgroundImage: `url(${src})`,
              backgroundRepeat: 'no-repeat',
              backgroundSize: `${ZOOM * 100}%`,
              backgroundPosition: `${dragPt[0] * 100}% ${dragPt[1] * 100}%`,
            }}
          />
        )}
      </div>

      {reasons.length > 0 && (
        <ul className="space-y-1 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800" role="status">
          {reasons.map((r) => <li key={r}>{copy.quality[r]}</li>)}
        </ul>
      )}

      <div className="flex flex-wrap justify-center gap-2 text-sm">
        <ToolButton onClick={() => onReset('auto')} icon={<Crop size={16} />} label={copy.reset} />
        <ToolButton onClick={() => onReset('full_frame')} icon={<Maximize size={16} />} label={copy.fullFrame} />
        <ToolButton onClick={() => onRotate((((page.rotation ?? 0) + 90) % 360) as Rotation)}
                    icon={<RotateCw size={16} />} label={copy.rotate} />
        <ToolButton onClick={onRetake} icon={<Camera size={16} />} label={copy.retake} />
        <ToolButton onClick={onRemove} icon={<Trash2 size={16} />} label={copy.remove} tone="danger" />
      </div>
    </div>
  )
}

function ToolButton({ onClick, icon, label, tone }: {
  onClick: () => void; icon: React.ReactNode; label: string; tone?: 'danger'
}) {
  return (
    <button type="button" onClick={onClick}
            className={`flex min-h-[44px] items-center gap-1.5 rounded-lg border px-3 py-2 ${
              tone === 'danger' ? 'border-red-200 text-red-700 hover:bg-red-50'
                                : 'border-surface-300 text-gray-700 hover:bg-surface-50'}`}>
      {icon}<span>{label}</span>
    </button>
  )
}
