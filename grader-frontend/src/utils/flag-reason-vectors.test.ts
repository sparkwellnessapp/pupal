import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { FLAG_REASON_LABELS, FLAG_REASON_UNKNOWN, flagReasonLabel } from '@/copy/batch'
import { IDENTITY_REASONS } from './batch-partition'

/**
 * Cross-pinned flag-reason vocabulary (closeout/B1) — the TS half.
 *
 * Reads THE SAME artifact as backend/tests/test_flag_reason_vectors.py (one
 * fixture, two consumers — the mechanism the audit asked for, not two
 * hand-maintained lists that drift apart while both stay green).
 *
 * The predicate itself is NOT mirrored: `partitionItems` consumes the
 * server's `review_needed`. What this pins is what the client genuinely owns
 * and can silently break —
 *   1. every server reason has a HEBREW label (F3: no raw Latin enum), and
 *   2. every server reason is classified identity-vs-content, because that
 *      split decides whether an item lands in the identity wave or the
 *      needs-eyes rows.
 */

const FIXTURE = join(
  process.cwd(), '..', 'backend', 'tests', 'fixtures', 'flag_reason_vocabulary.json',
)

interface Vector { reason: string; kind: 'identity' | 'content' }

const vectors: Vector[] = JSON.parse(readFileSync(FIXTURE, 'utf-8')).reasons

describe('flag-reason vocabulary — cross-pinned TS ⇄ PY', () => {
  it('reads the shared fixture (a missing file means the pin is broken, not absent)', () => {
    expect(vectors.length).toBeGreaterThan(0)
  })

  it('every server reason has a Hebrew label — a raw Latin enum must never render (F3)', () => {
    for (const { reason } of vectors) {
      const label = FLAG_REASON_LABELS[reason]
      expect(label, `no Hebrew label for server reason "${reason}"`).toBeTruthy()
      expect(label, `label for "${reason}" leaks Latin`).toMatch(/[֐-׿]/)
      expect(label).not.toMatch(/[A-Za-z_]/)
    }
  })

  it('every server reason is classified identity-vs-content (the wave/rows split)', () => {
    for (const { reason, kind } of vectors) {
      expect(
        IDENTITY_REASONS.has(reason),
        `"${reason}" is pinned as ${kind} but the client ${
          IDENTITY_REASONS.has(reason) ? 'treats it as identity' : 'treats it as content'
        }`,
      ).toBe(kind === 'identity')
    }
  })

  it('the client claims no identity reason the server cannot emit', () => {
    const pinned = new Set(vectors.map((v) => v.reason))
    for (const reason of Array.from(IDENTITY_REASONS)) {
      expect(pinned.has(reason), `client pins identity reason "${reason}" that is not in the shared vocabulary`).toBe(true)
    }
  })

  it('RUNTIME fallback: an unknown reason degrades to Hebrew, never a raw enum (F3 in the deploy window)', () => {
    // The repo-level pin cannot protect the minutes where Cloud Run has
    // shipped a new reason and Vercel has not.
    const warnings: unknown[] = []
    const original = console.warn
    console.warn = (...args: unknown[]) => { warnings.push(args[0]) }
    try {
      const label = flagReasonLabel('handwriting_illegible')
      expect(label).toBe(FLAG_REASON_UNKNOWN)
      expect(label).toMatch(/[֐-׿]/)
      expect(label).not.toMatch(/[A-Za-z_]/)
      expect(String(warnings[0])).toContain('handwriting_illegible')
    } finally {
      console.warn = original
    }
  })

  it('RUNTIME fallback passes known reasons through unchanged', () => {
    for (const { reason } of vectors) {
      expect(flagReasonLabel(reason)).toBe(FLAG_REASON_LABELS[reason])
    }
  })

  it('the label map carries no orphan the server never emits (dead copy)', () => {
    const pinned = new Set(vectors.map((v) => v.reason))
    const orphans = Object.keys(FLAG_REASON_LABELS).filter((k) => !pinned.has(k))
    expect(orphans, `FLAG_REASON_LABELS has orphans: ${orphans.join(', ')}`).toEqual([])
  })
})
