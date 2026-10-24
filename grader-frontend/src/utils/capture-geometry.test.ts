import { describe, expect, it } from 'vitest'

import { contentTypeOf, orderFiles } from './capture-files'
import {
  FULL_FRAME, applyHomography, homography, isValidQuad, previewAspect, quadToRectMatrix3d,
  type QuadPts,
} from './capture-geometry'

const QUAD: QuadPts = [[0.1, 0.1], [0.9, 0.12], [0.88, 0.9], [0.12, 0.88]]

describe('isValidQuad — the client twin of capture/geometry.validate_corners', () => {
  it('accepts a page and the full frame', () => {
    expect(isValidQuad(QUAD)).toBe(true)
    expect(isValidQuad(FULL_FRAME)).toBe(true)
  })
  it.each<[string, QuadPts]>([
    ['bow tie', [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]],
    ['concave', [[0.1, 0.1], [0.9, 0.1], [0.5, 0.3], [0.1, 0.9]]],
    ['tiny', [[0.4, 0.4], [0.5, 0.4], [0.5, 0.5], [0.4, 0.5]]],
    ['outside', [[0.1, 0.1], [1.2, 0.1], [0.9, 0.9], [0.1, 0.9]]],
  ])('refuses a %s quad', (_, q) => {
    expect(isValidQuad(q)).toBe(false)
  })
})

describe('homography — the D8 preview', () => {
  it('maps every source corner onto its target', () => {
    const dst: QuadPts = [[0, 0], [200, 0], [200, 283], [0, 283]]
    const h = homography(QUAD, dst)
    QUAD.forEach((p, i) => {
      const [x, y] = applyHomography(h, p)
      expect(x).toBeCloseTo(dst[i][0], 6)
      expect(y).toBeCloseTo(dst[i][1], 6)
    })
  })
  it('the full frame onto an equal box is the identity matrix', () => {
    expect(quadToRectMatrix3d(FULL_FRAME, 100, 140, 100, 140))
      .toBe('matrix3d(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)')
  })
})

describe('previewAspect — D11 mirrored', () => {
  it('forces A4 within 12% and keeps a strip as measured', () => {
    expect(previewAspect([[0, 0], [1, 0], [1, 1], [0, 1]], 1000, 1350)).toBeCloseTo(Math.SQRT2)
    expect(previewAspect([[0, 0], [1, 0], [1, 1], [0, 1]], 1000, 500)).toBeCloseTo(0.5)
  })
})

describe('capture files — D15', () => {
  it('orders by lastModified, then numerically by name', () => {
    const f = (name: string, lastModified: number) => ({ name, lastModified })
    expect(orderFiles([f('b.jpg', 2), f('page10.jpg', 1), f('page2.jpg', 1)]).map((x) => x.name))
      .toEqual(['page2.jpg', 'page10.jpg', 'b.jpg'])
  })
  it('a HEIC with an empty type is still a HEIC; a PDF is refused', () => {
    expect(contentTypeOf({ name: 'IMG_1.HEIC', type: '' })).toBe('image/heic')
    expect(contentTypeOf({ name: 'a.jpg', type: 'image/jpeg' })).toBe('image/jpeg')
    expect(contentTypeOf({ name: 'scan.pdf', type: 'application/pdf' })).toBeNull()
  })
})

describe('isValidQuad — the server twin refuses a MIRRORED quad', () => {
  it('accepts TL, TR, BR, BL clockwise on screen and refuses it reversed', () => {
    const page: QuadPts = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    expect(isValidQuad(page)).toBe(true)
    const mirrored: QuadPts = [[0.9, 0.1], [0.1, 0.1], [0.1, 0.9], [0.9, 0.9]]
    expect(isValidQuad(mirrored)).toBe(false)
  })
})
