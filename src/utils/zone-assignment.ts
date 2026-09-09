/**
 * ZC-1 — zone assignment (owner directive 2026-08-22): every uploaded
 * transcription lands in EXACTLY ONE actionable zone:
 *
 *     transcribed = Σ(eyesRows) + Σ(cleanRows)
 *
 * THE BUG THIS KILLS: the dashboard built its eyes rows with an inline spread
 * that kept only HALF of the identity-flagged bucket —
 * `identityOnly.filter(reasons ∋ 'student_unmatched')` — so an item flagged
 * ONLY `student_unassigned` (clean content + a successfully-extracted NEW
 * name; דן בסיוק in the owner's live batch) had NO row anywhere: not clean
 * (review_needed=true), not eyes (filtered), only a name pill in the identity
 * wave. The wave is an accelerator OVERLAY, never a home. The incidence
 * exploded once identity extraction became reliable (filename fallback +
 * the concurrency fix), because clean-content fixtures now land in exactly
 * the excluded sub-bucket.
 *
 * MEMBERSHIP = THE SERVER'S OWN PREDICATE. eyesRows is contentFlagged ∪
 * (identityOnly ∖ identity-pending) ∪ touchedClean — precisely `needs_eyes`
 * (v2: flagged-beyond-a-new-name ∨ touched) restricted to unapproved rows;
 * cleanRows absorbs the identity-pending items (owner refinement
 * 2026-08-23), keeping the ZC-1 sum intact. With this selector the
 * bar, the zone rows, the review walk, the list page and `accept_clean`'s
 * refusals all answer "who needs her?" identically. One number, five
 * surfaces.
 *
 * TOTALITY: built on `partitionItems`, whose classification is a single
 * exhaustive branch per item (approved | clean | touchedClean |
 * contentFlagged | identityOnly) — nothing can fall through TODAY. The sum
 * check below is a tripwire for the future refactor that adds a bucket and
 * forgets to map it: dev throws; production logs and ships the rows it has
 * (an unmapped item is a bug either way, but a silent one is how ZC-1 broke
 * the first time).
 */

import { partitionItems, type PartitionItem } from './batch-partition'

/**
 * ZC-1 v2 (owner refinement 2026-08-23): "identity-pending" — content is
 * clean, the ONLY flag is a successfully-extracted NEW student name, and the
 * teacher has not touched it. Its home is the CLEAN panel (per-item link
 * included), its name rides the identity wave, and it is EXCLUDED from the
 * bulk-accept count until the student exists (the server's accept_clean
 * would refuse it anyway — verdict flagged). Δ1 outranks this: a touched
 * item needs her eyes regardless.
 *
 * This predicate is the frontend HALF of a cross-language rule — the server's
 * `_needs_eyes` applies the same exclusion (batch_grading.py). Twin tests on
 * both sides reference each other; change one, change the other.
 */
export function isIdentityPending(item: PartitionItem): boolean {
  if (item.transcription_status !== 'transcribed') return false
  if (item.review != null) return false
  const { review_needed, reasons } = item.flag_verdict
  if (!review_needed || reasons.length === 0) return false
  return reasons.every((r) => r === 'student_unassigned')
}

export interface ZoneAssignment<T extends PartitionItem> {
  /** Needs her eyes: content-flagged ∪ identity-flagged (BOTH sub-cases) ∪
   *  teacher-touched. Display order: content, identity, touched (D6). */
  eyesRows: T[]
  /** Bulk-acceptable: clean verdict, untouched. */
  cleanRows: T[]
  approved: T[]
}

export function assignZones<T extends PartitionItem>(items: T[]): ZoneAssignment<T> {
  const p = partitionItems(items)
  // v2: identityOnly splits by the pending predicate — pending → CLEAN
  // (their home; the wave is an overlay), everything else → eyes. The v1 bug
  // (an item with NO home) stays impossible: both halves are assigned.
  const identityPending = p.identityOnly.filter(isIdentityPending)
  const identityEyes = p.identityOnly.filter((i) => !isIdentityPending(i))
  const eyesRows = [
    ...p.contentFlagged,
    ...identityEyes,
    ...p.touchedClean,
  ] as T[]
  const cleanRows = [...p.clean, ...identityPending] as T[]
  const approved = p.approved as T[]

  const assigned = eyesRows.length + cleanRows.length + approved.length
  if (assigned !== items.length) {
    const msg =
      `ZC-1 VIOLATION: ${items.length} transcription(s) but only ${assigned} ` +
      'assigned to a zone — partitionItems grew a bucket assignZones does not map. ' +
      'Every transcription must land in eyesRows, cleanRows, or approved.'
    if (process.env.NODE_ENV !== 'production') throw new Error(msg)
    // eslint-disable-next-line no-console
    console.error(msg)
  }
  return { eyesRows, cleanRows, approved }
}
