import { describe, expect, it, vi } from 'vitest'

import type { BatchTranscriptionItem } from '@/types/batch'
import { needsUnloadGuard, ReviewItemController, type SaveFn } from './reviewItemController'

function makeItem(overrides: Partial<BatchTranscriptionItem> = {}): BatchTranscriptionItem {
  return {
    transcription_id: 'tx-1',
    filename: 'a.pdf',
    transcription_status: 'transcribed',
    created_at: '2026-08-04T10:00:00Z',
    draft: {
      schema_version: '1.0',
      student_name_suggestion: 'רז כהן',
      page_count: 1,
      answers: [
        { question_number: 1, sub_question_id: null, answer_text: 'draft one', confidence: 0.9, page_numbers: [1] },
        { question_number: 2, sub_question_id: 'א', answer_text: 'draft two', confidence: 0.8, page_numbers: [1] },
      ],
      annotations: [],
      model_version: null,
      transcription_duration_ms: null,
    },
    review: null,
    student_name_suggestion: 'רז כהן',
    matched_student_id: 'student-match',
    matched_student_name: 'רז כהן',
    flag_verdict: { review_needed: false, reasons: [] },
    graded_test_id: null,
    graded_test_status: null,
    total_score: null,
    total_possible: null,
    ...overrides,
  }
}

const okReview = { schema_version: '1.0', answers: [], student_id: null, updated_at: null }

describe('view-without-edit-creates-no-overlay (Δ14)', () => {
  it('flushIfDirty on an untouched item issues NO request and allows navigation', async () => {
    const save = vi.fn()
    const ctrl = new ReviewItemController(makeItem(), save as unknown as SaveFn)
    expect(await ctrl.flushIfDirty()).toBe(true)
    expect(save).not.toHaveBeenCalled()
  })

  it('the matched-student pre-seed is hydration, not dirt', async () => {
    const save = vi.fn()
    const ctrl = new ReviewItemController(makeItem(), save as unknown as SaveFn)
    expect(ctrl.getSnapshot().studentId).toBe('student-match')  // pre-seeded
    expect(ctrl.getSnapshot().dirty).toBe(false)                // …but not dirty
    await ctrl.flushIfDirty()
    expect(save).not.toHaveBeenCalled()
  })
})

describe('dirty flush — full snapshot in draft order', () => {
  it('a keystroke makes the item dirty; flush saves the complete snapshot once', async () => {
    const save = vi.fn(async () => okReview)
    const ctrl = new ReviewItemController(makeItem(), save)

    ctrl.onAnswerChange('q1', 'edited one')
    expect(ctrl.getSnapshot().dirty).toBe(true)

    expect(await ctrl.flushIfDirty()).toBe(true)
    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith('tx-1', {
      answers: [
        { question_number: 1, sub_question_id: null, answer_text: 'edited one' },
        { question_number: 2, sub_question_id: 'א', answer_text: 'draft two' },  // untouched carried too
      ],
      student_id: 'student-match',
    })
    expect(ctrl.getSnapshot().saved).toBe(true)

    // Clean after success: a second flush is a no-op.
    await ctrl.flushIfDirty()
    expect(save).toHaveBeenCalledTimes(1)
  })

  it('an explicit student pick is dirt; the flush carries it', async () => {
    const save = vi.fn(async () => okReview)
    const ctrl = new ReviewItemController(makeItem(), save)
    ctrl.onStudentPick('student-chosen')
    await ctrl.flushIfDirty()
    expect(save).toHaveBeenCalledWith('tx-1', expect.objectContaining({ student_id: 'student-chosen' }))
  })

  it('a failed save blocks navigation, surfaces the error, and loses nothing', async () => {
    const save = vi.fn(async () => { throw new Error('offline') })
    const ctrl = new ReviewItemController(makeItem(), save as unknown as SaveFn)
    ctrl.onAnswerChange('q1', 'x')

    expect(await ctrl.flushIfDirty()).toBe(false)
    expect(ctrl.getSnapshot().saveError).toBe('offline')
    expect(ctrl.getSnapshot().dirty).toBe(true)
    expect(ctrl.getSnapshot().editedAnswers['q1']).toBe('x')
  })
})

describe('overlay-patch-suppressed-after-accept (Δ4)', () => {
  it('after markAccepted, flushIfDirty never issues a PATCH — even with pending edits', async () => {
    const save = vi.fn()
    const ctrl = new ReviewItemController(makeItem(), save as unknown as SaveFn)

    ctrl.onAnswerChange('q1', 'edited')
    ctrl.markAccepted()

    expect(await ctrl.flushIfDirty()).toBe(true)  // navigation proceeds
    expect(save).not.toHaveBeenCalled()           // the 409 path is never exercised
  })

  it('an already-approved item starts suppressed', async () => {
    const save = vi.fn()
    const ctrl = new ReviewItemController(
      makeItem({ transcription_status: 'approved' }), save as unknown as SaveFn)
    expect(ctrl.getSnapshot().accepted).toBe(true)
    await ctrl.flushIfDirty()
    expect(save).not.toHaveBeenCalled()
  })
})

describe('needsUnloadGuard — rider-1 amended OD-8 ruling', () => {
  const base = { dirty: false, saving: false, saveError: null as string | null, accepted: false }

  it('guards when there is something to lose: dirty, saving, or a failed save', () => {
    expect(needsUnloadGuard({ ...base, dirty: true })).toBe(true)
    expect(needsUnloadGuard({ ...base, saving: true })).toBe(true)
    expect(needsUnloadGuard({ ...base, saveError: 'offline' })).toBe(true)
  })

  it('clean idle item: no guard', () => {
    expect(needsUnloadGuard(base)).toBe(false)
  })

  it('accepted item never guards — PATCHes are suppressed, nothing can be lost', () => {
    expect(needsUnloadGuard({ ...base, dirty: true, accepted: true })).toBe(false)
  })
})

describe('hydration (Δ11 guard + overlay-over-draft)', () => {
  it('overlay text and student win over draft and auto-match', () => {
    const ctrl = new ReviewItemController(makeItem({
      review: {
        schema_version: '1.0',
        answers: [
          { question_number: 1, sub_question_id: null, answer_text: 'overlay one' },
          { question_number: 2, sub_question_id: 'א', answer_text: 'overlay two' },
        ],
        student_id: 'student-overlay',
        updated_at: '2026-08-04T11:00:00Z',
      },
    }), vi.fn() as unknown as SaveFn)
    expect(ctrl.getSnapshot().editedAnswers).toEqual({ q1: 'overlay one', 'q2.א': 'overlay two' })
    expect(ctrl.getSnapshot().studentId).toBe('student-overlay')
    expect(ctrl.getSnapshot().dirty).toBe(false)  // hydration is not dirt
  })

  it('a payload refresh of the SAME item never clobbers in-progress edits (Δ11)', () => {
    const ctrl = new ReviewItemController(makeItem(), vi.fn() as unknown as SaveFn)
    ctrl.onAnswerChange('q1', 'typing…')

    // Same transcription_id, new object with a server-side overlay — no re-hydration.
    ctrl.maybeRehydrate(makeItem({
      review: {
        schema_version: '1.0',
        answers: [
          { question_number: 1, sub_question_id: null, answer_text: 'server version' },
          { question_number: 2, sub_question_id: 'א', answer_text: 'server two' },
        ],
        student_id: null, updated_at: null,
      },
    }))
    expect(ctrl.getSnapshot().editedAnswers['q1']).toBe('typing…')
    expect(ctrl.getSnapshot().dirty).toBe(true)
  })

  it('an item-identity change re-hydrates cleanly', () => {
    const ctrl = new ReviewItemController(makeItem(), vi.fn() as unknown as SaveFn)
    ctrl.onAnswerChange('q1', 'typing…')

    ctrl.maybeRehydrate(makeItem({ transcription_id: 'tx-2' }))
    expect(ctrl.getSnapshot().editedAnswers['q1']).toBe('draft one')
    expect(ctrl.getSnapshot().dirty).toBe(false)
  })
})
