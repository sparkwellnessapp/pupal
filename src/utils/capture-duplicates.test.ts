import { describe, expect, it } from 'vitest'

import type { CaptureSubmissionRow } from '@/types/capture'

import { canKeep, claimName, duplicateRows, groupOfTranscription } from './capture-duplicates'

function row(over: Partial<CaptureSubmissionRow>): CaptureSubmissionRow {
  return {
    submission_id: 's', source: 'student_link', student_state: 'conflict', page_count: 2,
    duplicate_group: 'g', saved_at: '2026-10-29T17:00:00Z', ...over,
  } as CaptureSubmissionRow
}

describe('duplicateRows', () => {
  it('returns the group oldest set first, and nothing for no key', () => {
    const rows = [
      row({ submission_id: 'b', saved_at: '2026-10-29T18:52:00Z' }),
      row({ submission_id: 'x', duplicate_group: null, student_state: 'confirmed' }),
      row({ submission_id: 'a', saved_at: '2026-10-29T17:48:00Z' }),
    ]
    expect(duplicateRows(rows, 'g').map((r) => r.submission_id)).toEqual(['a', 'b'])
    expect(duplicateRows(rows, null)).toEqual([])
  })
})

describe('groupOfTranscription', () => {
  it("finds the group of a triage card's transcription", () => {
    const rows = [row({ submission_id: 'a', transcription_id: 't1' }),
                  row({ submission_id: 'b', transcription_id: 't2', duplicate_group: null })]
    expect(groupOfTranscription(rows, 't1')).toBe('g')
    expect(groupOfTranscription(rows, 't2')).toBeNull()
    expect(groupOfTranscription(rows, 'missing')).toBeNull()
  })
})

describe('canKeep (SCN-14)', () => {
  it('lets her keep any set when none is approved', () => {
    const group = [row({ submission_id: 'a' }), row({ submission_id: 'b' })]
    expect(group.every((r) => canKeep(group, r))).toBe(true)
  })
  it('lets her keep only the approved set when one is approved', () => {
    const approved = row({ submission_id: 'a', transcription_status: 'approved' })
    const other = row({ submission_id: 'b', transcription_status: 'transcribed' })
    expect(canKeep([approved, other], approved)).toBe(true)
    expect(canKeep([approved, other], other)).toBe(false)
  })
})

describe('claimName', () => {
  it('prefers the confirmed student over what was typed', () => {
    expect(claimName(row({ student: { student_id: 'x', display_name: 'דני כהן' },
                           pending_student_name: 'דני' }))).toBe('דני כהן')
    expect(claimName(row({ pending_student_name: 'נועה בר' }))).toBe('נועה בר')
  })
})
