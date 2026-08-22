import { describe, expect, it } from 'vitest'
import { detectMismatch, keyLabel, parseLeadingMarker, type AnswerKey } from './segmentation-check'

/**
 * CROSS-PINNED with backend/tests/services/test_segmentation_check.py:
 * the grammar fixtures are the SAME strings — a rule change must keep both
 * suites green or the two implementations have drifted.
 */

describe('parseLeadingMarker — grammar (shared fixtures)', () => {
  it('letter-paren-digit: "א) 3"', () => {
    expect(parseLeadingMarker('א) 3\npublic static int[] DiceStatistics(int[] arr)'))
      .toEqual({ question: 3, sub: 'א' })
  })

  it('digit-paren-letter: "3 (א"', () => {
    expect(parseLeadingMarker('3 (א\npublic static ...')).toEqual({ question: 3, sub: 'א' })
  })

  it('question word then sub letter composes: "שאלה 5" + "א."', () => {
    expect(parseLeadingMarker('שאלה 5\nא.\npublic bool IsSimilar(...)'))
      .toEqual({ question: 5, sub: 'א' })
  })

  it('sub-only marker claims no question: "ב)"', () => {
    expect(parseLeadingMarker('ב)\npublic static void PrintStatistics(int[] arr)'))
      .toEqual({ question: null, sub: 'ב' })
  })

  it('content first line claims nothing (trace table)', () => {
    expect(parseLeadingMarker('if:\nreturned | x | i | arr[i]'))
      .toEqual({ question: null, sub: null })
  })

  it('digits inside code never match', () => {
    expect(parseLeadingMarker('int[] counters = new int[21];'))
      .toEqual({ question: null, sub: null })
  })

  it('marker glued to content is not a marker (full-match only)', () => {
    expect(parseLeadingMarker('3 (א public static void F()'))
      .toEqual({ question: null, sub: null })
  })

  it('scan stops at the first non-marker line (no mid-text markers)', () => {
    expect(parseLeadingMarker('public int F()\nשאלה 4'))
      .toEqual({ question: null, sub: null })
  })

  it('two-digit question', () => {
    expect(parseLeadingMarker('שאלה 12')).toEqual({ question: 12, sub: null })
  })
})

// The real incident document (49f9a2e1): student skipped Q2; P2 renumbered.
const INCIDENT_KEYS: AnswerKey[] = [
  { question_number: 1, sub_question_id: 'א' },
  { question_number: 1, sub_question_id: 'ב' },
  { question_number: 2, sub_question_id: 'א' },
  { question_number: 2, sub_question_id: 'ב' },
  { question_number: 3, sub_question_id: 'א' },
  { question_number: 3, sub_question_id: 'ב' },
  { question_number: 4, sub_question_id: 'א' },
  { question_number: 4, sub_question_id: 'ב' },
  { question_number: 5, sub_question_id: null },
  { question_number: 6, sub_question_id: null },
]

describe('detectMismatch — the incident document', () => {
  it('q2.א holding "א) 3" content proposes the exact target q3.א', () => {
    const m = detectMismatch(
      'א) 3\npublic static int[] DiceStatistics(int[] arr)',
      { question_number: 2, sub_question_id: 'א' },
      INCIDENT_KEYS,
    )
    expect(m).toEqual({
      declaredQuestion: 3,
      proposedTarget: { question_number: 3, sub_question_id: 'א' },
    })
  })

  it('q4.א holding "שאלה 5\\nא." falls back to the bare q5 container (ruled)', () => {
    const m = detectMismatch(
      'שאלה 5\nא.',
      { question_number: 4, sub_question_id: 'א' },
      INCIDENT_KEYS,
    )
    expect(m).toEqual({
      declaredQuestion: 5,
      proposedTarget: { question_number: 5, sub_question_id: null },
    })
  })

  it('a matching marker is silent', () => {
    expect(detectMismatch(
      'א) 3\npublic static int[] DiceStatistics(int[] arr)',
      { question_number: 3, sub_question_id: 'א' },
      INCIDENT_KEYS,
    )).toBeNull()
  })

  it('sub-only markers never fire', () => {
    expect(detectMismatch(
      'ב)\npublic static void PrintStatistics(int[] arr)',
      { question_number: 2, sub_question_id: 'ב' },
      INCIDENT_KEYS,
    )).toBeNull()
  })

  it('declared target missing entirely yields a mismatch with no proposal', () => {
    const m = detectMismatch(
      'א) 9\nsome code',
      { question_number: 2, sub_question_id: 'א' },
      INCIDENT_KEYS,
    )
    expect(m).toEqual({ declaredQuestion: 9, proposedTarget: null })
  })

  it('LIVE recomputation: after the teacher swaps the text into q3.א, the banner clears', () => {
    // The same text evaluated under its new container — no mismatch.
    expect(detectMismatch(
      'א) 3\npublic static int[] DiceStatistics(int[] arr)',
      { question_number: 3, sub_question_id: 'א' },
      INCIDENT_KEYS,
    )).toBeNull()
  })
})

describe('keyLabel', () => {
  it('renders with and without a sub-question', () => {
    expect(keyLabel({ question_number: 3, sub_question_id: 'א' })).toBe('שאלה 3 סעיף א')
    expect(keyLabel({ question_number: 5, sub_question_id: null })).toBe('שאלה 5')
  })
})
