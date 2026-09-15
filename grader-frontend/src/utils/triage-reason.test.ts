/**
 * §5.3C — the reason line, in teacher words.
 *
 * The claim under test is narrow and load-bearing: every sentence this module
 * can produce corresponds to a reason the BACKEND actually emits, and no
 * sentence claims a detail the wire does not carry.
 */
import { describe, expect, it } from 'vitest'

import { reasonLinesFor, type TriageItemLike } from './triage-reason'
import { FLAG_REASON_LABELS } from '@/types/batch'

const item = (reasons: string[], over: Partial<TriageItemLike> = {}): TriageItemLike => ({
    draft: {
        answers: [
            { question_number: 1, sub_question_id: null, answer_text: 'x' },
            { question_number: 2, sub_question_id: null, answer_text: 'y' },
        ],
    },
    flag_verdict: { reasons },
    review: null,
    matched_student_name: 'דנה לוי',
    ...over,
})

describe('identity comes first — nothing else can be acted on until she decides', () => {
    it('no name was read off the page at all', () => {
        expect(reasonLinesFor(item(['student_unmatched']), [])[0]).toBe('התלמיד לא זוהה')
    })

    it('a name WAS read but no such student exists yet', () => {
        const lines = reasonLinesFor(
            item(['student_unassigned'], { matched_student_name: null }), [])
        expect(lines[0]).toBe('השם לא נמצא ברשימת הכיתה')
    })

    it("the SERVER's reason wins over a match on the row", () => {
        // This used to be guarded on `matched_student_name`, which is the
        // client second-guessing the verdict. The two together are
        // contradictory data; the honest reading is the reason, and the guard
        // meant such a row got NO line and fell through to a catch-all that
        // told her the transcription was doubtful.
        expect(reasonLinesFor(item(['student_unassigned']), []))
            .toContain('השם לא נמצא ברשימת הכיתה')
    })
})

describe('unclear handwriting is COUNTED — the count is what makes it actionable', () => {
    it('counts the [?] markers', () => {
        const withMarkers = item(['unparseable'], {
            draft: {
                answers: [
                    { question_number: 1, sub_question_id: null, answer_text: 'a [?] b [?] c' },
                    { question_number: 2, sub_question_id: null, answer_text: 'd [?] e' },
                ],
            },
        })
        expect(reasonLinesFor(withMarkers, [])).toContain('כתב יד לא ברור ב3 מקומות')
    })

    it('one place reads «מקום אחד», never «1 מקומות»', () => {
        const one = item(['unparseable'], {
            draft: { answers: [{ question_number: 1, sub_question_id: null, answer_text: 'a [?] b' }] },
        })
        expect(reasonLinesFor(one, [])).toContain('כתב יד לא ברור במקום אחד')
    })

    it('low-logprob is its OWN fact, never a «0 מקומות» count', () => {
        // It leaves no `[?]` markers, so it was previously folded into the
        // count above and degraded to the generic line at zero — losing the
        // one thing it actually says.
        const lines = reasonLinesFor(item(['low_logprob_span']), [])
        expect(lines).toContain('ויוי לא בטוחה בקריאה של חלק מהמילים')
        expect(lines.join(' ')).not.toContain('מקומות')
    })

    it('a flag with zero markers degrades to the generic line, never «ב0 מקומות»', () => {
        expect(reasonLinesFor(item(['unparseable']), []))
            .toContain('ויוי לא בטוחה בחלק מהתמלול')
    })
})

describe('page-level doubt names no page, because the wire carries none', () => {
    it('says «חלק מהעמודים» rather than inventing a number', () => {
        const lines = reasonLinesFor(item(['low_confidence']), [])
        expect(lines).toContain('חלק מהעמודים לא נקראו בביטחון')
        expect(lines.join(' ')).not.toMatch(/עמוד \d/)
    })
})

describe('missing answers speak through the completeness sentence', () => {
    it('uses the SAME selection-aware rule the clean cards use', () => {
        const gapped = item(['missing_answers'], {
            draft: {
                answers: [
                    { question_number: 1, sub_question_id: 'א', answer_text: 'x' },
                    { question_number: 1, sub_question_id: 'ב', answer_text: '' },
                ],
            },
        })
        expect(reasonLinesFor(gapped, [])).toContain('נמצאו 1 מתוך 2 סעיפים — 1.ב לא נמצאו')
    })

    it('a satisfied selection group produces no gap sentence at all', () => {
        const chosen = item(['missing_answers'], {
            draft: {
                answers: [1, 2, 3, 4, 5, 6].map((q) => ({
                    question_number: q, sub_question_id: null, answer_text: q <= 4 ? 'x' : '',
                })),
            },
        })
        const lines = reasonLinesFor(chosen, [{ choose_k: 4, question_numbers: [1, 2, 3, 4, 5, 6] }])
        expect(lines.join(' ')).toContain('כנדרש')
        expect(lines.join(' ')).not.toContain('לא נמצאו')
    })
})

describe('her own edits are a reason — and the one she can act on immediately', () => {
    it('says so, so she is not hunting for a machine flag', () => {
        expect(reasonLinesFor(item([], { review: { answers: [] } }), []))
            .toContain('ערכת את התמלול — אישור פרטני')
    })
})

describe('the catch-all', () => {
    it('covers the reasons with no more precise sentence', () => {
        for (const reason of ['grounding_retry', 'segmentation_mismatch']) {
            expect(reasonLinesFor(item([reason]), []))
                .toEqual(['ויוי לא בטוחה בחלק מהתמלול'])
        }
    })

    it('a reason this build has never heard of still gets Hebrew, never an enum', () => {
        const lines = reasonLinesFor(item(['some_future_reason']), [])
        expect(lines).toEqual(['ויוי לא בטוחה בחלק מהתמלול'])
        expect(lines.join(' ')).not.toMatch(/[A-Za-z_]/)
    })

    it('an unflagged item produces NO rail rather than an empty one', () => {
        expect(reasonLinesFor(item([]), [])).toEqual([])
    })
})

describe('every backend reason has a sentence (the vocabulary is covered)', () => {
    it('produces a non-empty Hebrew line for each cross-pinned reason', () => {
        for (const reason of Object.keys(FLAG_REASON_LABELS)) {
            const lines = reasonLinesFor(
                item([reason], { matched_student_name: null }), [])
            expect(lines.length, `${reason} produced no line`).toBeGreaterThan(0)
            expect(lines.join(' ')).not.toMatch(/[A-Za-z_]/)
        }
    })
})
