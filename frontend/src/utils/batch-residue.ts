/**
 * Δ15 — the progress-based un-transcribed residue.
 *
 * A batch item whose transcription failed leaves NO row (the fan-out swallows
 * the exception), so `test_count - rows` is the only visible residue. The
 * gate/completion computation counts ROWS ONLY — phantom items are never
 * reviewable; this line is how they stop being invisible.
 */

import { UNTRANSCRIBED_RESIDUE_HORIZON_MS } from '@/lib/constants'

export interface ResidueInput {
  testCount: number
  batchCreatedAt: string
  /** created_at of every transcription row present (ISO). */
  itemCreatedAts: string[]
  /** Current time in ms (Date.now()) — injected for testability. */
  now: number
}

export interface ResidueResult {
  /** Files with no transcription row. */
  missing: number
  /** True when the residue line should render (missing > 0 AND stuck past the horizon). */
  visible: boolean
}

export function untranscribedResidue(input: ResidueInput): ResidueResult {
  const missing = Math.max(0, input.testCount - input.itemCreatedAts.length)
  if (missing === 0) return { missing: 0, visible: false }

  const timestamps = [input.batchCreatedAt, ...input.itemCreatedAts]
    .map((t) => Date.parse(t))
    .filter((t) => !Number.isNaN(t))
  if (timestamps.length === 0) return { missing, visible: false }

  const lastProgress = Math.max(...timestamps)
  return {
    missing,
    visible: input.now - lastProgress > UNTRANSCRIBED_RESIDUE_HORIZON_MS,
  }
}
