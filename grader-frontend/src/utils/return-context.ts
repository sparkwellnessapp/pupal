import { LIST_TITLE } from '@/copy/batch'
import { CL_BACK_TO_BATCH, CL_BACK_TO_STUDENT } from '@/copy/classroom'

/**
 * Where the returned page goes BACK to — one pure resolver
 * (PR_student_profile.md §6.5, OD-9, UI-3).
 *
 * The page is reached by NAVIGATION with TYPED context — `?student=` from the
 * profile, `?batch=` from the dashboard and the review module — never a
 * free-form `back=` path, which would let any link send her anywhere. The
 * student wins over the batch because she came from the profile; the batch
 * stays on the URL regardless, since «עריכת הבדיקה» needs it (FA-9).
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export interface ReturnContext {
    href: string
    label: string
}

export function resolveReturnContext(
    params: { student: string | null; batch: string | null },
    studentName: string,
): ReturnContext {
    // A malformed student parameter is IGNORED, not trusted: the only thing
    // that may address a profile is a real id.
    if (params.student && UUID.test(params.student)) {
        return {
            href: `/my-classroom/students/${params.student}`,
            label: CL_BACK_TO_STUDENT(studentName),
        }
    }
    if (params.batch) {
        return { href: `/batches/${params.batch}`, label: CL_BACK_TO_BATCH }
    }
    return { href: '/batches', label: LIST_TITLE }
}

/**
 * The profile row's link (§6.2): the returned page with the student context,
 * plus the batch iff the test has one — a batch-less test has no dashboard
 * and no review route to carry, and an invented id would be worse than none.
 */
export function returnedExamHref(
    gradedTestId: string, studentId: string, batchId: string | null | undefined,
): string {
    const query = new URLSearchParams({ student: studentId })
    if (batchId) query.set('batch', batchId)
    return `/graded-tests/${gradedTestId}/returned?${query.toString()}`
}
