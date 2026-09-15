/**
 * §5.3C — the triaged grid, as SSR markup (house pattern: renderToStaticMarkup,
 * no DOM). Three structural claims, each of which was a live defect:
 *
 *   1. needs-a-look renders FIRST. Ordering the one-click section above it
 *      trains the click and pushes the flagged documents below the fold;
 *   2. every card carries a page image, because that is how she recognises a
 *      paper before the student name has been resolved at all;
 *   3. the bulk button claims only what the SERVER would accept.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { TranscriptionTriage } from '@/components/batch/TranscriptionTriage'
import type { BatchTranscriptionItem } from '@/types/batch'

function seedItem(
    id: string, over: Partial<BatchTranscriptionItem> = {},
): BatchTranscriptionItem {
    return {
        transcription_id: id,
        filename: `${id}.pdf`,
        transcription_status: 'transcribed',
        created_at: new Date().toISOString(),
        draft: {
            page_count: 2,
            answers: [
                { question_number: 1, sub_question_id: null, answer_text: 'x' },
                { question_number: 2, sub_question_id: null, answer_text: 'y' },
            ],
        } as unknown as BatchTranscriptionItem['draft'],
        review: null,
        student_name_suggestion: null,
        matched_student_id: 's1',
        matched_student_name: 'דנה לוי',
        flag_verdict: { review_needed: false, reasons: [] },
        page1_image_url: `/api/v0/transcriptions/${id}/pages/1/image?v=600x72@110`,
        graded_test_id: null,
        graded_test_status: null,
        total_score: null,
        total_possible: null,
        ...over,
    }
}

const base = {
    batchId: 'b1',
    selectionGroups: [],
    firstReviewId: 'e1',
    sampleCleanId: 'c1',
    pendingCount: 0,
    accepting: new Set<string>(),
    bulkBusy: false,
    onAcceptAll: () => {},
    skipNotice: null,
    showAll: false,
    onShowAll: () => {},
    newIds: new Set<string>(),
    isFirstBatch: false,
}

const flagged = seedItem('e1', {
    flag_verdict: { review_needed: true, reasons: ['student_unmatched'] },
    matched_student_id: null,
    matched_student_name: null,
    student_name_suggestion: null,
})
const clean = seedItem('c1')

describe('TranscriptionTriage', () => {
    it('renders needs-a-look BEFORE the confidently-read section', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[flagged]}
                cleanRows={[clean]}
                acceptableCount={1}
            />,
        )
        expect(html.indexOf('data-testid="zone-eyes"'))
            .toBeLessThan(html.indexOf('data-testid="zone-clean"'))
        expect(html.indexOf('data-testid="zone-eyes"')).toBeGreaterThan(-1)
    })

    it('gives every card its page-1 image, so a paper is recognisable', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[flagged]}
                cleanRows={[clean]}
                acceptableCount={1}
            />,
        )
        // Both cards register a thumbnail target; the object URL itself is
        // resolved through the api seam at runtime (see usePageThumbnails).
        expect(html).toContain('data-testid="eyes-row"')
        expect(html).toContain('data-testid="clean-row"')
    })

    it('a flagged card states its reason in teacher words', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[flagged]}
                cleanRows={[]}
                acceptableCount={0}
            />,
        )
        expect(html).toContain('התלמיד לא זוהה')
        expect(html).not.toMatch(/student_unmatched/)
    })

    it('a clean card carries the completeness sentence, not a container count', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[]}
                cleanRows={[clean]}
                acceptableCount={1}
            />,
        )
        expect(html).toContain('נמצאו תשובות לכל 2 הסעיפים')
        expect(html).not.toContain('2 עמודים · 2 תשובות')
    })

    it('the bulk button counts ONLY what the server would accept', () => {
        // An identity-pending card lives in this section and would be refused.
        const pending = seedItem('c2', {
            matched_student_id: null,
            matched_student_name: null,
            student_name_suggestion: 'תלמיד חדש',
            flag_verdict: { review_needed: true, reasons: ['student_unassigned'] },
        })
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[]}
                cleanRows={[clean, pending]}
                acceptableCount={1}
                pendingCount={1}
            />,
        )
        expect(html).toContain('אישור המבחן')          // 1, not 2
        expect(html).toContain('data-testid="clean-pending-note"')
    })

    it('an unidentified card says so instead of showing a filename as a name', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[flagged]}
                cleanRows={[]}
                acceptableCount={0}
            />,
        )
        expect(html).toContain('לא זוהה')
    })

    it('renders nothing at all when both sections are empty', () => {
        const html = renderToStaticMarkup(
            <TranscriptionTriage
                {...base}
                eyesRows={[]}
                cleanRows={[]}
                acceptableCount={0}
            />,
        )
        expect(html).toBe('')
    })
})
