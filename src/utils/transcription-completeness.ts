/**
 * §5.3D — «did the student answer everything he owed?», in one sentence.
 *
 * It replaces «6 עמודים · 6 תשובות», which counted CONTAINERS. The P2
 * segmentation emits an answer entry for every rubric target, empty when
 * unanswered, so that pair was 6·6 on a blank page and 6·6 on a full one: it
 * could not distinguish the two states it looked like it was reporting.
 *
 * ── SELECTION AWARENESS IS THE WHOLE DIFFICULTY ───────────────────────────
 * On a «ענו על 4 מתוך 6» exam the two questions the student did not answer are
 * not gaps — the exam TOLD him to skip two — and a card that named them would
 * send her hunting for work nobody owed. Two rules follow, and they are the
 * reason this is a function rather than a template:
 *
 *   * UNDER A GROUP, COUNTS ONLY. Never «שאלה 3 חסרה»: the student chose, and
 *     naming a choice as an absence is an accusation.
 *   * INSIDE A CHOSEN QUESTION, a gap is REAL. He picked question 3 and left
 *     3.ב blank — that is a missing answer and it is named.
 *
 * ── THIS FUNCTION DOES NOT TRIAGE ─────────────────────────────────────────
 * `needsLook` picks which SENTENCE a card shows; it never decides which SECTION
 * a card lives in. Section membership is the server's verdict
 * (`compute_flag_verdict` → `assignZones`), computed from the same
 * `expected_empty_keys` rule this module mirrors. A second partition here would
 * be exactly the two-derivations-of-one-fact failure the stage model exists to
 * end — and it would fail in the dangerous direction, since a client that
 * over-counts empties sends her to documents that are fine.
 *
 * Pure. Zero I/O. Computed against the CURRENT text, so a teacher typing into a
 * container makes its member attempted and the sentence updates live — the
 * `selection-expectation.ts` pattern.
 */

import {
    COMPLETE_ALL, COMPLETE_APPEND_SEP, COMPLETE_CLAUSE_SEP, COMPLETE_GROUP_EXCESS,
    COMPLETE_GROUP_LABEL, COMPLETE_GROUP_OK, COMPLETE_GROUP_SHORT, COMPLETE_MISSING,
    COMPLETE_MISSING_PREFIX, COMPLETE_NOT_COMPUTABLE, COMPLETE_PARTIAL_QUESTION,
} from '@/copy/batch'
import type { AnswerSpaceSelectionGroup } from '@/types/transcription'

export interface CompletenessAnswer {
    question_number: number
    sub_question_id: string | null
    /** CURRENT text — draft text overlaid with the teacher's live edits. */
    text: string
}

export type CompletenessReason =
    /** A leaf nobody could skip is empty. */
    | 'missing_mandatory'
    /** A group has fewer attempted members than `choose_k`. */
    | 'group_short'
    /** A group has MORE attempted members than `choose_k` (OD-6: surfaced, not judged). */
    | 'group_excess'
    /** A question the student DID choose has an empty part. */
    | 'partial_question'
    /**
     * The selection structure cannot be read, so NOTHING about missing answers
     * is claimed. Two causes, both real:
     *
     *   * a question in TWO groups — §5.3D ruled this undefined: flag, never
     *     guess. Computing it anyway counts one answer toward two requirements;
     *   * a group whose `choose_k` exceeds its member count, which
     *     `answer_space_groups` can produce by design (it DROPS dangling member
     *     ids and leaves `choose_k` alone). Unhandled, that renders a permanent
     *     «נמצאו 4 שאלות מתוך 5 הנדרשות» on an exam the student completed.
     *
     * `needsLook` is FALSE for it: the gap is ours, and sending her to a
     * document that is probably fine is the over-count failure §3.5a names.
     */
    | 'not_computable'

export interface Completeness {
    /** One sentence, already composed. Empty string when there is nothing to
     *  say (a transcription with no answer entries at all). */
    sentence: string
    /** True when any clause is a shortfall. Chooses the SENTENCE, never the
     *  section — see the module doc. */
    needsLook: boolean
    reasons: CompletenessReason[]
}

/**
 * `2.ג` for a sub-question leaf, `שאלה 2` for a whole-question one.
 *
 * The bare number is what the answer key carries, and it is unreadable in a
 * sentence: «נמצאו 1 מתוך 2 סעיפים — 1 לא נמצאו» reads as arithmetic, not as a
 * place to look. A sub-question key needs no prefix — `2.ג` is already a
 * location — and prefixing it would name it a question, which it is not.
 */
function leafKey(a: CompletenessAnswer): string {
    return a.sub_question_id
        ? `${a.question_number}.${a.sub_question_id}`
        : `שאלה ${a.question_number}`
}

const answered = (a: CompletenessAnswer) => a.text.trim() !== ''

export function deriveCompleteness(
    answers: readonly CompletenessAnswer[],
    groups: readonly AnswerSpaceSelectionGroup[] | undefined | null,
): Completeness {
    if (answers.length === 0) {
        return { sentence: '', needsLook: false, reasons: [] }
    }

    // Leaves per question, in the order the draft carries them — the order she
    // reads on the page.
    const byQuestion = new Map<number, CompletenessAnswer[]>()
    for (const a of answers) {
        const list = byQuestion.get(a.question_number) ?? []
        list.push(a)
        byQuestion.set(a.question_number, list)
    }
    const questionAnswered = (q: number) => (byQuestion.get(q) ?? []).some(answered)

    const activeGroups = (groups ?? []).filter((g) => g.question_numbers.length > 0)

    // ── the selection-free case: every leaf is owed ──
    if (activeGroups.length === 0) {
        const missing = answers.filter((a) => !answered(a))
        if (missing.length === 0) {
            return { sentence: COMPLETE_ALL(answers.length), needsLook: false, reasons: [] }
        }
        return {
            sentence: COMPLETE_MISSING(
                answers.length - missing.length,
                answers.length,
                missing.map(leafKey).join(', '),
            ),
            needsLook: true,
            reasons: ['missing_mandatory'],
        }
    }

    // ── selection rubric ──
    //
    // BEFORE anything is computed: is the structure readable at all? Both
    // checks are refusals, not repairs (see `not_computable`).
    const seen = new Set<number>()
    let overlapping = false
    for (const g of activeGroups) {
        for (const n of g.question_numbers) {
            if (seen.has(n)) overlapping = true
            seen.add(n)
        }
    }
    const malformed = activeGroups.some(
        (g) => g.choose_k < 1 || g.choose_k > g.question_numbers.length)
    if (overlapping || malformed) {
        return {
            sentence: COMPLETE_NOT_COMPUTABLE,
            needsLook: false,
            reasons: ['not_computable'],
        }
    }

    const reasons = new Set<CompletenessReason>()
    const inAGroup = seen

    // (1) Mandatory questions — in no group, so every leaf is owed and every
    //     missing one is named. A missing leaf inside a CHOSEN question that
    //     carries no sub-question id joins them: it is a real gap, and the
    //     «בשאלה 3 חסר ב» form has no letter to put in it, so naming it here is
    //     what stops it being dropped on the floor.
    const namedMissing = answers.filter(
        (a) => !inAGroup.has(a.question_number) && !answered(a))

    // (2)+(3) One clause per group, plus the real gaps inside chosen questions.
    // Overlap is impossible here (refused above), so each question is visited
    // by exactly one group and no gap can be reported twice.
    const clauses: string[] = []
    for (const g of activeGroups) {
        const attempted = g.question_numbers.filter(questionAnswered)
        let clause: string
        if (attempted.length < g.choose_k) {
            clause = COMPLETE_GROUP_SHORT(attempted.length, g.choose_k)
            reasons.add('group_short')
        } else if (attempted.length > g.choose_k) {
            clause = COMPLETE_GROUP_EXCESS(attempted.length, g.choose_k)
            reasons.add('group_excess')
        } else {
            clause = COMPLETE_GROUP_OK(g.choose_k, g.question_numbers.length)
        }

        // A partial answer inside a CHOSEN question is a real missing answer.
        for (const q of attempted) {
            const missing = (byQuestion.get(q) ?? []).filter((a) => !answered(a))
            const letters = missing
                .map((a) => a.sub_question_id)
                .filter((id): id is string => Boolean(id))
            for (const a of missing) {
                if (!a.sub_question_id) namedMissing.push(a)
            }
            if (letters.length > 0) {
                clause += COMPLETE_APPEND_SEP + COMPLETE_PARTIAL_QUESTION(q.toString(), letters.join(', '))
                reasons.add('partial_question')
            }
        }

        // Her own wording for the group, VERBATIM, when the contract carried
        // one. A single group needs no prefix; with several, the clauses are
        // unreadable without it. A group with no label gets no prefix rather
        // than an invented «קבוצה 1» (FC: never a value the teacher did not
        // write).
        clauses.push(
            activeGroups.length > 1 && g.label
                ? COMPLETE_GROUP_LABEL(g.label, clause)
                : clause,
        )
    }

    if (namedMissing.length > 0) reasons.add('missing_mandatory')

    const parts: string[] = []
    if (namedMissing.length > 0) {
        parts.push(COMPLETE_MISSING_PREFIX(namedMissing.map(leafKey).join(', ')))
    }
    parts.push(...clauses)

    // `group_excess` is SURFACED, not a shortfall (OD-6) — it never sends her
    // to a document, it only tells her what is there.
    const list = [...reasons]
    const needsLook = list.some((r) => r !== 'group_excess')
    return { sentence: parts.join(COMPLETE_CLAUSE_SEP), needsLook, reasons: list }
}
