import { BATCH_FALLBACK_NAME } from '@/copy/batch'

/**
 * THE exam event's title — one composer (PR_student_profile.md M-A4, FA-5).
 *
 * המבחנים שלי renders a batch as its STORED name, falling back to «מבחן {id8}»
 * when the teacher named nothing. The student profile must spell the same
 * event the same way (OD-6: «exactly as המבחנים שלי renders it»), so both
 * surfaces call this and neither carries its own arithmetic.
 *
 * A single-flow test has no batch at all; the only name it has is its
 * rubric's, and that is what it shows — the one case the list never meets.
 */
export interface ExamEventLike {
    /** The batch id, or null for a single-flow test. */
    batch_id: string | null | undefined
    /** `grading_batches.name` — null when she named nothing. */
    name: string | null | undefined
    rubric_name?: string | null | undefined
}

export function examEventTitle(exam: ExamEventLike): string {
    if (exam.name) return exam.name
    if (exam.batch_id) return BATCH_FALLBACK_NAME(exam.batch_id.slice(0, 8))
    return exam.rubric_name ?? ''
}
