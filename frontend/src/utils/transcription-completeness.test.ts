/**
 * `deriveCompleteness` — the §11 fixture list, verbatim, with ZERO mocks:
 * selection-free full and with a missing leaf; one group `choose_k=4` of 6 at
 * a=3, a=4 and a=5; a chosen question with a missing sub-key; a mandatory
 * question outside any group with a missing leaf; two groups with labels.
 *
 * The claim under test throughout is the one the sentence exists to make:
 * an UNCHOSEN question is not a gap, and a gap inside a CHOSEN one is.
 */
import { describe, expect, it } from 'vitest'

import { deriveCompleteness, type CompletenessAnswer } from './transcription-completeness'
import type { AnswerSpaceSelectionGroup } from '@/types/transcription'

/** `a(3, 'ב', 'text')` → question 3, part ב, answered. Empty text = unanswered. */
const a = (q: number, sub: string | null, text: string): CompletenessAnswer =>
    ({ question_number: q, sub_question_id: sub, text })

const GROUP_4_OF_6: AnswerSpaceSelectionGroup = {
    choose_k: 4,
    question_numbers: [1, 2, 3, 4, 5, 6],
    label: 'ענו על 4 מתוך 6 שאלות',
}

describe('no selection groups — every leaf is owed', () => {
    it('all answered', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, 'א', 'y'), a(2, 'ב', 'z'),
        ], [])
        expect(r.sentence).toBe('נמצאו תשובות לכל 3 השאלות')
        expect(r.needsLook).toBe(false)
        expect(r.reasons).toEqual([])
    })

    it('one missing leaf is NAMED, with its full key', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, 'א', 'y'), a(2, 'ג', ''),
        ], [])
        expect(r.sentence).toBe('נמצאו 2 מתוך 3 סעיפים — 2.ג לא נמצאו')
        expect(r.needsLook).toBe(true)
        expect(r.reasons).toEqual(['missing_mandatory'])
    })

    it('a WHOLE-QUESTION leaf is named «שאלה N», not a bare numeral', () => {
        // «נמצאו 1 מתוך 2 סעיפים — 1 לא נמצאו» reads as arithmetic
        // rather than as a place to look. Caught in the rendered screenshot.
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, ''),
        ], [])
        expect(r.sentence).toBe('נמצאו 1 מתוך 2 סעיפים — שאלה 2 לא נמצאו')
    })

    it('an absent `groups` is the same as an empty one', () => {
        expect(deriveCompleteness([a(1, null, 'x')], undefined).sentence)
            .toBe('נמצאו תשובות לכל 1 השאלות')
        expect(deriveCompleteness([a(1, null, 'x')], null).sentence)
            .toBe('נמצאו תשובות לכל 1 השאלות')
    })

    it('a transcription with no answer entries says nothing at all', () => {
        expect(deriveCompleteness([], [])).toEqual(
            { sentence: '', needsLook: false, reasons: [] })
    })
})

describe('one group, choose 4 of 6', () => {
    const sixQuestions = (answeredQs: number[]): CompletenessAnswer[] =>
        [1, 2, 3, 4, 5, 6].map((q) => a(q, null, answeredQs.includes(q) ? 'x' : ''))

    it('a = 4 — exactly as required, and nothing is missing', () => {
        const r = deriveCompleteness(sixQuestions([1, 2, 3, 4]), [GROUP_4_OF_6])
        expect(r.sentence)
            .toBe('נמצאו תשובות ל-4 מתוך 6 שאלות, כנדרש — אין תשובות חסרות')
        expect(r.needsLook).toBe(false)
    })

    it('a = 4 — the two unanswered questions are NEVER named', () => {
        const r = deriveCompleteness(sixQuestions([1, 2, 3, 4]), [GROUP_4_OF_6])
        expect(r.sentence).not.toContain('5')
        expect(r.sentence).not.toContain('לא נמצאו')
    })

    it('a = 3 — a shortfall, reported as a count', () => {
        const r = deriveCompleteness(sixQuestions([1, 2, 3]), [GROUP_4_OF_6])
        expect(r.sentence).toBe('נמצאו תשובות ל-3 שאלות מתוך 4 הנדרשות')
        expect(r.needsLook).toBe(true)
        expect(r.reasons).toEqual(['group_short'])
    })

    it('a = 5 — surfaced, never judged (OD-6), and it does not need her eyes', () => {
        const r = deriveCompleteness(sixQuestions([1, 2, 3, 4, 5]), [GROUP_4_OF_6])
        expect(r.sentence).toBe('נמצאו תשובות ל-5 שאלות — נדרשות 4')
        expect(r.reasons).toEqual(['group_excess'])
        expect(r.needsLook).toBe(false)
    })
})

describe('a gap inside a CHOSEN question is a real missing answer', () => {
    it('names the letters, appended to the group clause', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, 'x'),
            a(3, 'א', 'x'), a(3, 'ב', ''),
            a(4, null, 'x'),
            a(5, null, ''), a(6, null, ''),
        ], [GROUP_4_OF_6])
        expect(r.sentence).toBe(
            'נמצאו תשובות ל-4 מתוך 6 שאלות, כנדרש — אין תשובות חסרות; בשאלה 3 חסר ב')
        expect(r.needsLook).toBe(true)
        expect(r.reasons).toContain('partial_question')
    })

    it('an UNCHOSEN question with empty parts contributes nothing', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, 'x'), a(3, null, 'x'), a(4, null, 'x'),
            a(5, 'א', ''), a(5, 'ב', ''),
            a(6, null, ''),
        ], [GROUP_4_OF_6])
        expect(r.sentence).toBe('נמצאו תשובות ל-4 מתוך 6 שאלות, כנדרש — אין תשובות חסרות')
        expect(r.needsLook).toBe(false)
    })
})

describe('a mandatory question outside every group', () => {
    it('its missing leaf is named, and the group clause still follows', () => {
        const group: AnswerSpaceSelectionGroup = {
            choose_k: 2, question_numbers: [2, 3, 4], label: null,
        }
        const r = deriveCompleteness([
            a(1, 'א', 'x'), a(1, 'ב', ''),
            a(2, null, 'x'), a(3, null, 'x'), a(4, null, ''),
        ], [group])
        expect(r.sentence).toBe(
            '1.ב לא נמצאו · נמצאו תשובות ל-2 מתוך 3 שאלות, כנדרש — אין תשובות חסרות')
        expect(r.needsLook).toBe(true)
        expect(r.reasons).toContain('missing_mandatory')
    })
})

describe('two groups', () => {
    const partA: AnswerSpaceSelectionGroup = {
        choose_k: 2, question_numbers: [1, 2, 3], label: 'ענו על 2 מתוך 3 בחלק א',
    }
    const partB: AnswerSpaceSelectionGroup = {
        choose_k: 1, question_numbers: [4, 5], label: 'ענו על 1 מתוך 2 בחלק ב',
    }

    it('each clause is prefixed with HER wording, verbatim, in quotes', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, 'x'), a(3, null, ''),
            a(4, null, 'x'), a(5, null, ''),
        ], [partA, partB])
        expect(r.sentence).toBe(
            '"ענו על 2 מתוך 3 בחלק א": נמצאו תשובות ל-2 מתוך 3 שאלות, כנדרש — אין תשובות חסרות'
            + ' · "ענו על 1 מתוך 2 בחלק ב": נמצאו תשובות ל-1 מתוך 2 שאלות, כנדרש — אין תשובות חסרות')
        expect(r.needsLook).toBe(false)
    })

    it('a group with no label gets NO prefix — never an invented one', () => {
        const unlabelled: AnswerSpaceSelectionGroup = {
            choose_k: 1, question_numbers: [4, 5],
        }
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, 'x'), a(3, null, ''),
            a(4, null, 'x'), a(5, null, ''),
        ], [partA, unlabelled])
        expect(r.sentence).toContain('"ענו על 2 מתוך 3 בחלק א": ')
        expect(r.sentence.endsWith(
            'נמצאו תשובות ל-1 מתוך 2 שאלות, כנדרש — אין תשובות חסרות')).toBe(true)
        expect(r.sentence).not.toContain('קבוצה')
    })

    it('a SINGLE labelled group carries no prefix — there is nothing to tell apart', () => {
        const r = deriveCompleteness(
            [1, 2, 3, 4, 5, 6].map((q) => a(q, null, q <= 4 ? 'x' : '')),
            [GROUP_4_OF_6])
        expect(r.sentence).not.toContain('"')
    })

    it('one short group makes the whole card need a look', () => {
        const r = deriveCompleteness([
            a(1, null, 'x'), a(2, null, ''), a(3, null, ''),
            a(4, null, 'x'), a(5, null, ''),
        ], [partA, partB])
        expect(r.needsLook).toBe(true)
        expect(r.reasons).toContain('group_short')
    })
})

/**
 * The REFUSALS. A selection structure this module cannot read produces no
 * claim about missing answers at all — because the wrong claim on a
 * «choose k of N» exam reads as the student having skipped work he was never
 * set, and `needsLook` would then send her to a document that is fine.
 */
describe('a structure it cannot read is refused, never guessed', () => {
    it('a question in TWO groups (§5.3D: flag, do not approximate)', () => {
        const r = deriveCompleteness(
            [1, 2, 3, 4].map((q) => a(q, null, 'x')),
            [
                { choose_k: 1, question_numbers: [1, 2] },
                { choose_k: 1, question_numbers: [2, 3] },   // 2 is in both
            ],
        )
        expect(r.reasons).toEqual(['not_computable'])
        expect(r.needsLook).toBe(false)
        expect(r.sentence).toBe('לא ניתן לבדוק כאן תשובות חסרות — מבנה הבחירה במחוון לא ברור')
    })

    it('choose_k above the member count — what dropped dangling ids produce', () => {
        // `answer_space_groups` DROPS member ids missing from the contract and
        // leaves `choose_k` alone, so a «choose 4 of 6» whose last two ids
        // dangle arrives as choose_k 4 over 4 members… or fewer. Computed
        // anyway, that is a permanent shortfall on a completed exam.
        const r = deriveCompleteness(
            [1, 2, 3].map((q) => a(q, null, 'x')),
            [{ choose_k: 4, question_numbers: [1, 2, 3] }],
        )
        expect(r.reasons).toEqual(['not_computable'])
        expect(r.needsLook).toBe(false)
    })

    it('a nonsensical choose_k of zero', () => {
        const r = deriveCompleteness(
            [a(1, null, 'x')], [{ choose_k: 0, question_numbers: [1] }])
        expect(r.reasons).toEqual(['not_computable'])
    })

    it('a well-formed rubric is NOT refused', () => {
        const r = deriveCompleteness(
            [1, 2, 3].map((q) => a(q, null, q <= 2 ? 'x' : '')),
            [{ choose_k: 2, question_numbers: [1, 2, 3] }],
        )
        expect(r.reasons).not.toContain('not_computable')
    })
})

describe('no gap is reported twice, and none is dropped', () => {
    it('reasons are a SET — a rubric with two short groups says it once', () => {
        const r = deriveCompleteness(
            [1, 2, 3, 4].map((q) => a(q, null, '')),
            [
                { choose_k: 1, question_numbers: [1, 2] },
                { choose_k: 1, question_numbers: [3, 4] },
            ],
        )
        expect(r.reasons.filter((x) => x === 'group_short')).toHaveLength(1)
    })

    it('a missing leaf with NO sub-id inside a chosen question is still named', () => {
        // «בשאלה 3 חסר …» has no letter to put in it for such a leaf, so the
        // first version filtered it out and lost a real gap silently.
        const r = deriveCompleteness([
            a(1, 'א', 'x'), a(1, null, ''),
            a(2, null, ''),
        ], [{ choose_k: 1, question_numbers: [1, 2] }])
        expect(r.sentence).toContain('שאלה 1 לא נמצאו')
        expect(r.reasons).toContain('missing_mandatory')
    })
})
