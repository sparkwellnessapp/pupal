import { describe, expect, it } from 'vitest'
import { answerTargetId, deriveReviewFlags } from './review-flags'
import type { TranscriptionAnnotation } from '@/types/transcription'

const DRAFT = 'public int foo() {\n    return salary;\n}\n// תכונות'

function disagreement(lineQuote: string, opts?: Partial<TranscriptionAnnotation>): TranscriptionAnnotation {
  return {
    id: 'a1',
    severity: 'warning',
    target_id: 'q1',
    annotation_type: 'reader_disagreement',
    message: 'קריאה חוזרת של קטע זה זיהתה נוסח שונה',
    metadata: {
      page: 1,
      line_quote: lineQuote,
      transcribed: 'return salary;',
      alternatives: ['return this.salary;'],
      n_readers: 2,
      // DELIBERATELY MISLEADING offsets — they index the baseline PAGE text
      // (flagging.py L93-94) and must be ignored entirely (Δ6): as answer
      // offsets they would point at line 1, not the quote's line.
      char_start: 0,
      char_end: 10,
      anchor_similarity: 0.91,
    },
    ...opts,
  }
}

function lint(): TranscriptionAnnotation {
  return {
    id: 'a2', severity: 'info', target_id: 'q1', annotation_type: 'code_lint',
    message: 'סוגריים מסולסלים לא מאוזנים בתשובה זו (+1)', metadata: { balance: 1 },
  }
}

describe('deriveReviewFlags — frame of reference (Δ6)', () => {
  it('locates the line by trimmed-exact line_quote match; offsets are ignored', () => {
    const { lineFlags } = deriveReviewFlags({
      currentText: DRAFT, draftText: DRAFT,
      annotations: [disagreement('return salary;')], // draft has it indented; trimmed match
      dissolved: false,
    })
    // line 2, NOT line 1 (where the misleading char offsets would point)
    expect(lineFlags).toHaveLength(1)
    expect(lineFlags[0].line).toBe(2)
    expect(lineFlags[0].reason).toContain('return this.salary;')
  })

  it('a quote that does not exact-match degrades to an answer-level badge — never dropped', () => {
    const { lineFlags, badges } = deriveReviewFlags({
      currentText: DRAFT, draftText: DRAFT,
      annotations: [disagreement('some line the fuzzy matcher accepted but exact does not')],
      dissolved: false,
    })
    expect(lineFlags).toHaveLength(0)
    expect(badges).toHaveLength(1)
  })

  it('code_lint is always an answer-level badge', () => {
    const { badges } = deriveReviewFlags({
      currentText: DRAFT, draftText: DRAFT, annotations: [lint()], dissolved: false,
    })
    expect(badges).toEqual(['סוגריים מסולסלים לא מאוזנים בתשובה זו (+1)'])
  })
})

describe('flag dissolution on edit (Δ7) and [?] liveness', () => {
  it('unedited answer: span flags and [?] flags both present', () => {
    const text = DRAFT + '\nx = [?];'
    const { lineFlags } = deriveReviewFlags({
      currentText: text, draftText: text,
      annotations: [disagreement('return salary;')], dissolved: false,
    })
    expect(lineFlags.map((f) => f.line)).toEqual([2, 5])
  })

  it('any edit dissolves span flags while [?] flags track the LIVE content', () => {
    const edited = DRAFT.replace('return salary;', 'return this.salary; // [?] fixed')
    const { lineFlags } = deriveReviewFlags({
      currentText: edited, draftText: DRAFT,
      annotations: [disagreement('return salary;')], dissolved: false,
    })
    // span flag gone (text diverged); the teacher-typed [?] appears as a new live flag
    expect(lineFlags).toHaveLength(1)
    expect(lineFlags[0].line).toBe(2)
    expect(lineFlags[0].reason).toContain('[?]')
  })

  it('dissolved memory: reverting to byte-identical draft text does NOT resurrect span flags', () => {
    const { lineFlags } = deriveReviewFlags({
      currentText: DRAFT, draftText: DRAFT,           // reverted — texts equal again
      annotations: [disagreement('return salary;')],
      dissolved: true,                                 // the shell remembered the edit
    })
    expect(lineFlags).toHaveLength(0)
  })

  it('Δ17 stated consequence: after refresh (memory gone) flags on draft-identical text render again', () => {
    const { lineFlags } = deriveReviewFlags({
      currentText: DRAFT, draftText: DRAFT,
      annotations: [disagreement('return salary;')],
      dissolved: false,                                // fresh session
    })
    expect(lineFlags).toHaveLength(1)
  })
})

describe('answerTargetId mirrors backend answer_target', () => {
  it('builds q{n} and q{n}.{sub}', () => {
    expect(answerTargetId({ question_number: 1, sub_question_id: null })).toBe('q1')
    expect(answerTargetId({ question_number: 2, sub_question_id: 'א' })).toBe('q2.א')
  })
})
