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
 * identityOnly(ALL) ∪ touchedClean — precisely `needs_eyes` (flagged ∨
 * touched, Ruling 1) restricted to unapproved rows. With this selector the
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
  const eyesRows = [
    ...p.contentFlagged,
    ...p.identityOnly,          // ALL of it — never filtered by sub-reason
    ...p.touchedClean,
  ] as T[]
  const cleanRows = p.clean as T[]
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
