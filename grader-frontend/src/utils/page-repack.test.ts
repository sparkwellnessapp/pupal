import { describe, expect, it } from 'vitest'

import { chooseSmaller, PIPELINE_DPI } from './page-repack'

/**
 * The transform itself needs a real browser (Chromium's JPEG encoder is the
 * whole point) and is exercised in `e2e/page-repack.spec.ts`. What CAN be
 * tested here is the decision built on top of it — and that decision exists
 * because of a measurement, not a hunch.
 */

const bytes = (n: number) => new Uint8Array(n)

describe('chooseSmaller', () => {
  it('takes the repack when it actually saved something', () => {
    const r = chooseSmaller(bytes(9_170_000), bytes(3_000_000))
    expect(r.usedRepack).toBe(true)
    expect(r.bytes.length).toBe(3_000_000)
  })

  it('KEEPS THE ORIGINAL when re-encoding made the file bigger', () => {
    // Not hypothetical: all five hobby_tvshow fixtures came out larger at every
    // quality tested, because their scans are already at or below the 200 DPI
    // the pipeline reads — so re-rendering AT 200 DPI upsamples them. Without
    // this the upload a teacher is waiting on would sometimes GROW.
    const r = chooseSmaller(bytes(2_250_000), bytes(4_260_000))
    expect(r.usedRepack).toBe(false)
    expect(r.bytes.length).toBe(2_250_000)
  })

  it('keeps the original on an exact tie — no churn for no gain', () => {
    const r = chooseSmaller(bytes(1_000), bytes(1_000))
    expect(r.usedRepack).toBe(false)
  })

  it('pins the pipeline DPI it renders at', () => {
    // If PROD_CONFIG.dpi ever moves, this is the constant that has to follow —
    // and any change to it is a model-input change, so it is eval-gated.
    expect(PIPELINE_DPI).toBe(200)
  })
})
