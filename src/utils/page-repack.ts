/**
 * Stage E/F (UPLOAD_LATENCY_PLAN.md, rulings R4 + R12) — re-encode a scanned
 * PDF in the browser, at the resolution the transcription pipeline actually
 * consumes.
 *
 * WHY THIS EXISTS. A ten-test batch ships 57.2 MB up a teacher's ~2 Mbps
 * uplink to deliver pixels the pipeline throws away: the scans arrive at
 * ~260 DPI and the two-phase engine rasterises at 200 DPI (then resizes to a
 * 2000 px long edge) before it looks at them. This is not compression for its
 * own sake — it is declining to transmit resolution the system already refuses
 * to use.
 *
 * WHY IT MUST BE JPEG-IN-PDF, and not the obvious alternatives:
 *   * **The output is a PDF, not loose images.** The teacher hands each student
 *     ONE file with every page in it (R12), and the stored object is what
 *     `returned_exam.py` opens, stamps and appends feedback to. "Page images
 *     become the primitive" was considered and dropped (R7) — it would have
 *     rewritten the pipeline input, the page proxy, the thumbnail store and the
 *     returned exam.
 *   * **JPEG, not WebP**, even though WebP is ~20% smaller. PDF cannot hold a
 *     WebP stream, and the deployed PyMuPDF cannot even read one — verified:
 *     `fitz.Pixmap(webp)` and `insert_image(stream=webp)` both raise
 *     `FzErrorFormat: unknown image file format`. JPEG embeds byte-for-byte as
 *     a DCTDecode stream, so nothing on the server transcodes anything.
 *
 * NOTHING HERE IS WIRED INTO THE UPLOAD PATH YET. Ruling R1 freezes what the
 * model sees, so this ships as the input to an EVAL first (Stage E). Only a
 * quality setting that proves non-inferior on every fixture and every repeat
 * becomes a feature (Stage F), behind `USE_CLIENT_REPACK`. This module is the
 * single source of truth for both: the corpus the eval judges is produced by
 * the exact code that would later run in the teacher's browser, because a
 * corpus encoded by the server's Pillow would measure a different encoder
 * (libjpeg-turbo) than the one that would actually ship (Chromium's Skia).
 */

import { PDFDocument } from 'pdf-lib'

/** The pipeline's own rasterisation DPI (`PROD_CONFIG.dpi`). */
export const PIPELINE_DPI = 200

/** PDF user space is 1/72 inch, so this is the render scale for PIPELINE_DPI. */
const PDF_UNITS_PER_INCH = 72

export interface RepackOptions {
  /** JPEG quality, 0..1. Chosen by the Stage E gate — never guessed. */
  quality: number
  /** Render DPI. 200 matches the pipeline; lower is a separate eval question. */
  dpi?: number
  /**
   * Injected so tests and the corpus generator can drive this without a DOM
   * canvas implementation of their own. Defaults to the real browser canvas.
   */
  createCanvas?: (w: number, h: number) => HTMLCanvasElement
}

export interface RepackResult {
  bytes: Uint8Array
  pageCount: number
  /** Per-page JPEG sizes, so a caller can report the ratio it actually got. */
  jpegBytes: number[]
}

/** The pdf.js surface this module needs. Narrow on purpose: it keeps the
 *  library injectable, which is what lets the corpus generator load a
 *  browser-appropriate build without this module choosing one. */
export interface PdfJsLike {
  getDocument(src: { data: Uint8Array }): { promise: Promise<PdfDocumentLike> }
}
interface PdfDocumentLike {
  numPages: number
  getPage(n: number): Promise<PdfPageLike>
}
interface PdfPageLike {
  getViewport(o: { scale: number }): { width: number; height: number }
  render(o: {
    canvasContext: CanvasRenderingContext2D
    viewport: { width: number; height: number }
  }): { promise: Promise<void> }
}

function defaultCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  return c
}

async function canvasToJpeg(
  canvas: HTMLCanvasElement, quality: number,
): Promise<Uint8Array> {
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/jpeg', quality)
  })
  if (!blob) throw new Error('canvas.toBlob returned null')
  // A browser that cannot encode JPEG silently hands back a PNG. Catching it
  // HERE is the difference between "this document falls back to the original"
  // and "the server stores a 4 MB PNG believing it shrank the upload".
  if (blob.type !== 'image/jpeg') {
    throw new Error(`expected image/jpeg, got ${blob.type || '(none)'}`)
  }
  return new Uint8Array(await blob.arrayBuffer())
}

/**
 * Re-encode every page of `pdfBytes` as a JPEG at `dpi`, and reassemble them
 * into a new PDF whose pages keep their ORIGINAL physical size.
 *
 * Same size, not same pixels: a 595×842 pt A4 page stays 595×842 pt, and the
 * image inside it is that page rendered at `dpi`. So the server rasterising the
 * result at 200 DPI gets back what it would have got from the original scan at
 * 200 DPI — which is the whole claim the eval is there to test.
 *
 * THROWS rather than degrading. The caller owns the fallback, because the right
 * fallback differs by caller: the corpus generator must fail loudly (a silently
 * un-transformed fixture would make the eval compare a corpus against itself),
 * while the upload path must send the ORIGINAL file and carry on (§3.5a — never
 * block a teacher on a codec).
 */
export async function repackPdfToJpegPages(
  pdfjs: PdfJsLike,
  pdfBytes: Uint8Array,
  opts: RepackOptions,
): Promise<RepackResult> {
  const dpi = opts.dpi ?? PIPELINE_DPI
  const scale = dpi / PDF_UNITS_PER_INCH
  const makeCanvas = opts.createCanvas ?? defaultCanvas

  // pdf.js takes ownership of the buffer it is given and detaches it, so a
  // caller reusing its own bytes afterwards would find them empty.
  const doc = await pdfjs.getDocument({ data: pdfBytes.slice() }).promise
  const out = await PDFDocument.create()
  const jpegBytes: number[] = []

  for (let n = 1; n <= doc.numPages; n += 1) {
    const page = await doc.getPage(n)
    // `getViewport` already applies the page's own /Rotate, so a landscape
    // scan comes out landscape instead of sideways.
    const rendered = page.getViewport({ scale })
    const canvas = makeCanvas(Math.ceil(rendered.width), Math.ceil(rendered.height))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('2d canvas context unavailable')
    // Scans have no alpha, and an unpainted canvas is TRANSPARENT — which JPEG
    // renders as black. Paint the sheet first.
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    await page.render({ canvasContext: ctx, viewport: rendered }).promise

    const jpeg = await canvasToJpeg(canvas, opts.quality)
    jpegBytes.push(jpeg.length)

    const embedded = await out.embedJpg(jpeg)
    // The page keeps its original size in points: `rendered` is at `scale`, so
    // dividing takes it back to user space.
    const wPt = rendered.width / scale
    const hPt = rendered.height / scale
    const sheet = out.addPage([wPt, hPt])
    sheet.drawImage(embedded, { x: 0, y: 0, width: wPt, height: hPt })
  }

  return {
    bytes: await out.save(),
    pageCount: doc.numPages,
    jpegBytes,
  }
}

/**
 * Choose what to actually upload: the repack, or the original.
 *
 * MEASURED, NOT ASSUMED (corpus build, 2026-09-05, all 15 eval fixtures).
 *
 * THE RULE IS ABOUT THE ORIGINAL'S COMPRESSION, NOT ITS RESOLUTION — and the
 * obvious resolution story is WRONG, so it is written down here before someone
 * re-derives it. Both exam sets scan at ~255–282 DPI (measured off the embedded
 * images), so neither is "already too small to gain". What actually happens is
 * that this transform normalises every page to a roughly CONSTANT size at a
 * given quality — ~400–600 KB/page at q90. So:
 *   * bagrut pages average 892 KB each → shrink to ~406 → 2.2×;
 *   * hobby pages average 442 KB each → grow to ~606 → 0.73×.
 * A heavier original wins; one already lighter than our output loses. It is the
 * scanner app's compression that decides, and that varies per teacher — one
 * bagrut document (dan_basiuk, 288 KB/page) grows too.
 *
 * So the transform alone is not safe to apply blindly: on a real teacher's
 * batch it would sometimes make the upload she is waiting on LARGER, which is
 * the opposite of the entire point. This is the guard, and it is one
 * comparison: keep whichever is smaller. It turns "usually helps, sometimes
 * hurts" into "never hurts", and it lifts the whole-corpus figure at q90 from
 * 1.65× to 1.86× precisely by declining to hurt.
 *
 * A document that keeps its ORIGINAL needs no accuracy evidence — it is the
 * champion input, byte for byte. Only the repacked ones are a model-input
 * change, which is what the Stage E gate judges.
 */
export function chooseSmaller(
  original: Uint8Array, repacked: Uint8Array,
): { bytes: Uint8Array; usedRepack: boolean } {
  return repacked.length < original.length
    ? { bytes: repacked, usedRepack: true }
    : { bytes: original, usedRepack: false }
}
