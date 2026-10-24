/**
 * Corner geometry for the capture surfaces — pure.
 *
 *  * `isValidQuad` is the CLIENT twin of backend capture/geometry.validate_corners
 *    (four points in [0,1], convex, non-crossing, ≥ 5% of the frame): a drag
 *    that breaks it snaps back before any request is made. The server stays
 *    the authority (422).
 *  * `quadToRectMatrix3d` is D8's thumbnail: a CSS `matrix3d` that maps the
 *    page's quad in the photo onto a rectangle — a geometric preview, no
 *    server render. Lighting cleanup happens only at compilation.
 */

export type Pt = [number, number]
export type QuadPts = [Pt, Pt, Pt, Pt]

export const FULL_FRAME: QuadPts = [[0, 0], [1, 0], [1, 1], [0, 1]]
export const MIN_AREA_FRACTION = 0.05

export function toQuad(q: number[][] | null | undefined): QuadPts {
  if (!q || q.length !== 4) return FULL_FRAME.map((p) => [...p]) as QuadPts
  return q.map((p) => [p[0], p[1]]) as QuadPts
}

function cross(o: Pt, a: Pt, b: Pt): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
}

export function quadArea(q: QuadPts): number {
  let s = 0
  for (let i = 0; i < 4; i++) {
    const [x1, y1] = q[i]
    const [x2, y2] = q[(i + 1) % 4]
    s += x1 * y2 - x2 * y1
  }
  return Math.abs(s) / 2
}

export function isValidQuad(q: QuadPts): boolean {
  if (q.some(([x, y]) => !(x >= 0 && x <= 1 && y >= 0 && y <= 1))) return false
  const turns = [0, 1, 2, 3].map((i) => cross(q[i], q[(i + 1) % 4], q[(i + 2) % 4]))
  // Clockwise on screen (TL, TR, BR, BL) — the server's rule; a mirrored quad is refused.
  if (!turns.every((t) => t > 1e-9)) return false
  return quadArea(q) >= MIN_AREA_FRACTION
}

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

/** Solve A·x = b (8×8) by Gaussian elimination with partial pivoting. */
function solve(a: number[][], b: number[]): number[] {
  const n = b.length
  const m = a.map((row, i) => [...row, b[i]])
  for (let c = 0; c < n; c++) {
    let p = c
    for (let r = c + 1; r < n; r++) if (Math.abs(m[r][c]) > Math.abs(m[p][c])) p = r
    ;[m[c], m[p]] = [m[p], m[c]]
    const d = m[c][c]
    if (Math.abs(d) < 1e-12) throw new Error('singular homography')
    for (let r = 0; r < n; r++) {
      if (r === c) continue
      const f = m[r][c] / d
      for (let k = c; k <= n; k++) m[r][k] -= f * m[c][k]
    }
  }
  return m.map((row, i) => row[n] / row[i])
}

/** The 3×3 homography (row-major, h33 = 1) taking src[i] → dst[i]. */
export function homography(src: QuadPts, dst: QuadPts): number[] {
  const a: number[][] = []
  const b: number[] = []
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i]
    const [u, v] = dst[i]
    a.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u)
    a.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v)
  }
  return [...solve(a, b), 1]
}

export function applyHomography(h: number[], [x, y]: Pt): Pt {
  const w = h[6] * x + h[7] * y + h[8]
  return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w]
}

/** CSS `matrix3d(...)` for an element of size (imgW × imgH) px whose
 *  normalized `quad` must land on a (boxW × boxH) px rectangle. Apply with
 *  `transform-origin: 0 0` inside an `overflow: hidden` box. */
export function quadToRectMatrix3d(quad: QuadPts, imgW: number, imgH: number,
                                   boxW: number, boxH: number): string {
  const src = quad.map(([x, y]) => [x * imgW, y * imgH]) as QuadPts
  const dst: QuadPts = [[0, 0], [boxW, 0], [boxW, boxH], [0, boxH]]
  const h = homography(src, dst)
  // CSS matrix3d is COLUMN-major: (a1 b1 c1 d1, a2 b2 c2 d2, …).
  const m = [h[0], h[3], 0, h[6], h[1], h[4], 0, h[7], 0, 0, 1, 0, h[2], h[5], 0, h[8]]
  return `matrix3d(${m.map((v) => (Math.abs(v) < 1e-12 ? 0 : v)).join(',')})`
}

/** The aspect (height / width) the compiled page will have — the D11 rule,
 *  mirrored for the preview box: within 12% of A4 → exactly A4. */
export function previewAspect(quad: QuadPts, imgW: number, imgH: number): number {
  const p = quad.map(([x, y]) => [x * imgW, y * imgH])
  const d = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1])
  const width = Math.max(d(p[0], p[1]), d(p[3], p[2]))
  const height = Math.max(d(p[0], p[3]), d(p[1], p[2]))
  if (width <= 0 || height <= 0) return Math.SQRT2
  const portrait = height >= width
  const ratio = portrait ? height / width : width / height
  const a4 = Math.abs(ratio / Math.SQRT2 - 1) <= 0.12 ? Math.SQRT2 : ratio
  return portrait ? a4 : 1 / a4
}
