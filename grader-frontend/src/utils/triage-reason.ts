/**
 * §5.3C — WHY this test needs her eyes, in her words.
 *
 * The card used to carry raw triage chips («אי-ודאות לשונית», «חוסר עקביות
 * בזיהוי»). Those are accurate descriptions of what the machine measured and
 * they tell a teacher nothing about what to do, so she opened every one of them
 * to find out — which is the cost the triage exists to save.
 *
 * ── THE RULE THIS FILE OBEYS ──────────────────────────────────────────────
 * Every key here is a reason the backend ACTUALLY emits
 * (`batch_triage.compute_flag_verdict`, cross-pinned in
 * `tests/fixtures/flag_reason_vocabulary.json`). Nothing invents a reason, and
 * nothing claims a detail the wire does not carry — `low_confidence` is
 * page-level but the payload never says WHICH page, so its line does not name
 * one. An unknown reason falls through to the generic sentence rather than
 * leaking an enum onto an RTL screen.
 *
 * It DECIDES NOTHING. Section membership is the server's verdict; this only
 * chooses sentences for a card the server has already placed.
 */

import {
    REASON_EDITED, REASON_GENERIC, REASON_LOW_CONFIDENCE, REASON_LOW_LOGPROB,
    REASON_STUDENT_UNIDENTIFIED, REASON_STUDENT_UNMATCHED, REASON_UNCLEAR_PLACES,
} from '@/copy/batch'
import { unclearCount } from './batch-dashboard'
import { deriveCompleteness } from './transcription-completeness'
import type { AnswerSpaceSelectionGroup } from '@/types/transcription'

export interface TriageItemLike {
    draft: {
        answers: Array<{
            question_number: number
            sub_question_id: string | null
            answer_text: string
        }>
    }
    flag_verdict: { reasons: string[] }
    /** A saved teacher overlay — she has already touched this one. */
    review?: unknown | null
    matched_student_name?: string | null
}


/**
 * The lines for one card, in precedence order: who this is, what is missing,
 * what could not be read. Empty when the server flagged nothing — the caller
 * then renders no reason rail at all rather than an empty one.
 */
export function reasonLinesFor(
    item: TriageItemLike,
    groups: readonly AnswerSpaceSelectionGroup[] | undefined | null,
): string[] {
    const reasons = new Set(item.flag_verdict.reasons)
    const lines: string[] = []

    // 1. Identity first: until she says who this is, nothing else about the
    //    document can be acted on.
    //    `student_unmatched` = no name was read off the page at all.
    //    `student_unassigned` = a name WAS read but no such student exists yet.
    // The reason is the SERVER's verdict; this does not second-guess it against
    // `matched_student_name`. An earlier version did, and it opened a hole: an
    // item flagged `student_unassigned` that also carried a match produced NO
    // identity line, fell through to the catch-all, and told her the
    // TRANSCRIPTION was doubtful — about a document whose only problem was a
    // student who does not exist yet.
    if (reasons.has('student_unmatched')) lines.push(REASON_STUDENT_UNIDENTIFIED)
    else if (reasons.has('student_unassigned')) lines.push(REASON_STUDENT_UNMATCHED)

    // 2. Missing answers speak through the completeness sentence — the same
    //    selection-aware rule the clean cards use, so the two never disagree
    //    about what "missing" means.
    if (reasons.has('missing_answers')) {
        const { sentence } = deriveCompleteness(
            item.draft.answers.map((a) => ({
                question_number: a.question_number,
                sub_question_id: a.sub_question_id,
                text: a.answer_text,
            })),
            groups,
        )
        if (sentence) lines.push(sentence)
    }

    // 3. Handwriting she may have to read herself. The COUNT is what makes this
    //    actionable — «one place» and «eleven places» are different evenings.
    //    `[?]` markers ARE the `unparseable` signal, so only that reason may
    //    quote the count; a zero-count `unparseable` degrades to the generic
    //    line rather than claiming «ב0 מקומות».
    if (reasons.has('unparseable')) {
        const k = unclearCount({ answers: item.draft.answers })
        lines.push(k > 0 ? REASON_UNCLEAR_PLACES(k) : REASON_GENERIC)
    }

    // 3b. A DIFFERENT fact with its own sentence. `low_logprob_span` is the
    //     model's own uncertainty about words it did read — it leaves no `[?]`
    //     markers, so folding it into the count above gave it a number it does
    //     not have and, at zero, the generic line instead of the truth.
    if (reasons.has('low_logprob_span')) lines.push(REASON_LOW_LOGPROB)

    // 4. Page-level VLM doubt. No page number is on the wire, so none is named.
    if (reasons.has('low_confidence')) lines.push(REASON_LOW_CONFIDENCE)

    // 5. Her own edits are why this one is here (Δ1) — it cannot be bulk
    //    accepted, and saying so is what stops her hunting for a machine flag.
    if (item.review != null) lines.push(REASON_EDITED)

    // 6. A reason this build has no sentence for. Gated on the reason being
    //    genuinely UNMAPPED, not merely on the list being empty: falling back
    //    whenever nothing matched is how a mapped-but-silent reason came to be
    //    described as doubtful transcription (see the identity note above).
    if (lines.length === 0) {
        const unmapped = [...reasons].some((r) => !MAPPED.has(r))
        if (unmapped) lines.push(REASON_GENERIC)
    }

    return lines
}

/**
 * Every reason this module has a sentence for. `grounding_retry` and
 * `segmentation_mismatch` are deliberately ABSENT: they are mapped to the
 * generic line by not being here, which is also what makes a brand-new server
 * reason reach it.
 */
const MAPPED: ReadonlySet<string> = new Set([
    'student_unmatched', 'student_unassigned', 'missing_answers',
    'unparseable', 'low_logprob_span', 'low_confidence',
])
