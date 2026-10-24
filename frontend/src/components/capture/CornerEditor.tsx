'use client'

/**
 * CornerEditor — the post-capture screen IS the corner editor (D8): no extra
 * step. The photo, the detected page as a quad, four handles to drag
 * (pointer events, ≥ 44 px targets) and a loupe above the finger while
 * dragging. A shape that is not a page (concave, crossing, mirrored, < 5%)
 * snaps back; a release PATCHes the corners AT ONCE — the caller counts the
 * request as pending, so a save can never overtake her last drag. The quality
 * notice WARNS and never blocks (D10).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Crop, Maximize, RotateCw, Camera, Trash2, Loader2 } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { PageView, Quad, Rotation } from '@/types/capture'
import { clamp01, isValidQuad, toQuad, type QuadPts } from '@/utils/capture-geometry'

const HANDLE = 44
const LOUPE = 112
const ZOOM = 2.5

export function CornerEditor({ page, localSrc, copy, onCorners, onRotate, onReset, onRetake, onRemove,
                               onImageError }: {
  page: PageView
  /** The photo as captured on this device — shown until (or instead of) the preview. */
  localSrc?: string
  copy: FlowCopy
  onCorners: (q: Quad) => void
  onRotate: (r: Rotation) => void
  onReset: (to: 'auto' | 'full_frame') => void
  onRetake: () => void
  onRemove: () => void
  /** The preview would not load (its signed URL expired): fetch a fresh one. */
  onImageError?: () => void
}) {
  // An expired preview falls back to the photo this device captured, if any.
  const [previewBroken, setPreviewBroken] = useState(false)
  const src = (!previewBroken && page.preview_url) || localSrc || ''
  // Which src has loaded — compared, never reset by an effect (a cached image
  // can fire its load before an effect would have cleared a flag).
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null)
  const [quad, setQuad] = useState<QuadPts>(() => toQuad(page.corners))
  const [drag, setDrag] = useState<number | null>(null)
  const box = useRef<HTMLDivElement>(null)
  // The pointer handlers read the quad from here: a release can arrive before
  // React re-rendered with the last move, and a closure would hold a stale quad.
  const quadRef = useRef<QuadPts>(quad)
  const dragRef = useRef<number | null>(null)
  const lastGood = useRef<QuadPts>(quad)

  const setBoth = (q: QuadPts) => { quadRef.current = q; setQuad(q) }

  useEffect(() => { setPreviewBroken(false) }, [page.preview_url])

  // A server-side change (reset, a fresh analysis) replaces the local quad —
  // never while a finger is on a handle.
  useEffect(() => {
    if (dragRef.current === null) {
      const q = toQuad(page.corners)
      setBoth(q)
      lastGood.current = q
    }
  }, [page.corners, page.page_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const toNorm = useCallback((clientX: number, clientY: number): [number, number] => {
    const r = box.current!.getBoundingClientRect()
    return [clamp01((clientX - r.left) / r.width), clamp01((clientY - r.top) / r.height)]
  }, [])

  const onDown = (i: number) => (e: React.PointerEvent) => {
    e.preventDefault()
    ;(e.target as Element).setPointerCapture(e.pointerId)
    dragRef.current = i
    setDrag(i)
  }
  const onMove = (e: React.PointerEvent) => {
    const i = dragRef.current
    if (i === null) return
    const p = toNorm(e.clientX, e.clientY)
    setBoth(quadRef.current.map((pt, j) => (j === i ? p : pt)) as QuadPts)
  }
  const onUp = () => {
    if (dragRef.current === null) return
    dragRef.current = null
    setDrag(null)
    const q = quadRef.current
    if (!isValidQuad(q)) {                          // snap back to the last page-shaped quad
      setBoth(lastGood.current)
      return
    }
    if (q.every((p, i) => p[0] === lastGood.current[i][0] && p[1] === lastGood.current[i][1])) return
    lastGood.current = q
    onCorners(q.map((p) => [p[0], p[1]]))
  }

  // The loupe shows the image around the finger at ZOOM×: the background is
  // the WHOLE displayed image scaled by ZOOM, shifted so the touched point
  // sits at the loupe's centre. It sits above the finger, or below it near
  // the top edge, and never leaves the photo's box sideways.
  const shown = box.current?.getBoundingClientRect()
  const loupeStyle = (pt: [number, number]): React.CSSProperties => {
    if (!shown) return { display: 'none' }
    const x = pt[0] * shown.width
    const y = pt[1] * shown.height
    const above = y - LOUPE - HANDLE
    return {
      width: LOUPE, height: LOUPE,
      left: Math.min(Math.max(x - LOUPE / 2, 0), Math.max(0, shown.width - LOUPE)),
      top: above >= 0 ? above : y + HANDLE,
      backgroundImage: `url(${src})`,
      backgroundRepeat: 'no-repeat',
      backgroundSize: `${shown.width * ZOOM}px ${shown.height * ZOOM}px`,
      backgroundPosition: `${LOUPE / 2 - x * ZOOM}px ${LOUPE / 2 - y * ZOOM}px`,
    }
  }

  const reasons = (page.quality?.reasons ?? []) as (keyof FlowCopy['quality'])[]
  const points = quad.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')
  const dragPt = drag !== null ? quad[drag] : null
  const ready = !!src && loadedSrc === src
  const aspect = page.image_w && page.image_h ? `${page.image_w} / ${page.image_h}` : '3 / 4'

  return (
    <div className="space-y-3" dir="rtl">
      {/* Half a handle of padding on every side: a corner on the photo's edge
          keeps its whole 44 px target on screen. */}
      <div className="mx-auto w-full max-w-md px-[22px] py-[22px]">
        <div
          ref={box}
          className="relative w-full touch-none select-none rounded-lg bg-surface-100"
          style={ready ? undefined : { aspectRatio: aspect }}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          data-testid="corner-editor"
        >
          {src && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt="" draggable={false}
                 className={`block w-full rounded-lg ${ready ? '' : 'absolute inset-0 h-full opacity-0'}`}
                 onLoad={() => setLoadedSrc(src)}
                 onError={() => {
                   if (src === page.preview_url) { setPreviewBroken(true); onImageError?.() }
                 }} />
          )}
          {!ready && (
            <span className="absolute inset-0 flex items-center justify-center text-gray-400" aria-hidden>
              <Loader2 size={20} className="animate-spin" />
            </span>
          )}
          {ready && (
            <>
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
              {dragPt && (
                <div aria-hidden className="pointer-events-none absolute z-10 rounded-full border-2 border-white shadow-lg"
                     style={loupeStyle(dragPt)} />
              )}
            </>
          )}
        </div>
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
