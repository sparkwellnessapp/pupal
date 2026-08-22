/**
 * P2/D4 — the dashboard's item partition (framework-free, zero-mock-tested).
 *
 * One pass over the batch payload's items produces every set the dashboard
 * zones consume. The partition NEVER re-judges flags — `flag_verdict` is the
 * server's word (B1 made "clean" a server-guaranteed property); this module
 * only sorts the items by the verdict's SHAPE:
 *
 *   approved        terminal rows
 *   clean           !review_needed && no overlay        → clean panel
 *   touchedClean    !review_needed && overlay saved     → needs-eyes (Δ1)
 *   contentFlagged  ≥1 non-identity reason              → needs-eyes rows
 *   identityOnly    only identity reasons               → the wave, not rows
 *   identityPills   deduped names from student_unassigned items (D4)
 *   unmatchedItems  student_unmatched carriers          → dashed pills
 *
 * A mixed identity+content item is BOTH a pill source and a needs-eyes row
 * (D4 edge: creating its student drops only the identity chip).
 */

export interface PartitionItem {
  transcription_id: string
  filename: string | null
  transcription_status: 'transcribed' | 'approved'
  review: unknown | null
  student_name_suggestion: string | null
  flag_verdict: { review_needed: boolean; reasons: string[] }
}

export interface IdentityPill {
  /** First-seen ORIGINAL spelling (the teacher corrects it in place). */
  name: string
  transcriptionIds: string[]
  files: string[]
}

export interface Partition {
  approved: PartitionItem[]
  clean: PartitionItem[]
  touchedClean: PartitionItem[]
  contentFlagged: PartitionItem[]
  identityOnly: PartitionItem[]
  unmatchedItems: PartitionItem[]
  identityPills: IdentityPill[]
}

/** Exported for the cross-pinned vocabulary test (closeout/B1): this split
 *  decides identity-wave vs needs-eyes rows, and it is a hand-maintained
 *  mirror of the server's reason vocabulary. */
export const IDENTITY_REASONS = new Set(['student_unassigned', 'student_unmatched'])

/**
 * EXACT mirror of the server's batch_triage._normalize_name — NFC + lowercase
 * + trim + strip Hebrew niqqud/cantillation U+0591–U+05C7. Cross-pinned
 * vectors: batch-partition.test.ts ⇄ backend/tests/test_name_normalization_vectors.py
 * (the segmentation-grammar precedent — change one side, change the other).
 * (Python uses casefold(); toLowerCase() is identical over Hebrew, and the
 * vector table is the binding contract.)
 */
export function normalizeName(name: string): string {
  const nfc = name.normalize('NFC').toLowerCase().trim()
  let out = ''
  for (const ch of nfc) {
    const cp = ch.codePointAt(0) as number
    if (cp >= 0x0591 && cp <= 0x05c7) continue
    out += ch
  }
  return out
}

export function partitionItems(items: PartitionItem[]): Partition {
  const p: Partition = {
    approved: [], clean: [], touchedClean: [],
    contentFlagged: [], identityOnly: [],
    unmatchedItems: [], identityPills: [],
  }
  const pillsByNorm = new Map<string, IdentityPill>()

  for (const item of items) {
    if (item.transcription_status === 'approved') {
      p.approved.push(item)
      continue
    }

    const { review_needed, reasons } = item.flag_verdict
    if (!review_needed) {
      ;(item.review ? p.touchedClean : p.clean).push(item)
      continue
    }

    const contentReasons = reasons.filter((r) => !IDENTITY_REASONS.has(r))
    ;(contentReasons.length > 0 ? p.contentFlagged : p.identityOnly).push(item)

    if (reasons.includes('student_unmatched')) p.unmatchedItems.push(item)

    if (reasons.includes('student_unassigned')) {
      const suggestion = (item.student_name_suggestion ?? '').trim()
      if (suggestion) {
        const norm = normalizeName(suggestion)
        const pill = pillsByNorm.get(norm)
        if (pill) {
          pill.transcriptionIds.push(item.transcription_id)
          if (item.filename) pill.files.push(item.filename)
        } else {
          const fresh: IdentityPill = {
            name: suggestion,
            transcriptionIds: [item.transcription_id],
            files: item.filename ? [item.filename] : [],
          }
          pillsByNorm.set(norm, fresh)
          p.identityPills.push(fresh)
        }
      }
    }
  }
  return p
}
