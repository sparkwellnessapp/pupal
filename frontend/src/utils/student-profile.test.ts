import { describe, expect, it } from 'vitest'

import { CL_SIGNED_COUNT } from '@/copy/classroom'
import { examEventTitle } from './exam-event'
import { resolveReturnContext, returnedExamHref } from './return-context'

/**
 * PR_student_profile.md §8.2 — the pure half of Part A. Zero mocks.
 */

const STUDENT = '11111111-1111-4111-8111-111111111111'
const BATCH = '22222222-2222-4222-8222-222222222222'
const TEST = '33333333-3333-4333-8333-333333333333'

describe('resolveReturnContext (§6.5, OD-9)', () => {
    it('a student context returns to the profile, by name', () => {
        expect(resolveReturnContext({ student: STUDENT, batch: null }, 'עידו דוגמה')).toEqual({
            href: `/my-classroom/students/${STUDENT}`,
            label: 'חזרה אל עידו דוגמה',
        })
    })

    it('a batch context returns to the dashboard', () => {
        expect(resolveReturnContext({ student: null, batch: BATCH }, 'דן')).toEqual({
            href: `/batches/${BATCH}`,
            label: 'חזרה ללוח המקבץ',
        })
    })

    it('neither → המבחנים שלי', () => {
        expect(resolveReturnContext({ student: null, batch: null }, 'דן').href).toBe('/batches')
        expect(resolveReturnContext({ student: null, batch: null }, 'דן').label).toBe('המבחנים שלי')
    })

    it('a malformed student parameter is ignored — typed context only, never a path', () => {
        expect(resolveReturnContext({ student: '../admin', batch: BATCH }, 'דן').href)
            .toBe(`/batches/${BATCH}`)
        expect(resolveReturnContext({ student: 'not-a-uuid', batch: null }, 'דן').href)
            .toBe('/batches')
    })

    it('the student wins over the batch — she came from the profile', () => {
        expect(resolveReturnContext({ student: STUDENT, batch: BATCH }, 'דן').href)
            .toBe(`/my-classroom/students/${STUDENT}`)
    })
})

describe('returnedExamHref (§6.2 / FA-9)', () => {
    it('carries the batch iff the test has one', () => {
        expect(returnedExamHref(TEST, STUDENT, BATCH))
            .toBe(`/graded-tests/${TEST}/returned?student=${STUDENT}&batch=${BATCH}`)
        expect(returnedExamHref(TEST, STUDENT, null))
            .toBe(`/graded-tests/${TEST}/returned?student=${STUDENT}`)
        expect(returnedExamHref(TEST, STUDENT, undefined)).not.toContain('batch')
    })
})

describe('CL_SIGNED_COUNT (OD-12 / M-A5)', () => {
    it('0 hidden, 1 singular, n plural', () => {
        expect(CL_SIGNED_COUNT(0)).toBeNull()
        expect(CL_SIGNED_COUNT(1)).toBe('מבחן בדוק אחד')
        expect(CL_SIGNED_COUNT(2)).toBe('2 מבחנים בדוקים')
        expect(CL_SIGNED_COUNT(14)).toBe('14 מבחנים בדוקים')
    })
})

describe('examEventTitle (M-A4 / FA-5) — the ONE composer', () => {
    it('spells a batch exactly as המבחנים שלי does: the stored name, else «מבחן {id8}»', () => {
        expect(examEventTitle({ batch_id: BATCH, name: 'מבחן מחצית', rubric_name: 'Hobby' }))
            .toBe('מבחן מחצית')
        expect(examEventTitle({ batch_id: BATCH, name: null, rubric_name: 'Hobby' }))
            .toBe('מבחן 22222222')
    })

    it('a single-flow test has only its rubric to be named by', () => {
        expect(examEventTitle({ batch_id: null, name: null, rubric_name: 'Hobby' })).toBe('Hobby')
        expect(examEventTitle({ batch_id: null, name: null, rubric_name: null })).toBe('')
    })
})
