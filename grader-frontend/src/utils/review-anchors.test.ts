/**
 * R1 — reasonAnchors: each rail chip resolves to the FIRST relevant card in
 * the RENDERED (page-first) order, the picker, or a missing-target no-op.
 * Chips are entry-frozen (past tense); anchors read CURRENT text where the
 * rule says so (unparseable / missing) — a fixed card yields a missing target.
 */
import { describe, expect, it } from 'vitest'

import { orderAnswersPageFirst, reasonAnchors } from '@/utils/review-anchors'

const ans = (q: number, sub: string | null, text: string, conf = 0.95, pages: number[] = [1]) => ({
  question_number: q, sub_question_id: sub, answer_text: text,
  confidence: conf, page_numbers: pages,
})

const draftOf = (answers: ReturnType<typeof ans>[], annotations: unknown[] = []) => ({
  answers, annotations,
})

const itemOf = (reasons: string[], answers: ReturnType<typeof ans>[], annotations: unknown[] = []) => ({
  draft: draftOf(answers, annotations),
  flag_verdict: { review_needed: reasons.length > 0, reasons },
})

describe('orderAnswersPageFirst', () => {
  it('sorts by first page, then question, then sub; empty answers sink to the bottom', () => {
    const ordered = orderAnswersPageFirst([
      ans(2, null, 'page two', 0.9, [2]),
      ans(9, null, 'page one late q', 0.9, [1]),
      ans(3, null, '', 0.9, []),
      ans(1, 'א', 'page one', 0.9, [1]),
    ])
    expect(ordered.map((a) => a.question_number)).toEqual([1, 9, 2, 3])
  })
})

describe('reasonAnchors (R1)', () => {
  it('unparseable → first card whose CURRENT text contains [?]', () => {
    const item = itemOf(['unparseable'], [ans(1, null, 'clean'), ans(2, null, 'x = [?]')])
    const anchors = reasonAnchors(item, { q2: 'x = [?]' }, [])
    expect(anchors).toEqual([{ reason: 'unparseable', anchor: { kind: 'card', key: 'q2' } }])
  })

  it('unparseable fixed by the teacher → missing target (chip no-ops with a shake)', () => {
    const item = itemOf(['unparseable'], [ans(1, null, 'was [?] in the draft')])
    const anchors = reasonAnchors(item, { q1: 'now fixed' }, [])
    expect(anchors).toEqual([{ reason: 'unparseable', anchor: { kind: 'missing' } }])
  })

  it('missing_answers → first CURRENTLY-empty unexplained card, in rendered order', () => {
    const item = itemOf(['missing_answers'], [
      ans(1, null, 'full', 0.9, [1]),
      ans(2, null, '', 0.9, []),        // empty → sinks last, but is the only empty
      ans(3, null, 'full', 0.9, [2]),
    ])
    expect(reasonAnchors(item, {}, [])).toEqual([
      { reason: 'missing_answers', anchor: { kind: 'card', key: 'q2' } },
    ])
  })

  it('missing_answers explained by selection → missing target', () => {
    const item = itemOf(['missing_answers'], [
      ans(1, null, 'chosen', 0.9, [1]),
      ans(2, null, 'chosen too', 0.9, [1]),
      ans(3, null, '', 0.9, []),
    ])
    const groups = [{ choose_k: 2, question_numbers: [1, 2, 3] }]
    expect(reasonAnchors(item, {}, groups)).toEqual([
      { reason: 'missing_answers', anchor: { kind: 'missing' } },
    ])
  })

  it('low_confidence → first card under 0.8 in rendered order', () => {
    const item = itemOf(['low_confidence'], [
      ans(1, null, 'ok', 0.95, [1]),
      ans(2, null, 'shaky', 0.5, [1]),
    ])
    expect(reasonAnchors(item, {}, [])).toEqual([
      { reason: 'low_confidence', anchor: { kind: 'card', key: 'q2' } },
    ])
  })

  it('code_lint / segmentation_mismatch → the annotation target_id', () => {
    const item = itemOf(['code_lint', 'segmentation_mismatch'],
      [ans(2, 'א', 'code'), ans(3, null, 'other')],
      [
        { annotation_type: 'code_lint', target_id: 'q2.א' },
        { annotation_type: 'segmentation_mismatch', target_id: 'q3' },
      ])
    expect(reasonAnchors(item, {}, [])).toEqual([
      { reason: 'code_lint', anchor: { kind: 'card', key: 'q2.א' } },
      { reason: 'segmentation_mismatch', anchor: { kind: 'card', key: 'q3' } },
    ])
  })

  it('an annotation pointing at no existing card → missing target', () => {
    const item = itemOf(['code_lint'], [ans(1, null, 'x')],
      [{ annotation_type: 'code_lint', target_id: 'q9' }])
    expect(reasonAnchors(item, {}, [])).toEqual([
      { reason: 'code_lint', anchor: { kind: 'missing' } },
    ])
  })

  it('student_* → the picker; reasons keep verdict order', () => {
    const item = itemOf(['student_unassigned', 'unparseable'], [ans(1, null, '[?]')])
    expect(reasonAnchors(item, { q1: '[?]' }, [])).toEqual([
      { reason: 'student_unassigned', anchor: { kind: 'student' } },
      { reason: 'unparseable', anchor: { kind: 'card', key: 'q1' } },
    ])
  })
})
