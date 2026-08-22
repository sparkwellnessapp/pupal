/**
 * P5/L1 — the batches-list row derivations, PURE (spec §9).
 *
 * THE CONSTRAINT THAT SHAPES THIS FILE (the phase's open decision): the list
 * payload carries `rollup` and nothing else — no `transcriptions[]`. So the
 * dashboard's clean|needs-eyes split is NOT derivable here: `rollup.transcribed`
 * is one bucket holding both. Rather than invent a split (FC: never guess a
 * value the data doesn't contain), the list tells a COARSER truth — one
 * "awaiting your decision" segment — and says so in its copy.
 *
 * If the owner approves Option A (a `needs_eyes` field on `BatchRollup`,
 * RESOLVED (closeout, Ruling 1 — Option A approved): `rollup.needs_eyes` is
 * now computed server-side, so the split is real and the action line is
 * §3.2's `{F} דורשים עיון` verbatim. The interim merged segment and the
 * `{N} ממתינים להחלטה` line are retired; `pending` survives only for the
 * post-gate states (grading / grade-review) that owe her something else.
 */

import {
  LIST_ACTION_ALL_APPROVED,
  LIST_ACTION_FAILED,
  LIST_ACTION_NEEDS_EYES,
  LIST_ACTION_PENDING,
  LIST_ACTION_TRANSCRIBING,
} from '@/copy/batch'
import type { BarSegment } from './batch-dashboard'

export interface ListRollup {
  transcribing: number
  transcribed: number
  approved_transcription: number
  grading: number
  draft: number
  approved: number
  failed: number
  transcription_failed: number
  needs_eyes: number | null
  total: number
}

/**
 * The mini honesty bar, from rollup alone. Segment meanings, deliberately:
 *  - `approved`  — fully done.
 *  - `clean`     — past the transcription gate, moving through grading; no
 *                  decision is owed right now (approved_transcription + grading
 *                  + draft). Reusing the `clean` hue keeps one visual language
 *                  with D2 without claiming the dashboard's exact partition.
 *  - `eyes`      — the flagged-or-touched subset of `transcribed`
 *                  (server-computed: exactly what accept_clean refuses).
 *  - `moving`    — still transcribing.
 *  - `failed`    — dead transcriptions.
 */
export function listBarSegments(rollup: ListRollup): BarSegment[] {
  const inGrading = rollup.approved_transcription + rollup.grading + rollup.draft
  // Ruling 1 (Option A) — the split is REAL now: `needs_eyes` is the
  // flagged-or-touched subset, so the bulk-acceptable remainder is the rest
  // of `transcribed`. The interim merged segment is retired.
  // needs_eyes === null ⇒ the server could not compute it for this batch
  // (corrupt rubric contract). Degrade by OMISSION: fall back to ONE merged
  // "awaiting her decision" segment instead of inventing a split. Coarser,
  // never wrong.
  const known = rollup.needs_eyes !== null
  const eyes = known ? Math.min(rollup.needs_eyes!, rollup.transcribed) : rollup.transcribed
  const cleanWaiting = known ? Math.max(0, rollup.transcribed - eyes) : 0
  const all: BarSegment[] = [
    { kind: 'approved', count: rollup.approved },
    { kind: 'clean', count: inGrading + cleanWaiting },
    { kind: 'eyes', count: eyes },
    { kind: 'moving', count: rollup.transcribing },
    { kind: 'failed', count: rollup.transcription_failed },
  ]
  return all.filter((s) => s.count > 0)
}

export type ListActionKind = 'transcribing' | 'eyes' | 'pending' | 'failed' | 'done'

export interface ListAction {
  kind: ListActionKind
  text: string
}

/**
 * ONE action line per row (§3.2), precedence top-down:
 *  1. still arriving        → `{T} בתמלול`
 *  2. decisions owed        → the merged pending count (OPTION-A: `{F} דורשים עיון`)
 *  3. nothing owed, failures→ the failure line (never a false completion)
 *  4. everything approved   → `הכל אושר ✓`
 * An empty batch has no line at all.
 */
export function listActionLine(rollup: ListRollup): ListAction | null {
  if (rollup.total === 0) return null

  if (rollup.transcribing > 0) {
    return { kind: 'transcribing', text: LIST_ACTION_TRANSCRIBING(rollup.transcribing) }
  }

  // Ruling 1: needs-eyes is the sharp signal and wins — "5 דורשים עיון" is
  // information the status pill does not already carry, which the interim's
  // merged count was not (it paraphrased "ממתין להחלטות" directly above it).
  if (rollup.needs_eyes !== null && rollup.needs_eyes > 0) {
    return { kind: 'eyes', text: LIST_ACTION_NEEDS_EYES(rollup.needs_eyes) }
  }
  // Everything else past the transcription gate but short of `approved` still
  // owes her something — a bulk accept, or a grade review.
  const pending = rollup.transcribed
    + rollup.approved_transcription + rollup.grading + rollup.draft
  if (pending > 0) {
    return { kind: 'pending', text: LIST_ACTION_PENDING(pending) }
  }

  if (rollup.transcription_failed > 0 || rollup.failed > 0) {
    const n = rollup.transcription_failed + rollup.failed
    return { kind: 'failed', text: LIST_ACTION_FAILED(n) }
  }

  return { kind: 'done', text: LIST_ACTION_ALL_APPROVED }
}
