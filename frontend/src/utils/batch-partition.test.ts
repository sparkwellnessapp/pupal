/**
 * P2/D4 — partitionItems + normalizeName (zero-mock unit tests).
 *
 * normalizeName mirrors the server's batch_triage._normalize_name EXACTLY
 * (NFC + casefold + trim + strip Hebrew niqqud U+0591–U+05C7). The vector
 * table below is CROSS-PINNED with backend/tests/test_name_normalization_vectors.py
 * — change one side, change the other (the segmentation-grammar precedent).
 */
import { describe, expect, it } from 'vitest'

import {
  normalizeName,
  partitionItems,
  type PartitionItem,
} from '@/utils/batch-partition'

// ---------------------------------------------------------------------------
// Cross-pinned vectors (TS ⇄ PY)
// ---------------------------------------------------------------------------

const VECTORS: Array<[string, string]> = [
  ['  דנה לוי ', 'דנה לוי'],
  ['דָּנָה לֵוִי', 'דנה לוי'],          // niqqud stripped
  ['Dana Levi', 'dana levi'],           // casefold
  ['נועהְ שריד', 'נועה שריד'],     // combining sheva stripped
  ['אִיתַי כֹּהֵן', 'איתי כהן'],
]

describe('normalizeName (server-mirrored)', () => {
  it.each(VECTORS)('normalizes %s → %s', (input, expected) => {
    expect(normalizeName(input)).toBe(expected)
  })

  it('two spellings of the same name collide after normalization', () => {
    expect(normalizeName('דָּנָה לֵוִי')).toBe(normalizeName('דנה לוי '))
  })
})

// ---------------------------------------------------------------------------
// partitionItems
// ---------------------------------------------------------------------------

function item(id: string, over: Partial<PartitionItem> = {}): PartitionItem {
  return {
    transcription_id: id,
    filename: `${id}.pdf`,
    transcription_status: 'transcribed',
    review: null,
    student_name_suggestion: null,
    flag_verdict: { review_needed: false, reasons: [] },
    ...over,
  }
}

describe('partitionItems (D4/D5/D6 partitions)', () => {
  it('splits approved / clean / touchedClean / contentFlagged / identity-only', () => {
    const p = partitionItems([
      item('ap', { transcription_status: 'approved' }),
      item('cl'),
      item('tc', { review: { answers: [] } }),
      item('cf', { flag_verdict: { review_needed: true, reasons: ['missing_answers'] } }),
      item('io', {
        flag_verdict: { review_needed: true, reasons: ['student_unassigned'] },
        student_name_suggestion: 'נועה שריד',
      }),
    ])
    expect(p.approved.map(i => i.transcription_id)).toEqual(['ap'])
    expect(p.clean.map(i => i.transcription_id)).toEqual(['cl'])
    expect(p.touchedClean.map(i => i.transcription_id)).toEqual(['tc'])
    expect(p.contentFlagged.map(i => i.transcription_id)).toEqual(['cf'])
    expect(p.identityOnly.map(i => i.transcription_id)).toEqual(['io'])
    expect(p.identityPills).toEqual([
      { name: 'נועה שריד', transcriptionIds: ['io'], files: ['io.pdf'] },
    ])
  })

  it('dedupes pills by normalized name — two files, one student, one pill', () => {
    const p = partitionItems([
      item('a', {
        flag_verdict: { review_needed: true, reasons: ['student_unassigned'] },
        student_name_suggestion: 'דָּנָה לֵוִי',
      }),
      item('b', {
        flag_verdict: { review_needed: true, reasons: ['student_unassigned'] },
        student_name_suggestion: 'דנה לוי ',
      }),
    ])
    expect(p.identityPills).toHaveLength(1)
    expect(p.identityPills[0].name).toBe('דָּנָה לֵוִי')       // first-seen original
    expect(p.identityPills[0].transcriptionIds).toEqual(['a', 'b'])
    expect(p.identityPills[0].files).toEqual(['a.pdf', 'b.pdf'])
  })

  it('mixed identity+content item is contentFlagged (needs-eyes row) AND a pill source', () => {
    const p = partitionItems([
      item('mx', {
        flag_verdict: {
          review_needed: true,
          reasons: ['student_unassigned', 'unparseable'],
        },
        student_name_suggestion: 'רוני אלקיים',
      }),
    ])
    expect(p.contentFlagged.map(i => i.transcription_id)).toEqual(['mx'])
    expect(p.identityOnly).toEqual([])
    expect(p.identityPills.map(pl => pl.name)).toEqual(['רוני אלקיים'])
  })

  it('student_unmatched items become dashed-pill sources, not name pills', () => {
    const p = partitionItems([
      item('un', {
        flag_verdict: { review_needed: true, reasons: ['student_unmatched'] },
      }),
    ])
    expect(p.unmatchedItems.map(i => i.transcription_id)).toEqual(['un'])
    expect(p.identityPills).toEqual([])
    expect(p.identityOnly.map(i => i.transcription_id)).toEqual(['un'])
  })

  it('a touched item with a flag stays flagged (review overlay does not launder a verdict)', () => {
    const p = partitionItems([
      item('fx', {
        review: { answers: [] },
        flag_verdict: { review_needed: true, reasons: ['unparseable'] },
      }),
    ])
    expect(p.contentFlagged.map(i => i.transcription_id)).toEqual(['fx'])
    expect(p.touchedClean).toEqual([])
  })

  it('empty input → empty partitions', () => {
    const p = partitionItems([])
    expect(p.identityPills).toEqual([])
    expect(p.clean).toEqual([])
    expect(p.approved).toEqual([])
  })
})
