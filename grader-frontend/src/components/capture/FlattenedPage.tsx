'use client'

/**
 * ONE page, drawn the way the capture flow draws it (D8): the photo mapped
 * through a CSS `matrix3d` from the page's quad onto a rectangle of the page's
 * own aspect (A4 when D11 says so), then turned by its rotation — no server
 * render. The page strip's thumbnails, the «תמונות» viewer and the duplicate
 * comparison all draw pages here, so a page looks the same on every surface.
 *
 * `uncropped` shows the whole photo (turned, not cut to the corners): the
 * teacher's way to check that the crop did not cut off part of an answer.
 */
import type { PageView } from '@/types/capture'
import { FULL_FRAME, previewAspect, quadToRectMatrix3d, toQuad } from '@/utils/capture-geometry'

export function FlattenedPage({ page, width, src, uncropped = false, missingLabel }: {
  page: PageView | undefined
  /** CSS pixels, of the page's own (unturned) width */
  width: number
  /** the image to draw; defaults to the page's signed preview */
  src?: string | null
  uncropped?: boolean
  /** shown inside the placeholder when there is no picture to draw */
  missingLabel?: string
}) {
  const image = src || page?.preview_url
  const w = page?.image_w ?? 0
  const h = page?.image_h ?? 0
  if (!image || !page || !w || !h) {
    return (
      <span className="flex shrink-0 items-center justify-center rounded bg-surface-100 p-1 text-center text-xs text-batch-muted"
            style={{ width, height: width * Math.SQRT2 }}>
        {missingLabel}
      </span>
    )
  }
  const quad = uncropped ? FULL_FRAME : toQuad(page.corners)
  const aspect = previewAspect(quad, w, h)
  const boxH = width * aspect
  const rotation = page.rotation ?? 0
  const turned = rotation === 90 || rotation === 270
  // The preview image is scaled down from the oriented original; the quad is
  // normalized, so scaling the image to any width keeps the mapping exact.
  const imgW = Math.max(400, Math.round(width))
  const imgH = (imgW * h) / w
  return (
    <span className="relative block shrink-0 overflow-hidden rounded border border-surface-200 bg-white"
          style={{ width: turned ? boxH : width, height: turned ? width : boxH }}>
      {/* The page box, centred and turned: correct for every quarter turn by
          construction (the outer box already has the turned size). */}
      <span className="absolute left-1/2 top-1/2 block" style={{
        width, height: boxH,
        transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
      }}>
        <span className="absolute inset-0 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt="" width={imgW} height={imgH}
               style={{ width: imgW, height: imgH, maxWidth: 'none', transformOrigin: '0 0',
                        transform: quadToRectMatrix3d(quad, imgW, imgH, width, boxH) }} />
        </span>
      </span>
    </span>
  )
}
